"""The contract documentation (`tribunedesk-cms-api`) of one tag, from a local copy or GitHub.

Sources, first found wins: `--docs DIR`, `TRIBUNEDESK_DOCS_DIR`, the cache
`~/.cache/tdkit/cms-api@<tag>`, then a shallow `git clone` of the tag into that cache.
GitHub is the only network host `tdkit` ever talks to, and only here.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tdkit import __version__
from tdkit.errors import UsageError

# Every patch of these minors: a patch changes descriptions only (VERSIONING), so a docs patch
# must not stop the skill. A new minor or major needs a tdkit release that knows it, and that
# release keeps the previous minor until the release after the new tag: until the tag exists,
# `tdkit docs` still finds the old one (spec 2026-11-13 kontrakt najpierw, D2c). The tag guard
# of tribunedesk-cms-api reads this line with a regex: keep it on one line, in this form.
SUPPORTED_MINORS = frozenset({(3, 4)})
_VERSION = re.compile(r"^(\d+)\.(\d+)\.\d+(-draft)?$")


def is_supported(version: str) -> bool:
    """True for any patch of a supported minor, draft or not."""
    match = _VERSION.match(version)
    return bool(match) and (int(match.group(1)), int(match.group(2))) in SUPPORTED_MINORS


REPO_URL = "https://github.com/Tribunedesk/tribunedesk-cms-api"
SAMPLE_DELIVERY = Path("examples/payloads/article-delivered.json")
VECTORS = Path("examples/vectors/webhook-signature.json")

_TAG = re.compile(r"refs/tags/(v(\d+)\.(\d+)\.(\d+)(-draft)?)$")


@dataclass(frozen=True)
class ContractDocs:
    root: Path
    version: str
    openapi: dict[str, Any]
    sample_delivery: dict[str, Any]
    vectors: list[dict[str, Any]]


def latest_tag(lines: list[str]) -> str:
    """The newest `v*` tag in `git ls-remote --tags --refs` output.

    `-draft` sorts as the same version triple; on a tie the tag without `-draft` wins.
    """
    best: tuple[tuple[int, int, int, int], str] | None = None
    for line in lines:
        match = _TAG.search(line.strip())
        if not match:
            continue
        tag, major, minor, patch, draft = match.groups()
        key = (int(major), int(minor), int(patch), 0 if draft else 1)
        if best is None or key > best[0]:
            best = (key, tag)
    if best is None:
        raise UsageError(f"no v* tag found in {REPO_URL}")
    return best[1]


def resolve_docs(tag: str | None, docs_dir: Path | None) -> ContractDocs:
    """Load the documentation of `tag` (or the newest tag) and check tdkit supports it."""
    local = docs_dir or env_docs_dir()
    if local is not None:
        docs = load_docs(local)
        if tag is not None and docs.version != tag.removeprefix("v"):
            raise UsageError(
                f"--contract {tag} does not match the local documentation in {local} "
                f"(contract {docs.version})"
            )
        return docs
    if tag is None:
        tag = latest_tag(_git(["ls-remote", "--tags", "--refs", REPO_URL]).splitlines())
    if not tag.startswith("v"):
        tag = f"v{tag}"
    cache = Path.home() / ".cache" / "tdkit" / f"cms-api@{tag}"
    if not (cache / "openapi.json").is_file():
        if cache.exists():
            shutil.rmtree(cache)
        cache.parent.mkdir(parents=True, exist_ok=True)
        _git(["clone", "--quiet", "--depth", "1", "--branch", tag, REPO_URL, str(cache)])
    return load_docs(cache)


def load_docs(root: Path) -> ContractDocs:
    """Read one checkout of `tribunedesk-cms-api` and check tdkit supports its contract."""
    openapi = _read_json(root / "openapi.json")
    version = str(openapi.get("info", {}).get("version", ""))
    if not is_supported(version):
        raise UsageError(
            f"contract {version} is not supported by tdkit {__version__}; update the plugin"
        )
    # The signature vectors arrived in 3.4.1-draft; only tdkit's own tests read them.
    vectors = _read_json(root / VECTORS) if (root / VECTORS).is_file() else {"vectors": []}
    return ContractDocs(
        root=root,
        version=version,
        openapi=openapi,
        sample_delivery=_read_json(root / SAMPLE_DELIVERY),
        vectors=list(vectors["vectors"]),
    )


def env_docs_dir() -> Path | None:
    value = os.environ.get("TRIBUNEDESK_DOCS_DIR")
    return Path(value) if value else None


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UsageError(f"{path} is missing; is this a tribunedesk-cms-api checkout?") from exc


def _git(args: list[str]) -> str:
    git = shutil.which("git")
    if git is None:
        raise UsageError("git is not installed; pass --docs DIR with a copy of tribunedesk-cms-api")
    done = subprocess.run([git, *args], capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise UsageError(f"git {args[0]} failed: {done.stderr.strip()}")
    return done.stdout
