"""
Cron-воркер авто ШІ-аналізу записів дзвінків.

Запускається крон-джобом кожні 1–2 хв. Бере CallRecord зі статусом
ai_status=pending, які:
  - мають generalCallID,
  - завершилися щонайменше ANALYSIS_DELAY_SECONDS тому (щоб запис устиг
    зʼявитися у провайдера),
  - тривали >= MEANINGFUL_SECONDS.

Для кожного: атомарно бере «лок» (ai_status=running, ai_locked_at, ai_attempts++),
викликає синхронний analyze_call (тут таймаути не страшні — це фон), і ставить
ai_status=done / error. Ретраї обмежені MAX_ATTEMPTS. Денний кеп захищає від
вигорання квоти Gemini.

Ідемпотентно: stale-лок (running старше STALE_LOCK_MINUTES) перепідбирається —
страховка від падіння процесу.
"""
from __future__ import annotations

import os
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from management.models import CallAIAnalysis, CallRecord

ANALYSIS_DELAY_SECONDS = 90
MEANINGFUL_SECONDS = 30
MAX_ATTEMPTS = 3
STALE_LOCK_MINUTES = 15


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
        now = timezone.now()
        cutoff = now - timedelta(seconds=ANALYSIS_DELAY_SECONDS)
        stale = now - timedelta(minutes=STALE_LOCK_MINUTES)

        # Денний кеп: скільки done+error за сьогодні.
        start_day = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
        done_today = CallAIAnalysis.objects.filter(created_at__gte=start_day).count()
        cap = _daily_cap()
        if done_today >= cap:
            self.stdout.write(f"Денний кеп досягнуто ({done_today}/{cap}). Пропуск.")
            return

        candidates = (
            CallRecord.objects.filter(ai_status=CallRecord.AiStatus.PENDING)
            .exclude(external_call_id="")
            .filter(duration_seconds__gte=MEANINGFUL_SECONDS)
            .filter(created_at__lte=cutoff)
            .order_by("created_at")[: limit * 2]
        )
        # Підхопити «завислі» running.
        stale_running = list(
            CallRecord.objects.filter(
                ai_status=CallRecord.AiStatus.RUNNING, ai_locked_at__lte=stale
            ).order_by("ai_locked_at")[:limit]
        )

        ids = [r.id for r in list(candidates) + stale_running][:limit]
        if not ids:
            self.stdout.write("Немає записів для аналізу.")
            return
        if dry:
            self.stdout.write(f"Кандидати: {ids}")
            return

        from management.services.call_ai_analysis import CallAIAnalysisError, analyze_call

        processed = 0
        for rec_id in ids:
            if done_today + processed >= cap:
                break
            # Атомарний лок.
            with transaction.atomic():
                rec = CallRecord.objects.select_for_update().filter(id=rec_id).first()
                if not rec:
                    continue
                if rec.ai_status not in (CallRecord.AiStatus.PENDING, CallRecord.AiStatus.RUNNING):
                    continue
                if rec.ai_status == CallRecord.AiStatus.RUNNING and rec.ai_locked_at and rec.ai_locked_at > stale:
                    continue  # ще обробляється іншим процесом
                if rec.ai_attempts >= MAX_ATTEMPTS:
                    rec.ai_status = CallRecord.AiStatus.ERROR
                    rec.save(update_fields=["ai_status", "updated_at"])
                    continue
                rec.ai_status = CallRecord.AiStatus.RUNNING
                rec.ai_locked_at = timezone.now()
                rec.ai_attempts = (rec.ai_attempts or 0) + 1
                rec.save(update_fields=["ai_status", "ai_locked_at", "ai_attempts", "updated_at"])

            # Поза транзакцією — довгий мережевий виклик.
            try:
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
                CallRecord.AiStatus.PENDING if rec.ai_attempts < MAX_ATTEMPTS else CallRecord.AiStatus.ERROR
            )
            rec.save(update_fields=["ai_status", "updated_at"])
            processed += 1
            self.stdout.write(f"#{rec_id}: {'done' if ok else 'retry/error'}")

        self.stdout.write(f"Готово: оброблено {processed}.")
