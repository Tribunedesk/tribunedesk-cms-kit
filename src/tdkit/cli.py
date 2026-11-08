"""Command line: `tdkit mock` and `tdkit check`."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from tdkit import __version__
from tdkit.errors import UsageError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tdkit", description="Local mock of Tribune Desk and conformance checks."
    )
    parser.add_argument("--version", action="version", version=f"tdkit {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("mock", help="run a local mock of the Tribune Desk CMS API")
    sub.add_parser("check", help="run the conformance scenarios against your integration")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except UsageError as exc:
        print(f"tdkit: {exc}", file=sys.stderr)
        return 2


def _run(args: argparse.Namespace) -> int:
    raise UsageError(f"{args.command} is not available yet")


if __name__ == "__main__":
    sys.exit(main())
