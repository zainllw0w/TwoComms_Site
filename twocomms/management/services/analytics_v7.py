from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count
from django.utils import timezone

from management.models import (
    Client,
    ClientFollowUp,
    ClientInteractionAttempt,
    ClientStageEvent,
    FollowUpEvent,
    ManagerDayFact,
    ManagerDayStatus,
    ReasonSignal,
    ScoreAmendment,
    ScoreAppeal,
    VerifiedWorkEvent,
)


PROMISE_RESULTS = {
    Client.CallResult.THINKING,
    Client.CallResult.WAITING_PAYMENT,
    Client.CallResult.WAITING_PREPAYMENT,
    Client.CallResult.TEST_BATCH,
}

NURTURE_RESULTS = {
    Client.CallResult.SENT_EMAIL,
    Client.CallResult.SENT_MESSENGER,
    Client.CallResult.WROTE_IG,
    Client.CallResult.XML_CONNECTED,
}


@dataclass(frozen=True)
class ManagerDayScoreV7:
    authoritative_score: float
    pace_score: float
    evidence_score: float
    reason_score: float
    followup_score: float
    confidence_score: float
    recovery_actions: list[str]


def _local_day_bounds(day):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, time.min), tz)
    end = start + timedelta(days=1)
    return start, end


def _followup_kind_for_interaction(source_interaction: ClientInteractionAttempt | None) -> str:
    if not source_interaction:
        return ClientFollowUp.Kind.CALLBACK
    if source_interaction.result in PROMISE_RESULTS:
        return ClientFollowUp.Kind.PROMISE
    if source_interaction.result in NURTURE_RESULTS:
        return ClientFollowUp.Kind.NURTURE
    return ClientFollowUp.Kind.CALLBACK


def _priority_snapshot_for_followup(
    *,
    followup: ClientFollowUp,
    source_interaction: ClientInteractionAttempt | None,
) -> dict:
    snapshot = dict(followup.priority_snapshot or {})
    snapshot.setdefault("phase_number", followup.client.phase_number or 1)
    snapshot.setdefault("due_date", followup.due_date.isoformat() if followup.due_date else "")
    snapshot.setdefault("escalation_level", int(followup.escalation_level or 0))
    if source_interaction:
        snapshot.setdefault("result", source_interaction.result)
        snapshot.setdefault("reason_code", source_interaction.reason_code or "")
        snapshot.setdefault("verification_level", source_interaction.verification_level or "")
    return snapshot


def _reason_quality_label(interaction: ClientInteractionAttempt) -> str:
    has_code = bool((interaction.reason_code or "").strip())
    has_note = bool((interaction.reason_note or "").strip())
    if has_code and has_note:
        return "rich"
    if has_code or has_note:
        return "partial"
    return "missing"


def _evidence_kind(interaction: ClientInteractionAttempt) -> str:
    if interaction.cp_log_id:
        return "cp_log"
    if interaction.linked_shop_id:
        return "linked_shop"
    if interaction.messenger_type:
        return "messenger"
    if interaction.xml_platform:
        return "xml"
    if interaction.duplicate_review_id:
        return "duplicate_review"
    return interaction.verification_level or "self_reported"


def record_interaction_analytics(interaction: ClientInteractionAttempt) -> None:
    owner = interaction.manager
    client = interaction.client
    stage_code = f"phase_{client.phase_number or 1}"

    ClientStageEvent.objects.update_or_create(
        event_key=f"interaction:{interaction.id}:stage",
        defaults={
            "client": client,
            "owner": owner,
            "interaction": interaction,
            "stage_code": stage_code,
            "phase_number": client.phase_number or 1,
            "result_code": interaction.result or "",
            "occurred_at": interaction.created_at,
            "payload": {
                "phase_root_id": client.phase_root_id or client.id,
                "previous_phase_id": client.previous_phase_id,
            },
        },
    )

    if (interaction.reason_code or "").strip() or (interaction.reason_note or "").strip():
        ReasonSignal.objects.update_or_create(
            event_key=f"interaction:{interaction.id}:reason",
            defaults={
                "client": client,
                "owner": owner,
                "interaction": interaction,
                "result_code": interaction.result or "",
                "reason_code": interaction.reason_code or "",
                "quality_label": _reason_quality_label(interaction),
                "captured_at": interaction.created_at,
                "payload": {
                    "reason_note": interaction.reason_note or "",
                    "context": interaction.context or {},
                    "details": interaction.details or "",
                },
            },
        )

    VerifiedWorkEvent.objects.update_or_create(
        event_key=f"interaction:{interaction.id}:verified",
        defaults={
            "client": client,
            "owner": owner,
            "interaction": interaction,
            "verification_level": interaction.verification_level,
            "evidence_kind": _evidence_kind(interaction),
            "verified_at": interaction.created_at,
            "payload": {
                "duplicate_review_id": interaction.duplicate_review_id,
                "messenger_type": interaction.messenger_type or "",
                "xml_platform": interaction.xml_platform or "",
            },
        },
    )


