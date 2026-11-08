"""The integration project: its copy of the contract docs and its manifest `tribunedesk.json`.

`tdkit docs` puts the documentation of a tag into `.tribunedesk/cms-api@<tag>/` of the
project (ignored by git), so the skill reads the contract from there and cites it.
`tdkit manifest` validates and writes `tribunedesk.json` (spec D5).
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tarfile
import urllib.request
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from tdkit.docs import REPO_URL, latest_tag, load_docs
from tdkit.errors import UsageError

Transport = Callable[[str], bytes]

TARBALL_URL = "https://codeload.github.com/Tribunedesk/tribunedesk-cms-api/tar.gz/refs/tags/{tag}"
TAGS_URL = "https://api.github.com/repos/Tribunedesk/tribunedesk-cms-api/tags?per_page=100"
IGNORE_ENTRY = ".tribunedesk/"
MANIFEST = "tribunedesk.json"
DELIVERIES = ("webhook", "read", "none")


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


# -- docs ----------------------------------------------------------------------------------


def fetch_docs(
    project_dir: Path,
    *,
    tag: str | None,
    dest: Path | None,
    source: Path | None = None,
    transport: Transport | None = None,
) -> dict[str, str]:
    """Make sure the docs of `tag` (default: the newest) are in the project; return
    `{"tag", "version", "path"}`."""
    transport = transport or _download
    env_dir = os.environ.get("TRIBUNEDESK_DOCS_DIR")
    local = source or (Path(env_dir) if env_dir else None)
    if local is not None:
        version = load_docs(local).version
        if tag is not None and tag.removeprefix("v") != version:
            raise UsageError(f"--contract {tag} does not match {local} (contract {version})")
        tag = f"v{version}"
    elif tag is None:
        tag = _latest(transport)
    if not tag.startswith("v"):
        tag = f"v{tag}"
    target = dest or project_dir / ".tribunedesk" / f"cms-api@{tag}"
    if not (target / "openapi.json").is_file():
        if target.exists() and any(target.iterdir()):
            # Only a half-written copy of our own may be removed; never a folder of the user.
            ours = project_dir / ".tribunedesk"
            if dest is not None or not target.resolve().is_relative_to(ours.resolve()):
                raise UsageError(
                    f"{target} exists and is not empty; choose an empty --dest or remove it"
                )
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if local is not None:
            shutil.copytree(local, target, ignore=shutil.ignore_patterns(".git"))
        elif shutil.which("git"):
            _git_clone(tag, target)
        else:
            _extract(transport(TARBALL_URL.format(tag=tag)), target)
    docs = load_docs(target)
    if docs.version != tag.removeprefix("v"):
        raise UsageError(f"{target} holds contract {docs.version}, not {tag}")
    if dest is None:
        _ignore(project_dir, IGNORE_ENTRY)
    elif target.resolve().is_relative_to(project_dir.resolve()):
        relative = target.resolve().relative_to(project_dir.resolve()).as_posix()
        _ignore(project_dir, f"/{relative}/")
    return {"tag": tag, "version": docs.version, "path": str(target)}


def _latest(transport: Transport) -> str:
    git = shutil.which("git")
    if git:
        done = subprocess.run(
            [git, "ls-remote", "--tags", "--refs", REPO_URL],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if done.returncode != 0:
            raise UsageError(f"git ls-remote failed: {done.stderr.strip()}")
        return latest_tag(done.stdout.splitlines())
    names = [item["name"] for item in json.loads(transport(TAGS_URL))]
    return latest_tag([f"refs/tags/{name}" for name in names])


def _git_clone(tag: str, target: Path) -> None:
    git = shutil.which("git")
    assert git is not None
    done = subprocess.run(
        [git, "clone", "--quiet", "--depth", "1", "--branch", tag, REPO_URL, str(target)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if done.returncode != 0:
        raise UsageError(f"git clone of {tag} failed: {done.stderr.strip()}")


def _extract(data: bytes, target: Path) -> None:
    """Unpack a GitHub tarball (one top folder) into `target`."""
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        members = []
        for member in archive.getmembers():
            parts = Path(member.name).parts
            if len(parts) < 2:
                continue
            member.name = str(Path(*parts[1:]))
            members.append(member)
        target.mkdir(parents=True, exist_ok=True)
        archive.extractall(target, members=members, filter="data")


def _in_git_repo(project_dir: Path) -> bool:
    return any((folder / ".git").exists() for folder in (project_dir, *project_dir.parents))


def _ignore(project_dir: Path, entry: str) -> None:
    gitignore = project_dir / ".gitignore"
    if not gitignore.exists() and not _in_git_repo(project_dir):
        return
    text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    entries = {line.strip().strip("/") for line in text.splitlines()}
    if entry.strip("/") in entries:
        return
    if text and not text.endswith("\n"):
        text += "\n"
    gitignore.write_text(text + entry + "\n", encoding="utf-8")


# -- manifest ------------------------------------------------------------------------------


def validate_manifest(data: Any) -> list[str]:
    """Errors of a `tribunedesk.json` against spec D5; empty when it is valid."""
    if not isinstance(data, dict):
        return ["the manifest is not a JSON object"]
    errors: list[str] = []
    for key in ("contract", "cms", "kit"):
        if not isinstance(data.get(key), str) or not data[key]:
            errors.append(f"{key}: a non-empty string is required")
    levels = data.get("levels")
    if (
        not isinstance(levels, list)
        or not levels
        or not all(isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 4 for v in levels)
    ):
        errors.append("levels: a non-empty list of levels 1 to 4 is required")
    if data.get("delivery") not in DELIVERIES:
        errors.append(f"delivery: one of {', '.join(DELIVERIES)} is required")
    if "protocol" in data and not isinstance(data["protocol"], str):
        errors.append("protocol: a string (the cms-protocol library version)")
    if "conformance" in data:
        conformance = data["conformance"]
        if not isinstance(conformance, dict):
            errors.append("conformance: an object {date, kit, contract, passed}")
        else:
            for key in ("date", "kit", "contract"):
                if not isinstance(conformance.get(key), str):
                    errors.append(f"conformance.{key}: a string is required")
            passed = conformance.get("passed")
            if not isinstance(passed, list) or not all(
                isinstance(v, int) and 1 <= v <= 4 for v in passed
            ):
                errors.append("conformance.passed: a list of levels 1 to 4 is required")
    known = {"contract", "levels", "delivery", "cms", "kit", "protocol", "conformance"}
    errors += [f"{key}: unknown field" for key in sorted(set(data) - known)]
    return errors


def passed_levels(report: dict[str, Any]) -> list[int]:
    """Levels of a `tdkit check --json` report where at least one scenario passed and none
    failed."""
    result: list[int] = []
    for level in report.get("levels", []):
        outcomes = [r.get("passed") for r in report.get("results", []) if r.get("level") == level]
        if True in outcomes and False not in outcomes:
            result.append(level)
    return result


def build_manifest(
    *,
    contract: str,
    levels: list[int],
    delivery: str,
    cms: str,
    kit: str,
    protocol: str | None = None,
    report: dict[str, Any] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "contract": contract,
        "levels": sorted(levels),
        "delivery": delivery,
        "cms": cms,
        "kit": kit,
    }
    if protocol:
        manifest["protocol"] = protocol
    if report is not None:
        reported = str(report.get("contract", "")).removeprefix("v")
        if reported != contract.removeprefix("v"):
            raise UsageError(
                f"the report is for contract {reported}, the manifest says {contract}; "
                "run tdkit check against the same contract"
            )
        if report.get("mode") != delivery:
            raise UsageError(
                f"the report ran in {report.get('mode')} mode, the manifest says {delivery}"
            )
        manifest["conformance"] = {
            "date": (today or date.today()).isoformat(),
            "kit": str(report.get("tdkit", kit)),
            "contract": str(report.get("contract", contract)),
            "passed": passed_levels(report),
        }
    errors = validate_manifest(manifest)
    if errors:
        raise UsageError("; ".join(errors))
    return manifest


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise UsageError(f"{path} does not exist") from None
    except ValueError as exc:
        raise UsageError(f"{path} is not valid JSON: {exc}") from None
