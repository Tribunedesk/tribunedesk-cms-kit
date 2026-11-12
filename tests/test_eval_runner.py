"""The checks of `evals/run.py` (plan E9.6, Windows runner instead of `claude plugin eval`)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def load_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("eval_runner", ROOT / "evals" / "run.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["eval_runner"] = module
    spec.loader.exec_module(module)
    return module


runner = load_runner()


def make_run(tmp_path: Path, events: list[dict] | None = None):
    return runner.Run(tmp_path, events or [])


def write_report(root: Path, results: list[bool | None], levels: list[int], mode: str) -> None:
    (root / ".tribunedesk").mkdir()
    report = {
        "tdkit": "1.0.0",
        "contract": "3.4.1-draft",
        "levels": levels,
        "mode": mode,
        "results": [{"id": str(i), "level": 1, "passed": p} for i, p in enumerate(results)],
    }
    (root / ".tribunedesk" / "tdkit-report.json").write_text(json.dumps(report), encoding="utf-8")


def test_every_scenario_has_a_prompt() -> None:
    files = {p.stem for p in (ROOT / "evals" / "scenarios").glob("*.md")}
    assert set(runner.SCENARIO) <= files
    for name in files:
        assert runner.prompt_of(name)


def test_report_green(tmp_path: Path) -> None:
    write_report(tmp_path, [True, None, True], [1, 2], "webhook")
    run = make_run(tmp_path)
    assert runner.report_green([1, 2], "webhook")(run)[0]
    assert not runner.report_green([1], "read")(run)[0]


def test_report_with_a_failure_is_not_green(tmp_path: Path) -> None:
    write_report(tmp_path, [True, False], [1, 2], "webhook")
    assert not runner.report_green([1, 2], "webhook")(make_run(tmp_path))[0]


def test_missing_report_is_not_green(tmp_path: Path) -> None:
    assert not runner.report_green([1, 2], "webhook")(make_run(tmp_path))[0]


def test_manifest(tmp_path: Path) -> None:
    data = {"levels": [4], "delivery": "none"}
    (tmp_path / "tribunedesk.json").write_text(json.dumps(data), encoding="utf-8")
    run = make_run(tmp_path)
    assert runner.manifest(levels=[4], delivery="none", passed=None)(run)[0]
    assert not runner.manifest(levels=[1, 2])(run)[0]


def test_skill_and_bash_checks(tmp_path: Path) -> None:
    events = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Skill", "input": {"skill": "x:tribunedesk-integration"}},
                    {"type": "tool_use", "name": "Bash", "input": {"command": "$TDKIT_CMD check --levels 1"}},
                ]
            },
        }
    ]  # fmt: skip
    run = make_run(tmp_path, events)
    assert runner.skill_fired(run)[0]
    assert runner.ran(rf"{runner.TDKIT} check")(run)[0]
    assert runner.ran(rf"{runner.TDKIT} manifest write", expected=False)(run)[0]


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def test_secret_in_tracked_file_is_found(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")
    secret = "whsec_" + "A" * 32
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    (tmp_path / ".env").write_text(f"TD_SIGNING_SECRET={secret}\n", encoding="utf-8")
    run = make_run(tmp_path)
    assert runner.no_secret_in_git(run)[0]
    assert runner.env_ignored(run)[0]
    (tmp_path / "settings.py").write_text(f'SECRET = "{secret}"\n', encoding="utf-8")
    ok, detail = runner.no_secret_in_git(run)
    assert not ok and "settings.py" in detail


def test_env_not_ignored(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")
    (tmp_path / ".env").write_text("X=1\n", encoding="utf-8")
    assert not runner.env_ignored(make_run(tmp_path))[0]


def test_secret_in_a_test_file_is_a_test_vector(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")
    (tmp_path / "tests_tribunedesk.py").write_text(
        'V = "whsec_' + "B" * 32 + '"\n', encoding="utf-8"
    )
    assert runner.no_secret_in_git(make_run(tmp_path))[0]


def test_final_message_complete(tmp_path: Path) -> None:
    good = (
        "Nic nie wdrażałem na produkcję.\n| 1. Projekt | ok |\n| 2. Zakres | ok |\n"
        "| 3. Wiadomość | ok |\n| 5. Budowa | ok |\n| 6. Zgodność | ok |\n"
        "Pliki: `blog/tribunedesk.py`, `blog/views.py`, `.env.example`."
    )
    events = [{"type": "result", "result": good}]
    assert runner.final_message_complete(make_run(tmp_path, events))[0]
    events = [{"type": "result", "result": "Gotowe, 13 PASS."}]
    assert not runner.final_message_complete(make_run(tmp_path, events))[0]
