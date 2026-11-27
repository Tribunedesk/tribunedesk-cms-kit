"""`ci/contract_drift.py`: the pin, the comparison, the fixture copy and the PR body, offline."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from .conftest import FIXTURE, PIN_FILE

_SPEC = importlib.util.spec_from_file_location(
    "contract_drift", Path(__file__).parent.parent / "ci" / "contract_drift.py"
)
assert _SPEC and _SPEC.loader
drift = importlib.util.module_from_spec(_SPEC)
sys.modules["contract_drift"] = drift
_SPEC.loader.exec_module(drift)

CHANGELOG = (FIXTURE / "CHANGELOG.md").read_text(encoding="utf-8")


def test_pin_file_holds_one_tag() -> None:
    assert drift.PIN == PIN_FILE
    assert drift.read_pin(PIN_FILE).startswith("v")


def test_workflow_commits_no_workflow_file() -> None:
    """GITHUB_TOKEN may not push changes under .github/workflows/ (review, critical 1)."""
    text = (PIN_FILE.parent.parent / ".github" / "workflows" / "contract-drift.yml").read_text(
        encoding="utf-8"
    )
    add = [line for line in text.splitlines() if "ci/drift-branch.sh" in line]
    assert add and all(".github" not in line for line in add)


def test_open_step_reads_the_pin_only_with_an_open_pull_request() -> None:
    """A closed, unmerged pull request must not keep its pin: the branch is rebuilt instead."""
    text = (PIN_FILE.parent.parent / ".github" / "workflows" / "contract-drift.yml").read_text(
        encoding="utf-8"
    )
    step = text[text.index("id: open") : text.index("- name: Compare the pin")]
    listing = step.index("gh pr list --head contract/latest --state open")
    assert listing < step.index("git fetch")
    assert "GH_TOKEN: ${{ github.token }}" in step


def test_push_step_fails_loudly_without_its_pull_request() -> None:
    """2026-11-25: `gh pr create` failed on a GraphQL error and the run was as red as a plain
    "pin behind"; the step retries and then says that no pull request exists."""
    text = (PIN_FILE.parent.parent / ".github" / "workflows" / "contract-drift.yml").read_text(
        encoding="utf-8"
    )
    step = text[text.index("- name: Push contract/latest") : text.index("- name: Approve")]
    assert "for try in 1 2 3" in step
    assert "NOT opened or updated" in step
    assert step.index("NOT opened") < step.index("exit 1") < step.index("gh workflow run")
    assert "/ship" not in text


def test_compare_orders_versions() -> None:
    assert drift.compare("v3.4.1-draft", "v3.4.2-draft") == "behind"
    assert drift.compare("v3.4.2-draft", "v3.5.0-draft") == "behind"
    assert drift.compare("v3.4.2-draft", "v3.4.2-draft") == "current"
    assert drift.compare("v3.10.0-draft", "v3.9.0-draft") == "ahead"


def test_release_after_draft_is_newer() -> None:
    assert drift.compare("v3.4.2-draft", "v3.4.2") == "behind"


def _fake_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tags: list[str]) -> Path:
    pin = tmp_path / "contract-tag"
    pin.write_text("v3.4.2-draft\n", encoding="utf-8")
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "stale.md").write_text("old", encoding="utf-8")
    monkeypatch.setattr(drift, "PIN", pin)
    monkeypatch.setattr(drift, "FIXTURE", fixture)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

    def fake_git(args: list[str]) -> str:
        if args[0] == "ls-remote":
            return "".join(f"0\trefs/tags/{t}\n" for t in tags)
        assert args[0] == "clone"
        target = Path(args[-1])
        (target / ".git").mkdir(parents=True)
        (target / "guide").mkdir()
        (target / "guide" / "1-article-delivery.md").write_text("g", encoding="utf-8")
        (target / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
        return ""

    monkeypatch.setattr(drift, "_git", fake_git)
    return pin


def test_pin_ahead_of_latest_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pin = _fake_repo(monkeypatch, tmp_path, ["v3.4.1-draft"])
    assert drift.main(["--body-out", str(tmp_path / "body.md")]) == 1
    assert drift.read_pin(pin) == "v3.4.2-draft"
    assert (tmp_path / "fixture" / "stale.md").is_file()
    assert not (tmp_path / "body.md").exists()


def test_current_pin_changes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fake_repo(monkeypatch, tmp_path, ["v3.4.1-draft", "v3.4.2-draft"])
    assert drift.main(["--body-out", str(tmp_path / "body.md")]) == 0
    assert not (tmp_path / "body.md").exists()


def test_behind_moves_pin_fixture_and_writes_body(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pin = _fake_repo(monkeypatch, tmp_path, ["v3.4.2-draft", "v3.5.0-draft"])
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    assert drift.main(["--body-out", str(tmp_path / "body.md")]) == 0
    assert drift.read_pin(pin) == "v3.5.0-draft"
    assert (tmp_path / "fixture" / "CHANGELOG.md").is_file()
    assert not (tmp_path / "fixture" / ".git").exists()
    assert out.read_text("utf-8") == (
        "behind=true\nrebuild=true\npinned=v3.4.2-draft\ntag=v3.5.0-draft\n"
    )


def test_open_pr_at_the_newest_tag_is_left_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No daily rebuild of contract/latest: fixes pushed onto it survive (review, important 3)."""
    pin = _fake_repo(monkeypatch, tmp_path, ["v3.4.2-draft", "v3.5.0-draft"])
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    body = tmp_path / "body.md"
    assert drift.main(["--body-out", str(body), "--open-pr-pin", "v3.5.0-draft"]) == 0
    assert drift.read_pin(pin) == "v3.4.2-draft"
    assert (tmp_path / "fixture" / "stale.md").is_file()
    assert not body.exists()
    assert out.read_text("utf-8") == (
        "behind=true\nrebuild=false\npinned=v3.4.2-draft\ntag=v3.5.0-draft\n"
    )


