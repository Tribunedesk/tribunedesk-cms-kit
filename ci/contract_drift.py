"""Is the kit's contract pin behind the newest tag of `tribunedesk-cms-api`? If so, bump it.

    uv run python ci/contract_drift.py --body-out BODY.md

Run by `.github/workflows/contract-drift.yml` (spec 2026-11-13 kontrakt najpierw, D2b). It
compares `CONTRACT_TAG` in `.github/workflows/ci.yml` with the newest `v*` tag:

- current: prints so and exits 0;
- ahead (the pin names a tag newer than any tag, e.g. a deleted one): exits 1, changes nothing;
- behind: rewrites the pin, replaces `tests/fixtures/cms-api` with the tag's tree, writes the
  pull request body (the `Integrators` items in between) to `--body-out`, sets `behind=true`,
  `pinned=` and `tag=` in `$GITHUB_OUTPUT`, exits 0. The workflow commits, opens the pull
  request and then fails the run, so a pin left behind stays red every day.

Network: `git ls-remote` and a shallow `git clone` of the public repository, nothing else.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Literal

from tdkit.docs import REPO_URL, latest_tag
from tdkit.integrators import changelog_items, version_key

KIT = Path(__file__).resolve().parents[1]
CI_YML = KIT / ".github" / "workflows" / "ci.yml"
FIXTURE = KIT / "tests" / "fixtures" / "cms-api"
_PIN = re.compile(r"^(  CONTRACT_TAG: )(v\S+)$", re.M)


def _git(args: list[str]) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout


def pinned_tag(ci_yml: str) -> str:
    match = _PIN.search(ci_yml)
    if not match:
        raise SystemExit("ci.yml has no workflow-level `  CONTRACT_TAG: v…` line")
    return match[2]


def with_pin(ci_yml: str, tag: str) -> str:
    """`ci_yml` with only the `CONTRACT_TAG` line changed."""
    pinned_tag(ci_yml)
    return _PIN.sub(lambda m: m[1] + tag, ci_yml, count=1)


def compare(pinned: str, latest: str) -> Literal["current", "behind", "ahead"]:
    old, new = version_key(pinned), version_key(latest)
    return "current" if old == new else "behind" if old < new else "ahead"


def refresh_fixture(source: Path, fixture: Path) -> None:
    """Replace `fixture` with `source`, without `.git` and `.github`."""
    if fixture.exists():
        shutil.rmtree(fixture)
    shutil.copytree(source, fixture, ignore=shutil.ignore_patterns(".git", ".github"))


def pr_body(changelog: str, pinned: str, latest: str) -> str:
    low, high = version_key(pinned), version_key(latest)
    lines = [
        f"The contract has a newer tag: `{pinned}` → `{latest}`.",
        "",
        f"CHANGELOG: {REPO_URL}/blob/{latest}/CHANGELOG.md",
        "",
        "This pull request moves `CONTRACT_TAG` and `tests/fixtures/cms-api` to the new tag;",
        "its CI shows what the new tag breaks. A new point of a guide's “Done when” or a new",
        "`Integrators` item needs a scenario or an entry in `src/tdkit/check/coverage.toml`.",
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
    args = parser.parse_args(argv)

    ci_yml = CI_YML.read_text(encoding="utf-8")
    pinned = pinned_tag(ci_yml)
    latest = latest_tag(_git(["ls-remote", "--tags", "--refs", REPO_URL]).splitlines())
    state = compare(pinned, latest)
    if state == "current":
        print(f"CONTRACT_TAG {pinned} is the newest tag.")
        _output(behind="false")
        return 0
    if state == "ahead":
        print(f"CONTRACT_TAG {pinned} is newer than the newest tag {latest}.", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "cms-api"
        _git(["clone", "--quiet", "--depth", "1", "--branch", latest, REPO_URL, str(source)])
        changelog = (source / "CHANGELOG.md").read_text(encoding="utf-8")
        refresh_fixture(source, FIXTURE)
    CI_YML.write_bytes(with_pin(ci_yml, latest).encode("utf-8"))
    args.body_out.write_text(pr_body(changelog, pinned, latest), encoding="utf-8")
    print(f"CONTRACT_TAG {pinned} is behind {latest}; pin and fixture moved.")
    _output(behind="true", pinned=pinned, tag=latest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
