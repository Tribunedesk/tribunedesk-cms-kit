from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
import uuid
from typing import Any

from tdkit.docs import ContractDocs
from tdkit.mock.server import MockServer
from tdkit.mock.state import ALL_SCOPES, MockState

TOKEN = "tdcms_mock"


def call(
    base: str,
    method: str,
    path: str,
    *,
    token: str | None = TOKEN,
    body: Any = None,
    raw: bytes | None = None,
) -> tuple[int, Any, dict[str, str]]:
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status, payload, got = response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        status, payload, got = exc.code, exc.read(), dict(exc.headers)
    return status, json.loads(payload) if payload else None, got


def sample(docs: ContractDocs, **changes: Any) -> dict[str, Any]:
    body = json.loads(json.dumps(docs.sample_delivery))
    body["article_id"] = str(uuid.uuid4())
    body.update(changes)
    return body


def test_status_requires_token(base: str, docs: ContractDocs) -> None:
    status, error, _ = call(base, "GET", "/v3/cms/status", token=None)
    assert status == 401
    assert error["code"] == "unauthorized"
    assert call(base, "GET", "/v3/cms/status", token="tdcms_unknown")[0] == 401
    status, body, _ = call(base, "GET", "/v3/cms/status")
    assert status == 200
    assert body["contract_version"] == docs.version
    assert body["image_hosts"] == ["127.0.0.1"]
    assert sorted(body["scopes"]) == sorted(ALL_SCOPES)


def test_scope_missing_is_403(state: MockState, base: str) -> None:
    state.tokens["tdcms_media"] = {"media:read"}
    status, error, _ = call(
        base, "POST", "/v3/cms/articles/published", token="tdcms_media", body={"items": []}
    )
    assert status == 403
    assert error["code"] == "forbidden"


def test_published_validates_body_against_openapi(
    state: MockState, base: str, docs: ContractDocs
) -> None:
    status, error, _ = call(base, "POST", "/v3/cms/articles/published", body={"items": []})
    assert status == 422
    assert error["code"] == "validation_error"
    sent = state.add_send(sample(docs))
    status, answer, _ = call(
        base,
        "POST",
        "/v3/cms/articles/published",
        body={
            "items": [
                {"article_id": sent.article_id, "url": "https://cms.example.com/a/"},
                {"article_id": str(uuid.uuid4()), "url": "https://cms.example.com/b/"},
                {"article_id": sent.article_id, "url": "ftp://cms.example.com/a/"},
            ]
        },
    )
    assert status == 200
    assert [r["status"] for r in answer["results"]] == ["ok", "not_found", "invalid_url"]
    assert state.published[sent.article_id]["url"] == "https://cms.example.com/a/"


def test_published_unknown_field_is_422(base: str) -> None:
    item = {"article_id": str(uuid.uuid4()), "url": "https://x.example/", "tdkit_extra": 1}
    status, error, _ = call(base, "POST", "/v3/cms/articles/published", body={"items": [item]})
    assert status == 422
    assert "tdkit_extra" in error["message"]


def test_malformed_json_is_422_before_the_token_check(base: str) -> None:
    status, error, _ = call(
        base, "POST", "/v3/cms/articles/published", token=None, raw=b"{not json"
    )
    assert status == 422
    assert error["code"] == "validation_error"


def test_result_unknown_field_is_listed_in_ignored_fields(
    state: MockState, base: str, docs: ContractDocs
) -> None:
    sent = state.add_send(sample(docs))
    status, ack, _ = call(
        base,
        "POST",
        f"/v3/cms/articles/{sent.article_id}/result",
        body={"delivery_id": sent.delivery_id, "cms_post_id": "1", "tdkit_extra": True},
    )
    assert status == 200
    assert ack == {
        "article_id": sent.article_id,
        "state": "delivered",
        "ignored_fields": ["tdkit_extra"],
    }
    status, _, _ = call(
        base, "POST", f"/v3/cms/articles/{sent.article_id}/result", body={"cms_post_id": 5}
    )
    assert status == 422


