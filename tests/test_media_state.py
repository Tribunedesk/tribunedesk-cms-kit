"""Level 4 rules of the mock (`tdkit.mock.media`), one test per rule of guide 4."""

from __future__ import annotations

import struct
import zlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tdkit.mock import media
from tdkit.mock.media import MediaError
from tdkit.mock.png import png
from tdkit.mock.state import MockState

T0 = datetime.now(UTC).replace(microsecond=0)  # td_edit uses the real clock


def at(minutes: float) -> str:
    return (T0 + timedelta(minutes=minutes)).isoformat()


@pytest.fixture
def st() -> MockState:
    state = MockState()
    state.media.enabled_at = T0 - timedelta(days=1)
    return state


def paired(st: MockState, cms_id: str = "m1", **fields: str) -> media.Asset:
    asset = media.td_new_file(st, fields=fields or {"alt": "old"})
    media.link(st, asset.asset_id, cms_id, "http://127.0.0.1:8000/m1.png", False)
    return asset


def write(cms_id: str, field: str, value: str, changed_at: str, base: int | None = None) -> dict:
    one: dict[str, Any] = {"field": field, "value": value, "changed_at": changed_at}
    if base is not None:
        one["base_version"] = base
    return {"cms_media_id": cms_id, "fields": [one]}


def outcome(st: MockState, item: dict, moment: datetime | None = None) -> dict[str, Any]:
    results, _ = media.cms_field_writes(st, [item], moment or T0 + timedelta(hours=1))
    return results[0]["fields"][0]


# -- files, feed, link ---------------------------------------------------------------------


def test_png_is_valid() -> None:
    data = png(800, 600)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", data[16:24]) == (800, 600)
    length = struct.unpack(">I", data[33:37])[0]
    raw = zlib.decompress(data[41 : 41 + length])
    assert len(raw) == 600 * (1 + 800 * 3)


def test_new_asset_change_payload_has_guide_fields(st: MockState) -> None:
    asset = media.td_new_file(st, fields={"alt": "A fire engine"})
    body = media.change_body(st, st.changes[-1])
    assert body is not None
    assert body["kind"] == "new_asset"
    assert body["asset_id"] == asset.asset_id
    for key in ("file_url", "file_url_expires_at", "mime_type", "filename", "sha256"):
        assert body[key]
    assert (body["width"], body["height"]) == (1200, 800)
    assert body["fields"][0]["field"] == "alt"
    assert body["fields"][0]["value"] == "A fire engine"


def test_field_change_only_for_paired(st: MockState) -> None:
    asset = media.td_new_file(st, fields={"alt": "x"})
    before = len(st.changes)
    assert media.td_edit(st, asset.asset_id, "alt", "y") == 1
    assert len(st.changes) == before


def test_edit_of_paired_file_grows_version_and_enters_feed(st: MockState) -> None:
    asset = paired(st)
    assert media.td_edit(st, asset.asset_id, "alt", "new") == 2
    body = media.change_body(st, st.changes[-1])
    assert body is not None
    assert body["kind"] == "fields"
    assert body["cms_media_id"] == "m1"
    assert body["fields"][0]["version"] == 2


def test_repeat_keeps_version(st: MockState) -> None:
    asset = paired(st)
    media.td_edit(st, asset.asset_id, "alt", "new")
    media.td_repeat(st, asset.asset_id, "alt")
    body = media.change_body(st, st.changes[-1])
    assert body is not None
    assert body["fields"][0]["version"] == 2
    assert body["fields"][0]["changed_by"] == "editor"


def test_link_ok_then_known_then_conflict_other_id(st: MockState) -> None:
    asset = media.td_new_file(st)
    url = "http://127.0.0.1:8000/a.png"
    assert media.link(st, asset.asset_id, "m1", url, False)["status"] == "ok"
    assert media.link(st, asset.asset_id, "m1", url, False)["status"] == "known"
    with pytest.raises(MediaError) as err:
        media.link(st, asset.asset_id, "m2", url, False)
    assert err.value.status == 409


def test_link_404_trashed(st: MockState) -> None:
    asset = media.td_new_file(st)
    media.td_trash(st, asset.asset_id, True)
    with pytest.raises(MediaError) as err:
        media.link(st, asset.asset_id, "m1", "http://127.0.0.1/a", False)
    assert err.value.status == 404


