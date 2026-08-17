# Call Auto-Analysis Toggle Design

**Status:** Approved for implementation from the requested administrator-facing control.

**Goal:** Give staff one visible, default-off switch named `Автоаналіз дзвінків` that stops all automatic analysis work without deleting calls, analyses, or the saved queue.

## Scope and invariants

The switch is independent from Instagram bot settings and is stored on the existing singleton `InstagramBotSettings` row as `call_auto_analysis_enabled`, defaulting to `False`. The database value is the administrative configuration; a private marker in the Django `tmp` directory is its runtime projection for the scheduler.

When the effective state is off:

- no new analysis intent or queue row is created;
- existing pending/running/error rows are not read, changed, retried, or deleted;
- the cron shell gate exits before `cd`, `flock`, `timeout`, Python, Django, MariaDB, telephony, or Gemini are started;
- the worker does not write a heartbeat or query the queue;
- health monitoring omits only the auto-analysis owner while monitoring every other owner;
- queue snapshots return a complete shape with zero auto-analysis counters and exclude the saved backlog from `dangerous_backlog`;
- webhook call/session persistence and manual telephony tools continue to work, but webhook processing does not move an analysis state into or out of the queue.

Turning the switch on does not reset anything. After the marker is published, the existing state machine may resume previously saved `PENDING` work. Turning it off first removes the marker, so a database write failure cannot leave the scheduler enabled; the queue remains intact.

## Runtime state and failure handling

The marker contains one exact versioned token and is written with mode `0600` through a temporary file plus `os.replace`. A missing marker, empty/corrupt content, symlink, directory, or unreadable path is off. The application helper is fail-closed on database or filesystem errors and exposes configured versus effective state to the staff endpoint.

Enabling saves the database flag inside `transaction.atomic()` and registers marker publication with `transaction.on_commit()`. The callback cannot run after a rolled-back transaction. If publication fails, the API reports a degraded/off effective state and attempts a compensating database disable; no request path may treat a missing marker as enabled. Disabling removes the marker before saving `False`, then reports any partial failure explicitly while remaining effective-off.

## Integration boundaries

The same state helper is checked before enqueue transactions, at webhook queue transitions, before the worker heartbeat, and again before worker queue queries to cover races. Provider/Gemini imports and calls remain unreachable while off. The health and release snapshot paths check the helper before importing or querying call-analysis data.

The periodic-cron installer installs one stable job. Its shell gate is deliberately cheaper than a Django command and is idempotent with the existing managed block. It preserves unrelated crontab entries and rejects duplicate or unknown owner lines.

## Staff experience

The existing staff-only telephony page receives a compact card near its heading. New copy uses only `Автоаналіз дзвінків`, `Увімкнути автоаналіз дзвінків`, `Увімкнено`, and `Вимкнено`; it does not expose the provider name in the new control. A dedicated CSRF-protected JSON endpoint accepts only an explicit boolean. It returns configured/effective state, a short failure reason when projection is inconsistent, and never calls the telephony API.

## Verification

Focused tests cover default-off migration behavior, exact marker reads/writes, atomic callback semantics, failed publication, API access/CSRF/validation, enqueue/webhook preservation, worker heartbeat and provider boundaries, health/snapshot filtering, cron shell-gate behavior, and re-enabling saved pending work. Shared management tests, migration drift, `manage.py check`, `compileall`, `git diff --check`, and a production read-only smoke follow. Production verification must prove the database flag is false, the marker is absent, the cron command exits before Python, call rows/counts are unchanged, and other health owners remain monitored.
