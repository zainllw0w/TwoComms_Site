from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from management.models import Client, ClientFollowUp, DuplicateReview, ReminderRead, Shop
from management.services.config_versions import get_management_config


def _time_label(dt_local, now):
    delta = (now - dt_local).total_seconds()
    if delta >= 0:
        minutes = int(delta // 60)
        hours = int(delta // 3600)
        days = int(delta // 86400)
        if minutes < 1:
            return "щойно"
        if minutes < 60:
            return f"{minutes} хв тому"
        if hours < 24:
            return f"{hours} год тому"
        return f"{days} дн тому"

    delta_abs = abs(delta)
    minutes = int(delta_abs // 60)
    hours = int(delta_abs // 3600)
    days = int(delta_abs // 86400)
    if minutes < 1:
        return "за кілька секунд"
    if minutes < 60:
        return f"через {minutes} хв"
    if hours < 24:
        return f"через {hours} год"
    return f"через {days} дн"


def _ladder_for_due(dt_local, now):
    if dt_local > now:
        seconds = int((dt_local - now).total_seconds())
        if seconds <= 900:
            return "t_minus_15"
        return "scheduled"
    overdue = now - dt_local
    if overdue < timedelta(hours=12):
        return "due_now"
    if overdue < timedelta(days=1):
        return "overdue_same_day"
    if overdue < timedelta(days=2):
        return "next_day_escalation"
    return "accumulated_overdue"


def _in_quiet_hours(now, ui_config: dict) -> bool:
    quiet = (ui_config or {}).get("quiet_hours") or {}
    start = int(quiet.get("start", 21) or 21)
    end = int(quiet.get("end", 8) or 8)
    hour = now.hour
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end


def build_reminder_digest(user, *, now=None, stats=None, report_sent=False) -> dict:
    now = timezone.localtime(now or timezone.now())
    today = now.date()
    cfg = get_management_config()
    ui_config = cfg.get("ui_config") or {}
    max_followups = int(ui_config.get("max_followups_per_day", 25) or 25)
    duplicate_queue_warn = int(ui_config.get("duplicate_queue_warn", 5) or 5)
    read_keys = set(ReminderRead.objects.filter(user=user).values_list("key", flat=True))
    reminders = []

    followups = (
        ClientFollowUp.objects.filter(owner=user, status=ClientFollowUp.Status.OPEN)
        .select_related("client")
        .order_by("due_at", "id")
    )
    due_followups = []
    for followup in followups:
        if followup.grace_until and followup.grace_until > now:
            continue
        dt_local = timezone.localtime(followup.due_at)
        if dt_local.date() != today:
            continue
        ladder = _ladder_for_due(dt_local, now)
        eta_raw = max(0, int((dt_local - now).total_seconds()))
        status = "soon" if dt_local > now else "due"
        reminder = {
            "followup_id": followup.id,
            "client_id": followup.client_id,
            "shop": getattr(followup.client, "shop_name", "") or "",
            "name": getattr(followup.client, "full_name", "") or "",
            "phone": getattr(followup.client, "phone", "") or "",
            "when": dt_local.strftime("%d.%m %H:%M"),
            "time_label": _time_label(dt_local, now),
            "status": status,
            "kind": "call",
            "ladder": ladder,
            "dt": dt_local,
            "dt_iso": dt_local.isoformat(),
            "eta_seconds": eta_raw,
            "key": f"followup-{followup.id}-{dt_local.isoformat()}-{ladder}",
            "is_timer": status == "soon" and eta_raw > 0,
        }
        reminder["read"] = False if status == "soon" else reminder["key"] in read_keys
        reminders.append(reminder)
        if dt_local <= now:
            due_followups.append(reminder)

    shop_qs = Shop.objects.filter(created_by=user, next_contact_at__isnull=False).prefetch_related("phones").order_by("next_contact_at")
    for shop in shop_qs:
        dt_local = timezone.localtime(shop.next_contact_at)
        if dt_local.date() != today:
            continue
        eta_raw = max(0, int((dt_local - now).total_seconds()))
        if eta_raw > 3600 and dt_local > now:
            continue
        ladder = _ladder_for_due(dt_local, now)
        reminders.append(
            {
                "shop": shop.name,
                "name": shop.owner_full_name or "",
                "phone": next((p.phone for p in shop.phones.all() if getattr(p, "is_primary", False)), ""),
                "when": dt_local.strftime("%d.%m %H:%M"),
                "time_label": _time_label(dt_local, now),
                "status": "soon" if dt_local > now else "due",
                "kind": "shop",
                "ladder": ladder,
                "dt": dt_local,
                "dt_iso": dt_local.isoformat(),
                "eta_seconds": eta_raw,
                "key": f"shop-{shop.id}-{dt_local.isoformat()}-{ladder}",
                "is_timer": dt_local > now and eta_raw > 0,
                "read": False if dt_local > now else f"shop-{shop.id}-{dt_local.isoformat()}-{ladder}" in read_keys,
            }
        )

    if stats and stats.get("processed_today", 0) > 0 and not report_sent and now.weekday() < 5 and now.hour >= 19:
        reminders.append(
            {
                "shop": "Звітність",
                "name": "",
                "phone": "",
                "when": now.strftime("%d.%m %H:%M"),
                "time_label": "щойно",
                "status": "report",
                "kind": "report",
                "ladder": "report_due",
                "title": "Потрібно відправити звіт",
                "dt": now,
                "dt_iso": now.isoformat(),
                "eta_seconds": 0,
                "key": f"report-{now.strftime('%Y%m%d')}",
                "read": f"report-{now.strftime('%Y%m%d')}" in read_keys,
            }
        )

    reminders.sort(key=lambda item: item.get("dt") or now)

    digest_mode = len(due_followups) > max_followups
    trimmed = reminders[:max_followups] if digest_mode else reminders
    incident_keys = []
    if digest_mode:
        incident_keys.append("REMINDER_STORM")
    duplicate_backlog = DuplicateReview.objects.filter(owner=user, status=DuplicateReview.Status.OPEN).count()
    if duplicate_backlog >= duplicate_queue_warn:
        incident_keys.append("DUPLICATE_QUEUE_BACKLOG")

    return {
        "reminders": trimmed,
        "digest_mode": digest_mode,
        "overload_count": max(0, len(due_followups) - max_followups),
        "quiet_hours_active": _in_quiet_hours(now, ui_config),
        "incident_keys": incident_keys,
        "duplicate_backlog": duplicate_backlog,
    }
