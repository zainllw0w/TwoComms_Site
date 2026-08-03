from django.core.management.base import BaseCommand

from management.services.ig_funnel_analytics import backfill_reconstructible_funnel_events


class Command(BaseCommand):
    help = "Report or backfill only Instagram funnel facts with canonical persisted evidence."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Persist facts; default is dry-run.")
        parser.add_argument("--limit", type=int, default=1000, help="Maximum rows per source to inspect.")

    def handle(self, *args, **options):
        result = backfill_reconstructible_funnel_events(
            limit=max(1, options["limit"]),
            apply=bool(options["apply"]),
        )
        self.stdout.write(self.style.SUCCESS(str(result)))
