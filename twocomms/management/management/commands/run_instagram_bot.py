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

Демон-singleton тримається через OS advisory lock: другий демон не стартує,
навіть якщо FileBasedCache очищений або недоступний. Кожна ітерація викликає close_old_connections() — інакше на
shared-MySQL (wait_timeout=60) з'являється "MySQL server has gone away".
"""
import os
import fcntl
import subprocess
import sys
import threading
import time
from pathlib import Path
from contextlib import contextmanager

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, connection
from django.utils import timezone

from management.models import InstagramBotSettings
from management.services import bot_followups, bot_payments
from management.services import instagram_bot as bot
from management.services.ig_task_health import (
    check_task_health,
    ensure_task_expectations,
    task_heartbeat,
)
from management.services.ig_maintenance import (
    DEFAULT_MAINTENANCE_SECONDS,
    MAINTENANCE_FILE,
    MaintenanceLeaseConflict,
    activate_maintenance,
    deactivate_maintenance,
    maintenance_status,
    runtime_root,
)

HB_KEY = "ig_bot_daemon_hb"            # heartbeat демона (epoch seconds)
HB_ALIVE_WINDOW = 45                   # демон вважається живим, якщо hb свіжіший
SPAWN_LOCK_KEY = "ig_bot_spawn_lock"
DAEMON_LOCK_KEY = "ig_bot_daemon_lock"
CONV_REFRESH_EVERY = 120               # фонове оновлення списку тредів, c
CONV_REFRESH_PROGRESS_EVERY = 5        # швидко завершуємо resumable scan
ANALYSIS_RECONCILE_EVERY = 600         # bounded repair of missed scheduling, c
ANALYSIS_RECONCILE_BATCH = 100
RELOAD_LOCK_WAIT_SECONDS = 45
MAX_RELOAD_LOCK_WAIT_SECONDS = 300
DAEMON_START_WAIT_SECONDS = 15
TASK_HEALTH_CHECK_EVERY = 60

# Cron may invoke manage.py from an arbitrary working directory. Resolve the
# entry point from this command module and keep the child in the Django root.
PROJECT_ROOT = str(runtime_root())
MANAGE_PY_PATH = str(Path(PROJECT_ROOT) / "manage.py")
PID_FILE = os.path.join(PROJECT_ROOT, "tmp", "ig_bot.pid")
SPAWN_LOCK_FILE = os.path.join(PROJECT_ROOT, "tmp", "ig_bot_spawn.lock")
DAEMON_LOCK_FILE = os.path.join(PROJECT_ROOT, "tmp", "ig_bot_daemon.lock")


@contextmanager
def _try_process_lock(path: str):
    """Yield an open lock handle, or ``None`` when another process owns it."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    handle = open(path, "a+")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            yield None
            return
        yield handle
    finally:
        if not handle.closed:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()


def _process_lock_held(path: str) -> bool:
    with _try_process_lock(path) as handle:
        return handle is None


def _wait_for_lock(path: str, *, held: bool, timeout: float = 6.0) -> bool:
    deadline = time.monotonic() + max(0.0, timeout)
    while time.monotonic() < deadline:
        if _process_lock_held(path) is held:
            return True
        time.sleep(0.1)
    return _process_lock_held(path) is held


def _bounded_reload_lock_wait(value: int | float | None) -> float:
    """Validate the operator-controlled drain wait without allowing infinity."""
    if value is None:
        return float(RELOAD_LOCK_WAIT_SECONDS)
    try:
        wait_seconds = float(value)
    except (TypeError, ValueError) as exc:
        raise CommandError("maintenance lock wait must be a number") from exc
    if not 0 <= wait_seconds <= MAX_RELOAD_LOCK_WAIT_SECONDS:
        raise CommandError(
            "maintenance lock wait must be between 0 and "
            f"{MAX_RELOAD_LOCK_WAIT_SECONDS} seconds"
        )
    return wait_seconds


def _daemon_alive() -> bool:
    hb = cache.get(HB_KEY)
    try:
        heartbeat_at = float(hb.get("at")) if isinstance(hb, dict) else float(hb)
    except (TypeError, ValueError, AttributeError):
        return False
    return bool(heartbeat_at and (time.time() - heartbeat_at) < HB_ALIVE_WINDOW)


def _restart_sentinel_mtime() -> float:
    """mtime файлу tmp/restart.txt — маркер деплою (його torkає кожен git pull).
    Демон стежить за ним і перезавантажується, коли код оновлено."""
    try:
        return os.path.getmtime(os.path.join(PROJECT_ROOT, "tmp", "restart.txt"))
    except OSError:
        return 0.0


