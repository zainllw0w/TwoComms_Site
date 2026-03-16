from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from management.models import Client, ClientFollowUp, ClientInteractionAttempt


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


def sync_client_followup(client: Client, prev_next_call_at, new_next_call_at, now_dt, *, source: str = "client.next_call_at"):
    """
    Keep ClientFollowUp in sync with Client.next_call_at across all entry points.
    - Creates a new OPEN follow-up when a callback is scheduled.
    - Closes prior OPEN follow-ups when the callback is cleared or moved.
    - Stamps callback-cycle metadata for later UI/advice/admin visibility.
    """
    owner = client.owner
    if not owner:
        return

    open_qs = ClientFollowUp.objects.filter(client=client, owner=owner, status=ClientFollowUp.Status.OPEN)

    if prev_next_call_at:
        if not new_next_call_at:
            open_qs.update(
                status=ClientFollowUp.Status.CANCELLED,
                closed_at=now_dt,
            )
        elif new_next_call_at != prev_next_call_at:
            status = ClientFollowUp.Status.RESCHEDULED if now_dt < prev_next_call_at else ClientFollowUp.Status.DONE
            open_qs.update(
                status=status,
                closed_at=now_dt,
            )

    if new_next_call_at and (not prev_next_call_at or new_next_call_at != prev_next_call_at):
        meta = {"source": source}
        meta.update(callback_cycle_meta(client=client, now_dt=now_dt))
        ClientFollowUp.objects.create(
            client=client,
            owner=owner,
            due_at=new_next_call_at,
            due_date=local_followup_date(new_next_call_at),
            status=ClientFollowUp.Status.OPEN,
            meta=meta,
        )
