# Telegram Alerts and Instagram Worker Reliability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Stop repeated unresolved-alert spam, make system incidents self-healing, gate discount offers on an explicit manager decision, and make slow Instagram daemon starts idempotent without interrupting in-flight work.

**Architecture:** The existing `--ensure` watchdog records a durable starting-child marker so a slow Django import cannot produce a false failure or duplicate worker. Operational alerts are queued outside failing cron I/O, reconciled from durable task truth, and monitored once per stable set under a centralized human-review policy. Discount follow-ups use the existing authenticated Telegram callback webhook and durable task fields for approve/reject state.

**Tech Stack:** Python 3.14.6, Django 6.1, MariaDB production / SQLite tests, Telegram Bot API callbacks, POSIX `flock` and `timeout`, Django TestCase and unittest.

---

### Task 1: Idempotent slow-start watchdog handoff

**Files:**
- Modify: `twocomms/management/management/commands/run_instagram_bot.py`
- Modify: `twocomms/management/tests_ig_daemon.py`
- Modify: `scripts/install_instagram_bot_watchdog_cron.sh`
- Modify: `tests/test_install_instagram_bot_watchdog_cron.py`

**Step 1: Write the failing command tests**

Add tests proving a live child that has not acquired the daemon lock is recorded
as `starting`, the next watchdog cannot spawn another child, dead markers are
recoverable, and an over-age live marker fails closed.

**Step 2: Run the focused command tests and verify RED**

Run:

```bash
TWC_PYTHON="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.venv/bin/python"
cd twocomms
"$TWC_PYTHON" manage.py test --settings=test_settings management.tests_ig_daemon -v 1
```

Expected: new marker assertions fail because the durable startup state does not
exist.

**Step 3: Implement the durable startup marker**

Atomically persist PID/start/sentinel after spawn. Treat a still-live child as a
pending handoff, reject stale live ownership, clear dead markers, and let only
the matching child clear the marker only after reconciliation and heartbeat/PID
publication make it genuinely ready.

**Step 4: Update the managed cron contract test first**

Keep the repository-owned `--ensure` line beneath its existing outer timeout,
then run:

```bash
"$TWC_PYTHON" -m unittest tests.test_install_instagram_bot_watchdog_cron -v
```

Expected: the managed cron contract remains unchanged and green.

**Step 5: Verify the installer and daemon suite GREEN**

Retain explicit production settings, non-overlap locking, and enough timeout
margin for reload/startup. Re-run both focused suites; expected result is zero
failures.

### Task 2: Self-healing and one-shot Telegram alert lifecycle

**Files:**
- Modify: `twocomms/management/services/ig_task_health.py`
- Modify: `twocomms/management/services/instagram_bot.py`
- Modify: `twocomms/management/services/ig_alerts.py`
- Modify: `twocomms/management/tests_ig_task_health.py`
- Modify: `twocomms/management/tests_ig_notifications.py`

**Step 1: Write RED tests for deferred failure delivery**

Prove a task failure queues one `ig_task_failure` row without calling Telegram,
and that its payload contains `task_key`, heartbeat id, a bounded reason code,
and `requires_human_review=False`.

**Step 2: Write RED tests for automatic recovery**

Create new-style and legacy `UNKNOWN` task-failure notifications, persist a
later successful heartbeat, drain notifications, and assert both rows become
`RESOLVED` with one `IgBotNotificationAudit(action="auto_recovered")` each.

**Step 3: Write RED tests for stable human-review monitoring**

Create an actionable terminal row and a system-only terminal row. Force the
monitor twice at different times and assert only the actionable row is listed
and only one monitor notification exists while the unresolved set is
unchanged. Add a second actionable row and assert a new fingerprint creates one
new summary.

**Step 4: Implement minimal lifecycle policy**

Queue task-failure alerts with `deliver_immediately=False`; reconcile recovered
task notifications before draining; require explicit human-review metadata;
replace the hourly bucket key with a stable fingerprint; and add typed event
labels for task failures and discount approval.

**Step 5: Run focused tests and verify GREEN**

