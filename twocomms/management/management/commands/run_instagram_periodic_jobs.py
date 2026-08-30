"""Run all cron-owned Instagram lanes in one bounded Django process."""

from __future__ import annotations

import time

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from management.models import InstagramBotTaskHeartbeat
from management.services.ig_runtime_ownership import PERIODIC_LANES


DEFAULT_BUDGET_SECONDS = 540
MAX_BUDGET_SECONDS = 570


def _call_auto_analysis_enabled() -> bool:
    try:
        from management.services.call_auto_analysis import is_call_auto_analysis_enabled

        return bool(is_call_auto_analysis_enabled())
    except Exception:
        # This optional lane fails closed without starving payment/fulfillment.
        return False


def _lane_enabled(lane) -> bool:
    if lane.optional_gate == "call_auto_analysis":
        return _call_auto_analysis_enabled()
    return True


def due_periodic_lanes(*, now=None, selected_lane: str = "", force: bool = False):
    """Return due lanes from one heartbeat query.

    The child command writes ``last_started_at`` at its real work boundary.
    Using that durable timestamp preserves each lane's former cadence while a
    single every-minute coordinator replaces five independent cron processes.
    """
    now = now or timezone.now()
    lanes = tuple(
        lane
        for lane in PERIODIC_LANES
        if (not selected_lane or lane.task_key == selected_lane) and _lane_enabled(lane)
    )
    if force:
        return lanes
    rows = {
        row.task_key: row.last_started_at
        for row in InstagramBotTaskHeartbeat.objects.filter(
            task_key__in=[lane.task_key for lane in lanes]
        ).only("task_key", "last_started_at")
    }
    return tuple(
        lane
        for lane in lanes
        if rows.get(lane.task_key) is None
        or (now - rows[lane.task_key]).total_seconds() >= lane.interval_seconds
    )


class Command(BaseCommand):
    help = "Run due Instagram periodic lanes sequentially under one cron owner."

    def add_arguments(self, parser):
        parser.add_argument(
            "--lane",
            choices=[lane.task_key for lane in PERIODIC_LANES],
            default="",
            help="Run or inspect one declared lane.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Ignore cadence for an explicitly requested operational run.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print due lane keys without running their commands.",
        )
        parser.add_argument(
            "--budget-seconds",
            type=int,
            default=DEFAULT_BUDGET_SECONDS,
            help="Do not start another lane after this coordinator budget.",
        )

    def handle(self, *args, **options):
        selected_lane = str(options.get("lane") or "")
        force = bool(options.get("force"))
        if force and not selected_lane:
            raise CommandError("--force requires --lane")
        budget = int(options.get("budget_seconds") or DEFAULT_BUDGET_SECONDS)
        if not 1 <= budget <= MAX_BUDGET_SECONDS:
            raise CommandError(
                f"--budget-seconds must be between 1 and {MAX_BUDGET_SECONDS}"
            )
        due = due_periodic_lanes(selected_lane=selected_lane, force=force)
        if options.get("dry_run"):
            self.stdout.write("due=" + ",".join(lane.task_key for lane in due))
            return

        started = time.monotonic()
        completed = []
        deferred = []
        failures = []
        for lane in due:
            if time.monotonic() - started >= budget:
                deferred.append(lane.task_key)
                continue
            try:
                call_command(lane.command, **lane.command_options())
            except Exception as exc:
                # The child command owns its typed heartbeat/failure record.
                # Continue so one broken lane cannot starve payment or delivery.
                failures.append((lane.task_key, exc.__class__.__name__))
            else:
                completed.append(lane.task_key)

        summary = (
            f"completed={','.join(completed) or '-'} "
            f"deferred={','.join(deferred) or '-'} "
            f"failed={','.join(key for key, _kind in failures) or '-'}"
        )
        self.stdout.write(summary)
        if failures:
            safe_failure_kinds = ",".join(
                f"{key}:{kind}" for key, kind in failures
            )
            raise CommandError(f"periodic lane failures: {safe_failure_kinds}")
