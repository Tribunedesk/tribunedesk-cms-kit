"""The conformance scenarios of tdkit 1.0: data records, each tied to a point of the guide.

`done_when` quotes the guide literally: a point of its "Done when" section, or, where that
section has no point for the behaviour, the sentence of the guide that requires it (then
`guide` names that section). `tests/test_check.py` checks every quote against the tag.
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Literal

from tdkit.check.context import Context, Fail, image_hosts_for
from tdkit.sender import DeliveryResult
from tdkit.signing import SECRET_PREFIX

G1 = "guide/1-article-delivery.md"
G2 = "guide/2-link-back.md"
G3 = "guide/3-full-content.md"

Mode = Literal["webhook", "read", "any"]


@dataclass(frozen=True)
class Scenario:
    id: str
    level: int
    mode: Mode
    done_when: str
    guide: str
    run: Callable[[Context], str]
    needs_social_flag: bool = False


# -- helpers -------------------------------------------------------------------------------


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def text_of(html: str) -> str:
    """The words of `html`, tags dropped and whitespace collapsed (a CMS may reformat tags)."""
    parser = _Text()
    parser.feed(html)
    return " ".join("".join(parser.parts).split())


def expect(condition: bool, detail: str) -> None:
    if not condition:
        raise Fail(detail)


def ids_from(*results: DeliveryResult) -> list[str]:
    return [
        str(r.json["cms_post_id"])
        for r in results
        if r.json is not None and r.json.get("cms_post_id") is not None
    ]


def placeholder_link(ctx: Context, target_id: str, anchor: str) -> tuple[str, dict[str, Any]]:
    prefix = ctx.opts.docs.sample_delivery["link_placeholder_prefix"]
    href = f"{prefix}{target_id}"
    html = f'<p>Read also <a href="{href}">{anchor}</a> today.</p>'
    link = {
        "article_id": target_id,
        "anchor_text": anchor,
        "href": href,
        "url": href,
        "kind": "placeholder",
        "headline": anchor,
    }
    return html, link


# -- level 1, webhook ----------------------------------------------------------------------


def creates_draft(ctx: Context) -> str:
    body = ctx.article()
    ctx.delivered(body)
    post = ctx.must_inspect(body["article_id"])
    expect(post.get("title") == body["title"], f"title is {post.get('title')!r}")
    expect(
        text_of(str(post.get("html") or "")) == text_of(body["html"]),
        f"html differs from the delivery: {str(post.get('html'))[:200]!r}",
    )
    expect(post.get("excerpt") == body["excerpt"], f"excerpt is {post.get('excerpt')!r}")
    expect(bool(post.get("featured_image_url")), "featured_image_url is empty")
    expect(post.get("status") != "published", "the post was published, not left as a draft")
    return f"draft {post.get('cms_post_id')!r} made"


def answer_fields(ctx: Context) -> str:
    result = ctx.delivered(ctx.article())
    answer = result.json
    expect(answer is not None, "the answer has no JSON object body")
    assert answer is not None
    post_id = answer.get("cms_post_id")
    expect(isinstance(post_id, str) and post_id != "", f"cms_post_id is {post_id!r}, not text")
    status = answer.get("status")
    expect(
        status in ("created", "updated", "skipped_already_published"),
        f"status is {status!r}",
    )
    edit_url = answer.get("edit_url")
    expect(
        isinstance(edit_url, str) and edit_url.startswith(("http://", "https://")),
        f"edit_url is {edit_url!r}, not an http(s) address",
    )
    return f"cms_post_id {post_id!r}, status {status!r}, edit_url {edit_url!r}"


def bad_signature(ctx: Context) -> str:
    body = ctx.article()
    wrong = SECRET_PREFIX + "dGRraXQtd3Jvbmctc2lnbmluZy1zZWNyZXQtMDAwMDAw"
    result = ctx.send(body, secrets=[wrong])
    expect(result.status == 401, f"a wrong signature got {result.status}, not 401")
    expect(ctx.inspect(body["article_id"]) is None, "a post was made from an unsigned request")
    return "401, no post"


def clock_skew(ctx: Context) -> str:
    body = ctx.article()
    result = ctx.send(body, timestamp=int(time.time()) - 301)
    expect(
        result.status == 401,
        f"a webhook-timestamp 301 s old got {result.status}, not 401",
    )
    expect(ctx.inspect(body["article_id"]) is None, "a post was made from a replayed request")
    return "401, no post (tdkit cannot see your clock: keep it in sync)"


def duplicate_attempt(ctx: Context) -> str:
    body = ctx.article()
    delivery_id = str(uuid.uuid4())
    first = ctx.delivered(body, delivery_id=delivery_id, attempt=1)
    second = ctx.delivered(body, delivery_id=delivery_id, attempt=2)
    post = ctx.must_inspect(body["article_id"])
    ids = {*ids_from(first, second), str(post.get("cms_post_id"))}
    expect(len(ids) == 1, f"two attempts gave different posts: {sorted(ids)}")
    return f"one post {ids.pop()!r}"


def resend_updates(ctx: Context) -> str:
    body = ctx.article(minutes=-10)
    ctx.delivered(body)
    before = ctx.must_inspect(body["article_id"])
    newer = {**body, "sent_at": ctx.sent_at(), "title": body["title"] + " (updated)"}
    ctx.delivered(newer)
    after = ctx.must_inspect(body["article_id"])
    expect(
        after.get("title") == newer["title"], f"title after the new send: {after.get('title')!r}"
    )
    expect(
        after.get("cms_post_id") == before.get("cms_post_id"),
        f"the new send made another post ({before.get('cms_post_id')!r} → "
        f"{after.get('cms_post_id')!r})",
    )
    return "the same post was updated"


def older_send_ignored(ctx: Context) -> str:
    base = ctx.article()
    newer = {**base, "title": base["title"] + " (newer send)"}
    ctx.delivered(newer)
    older = {**base, "sent_at": ctx.sent_at(-60), "title": base["title"] + " (older send)"}
    ctx.send(older)
    post = ctx.must_inspect(base["article_id"])
    expect(
        post.get("title") == newer["title"],
        f"the older send overwrote the post: title {post.get('title')!r}",
    )
    return "the newer send stays"


def overlapping_attempts(ctx: Context) -> str:
    body = ctx.article()
    delivery_id = str(uuid.uuid4())
    ctx.state.add_send(body, delivery_id=delivery_id)
    barrier = threading.Barrier(2)
    results: list[DeliveryResult] = []

    def attempt(number: int) -> None:
        barrier.wait()
        results.append(ctx.send(body, delivery_id=delivery_id, attempt=number))

    threads = [threading.Thread(target=attempt, args=(n,)) for n in (1, 2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    statuses = sorted(r.status or 0 for r in results)
    expect(any(200 <= s < 300 for s in statuses), f"neither attempt was answered 2xx: {statuses}")
    post = ctx.must_inspect(body["article_id"])
    ids = {*ids_from(*results), str(post.get("cms_post_id"))}
    expect(len(ids) == 1, f"two overlapping attempts gave different posts: {sorted(ids)}")
    return f"one post {ids.pop()!r} (answers {statuses})"


def unknown_fields(ctx: Context) -> str:
    body = ctx.article()
    body["tdkit_future_field"] = {"added_in": "a future minor version"}
    body["internal_links"] = [
        {
            "article_id": None,
            "anchor_text": "a future link",
            "href": "https://example.org/future",
            "url": "https://example.org/future",
            "kind": "tdkit_future_kind",
            "headline": None,
        }
    ]
    ctx.delivered(body)
    ctx.must_inspect(body["article_id"])
    return "accepted"


NON_ASCII_TITLE = "Zażółć gęślą jaźń — „test”"


def non_ascii(ctx: Context) -> str:
    body = ctx.article(title=NON_ASCII_TITLE)
    ctx.delivered(body)
    post = ctx.must_inspect(body["article_id"])
    expect(post.get("title") == NON_ASCII_TITLE, f"title came back as {post.get('title')!r}")
    return "title kept byte for byte"


def image_host(ctx: Context) -> str:
    body = ctx.article()
    name = f"{body['article_id']}-not-allowed.jpg"
    url = f"http://{ctx.forbidden_image_host}:{ctx.port}/files/{name}"
    body["featured_image"] = {**body["featured_image"], "url": url}
    body["generated_images"] = [body["featured_image"]]
    ctx.delivered(body)
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and not ctx.state.pulls.get(name):
        time.sleep(0.1)
    expect(not ctx.state.pulls.get(name), f"the integration downloaded {url}")
    return f"the image on {ctx.forbidden_image_host}, outside image_hosts, was not downloaded"


# -- level 1, read mode --------------------------------------------------------------------


def read_delivers_result(ctx: Context) -> str:
    body = ctx.article()
    send = ctx.state.add_send(body)
    ctx.poll()
    calls = [r for r in ctx.state.results if r.article_id == body["article_id"]]
    expect(bool(calls), "the integration reported no result for the send")
    ok = [r for r in calls if r.status == 200 and r.delivery_id == send.delivery_id]
    expect(bool(ok), f"no accepted result for the send (answers {[r.status for r in calls]})")
    expect(
        ok[-1].body.get("delivery_id") == send.delivery_id,
        "the result does not carry delivery_id (the X-Delivery-Id of GET /articles/{id})",
    )
    ctx.must_inspect(body["article_id"])
    return "result with delivery_id; post made"


def read_superseded(ctx: Context) -> str:
    body = ctx.article()
    first = ctx.state.add_send(body)
    ctx.state.supersede_after_get.add(body["article_id"])
    ctx.poll()
    ctx.poll()
    calls = [r for r in ctx.state.results if r.article_id == body["article_id"]]
    newest = ctx.state.newest_send(body["article_id"])
    assert newest is not None
    expect(newest.delivery_id != first.delivery_id, "the integration never fetched the article")
    expect(
        any(r.status == 409 and r.delivery_id == first.delivery_id for r in calls),
        "no result for the replaced send got 409: send delivery_id with every result",
    )
    accepted = [r for r in calls if r.status == 200]
    expect(bool(accepted), "no result was accepted after the 409")
    expect(
        accepted[-1].delivery_id == newest.delivery_id,
        "the last accepted result is not for the newer send",
    )
    return "409 for the replaced send, then the newer send reported"


def read_cursor_expired(ctx: Context) -> str:
    ctx.poll()  # the integration now holds a cursor
    body = ctx.article()
    send = ctx.state.add_send(body)
    ctx.state.expire_cursor_once = True
    mark = len(ctx.state.calls)
    ctx.poll()
    if ctx.state.expire_cursor_once:
        ctx.state.expire_cursor_once = False
        raise Fail("the integration polled GET /changes without its cursor; keep the cursor")
    later = ctx.state.calls[mark:]
    expect(
        any(path == "/v3/cms/articles/awaiting" for _, path, _ in later),
        "after 410 the integration did not list GET /v3/cms/articles/awaiting",
    )
    expect(
        any(r.status == 200 and r.delivery_id == send.delivery_id for r in ctx.state.results),
        "the waiting send was not reported after 410",
    )
    return "410 → /awaiting → result"


# -- level 2 -------------------------------------------------------------------------------


def _published_post(ctx: Context) -> tuple[dict[str, Any], dict[str, Any]]:
    body = ctx.article()
    ctx.delivered(body)
    ctx.publish(body["article_id"])
    post = ctx.must_inspect(body["article_id"])
    return body, post


def reports_url(ctx: Context) -> str:
    body, post = _published_post(ctx)
    permalink = post.get("permalink")
    expect(isinstance(permalink, str) and bool(permalink), f"permalink is {permalink!r}")
    reported = ctx.state.published.get(body["article_id"])
    expect(reported is not None, "the published post was not reported to Tribune Desk")
    assert reported is not None
    expect(
        reported["url"] == permalink,
        f"reported {reported['url']!r}, but the post is at {permalink!r}",
    )
    return f"reported {permalink!r}"


def repeat_is_harmless(ctx: Context) -> str:
    body, post = _published_post(ctx)
    ctx.publish(body["article_id"])
    again = ctx.must_inspect(body["article_id"])
    reported = ctx.state.published.get(body["article_id"])
    expect(reported is not None, "the published post was not reported to Tribune Desk")
    assert reported is not None
    expect(
        reported["url"] == again.get("permalink") == post.get("permalink"),
        f"after the repeat: reported {reported['url']!r}, post at {again.get('permalink')!r}",
    )
    return "the repeat changed nothing"


def social_flag(ctx: Context) -> str:
    body, _ = _published_post(ctx)
    reports = ctx.state.reports.get(body["article_id"], [])
    expect(bool(reports), "the published post was not reported to Tribune Desk")
    missing = [r["source"] for r in reports if not isinstance(r["social_queue_exclude"], bool)]
    expect(not missing, f"social_queue_exclude missing in: {', '.join(missing)}")
    return f"{len(reports)} report(s), each with social_queue_exclude"


# -- level 3 -------------------------------------------------------------------------------


def placeholder_unwrapped(ctx: Context) -> str:
    target = str(uuid.uuid4())
    anchor = "an article your CMS does not have"
    html, link = placeholder_link(ctx, target, anchor)
    body = ctx.article(html=html, internal_links=[link])
    ctx.delivered(body)
    ctx.publish(body["article_id"])
    post = ctx.must_inspect(body["article_id"])
    stored = str(post.get("html") or "")
    expect(link["href"] not in stored, "the placeholder link is still in html")
    expect(anchor in text_of(stored), "the link text was dropped with the link")
    return "link dropped, text kept"


def placeholder_resolved_later(ctx: Context) -> str:
    target = ctx.article()
    ctx.delivered(target)
    ctx.publish(target["article_id"])
    permalink = ctx.must_inspect(target["article_id"]).get("permalink")
    expect(isinstance(permalink, str) and bool(permalink), f"the target's permalink: {permalink!r}")
    html, link = placeholder_link(ctx, target["article_id"], "the published target")
    body = ctx.article(html=html, internal_links=[link])
    ctx.delivered(body)
    ctx.publish(body["article_id"])
    stored = str(ctx.must_inspect(body["article_id"]).get("html") or "")
    expect(link["href"] not in stored, "the placeholder link is still in html")
    expect(
        re.search(r"href=[\"']" + re.escape(str(permalink)) + r"[\"']", stored) is not None,
        f"html does not link to the target's permalink {permalink!r}",
    )
    return f"placeholder replaced with {permalink!r}"


def backlinks_rules(ctx: Context) -> str:
    older = ctx.article(minutes=-30)
    ctx.delivered(older)
    newer = ctx.article(
        minutes=-20, backlink_sources=[{"article_id": older["article_id"], "distance": 0.2}]
    )
    ctx.delivered(newer)
    steps: list[tuple[str, dict[str, Any], list[str]]] = [
        ("a list", newer, [newer["article_id"]]),
    ]
    without = {k: v for k, v in newer.items() if k != "backlink_sources"}
    steps.append(("a missing key", {**without, "sent_at": ctx.sent_at(-10)}, [newer["article_id"]]))
    steps.append(("an empty list", {**newer, "sent_at": ctx.sent_at(), "backlink_sources": []}, []))
    for index, (what, body, expected) in enumerate(steps):
        if index:
            ctx.delivered(body)
        box = ctx.must_inspect(older["article_id"]).get("read_more")
        expect(isinstance(box, list), f"read_more of the older post is {box!r}, not a list")
        assert isinstance(box, list)
        expect(
            sorted(map(str, box)) == expected,
            f"after {what}: the older post's read_more is {box}, expected {expected}",
        )
    return "list, missing key and empty list followed"


def seo_author_language(ctx: Context) -> str:
    sample = ctx.opts.docs.sample_delivery
    body = ctx.article(
        seo_title=sample["seo_title"],
        meta_description=sample["meta_description"],
        language=sample["language"],
        author=sample["author"],
    )
    ctx.delivered(body)
    post = ctx.must_inspect(body["article_id"])
    for key in ("seo_title", "meta_description", "language"):
        expect(post.get(key) == body[key], f"{key} is {post.get(key)!r}, not {body[key]!r}")
    expect(bool(post.get("author")), "author is empty")
    return "seo_title, meta_description, language and author stored"


def ai_label(ctx: Context) -> str:
    sample = ctx.opts.docs.sample_delivery
    provenance = sample["ai_provenance"]
    block = sample["html"][sample["html"].index("<script") :]
    body = ctx.article(ai_provenance=provenance)
    body["html"] = body["html"] + "\n" + block
    ctx.delivered(body)
    ctx.publish(body["article_id"])
    post = ctx.must_inspect(body["article_id"])
    expect(
        post.get("ai_provenance_jws") == provenance["jws"],
        f"ai_provenance_jws is {post.get('ai_provenance_jws')!r}",
    )
    return "the AI label's JWS is on the post"


# -- the list ------------------------------------------------------------------------------

DW1 = f"{G1}#done-when"
DW2 = f"{G2}#done-when"
DW3 = f"{G3}#done-when"
READ = f"{G1}#level-1-without-a-public-endpoint-read-mode"

D1_DRAFT = (
    "An editor's “Send to CMS” makes a draft post with `title`, `html`, `excerpt` and "
    "`featured_image`."
)
D1_ANSWER = (
    "Your answer carries `cms_post_id`, `status` and `edit_url`, so the editor gets an "
    "“Edit in CMS” link."
)
D1_401 = (
    "A request whose signature does not verify, or whose `webhook-timestamp` is more than "
    "5 minutes off, gets `401` and changes nothing."
)
D1_REPEAT = (
    "A repeated attempt with the same `webhook-id` makes no second draft, and a new send of "
    "the same `article_id` updates the post you made the first time."
)
D1_UNKNOWN = (
    "Fields you do not know are ignored, not rejected; do not validate the body with a schema "
    "that rejects unknown properties."
)
D1_OLDER = "An attempt of an older send that arrives after a newer one does not overwrite the post."
D1_IMAGES = "Download images only from these hosts and refuse any other address."
D1_OVERLAP = (
    "Keep `article_id` unique in your database and lock the row while you write, or you get "
    "two posts."
)
R_RESULT = (
    "The body (`ArticleResultReport`) is what your webhook would answer with, plus "
    "`delivery_id`: the `X-Delivery-Id` from step 2."
)
R_409 = (
    "With it the result closes exactly that send; if a newer send of the article replaced it "
    "you get `409` with `state_conflict` and nothing is stored, so fetch the article again."
)
R_410 = (
    "List the sends still waiting with `GET /v3/cms/articles/awaiting` (`articles:read`, "
    "oldest first, pages with `next_cursor`), handle each as in steps 2 and 3, then poll "
    "`GET /changes` again without a cursor."
)
D2_REPORTED = (
    "Every post made from a delivered article is reported once it is public, either by "
    "`permalink` in the delivery answer or by `POST /v3/cms/articles/published`."
)
D2_REPEAT = (
    "Reporting the same post again does no harm, and an item answered `not_found` or "
    "`invalid_url` is logged, not retried unchanged."
)
D2_SOCIAL = (
    "Once your CMS has the setting, send the field every time, also as `false`; otherwise "
    "clearing the setting never reaches Tribune Desk."
)
D3_LINKS = (
    "Placeholders are replaced with your addresses, or the link text is left without a link."
)
D3_BOX = (
    "The “read more” box follows `backlink_sources`, including the missing-key and "
    "empty-list rules."
)
D3_SEO = "SEO fields, author and language are stored on the post."
D3_AI = (
    "The AI label is in the `<head>` of every public page made from a delivery whose "
    "`ai_provenance` is not `null`."
)

__all__ = ["SCENARIOS", "Scenario", "image_hosts_for"]

SCENARIOS: tuple[Scenario, ...] = (
    Scenario("l1-creates-draft", 1, "webhook", D1_DRAFT, DW1, creates_draft),
    Scenario("l1-answer-fields", 1, "webhook", D1_ANSWER, DW1, answer_fields),
    Scenario("l1-bad-signature", 1, "webhook", D1_401, DW1, bad_signature),
    Scenario("l1-clock-skew", 1, "webhook", D1_401, DW1, clock_skew),
    Scenario("l1-duplicate-attempt", 1, "webhook", D1_REPEAT, DW1, duplicate_attempt),
    Scenario("l1-resend-updates", 1, "webhook", D1_REPEAT, DW1, resend_updates),
    Scenario("l1-older-send-ignored", 1, "webhook", D1_OLDER, DW1, older_send_ignored),
    Scenario(
        "l1-overlapping-attempts",
        1,
        "webhook",
        D1_OVERLAP,
        f"{G1}#article-delivery-webhook",
        overlapping_attempts,
    ),
    Scenario("l1-unknown-fields", 1, "webhook", D1_UNKNOWN, DW1, unknown_fields),
    Scenario("l1-non-ascii", 1, "webhook", D1_DRAFT, DW1, non_ascii),
    Scenario("l1-image-host", 1, "webhook", D1_IMAGES, f"{G1}#where-images-come-from", image_host),
    Scenario("read-delivers-result", 1, "read", R_RESULT, READ, read_delivers_result),
    Scenario("read-superseded-409", 1, "read", R_409, READ, read_superseded),
    Scenario("read-cursor-expired", 1, "read", R_410, READ, read_cursor_expired),
    Scenario("l2-reports-url", 2, "any", D2_REPORTED, DW2, reports_url),
    Scenario("l2-repeat-is-harmless", 2, "any", D2_REPEAT, DW2, repeat_is_harmless),
    Scenario(
        "l2-social-flag",
        2,
        "any",
        D2_SOCIAL,
        f"{G2}#keeping-a-post-off-facebook",
        social_flag,
        needs_social_flag=True,
    ),
    Scenario("l3-placeholder-unwrapped", 3, "any", D3_LINKS, DW3, placeholder_unwrapped),
    Scenario("l3-placeholder-resolved-later", 3, "any", D3_LINKS, DW3, placeholder_resolved_later),
    Scenario("l3-backlinks-rules", 3, "any", D3_BOX, DW3, backlinks_rules),
    Scenario("l3-seo-author-language", 3, "any", D3_SEO, DW3, seo_author_language),
    Scenario("l3-ai-label", 3, "any", D3_AI, DW3, ai_label),
)
