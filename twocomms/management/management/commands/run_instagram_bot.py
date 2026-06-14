"""
Поллер Instagram-бота.

Запускається кроном раз на хвилину; всередині крутить короткий цикл, опитуючи
інбокс кожні N секунд (poll_interval_seconds) протягом ~runtime секунд. Так
ми отримуємо майже миттєву відповідь (~3 c) без постійного демона, який на
Passenger-хостингу жити не може.

Реагує лише коли бот увімкнено (is_enabled). Захищений локом у кеші, щоб два
крон-запуски не накладались.

Приклади:
  python manage.py run_instagram_bot            # ~55 c циклу
  python manage.py run_instagram_bot --once     # один прохід (для тесту)
  python manage.py run_instagram_bot --runtime 55 --interval 3
"""
import time

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.utils import timezone

from management.models import InstagramBotSettings
from management.services import instagram_bot as bot

LOCK_KEY = "ig_bot_poller_lock"
LOCK_TTL = 70  # трохи більше за хвилину


class Command(BaseCommand):
    help = "Поллер Instagram-бота (запускати кроном щохвилини)."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Один прохід і вихід.")
        parser.add_argument("--runtime", type=int, default=55, help="Тривалість циклу, c.")
        parser.add_argument("--interval", type=int, default=0, help="Пауза між опитуваннями, c (0 = з налаштувань).")

    def handle(self, *args, **opts):
        # Лок проти накладання крон-запусків.
        if not cache.add(LOCK_KEY, "1", LOCK_TTL):
            self.stdout.write("Інший поллер вже працює — вихід.")
            return

        try:
            settings_obj = InstagramBotSettings.load()
            interval = opts["interval"] or settings_obj.poll_interval_seconds or 3
            interval = max(2, interval)

            if opts["once"]:
                res = bot.poll_once(settings_obj)
                self.stdout.write(f"poll_once: {res}")
                return

            deadline = time.monotonic() + max(5, opts["runtime"])
            cycles = 0
            while time.monotonic() < deadline:
                # Перечитуємо налаштування щоб одразу ловити Stop.
                settings_obj = InstagramBotSettings.load()
                res = bot.poll_once(settings_obj)
                cycles += 1
                # Подовжуємо лок.
                cache.set(LOCK_KEY, "1", LOCK_TTL)
                time.sleep(interval)
            self.stdout.write(
                f"{timezone.now():%H:%M:%S} done, cycles={cycles}, interval={interval}s"
            )
        finally:
            cache.delete(LOCK_KEY)
