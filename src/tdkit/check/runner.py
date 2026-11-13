"""`tdkit check`: run the scenarios of the chosen levels and mode, report each point."""

from __future__ import annotations

import json
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tdkit import __version__
from tdkit.check.context import CheckOptions, Context, Fail
from tdkit.check.scenarios import SCENARIOS, Scenario
from tdkit.check.scenarios_media import MEDIA_SCENARIOS
from tdkit.errors import UsageError
from tdkit.mock.server import MockServer
from tdkit.mock.state import MockState
from tdkit.signing import signing_key

COVERED_LEVELS = (1, 2, 3, 4)
MODES = ("webhook", "read", "none")
LEVEL4_OPTIONS = {
    "sync_cmd": "--sync-cmd",
    "media_inspect_cmd": "--media-inspect-cmd",
    "media_add_cmd": "--media-add-cmd",
    "media_edit_cmd": "--media-edit-cmd",
    "media_delete_cmd": "--media-delete-cmd",
}


@dataclass(frozen=True)
class Result:
    id: str
    level: int
    done_when: str
    guide: str
    passed: bool | None  # None: skipped (another mode, or a CMS without the setting)
    detail: str


@dataclass(frozen=True)
class Report:
    tdkit: str
    contract: str
    levels: list[int]
    mode: str
    results: list[Result]

    @property
    def failed(self) -> list[Result]:
        return [r for r in self.results if r.passed is False]

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def kit_minor() -> str:
    return ".".join(__version__.split(".")[:2])


def validate(
    levels: list[int],
    mode: str,
    *,
    webhook: str | None,
    inspect_cmd: str | None,
    publish_cmd: str | None,
    poll_cmd: str | None,
    secret: str | None = None,
    level4: dict[str, str | None] | None = None,
) -> None:
    """Usage errors (exit code 2), checked before anything runs."""
    if secret is not None:
        try:
            signing_key(secret)
        except ValueError:
            raise UsageError(
                "--secret must be a signing secret: whsec_ followed by base64 (not shown)"
            ) from None
    if not levels:
        raise UsageError("--levels names no level")
    for level in levels:
        if level not in COVERED_LEVELS:
            raise UsageError(f"level {level} does not exist; levels are 1 to 4")
    if mode not in MODES:
        raise UsageError(f"--mode is webhook, read or none, not {mode}")
    articles = [level for level in levels if level != 4]
    if mode == "none" and articles:
        raise UsageError("--mode none is for level 4 alone; levels 1-3 need webhook or read")
    if 4 in levels:
        given = level4 or {}
        missing = [flag for key, flag in LEVEL4_OPTIONS.items() if not given.get(key)]
        if missing:
            raise UsageError(f"level 4 needs {', '.join(missing)}")
    if not articles:
        return
    if mode == "webhook" and not webhook:
        raise UsageError("webhook mode needs --webhook URL")
    if mode == "read" and not poll_cmd:
        raise UsageError("read mode needs --poll-cmd")
    if not inspect_cmd:
        raise UsageError("levels 1-3 need --inspect-cmd")
    if any(level in (2, 3) for level in levels) and not publish_cmd:
        raise UsageError("levels 2 and 3 need --publish-cmd")


def level4_of(opts: CheckOptions) -> dict[str, str | None]:
    return {key: getattr(opts, key) for key in LEVEL4_OPTIONS}


def selected(levels: list[int]) -> list[Scenario]:
    return [s for s in (*SCENARIOS, *MEDIA_SCENARIOS) if s.level in levels]


def run_check(
    levels: list[int], mode: str, opts: CheckOptions, *, stop_after: str | None = None
) -> Report:
    """Run the scenarios; `stop_after` (kit tests only) ends after that scenario id."""
    validate(
        levels,
        mode,
        webhook=opts.webhook,
        inspect_cmd=opts.inspect_cmd,
        publish_cmd=opts.publish_cmd,
        poll_cmd=opts.poll_cmd,
        secret=opts.secret,
        level4=level4_of(opts),
    )
    state = MockState(read_mode=mode == "read")
    server = MockServer(
        state, opts.docs, opts.port, retry_scale=0, media_hosts=list(opts.media_hosts)
    )
    try:
        _, port = server.start()
    except OSError as exc:
        raise UsageError(f"cannot run the mock on 127.0.0.1:{opts.port}: {exc}") from exc
    try:
        ctx = Context(opts, mode, state, port)
        results = []
        reset = False
        broken: str | None = None
        for scenario in selected(levels):
            if scenario.level == 4 and not reset:
                reset = True
                try:
                    ctx.reset()
                except Fail as exc:
                    broken = str(exc)
            if scenario.level == 4 and broken is not None:
                results.append(
                    Result(
                        scenario.id,
                        4,
                        scenario.done_when,
                        scenario.guide,
                        False,
                        f"not run: {broken}",
                    )
                )
            else:
                results.append(_run_one(scenario, ctx, opts))
            if scenario.id == stop_after:
                break
    finally:
        server.stop()
    return Report(__version__, opts.docs.version, sorted(levels), mode, results)


def _run_one(scenario: Scenario, ctx: Context, opts: CheckOptions) -> Result:
    def result(passed: bool | None, detail: str) -> Result:
        return Result(
            scenario.id, scenario.level, scenario.done_when, scenario.guide, passed, detail
        )

    if scenario.mode not in ("any", ctx.mode):
        return result(None, f"skipped: needs {scenario.mode} mode")
    if scenario.needs_social_flag and not opts.social_flag:
        return result(None, "skipped: the CMS has no 'keep off Facebook' setting (--social-flag)")
    if scenario.needs_backfill and not opts.backfill:
        return result(None, "skipped: the integration does not answer import requests (--backfill)")
    try:
        return result(True, scenario.run(ctx))
    except Fail as exc:
        return result(False, str(exc))
    except Exception as exc:  # a tdkit bug must not hide the other scenarios
        where = traceback.format_exception_only(exc)[-1].strip()
        return result(False, f"tdkit error, please report it: {where}")


def render_text(report: Report, opts: CheckOptions) -> str:
    secret = "your own (set; not shown)" if opts.secret else "the tdkit mock secret"
    lines = [
        f"tdkit {report.tdkit} check: contract {report.contract}, "
        f"levels {','.join(map(str, report.levels))}, mode {report.mode}",
        f"signing secret: {secret}",
        "",
    ]
    for r in report.results:
        mark = {True: "PASS", False: "FAIL", None: "SKIP"}[r.passed]
        lines.append(f"{mark}  {r.id}: {r.detail}")
        if r.passed is False:
            lines.append(f"      Done when: {r.done_when}")
            lines.append(f"      Guide: {r.guide}")
    passed = sum(1 for r in report.results if r.passed)
    skipped = sum(1 for r in report.results if r.passed is None)
    lines += [
        "",
        f"{len(report.results)} scenarios: {passed} passed, {len(report.failed)} failed, "
        f"{skipped} skipped",
    ]
    if report.mode == "webhook":
        lines.append(
            "Note: tdkit cannot see your server's clock. A receiver more than 5 minutes off "
            "answers 401 to real deliveries and loses articles: keep the clock in sync."
        )
    return "\n".join(lines)


def write_json(report: Report, path: Path) -> None:
    path.write_text(
        json.dumps(report.to_json(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
