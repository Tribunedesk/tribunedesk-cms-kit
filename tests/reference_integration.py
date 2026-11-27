"""A small integration that does levels 1-3 and read mode right: the yardstick of `tdkit check`.

Standard library only. Posts live in a JSON file shared by the webhook server and the
developer commands:

    python reference_integration.py serve --port 8080 --store store.json [--no-verify]
        [--overwrite-older] [--empty-answer] [--any-image-host] [--answer-500]
        [--keep-embeds] [--naive-embed-hosts] [--regex-embeds] [--ignore-publication] [--unpublish]
        [--create-terms] [--clear-missing-taxonomy]
    python reference_integration.py inspect --store store.json <article_id>
    python reference_integration.py publish --store store.json <article_id>
    python reference_integration.py poll --store store.json
    python reference_integration.py taxonomy-sync --store store.json [--no-is-last]

`TD_API_BASE` and `TD_CMS_TOKEN` point at the API (the mock); `TD_WEBHOOK_SECRET` is the
signing secret (default: the tdkit mock secret). The flags break one rule each, so the tests
can see `tdkit check` catch it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import nh3

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tdkit.signing import MOCK_SECRET, verify

LOCK = threading.Lock()


# -- store ---------------------------------------------------------------------------------


# The CMS's own categories and tags; Tribune Desk never adds to them (contract 3.8).
TERMS = {
    "category": {"1": "Uncategorized", "2": "Local politics"},
    "tag": {"10": "City budget", "11": "Łódź", "12": "Mayor", "13": "Kasia Nowak"},
}


def load(store: Path) -> dict[str, Any]:
    if not store.exists():
        return {"posts": {}, "cursor": None, "terms": json.loads(json.dumps(TERMS))}
    return json.loads(store.read_text(encoding="utf-8"))


def save(store: Path, data: dict[str, Any]) -> None:
    tmp = store.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, store)


# -- the API -------------------------------------------------------------------------------


def api(method: str, path: str, body: Any = None) -> tuple[int, Any, dict[str, str]]:
    base = os.environ["TD_API_BASE"].rstrip("/")
    request = urllib.request.Request(
        base + path,
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={
            "Authorization": f"Bearer {os.environ['TD_CMS_TOKEN']}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw, status, headers = response.read(), response.status, dict(response.headers)
    except urllib.error.HTTPError as exc:
        raw, status, headers = exc.read(), exc.code, dict(exc.headers)
    return status, json.loads(raw) if raw else None, headers


def image_hosts() -> list[str]:
    if not os.environ.get("TD_API_BASE"):
        return []
    status, body, _ = api("GET", "/v3/cms/status")
    return list(body.get("image_hosts") or []) if status == 200 else []


# -- applying a delivery -------------------------------------------------------------------


def render(post: dict[str, Any], posts: dict[str, Any]) -> str:
    """`html` with placeholders replaced by our addresses, or unwrapped (guide 3)."""
    html = post["html_raw"]
    for link in post.get("internal_links") or []:
        if not isinstance(link, dict) or link.get("kind") != "placeholder":
            continue
        target = posts.get(str(link.get("article_id")))
        href = re.escape(str(link.get("href")))
        pattern = re.compile(r"<a\s[^>]*href=\"" + href + r"\"[^>]*>(.*?)</a>", re.S)
        if target and target.get("status") == "published" and target.get("permalink"):
            html = html.replace(str(link["href"]), target["permalink"])
        else:
            html = pattern.sub(lambda m: m.group(1), html)
    return html


def rerender(posts: dict[str, Any]) -> None:
    for post in posts.values():
        post["html"] = render(post, posts)


# Guide 1, The HTML body (3.5): players we trust, compared with the trailing slash.
TRUSTED_PLAYERS = ("https://www.youtube.com/embed/", "https://player.vimeo.com/video/")
_SCRIPT = re.compile(r"<script\b[^>]*>.*?</script>", re.S | re.I)
_IFRAME = re.compile(r"<iframe\b[^>]*\bsrc=\"([^\"]*)\"[^>]*>.*?</iframe>", re.S | re.I)


_TAGS = {
    "p", "h2", "h3", "h4", "h5", "h6", "strong", "b", "em", "i", "u", "br", "hr", "ul", "ol",
    "li", "blockquote", "a", "figure", "figcaption", "img", "table", "thead", "tbody", "tfoot",
    "tr", "th", "td", "caption", "iframe",
}  # fmt: skip
_ATTRIBUTES = {
    "a": {"href", "target", "rel", "title"},
    "img": {"src", "alt", "width", "height"},
    "figure": {"class"},
    "iframe": {"src", "width", "height", "frameborder", "allowfullscreen", "allow", "title"},
}
_EMPTY_IFRAME = re.compile(r"<iframe\b(?![^>]*\ssrc=)[^>]*>.*?</iframe>", re.S)


def filter_embeds(
    html: str, *, keep_all: bool = False, naive_hosts: bool = False, regex: bool = False
) -> str:
    """Contract 3.9, complete-integration.md, Filtering the HTML: an allow list on a parser
    (nh3); iframes only from TRUSTED_PLAYERS. `regex` is the filter before tdkit 1.8 (scripts
    and iframes by regular expression), which the unsafe samples get through."""
    if keep_all:
        return html
    prefixes = (
        tuple(p.rstrip("/").rsplit("/", 1)[0] for p in TRUSTED_PLAYERS)
        if naive_hosts
        else TRUSTED_PLAYERS
    )
    if regex:
        html = _SCRIPT.sub("", html)
        return _IFRAME.sub(lambda m: m.group(0) if m.group(1).startswith(prefixes) else "", html)

    def keep(tag: str, attribute: str, value: str) -> str | None:
        if tag == "iframe" and attribute == "src" and not value.startswith(prefixes):
            return None
        return value

    clean = nh3.clean(
        html,
        tags=_TAGS,
        clean_content_tags={"script", "style", "object", "embed", "form", "svg", "math"},
        attributes=_ATTRIBUTES,
        generic_attribute_prefixes={"data-td-"},
        attribute_filter=keep,
        url_schemes={"http", "https", "mailto"},
        link_rel=None,
    )
    return _EMPTY_IFRAME.sub("", clean)


def _tls() -> ssl.SSLContext | None:
    """Trust the mock's test CA, as an integrator does in a test environment (D5)."""
    bundle = os.environ.get("TD_CA_BUNDLE")
    return ssl.create_default_context(cafile=bundle) if bundle else None


