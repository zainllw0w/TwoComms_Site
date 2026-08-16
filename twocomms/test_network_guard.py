"""Process-local external network denial used by deterministic test profiles."""

from __future__ import annotations

import ipaddress
import socket as _socket


_INSTALLED = False
_OriginalSocket = _socket.socket
_original_getaddrinfo = _socket.getaddrinfo
_original_gethostbyname = _socket.gethostbyname
_original_gethostbyname_ex = _socket.gethostbyname_ex


def _is_local_host(host: object) -> bool:
    value = str(host or "").strip().lower().rstrip(".")
    if value in {"localhost", "ip6-localhost"}:
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _is_local_address(address: object) -> bool:
    if not isinstance(address, tuple) or not address:
        return True
    return _is_local_host(address[0])


def _deny_external(host: object) -> None:
    if not _is_local_host(host):
        raise OSError("external network denied by test network policy")


def _getaddrinfo(host, *args, **kwargs):
    _deny_external(host)
    return _original_getaddrinfo(host, *args, **kwargs)


def _gethostbyname(host):
    _deny_external(host)
    return _original_gethostbyname(host)


def _gethostbyname_ex(host):
    _deny_external(host)
    return _original_gethostbyname_ex(host)


class _NetworkDeniedSocket(_OriginalSocket):
    def connect(self, address):
        if not _is_local_address(address):
            raise OSError("external network denied by test network policy")
        return super().connect(address)

    def connect_ex(self, address):
        if not _is_local_address(address):
            return 101
        return super().connect_ex(address)

    def sendto(self, data, *args):
        address = args[-1] if args else None
        if address is not None and not _is_local_address(address):
            raise OSError("external network denied by test network policy")
        return super().sendto(data, *args)

    def sendmsg(self, buffers, *args, **kwargs):
        address = kwargs.get("address")
        if address is None and args and isinstance(args[-1], tuple):
            address = args[-1]
        if address is not None and not _is_local_address(address):
            raise OSError("external network denied by test network policy")
        return super().sendmsg(buffers, *args, **kwargs)


def install_external_network_guard() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _socket.socket = _NetworkDeniedSocket
    _socket.getaddrinfo = _getaddrinfo
    _socket.gethostbyname = _gethostbyname
    _socket.gethostbyname_ex = _gethostbyname_ex
    _INSTALLED = True