def test_changes_shows_article_sent_only_to_articles_read(
    state: MockState, base: str, docs: ContractDocs
) -> None:
    state.tokens["tdcms_media"] = {"media:read"}
    start = call(base, "GET", "/v3/cms/changes")[1]["next_cursor"]
    sent = state.add_send(sample(docs))
    status, page, _ = call(base, "GET", f"/v3/cms/changes?cursor={start}")
    assert status == 200
    assert [(c["kind"], c["article_id"]) for c in page["changes"]] == [
        ("article_sent", sent.article_id)
    ]
    status, page_media, _ = call(
        base, "GET", f"/v3/cms/changes?cursor={start}", token="tdcms_media"
    )
    assert status == 200
    assert page_media["changes"] == []
    assert page_media["next_cursor"] == page["next_cursor"]


def test_changes_409_when_integration_disabled(state: MockState, base: str) -> None:
    state.integration_enabled = False
    status, error, _ = call(base, "GET", "/v3/cms/changes")
    assert status == 409
    assert error["code"] == "state_conflict"
    assert call(base, "GET", "/v3/cms/status")[1]["state"] == "disabled"


def test_result_with_old_delivery_id_is_409_state_conflict(
    state: MockState, base: str, docs: ContractDocs
) -> None:
    body = sample(docs)
    old = state.add_send(body)
    new = state.add_send({**body, "sent_at": "2026-11-05T09:00:00+00:00"})
    path = f"/v3/cms/articles/{old.article_id}/result"
    status, error, _ = call(base, "POST", path, body={"delivery_id": old.delivery_id})
    assert status == 409
    assert error["code"] == "state_conflict"
    status, got, headers = call(base, "GET", f"/v3/cms/articles/{old.article_id}")
    assert status == 200
    assert headers["X-Delivery-Id"] == new.delivery_id
    assert got["sent_at"] == "2026-11-05T09:00:00+00:00"
    assert call(base, "POST", path, body={"delivery_id": new.delivery_id})[0] == 200
    never = f"/v3/cms/articles/{uuid.uuid4()}/result"
    assert call(base, "POST", never, body={})[0] == 409
    assert call(base, "GET", f"/v3/cms/articles/{uuid.uuid4()}")[0] == 404


def test_expired_cursor_is_410_then_awaiting_lists_waiting_sends(
    state: MockState, base: str, docs: ContractDocs
) -> None:
    cursor = call(base, "GET", "/v3/cms/changes")[1]["next_cursor"]
    sent = state.add_send(sample(docs))
    state.expire_cursor_once = True
    status, error, _ = call(base, "GET", f"/v3/cms/changes?cursor={cursor}")
    assert status == 410
    assert error["code"] == "cursor_expired"
    # The feed before the expiry is gone: a fresh poll does not show the waiting send.
    assert call(base, "GET", "/v3/cms/changes")[1]["changes"] == []
    status, page, _ = call(base, "GET", "/v3/cms/articles/awaiting")
    assert status == 200
    assert page["items"] == [
        {"article_id": sent.article_id, "delivery_id": sent.delivery_id, "sent_at": sent.sent_at}
    ]
    assert page["next_cursor"] is None


def test_route_outside_the_contract_is_404(base: str) -> None:
    assert call(base, "GET", "/v3/cms/held", token=None)[0] == 401
    assert call(base, "GET", "/v3/cms/nothing-here")[0] == 404


def test_mock_listens_on_loopback_only(state: MockState, docs: ContractDocs) -> None:
    server = MockServer(state, docs)
    host, port = server.start()
    try:
        assert host == "127.0.0.1"
        assert server.bound_address() == ("127.0.0.1", port)
        with socket.create_connection(("127.0.0.1", port), timeout=5):
            pass
    finally:
        server.stop()


def test_files_are_served_and_recorded(state: MockState, base: str) -> None:
    with urllib.request.urlopen(f"{base}/files/a.jpg", timeout=5) as response:
        assert response.headers["Content-Type"] == "image/jpeg"
        assert response.read()[:2] == b"\xff\xd8"
    assert state.pulls == {"a.jpg": 1}


def test_openapi_is_served_without_token(base: str, docs: ContractDocs) -> None:
    status, body, _ = call(base, "GET", "/v3/cms/openapi.json", token=None)
    assert status == 200
    assert body["info"]["version"] == docs.version


