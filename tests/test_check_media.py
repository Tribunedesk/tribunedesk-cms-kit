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


# -- the scenarios, run on the reference media integration ---------------------------------

import json  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

from tdkit.check.context import CheckOptions  # noqa: E402
from tdkit.check.runner import Report, run_check  # noqa: E402
from tdkit.check.scenarios_media import G4, MEDIA_SCENARIOS  # noqa: E402
from tdkit.docs import ContractDocs  # noqa: E402

from .conftest import FIXTURE  # noqa: E402
from .test_check import free_port  # noqa: E402

REFERENCE = Path(__file__).parent / "reference_media.py"
CORE = [s.id for s in MEDIA_SCENARIOS if not s.needs_backfill]

# Each flag of the reference breaks one rule; the first scenario that must catch it.
BREAKS = {
    "--no-cursor": "l4-first-poll",
    "--keep-first-cursor": "l4-first-poll",
    "--one-page": "l4-new-asset-linked",
    "--cursor-before-apply": "l4-cursor-after-apply",
    "--ignore-versions": "l4-field-versions",
    "--duplicate-new-files": "l4-cms-new-file",
    "--no-base-version": "l4-cms-field-edit",
    "--skip-deletions": "l4-cms-deletion",
    "--resend-conflict": "l4-conflict-winning-value",
    "--apply-over-dirty": "l4-both-sides-edited",
    "--resend-held": "l4-held-not-resent",
    "--auto-decide-held": "l4-held-not-resent",
    "--cache-settings": "l4-settings-and-unknown-kinds",
    "--crash-on-unknown-kind": "l4-settings-and-unknown-kinds",
    "--keep-trash-mark": "l4-td-trash-mark",
    "--no-backfill-last": "l4-backfill-answered",
    "--fresh-after-410": "l4-cursor-expired-resync",
    "--auto-confirm-resync": "l4-cursor-expired-resync",
}


def media_command(sub: str, store: Path, flags: tuple[str, ...]) -> str:
    joined = " ".join(flags)
    return f'"{sys.executable}" "{REFERENCE}" {joined} --backfill --store "{store}" {sub}'


def media_options(
    docs: ContractDocs, store: Path, *flags: str, reset: bool = True, backfill: bool = True
) -> CheckOptions:
    return CheckOptions(
        docs=docs,
        port=free_port(),
        sync_cmd=media_command("sync", store, flags),
        media_inspect_cmd=media_command("inspect {cms_media_id}", store, flags),
        media_add_cmd=media_command("add {file}", store, flags),
        media_edit_cmd=media_command("edit {cms_media_id} {field} {value}", store, flags),
        media_delete_cmd=media_command("delete {cms_media_id}", store, flags),
        reset_cmd=media_command("reset", store, flags) if reset else None,
        backfill=backfill,
    )


def failed(report: Report) -> set[str]:
    return {r.id for r in report.results if r.passed is False}


def test_reference_media_passes_level4(tmp_path: Path, docs: ContractDocs) -> None:
    report = run_check([4], "none", media_options(docs, tmp_path / "store.json"))
    details = {r.id: r.detail for r in report.results if not r.passed}
    assert not details, details
    assert [r.id for r in report.results] == [s.id for s in MEDIA_SCENARIOS]


def test_rerun_without_reset_fails_first_poll_with_hint(tmp_path: Path, docs: ContractDocs) -> None:
    store = tmp_path / "store.json"
    run_check([4], "none", media_options(docs, store, backfill=False))
    # The last scenario leaves a resync waiting for a person; a person confirmed it.
    data = json.loads(store.read_text(encoding="utf-8"))
    data["needs_resync"] = False
    store.write_text(json.dumps(data), encoding="utf-8")
    report = run_check([4], "none", media_options(docs, store, reset=False, backfill=False))
    first = report.results[0]
    assert first.id == "l4-first-poll"
    assert first.passed is False
    assert "--reset-cmd" in first.detail


def test_backfill_skipped_without_flag(tmp_path: Path, docs: ContractDocs) -> None:
    report = run_check([4], "none", media_options(docs, tmp_path / "s.json", backfill=False))
    skipped = {r.id: r.detail for r in report.results if r.passed is None}
    assert list(skipped) == ["l4-backfill-answered"]
    assert "--backfill" in skipped["l4-backfill-answered"]


@pytest.mark.parametrize(("flag", "scenario"), sorted(BREAKS.items()))
def test_each_break_flag_fails_its_scenario(
    tmp_path: Path, docs: ContractDocs, flag: str, scenario: str
) -> None:
    options = media_options(docs, tmp_path / "store.json", flag)
    report = run_check([4], "none", options, stop_after=scenario)
    ids = [r.id for r in report.results]
    bad = failed(report)
    assert scenario in bad, {r.id: r.detail for r in report.results}
    # Everything before the scenario that must catch the flag still passes.
    assert not bad & set(ids[: ids.index(scenario)]), bad


def test_media_done_when_quotes_are_literal() -> None:
    text = (FIXTURE / G4).read_text(encoding="utf-8")
    for scenario in MEDIA_SCENARIOS:
        assert scenario.done_when in text, scenario.id
        assert scenario.guide.startswith(G4)


def test_failing_reset_fails_level4_with_a_report(tmp_path: Path, docs: ContractDocs) -> None:
    options = media_options(docs, tmp_path / "store.json")
    broken = CheckOptions(**{**options.__dict__, "reset_cmd": f'"{sys.executable}" -c "exit(3)"'})
    report = run_check([4], "none", broken)
    assert all(r.passed is False for r in report.results)
    assert report.results[0].detail.startswith("not run: --reset-cmd failed")
