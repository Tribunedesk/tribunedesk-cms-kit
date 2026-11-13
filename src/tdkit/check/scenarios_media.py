"""The level 4 scenarios (media library), each tied to a point of guide 4 (spec 1.1 D4).

`done_when` quotes `guide/4-media-library.md` literally: a point of its "Done when" section, or
the guide's sentence that requires the behaviour (then `guide` names that section). Changes
"in Tribune Desk" are made in the mock's state (`tdkit.mock.media`); changes in the CMS go
through the integration's commands. The order matters: `l4-cursor-expired-resync` runs last,
because afterwards the integration waits for a person to confirm a resync.
"""

from __future__ import annotations

from typing import Any

from tdkit.check.context import Context, Fail
from tdkit.check.scenarios import Scenario, expect
from tdkit.mock import media
from tdkit.mock.state import Recorded

G4 = "guide/4-media-library.md"
DW4 = f"{G4}#done-when"
CYCLE = f"{G4}#the-sync-cycle"
CHANGES = r"/v3/cms/changes"
LINK = r"/v3/cms/media/[^/]+/link"

DW_POLL = (
    "Your CMS polls `GET /v3/cms/changes` and stores the cursor only after applying the "
    "changes it returned."
)
DW_PUSH = (
    "New files, field changes and deletions on your side reach Tribune Desk, and a repeated "
    "request creates no duplicates."
)
DW_CONFLICT = (
    "A field result `conflict` (in a `200` answer) is resolved by adopting `winning_value`, "
    "not by sending yours again."
)
DW_410 = "An expired cursor (`410`) leads to a resync, not to a fresh start from now."
DW_HELD = "Held batches are shown to a person who decides them."
S_LINK = (
    "Call `POST /v3/cms/media/{asset_id}/link` with `cms_media_id` (any id of yours) and "
    "`file_url` (see Allowed file hosts)."
)
S_VERSION = (
    "Apply by version: skip a change only when its `version` is lower than yours, because a "
    "repeated current value (after a link and after a `td_to_cms` resync) has the same version "
    "as before and a new value."
)
S_BOTH = (
    "If a change from the feed touches a field you edited and have not sent yet, do not apply "
    "it and do not take its version."
)
S_SETTINGS = (
    'A `kind="settings"` change has no `asset_id` and no values: when you see one, read '
    "`GET /v3/cms/settings` again."
)
S_TRASH = (
    "Do what suits your CMS, such as a hidden mark; do not delete a file used in published content."
)
S_BACKFILL = (
    "If you have no candidates, send one page with an empty `items` and `is_last` true: "
    "silence leaves the request open, and an organization can have only one open."
)


# -- helpers -------------------------------------------------------------------------------


def _polls(ctx: Context, mark: int) -> list[Recorded]:
    polls = ctx.requests_since(mark, "GET", CHANGES)
    foreign = [p for p in polls if p.status == 422 and "--reset-cmd" in str(p.answer)]
    if foreign:
        raise Fail(
            "the integration polled with a cursor from an earlier tdkit run: clear its level 4 "
            "state before check, or pass --reset-cmd"
        )
    return polls


def _cursor(poll: Recorded) -> str | None:
    values = poll.query.get("cursor")
    return values[0] if values else None


def _link_of(ctx: Context, mark: int, asset_id: str) -> str:
    """The `cms_media_id` the integration linked `asset_id` with, after `mark`."""
    for request in ctx.requests_since(mark, "POST", LINK):
        if request.path == f"/v3/cms/media/{asset_id}/link" and request.status == 200:
            return str(request.body["cms_media_id"])
    raise Fail(f"the integration did not link the new file {asset_id} (POST /media/{{id}}/link)")


def _paired(ctx: Context, value: str = "from Tribune Desk") -> tuple[media.Asset, str]:
    """A file made in Tribune Desk and taken by the integration: `(asset, cms_media_id)`."""
    mark = ctx.mark()
    asset = media.td_new_file(ctx.state, fields={ctx.field: value})
    ctx.sync()
    return asset, _link_of(ctx, mark, asset.asset_id)


def _value(ctx: Context, cms_media_id: str) -> Any:
    fields = ctx.must_media(cms_media_id).get("fields")
    if not isinstance(fields, dict):
        raise Fail(f"--media-inspect-cmd printed fields {fields!r}, not an object")
    return fields.get(ctx.field)