```bash
"$TWC_PYTHON" manage.py test --settings=test_settings \
  management.tests_ig_notifications management.tests_ig_task_health -v 1
```

Expected: all tests pass and no unexpected network request is made.

### Task 3: Manager approval gate for 5% and 10% discount follow-ups

**Files:**
- Modify: `twocomms/management/ig_bot_models.py`
- Create: `twocomms/management/migrations/0169_ig_followup_manager_approval.py`
- Modify: `twocomms/management/services/bot_followups.py`
- Modify: `twocomms/management/views.py`
- Modify: `twocomms/management/services/ig_alerts.py`
- Modify: `twocomms/management/tests_ig_followups.py`
- Modify: `twocomms/management/tests_ig_notifications.py`

**Step 1: Write RED model and send-boundary tests**

Assert discount tasks start in `pending` manager approval, ordinary follow-ups
remain `not_required`, and an unapproved due discount produces one Telegram
approval request without calling Meta.

**Step 2: Add approval persistence**

Add `manager_approval_status`, requested/decided timestamps, and an optional
actor FK. Generate and inspect migration `0169`; run migration checks.

**Step 3: Write RED callback tests**

Post Telegram callback payloads for approve/reject as an authorized and an
unauthorized actor. Assert authorization, idempotency, stale-task rejection,
notification resolution, immutable audit creation, approved-task eligibility,
and rejected-task cancellation.

**Step 4: Implement the callback and request creation**

Create one `discount_approval:<task_id>` notification with Approve/Reject
callback buttons when a discount becomes due. Handle `igdisc:approve:<id>` and
`igdisc:reject:<id>` in the existing management Telegram webhook under the
same admin chat/user checks as payment reviews.

**Step 5: Verify focused follow-up and webhook suites**

```bash
"$TWC_PYTHON" manage.py test --settings=test_settings \
  management.tests_ig_followups management.tests_ig_notifications \
  management.tests_ig_payment_review -v 1
```

Expected: all tests pass; no unapproved discount send reaches Meta.

### Task 4: Integrated verification and shipment

**Files:**
- Modify if required by findings: `docs/plans/2026-08-23-telegram-alerts-watchdog-design.md`
- Modify if required by findings: `docs/plans/2026-08-23-telegram-alerts-watchdog.md`

**Step 1: Run code-quality and migration gates**

```bash
git diff --check
cd twocomms
"$TWC_PYTHON" manage.py check --settings=test_settings
"$TWC_PYTHON" manage.py makemigrations --check --dry-run --settings=test_settings
"$TWC_PYTHON" -m compileall -q management twocomms
```

Expected: exit 0 and no pending migration.

**Step 2: Run the focused shared regression gate**

```bash
"$TWC_PYTHON" manage.py test --settings=test_settings \
  management.tests_ig_daemon management.tests_ig_notifications \
  management.tests_ig_task_health management.tests_ig_followup_core \
  management.tests_ig_followup_policies management.tests_ig_discount_approval \
  management.tests_ig_payment_review -v 1
```

Expected: zero failures.

**Step 3: Review and commit the scoped diff**

Inspect `git status`, `git diff --stat`, and the complete diff. Commit only the
files in this plan.

**Step 4: Integrate and push to `main`**

Fetch `origin/main`, rebase or fast-forward the scoped branch if necessary,
then push the verified commits to `origin/main` without including changes from
the dirty primary checkout.

**Step 5: Deploy through the supported SSH path**

On production: pull `main`, apply the new migration, run Django `check`, install
and verify the repository-owned watchdog cron block, touch `tmp/restart.txt`,
and launch/observe the durable starting-marker handoff.

**Step 6: Repair and verify production state**

Run the notification reconciler/drain so recovered alert `#145` becomes
`RESOLVED`. Verify deployed SHA, migration state, no unresolved system alert,
one-shot monitor behavior, task heartbeat freshness, exactly one live
`run_instagram_bot --forever` process, watchdog ownership, and fresh logs.
Use only a small sequential HTTP smoke set; do not crawl the storefront.