def test_link_422_bad_host(st: MockState) -> None:
    asset = media.td_new_file(st)
    with pytest.raises(MediaError) as err:
        media.link(st, asset.asset_id, "m1", "https://example.com/a", False)
    assert err.value.status == 422


def test_link_emits_fields_change(st: MockState) -> None:
    paired(st)
    body = media.change_body(st, st.changes[-1])
    assert body is not None
    assert (body["kind"], body["cms_media_id"]) == ("fields", "m1")


def test_new_asset_left_out_once_linked(st: MockState) -> None:
    asset = media.td_new_file(st)
    change = st.changes[-1]
    media.link(st, asset.asset_id, "m1", "http://127.0.0.1/a", False)
    assert media.change_body(st, change) is None


@pytest.mark.parametrize(
    ("url", "extra", "ok"),
    [
        ("http://127.0.0.1:8000/x", (), True),
        ("https://localhost/x", (), True),
        ("http://www.localhost:9/x", (), True),
        ("http://user:pw@127.0.0.1/x", (), False),
        ("ftp://127.0.0.1/x", (), False),
        ("http://example.com/x", (), False),
        ("http://example.com/x", ("example.com",), True),
    ],
)
def test_allowed_cms_url(url: str, extra: tuple[str, ...], ok: bool) -> None:
    assert media.allowed_cms_url(url, extra) is ok


# -- writes from the CMS: the six steps -----------------------------------------------------


def test_field_disabled_rejected(st: MockState) -> None:
    paired(st)
    st.media.options["fields_cms_to_td"]["alt"] = False
    result = outcome(st, write("m1", "alt", "new", at(0), 1))
    assert (result["status"], result["reason"]) == ("rejected", "field_disabled")


def test_same_value_unchanged_not_counted(st: MockState) -> None:
    paired(st)
    st.media.options["mass_change_threshold"] = 1
    assert outcome(st, write("m1", "alt", "old", at(0), 1))["status"] == "unchanged"
    assert outcome(st, write("m1", "alt", "new", at(0), 1))["status"] == "ok"


def test_keep_nonempty_rejected(st: MockState) -> None:
    paired(st)
    st.media.options["keep_nonempty_cms_to_td"] = True
    result = outcome(st, write("m1", "alt", "new", at(0), 1))
    assert (result["status"], result["reason"]) == ("rejected", "keep_nonempty")


def test_base_version_equal_applies(st: MockState) -> None:
    asset = paired(st)
    media.td_edit(st, asset.asset_id, "alt", "td")
    result = outcome(st, write("m1", "alt", "cms", at(-600), 2))
    assert (result["status"], result["version"]) == ("ok", 3)


def test_never_changed_by_td_applies_any_base(st: MockState) -> None:
    paired(st)
    assert outcome(st, write("m1", "alt", "cms", at(-600), 7))["status"] == "ok"


def test_no_base_changed_at_newer_applies(st: MockState) -> None:
    asset = paired(st)
    st.media.options["conflict_rule"] = "td"
    media.td_edit(st, asset.asset_id, "alt", "td")
    assert outcome(st, write("m1", "alt", "cms", at(120))) == {
        "field": "alt",
        "version": 3,
        "status": "ok",
    }


def test_rule_td_conflict_has_winning_value(st: MockState) -> None:
    asset = paired(st)
    st.media.options["conflict_rule"] = "td"
    media.td_edit(st, asset.asset_id, "alt", "td")
    result = outcome(st, write("m1", "alt", "cms", at(120), 1))
    assert result["status"] == "conflict"
    assert (result["winning_value"], result["version"]) == ("td", 2)


def test_rule_cms_applies(st: MockState) -> None:
    asset = paired(st)
    st.media.options["conflict_rule"] = "cms"
    media.td_edit(st, asset.asset_id, "alt", "td")
    assert outcome(st, write("m1", "alt", "cms", at(-600), 1))["status"] == "ok"


def test_last_change_older_conflict(st: MockState) -> None:
    asset = paired(st)
    media.td_edit(st, asset.asset_id, "alt", "td")
    old = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    assert outcome(st, write("m1", "alt", "cms", old, 1))["status"] == "conflict"


def test_future_changed_at_counts_as_now(st: MockState) -> None:
    asset = paired(st)
    media.td_edit(st, asset.asset_id, "alt", "td")
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    moment = datetime.now(UTC) + timedelta(seconds=5)
    assert outcome(st, write("m1", "alt", "cms", future, 1), moment)["status"] == "ok"
    assert st.media.assets[asset.asset_id].fields["alt"].changed_at <= moment


