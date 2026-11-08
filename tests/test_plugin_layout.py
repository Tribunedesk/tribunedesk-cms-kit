from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
PLUGIN_DIR = ROOT / "plugins" / "tribunedesk-integration"
SKILL_DIR = PLUGIN_DIR / "skills" / "tribunedesk-integration"
NAME = "tribunedesk-integration"


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert match, f"{path} has no frontmatter"
    fields: dict[str, str] = {}
    for line in match[1].splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def test_names_agree_in_marketplace_plugin_and_skill() -> None:
    marketplace = load(MARKETPLACE)
    assert marketplace["name"] == "tribunedesk"
    [entry] = marketplace["plugins"]
    plugin = load(PLUGIN_DIR / ".claude-plugin" / "plugin.json")
    assert entry["name"] == plugin["name"] == NAME
    assert frontmatter(SKILL_DIR / "SKILL.md")["name"] == NAME


def test_marketplace_source_points_to_the_plugin() -> None:
    [entry] = load(MARKETPLACE)["plugins"]
    assert (ROOT / entry["source"]).resolve() == PLUGIN_DIR.resolve()
    assert (PLUGIN_DIR / ".claude-plugin" / "plugin.json").is_file()


def test_skill_frontmatter_has_name_and_short_description() -> None:
    fields = frontmatter(SKILL_DIR / "SKILL.md")
    assert fields["name"]
    assert fields["description"]
    assert len(fields["description"]) <= 1024
    for phrase in ("Zbuduj mi integrację z Tribune Desk", "update my Tribune Desk integration"):
        assert phrase in fields["description"]