def apply(
    article: dict[str, Any],
    data: dict[str, Any],
    *,
    overwrite_older: bool,
    any_host: bool = False,
    download: bool = True,
    trust_ca: bool = True,
    keep_embeds: bool = False,
    naive_embed_hosts: bool = False,
    regex_embeds: bool = False,
    download_body_images: bool = False,
    ignore_publication: bool = False,
    unpublish: bool = False,
    create_terms: bool = False,
    clear_missing_taxonomy: bool = False,
) -> dict:
    posts = data["posts"]
    article_id = article["article_id"]
    existing = posts.get(article_id)
    if (
        existing
        and not overwrite_older
        and datetime.fromisoformat(article["sent_at"]) < datetime.fromisoformat(existing["sent_at"])
    ):
        return {"cms_post_id": existing["cms_post_id"], "edit_url": existing["edit_url"]}
    post_id = existing["cms_post_id"] if existing else str(len(posts) + 1)
    post = existing or {
        "status": "draft",
        "permalink": None,
        "backlink_sources": [],
        "categories": ["1"],
        "tags": [],
    }
    image = (article.get("featured_image") or {}).get("url")
    if image and download and (any_host or urllib.parse.urlsplit(image).hostname in image_hosts()):
        try:
            context = _tls() if trust_ca else None
            with urllib.request.urlopen(image, timeout=10, context=context) as response:
                response.read()
        except (urllib.error.URLError, OSError):
            pass  # an image that cannot be downloaded does not stop the draft
    if download_body_images:  # breaks l4-body-image: ignores data-td-cms-media-id
        for src in re.findall(r'<img [^>]*src="([^"]+)"', article["html"]):
            try:
                with urllib.request.urlopen(src, timeout=10, context=_tls()) as response:
                    response.read()
            except (urllib.error.URLError, OSError):
                pass
    provenance = article.get("ai_provenance") or {}
    post.update(
        cms_post_id=post_id,
        edit_url=f"https://cms.example.com/posts/{post_id}/edit",
        sent_at=article["sent_at"],
        title=article["title"],
        html_raw=filter_embeds(
            article["html"],
            keep_all=keep_embeds,
            naive_hosts=naive_embed_hosts,
            regex=regex_embeds,
        ),
        excerpt=article.get("excerpt"),
        featured_image_url=image,
        internal_links=article.get("internal_links") or [],
        seo_title=article.get("seo_title"),
        meta_description=article.get("meta_description"),
        language=article.get("language"),
        author=(article.get("author") or {}).get("name") or "Default author",
        ai_provenance_jws=provenance.get("jws"),
    )
    if article.get("backlink_sources") is not None:
        post["backlink_sources"] = [str(s["article_id"]) for s in article["backlink_sources"]]
    taxonomy = article.get("taxonomy")
    if clear_missing_taxonomy and not isinstance(taxonomy, dict):
        taxonomy = {"categories": [], "tags": []}  # breaks l3-taxonomy: a missing key is kept
    ignored = None
    if isinstance(taxonomy, dict):
        ignored = apply_taxonomy(post, taxonomy, data["terms"], create=create_terms)
    if not ignore_publication:
        apply_publication(post, article.get("publication"), unpublish=unpublish)
    posts[article_id] = post
    rerender(posts)
    answer = {
        "cms_post_id": post_id,
        "status": "updated" if existing else "created",
        "edit_url": post["edit_url"],
    }
    if not ignore_publication:
        answer["publication"] = publication_state(post)
    if ignored is not None:
        answer["taxonomy"] = taxonomy_state(post, data["terms"], ignored)
    return answer


