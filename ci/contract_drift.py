"""Is the kit's contract pin behind the newest tag of `tribunedesk-cms-api`? If so, bump it.

    uv run python ci/contract_drift.py --body-out BODY.md [--open-pr-pin TAG]

Run by `.github/workflows/contract-drift.yml` (spec 2026-11-13 kontrakt najpierw, D2b). It
compares `ci/contract-tag` (the pin every job of `ci.yml` reads) with the newest `v*` tag:

- current: prints so and exits 0;
- ahead (the pin names a tag newer than any tag, e.g. a deleted one): exits 1, changes nothing;
- behind, and the open pull request (`--open-pr-pin`, the pin on `contract/latest`) is already
  at the newest tag: changes nothing, sets `behind=true` and `rebuild=false`, so the workflow
  keeps that branch and whatever was pushed onto it;
- behind otherwise: rewrites the pin, replaces `tests/fixtures/cms-api` with the files of the
  tag the tests read, writes the pull request body (the `Integrators` items in between) to
  `--body-out`, sets `behind=true` and `rebuild=true`, exits 0.

`pinned=` and `tag=` go to `$GITHUB_OUTPUT` with every `behind`. The workflow fails the run
while the pin is behind, so it stays red every day until the pull request lands.

The pin is not a line of `ci.yml`: GITHUB_TOKEN may not push changes under `.github/workflows/`.

Network: `git ls-remote` and a shallow `git clone` of the public repository, nothing else.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Literal

from tdkit.docs import REPO_URL, latest_tag
from tdkit.integrators import changelog_items, version_key

KIT = Path(__file__).resolve().parents[1]
PIN = KIT / "ci" / "contract-tag"
FIXTURE = KIT / "tests" / "fixtures" / "cms-api"
# What the tests read from a tag; example code would land under tests/ for ruff and pyright.
FIXTURE_FILES = ("CHANGELOG.md", "README.md", "openapi.json")
FIXTURE_DIRS = ("guide", "examples/payloads", "examples/vectors")


def _git(args: list[str]) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout


def read_pin(path: Path) -> str:
    tag = path.read_text(encoding="utf-8").strip()
    if not tag.startswith("v"):
        raise SystemExit(f"{path} does not hold a contract tag: {tag!r}")
    return tag


def compare(pinned: str, latest: str) -> Literal["current", "behind", "ahead"]:
    old, new = version_key(pinned), version_key(latest)
    return "current" if old == new else "behind" if old < new else "ahead"


def refresh_fixture(source: Path, fixture: Path) -> None:
    """Replace `fixture` with the files of `source` the tests read; nothing else survives."""
    if fixture.exists():
        shutil.rmtree(fixture)
    fixture.mkdir(parents=True)
    for name in FIXTURE_FILES:
        if (source / name).is_file():
            shutil.copy2(source / name, fixture / name)
    for name in FIXTURE_DIRS:
        if (source / name).is_dir():
            shutil.copytree(source / name, fixture / name)


def pr_body(changelog: str, pinned: str, latest: str) -> str:
    low, high = version_key(pinned), version_key(latest)
    lines = [
        f"The contract has a newer tag: `{pinned}` → `{latest}`.",
        "",
        f"CHANGELOG: {REPO_URL}/blob/{latest}/CHANGELOG.md",
        "",
        "This pull request moves `ci/contract-tag` and `tests/fixtures/cms-api` to the new tag;",
        "its CI shows what the new tag breaks. A new point of a guide's “Done when” or a new",
        "`Integrators` item needs a scenario or an entry in `src/tdkit/check/coverage.toml`.",
        "Commits pushed onto this branch stay until a newer tag replaces it.",
        "",
        "**Integrators** items in between:",
        "",
    ]
    items = [i for i in changelog_items(changelog) if low < version_key(i["version"]) <= high]
    for item in items:
        tags = ", ".join(f"`{t}`" for t in item["tags"])
        lines.append(f"- {item['version']} {tags}: {item['action']}")
    if not items:
        lines.append("- Nothing to do.")
    return "\n".join(lines) + "\n"


def _output(**values: str) -> None:
    target = os.environ.get("GITHUB_OUTPUT")
    if not target:
        return
    with Path(target).open("a", encoding="utf-8") as out:
        for key, value in values.items():
            out.write(f"{key}={value}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--body-out", type=Path, required=True)
    parser.add_argument("--open-pr-pin", default="", help="the pin on contract/latest, if any")
    args = parser.parse_args(argv)

    pinned = read_pin(PIN)
    latest = latest_tag(_git(["ls-remote", "--tags", "--refs", REPO_URL]).splitlines())
    state = compare(pinned, latest)
    if state == "current":
        print(f"The pin {pinned} is the newest tag.")
        _output(behind="false")
        return 0
    if state == "ahead":
        print(f"The pin {pinned} is newer than the newest tag {latest}.", file=sys.stderr)
        return 1
    if args.open_pr_pin.strip() == latest:
        print(f"The pin {pinned} is behind {latest}; contract/latest already moves it.")
        _output(behind="true", rebuild="false", pinned=pinned, tag=latest)
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "cms-api"
        _git(["clone", "--quiet", "--depth", "1", "--branch", latest, REPO_URL, str(source)])
        changelog = (source / "CHANGELOG.md").read_text(encoding="utf-8")
        refresh_fixture(source, FIXTURE)
    PIN.write_bytes(f"{latest}\n".encode())
    args.body_out.write_text(pr_body(changelog, pinned, latest), encoding="utf-8")
    print(f"The pin {pinned} is behind {latest}; pin and fixture moved.")
    _output(behind="true", rebuild="true", pinned=pinned, tag=latest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
