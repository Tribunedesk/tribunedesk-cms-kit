"""Signed `article.delivered` requests, sent the way Tribune Desk sends them (guide 1)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from tdkit.signing import sign

USER_AGENT = "ArticleWriter/2"


@dataclass(frozen=True)
class DeliveryResult:
    status: int | None
    body: bytes
    json: dict[str, Any] | None
    error: str | None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Tribune Desk does not follow redirects: a 3xx ends the send."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


# No proxy: deliveries go straight to the integration, never through HTTP(S)_PROXY.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)


def deliver(
    url: str,
    body: bytes,
    *,
    secrets: list[str],
    delivery_id: str,
    attempt: int,
    timestamp: int | None = None,
    timeout: float = 30.0,
) -> DeliveryResult:
    """POST one signed attempt of a send and return what the receiver answered."""
    ts = int(time.time()) if timestamp is None else timestamp
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "webhook-id": delivery_id,
            "webhook-timestamp": str(ts),
            "webhook-signature": sign(secrets, delivery_id, ts, body),
            "X-Delivery-Id": delivery_id,
            "X-Delivery-Attempt": str(attempt),
        },
    )
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            return _result(response.status, response.read())
    except urllib.error.HTTPError as exc:
        return _result(exc.code, exc.read())
    except (urllib.error.URLError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return DeliveryResult(status=None, body=b"", json=None, error=str(reason))


def _result(status: int, raw: bytes) -> DeliveryResult:
    try:
        parsed = json.loads(raw) if raw else None
    except ValueError:
        parsed = None
    return DeliveryResult(
        status=status,
        body=raw,
        json=parsed if isinstance(parsed, dict) else None,
        error=None,
    )