def test_nul_is_value_error(st: MockState) -> None:
    paired(st)
    with pytest.raises(ValueError):
        media.cms_field_writes(st, [write("m1", "alt", "a\x00b", at(0), 1)])


def test_threshold_holds_over_limit_same_batch_in_window(st: MockState) -> None:
    paired(st, "m1")
    paired(st, "m2")
    paired(st, "m3")
    st.media.options["mass_change_threshold"] = 1
    moment = T0 + timedelta(hours=1)
    first, held = media.cms_field_writes(st, [write("m1", "alt", "a", at(0), 1)], moment)
    assert first[0]["fields"][0]["status"] == "ok"
    assert held is None
    second, held2 = media.cms_field_writes(st, [write("m2", "alt", "b", at(0), 1)], moment)
    assert second[0]["fields"][0]["status"] == "held"
    later = moment + timedelta(minutes=30)
    _, held3 = media.cms_field_writes(st, [write("m3", "alt", "c", at(0), 1)], later)
    assert held2 is not None
    assert held3 == held2
    assert st.media.held[held2].view()["count"] == 2
    _, held4 = media.cms_field_writes(
        st, [write("m3", "alt", "d", at(0), 1)], moment + timedelta(minutes=61)
    )
    assert held4 is None


def test_unknown_before_import_then_ok(st: MockState) -> None:
    item = {
        "cms_media_id": "c1",
        "file_url": "http://127.0.0.1:8000/c1.png",
        "width": 1200,
        "height": 800,
        "mime_type": "image/png",
    }
    assert media.cms_new_files(st, [item])[0] == {"id": "c1", "asset_id": None, "status": "ok"}
    results, _ = media.cms_field_writes(st, [write("c1", "alt", "x", at(0), 1)])
    assert results[0]["status"] == "unknown"
    assert media.cms_new_files(st, [item])[0]["status"] == "known"
    assert media.import_pending(st) == ["c1"]
    again = media.cms_new_files(st, [item])[0]
    assert again["status"] == "known"
    assert again["asset_id"] is not None
    assert outcome(st, write("c1", "alt", "x", at(0), 1))["status"] == "ok"


def test_import_does_not_write_initial_fields(st: MockState) -> None:
    item = {
        "cms_media_id": "c1",
        "file_url": "http://127.0.0.1:8000/c1.png",
        "width": 1200,
        "height": 800,
        "mime_type": "image/png",
        "fields": [{"field": "alt", "value": "context", "changed_at": at(0)}],
    }
    media.cms_new_files(st, [item])
    media.import_pending(st)
    asset = st.media.paired("c1")
    assert asset is not None
    assert asset.fields["alt"].value == ""


@pytest.mark.parametrize(
    ("change", "option", "reason"),
    [
        ({"width": None}, {}, "missing_metadata"),
        ({}, {"new_files_cms_to_td": False}, "new_files_disabled"),
        ({"created_at": at(-60)}, {"new_files_cms_to_td_since": at(0)}, "before_since"),
        ({"width": 1000}, {"new_files_cms_to_td_min_width": 1100}, "below_min_width"),
        ({"file_url": "https://example.com/a.png"}, {}, "host"),
        ({"width": 799}, {}, "too_small"),
        ({"mime_type": "image/gif"}, {}, "mime"),
    ],
)
def test_new_files_rejections(
    st: MockState, change: dict[str, Any], option: dict[str, Any], reason: str
) -> None:
    item = {
        "cms_media_id": "c1",
        "file_url": "http://127.0.0.1:8000/c1.png",
        "width": 1200,
        "height": 800,
        "mime_type": "image/png",
        **change,
    }
    st.media.options.update(option)
    result = media.cms_new_files(st, [item])[0]
    assert (result["status"], result["reason"]) == ("rejected", reason)
    assert "c1" not in st.media.pending_imports


def test_deletions_duplicate_id_is_value_error(st: MockState) -> None:
    with pytest.raises(ValueError):
        media.cms_deletions(st, [{"cms_media_id": "a"}, {"cms_media_id": "a"}])


def test_deletions_ok_known_unknown(st: MockState) -> None:
    paired(st)
    assert media.cms_deletions(st, [{"cms_media_id": "m1"}])[0]["status"] == "ok"
    assert media.cms_deletions(st, [{"cms_media_id": "m1"}])[0]["status"] == "known"
    assert media.cms_deletions(st, [{"cms_media_id": "zz"}])[0]["status"] == "unknown"


