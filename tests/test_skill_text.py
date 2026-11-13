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


def test_skill_runs_check_for_level_4() -> None:
    text = skill_text()
    assert "does not test level 4" not in text
    assert "without level 4" not in text
    assert "photos only" in text.lower() or "only photos" in text.lower()
    tdkit = (REFERENCES / "tdkit.md").read_text(encoding="utf-8")
    for needle in ("--levels 4", "--mode none", "--sync-cmd", "--reset-cmd", "--backfill"):
        assert needle in tdkit, needle


def test_cms_references_have_level_4_section() -> None:
    for name in ("generic.md", "laravel.md", "django.md", "wordpress.md"):
        text = (REFERENCES / "cms" / name).read_text(encoding="utf-8")
        assert "## 10. Level 4 (media library)" in text, name
    generic = (REFERENCES / "cms" / "generic.md").read_text(encoding="utf-8")
    for needle in ("CmsSync.php", "Staging", "held batches", "resync", "changed_at", "lock"):
        assert needle in generic, needle


def test_scope_splits_level_4() -> None:
    scope = (REFERENCES / "scope.md").read_text(encoding="utf-8")
    section = scope.split("## Level 4: core and options", 1)[1].split("\n## ", 1)[0]
    for needle in ("**Core**", "**Optional**", "backfill", "push-existing", "PUT /settings"):
        assert needle in section, needle


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
    # ghost run: not pre-approved, the welcome was only a heading in the first turn.
    assert "The last message of the first turn also opens with the two sentences" in text
    assert "as the first lines of the last" in text
    assert "Never say you showed something you did not" in text


def test_publish_finishes_the_link_back() -> None:
    """`check` reads the report right after --publish-cmd returns (scenario l2-reports-url)."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "before it exits" in readme
    for path in sorted((REFERENCES / "cms").glob("*.md")):
        assert "before it exits" in path.read_text(encoding="utf-8"), path.name


def test_generic_reference_covers_cases_without_a_user_or_tests() -> None:
    generic = (REFERENCES / "cms" / "generic.md").read_text(encoding="utf-8")
    for needle in (
        "**Scheduled publication.**",
        "**No logged-in user.**",
        "`TD_SITE_URL`",
        "**Secrets without environment variables.**",
        "**No tests in the project.**",
    ):
        assert needle in generic, needle


def test_drupal_reference_points_to_the_kit_reference() -> None:
    drupal = (REFERENCES / "cms" / "drupal.md").read_text(encoding="utf-8")
    assert "reference/drupal" in drupal


def test_php_library_reference_names_the_secret_variables() -> None:
    php = (REFERENCES / "php-library.md").read_text(encoding="utf-8")
    for name in ("TD_WEBHOOK_SECRET", "TD_CMS_TOKEN", "TD_API_BASE"):
        assert name in php, name
    assert "WebhookSignature::verify($secret" in php


def test_php_library_reference_explains_the_library_readme_name() -> None:
    """The library README reads TRIBUNEDESK_WEBHOOK_SECRET; the kit names it TD_WEBHOOK_SECRET."""
    php = (REFERENCES / "php-library.md").read_text(encoding="utf-8")
    section = php.split("## Secret and token names", 1)[1]
    assert "TRIBUNEDESK_WEBHOOK_SECRET" in section
    assert "do not give the library other names" not in section


def test_drupal_link_back_queue_is_flushed_by_publish() -> None:
    drupal = (REFERENCES / "cms" / "drupal.md").read_text(encoding="utf-8")
    section = drupal.split("## 4. Publish hook and link back", 1)[1].split("\n## ", 1)[0]
    assert "td:publish" in section


def test_docs_flag_is_the_same_in_update_mode_and_tdkit_reference() -> None:
    update = (REFERENCES / "update-mode.md").read_text(encoding="utf-8")
    assert "--contract <new tag>" not in update
    assert "TDKIT check --docs <path>" in update
    tdkit = (REFERENCES / "tdkit.md").read_text(encoding="utf-8")
    assert "cms-api@v3." not in tdkit


def test_tdkit_reference_gives_the_mock_secret() -> None:
    """Second django-l12 run: the agent could not find the mock's secret and made its own."""
    from tdkit.signing import MOCK_SECRET

    assert MOCK_SECRET in (REFERENCES / "tdkit.md").read_text(encoding="utf-8")


def test_skill_pins_tdkit_tag() -> None:
    """The skill runs the tdkit of its own release, and the plugin carries the same version."""
    from tdkit import __version__

    plugin = json.loads(
        (ROOT / "plugins" / "tribunedesk-integration" / ".claude-plugin" / "plugin.json").read_text(
            encoding="utf-8"
        )
    )
    assert f"tribunedesk-cms-kit@v{__version__} tdkit" in skill_text()
    assert plugin["version"] == __version__


def test_message_rules_do_not_contradict() -> None:
    """Final review of E9.6: stage 0 still said "first message", stage 5 and the template did
    not mention the pre-approval exception of "The last message of a turn"."""
    text = skill_text()
    assert "Your first message to the user is the welcome" not in text
    template = text.split("### Stage summary template", 1)[1].split("###", 1)[0]
    stage5 = text.split("### Stage 5.", 1)[1].split("###", 1)[0]
    for part in (template, stage5):
        assert "pre-approv" in part.lower(), part[:80]


def test_skill_gitignore_sentence_matches_docs_command() -> None:
    assert "when the project has a `.gitignore` or is a git repository" in skill_text()


def test_cms_references_name_the_ca_bundle() -> None:
    """D5: the mock serves files over https with a test CA; each CMS says how to trust it."""
    for path in sorted((REFERENCES / "cms").glob("*.md")):
        if path.name == "ghost.md":
            continue
        assert "TD_CA_BUNDLE" in path.read_text(encoding="utf-8"), path.name
    assert "TD_CA_BUNDLE" in (REFERENCES / "tdkit.md").read_text(encoding="utf-8")


def test_wordpress_reference_lets_wordpress_reach_the_mock() -> None:
    """wp_safe_remote_get refuses loopback hosts and ports other than 80, 443 and 8080."""
    text = (REFERENCES / "cms" / "wordpress.md").read_text(encoding="utf-8")
    assert "http_request_host_is_external" in text
    assert "http_allowed_safe_ports" in text
