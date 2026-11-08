"""Run `tdkit check` on the official Python examples of a contract tag.

The examples (`examples/python/level1_receiver.py`, `level2_link_back.py`) keep posts in
memory and run one process each, so this harness wraps their functions: a webhook server
around `level1_receiver.handle_delivery`, and the developer commands `tdkit check` needs.
Posts live in one JSON file shared by the server and the commands. Nothing here changes what
the examples do; when an example fails a scenario, that is a finding about the example (or
the mock), not something to work around here.

    python ci/example_harness.py serve --examples DOCS/examples/python --store S --port 8080
    python ci/example_harness.py inspect --examples ... --store S <article_id>
    python ci/example_harness.py publish --examples ... --store S <article_id>

`TD_WEBHOOK_SECRET` (default: the tdkit mock secret), `TD_API_BASE` and `TD_CMS_TOKEN` (set
by `tdkit check` for the commands).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import ModuleType
from typing import Any

# The tdkit mock's public test secret (tdkit.signing.MOCK_SECRET), spelled out so the harness
# runs with the examples' standard library only.
MOCK_SECRET = "whsec_dGRraXQtbW9jay1zaWduaW5nLXNlY3JldC0wMDAwMDA="


def load_module(examples: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, examples / f"{name}.py")
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {name} from {examples}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load(store: Path) -> dict[str, dict[str, Any]]:
    if not store.exists():
        return {}
    posts = json.loads(store.read_text(encoding="utf-8"))
    for post in posts.values():
        post["sent_at"] = datetime.fromisoformat(post["sent_at"])
    return posts


def save(store: Path, posts: dict[str, dict[str, Any]]) -> None:
    plain = {
        article_id: {**post, "sent_at": post["sent_at"].isoformat()}
        for article_id, post in posts.items()
    }
    tmp = store.with_suffix(".tmp")
    tmp.write_text(json.dumps(plain, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, store)


def serve(args: argparse.Namespace) -> None:
    receiver = load_module(args.examples, "level1_receiver")
    secret = os.environ.get("TD_WEBHOOK_SECRET", MOCK_SECRET)
    receiver.check_secret(secret)
    store_path: Path = args.store

    class Handler(BaseHTTPRequestHandler):
        # Mirrors level1_receiver.main(): the same answers for the same errors.
        def do_POST(self) -> None:
            try:
                body = self.rfile.read(receiver.content_length(self.headers.get("Content-Length")))
                store = load(store_path)
                answer = receiver.handle_delivery(
                    body, dict(self.headers), secret=secret, store=store
                )
                save(store_path, store)
            except receiver.BodyTooLarge:
                self._reply(413, {"error": "body too large"})
                return
            except receiver.InvalidSignature:
                self._reply(401, {"error": "invalid signature"})
                return
            except (ValueError, KeyError, TypeError):
                self._reply(400, {"error": "invalid body"})
                return
            self._reply(200, answer)

        def _reply(self, status: int, data: dict[str, Any]) -> None:
            payload = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            pass

    # One request at a time, as the example's own HTTPServer does.
    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


def inspect(args: argparse.Namespace) -> None:
    post = load(args.store).get(args.article_id)
    if post is None:
        print("null")
        return
    shown = {
        "cms_post_id": post["cms_post_id"],
        "title": post["title"],
        "html": post["html"],
        "excerpt": post["excerpt"],
        "status": post["state"],
        "featured_image_url": post["featured_image_url"],
        "permalink": post.get("permalink"),
    }
    print(json.dumps(shown, ensure_ascii=False))


def publish(args: argparse.Namespace) -> None:
    link_back = load_module(args.examples, "level2_link_back")
    posts = load(args.store)
    post = posts[args.article_id]
    post["state"] = "published"
    post["permalink"] = f"https://cms.example.com/posts/{post['cms_post_id']}/"
    save(args.store, posts)
    item = {"article_id": args.article_id, "url": post["permalink"]}
    answer = link_back.report_published(
        os.environ["TD_API_BASE"], os.environ["TD_CMS_TOKEN"], [item]
    )
    results = [r["status"] for r in answer["results"]]
    if results != ["ok"]:
        raise SystemExit(f"link back answered {results}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    serve_cmd = sub.add_parser("serve")
    serve_cmd.add_argument("--port", type=int, default=8080)
    sub.add_parser("inspect").add_argument("article_id")
    sub.add_parser("publish").add_argument("article_id")
    for command in sub.choices.values():
        command.add_argument("--examples", type=Path, required=True)
        command.add_argument("--store", type=Path, required=True)
    args = parser.parse_args()
    {"serve": serve, "inspect": inspect, "publish": publish}[args.command](args)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    main()
