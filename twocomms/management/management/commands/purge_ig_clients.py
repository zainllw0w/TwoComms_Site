"""Чистить картки IG-клієнтів, неактивні понад N днів (ретеншн 6 міс).

Запуск кроном раз на добу:
    python manage.py purge_ig_clients            # 180 днів за замовчуванням
    python manage.py purge_ig_clients --days 365
"""
from django.core.management.base import BaseCommand

from management.services import bot_memory


class Command(BaseCommand):
    help = "Видаляє IG-картки, неактивні понад --days (каскадом — їх повідомлення)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=bot_memory.RETENTION_DAYS)

    def handle(self, *args, **opts):
        days = opts.get("days") or bot_memory.RETENTION_DAYS
        n = bot_memory.purge_stale_clients(days=days)
        self.stdout.write(self.style.SUCCESS(f"Видалено карток: {n} (неактивні понад {days} днів)."))
