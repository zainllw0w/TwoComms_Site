"""Bounded reconciliation for demand-driven follow work and UGC delivery."""

from __future__ import annotations

from collections.abc import Iterable

from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from management.ig_bot_models import (
    IgFollowRefreshJob,
    IgPaymentFollowPreparation,
    IgUgcRewardDelivery,
)


MAX_RECONCILE_LIMIT = 500


def is_follow_job_due(job, *, now) -> bool:
    if job.status == IgFollowRefreshJob.Status.PROCESSING:
        return bool(job.lease_expires_at and job.lease_expires_at < now)
    if job.status not in {
        IgFollowRefreshJob.Status.PENDING,
        IgFollowRefreshJob.Status.FAILED,
    }:
        return False
    return (job.next_attempt_at or job.due_at) <= now


def select_reconciliation_batch(
    follow_jobs: Iterable,
    ugc_deliveries: Iterable,
    *,
    limit: int,
    now,
) -> tuple[list, list]:
    """Reserve capacity for UGC so an unbounded follow queue cannot starve it."""
    bounded = max(0, min(MAX_RECONCILE_LIMIT, int(limit)))
    if bounded == 0:
        return [], []
    due_follow = [row for row in follow_jobs if is_follow_job_due(row, now=now)]
    due_ugc = [
        row
        for row in ugc_deliveries
        if row.due_at <= now
        or (
            row.state == IgUgcRewardDelivery.State.PROCESSING
            and row.lease_expires_at
            and row.lease_expires_at < now
        )
    ]

    ugc_reserved = 1 if due_ugc else 0
    selected_follow = due_follow[: max(0, bounded - ugc_reserved)]
    remaining = bounded - len(selected_follow)
    selected_ugc = due_ugc[:remaining]
    remaining = bounded - len(selected_follow) - len(selected_ugc)
    if remaining:
        selected_follow.extend(due_follow[len(selected_follow) : len(selected_follow) + remaining])
    return selected_follow, selected_ugc


def _due_follow_jobs(*, now, limit: int):
    retry_due = Q(
        status__in=(
            IgFollowRefreshJob.Status.PENDING,
            IgFollowRefreshJob.Status.FAILED,
        )
    ) & (
        Q(next_attempt_at__isnull=True, due_at__lte=now)
        | Q(next_attempt_at__lte=now)
    )
    expired_lease = Q(
        status=IgFollowRefreshJob.Status.PROCESSING,
        lease_expires_at__lt=now,
    )
    return list(
        IgFollowRefreshJob.objects.filter(retry_due | expired_lease)
        .annotate(effective_due_at=Coalesce("next_attempt_at", "due_at"))
        .order_by("effective_due_at", "id")[:limit]
    )


def _due_ugc_deliveries(*, now, limit: int):
    return list(
        IgUgcRewardDelivery.objects.filter(
            Q(
                state__in=(
                    IgUgcRewardDelivery.State.PENDING,
                    IgUgcRewardDelivery.State.FAILED,
                    IgUgcRewardDelivery.State.WAITING_WINDOW,
                ),
                due_at__lte=now,
            )
            | Q(
                state=IgUgcRewardDelivery.State.PROCESSING,
                lease_expires_at__lt=now,
            )
        )
        .annotate(effective_due_at=Coalesce("lease_expires_at", "due_at"))
        .order_by("effective_due_at", "id")[:limit]
    )


def _due_payment_follow_preparations(*, now, limit: int):
    return list(
        IgPaymentFollowPreparation.objects.filter(
            Q(
                state=IgPaymentFollowPreparation.State.PENDING,
            )
            | Q(
                state=IgPaymentFollowPreparation.State.PROCESSING,
                lease_expires_at__lt=now,
            )
        )
        .order_by("deadline_at", "id")[:limit]
    )