def record_followup_opened(
    *,
    followup: ClientFollowUp,
    occurred_at,
    source: str,
    source_interaction: ClientInteractionAttempt | None = None,
) -> None:
    FollowUpEvent.objects.update_or_create(
        event_key=f"followup:{followup.id}:opened",
        defaults={
            "followup": followup,
            "client": followup.client,
            "owner": followup.owner,
            "source_interaction": source_interaction or followup.source_interaction,
            "event_type": FollowUpEvent.EventType.OPENED,
            "followup_kind": followup.followup_kind,
            "status_before": "",
            "status_after": followup.status,
            "close_reason": "",
            "completion_quality": followup.completion_quality or "",
            "due_at": followup.due_at,
            "due_date": followup.due_date,
            "occurred_at": occurred_at,
            "source": source,
            "priority_snapshot": _priority_snapshot_for_followup(
                followup=followup,
                source_interaction=source_interaction or followup.source_interaction,
            ),
            "payload": {"reschedule_count": int(followup.reschedule_count or 0)},
        },
    )


def record_followup_closed(
    *,
    followup: ClientFollowUp,
    occurred_at,
    source: str,
    status_before: str,
    source_interaction: ClientInteractionAttempt | None = None,
) -> None:
    FollowUpEvent.objects.update_or_create(
        event_key=f"followup:{followup.id}:closed:{followup.status}",
        defaults={
            "followup": followup,
            "client": followup.client,
            "owner": followup.owner,
            "source_interaction": source_interaction or followup.source_interaction,
            "event_type": FollowUpEvent.EventType.CLOSED,
            "followup_kind": followup.followup_kind,
            "status_before": status_before or "",
            "status_after": followup.status,
            "close_reason": followup.close_reason or followup.status,
            "completion_quality": followup.completion_quality or "",
            "due_at": followup.due_at,
            "due_date": followup.due_date,
            "occurred_at": occurred_at,
            "source": source,
            "priority_snapshot": _priority_snapshot_for_followup(
                followup=followup,
                source_interaction=source_interaction or followup.source_interaction,
            ),
            "payload": {"reschedule_count": int(followup.reschedule_count or 0)},
        },
    )


def record_followup_notified(*, followup: ClientFollowUp, notified_at, source: str = "reminder_digest") -> None:
    FollowUpEvent.objects.update_or_create(
        event_key=f"followup:{followup.id}:notified:{notified_at.isoformat()}",
        defaults={
            "followup": followup,
            "client": followup.client,
            "owner": followup.owner,
            "source_interaction": followup.source_interaction,
            "event_type": FollowUpEvent.EventType.NOTIFIED,
            "followup_kind": followup.followup_kind,
            "status_before": followup.status,
            "status_after": followup.status,
            "close_reason": "",
            "completion_quality": followup.completion_quality or "",
            "due_at": followup.due_at,
            "due_date": followup.due_date,
            "occurred_at": notified_at,
            "source": source,
            "priority_snapshot": _priority_snapshot_for_followup(
                followup=followup,
                source_interaction=followup.source_interaction,
            ),
            "payload": {"last_notified_at": notified_at.isoformat()},
        },
    )


def sync_manager_day_status_fact(day_status: ManagerDayStatus) -> ManagerDayFact:
    return materialize_manager_day_fact(owner=day_status.owner, day=day_status.day)


