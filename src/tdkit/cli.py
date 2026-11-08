"""Command line: `tdkit mock` and `tdkit check`."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from tdkit import __version__
from tdkit.docs import resolve_docs
from tdkit.errors import UsageError
from tdkit.mock.state import ALL_SCOPES, DEFAULT_TOKEN, MockState


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tdkit", description="Local mock of Tribune Desk and conformance checks."
    )
    parser.add_argument("--version", action="version", version=f"tdkit {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    mock = sub.add_parser("mock", help="run a local mock of the Tribune Desk CMS API")
    mock.add_argument("--port", type=int, default=8787, help="port on 127.0.0.1 (default 8787)")
    _docs_options(mock)
    mock.add_argument(
        "--read-mode", action="store_true", help="the organization is in read mode (level 1)"
    )
    mock.add_argument(
        "--token-scopes",
        help=f"comma-separated scopes of the token {DEFAULT_TOKEN} (default: all of them)",
    )
    mock.add_argument("--webhook", help="where POST /_tdkit/send delivers articles (webhook mode)")

    sub.add_parser("check", help="run the conformance scenarios against your integration")
    return parser


def _docs_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--docs", type=Path, help="local copy of tribunedesk-cms-api (else TRIBUNEDESK_DOCS_DIR)"
    )
    parser.add_argument(
        "--contract", help="contract tag, e.g. v3.4.1-draft (default: the newest tag)"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "mock":
            return run_mock(args)
        raise UsageError(f"{args.command} is not available yet")
    except UsageError as exc:
        print(f"tdkit: {exc}", file=sys.stderr)
        return 2


def mock_state(args: argparse.Namespace) -> MockState:
    state = MockState(read_mode=args.read_mode)
    if args.token_scopes:
        scopes = {s.strip() for s in args.token_scopes.split(",") if s.strip()}
        unknown = sorted(scopes - set(ALL_SCOPES))
        if unknown:
            raise UsageError(f"unknown scope {', '.join(unknown)}; known: {', '.join(ALL_SCOPES)}")
        state.tokens = {DEFAULT_TOKEN: scopes}
    return state


def run_mock(args: argparse.Namespace) -> int:
    from tdkit.mock.server import MockServer
    from tdkit.signing import MOCK_SECRET

    state = mock_state(args)
    docs = resolve_docs(args.contract, args.docs)
    server = MockServer(state, docs, args.port, webhook=args.webhook)
    try:
        host, port = server.start()
    except OSError as exc:
        raise UsageError(f"cannot listen on 127.0.0.1:{args.port}: {exc}") from exc
    base = f"http://{host}:{port}"
    scopes = ",".join(sorted(state.tokens[DEFAULT_TOKEN]))
    print(f"tdkit {__version__} mock of Tribune Desk, contract {docs.version}")
    print(f"  API:            {base}/v3/cms/  (mode: {'read' if state.read_mode else 'webhook'})")
    print(f"  token:          {DEFAULT_TOKEN}  (scopes: {scopes})")
    print(f"  signing secret: {MOCK_SECRET}  (a public test value)")
    print(f"  make a send:    POST {base}/_tdkit/send  (optional JSON body overrides fields)")
    print(f"  your CMS:       TD_API_BASE={base} TD_CMS_TOKEN={DEFAULT_TOKEN}")
    print("Ctrl+C stops it.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
