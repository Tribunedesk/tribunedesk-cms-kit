"""tdkit 1.1: tokens from a file, the integration switch, cursors with run and epoch."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tdkit.cli import build_parser, load_tokens, main, mock_state
from tdkit.errors import UsageError
from tdkit.mock.state import MockState

from .test_mock_routes import call


def _tokens(tmp_path: Path, body: object) -> Path:
    path = tmp_path / "tokens.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def test_tokens_file_loaded(tmp_path: Path) -> None:
    path = _tokens(
        tmp_path,
        {
            "tokens": [
                {"token": "a", "scopes": ["media:read"]},
                {"token": "b", "scopes": ["articles:write"]},
            ]
        },
    )
    assert load_tokens(path) == {"a": {"media:read"}, "b": {"articles:write"}}


@pytest.mark.parametrize(
    "body",
    [
        {"tokens": [{"token": "a", "scopes": ["media:fly"]}]},
        {"tokens": []},
        {"tokens": [{"token": "a", "scopes": []}, {"token": "a", "scopes": ["media:read"]}]},
        ["not", "an", "object"],
    ],
)
def test_tokens_file_errors_are_usage_errors(tmp_path: Path, body: object) -> None:
    with pytest.raises(UsageError):
        load_tokens(_tokens(tmp_path, body))


def test_tokens_file_bad_json_is_usage_error(tmp_path: Path) -> None:
    path = tmp_path / "tokens.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(UsageError):
        load_tokens(path)


def test_tokens_and_token_scopes_exclusive(tmp_path: Path) -> None:
    path = _tokens(tmp_path, {"tokens": [{"token": "a", "scopes": ["media:read"]}]})
    assert main(["mock", "--tokens", str(path), "--token-scopes", "media:read"]) == 2


def test_mock_answers_403_for_scope_from_file(state: MockState, base: str) -> None:
    state.tokens = {"b": {"articles:write"}}
    status, error, _ = call(base, "GET", "/v3/cms/status", token="b")
    assert status == 403
    assert error["code"] == "forbidden"


def test_mock_cli_disabled_flag() -> None:
    args = build_parser().parse_args(["mock", "--disabled"])
    assert mock_state(args).integration_enabled is False


def test_cursor_from_other_run_is_422_with_hint(state: MockState, base: str) -> None:
    other = MockState(read_mode=True)
    cursor = other.cursor_for(0)
    assert cursor != state.cursor_for(0)
    status, error, _ = call(base, "GET", f"/v3/cms/changes?cursor={cursor}")
    assert status == 422
    assert "--reset-cmd" in error["message"]


def test_disabled_changes_409_and_status_disabled(state: MockState, base: str) -> None:
    state.set_enabled(False)
    status, error, _ = call(base, "GET", "/v3/cms/changes")
    assert (status, error["code"]) == (409, "state_conflict")
    status, body, _ = call(base, "GET", "/v3/cms/status")
    assert (status, body["state"]) == (200, "disabled")


def test_reenable_expires_old_cursors_410(state: MockState, base: str) -> None:
    cursor = call(base, "GET", "/v3/cms/changes")[1]["next_cursor"]
    status, body, _ = call(base, "POST", "/_tdkit/integration", body={"enabled": False})
    assert (status, body["enabled"]) == (200, False)
    status, body, _ = call(base, "POST", "/_tdkit/integration", body={"enabled": True})
    assert (status, body) == (200, {"enabled": True, "epoch": 2})
    status, error, _ = call(base, "GET", f"/v3/cms/changes?cursor={cursor}")
    assert (status, error["code"]) == (410, "cursor_expired")
    status, page, _ = call(base, "GET", "/v3/cms/changes")
    assert status == 200
    assert call(base, "GET", f"/v3/cms/changes?cursor={page['next_cursor']}")[0] == 200


def test_disable_then_disable_keeps_epoch(state: MockState) -> None:
    state.set_enabled(False)
    state.set_enabled(False)
    state.set_enabled(True)
    assert state.epoch == 2
    state.set_enabled(True)
    assert state.epoch == 2
