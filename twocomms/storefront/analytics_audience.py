from __future__ import annotations

from functools import lru_cache
from ipaddress import ip_address, ip_network
from typing import Any, Mapping

from django.db.models import Q, Subquery


ANALYTICS_SCOPE_KEY = "analytics_scope"
ANALYTICS_SCOPE_REASON_KEY = "analytics_scope_reason"

ANALYTICS_SCOPE_PUBLIC = "public"
ANALYTICS_SCOPE_ADMIN = "admin"
ANALYTICS_SCOPE_INTERNAL = "internal"
ANALYTICS_NON_PUBLIC_SCOPES = (
    ANALYTICS_SCOPE_ADMIN,
    ANALYTICS_SCOPE_INTERNAL,
)


def _normalized_ip(value: str | None) -> str:
    try:
        return str(ip_address((value or "").strip()))
    except Exception:
        return ""


@lru_cache(maxsize=1)
def _internal_ip_patterns() -> tuple[str, ...]:
    import os

    raw_value = (os.environ.get("ANALYTICS_INTERNAL_IPS") or "").strip()
    if not raw_value:
        return ()
    return tuple(part.strip() for part in raw_value.split(",") if part.strip())


@lru_cache(maxsize=1)
def _internal_ip_networks() -> tuple[Any, ...]:
    networks = []
    for pattern in _internal_ip_patterns():
        try:
            if "/" in pattern:
                networks.append(ip_network(pattern, strict=False))
        except Exception:
            continue
    return tuple(networks)


@lru_cache(maxsize=1)
def internal_ip_exact_values() -> tuple[str, ...]:
    values: list[str] = []
    for pattern in _internal_ip_patterns():
        if "/" in pattern:
            continue
        normalized = _normalized_ip(pattern)
        if normalized:
            values.append(normalized)
    return tuple(values)


def is_staff_like_user(user: Any | None) -> bool:
    if user is None:
        return False
    if hasattr(user, "is_authenticated") and not user.is_authenticated:
        return False
    return bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))


def audience_scope_from_mapping(payload: Mapping[str, Any] | None) -> str:
    raw_scope = str((payload or {}).get(ANALYTICS_SCOPE_KEY) or "").strip().lower()
    if raw_scope in {
        ANALYTICS_SCOPE_PUBLIC,
        ANALYTICS_SCOPE_ADMIN,
        ANALYTICS_SCOPE_INTERNAL,
    }:
        return raw_scope
    return ANALYTICS_SCOPE_PUBLIC


def audience_scope_reason_from_mapping(payload: Mapping[str, Any] | None) -> str:
    return str((payload or {}).get(ANALYTICS_SCOPE_REASON_KEY) or "").strip()


def is_internal_ip(ip_value: str | None) -> bool:
    normalized = _normalized_ip(ip_value)
    if not normalized:
        return False
    if normalized in internal_ip_exact_values():
        return True
    try:
        current = ip_address(normalized)
    except Exception:
        return False
    return any(current in network for network in _internal_ip_networks())


