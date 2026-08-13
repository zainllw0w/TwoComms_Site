"""Deterministic SQLite test settings with external network denied."""

from __future__ import annotations

import ipaddress
import os
import socket as _socket

from test_settings import *  # noqa: F401,F403


os.environ["SECRET_KEY"] = "test-secret-key-for-no-network-profile"
for _name in (
    "DATABASE_URL",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_ADMIN_ID",
    "MANAGER_TG_BOT_TOKEN",
    "MANAGEMENT_TG_BOT_TOKEN",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "BINOTEL_SECRET",
    "META_ACCESS_TOKEN",
):
    os.environ[_name] = ""


_OriginalSocket = _socket.socket


def _is_local_address(address) -> bool:
    if not isinstance(address, tuple) or not address:
        return True
    host = str(address[0]).strip().lower()
    if host in {"localhost", "ip6-localhost"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


_original_getaddrinfo = _socket.getaddrinfo


def _getaddrinfo(host, *args, **kwargs):
    if not _is_local_address((host,)):
        raise OSError("external network denied by test_settings_no_network")
    return _original_getaddrinfo(host, *args, **kwargs)


class _NetworkDeniedSocket(_OriginalSocket):
    def connect(self, address):
        if not _is_local_address(address):
            raise OSError("external network denied by test_settings_no_network")
        return super().connect(address)

    def connect_ex(self, address):
        if not _is_local_address(address):
            return 101
        return super().connect_ex(address)

    def sendto(self, data, address, *args):
        if not _is_local_address(address):
            raise OSError("external network denied by test_settings_no_network")
        return super().sendto(data, address, *args)

    def sendmsg(self, buffers, *args, **kwargs):
        address = kwargs.get("address")
        if address is None and args and isinstance(args[-1], tuple):
            address = args[-1]
        if address is not None and not _is_local_address(address):
            raise OSError("external network denied by test_settings_no_network")
        return super().sendmsg(buffers, *args, **kwargs)


_socket.socket = _NetworkDeniedSocket
_socket.getaddrinfo = _getaddrinfo
TEST_NETWORK_POLICY = "deny-external"
TESTING = True