def _writes(ctx: Context, mark: int, cms_media_id: str) -> list[dict[str, Any]]:
    """The field writes of `cms_media_id` for the scenario's field, after `mark`."""
    out = []
    for request in ctx.requests_since(mark, "POST", r"/v3/cms/media/fields"):
        for item in (request.body or {}).get("items", []):
            if item.get("cms_media_id") == cms_media_id:
                out += [w for w in item.get("fields", []) if w.get("field") == ctx.field]
    return out


def _settle_window(ctx: Context) -> None:
    """Start a new 60-minute run, so writes of earlier scenarios do not count."""
    with ctx.state.lock:
        ctx.state.media.window_start = None


# -- scenarios -----------------------------------------------------------------------------


def first_poll(ctx: Context) -> str:
    mark = ctx.mark()
    try:
        ctx.sync()
        media.td_new_file(ctx.state)
        ctx.sync()
    except Fail:
        _polls(ctx, mark)  # a cursor from an earlier run explains the failure better
        raise
    polls = _polls(ctx, mark)
    expect(
        len(polls) >= 2,
        f"two syncs made {len(polls)} GET /changes; if a resync from an earlier check waits for "
        "confirmation, clear the integration's state first (--reset-cmd)",
    )
    without = [p for p in polls[1:] if _cursor(p) is None]
    expect(
        not without,
        "a later poll had no cursor: a poll without one starts from now and skips changes; "
        "keep your cursor and send it every time",
    )
    return f"{len(polls)} polls, each after the first with the stored cursor"


def new_asset_linked(ctx: Context) -> str:
    _settle_window(ctx)
    old, old_id = _paired(ctx)
    for n in range(101):  # more than one page (limit 100) before the new file
        media.td_edit(ctx.state, old.asset_id, ctx.field, f"edit {n}")
    mark = ctx.mark()
    asset = media.td_new_file(ctx.state, fields={ctx.field: "A fire engine at night"})
    ctx.sync()
    cms_media_id = _link_of(ctx, mark, asset.asset_id)
    item = ctx.must_media(cms_media_id)
    expect(
        item.get("sha256") == asset.sha256,
        f"sha256 of the stored file is {item.get('sha256')!r}, not the file's {asset.sha256!r}",
    )
    expect(
        _value(ctx, cms_media_id) == "A fire engine at night",
        f"{ctx.field} is {_value(ctx, cms_media_id)!r}, not the value from the feed",
    )
    expect(
        _value(ctx, old_id) == "edit 100",
        f"after 102 changes {ctx.field} of {old_id!r} is {_value(ctx, old_id)!r}: read every "
        "page while has_more is true",
    )
    return f"linked as {cms_media_id!r}, same bytes and texts; all pages read"


def cursor_after_apply(ctx: Context) -> str:
    asset = media.td_new_file(ctx.state)
    asset.fail_download = 1_000_000
    mark = ctx.mark()
    try:
        ctx.sync()
    except Fail:
        pass  # a failing download may fail the sync command; that is allowed
    finally:
        asset.fail_download = 0
    linked = [r for r in ctx.requests_since(mark, "POST", LINK) if asset.asset_id in r.path]
    expect(not linked, "the integration linked a file it could not download")
    ctx.sync()
    _link_of(ctx, mark, asset.asset_id)
    return "the failed file came again after the fix: the cursor stayed before it"


def field_versions(ctx: Context) -> str:
    asset, cms_media_id = _paired(ctx)
    media.td_edit(ctx.state, asset.asset_id, ctx.field, "two")
    media.td_edit(ctx.state, asset.asset_id, ctx.field, "three")
    version = asset.fields[ctx.field].version
    ctx.state.add_change(
        "fields",
        payload={
            "asset_id": asset.asset_id,
            "cms_media_id": cms_media_id,
            "fields": [
                {
                    "field": ctx.field,
                    "value": "an older value",
                    "version": version - 1,
                    "changed_at": media.iso(media.now()),
                    "changed_by": "editor",
                }
            ],
        },
    )
    ctx.sync()
    got = _value(ctx, cms_media_id)
    expect(got == "three", f"a change with a lower version overwrote {ctx.field}: {got!r}")
    with ctx.state.lock:
        asset.fields[ctx.field].value = "repeated with the same version"
    media.td_repeat(ctx.state, asset.asset_id, ctx.field)
    ctx.sync()
    got = _value(ctx, cms_media_id)
    expect(
        got == "repeated with the same version",
        f"a change with the same version was skipped: {ctx.field} is {got!r}",
    )
    return "lower version skipped, same version applied"


