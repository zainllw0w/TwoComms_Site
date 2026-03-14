import json

from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import F, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import ManagementDailyActivity, ManagementStatsAdviceDismissal, NightlyScoreSnapshot, ScoreAppeal, SupervisorActionLog
from .stats_service import parse_stats_range, get_stats_payload
from .views import (
    get_manager_bot_username,
    get_reminders,
    get_user_stats,
    has_report_today,
    user_is_management,
)
from .constants import TARGET_CLIENTS_DAY, TARGET_POINTS_DAY


@login_required(login_url="management_login")
def stats(request):
    if not user_is_management(request.user):
        return redirect("management_login")

    r = parse_stats_range(request.GET)
    payload = get_stats_payload(user=request.user, range_current=r)

    # Sidebar / header context (existing management shell expectations)
    user_stats = get_user_stats(request.user)
    report_sent_today = has_report_today(request.user)
    reminders = get_reminders(request.user, stats=user_stats, report_sent=report_sent_today)
    progress_clients_pct = min(100, int(user_stats["processed_today"] / TARGET_CLIENTS_DAY * 100)) if TARGET_CLIENTS_DAY else 0
    progress_points_pct = min(100, int(user_stats["points_today"] / TARGET_POINTS_DAY * 100)) if TARGET_POINTS_DAY else 0

    return render(
        request,
        "management/stats.html",
        {
            "stats_payload": payload,
            "stats_owner": request.user,
            "is_admin_view": False,
            "range": payload.get("range", {}),
            "user_points_today": user_stats["points_today"],
            "user_points_total": user_stats["points_total"],
            "processed_today": user_stats["processed_today"],
            "target_clients": TARGET_CLIENTS_DAY,
            "target_points": TARGET_POINTS_DAY,
            "progress_clients_pct": progress_clients_pct,
            "progress_points_pct": progress_points_pct,
            "has_report_today": report_sent_today,
            "reminders": reminders,
            "manager_bot_username": get_manager_bot_username(),
        },
    )


@login_required(login_url="management_login")
def stats_admin_list(request):
    if not request.user.is_staff:
        return redirect("management_home")

    User = get_user_model()
    users = (
        User.objects.filter(is_active=True)
        .filter(Q(is_staff=True) | Q(userprofile__is_manager=True))
        .distinct()
        .order_by("username")
    )

    rows = []
    for u in users:
        last_login = u.last_login
        online = False
        last_login_local = None
        if last_login:
            last_login_local = timezone.localtime(last_login)
            online = (timezone.now() - last_login) <= timedelta(minutes=5)
        rows.append(
            {
                "id": u.id,
                "name": u.get_full_name() or u.username,
                "role": "Адмін" if u.is_staff else "Менеджер",
                "online": online,
                "last_login": last_login_local.strftime("%d.%m.%Y %H:%M") if last_login_local else "Немає даних",
                "first_seen": u.date_joined.strftime("%d.%m.%Y") if getattr(u, "date_joined", None) else "",
            }
        )

    # Sidebar context for admin viewer
    user_stats = get_user_stats(request.user)
    report_sent_today = has_report_today(request.user)
    reminders = get_reminders(request.user, stats=user_stats, report_sent=report_sent_today)
    progress_clients_pct = min(100, int(user_stats["processed_today"] / TARGET_CLIENTS_DAY * 100)) if TARGET_CLIENTS_DAY else 0
    progress_points_pct = min(100, int(user_stats["points_today"] / TARGET_POINTS_DAY * 100)) if TARGET_POINTS_DAY else 0

    return render(
        request,
        "management/stats_admin_list.html",
        {
            "admin_users": rows,
            "user_points_today": user_stats["points_today"],
            "user_points_total": user_stats["points_total"],
            "processed_today": user_stats["processed_today"],
            "target_clients": TARGET_CLIENTS_DAY,
            "target_points": TARGET_POINTS_DAY,
            "progress_clients_pct": progress_clients_pct,
            "progress_points_pct": progress_points_pct,
            "has_report_today": report_sent_today,
            "reminders": reminders,
            "manager_bot_username": get_manager_bot_username(),
        },
    )


@login_required(login_url="management_login")
def stats_admin_user(request, user_id: int):
    if not request.user.is_staff:
        return redirect("management_home")

    User = get_user_model()
    target = User.objects.filter(id=user_id, is_active=True).first()
    if not target:
        return redirect("management_stats_admin")

    r = parse_stats_range(request.GET)
    payload = get_stats_payload(user=target, range_current=r)

    # Sidebar context for admin viewer
    user_stats = get_user_stats(request.user)
    report_sent_today = has_report_today(request.user)
    reminders = get_reminders(request.user, stats=user_stats, report_sent=report_sent_today)
    progress_clients_pct = min(100, int(user_stats["processed_today"] / TARGET_CLIENTS_DAY * 100)) if TARGET_CLIENTS_DAY else 0
    progress_points_pct = min(100, int(user_stats["points_today"] / TARGET_POINTS_DAY * 100)) if TARGET_POINTS_DAY else 0

    return render(
        request,
        "management/stats.html",
        {
            "stats_payload": payload,
            "stats_owner": target,
            "is_admin_view": True,
            "range": payload.get("range", {}),
            "admin_back_url": "management_stats_admin",
            "user_points_today": user_stats["points_today"],
            "user_points_total": user_stats["points_total"],
            "processed_today": user_stats["processed_today"],
            "target_clients": TARGET_CLIENTS_DAY,
            "target_points": TARGET_POINTS_DAY,
            "progress_clients_pct": progress_clients_pct,
            "progress_points_pct": progress_points_pct,
            "has_report_today": report_sent_today,
            "reminders": reminders,
            "manager_bot_username": get_manager_bot_username(),
        },
    )


