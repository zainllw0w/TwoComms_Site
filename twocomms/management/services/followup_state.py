from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.utils import timezone

from management.models import Client, ClientFollowUp


CALLBACK_GRACE_HOURS = 2


@dataclass(frozen=True)
class CallbackState:
    code: str
    due_at: datetime | None
    grace_until: datetime | None
    followup_id: int | None


def build_grace_until(due_at: datetime | None) -> datetime | None:
    if not due_at:
        return None
    return due_at + timedelta(hours=CALLBACK_GRACE_HOURS)


def _pick_open_followup(client: Client) -> ClientFollowUp | None:
    prefetched = getattr(client, "prefetched_open_followups", None)
    if prefetched:
        return prefetched[0]
    return (
        client.followups.filter(status=ClientFollowUp.Status.OPEN)
        .order_by("-due_at", "-id")
        .first()
    )


def _local(dt_value: datetime | None) -> datetime | None:
    if not dt_value:
        return None
    return timezone.localtime(dt_value)


def get_effective_callback_state(*, client: Client, now_dt: datetime | None = None) -> CallbackState:
    now_local = _local(now_dt or timezone.now())
    open_followup = _pick_open_followup(client)
    due_at = _local(open_followup.due_at if open_followup else client.next_call_at)
    grace_until = _local(open_followup.grace_until if open_followup else build_grace_until(client.next_call_at))
    followup_id = open_followup.id if open_followup else None

    if not due_at or not now_local:
        return CallbackState(code="none", due_at=due_at, grace_until=grace_until, followup_id=followup_id)
    if due_at > now_local:
        return CallbackState(code="scheduled", due_at=due_at, grace_until=grace_until, followup_id=followup_id)
    if grace_until and now_local <= grace_until:
        return CallbackState(code="due_now", due_at=due_at, grace_until=grace_until, followup_id=followup_id)
    return CallbackState(code="missed", due_at=due_at, grace_until=grace_until, followup_id=followup_id)
