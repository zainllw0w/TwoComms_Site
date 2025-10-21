from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError, ProgrammingError


class Command(BaseCommand):
    help = "Включает slow query log и задает порог long_query_time для MySQL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--long-query-time",
            type=float,
            default=2.0,
            help="Новый порог long_query_time в секундах (по умолчанию 2 секунды).",
        )
        parser.add_argument(
            "--log-file",
            type=str,
            default=None,
            help="Необязательный путь к slow query log файлу (оставьте пустым, чтобы не менять текущий).",
        )

    def handle(self, *args, **options):
        long_query_time = max(options["long_query_time"], 0.1)
        slow_log_file = options["log_file"]

        try:
            with connection.cursor() as cursor:
                cursor.execute("SET GLOBAL slow_query_log = 'ON'")
                cursor.execute("SET GLOBAL long_query_time = %s", [long_query_time])
                if slow_log_file:
                    cursor.execute("SET GLOBAL slow_query_log_file = %s", [slow_log_file])
        except (OperationalError, ProgrammingError) as exc:
            self.stderr.write(
                self.style.ERROR(
                    "Не удалось включить slow query log. Проверьте привилегии БД: "
                    f"{exc}"
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Slow query log включен. long_query_time = {long_query_time:g} секунд."
            )
        )
        if slow_log_file:
            self.stdout.write(self.style.SUCCESS(f"Путь к журналу: {slow_log_file}"))