def cms_new_file(ctx: Context) -> str:
    before = set(ctx.state.media.pending_imports) | set(ctx.state.media.by_cms)
    mark = ctx.mark()
    cms_media_id = ctx.media_add()
    ctx.sync()
    sent = [
        item
        for r in ctx.requests_since(mark, "POST", r"/v3/cms/media")
        for item in (r.body or {}).get("items", [])
    ]
    mine = [i for i in sent if i.get("cms_media_id") == cms_media_id]
    expect(bool(mine), f"the new file {cms_media_id!r} was not sent with POST /v3/cms/media")
    missing = [k for k in ("width", "height", "mime_type") if not mine[0].get(k)]
    expect(not missing, f"POST /media without {', '.join(missing)}: it is rejected")
    ctx.media_edit(cms_media_id, ctx.field, "written before the import")
    ctx.sync()
    media.import_pending(ctx.state)
    ctx.sync()
    ctx.sync()
    asset = ctx.state.media.paired(cms_media_id)
    expect(asset is not None, "the file was never paired")
    assert asset is not None
    got = asset.fields[ctx.field].value
    expect(
        got == "written before the import",
        f"the edit made before the import did not reach Tribune Desk ({ctx.field}: {got!r})",
    )
    item = ctx.must_media(cms_media_id)
    expect(
        item.get("asset_id") == asset.asset_id,
        f"asset_id is {item.get('asset_id')!r}; send POST /media again to learn it",
    )
    after = set(ctx.state.media.pending_imports) | set(ctx.state.media.by_cms)
    extra = sorted(after - before - {cms_media_id})
    expect(not extra, f"repeated requests made other ids for the same file: {extra}")
    return f"{cms_media_id!r} sent, paired, its edit delivered, no duplicate"


def cms_field_edit(ctx: Context) -> str:
    asset, cms_media_id = _paired(ctx)
    media.td_edit(ctx.state, asset.asset_id, ctx.field, "edited in Tribune Desk")
    ctx.sync()
    known = asset.fields[ctx.field].version
    _settle_window(ctx)
    mark = ctx.mark()
    ctx.media_edit(cms_media_id, ctx.field, "edited in the CMS")
    ctx.sync()
    ctx.sync()
    writes = _writes(ctx, mark, cms_media_id)
    expect(bool(writes), "the edit was not sent with POST /v3/cms/media/fields")
    expect(
        writes[0].get("base_version") == known,
        f"base_version is {writes[0].get('base_version')!r}, not the version you held ({known})",
    )
    got = asset.fields[ctx.field].value
    expect(got == "edited in the CMS", f"Tribune Desk has {got!r}")
    expect(len(writes) == 1, f"the same edit was sent {len(writes)} times")
    return f"one write with base_version {known}"


def cms_deletion(ctx: Context) -> str:
    asset, cms_media_id = _paired(ctx)
    mark = ctx.mark()
    ctx.media_delete(cms_media_id)
    ctx.sync()
    ctx.sync()
    calls = ctx.requests_since(mark, "POST", r"/v3/cms/media/deletions")
    items = [i for r in calls for i in (r.body or {}).get("items", [])]
    expect(
        any(i.get("cms_media_id") == cms_media_id and i.get("deleted_at") for i in items),
        "the deletion was not sent with POST /v3/cms/media/deletions",
    )
    expect(all(r.status == 200 for r in calls), f"answers {[r.status for r in calls]}")
    expect(asset.missing, "Tribune Desk did not record the deletion")
    return "deletion reported"


