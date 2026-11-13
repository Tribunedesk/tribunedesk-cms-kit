"""The level 4 routes of the mock and its `/_tdkit/*` controls for level 4.

Each route checks, in the contract's order, the token (401), the scope (403), the body against
the tag's schema (422) and the integration's state (409), then calls `tdkit.mock.media`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from tdkit.mock import media
from tdkit.mock.api import Answer, ApiError, Request
from tdkit.mock.media import MediaError

if TYPE_CHECKING:
    from tdkit.mock.server import MockServer

Route = tuple[str, re.Pattern[str], Callable[[Request], Answer]]

SCHEMAS = (
    "NewMediaRequest",
    "FieldsRequest",
    "DeletionsRequest",
    "LinkRequest",
    "ResyncPreviewRequest",
    "ResyncConfirmRequest",
    "HeldDecisionRequest",
    "SettingsUpdate",
    "PushExistingRequest",
    "BackfillPageRequest",
)


def _has_nul(value: Any) -> bool:
    if isinstance(value, str):
        return "\x00" in value
    if isinstance(value, dict):
        return any(_has_nul(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_nul(v) for v in value)
    return False


def routes(server: MockServer) -> list[Route]:
    state = server.state

    def guard(request: Request, scopes: tuple[str, ...], schema: str | None) -> dict[str, Any]:
        server._require(request, *scopes)
        body: dict[str, Any] = {}
        if schema is not None:
            if not request.raw and schema == "PushExistingRequest":
                request.raw = b"{}"
            body = server._body(request, schema)
            if _has_nul(body):
                raise ApiError(422, "validation_error", "a NUL character in a value")
        if not state.integration_enabled:
            raise ApiError(409, "state_conflict", "the integration is not enabled")
        return body

    def call(action: Callable[[], Any]) -> Any:
        try:
            return action()
        except MediaError as exc:
            raise ApiError(exc.status, exc.code, exc.message) from None
        except ValueError as exc:
            raise ApiError(422, "validation_error", str(exc)) from None

    def new_files(request: Request) -> Answer:
        body = guard(request, ("media:write",), "NewMediaRequest")
        results = call(lambda: media.cms_new_files(state, body["items"]))
        return Answer(200, {"results": results, "held_batch_id": None})

    def fields(request: Request) -> Answer:
        body = guard(request, ("media:write",), "FieldsRequest")
        results, held = call(lambda: media.cms_field_writes(state, body["items"]))
        return Answer(200, {"results": results, "held_batch_id": held})

    def deletions(request: Request) -> Answer:
        body = guard(request, ("media:write",), "DeletionsRequest")
        results = call(lambda: media.cms_deletions(state, body["items"]))
        return Answer(200, {"results": results, "held_batch_id": None})

    def link(request: Request) -> Answer:
        body = guard(request, ("media:write",), "LinkRequest")
        asset_id = request.match.group("asset_id")
        result = call(
            lambda: media.link(
                state,
                asset_id,
                str(body["cms_media_id"]),
                str(body["file_url"]),
                bool(body.get("reencoded", False)),
            )
        )
        return Answer(200, result)

    def push(request: Request) -> Answer:
        body = guard(request, ("media:write",), "PushExistingRequest")
        result = call(lambda: media.push_existing(state, body.get("since"), body.get("after")))
        return Answer(200, result)

    def resync(request: Request) -> Answer:
        server._require(request, "media:write")
        raw = json.loads(request.raw) if request.raw else None
        confirm = isinstance(raw, dict) and "confirm" in raw
        body = guard(
            request, ("media:write",), "ResyncConfirmRequest" if confirm else "ResyncPreviewRequest"
        )
        return Answer(200, call(lambda: media.resync(state, body)))

    def held(request: Request) -> Answer:
        guard(request, ("media:read",), None)
        return Answer(200, media.held_list(state))

    def decision(request: Request) -> Answer:
        body = guard(request, ("media:write",), "HeldDecisionRequest")
        held_id = request.match.group("held_id")
        return Answer(200, call(lambda: media.decide_held(state, held_id, body["decision"])))

    def settings_get(request: Request) -> Answer:
        server._require(request, "settings:read")
        return Answer(200, media.settings_view(state))

    def settings_put(request: Request) -> Answer:
        server._require(request, "settings:write")
        body = server._body(request, "SettingsUpdate")
        return Answer(200, call(lambda: media.settings_put(state, body)))

    def backfill_list(request: Request) -> Answer:
        guard(request, ("backfill:write",), None)
        return Answer(200, media.backfill_list(state))

    def backfill_page(request: Request) -> Answer:
        body = guard(request, ("backfill:write",), "BackfillPageRequest")
        request_id = request.match.group("request_id")
        return Answer(200, call(lambda: media.backfill_page(state, request_id, body)))

    # -- controls (no token): changes "in Tribune Desk" for manual work --------------------

    def _json(request: Request) -> dict[str, Any]:
        body = json.loads(request.raw) if request.raw else {}
        if not isinstance(body, dict):
            raise ApiError(422, "validation_error", "the body must be a JSON object")
        return body

    def _asset(request: Request) -> str:
        asset_id = request.match.group("asset_id")
        if asset_id not in state.media.assets:
            raise ApiError(404, "not_found", "no such file in the mock")
        return asset_id

    def c_new(request: Request) -> Answer:
        body = _json(request)
        asset = media.td_new_file(
            state,
            fields=body.get("fields"),
            width=int(body.get("width", 1200)),
            height=int(body.get("height", 800)),
        )
        return Answer(200, {"asset_id": asset.asset_id})

    def c_field(request: Request) -> Answer:
        asset_id, body = _asset(request), _json(request)
        if body.get("field") not in media.FIELDS or not isinstance(body.get("value"), str):
            raise ApiError(422, "validation_error", 'the body is {"field": …, "value": "…"}')
        version = media.td_edit(state, asset_id, body["field"], body["value"])
        return Answer(200, {"version": version})

    def c_trash(request: Request) -> Answer:
        asset_id, body = _asset(request), _json(request)
        media.td_trash(state, asset_id, bool(body.get("trashed", True)))
        return Answer(200, {"trashed": state.media.assets[asset_id].trashed})

    def c_settings(request: Request) -> Answer:
        try:
            media.td_settings(state, **_json(request))
        except KeyError as exc:
            raise ApiError(422, "validation_error", f"unknown option {exc}") from None
        return Answer(200, media.settings_view(state))

    def c_import(request: Request) -> Answer:
        return Answer(200, {"paired": media.import_pending(state)})

    def c_backfill(request: Request) -> Answer:
        return Answer(
            200, {"request_id": media.td_backfill_request(state, _json(request).get("filters"))}
        )

    def c_expire(request: Request) -> Answer:
        state.expire_cursor_once = True
        return Answer(200, {"expire_next_cursor": True})

    def r(pattern: str) -> re.Pattern[str]:
        return re.compile(pattern)

    return [
        ("POST", r(r"/v3/cms/media"), new_files),
        ("POST", r(r"/v3/cms/media/fields"), fields),
        ("POST", r(r"/v3/cms/media/deletions"), deletions),
        ("POST", r(r"/v3/cms/media/push-existing"), push),
        ("POST", r(r"/v3/cms/media/(?P<asset_id>[^/]+)/link"), link),
        ("POST", r(r"/v3/cms/resync"), resync),
        ("GET", r(r"/v3/cms/held"), held),
        ("POST", r(r"/v3/cms/held/(?P<held_id>[^/]+)/decision"), decision),
        ("GET", r(r"/v3/cms/settings"), settings_get),
        ("PUT", r(r"/v3/cms/settings"), settings_put),
        ("GET", r(r"/v3/cms/backfill/requests"), backfill_list),
        ("POST", r(r"/v3/cms/backfill/requests/(?P<request_id>[^/]+)/pages"), backfill_page),
        ("POST", r(r"/_tdkit/media"), c_new),
        ("POST", r(r"/_tdkit/media/(?P<asset_id>[^/]+)/fields"), c_field),
        ("POST", r(r"/_tdkit/media/(?P<asset_id>[^/]+)/trash"), c_trash),
        ("POST", r(r"/_tdkit/settings"), c_settings),
        ("POST", r(r"/_tdkit/import"), c_import),
        ("POST", r(r"/_tdkit/backfill"), c_backfill),
        ("POST", r(r"/_tdkit/expire-cursors"), c_expire),
    ]
