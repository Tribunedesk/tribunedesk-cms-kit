"""Level 4 of the mock: the media library, written by hand from `guide/4-media-library.md`.

Pure state and rules, no HTTP: `media_routes.py` maps routes onto these functions and the
conformance scenarios call the `td_*` functions to make changes "in Tribune Desk". Every
function takes the `MockState` and holds its lock. Section names in comments are the guide's.
"""

from __future__ import annotations

import copy
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from tdkit.mock.png import png

if TYPE_CHECKING:
    from tdkit.mock.state import Change, MockState

FIELDS = ("title", "alt", "caption", "description")
MIME_TYPES = ("image/jpeg", "image/png", "image/webp")
MIN_WIDTH = 800
WINDOW = timedelta(minutes=60)
FILE_URL_TTL = timedelta(hours=24)
RESYNC_TTL = timedelta(hours=24)
RESYNC_CAP = 50_000
PUSH_PAGE = 1000
LOOPBACK = ("127.0.0.1", "localhost")
LIMITS = {
    "max_batch_items": 100,
    "max_backfill_page_items": 1000,
    "max_field_value_length": 5000,
    "requests_per_minute": 600,
    "file_url_ttl_hours": 24,
}


def _all(value: bool) -> dict[str, bool]:
    return dict.fromkeys(FIELDS, value)


def default_options() -> dict[str, Any]:
    """Spec 1.1 D3: variant `full`, rule `last_change`, trash marks on, threshold 500."""
    return {
        "cms_deletion_trashes_in_td": False,
        "conflict_rule": "last_change",
        "fields_cms_to_td": _all(True),
        "fields_td_to_cms": _all(True),
        "keep_copies_in_td": True,
        "keep_nonempty_cms_to_td": False,
        "keep_nonempty_td_to_cms": False,
        "mass_change_threshold": 500,
        "model_texts_to_cms": "empty_only",
        "new_files_cms_to_td": True,
        "new_files_cms_to_td_min_width": None,
        "new_files_cms_to_td_since": None,
        "new_files_td_to_cms": True,
        "td_deletion_marks_in_cms": True,
        "td_to_cms_editor_files": True,
        "td_to_cms_graphics": True,
    }


def now() -> datetime:
    return datetime.now(UTC)


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds")


def parse(value: str) -> datetime:
    moment = datetime.fromisoformat(value.replace("z", "Z").replace("Z", "+00:00"))
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


