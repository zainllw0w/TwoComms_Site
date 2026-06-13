"""Retention trim for first-party analytics tables.

Keeps ``PageView`` / ``SiteSession`` tables from growing unbounded on
shared hosting (the reason analytics was disabled in May 2026).
Intended to run from cron once a day.
"""

from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from storefront.models import PageView, SiteSession

DEFAULT_KEEP_DAYS = 90
CHUNK = 5000


class Command(BaseCommand):
    help = "Deletes analytics rows older than --days (default 90) and expired Django sessions."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=DEFAULT_KEEP_DAYS)

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options["days"])

        total_pv = 0
        while True:
            ids = list(
                PageView.objects.filter(when__lt=cutoff).values_list("id", flat=True)[:CHUNK]
            )
            if not ids:
                break
            PageView.objects.filter(id__in=ids).delete()
            total_pv += len(ids)

        # Deleting stale sessions cascades to their remaining pageviews.
        total_sess = 0
        while True:
            ids = list(
                SiteSession.objects.filter(last_seen__lt=cutoff).values_list("id", flat=True)[:CHUNK]
            )
            if not ids:
                break
            SiteSession.objects.filter(id__in=ids).delete()
            total_sess += len(ids)

        call_command("clearsessions")
        self.stdout.write(
            self.style.SUCCESS(
                f"trim_analytics: removed {total_pv} pageviews, {total_sess} sessions older than {options['days']}d"
            )
        )
