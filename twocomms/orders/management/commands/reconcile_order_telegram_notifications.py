"""Retry paid Monobank order cards that a request-owned daemon thread lost."""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from orders.models import Order
from storefront.views.utils import _send_post_payment_events


class Command(BaseCommand):
    help = 'Retry missing Telegram order cards for recent paid PaymentAttempt orders'

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

        now = timezone.now()
        queryset = Order.objects.filter(
            payment_provider='monobank_pay',
            payment_status__in=('paid', 'prepaid', 'partial'),
            created__gte=now - timedelta(hours=max_age_hours),
            created__lte=now - timedelta(seconds=min_age_seconds),
        ).exclude(status='cancelled').order_by('created', 'pk')
        if options.get('order_number'):
            queryset = queryset.filter(order_number=options['order_number'])

        scanned = attempted = sent = failed = leased = 0
        for order in queryset.iterator():
            scanned += 1
            payload = order.payment_payload if isinstance(order.payment_payload, dict) else {}
            if not payload.get('attempt_id'):
                continue
            if attempted >= limit:
                break

            attempted += 1
            # Replay the shared idempotent dispatcher. Telegram delivery is
            # the durable recovery gate, while Purchase/Meta/TikTok/email
            # markers make the adjacent post-payment work safe to heal too.
            result = _send_post_payment_events(
                order.pk,
                'unpaid',
                order.pay_type,
            )
            if result == 'sent':
                sent += 1
            elif result == 'leased':
                leased += 1
            elif result == 'failed':
                failed += 1

        self.stdout.write(
            'reconcile_order_telegram_notifications: '
            f'scanned={scanned} attempted={attempted} sent={sent} '
            f'failed={failed} leased={leased}'
        )
