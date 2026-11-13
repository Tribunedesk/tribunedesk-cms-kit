from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from tdkit.docs import ContractDocs, load_docs
from tdkit.mock.server import MockServer
from tdkit.mock.state import MockState

FIXTURE = Path(__file__).parent / "fixtures" / "cms-api"
CI_YML = Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"
PIN_FILE = Path(__file__).parent.parent / "ci" / "contract-tag"


def ci_contract_tag() -> str:
    """The contract tag CI tests against: `ci/contract-tag`, read by every job of `ci.yml`.

    Not a line of `ci.yml`: the drift job pushes with GITHUB_TOKEN, which may not change files
    under `.github/workflows/`."""
    return PIN_FILE.read_text(encoding="utf-8").strip()


@pytest.fixture(scope="session")
def docs() -> ContractDocs:
    return load_docs(FIXTURE)


@contextmanager
def serve(handler: type[BaseHTTPRequestHandler]) -> Iterator[str]:
    """Run `handler` on a free loopback port; yield its base URL."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def state() -> MockState:
    return MockState(read_mode=True)


@pytest.fixture
def base(state: MockState, docs: ContractDocs) -> Iterator[str]:
    server = MockServer(state, docs)
    host, port = server.start()
    try:
        yield f"http://{host}:{port}"
    finally:
        server.stop()
