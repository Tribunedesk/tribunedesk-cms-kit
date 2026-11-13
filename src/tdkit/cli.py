"""Command line: `tdkit mock` and `tdkit check`."""

from __future__ import annotations

import argparse
import io
import json
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
    mock.add_argument(
        "--tokens", type=Path, help='JSON file {"tokens": [{"token": "…", "scopes": […]}]}'
    )
    mock.add_argument(
        "--retry-scale",
        type=float,
        default=1.0,
        help="seconds per minute of the guide's retry schedule (default 1; 0: no retries)",
    )
    mock.add_argument(
        "--media-hosts",
        help="extra hosts accepted in file_url of POST /media and /link (127.0.0.1, localhost)",
    )
    mock.add_argument(
        "--disabled",
        action="store_true",
        help="start with the integration disabled (POST /_tdkit/integration enables it)",
    )

    check = sub.add_parser("check", help="run the conformance scenarios against your integration")
    check.add_argument("--levels", default="1", help="comma-separated levels, e.g. 1,2,3")
    check.add_argument("--mode", default="webhook", choices=("webhook", "read"))
    check.add_argument("--webhook", help="your webhook address (webhook mode)")
    check.add_argument(
        "--secret", help="the signing secret your webhook verifies (default: the mock's)"
    )
    check.add_argument(
        "--inspect-cmd",
        required=True,
        help="prints the post made from {article_id} as JSON, or null",
    )
    check.add_argument("--publish-cmd", help="publishes the post of {article_id} (levels 2, 3)")
    check.add_argument("--poll-cmd", help="runs one poll of the read mode client")
    check.add_argument(
        "--social-flag", action="store_true", help="the CMS has a “keep off Facebook” setting"
    )
    check.add_argument(
        "--port", type=int, default=8787, help="port of the mock on 127.0.0.1 (default 8787)"
    )
    check.add_argument("--json", type=Path, help="also write the report as JSON to this file")
    _docs_options(check)

    docs = sub.add_parser("docs", help="put the contract documentation into this project")
    _docs_options(docs)
    docs.add_argument(
        "--dest", type=Path, help="where to put it (default: .tribunedesk/cms-api@<tag>)"
    )

    integ = sub.add_parser(
        "integrators", help="what integrators must do between two contract versions"
    )
    integ.add_argument("--from", dest="from_version", required=True, help="e.g. 3.3.0-draft")
    integ.add_argument("--to", dest="to_version", required=True, help="e.g. 3.4.1-draft")
    integ.add_argument("--levels", default="1,2,3,4", help="levels the integration built")
    integ.add_argument("--mode", default="webhook", choices=("webhook", "read", "none"))
    _docs_options(integ)

    manifest = sub.add_parser("manifest", help="validate or write tribunedesk.json")
    msub = manifest.add_subparsers(dest="manifest_command", required=True)
    validate = msub.add_parser("validate", help="check tribunedesk.json")
    validate.add_argument("path", nargs="?", type=Path, default=Path("tribunedesk.json"))
    write = msub.add_parser("write", help="write tribunedesk.json")
    write.add_argument("--contract", required=True)
    write.add_argument("--levels", required=True, help="e.g. 1,2")
    write.add_argument("--delivery", required=True, choices=("webhook", "read", "none"))
    write.add_argument("--cms", required=True, help="e.g. django, drupal, laravel")
    write.add_argument("--protocol", help="version of tribunedesk/cms-protocol, for PHP")
    write.add_argument(
        "--conformance", type=Path, help="a tdkit check --json report of this integration"
    )
    write.add_argument("--path", type=Path, default=Path("tribunedesk.json"))
    return parser


def _docs_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--docs",
        type=Path,
        help="local copy of tribunedesk-cms-api (else TRIBUNEDESK_DOCS_DIR)",
    )
    parser.add_argument(
        "--contract", help="contract tag, e.g. v3.4.1-draft (default: the newest tag)"
    )


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        # The report quotes the guide (curly quotes); a legacy console must not crash on it.
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "mock":
            return run_mock(args)
        if args.command == "docs":
            return run_docs(args)
        if args.command == "integrators":
            return run_integrators(args)
        if args.command == "manifest":
            return run_manifest(args)
        return run_checks(args)
    except UsageError as exc:
        print(f"tdkit: {exc}", file=sys.stderr)
        return 2


def load_tokens(path: Path) -> dict[str, set[str]]:
    """Tokens and their scopes from `{"tokens": [{"token": "…", "scopes": ["…"]}]}`."""
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UsageError(f"cannot read {path}: {exc}") from None
    except ValueError as exc:
        raise UsageError(f"{path} is not JSON: {exc}") from None
    items = body.get("tokens") if isinstance(body, dict) else None
    if not isinstance(items, list) or not items:
        raise UsageError(f'{path}: expected {{"tokens": [{{"token": …, "scopes": […]}}]}}')
    tokens: dict[str, set[str]] = {}
    for item in items:
        token = item.get("token") if isinstance(item, dict) else None
        scopes = item.get("scopes") if isinstance(item, dict) else None
        if not isinstance(token, str) or not token or not isinstance(scopes, list):
            raise UsageError(f"{path}: every item needs a token (text) and scopes (a list)")
        if token in tokens:
            raise UsageError(f"{path}: the token {token!r} is listed twice")
        unknown = sorted(set(map(str, scopes)) - set(ALL_SCOPES))
        if unknown:
            raise UsageError(f"{path}: unknown scope {', '.join(unknown)}")
        tokens[token] = set(map(str, scopes))
    return tokens


