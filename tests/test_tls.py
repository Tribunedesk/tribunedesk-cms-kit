"""The mock's test TLS certificates (spec 2026-11-13 kontrakt najpierw, D5)."""

from __future__ import annotations

import socket
import ssl
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tdkit.mock import tls

TLS_DIR = Path(tls.__file__).parent


def _not_after(path: Path) -> datetime:
    decoded = ssl._ssl._test_decode_cert(str(path))  # type: ignore[attr-defined]
    return datetime.strptime(decoded["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=UTC)


def _handshake(server_name: str) -> str:
    server_ctx = tls.server_context()
    listener = socket.create_server(("127.0.0.1", 0))
    port = listener.getsockname()[1]

    def serve() -> None:
        conn, _ = listener.accept()
        with server_ctx.wrap_socket(conn, server_side=True) as tls_conn:
            tls_conn.sendall(b"ok")

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    client = ssl.create_default_context(cafile=str(tls.CA_BUNDLE))
    client.verify_flags |= ssl.VERIFY_X509_STRICT
    with (
        socket.create_connection(("127.0.0.1", port), timeout=5) as raw,
        client.wrap_socket(raw, server_hostname=server_name) as conn,
    ):
        data = conn.recv(2).decode()
    thread.join(5)
    listener.close()
    return data


def test_tls_chain_verifies_strict() -> None:
    assert _handshake("127.0.0.1") == "ok"
    assert _handshake("localhost") == "ok"


def test_tls_cert_valid_for_another_year() -> None:
    soon = datetime.now(UTC) + timedelta(days=365)
    for name in ("ca.pem", "server.pem"):
        assert _not_after(TLS_DIR / name) > soon, f"{name}: run ci/make_test_tls.sh again"


def test_ca_key_is_not_in_the_repo() -> None:
    names = [p.name for p in TLS_DIR.iterdir()]
    assert not [n for n in names if "ca" in n and "key" in n]
    assert sorted(n for n in names if n.endswith(".pem")) == [
        "ca.pem",
        "server-key.pem",
        "server.pem",
    ]


def test_ca_bundle_is_the_ca() -> None:
    assert tls.CA_BUNDLE == TLS_DIR / "ca.pem"
    assert tls.CA_BUNDLE.is_file()
