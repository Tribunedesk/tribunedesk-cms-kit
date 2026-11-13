"""Test TLS certificates of the mock: public values for the loopback interface only.

The mock serves files over https with `server.pem`, signed by the test CA in `ca.pem`. An
integration under test trusts that CA through `TD_CA_BUNDLE`, never in production. Made by
`ci/make_test_tls.sh`; the CA key is not kept anywhere.
"""

from __future__ import annotations

import ssl
from pathlib import Path

_DIR = Path(__file__).parent
CA_BUNDLE = _DIR / "ca.pem"


def server_context() -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(_DIR / "server.pem", _DIR / "server-key.pem")
    return context
