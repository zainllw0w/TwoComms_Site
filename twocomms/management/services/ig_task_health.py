"""Durable supervision for the Instagram bot's production cron boundary.

Cron itself cannot tell us that another entry disappeared.  Each scheduled
command therefore records its last successful run here, while the long-lived
bot daemon checks freshness and emits one bounded incident alert per hour.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from time import monotonic

from django.db import DatabaseError, OperationalError, ProgrammingError
from django.db.models import F
from django.utils import timezone

from management.models import InstagramBotTaskHeartbeat


@dataclass(frozen=True)
class TaskSpec:
    key: str
    label: str
    expected_interval_seconds: int
    stale_after_seconds: int


# These are the actual crontab-owned commands on production.  A stale threshold
# tolerates one missed scheduling window without hiding a removed cron line.
TASK_SPECS = (
    TaskSpec("ig_daemon_watchdog", "watchdog Instagram-демона", 60, 180),
    TaskSpec("ig_checkout_reconcile", "звірка IG checkout", 120, 480),
    TaskSpec("ig_order_fulfillment", "доставка IG-подій замовлення", 120, 480),
    TaskSpec("ig_deal_payments", "backstop перевірки IG-оплат", 240, 720),
    TaskSpec("order_telegram_reconcile", "відновлення Telegram-карток замовлень", 120, 480),
)
_SPECS_BY_KEY = {spec.key: spec for spec in TASK_SPECS}


def _spec(task_key: str) -> TaskSpec:
    try:
        return _SPECS_BY_KEY[task_key]
    except KeyError as exc:
        raise ValueError(f"Unknown Instagram operational task: {task_key!r}") from exc


def _upsert_expectation(spec: TaskSpec) -> InstagramBotTaskHeartbeat:
    row, created = InstagramBotTaskHeartbeat.objects.get_or_create(
        task_key=spec.key,
        defaults={
            "label": spec.label,
            "expected_interval_seconds": spec.expected_interval_seconds,
            "stale_after_seconds": spec.stale_after_seconds,
        },
    )
    if not created and (
        row.label != spec.label
        or row.expected_interval_seconds != spec.expected_interval_seconds
        or row.stale_after_seconds != spec.stale_after_seconds
    ):
        row.label = spec.label
        row.expected_interval_seconds = spec.expected_interval_seconds
        row.stale_after_seconds = spec.stale_after_seconds
        row.save(update_fields=["label", "expected_interval_seconds", "stale_after_seconds", "updated_at"])
    return row


def ensure_task_expectations() -> bool:
    """Register every expected task without making a pre-migration deploy fail."""
    try:
        for spec in TASK_SPECS:
            _upsert_expectation(spec)
    except (DatabaseError, OperationalError, ProgrammingError):
        return False
    return True


def mark_task_started(task_key: str, *, at=None) -> InstagramBotTaskHeartbeat | None:
    try:
        row = _upsert_expectation(_spec(task_key))
        now = at or timezone.now()
        row.last_started_at = now
        row.save(update_fields=["last_started_at", "updated_at"])
        return row
    except (DatabaseError, OperationalError, ProgrammingError):
        return None


def mark_task_succeeded(task_key: str, *, duration_ms: int = 0, at=None) -> InstagramBotTaskHeartbeat | None:
    try:
        row = _upsert_expectation(_spec(task_key))
        now = at or timezone.now()
        row.last_started_at = row.last_started_at or now
        row.last_succeeded_at = now
        row.last_duration_ms = max(0, int(duration_ms or 0))
        row.consecutive_failures = 0
        row.last_error_kind = ""
        row.save(update_fields=[
            "last_started_at", "last_succeeded_at", "last_duration_ms",
            "consecutive_failures", "last_error_kind", "updated_at",
        ])
        return row
    except (DatabaseError, OperationalError, ProgrammingError):
        return None


def _notify_failure(row: InstagramBotTaskHeartbeat, error_kind: str) -> None:
    try:
        from management.services.ig_alerts import alert_dedupe_key, format_alert
        from management.services import instagram_bot as bot

        text = format_alert(
            "⚠️ Помилка IG cron-задачі",
            lines=(
                f"Задача: {row.label}",
                f"Тип помилки: {error_kind}",
                f"Очікуваний інтервал: {row.expected_interval_seconds} с",
            ),
        )
        bot.notify_manager(
            text,
            dedupe_key=alert_dedupe_key(
                "ig_task_failure", entity_id=row.pk, window_minutes=60
            ),
            event_type="ig_task_failure",
        )
    except Exception:
        # A notification problem must not hide the original command failure.
        pass


def mark_task_failed(
    task_key: str,
    exc: Exception,
    *,
    duration_ms: int = 0,
    at=None,
) -> InstagramBotTaskHeartbeat | None:
    """Persist a failure without storing potentially sensitive exception text."""
    try:
        row = _upsert_expectation(_spec(task_key))
        now = at or timezone.now()
        error_kind = exc.__class__.__name__[:128]
        row.last_started_at = row.last_started_at or now
        row.last_failed_at = now
        row.last_duration_ms = max(0, int(duration_ms or 0))
        row.last_error_kind = error_kind
        row.save(update_fields=[
            "last_started_at", "last_failed_at", "last_duration_ms",
            "last_error_kind", "updated_at",
        ])
        InstagramBotTaskHeartbeat.objects.filter(pk=row.pk).update(
            consecutive_failures=F("consecutive_failures") + 1,
            updated_at=now,
        )
        row.refresh_from_db(fields=["consecutive_failures"])
    except (DatabaseError, OperationalError, ProgrammingError):
        return None
    _notify_failure(row, error_kind)
    return row


@contextmanager
def task_heartbeat(task_key: str):
    """Record success/failure around the real cron work, never a dry-run."""
    mark_task_started(task_key)
    started = monotonic()
    try:
        yield
    except Exception as exc:
        mark_task_failed(task_key, exc, duration_ms=round((monotonic() - started) * 1000))
        raise
    else:
        mark_task_succeeded(task_key, duration_ms=round((monotonic() - started) * 1000))


def task_health_snapshot(*, now=None) -> dict:
    """Return a non-sensitive health summary suitable for UI and public probe."""
    now = now or timezone.now()
    try:
        rows = {
            row.task_key: row
            for row in InstagramBotTaskHeartbeat.objects.filter(
                task_key__in=_SPECS_BY_KEY
            )
        }
    except (DatabaseError, OperationalError, ProgrammingError):
        return {"available": False, "healthy": False, "tasks": [], "unhealthy_count": 0}

    tasks = []
    for spec in TASK_SPECS:
        row = rows.get(spec.key)
        if row is None:
            state = "unobserved"
            age_seconds = None
            error_kind = ""
            observed_at = None
        else:
            observed_at = row.last_succeeded_at
            failure_is_newer = bool(
                row.last_failed_at
                and (not row.last_succeeded_at or row.last_failed_at >= row.last_succeeded_at)
            )
            reference = row.last_succeeded_at or row.first_expected_at
            age_seconds = max(0, int((now - reference).total_seconds())) if reference else None
            error_kind = row.last_error_kind
            if failure_is_newer:
                state = "failed"
            elif not row.last_succeeded_at and age_seconds is not None and age_seconds > spec.stale_after_seconds:
                state = "not_observed"
            elif age_seconds is not None and age_seconds > spec.stale_after_seconds:
                state = "stale"
            else:
                state = "healthy"
        tasks.append({
            "key": spec.key,
            "label": spec.label,
            "state": state,
            "healthy": state == "healthy",
            "age_seconds": age_seconds,
            "stale_after_seconds": spec.stale_after_seconds,
            "last_succeeded_at": observed_at.isoformat() if observed_at else "",
            "last_error_kind": error_kind,
        })
    unhealthy = [task for task in tasks if not task["healthy"]]
    return {
        "available": True,
        "healthy": not unhealthy,
        "tasks": tasks,
        "unhealthy_count": len(unhealthy),
    }


def check_task_health(*, now=None) -> dict:
    """Alert once per hour when one or more expected operational tasks are bad."""
    snapshot = task_health_snapshot(now=now)
    if not snapshot["available"]:
        return snapshot
    unhealthy = [task for task in snapshot["tasks"] if not task["healthy"]]
    if not unhealthy:
        return snapshot
    try:
        from management.services.ig_alerts import alert_dedupe_key, format_alert
        from management.services import instagram_bot as bot

        lines = [
            f"{task['label']}: {task['state']}"
            + (f" ({task['age_seconds']} с)" if task["age_seconds"] is not None else "")
            for task in unhealthy
        ]
        text = format_alert("🚨 IG operations потребують уваги", lines=lines)
        incident_fingerprint = ";".join(
            f"{task['key']}:{task['state']}" for task in unhealthy
        )
        bot.notify_manager(
            text,
            dedupe_key=alert_dedupe_key(
                "ig_task_health", window_minutes=60, text=incident_fingerprint
            ),
            event_type="ig_task_health",
        )
    except Exception:
        pass
    return snapshot
