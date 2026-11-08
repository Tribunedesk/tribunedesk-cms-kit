from __future__ import annotations

import base64
import json
from http.server import BaseHTTPRequestHandler
from typing import Any, ClassVar

import pytest

from tdkit.sender import deliver
from tdkit.signing import sign, verify

from .conftest import FIXTURE, serve

VECTORS = json.loads(
    (FIXTURE / "examples" / "vectors" / "webhook-signature.json").read_text(encoding="utf-8")
)["vectors"]


@pytest.mark.parametrize("vector", VECTORS, ids=[v["name"] for v in VECTORS])
def test_sign_and_verify_agree_with_every_contract_vector(vector: dict[str, Any]) -> None:
    body = base64.b64decode(vector["body_base64"])
    headers = vector["headers"]
    if vector["valid"]:
        signature = sign(
            vector["secrets"], headers["webhook-id"], int(headers["webhook-timestamp"]), body
        )
        assert signature == headers["webhook-signature"]
    assert verify(vector["verify_with"], headers, body, now=vector["now"]) is vector["valid"]


class _Recorder(BaseHTTPRequestHandler):
    seen: ClassVar[list[tuple[str, dict[str, str], bytes]]] = []

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.seen.append((self.path, dict(self.headers), body))
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/target")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        payload = b'{"cms_post_id": "7"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        self.seen.append((self.path, dict(self.headers), b""))
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass


SECRET = "whsec_" + base64.b64encode(b"tdkit-mock-signing-secret-000000").decode()


def test_mock_sender_does_not_follow_redirects() -> None:
    _Recorder.seen.clear()
    with serve(_Recorder) as base:
        result = deliver(f"{base}/redirect", b"{}", secrets=[SECRET], delivery_id="d-1", attempt=1)
    assert result.status == 302
    assert [path for path, _, _ in _Recorder.seen] == ["/redirect"]


def test_sender_sends_headers_of_guide_1() -> None:
    _Recorder.seen.clear()
    body = '{"title": "Zażółć"}'.encode()
    with serve(_Recorder) as base:
        result = deliver(
            f"{base}/hook",
            body,
            secrets=[SECRET],
            delivery_id="d-2",
            attempt=3,
            timestamp=1700000000,
        )
    assert result.status == 200
    assert result.json == {"cms_post_id": "7"}
    _, headers, sent = _Recorder.seen[0]
    lower = {k.lower(): v for k, v in headers.items()}
    assert sent == body
    assert lower["webhook-id"] == "d-2"
    assert lower["x-delivery-id"] == "d-2"
    assert lower["x-delivery-attempt"] == "3"
    assert lower["webhook-timestamp"] == "1700000000"
    assert lower["user-agent"] == "ArticleWriter/2"
    assert lower["content-type"] == "application/json"
    assert verify(SECRET, lower, sent, now=1700000000)


def test_sender_reports_connection_error() -> None:
    result = deliver(
        "http://127.0.0.1:9/hook", b"{}", secrets=[SECRET], delivery_id="d", attempt=1, timeout=2
    )
    assert result.status is None
    assert result.error
