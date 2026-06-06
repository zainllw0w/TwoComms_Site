"""
Розморозка винагороди у ledger: frozen -> available по available_at <= now.

Скасовані через повернення накладні не розморожуються (стають cancelled).
Ідемпотентно (повторний прогін нічого зайвого не робить).

Док: twocomms/Management Implementations/07 (7.5) + 09 (9.1).
Cron (рекоменд.): 0 3 * * * (flock).
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from management.models import CommandRunLog


class Command(BaseCommand):
    help = "Releases due frozen commission ledger entries (frozen -> available)."

    def handle(self, *args, **options):
        from management.services.ledger import release_due

        run_log = CommandRunLog.objects.create(
            command_name="release_frozen_commissions",
            run_key=f"release_frozen_commissions:{timezone.now().isoformat()}",
            meta={},
        )
        try:
            result = release_due()
            run_log.meta = result
            run_log.save(update_fields=["meta"])
            run_log.mark_finished(
                status=CommandRunLog.Status.SUCCESS,
                rows_processed=result.get("released", 0),
                warnings_count=result.get("skipped_cancelled", 0),
            )
        except Exception as exc:
            run_log.mark_finished(status=CommandRunLog.Status.FAILED, error_excerpt=str(exc)[:500])
            raise

        self.stdout.write(self.style.SUCCESS(
            f"Released {result.get('released', 0)} entry(ies); cancelled {result.get('skipped_cancelled', 0)}."
        ))