def reconcile_follow_intelligence_once(*, limit=50, dry_run=False, now=None):
    """Process one bounded, fair batch without discovering or scanning clients."""
    from management.services.ig_follow_state import run_follow_refresh_job
    from management.services.ig_follow_cta import (
        process_payment_follow_preparation,
        reconcile_expired_follow_reservations,
    )
    from management.services.ig_ugc_rewards import process_external_ugc_reward_delivery
    from management.services.ig_ugc_assessment import reconcile_pending_ugc_media

    now = now or timezone.now()
    requested_limit = 50 if limit is None else int(limit)
    bounded = max(0, min(MAX_RECONCILE_LIMIT, requested_limit))
    counts = {
        "follow_selected": 0,
        "follow_known": 0,
        "follow_error": 0,
        "follow_skipped": 0,
        "cta_cancelled": 0,
        "cta_ambiguous": 0,
        "payment_selected": 0,
        "payment_prepared": 0,
        "payment_suppressed": 0,
        "payment_expired": 0,
        "payment_failed": 0,
        "ugc_selected": 0,
        "ugc_media_selected": 0,
        "ugc_media_retried": 0,
        "ugc_media_owned": 0,
        "ugc_media_assessed": 0,
        "ugc_media_awarded": 0,
        "ugc_media_waiting": 0,
        "ugc_media_skipped": 0,
        "ugc_media_failed": 0,
        "selected": 0,
        "sent": 0,
        "waiting": 0,
        "ambiguous": 0,
        "failed": 0,
    }
    if bounded == 0:
        return counts
    payment_candidates = _due_payment_follow_preparations(now=now, limit=bounded)
    follow_candidates = _due_follow_jobs(now=now, limit=bounded)
    ugc_candidates = _due_ugc_deliveries(now=now, limit=bounded)
    payment_budget = min(len(payment_candidates), max(1, bounded // 2))
    payment_preparations = payment_candidates[:payment_budget]
    follow_jobs, deliveries = select_reconciliation_batch(
        follow_candidates,
        ugc_candidates,
        limit=max(0, bounded - len(payment_preparations)),
        now=now,
    )
    counts["follow_selected"] = len(follow_jobs)
    counts["payment_selected"] = len(payment_preparations)
    counts["ugc_selected"] = len(deliveries)
    counts["selected"] = len(deliveries)
    if dry_run:
        return counts

    recovered = reconcile_expired_follow_reservations(now=now, limit=bounded)
    counts["cta_cancelled"] = int(recovered.get("cancelled", 0) or 0)
    counts["cta_ambiguous"] = int(recovered.get("ambiguous", 0) or 0)

    for preparation in payment_preparations:
        state = process_payment_follow_preparation(preparation.pk, now=now)
        key = {
            "prepared": "payment_prepared",
            "suppressed": "payment_suppressed",
            "expired": "payment_expired",
            "failed": "payment_failed",
        }.get(state)
        if key:
            counts[key] += 1
    for job in follow_jobs:
        state = run_follow_refresh_job(job.pk, now=now)
        key = {
            "known": "follow_known",
            "error": "follow_error",
            "skipped": "follow_skipped",
        }.get(state)
        if key:
            counts[key] += 1
    for delivery in deliveries:
        state = process_external_ugc_reward_delivery(delivery.pk)
        key = {
            IgUgcRewardDelivery.State.SENT: "sent",
            IgUgcRewardDelivery.State.AMBIGUOUS: "ambiguous",
            IgUgcRewardDelivery.State.WAITING_WINDOW: "waiting",
            IgUgcRewardDelivery.State.FAILED: "failed",
        }.get(state)
        if key:
            counts[key] += 1

    # Media capture is an event-scoped queue backed by pending assessments.
    # Spend only capacity left after mandatory payment/follow/outbox work so
    # one hot queue cannot starve either delivery or UGC recovery.  The helper
    # itself uses per-assessment and per-media leases and never creates a
    # synthetic inbound message.
    media_budget = max(
        0,
        bounded
        - len(payment_preparations)
        - len(follow_jobs)
        - len(deliveries),
    )
    if media_budget:
        media_counts = reconcile_pending_ugc_media(limit=media_budget, now=now)
        counts["ugc_media_selected"] = int(media_counts.get("selected", 0) or 0)
        counts["ugc_media_retried"] = int(media_counts.get("retried", 0) or 0)
        counts["ugc_media_owned"] = int(media_counts.get("owned", 0) or 0)
        counts["ugc_media_assessed"] = int(media_counts.get("assessed", 0) or 0)
        counts["ugc_media_awarded"] = int(media_counts.get("awarded", 0) or 0)
        counts["ugc_media_waiting"] = int(media_counts.get("waiting", 0) or 0)
        counts["ugc_media_skipped"] = int(media_counts.get("skipped", 0) or 0)
        counts["ugc_media_failed"] = int(media_counts.get("failed", 0) or 0)
    return counts
