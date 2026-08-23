# Telegram Alerts and Instagram Worker Reliability Design

## Problem statement

Production alert `IgBotNotification#145` is the only unresolved Telegram
notification. It was created at 2026-08-23 01:08:57 Europe/Kyiv after the
Instagram watchdog raised `CommandError`. Its synchronous Telegram send was
interrupted before a provider receipt was persisted, so stale-send recovery
moved it to `UNKNOWN`. The terminal monitor then created and delivered a new
summary every hour while the same row remained unresolved.

Production evidence also shows that the long-lived Instagram process is not
stable on the current CloudLinux/LVE host: it was started 257 times in 48
hours, without an application traceback or graceful reload for almost all
exits. The process uses about 150 MB RSS and eight threads. At cron boundaries
it overlaps with the watchdog Django process, the durable-task runner, and
other periodic jobs. The same incident windows contain LSAPI saturation,
signal-9 worker termination, and storefront 503 responses.

## Considered approaches

1. Suppress the hourly terminal monitor only. This stops the visible spam but
   leaves false watchdog failures, unresolved system rows, and unstable orphan
   workers.
2. Keep the detached daemon and add a longer startup wait/marker. This reduces
   duplicate startup attempts, but a long-lived orphan process remains a poor
   fit for the observed LVE lifecycle and still competes with cron workers.
3. Run the worker for a bounded interval owned by cron, and make alert
   lifecycle decisions explicit. This removes the orphan process, preserves
   low-latency polling for most of every minute, releases resources
   deterministically, and lets `flock`/`timeout` own the complete process.

Approach 3 is selected.

## Worker architecture

Add a production mode that runs the existing daemon work loop inline for a
bounded number of seconds. The managed crontab invokes it once per minute under
the existing OS lock and a timeout longer than the worker budget. The process
acquires the daemon singleton, publishes heartbeat/PID, runs the same durable
work and background services, then exits normally before the cron timeout.

`--forever` remains available for environments with a real service manager.
The production installer switches only the managed watchdog block to the
bounded mode. A bounded exit is recorded separately from a deploy reload or an
error. No detached child survives the cron owner, so its result is observable
and cleanup runs deterministically.

## Notification lifecycle

Operational task failures are persisted without performing Telegram network
I/O inside the failing cron exception path. The next notification drain sends
them. The payload includes typed task identity and a bounded reason code so an
operator sees which watchdog condition occurred without leaking arbitrary
exception text.

Before terminal monitoring, the notification reconciler closes system-only
alerts when durable task state proves a later successful run. It creates an
immutable audit row with an automatic actor. This also repairs legacy alert
`#145`, whose task identity can be derived from its typed dedupe key.

Terminal monitoring considers only notifications explicitly marked
`requires_human_review`. Its dedupe key is a stable fingerprint of the current
unresolved set, not an hourly time bucket. An unchanged incident therefore
produces one Telegram message, while a genuinely new or changed review set
produces a new one.

## Manager decisions

Discount follow-ups become human-in-the-loop. A 5% or 10% task remains pending
until a manager approves it. When it becomes due, one durable Telegram alert is
created with Approve and Reject inline buttons. Telegram delivers the callback
to the existing Django management webhook; no continuously waiting bot loop is
required.

The callback authenticates the configured admin chat/user, locks the task and
notification, and is idempotent. Approval makes the follow-up sendable;
rejection cancels it. A client reply, payment, pause, or other existing policy
gate can still cancel the task before approval. The notification and audit
trail record the final decision.

## Resource and verification policy

Production verification must be bounded and sequential. It must not repeat the
2026-08-23 `TwoComms-Deploy-Verification/1.0` crawl, which made 1,279 requests
and caused 49 of the day's 95 HTTP 503 responses. Verification will use a small
endpoint set, low concurrency, deployed-SHA checks, MariaDB state, heartbeat,
process ownership, and fresh logs.

## Failure handling

- A bounded worker that exceeds its budget is terminated by the outer timeout
  and recorded as a task failure; alert delivery happens later.
- Telegram ambiguous delivery remains non-retryable, but only actionable
  business decisions enter the human-review monitor.
- A recovered system incident is auto-resolved; it never becomes manager debt.
- Approval callbacks are idempotent and reject stale, cancelled, unauthorized,
  or conflicting actions.
- Existing receipt-first and Meta delivery ambiguity protections remain
  unchanged.

## Test strategy

Regression tests cover bounded worker exit and cleanup, the managed cron
contract, deferred task-failure delivery, typed reason metadata, automatic
recovery of legacy and new system alerts, stable one-shot terminal monitoring,
discount approval/rejection authorization and idempotency, and the guarantee
that unapproved discounts never cross the Meta send boundary.