def build_audience_snapshot(
    *,
    user: Any | None = None,
    ip_value: str | None = None,
    existing_payload: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    existing_scope = audience_scope_from_mapping(existing_payload)
    if existing_scope in ANALYTICS_NON_PUBLIC_SCOPES:
        return {
            "scope": existing_scope,
            "reason": audience_scope_reason_from_mapping(existing_payload) or "persisted_scope",
        }

    if is_staff_like_user(user):
        return {"scope": ANALYTICS_SCOPE_ADMIN, "reason": "staff_user"}
    if is_internal_ip(ip_value):
        return {"scope": ANALYTICS_SCOPE_INTERNAL, "reason": "internal_ip"}
    return {"scope": ANALYTICS_SCOPE_PUBLIC, "reason": "public_traffic"}


def build_request_audience_snapshot(request, *, ip_value: str | None = None) -> dict[str, str]:
    return build_audience_snapshot(
        user=getattr(request, "user", None),
        ip_value=ip_value,
        existing_payload=getattr(request, "analytics_first_touch_data", None),
    )


def merge_audience_metadata(payload: Mapping[str, Any] | None, snapshot: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(payload or {})
    merged[ANALYTICS_SCOPE_KEY] = str(snapshot.get("scope") or ANALYTICS_SCOPE_PUBLIC)
    merged[ANALYTICS_SCOPE_REASON_KEY] = str(snapshot.get("reason") or "public_traffic")
    return merged


def audience_scope_from_session(session: Any | None) -> str:
    if session is None:
        return ANALYTICS_SCOPE_PUBLIC
    scope = audience_scope_from_mapping(getattr(session, "first_touch_data", None))
    if scope in ANALYTICS_NON_PUBLIC_SCOPES:
        return scope
    if is_staff_like_user(getattr(session, "user", None)):
        return ANALYTICS_SCOPE_ADMIN
    if is_internal_ip(getattr(session, "ip_address", None)):
        return ANALYTICS_SCOPE_INTERNAL
    return ANALYTICS_SCOPE_PUBLIC


def audience_scope_from_action(action: Any | None) -> str:
    if action is None:
        return ANALYTICS_SCOPE_PUBLIC
    scope = audience_scope_from_mapping(getattr(action, "metadata", None))
    if scope in ANALYTICS_NON_PUBLIC_SCOPES:
        return scope
    if is_staff_like_user(getattr(action, "user", None)):
        return ANALYTICS_SCOPE_ADMIN
    return audience_scope_from_session(getattr(action, "site_session", None))


def non_public_session_q(prefix: str = "") -> Q:
    query = (
        (Q(**{f"{prefix}user_id__isnull": False}) & Q(**{f"{prefix}user__is_staff": True}))
        | (Q(**{f"{prefix}user_id__isnull": False}) & Q(**{f"{prefix}user__is_superuser": True}))
        | (
            Q(**{f"{prefix}first_touch_data__{ANALYTICS_SCOPE_KEY}__isnull": False})
            & Q(**{f"{prefix}first_touch_data__{ANALYTICS_SCOPE_KEY}__in": ANALYTICS_NON_PUBLIC_SCOPES})
        )
    )
    exact_ips = internal_ip_exact_values()
    if exact_ips:
        query |= Q(**{f"{prefix}ip_address__in": exact_ips})
    return query


def public_session_q(prefix: str = "") -> Q:
    return ~non_public_session_q(prefix)


def non_public_action_q(prefix: str = "") -> Q:
    query = (
        (Q(**{f"{prefix}user_id__isnull": False}) & Q(**{f"{prefix}user__is_staff": True}))
        | (Q(**{f"{prefix}user_id__isnull": False}) & Q(**{f"{prefix}user__is_superuser": True}))
        | (
            Q(**{f"{prefix}site_session__user_id__isnull": False})
            & Q(**{f"{prefix}site_session__user__is_staff": True})
        )
        | (
            Q(**{f"{prefix}site_session__user_id__isnull": False})
            & Q(**{f"{prefix}site_session__user__is_superuser": True})
        )
        | (
            Q(**{f"{prefix}metadata__{ANALYTICS_SCOPE_KEY}__isnull": False})
            & Q(**{f"{prefix}metadata__{ANALYTICS_SCOPE_KEY}__in": ANALYTICS_NON_PUBLIC_SCOPES})
        )
        | Q(
            **{
                f"{prefix}site_session__first_touch_data__{ANALYTICS_SCOPE_KEY}__isnull": False,
                f"{prefix}site_session__first_touch_data__{ANALYTICS_SCOPE_KEY}__in": ANALYTICS_NON_PUBLIC_SCOPES
            }
        )
    )
    exact_ips = internal_ip_exact_values()
    if exact_ips:
        query |= Q(**{f"{prefix}site_session__ip_address__in": exact_ips})
    return query


def public_action_q(prefix: str = "") -> Q:
    return ~non_public_action_q(prefix)


def non_public_order_q() -> Q:
    from .models import SiteSession

    excluded_sessions = SiteSession.objects.filter(non_public_session_q()).values("session_key")
    return (
        (Q(user_id__isnull=False) & Q(user__is_staff=True))
        | (Q(user_id__isnull=False) & Q(user__is_superuser=True))
        | (Q(utm_session__session__user_id__isnull=False) & Q(utm_session__session__user__is_staff=True))
        | (Q(utm_session__session__user_id__isnull=False) & Q(utm_session__session__user__is_superuser=True))
        | (
            Q(utm_session__session__first_touch_data__analytics_scope__isnull=False)
            & Q(utm_session__session__first_touch_data__analytics_scope__in=ANALYTICS_NON_PUBLIC_SCOPES)
        )
        | Q(session_key__in=Subquery(excluded_sessions))
    )


def public_order_q() -> Q:
    return ~non_public_order_q()
