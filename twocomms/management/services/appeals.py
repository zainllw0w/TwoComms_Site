from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from management.models import ScoreAppeal, SupervisorActionLog


def create_score_appeal(*, owner, snapshot, reason: str, evidence_payload: dict | None = None, reason_code: str = "", appeal_type: str = "score") -> ScoreAppeal:
    opened_at = timezone.now()
    return ScoreAppeal.objects.create(
        owner=owner,
        snapshot=snapshot,
        appeal_type=appeal_type,
        reason=(reason or "").strip(),
        reason_code=(reason_code or "").strip(),
        manager_note=(reason or "").strip(),
        evidence=evidence_payload or {},
        evidence_payload=evidence_payload or {},
        opened_at=opened_at,
        due_at=opened_at + timedelta(hours=48),
    )


def resolve_score_appeal(*, appeal: ScoreAppeal, status: str, resolution_note: str, resolved_by=None) -> ScoreAppeal:
    appeal.mark_resolved(status, resolution_note)
    appeal.resolved_by = resolved_by
    appeal.save(update_fields=["resolved_by"])
    if resolved_by:
        SupervisorActionLog.objects.create(
            manager=appeal.owner,
            actor=resolved_by,
            action_type=SupervisorActionLog.ActionType.APPEAL_RESOLUTION,
            payload={
                "appeal_id": appeal.id,
                "status": status,
                "snapshot_id": appeal.snapshot_id,
            },
        )
    return appeal


def summarize_appeals(snapshot) -> dict:
    appeals_qs = ScoreAppeal.objects.filter(snapshot=snapshot)
    latest = appeals_qs.order_by("-opened_at", "-created_at").first()
    return {
        "total": appeals_qs.count(),
        "open": appeals_qs.filter(status=ScoreAppeal.Status.OPEN).count(),
        "latest_status": latest.status if latest else "",
        "nearest_due_at": latest.due_at.isoformat() if latest and latest.due_at else "",
    }
