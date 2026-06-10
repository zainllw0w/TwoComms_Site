from __future__ import annotations

from django.core.exceptions import DisallowedHost
from django.db.models import Prefetch
from django.db.models import Q
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from management.models import Client, ClientFollowUp, DuplicateReview, NightlyScoreSnapshot
from management.services.followup_state import get_effective_callback_state
from management.services.payouts import get_manager_payout_summary
from management.services.roster import management_role_label


def _is_management_host(request):
    try:
        host = request.get_host().split(":")[0].lower()
    except DisallowedHost:
        return False
    return host.startswith("management.")


def build_management_shell_metrics(user, profile=None):
    today = timezone.localdate()
    processed_today = Client.objects.filter(owner=user, created_at__date=today).count()
    processed_total = Client.objects.filter(owner=user).count()
    if processed_today < 20:
        daily_zone = "danger"
    elif processed_today < 50:
        daily_zone = "warning"
    else:
        daily_zone = "success"

    latest_snapshot = NightlyScoreSnapshot.objects.filter(owner=user).order_by("-snapshot_date").first()
    mosaic_score = float(latest_snapshot.mosaic_score or 0) if latest_snapshot else None
    mosaic_ready = processed_total >= 20 and mosaic_score is not None
    mosaic_label = f"{mosaic_score:.1f}" if mosaic_ready else "Накопичуємо дані"
    mosaic_meta = "Shadow-індикатор темпу та якості." if mosaic_ready else "Потрібно щонайменше 20 обробок для стабільного показу."
    callback_clients = (
        Client.objects.filter(
            Q(owner=user),
            Q(next_call_at__isnull=False) | Q(followups__status=ClientFollowUp.Status.OPEN),
        )
        .distinct()
        .prefetch_related(
            Prefetch(
                "followups",
                queryset=ClientFollowUp.objects.filter(status=ClientFollowUp.Status.OPEN).order_by("-due_at"),
                to_attr="prefetched_open_followups",
            )
        )
    )
    now = timezone.localtime(timezone.now())
    today_callbacks = 0
    urgent_callbacks = 0
    missed_callbacks = 0
    for client in callback_clients:
        state = get_effective_callback_state(client=client, now_dt=now)
        if state.code == "missed":
            missed_callbacks += 1
        elif state.code == "due_now":
            urgent_callbacks += 1
            if state.due_at and state.due_at.date() == today:
                today_callbacks += 1
        elif state.code in {"scheduled", "due_now"} and state.due_at and state.due_at.date() == today:
            today_callbacks += 1
    duplicate_reviews_qs = DuplicateReview.objects.filter(status=DuplicateReview.Status.OPEN)
    if not (getattr(user, "is_staff", False) and not getattr(profile, "is_manager", False)):
        duplicate_reviews_qs = duplicate_reviews_qs.filter(owner=user)
    duplicate_reviews = duplicate_reviews_qs.count()
    payout_summary = get_manager_payout_summary(user)
    try:
        payout_url = reverse("management_payouts")
    except NoReverseMatch:
        payout_url = ""

    return {
        "management_shell_daily_zone": daily_zone,
        "management_shell_processed_today": processed_today,
        "management_shell_processed_total": processed_total,
        "management_shell_mosaic_label": mosaic_label,
        "management_shell_mosaic_ready": mosaic_ready,
        "management_shell_mosaic_meta": mosaic_meta,
        "management_shell_today_callbacks": today_callbacks,
        "management_shell_urgent_callbacks": urgent_callbacks,
        "management_shell_missed_callbacks": missed_callbacks,
        "management_shell_duplicate_reviews": duplicate_reviews,
        "management_shell_payout_available": payout_summary["available"],
        "management_shell_has_active_payout_request": payout_summary["has_active_request"],
        "management_shell_payout_url": payout_url,
        "management_shell_secondary_counts": {
            "today_callbacks": today_callbacks,
            "urgent_callbacks": urgent_callbacks,
            "missed_callbacks": missed_callbacks,
            "duplicate_reviews": duplicate_reviews,
        },
    }


