"""`POST /v3/cms/taxonomy/terms` of the mock: the CMS sends its categories and tags (level 3).

Checks in the contract's order: the token (401), `articles:write` (403), the body against the
tag's `TaxonomyPageRequest` and the rules its description states (422), a full run left open
for 24 hours (409). It does not need the media library to be enabled. The state lives in
`MockState.taxonomy`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from tdkit.mock.api import Answer, ApiError, Request
from tdkit.mock.state import TaxonomyConflict

if TYPE_CHECKING:
    from tdkit.mock.server import MockServer

Route = tuple[str, re.Pattern[str], Callable[[Request], Answer]]

SCHEMAS = ("TaxonomyPageRequest",)


def routes(server: MockServer) -> list[Route]:
    state = server.state

    def terms(request: Request) -> Answer:
        server._require(request, "articles:write")
        body = server._body(request, "TaxonomyPageRequest")
        with state.lock:
            try:
                results = state.taxonomy.apply_page(body)
            except ValueError as exc:
                raise ApiError(422, "validation_error", str(exc)) from None
            except TaxonomyConflict as exc:
                raise ApiError(409, "state_conflict", str(exc)) from None
        return Answer(200, {"results": results, "held_batch_id": None})

    def r(pattern: str) -> re.Pattern[str]:
        return re.compile(pattern)

    return [("POST", r(r"/v3/cms/taxonomy/terms"), terms)]
