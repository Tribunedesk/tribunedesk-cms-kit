"""`ci/contract_drift.py`: the pin, the comparison, the fixture copy and the PR body, offline."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from .conftest import CI_YML, FIXTURE

_SPEC = importlib.util.spec_from_file_location(
    "contract_drift", Path(__file__).parent.parent / "ci" / "contract_drift.py"
)
assert _SPEC and _SPEC.loader
drift = importlib.util.module_from_spec(_SPEC)
sys.modules["contract_drift"] = drift
_SPEC.loader.exec_module(drift)

CHANGELOG = (FIXTURE / "CHANGELOG.md").read_text(encoding="utf-8")


def test_pin_is_read_and_replaced_alone() -> None:
    text = CI_YML.read_text(encoding="utf-8")
    pinned = drift.pinned_tag(text)
    moved = drift.with_pin(text, "v3.5.0-draft")
    assert drift.pinned_tag(moved) == "v3.5.0-draft"
    assert moved.replace("v3.5.0-draft", pinned) == text


def test_compare_orders_versions() -> None:
    assert drift.compare("v3.4.1-draft", "v3.4.2-draft") == "behind"
    assert drift.compare("v3.4.2-draft", "v3.5.0-draft") == "behind"
    assert drift.compare("v3.4.2-draft", "v3.4.2-draft") == "current"
    assert drift.compare("v3.10.0-draft", "v3.9.0-draft") == "ahead"


def test_release_after_draft_is_newer() -> None:
    assert drift.compare("v3.4.2-draft", "v3.4.2") == "behind"


def _fake_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tags: list[str]) -> Path:
    ci = tmp_path / "ci.yml"
    ci.write_text("env:\n  CONTRACT_TAG: v3.4.2-draft\n", encoding="utf-8")
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "stale.md").write_text("old", encoding="utf-8")
    monkeypatch.setattr(drift, "CI_YML", ci)
    monkeypatch.setattr(drift, "FIXTURE", fixture)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

    def fake_git(args: list[str]) -> str:
        if args[0] == "ls-remote":
            return "".join(f"0\trefs/tags/{t}\n" for t in tags)
        assert args[0] == "clone"
        target = Path(args[-1])
        target.mkdir(parents=True)
        (target / ".git").mkdir()
        (target / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
        return ""

    monkeypatch.setattr(drift, "_git", fake_git)
    return ci


def test_pin_ahead_of_latest_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ci = _fake_repo(monkeypatch, tmp_path, ["v3.4.1-draft"])
    before = ci.read_text(encoding="utf-8")
    assert drift.main(["--body-out", str(tmp_path / "body.md")]) == 1
    assert ci.read_text(encoding="utf-8") == before
    assert (tmp_path / "fixture" / "stale.md").is_file()
    assert not (tmp_path / "body.md").exists()


def test_current_pin_changes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fake_repo(monkeypatch, tmp_path, ["v3.4.1-draft", "v3.4.2-draft"])
    assert drift.main(["--body-out", str(tmp_path / "body.md")]) == 0
    assert not (tmp_path / "body.md").exists()


def test_behind_moves_pin_fixture_and_writes_body(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ci = _fake_repo(monkeypatch, tmp_path, ["v3.4.2-draft", "v3.5.0-draft"])
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    assert drift.main(["--body-out", str(tmp_path / "body.md")]) == 0
    assert drift.pinned_tag(ci.read_text(encoding="utf-8")) == "v3.5.0-draft"
    assert (tmp_path / "fixture" / "CHANGELOG.md").is_file()
    assert not (tmp_path / "fixture" / ".git").exists()
    assert out.read_text("utf-8") == "behind=true\npinned=v3.4.2-draft\ntag=v3.5.0-draft\n"


def test_refresh_fixture_removes_stale_files(tmp_path: Path) -> None:
    source, fixture = tmp_path / "src", tmp_path / "fixture"
    (source / ".github").mkdir(parents=True)
    (source / "guide").mkdir()
    (source / "guide" / "1.md").write_text("new", encoding="utf-8")
    fixture.mkdir()
    (fixture / "gone.md").write_text("old", encoding="utf-8")
    drift.refresh_fixture(source, fixture)
    assert sorted(p.name for p in fixture.rglob("*")) == ["1.md", "guide"]


def test_pr_body_lists_integrators_between() -> None:
    patch = drift.pr_body(CHANGELOG, "v3.4.1-draft", "v3.4.2-draft")
    assert "- Nothing to do." in patch
    assert "3.4.0-draft" not in patch
    body = drift.pr_body(CHANGELOG, "v3.2.0-draft", "v3.4.2-draft")
    assert "- 3.4.0-draft `L1`: answer `401`" in body
    assert "- 3.3.0-draft `L2`: move from" in body
    assert "3.2.0-draft `" not in body
    assert "blob/v3.4.2-draft/CHANGELOG.md" in body
