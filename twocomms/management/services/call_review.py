"""
Адмін-огляд дзвінків менеджера (Фаза 5).

Для адмін-перегляду статистики менеджера збирає його дзвінки з ШІ-оцінкою,
вердиктом, розбіжностями (та фактом підтвердження менеджером) і доступом до
прослуховування запису. На відміну від менеджерського вигляду — ТУТ бали
показуються (це інструмент контролю для адміна).
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Prefetch
from django.utils import timezone

from management.models import CallAIAnalysis, CallRecord, ManagerNotification

DEFAULT_LIMIT = 40


def _verdict_label(v: str) -> str:
    return {
        "pass": "Сильна розмова",
        "coaching": "Потрібен коучинг",
        "fail": "Слабка розмова",
    }.get(v, "Невизначено")


def build_admin_call_review(manager, limit: int = DEFAULT_LIMIT) -> dict:
    analyses_qs = CallAIAnalysis.objects.order_by("-created_at").prefetch_related(
        Prefetch("notifications", queryset=ManagerNotification.objects.filter(requires_ack=True))
    )
    records = list(
        CallRecord.objects.filter(manager=manager)
        .select_related("matched_client")
        .prefetch_related(Prefetch("ai_analyses", queryset=analyses_qs))
        .order_by("-started_at", "-created_at")[:limit]
    )

    calls = []
    score_sum = Decimal("0")
    analyzed = 0
    with_discrepancies = 0
    fails = 0
    pending = 0
    for r in records:
        analysis = None
        for an in r.ai_analyses.all():
            if an.status == CallAIAnalysis.Status.DONE:
                analysis = an
                break
        recordable = (r.payload or {}).get("disposition", "").upper() in {"ANSWER", "VM-SUCCESS", "SUCCESS", "TRANSFER"}
        item = {
            "id": r.id,
            "client_id": r.matched_client_id,
            "client_name": r.matched_client.shop_name if r.matched_client_id else (r.phone or "—"),
            "started_at": timezone.localtime(r.started_at).strftime("%d.%m.%Y %H:%M") if r.started_at else "",
            "duration": r.duration_seconds,
            "direction": r.direction,
            "has_recording": bool(r.external_call_id) and recordable,
            "recording_url": f"/api/call/recording/{r.id}.mp3" if r.external_call_id else "",
            "ai_status": r.ai_status,
            "analysis": None,
        }
        if r.ai_status == CallRecord.AiStatus.PENDING or r.ai_status == CallRecord.AiStatus.RUNNING:
            pending += 1
        if analysis:
            analyzed += 1
            score_sum += analysis.overall_score
            disc = analysis.discrepancies or []
            if disc:
                with_discrepancies += 1
            if analysis.verdict == "fail":
                fails += 1
            # підтвердження менеджером (ack)
            ack_exists = False
            ack_done = False
            for n in analysis.notifications.all():
                ack_exists = True
                if n.acknowledged_at:
                    ack_done = True
            item["analysis"] = {
                "overall_score": float(analysis.overall_score),
                "verdict": analysis.verdict,
                "verdict_label": _verdict_label(analysis.verdict),
                "summary": analysis.summary,
                "discrepancies": disc,
                "discrepancy_acknowledged": ack_done if ack_exists else None,
                "axes": analysis.axes or [],
                "recommendations": analysis.recommendations or [],
            }
        calls.append(item)

    avg = round(float(score_sum) / analyzed, 1) if analyzed else None
    return {
        "calls": calls,
        "summary": {
            "total": len(records),
            "analyzed": analyzed,
            "avg_score": avg,
            "with_discrepancies": with_discrepancies,
            "fails": fails,
            "pending": pending,
        },
    }
