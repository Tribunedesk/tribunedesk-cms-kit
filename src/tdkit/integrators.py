"""The `**Integrators:**` lists of the contract CHANGELOG between two versions.

Each item starts with its tags in backticks, then a colon: `` - `L1`: verify the signature``.
Known tags are `L1`-`L4` and `read`. An item is for an integration when one of its level tags
is a level the integration built; an item tagged `read` is only for read mode. Unknown tags
(a future `L5`) are dropped with a warning on stderr; "Nothing to do." is skipped.
"""

from __future__ import annotations

import re
import sys
from typing import Any

KNOWN_TAGS = ("L1", "L2", "L3", "L4", "read")

_VERSION = re.compile(r"^## (\d+)\.(\d+)\.(\d+)(-draft)?\b")
_ITEM = re.compile(r"^- ((?:`[^`]+`(?:,\s*|\s+)?)+):\s*(.+)$")


def version_key(version: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(-draft)?", version.strip())
    if not match:
        raise ValueError(f"not a contract version: {version!r}")
    return int(match[1]), int(match[2]), int(match[3])


def integrators(
    changelog: str, from_version: str, to_version: str, *, levels: list[int], mode: str
) -> list[dict[str, Any]]:
    """Items for versions `> from_version` and `<= to_version`, newest first."""
    low, high = version_key(from_version), version_key(to_version)
    wanted = {f"L{level}" for level in levels}
    items: list[dict[str, Any]] = []
    version: str | None = None
    in_list = False
    for line in changelog.splitlines():
        heading = _VERSION.match(line)
        if heading:
            version = line[3:].split()[0]
            in_list = False
            continue
        if line.startswith("## "):
            version, in_list = None, False
            continue
        if line.strip() == "**Integrators:**":
            in_list = True
            continue
        if not in_list or version is None or not line.startswith("- "):
            continue
        if not low < version_key(version) <= high:
            continue
        match = _ITEM.match(line)
        if not match:
            continue  # "Nothing to do." and any untagged line
        tags = re.findall(r"`([^`]+)`", match[1])
        unknown = [t for t in tags if t not in KNOWN_TAGS]
        if unknown:
            print(
                f"tdkit: {version}: ignoring unknown tag(s) {', '.join(unknown)} in: {match[2]}",
                file=sys.stderr,
            )
        tags = [t for t in tags if t in KNOWN_TAGS]
        level_tags = [t for t in tags if t != "read"]
        if "read" in tags:
            applies = mode == "read" and (not level_tags or bool(wanted & set(level_tags)))
        else:
            applies = bool(wanted & set(level_tags))
        if applies:
            items.append({"version": version, "tags": tags, "action": match[2].strip()})
    return items
