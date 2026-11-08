from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from tdkit.check.commands import split_command
from tdkit.check.context import CheckOptions
from tdkit.check.runner import Report, run_check
from tdkit.check.scenarios import SCENARIOS
from tdkit.cli import main
from tdkit.docs import ContractDocs

from .conftest import FIXTURE

REFERENCE = Path(__file__).parent / "reference_integration.py"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def command(sub: str, store: Path) -> str:
    """A command template for the reference integration (paths quoted for either OS)."""
    return f'"{sys.executable}" "{REFERENCE}" {sub} --store "{store}"'


@contextmanager
def reference(tmp_path: Path, mock_port: int, *flags: str) -> Iterator[tuple[str, Path]]:
    port = free_port()
    store = tmp_path / "store.json"
    env = {
        **__import__("os").environ,
        "TD_API_BASE": f"http://127.0.0.1:{mock_port}",
        "TD_CMS_TOKEN": "tdcms_mock",
    }
    process = subprocess.Popen(
        [
            sys.executable,
            str(REFERENCE),
            "serve",
            "--port",
            str(port),
            "--store",
            str(store),
            *flags,
        ],
        env=env,
    )
    try:
        deadline = time.monotonic() + 15
        while True:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.1)
        yield f"http://127.0.0.1:{port}/td/webhook", store
    finally:
        process.terminate()
        process.wait(timeout=10)


def options(
    docs: ContractDocs, webhook: str | None, store: Path, port: int, **extra: Any
) -> CheckOptions:
    return CheckOptions(
        docs=docs,
        webhook=webhook,
        inspect_cmd=command("inspect {article_id}", store),
        publish_cmd=command("publish {article_id}", store),
        poll_cmd=command("poll", store),
        port=port,
        **extra,
    )


def outcome(report: Report) -> dict[str, bool | None]:
    return {r.id: r.passed for r in report.results}


@pytest.fixture(scope="module")
def webhook_run(
    tmp_path_factory: pytest.TempPathFactory, docs: ContractDocs
) -> tuple[int, dict[str, Any], str]:
    """One full CLI run on the reference integration: levels 1-3, webhook mode, JSON report."""
    tmp_path = tmp_path_factory.mktemp("webhook")
    port = free_port()
    report_path = tmp_path / "report.json"
    with reference(tmp_path, port) as (webhook, store):
        code = main(
            [
                "check",
                "--levels",
                "1,2,3",
                "--mode",
                "webhook",
                "--webhook",
                webhook,
                "--inspect-cmd",
                command("inspect {article_id}", store),
                "--publish-cmd",
                command("publish {article_id}", store),
                "--social-flag",
                "--port",
                str(port),
                "--docs",
                str(FIXTURE),
                "--json",
                str(report_path),
            ]
        )
    return code, json.loads(report_path.read_text(encoding="utf-8")), ""


def test_reference_integration_passes_all_levels(
    webhook_run: tuple[int, dict[str, Any], str], tmp_path: Path, docs: ContractDocs
) -> None:
    code, report, _ = webhook_run
    failed = {r["id"]: r["detail"] for r in report["results"] if r["passed"] is False}
    assert failed == {}
    assert code == 0
    skipped = {r["id"] for r in report["results"] if r["passed"] is None}
    assert skipped == {"read-delivers-result", "read-superseded-409", "read-cursor-expired"}

    port = free_port()
    read = run_check(
        [1, 2, 3], "read", options(docs, None, tmp_path / "read.json", port, social_flag=True)
    )
    failed = {r.id: r.detail for r in read.results if r.passed is False}
    assert failed == {}
    skipped = {r.id for r in read.results if r.passed is None}
    assert skipped == {s.id for s in SCENARIOS if s.mode == "webhook"}


def test_json_report_shape(webhook_run: tuple[int, dict[str, Any], str]) -> None:
    _, report, _ = webhook_run
    assert set(report) == {"tdkit", "contract", "levels", "mode", "results"}
    assert report["contract"] == "3.4.1-draft"
    assert report["levels"] == [1, 2, 3]
    assert report["mode"] == "webhook"
    assert [r["id"] for r in report["results"]] == [s.id for s in SCENARIOS]
    for result in report["results"]:
        assert set(result) == {"id", "level", "done_when", "guide", "passed", "detail"}


def _webhook_check(
    tmp_path: Path, docs: ContractDocs, flags: tuple[str, ...], levels: list[int]
) -> Report:
    port = free_port()
    with reference(tmp_path, port, *flags) as (webhook, store):
        return run_check(levels, "webhook", options(docs, webhook, store, port))


def test_check_fails_when_signature_not_verified(
    tmp_path: Path, docs: ContractDocs, capsys: pytest.CaptureFixture[str]
) -> None:
    report = _webhook_check(tmp_path, docs, ("--no-verify", "--any-image-host"), [1])
    results = outcome(report)
    assert results["l1-bad-signature"] is False
    assert results["l1-clock-skew"] is False
    assert results["l1-image-host"] is False
    assert results["l1-creates-draft"] is True
    assert report.failed


def test_check_fails_older_send_overwrites(tmp_path: Path, docs: ContractDocs) -> None:
    report = _webhook_check(tmp_path, docs, ("--overwrite-older",), [1])
    results = outcome(report)
    assert results["l1-older-send-ignored"] is False
    assert [r.id for r in report.failed] == ["l1-older-send-ignored"]


def test_check_accepts_empty_2xx_for_delivery_only_scenarios(
    tmp_path: Path, docs: ContractDocs
) -> None:
    report = _webhook_check(tmp_path, docs, ("--empty-answer",), [1, 2])
    assert [r.id for r in report.failed] == ["l1-answer-fields"]


def test_cli_exit_code_1_when_a_scenario_fails(tmp_path: Path) -> None:
    port = free_port()
    with reference(tmp_path, port, "--no-verify") as (webhook, store):
        code = main(
            [
                "check",
                "--levels",
                "1",
                "--webhook",
                webhook,
                "--inspect-cmd",
                command("inspect {article_id}", store),
                "--port",
                str(port),
                "--docs",
                str(FIXTURE),
            ]
        )
    assert code == 1


def test_command_template_splits_windows_paths() -> None:
    template = (
        '"C:\\Program Files\\Python 3.12\\python.exe" '
        "C:\\Users\\O'Brien\\cms\\manage.py td_inspect {article_id}"
    )
    assert split_command(template, windows=True) == [
        "C:\\Program Files\\Python 3.12\\python.exe",
        "C:\\Users\\O'Brien\\cms\\manage.py",
        "td_inspect",
        "{article_id}",
    ]
    assert split_command("'/home/o b/cms/bin/td' inspect {article_id}", windows=False) == [
        "/home/o b/cms/bin/td",
        "inspect",
        "{article_id}",
    ]


def test_level_4_is_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        ["check", "--levels", "1,4", "--webhook", "https://x.example/", "--inspect-cmd", "x"]
    )
    assert code == 2
    assert "level 4 is not covered by tdkit 1.0" in capsys.readouterr().err


def test_done_when_quotes_are_literal() -> None:
    for scenario in SCENARIOS:
        guide = scenario.guide.split("#")[0]
        text = (FIXTURE / guide).read_text(encoding="utf-8")
        assert scenario.done_when in text, scenario.id
