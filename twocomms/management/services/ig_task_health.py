"""Durable supervision for the Instagram bot's production cron boundary.

Cron itself cannot tell us that another entry disappeared.  Each scheduled
command therefore records its last successful run here, while the long-lived
bot daemon checks freshness and emits one bounded incident alert per hour.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
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
    TaskSpec("nova_poshta_tracking", "оновлення статусів Нової Пошти", 300, 900),
    TaskSpec("binotel_call_ai_analyses", "Автоаналіз дзвінків", 300, 900),
    TaskSpec("ig_gemini_metadata_health", "перевірка Gemini API metadata", 3600, 7500),
)
_SPECS_BY_KEY = {spec.key: spec for spec in TASK_SPECS}
_CALL_AUTO_ANALYSIS_TASK_KEY = "binotel_call_ai_analyses"
_CALL_QUEUE_KEYS = ("eligible", "metadata_pending", "ineligible")


def _call_auto_analysis_enabled() -> bool:
    """Read the optional task state without weakening other monitors."""
    try:
        from management.services.call_auto_analysis import (
            is_call_auto_analysis_enabled,
        )

        return bool(is_call_auto_analysis_enabled())
    except (DatabaseError, OperationalError, ProgrammingError):
        return False


def _active_task_specs() -> tuple[TaskSpec, ...]:
    if _call_auto_analysis_enabled():
        return TASK_SPECS
    return tuple(
        spec
        for spec in TASK_SPECS
        if spec.key != _CALL_AUTO_ANALYSIS_TASK_KEY
    )


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
    """Register active tasks without deleting historical heartbeat rows."""
    try:
        for spec in _active_task_specs():
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


def _task_failure_reason_code(exc: Exception) -> str:
    if exc.__class__.__name__ == "CommandError":
        message = str(exc or "").lower()
        if "still running" in message and "singleton lock" in message:
            return "daemon_start_pending"
        if "did not release singleton lock" in message:
            return "daemon_lock_stale"
        if "child exited with code" in message:
            return "daemon_child_exited"
        if "spawn failed" in message:
            return "daemon_spawn_failed"
        return "command_error"
    name = exc.__class__.__name__
    snake = []
    for index, char in enumerate(name):
        if char.isupper() and index:
            snake.append("_")
        snake.append(char.lower())
    return "".join(snake)[:64] or "task_error"


def _notify_failure(
    row: InstagramBotTaskHeartbeat,
    error_kind: str,
    exc: Exception,
) -> None:
    try:
        from management.services.ig_alerts import alert_dedupe_key, format_alert
        from management.services import instagram_bot as bot

        reason_code = _task_failure_reason_code(exc)
        text = format_alert(
            "⚠️ Помилка IG cron-задачі",
            lines=(
                f"Задача: {row.label}",
                f"Тип помилки: {error_kind}",
                f"Причина: {reason_code}",
                f"Очікуваний інтервал: {row.expected_interval_seconds} с",
            ),
        )
        bot.notify_manager(
            text,
            dedupe_key=alert_dedupe_key(
                "ig_task_failure", entity_id=row.pk, window_minutes=60
            ),
            event_type="ig_task_failure",
            metadata={
                "task_key": row.task_key,
                "task_heartbeat_id": row.pk,
                "task_failure_reason": reason_code,
                "requires_human_review": False,
            },
            deliver_immediately=False,
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
    _notify_failure(row, error_kind, exc)
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
    active_specs = _active_task_specs()
    active_keys = {spec.key for spec in active_specs}
    try:
        rows = {
            row.task_key: row
            for row in InstagramBotTaskHeartbeat.objects.filter(
                task_key__in=active_keys
            )
        }
    except (DatabaseError, OperationalError, ProgrammingError):
        return {"available": False, "healthy": False, "tasks": [], "unhealthy_count": 0}

    tasks = []
    for spec in active_specs:
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


def release_queue_snapshot() -> dict:
    """Return sanitized release-boundary queue counts, without customer data."""
    from management.models import IgBotNotification, InstagramBotMessage
    from management.ig_bot_models import IgAiReplyRecoveryJob, IgConversationAnalysisJob

    try:
        call_auto_analysis_enabled = _call_auto_analysis_enabled()
        inbound_pending = InstagramBotMessage.objects.filter(
            role=InstagramBotMessage.Role.USER,
            status__in=(InstagramBotMessage.Status.PENDING, InstagramBotMessage.Status.PROCESSING),
        ).count()
        reply_pending = InstagramBotMessage.objects.filter(
            role=InstagramBotMessage.Role.MODEL,
            status__in=(InstagramBotMessage.Status.PENDING, InstagramBotMessage.Status.PROCESSING),
        ).count()
        notification_unresolved = IgBotNotification.objects.filter(
            status__in=(
                IgBotNotification.Status.PENDING,
                IgBotNotification.Status.SENDING,
                IgBotNotification.Status.UNKNOWN,
                IgBotNotification.Status.FAILED,
                IgBotNotification.Status.DEAD_LETTER,
            )
        ).count()
        analysis_pending = IgConversationAnalysisJob.objects.filter(
            status__in=(
                IgConversationAnalysisJob.Status.PENDING,
                IgConversationAnalysisJob.Status.PROCESSING,
            )
        ).count()
        recovery_unresolved = IgAiReplyRecoveryJob.objects.filter(
            status__in=(
                IgAiReplyRecoveryJob.Status.PENDING,
                IgAiReplyRecoveryJob.Status.PROCESSING,
                IgAiReplyRecoveryJob.Status.SENDING,
                IgAiReplyRecoveryJob.Status.AMBIGUOUS,
                IgAiReplyRecoveryJob.Status.FAILED,
            )
        ).count()
        analysis_failed = IgConversationAnalysisJob.objects.filter(
            status=IgConversationAnalysisJob.Status.FAILED
        ).count()
        binotel_counts = dict.fromkeys(_CALL_QUEUE_KEYS, 0)
        binotel_stale_running = 0
        binotel_error = 0
        if call_auto_analysis_enabled:
            from django.db.models import Q

            from management.models import CallRecord
            from management.services.call_ai_queue import (
                ELIGIBLE,
                INELIGIBLE,
                METADATA_PENDING,
                STALE_ANALYSIS_LOCK_MINUTES,
                analysis_queue_category,
            )

            binotel_pending = CallRecord.objects.filter(
                provider="binotel", ai_status=CallRecord.AiStatus.PENDING,
            ).values_list("duration_seconds", "payload")
            for duration_seconds, payload in binotel_pending:
                category = analysis_queue_category(payload, duration_seconds)
                binotel_counts[category] += 1
            stale_before = timezone.now() - timedelta(minutes=STALE_ANALYSIS_LOCK_MINUTES)
            binotel_stale_running = CallRecord.objects.filter(
                Q(ai_locked_at__lte=stale_before) | Q(ai_locked_at__isnull=True),
                provider="binotel", ai_status=CallRecord.AiStatus.RUNNING,
            ).count()
            binotel_error = CallRecord.objects.filter(
                provider="binotel", ai_status=CallRecord.AiStatus.ERROR,
            ).count()
    except (DatabaseError, OperationalError, ProgrammingError) as exc:
        return {
            "available": False,
            "dangerous_backlog": 0,
            "inbound_pending": 0,
            "reply_pending": 0,
            "notification_unresolved": 0,
            "analysis_pending": 0,
            "recovery_unresolved": 0,
            "analysis_failed": 0,
            "binotel_eligible_pending": 0,
            "binotel_metadata_pending": 0,
            "binotel_ineligible_pending": 0,
            "binotel_stale_running": 0,
            "binotel_error": 0,
            "error": type(exc).__name__,
        }

    dangerous_backlog = (
        inbound_pending
        + reply_pending
        + notification_unresolved
        + analysis_pending
        + recovery_unresolved
        + binotel_counts["eligible"]
        + binotel_counts["metadata_pending"]
        + binotel_counts["ineligible"]
        + binotel_stale_running
    )
    return {
        "available": True,
        "dangerous_backlog": dangerous_backlog,
        "inbound_pending": inbound_pending,
        "reply_pending": reply_pending,
        "notification_unresolved": notification_unresolved,
        "analysis_pending": analysis_pending,
        "recovery_unresolved": recovery_unresolved,
        "analysis_failed": analysis_failed,
        "binotel_eligible_pending": binotel_counts["eligible"],
        "binotel_metadata_pending": binotel_counts["metadata_pending"],
        "binotel_ineligible_pending": binotel_counts["ineligible"],
        "binotel_stale_running": binotel_stale_running,
        "binotel_error": binotel_error,
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
