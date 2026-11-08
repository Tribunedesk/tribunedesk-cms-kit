"""A small integration that does levels 1-3 and read mode right: the yardstick of `tdkit check`.

Standard library only. Posts live in a JSON file shared by the webhook server and the
developer commands:

    python reference_integration.py serve --port 8080 --store store.json [--no-verify]
        [--overwrite-older] [--empty-answer] [--any-image-host]
    python reference_integration.py inspect --store store.json <article_id>
    python reference_integration.py publish --store store.json <article_id>
    python reference_integration.py poll --store store.json

`TD_API_BASE` and `TD_CMS_TOKEN` point at the API (the mock); `TD_WEBHOOK_SECRET` is the
signing secret (default: the tdkit mock secret). The flags break one rule each, so the tests
can see `tdkit check` catch it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tdkit.signing import MOCK_SECRET, verify

LOCK = threading.Lock()


# -- store ---------------------------------------------------------------------------------


def load(store: Path) -> dict[str, Any]:
    if not store.exists():
        return {"posts": {}, "cursor": None}
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


def apply(
    article: dict[str, Any], data: dict[str, Any], *, overwrite_older: bool, any_host: bool = False
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
    post = existing or {"status": "draft", "permalink": None, "backlink_sources": []}
    image = (article.get("featured_image") or {}).get("url")
    if image and (any_host or urllib.parse.urlsplit(image).hostname in image_hosts()):
        with urllib.request.urlopen(image, timeout=10) as response:
            response.read()
    provenance = article.get("ai_provenance") or {}
    post.update(
        cms_post_id=post_id,
        edit_url=f"https://cms.example.com/posts/{post_id}/edit",
        sent_at=article["sent_at"],
        title=article["title"],
        html_raw=article["html"],
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
    posts[article_id] = post
    rerender(posts)
    return {
        "cms_post_id": post_id,
        "status": "updated" if existing else "created",
        "edit_url": post["edit_url"],
    }


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
    shown["read_more"] = sorted(
        other for other, p in posts.items() if article_id in p.get("backlink_sources", [])
    )
    return shown


def publish(data: dict[str, Any], article_id: str) -> None:
    post = data["posts"][article_id]
    post["status"] = "published"
    post["permalink"] = f"https://cms.example.com/{post['cms_post_id']}/"
    rerender(data["posts"])
    item = {"article_id": article_id, "url": post["permalink"], "social_queue_exclude": False}
    status, body, _ = api("POST", "/v3/cms/articles/published", {"items": [item]})
    if status != 200 or body["results"][0]["status"] != "ok":
        raise SystemExit(f"link back failed: {status} {body}")


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
    for name in ("inspect", "publish"):
        sub.add_parser(name).add_argument("article_id")
    sub.add_parser("poll")
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
        else:
            poll(data)
        save(store, data)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    main()