def _daemon_code_current() -> bool:
    """A fresh heartbeat from a process started before deploy is not usable."""
    try:
        return os.path.getmtime(PID_FILE) >= _restart_sentinel_mtime()
    except OSError:
        return False


def _conversation_refresh_wait_seconds(s: InstagramBotSettings) -> int:
    """Use a short cadence only while a resumable scan is making progress."""
    if (
        str(getattr(s, "conversation_discovery_cursor", "") or "").strip()
        and not bot._current_ingress_degradation(s)
    ):
        return CONV_REFRESH_PROGRESS_EVERY
    return CONV_REFRESH_EVERY


def _conv_refresher(stop_event: threading.Event):
    """Фоновий потік: рідко оновлює список тредів (важкий ~25 c виклик),
    тільки коли увімкнено резервний поллінг."""
    while not stop_event.is_set():
        wait_seconds = CONV_REFRESH_EVERY
        try:
            close_old_connections()
            s = InstagramBotSettings.load()
            if s.receive_via_poll and bot._provider_account_id(s):
                token = bot.get_page_token(s)
                if token:
                    bot.refresh_conv_ids(s, token)
                    s.refresh_from_db(fields=["conversation_discovery_cursor"])
                    wait_seconds = _conversation_refresh_wait_seconds(s)
        except Exception as exc:
            try:
                bot.log("warning", "conv_refresh", repr(exc))
            except Exception:
                pass
        stop_event.wait(wait_seconds)


def _analysis_worker(stop_event: threading.Event):
    """Drain durable CRM-analysis jobs without coupling them to reply enablement."""
    from management.services.bot_conversation_analysis import (
        process_due_analysis,
        reconcile_analysis_jobs,
    )
    from management.services.ig_analysis_events import process_due_analysis_events

    last_reconcile_at = None
    while not stop_event.is_set():
        try:
            close_old_connections()
            if not maintenance_status(path=MAINTENANCE_FILE)["active"]:
                monotonic_now = time.monotonic()
                if (
                    last_reconcile_at is None
                    or monotonic_now - last_reconcile_at >= ANALYSIS_RECONCILE_EVERY
                ):
                    try:
                        reconcile_analysis_jobs(limit=ANALYSIS_RECONCILE_BATCH)
                    except Exception as exc:
                        try:
                            bot.log(
                                "error",
                                "conversation_analysis_reconcile",
                                repr(exc),
                            )
                        except Exception:
                            pass
                    else:
                        last_reconcile_at = monotonic_now
                try:
                    process_due_analysis(limit=1)
                except Exception as exc:
                    try:
                        bot.log("error", "conversation_analysis_due", repr(exc))
                    except Exception:
                        pass
                try:
                    event_result = process_due_analysis_events(limit=1)
                    terminal_rejected = int(event_result.get("rejected", 0) or 0)
                    terminal_failed = int(event_result.get("failed", 0) or 0)
                    if terminal_rejected or terminal_failed:
                        bot.log(
                            "error" if terminal_failed else "warning",
                            "conversation_analysis_events_terminal",
                            f"rejected={terminal_rejected} failed={terminal_failed}",
                        )
                except Exception as exc:
                    try:
                        bot.log("error", "conversation_analysis_events", repr(exc))
                    except Exception:
                        pass
        except Exception as exc:
            try:
                bot.log("error", "conversation_analysis", repr(exc))
            except Exception:
                pass
        finally:
            close_old_connections()
        stop_event.wait(5)


def _ai_reply_recovery_worker(stop_event: threading.Event):
    """Drain one failed live-reply recovery independently of deep analysis."""
    from management.services.ig_ai_reply_recovery import process_due_recoveries

    while not stop_event.is_set():
        worked = False
        try:
            close_old_connections()
            if not maintenance_status(path=MAINTENANCE_FILE)["active"]:
                worked = bool(process_due_recoveries(limit=1))
        except Exception as exc:
            try:
                bot.log("error", "ai_reply_recovery", repr(exc))
            except Exception:
                pass
        finally:
            close_old_connections()
        if stop_event.wait(0.5 if worked else 2):
            break


