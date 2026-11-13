"""Level 4 routes of the mock over HTTP: checks in the contract's order, shapes, controls."""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.jsonschema import DRAFT202012

from tdkit.docs import ContractDocs
from tdkit.mock.state import MockState

from .test_mock_routes import call

NOW = "2026-11-13T10:00:00+00:00"
LEVEL4 = ("/media", "/resync", "/held", "/settings", "/backfill")


def contract_routes(docs: ContractDocs) -> list[tuple[str, str]]:
    return [
        (method.upper(), re.sub(r"\{[^}]+\}", "00000000-0000-4000-8000-000000000000", path))
        for path, ops in docs.openapi["paths"].items()
        for method in ops
        if method in ("get", "post", "put") and any(k in path for k in LEVEL4)
    ]


def validator(docs: ContractDocs, name: str) -> Draft202012Validator:
    registry: Registry = Registry().with_resource(
        "urn:t", DRAFT202012.create_resource(docs.openapi)
    )
    return Draft202012Validator({"$ref": f"urn:t#/components/schemas/{name}"}, registry=registry)


def test_each_level4_route_answers_not_501(base: str, docs: ContractDocs) -> None:
    routes = contract_routes(docs)
    assert len(routes) == 12
    for method, path in routes:
        status, _, _ = call(base, method, path, body={} if method != "GET" else None)
        assert status != 501, (method, path)


def test_level4_scope_403(state: MockState, base: str) -> None:
    state.tokens["reader"] = {"media:read"}
    status, error, _ = call(base, "POST", "/v3/cms/media/fields", token="reader", body={})
    assert (status, error["code"]) == (403, "forbidden")


def test_level4_body_additional_property_422(base: str) -> None:
    body = {"items": [{"cms_media_id": "a", "deleted_at": NOW, "extra": 1}]}
    status, error, _ = call(base, "POST", "/v3/cms/media/deletions", body=body)
    assert (status, error["code"]) == (422, "validation_error")


def test_level4_time_without_zone_422(base: str) -> None:
    body = {
        "items": [
            {
                "cms_media_id": "a",
                "fields": [{"field": "alt", "value": "x", "changed_at": "2026-11-13T10:00:00"}],
            }
        ]
    }
    assert call(base, "POST", "/v3/cms/media/fields", body=body)[0] == 422


def test_level4_disabled_409(state: MockState, base: str) -> None:
    state.set_enabled(False)
    body = {"items": [{"cms_media_id": "a", "deleted_at": NOW}]}
    status, error, _ = call(base, "POST", "/v3/cms/media/deletions", body=body)
    assert (status, error["code"]) == (409, "state_conflict")


def test_changes_new_asset_shape_validates_against_change_schema(
    base: str, docs: ContractDocs
) -> None:
    cursor = call(base, "GET", "/v3/cms/changes")[1]["next_cursor"]
    call(base, "POST", "/_tdkit/media", token=None, body={"fields": {"alt": "A"}})
    page = call(base, "GET", f"/v3/cms/changes?cursor={cursor}")[1]
    validator(docs, "ChangesResponse").validate(page)
    (change,) = page["changes"]
    assert change["kind"] == "new_asset"
    assert change["file_url"].startswith(base + "/files/")


def test_files_png_served_and_fail_download_500(state: MockState, base: str) -> None:
    asset_id = call(base, "POST", "/_tdkit/media", token=None, body={})[1]["asset_id"]
    asset = state.media.assets[asset_id]
    with urllib.request.urlopen(f"{base}/files/{asset.filename}", timeout=5) as response:
        assert response.headers["Content-Type"] == "image/png"
        assert response.read() == asset.data
    asset.fail_download = 1
    try:
        urllib.request.urlopen(f"{base}/files/{asset.filename}", timeout=5)
        raise AssertionError("expected 500")
    except urllib.error.HTTPError as exc:
        assert exc.code == 500
    with urllib.request.urlopen(f"{base}/files/{asset.filename}", timeout=5) as response:
        assert response.status == 200


def test_control_routes_roundtrip(state: MockState, base: str, docs: ContractDocs) -> None:
    cursor = call(base, "GET", "/v3/cms/changes")[1]["next_cursor"]
    asset_id = call(base, "POST", "/_tdkit/media", token=None, body={})[1]["asset_id"]
    link = {"cms_media_id": "m1", "file_url": "http://127.0.0.1:8000/m1.png"}
    status, result, _ = call(base, "POST", f"/v3/cms/media/{asset_id}/link", body=link)
    assert (status, result["status"]) == (200, "ok")
    body = {"field": "alt", "value": "edited in TD"}
    call(base, "POST", f"/_tdkit/media/{asset_id}/fields", token=None, body=body)
    page = call(base, "GET", f"/v3/cms/changes?cursor={cursor}")[1]
    validator(docs, "ChangesResponse").validate(page)
    kinds = [c["kind"] for c in page["changes"]]
    assert kinds == ["fields"]  # new_asset is left out once linked; the edit follows
    assert page["changes"][-1]["fields"][0]["value"] == "edited in TD"
    write: dict[str, Any] = {
        "items": [
            {
                "cms_media_id": "m1",
                "fields": [{"field": "alt", "value": "cms", "changed_at": NOW, "base_version": 2}],
            }
        ]
    }
    status, answer, _ = call(base, "POST", "/v3/cms/media/fields", body=write)
    assert status == 200
    validator(docs, "BatchResult").validate(answer)
    assert answer["results"][0]["fields"][0]["status"] == "ok"


@pytest.mark.parametrize(
    ("path", "body", "schema"),
    [
        ("/v3/cms/held", None, "HeldList"),
        ("/v3/cms/settings", None, "SettingsResponse"),
        ("/v3/cms/backfill/requests", None, "BackfillRequestList"),
        ("/v3/cms/status", None, "StatusResponse"),
    ],
)
def test_read_routes_match_their_schemas(
    base: str, docs: ContractDocs, path: str, body: Any, schema: str
) -> None:
    call(base, "POST", "/_tdkit/backfill", token=None, body={"filters": {"min_width": 900}})
    status, answer, _ = call(base, "GET", path)
    assert status == 200
    validator(docs, schema).validate(answer)


def test_resync_preview_and_confirm_over_http(base: str, docs: ContractDocs) -> None:
    preview = {"direction": "td_to_cms", "items": [], "is_last": True}
    status, ready, _ = call(base, "POST", "/v3/cms/resync", body=preview)
    assert (status, ready["status"]) == (200, "ready")
    validator(docs, "ResyncPreviewResponse").validate(ready)
    confirm = {"resync_id": ready["resync_id"], "confirm": True}
    status, done, _ = call(base, "POST", "/v3/cms/resync", body=confirm)
    assert (status, done["status"]) == (200, "applied")
    validator(docs, "ResyncConfirmResponse").validate(done)
    assert call(base, "GET", f"/v3/cms/changes?cursor={done['cursor']}")[0] == 200