class MediaError(Exception):
    """An error answer of a level 4 route: `status`, `code`, `message`."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


@dataclass
class FieldValue:
    value: str
    changed_at: datetime  # the last change, from either side; enabling time when never changed
    version: int = 1
    td_changed: bool = False  # Tribune Desk changed it since the integration was enabled
    td_seq: int = 0  # feed position of the last change in Tribune Desk


@dataclass
class Asset:
    asset_id: str
    filename: str
    data: bytes
    width: int
    height: int
    mime_type: str
    created_at: datetime
    fields: dict[str, FieldValue]
    origin: str = "td"  # "td": a Tribune Desk file; "cms": imported from the CMS
    source: str = "editor"  # a Tribune Desk file: "editor" upload or generated "graphic"
    cms_media_id: str | None = None
    link_url: str | None = None
    reencoded: bool = False
    trashed: bool = False
    missing: bool = False  # deleted in the CMS
    fail_download: int = 0  # the next N downloads of /files/ answer 500

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


@dataclass
class HeldBatch:
    id: str
    direction: str
    epoch: int
    created_at: datetime
    writes: list[tuple[str, str, str]] = field(default_factory=list)  # asset, field, value
    state: str = "pending"
    start_seq: int | None = None  # a resync batch: the feed position its preview started at

    def view(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": "fields",
            "direction": self.direction,
            "state": self.state,
            "count": len(self.writes),
            "created_at": iso(self.created_at),
        }


@dataclass
class Resync:
    id: str
    direction: str
    epoch: int
    start_seq: int
    started: datetime
    expires: datetime
    items: dict[str, dict[str, str]] = field(default_factory=dict)  # asset id -> field -> value
    status: str = "collecting"
    answer: dict[str, Any] | None = None


@dataclass
class Backfill:
    id: str
    filters: dict[str, Any]
    created_at: datetime
    state: str = "open"  # open, paused, closed
    accepted: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class MediaLibrary:
    options: dict[str, Any] = field(default_factory=default_options)
    locked: set[str] = field(default_factory=set)
    variant: str = "full"
    updated_at: datetime | None = None
    enabled_at: datetime = field(default_factory=now)
    assets: dict[str, Asset] = field(default_factory=dict)
    by_cms: dict[str, str] = field(default_factory=dict)  # cms_media_id -> asset_id
    pending_imports: dict[str, dict[str, Any]] = field(default_factory=dict)
    window_start: datetime | None = None
    window_count: int = 0
    window_batch: str | None = None
    held: dict[str, HeldBatch] = field(default_factory=dict)
    resyncs: dict[str, Resync] = field(default_factory=dict)
    backfills: dict[str, Backfill] = field(default_factory=dict)
    files_base: str = "https://127.0.0.1"  # set by the server on each poll (D5)
    media_hosts: list[str] = field(default_factory=list)

    def paired(self, cms_media_id: str) -> Asset | None:
        asset_id = self.by_cms.get(cms_media_id)
        asset = self.assets.get(asset_id) if asset_id else None
        return asset if asset is not None and not asset.trashed else None


# -- helpers -------------------------------------------------------------------------------


def allowed_cms_url(url: str, extra_hosts: list[str] | tuple[str, ...] = ()) -> bool:
    """A `file_url` from the CMS: `http(s)`, no login data, a loopback host or an extra one.

    Production wants `https` on port 443 on the organization's hosts (guide 4, Allowed file
    hosts); locally the CMS runs on `127.0.0.1:<port>`, so the mock relaxes scheme and port.
    """
    try:
        parts = urlsplit(url)
        host = parts.hostname
        _ = parts.port
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or not host or parts.username or parts.password:
        return False
    host = host.removeprefix("www.")
    return host in LOOPBACK or host in {h.removeprefix("www.") for h in extra_hosts}


def _field_change(name: str, fv: FieldValue) -> dict[str, Any]:
    return {
        "field": name,
        "value": fv.value,
        "version": fv.version,
        "changed_at": iso(fv.changed_at),
        "changed_by": "editor",
    }


def _sent_fields(lib: MediaLibrary, asset: Asset, names: list[str] | None = None) -> list[dict]:
    return [
        _field_change(name, asset.fields[name])
        for name in names or list(asset.fields)
        if name in asset.fields and lib.options["fields_td_to_cms"].get(name, False)
    ]


def _emit_fields(state: MockState, asset: Asset, names: list[str] | None = None) -> None:
    lib = state.media
    fields = _sent_fields(lib, asset, names)
    if asset.cms_media_id is None or not fields:
        return
    state.add_change(
        "fields",
        payload={"asset_id": asset.asset_id, "cms_media_id": asset.cms_media_id, "fields": fields},
    )


def _count(lib: MediaLibrary, at: datetime) -> bool:
    """Count one change towards the run; False when it goes over the threshold."""
    if lib.window_start is None or at - lib.window_start >= WINDOW:
        lib.window_start, lib.window_count, lib.window_batch = at, 0, None
    lib.window_count += 1
    return lib.window_count <= int(lib.options["mass_change_threshold"])


def _new_asset(
    state: MockState,
    *,
    origin: str,
    width: int,
    height: int,
    fields: dict[str, str] | None,
    cms_media_id: str | None = None,
    created_at: datetime | None = None,
) -> Asset:
    lib = state.media
    asset_id = str(uuid.uuid4())
    stamp = now()
    asset = Asset(
        asset_id=asset_id,
        filename=f"{asset_id}.png",
        data=png(width, height),
        width=width,
        height=height,
        mime_type="image/png",
        created_at=created_at or stamp,
        fields={k: FieldValue(v, lib.enabled_at) for k, v in (fields or {}).items()},
        origin=origin,
        cms_media_id=cms_media_id,
    )
    lib.assets[asset_id] = asset
    if cms_media_id is not None:
        lib.by_cms[cms_media_id] = asset_id
    return asset


# -- changes in Tribune Desk (scenarios and /_tdkit) ----------------------------------------


def td_new_file(
    state: MockState,
    *,
    fields: dict[str, str] | None = None,
    width: int = 1200,
    height: int = 800,
    source: str = "editor",
) -> Asset:
    """A new file in Tribune Desk (an editor's upload or a generated graphic): `new_asset`."""
    if source not in ("editor", "graphic"):
        raise ValueError(f"source is editor or graphic, not {source!r}")
    with state.lock:
        asset = _new_asset(state, origin="td", width=width, height=height, fields=fields)
        asset.source = source
        state.add_change("new_asset", payload={"asset_id": asset.asset_id})
        return asset


def td_edit(state: MockState, asset_id: str, name: str, value: str) -> int:
    """An editor changes a field in Tribune Desk; returns the field's version."""
    with state.lock:
        lib = state.media
        asset = lib.assets[asset_id]
        fv = asset.fields.setdefault(name, FieldValue("", lib.enabled_at))
        fv.value, fv.changed_at, fv.td_changed = value, now(), True
        # The version grows only for a change that goes into the feed (Conflicts and
        # base_version): a paired file and a field sent to the CMS.
        if asset.cms_media_id is not None and lib.options["fields_td_to_cms"].get(name):
            fv.version += 1
            fv.td_seq = state.seq + 1
            _emit_fields(state, asset, [name])
        return fv.version


def td_repeat(state: MockState, asset_id: str, name: str) -> None:
    """The current value again with the same version, as a `td_to_cms` resync repeats it."""
    with state.lock:
        _emit_fields(state, state.media.assets[asset_id], [name])


def td_trash(state: MockState, asset_id: str, trashed: bool) -> None:
    """An editor trashes or restores a file in Tribune Desk."""
    with state.lock:
        lib = state.media
        asset = lib.assets[asset_id]
        if asset.trashed == trashed:
            return
        asset.trashed = trashed
        if asset.cms_media_id is not None and lib.options["td_deletion_marks_in_cms"]:
            state.add_change(
                "deleted" if trashed else "restored",
                payload={"asset_id": asset_id, "cms_media_id": asset.cms_media_id},
            )


def td_settings(state: MockState, **options: Any) -> None:
    """Tribune Desk changes options (a super admin, or a lock): a `settings` change."""
    with state.lock:
        lib = state.media
        for key, value in options.items():
            if key not in lib.options:
                raise KeyError(key)
            lib.options[key] = copy.deepcopy(value)
        lib.updated_at = now()
        state.add_change("settings")


def td_unknown_kind(state: MockState, kind: str) -> None:
    """A change of a kind a client of this version does not know (skip it, The sync cycle)."""
    with state.lock:
        state.add_change(kind)


def import_pending(state: MockState) -> list[str]:
    """Tribune Desk's import saves every accepted file and pairs it with its `cms_media_id`.

    Initial `fields` are context, not values: the texts stay empty (Sending new files).
    """
    with state.lock:
        lib = state.media
        done = []
        for cms_media_id, item in list(lib.pending_imports.items()):
            created = item.get("created_at")
            _new_asset(
                state,
                origin="cms",
                width=int(item.get("width") or 1200),
                height=int(item.get("height") or 800),
                fields=dict.fromkeys(FIELDS, ""),
                cms_media_id=cms_media_id,
                created_at=parse(created) if created else None,
            )
            del lib.pending_imports[cms_media_id]
            done.append(cms_media_id)
        return done


# -- the feed ------------------------------------------------------------------------------


def change_body(state: MockState, change: Change) -> dict[str, Any] | None:
    """The `Change` of a level 4 change as read now; `None` to leave it out of the answer.

    A file trashed or linked meanwhile, or one the settings no longer allow, is left out; the
    cursor still moves past it (Taking files). Every read renews `file_url`.
    """
    lib = state.media
    body: dict[str, Any] = {
        "cursor": change.cursor,
        "kind": change.kind,
        "changed_at": change.changed_at,
        "article_id": None,
        "asset_id": None,
        "cms_media_id": None,
        "fields": [],
    }
    if change.kind == "settings" or change.kind not in (
        "new_asset",
        "fields",
        "deleted",
        "restored",
    ):
        return body
    asset = lib.assets.get(str(change.payload.get("asset_id")))
    if asset is None:
        return None
    body["asset_id"] = asset.asset_id
    if change.kind == "new_asset":
        kind = "td_to_cms_graphics" if asset.source == "graphic" else "td_to_cms_editor_files"
        allowed = lib.options["new_files_td_to_cms"] and lib.options[kind]
        if asset.trashed or asset.cms_media_id is not None or not allowed:
            return None
        body.update(
            file_url=f"{lib.files_base}/files/{asset.filename}",
            file_url_expires_at=iso(now() + FILE_URL_TTL),
            mime_type=asset.mime_type,
            filename=asset.filename,
            sha256=asset.sha256,
            width=asset.width,
            height=asset.height,
            fields=_sent_fields(lib, asset),
        )
        return body
    body["cms_media_id"] = change.payload.get("cms_media_id")
    if change.kind == "fields":
        body["fields"] = change.payload.get("fields", [])
    return body


# -- /link ---------------------------------------------------------------------------------


def link(
    state: MockState, asset_id: str, cms_media_id: str, file_url: str, reencoded: bool
) -> dict[str, Any]:
    """`POST /media/{asset_id}/link`: `ok` or `known`, or a `MediaError` (Taking files)."""
    with state.lock:
        lib = state.media
        asset = lib.assets.get(asset_id)
        if asset is None or asset.trashed:
            raise MediaError(404, "not_found", "no such file, or it is in the trash")
        if not allowed_cms_url(file_url, lib.media_hosts):
            raise MediaError(422, "validation_error", "file_url: the host is not allowed")
        other = lib.by_cms.get(cms_media_id)
        if other is not None and other != asset_id:
            raise MediaError(409, "state_conflict", "cms_media_id belongs to another file")
        if asset.cms_media_id is not None and asset.cms_media_id != cms_media_id:
            raise MediaError(409, "state_conflict", "the file is linked to another cms_media_id")
        if (
            asset.link_url is not None
            and asset.link_url != file_url
            and not lib.options["keep_copies_in_td"]
        ):
            raise MediaError(409, "state_conflict", "no copy is kept; the URL cannot change")
        same = (
            asset.cms_media_id == cms_media_id
            and asset.link_url == file_url
            and asset.reencoded == reencoded
        )
        first = asset.cms_media_id is None
        asset.cms_media_id, asset.link_url, asset.reencoded = cms_media_id, file_url, reencoded
        lib.by_cms[cms_media_id] = asset_id
        asset.missing = False
        if first:
            # After a link a `fields` change with the current texts follows (Taking files).
            _emit_fields(state, asset)
        return {"id": cms_media_id, "status": "known" if same else "ok"}


# -- writes from the CMS -------------------------------------------------------------------


def cms_new_files(state: MockState, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`POST /media`: `ok`, `known` or `rejected` with a reason (Sending new files)."""
    with state.lock:
        lib = state.media
        opts = lib.options
        results = []
        for item in items:
            cms_media_id = str(item["cms_media_id"])
            asset = lib.paired(cms_media_id)
            result: dict[str, Any] = {
                "id": cms_media_id,
                "asset_id": asset.asset_id if asset else None,
            }
            reason = None
            if not opts["new_files_cms_to_td"]:
                reason = "new_files_disabled"
            elif asset is not None or cms_media_id in lib.pending_imports:
                results.append({**result, "status": "known"})
                continue
            elif not all(item.get(k) for k in ("width", "height", "mime_type")):
                reason = "missing_metadata"
            elif (since := opts["new_files_cms_to_td_since"]) and (
                not item.get("created_at") or parse(item["created_at"]) < parse(since)
            ):
                reason = "before_since"
            elif (floor := opts["new_files_cms_to_td_min_width"]) and int(item["width"]) < floor:
                reason = "below_min_width"
            elif not allowed_cms_url(str(item["file_url"]), lib.media_hosts):
                reason = "host"
            elif int(item["width"]) < MIN_WIDTH:
                reason = "too_small"
            elif item["mime_type"] not in MIME_TYPES:
                reason = "mime"
            if reason is not None:
                results.append({**result, "status": "rejected", "reason": reason})
                continue
            lib.pending_imports[cms_media_id] = dict(item)
            results.append({**result, "status": "ok"})
        return results


def _hold(state: MockState, lib: MediaLibrary, at: datetime, write: tuple[str, str, str]) -> str:
    batch = lib.held.get(lib.window_batch or "")
    if batch is None or batch.state != "pending":
        batch = HeldBatch(str(uuid.uuid4()), "cms_to_td", state.epoch, at)
        lib.held[batch.id] = batch
        lib.window_batch = batch.id
    batch.writes.append(write)
    return batch.id


def cms_field_writes(
    state: MockState, items: list[dict[str, Any]], at: datetime | None = None
) -> tuple[list[dict[str, Any]], str | None]:
    """`POST /media/fields`: the six steps of Conflicts and base_version, then the threshold.

    A NUL character raises `ValueError` (the route answers 422 for the whole request).
    """
    moment = at or now()
    for item in items:
        for write in item["fields"]:
            if "\x00" in str(write["value"]):
                raise ValueError("a NUL character in a value")
    with state.lock:
        lib = state.media
        opts = lib.options
        results: list[dict[str, Any]] = []
        held_id: str | None = None
        for item in items:
            cms_media_id = str(item["cms_media_id"])
            asset = lib.paired(cms_media_id)
            if asset is None:
                results.append({"id": cms_media_id, "status": "unknown"})
                continue
            outcomes = []
            for write in item["fields"]:
                name, value = str(write["field"]), str(write["value"])
                base = write.get("base_version")
                changed_at = min(parse(str(write["changed_at"])), moment)  # future counts as now
                fv = asset.fields.setdefault(name, FieldValue("", lib.enabled_at))
                outcome: dict[str, Any] = {"field": name, "version": fv.version}
                if not opts["fields_cms_to_td"].get(name, False):
                    outcome.update(status="rejected", reason="field_disabled")
                elif value == fv.value:
                    outcome["status"] = "unchanged"
                elif fv.value.strip() and opts["keep_nonempty_cms_to_td"]:
                    outcome.update(status="rejected", reason="keep_nonempty")
                else:
                    if base is not None:
                        applies = base == fv.version or not fv.td_changed
                    else:
                        applies = changed_at >= fv.changed_at
                    if not applies:
                        rule = opts["conflict_rule"]
                        applies = rule == "cms" or (
                            rule == "last_change" and changed_at >= fv.changed_at
                        )
                    if not applies:
                        outcome.update(status="conflict", winning_value=fv.value)
                    elif not _count(lib, moment):
                        held_id = _hold(state, lib, moment, (asset.asset_id, name, value))
                        outcome["status"] = "held"
                    else:
                        fv.value, fv.changed_at = value, changed_at
                        fv.version += 1
                        outcome.update(status="ok", version=fv.version)
                outcomes.append(outcome)
            results.append({"id": cms_media_id, "status": "ok", "fields": outcomes})
        return results, held_id


def cms_deletions(state: MockState, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`POST /media/deletions`: `ok`, `known` or `unknown` (Deletions).

    A repeated id raises `ValueError` (the route answers 422 for the whole request).
    """
    ids = [str(i["cms_media_id"]) for i in items]
    if len(set(ids)) != len(ids):
        raise ValueError("an id is repeated")
    with state.lock:
        lib = state.media
        results = []
        moment = now()
        for cms_media_id in ids:
            asset = lib.paired(cms_media_id)
            if asset is None:
                results.append({"id": cms_media_id, "status": "unknown"})
                continue
            if asset.missing:
                results.append({"id": cms_media_id, "status": "known"})
                continue
            asset.missing = True
            result: dict[str, Any] = {"id": cms_media_id, "status": "ok"}
            if lib.options["cms_deletion_trashes_in_td"]:
                if _count(lib, moment):
                    td_trash(state, asset.asset_id, True)
                else:
                    result["reason"] = "threshold"
            results.append(result)
        return results


# -- held batches --------------------------------------------------------------------------


def _apply_writes(state: MockState, direction: str, writes: list[tuple[str, str, str]]) -> None:
    lib = state.media
    for asset_id, name, value in writes:
        asset = lib.assets.get(asset_id)
        if asset is None:
            continue
        fv = asset.fields.setdefault(name, FieldValue("", lib.enabled_at))
        if direction == "cms_to_td":
            fv.value, fv.changed_at = value, now()
            fv.version += 1
        else:
            _emit_fields(state, asset, [name])


def held_list(state: MockState) -> dict[str, Any]:
    with state.lock:
        return {"items": [b.view() for b in state.media.held.values()]}


def decide_held(state: MockState, held_id: str, decision: str) -> dict[str, Any]:
    """`POST /held/{id}/decision`: `send` applies the batch, `discard` changes nothing."""
    with state.lock:
        batch = state.media.held.get(held_id)
        if batch is None:
            raise MediaError(404, "not_found", "no such held batch")
        if batch.state != "pending":
            raise MediaError(409, "state_conflict", "the batch is no longer pending")
        stale = batch.epoch != state.epoch or (
            batch.direction == "cms_to_td" and now() - batch.created_at > timedelta(days=7)
        )
        if decision == "send" and stale:
            raise MediaError(409, "state_conflict", "the batch is stale: discard it, resync")
        if decision == "send":
            writes = batch.writes
            if batch.start_seq is not None and batch.direction == "cms_to_td":
                # A field changed in Tribune Desk after the preview started is not overwritten.
                writes = [w for w in writes if _td_seq(state.media, w) <= batch.start_seq]
            _apply_writes(state, batch.direction, writes)
            batch.state = "sent"
        else:
            batch.state = "discarded"
        return batch.view()


# -- resync --------------------------------------------------------------------------------


def _differences(lib: MediaLibrary, session: Resync) -> list[tuple[str, str, str]]:
    toggles = lib.options[
        "fields_cms_to_td" if session.direction == "cms_to_td" else "fields_td_to_cms"
    ]
    out = []
    for asset_id, values in session.items.items():
        asset = lib.assets.get(asset_id)
        if asset is None:
            continue
        for name, value in values.items():
            current = asset.fields.get(name)
            if toggles.get(name) and (current.value if current else "") != value:
                out.append((asset_id, name, value))
    return out


def _td_seq(lib: MediaLibrary, diff: tuple[str, str, str]) -> int:
    current = lib.assets[diff[0]].fields.get(diff[1])
    return current.td_seq if current is not None else 0


def resync(state: MockState, body: dict[str, Any]) -> dict[str, Any]:
    """`POST /resync`: a page of a preview, or the confirmation (Cursors and expiry)."""
    with state.lock:
        if body.get("confirm") is True:
            return _resync_confirm(state, str(body["resync_id"]))
        lib = state.media
        moment = now()
        resync_id = body.get("resync_id")
        if resync_id is None:
            session = Resync(
                str(uuid.uuid4()),
                str(body["direction"]),
                state.epoch,
                state.seq,
                moment,
                moment + RESYNC_TTL,
            )
            lib.resyncs[session.id] = session
        else:
            found = lib.resyncs.get(str(resync_id))
            if found is None:
                raise MediaError(404, "not_found", "no such resync")
            session = found
            if session.epoch != state.epoch or moment > session.expires:
                raise MediaError(409, "state_conflict", "the resync is closed or expired")
            if session.status != "collecting":
                raise MediaError(409, "state_conflict", "the preview is ready: start a new one")
            if session.direction != body["direction"]:
                raise MediaError(409, "state_conflict", "a page with another direction")
        added: dict[str, dict[str, str]] = {}
        for item in body["items"]:
            asset = lib.paired(str(item["cms_media_id"]))
            if asset is not None:  # unpaired ids are ignored silently
                added[asset.asset_id] = {str(f["field"]): str(f["value"]) for f in item["fields"]}
        before = dict(session.items)
        session.items.update(added)
        if len(_differences(lib, session)) > RESYNC_CAP:
            session.items = before
            raise MediaError(422, "validation_error", "the preview would exceed 50 000 differences")
        if body["is_last"]:
            session.status = "ready"
        return {
            "resync_id": session.id,
            "status": session.status,
            "differences": len(_differences(lib, session)),
            "expires_at": iso(session.expires),
        }


def _resync_confirm(state: MockState, resync_id: str) -> dict[str, Any]:
    lib = state.media
    session = lib.resyncs.get(resync_id)
    if session is None:
        raise MediaError(404, "not_found", "no such resync")
    if session.epoch != state.epoch:
        raise MediaError(409, "state_conflict", "the resync started before a re-enable")
    if session.answer is not None:  # applied or held: the same answer again
        return session.answer
    if session.status != "ready" or session.epoch != state.epoch or now() > session.expires:
        raise MediaError(409, "state_conflict", "the preview is not ready, expired or stale")
    diffs = _differences(lib, session)
    cursor = state.cursor_for(max(session.start_seq, state.floor))
    if len(diffs) > int(lib.options["mass_change_threshold"]):
        batch = HeldBatch(
            str(uuid.uuid4()),
            session.direction,
            state.epoch,
            now(),
            diffs,
            "pending",
            session.start_seq,
        )
        lib.held[batch.id] = batch
        session.answer = {"status": "held", "cursor": cursor, "held_batch_id": batch.id}
    else:
        if session.direction == "cms_to_td":
            # A field changed in Tribune Desk after the preview started is not overwritten.
            diffs = [d for d in diffs if _td_seq(lib, d) <= session.start_seq]
        _apply_writes(state, session.direction, diffs)
        session.answer = {"status": "applied", "cursor": cursor, "held_batch_id": None}
    session.status = session.answer["status"]
    return session.answer


# -- settings ------------------------------------------------------------------------------


def settings_view(state: MockState) -> dict[str, Any]:
    with state.lock:
        lib = state.media
        return {
            "variant": lib.variant,
            "options": copy.deepcopy(lib.options),
            "locked_options": sorted(lib.locked),
            "limits": dict(LIMITS),
            "image_hosts": list(state.image_hosts),
            "updated_at": iso(lib.updated_at) if lib.updated_at else None,
        }


def _flat(options: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in options.items():
        if isinstance(value, dict):
            flat.update({f"{key}.{k}": v for k, v in value.items()})
        else:
            flat[key] = value
    return flat


def settings_put(state: MockState, body: dict[str, Any]) -> dict[str, Any]:
    """`PUT /settings` (Settings): a variant sets four things; `custom` gives every option."""
    with state.lock:
        lib = state.media
        variant = str(body["variant"])
        options = body.get("options")
        if (variant == "custom") != (options is not None):
            raise MediaError(422, "validation_error", "options: required exactly for custom")
        new = copy.deepcopy(lib.options)
        if variant == "custom":
            assert isinstance(options, dict)
            new.update(copy.deepcopy(options))
        else:
            one = variant in ("full", "cms_to_td_only")
            two = variant in ("full", "td_to_cms_only")
            new.update(
                new_files_cms_to_td=one,
                fields_cms_to_td=_all(one),
                new_files_td_to_cms=two,
                fields_td_to_cms=_all(two),
            )
        old_flat, new_flat = _flat(lib.options), _flat(new)
        locked = [k for k in lib.locked if old_flat.get(k) != new_flat.get(k)]
        if locked:
            raise MediaError(409, "option_locked", f"locked: {', '.join(sorted(locked))}")
        lib.options, lib.variant, lib.updated_at = new, variant, now()
        state.add_change("settings")
    return settings_view(state)


# -- push-existing -------------------------------------------------------------------------


def push_existing(state: MockState, since: str | None, after: str | None) -> dict[str, Any]:
    """`POST /media/push-existing` (Older files): queue up to 1000 files as `new_asset`."""
    with state.lock:
        if not state.switched:
            raise MediaError(409, "state_conflict", "poll GET /changes once first")
        lib = state.media
        waiting = {
            str(c.payload.get("asset_id"))
            for c in state.changes
            if c.kind == "new_asset" and c.seq > state.acked
        }
        floor = parse(since) if since else None
        candidates = sorted(
            (
                a
                for a in lib.assets.values()
                if a.origin == "td"
                and a.cms_media_id is None
                and not a.trashed
                and a.asset_id not in waiting
                and (floor is None or a.created_at >= floor)
            ),
            key=lambda a: (a.created_at, a.asset_id),
        )
        if after is not None:
            if after not in lib.assets:
                raise MediaError(422, "validation_error", "after: not a value of next_after")
            mark = (lib.assets[after].created_at, after)
            candidates = [a for a in candidates if (a.created_at, a.asset_id) > mark]
        page, more = candidates[:PUSH_PAGE], len(candidates) > PUSH_PAGE
        for asset in page:
            state.add_change("new_asset", payload={"asset_id": asset.asset_id})
        return {
            "queued": len(page),
            "next_after": page[-1].asset_id if more else None,
            "held_batch_id": None,
        }


# -- historical import ---------------------------------------------------------------------


def td_backfill_request(state: MockState, filters: dict[str, Any] | None = None) -> str:
    """An operator at Tribune Desk starts an export request (Historical import)."""
    with state.lock:
        request = Backfill(str(uuid.uuid4()), dict(filters or {}), now())
        state.media.backfills[request.id] = request
        return request.id


def td_backfill_pause(state: MockState, request_id: str, paused: bool) -> None:
    with state.lock:
        request = state.media.backfills[request_id]
        if request.state != "closed":
            request.state = "paused" if paused else "open"


def backfill_list(state: MockState) -> dict[str, Any]:
    with state.lock:
        return {
            "items": [
                {
                    "id": r.id,
                    "status": "collecting",
                    "filters": r.filters,
                    "created_at": iso(r.created_at),
                }
                for r in state.media.backfills.values()
                if r.state == "open"
            ]
        }


def backfill_page(state: MockState, request_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """`POST /backfill/requests/{id}/pages`: a result per candidate (Historical import)."""
    with state.lock:
        lib = state.media
        request = lib.backfills.get(request_id)
        if request is None:
            raise MediaError(404, "not_found", "no such request")
        items = body["items"]
        if request.state == "paused" and not items and not body.get("is_last"):
            return {"accepted": 0, "results": []}
        if request.state != "open":
            raise MediaError(409, "state_conflict", "the request is closed or paused")
        floor = int(request.filters.get("min_width") or MIN_WIDTH)
        cap = request.filters.get("max_files")
        results, accepted = [], 0
        for item in items:
            cms_media_id = str(item["cms_media_id"])
            result: dict[str, Any] = {"id": cms_media_id}
            if cms_media_id in request.accepted:
                result["status"] = "ok"
                accepted += 1
            elif lib.paired(cms_media_id) is not None or cms_media_id in lib.pending_imports:
                result["status"] = "known"
            elif not allowed_cms_url(str(item.get("file_url", "")), lib.media_hosts):
                result.update(status="rejected", reason="host")
            elif not all(item.get(k) for k in ("width", "height", "mime_type")):
                result.update(status="rejected", reason="missing_metadata")
            elif item["mime_type"] not in MIME_TYPES:
                result.update(status="rejected", reason="mime")
            elif int(item["width"]) < floor:
                result.update(status="rejected", reason="too_small")
            elif cap is not None and len(request.accepted) >= int(cap):
                result.update(status="rejected", reason="max_files")
            else:
                request.accepted[cms_media_id] = dict(item)
                lib.pending_imports[cms_media_id] = dict(item)
                result["status"] = "ok"
                accepted += 1
            results.append(result)
        if body.get("is_last") or (cap is not None and len(request.accepted) >= int(cap)):
            request.state = "closed"
        return {"accepted": accepted, "results": results}
