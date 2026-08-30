from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from management.services.ig_checkout_terminalization import (
    terminalize_payment_attempt,
)
from orders.models import PaymentAttempt


class Command(BaseCommand):
    help = 'Mark stale unpaid checkout attempts as expired without creating orders.'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=24)
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        hours = max(1, options['hours'])
        limit = max(1, min(options['limit'], 500))
        now = timezone.now()
        legacy_age = timedelta(hours=hours)
        cutoff = now - legacy_age
        ids = list(
            PaymentAttempt.objects.filter(
                status__in=(PaymentAttempt.Status.INITIATED, PaymentAttempt.Status.PROCESSING),
            )
            .filter(
                Q(event_state__invoice_creation_ambiguous__isnull=True)
                | Q(event_state__invoice_creation_ambiguous=False)
            )
            .filter(
                Q(invoice_expires_at__lte=now)
                | Q(invoice_expires_at__isnull=True, created__lte=cutoff)
            ).order_by('pk').values_list('pk', flat=True)[:limit]
        )
        if not ids:
            self.stdout.write('No stale payment attempts found.')
            return
        updated = 0
        errors = 0
        for attempt_id in ids:
            try:
                outcome = terminalize_payment_attempt(
                    attempt_id,
                    terminal_status=PaymentAttempt.Status.EXPIRED,
                    reason='invoice_expired',
                    source='system_expiry',
                    now=now,
                    require_due=True,
                    legacy_null_expiry_age=legacy_age,
                )
            except Exception as exc:
                errors += 1
                self.stderr.write(
                    f'Payment attempt {attempt_id} terminalization failed: '
                    f'{exc.__class__.__name__}'
                )
                continue
            updated += int(outcome.outcome == 'terminalized')
        self.stdout.write(
            self.style.SUCCESS(
                f'Expired {updated} payment attempts; errors={errors}.'
            )
        )
