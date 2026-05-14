"""
Helpers for the user-managed AnalyticsExclusion list.

Used both by the tracking middleware (to skip writes for excluded entities)
and by the admin analytics services (to filter excluded data out of every
widget/queryset). The helper layer caches the active exclusion snapshot for
30 seconds to keep middleware overhead negligible while still picking up
admin-panel changes within a reasonable window.
"""

from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass, field
from typing import Iterable

from django.core.cache import cache
from django.db.models import Q

logger = logging.getLogger(__name__)

CACHE_KEY = "analytics_exclusions:snapshot:v1"
CACHE_TTL = 30  # seconds; admin edits flush via signal below.


@dataclass(frozen=True)
class ExclusionSnapshot:
    ips: tuple[str, ...] = ()
    networks: tuple[ipaddress._BaseNetwork, ...] = ()
    user_ids: frozenset[int] = field(default_factory=frozenset)
    visitor_ids: frozenset[str] = field(default_factory=frozenset)
    user_agents: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (
            self.ips
            or self.networks
            or self.user_ids
            or self.visitor_ids
            or self.user_agents
            or self.paths
        )


def _build_snapshot() -> ExclusionSnapshot:
    """Load the active exclusions from the DB into normalized buckets."""
    from .models import AnalyticsExclusion  # local import to avoid app-loading cycles

    ips: list[str] = []
    networks: list[ipaddress._BaseNetwork] = []
    user_ids: set[int] = set()
    visitor_ids: set[str] = set()
    user_agents: list[str] = []
    paths: list[str] = []

    queryset = AnalyticsExclusion.objects.filter(is_active=True).only("kind", "value")
    for entry in queryset:
        raw = (entry.value or "").strip()
        if not raw:
            continue
        kind = entry.kind
        if kind == AnalyticsExclusion.Kind.IP:
            if "/" in raw:
                try:
                    networks.append(ipaddress.ip_network(raw, strict=False))
                except ValueError:
                    logger.warning("Invalid CIDR network in AnalyticsExclusion #%s: %s", entry.pk, raw)
            else:
                ips.append(raw)
        elif kind == AnalyticsExclusion.Kind.USER:
            try:
                user_ids.add(int(raw))
            except ValueError:
                logger.warning("Invalid user id in AnalyticsExclusion #%s: %s", entry.pk, raw)
        elif kind == AnalyticsExclusion.Kind.VISITOR:
            visitor_ids.add(raw)
        elif kind == AnalyticsExclusion.Kind.USER_AGENT:
            user_agents.append(raw.lower())
        elif kind == AnalyticsExclusion.Kind.PATH:
            paths.append(raw)

    return ExclusionSnapshot(
        ips=tuple(ips),
        networks=tuple(networks),
        user_ids=frozenset(user_ids),
        visitor_ids=frozenset(visitor_ids),
        user_agents=tuple(user_agents),
        paths=tuple(paths),
    )


def get_snapshot() -> ExclusionSnapshot:
    """Return the cached exclusion snapshot, building it on cache miss."""
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached
    try:
        snapshot = _build_snapshot()
    except Exception:  # pragma: no cover - DB might be unavailable during boot
        logger.exception("Failed to build analytics exclusion snapshot")
        snapshot = ExclusionSnapshot()
    cache.set(CACHE_KEY, snapshot, CACHE_TTL)
    return snapshot


def invalidate_snapshot() -> None:
    """Drop cached snapshot so the next request rebuilds it from the DB."""
    cache.delete(CACHE_KEY)


def _ip_matches(ip: str, snapshot: ExclusionSnapshot) -> bool:
    if not ip:
        return False
    if ip in snapshot.ips:
        return True
    if not snapshot.networks:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in network for network in snapshot.networks)


def is_request_excluded(
    request,
    *,
    ip: str | None = None,
    visitor_id: str | None = None,
    user_id: int | None = None,
    user_agent: str | None = None,
    path: str | None = None,
) -> bool:
    """
    Return True if this request should be skipped from analytics writes.

    Pass already-resolved ``ip`` / ``visitor_id`` / ``user_id`` / ``user_agent``
    when you have them, otherwise the helper extracts them from the request.
    """
    snapshot = get_snapshot()
    if snapshot.is_empty:
        return False

    if ip is None:
        try:
            from .utm_utils import get_client_ip  # local to avoid module-load cycles
            ip = get_client_ip(request) or ""
        except Exception:
            ip = ""
    if _ip_matches(ip or "", snapshot):
        return True

    if visitor_id is None:
        visitor_id = (getattr(request, "analytics_visitor_id", "") or "").strip()
    if visitor_id and visitor_id in snapshot.visitor_ids:
        return True

    if user_id is None:
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            user_id = user.id
    if user_id is not None and user_id in snapshot.user_ids:
        return True

    if user_agent is None:
        user_agent = (request.META.get("HTTP_USER_AGENT") or "") if hasattr(request, "META") else ""
    ua_lower = (user_agent or "").lower()
    if ua_lower and any(token in ua_lower for token in snapshot.user_agents):
        return True

    if path is None:
        path = (request.path or "") if hasattr(request, "path") else ""
    if path and any(path.startswith(prefix) for prefix in snapshot.paths):
        return True

    return False


