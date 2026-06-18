from __future__ import annotations

from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.utils import timezone

from management.models import CallAIAnalysis, CallRecord, TelephonyHealthSnapshot
from management.services.config_versions import get_management_config
from management.services.ui_labels import translate_telephony_status


MEANINGFUL_CALL_SECONDS = 30


def build_call_quality_signal(
    owner,
    as_of_date,
    *,
    window_days: int = 30,
    target_meaningful: int = 10,
) -> dict:
    """Date-scoped сигнал якості дзвінків менеджера для осі verified_communication.

    Вікно [as_of_date-(window-1); as_of_date] по created_at (надійніше за
    started_at, що буває null). Повертає vc_real у [0..1] АБО None, якщо у вікні
    немає значущих дзвінків — тоді вісь падає на легасі success_rate-проксі
    (нуль регресу для тих, хто ще не дзвонить).

    vc_real = 0.6*qa_quality + 0.4*call_presence, де
      qa_quality   = середній overall_score завершених ШІ-аналізів / 100,
      call_presence = min(1, meaningful_calls / target).
    Якщо аналізів ще немає — vc_real = call_presence (мʼяко, поки черга догоняє).
    """
    if not owner or not as_of_date:
        return {"has_calls": False, "meaningful_calls": 0, "analyzed_count": 0,
                "qa_quality": None, "call_presence": 0.0, "vc_real": None}
    start = as_of_date - timedelta(days=max(0, window_days - 1))
    base_qs = CallRecord.objects.filter(
        manager=owner, created_at__date__gte=start, created_at__date__lte=as_of_date
    )
    meaningful = base_qs.filter(duration_seconds__gte=MEANINGFUL_CALL_SECONDS).count()
    if meaningful <= 0:
        return {"has_calls": False, "meaningful_calls": 0, "analyzed_count": 0,
                "qa_quality": None, "call_presence": 0.0, "vc_real": None}

    agg = CallAIAnalysis.objects.filter(
        status=CallAIAnalysis.Status.DONE,
        call_record__manager=owner,
        call_record__created_at__date__gte=start,
        call_record__created_at__date__lte=as_of_date,
    ).aggregate(avg=Avg("overall_score"), n=Count("id"))
    analyzed_count = int(agg["n"] or 0)
    qa_quality = (float(agg["avg"]) / 100.0) if agg["avg"] is not None else None

    target = max(1, int(target_meaningful or 10))
    call_presence = min(1.0, meaningful / float(target))
    if qa_quality is not None:
        vc_real = round(0.6 * qa_quality + 0.4 * call_presence, 4)
    else:
        vc_real = round(call_presence, 4)
    return {
        "has_calls": True,
        "meaningful_calls": meaningful,
        "analyzed_count": analyzed_count,
        "qa_quality": round(qa_quality, 4) if qa_quality is not None else None,
        "call_presence": round(call_presence, 4),
        "vc_real": vc_real,
    }


def _resolve_freshness_seconds(latest: TelephonyHealthSnapshot | None) -> int:
    if not latest:
        return 0
    meta = latest.meta or {}
    meta_freshness = meta.get("freshness_seconds")
    if meta_freshness not in (None, ""):
        try:
            return max(0, int(meta_freshness))
        except (TypeError, ValueError):
            pass
    snapshot_at = getattr(latest, "snapshot_at", None)
    if not snapshot_at:
        return 0
    return max(0, int((timezone.now() - snapshot_at).total_seconds()))


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
        "status_label": translate_telephony_status(provider_status),
        "provider": latest.provider if latest else "aggregate",
        "freshness_seconds": _resolve_freshness_seconds(latest),
        "backlog_count": int(latest.backlog_count or 0) if latest else 0,
        "unmatched_ratio": unmatched_ratio,
        "missing_recording_ratio": missing_recording_ratio,
        "total_calls": total_calls,
        "meaningful_calls": meaningful_calls,
        "meaningful_call_seconds": meaningful_seconds,
        "punitively_available": punitively_available,
        "incident_keys": incident_keys,
    }
