from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from management.models import CommandRunLog
from management.services.roster import management_subjects_queryset
from management.services.snapshots import persist_nightly_snapshot


class Command(BaseCommand):
    help = "Builds or refreshes shadow nightly score snapshots for management users."

    def add_arguments(self, parser):
        parser.add_argument("--date", dest="date", help="Snapshot local date in YYYY-MM-DD format.")
        parser.add_argument("--user-id", dest="user_id", type=int, help="Process only one management user.")

    def handle(self, *args, **options):
        snapshot_date_raw = options.get("date")
        user_id = options.get("user_id")
        if snapshot_date_raw:
            try:
                snapshot_date = date.fromisoformat(snapshot_date_raw)
            except ValueError as exc:
                raise CommandError("Invalid --date. Use YYYY-MM-DD.") from exc
        else:
            snapshot_date = timezone.localdate() - timedelta(days=1)

        run_key = f"compute_nightly_scores:{snapshot_date.isoformat()}:{user_id or 'all'}"
        run_log, _ = CommandRunLog.objects.update_or_create(
            run_key=run_key,
            defaults={
                "command_name": "compute_nightly_scores",
                "status": CommandRunLog.Status.RUNNING,
                "rows_processed": 0,
                "warnings_count": 0,
                "error_excerpt": "",
                "meta": {
                    "snapshot_date": snapshot_date.isoformat(),
                    "scope": "single-user" if user_id else "all-management-users",
                },
                "finished_at": None,
            },
        )

        queryset = management_subjects_queryset().order_by("id")
        if user_id:
            queryset = queryset.filter(id=user_id)

        processed = 0
        try:
            for owner in queryset:
                persist_nightly_snapshot(owner=owner, snapshot_date=snapshot_date, job_run=run_log)
                processed += 1
            run_log.meta = {
                **(run_log.meta or {}),
                "snapshot_date": snapshot_date.isoformat(),
                "processed_user_ids": list(queryset.values_list("id", flat=True)),
            }
            run_log.save(update_fields=["meta"])
            run_log.mark_finished(status=CommandRunLog.Status.SUCCESS, rows_processed=processed)
        except Exception as exc:
            run_log.mark_finished(
                status=CommandRunLog.Status.FAILED,
                rows_processed=processed,
                error_excerpt=str(exc)[:500],
            )
            raise

        self.stdout.write(
            self.style.SUCCESS(f"Built {processed} nightly snapshot(s) for {snapshot_date.isoformat()}.")
        )
