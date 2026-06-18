"""Cron-команда авто-чекінгу AI-чекера.

Викликається кроном (наприклад, кожні 5 хв). Якщо у налаштуваннях чекера
ввімкнено «Авто-чекінг» і є вільний ключ checker-пулу та непроверені ліди —
продовжує перевірку наступного батчу. Інакше — тихо виходить.

Приклад crontab (кожні 5 хв):
  */5 * * * * cd /path/twocomms && /path/venv/bin/python manage.py checker_tick >> tmp/checker_tick.log 2>&1
"""
from django.core.management.base import BaseCommand

from management.services import lead_check_job as ljob


class Command(BaseCommand):
    help = "Авто-чекінг AI-чекера: продовжує перевірку, щойно квота відновлюється."

    def add_arguments(self, parser):
        parser.add_argument("--max-seconds", type=int, default=240,
                            help="Максимальний час одного проходу, сек.")

    def handle(self, *args, **options):
        result = ljob.auto_recheck_tick(max_seconds=options["max_seconds"])
        self.stdout.write(self.style.SUCCESS(f"checker_tick: {result}"))
