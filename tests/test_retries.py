"""tdkit 1.1: the mock retries a delivery on the guide's schedule, scaled to seconds."""

from __future__ import annotations

import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler

import pytest

from tdkit.docs import ContractDocs
from tdkit.mock.retries import SCHEDULE_MINUTES, should_retry
from tdkit.mock.server import MockServer
from tdkit.mock.state import MockState

from .conftest import serve
from .test_mock_routes import call


class Receiver:
    """A webhook that answers the statuses in `answers`, then 200, and records attempts."""

    def __init__(self, answers: list[int]) -> None:
        self.answers = list(answers)
        self.attempts: list[tuple[str, str]] = []

    def handler(self) -> type[BaseHTTPRequestHandler]:
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                receiver.attempts.append(
                    (self.headers["webhook-id"], self.headers["X-Delivery-Attempt"])
                )
                status = receiver.answers.pop(0) if receiver.answers else 200
                self.send_response(status)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, format: str, *args: object) -> None:
                pass

        return Handler


@pytest.fixture
def mock(docs: ContractDocs) -> Iterator[tuple[MockState, str, Receiver]]:
    receiver = Receiver([])
    with serve(receiver.handler()) as hook:
        state = MockState()
        server = MockServer(state, docs, webhook=hook + "/", retry_scale=0.002)
        host, port = server.start()
        try:
            yield state, f"http://{host}:{port}", receiver
        finally:
            server.stop()


def _wait(predicate: object, seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if callable(predicate) and predicate():
            return
        time.sleep(0.02)


def test_schedule_is_the_guides() -> None:
    assert SCHEDULE_MINUTES == (2, 10, 30, 120, 360, 840)


@pytest.mark.parametrize(
    ("status", "retry"),
    [
        *[(s, True) for s in (500, 503, 408, 425, 429, None)],
        *[(s, False) for s in (404, 401, 301, 200)],
    ],
)
def test_should_retry_codes(status: int | None, retry: bool) -> None:
    assert should_retry(status) is retry


def test_retries_after_503_then_delivers(mock: tuple[MockState, str, Receiver]) -> None:
    state, base, receiver = mock
    receiver.answers[:] = [503, 503]
    article_id = call(base, "POST", "/_tdkit/send", token=None, body={})[1]["article_id"]
    _wait(lambda: len(receiver.attempts) >= 3)
    ids = {a[0] for a in receiver.attempts}
    assert [a[1] for a in receiver.attempts] == ["1", "2", "3"]
    assert len(ids) == 1
    _wait(lambda: state.sends[article_id][-1].state == "delivered")
    assert state.sends[article_id][-1].state == "delivered"


def test_no_retry_after_400(mock: tuple[MockState, str, Receiver]) -> None:
    state, base, receiver = mock
    receiver.answers[:] = [400]
    article_id = call(base, "POST", "/_tdkit/send", token=None, body={})[1]["article_id"]
    time.sleep(0.5)
    assert len(receiver.attempts) == 1
    assert state.sends[article_id][-1].state == "failed"


def test_newer_send_cancels_retries(docs: ContractDocs) -> None:
    receiver = Receiver([503, 503, 503])
    with serve(receiver.handler()) as hook:
        state = MockState()
        server = MockServer(state, docs, webhook=hook + "/", retry_scale=0.1)
        host, port = server.start()
        base = f"http://{host}:{port}"
        try:
            first = call(base, "POST", "/_tdkit/send", token=None, body={})[1]
            call(base, "POST", "/_tdkit/send", token=None, body={"article_id": first["article_id"]})
            time.sleep(1.5)  # retries of the first send would come after 0.2 s and 1 s
        finally:
            server.stop()
    old = [a for a in receiver.attempts if a[0] == first["delivery_id"]]
    assert old == [(first["delivery_id"], "1")]


def test_scale_zero_never_retries(docs: ContractDocs) -> None:
    receiver = Receiver([503])
    with serve(receiver.handler()) as hook:
        state = MockState()
        server = MockServer(state, docs, webhook=hook + "/", retry_scale=0)
        host, port = server.start()
        try:
            call(f"http://{host}:{port}", "POST", "/_tdkit/send", token=None, body={})
            time.sleep(0.3)
        finally:
            server.stop()
    assert len(receiver.attempts) == 1
