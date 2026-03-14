from django.core.management.base import BaseCommand
from django.utils import timezone

from management.models import CommandRunLog, DtfBridgeSnapshot


class Command(BaseCommand):
    help = "Refreshes the read-only DTF bridge snapshot in degraded-safe mode."

    def add_arguments(self, parser):
        parser.add_argument("--source-key", dest="source_key", default="default", help="Bridge source key.")

    def handle(self, *args, **options):
        source_key = (options.get("source_key") or "default").strip() or "default"
        snapshot_date = timezone.localdate()
        run_log = CommandRunLog.objects.create(
            command_name="refresh_dtf_bridge_snapshot",
            run_key=f"refresh_dtf_bridge_snapshot:{snapshot_date.isoformat()}:{timezone.now().isoformat()}",
            meta={"source_key": source_key, "snapshot_date": snapshot_date.isoformat()},
        )

        DtfBridgeSnapshot.objects.update_or_create(
            source_key=source_key,
            snapshot_date=snapshot_date,
            defaults={
                "status": DtfBridgeSnapshot.Status.DEGRADED,
                "freshness_seconds": 0,
                "payload": {
                    "reason": "dtf_bridge_not_configured",
                    "items": [],
                    "links": [],
                },
            },
        )
        run_log.mark_finished(status=CommandRunLog.Status.SUCCESS, rows_processed=1)
        self.stdout.write(self.style.SUCCESS(f"Refreshed DTF bridge snapshot for {source_key}."))
