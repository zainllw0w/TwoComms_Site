"""
Staff-only AJAX endpoints powering the analytics dashboard side panels:

- CRUD for ``AnalyticsExclusion`` rows (offices, staff, bot agents)
- Session list / detail view for "drill-down" inspection of recent visitors

These views are intentionally tiny — heavy lifting lives in
``services/admin_analytics.py``. The session detail view is read-only and
respects the same ``AnalyticsExclusion`` filter set as the main dashboard.
"""

from __future__ import annotations

import ipaddress
import json
import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from ..analytics_exclusions import (
    invalidate_snapshot,
    pageview_exclusion_q,
    session_exclusion_q,
)
from ..models import AnalyticsExclusion, PageView, SiteSession, UserAction, UTMSession

logger = logging.getLogger(__name__)


def _serialize_exclusion(entry: AnalyticsExclusion) -> dict:
    return {
        "id": entry.id,
        "kind": entry.kind,
        "kind_label": entry.get_kind_display(),
        "value": entry.value,
        "note": entry.note or "",
        "is_active": entry.is_active,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else "",
        "created_at": entry.created_at.isoformat() if entry.created_at else "",
        "created_by": entry.created_by.username if entry.created_by_id else "",
    }


def _validate_exclusion_value(kind: str, raw_value: str) -> tuple[str, str | None]:
    value = (raw_value or "").strip()
    if not value:
        return "", "Значення не може бути порожнім."
    if kind == AnalyticsExclusion.Kind.IP:
        try:
            if "/" in value:
                ipaddress.ip_network(value, strict=False)
            else:
                ipaddress.ip_address(value)
        except ValueError:
            return "", "IP-адреса має бути валідною (192.168.0.1 або 10.0.0.0/24)."
    elif kind == AnalyticsExclusion.Kind.USER:
        if not value.isdigit():
            return "", "User ID має бути цілим числом."
    elif kind == AnalyticsExclusion.Kind.PATH and not value.startswith("/"):
        return "", "Шлях має починатись зі слеша (/)."
    if len(value) > 512:
        return "", "Значення занадто довге (максимум 512 символів)."
    return value, None


@staff_member_required
def admin_analytics_exclusions_list(request):
    """Return the current exclusion roster for the dashboard side panel."""
    rows = list(
        AnalyticsExclusion.objects.select_related("created_by").order_by(
            "-is_active", "kind", "value"
        )
    )
    return JsonResponse(
        {
            "success": True,
            "items": [_serialize_exclusion(row) for row in rows],
            "total": len(rows),
            "active": sum(1 for row in rows if row.is_active),
        }
    )


