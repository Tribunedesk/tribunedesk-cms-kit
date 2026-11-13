import json
import shutil
from pathlib import Path

import pytest

from tdkit.docs import is_supported, latest_tag, resolve_docs
from tdkit.errors import UsageError

FIXTURE = Path(__file__).parent / "fixtures" / "cms-api"


def test_resolve_docs_from_dir() -> None:
    docs = resolve_docs(None, FIXTURE)
    assert docs.root == FIXTURE
    assert docs.version == "3.4.1-draft"
    assert "/v3/cms/status" in docs.openapi["paths"]
    assert docs.sample_delivery["article_id"]
    assert len(docs.vectors) >= 5


def test_resolve_docs_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRIBUNEDESK_DOCS_DIR", str(FIXTURE))
    docs = resolve_docs(None, None)
    assert docs.root == FIXTURE
    assert is_supported(docs.version)


def test_unsupported_contract_is_usage_error(tmp_path: Path) -> None:
    root = tmp_path / "cms-api"
    shutil.copytree(FIXTURE, root)
    openapi_path = root / "openapi.json"
    openapi = json.loads(openapi_path.read_text(encoding="utf-8"))
    openapi["info"]["version"] = "9.0.0"
    openapi_path.write_text(json.dumps(openapi), encoding="utf-8")
    with pytest.raises(
        UsageError, match=r"contract 9\.0\.0 is not supported by tdkit .*; update the plugin"
    ):
        resolve_docs(None, root)


def test_contract_tag_must_match_local_copy() -> None:
    with pytest.raises(UsageError, match=r"3.4.0-draft"):
        resolve_docs("v3.4.0-draft", FIXTURE)


def test_latest_tag_sorts_versions() -> None:
    lines = [
        "0e61\trefs/tags/v3.2.0-draft",
        "a12d\trefs/tags/v3.4.1-draft",
        "4231\trefs/tags/v3.4.0-draft",
        "9999\trefs/tags/v3.10.0-draft",
        "abcd\trefs/tags/not-a-version",
        "",
    ]
    assert latest_tag(lines) == "v3.10.0-draft"
    assert latest_tag(["1\trefs/tags/v3.4.1-draft", "2\trefs/tags/v3.4.1"]) == "v3.4.1"


@pytest.mark.parametrize(
    ("version", "ok"),
    [
        ("3.4.0-draft", True),
        ("3.4.2-draft", True),
        ("3.4.17", True),
        ("3.5.0-draft", False),
        ("4.0.0", False),
        ("3.4.x-draft", False),
    ],
)
def test_every_patch_of_the_supported_minor_is_accepted(version, ok):
    """A patch changes no shape (VERSIONING), so a docs patch must not stop the skill."""
    assert is_supported(version) is ok


def test_fixture_is_3_4_2_with_guide_4() -> None:
    from tdkit.docs import load_docs

    from .conftest import FIXTURE

    assert load_docs(FIXTURE).version == "3.4.2-draft"
    assert (FIXTURE / "guide/4-media-library.md").is_file()


def test_readme_lists_every_scenario() -> None:
    from pathlib import Path

    from tdkit.check.scenarios import SCENARIOS
    from tdkit.check.scenarios_media import MEDIA_SCENARIOS

    readme = (Path(__file__).parent.parent / "README.md").read_text(encoding="utf-8")
    missing = [s.id for s in (*SCENARIOS, *MEDIA_SCENARIOS) if f"`{s.id}`" not in readme]
    assert not missing


def test_readme_lists_every_check_and_mock_option() -> None:
    import argparse
    from pathlib import Path

    from tdkit.cli import build_parser

    readme = (Path(__file__).parent.parent / "README.md").read_text(encoding="utf-8")
    parser = build_parser()
    subparsers = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    missing = []
    for name in ("mock", "check"):
        for action in subparsers.choices[name]._actions:
            for flag in action.option_strings:
                if flag.startswith("--") and flag != "--help" and flag not in readme:
                    missing.append(f"{name} {flag}")
    assert not missing
