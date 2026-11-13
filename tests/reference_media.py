"""A small level 4 integration that does the media library right: the yardstick of
`tdkit check --levels 4`.

Standard library only. The "CMS library" is a JSON file shared by the commands:

    python reference_media.py [FLAGS] --store store.json sync
    python reference_media.py [FLAGS] --store store.json inspect <cms_media_id>
    python reference_media.py [FLAGS] --store store.json add <file>
    python reference_media.py [FLAGS] --store store.json edit <cms_media_id> <field> <value>
    python reference_media.py [FLAGS] --store store.json delete <cms_media_id>
    python reference_media.py [FLAGS] --store store.json reset

`TD_API_BASE` and `TD_CMS_TOKEN` point at the API (the mock). Each flag breaks one rule of
guide 4, so the tests can see `tdkit check` catch it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
import time
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BREAKS = (
    "cursor-before-apply",
    "one-page",
    "no-cursor",
    "ignore-versions",
    "resend-conflict",
    "apply-over-dirty",
    "fresh-after-410",
    "auto-confirm-resync",
    "auto-decide-held",
    "resend-held",
    "no-base-version",
    "duplicate-new-files",
    "skip-deletions",
    "crash-on-unknown-kind",
    "cache-settings",
    "keep-trash-mark",
    "keep-first-cursor",
    "drop-unknown-edits",
    "no-backfill-last",
)
KINDS = ("new_asset", "fields", "deleted", "restored", "settings")
ATTEMPTS = 5  # a change that cannot be applied is retried this many syncs, then skipped

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class Stop(Exception):
    """A change could not be applied: keep the cursor before it."""


class Gone(Exception):
    """The cursor expired (410)."""


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def api(method: str, path: str, body: Any = None) -> tuple[int, Any]:
    base = os.environ["TD_API_BASE"].rstrip("/")
    data = None if body is None else json.dumps(body).encode()
    headers = {"Authorization": f"Bearer {os.environ['TD_CMS_TOKEN']}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base + "/v3/cms" + path, data, headers, method=method)
    try:
        with _OPENER.open(request, timeout=30) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, json.loads(raw) if raw else None


# -- the store -----------------------------------------------------------------------------


def empty() -> dict[str, Any]:
    return {
        "cursor": None,
        "polled": False,
        "attempts": {},
        "needs_resync": False,
        "resync_id": None,
        "media": {},
        "deletions": [],
        "next_id": 1,
        "settings": None,
    }


def load(store: Path) -> dict[str, Any]:
    if not store.is_file():
        return empty()
    return json.loads(store.read_text(encoding="utf-8"))


def save(store: Path, data: dict[str, Any]) -> None:
    tmp = store.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(store)


@contextmanager
def locked(store: Path) -> Any:
    """One sync at a time (generic.md: never two cycles at once)."""
    lock = store.with_suffix(".lock")
    for _ in range(600):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            time.sleep(0.05)
    else:
        raise SystemExit("another sync holds the lock")
    try:
        yield
    finally:
        os.close(fd)
        lock.unlink(missing_ok=True)


def record(data: dict[str, Any], **values: Any) -> dict[str, Any]:
    item = {
        "asset_id": None,
        "sha256": None,
        "width": None,
        "height": None,
        "mime_type": "image/png",
        "fields": {},
        "versions": {},
        "dirty": {},
        "kept": {},
        "deleted_in_td": False,
        "pushed": None,
        "created_at": now(),
    }
    item.update(values)
    return item


def png_size(data: bytes) -> tuple[int, int]:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit("not a PNG")
    width, height = struct.unpack(">II", data[16:24])
    return int(width), int(height)


# -- sync ----------------------------------------------------------------------------------


def settings(data: dict[str, Any]) -> dict[str, Any]:
    if data["settings"] is None:
        status, body = api("GET", "/settings")
        data["settings"] = body["options"] if status == 200 else {}
    return data["settings"]


def apply_change(data: dict[str, Any], change: dict[str, Any], flags: set[str]) -> None:
    kind = change["kind"]
    media: dict[str, Any] = data["media"]
    if kind == "new_asset":
        try:
            with _OPENER.open(change["file_url"], timeout=30) as response:
                body = response.read()
        except (urllib.error.URLError, OSError) as exc:
            raise Stop(f"download failed: {exc}") from None
        if change.get("sha256") and hashlib.sha256(body).hexdigest() != change["sha256"]:
            raise Stop("checksum differs")
        cms_media_id = f"r{data['next_id']}"
        data["next_id"] += 1
        width, height = png_size(body)
        item = record(
            data,
            asset_id=change["asset_id"],
            sha256=hashlib.sha256(body).hexdigest(),
            width=width,
            height=height,
            pushed="td",
        )
        for f in change.get("fields", []):
            item["fields"][f["field"]] = f["value"]
            item["versions"][f["field"]] = f["version"]
        url = f"http://127.0.0.1:1/media/{cms_media_id}"
        status, _ = api(
            "POST",
            f"/media/{change['asset_id']}/link",
            {"cms_media_id": cms_media_id, "file_url": url},
        )
        if status != 200:
            raise Stop(f"link answered {status}")
        media[cms_media_id] = item
    elif kind == "fields":
        item = media.get(change.get("cms_media_id") or "")
        if item is None:
            return  # a file this CMS does not hold
        keep = bool(settings(data).get("keep_nonempty_td_to_cms"))
        for f in change["fields"]:
            name, version = f["field"], int(f["version"])
            if name in item["dirty"] and "apply-over-dirty" not in flags:
                item["kept"][name] = {"value": f["value"], "version": version}
                continue
            if "ignore-versions" not in flags and version < item["versions"].get(name, 0):
                continue
            if not (keep and item["fields"].get(name, "").strip()):
                item["fields"][name] = f["value"]
            item["versions"][name] = version
            item["dirty"].pop(name, None)
    elif kind in ("deleted", "restored"):
        cms_media_id = change.get("cms_media_id") or ""
        if cms_media_id in media:
            if kind == "restored" and "keep-trash-mark" in flags:
                return
            media[cms_media_id]["deleted_in_td"] = kind == "deleted"
    elif kind == "settings":
        if "cache-settings" not in flags:
            data["settings"] = None
            settings(data)
    elif "crash-on-unknown-kind" in flags:
        raise SystemExit(f"unknown kind {kind}")


def pull(data: dict[str, Any], flags: set[str]) -> None:
    page_cursor = None  # within one sync, follow has_more in memory
    while True:
        cursor = None if "no-cursor" in flags else data["cursor"]
        if "keep-first-cursor" in flags:
            cursor = page_cursor or data.get("first_cursor") or data["cursor"]
        query = "?limit=100" + (f"&cursor={cursor}" if cursor else "")
        status, body = api("GET", "/changes" + query)
        if status == 410:
            raise Gone()
        if status != 200:
            raise SystemExit(f"GET /changes answered {status}: {body}")
        data["polled"] = True
        if "cursor-before-apply" in flags:
            data["cursor"] = body["next_cursor"]
        for change in body["changes"]:
            try:
                apply_change(data, change, flags)
            except Stop:
                key = change["cursor"]
                data["attempts"][key] = data["attempts"].get(key, 0) + 1
                if data["attempts"][key] < ATTEMPTS and "cursor-before-apply" not in flags:
                    return  # keep the cursor before this change
            if "cursor-before-apply" not in flags:
                data["cursor"] = change["cursor"]
        if "cursor-before-apply" not in flags:
            data["cursor"] = body["next_cursor"]
        if "keep-first-cursor" in flags:
            data.setdefault("first_cursor", body["next_cursor"])
            page_cursor = body["next_cursor"]
        if not body.get("has_more") or "one-page" in flags:
            return


def push_new_files(data: dict[str, Any], flags: set[str]) -> None:
    items, ids = [], {}
    for cms_media_id, item in data["media"].items():
        if item["pushed"] in (None, "ok") and item["asset_id"] is None:
            sent = cms_media_id
            if "duplicate-new-files" in flags:
                sent = f"{cms_media_id}-{uuid.uuid4().hex[:6]}"
            ids[sent] = cms_media_id
            items.append(
                {
                    "cms_media_id": sent,
                    "file_url": f"http://127.0.0.1:1/media/{cms_media_id}",
                    "width": item["width"],
                    "height": item["height"],
                    "mime_type": item["mime_type"],
                    "created_at": item["created_at"],
                }
            )
    if not items:
        return
    status, body = api("POST", "/media", {"items": items})
    if status != 200:
        return
    for result in body["results"]:
        item = data["media"][ids[result["id"]]]
        if result["status"] in ("ok", "known"):
            item["pushed"] = "ok"
            item["asset_id"] = result.get("asset_id")


def push_fields(data: dict[str, Any], flags: set[str]) -> None:
    items = []
    for cms_media_id, item in data["media"].items():
        if not item["dirty"] or (item["asset_id"] is None and item["pushed"] != "ok"):
            continue
        writes = []
        for name, changed_at in item["dirty"].items():
            write: dict[str, Any] = {
                "field": name,
                "value": item["fields"].get(name, ""),
                "changed_at": changed_at,
            }
            if "no-base-version" not in flags:
                write["base_version"] = item["versions"].get(name, 1)
            writes.append(write)
        items.append({"cms_media_id": cms_media_id, "fields": writes})
    if not items:
        return
    status, body = api("POST", "/media/fields", {"items": items})
    if status != 200:
        return
    for result in body["results"]:
        item = data["media"][result["id"]]
        if result["status"] == "unknown":
            # Not paired yet (the import is pending): keep the edit and send it again later.
            if "drop-unknown-edits" in flags:
                item["dirty"].clear()
            continue
        for f in result.get("fields", []):
            name, outcome = f["field"], f["status"]
            if outcome in ("ok", "unchanged"):
                item["versions"][name] = f["version"]
                item["kept"].pop(name, None)
            elif outcome == "conflict":
                item["fields"][name] = f["winning_value"]
                item["versions"][name] = f["version"]
                item["kept"].pop(name, None)
                if "resend-conflict" in flags:
                    continue
            elif outcome == "rejected":
                kept = item["kept"].pop(name, None)
                if kept is not None:
                    item["fields"][name] = kept["value"]
                    item["versions"][name] = kept["version"]
            elif outcome == "held" and "resend-held" in flags:
                continue
            item["dirty"].pop(name, None)
    held = body.get("held_batch_id")
    if held and "auto-decide-held" in flags:
        api("POST", f"/held/{held}/decision", {"decision": "send"})


def push_deletions(data: dict[str, Any], flags: set[str]) -> None:
    if not data["deletions"] or "skip-deletions" in flags:
        return
    status, _ = api("POST", "/media/deletions", {"items": data["deletions"][:100]})
    if status == 200:
        data["deletions"] = data["deletions"][100:]


def answer_backfill(data: dict[str, Any], flags: set[str]) -> None:
    status, body = api("GET", "/backfill/requests")
    if status != 200:
        return
    for request in body["items"]:
        filters = request.get("filters") or {}
        floor = int(filters.get("min_width") or 800)
        since = filters.get("date_from")
        candidates = [
            {
                "cms_media_id": cms_media_id,
                "file_url": f"http://127.0.0.1:1/media/{cms_media_id}",
                "width": item["width"],
                "height": item["height"],
                "mime_type": item["mime_type"],
                "created_at": item["created_at"],
            }
            for cms_media_id, item in data["media"].items()
            if item["width"]
            and item["width"] >= floor
            and (not since or item["created_at"] >= since)
        ]
        page = {"items": candidates, "is_last": "no-backfill-last" not in flags}
        api("POST", f"/backfill/requests/{request['id']}/pages", page)


def start_resync(data: dict[str, Any], flags: set[str]) -> None:
    """After 410: send unsent edits, then preview `td_to_cms` for a person to confirm."""
    data["needs_resync"] = True
    push_fields(data, flags)
    items = [
        {
            "cms_media_id": cms_media_id,
            "fields": [{"field": k, "value": v} for k, v in item["fields"].items()],
        }
        for cms_media_id, item in data["media"].items()
        if item["asset_id"]
    ]
    resync_id = None
    pages = [items[i : i + 100] for i in range(0, len(items), 100)] or [[]]
    for index, page in enumerate(pages):
        body: dict[str, Any] = {
            "direction": "td_to_cms",
            "items": page,
            "is_last": index == len(pages) - 1,
        }
        if resync_id:
            body["resync_id"] = resync_id
        status, answer = api("POST", "/resync", body)
        if status != 200:
            return
        resync_id = answer["resync_id"]
    data["resync_id"] = resync_id
    if "auto-confirm-resync" in flags:
        status, answer = api("POST", "/resync", {"resync_id": resync_id, "confirm": True})
        if status == 200:
            data["cursor"], data["needs_resync"] = answer["cursor"], False


def sync(data: dict[str, Any], flags: set[str], backfill: bool) -> None:
    if not data["needs_resync"]:
        try:
            pull(data, flags)
        except Gone:
            if "fresh-after-410" in flags:
                data["cursor"] = None
                pull(data, flags)
            else:
                start_resync(data, flags)
                return
    push_new_files(data, flags)
    push_fields(data, flags)
    push_deletions(data, flags)
    if backfill:
        answer_backfill(data, flags)


# -- commands ------------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()
    for flag in BREAKS:
        parser.add_argument(f"--{flag}", action="store_true")
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--store", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sync")
    sub.add_parser("reset")
    sub.add_parser("inspect").add_argument("cms_media_id")
    sub.add_parser("add").add_argument("file", type=Path)
    edit = sub.add_parser("edit")
    edit.add_argument("cms_media_id")
    edit.add_argument("field")
    edit.add_argument("value")
    sub.add_parser("delete").add_argument("cms_media_id")
    args = parser.parse_args()
    flags = {f for f in BREAKS if getattr(args, f.replace("-", "_"))}
    store: Path = args.store
    if args.command == "reset":
        store.unlink(missing_ok=True)
        return
    with locked(store):
        data = load(store)
        if args.command == "sync":
            sync(data, flags, args.backfill)
        elif args.command == "inspect":
            item = data["media"].get(args.cms_media_id)
            out = None
            if item is not None:
                out = {
                    "cms_media_id": args.cms_media_id,
                    "asset_id": item["asset_id"],
                    "sha256": item["sha256"],
                    "fields": item["fields"],
                    "deleted_in_td": item["deleted_in_td"],
                }
            print(json.dumps(out, ensure_ascii=False))
        elif args.command == "add":
            body = args.file.read_bytes()
            width, height = png_size(body)
            cms_media_id = f"r{data['next_id']}"
            data["next_id"] += 1
            data["media"][cms_media_id] = record(
                data, sha256=hashlib.sha256(body).hexdigest(), width=width, height=height
            )
            print(json.dumps({"cms_media_id": cms_media_id}))
        elif args.command == "edit":
            item = data["media"][args.cms_media_id]
            item["fields"][args.field] = args.value
            item["dirty"][args.field] = now()
        elif args.command == "delete" and data["media"].pop(args.cms_media_id, None):
            data["deletions"].append({"cms_media_id": args.cms_media_id, "deleted_at": now()})
        save(store, data)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    main()
