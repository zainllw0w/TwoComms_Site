from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.utils import timezone
from management.services import gemini_metadata_health
from management.services.ig_task_health import task_heartbeat

class Command(BaseCommand):
    help = "Record token-free Gemini model metadata readiness once per hour"
    def handle(self, *args, **options):
        now = timezone.now()
        hour = now.strftime("%Y%m%d%H")
        done_key = f"management:gemini-metadata-health:done:{hour}"
        lock_key = f"management:gemini-metadata-health:lock:{hour}"
        if cache.get(done_key) or not cache.add(lock_key, "1", timeout=600):
            self.stdout.write("Gemini metadata health already checked for this hour.")
            return
        try:
            with task_heartbeat("ig_gemini_metadata_health"):
                result = gemini_metadata_health.run_hour(now=now)
            cache.set(done_key, "1", timeout=3700)
            self.stdout.write(self.style.SUCCESS(
                f"Scanned {result['checked_aliases']} Gemini aliases "
                f"({result['configured_aliases']} configured): "
                f"{result['provider_requests']} provider requests, "
                f"{result['deadline_skipped_models']} deadline skips."
            ))
        finally:
            cache.delete(lock_key)
