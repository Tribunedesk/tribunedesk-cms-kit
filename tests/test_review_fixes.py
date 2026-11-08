"""Regression tests for the findings of the whole-branch review."""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import uuid
from pathlib import Path

import pytest

from tdkit.check.commands import run_template
from tdkit.check.context import CheckOptions, Context, Fail
from tdkit.check.runner import run_check
from tdkit.check.scenarios import image_hosts_for
from tdkit.cli import main
from tdkit.docs import ContractDocs, load_docs
from tdkit.mock.state import MockState, ResultCall
from tdkit.sender import deliver
from tdkit.signing import MOCK_SECRET

from .conftest import FIXTURE
from .test_check import free_port, options, reference
from .test_mock_routes import call, sample
from .test_signing import _Recorder, serve


def test_image_host_needs_a_2xx_answer(tmp_path: Path, docs: ContractDocs) -> None:
    port = free_port()
    with reference(tmp_path, port, "--answer-500") as (webhook, store):
        report = run_check([1], "webhook", options(docs, webhook, store, port))
    assert {r.id: r.passed for r in report.results}["l1-image-host"] is False


def test_forbidden_image_host_differs_from_the_webhook_host() -> None:
    assert image_hosts_for("http://127.0.0.1:8080/hook") == ("127.0.0.1", "localhost")
    assert image_hosts_for("http://localhost:8080/hook") == ("localhost", "127.0.0.1")
    assert image_hosts_for("https://abc.trycloudflare.com/td") == ("127.0.0.1", "localhost")


def _read_ctx(docs: ContractDocs, state: MockState) -> Context:
    opts = CheckOptions(
        docs=docs, inspect_cmd="x", poll_cmd=f'"{sys.executable}" -c "pass"', port=0
    )
    return Context(opts, "read", state, 1)


def test_read_mode_send_needs_a_result_for_that_send(
    docs: ContractDocs, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = MockState(read_mode=True)
    ctx = _read_ctx(docs, state)
    body = ctx.article()
    old = state.add_send(body)
    # The poll reports the OLD send again and ignores the new one.
    monkeypatch.setattr(
        ctx,
        "poll",
        lambda: state.results.append(ResultCall(body["article_id"], {}, 200, old.delivery_id)),
    )
    with pytest.raises(Fail, match="no result"):
        ctx.send({**body, "sent_at": ctx.sent_at(5)})


def test_read_mode_error_result_is_not_a_delivery(
    docs: ContractDocs, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = MockState(read_mode=True)
    ctx = _read_ctx(docs, state)
    body = ctx.article()

    def poll() -> None:
        send = state.newest_send(body["article_id"])
        assert send is not None
        state.results.append(ResultCall(body["article_id"], {"error": "no"}, 200, send.delivery_id))

    monkeypatch.setattr(ctx, "poll", poll)
    with pytest.raises(Fail, match="failed"):
        ctx.delivered(body)


def test_published_at_without_time_zone_is_422(
    state: MockState,
    base: str,
    docs: ContractDocs,
) -> None:
    sent = state.add_send(sample(docs))
    item = {
        "article_id": sent.article_id,
        "url": "https://x.example/",
        "published_at": "2026-01-01T10:00:00",
    }
    assert call(base, "POST", "/v3/cms/articles/published", body={"items": [item]})[0] == 422
    item["published_at"] = "2026-01-01T10:00:00+01:00"
    assert call(base, "POST", "/v3/cms/articles/published", body={"items": [item]})[0] == 200


def test_contract_without_signature_vectors_loads(tmp_path: Path) -> None:
    root = tmp_path / "cms-api"
    shutil.copytree(FIXTURE, root)
    (root / "examples" / "vectors" / "webhook-signature.json").unlink()
    openapi = json.loads((root / "openapi.json").read_text(encoding="utf-8"))
    openapi["info"]["version"] = "3.4.0-draft"
    (root / "openapi.json").write_text(json.dumps(openapi), encoding="utf-8")
    docs = load_docs(root)
    assert docs.version == "3.4.0-draft"
    assert docs.vectors == []


def test_commands_resolve_through_path(tmp_path: Path) -> None:
    if os.name == "nt":
        (tmp_path / "tdtool.cmd").write_text("@echo hello %1\r\n", encoding="utf-8")
    else:
        script = tmp_path / "tdtool"
        script.write_text("#!/bin/sh\necho hello $1\n", encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}"}
    assert run_template("tdtool {article_id}", env=env, article_id="a1").strip() == "hello a1"


def test_awaiting_pages_do_not_skip_sends_reported_meanwhile(
    state: MockState,
    base: str,
    docs: ContractDocs,
) -> None:
    sends = [
        state.add_send(sample(docs, sent_at=f"2026-11-0{i}T09:00:00+00:00")) for i in (1, 2, 3)
    ]
    page = call(base, "GET", "/v3/cms/articles/awaiting?limit=2")[1]
    assert [i["delivery_id"] for i in page["items"]] == [s.delivery_id for s in sends[:2]]
    for item in page["items"]:
        path = f"/v3/cms/articles/{item['article_id']}/result"
        assert call(base, "POST", path, body={"delivery_id": item["delivery_id"]})[0] == 200
    cursor = page["next_cursor"]
    rest = call(base, "GET", f"/v3/cms/articles/awaiting?limit=2&cursor={cursor}")[1]
    assert [i["delivery_id"] for i in rest["items"]] == [sends[2].delivery_id]


def test_bad_secret_is_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "check",
            "--webhook",
            "http://127.0.0.1:9/",
            "--inspect-cmd",
            "x",
            "--secret",
            "not-a-secret",
            "--docs",
            str(FIXTURE),
        ]
    )
    assert code == 2
    assert "whsec_" in capsys.readouterr().err


def test_sender_ignores_proxy_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:9")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    with serve(_Recorder) as url:
        result = deliver(
            f"{url}/hook", b"{}", secrets=[MOCK_SECRET], delivery_id=str(uuid.uuid4()), attempt=1
        )
    assert result.status == 200
