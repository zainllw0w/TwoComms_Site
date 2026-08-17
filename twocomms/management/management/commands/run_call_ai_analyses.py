"""
Cron-воркер авто ШІ-аналізу записів дзвінків.

Запускається крон-джобом кожні 5 хв. Бере CallRecord зі статусом
ai_status=pending, які:
  - мають generalCallID,
  - завершилися щонайменше ANALYSIS_DELAY_SECONDS тому (щоб запис устиг
    зʼявитися у провайдера),
  - завершили provider metadata hydration або ще очікують її.

Для кожного: атомарно бере «лок» (ai_status=running, ai_locked_at, ai_attempts++),
класифікує непридатні дзвінки без Gemini або викликає синхронний analyze_call,
після чого ставить ai_status=done / skipped / pending / error. Ретраї обмежені
MAX_ATTEMPTS. Денний кеп захищає від вигорання квоти Gemini.

Ідемпотентно: stale-лок (running старше STALE_LOCK_MINUTES) перепідбирається —
страховка від падіння процесу.
"""
from __future__ import annotations

import os
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from management.models import CallAIAnalysis, CallRecord
from management.services.call_ai_queue import (
    ANALYSIS_DELAY_SECONDS,
    ELIGIBLE,
    INELIGIBLE,
    MAX_ANALYSIS_ATTEMPTS,
    METADATA_PENDING,
    STALE_ANALYSIS_LOCK_MINUTES,
    analysis_queue_category,
)


def _daily_cap() -> int:
    try:
        return int(os.environ.get("GEMINI_CALL_ANALYSIS_DAILY_CAP", "200"))
    except (TypeError, ValueError):
        return 200