def test_deletions_threshold_reason(st: MockState) -> None:
    paired(st, "m1")
    paired(st, "m2")
    st.media.options.update(cms_deletion_trashes_in_td=True, mass_change_threshold=1)
    results = media.cms_deletions(st, [{"cms_media_id": "m1"}, {"cms_media_id": "m2"}])
    assert results[0] == {"id": "m1", "status": "ok"}
    assert results[1] == {"id": "m2", "status": "ok", "reason": "threshold"}


def test_decide_held_send_applies_and_second_decision_409(st: MockState) -> None:
    paired(st, "m1")
    paired(st, "m2")
    st.media.options["mass_change_threshold"] = 1
    media.cms_field_writes(st, [write("m1", "alt", "a", at(0), 1)])
    _, held = media.cms_field_writes(st, [write("m2", "alt", "b", at(0), 1)])
    assert held is not None
    assert media.decide_held(st, held, "send")["state"] == "sent"
    asset = st.media.paired("m2")
    assert asset is not None
    assert asset.fields["alt"].value == "b"
    with pytest.raises(MediaError) as err:
        media.decide_held(st, held, "discard")
    assert err.value.status == 409


# -- resync, settings, push-existing, backfill ----------------------------------------------


def preview(st: MockState, direction: str, value: str, **extra: Any) -> dict[str, Any]:
    body = {
        "direction": direction,
        "items": [{"cms_media_id": "m1", "fields": [{"field": "alt", "value": value}]}],
        "is_last": True,
        **extra,
    }
    return media.resync(st, body)


def test_resync_collecting_ready_and_page_after_ready_409(st: MockState) -> None:
    paired(st)
    first = media.resync(st, {"direction": "td_to_cms", "items": [], "is_last": False})
    assert first["status"] == "collecting"
    ready = preview(st, "td_to_cms", "cms", resync_id=first["resync_id"])
    assert (ready["status"], ready["differences"]) == ("ready", 1)
    with pytest.raises(MediaError) as err:
        preview(st, "td_to_cms", "cms", resync_id=first["resync_id"])
    assert err.value.status == 409


def test_resync_repeat_page_replaces(st: MockState) -> None:
    paired(st)
    first = media.resync(
        st,
        {
            "direction": "cms_to_td",
            "items": [{"cms_media_id": "m1", "fields": [{"field": "alt", "value": "x"}]}],
            "is_last": False,
        },
    )
    again = preview(st, "cms_to_td", "x", resync_id=first["resync_id"])
    assert again["differences"] == 1


def test_resync_other_direction_409(st: MockState) -> None:
    paired(st)
    first = media.resync(st, {"direction": "cms_to_td", "items": [], "is_last": False})
    with pytest.raises(MediaError):
        preview(st, "td_to_cms", "x", resync_id=first["resync_id"])


def test_resync_confirm_cursor_from_preview_start(st: MockState) -> None:
    paired(st)
    start = st.seq
    ready = preview(st, "cms_to_td", "cms")
    media.td_new_file(st)
    answer = media.resync(st, {"resync_id": ready["resync_id"], "confirm": True})
    assert answer == {"status": "applied", "cursor": st.cursor_for(start), "held_batch_id": None}
    assert media.resync(st, {"resync_id": ready["resync_id"], "confirm": True}) == answer
    asset = st.media.paired("m1")
    assert asset is not None
    assert asset.fields["alt"].value == "cms"


def test_resync_td_to_cms_emits_fields_same_version(st: MockState) -> None:
    asset = paired(st)
    version = asset.fields["alt"].version
    ready = preview(st, "td_to_cms", "stale")
    before = st.seq
    media.resync(st, {"resync_id": ready["resync_id"], "confirm": True})
    after = [c for c in st.changes if c.seq > before]
    assert [c.kind for c in after] == ["fields"]
    body = media.change_body(st, after[0])
    assert body is not None
    assert body["fields"][0]["version"] == version
    assert body["fields"][0]["value"] == "old"


