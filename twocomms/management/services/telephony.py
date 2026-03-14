from __future__ import annotations

from management.models import CallRecord, TelephonyHealthSnapshot


def build_telephony_health_summary(*, owner=None) -> dict:
    qs = TelephonyHealthSnapshot.objects.order_by("-snapshot_at")
    latest = qs.first()
    owner_calls = CallRecord.objects.filter(manager=owner) if owner else CallRecord.objects.all()
    matched_calls = owner_calls.exclude(manager__isnull=True).count()
    total_calls = owner_calls.count()
    unmatched_ratio = 0.0 if total_calls <= 0 else round((total_calls - matched_calls) / total_calls, 4)
    return {
        "status": latest.status if latest else TelephonyHealthSnapshot.Status.DEGRADED,
        "provider": latest.provider if latest else "aggregate",
        "freshness_seconds": int(latest.freshness_seconds or 0) if latest else 0,
        "backlog_count": int(latest.backlog_count or 0) if latest else 0,
        "unmatched_ratio": unmatched_ratio,
        "total_calls": total_calls,
    }