def _permission_transition_worker(stop_event: threading.Event):
    """Apply durable reply-permission changes outside the webhook thread."""
    from management.services.ig_permission_transitions import (
        process_due_permission_transitions,
    )

    while not stop_event.is_set():
        worked = False
        try:
            close_old_connections()
            if not maintenance_status(path=MAINTENANCE_FILE)["active"]:
                worked = bool(process_due_permission_transitions(limit=1))
        except Exception as exc:
            try:
                bot.log(
                    "error",
                    "permission_transition",
                    exc.__class__.__name__,
                )
            except Exception:
                pass
        finally:
            close_old_connections()
        if stop_event.wait(0.25 if worked else 1):
            break


def _inbox_refresh_worker(stop_event: threading.Event):
    """Drain administrator-requested inbox recovery outside the reply loop."""
    from management.services.ig_inbox_refresh import process_refresh_slice

    while not stop_event.is_set():
        worked = False
        try:
            close_old_connections()
            if not maintenance_status(path=MAINTENANCE_FILE)["active"]:
                result = process_refresh_slice()
                worked = bool(result.get("worked")) if isinstance(result, dict) else False
        except Exception as exc:
            try:
                bot.log("error", "inbox_refresh", repr(exc))
            except Exception:
                pass
        finally:
            close_old_connections()
        if stop_event.wait(0.25 if worked else 2):
            break


def _checkout_lifecycle_worker(stop_event: threading.Event):
    """Drain payment/TTN/delivery events without coupling them to inbox replies."""
    from management.services.ig_lifecycle import dispatch_due_lifecycle_events

    while not stop_event.is_set():
        try:
            close_old_connections()
            if not maintenance_status(path=MAINTENANCE_FILE)["active"]:
                dispatch_due_lifecycle_events(limit=10)
        except Exception as exc:
            try:
                bot.log("error", "ig_checkout_lifecycle", repr(exc))
            except Exception:
                pass
        finally:
            close_old_connections()
        if stop_event.wait(5):
            break


def _follow_intelligence_worker(stop_event: threading.Event):
    """Drain demand-created follow jobs and mandatory UGC delivery fairly."""
    from management.services.ig_follow_reconcile import (
        reconcile_follow_intelligence_once,
    )

    while not stop_event.is_set():
        worked = False
        try:
            close_old_connections()
            if not maintenance_status(path=MAINTENANCE_FILE)["active"]:
                counts = reconcile_follow_intelligence_once(limit=10)
                worked = bool(
                    int(counts.get("payment_selected", 0) or 0)
                    + int(counts.get("follow_selected", 0) or 0)
                    + int(counts.get("ugc_selected", 0) or 0)
                )
        except Exception as exc:
            try:
                bot.log("error", "ig_follow_intelligence", repr(exc))
            except Exception:
                pass
        finally:
            close_old_connections()
        if stop_event.wait(0.5 if worked else 5):
            break


def _reconcile_commercial_episodes_after_reload():
    """Repair source rows written by old workers during the deploy window."""
    from django.core.management import call_command

    close_old_connections()
    try:
        call_command("reconcile_ig_commercial_episodes", passes=3)
    finally:
        close_old_connections()


def _process_order_fulfillment():
    """Drain bounded durable order notifications without breaking the daemon."""
    try:
        from management.services.ig_order_fulfillment import (
            reconcile_order_customer_events,
        )

        reconcile_order_customer_events(limit=10, send=True)
    except Exception as exc:
        bot.log("error", "order_fulfillment", repr(exc))


def _run_work_cycle(settings_obj, last_poll: float) -> tuple[bool, float]:
    """Run durable operational work, then reply work only when enabled."""
    enabled = bool(settings_obj.is_enabled)
    interval = max(2, settings_obj.poll_interval_seconds or 3)
    try:
        bot.drain_manager_notifications(limit=10)
    except Exception as exc:
        # Manager-alert availability must never become a global customer-reply
        # kill switch. The next cycle retries and the error remains visible in
        # the operational log/status surface.
        bot.log("error", "notification_outbox", repr(exc))
    try:
        bot_payments.poll_pending_deals_locked(limit=50)
    except Exception as exc:
        bot.log("error", "payment_poll_backstop", repr(exc))
    profile_key = f"ig_profile_batch:{bot._provider_owner_id(settings_obj)}"
    if cache.add(profile_key, "1", timeout=bot.PROFILE_REFRESH_INTERVAL):
        try:
            bot.refresh_profiles_batch(settings_obj)
        except Exception as exc:
            bot.log("warning", "profile_refresh_batch", repr(exc))
    if enabled:
        bot.process_pending(settings_obj)
        if maintenance_status(path=MAINTENANCE_FILE)["active"]:
            return enabled, last_poll
        bot_followups.process_due_followups(settings_obj)
        if settings_obj.pk:
            _process_order_fulfillment()
    now = time.time()
    if settings_obj.receive_via_poll and (now - last_poll) >= interval:
        poll_result = bot.poll_ingest(settings_obj)
        if isinstance(poll_result, dict) and settings_obj.pk:
            poll_ok = bool(poll_result.get("ok")) and not bool(
                poll_result.get("degraded") or poll_result.get("refresh_pending")
            )
            if poll_ok:
                settings_obj.last_poll_at = timezone.now()
                if settings_obj.last_error.startswith("polling:"):
                    settings_obj.last_error = ""
            else:
                reason = (
                    poll_result.get("error")
                    or poll_result.get("reason")
                    or "provider_unavailable"
                )
                settings_obj.last_error = f"polling:{reason}"[:2000]
            settings_obj.save(update_fields=["last_poll_at", "last_error", "updated_at"])
        if enabled:
            bot.process_pending(settings_obj)
            if maintenance_status(path=MAINTENANCE_FILE)["active"]:
                return enabled, last_poll
            bot_followups.process_due_followups(settings_obj)
        last_poll = now
    return enabled, last_poll


