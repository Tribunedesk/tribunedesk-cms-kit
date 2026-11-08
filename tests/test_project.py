from __future__ import annotations

import io
import json
import shutil
import tarfile
from pathlib import Path

import pytest

from tdkit import project
from tdkit.cli import main
from tdkit.project import fetch_docs, validate_manifest

from .conftest import FIXTURE

GOOD = {
    "contract": "3.4.1-draft",
    "levels": [1, 2],
    "delivery": "webhook",
    "cms": "django",
    "kit": "1.0.0",
    "conformance": {
        "date": "2026-11-20",
        "kit": "1.0.0",
        "contract": "3.4.1-draft",
        "passed": [1, 2],
    },
}


def test_manifest_validate_rejects_level_5_and_bad_delivery(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert validate_manifest(GOOD) == []
    errors = validate_manifest({**GOOD, "levels": [1, 5], "delivery": "email"})
    assert any("levels" in e for e in errors)
    assert any("delivery" in e for e in errors)
    path = tmp_path / "tribunedesk.json"
    path.write_text(json.dumps({**GOOD, "levels": [5]}), encoding="utf-8")
    assert main(["manifest", "validate", str(path)]) == 2
    assert "levels" in capsys.readouterr().err
    path.write_text(json.dumps(GOOD), encoding="utf-8")
    assert main(["manifest", "validate", str(path)]) == 0


def test_manifest_write_takes_passed_levels_from_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = {
        "tdkit": "1.0.0",
        "contract": "3.4.1-draft",
        "levels": [1, 2, 3],
        "mode": "webhook",
        "results": [
            {"id": "a", "level": 1, "passed": True},
            {"id": "r", "level": 1, "passed": None},
            {"id": "b", "level": 2, "passed": True},
            {"id": "s", "level": 2, "passed": None},
            {"id": "c", "level": 3, "passed": False},
            {"id": "d", "level": 3, "passed": True},
        ],
    }
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    code = main(
        [
            "manifest",
            "write",
            "--contract",
            "3.4.1-draft",
            "--levels",
            "1,2,3",
            "--delivery",
            "webhook",
            "--cms",
            "django",
            "--conformance",
            str(report_path),
        ]
    )
    assert code == 0
    written = json.loads((tmp_path / "tribunedesk.json").read_text(encoding="utf-8"))
    assert written["conformance"]["passed"] == [1, 2]
    assert written["conformance"]["contract"] == "3.4.1-draft"
    assert written["levels"] == [1, 2, 3]
    assert validate_manifest(written) == []


def test_docs_writes_gitignore_entry_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRIBUNEDESK_DOCS_DIR", str(FIXTURE))
    (tmp_path / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    first = fetch_docs(tmp_path, tag=None, dest=None)
    second = fetch_docs(tmp_path, tag=None, dest=None)
    assert first == second
    assert first["version"] == "3.4.1-draft"
    assert Path(first["path"]) == tmp_path / ".tribunedesk" / "cms-api@v3.4.1-draft"
    assert (Path(first["path"]) / "openapi.json").is_file()
    lines = (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert lines.count(".tribunedesk/") == 1


def _tarball() -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        archive.add(FIXTURE, arcname="tribunedesk-cms-api-3.4.1-draft")
    return buffer.getvalue()


def test_docs_fetch_without_git_uses_tarball(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TRIBUNEDESK_DOCS_DIR", raising=False)
    monkeypatch.setattr(project.shutil, "which", lambda name: None)
    asked: list[str] = []

    def transport(url: str) -> bytes:
        asked.append(url)
        return _tarball()

    result = fetch_docs(tmp_path, tag="v3.4.1-draft", dest=None, transport=transport)
    assert asked == [
        "https://codeload.github.com/Tribunedesk/tribunedesk-cms-api/tar.gz/refs/tags/v3.4.1-draft"
    ]
    assert result["tag"] == "v3.4.1-draft"
    assert (Path(result["path"]) / "guide" / "1-article-delivery.md").is_file()
    # No .gitignore and no git repository: nothing is written.
    assert not (tmp_path / ".gitignore").exists()


def test_docs_reuses_an_existing_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRIBUNEDESK_DOCS_DIR", raising=False)
    dest = tmp_path / ".tribunedesk" / "cms-api@v3.4.1-draft"
    shutil.copytree(FIXTURE, dest)

    def transport(url: str) -> bytes:
        raise AssertionError("no download for an existing copy")

    result = fetch_docs(tmp_path, tag="v3.4.1-draft", dest=None, transport=transport)
    assert Path(result["path"]) == dest
