"""Drain the durable payment side-effect outbox with one bounded cron owner."""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from orders.models import Order
from orders.payment_side_effects import (
    due_payment_side_effect_job_ids,
    enqueue_order_post_payment_side_effect,
    process_payment_side_effect_job,
)
from storefront.views.utils import _POST_PAYMENT_CHANNEL_NAMES
from management.services.ig_task_health import task_heartbeat


_TERMINAL_POST_PAYMENT_STATES = frozenset(
    {"sent", "skipped", "disabled", "unknown", "ambiguous"}
)
_RECOVERABLE_DISPATCH_CHANNELS = tuple(
    channel for channel in _POST_PAYMENT_CHANNEL_NAMES
    if channel != "instagram_lifecycle"
)


def _has_recoverable_post_payment_channel(payload):
    channels = payload.get("post_payment_channels")
    if not isinstance(channels, dict):
        return True
    # Instagram lifecycle has its own durable event dispatcher. A waiting
    # window or manager-review state must not wake this command and replay
    # already completed Telegram/Meta/TikTok/email work every cron tick.
    return any(
        not isinstance(channels.get(channel), dict)
        or str(channels[channel].get("state") or "").strip().lower()
        not in _TERMINAL_POST_PAYMENT_STATES
        for channel in _RECOVERABLE_DISPATCH_CHANNELS
    )


class Command(BaseCommand):
    help = 'Drain durable CAPI/Telegram/post-payment jobs and backfill recent paid orders'

    def add_arguments(self, parser):
        parser.add_argument('--max-age-hours', type=int, default=168)
        parser.add_argument('--min-age-seconds', type=int, default=60)
        parser.add_argument('--limit', type=int, default=50)
        parser.add_argument('--order-number')

    def handle(self, *args, **options):
        max_age_hours = options['max_age_hours']
        min_age_seconds = options['min_age_seconds']
        limit = options['limit']
        if max_age_hours <= 0 or min_age_seconds < 0 or limit <= 0:
            raise CommandError('Age and limit options must be positive')

        with task_heartbeat('order_telegram_reconcile'):
            now = timezone.now()
            queryset = Order.objects.filter(
                payment_provider='monobank_pay',
                payment_status__in=('paid', 'prepaid', 'partial'),
                created__gte=now - timedelta(hours=max_age_hours),
                created__lte=now - timedelta(seconds=min_age_seconds),
            ).exclude(status='cancelled').order_by('created', 'pk')
            if options.get('order_number'):
                queryset = queryset.filter(order_number=options['order_number'])

            scanned = backfilled = 0
            selected_order_id = None
            for order in queryset.iterator():
                scanned += 1
                if options.get('order_number'):
                    selected_order_id = order.pk
                payload = order.payment_payload if isinstance(order.payment_payload, dict) else {}
                if not payload.get('attempt_id'):
                    continue
                if not _has_recoverable_post_payment_channel(payload):
                    continue
                _, created = enqueue_order_post_payment_side_effect(
                    order.pk,
                    previous_status='unpaid',
                    pay_type=order.pay_type,
                    due_at=now,
                )
                backfilled += int(created)
                if backfilled >= limit:
                    break

            if options.get('order_number') and selected_order_id is None:
                job_ids = []
            else:
                job_ids = due_payment_side_effect_job_ids(
                    limit=limit,
                    now=now,
                    order_id=selected_order_id,
                )
            attempted = sent = failed = leased = ambiguous = 0
            for job_id in job_ids:
                attempted += 1
                result = process_payment_side_effect_job(job_id)
                if result == 'done':
                    sent += 1
                elif result == 'leased':
                    leased += 1
                elif result == 'failed':
                    failed += 1
                elif result == 'ambiguous':
                    ambiguous += 1

        self.stdout.write(
            'reconcile_order_telegram_notifications: '
            f'scanned={scanned} attempted={attempted} sent={sent} '
            f'failed={failed} leased={leased} ambiguous={ambiguous} '
            f'jobs_scanned={len(job_ids)} backfilled={backfilled}'
        )
