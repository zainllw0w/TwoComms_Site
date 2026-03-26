from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from management.models import Client, ClientFollowUp, ClientInteractionAttempt
from management.services.analytics_v7 import record_followup_closed, record_followup_opened
from management.services.followup_state import build_grace_until


def local_followup_date(dt_value):
    try:
        return timezone.localtime(dt_value).date()
    except Exception:
        try:
            return timezone.localdate(dt_value)
        except Exception:
            return timezone.localdate()


def callback_cycle_meta(*, client: Client, now_dt) -> dict:
    window_start = now_dt - timedelta(days=7)
    recent_reschedules = (
        ClientInteractionAttempt.objects.filter(
            client=client,
            created_at__gte=window_start,
            next_call_at__isnull=False,
        )
        .exclude(result__in=[Client.CallResult.ORDER, Client.CallResult.TEST_BATCH, Client.CallResult.XML_CONNECTED])
        .count()
    )
    return {
        "recent_callback_attempts": recent_reschedules,
        "callback_review_candidate": recent_reschedules >= 3,
    }


def _followup_kind(source_interaction: ClientInteractionAttempt | None) -> str:
    if not source_interaction:
        return ClientFollowUp.Kind.CALLBACK
    if source_interaction.result in {
        Client.CallResult.THINKING,
        Client.CallResult.WAITING_PAYMENT,
        Client.CallResult.WAITING_PREPAYMENT,
        Client.CallResult.TEST_BATCH,
    }:
        return ClientFollowUp.Kind.PROMISE
    if source_interaction.result in {
        Client.CallResult.SENT_EMAIL,
        Client.CallResult.SENT_MESSENGER,
        Client.CallResult.WROTE_IG,
        Client.CallResult.XML_CONNECTED,
    }:
        return ClientFollowUp.Kind.NURTURE
    return ClientFollowUp.Kind.CALLBACK


def _close_reason_for_status(status: str) -> str:
    return {
        ClientFollowUp.Status.CANCELLED: "callback_cleared",
        ClientFollowUp.Status.RESCHEDULED: "callback_rescheduled",
        ClientFollowUp.Status.DONE: "callback_completed_after_due",
        ClientFollowUp.Status.MISSED: "callback_missed",
    }.get(status, status or "")


def _completion_quality_for_status(status: str) -> str:
    return {
        ClientFollowUp.Status.CANCELLED: "cleared",
        ClientFollowUp.Status.RESCHEDULED: "rescheduled",
        ClientFollowUp.Status.DONE: "completed",
        ClientFollowUp.Status.MISSED: "missed",
    }.get(status, "")


def sync_client_followup(
    client: Client,
    prev_next_call_at,
    new_next_call_at,
    now_dt,
    *,
    source: str = "client.next_call_at",
    source_interaction: ClientInteractionAttempt | None = None,
):
    """
    Keep ClientFollowUp in sync with Client.next_call_at across all entry points.
    - Creates a new OPEN follow-up when a callback is scheduled.
    - Closes prior OPEN follow-ups when the callback is cleared or moved.
    - Stamps callback-cycle metadata for later UI/advice/admin visibility.
    """
    owner = client.owner
    if not owner:
        return

    with transaction.atomic():
        open_followups = list(
            ClientFollowUp.objects.select_for_update()
            .filter(client=client, owner=owner, status=ClientFollowUp.Status.OPEN)
            .order_by("id")
        )

        next_reschedule_count = 0

        if prev_next_call_at:
            if not new_next_call_at:
                close_status = ClientFollowUp.Status.CANCELLED
            elif new_next_call_at != prev_next_call_at:
                close_status = ClientFollowUp.Status.RESCHEDULED if now_dt < prev_next_call_at else ClientFollowUp.Status.DONE
            else:
                close_status = ""

            for followup in open_followups:
                if not close_status:
                    continue
                status_before = followup.status
                followup.status = close_status
                followup.closed_at = now_dt
                followup.close_reason = _close_reason_for_status(close_status)
                followup.completion_quality = _completion_quality_for_status(close_status)
                followup.source_interaction = source_interaction or followup.source_interaction
                followup.save(
                    update_fields=[
                        "status",
                        "closed_at",
                        "close_reason",
                        "completion_quality",
                        "source_interaction",
                    ]
                )
                next_reschedule_count = max(next_reschedule_count, int(followup.reschedule_count or 0) + 1)
                record_followup_closed(
                    followup=followup,
                    occurred_at=now_dt,
                    source=source,
                    status_before=status_before,
                    source_interaction=source_interaction,
                )

        if new_next_call_at and (not prev_next_call_at or new_next_call_at != prev_next_call_at):
            meta = {"source": source}
            meta.update(callback_cycle_meta(client=client, now_dt=now_dt))
            followup = ClientFollowUp.objects.create(
                client=client,
                owner=owner,
                due_at=new_next_call_at,
                due_date=local_followup_date(new_next_call_at),
                status=ClientFollowUp.Status.OPEN,
                followup_kind=_followup_kind(source_interaction),
                grace_until=build_grace_until(new_next_call_at),
                source_interaction=source_interaction,
                reschedule_count=next_reschedule_count if prev_next_call_at else 0,
                priority_snapshot={
                    "source": source,
                    "phase_number": client.phase_number or 1,
                    "result": source_interaction.result if source_interaction else "",
                    "reason_code": source_interaction.reason_code if source_interaction else "",
                },
                meta=meta,
            )
            record_followup_opened(
                followup=followup,
                occurred_at=now_dt,
                source=source,
                source_interaction=source_interaction,
            )
