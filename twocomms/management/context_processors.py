from __future__ import annotations

from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from management.models import Client, DuplicateReview, NightlyScoreSnapshot
from management.services.roster import management_role_label


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
    today_callbacks = Client.objects.filter(owner=user, next_call_at__date=today).count()
    missed_callbacks = Client.objects.filter(owner=user, next_call_at__isnull=False, next_call_at__date__lt=today).count()
    duplicate_reviews_qs = DuplicateReview.objects.filter(status=DuplicateReview.Status.OPEN)
    if not (getattr(user, "is_staff", False) and not getattr(profile, "is_manager", False)):
        duplicate_reviews_qs = duplicate_reviews_qs.filter(owner=user)
    duplicate_reviews = duplicate_reviews_qs.count()

    return {
        "management_shell_daily_zone": daily_zone,
        "management_shell_processed_today": processed_today,
        "management_shell_processed_total": processed_total,
        "management_shell_mosaic_label": mosaic_label,
        "management_shell_mosaic_ready": mosaic_ready,
        "management_shell_mosaic_meta": mosaic_meta,
        "management_shell_today_callbacks": today_callbacks,
        "management_shell_missed_callbacks": missed_callbacks,
        "management_shell_duplicate_reviews": duplicate_reviews,
        "management_shell_secondary_counts": {
            "today_callbacks": today_callbacks,
            "missed_callbacks": missed_callbacks,
            "duplicate_reviews": duplicate_reviews,
        },
    }


def management_shell_context(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}

    try:
        profile = user.userprofile
    except Exception:
        profile = None

    if not (getattr(user, "is_staff", False) or getattr(profile, "is_manager", False)):
        return {}

    try:
        stats_url = reverse("management_stats_admin" if user.is_staff and not getattr(profile, "is_manager", False) else "management_stats")
    except NoReverseMatch:
        stats_url = ""

    return {
        "management_shell_role_label": management_role_label(user),
        "management_shell_stats_url": stats_url,
        **build_management_shell_metrics(user, profile),
    }