def build_management_shell_career(user):
    """Дані про кар'єрний прогрес менеджера для шапки модалки профілю.

    Повертає горизонтальний степпер усіх рівнів зі статусами та прогрес до
    наступного рівня (з умовами). Усе загорнуто в try/except, щоб помилка не
    зламала рендер shell на будь-якій сторінці менеджменту.
    """
    empty = {
        "management_shell_career_ready": False,
        "management_shell_levels": [],
        "management_shell_next_level_label": "",
        "management_shell_progress_pct": 0,
        "management_shell_progress_conditions": [],
        "management_shell_progress_manual": False,
        "management_shell_is_max_level": False,
    }
    try:
        from management.services.manager_levels import (
            get_current_level,
            get_level_display_name,
            LEVEL_HIERARCHY,
        )
        from management.services.level_progression import (
            get_progression_status,
            get_next_level_requirements,
        )

        level_obj = get_current_level(user)
        if not level_obj:
            return empty

        current_code = level_obj.level
        current_rank = LEVEL_HIERARCHY.get(current_code, 0)

        # Короткі підписи для компактного степпера.
        short_labels = {
            "candidate": "Кандидат",
            "level_1": "Менеджер I",
            "level_2": "Менеджер II",
            "top_manager": "Топ",
            "project_manager": "Project",
            "admin": "Адмін",
        }
        order = sorted(LEVEL_HIERARCHY.items(), key=lambda kv: kv[1])
        levels = []
        for code, rank in order:
            if rank < current_rank:
                status = "completed"
            elif rank == current_rank:
                status = "current"
            else:
                status = "locked"
            levels.append({
                "code": code,
                "name": get_level_display_name(code),
                "short": short_labels.get(code, get_level_display_name(code)),
                "status": status,
                "order": rank,
            })

        progression = get_progression_status(user)
        requirements = get_next_level_requirements(current_code)
        next_code = progression.get("next_level")
        is_max = next_code is None
        manual = bool(requirements) and not requirements.get("auto_check", False)

        conditions = []
        for cond in progression.get("conditions", []) or []:
            conditions.append({
                "label": cond.get("description", ""),
                "current": cond.get("current", 0),
                "target": cond.get("target", 0),
                "pct": cond.get("progress_pct", 0),
                "is_met": cond.get("is_met", False),
            })

        return {
            "management_shell_career_ready": True,
            "management_shell_levels": levels,
            "management_shell_next_level_label": get_level_display_name(next_code) if next_code else "",
            "management_shell_progress_pct": progression.get("progress_pct", 0),
            "management_shell_progress_conditions": conditions,
            "management_shell_progress_manual": manual,
            "management_shell_is_max_level": is_max,
        }
    except Exception:
        return empty


def management_shell_context(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    if not _is_management_host(request):
        return {}

    try:
        profile = user.userprofile
    except Exception:
        profile = None

    if not (getattr(user, "is_staff", False) or getattr(profile, "is_manager", False)):
        return {}

    try:
        # The profile shortcut must always open the current user's own stats page,
        # not the admin-wide manager list.
        stats_url = reverse("management_stats")
    except NoReverseMatch:
        stats_url = ""

    # Рівень менеджера для відображення в sidebar
    try:
        from management.services.manager_levels import get_current_level, get_level_display_name
        level_obj = get_current_level(user)
        level_label = get_level_display_name(level_obj.level) if level_obj else ""
        level_code = level_obj.level if level_obj else ""
    except Exception:
        level_label = ""
        level_code = ""

    # In-app сповіщення (дзвіночок)
    notifications = []
    notifications_unread = 0
    try:
        from management.models import ManagerNotification
        qs = ManagerNotification.objects.filter(user=user).order_by("-created_at")
        notifications_unread = qs.filter(is_read=False).count()
        notifications = list(qs[:15])
    except Exception:
        notifications = []
        notifications_unread = 0

    return {
        "management_shell_role_label": management_role_label(user),
        "management_shell_stats_url": stats_url,
        "management_shell_level_label": level_label,
        "management_shell_level_code": level_code,
        "management_notifications": notifications,
        "management_notifications_unread": notifications_unread,
        **build_management_shell_career(user),
        **build_management_shell_metrics(user, profile),
    }
