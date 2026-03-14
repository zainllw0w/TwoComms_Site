from django.core.management.base import BaseCommand
from django.utils import timezone

from management.models import CommandRunLog, DuplicateReview


class Command(BaseCommand):
    help = "Checks duplicate review backlog and records a run-log health summary."

    def handle(self, *args, **options):
        run_log = CommandRunLog.objects.create(
            command_name="check_duplicate_queue",
            run_key=f"check_duplicate_queue:{timezone.now().isoformat()}",
            meta={"mode": "backlog-check"},
        )
        open_qs = DuplicateReview.objects.filter(status=DuplicateReview.Status.OPEN)
        backlog = open_qs.count()
        oldest = open_qs.order_by("created_at").values_list("created_at", flat=True).first()
        run_log.meta = {
            "backlog": backlog,
            "oldest_opened_at": oldest.isoformat() if oldest else "",
        }
        run_log.save(update_fields=["meta"])
        run_log.mark_finished(
            status=CommandRunLog.Status.SUCCESS,
            rows_processed=backlog,
            warnings_count=1 if backlog else 0,
        )
        self.stdout.write(self.style.SUCCESS(f"Duplicate backlog: {backlog}."))
