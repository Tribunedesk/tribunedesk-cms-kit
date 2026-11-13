from __future__ import annotations

import pytest

from tdkit.integrators import integrators

from .conftest import FIXTURE

CHANGELOG = (FIXTURE / "CHANGELOG.md").read_text(encoding="utf-8")


def test_integrators_between_versions_filters_levels() -> None:
    items = integrators(CHANGELOG, "3.2.0-draft", "3.4.1-draft", levels=[1, 2], mode="webhook")
    versions = {item["version"] for item in items}
    assert versions == {"3.3.0-draft", "3.4.0-draft"}
    for item in items:
        assert set(item["tags"]) & {"L1", "L2"}
        assert "read" not in item["tags"]
        assert "L4" not in item["tags"]
    assert any("social_queue_exclude" in item["action"] for item in items)
    # Newest first, as in the CHANGELOG.
    assert items[0]["version"] == "3.4.0-draft"


def test_integrators_read_mode_includes_read_items() -> None:
    items = integrators(CHANGELOG, "3.3.0-draft", "3.4.1-draft", levels=[1], mode="read")
    read = [item for item in items if "read" in item["tags"]]
    assert [item["version"] for item in read] == ["3.4.0-draft", "3.4.0-draft"]
    assert any("delivery_id" in item["action"] for item in read)
    webhook = integrators(CHANGELOG, "3.3.0-draft", "3.4.1-draft", levels=[1], mode="webhook")
    assert all("read" not in item["tags"] for item in webhook)
    assert len(webhook) == len(items) - len(read)


def test_integrators_ignores_unknown_tags(capsys: pytest.CaptureFixture[str]) -> None:
    text = CHANGELOG.replace(
        "- Nothing to do.",
        "- `L5`: send your archive.\n- `L1`, `L5`: something for level 1.",
        1,
    )
    items = integrators(text, "3.4.1-draft", "3.4.2-draft", levels=[1, 5], mode="webhook")
    assert [item["action"] for item in items] == ["something for level 1."]
    assert items[0]["tags"] == ["L1"]
    assert "L5" in capsys.readouterr().err


def test_integrators_skips_nothing_to_do() -> None:
    items = integrators(
        CHANGELOG, "3.4.0-draft", "3.4.1-draft", levels=[1, 2, 3, 4], mode="webhook"
    )
    assert items == []


def test_integrators_compares_draft_versions() -> None:
    """A draft comes before the release of the same three numbers."""
    text = (
        "# Changelog\n\n## 3.4.1 — 2026-12-01\n\n**Integrators:**\n\n"
        "- `L1`: released change.\n\n" + CHANGELOG.split("\n", 1)[1]
    )
    items = integrators(text, "3.4.1-draft", "3.4.1", levels=[1], mode="webhook")
    assert [item["version"] for item in items] == ["3.4.1"]
    assert integrators(text, "3.4.1", "3.4.1", levels=[1], mode="webhook") == []
    assert integrators(text, "3.4.0", "3.4.1-draft", levels=[1], mode="webhook") == []