def test_resync_over_threshold_held(st: MockState) -> None:
    paired(st)
    st.media.options["mass_change_threshold"] = 1
    st.media.resyncs.clear()
    body = {
        "direction": "cms_to_td",
        "items": [
            {
                "cms_media_id": "m1",
                "fields": [{"field": "alt", "value": "a"}, {"field": "title", "value": "t"}],
            }
        ],
        "is_last": True,
    }
    ready = media.resync(st, body)
    answer = media.resync(st, {"resync_id": ready["resync_id"], "confirm": True})
    assert answer["status"] == "held"
    assert answer["held_batch_id"] in st.media.held


def test_resync_after_reenable_409(st: MockState) -> None:
    paired(st)
    ready = preview(st, "cms_to_td", "x")
    st.set_enabled(False)
    st.set_enabled(True)
    with pytest.raises(MediaError) as err:
        media.resync(st, {"resync_id": ready["resync_id"], "confirm": True})
    assert err.value.status == 409


def test_settings_put_variant_and_locked_409(st: MockState) -> None:
    view = media.settings_put(st, {"variant": "cms_to_td_only"})
    assert view["variant"] == "cms_to_td_only"
    assert view["options"]["new_files_td_to_cms"] is False
    assert view["options"]["fields_td_to_cms"]["alt"] is False
    st.media.locked.add("fields_td_to_cms.alt")
    with pytest.raises(MediaError) as err:
        media.settings_put(st, {"variant": "full"})
    assert (err.value.status, err.value.code) == (409, "option_locked")


def test_settings_custom_needs_options(st: MockState) -> None:
    with pytest.raises(MediaError) as err:
        media.settings_put(st, {"variant": "custom"})
    assert err.value.status == 422


def test_settings_change_in_feed(st: MockState) -> None:
    media.settings_put(st, {"variant": "full"})
    assert st.changes[-1].kind == "settings"
    media.td_settings(st, conflict_rule="td")
    assert st.changes[-1].kind == "settings"
    assert media.settings_view(st)["options"]["conflict_rule"] == "td"


def test_push_existing_needs_first_poll(st: MockState) -> None:
    with pytest.raises(MediaError) as err:
        media.push_existing(st, None, None)
    assert err.value.status == 409


def test_push_existing_pages_until_next_after_null(st: MockState) -> None:
    for _ in range(3):
        media.td_new_file(st)
    st.switched, st.acked = True, st.seq  # the client acknowledged the three new_asset
    monkey = media.PUSH_PAGE
    media.PUSH_PAGE = 2
    try:
        first = media.push_existing(st, None, None)
        assert (first["queued"], first["held_batch_id"]) == (2, None)
        assert first["next_after"] is not None
        st.acked = st.seq
        second = media.push_existing(st, None, first["next_after"])
        assert (second["queued"], second["next_after"]) == (1, None)
        with pytest.raises(MediaError) as err:
            media.push_existing(st, None, "nonsense")
        assert err.value.status == 422
    finally:
        media.PUSH_PAGE = monkey


def candidate(cms_id: str, **change: Any) -> dict[str, Any]:
    return {
        "cms_media_id": cms_id,
        "file_url": f"http://127.0.0.1:8000/{cms_id}.png",
        "width": 1200,
        "height": 800,
        "mime_type": "image/png",
        **change,
    }


def test_backfill_page_results_and_close_on_last(st: MockState) -> None:
    request_id = media.td_backfill_request(st, {"min_width": 1000})
    assert media.backfill_list(st)["items"][0]["id"] == request_id
    page = media.backfill_page(
        st,
        request_id,
        {"items": [candidate("b1"), candidate("b2", width=900)], "is_last": False},
    )
    assert page["accepted"] == 1
    assert [r["status"] for r in page["results"]] == ["ok", "rejected"]
    assert page["results"][1]["reason"] == "too_small"
    again = media.backfill_page(st, request_id, {"items": [candidate("b1")], "is_last": True})
    assert again["results"][0]["status"] == "ok"
    assert media.backfill_list(st)["items"] == []
    with pytest.raises(MediaError) as err:
        media.backfill_page(st, request_id, {"items": [], "is_last": True})
    assert err.value.status == 409


def test_backfill_paused_empty_page_200_else_409(st: MockState) -> None:
    request_id = media.td_backfill_request(st)
    media.td_backfill_pause(st, request_id, True)
    assert media.backfill_page(st, request_id, {"items": [], "is_last": False}) == {
        "accepted": 0,
        "results": [],
    }
    with pytest.raises(MediaError):
        media.backfill_page(st, request_id, {"items": [candidate("b1")], "is_last": False})