def conflict_winning_value(ctx: Context) -> str:
    asset, cms_media_id = _paired(ctx)
    media.td_settings(ctx.state, conflict_rule="td")
    try:
        ctx.sync()
        _settle_window(ctx)
        ctx.media_edit(cms_media_id, ctx.field, "the CMS's value")
        media.td_edit(ctx.state, asset.asset_id, ctx.field, "Tribune Desk's value")
        mark = ctx.mark()
        ctx.sync()
        ctx.sync()
    finally:
        media.td_settings(ctx.state, conflict_rule="last_change")
    got = _value(ctx, cms_media_id)
    expect(got == "Tribune Desk's value", f"after conflict {ctx.field} is {got!r}")
    writes = _writes(ctx, mark, cms_media_id)
    expect(len(writes) <= 1, f"the losing value was sent {len(writes)} times")
    return "winning_value adopted, nothing resent"


def both_sides_edited(ctx: Context) -> str:
    asset, cms_media_id = _paired(ctx)
    held = asset.fields[ctx.field].version
    _settle_window(ctx)
    ctx.media_edit(cms_media_id, ctx.field, "edited here, not sent yet")
    media.td_edit(ctx.state, asset.asset_id, ctx.field, "edited there meanwhile")
    mark = ctx.mark()
    ctx.sync()
    writes = _writes(ctx, mark, cms_media_id)
    expect(
        bool(writes),
        "the local edit was not sent: the feed's change overwrote a field you had not sent",
    )
    expect(
        writes[0].get("base_version") == held,
        f"base_version {writes[0].get('base_version')!r}: send the version you held ({held}), "
        "not the feed's",
    )
    return f"the local edit went with base_version {held}; the server decided"


def held_not_resent(ctx: Context) -> str:
    _, first = _paired(ctx)
    _, second = _paired(ctx)
    media.td_settings(ctx.state, mass_change_threshold=1)
    try:
        ctx.sync()
        _settle_window(ctx)
        mark = ctx.mark()
        ctx.media_edit(first, ctx.field, "within the threshold")
        ctx.media_edit(second, ctx.field, "over the threshold")
        ctx.sync()
        held = [
            (item["id"], f["field"])
            for r in ctx.requests_since(mark, "POST", r"/v3/cms/media/fields")
            for item in (r.answer or {}).get("results", [])
            for f in item.get("fields", [])
            if f.get("status") == "held"
        ]
        expect(bool(held), "no write was held: the scenario could not set the threshold")
        later = ctx.mark()
        ctx.sync()
    finally:
        media.td_settings(ctx.state, mass_change_threshold=500)
    held_id, _ = held[0]
    again = _writes(ctx, later, held_id)
    expect(not again, "a held field was sent again: it waits in the batch, decide it instead")
    decided = ctx.requests_since(mark, "POST", r"/v3/cms/held/[^/]+/decision")
    expect(not decided, "the sync decided a held batch by itself; a person decides it")
    return "held field not resent, batch left for a person (check the screen by hand)"


def settings_and_unknown_kinds(ctx: Context) -> str:
    mark = ctx.mark()
    media.td_settings(ctx.state, keep_copies_in_td=True)
    media.td_unknown_kind(ctx.state, "tdkit_future_kind")
    asset = media.td_new_file(ctx.state)
    ctx.sync()
    read = ctx.requests_since(mark, "GET", r"/v3/cms/settings")
    expect(bool(read), 'after kind="settings" the integration did not read GET /v3/cms/settings')
    _link_of(ctx, mark, asset.asset_id)
    return "settings read again; the unknown kind skipped"


def td_trash_mark(ctx: Context) -> str:
    asset, cms_media_id = _paired(ctx)
    media.td_trash(ctx.state, asset.asset_id, True)
    ctx.sync()
    item = ctx.media_inspect(cms_media_id)
    expect(item is not None, "the file was deleted from the library after a trash in Tribune Desk")
    assert item is not None
    expect(item.get("deleted_in_td") is True, f"deleted_in_td is {item.get('deleted_in_td')!r}")
    media.td_trash(ctx.state, asset.asset_id, False)
    ctx.sync()
    item = ctx.must_media(cms_media_id)
    expect(item.get("deleted_in_td") is False, f"after restore: {item.get('deleted_in_td')!r}")
    return "marked, then unmarked; the file stayed"


