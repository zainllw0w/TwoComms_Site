from __future__ import annotations

import base64
import binascii


class InvalidBase64(ValueError):
    pass


def strict_b64decode(value: str | bytes | bytearray | memoryview) -> bytes:
    """Decode standard or URL-safe Base64 without accepting ignored garbage."""
    try:
        if isinstance(value, str):
            encoded = value.encode("ascii")
        elif isinstance(value, (bytes, bytearray, memoryview)):
            encoded = bytes(value)
        else:
            raise TypeError
    except (TypeError, UnicodeEncodeError):
        raise InvalidBase64("Invalid Base64 payload") from None

    if b"=" in encoded:
        if len(encoded) % 4:
            raise InvalidBase64("Invalid Base64 payload")
        padded = encoded
    else:
        remainder = len(encoded) % 4
        if remainder == 1:
            raise InvalidBase64("Invalid Base64 payload")
        padded = encoded + (b"=" * ((4 - remainder) % 4))

    try:
        return base64.b64decode(padded, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError):
        raise InvalidBase64("Invalid Base64 payload") from None
