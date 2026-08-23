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
2. Keep the detached daemon, but make its slow-start handoff durable and
   idempotent. This preserves the current low-latency worker and long-lived
   cadences while preventing duplicate children and false startup failures.
3. Run the full worker for a bounded interval owned by cron. Review rejected
   this option because provider calls and seven background loops cannot all be
   drained safely inside a short shared-hosting timeout, and process-local
   cadences would restart every minute.

Approach 2 is selected together with the explicit alert-lifecycle changes.

## Worker architecture

The existing `--ensure` watchdog retains OS `flock`, the daemon singleton, and
the 75-second outer timeout. When it launches a child it atomically writes a
starting marker containing PID, start time, and deploy sentinel. If Django
startup takes more than the 15-second handshake but the child is still alive,
the watchdog reports `daemon starting — pending` instead of a false
`CommandError`; the next minute sees the marker and cannot spawn a duplicate.

The child clears only its own marker after acquiring the singleton, completing
commercial reconciliation, and publishing heartbeat/PID. Lock ownership alone
is therefore `initialization pending`, not healthy. Dead markers are removed
automatically; a live marker older than the bounded startup window fails closed
and does not permit a second child. This preserves long-lived
conversation/analysis cadences and avoids terminating in-flight Telegram,
Meta, or MariaDB operations.

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

Terminal monitoring uses a central typed policy for human-only event types and
also honors explicit `requires_human_review`. This keeps legacy actionable rows
visible. Its dedupe key is a stable fingerprint of the current unresolved set,
not an hourly time bucket. An unchanged incident therefore produces one
Telegram message, while a genuinely new or changed review set produces a new
one.

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

- A child that is alive but still importing Django after the initial handshake
  remains a single durable startup attempt rather than a false failure or a
  duplicate process.
- Telegram ambiguous delivery remains non-retryable, but only actionable
  business decisions enter the human-review monitor.
- A recovered system incident is auto-resolved; it never becomes manager debt.
- Approval callbacks are idempotent and reject stale, cancelled, unauthorized,
  or conflicting actions.
- Existing receipt-first and Meta delivery ambiguity protections remain
  unchanged.

## Test strategy

Regression tests cover durable startup-marker ownership, the managed cron
contract, deferred task-failure delivery, typed reason metadata, automatic
recovery of legacy and new system alerts, stable one-shot terminal monitoring,
discount approval/rejection authorization and idempotency, and the guarantee
that unapproved discounts never cross the Meta send boundary.
