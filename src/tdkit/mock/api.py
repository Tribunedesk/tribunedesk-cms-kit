"""What a route of the mock receives and returns, shared by `server.py` and `media_routes.py`."""

from __future__ import annotations

import re
from typing import Any


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class Answer:
    def __init__(self, status: int, body: Any, headers: dict[str, str] | None = None) -> None:
        self.status, self.body, self.headers = status, body, headers or {}


class Request:
    def __init__(
        self,
        method: str,
        path: str,
        query: dict[str, list[str]],
        raw: bytes,
        token: str | None,
        match: re.Match[str],
    ) -> None:
        self.method, self.path, self.query, self.raw = method, path, query, raw
        self.token, self.match = token, match