def apply_taxonomy(
    post: dict[str, Any], taxonomy: dict[str, Any], terms: dict[str, Any], *, create: bool
) -> list[dict[str, str]]:
    """Contract 3.8: a present key replaces that taxonomy, a missing one leaves it alone; a term
    is found by `cms_term_id`, else by name ignoring case, and never created. Only a post that
    is not public changes. Returns `ignored`."""
    ignored: list[dict[str, str]] = []
    if post["status"] == "published":
        return ignored
    for key, name in (("categories", "category"), ("tags", "tag")):
        refs = taxonomy.get(key)
        if not isinstance(refs, list):
            continue
        other = terms["tag" if name == "category" else "category"]
        ids: list[str] = []
        for ref in refs:
            if not isinstance(ref, dict) or not isinstance(ref.get("name"), str):
                continue
            given = str(ref.get("cms_term_id") or "")
            folded = ref["name"].casefold()
            term_id = given if given in terms[name] else ""
            if not term_id:
                term_id = next((i for i, n in terms[name].items() if n.casefold() == folded), "")
            if not term_id and create:  # breaks l3-taxonomy: a CMS must never do this
                term_id = str(100 + sum(len(t) for t in terms.values()))
                terms[name][term_id] = ref["name"]
            if term_id:
                if term_id not in ids:
                    ids.append(term_id)
                continue
            elsewhere = given in other or any(n.casefold() == folded for n in other.values())
            reason = "wrong_taxonomy" if elsewhere else "unknown_term"
            ignored.append({"name": ref["name"], "reason": reason})
        post[key] = ids
    return ignored


def taxonomy_state(
    post: dict[str, Any], terms: dict[str, Any], ignored: list[dict[str, str]]
) -> dict[str, Any]:
    def named(key: str, name: str) -> list[dict[str, str]]:
        return [{"cms_term_id": i, "name": terms[name][i]} for i in post.get(key, [])]

    return {
        "categories": named("categories", "category"),
        "tags": named("tags", "tag"),
        "ignored": ignored,
    }


