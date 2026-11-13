"""`tdkit check --levels 4`: options, mode none, reset, and the level 4 scenarios."""

from __future__ import annotations

import pytest

from tdkit.check.commands import render
from tdkit.check.runner import validate
from tdkit.errors import UsageError

L4 = {
    "sync_cmd": "s",
    "media_inspect_cmd": "i {cms_media_id}",
    "media_add_cmd": "a {file}",
    "media_edit_cmd": "e {cms_media_id} {field} {value}",
    "media_delete_cmd": "d {cms_media_id}",
}


def check(levels: list[int], mode: str, **extra: object) -> None:
    validate(
        levels,
        mode,
        webhook=extra.get("webhook"),  # type: ignore[arg-type]
        inspect_cmd=extra.get("inspect_cmd"),  # type: ignore[arg-type]
        publish_cmd=None,
        poll_cmd=None,
        level4=extra.get("level4"),  # type: ignore[arg-type]
    )


def test_level4_requires_its_commands() -> None:
    with pytest.raises(UsageError) as err:
        check([4], "none", level4={"sync_cmd": "s"})
    message = str(err.value)
    for flag in ("--media-inspect-cmd", "--media-add-cmd", "--media-edit-cmd"):
        assert flag in message
    assert "--sync-cmd" not in message
    check([4], "none", level4=L4)


def test_mode_none_only_for_level4_alone() -> None:
    with pytest.raises(UsageError):
        check([1, 4], "none", inspect_cmd="x", level4=L4)


def test_levels_1_4_accept_webhook_mode() -> None:
    check([1, 4], "webhook", webhook="http://127.0.0.1:1/", inspect_cmd="x", level4=L4)


def test_render_keeps_value_with_spaces_quotes_polish() -> None:
    # Values go in after the split, so a value is one argument on Windows and POSIX alike.
    value = 'Zażółć "x" y'
    args = render("e {cms_media_id} {field} {value}", cms_media_id="m 1", field="alt", value=value)
    assert args == ["e", "m 1", "alt", value]