def materialize_manager_day_fact(*, owner, day, fact_key: str = "daily_shadow_v7") -> ManagerDayFact:
    start, end = _local_day_bounds(day)
    status_obj = ManagerDayStatus.objects.filter(owner=owner, day=day).first()
    effective_status = status_obj.status if status_obj else ManagerDayStatus.Status.WORKING
    capacity_factor = Decimal(status_obj.capacity_factor if status_obj else Decimal("1.00"))

    interaction_qs = ClientInteractionAttempt.objects.filter(manager=owner, created_at__gte=start, created_at__lt=end)
    reason_qs = ReasonSignal.objects.filter(owner=owner, captured_at__gte=start, captured_at__lt=end)
    verified_qs = VerifiedWorkEvent.objects.filter(owner=owner, verified_at__gte=start, verified_at__lt=end)
    followup_event_qs = FollowUpEvent.objects.filter(owner=owner, occurred_at__gte=start, occurred_at__lt=end)
    overdue_qs = ClientFollowUp.objects.filter(owner=owner, status=ClientFollowUp.Status.OPEN, due_date__lte=day)
    top_reasons = list(
        reason_qs.exclude(reason_code="")
        .values("reason_code")
        .annotate(total=Count("id"))
        .order_by("-total", "reason_code")[:5]
    )

    latest_points = [
        interaction_qs.order_by("-created_at").values_list("created_at", flat=True).first(),
        reason_qs.order_by("-captured_at").values_list("captured_at", flat=True).first(),
        verified_qs.order_by("-verified_at").values_list("verified_at", flat=True).first(),
        followup_event_qs.order_by("-occurred_at").values_list("occurred_at", flat=True).first(),
        status_obj.updated_at if status_obj else None,
    ]
    latest_seen = max((item for item in latest_points if item is not None), default=None)
    freshness_seconds = int(max(0, (timezone.now() - latest_seen).total_seconds())) if latest_seen else 0

    fact, _ = ManagerDayFact.objects.update_or_create(
        owner=owner,
        day=day,
        fact_key=fact_key,
        defaults={
            "schema_version": "v7",
            "day_status": effective_status,
            "capacity_factor": capacity_factor,
            "interactions_total": interaction_qs.count(),
            "verified_interactions": verified_qs.exclude(
                verification_level=ClientInteractionAttempt.VerificationLevel.SELF_REPORTED
            ).count(),
            "reason_signals_total": reason_qs.count(),
            "followups_opened": followup_event_qs.filter(event_type=FollowUpEvent.EventType.OPENED).count(),
            "followups_closed": followup_event_qs.filter(event_type=FollowUpEvent.EventType.CLOSED).count(),
            "followups_completed": followup_event_qs.filter(
                event_type=FollowUpEvent.EventType.CLOSED,
                status_after=ClientFollowUp.Status.DONE,
            ).count(),
            "followups_overdue": overdue_qs.count(),
            "open_promises": overdue_qs.filter(followup_kind=ClientFollowUp.Kind.PROMISE).count(),
            "open_nurtures": overdue_qs.filter(followup_kind=ClientFollowUp.Kind.NURTURE).count(),
            "freshness_seconds": freshness_seconds,
            "payload": {
                "top_reason_codes": top_reasons,
                "notified_events": followup_event_qs.filter(event_type=FollowUpEvent.EventType.NOTIFIED).count(),
                "calendar_profile_override": bool(status_obj),
                "verified_share": round(
                    verified_qs.exclude(
                        verification_level=ClientInteractionAttempt.VerificationLevel.SELF_REPORTED
                    ).count() / max(interaction_qs.count(), 1),
                    4,
                ),
                "reason_capture_rate": round(reason_qs.count() / max(interaction_qs.count(), 1), 4),
            },
        },
    )
    return fact


