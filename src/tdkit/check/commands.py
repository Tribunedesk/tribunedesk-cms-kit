"""The integration's developer commands (`--inspect-cmd`, `--publish-cmd`, `--poll-cmd`).

A template gets `{article_id}`; the result is split into arguments and run without a shell.
On Windows the split follows the Windows convention: only double quotes group, so a path
like `C:\\Users\\O'Brien\\cms\\manage.py` or `"C:\\Program Files\\Python\\python.exe"` works.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from collections.abc import Mapping

TIMEOUT_SECONDS = 60


class CommandError(Exception):
    """The command could not run, timed out or exited with a non-zero code."""


def split_command(command: str, *, windows: bool = os.name == "nt") -> list[str]:
    if not windows:
        return shlex.split(command, posix=True)
    args: list[str] = []
    current: list[str] = []
    quoted = False
    started = False
    for char in command:
        if char == '"':
            quoted = not quoted
            started = True
        elif char.isspace() and not quoted:
            if started:
                args.append("".join(current))
                current, started = [], False
        else:
            current.append(char)
            started = True
    if quoted:
        raise ValueError("no closing quotation")
    if started:
        args.append("".join(current))
    return args


def render(template: str, **values: str) -> list[str]:
    """Split `template` into arguments, then put `values` (e.g. `article_id`) into them.

    Values go in after the split, so a value never changes how the command is split.
    Other braces in the template are left alone.
    """
    try:
        args = split_command(template)
    except ValueError as exc:
        raise CommandError(f"cannot split the command {template!r}: {exc}") from exc
    for name, value in values.items():
        args = [arg.replace("{" + name + "}", value) for arg in args]
    if not args:
        raise CommandError("the command is empty")
    return args


def run_template(template: str, *, env: Mapping[str, str] | None = None, **values: str) -> str:
    """Run the command and return its stdout; `CommandError` unless it exits with 0."""
    args = render(template, **values)
    # Without a shell, Windows does not try PATHEXT (.cmd, .bat): resolve the program first.
    search = (env if env is not None else os.environ).get("PATH")
    program = shutil.which(args[0], path=search)
    if program is None:
        raise CommandError(f"{args[0]}: command not found")
    args = [program, *args[1:]]
    try:
        done = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_SECONDS,
            env=dict(env) if env is not None else None,
            check=False,
        )
    except FileNotFoundError as exc:
        raise CommandError(f"{args[0]}: command not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise CommandError(f"{' '.join(args)} did not finish in {TIMEOUT_SECONDS} s") from exc
    if done.returncode != 0:
        tail = (done.stderr or done.stdout).strip()[-500:]
        raise CommandError(f"{' '.join(args)} exited with {done.returncode}: {tail}")
    return done.stdout
