"""Запускає вечірнє нагадування на Storage-бота (можна викликати з cron, якщо немає Celery)."""
from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Запускає вечірнє нагадування Storage-боту (синхронно, без Celery)"

    def handle(self, *args, **options):
        from warehouse.tasks import send_evening_reminder_task

        result = send_evening_reminder_task()
        self.stdout.write(self.style.SUCCESS(f"Готово: {result}"))
