from __future__ import annotations

from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from management.models import Client
from management.services.visible_points import sync_client_visible_points


class Command(BaseCommand):
    help = "Recalculate management visible points v2 for selected clients without rewriting unrelated history."

    def add_arguments(self, parser):
        parser.add_argument("--date", dest="date")
        parser.add_argument("--from-date", dest="from_date")
        parser.add_argument("--to-date", dest="to_date")
        parser.add_argument("--user-id", dest="user_id", type=int)

    def handle(self, *args, **options):
        target_date = self._parse_date(options.get("date"))
        date_from = self._parse_date(options.get("from_date")) or target_date
        date_to = self._parse_date(options.get("to_date")) or target_date
        user_id = options.get("user_id")

        qs = Client.objects.select_related("owner", "phase_root", "previous_phase")
        if user_id:
            qs = qs.filter(owner_id=user_id)

        if date_from:
            start_dt = timezone.make_aware(datetime.combine(date_from, time.min))
            qs = qs.filter(created_at__gte=start_dt)
        if date_to:
            end_dt = timezone.make_aware(datetime.combine(date_to + timedelta(days=1), time.min))
            qs = qs.filter(created_at__lt=end_dt)

        processed = 0
        for client in qs.order_by("created_at", "id").iterator():
            sync_client_visible_points(client)
            processed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Recalculated visible points for {processed} client rows."
            )
        )

    @staticmethod
    def _parse_date(raw_value):
        if not raw_value:
            return None
        return date.fromisoformat(str(raw_value))