def test_control_send_queues_an_article_in_read_mode(state: MockState, base: str) -> None:
    status, made, _ = call(base, "POST", "/_tdkit/send", token=None, body={"title": "Hello"})
    assert status == 200
    assert made["delivery"] is None
    send = state.newest_send(made["article_id"])
    assert send is not None
    assert send.delivery_id == made["delivery_id"]
    assert send.body["title"] == "Hello"
    assert call(base, "GET", "/v3/cms/changes")[1]["changes"] == []  # from now
    sent = [c for c in state.changes if c.kind == "article_sent"]
    assert [c.article_id for c in sent] == [made["article_id"]]


def test_poll_without_cursor_starts_from_now(
    state: MockState, base: str, docs: ContractDocs
) -> None:
    state.add_send(sample(docs))
    status, page, _ = call(base, "GET", "/v3/cms/changes")
    assert (status, page["changes"]) == (200, [])
    later = state.add_send(sample(docs))
    page = call(base, "GET", f"/v3/cms/changes?cursor={page['next_cursor']}")[1]
    assert [c["article_id"] for c in page["changes"]] == [later.article_id]


def _https_get(url: str) -> tuple[int, bytes]:
    import ssl

    from tdkit.mock import tls

    context = ssl.create_default_context(cafile=str(tls.CA_BUNDLE))
    with urllib.request.urlopen(url, timeout=10, context=context) as response:
        return response.status, response.read()


def test_files_are_served_over_https(state: MockState, docs: ContractDocs) -> None:
    """D5: integrations on tribunedesk/cms-protocol download only over https."""
    server = MockServer(state, docs)
    server.start()
    try:
        host, tls_port = server.tls_address()
        status, data = _https_get(f"https://{host}:{tls_port}/files/x.jpg")
        assert status == 200 and data
        assert state.pulls.get("x.jpg") == 1
        assert server.files_base("localhost") == f"https://localhost:{tls_port}"
    finally:
        server.stop()


def test_api_stays_on_http(base: str) -> None:
    assert base.startswith("http://")
    assert call(base, "GET", "/v3/cms/status")[0] == 200


def test_two_mocks_get_distinct_tls_ports(state: MockState, docs: ContractDocs) -> None:
    first, second = MockServer(state, docs), MockServer(MockState(), docs)
    first.start()
    second.start()
    try:
        assert first.tls_address()[1] != second.tls_address()[1]
    finally:
        first.stop()
        second.stop()


def test_stalled_tls_client_blocks_nothing(state: MockState, docs: ContractDocs) -> None:
    """A client that connects to the TLS port and never handshakes (a probe, a debugger) must
    not hold up other downloads or the mock's shutdown (review of 1b, important 2)."""
    import time

    server = MockServer(state, docs)
    server.start()
    host, tls_port = server.tls_address()
    stalled = socket.create_connection((host, tls_port), timeout=5)
    try:
        started = time.monotonic()
        status, _ = _https_get(f"https://{host}:{tls_port}/files/y.jpg")
        assert status == 200
        assert time.monotonic() - started < 3
    finally:
        started = time.monotonic()
        server.stop()
        stalled.close()
    assert time.monotonic() - started < 3


def test_untrusted_tls_client_is_counted(state: MockState, docs: ContractDocs) -> None:
    """A client that does not trust the test CA fails the handshake; the mock counts it, so
    `l1-image-host` can say why the image did not arrive."""
    import ssl

    server = MockServer(state, docs)
    server.start()
    try:
        host, tls_port = server.tls_address()
        untrusted = ssl.create_default_context()  # the system CAs only
        try:
            urllib.request.urlopen(
                f"https://{host}:{tls_port}/files/z.jpg", timeout=5, context=untrusted
            )
            raise AssertionError("expected a certificate error")
        except urllib.error.URLError:
            pass
        deadline = time.monotonic() + 3 if (time := __import__("time")) else 0
        while state.tls_failures == 0 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert state.tls_failures == 1
        assert not state.pulls.get("z.jpg")
    finally:
        server.stop()
