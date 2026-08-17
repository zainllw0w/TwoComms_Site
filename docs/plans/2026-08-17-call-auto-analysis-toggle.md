# Call Auto-Analysis Toggle Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement and deploy a default-off staff switch for automatic call analysis with a fail-closed cron gate and no data loss.

**Architecture:** Persist the administrator's choice in `InstagramBotSettings.call_auto_analysis_enabled` and project enabled state to a private exact-token marker. Every producer, worker, health path, and snapshot uses one helper; the cron shell checks the marker before starting any Django process. The switch never mutates historical calls or the saved queue while off.

**Tech Stack:** Django 6.1, MariaDB, Django migrations, Django `transaction.on_commit`, staff JSON views with CSRF, POSIX shell cron, unittest/Django `TestCase`.

---

### Task 1: Add the failing state and marker tests

**Files:**
- Create: `twocomms/management/tests_call_auto_analysis.py`
- Modify: `twocomms/management/tests_ig_task_health.py`
- Modify: `twocomms/management/tests_telephony_call.py`

**Steps:**
1. Add tests for a missing singleton/default flag, exact valid/invalid marker content, fail-closed database/filesystem errors, and enable/disable publication with `captureOnCommitCallbacks(execute=True)`.
2. Add tests for API staff/CSRF/explicit-boolean behavior and queue-preserving OFF responses.
3. Add tests proving webhook/session persistence remains, while no `PENDING` or `SKIPPED` transition occurs when off; add worker tests proving no heartbeat, queue query, or provider call when off and that an existing pending row resumes after on.
4. Add health and snapshot tests for OFF filtering and ON monitoring.
5. Run the focused tests and confirm they fail because the field/helper/API do not exist yet.

### Task 2: Implement the persistent setting and runtime helper

**Files:**
- Modify: `twocomms/management/models.py`
- Create: `twocomms/management/migrations/0167_call_auto_analysis_enabled.py`
- Create: `twocomms/management/services/call_auto_analysis.py`

**Steps:**
1. Add the independent BooleanField with `default=False` and generate the migration with dependency `0166`.
2. Implement marker path resolution, strict token validation, atomic `0600` publication, safe removal, and state reads that never create a singleton row and always fail closed.
3. Implement atomic enable/disable transitions and expose configured/effective/error data for the staff endpoint.
4. Run the state tests until green, then refactor only without changing the contract.

### Task 3: Gate producers, worker, health, and snapshots

**Files:**
- Modify: `twocomms/management/services/call_ai_analysis.py`
- Modify: `twocomms/management/binotel_webhook.py`
- Modify: `twocomms/management/management/commands/run_call_ai_analyses.py`
- Modify: `twocomms/management/services/ig_task_health.py`
- Modify: `twocomms/management/bot_views.py` if its snapshot boundary requires it

**Steps:**
1. Gate `schedule_call_analysis()` before any queue transaction and preserve terminal states only when enabled.
2. Keep webhook call/session writes but block every analysis status transition while disabled.
3. Check the helper before heartbeat and before the worker's first queue/cap query; keep a second race guard before processing each row.
4. Exclude only the auto-analysis owner from health when off and return zero call counters without queue queries in release snapshots.
5. Run focused call, worker, health, and snapshot tests; verify the saved pending row is processed after re-enable.

### Task 4: Add the staff endpoint and switch UI

**Files:**
- Modify: `twocomms/management/binotel_views.py`
- Modify: `twocomms/management/urls.py`
- Modify: `twocomms/management/templates/management/binotel_test.html`
- Modify: `twocomms/management/templates/management/binotel_test_js.html`
- Create or extend: `twocomms/management/tests_binotel.py`

**Steps:**
1. Add a staff-only GET/POST JSON endpoint with normal CSRF enforcement and strict boolean parsing.
2. Render the compact Ukrainian switch card with explicit status and off explanation; do not add provider wording to the new card or messages.
3. Disable the control during POST, restore the previous state on errors, and display projection failures without silently claiming enabled.
4. Run endpoint/template tests and the existing telephony suite.

### Task 5: Gate the periodic cron before Python

**Files:**
- Modify: `scripts/install_instagram_periodic_jobs_cron.sh`
- Modify: `tests/test_install_instagram_periodic_jobs_cron.py`

**Steps:**
1. Add a validated absolute marker path and a shell gate that exits zero for missing, corrupt, symlinked, or unreadable markers before `cd`, `flock`, `timeout`, or Python.
2. Keep the managed block versioned, idempotent, and protective of unrelated crontab entries; update legacy-line recognition for the gated command.
3. Add installer and execution tests with fake marker/Python binaries proving OFF cannot launch Python and ON can reach the worker command.
4. Run the cron test module and shell syntax checks.

### Task 6: Verify, integrate, and deploy

**Files:**
- Modify: `docs/plans/2026-08-17-call-auto-analysis-toggle.md` only for evidence/status updates

**Steps:**
1. Run focused suites, shared management suites, migration drift checks, `manage.py check`, `compileall`, and `git diff --check` with the project CPython 3.14.6/Django 6.1 runtime.
2. Review every changed file and obtain independent agent review; reject unrelated changes or provider-name copy in the new control.
3. Fetch `origin/main`, reconcile with the adjacent Django implementation thread, rebase/fast-forward the isolated branch, and commit the scoped change.
4. Push the commit to `origin/main`; on production use only the documented SSH `git pull --ff-only origin main`, then run the required migration, cron installer, restart marker, and read-only checks.
5. Prove production flag `False`, absent marker, no Python launch from the gated cron, unchanged call/analysis/heartbeat counts, and healthy non-call owners before reporting completion.
