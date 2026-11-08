"""HTTP server of the mock: the `/v3/cms` routes of levels 1-3 and read mode, on 127.0.0.1 only.

Request bodies are validated with the schemas of the tag's OpenAPI document, literally,
including `additionalProperties`. Order of checks as in the contract README: a malformed
JSON body 422, then 401 (token), 403 (scope), 422 (shape), 409 (state). Every other route
of the OpenAPI document checks the token and answers 501 `not_implemented`.
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from collections.abc import Callable
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry
from referencing.jsonschema import DRAFT202012

from tdkit.docs import ContractDocs
from tdkit.mock.state import ORG_CODE, MockState, ResultCall, now_iso
from tdkit.sender import deliver
from tdkit.signing import MOCK_SECRET

HOST = "127.0.0.1"
OPENAPI_URI = "urn:tdkit:openapi"

# Smallest valid JPEG (1x1, grey): what `/files/<name>` serves.
JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c140d0c0b0b0c"
    "1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffc000"
    "0b080001000101011100ffc4001f0000010501010101010100000000000000000102030405060708090a0bffc400"
    "b5100002010303020403050504040000017d01020300041105122131410613516107227114328191a1082342b1c1"
    "1552d1f02433627282090a161718191a25262728292a3435363738393a434445464748494a535455565758595a63"
    "6465666768696a737475767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6"
    "b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffda0008"
    "010100003f00fbd3ffd9"
)

FORMATS = FormatChecker()


@FORMATS.checks("date-time", raises=ValueError)
def _date_time(value: object) -> bool:
    """RFC 3339 date-time: jsonschema checks it only with an optional extra package."""
    if not isinstance(value, str):
        return True
    if "T" not in value.upper():
        raise ValueError("not a date-time")
    moment = datetime.fromisoformat(value.replace("z", "Z"))
    if moment.tzinfo is None:
        raise ValueError("a date-time needs a time zone")
    return True


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class Answer:
    def __init__(self, status: int, body: Any, headers: dict[str, str] | None = None) -> None:
        self.status, self.body, self.headers = status, body, headers or {}


class _Request:
    def __init__(
        self,
        method: str,
        path: str,
        query: dict[str, list[str]],
        raw: bytes,
        token: str | None,
        match: re.Match[str],
    ) -> None:
        self.method, self.path, self.query, self.raw = method, path, query, raw
        self.token, self.match = token, match


class MockServer:
    """The mock API over one `MockState`; `start()` returns `(host, port)`."""

    def __init__(
        self,
        state: MockState,
        docs: ContractDocs,
        port: int = 0,
        *,
        webhook: str | None = None,
        secrets: list[str] | None = None,
    ) -> None:
        self.state, self.docs, self.port = state, docs, port
        self.webhook = webhook
        self.secrets = secrets or [MOCK_SECRET]
        registry: Registry = Registry().with_resource(
            OPENAPI_URI, DRAFT202012.create_resource(docs.openapi)
        )
        self._validators: dict[str, Draft202012Validator] = {}
        for name in ("PublishedArticlesRequest", "ArticleResultReport"):
            self._validators[name] = Draft202012Validator(
                {"$ref": f"{OPENAPI_URI}#/components/schemas/{name}"},
                registry=registry,
                format_checker=FORMATS,
            )
        self._result_fields = set(
            docs.openapi["components"]["schemas"]["ArticleResultReport"]["properties"]
        )
        self._routes: list[tuple[str, re.Pattern[str], Callable[[_Request], Answer]]] = [
            ("GET", re.compile(r"/v3/cms/status"), self._status),
            ("GET", re.compile(r"/v3/cms/changes"), self._changes),
            ("GET", re.compile(r"/v3/cms/articles/awaiting"), self._awaiting),
            ("POST", re.compile(r"/v3/cms/articles/published"), self._published),
            ("GET", re.compile(r"/v3/cms/articles/(?P<article_id>[^/]+)"), self._article),
            ("POST", re.compile(r"/v3/cms/articles/(?P<article_id>[^/]+)/result"), self._result),
            ("GET", re.compile(r"/v3/cms/openapi\.json"), self._openapi),
            ("POST", re.compile(r"/_tdkit/send"), self._control_send),
        ]
        self._planned = [
            (method.upper(), re.compile(re.sub(r"\{[^}]+\}", "[^/]+", path)))
            for path, ops in docs.openapi["paths"].items()
            for method in ops
            if method in ("get", "post", "put", "delete", "patch")
        ]
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # -- lifecycle -------------------------------------------------------------------------

    def start(self) -> tuple[str, int]:
        mock = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:
                mock._handle(self, "GET")

            def do_POST(self) -> None:
                mock._handle(self, "POST")

            def do_PUT(self) -> None:
                mock._handle(self, "PUT")

            def do_DELETE(self) -> None:
                mock._handle(self, "DELETE")

            def log_message(self, format: str, *args: object) -> None:
                pass

        self._server = ThreadingHTTPServer((HOST, self.port), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(
            target=self._server.serve_forever, args=(0.05,), daemon=True
        )
        self._thread.start()
        return HOST, self.bound_address()[1]

    def bound_address(self) -> tuple[str, int]:
        if self._server is None:
            raise RuntimeError("the mock is not running")
        host, port = self._server.server_address[:2]
        return str(host), int(port)

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    def serve_forever(self) -> None:
        """Block until interrupted (`tdkit mock`)."""
        # join() with a timeout, so Ctrl+C reaches the main thread on Windows too.
        while self._thread is not None and self._thread.is_alive():
            self._thread.join(0.5)

    # -- dispatch --------------------------------------------------------------------------

    def _handle(self, handler: BaseHTTPRequestHandler, method: str) -> None:
        parts = urlsplit(handler.path)
        path = parts.path
        length = handler.headers.get("Content-Length")
        raw = handler.rfile.read(int(length)) if length and length.isdigit() else b""
        if method == "GET" and path.startswith("/files/"):
            self._file(handler, path.removeprefix("/files/"))
            return
        auth = handler.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else None
        try:
            answer = self._dispatch(method, path, parse_qs(parts.query), raw, token)
        except ApiError as exc:
            answer = Answer(exc.status, {"code": exc.code, "message": exc.message})
        self.state.record_call(method, path, answer.status)
        payload = json.dumps(answer.body).encode()
        handler.send_response(answer.status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(payload)))
        for key, value in answer.headers.items():
            handler.send_header(key, value)
        handler.end_headers()
        handler.wfile.write(payload)

    def _dispatch(
        self, method: str, path: str, query: dict[str, list[str]], raw: bytes, token: str | None
    ) -> Answer:
        if raw:
            try:
                json.loads(raw)
            except ValueError:
                raise ApiError(422, "validation_error", "the body is not valid JSON") from None
        for route_method, pattern, action in self._routes:
            match = pattern.fullmatch(path)
            if match and route_method == method:
                return action(_Request(method, path, query, raw, token, match))
        for route_method, pattern in self._planned:
            if route_method == method and pattern.fullmatch(path):
                self._scopes(token)
                raise ApiError(
                    501, "not_implemented", f"{method} {path} is not part of the tdkit mock"
                )
        raise ApiError(404, "not_found", f"no route {method} {path}")

    # -- checks ----------------------------------------------------------------------------

    def _scopes(self, token: str | None) -> set[str]:
        scopes = self.state.tokens.get(token or "")
        if scopes is None:
            raise ApiError(401, "unauthorized", "token missing, unknown or revoked")
        return scopes

    def _require(self, request: _Request, *any_of: str) -> set[str]:
        scopes = self._scopes(request.token)
        if not scopes.intersection(any_of):
            raise ApiError(403, "forbidden", f"the token needs {' or '.join(any_of)}")
        return scopes

    def _body(self, request: _Request, schema: str) -> dict[str, Any]:
        body = json.loads(request.raw) if request.raw else None
        errors = sorted(self._validators[schema].iter_errors(body), key=lambda e: list(e.path))
        if errors:
            first = errors[0]
            where = "/".join(str(p) for p in first.absolute_path) or "body"
            raise ApiError(422, "validation_error", f"{where}: {first.message}")
        assert isinstance(body, dict)
        return body

    def _article_id(self, request: _Request) -> str:
        value = request.match.group("article_id")
        try:
            return str(uuid.UUID(value))
        except ValueError:
            raise ApiError(422, "validation_error", "article_id: not a UUID") from None

    def _int_param(self, request: _Request, name: str, default: int, maximum: int) -> int:
        values = request.query.get(name)
        if not values:
            return default
        value = values[0]
        if not (value.isascii() and value.isdigit()) or not 1 <= int(value) <= maximum:
            raise ApiError(422, "validation_error", f"{name}: an integer from 1 to {maximum}")
        return int(value)

    # -- routes ----------------------------------------------------------------------------

    def _status(self, request: _Request) -> Answer:
        scopes = self._require(request, "media:read", "articles:read")
        enabled = self.state.integration_enabled
        with self.state.lock:
            pending = len([c for c in self.state.changes if c.seq > self.state.floor])
        return Answer(
            200,
            {
                "org_code": ORG_CODE,
                "contract_version": self.docs.version,
                "scopes": sorted(scopes),
                "state": "active" if enabled else "disabled",
                "image_hosts": list(self.state.image_hosts),
                "last_changes_poll_at": self.state.last_changes_poll_at if enabled else None,
                "pending_changes": pending if enabled else None,
                "held_batches": 0 if enabled else None,
                "recent_errors": [],
            },
        )

    def _changes(self, request: _Request) -> Answer:
        scopes = self._require(request, "media:read", "articles:read")
        limit = self._int_param(request, "limit", 100, 500)
        if not self.state.integration_enabled:
            raise ApiError(409, "state_conflict", "the integration is not enabled")
        cursor = (request.query.get("cursor") or [None])[0]
        state = self.state
        with state.lock:
            state.last_changes_poll_at = now_iso()
            if cursor is None:
                start = state.floor
            else:
                if not re.fullmatch(r"c\d+", cursor):
                    raise ApiError(422, "validation_error", "cursor: not a cursor of this feed")
                start = int(cursor[1:])
                if state.expire_cursor_once:
                    state.expire_cursor_once = False
                    state.floor = state.seq
                    raise ApiError(410, "cursor_expired", "the cursor has expired")
                if start < state.floor:
                    raise ApiError(410, "cursor_expired", "the cursor has expired")
            after = [c for c in state.changes if c.seq > max(start, state.floor)]
            page, more = after[:limit], len(after) > limit
            visible = [c for c in page if c.kind != "article_sent" or "articles:read" in scopes]
            next_cursor = page[-1].cursor if page else f"c{max(start, state.floor)}"
        return Answer(
            200,
            {
                "changes": [
                    {
                        "cursor": c.cursor,
                        "kind": c.kind,
                        "changed_at": c.changed_at,
                        "article_id": c.article_id,
                    }
                    for c in visible
                ],
                "next_cursor": next_cursor,
                "has_more": more,
            },
        )

    def _awaiting(self, request: _Request) -> Answer:
        self._require(request, "articles:read")
        limit = self._int_param(request, "limit", 100, 100)
        cursor = (request.query.get("cursor") or [None])[0]
        waiting = self.state.awaiting()
        if cursor is not None:
            # The cursor names the last send of the previous page, not an offset: sends
            # reported meanwhile leave the list without moving the next page.
            last = (
                self.state.send_by_seq(int(cursor[1:])) if re.fullmatch(r"a\d+", cursor) else None
            )
            if last is None:
                raise ApiError(422, "validation_error", "cursor: not a cursor of this list")
            waiting = [s for s in waiting if s.key > last.key]
        page = waiting[:limit]
        more = len(waiting) > limit
        return Answer(
            200,
            {
                "items": [
                    {"article_id": s.article_id, "delivery_id": s.delivery_id, "sent_at": s.sent_at}
                    for s in page
                ],
                "next_cursor": f"a{page[-1].seq}" if more else None,
            },
        )

    def _article(self, request: _Request) -> Answer:
        self._require(request, "articles:read")
        article_id = self._article_id(request)
        send = self.state.newest_send(article_id)
        if send is None:
            raise ApiError(404, "not_found", "this article was never sent")
        answer = Answer(200, send.body, {"X-Delivery-Id": send.delivery_id})
        with self.state.lock:
            if article_id in self.state.supersede_after_get:
                self.state.supersede_after_get.discard(article_id)
                self.state.add_send({**send.body, "sent_at": now_iso()})
        return answer

    def _result(self, request: _Request) -> Answer:
        self._require(request, "articles:write")
        article_id = self._article_id(request)
        body = self._body(request, "ArticleResultReport")
        state = self.state
        with state.lock:
            sends = state.sends.get(article_id, [])
            delivery_id = body.get("delivery_id")
            if delivery_id is not None:
                target = next((s for s in sends if s.delivery_id == delivery_id), None)
            else:
                waiting = [s for s in sends if s.state == "awaiting"]
                target = waiting[-1] if waiting else (sends[-1] if sends else None)
            if target is None or target.state == "superseded":
                state.results.append(ResultCall(article_id, body, 409, delivery_id))
                reason = (
                    "this article was never sent"
                    if not sends
                    else "a newer send replaced this one; fetch the article again"
                )
                raise ApiError(409, "state_conflict", reason)
            target.state = "failed" if body.get("error") else "delivered"
            state.results.append(ResultCall(article_id, body, 200, target.delivery_id))
            if not body.get("error") and body.get("permalink"):
                state.record_link_back(
                    article_id,
                    str(body["permalink"]),
                    published_at=None,
                    social_queue_exclude=body.get("social_queue_exclude"),
                    source="result",
                )
        ignored = sorted(set(body) - self._result_fields)
        return Answer(
            200, {"article_id": article_id, "state": target.state, "ignored_fields": ignored}
        )

    def _published(self, request: _Request) -> Answer:
        self._require(request, "articles:write")
        body = self._body(request, "PublishedArticlesRequest")
        results = []
        for item in body["items"]:
            article_id = str(item["article_id"])
            status = self.state.record_link_back(
                article_id,
                str(item["url"]),
                published_at=item.get("published_at"),
                social_queue_exclude=item.get("social_queue_exclude"),
                source="published",
            )
            results.append({"article_id": article_id, "status": status})
        return Answer(200, {"results": results})

    def _openapi(self, request: _Request) -> Answer:
        return Answer(200, self.docs.openapi)

    def _control_send(self, request: _Request) -> Answer:
        """`POST /_tdkit/send`: a "Send to CMS" of the sample article, with fields overridden.

        Not a Tribune Desk route: the mock's own control, so `tdkit mock` alone can make sends.
        In read mode the send waits in the feed; otherwise it goes to `--webhook` once.
        """
        overrides = json.loads(request.raw) if request.raw else {}
        if not isinstance(overrides, dict):
            raise ApiError(422, "validation_error", "the body must be a JSON object")
        body = json.loads(json.dumps(self.docs.sample_delivery))
        body.update(article_id=str(uuid.uuid4()), sent_at=now_iso())
        body.update(overrides)
        send = self.state.add_send(body)
        delivery = None
        if not self.state.read_mode and self.webhook:
            result = deliver(
                self.webhook,
                json.dumps(body, ensure_ascii=False).encode(),
                secrets=self.secrets,
                delivery_id=send.delivery_id,
                attempt=1,
            )
            delivery = {"status": result.status, "error": result.error, "answer": result.json}
            if result.status is not None and 200 <= result.status < 300:
                send.state = "delivered"
        return Answer(
            200,
            {"article_id": send.article_id, "delivery_id": send.delivery_id, "delivery": delivery},
        )

    def _file(self, handler: BaseHTTPRequestHandler, name: str) -> None:
        self.state.record_pull(name)
        handler.send_response(200)
        handler.send_header("Content-Type", "image/jpeg")
        handler.send_header("Content-Length", str(len(JPEG)))
        handler.end_headers()
        handler.wfile.write(JPEG)