@login_required(login_url="management_login")
@require_POST
def activity_pulse(request):
    if not user_is_management(request.user):
        return JsonResponse({"ok": False}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    raw = payload.get("active_seconds")
    try:
        active_seconds = int(raw)
    except Exception:
        active_seconds = 0

    # Clamp to avoid abuse and to keep increments sane.
    active_seconds = max(0, min(active_seconds, 60))

    now = timezone.now()
    day = timezone.localdate(now)

    obj, _ = ManagementDailyActivity.objects.get_or_create(user=request.user, date=day)
    ManagementDailyActivity.objects.filter(pk=obj.pk).update(
        active_seconds=F("active_seconds") + active_seconds,
        last_seen_at=now,
    )

    return JsonResponse({"ok": True})


@login_required(login_url="management_login")
@require_POST
def advice_dismiss(request):
    if not user_is_management(request.user):
        return JsonResponse({"ok": False}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    key = str(payload.get("key") or "").strip()
    if not key or len(key) > 255:
        return JsonResponse({"ok": False, "error": "bad_key"}, status=400)

    expires_at = None
    exp_raw = payload.get("expires_at")
    if isinstance(exp_raw, str) and exp_raw.strip():
        try:
            dt_parsed = datetime.fromisoformat(exp_raw.replace("Z", "+00:00"))
            expires_at = timezone.make_aware(dt_parsed) if timezone.is_naive(dt_parsed) else dt_parsed
        except Exception:
            expires_at = None

    obj, _ = ManagementStatsAdviceDismissal.objects.get_or_create(user=request.user, key=key)
    obj.expires_at = expires_at
    obj.save(update_fields=["expires_at"])
    return JsonResponse({"ok": True})


@login_required(login_url="management_login")
@require_POST
def score_appeal_create(request):
    if not user_is_management(request.user):
        return JsonResponse({"success": False, "error": "Доступ заборонено."}, status=403)

    snapshot_id_raw = str(request.POST.get("snapshot_id") or "").strip()
    reason = (request.POST.get("reason") or "").strip()
    evidence_note = (request.POST.get("evidence_note") or "").strip()

    try:
        snapshot_id = int(snapshot_id_raw)
    except (TypeError, ValueError):
        return JsonResponse({"success": False, "error": "Некоректний snapshot."}, status=400)

    if not reason:
        return JsonResponse({"success": False, "error": "Опишіть причину апеляції."}, status=400)

    snapshot = NightlyScoreSnapshot.objects.filter(id=snapshot_id, owner=request.user).first()
    if not snapshot:
        return JsonResponse({"success": False, "error": "Snapshot не знайдено."}, status=404)

    appeal = (
        ScoreAppeal.objects.filter(owner=request.user, snapshot=snapshot, status=ScoreAppeal.Status.OPEN)
        .order_by("-created_at")
        .first()
    )
    if appeal:
        appeal.reason = reason
        appeal.evidence = {"note": evidence_note} if evidence_note else {}
        appeal.save(update_fields=["reason", "evidence"])
    else:
        appeal = ScoreAppeal.objects.create(
            owner=request.user,
            snapshot=snapshot,
            reason=reason,
            evidence={"note": evidence_note} if evidence_note else {},
        )

    return JsonResponse(
        {
            "success": True,
            "appeal": {
                "id": appeal.id,
                "status": appeal.status,
                "snapshot_id": snapshot.id,
                "snapshot_date": snapshot.snapshot_date.isoformat(),
            },
        }
    )


@login_required(login_url="management_login")
@require_POST
def score_appeal_resolve(request, appeal_id: int):
    if not request.user.is_staff:
        return JsonResponse({"success": False, "error": "Доступ лише для адміністраторів."}, status=403)

    status = (request.POST.get("status") or "").strip()
    resolution_note = (request.POST.get("resolution_note") or "").strip()
    if status not in {ScoreAppeal.Status.APPROVED, ScoreAppeal.Status.REJECTED}:
        return JsonResponse({"success": False, "error": "Некоректний статус рішення."}, status=400)

    appeal = ScoreAppeal.objects.select_related("owner", "snapshot").filter(id=appeal_id).first()
    if not appeal:
        return JsonResponse({"success": False, "error": "Апеляцію не знайдено."}, status=404)

    appeal.mark_resolved(status=status, resolution_note=resolution_note)
    SupervisorActionLog.objects.create(
        manager=appeal.owner,
        actor=request.user,
        action_type=SupervisorActionLog.ActionType.APPEAL_RESOLUTION,
        payload={
            "appeal_id": appeal.id,
            "snapshot_id": appeal.snapshot_id,
            "status": status,
        },
    )
    return JsonResponse(
        {
            "success": True,
            "appeal": {
                "id": appeal.id,
                "status": appeal.status,
                "resolved_at": timezone.localtime(appeal.resolved_at).isoformat() if appeal.resolved_at else "",
            },
        }
    )