def mock_state(args: argparse.Namespace) -> MockState:
    state = MockState(read_mode=args.read_mode, integration_enabled=not args.disabled)
    if args.tokens and args.token_scopes:
        raise UsageError("--tokens and --token-scopes exclude each other")
    if args.tokens:
        state.tokens = load_tokens(args.tokens)
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
    server = MockServer(
        state,
        docs,
        args.port,
        webhook=args.webhook,
        retry_scale=args.retry_scale,
        media_hosts=split_list(args.media_hosts),
    )
    try:
        host, port = server.start()
    except OSError as exc:
        raise UsageError(f"cannot listen on 127.0.0.1:{args.port}: {exc}") from exc
    base = f"http://{host}:{port}"
    print(f"tdkit {__version__} mock of Tribune Desk, contract {docs.version}")
    print(f"  API:            {base}/v3/cms/  (mode: {'read' if state.read_mode else 'webhook'})")
    for token, scopes in state.tokens.items():
        print(f"  token:          {token}  (scopes: {','.join(sorted(scopes))})")
    enabled = "enabled" if state.integration_enabled else "disabled"
    print(f'  integration:    {enabled}  (POST {base}/_tdkit/integration {{"enabled": …}})')
    print(f"  signing secret: {MOCK_SECRET}  (a public test value)")
    print(f"  make a send:    POST {base}/_tdkit/send  (optional JSON body overrides fields)")
    print(f"  level 4:        POST {base}/_tdkit/media  {{fields?, width?, height?}} → asset_id")
    print(f"                  POST {base}/_tdkit/media/<asset_id>/fields  {{field, value}}")
    print(f"                  POST {base}/_tdkit/media/<asset_id>/trash  {{trashed}}")
    print(f"                  POST {base}/_tdkit/settings  {{option: value, …}}")
    print(f"                  POST {base}/_tdkit/import  (pairs files accepted by POST /media)")
    print(f"                  POST {base}/_tdkit/backfill  {{filters?}} → request_id")
    print(f"                  POST {base}/_tdkit/expire-cursors  (the next cursor answers 410)")
    first = next(iter(state.tokens))
    print(f"  your CMS:       TD_API_BASE={base} TD_CMS_TOKEN={first}")
    print("Ctrl+C stops it.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return 0


def split_list(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def parse_levels(value: str) -> list[int]:
    try:
        return sorted({int(part) for part in value.split(",") if part.strip()})
    except ValueError:
        raise UsageError(f"--levels takes numbers like 1,2,3, not {value!r}") from None


def run_checks(args: argparse.Namespace) -> int:
    from tdkit.check.context import CheckOptions
    from tdkit.check.runner import render_text, run_check, validate, write_json

    levels = parse_levels(args.levels)
    validate(
        levels,
        args.mode,
        webhook=args.webhook,
        inspect_cmd=args.inspect_cmd,
        publish_cmd=args.publish_cmd,
        poll_cmd=args.poll_cmd,
        secret=args.secret,
    )
    opts = CheckOptions(
        docs=resolve_docs(args.contract, args.docs),
        inspect_cmd=args.inspect_cmd,
        webhook=args.webhook,
        secret=args.secret,
        publish_cmd=args.publish_cmd,
        poll_cmd=args.poll_cmd,
        social_flag=args.social_flag,
        port=args.port,
    )
    report = run_check(levels, args.mode, opts)
    print(render_text(report, opts), flush=True)
    if args.json:
        write_json(report, args.json)
    return 1 if report.failed else 0


def run_docs(args: argparse.Namespace) -> int:
    from tdkit.project import fetch_docs

    result = fetch_docs(Path.cwd(), tag=args.contract, dest=args.dest, source=args.docs)
    print(json.dumps(result))
    return 0


def run_integrators(args: argparse.Namespace) -> int:
    from tdkit.integrators import integrators

    docs = resolve_docs(args.contract or f"v{args.to_version.removeprefix('v')}", args.docs)
    changelog = (docs.root / "CHANGELOG.md").read_text(encoding="utf-8")
    try:
        items = integrators(
            changelog,
            args.from_version,
            args.to_version,
            levels=parse_levels(args.levels),
            mode=args.mode,
        )
    except ValueError as exc:
        raise UsageError(str(exc)) from None
    print(json.dumps(items, ensure_ascii=False, indent=2))
    return 0


def run_manifest(args: argparse.Namespace) -> int:
    from tdkit.project import build_manifest, read_json, validate_manifest

    if args.manifest_command == "validate":
        errors = validate_manifest(read_json(args.path))
        if errors:
            raise UsageError(f"{args.path}: " + "; ".join(errors))
        print(f"{args.path}: valid")
        return 0
    report = read_json(args.conformance) if args.conformance else None
    manifest = build_manifest(
        contract=args.contract.removeprefix("v"),
        levels=parse_levels(args.levels),
        delivery=args.delivery,
        cms=args.cms,
        kit=__version__,
        protocol=args.protocol,
        report=report,
    )
    args.path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
