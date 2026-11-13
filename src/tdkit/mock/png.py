"""A one-colour PNG of any size, with the standard library only (no new dependency)."""

from __future__ import annotations

import struct
import zlib


def _chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def png(width: int, height: int, rgb: tuple[int, int, int] = (128, 128, 128)) -> bytes:
    """A valid 8-bit RGB PNG of `width` x `height` pixels, all `rgb`."""
    row = b"\x00" + bytes(rgb) * width  # filter type 0 per scanline
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(row * height, 9))
        + _chunk(b"IEND", b"")
    )