def backfill_answered(ctx: Context) -> str:
    some = media.td_backfill_request(ctx.state, {"min_width": 1000})
    none = media.td_backfill_request(ctx.state, {"date_from": "2999-01-01T00:00:00+00:00"})
    mark = ctx.mark()
    ctx.sync()
    lib = ctx.state.media
    for request_id, what in ((some, "with candidates"), (none, "without candidates")):
        pages = ctx.requests_since(mark, "POST", rf"/v3/cms/backfill/requests/{request_id}/pages")
        expect(bool(pages), f"the request {what} got no page")
        expect(
            lib.backfills[request_id].state == "closed",
            f"the request {what} is still open: send is_last on the last page",
        )
    return "both requests answered and closed"


def cursor_expired_resync(ctx: Context) -> str:
    asset, cms_media_id = _paired(ctx)
    ctx.sync()
    _settle_window(ctx)
    ctx.media_edit(cms_media_id, ctx.field, "unsent before the 410")
    ctx.state.expire_cursor_once = True
    mark = ctx.mark()
    ctx.sync()
    polls = _polls(ctx, mark)
    expect(any(p.status == 410 for p in polls), "the integration did not poll with its cursor")
    gone = next(i for i, p in enumerate(polls) if p.status == 410)
    fresh = [p for p in polls[gone + 1 :] if _cursor(p) is None]
    expect(not fresh, "after 410 the integration polled from now (no cursor) instead of a resync")
    resyncs = ctx.requests_since(mark, "POST", r"/v3/cms/resync")
    previews = [r for r in resyncs if not (r.body or {}).get("confirm")]
    expect(bool(previews), "after 410 no resync preview was started (POST /v3/cms/resync)")
    expect(
        all((r.body or {}).get("direction") == "td_to_cms" for r in previews),
        "the preview after 410 is not td_to_cms (send your edits first, then td_to_cms)",
    )
    expect(any((r.body or {}).get("is_last") for r in previews), "no preview page had is_last")
    confirmed = [r for r in resyncs if (r.body or {}).get("confirm")]
    expect(not confirmed, "the sync confirmed the resync by itself; show the preview to a person")
    first_preview = ctx.state.requests.index(previews[0])
    writes = [
        r
        for r in ctx.state.requests[mark:first_preview]
        if r.method == "POST" and r.path == "/v3/cms/media/fields"
    ]
    expect(bool(writes), "the unsent edit was not sent before the preview")
    expect(asset.fields[ctx.field].value == "unsent before the 410", "the edit did not arrive")
    return "edits sent, td_to_cms preview waiting for a person"


# -- the list ------------------------------------------------------------------------------

MEDIA_SCENARIOS: tuple[Scenario, ...] = (
    Scenario("l4-first-poll", 4, "any", DW_POLL, DW4, first_poll),
    Scenario(
        "l4-new-asset-linked",
        4,
        "any",
        S_LINK,
        f"{G4}#taking-files-from-tribune-desk",
        new_asset_linked,
    ),
    Scenario("l4-cursor-after-apply", 4, "any", DW_POLL, DW4, cursor_after_apply),
    Scenario("l4-field-versions", 4, "any", S_VERSION, CYCLE, field_versions),
    Scenario("l4-cms-new-file", 4, "any", DW_PUSH, DW4, cms_new_file),
    Scenario("l4-cms-field-edit", 4, "any", DW_PUSH, DW4, cms_field_edit),
    Scenario("l4-cms-deletion", 4, "any", DW_PUSH, DW4, cms_deletion),
    Scenario("l4-conflict-winning-value", 4, "any", DW_CONFLICT, DW4, conflict_winning_value),
    Scenario("l4-both-sides-edited", 4, "any", S_BOTH, CYCLE, both_sides_edited),
    Scenario("l4-held-not-resent", 4, "any", DW_HELD, DW4, held_not_resent),
    Scenario(
        "l4-settings-and-unknown-kinds", 4, "any", S_SETTINGS, CYCLE, settings_and_unknown_kinds
    ),
    Scenario("l4-td-trash-mark", 4, "any", S_TRASH, f"{G4}#deletions", td_trash_mark),
    Scenario(
        "l4-backfill-answered",
        4,
        "any",
        S_BACKFILL,
        f"{G4}#historical-import",
        backfill_answered,
        needs_backfill=True,
    ),
    Scenario("l4-cursor-expired-resync", 4, "any", DW_410, DW4, cursor_expired_resync),
)
