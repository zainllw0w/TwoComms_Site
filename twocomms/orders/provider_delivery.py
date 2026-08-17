"""Typed outcomes for external provider calls."""

from http.client import RemoteDisconnected

import requests


class ProviderDeliveryAmbiguous(RuntimeError):
    """The request crossed the I/O boundary but its result is unknown."""


_AMBIGUOUS_TRANSPORT_ERRORS = (
    TimeoutError,
    ConnectionResetError,
    ConnectionAbortedError,
    ConnectionRefusedError,
    RemoteDisconnected,
    requests.Timeout,
    requests.ConnectionError,
)


def is_ambiguous_transport_error(exc):
    """Return whether an exception chain represents an uncertain send."""
    seen = set()
    current = exc
    while current is not None and id(current) not in seen:
        if isinstance(current, _AMBIGUOUS_TRANSPORT_ERRORS):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False
