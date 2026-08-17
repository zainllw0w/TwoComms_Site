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

def _daily_cap() -> int:
    try:
        return int(os.environ.get("GEMINI_CALL_ANALYSIS_DAILY_CAP", "200"))
    except (TypeError, ValueError):
        return 200


class _AutoAnalysisDisabled(Exception):
    """Stop the current run without consuming or changing queued work."""


class Command(BaseCommand):
    help = "Прогнати чергу авто ШІ-аналізу записів дзвінків (для cron)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=15, help="Скільки записів за один прогін.")
        parser.add_argument("--dry-run", action="store_true", help="Лише показати кандидатів.")

    def handle(self, *args, **options):
        limit = max(1, int(options["limit"]))
        dry = bool(options["dry_run"])
        # This check deliberately precedes heartbeat, model and provider imports.
        from management.services.call_auto_analysis import is_call_auto_analysis_enabled

        if not is_call_auto_analysis_enabled():
            self.stdout.write("Автоаналіз дзвінків вимкнено; пропуск.")
            return
        if dry:
            return self._handle(limit=limit, dry=True)

        from management.services.ig_task_health import task_heartbeat

        with task_heartbeat("binotel_call_ai_analyses"):
            return self._handle(limit=limit, dry=False)

    def _handle(self, *, limit: int, dry: bool):
        from management.services.call_auto_analysis import is_call_auto_analysis_enabled

        if not is_call_auto_analysis_enabled():
            self.stdout.write("Автоаналіз дзвінків вимкнено; пропуск.")
            return

        # Keep the expensive ORM/provider modules out of the disabled path.
        from management.models import CallAIAnalysis, CallRecord, InstagramBotSettings
        from management.services.call_ai_analysis import CallAIAnalysisError
        from management.services.call_ai_queue import (
            ANALYSIS_DELAY_SECONDS,
            ELIGIBLE,
            INELIGIBLE,
            MAX_ANALYSIS_ATTEMPTS,
            METADATA_PENDING,
            STALE_ANALYSIS_LOCK_MINUTES,
            analysis_queue_category,
        )

        if not is_call_auto_analysis_enabled():
            self.stdout.write("Автоаналіз дзвінків вимкнено; пропуск.")
            return

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

        processed = 0
        for rec_id in ids:
            if not is_call_auto_analysis_enabled():
                self.stdout.write("Автоаналіз дзвінків вимкнено; чергу збережено.")
                break
            # Атомарний лок.
            with transaction.atomic():
                settings_row = (
                    InstagramBotSettings.objects.select_for_update()
                    .filter(pk=1)
                    .first()
                )
                if settings_row is None or not is_call_auto_analysis_enabled():
                    self.stdout.write(
                        "Автоаналіз дзвінків вимкнено; чергу збережено."
                    )
                    break
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
            if not is_call_auto_analysis_enabled():
                rec.refresh_from_db(fields=["ai_attempts"])
                rec.ai_status = CallRecord.AiStatus.PENDING
                rec.ai_locked_at = None
                rec.ai_attempts = max(0, int(rec.ai_attempts or 0) - 1)
                rec.save(update_fields=["ai_status", "ai_locked_at", "ai_attempts", "updated_at"])
                break

            try:
                queue_category = analysis_queue_category(rec.payload, rec.duration_seconds)
                if queue_category == METADATA_PENDING:
                    if not is_call_auto_analysis_enabled():
                        raise _AutoAnalysisDisabled
                    from management.services.call_ai_analysis import BinotelClient, upsert_call_record

                    client = BinotelClient.from_settings()
                    if not is_call_auto_analysis_enabled():
                        raise _AutoAnalysisDisabled
                    rec = upsert_call_record(
                        client,
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
                if not is_call_auto_analysis_enabled():
                    raise _AutoAnalysisDisabled
                from management.services.call_ai_analysis import analyze_call

                analysis_attempts_today += 1
                analysis = analyze_call(rec.external_call_id, force=True)
                # Once the provider request has started it may complete while
                # an administrator turns the switch off. Persist that one
                # completed result; the next record is gated at loop entry.
                ok = analysis.status == CallAIAnalysis.Status.DONE
            except _AutoAnalysisDisabled:
                rec.refresh_from_db(fields=["ai_attempts"])
                completed = rec.ai_analyses.filter(
                    status=CallAIAnalysis.Status.DONE
                ).exists()
                rec.ai_status = (
                    CallRecord.AiStatus.DONE
                    if completed
                    else CallRecord.AiStatus.PENDING
                )
                rec.ai_locked_at = None
                update_fields = ["ai_status", "ai_locked_at", "updated_at"]
                if not completed:
                    rec.ai_attempts = max(0, int(rec.ai_attempts or 0) - 1)
                    update_fields.append("ai_attempts")
                rec.save(update_fields=update_fields)
                break
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
