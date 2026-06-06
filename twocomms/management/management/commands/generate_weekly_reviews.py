"""
Генерує ManagerWeeklyReview за попередній тиждень (факти KPI без рішення).

Рішення приймає адмін у адмін-центрі. Ідемпотентно: вже вирішені відгуки
не перезаписуються.

Док: twocomms/Management Implementations/07 (7.3) + 09 (9.1).
Cron (рекоменд.): 30 0 * * 1 (понеділок, flock).
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from management.models import CommandRunLog


class Command(BaseCommand):
    help = "Generates ManagerWeeklyReview rows for the previous week (KPI facts, no decision)."

    def add_arguments(self, parser):
        parser.add_argument("--week-start", dest="week_start", help="Monday of the week (YYYY-MM-DD).")
        parser.add_argument("--user-id", dest="user_id", type=int)

    def handle(self, *args, **options):
        from management.services.weekly_review import week_bounds, previous_week_bounds, generate_for_week

        raw = options.get("week_start")
        if raw:
            try:
                ref = date.fromisoformat(raw)
            except ValueError as exc:
                raise CommandError("Invalid --week-start. Use YYYY-MM-DD.") from exc
            week_start, week_end = week_bounds(ref)
        else:
            week_start, week_end = previous_week_bounds()

        run_log = CommandRunLog.objects.create(
            command_name="generate_weekly_reviews",
            run_key=f"generate_weekly_reviews:{week_start.isoformat()}:{options.get('user_id') or 'all'}",
            meta={"week_start": week_start.isoformat(), "week_end": week_end.isoformat()},
        )
        try:
            result = generate_for_week(week_start, week_end, only_user=options.get("user_id"))
            run_log.meta = {**run_log.meta, **result}
            run_log.save(update_fields=["meta"])
            run_log.mark_finished(
                status=CommandRunLog.Status.SUCCESS,
                rows_processed=result.get("created", 0) + result.get("updated", 0),
            )
        except Exception as exc:
            run_log.mark_finished(status=CommandRunLog.Status.FAILED, error_excerpt=str(exc)[:500])
            raise

        self.stdout.write(self.style.SUCCESS(
            f"Weekly reviews for {week_start}..{week_end}: created {result.get('created',0)}, updated {result.get('updated',0)}."
        ))
