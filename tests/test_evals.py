"""The eval cases keep the `claude plugin eval` case format (plan E9.6, Task 3).

Running them needs WSL and a subscription (evals/README.md); these checks catch a broken case
before that costs a run.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "plugins" / "tribunedesk-integration" / "evals"
CASES = sorted(p for p in EVALS.iterdir() if (p / "prompt.md").is_file())

PROMPT_KEYS = {
    "schema_version",
    "name",
    "description",
    "tags",
    "plugins",
    "runs",
    "expected_outcome",
    "model",
    "max_turns",
    "timeout_seconds",
    "allowed_tools",
    "append_system_prompt",
    "env",
}
GRADER_TYPES = {"regex", "tool_used", "tool_order", "file_exists", "llm", "baseline"}
CACHE = "/opt/tribunedesk-evals"


def frontmatter(path: Path) -> tuple[dict[str, str], dict[str, dict[str, str]], str]:
    """Top-level keys, one level of nested keys, and the body. Enough for these files."""
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    head, body = text[4:].split("\n---\n", 1)
    top: dict[str, str] = {}
    nested: dict[str, dict[str, str]] = {}
    current = ""
    for line in head.splitlines():
        if not line.strip():
            continue
        key, _, value = line.strip().partition(":")
        if line.startswith(" "):
            nested.setdefault(current, {})[key] = value.strip()
        else:
            current = key
            top[key] = value.strip()
    return top, nested, body


def unquote(value: str) -> str:
    return value[1:-1] if value[:1] in "'\"" and value[-1:] == value[:1] else value


def test_six_cases() -> None:
    names = {case.name for case in CASES}
    assert names == {
        "django-l12",
        "drupal-l12",
        "photos-only",
        "no-public-endpoint",
        "update-3.2",
        "ghost",
    }


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_prompt_and_case_yaml(case: Path) -> None:
    top, nested, body = frontmatter(case / "prompt.md")
    assert set(top) <= PROMPT_KEYS, set(top) - PROMPT_KEYS
    assert body.strip()
    assert int(top["max_turns"]) <= 200
    assert int(top["timeout_seconds"]) <= 3600
    for key, value in nested.get("env", {}).items():
        assert re.fullmatch(r"EVAL_[A-Z0-9_]*", key), key
        assert value.startswith(CACHE), value
    case_yaml = (case / "case.yaml").read_text(encoding="utf-8")
    assert 'schema_version: "1.1"' in case_yaml
    assert f"name: {case.name}\n" in case_yaml
    assert "scaffold_script: scaffold.sh" in case_yaml


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_graders(case: Path) -> None:
    graders = sorted((case / "graders").glob("*.md"))
    assert graders
    assert (case / "graders" / "skill-fired.md").is_file()
    for path in graders:
        top, nested, body = frontmatter(path)
        assert top["type"] in GRADER_TYPES, path
        if top["type"] == "llm":
            assert "PASS" in body and "FAIL" in body, path
        for key in ("pattern", "input_match"):
            if key in top:
                re.compile(unquote(top[key]))
        # Without the plugin there is no tdkit: such graders must not count in the baseline.
        uses_tdkit = "[Tt][Dd][Kk][Ii][Tt]" in top.get("input_match", "") or ".tribunedesk/" in (
            nested.get("target", {}).get("path", "")
        )
        if uses_tdkit:
            assert top.get("arm") == "with-only", path


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_scaffold_only_copies(case: Path) -> None:
    raw = (case / "scaffold.sh").read_bytes()
    assert b"\r\n" not in raw, "bash needs LF line endings"
    text = raw.decode("utf-8")
    assert text.startswith("#!/usr/bin/env bash\n")
    assert "set -euo pipefail" in text
    # 120 s and no EVAL_* variables: no installs, no network.
    for forbidden in ("pip install", "uv sync", "composer install", "composer require", "curl"):
        assert forbidden not in text, forbidden
    assert "$EVAL_" not in text and "${EVAL_" not in text


def test_secret_grader_pattern() -> None:
    """The trace grader flags a secret written into a tracked file, not into `.env`."""
    path = EVALS / "django-l12" / "graders" / "no-secret-in-tracked-files.md"
    pattern = re.compile(unquote(frontmatter(path)[0]["pattern"]))
    secret = "whsec_" + "A" * 32
    leak = f'{{"name":"Write","input":{{"file_path":"/w/blogsite/settings.py","content":"S=\\"{secret}\\""}}}}'
    env = f'{{"name":"Write","input":{{"file_path":"/w/.env","content":"TD_SECRET={secret}"}}}}'
    assert pattern.search(leak)
    assert not pattern.search(env)


def test_setup_script_is_lf() -> None:
    assert b"\r\n" not in (ROOT / "evals" / "setup.sh").read_bytes()