def test_refresh_fixture_removes_stale_files(tmp_path: Path) -> None:
    source, fixture = tmp_path / "src", tmp_path / "fixture"
    (source / ".github").mkdir(parents=True)
    (source / "guide").mkdir()
    (source / "guide" / "1.md").write_text("new", encoding="utf-8")
    fixture.mkdir()
    (fixture / "gone.md").write_text("old", encoding="utf-8")
    drift.refresh_fixture(source, fixture)
    assert sorted(p.name for p in fixture.rglob("*")) == ["1.md", "guide"]


def test_refresh_fixture_copies_only_what_tests_read(tmp_path: Path) -> None:
    """No example code under tests/ for ruff and pyright to trip on (review, important 4)."""
    source, fixture = tmp_path / "src", tmp_path / "fixture"
    for name in (
        "CHANGELOG.md",
        "README.md",
        "VERSIONING.md",
        "openapi.json",
        "guide/5-archive.md",
        "examples/payloads/a.json",
        "examples/vectors/v.json",
        "examples/python/level1_receiver.py",
        "pl/README.md",
    ):
        (source / name).parent.mkdir(parents=True, exist_ok=True)
        (source / name).write_text("x", encoding="utf-8")
    drift.refresh_fixture(source, fixture)
    files = sorted(p.relative_to(fixture).as_posix() for p in fixture.rglob("*") if p.is_file())
    assert files == [
        "CHANGELOG.md",
        "README.md",
        "examples/payloads/a.json",
        "examples/vectors/v.json",
        "guide/5-archive.md",
        "openapi.json",
    ]


def test_pr_body_lists_integrators_between() -> None:
    patch = drift.pr_body(CHANGELOG, "v3.4.1-draft", "v3.4.2-draft")
    assert "- Nothing to do." in patch
    assert "3.4.0-draft" not in patch
    body = drift.pr_body(CHANGELOG, "v3.2.0-draft", "v3.4.2-draft")
    assert "- 3.4.0-draft `L1`: answer `401`" in body
    assert "- 3.3.0-draft `L2`: move from" in body
    assert "3.2.0-draft `" not in body
    assert "blob/v3.4.2-draft/CHANGELOG.md" in body


