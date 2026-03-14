from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef, Q

from management.models import ManagementDailyActivity, Report


def _with_management_history(queryset):
    report_exists = Report.objects.filter(owner=OuterRef("pk"))
    activity_exists = ManagementDailyActivity.objects.filter(user=OuterRef("pk"))
    return queryset.annotate(
        has_report_history=Exists(report_exists),
        has_activity_history=Exists(activity_exists),
    )


def manager_roster_queryset(*, include_staff: bool = False, include_excluded: bool = True):
    user_model = get_user_model()
    queryset = _with_management_history(user_model.objects.filter(is_active=True).select_related("userprofile"))
    eligibility = Q(userprofile__is_manager=True)
    if include_excluded:
        eligibility |= Q(has_report_history=True) | Q(has_activity_history=True)
    if include_staff:
        eligibility |= Q(is_staff=True)
    return queryset.filter(eligibility).distinct().order_by("username")


def management_subjects_queryset():
    return manager_roster_queryset(include_staff=True, include_excluded=True)


def management_role_label(user) -> str:
    if user.is_staff and not getattr(getattr(user, "userprofile", None), "is_manager", False):
        return "Адмін"
    if getattr(getattr(user, "userprofile", None), "is_manager", False):
        return "Менеджер"
    if getattr(user, "has_report_history", False) or getattr(user, "has_activity_history", False):
        return "Виключений менеджер"
    return "Користувач"
