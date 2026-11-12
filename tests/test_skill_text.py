"""Rules the skill's text must keep (plan E9.5, Task 3-5)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from tdkit.cli import build_parser

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "plugins" / "tribunedesk-integration" / "skills" / "tribunedesk-integration"
SKILL = SKILL_DIR / "SKILL.md"
REFERENCES = SKILL_DIR / "references"
FIXTURE = Path(__file__).parent / "fixtures" / "cms-api"

CMS_SECTIONS = (
    "## 1. Raw body and the webhook route",
    "## 2. Secret and token",
    "## 3. Unique key and lock",
    "## 4. Publish hook and link back",
    "## 5. Edit URL",
    "## 6. Images",
    "## 7. Developer commands",
    "## 8. Running the project's tests",
    "## 9. Pitfalls",
)


def skill_text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_skill_under_500_lines() -> None:
    assert len(skill_text().splitlines()) <= 500


def test_skill_has_preapproval_rule() -> None:
    text = skill_text()
    assert "approved the plan in the request" in text


def test_skill_states_level_4_not_covered() -> None:
    text = skill_text()
    assert re.search(r"tdkit 1\.0 does not test level 4", text)
    assert "photos only" in text.lower() or "only photos" in text.lower()


def test_skill_lists_every_cms_reference_and_generic() -> None:
    text = skill_text()
    files = sorted(p.name for p in (REFERENCES / "cms").glob("*.md"))
    assert "generic.md" in files
    for name in files:
        assert f"references/cms/{name}" in text, name
    for path in REFERENCES.glob("*.md"):
        assert f"references/{path.name}" in text, path.name


def test_skill_never_names_contract_fields_without_docs_pointer() -> None:
    for number, line in enumerate(skill_text().splitlines(), 1):
        if "/v3/cms/" in line:
            assert re.search(r"guide/\S+\.md|README\.md", line), f"line {number}: {line}"


def test_tdkit_commands_in_skill_exist() -> None:
    parser = build_parser()
    sub = next(a for a in parser._actions if a.dest == "command")
    commands = set(sub.choices)  # type: ignore[union-attr]
    used = set(re.findall(r"TDKIT ([a-z][a-z-]*)", skill_text()))
    assert used, "the skill names no TDKIT command"
    assert used <= commands, used - commands


def test_every_cms_reference_has_all_sections() -> None:
    for path in sorted((REFERENCES / "cms").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for section in CMS_SECTIONS:
            assert section in text, f"{path.name}: {section}"


def test_references_have_no_contract_copies() -> None:
    """No JSON blocks of delivery bodies: the contract is read from the downloaded docs."""
    openapi = json.loads((FIXTURE / "openapi.json").read_text(encoding="utf-8"))
    fields = set(openapi["components"]["schemas"]["ArticleDelivery"]["properties"])
    for path in [*REFERENCES.glob("*.md"), *(REFERENCES / "cms").glob("*.md"), SKILL]:
        text = path.read_text(encoding="utf-8")
        for block in re.findall(r"```(?:json)?\n(.*?)```", text, re.S):
            named = {f for f in fields if f'"{f}"' in block}
            assert len(named) < 3, f"{path.name} copies delivery fields: {sorted(named)}"


def test_skill_requires_git_and_passes_the_downloaded_docs() -> None:
    text = skill_text()
    assert "git is required" in text
    assert re.search(r"TDKIT check[^\n]*--docs", text)
    assert re.search(r"TDKIT integrators[^\n]*--docs", text)


def test_skill_never_passes_level_4_to_check() -> None:
    assert "without level 4" in skill_text()


def test_skill_keeps_env_and_report_out_of_git() -> None:
    text = skill_text()
    assert re.search(r"`\.env`[^\n]*\.gitignore", text)
    assert ".tribunedesk/tdkit-report.json" in text


def test_skill_stage_7_is_scoped() -> None:
    text = skill_text()
    stage = text.split("### Stage 7.", 1)[1].split("\n## ", 1)[0]
    for heading in ("**Webhook mode", "**Read mode", "**Level 4 only"):
        assert heading in stage, heading
    level4 = stage.split("**Level 4 only", 1)[1].split("\n**", 1)[0]
    assert "webhook" not in level4.lower()


def test_last_message_stands_alone() -> None:
    """django-l12 runs 1-5 (E9.6): with the plan approved up front the welcome, the plan and the
    stage summaries landed between tool calls (often as thinking); only the last message was
    reliably complete. Owner's choice 2026-11-12: the last message carries them."""
    text = skill_text()
    assert "### The last message of a turn" in text
    assert "the last message of every turn stands alone" in text
    assert "Never say you showed something you did not" in text


def test_tdkit_reference_gives_the_mock_secret() -> None:
    """Second django-l12 run: the agent could not find the mock's secret and made its own."""
    from tdkit.signing import MOCK_SECRET

    assert MOCK_SECRET in (REFERENCES / "tdkit.md").read_text(encoding="utf-8")
