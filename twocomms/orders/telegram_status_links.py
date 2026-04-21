from __future__ import annotations

from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.urls import reverse


SIGNER_SALT = "orders.telegram-action-link"
TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 30


def get_public_base_url() -> str:
    return (getattr(settings, "SITE_BASE_URL", "") or "https://twocomms.shop").rstrip("/")


def build_order_action_token(order_id: int, action: str) -> str:
    signer = signing.TimestampSigner(salt=SIGNER_SALT)
    return signer.sign(f"{order_id}:{action}")


def verify_order_action_token(token: str, *, order_id: int, action: str, max_age: int = TOKEN_MAX_AGE_SECONDS) -> bool:
    if not token:
        return False

    signer = signing.TimestampSigner(salt=SIGNER_SALT)
    try:
        value = signer.unsign(token, max_age=max_age)
    except signing.BadSignature:
        return False
    return value == f"{order_id}:{action}"


def build_order_action_url(order, action: str, *, route_name: str, path_value: str | None = None) -> str:
    token = build_order_action_token(order.pk, action)
    path = reverse(route_name, args=[order.pk, path_value or action])
    query = urlencode({"token": token})
    return f"{get_public_base_url()}{path}?{query}"


def build_order_status_token(order_id: int, status: str) -> str:
    return build_order_action_token(order_id, status)


def verify_order_status_token(token: str, *, order_id: int, status: str, max_age: int = TOKEN_MAX_AGE_SECONDS) -> bool:
    return verify_order_action_token(token, order_id=order_id, action=status, max_age=max_age)


def build_order_status_action_url(order, status: str) -> str:
    return build_order_action_url(order, status, route_name="telegram_order_status_action")
