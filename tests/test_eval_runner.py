"""The checks of `evals/run.py` (plan E9.6, Windows runner instead of `claude plugin eval`)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import zipfile
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
        "tdkit": "1.1.0",
        "contract": runner.CONTRACT,
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
    assert runner.ran(r"\bcheck\s+--")(run)[0]
    assert runner.ran(r"\bmanifest write\b", expected=False)(run)[0]


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


def test_secret_in_a_test_folder_is_a_test_vector(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")
    (tmp_path / "testdata").mkdir()
    (tmp_path / "testdata" / "vectors.json").write_text(
        '"whsec_' + "C" * 32 + '"', encoding="utf-8"
    )
    assert runner.no_secret_in_git(make_run(tmp_path))[0]


def test_tdkit_through_a_variable(tmp_path: Path) -> None:
    command = 'T="uv run --project kit tdkit"; $T integrators --from 3.2.0-draft --to 3.4.1-draft'
    block = {"type": "tool_use", "name": "Bash", "input": {"command": command}}
    run = make_run(tmp_path, [{"type": "assistant", "message": {"content": [block]}}])
    assert runner.ran(r"\bintegrators\b")(run)[0]
    assert runner.ran(r"\bcheck\s+--", expected=False)(run)[0]


# -- final review of E9.6 ---------------------------------------------------------------------


def _write_call(path: str) -> dict:
    block = {"type": "tool_use", "name": "Write", "input": {"file_path": path, "content": "{}"}}
    return {"type": "assistant", "message": {"content": [block]}}


def test_hand_written_report_or_manifest_fails(tmp_path: Path) -> None:
    for name in ("C:/p/.tribunedesk/tdkit-report.json", "/p/tribunedesk.json"):
        run = make_run(tmp_path, [_write_call(name)])
        assert not runner.results_from_tdkit(run)[0], name
    assert runner.results_from_tdkit(make_run(tmp_path, [_write_call("/p/blog/views.py")]))[0]


def test_report_of_another_contract_is_not_green(tmp_path: Path) -> None:
    write_report(tmp_path, [True], [1, 2], "webhook")
    report = tmp_path / ".tribunedesk" / "tdkit-report.json"
    data = json.loads(report.read_text(encoding="utf-8"))
    data["contract"] = "3.2.0-draft"
    report.write_text(json.dumps(data), encoding="utf-8")
    assert not runner.report_green([1, 2], "webhook")(make_run(tmp_path))[0]


def test_manifest_conformance_must_match_the_contract(tmp_path: Path) -> None:
    data = {
        "contract": "3.4.1-draft",
        "levels": [1, 2],
        "delivery": "webhook",
        "conformance": {"contract": "3.2.0-draft", "passed": [1, 2]},
    }
    (tmp_path / "tribunedesk.json").write_text(json.dumps(data), encoding="utf-8")
    assert not runner.manifest(contract="3.4.1-draft", passed=[1, 2])(make_run(tmp_path))[0]


def test_secret_in_a_config_named_like_test_is_found(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")
    secret = "whsec_" + "D" * 32
    for name in (".env.test", "settings_test_like.py", "latest/config.py"):
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(f"S={secret}\n", encoding="utf-8")
    ok, detail = runner.no_secret_in_git(make_run(tmp_path))
    assert not ok
    assert ".env.test" in detail and "latest/config.py" in detail


def test_secret_committed_then_deleted_is_found(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "t")
    git(tmp_path, "config", "user.email", "t@example.com")
    leak = tmp_path / "settings.py"
    leak.write_text('S = "whsec_' + "E" * 32 + '"\n', encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "leak")
    leak.write_text("S = ''\n", encoding="utf-8")
    git(tmp_path, "commit", "-qam", "remove")
    ok, detail = runner.no_secret_in_git(make_run(tmp_path))
    assert not ok and "settings.py" in detail


def test_photos_only_checks_a_green_level_4_report(tmp_path: Path) -> None:
    checks = runner.SCENARIO["photos-only"].checks
    assert "tdkit check ran" in checks
    green = checks["report green (4, none)"]
    write_report(tmp_path, [True, True, None], [4], "none")
    assert green(make_run(tmp_path))[0]
    red = tmp_path / "red"
    red.mkdir()
    write_report(red, [True, False], [4], "none")
    assert not green(make_run(red))[0]


def _calls(*calls: tuple[str, dict]) -> list[dict]:
    content = [{"type": "tool_use", "name": n, "input": i} for n, i in calls]
    return [{"type": "assistant", "message": {"content": content}}]


def test_parity_scenarios_are_registered() -> None:
    names = {"parity-django", "parity-laravel", "parity-node"}
    assert names <= set(runner.SCENARIO)
    for name in names:
        assert runner.SCENARIO[name].checks == runner.PARITY


def test_no_local_sources_flags_a_read_of_the_kit(tmp_path: Path) -> None:
    kit_file = str(runner.KIT / "src" / "tdkit" / "docs.py")
    run = make_run(tmp_path, _calls(("Read", {"file_path": kit_file})))
    assert not runner.no_local_sources(run)[0]
    run = make_run(tmp_path, _calls(("Bash", {"command": "cat ../tribunedesk-wordpress/x.php"})))
    assert not runner.no_local_sources(run)[0]
    run = make_run(tmp_path, _calls(("Grep", {"pattern": "x", "path": str(runner.KIT)})))
    assert not runner.no_local_sources(run)[0]


def test_no_local_sources_allows_tdkit_cmd(tmp_path: Path) -> None:
    command = f'"uv" run --project "{runner.KIT.as_posix()}" tdkit check --levels 1,2,3,4'
    run = make_run(
        tmp_path,
        _calls(("Bash", {"command": command}), ("Read", {"file_path": str(tmp_path / "a.py")})),
    )
    assert runner.no_local_sources(run)[0]


def test_no_local_sources_allows_the_skill_itself(tmp_path: Path) -> None:
    """The plugin is loaded from this kit; SKILL.md tells the agent to read its references."""
    ref = runner.PLUGIN / "skills" / "tribunedesk-integration" / "references" / "scope.md"
    run = make_run(tmp_path, _calls(("Read", {"file_path": str(ref)})))
    assert runner.no_local_sources(run)[0]


def test_no_local_sources_allows_public_github_urls(tmp_path: Path) -> None:
    command = (
        "composer config repositories.tribunedesk-cms-php vcs "
        "https://github.com/Tribunedesk/tribunedesk-cms-php"
    )
    run = make_run(tmp_path, _calls(("Bash", {"command": command})))
    assert runner.no_local_sources(run)[0]


def test_no_local_sources_flags_bash_into_the_kit(tmp_path: Path) -> None:
    for path in (runner.KIT / "reference" / "django", runner.KIT / "evals"):
        for form in (path.as_posix(), str(path)):
            run = make_run(tmp_path, _calls(("Bash", {"command": f'ls "{form}"'})))
            assert not runner.no_local_sources(run)[0], form


def test_no_local_sources_flags_a_glob_pattern_into_the_kit(tmp_path: Path) -> None:
    pattern = (runner.KIT / "reference" / "**" / "*.py").as_posix()
    run = make_run(tmp_path, _calls(("Glob", {"pattern": pattern})))
    assert not runner.no_local_sources(run)[0]


def test_no_local_sources_flags_a_sibling_checkout(tmp_path: Path) -> None:
    sibling = runner.KIT.parent / "tribunedesk-wordpress" / "src" / "WordPress" / "CmsSync.php"
    run = make_run(tmp_path, _calls(("Read", {"file_path": str(sibling)})))
    assert not runner.no_local_sources(run)[0]


def test_no_local_sources_allows_the_kit_readme(tmp_path: Path) -> None:
    """SKILL.md and references/tdkit.md send the agent to the kit README (public on GitHub);
    all three parity runs of 13.11 read it from the local checkout and listed its root."""
    kit = runner.KIT.as_posix()
    calls = [
        ("Read", {"file_path": str(runner.KIT / "README.md")}),
        ("Bash", {"command": f'cd "{kit}" && ls && grep -n "^#" README.md'}),
        ("Bash", {"command": f'K="{kit}"; ls "$K"; grep -n "^#" "$K/README.md"'}),
        # parity-node 2026-11-17: the kit root with a trailing slash.
        ("Bash", {"command": f'cd "{kit}/" && grep -n "^#" README.md | head -80'}),
        ("Bash", {"command": f"cd {kit}/ && ls"}),
    ]
    assert runner.no_local_sources(make_run(tmp_path, _calls(*calls)))[0]


def test_no_local_sources_flags_kit_code_next_to_the_readme(tmp_path: Path) -> None:
    kit = runner.KIT.as_posix()
    for command in (
        f'cd "{kit}" && cat reference/django/td/webhook.py',
        f'K="{kit}"; grep -rn signature "$K/src"',
        f'cd "{kit}" && ls evals/scenarios',
        f'cd "{kit}/" && cat src/tdkit/docs.py',
    ):
        run = make_run(tmp_path, _calls(("Bash", {"command": command})))
        assert not runner.no_local_sources(run)[0], command


def test_manifest_checks_expect_the_eval_contract() -> None:
    """A manifest written by tdkit carries the contract the run tested, CONTRACT; a stale literal
    made every django-l12, drupal-l12 and update-3.2 run report a false FAIL `manifest`."""
    source = (ROOT / "evals" / "run.py").read_text(encoding="utf-8")
    assert 'contract="3.4.1-draft"' not in source


def test_eval_contract_is_the_pinned_tag() -> None:
    """The evals expect the contract CI tests against; a literal went stale on every drift."""
    pin = (ROOT / "ci" / "contract-tag").read_text(encoding="utf-8").strip()
    assert pin.removeprefix("v") == runner.CONTRACT


def test_no_local_sources_allows_the_ca_bundle(tmp_path: Path) -> None:
    """D5: TD_CA_BUNDLE points into the kit (`src/tdkit/mock/tls/ca.pem`); using it is allowed."""
    tls_dir = (runner.KIT / "src" / "tdkit" / "mock" / "tls").as_posix()
    calls = [
        ("Bash", {"command": f'ls "{tls_dir}/"'}),
        ("Bash", {"command": f'export TD_CA_BUNDLE="{tls_dir}/ca.pem"; php artisan test'}),
    ]
    assert runner.no_local_sources(make_run(tmp_path, _calls(*calls)))[0]
    reading_code = [("Bash", {"command": f'sed -n 1,40p "{tls_dir}/__init__.py"'})]
    assert not runner.no_local_sources(make_run(tmp_path, _calls(*reading_code)))[0]


def test_tdkit_command_runs_a_wheel_not_the_checkout(tmp_path: Path) -> None:
    """The agent's `tdkit` is the package a user installs (`uvx --from <wheel>`): TDKIT_CMD names
    no folder of this checkout."""
    wheel = tmp_path / "tdkit-1.3.0-py3-none-any.whl"
    command = runner.tdkit_command(wheel)
    assert command.endswith(f'--from "{wheel.as_posix()}" tdkit')
    assert runner.KIT.as_posix() not in command
    assert str(runner.KIT) not in command


def test_built_wheel_is_outside_the_kit_and_carries_the_test_ca(tmp_path: Path) -> None:
    """The wheel is built into the run's folder, not the kit, and holds the test CA that
    TD_CA_BUNDLE points at (the package's own file, so it exists where tdkit runs)."""
    wheel = runner.build_tdkit_wheel(tmp_path)
    assert wheel.parent == tmp_path
    assert not wheel.is_relative_to(runner.KIT)
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    assert {"tdkit/mock/tls/ca.pem", "tdkit/mock/tls/server.pem"} <= names


def test_agent_env_keeps_only_the_allowed_names() -> None:
    base = {
        "PATH": "/bin",
        "Path": "C:/bin",
        "CLAUDE_CONFIG_DIR": "/c",
        "TEMP": "/t",
        "TMP": "/t",
        "ANTHROPIC_API_KEY": "k",
        "CLAUDE_CODE_GIT_BASH_PATH": "/g",
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_x",
        "AWS_SECRET_ACCESS_KEY": "a",
    }
    env = runner.agent_env(base, "tdkit-cmd")
    assert "GITHUB_PERSONAL_ACCESS_TOKEN" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    for name in ("PATH", "Path", "CLAUDE_CONFIG_DIR", "TEMP", "TMP", "ANTHROPIC_API_KEY"):
        assert env[name] == base[name]
    assert env["CLAUDE_CODE_GIT_BASH_PATH"] == "/g"
    assert env["TDKIT_CMD"] == "tdkit-cmd"


def test_stream_ends_a_hanging_command(tmp_path: Path) -> None:
    script = "import json, time; print(json.dumps({'type': 'system'}), flush=True); time.sleep(60)"
    finished = runner.stream(
        [sys.executable, "-c", script],
        tmp_path,
        dict(os.environ),
        tmp_path / "transcript.jsonl",
        timeout_s=2,
    )
    assert finished.timed_out
    assert finished.returncode != 0
    assert finished.events == [{"type": "system"}]


def test_stream_reports_the_exit_code(tmp_path: Path) -> None:
    finished = runner.stream(
        [sys.executable, "-c", "raise SystemExit(3)"],
        tmp_path,
        dict(os.environ),
        tmp_path / "transcript.jsonl",
        timeout_s=30,
    )
    assert not finished.timed_out
    assert finished.returncode == 3


def _final(tmp_path: Path, text: str):
    return make_run(tmp_path, [{"type": "result", "result": text}])


def test_welcome_needs_a_sentence_saying_nothing_was_deployed(tmp_path: Path) -> None:
    for text in (
        "Tokens: none ordered. Nothing was deployed.",
        "Token: nie zamawiałem. Nic nie wdrażałem na produkcję.",
        "I did not deploy anything; no token was ordered.",
    ):
        assert runner.welcome_in_final(_final(tmp_path, text))[0], text
    for text in (
        "Put the token into the production environment.",
        "Token ready. Deploy it to production when you like.",
    ):
        assert not runner.welcome_in_final(_final(tmp_path, text))[0], text


def test_ghost_flags_edit_and_bash_writes(tmp_path: Path) -> None:
    assert runner.no_code_written(make_run(tmp_path, _calls(("Read", {"file_path": "a"}))))[0]
    for call in (
        ("Edit", {"file_path": "a.py"}),
        ("Write", {"file_path": "a.py"}),
        ("Bash", {"command": "cat > a.py <<'EOF'\nx\nEOF"}),
        ("Bash", {"command": "echo x | tee a.py"}),
    ):
        assert not runner.no_code_written(make_run(tmp_path, _calls(call)))[0], call


def test_photos_only_looks_for_a_webhook_in_every_urls_py(tmp_path: Path) -> None:
    check = runner.SCENARIO["photos-only"].checks["no webhook route"]
    (tmp_path / "blogsite").mkdir()
    (tmp_path / "blogsite" / "urls.py").write_text("urlpatterns = []\n", encoding="utf-8")
    assert check(make_run(tmp_path))[0]
    (tmp_path / "tribunedesk").mkdir()
    (tmp_path / "tribunedesk" / "urls.py").write_text(
        'path("td/webhook/", views.webhook)\n', encoding="utf-8"
    )
    assert not check(make_run(tmp_path))[0]


def test_read_mode_accepts_an_equals_sign(tmp_path: Path) -> None:
    check = runner.SCENARIO["no-public-endpoint"].checks["tdkit check in read mode"]
    for command in ("$TDKIT_CMD check --levels 1 --mode=read", "$TDKIT_CMD check --mode read"):
        assert check(make_run(tmp_path, _calls(("Bash", {"command": command}))))[0], command
    command = "$TDKIT_CMD check --levels 1 --mode=webhook"
    assert not check(make_run(tmp_path, _calls(("Bash", {"command": command}))))[0]


def test_update_flags_the_old_route_and_header(tmp_path: Path) -> None:
    check = runner.SCENARIO["update-3.2"].checks["old route and header gone"]
    (tmp_path / "blog").mkdir()
    path = tmp_path / "blog" / "tribunedesk.py"
    path.write_text('URL = "/v3/cms/articles/published"\n', encoding="utf-8")
    assert check(make_run(tmp_path))[0]
    for old in ('H = "X-Webhook-Secret"\n', 'U = "/v2/cms/published-urls"\n'):
        path.write_text(old, encoding="utf-8")
        assert not check(make_run(tmp_path))[0], old
