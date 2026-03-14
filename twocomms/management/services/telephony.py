from __future__ import annotations

from management.models import CallRecord, TelephonyHealthSnapshot
from management.services.config_versions import get_management_config


def build_telephony_health_summary(*, owner=None) -> dict:
    qs = TelephonyHealthSnapshot.objects.order_by("-snapshot_at")
    latest = qs.first()
    config = get_management_config().get("telephony_config") or {}
    thresholds = config.get("health_thresholds") or {}
    meaningful_seconds = int(config.get("meaningful_call_seconds") or 30)
    owner_calls = CallRecord.objects.filter(manager=owner) if owner else CallRecord.objects.all()
    matched_calls = owner_calls.exclude(manager__isnull=True).count()
    total_calls = owner_calls.count()
    meaningful_calls = owner_calls.filter(duration_seconds__gte=meaningful_seconds).count()
    missing_recording_ratio = (
        0.0
        if total_calls <= 0
        else round(owner_calls.filter(recording_url="").count() / total_calls, 4)
    )
    unmatched_ratio = 0.0 if total_calls <= 0 else round((total_calls - matched_calls) / total_calls, 4)
    provider_status = latest.status if latest else TelephonyHealthSnapshot.Status.DEGRADED
    warn_unmatched = float(thresholds.get("unmatched_ratio_warn", 0.15) or 0.15)
    warn_backlog = int(thresholds.get("backlog_warn", 5) or 5)
    warn_missing_recording = float(thresholds.get("missing_recording_warn", 0.20) or 0.20)
    backlog_ok = bool(latest) and int(latest.backlog_count or 0) <= warn_backlog
    punitively_available = (
        provider_status == TelephonyHealthSnapshot.Status.HEALTHY
        and unmatched_ratio <= warn_unmatched
        and backlog_ok
        and missing_recording_ratio <= warn_missing_recording
    )
    incident_keys = []
    if provider_status != TelephonyHealthSnapshot.Status.HEALTHY:
        incident_keys.append("TELEPHONY_OUTAGE")
    if unmatched_ratio > warn_unmatched:
        incident_keys.append("TELEPHONY_UNMATCHED")
    if latest and int(latest.backlog_count or 0) > warn_backlog:
        incident_keys.append("TELEPHONY_BACKLOG")
    return {
        "status": provider_status,
        "provider": latest.provider if latest else "aggregate",
        "freshness_seconds": int(latest.freshness_seconds or 0) if latest else 0,
        "backlog_count": int(latest.backlog_count or 0) if latest else 0,
        "unmatched_ratio": unmatched_ratio,
        "missing_recording_ratio": missing_recording_ratio,
        "total_calls": total_calls,
        "meaningful_calls": meaningful_calls,
        "meaningful_call_seconds": meaningful_seconds,
        "punitively_available": punitively_available,
        "incident_keys": incident_keys,
    }
