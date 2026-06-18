"""
Адмін-перегляд обробок менеджера (детально, за днями).

Дає адміну подивитися все, що менеджер реально обробляв (а не лише звіти):
кожен клієнт за обраний день/період з повними деталями (нотатка, причина,
докази, фази передзвонів), записами дзвінків (+ШІ-вердикт) і денним підсумком
із прогресом/регресом відносно попереднього дня. Плюс тренд MOSAIC.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from django.utils import timezone

from management.lead_services import client_points_value
from management.models import (
    CallAIAnalysis,
    CallRecord,
    Client,
    ClientInteractionAttempt,
    NightlyScoreSnapshot,
)

CONVERSION_RESULTS = {Client.CallResult.ORDER, Client.CallResult.TEST_BATCH}
RECORDABLE = {"ANSWER", "VM-SUCCESS", "SUCCESS", "TRANSFER"}


def _date_bounds(start_d: date, end_d: date) -> tuple:
    """Межі [start_d 00:00, end_d+1 00:00) у локальній TZ як aware datetimes.

    ВАЖЛИВО: не використовуємо lookup `__date`. На проді (MySQL без завантажених
    timezone-таблиць) `__date` з USE_TZ генерує CONVERT_TZ(..., 'UTC', tz), який
    повертає NULL → фільтр випадає в нуль рядків (звідси баг «за сьогодні 0»,
    хоча «весь час» показує клієнтів). Порівняння діапазону datetime працює
    скрізь однаково.
    """
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_d, datetime.min.time()), tz)
    end_dt = timezone.make_aware(datetime.combine(end_d + timedelta(days=1), datetime.min.time()), tz)
    return start_dt, end_dt


def _created_client_ids(manager, start: date, end: date) -> set[int]:
    """Клієнти, СТВОРЕНІ менеджером у вікні (нові обробки/фази)."""
    start_dt, end_dt = _date_bounds(start, end)
    return set(
        Client.objects.filter(
            owner=manager, created_at__gte=start_dt, created_at__lt=end_dt
        ).values_list("id", flat=True)
    )


def _reengaged_client_ids(manager, start: date, end: date, exclude: set[int]) -> set[int]:
    """Клієнти, з якими була активність у вікні (дзвінок або спроба контакту),
    але створені РАНІШЕ за вікно. Саме через них раніше зникали дзвінки «за
    сьогодні»: картку додали давно, а дзвінок/контакт стався сьогодні.
    """
    start_dt, end_dt = _date_bounds(start, end)
    call_ids = set(
        CallRecord.objects.filter(
            manager=manager,
            matched_client__owner=manager,
            started_at__gte=start_dt,
            started_at__lt=end_dt,
        ).values_list("matched_client_id", flat=True)
    )
    call_ids.discard(None)
    attempt_ids = set(
        ClientInteractionAttempt.objects.filter(
            client__owner=manager,
            created_at__gte=start_dt,
            created_at__lt=end_dt,
        ).values_list("client_id", flat=True)
    )
    return (call_ids | attempt_ids) - exclude


def resolve_review_window(period: str, date_str: str, today: date) -> dict:
    """Повертає опис вікна перегляду: межі дат, лейбл, режим, попередній день."""
    period = (period or "").strip().lower()
    explicit = None
    if date_str:
        try:
            explicit = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            explicit = None

    if explicit:
        return {"start": explicit, "end": explicit, "label": explicit.strftime("%d.%m.%Y"),
                "mode": "day", "single_day": explicit, "key": "date", "date_value": explicit.isoformat()}
    if period == "yesterday":
        d = today - timedelta(days=1)
        return {"start": d, "end": d, "label": "Вчора", "mode": "day", "single_day": d, "key": "yesterday"}
    if period == "week":
        return {"start": today - timedelta(days=6), "end": today, "label": "Останні 7 днів",
                "mode": "range", "single_day": None, "key": "week"}
    if period == "all":
        return {"start": None, "end": None, "label": "Весь час", "mode": "all", "single_day": None, "key": "all"}
    # default: today
    return {"start": today, "end": today, "label": "Сьогодні", "mode": "day", "single_day": today, "key": "today"}


def _day_summary(manager, day: date) -> dict:
    start_dt, end_dt = _date_bounds(day, day)
    qs = Client.objects.filter(owner=manager, created_at__gte=start_dt, created_at__lt=end_dt)
    rows = list(qs)
    processed = len(rows)
    points = sum(client_points_value(c) for c in rows)
    conversions = sum(1 for c in rows if c.call_result in CONVERSION_RESULTS)
    return {"processed": processed, "points": points, "conversions": conversions}


def _delta(curr: int, prev: int) -> dict:
    diff = curr - prev
    tone = "neutral" if diff == 0 else ("good" if diff > 0 else "bad")
    arrow = "→" if diff == 0 else ("▲" if diff > 0 else "▼")
    return {"diff": diff, "tone": tone, "arrow": arrow, "prev": prev}


def build_mosaic_trend(manager, days: int = 7) -> dict:
    snaps = list(
        NightlyScoreSnapshot.objects.filter(owner=manager)
        .order_by("-snapshot_date")[:days]
    )
    snaps.reverse()  # хронологічно
    series = [{"date": s.snapshot_date.strftime("%d.%m"), "score": float(s.mosaic_score)} for s in snaps]
    latest = series[-1]["score"] if series else None
    direction = {"tone": "neutral", "label": "Накопичуємо дані", "arrow": "→"}
    if len(series) >= 2:
        diff = series[-1]["score"] - series[0]["score"]
        if diff >= 1:
            direction = {"tone": "good", "label": f"Зростання +{round(diff,1)}", "arrow": "▲"}
        elif diff <= -1:
            direction = {"tone": "bad", "label": f"Спад {round(diff,1)}", "arrow": "▼"}
        else:
            direction = {"tone": "neutral", "label": "Стабільно", "arrow": "→"}
    return {"series": series, "latest": latest, "direction": direction}


def _evidence_summary(ctx: dict) -> list[str]:
    out = []
    if not isinstance(ctx, dict):
        return out
    if ctx.get("cp_recipient_email"):
        out.append(f"КП: {ctx['cp_recipient_email']}")
    if ctx.get("messenger_type"):
        out.append(f"Месенджер: {ctx.get('messenger_type')} · {ctx.get('messenger_target_value', '')}".strip())
    if ctx.get("xml_platform") or ctx.get("xml_resource_url"):
        out.append(f"XML: {ctx.get('xml_platform', '')} {ctx.get('xml_resource_url', '')}".strip())
    if ctx.get("linked_shop_name"):
        out.append(f"Магазин: {ctx['linked_shop_name']}")
    if ctx.get("duplicate_override_reason"):
        out.append(f"Override дубля: {ctx['duplicate_override_reason']}")
    return out


def _calls_for_clients(client_ids: list[int], window: dict | None = None) -> dict[int, list]:
    if not client_ids:
        return {}
    records = (
        CallRecord.objects.filter(matched_client_id__in=client_ids)
        .prefetch_related("ai_analyses")
        .order_by("-started_at", "-created_at")
    )
    # Для денних/діапазонних вікон показуємо дзвінки саме цього періоду —
    # так «Сьогодні» показує сьогоднішні розмови, а не всю історію.
    # Записи без started_at (ще не збагачені вебхуком) лишаємо — вони привʼязані
    # до клієнта цього вікна.
    if window and window.get("start") and window.get("end"):
        from django.db.models import Q
        start_dt, end_dt = _date_bounds(window["start"], window["end"])
        records = records.filter(
            Q(started_at__isnull=True)
            | Q(started_at__gte=start_dt, started_at__lt=end_dt)
        )
    grouped: dict[int, list] = {}
    for r in records:
        analysis = None
        for an in r.ai_analyses.all():
            if an.status == CallAIAnalysis.Status.DONE:
                analysis = an
                break
        recordable = (r.payload or {}).get("disposition", "").upper() in RECORDABLE
        item = {
            "id": r.id,
            "started_at": timezone.localtime(r.started_at).strftime("%d.%m.%Y %H:%M") if r.started_at else "",
            "duration": r.duration_seconds,
            "direction": r.direction,
            "has_recording": bool(r.external_call_id) and recordable,
            "recording_url": f"/api/call/recording/{r.id}.mp3" if r.external_call_id else "",
            "ai_status": r.ai_status,
            "ai": None,
        }
        if analysis:
            item["ai"] = {
                "overall_score": float(analysis.overall_score),
                "verdict": analysis.verdict,
                "verdict_label": analysis.get_verdict_display(),
                "summary": analysis.summary,
                "discrepancies": analysis.discrepancies or [],
                "axes": analysis.axes or [],
            }
        grouped.setdefault(r.matched_client_id, []).append(item)
    return grouped


def _discrepancy_ack_map(client_ids: list[int]) -> dict[int, dict]:
    """Стан підтвердження розбіжностей по клієнтах (для адмін-перегляду):
    бачив менеджер модалку чи ні, підтвердив чи ні."""
    if not client_ids:
        return {}
    from management.models import ManagerNotification
    notifs = (
        ManagerNotification.objects.filter(requires_ack=True, related_client_id__in=client_ids)
        .order_by("related_client_id", "-created_at")
    )
    out: dict[int, dict] = {}
    for n in notifs:
        cid = n.related_client_id
        slot = out.setdefault(cid, {"state": "ack", "seen": False, "_pending": False})
        if n.acknowledged_at is None:
            slot["_pending"] = True
        if n.is_read:
            slot["seen"] = True
    for slot in out.values():
        slot["state"] = "pending" if slot["_pending"] else "ack"
        slot.pop("_pending", None)
    return out


def _serialize_review_client(c: Client, calls: list, *, reengaged: bool = False, ack_info: dict | None = None) -> dict:
    attempts = []
    for a in c.interaction_attempts.all():
        attempts.append({
            "result": a.get_result_display() if hasattr(a, "get_result_display") else a.result,
            "reason_note": a.reason_note or "",
            "details": a.details or "",
            "next_call": timezone.localtime(a.next_call_at).strftime("%d.%m.%Y %H:%M") if a.next_call_at else "",
            "created": timezone.localtime(a.created_at).strftime("%d.%m.%Y %H:%M") if a.created_at else "",
            "verification": a.get_verification_level_display() if hasattr(a, "get_verification_level_display") else "",
        })
    ctx = c.call_result_context or {}
    test_batch = None
    if c.call_result == Client.CallResult.TEST_BATCH:
        test_batch = {
            "shop": ctx.get("linked_shop_name") or "",
            "ordered_at": timezone.localtime(c.created_at).strftime("%d.%m.%Y") if c.created_at else "",
        }
    # Зведення по дзвінках: розбіжності + найкращий ШІ-бал (для шапки картки).
    discrepancy_count = 0
    best_score = None
    analyzed_calls = 0
    for call in calls:
        ai = call.get("ai") if isinstance(call, dict) else None
        if ai:
            analyzed_calls += 1
            discrepancy_count += len(ai.get("discrepancies") or [])
            sc = ai.get("overall_score")
            if sc is not None and (best_score is None or sc > best_score):
                best_score = sc
    return {
        "id": c.id,
        "shop": c.shop_name,
        "phone": c.phone,
        "full_name": c.full_name,
        "role": c.get_role_display(),
        "source": c.source or "",
        "result": c.get_call_result_display(),
        "result_code": c.call_result,
        "result_group": _result_group(c.call_result),
        "points": client_points_value(c),
        "manager_note": c.manager_note or "",
        "reason_note": c.call_result_reason_note or "",
        "details": c.call_result_details or "",
        "evidence": _evidence_summary(ctx),
        "phase_number": c.phase_number or 1,
        "test_batch": test_batch,
        "reengaged": reengaged,
        "discrepancy_count": discrepancy_count,
        "has_discrepancy": discrepancy_count > 0,
        "discrepancy_admin": ({"state": ack_info.get("state"), "seen": bool(ack_info.get("seen"))} if ack_info else None),
        "best_score": best_score,
        "analyzed_calls": analyzed_calls,
        "next_call": timezone.localtime(c.next_call_at).strftime("%d.%m.%Y %H:%M") if c.next_call_at else "",
        "created": timezone.localtime(c.created_at).strftime("%d.%m.%Y %H:%M") if c.created_at else "",
        "attempts": attempts,
        "calls": calls,
    }


def _result_group(code: str) -> str:
    """Категорія підсумку для кольорового кодування карток."""
    if code in CONVERSION_RESULTS:
        return "conversion"
    if code in {
        Client.CallResult.NOT_INTERESTED,
        Client.CallResult.INVALID_NUMBER,
        Client.CallResult.EXPENSIVE,
    }:
        return "lost"
    if code in {
        Client.CallResult.NO_ANSWER,
        Client.CallResult.THINKING,
        Client.CallResult.WAITING_PAYMENT,
        Client.CallResult.WAITING_PREPAYMENT,
    }:
        return "pending"
    return "neutral"


def build_manager_clients_review(manager, *, period: str = "today", date_str: str = "") -> dict:
    today = timezone.localdate()
    window = resolve_review_window(period, date_str, today)
    bounded = bool(window["start"] and window["end"])

    qs = Client.objects.filter(owner=manager).prefetch_related("interaction_attempts").order_by("-created_at")
    if bounded:
        start_dt, end_dt = _date_bounds(window["start"], window["end"])
        qs = qs.filter(created_at__gte=start_dt, created_at__lt=end_dt)
    rows = list(qs[:500])

    # Клієнти з активністю за період, але створені раніше (передзвони/повторні
    # дзвінки) — раніше вони повністю випадали з перегляду «за сьогодні».
    reengaged_rows: list[Client] = []
    if bounded:
        created_ids = {c.id for c in rows}
        reeng_ids = _reengaged_client_ids(manager, window["start"], window["end"], created_ids)
        if reeng_ids:
            reengaged_rows = list(
                Client.objects.filter(id__in=reeng_ids)
                .prefetch_related("interaction_attempts")
                .order_by("-updated_at")[:200]
            )

    all_ids = [c.id for c in rows] + [c.id for c in reengaged_rows]
    calls_map = _calls_for_clients(all_ids, window)
    ack_map = _discrepancy_ack_map(all_ids)

    clients = []
    result_breakdown: Counter = Counter()
    points_total = 0
    conversions = 0
    for c in rows:
        points_total += client_points_value(c)
        result_breakdown[c.get_call_result_display()] += 1
        if c.call_result in CONVERSION_RESULTS:
            conversions += 1
        clients.append(_serialize_review_client(c, calls_map.get(c.id, []), ack_info=ack_map.get(c.id)))

    reengaged = [
        _serialize_review_client(c, calls_map.get(c.id, []), reengaged=True, ack_info=ack_map.get(c.id))
        for c in reengaged_rows
    ]

    summary = {
        "processed": len(rows),
        "points": points_total,
        "conversions": conversions,
        "reengaged": len(reengaged),
        "result_breakdown": [{"label": k, "count": v} for k, v in result_breakdown.most_common()],
    }

    # Прогрес/регрес — лише для одноденного вікна (vs попередній день).
    deltas = None
    day_audit = None
    if window["single_day"]:
        prev_day = window["single_day"] - timedelta(days=1)
        prev = _day_summary(manager, prev_day)
        deltas = {
            "prev_label": prev_day.strftime("%d.%m.%Y"),
            "processed": _delta(summary["processed"], prev["processed"]),
            "points": _delta(summary["points"], prev["points"]),
            "conversions": _delta(summary["conversions"], prev["conversions"]),
        }
        from management.models import DayReportAudit
        da = (
            DayReportAudit.objects.filter(
                owner=manager, day=window["single_day"], status=DayReportAudit.Status.DONE
            ).order_by("-created_at").first()
        )
        if da:
            day_audit = {
                "summary": da.summary,
                "verdict": da.verdict,
                "day_score": float(da.day_score),
                "matches": da.matches or [],
                "mismatches": da.mismatches or [],
                "missed_callbacks": da.missed_callbacks or [],
                "growth": da.growth or {},
                "weaknesses": da.weaknesses or [],
                "recommendations": da.recommendations or [],
                "prospects": da.prospects,
                "tenure_days": da.tenure_days,
                "reports_count": da.reports_count,
            }

    return {
        "window": window,
        "summary": summary,
        "deltas": deltas,
        "day_audit": day_audit,
        "clients": clients,
        "reengaged": reengaged,
        "mosaic": build_mosaic_trend(manager),
    }
