"""Bounded recovery worker for committed Instagram payment/shipment events."""

from django.core.management.base import BaseCommand, CommandError

from management.services.ig_lifecycle import dispatch_due_lifecycle_events


class Command(BaseCommand):
    help = "Process due Instagram lifecycle events with lease and policy guards."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count due events without claiming or sending them.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        if limit <= 0 or limit > 500:
            raise CommandError("--limit must be between 1 and 500")
        if options["dry_run"]:
            from django.utils import timezone
            from management.models import IgLifecycleEvent

            due = IgLifecycleEvent.objects.filter(
                due_at__lte=timezone.now(),
                state__in=(
                    IgLifecycleEvent.State.PENDING,
                    IgLifecycleEvent.State.WAITING_WINDOW,
                    IgLifecycleEvent.State.PROCESSING,
                ),
            ).count()
            self.stdout.write(f"process_ig_lifecycle_events: due={min(due, limit)} dry_run=true")
            return

        delivered = dispatch_due_lifecycle_events(limit=limit)
        self.stdout.write(
            self.style.SUCCESS(
                f"process_ig_lifecycle_events: delivered={delivered} limit={limit}"
            )
        )
