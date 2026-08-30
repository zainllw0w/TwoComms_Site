"""Single-owner contract for Instagram runtime work.

This module is deliberately free of provider code.  It is the small, importable
source of truth used by the daemon, the periodic coordinator and contract
tests.  A lane may have exactly one runtime owner; business-level idempotency
remains mandatory inside every lane.
"""

from __future__ import annotations

from dataclasses import dataclass


DAEMON_OWNER = "instagram_daemon"
PERIODIC_OWNER = "instagram_periodic_coordinator"
SUPERVISOR_OWNER = "instagram_stdlib_supervisor"
MANUAL_OWNER = "manual_diagnostic"
DURABLE_TASK_OWNER = "django61_durable_tasks_cron"
NOVA_POSHTA_OWNER = "nova_poshta_tracking_cron"
GLOBAL_BACKGROUND_LOCK = "tmp/twocomms_heavy_background.lock"


@dataclass(frozen=True)
class RuntimeLaneOwner:
    lane: str
    owner: str
    detail: str


@dataclass(frozen=True)
class PeriodicLane:
    task_key: str
    command: str
    interval_seconds: int
    options: tuple[tuple[str, object], ...]
    optional_gate: str = ""

    def command_options(self) -> dict[str, object]:
        return dict(self.options)


RUNTIME_LANE_OWNERS = (
    RuntimeLaneOwner("daemon_supervision", SUPERVISOR_OWNER, "spawn, wait, exit attribution"),
    RuntimeLaneOwner("live_reply", DAEMON_OWNER, "inbound queue and customer reply"),
    RuntimeLaneOwner("manager_notification_outbox", DAEMON_OWNER, "durable manager notification drain"),
    RuntimeLaneOwner("customer_followups", DAEMON_OWNER, "latency-sensitive due follow-ups"),
    RuntimeLaneOwner("profile_refresh", DAEMON_OWNER, "bounded provider profile refresh"),
    RuntimeLaneOwner("conversation_discovery", DAEMON_OWNER, "resumable inbox discovery"),
    RuntimeLaneOwner("conversation_analysis", DAEMON_OWNER, "durable CRM analysis queue"),
    RuntimeLaneOwner("ai_reply_recovery", DAEMON_OWNER, "failed live-reply recovery"),
    RuntimeLaneOwner("permission_transitions", DAEMON_OWNER, "reply permission changes"),
    RuntimeLaneOwner("inbox_refresh", DAEMON_OWNER, "administrator-requested inbox repair"),
    RuntimeLaneOwner("checkout_lifecycle", DAEMON_OWNER, "payment and delivery lifecycle events"),
    RuntimeLaneOwner("follow_intelligence", DAEMON_OWNER, "follow and UGC intelligence queue"),
    RuntimeLaneOwner("order_telegram_reconcile", PERIODIC_OWNER, "post-payment side-effect repair"),
    RuntimeLaneOwner("ig_checkout_reconcile", PERIODIC_OWNER, "assisted-checkout repair"),
    RuntimeLaneOwner("ig_order_fulfillment", PERIODIC_OWNER, "order customer-event delivery"),
    RuntimeLaneOwner("ig_deal_payments", PERIODIC_OWNER, "payment polling backstop"),
    RuntimeLaneOwner("binotel_call_ai_analyses", PERIODIC_OWNER, "runtime-gated call analysis"),
    RuntimeLaneOwner("django61_durable_tasks", DURABLE_TASK_OWNER, "shared global admission lock"),
    RuntimeLaneOwner("nova_poshta_tracking", NOVA_POSHTA_OWNER, "shared global admission lock"),
    RuntimeLaneOwner("gemini_metadata_diagnostic", MANUAL_OWNER, "explicit token-free diagnostic only"),
)


PERIODIC_LANES = (
    PeriodicLane(
        "order_telegram_reconcile",
        "reconcile_order_telegram_notifications",
        120,
        (("max_age_hours", 168), ("min_age_seconds", 60), ("limit", 50)),
    ),
    PeriodicLane(
        "ig_checkout_reconcile",
        "reconcile_ig_checkout",
        120,
        (("limit", 100),),
    ),
    PeriodicLane(
        "ig_order_fulfillment",
        "reconcile_ig_order_fulfillment",
        120,
        (("limit", 100),),
    ),
    PeriodicLane(
        "ig_deal_payments",
        "poll_ig_deal_payments",
        240,
        (("limit", 50),),
    ),
    PeriodicLane(
        "binotel_call_ai_analyses",
        "run_call_ai_analyses",
        300,
        (("limit", 1),),
        optional_gate="call_auto_analysis",
    ),
)


def validate_runtime_lane_owners() -> None:
    lanes = [entry.lane for entry in RUNTIME_LANE_OWNERS]
    if len(lanes) != len(set(lanes)):
        raise RuntimeError("Instagram runtime lane has more than one owner")
    periodic_owner_keys = {
        entry.lane
        for entry in RUNTIME_LANE_OWNERS
        if entry.owner == PERIODIC_OWNER
    }
    periodic_lane_keys = {entry.task_key for entry in PERIODIC_LANES}
    if periodic_owner_keys != periodic_lane_keys:
        raise RuntimeError("Periodic lane definitions and owner manifest disagree")


def lane_owner(lane: str) -> str:
    for entry in RUNTIME_LANE_OWNERS:
        if entry.lane == lane:
            return entry.owner
    raise KeyError(lane)


validate_runtime_lane_owners()
