from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from management.models import ClientFollowUp, CommandRunLog
from management.services.followups import build_reminder_digest


class Command(BaseCommand):
    help = "Builds reminder digests for management users and stamps follow-ups that were notified."

    def handle(self, *args, **options):
        run_log = CommandRunLog.objects.create(
            command_name="send_management_reminders",
            run_key=f"send_management_reminders:{timezone.now().isoformat()}",
            meta={"mode": "digest"},
        )
        User = get_user_model()
        users = (
            User.objects.filter(is_active=True)
            .filter(Q(is_staff=True) | Q(userprofile__is_manager=True))
            .distinct()
        )
        rows_processed = 0
        warnings_count = 0
        now = timezone.now()
        for user in users:
            digest = build_reminder_digest(user, now=now)
            followup_ids = [item.get("followup_id") for item in digest["reminders"] if item.get("followup_id")]
            if followup_ids:
                ClientFollowUp.objects.filter(id__in=followup_ids).update(last_notified_at=now)
            if digest["quiet_hours_active"] and not any(item.get("status") == "report" for item in digest["reminders"]):
                warnings_count += 1
            rows_processed += len(digest["reminders"])
            warnings_count += len(digest["incident_keys"])

        run_log.mark_finished(
            status=CommandRunLog.Status.SUCCESS,
            rows_processed=rows_processed,
            warnings_count=warnings_count,
        )
        self.stdout.write(self.style.SUCCESS(f"Prepared {rows_processed} reminder item(s)."))
