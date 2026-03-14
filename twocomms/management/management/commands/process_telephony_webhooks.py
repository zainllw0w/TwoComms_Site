from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from management.models import CallRecord, CommandRunLog, TelephonyHealthSnapshot, TelephonyWebhookLog


class Command(BaseCommand):
    help = "Processes pending telephony webhooks into normalized call records."

    def add_arguments(self, parser):
        parser.add_argument("--provider", dest="provider", help="Optional provider filter.")

    def handle(self, *args, **options):
        provider = (options.get("provider") or "").strip()
        run_log = CommandRunLog.objects.create(
            command_name="process_telephony_webhooks",
            run_key=f"process_telephony_webhooks:{timezone.now().isoformat()}",
            meta={"provider": provider or "all"},
        )

        queryset = TelephonyWebhookLog.objects.filter(status=TelephonyWebhookLog.Status.PENDING).order_by("received_at")
        if provider:
            queryset = queryset.filter(provider=provider)

        processed = 0
        ignored = 0
        user_model = get_user_model()

        for webhook in queryset:
            payload = webhook.payload or {}
            external_call_id = str(payload.get("external_call_id") or payload.get("call_id") or "").strip()
            if not external_call_id:
                webhook.status = TelephonyWebhookLog.Status.IGNORED
                webhook.error_excerpt = "Missing external_call_id"
                webhook.processed_at = timezone.now()
                webhook.save(update_fields=["status", "error_excerpt", "processed_at"])
                ignored += 1
                continue

            manager = None
            manager_id = payload.get("manager_id")
            if manager_id:
                manager = user_model.objects.filter(id=manager_id).first()

            started_at = parse_datetime(str(payload.get("started_at") or "")) if payload.get("started_at") else None
            ended_at = parse_datetime(str(payload.get("ended_at") or "")) if payload.get("ended_at") else None
            if started_at and timezone.is_naive(started_at):
                started_at = timezone.make_aware(started_at)
            if ended_at and timezone.is_naive(ended_at):
                ended_at = timezone.make_aware(ended_at)

            CallRecord.objects.update_or_create(
                provider=webhook.provider,
                external_call_id=external_call_id,
                defaults={
                    "manager": manager,
                    "phone": str(payload.get("phone") or "").strip(),
                    "direction": str(payload.get("direction") or CallRecord.Direction.UNKNOWN).strip() or CallRecord.Direction.UNKNOWN,
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "duration_seconds": max(0, int(payload.get("duration_seconds") or 0)),
                    "recording_url": str(payload.get("recording_url") or "").strip(),
                    "payload": payload,
                },
            )
            webhook.status = TelephonyWebhookLog.Status.PROCESSED
            webhook.error_excerpt = ""
            webhook.processed_at = timezone.now()
            webhook.save(update_fields=["status", "error_excerpt", "processed_at"])
            processed += 1

        unmatched_calls = CallRecord.objects.filter(manager__isnull=True).count()
        backlog_count = TelephonyWebhookLog.objects.filter(status=TelephonyWebhookLog.Status.PENDING).count()
        TelephonyHealthSnapshot.objects.create(
            provider=provider or "aggregate",
            status=TelephonyHealthSnapshot.Status.DEGRADED if unmatched_calls or backlog_count else TelephonyHealthSnapshot.Status.HEALTHY,
            total_events=processed,
            unmatched_calls=unmatched_calls,
            backlog_count=backlog_count,
            meta={"ignored": ignored, "run_key": run_log.run_key},
        )
        run_log.mark_finished(
            status=CommandRunLog.Status.SUCCESS,
            rows_processed=processed,
            warnings_count=ignored,
        )
        self.stdout.write(self.style.SUCCESS(f"Processed {processed} webhook(s), ignored {ignored}."))
