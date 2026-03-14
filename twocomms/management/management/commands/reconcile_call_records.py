from django.core.management.base import BaseCommand
from django.utils import timezone

from management.models import CallRecord, CommandRunLog, TelephonyHealthSnapshot, TelephonyWebhookLog


class Command(BaseCommand):
    help = "Builds an aggregate telephony health snapshot from current call records and webhook backlog."

    def handle(self, *args, **options):
        run_log = CommandRunLog.objects.create(
            command_name="reconcile_call_records",
            run_key=f"reconcile_call_records:{timezone.now().isoformat()}",
            meta={"mode": "aggregate"},
        )

        total_events = CallRecord.objects.count()
        unmatched_calls = CallRecord.objects.filter(manager__isnull=True).count()
        backlog_count = TelephonyWebhookLog.objects.filter(status=TelephonyWebhookLog.Status.PENDING).count()
        status = TelephonyHealthSnapshot.Status.DEGRADED if unmatched_calls or backlog_count else TelephonyHealthSnapshot.Status.HEALTHY

        TelephonyHealthSnapshot.objects.create(
            provider="aggregate",
            status=status,
            total_events=total_events,
            unmatched_calls=unmatched_calls,
            backlog_count=backlog_count,
            meta={"run_key": run_log.run_key},
        )
        run_log.mark_finished(
            status=CommandRunLog.Status.SUCCESS,
            rows_processed=total_events,
            warnings_count=unmatched_calls + backlog_count,
        )
        self.stdout.write(self.style.SUCCESS(f"Reconciled {total_events} call record(s)."))
