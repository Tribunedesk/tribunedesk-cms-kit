"""Standard Webhooks signatures, as guide 1 "Verifying the signature" describes them."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
from collections.abc import Mapping

SECRET_PREFIX = "whsec_"
# The mock's signing secret: a public test value, never a real one.
MOCK_SECRET = SECRET_PREFIX + base64.b64encode(b"tdkit-mock-signing-secret-000000").decode()


def signing_key(secret: str) -> bytes:
    """The HMAC key of a `whsec_` secret; `ValueError` when it is not one."""
    if not secret.startswith(SECRET_PREFIX):
        raise ValueError("a signing secret starts with whsec_")
    try:
        return base64.b64decode(secret.removeprefix(SECRET_PREFIX), validate=True)
    except binascii.Error as exc:
        raise ValueError("a signing secret is base64 after whsec_") from exc


def _signature(secret: str, msg_id: str, timestamp: int | str, body: bytes) -> str:
    signed = f"{msg_id}.{timestamp}.".encode() + body
    return base64.b64encode(hmac.new(signing_key(secret), signed, hashlib.sha256).digest()).decode()


def sign(secrets: list[str], msg_id: str, timestamp: int, body: bytes) -> str:
    """The `webhook-signature` header: one `v1,<base64>` per secret, separated by spaces."""
    return " ".join(f"v1,{_signature(s, msg_id, timestamp, body)}" for s in secrets)


def verify(
    secret: str, headers: Mapping[str, str], body: bytes, now: int, tolerance: int = 300
) -> bool:
    """True when `body` carries a valid signature by `secret` within `tolerance` seconds."""
    lower = {key.lower(): value for key, value in headers.items()}
    msg_id = lower.get("webhook-id")
    timestamp = lower.get("webhook-timestamp")
    signatures = lower.get("webhook-signature")
    if not msg_id or not timestamp or not signatures:
        return False
    if not (timestamp.isascii() and timestamp.isdigit()):
        return False
    if abs(now - int(timestamp)) > tolerance:
        return False
    expected = _signature(secret, msg_id, timestamp, body).encode()
    for entry in signatures.split(" "):
        version, _, value = entry.partition(",")
        if version == "v1" and hmac.compare_digest(value.encode(), expected):
            return True
    return False