def session_exclusion_q() -> Q:
    """Build a queryset Q to subtract excluded SiteSession rows.

    Returns ``Q()`` (empty matcher) when no exclusions are configured so
    callers can safely chain it with ``.exclude(...)``.
    """
    snapshot = get_snapshot()
    if snapshot.is_empty:
        return Q()

    query = Q()
    if snapshot.ips:
        query |= Q(ip_address__in=snapshot.ips)
    if snapshot.user_ids:
        query |= Q(user_id__in=snapshot.user_ids)
    if snapshot.visitor_ids:
        query |= Q(visitor_id__in=snapshot.visitor_ids)
    for token in snapshot.user_agents:
        query |= Q(user_agent__icontains=token)
    return query


def utm_session_exclusion_q() -> Q:
    """Q-filter for excluding UTMSession rows."""
    snapshot = get_snapshot()
    if snapshot.is_empty:
        return Q()

    query = Q()
    if snapshot.ips:
        query |= Q(ip_address__in=snapshot.ips)
    if snapshot.visitor_ids:
        query |= Q(visitor_id__in=snapshot.visitor_ids)
    for token in snapshot.user_agents:
        query |= Q(user_agent__icontains=token)
    return query


def pageview_exclusion_q() -> Q:
    """Q-filter for excluding PageView rows via session join + path prefix."""
    snapshot = get_snapshot()
    if snapshot.is_empty:
        return Q()

    query = Q()
    if snapshot.ips:
        query |= Q(session__ip_address__in=snapshot.ips)
    if snapshot.user_ids:
        query |= Q(user_id__in=snapshot.user_ids) | Q(session__user_id__in=snapshot.user_ids)
    if snapshot.visitor_ids:
        query |= Q(session__visitor_id__in=snapshot.visitor_ids)
    for token in snapshot.user_agents:
        query |= Q(session__user_agent__icontains=token)
    for prefix in snapshot.paths:
        query |= Q(path__startswith=prefix)
    return query


def action_exclusion_q() -> Q:
    """Q-filter for UserAction rows. Joins through site_session/utm_session."""
    snapshot = get_snapshot()
    if snapshot.is_empty:
        return Q()

    query = Q()
    if snapshot.ips:
        query |= Q(site_session__ip_address__in=snapshot.ips) | Q(utm_session__ip_address__in=snapshot.ips)
    if snapshot.user_ids:
        query |= Q(user_id__in=snapshot.user_ids) | Q(site_session__user_id__in=snapshot.user_ids)
    if snapshot.visitor_ids:
        query |= (
            Q(site_session__visitor_id__in=snapshot.visitor_ids)
            | Q(utm_session__visitor_id__in=snapshot.visitor_ids)
        )
    for token in snapshot.user_agents:
        query |= Q(site_session__user_agent__icontains=token) | Q(utm_session__user_agent__icontains=token)
    for prefix in snapshot.paths:
        query |= Q(page_path__startswith=prefix)
    return query


def order_exclusion_q() -> Q:
    """Q-filter for Order rows (via utm_session join + user link)."""
    snapshot = get_snapshot()
    if snapshot.is_empty:
        return Q()

    query = Q()
    if snapshot.user_ids:
        query |= Q(user_id__in=snapshot.user_ids)
    if snapshot.ips:
        query |= Q(utm_session__ip_address__in=snapshot.ips)
    if snapshot.visitor_ids:
        query |= Q(utm_session__visitor_id__in=snapshot.visitor_ids)
    for token in snapshot.user_agents:
        query |= Q(utm_session__user_agent__icontains=token)
    return query


def filter_iterable(values: Iterable, *, attr_ip: str | None = None) -> list:
    """Drop excluded items from an in-memory iterable using their ip attr."""
    snapshot = get_snapshot()
    if snapshot.is_empty or not attr_ip:
        return list(values)
    result = []
    for item in values:
        ip = getattr(item, attr_ip, "") or ""
        if not _ip_matches(ip, snapshot):
            result.append(item)
    return result