def _compute_day_score_v7(fact: ManagerDayFact) -> ManagerDayScoreV7:
    interactions_total = max(int(fact.interactions_total or 0), 0)
    verified_total = max(int(fact.verified_interactions or 0), 0)
    reasons_total = max(int(fact.reason_signals_total or 0), 0)
    overdue_total = max(int(fact.followups_overdue or 0), 0)
    completed_total = max(int(fact.followups_completed or 0), 0)
    opened_total = max(int(fact.followups_opened or 0), 0)
    capacity = float(fact.capacity_factor or Decimal("1.00"))

    pace_score = min(interactions_total / 12.0, 1.0)
    evidence_score = min(verified_total / max(interactions_total, 1), 1.0)
    reason_score = min(reasons_total / max(interactions_total, 1), 1.0)
    followup_score = max(0.0, 1.0 - (overdue_total / max(opened_total + completed_total, 1)))
    confidence_score = round((evidence_score + reason_score) / 2.0, 4)

    authoritative_score = round((((pace_score + evidence_score + reason_score + followup_score) / 4.0) * 100.0) * capacity, 2)

    recovery_actions: list[str] = []
    if overdue_total:
        recovery_actions.append("Закрити або перепланувати прострочені follow-up")
    if evidence_score < 0.5:
        recovery_actions.append("Підвищити частку підтверджених взаємодій")
    if reason_score < 0.5:
        recovery_actions.append("Покращити capture причин у результатах")
    if not recovery_actions:
        recovery_actions.append("Підтримувати поточний темп без втрати якості")

    return ManagerDayScoreV7(
        authoritative_score=authoritative_score,
        pace_score=round(pace_score, 4),
        evidence_score=round(evidence_score, 4),
        reason_score=round(reason_score, 4),
        followup_score=round(followup_score, 4),
        confidence_score=confidence_score,
        recovery_actions=recovery_actions,
    )


def build_shadow_score_payload_v7(*, owner, snapshot_date) -> dict:
    fact = materialize_manager_day_fact(owner=owner, day=snapshot_date)
    score = _compute_day_score_v7(fact)
    return {
        "schema_version": "v7",
        "fact_key": fact.fact_key,
        "readiness_state": "shadow",
        "score": {
            "authoritative": score.authoritative_score,
            "confidence": score.confidence_score,
        },
        "components": {
            "pace": score.pace_score,
            "evidence": score.evidence_score,
            "reason_quality": score.reason_score,
            "followup_discipline": score.followup_score,
        },
        "facts": {
            "day_status": fact.day_status,
            "capacity_factor": float(fact.capacity_factor),
            "interactions_total": fact.interactions_total,
            "verified_interactions": fact.verified_interactions,
            "reason_signals_total": fact.reason_signals_total,
            "followups_opened": fact.followups_opened,
            "followups_closed": fact.followups_closed,
            "followups_completed": fact.followups_completed,
            "followups_overdue": fact.followups_overdue,
            "open_promises": fact.open_promises,
            "open_nurtures": fact.open_nurtures,
            "freshness_seconds": fact.freshness_seconds,
        },
        "recovery_actions": score.recovery_actions,
        "top_reason_codes": fact.payload.get("top_reason_codes") or [],
        "lineage": {
            "fact_id": fact.id,
            "materialized_at": timezone.localtime(fact.materialized_at).isoformat() if fact.materialized_at else "",
        },
    }


def sync_score_amendment_for_appeal(*, appeal: ScoreAppeal, status: str | None = None, resolution_note: str = "") -> ScoreAmendment:
    effective_date = appeal.snapshot.snapshot_date if appeal.snapshot_id and appeal.snapshot else timezone.localdate()
    fact = ManagerDayFact.objects.filter(owner=appeal.owner, day=effective_date, fact_key="daily_shadow_v7").first()
    amendment_status = status or ScoreAmendment.Status.PENDING
    if amendment_status not in ScoreAmendment.Status.values:
        amendment_status = ScoreAmendment.Status.PENDING
    return ScoreAmendment.objects.update_or_create(
        event_key=f"appeal:{appeal.id}:amendment",
        defaults={
            "owner": appeal.owner,
            "effective_date": effective_date,
            "fact": fact,
            "appeal": appeal,
            "status": amendment_status,
            "delta_score": Decimal("0.00"),
            "reason": resolution_note or appeal.reason or "",
            "payload": {
                "appeal_status": appeal.status,
                "reason_code": appeal.reason_code or "",
                "snapshot_id": appeal.snapshot_id,
            },
        },
    )[0]
