from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from management.services import gemini_metadata_health


class Command(BaseCommand):
    help = "Run an explicit token-free Gemini metadata diagnostic (never scheduled)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--manual",
            action="store_true",
            help="Confirm this is an operator-requested diagnostic",
        )

    def handle(self, *args, **options):
        if not options.get("manual"):
            raise CommandError(
                "Automatic Gemini checks are disabled; rerun with --manual only "
                "for an explicit operator diagnostic."
            )
        now = timezone.now()
        result = gemini_metadata_health.run_hour(now=now)
        self.stdout.write(
            self.style.SUCCESS(
                f"Scanned {result['checked_aliases']} Gemini aliases "
                f"({result['configured_aliases']} configured): "
                f"{result['provider_requests']} metadata requests, "
                f"{result['deadline_skipped_models']} deadline skips."
            )
        )
