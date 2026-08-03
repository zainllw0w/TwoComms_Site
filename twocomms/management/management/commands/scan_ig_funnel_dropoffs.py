from django.core.management.base import BaseCommand
from django.utils import timezone

from management.services.ig_funnel_analytics import scan_open_dropoffs


class Command(BaseCommand):
    help = "Report or materialize deterministic Instagram funnel drop-off facts."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Persist matched facts; default is dry-run.")
        parser.add_argument("--limit", type=int, default=100, help="Maximum clients to inspect.")

    def handle(self, *args, **options):
        result = scan_open_dropoffs(
            now=timezone.now(),
            limit=max(1, options["limit"]),
            apply=bool(options["apply"]),
        )
        self.stdout.write(self.style.SUCCESS(str(result)))