def apply_publication(post: dict[str, Any], publication: Any, *, unpublish: bool) -> None:
    """Contract 3.7: draft, schedule for `at` or publish now; a published post stays published."""
    if not isinstance(publication, dict):
        return  # no field: the post keeps the status it has
    if post["status"] == "published" and not unpublish:
        return
    mode = publication.get("mode")
    now = datetime.now(UTC)
    if mode == "schedule":
        at = datetime.fromisoformat(str(publication.get("at")).replace("Z", "+00:00"))
        if at > now:
            post.update(status="scheduled", publish_at=at.strftime("%Y-%m-%dT%H:%M:%SZ"))
            post["permalink"] = None
            return
        mode = "publish"  # a time already past is published at once
    if mode == "draft":
        post.update(status="draft", publish_at=None, permalink=None)
    elif mode == "publish":
        post.update(status="published", publish_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"))
        post["permalink"] = f"https://cms.example.com/{post['cms_post_id']}/"


def publication_state(post: dict[str, Any]) -> dict[str, Any]:
    if post["status"] in ("scheduled", "published"):
        return {"status": post["status"], "at": post.get("publish_at")}
    return {"status": "draft", "at": None}


def inspect(data: dict[str, Any], article_id: str) -> dict[str, Any] | None:
    posts = data["posts"]
    post = posts.get(article_id)
    if post is None:
        return None
    keys = [
        "cms_post_id",
        "title",
        "html",
        "excerpt",
        "status",
        "featured_image_url",
        "permalink",
        "seo_title",
        "meta_description",
        "language",
        "author",
        "ai_provenance_jws",
    ]
    shown = {key: post.get(key) for key in keys}
    terms = data["terms"]
    shown["categories"] = [terms["category"][i] for i in post.get("categories", [])]
    shown["tags"] = [terms["tag"][i] for i in post.get("tags", [])]
    # The box is part of the public page: it lists published articles on a published post, as
    # the WordPress plugin does.
    shown["read_more"] = sorted(
        other
        for other, p in posts.items()
        if article_id in p.get("backlink_sources", [])
        and p.get("status") == "published"
        and post.get("status") == "published"
    )
    return shown


def publish(data: dict[str, Any], article_id: str) -> None:
    post = data["posts"][article_id]
    post["status"] = "published"
    post["publish_at"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    post["permalink"] = f"https://cms.example.com/{post['cms_post_id']}/"
    rerender(data["posts"])
    item = {"article_id": article_id, "url": post["permalink"], "social_queue_exclude": False}
    status, body, _ = api("POST", "/v3/cms/articles/published", {"items": [item]})
    if status != 200 or body["results"][0]["status"] != "ok":
        raise SystemExit(f"link back failed: {status} {body}")


def taxonomy_sync(data: dict[str, Any], *, last: bool = True, size: int = 3) -> None:
    """One full run of every term, in pages of `size` (small, so a run has several pages)."""
    items = [
        {"taxonomy": name, "cms_term_id": term_id, "name": term}
        for name, found in data["terms"].items()
        for term_id, term in sorted(found.items(), key=lambda kv: int(kv[0]))
    ]
    run_id = str(uuid.uuid4())
    pages = [items[i : i + size] for i in range(0, len(items), size)] or [[]]
    for number, page in enumerate(pages, 1):
        body: dict[str, Any] = {"run_id": run_id, "items": page}
        if last and number == len(pages):
            body["is_last"] = True
        status, answer, _ = api("POST", "/v3/cms/taxonomy/terms", body)
        if status != 200:
            raise SystemExit(f"POST /taxonomy/terms answered {status}: {answer}")


# -- read mode -----------------------------------------------------------------------------


def handle_sent(data: dict[str, Any], article_id: str) -> None:
    for _ in range(3):
        status, article, headers = api("GET", f"/v3/cms/articles/{article_id}")
        if status != 200:
            return
        answer = apply(article, data, overwrite_older=False)
        delivery_id = headers.get("X-Delivery-Id")
        status, _, _ = api(
            "POST", f"/v3/cms/articles/{article_id}/result", {**answer, "delivery_id": delivery_id}
        )
        if status != 409:
            return


def poll(data: dict[str, Any]) -> None:
    cursor = data.get("cursor")
    while True:
        query = f"?cursor={urllib.parse.quote(cursor)}" if cursor else ""
        status, page, _ = api("GET", f"/v3/cms/changes{query}")
        if status == 410:
            after = ""
            while True:
                _, waiting, _ = api("GET", f"/v3/cms/articles/awaiting{after}")
                for item in waiting["items"]:
                    handle_sent(data, item["article_id"])
                if not waiting["next_cursor"]:
                    break
                after = f"?cursor={waiting['next_cursor']}"
            cursor = None
            continue
        if status != 200:
            raise SystemExit(f"GET /changes answered {status}: {page}")
        for change in page["changes"]:
            if change["kind"] == "article_sent":
                handle_sent(data, change["article_id"])
        cursor = page["next_cursor"]
        data["cursor"] = cursor
        if not page.get("has_more"):
            return


# -- the webhook server --------------------------------------------------------------------


def serve(args: argparse.Namespace) -> None:
    secret = os.environ.get("TD_WEBHOOK_SECRET", MOCK_SECRET)
    store = Path(args.store)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if args.answer_500:
                self._reply(500, {"error": "broken"})
                return
            if not args.no_verify and not verify(
                secret, dict(self.headers), body, now=int(time.time())
            ):
                self._reply(401, {"error": "invalid signature"})
                return
            article = json.loads(body)
            with LOCK:
                data = load(store)
                answer = apply(
                    article,
                    data,
                    overwrite_older=args.overwrite_older,
                    any_host=args.any_image_host,
                    download=not args.no_image_download,
                    trust_ca=not args.no_ca,
                    keep_embeds=args.keep_embeds,
                    naive_embed_hosts=args.naive_embed_hosts,
                    regex_embeds=args.regex_embeds,
                    download_body_images=args.download_body_images,
                    ignore_publication=args.ignore_publication,
                    unpublish=args.unpublish,
                    create_terms=args.create_terms,
                    clear_missing_taxonomy=args.clear_missing_taxonomy,
                )
                save(store, data)
            self._reply(200, None if args.empty_answer else answer)

        def _reply(self, status: int, data: Any) -> None:
            payload = b"" if data is None else json.dumps(data).encode()
            self.send_response(status)
            if payload:
                self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            pass

    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, required=True)
    s.add_argument("--no-verify", action="store_true")
    s.add_argument("--overwrite-older", action="store_true")
    s.add_argument("--empty-answer", action="store_true")
    s.add_argument("--any-image-host", action="store_true")
    s.add_argument("--no-image-download", action="store_true")
    s.add_argument("--no-ca", action="store_true")
    s.add_argument("--answer-500", action="store_true")
    s.add_argument("--keep-embeds", action="store_true")
    s.add_argument("--naive-embed-hosts", action="store_true")
    s.add_argument("--regex-embeds", action="store_true")
    s.add_argument("--download-body-images", action="store_true")
    s.add_argument("--ignore-publication", action="store_true")
    s.add_argument("--unpublish", action="store_true")
    s.add_argument("--create-terms", action="store_true")
    s.add_argument("--clear-missing-taxonomy", action="store_true")
    for name in ("inspect", "publish"):
        sub.add_parser(name).add_argument("article_id")
    sub.add_parser("poll")
    sub.add_parser("taxonomy-sync").add_argument("--no-is-last", action="store_true")
    for p in sub.choices.values():
        p.add_argument("--store", required=True)
    args = parser.parse_args()
    if args.command == "serve":
        serve(args)
        return
    store = Path(args.store)
    with LOCK:
        data = load(store)
        if args.command == "inspect":
            print(json.dumps(inspect(data, args.article_id), ensure_ascii=False))
            return
        if args.command == "publish":
            publish(data, args.article_id)
        elif args.command == "taxonomy-sync":
            taxonomy_sync(data, last=not args.no_is_last)
        else:
            poll(data)
        save(store, data)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    main()
