from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from management.models import ClientFollowUp, ClientInteractionAttempt, ManagerDayStatus
from management.services.analytics_v7 import (
    materialize_manager_day_fact,
    record_followup_closed,
    record_followup_notified,
    record_followup_opened,
    record_interaction_analytics,
)


class Command(BaseCommand):
    help = "Backfill additive v7 analytics tables from existing management data."

    def add_arguments(self, parser):
        parser.add_argument("--date-from", dest="date_from")
        parser.add_argument("--date-to", dest="date_to")
        parser.add_argument("--user-id", dest="user_id", type=int)
        parser.add_argument("--skip-facts", action="store_true", dest="skip_facts")

    def handle(self, *args, **options):
        date_from = self._parse_date(options.get("date_from"))
        date_to = self._parse_date(options.get("date_to"))
        user_id = options.get("user_id")
        skip_facts = bool(options.get("skip_facts"))

        interactions = ClientInteractionAttempt.objects.select_related("client", "manager")
        followups = ClientFollowUp.objects.select_related("client", "owner", "source_interaction")
        statuses = ManagerDayStatus.objects.select_related("owner")

        if user_id:
            interactions = interactions.filter(manager_id=user_id)
            followups = followups.filter(owner_id=user_id)
            statuses = statuses.filter(owner_id=user_id)

        if date_from:
            start_dt = timezone.make_aware(datetime.combine(date_from, time.min))
            interactions = interactions.filter(created_at__gte=start_dt)
            followups = followups.filter(due_date__gte=date_from)
            statuses = statuses.filter(day__gte=date_from)
        if date_to:
            end_dt = timezone.make_aware(datetime.combine(date_to + timedelta(days=1), time.min))
            interactions = interactions.filter(created_at__lt=end_dt)
            followups = followups.filter(due_date__lte=date_to)
            statuses = statuses.filter(day__lte=date_to)

        touched_days = defaultdict(set)
        owners_by_id = {}

        for interaction in interactions.iterator():
            record_interaction_analytics(interaction)
            if interaction.manager_id:
                touched_days[interaction.manager_id].add(timezone.localtime(interaction.created_at).date())
                owners_by_id[interaction.manager_id] = interaction.manager

        for followup in followups.iterator():
            opened_at = followup.scheduled_at or followup.created_at or timezone.now()
            record_followup_opened(
                followup=followup,
                occurred_at=opened_at,
                source="backfill.v7",
                source_interaction=followup.source_interaction,
            )
            if followup.status != ClientFollowUp.Status.OPEN and followup.closed_at:
                record_followup_closed(
                    followup=followup,
                    occurred_at=followup.closed_at,
                    source="backfill.v7",
                    status_before=ClientFollowUp.Status.OPEN,
                    source_interaction=followup.source_interaction,
                )
            if followup.last_notified_at:
                record_followup_notified(
                    followup=followup,
                    notified_at=followup.last_notified_at,
                    source="backfill.v7",
                )
            if followup.owner_id and followup.due_date:
                touched_days[followup.owner_id].add(followup.due_date)
                owners_by_id[followup.owner_id] = followup.owner

        for status in statuses.iterator():
            if status.owner_id:
                touched_days[status.owner_id].add(status.day)
                owners_by_id[status.owner_id] = status.owner

        fact_rows = 0
        if not skip_facts:
            for owner_id, days in touched_days.items():
                owner = owners_by_id.get(owner_id)
                if owner is None:
                    continue
                for day in sorted(days):
                    materialize_manager_day_fact(owner=owner, day=day)
                    fact_rows += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfilled v7 analytics: interactions={interactions.count()} followups={followups.count()} facts={fact_rows}"
            )
        )

    @staticmethod
    def _parse_date(raw_value):
        if not raw_value:
            return None
        return date.fromisoformat(str(raw_value))
