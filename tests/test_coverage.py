"""Coverage of the contract (spec 2026-11-13 kontrakt najpierw, D3).

Every point of a guide's "Done when" has a scenario or an explicit reason, and every tagged item
of the CHANGELOG `**Integrators:**` lists is handled by a scenario, a file of the skill or an
explicit `none`. The data is `src/tdkit/check/coverage.toml`; the documentation is the fixture,
a copy of `CONTRACT_TAG`. A new tag with a new point turns this red until someone handles it.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from tdkit.check.scenarios import SCENARIOS
from tdkit.check.scenarios_media import MEDIA_SCENARIOS
from tdkit.integrators import KNOWN_TAGS, changelog_items

from .conftest import FIXTURE

KIT = Path(__file__).parent.parent
COVERAGE = KIT / "src" / "tdkit" / "check" / "coverage.toml"
SKILL = KIT / "plugins" / "tribunedesk-integration" / "skills" / "tribunedesk-integration"
QUOTES = {s.done_when for s in (*SCENARIOS, *MEDIA_SCENARIOS)}
SCENARIO_IDS = {s.id for s in (*SCENARIOS, *MEDIA_SCENARIOS)}


def done_when_points(guide_dir: Path) -> list[tuple[str, str]]:
    """`(guide/<file>, point)` for every bullet of every "## Done when" section."""
    points: list[tuple[str, str]] = []
    for path in sorted(guide_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if "\n## Done when\n" not in text:
            continue
        section = text.split("\n## Done when\n", 1)[1].split("\n## ", 1)[0]
        for line in section.splitlines():
            if line.startswith("- "):
                points.append((f"guide/{path.name}", line[2:].strip()))
    return points


def problems(guide_dir: Path, changelog: str, entries: dict[str, Any]) -> list[str]:
    """What is missing, stale or wrong; empty when the contract is covered."""
    found: list[str] = []
    points = done_when_points(guide_dir)
    done_when = {(e["guide"], e["point"]): e for e in entries.get("done_when", [])}
    for key in points:
        if any(quote in key[1] for quote in QUOTES):
            continue
        if key not in done_when:
            found.append(f"Done when without a scenario or entry: {key[0]}: {key[1]}")
    for key, entry in done_when.items():
        if key not in points:
            found.append(f"stale [[done_when]] entry: {key[0]}: {key[1]}")
        has_scenarios, has_reason = bool(entry.get("scenarios")), bool(entry.get("reason"))
        if has_scenarios == has_reason:
            found.append(f"[[done_when]] needs scenarios or a reason, not both: {key[1]}")
        for sid in entry.get("scenarios", []):
            if sid not in SCENARIO_IDS:
                found.append(f"[[done_when]] names an unknown scenario {sid}: {key[1]}")

    items = changelog_items(changelog)
    integrators = {(e["version"], e["action"]): e for e in entries.get("integrators", [])}
    for item in items:
        unknown = [t for t in item["tags"] if t not in KNOWN_TAGS]
        if unknown:
            found.append(f"{item['version']}: unknown tag(s) {', '.join(unknown)}: teach tdkit")
        if (item["version"], item["action"]) not in integrators:
            found.append(f"Integrators item not handled: {item['version']}: {item['action']}")
    keys = {(i["version"], i["action"]) for i in items}
    for key, entry in integrators.items():
        if key not in keys:
            found.append(f"stale [[integrators]] entry: {key[0]}: {key[1]}")
        handled = entry.get("handled_by", [])
        if not handled:
            found.append(f"[[integrators]] without handled_by: {key[1]}")
        if "none" in handled and (len(handled) > 1 or not entry.get("reason")):
            found.append(f"[[integrators]] `none` stands alone and needs a reason: {key[1]}")
        for ref in handled:
            kind, _, name = ref.partition(":")
            if kind == "scenario" and name not in SCENARIO_IDS:
                found.append(f"[[integrators]] names an unknown scenario {name}: {key[1]}")
            elif kind == "skill" and not (SKILL / name).is_file():
                found.append(f"[[integrators]] names a missing skill file {name}: {key[1]}")
            elif kind not in ("scenario", "skill", "none"):
                found.append(f"[[integrators]] unknown handled_by {ref}: {key[1]}")
    return found


def _entries() -> dict[str, Any]:
    return tomllib.loads(COVERAGE.read_text(encoding="utf-8"))


def _changelog() -> str:
    return (FIXTURE / "CHANGELOG.md").read_text(encoding="utf-8")


def test_every_done_when_point_is_covered() -> None:
    entries = {"done_when": _entries().get("done_when", [])}
    assert problems(FIXTURE / "guide", "", entries) == []


def test_every_integrators_item_is_handled(tmp_path: Path) -> None:
    entries = {"integrators": _entries().get("integrators", [])}
    assert problems(tmp_path, _changelog(), entries) == []  # no guide: the CHANGELOG half only


def test_the_whole_file_is_clean() -> None:
    assert problems(FIXTURE / "guide", _changelog(), _entries()) == []


def test_stale_entry_is_reported(tmp_path: Path) -> None:
    (tmp_path / "1-x.md").write_text("# X\n\n## Done when\n\n- New wording.\n", encoding="utf-8")
    entries = {"done_when": [{"guide": "guide/1-x.md", "point": "Old wording.", "reason": "r"}]}
    found = problems(tmp_path, "", entries)
    assert any(f.startswith("Done when without") for f in found)
    assert any(f.startswith("stale [[done_when]]") for f in found)


def test_entries_name_real_scenarios_and_files(tmp_path: Path) -> None:
    changelog = "## 9.0.0\n\n**Integrators:**\n\n- `L1`: do a thing.\n"
    entry = {"version": "9.0.0", "action": "do a thing.", "handled_by": ["scenario:nope"]}
    assert problems(tmp_path, changelog, {"integrators": [entry]}) != []
    entry["handled_by"] = ["skill:references/missing.md"]
    assert problems(tmp_path, changelog, {"integrators": [entry]}) != []
    entry["handled_by"] = ["scenario:l1-bad-signature", "skill:SKILL.md"]
    assert problems(tmp_path, changelog, {"integrators": [entry]}) == []


def test_entry_has_exactly_one_of_scenarios_or_reason(tmp_path: Path) -> None:
    (tmp_path / "1-x.md").write_text("# X\n\n## Done when\n\n- A point.\n", encoding="utf-8")
    both = {"guide": "guide/1-x.md", "point": "A point.", "scenarios": ["l1-bad-signature"]}
    both["reason"] = "r"
    assert problems(tmp_path, "", {"done_when": [both]}) != []
    changelog = "## 9.0.0\n\n**Integrators:**\n\n- `L1`: do a thing.\n"
    bare_none = {"version": "9.0.0", "action": "do a thing.", "handled_by": ["none"]}
    assert problems(tmp_path, changelog, {"integrators": [bare_none]}) != []


def test_integrators_key_includes_version(tmp_path: Path) -> None:
    changelog = (
        "## 9.1.0\n\n**Integrators:**\n\n- `L1`: same advice.\n\n"
        "## 9.0.0\n\n**Integrators:**\n\n- `L1`: same advice.\n"
    )
    one = {
        "version": "9.1.0",
        "action": "same advice.",
        "handled_by": ["scenario:l1-bad-signature"],
    }
    found = problems(tmp_path, changelog, {"integrators": [one]})
    assert found == ["Integrators item not handled: 9.0.0: same advice."]


def test_unknown_level_tag_fails(tmp_path: Path) -> None:
    changelog = "## 9.0.0\n\n**Integrators:**\n\n- `L5`: send your archive.\n"
    entry = {"version": "9.0.0", "action": "send your archive.", "handled_by": ["skill:SKILL.md"]}
    found = problems(tmp_path, changelog, {"integrators": [entry]})
    assert any("unknown tag(s) L5" in f for f in found)


def test_the_file_is_red_without_an_entry() -> None:
    """The real data with one entry removed fails: the test can fail at all."""
    entries = _entries()
    entries["integrators"] = entries["integrators"][1:]
    entries["done_when"] = entries["done_when"][1:]
    assert len(problems(FIXTURE / "guide", _changelog(), entries)) == 2