# -- ci/drift-branch.sh: rebuilding contract/latest on a newer tag ---------------------------

DRIFT_BRANCH = Path(__file__).parent.parent / "ci" / "drift-branch.sh"
BOT = "tribunedesk-contract-drift@users.noreply.github.com"


def _bash() -> str:
    if os.name == "nt":  # system32\bash.exe is WSL; Git for Windows ships its own
        path = Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Git" / "bin" / "bash.exe"
        return str(path) if path.exists() else ""
    return shutil.which("bash") or ""


def _git(cwd: Path, *args: str, email: str = "dev@example.com") -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "dev",
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": "dev",
        "GIT_COMMITTER_EMAIL": email,
    }
    done = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return done.stdout.strip()


def _commit(cwd: Path, path: str, text: str, message: str, email: str = "dev@example.com") -> None:
    (cwd / path).parent.mkdir(parents=True, exist_ok=True)
    (cwd / path).write_text(text, encoding="utf-8")
    _git(cwd, "add", path, email=email)
    _git(cwd, "commit", "-q", "-m", message, email=email)


@pytest.fixture
def drift_repo(tmp_path: Path) -> tuple[Path, Path]:
    """An origin with main (pin v1) and an open drift branch: the drift's commit (pin v2) and a
    scenario someone pushed onto it. Returns (origin, a fresh clone of main)."""
    if not _bash():
        pytest.skip("bash is not available")
    origin, work = tmp_path / "origin.git", tmp_path / "work"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    _git(tmp_path, "clone", "-q", str(origin), str(work))
    _commit(work, "ci/contract-tag", "v1\n", "init")
    _git(work, "push", "-q", "origin", "main")
    _git(work, "checkout", "-q", "-b", "contract/latest")
    _commit(work, "ci/contract-tag", "v2\n", "contract: v1 → v2", email=BOT)
    _commit(work, "src/scenario.py", "SCENARIO = 2\n", "feat: scenario for v2")
    _git(work, "push", "-q", "origin", "contract/latest")
    clone = tmp_path / "runner"
    _git(tmp_path, "clone", "-q", str(origin), str(clone))
    (clone / "ci" / "contract-tag").write_text("v3\n", encoding="utf-8")
    return origin, clone


def _drift_branch(clone: Path, open_pr: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OPEN_PR": open_pr}
    return subprocess.run(
        [_bash(), DRIFT_BRANCH.as_posix(), "contract: v1 → v3", "ci/contract-tag"],
        cwd=clone,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_newer_tag_keeps_commits_pushed_onto_the_branch(drift_repo: tuple[Path, Path]) -> None:
    origin, clone = drift_repo
    done = _drift_branch(clone, "7")
    assert done.returncode == 0, done.stdout + done.stderr
    log = _git(origin, "log", "--format=%s", "contract/latest")
    assert log.splitlines() == ["feat: scenario for v2", "contract: v1 → v3", "init"]
    assert _git(origin, "show", "contract/latest:ci/contract-tag") == "v3"


def test_without_an_open_pull_request_the_branch_is_rebuilt(
    drift_repo: tuple[Path, Path],
) -> None:
    origin, clone = drift_repo
    assert _drift_branch(clone, "").returncode == 0
    log = _git(origin, "log", "--format=%s", "contract/latest")
    assert log.splitlines() == ["contract: v1 → v3", "init"]


def test_a_commit_that_no_longer_applies_stops_the_run(
    drift_repo: tuple[Path, Path], tmp_path: Path
) -> None:
    origin, clone = drift_repo
    work = tmp_path / "work"
    _commit(work, "ci/contract-tag", "v2-patched\n", "fix: pin by hand")
    _git(work, "push", "-q", "origin", "contract/latest")
    before = _git(origin, "rev-parse", "contract/latest")
    done = _drift_branch(clone, "7")
    assert done.returncode == 1
    assert "fix: pin by hand" in done.stdout and "carry it by hand" in done.stdout
    assert _git(origin, "rev-parse", "contract/latest") == before
