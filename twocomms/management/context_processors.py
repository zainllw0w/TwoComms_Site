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

    return {
        "management_shell_role_label": management_role_label(user),
        "management_shell_stats_url": stats_url,
        **build_management_shell_metrics(user, profile),
    }
