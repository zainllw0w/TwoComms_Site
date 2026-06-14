"""
Раннер Instagram-бота.

Режими:
  --forever   Постійний демон: онлайн весь час, опитує інбокс кожні N секунд.
              Це основний режим — агент «живе» постійно, а не запускається кроном.
  --ensure    Watchdog: якщо демон живий (свіжий heartbeat) — нічого не робить;
              якщо помер (рестарт сервера/деплой/збій) — піднімає демона
              відв'язаним процесом. Саме цей режим чіпляємо в cron раз на хвилину —
              cron НЕ робить запитів до API, лише підстраховує, що демон живий.
  --once      Один прохід опитування (для діагностики).

Демон-singleton тримається через кеш-heartbeat: другий демон не стартує, поки
живий перший. Кожна ітерація викликає close_old_connections() — інакше на
shared-MySQL (wait_timeout=60) з'являється "MySQL server has gone away".
"""
import os
import subprocess
import sys
import time

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from management.models import InstagramBotSettings
from management.services import instagram_bot as bot

HB_KEY = "ig_bot_daemon_hb"            # heartbeat демона (epoch seconds)
HB_ALIVE_WINDOW = 45                   # демон вважається живим, якщо hb свіжіший
SPAWN_LOCK_KEY = "ig_bot_spawn_lock"
PID_FILE = "tmp/ig_bot.pid"


def _daemon_alive() -> bool:
    hb = cache.get(HB_KEY)
    return bool(hb and (time.time() - float(hb)) < HB_ALIVE_WINDOW)


class Command(BaseCommand):
    help = "Раннер Instagram-бота (демон / watchdog / одиночний прохід)."

    def add_arguments(self, parser):
        parser.add_argument("--forever", action="store_true", help="Постійний демон.")
        parser.add_argument("--ensure", action="store_true", help="Watchdog: підняти демона, якщо мертвий.")
        parser.add_argument("--once", action="store_true", help="Один прохід.")

    def handle(self, *args, **opts):
        if opts["once"]:
            res = bot.poll_once(InstagramBotSettings.load())
            self.stdout.write(f"poll_once: {res}")
            return

        if opts["ensure"]:
            return self._ensure()

        if opts["forever"]:
            return self._forever()

        self.stdout.write("Вкажіть режим: --forever | --ensure | --once")

    # ------------------------------------------------------------------
    def _ensure(self):
        if _daemon_alive():
            self.stdout.write("daemon alive — ok")
            return
        # Захист від подвійного спавну.
        if not cache.add(SPAWN_LOCK_KEY, "1", 30):
            self.stdout.write("spawn in progress — skip")
            return
        manage_py = sys.argv[0]
        log_path = os.path.join(os.getcwd(), "tmp", "ig_bot_daemon.log")
        try:
            with open(log_path, "a") as logf:
                subprocess.Popen(
                    [sys.executable, manage_py, "run_instagram_bot", "--forever"],
                    stdout=logf,
                    stderr=logf,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,  # відв'язуємо (setsid) — переживе cron
                    env=os.environ.copy(),
                )
            bot.log("info", "daemon_spawn", "watchdog підняв демона")
            self.stdout.write("daemon spawned")
        except Exception as exc:
            self.stdout.write(f"spawn failed: {exc!r}")

    # ------------------------------------------------------------------
    def _forever(self):
        # Singleton: не стартуємо другий демон поверх живого.
        if _daemon_alive():
            self.stdout.write("daemon already alive — exit")
            return
        cache.set(HB_KEY, time.time(), HB_ALIVE_WINDOW * 3)
        try:
            with open(PID_FILE, "w") as f:
                f.write(str(os.getpid()))
        except Exception:
            pass
        bot.log("success", "daemon_start", f"Демон онлайн (pid {os.getpid()}).")

        idle_streak = 0
        while True:
            close_old_connections()  # лікує "MySQL server has gone away"
            try:
                s = InstagramBotSettings.load()
                res = bot.poll_once(s)
                interval = max(2, s.poll_interval_seconds or 3)
                if not res.get("enabled"):
                    interval = 5  # вимкнено — опитуємо рідше, але лишаємось онлайн
            except Exception as exc:
                bot.log("error", "daemon_loop", repr(exc))
                interval = 5
            finally:
                cache.set(HB_KEY, time.time(), HB_ALIVE_WINDOW * 3)
            time.sleep(interval)