class Command(BaseCommand):
    help = "Раннер Instagram-бота (демон / watchdog / одиночний прохід)."

    @staticmethod
    def _guard_runtime_database() -> None:
        """Never let a production-like bot silently operate on SQLite."""
        if not settings.DEBUG and connection.vendor == "sqlite":
            raise CommandError(
                "run_instagram_bot refuses SQLite when DEBUG=False; "
                "configure the CloudLinux-bound MariaDB runtime"
            )

    def add_arguments(self, parser):
        parser.add_argument("--forever", action="store_true", help="Постійний демон.")
        parser.add_argument("--ensure", action="store_true", help="Watchdog: підняти демона, якщо мертвий.")
        parser.add_argument("--once", action="store_true", help="Один прохід.")
        parser.add_argument(
            "--maintenance-on",
            nargs="?",
            const=DEFAULT_MAINTENANCE_SECONDS,
            type=int,
            metavar="SECONDS",
            help="Зупинити daemon і заблокувати watchdog на обмежений час.",
        )
        parser.add_argument(
            "--maintenance-off",
            metavar="LEASE_ID",
            help="Зняти лише власний maintenance lease; потім запустіть --ensure.",
        )
        parser.add_argument(
            "--maintenance-lease-id",
            metavar="LEASE_ID",
            help="Внутрішній token для атомарного maintenance-on від release orchestrator.",
        )
        parser.add_argument(
            "--maintenance-wait-seconds",
            type=float,
            metavar="SECONDS",
            help=(
                "Максимальний час очікування штатного звільнення daemon lock "
                f"(0..{MAX_RELOAD_LOCK_WAIT_SECONDS})."
            ),
        )

    def handle(self, *args, **opts):
        selected = sum(
            bool(opts.get(name))
            for name in ("once", "ensure", "forever")
        )
        selected += int(opts.get("maintenance_on") is not None)
        selected += int(opts.get("maintenance_off") is not None)
        if selected > 1:
            raise CommandError("choose exactly one daemon mode")
        if opts.get("maintenance_lease_id") and opts.get("maintenance_on") is None:
            raise CommandError("--maintenance-lease-id requires --maintenance-on")
        if opts.get("maintenance_on") is not None:
            return self._maintenance_on(
                opts["maintenance_on"],
                requested_lease_id=opts.get("maintenance_lease_id"),
                wait_seconds=opts.get("maintenance_wait_seconds"),
            )
        if opts.get("maintenance_off") is not None:
            try:
                deactivate_maintenance(
                    lease_id=opts["maintenance_off"],
                    path=MAINTENANCE_FILE,
                )
            except MaintenanceLeaseConflict as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write("maintenance disabled")
            return
        if opts["once"] or opts["ensure"] or opts["forever"]:
            self._guard_runtime_database()
        if opts["once"]:
            if maintenance_status(path=MAINTENANCE_FILE)["active"]:
                raise CommandError("maintenance active — --once refused")
            res = bot.poll_once(InstagramBotSettings.load())
            self.stdout.write(f"poll_once: {res}")
            return

        if opts["ensure"]:
            with task_heartbeat("ig_daemon_watchdog"):
                return self._ensure()

        if opts["forever"]:
            return self._forever()

        self.stdout.write(
            "Вкажіть режим: --forever | --ensure | --once | --maintenance-on | --maintenance-off"
        )

    def _maintenance_on(
        self,
        duration_seconds: int,
        *,
        requested_lease_id: str | None = None,
        wait_seconds: int | float | None = None,
    ):
        bounded_wait = _bounded_reload_lock_wait(wait_seconds)
        try:
            payload = activate_maintenance(
                path=MAINTENANCE_FILE,
                duration_seconds=duration_seconds,
                actor="run_instagram_bot",
                requested_lease_id=requested_lease_id,
            )
        except (MaintenanceLeaseConflict, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        # The daemon observes the lease before its next work cycle. Do not
        # report a safe maintenance boundary until its OS singleton is free.
        if _process_lock_held(DAEMON_LOCK_FILE) and not _wait_for_lock(
            DAEMON_LOCK_FILE,
            held=False,
            timeout=bounded_wait,
        ):
            try:
                deactivate_maintenance(
                    path=MAINTENANCE_FILE,
                    lease_id=str(payload["lease_id"]),
                )
            except MaintenanceLeaseConflict:
                # Another owner replaced the marker after activation. Exact
                # token cleanup must preserve that newer lease.
                pass
            except OSError as exc:
                raise CommandError(
                    "daemon did not stop and owned maintenance lease cleanup failed"
                ) from exc
            raise CommandError("daemon did not stop after maintenance activation")
        self.stdout.write(
            f"maintenance active lease_id={payload['lease_id']} "
            f"expires_at={payload['expires_at']:.0f}"
        )

    # ------------------------------------------------------------------
    def _ensure(self):
        with _try_process_lock(SPAWN_LOCK_FILE) as spawn_lock:
            if spawn_lock is None:
                self.stdout.write("spawn in progress — skip")
                return
            if maintenance_status(path=MAINTENANCE_FILE)["active"]:
                self.stdout.write("maintenance active — watchdog skip")
                return
            if _process_lock_held(DAEMON_LOCK_FILE):
                # A held singleton lock only proves that a process exists. A
                # hung worker can keep the lock while its heartbeat is stale;
                # let the bounded reload path recover it instead of reporting
                # a false healthy daemon to cron.
                if _daemon_code_current() and _daemon_alive():
                    self.stdout.write("daemon alive — ok")
                    return
                # Old code sees restart.txt and exits within at most one idle
                # loop. Never spawn while it still owns the process lock.
                if not _wait_for_lock(
                    DAEMON_LOCK_FILE,
                    held=False,
                    timeout=RELOAD_LOCK_WAIT_SECONDS,
                ):
                    raise CommandError("stale daemon did not release singleton lock during reload")
            log_dir = os.path.join(PROJECT_ROOT, "tmp")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "ig_bot_daemon.log")
            try:
                with open(log_path, "a") as logf:
                    child = subprocess.Popen(
                        [sys.executable, MANAGE_PY_PATH, "run_instagram_bot", "--forever"],
                        stdout=logf,
                        stderr=logf,
                        stdin=subprocess.DEVNULL,
                        start_new_session=True,
                        cwd=PROJECT_ROOT,
                        env=os.environ.copy(),
                    )
                if not _wait_for_lock(
                    DAEMON_LOCK_FILE,
                    held=True,
                    timeout=DAEMON_START_WAIT_SECONDS,
                ):
                    # A cron/watchdog process can win the singleton race while
                    # our child exits normally. Reconcile lock + heartbeat once
                    # more before reporting failure.
                    if _process_lock_held(DAEMON_LOCK_FILE) and _daemon_alive():
                        self.stdout.write("daemon alive — ok")
                        return
                    return_code = child.poll()
                    if return_code is None:
                        raise CommandError(
                            "daemon child still running after "
                            f"{DAEMON_START_WAIT_SECONDS}s without singleton lock"
                        )
                    raise CommandError(
                        f"daemon child exited with code {return_code} "
                        "before acquiring singleton lock"
                    )
                bot.log("info", "daemon_spawn", "watchdog підняв демона")
                self.stdout.write("daemon spawned")
            except CommandError:
                raise
            except Exception as exc:
                raise CommandError(f"daemon spawn failed: {exc!r}") from exc

    # ------------------------------------------------------------------
    def _forever(self):
        if maintenance_status(path=MAINTENANCE_FILE)["active"]:
            self.stdout.write("maintenance active — daemon exit")
            return
        with _try_process_lock(DAEMON_LOCK_FILE) as daemon_lock:
            if daemon_lock is None:
                self.stdout.write("daemon already alive — exit")
                return
            return self._forever_locked()

    def _forever_locked(self):
        if maintenance_status(path=MAINTENANCE_FILE)["active"]:
            self.stdout.write("maintenance active — daemon exit")
            return
        # This process starts only after the previous daemon released the
        # singleton lock. Reconcile once with the newly deployed code before
        # any notification, analysis, payment, or reply work can run.
        _reconcile_commercial_episodes_after_reload()
        owner = f"{os.getpid()}:{time.time_ns()}"
        cache.set(HB_KEY, {"at": time.time(), "sentinel": _restart_sentinel_mtime()}, HB_ALIVE_WINDOW * 3)
        try:
            os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
            with open(PID_FILE, "w") as f:
                f.write(str(os.getpid()))
        except Exception:
            pass
        bot.log("success", "daemon_start", f"Демон онлайн (pid {os.getpid()}).")

        # Sentinel: запам'ятовуємо mtime tmp/restart.txt (його torkає кожен деплой).
        # Якщо файл змінився — демон штатно виходить, watchdog (--ensure) підніме
        # процес із НОВИМ кодом. Без цього --forever крутив би старий код у пам'яті.
        start_sentinel = _restart_sentinel_mtime()

        # Фоновий потік для важкого /conversations (поза гарячим циклом).
        stop_event = threading.Event()
        refresher = threading.Thread(target=_conv_refresher, args=(stop_event,), daemon=True)
        refresher.start()
        analysis_worker = threading.Thread(
            target=_analysis_worker,
            args=(stop_event,),
            daemon=True,
        )
        analysis_worker.start()
        recovery_worker = threading.Thread(
            target=_ai_reply_recovery_worker,
            args=(stop_event,),
            daemon=True,
        )
        recovery_worker.start()
        permission_transition_worker = threading.Thread(
            target=_permission_transition_worker,
            args=(stop_event,),
            daemon=True,
        )
        permission_transition_worker.start()
        inbox_refresh_worker = threading.Thread(
            target=_inbox_refresh_worker,
            args=(stop_event,),
            daemon=True,
        )
        inbox_refresh_worker.start()
        lifecycle_worker = threading.Thread(
            target=_checkout_lifecycle_worker,
            args=(stop_event,),
            daemon=True,
        )
        lifecycle_worker.start()
        follow_intelligence_worker = threading.Thread(
            target=_follow_intelligence_worker,
            args=(stop_event,),
            daemon=True,
        )
        follow_intelligence_worker.start()

        from django.utils import timezone as tz

        last_poll = 0.0
        last_task_health_check = 0.0
        task_expectations_registered = False
        try:
            while True:
                close_old_connections()  # лікує "MySQL server has gone away"
                if maintenance_status(path=MAINTENANCE_FILE)["active"]:
                    bot.log("info", "daemon_maintenance", "Maintenance активний — daemon зупинено")
                    break
                if _restart_sentinel_mtime() != start_sentinel:
                    bot.log("info", "daemon_reload",
                            "restart.txt змінено — демон перезавантажується для нового коду")
                    break
                enabled = False
                try:
                    if not task_expectations_registered:
                        task_expectations_registered = ensure_task_expectations()
                    s = InstagramBotSettings.load()
                    enabled, last_poll = _run_work_cycle(s, last_poll)
                    if time.monotonic() - last_task_health_check >= TASK_HEALTH_CHECK_EVERY:
                        check_task_health()
                        last_task_health_check = time.monotonic()
                    # heartbeat для UI навіть коли зупинено (агент онлайн)
                    s.heartbeat_at = tz.now()
                    s.save(update_fields=["heartbeat_at"])
                except Exception as exc:
                    bot.log("error", "daemon_loop", repr(exc))
                finally:
                    cache.set(HB_KEY, {"at": time.time(), "sentinel": start_sentinel}, HB_ALIVE_WINDOW * 3)
                    cache.set(DAEMON_LOCK_KEY, owner, HB_ALIVE_WINDOW * 3)
                # працює — кожні ~1.5 c (низька латентність черги); зупинено — рідше
                time.sleep(1.5 if enabled else 5)
        finally:
            stop_event.set()
            # Звільняємо heartbeat одразу, щоб watchdog підняв новий демон без
            # очікування TTL (інакше до 45 c простою після деплою).
            try:
                if cache.get(DAEMON_LOCK_KEY) == owner:
                    cache.delete(HB_KEY)
                    cache.delete(DAEMON_LOCK_KEY)
            except Exception:
                pass