class Command(BaseCommand):
    help = "Прогнати чергу авто ШІ-аналізу записів дзвінків (для cron)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=15, help="Скільки записів за один прогін.")
        parser.add_argument("--dry-run", action="store_true", help="Лише показати кандидатів.")

    def handle(self, *args, **options):
        limit = max(1, int(options["limit"]))
        dry = bool(options["dry_run"])
        if dry:
            return self._handle(limit=limit, dry=True)

        from management.services.ig_task_health import task_heartbeat

        with task_heartbeat("binotel_call_ai_analyses"):
            return self._handle(limit=limit, dry=False)

    def _handle(self, *, limit: int, dry: bool):
        now = timezone.now()
        cutoff = now - timedelta(seconds=ANALYSIS_DELAY_SECONDS)
        stale = now - timedelta(minutes=STALE_ANALYSIS_LOCK_MINUTES)

        # The cap limits analysis calls, not hydration and queue reconciliation.
        start_day = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
        analysis_attempts_today = CallAIAnalysis.objects.filter(created_at__gte=start_day).count()
        cap = _daily_cap()

        # Stale work has priority so a constant pending queue cannot starve it.
        stale_running = list(
            CallRecord.objects.filter(
                Q(ai_locked_at__lte=stale) | Q(ai_locked_at__isnull=True),
                ai_status=CallRecord.AiStatus.RUNNING,
                provider="binotel",
            ).order_by(F("ai_locked_at").asc(nulls_first=True), "created_at", "id")[:limit]
        )
        remaining = max(0, limit - len(stale_running))
        pending = list(
            CallRecord.objects.filter(provider="binotel", ai_status=CallRecord.AiStatus.PENDING)
            .exclude(external_call_id="")
            .filter(created_at__lte=cutoff)
            .order_by("created_at", "id")[:remaining]
        )

        ids = [record.id for record in stale_running + pending]
        if not ids:
            self.stdout.write("Немає записів для аналізу.")
            return
        if dry:
            self.stdout.write(f"Кандидати: {ids}")
            return

        from management.services.call_ai_analysis import (
            BinotelClient,
            CallAIAnalysisError,
            analyze_call,
            upsert_call_record,
        )

        processed = 0
        for rec_id in ids:
            # Атомарний лок.
            with transaction.atomic():
                rec = CallRecord.objects.select_for_update().filter(id=rec_id).first()
                if not rec:
                    continue
                if rec.ai_status not in (CallRecord.AiStatus.PENDING, CallRecord.AiStatus.RUNNING):
                    continue
                if rec.ai_status == CallRecord.AiStatus.RUNNING and rec.ai_locked_at and rec.ai_locked_at > stale:
                    continue  # ще обробляється іншим процесом
                if (
                    rec.ai_status == CallRecord.AiStatus.RUNNING
                    and rec.ai_analyses.filter(status=CallAIAnalysis.Status.DONE).exists()
                ):
                    rec.ai_status = CallRecord.AiStatus.DONE
                    rec.ai_locked_at = None
                    rec.save(update_fields=["ai_status", "ai_locked_at", "updated_at"])
                    processed += 1
                    self.stdout.write(f"#{rec_id}: reconciled done")
                    continue
                if rec.ai_attempts >= MAX_ANALYSIS_ATTEMPTS:
                    rec.ai_status = CallRecord.AiStatus.ERROR
                    rec.ai_locked_at = None
                    rec.save(update_fields=["ai_status", "ai_locked_at", "updated_at"])
                    continue
                rec.ai_status = CallRecord.AiStatus.RUNNING
                rec.ai_locked_at = timezone.now()
                rec.ai_attempts = (rec.ai_attempts or 0) + 1
                rec.save(update_fields=["ai_status", "ai_locked_at", "ai_attempts", "updated_at"])

            # Поза транзакцією — довгий мережевий виклик.
            try:
                queue_category = analysis_queue_category(rec.payload, rec.duration_seconds)
                if queue_category == METADATA_PENDING:
                    rec = upsert_call_record(
                        BinotelClient.from_settings(),
                        rec.external_call_id,
                    )
                    queue_category = analysis_queue_category(rec.payload, rec.duration_seconds)
                if queue_category == METADATA_PENDING:
                    raise CallAIAnalysisError("Binotel metadata is not available yet.")
                if queue_category == INELIGIBLE:
                    rec.ai_status = CallRecord.AiStatus.SKIPPED
                    rec.ai_locked_at = None
                    rec.save(update_fields=["ai_status", "ai_locked_at", "updated_at"])
                    processed += 1
                    self.stdout.write(f"#{rec_id}: skipped")
                    continue
                if analysis_attempts_today >= cap:
                    rec.ai_status = CallRecord.AiStatus.PENDING
                    rec.ai_locked_at = None
                    rec.ai_attempts = max(0, int(rec.ai_attempts or 0) - 1)
                    rec.save(
                        update_fields=["ai_status", "ai_locked_at", "ai_attempts", "updated_at"]
                    )
                    self.stdout.write(
                        f"#{rec_id}: денний кеп досягнуто ({analysis_attempts_today}/{cap})"
                    )
                    continue
                analysis_attempts_today += 1
                analysis = analyze_call(rec.external_call_id, force=True)
                ok = analysis.status == CallAIAnalysis.Status.DONE
            except CallAIAnalysisError as exc:
                ok = False
                self.stderr.write(f"#{rec_id}: {exc}")
            except Exception as exc:  # не валимо весь прогін
                ok = False
                self.stderr.write(f"#{rec_id}: unexpected {exc}")

            rec.refresh_from_db(fields=["ai_attempts"])
            rec.ai_status = CallRecord.AiStatus.DONE if ok else (
                CallRecord.AiStatus.PENDING
                if rec.ai_attempts < MAX_ANALYSIS_ATTEMPTS
                else CallRecord.AiStatus.ERROR
            )
            rec.ai_locked_at = None
            rec.save(update_fields=["ai_status", "ai_locked_at", "updated_at"])
            processed += 1
            self.stdout.write(f"#{rec_id}: {'done' if ok else 'retry/error'}")

        self.stdout.write(f"Готово: оброблено {processed}.")
