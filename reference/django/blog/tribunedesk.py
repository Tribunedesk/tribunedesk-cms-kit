"""Tribune Desk CMS API integration, levels 1 (article delivery) and 2 (link back).

Contract: .tribunedesk/cms-api@<tag>/guide/1-article-delivery.md and guide/2-link-back.md.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import logging
import time
from datetime import datetime

import requests
from django.conf import settings
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils.text import slugify

from .models import Post, TribuneDeskArticle

logger = logging.getLogger(__name__)

SECRET_PREFIX = "whsec_"
TOLERANCE_SECONDS = 300  # guide 1, "Verifying the signature", step 5
LINK_BACK_BATCH = 100  # guide 2: 1 to 100 items per request
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}  # README, "Retries"


class InvalidSignature(Exception):
    """The request is not signed by Tribune Desk, or is too old to trust."""


def signing_key(secret: str) -> bytes:
    """The HMAC key from a `whsec_` secret; `ValueError` when the secret is malformed."""
    if not secret.startswith(SECRET_PREFIX):
        raise ValueError("the signing secret must start with whsec_")
    try:
        return base64.b64decode(secret.removeprefix(SECRET_PREFIX), validate=True)
    except binascii.Error as exc:
        raise ValueError("the signing secret is not valid base64 after whsec_") from exc


def verify_signature(secret: str, headers, body: bytes, *, now: int | None = None) -> None:
    """Raise `InvalidSignature` unless `body` carries a valid Standard Webhooks signature."""
    msg_id = headers.get("webhook-id")
    timestamp = headers.get("webhook-timestamp")
    signatures = headers.get("webhook-signature")
    if not msg_id or not timestamp or not signatures:
        raise InvalidSignature("missing signature headers")
    try:
        sent = int(timestamp)
    except ValueError as exc:
        raise InvalidSignature("bad timestamp") from exc
    current = int(time.time()) if now is None else now
    if abs(current - sent) > TOLERANCE_SECONDS:
        raise InvalidSignature("timestamp outside the tolerance")

    signed = f"{msg_id}.{timestamp}.".encode() + body
    expected = base64.b64encode(hmac.new(signing_key(secret), signed, hashlib.sha256).digest())
    for entry in signatures.split(" "):
        version, _, value = entry.partition(",")
        if version == "v1" and hmac.compare_digest(value.encode(), expected):
            return
    raise InvalidSignature("no signature matches")


def edit_url(post: Post) -> str:
    # Built without a request: no editor is logged in during a delivery (guide 1, "edit_url").
    return settings.SITE_URL + reverse("admin:blog_post_change", args=[post.pk])


def permalink(post: Post) -> str | None:
    if post.status != Post.PUBLISHED:
        return None
    return settings.SITE_URL + post.get_absolute_url()


def _new_slug(title: str, article_id: str) -> str:
    base = slugify(title)[:250].strip("-")
    suffix = article_id.replace("-", "")[:8]
    return f"{base}-{suffix}" if base else f"td-{suffix}"


def _featured_image_url(article: dict) -> str:
    # Only the delivered URL is kept; the blog does not download or store images.
    image = article.get("featured_image")
    url = image.get("url") if isinstance(image, dict) else None
    return url if isinstance(url, str) else ""


def apply_delivery(article: dict, delivery_id: str) -> dict:
    """Create or update the draft made from `article`; return the webhook answer.

    Raises `ValueError` (or `KeyError`/`TypeError`) for a body without the level 1 fields.
    """
    article_id = str(article["article_id"])
    sent_at = datetime.fromisoformat(article["sent_at"])
    if sent_at.tzinfo is None:
        raise ValueError("sent_at has no time zone")
    title = article["title"]
    html = article["html"]
    if not isinstance(title, str) or not isinstance(html, str):
        raise ValueError("title and html must be text")
    excerpt = article.get("excerpt") or ""

    for attempt in range(2):
        try:
            with transaction.atomic():
                link = (
                    TribuneDeskArticle.objects.select_for_update()
                    .select_related("post")
                    .filter(article_id=article_id)
                    .first()
                )
                if link is None:
                    post = Post.objects.create(
                        title=title, slug=_new_slug(title, article_id), excerpt=excerpt,
                        body=html, status=Post.DRAFT,
                    )
                    TribuneDeskArticle.objects.create(
                        article_id=article_id, post=post, last_sent_at=sent_at,
                        last_delivery_id=delivery_id,
                        featured_image_url=_featured_image_url(article),
                    )
                    return _answer(post, "created")

                post = link.post
                if sent_at < link.last_sent_at:
                    # An attempt of an older send that arrived after a newer one (guide 1,
                    # "Order of sends"): keep the newer post.
                    return {"cms_post_id": str(post.pk), "edit_url": edit_url(post)}
                post.title, post.body, post.excerpt = title, html, excerpt
                post.save(update_fields=["title", "body", "excerpt"])
                link.last_sent_at = sent_at
                link.last_delivery_id = delivery_id
                link.featured_image_url = _featured_image_url(article)
                link.save(update_fields=["last_sent_at", "last_delivery_id", "featured_image_url"])
                return _answer(post, "updated")
        except IntegrityError:
            # Two attempts raced to create the same article; the second one updates.
            if attempt:
                raise
    raise AssertionError("unreachable")


def _answer(post: Post, status: str) -> dict:
    answer = {"cms_post_id": str(post.pk), "status": status, "edit_url": edit_url(post)}
    url = permalink(post)
    if url:
        answer["permalink"] = url
    return answer


# Level 2: link back.

def mark_link_back(post: Post) -> bool:
    """Queue the link back of a published post when its address is not reported yet."""
    url = permalink(post)
    if url is None:
        return False
    updated = (
        TribuneDeskArticle.objects.filter(post=post)
        .exclude(reported_url=url, link_back_error="")
        .update(link_back_pending=True)
    )
    return bool(updated)


def send_pending_link_backs() -> int:
    """Report every queued post to `POST /v3/cms/articles/published`; return how many were sent.

    A failure that may pass (network, 429, 5xx) leaves the item queued for the next run.
    """
    token = settings.TD_CMS_TOKEN
    if not token:
        logger.warning("TD_CMS_TOKEN is not set; link back skipped")
        return 0
    sent = 0
    while True:
        links = list(
            TribuneDeskArticle.objects.filter(link_back_pending=True)
            .select_related("post").order_by("pk")[:LINK_BACK_BATCH]
        )
        if not links:
            return sent
        items, by_id = [], {}
        for link in links:
            url = permalink(link.post)
            if url is None:  # unpublished meanwhile; nothing to report
                link.link_back_pending = False
                link.save(update_fields=["link_back_pending"])
                continue
            item = {"article_id": str(link.article_id), "url": url}
            if link.post.published_at:
                item["published_at"] = link.post.published_at.isoformat()
            items.append(item)
            by_id[item["article_id"]] = (link, url)
        if not items:
            continue
        try:
            response = requests.post(
                settings.TD_API_BASE.rstrip("/") + "/v3/cms/articles/published",
                json={"items": items},
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
        except requests.RequestException as exc:
            logger.warning("Tribune Desk link back failed, will retry: %s", exc)
            return sent
        if response.status_code in RETRYABLE_STATUSES:
            logger.warning("Tribune Desk link back answered %s, will retry", response.status_code)
            return sent
        if response.status_code != 200:
            # Other 4xx: do not retry unchanged (README, "Retries"); the error stays visible.
            error = f"HTTP {response.status_code}: {_error_code(response)}"
            logger.error("Tribune Desk link back rejected: %s", error)
            for link, _url in by_id.values():
                link.link_back_pending = False
                link.link_back_error = error
                link.save(update_fields=["link_back_pending", "link_back_error"])
            return sent
        results = {r.get("article_id"): r.get("status") for r in response.json().get("results", [])}
        for article_id, (link, url) in by_id.items():
            status = results.get(article_id)
            link.link_back_pending = False
            if status == "ok":
                link.reported_url, link.link_back_error = url, ""
                sent += 1
            else:
                # not_found / invalid_url: logged, not retried unchanged (guide 2, Done when).
                link.link_back_error = str(status)
                logger.error("Tribune Desk link back for %s: %s", article_id, status)
            link.save(update_fields=["link_back_pending", "reported_url", "link_back_error"])


def _error_code(response) -> str:
    try:
        return str(response.json().get("code", "unknown"))
    except ValueError:
        return "unknown"