@staff_member_required
def admin_analytics_exclusion_create(request):
    """Create a new analytics exclusion."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"}, status=405)

    kind = (request.POST.get("kind") or "").strip()
    if kind not in dict(AnalyticsExclusion.Kind.choices):
        return JsonResponse({"success": False, "error": "Невірний тип виключення"}, status=400)

    value, error = _validate_exclusion_value(kind, request.POST.get("value", ""))
    if error:
        return JsonResponse({"success": False, "error": error}, status=400)

    note = (request.POST.get("note") or "").strip()[:255]

    if AnalyticsExclusion.objects.filter(kind=kind, value=value).exists():
        return JsonResponse(
            {"success": False, "error": "Таке виключення вже існує."},
            status=409,
        )

    entry = AnalyticsExclusion.objects.create(
        kind=kind,
        value=value,
        note=note,
        is_active=True,
        created_by=request.user if request.user.is_authenticated else None,
    )
    invalidate_snapshot()
    logger.info("Analytics exclusion created: #%s %s=%s by %s", entry.pk, kind, value, request.user)
    return JsonResponse({"success": True, "item": _serialize_exclusion(entry)})


@staff_member_required
def admin_analytics_exclusion_update(request, pk: int):
    """Toggle, edit or delete an exclusion."""
    entry = get_object_or_404(AnalyticsExclusion, pk=pk)

    if request.method == "DELETE":
        entry.delete()
        invalidate_snapshot()
        logger.info("Analytics exclusion deleted: #%s by %s", pk, request.user)
        return JsonResponse({"success": True, "deleted": True})

    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"}, status=405)

    update_fields: list[str] = []
    action = (request.POST.get("action") or "").strip()
    if action == "toggle":
        entry.is_active = not entry.is_active
        update_fields.append("is_active")
    else:
        if "kind" in request.POST or "value" in request.POST:
            new_kind = (request.POST.get("kind") or entry.kind).strip()
            if new_kind not in dict(AnalyticsExclusion.Kind.choices):
                return JsonResponse({"success": False, "error": "Невірний тип"}, status=400)
            value, error = _validate_exclusion_value(new_kind, request.POST.get("value") or entry.value)
            if error:
                return JsonResponse({"success": False, "error": error}, status=400)
            entry.kind = new_kind
            entry.value = value
            update_fields += ["kind", "value"]
        if "note" in request.POST:
            entry.note = (request.POST.get("note") or "").strip()[:255]
            update_fields.append("note")
        if "is_active" in request.POST:
            entry.is_active = request.POST.get("is_active", "").lower() in {"1", "true", "yes", "on"}
            update_fields.append("is_active")

    if not update_fields:
        return JsonResponse({"success": False, "error": "Нічого оновлювати"}, status=400)

    update_fields.append("updated_at")
    try:
        entry.save(update_fields=update_fields)
    except Exception as exc:
        logger.warning("Failed to save AnalyticsExclusion #%s: %s", pk, exc)
        return JsonResponse({"success": False, "error": str(exc)}, status=400)

    invalidate_snapshot()
    logger.info("Analytics exclusion updated: #%s fields=%s by %s", pk, update_fields, request.user)
    return JsonResponse({"success": True, "item": _serialize_exclusion(entry)})


def _filtered_session_qs(*, days: int, include_bots: bool):
    qs = SiteSession.objects.select_related("user").all()
    if days:
        since = timezone.now() - timezone.timedelta(days=days)
        qs = qs.filter(last_seen__gte=since)
    if not include_bots:
        qs = qs.filter(is_bot=False)
    excl = session_exclusion_q()
    if excl:
        qs = qs.exclude(excl)
    return qs


@staff_member_required
def admin_analytics_sessions(request):
    """Return a paginated list of recent sessions with quick stats."""
    try:
        days = max(0, min(int(request.GET.get("days", 7)), 90))
    except ValueError:
        days = 7
    try:
        limit = max(1, min(int(request.GET.get("limit", 30)), 200))
    except ValueError:
        limit = 30
    try:
        offset = max(0, int(request.GET.get("offset", 0)))
    except ValueError:
        offset = 0
    include_bots = (request.GET.get("include_bots") or "").lower() in {"1", "true", "yes", "on"}
    search = (request.GET.get("q") or "").strip()

    qs = _filtered_session_qs(days=days, include_bots=include_bots)
    if search:
        qs = qs.filter(
            ip_address__icontains=search
        ) | qs.filter(visitor_id__icontains=search) | qs.filter(user__username__icontains=search)

    qs = qs.order_by("-last_seen")
    total = qs.count()
    rows = list(qs[offset:offset + limit].values(
        "id",
        "session_key",
        "visitor_id",
        "user_id",
        "user__username",
        "ip_address",
        "user_agent",
        "is_bot",
        "first_seen",
        "last_seen",
        "last_path",
        "pageviews",
    ))

    items = []
    for row in rows:
        items.append(
            {
                "id": row["id"],
                "session_key": row["session_key"],
                "visitor_id": row["visitor_id"],
                "user_id": row["user_id"],
                "username": row["user__username"] or "",
                "ip_address": row["ip_address"] or "",
                "user_agent": (row["user_agent"] or "")[:200],
                "is_bot": row["is_bot"],
                "first_seen": row["first_seen"].isoformat() if row["first_seen"] else "",
                "last_seen": row["last_seen"].isoformat() if row["last_seen"] else "",
                "last_path": row["last_path"] or "",
                "pageviews": row["pageviews"],
                "duration_seconds": int(
                    (row["last_seen"] - row["first_seen"]).total_seconds()
                ) if row["first_seen"] and row["last_seen"] else 0,
            }
        )

    return JsonResponse({
        "success": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    })


@staff_member_required
def admin_analytics_session_detail(request, session_id: int):
    """Detailed view: pageview timeline + actions + UTM info for a session."""
    session = get_object_or_404(SiteSession.objects.select_related("user"), pk=session_id)

    pv_qs = (
        PageView.objects.filter(session_id=session.id)
        .order_by("when")
        .values("path", "referrer", "when", "is_bot")
    )
    pv_excl = pageview_exclusion_q()
    if pv_excl:
        pv_qs = pv_qs.exclude(pv_excl)
    pageviews = []
    previous_when = None
    for entry in pv_qs:
        delta = None
        if previous_when:
            delta = int((entry["when"] - previous_when).total_seconds())
        pageviews.append(
            {
                "path": entry["path"] or "",
                "referrer": entry["referrer"] or "",
                "when": entry["when"].isoformat() if entry["when"] else "",
                "is_bot": entry["is_bot"],
                "seconds_since_prev": delta,
            }
        )
        previous_when = entry["when"]

    actions = list(
        UserAction.objects.filter(site_session_id=session.id)
        .order_by("timestamp")
        .values(
            "action_type",
            "page_path",
            "product_id",
            "product_name",
            "cart_value",
            "order_id",
            "order_number",
            "timestamp",
            "metadata",
            "points_earned",
        )
    )
    for action in actions:
        if action.get("timestamp"):
            action["timestamp"] = action["timestamp"].isoformat()
        if action.get("cart_value") is not None:
            action["cart_value"] = float(action["cart_value"])

    utm = UTMSession.objects.filter(session_key=session.session_key).first()
    utm_payload = None
    if utm is not None:
        utm_payload = {
            "utm_source": utm.utm_source or "",
            "utm_medium": utm.utm_medium or "",
            "utm_campaign": utm.utm_campaign or "",
            "utm_content": utm.utm_content or "",
            "utm_term": utm.utm_term or "",
            "fbclid": utm.fbclid or "",
            "gclid": utm.gclid or "",
            "ttclid": utm.ttclid or "",
            "country": utm.country_name or utm.country or "",
            "city": utm.city or "",
            "device_type": utm.device_type or "",
            "browser_name": utm.browser_name or "",
            "os_name": utm.os_name or "",
            "referrer": utm.referrer or "",
            "landing_page": utm.landing_page or "",
            "is_returning_visitor": utm.is_returning_visitor,
            "visit_count": utm.visit_count,
            "is_converted": utm.is_converted,
        }

    summary = {
        "id": session.id,
        "session_key": session.session_key,
        "visitor_id": session.visitor_id or "",
        "user_id": session.user_id,
        "username": session.user.username if session.user_id else "",
        "ip_address": session.ip_address or "",
        "user_agent": session.user_agent or "",
        "is_bot": session.is_bot,
        "first_seen": session.first_seen.isoformat() if session.first_seen else "",
        "last_seen": session.last_seen.isoformat() if session.last_seen else "",
        "last_path": session.last_path or "",
        "pageviews": session.pageviews,
        "first_touch_data": session.first_touch_data or {},
        "duration_seconds": int(
            (session.last_seen - session.first_seen).total_seconds()
        ) if session.first_seen and session.last_seen else 0,
    }

    return JsonResponse({
        "success": True,
        "session": summary,
        "pageviews": pageviews,
        "actions": actions,
        "utm": utm_payload,
    })
