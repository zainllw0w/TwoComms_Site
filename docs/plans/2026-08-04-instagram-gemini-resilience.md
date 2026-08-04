# Instagram Gemini Resilience Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the Instagram live-reply path prefer Gemini 3.6, use all six keys intelligently, degrade only when necessary, and recover failed customer turns with provider-receipt evidence.

**Architecture:** Add a chat-specific, deadline-aware attempt planner on top of DB-backed key/model leases and typed provider errors. Keep background analysis independent. Add a dedicated durable recovery outbox that revalidates consent and reply boundaries, persists a draft before Meta I/O, and never replays an ambiguous send.

**Tech Stack:** Python 3.14/3.13, Django 5.2, MariaDB, `requests`, Meta Instagram Login Send API, Gemini REST `generateContent`, Django `TestCase`/`TransactionTestCase`.

---

### Task 1: Lock the incident and model policy with failing tests

**Files:**
- Modify: `twocomms/management/tests_checker_gemini.py`
- Modify: `twocomms/management/tests_gemini_keys.py`
- Modify: `twocomms/management/tests_gemini_reasoning.py`
- Test: `twocomms/management/tests_ig_bot_resilience.py`

**Step 1: Write the incident regression**

Add a fake monotonic clock and `_gemini_call_once` side effect that raises two
slow 3.6 timeouts and succeeds on a 3.5 fallback. Assert the fallback is reached,
the timeout passed to each request shrinks, and total elapsed time does not
exceed the selected 35/45-second budget.

**Step 2: Write model and six-key ordering tests**

Assert the live chain is `3.6 -> 3.5 Flash -> 3.5 Flash-Lite`, hot aliases precede
shared and last reserves, fast auth failures can rotate all six, and slow
transients cannot consume six long calls.

**Step 3: Write reasoning/output-budget tests**

Assert ordinary chat is low/1536 while product, size, payment, order, catalog,
and media tasks remain high/4096.

**Step 4: Run the tests and verify RED**

Run:

```bash
/Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_checker_gemini \
  management.tests_gemini_keys \
  management.tests_gemini_reasoning \
  management.tests_ig_bot_resilience \
  --settings=test_settings --verbosity=2
```

Expected: new adaptive-planner, lease, and model-chain assertions fail.

**Step 5: Commit tests**

```bash
git add twocomms/management/tests_checker_gemini.py \
  twocomms/management/tests_gemini_keys.py \
  twocomms/management/tests_gemini_reasoning.py \
  twocomms/management/tests_ig_bot_resilience.py
git commit -m "test: reproduce Instagram Gemini failover deadline"
```

### Task 2: Add durable Gemini leases, circuits, and redacted attempts

**Files:**
- Modify: `twocomms/management/models.py`
- Modify: `twocomms/management/ig_bot_models.py`
- Create: `twocomms/management/migrations/0135_gemini_resilience_state.py`
- Modify: `twocomms/management/services/gemini_keys.py`
- Modify: `twocomms/management/services/ig_engine_health.py`
- Modify: `twocomms/management/tests_ig_engine_health.py`
- Test: `twocomms/management/tests_gemini_keys.py`

**Step 1: Add state models**

Extend `GeminiKeyState` with `lease_token`, `lease_until`, `lease_role`,
`last_http_code`, `last_failure_kind`, `consecutive_failures`, and
`latency_ewma_ms`. Add `GeminiModelState(model_name unique, circuit_until,
circuit_reason, transient_failures, last_failure_project, last_failure_at,
last_ok_at)`. Add redacted `GeminiRequestAttempt` fields described in the design.

**Step 2: Generate and inspect migration 0135**

Run:

```bash
/Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py makemigrations management --name gemini_resilience_state
```

Expected: only intended Gemini state/attempt schema changes.

**Step 3: Implement atomic lease primitives**

Implement `ordered_key_candidates`, `acquire_key_lease`, `release_key_lease`,
`record_key_success`, and `record_key_failure`. Use `transaction.atomic()` and
`select_for_update()`. Claim known project siblings together, release only with
the matching token, and never keep a transaction open during HTTP.

**Step 4: Implement DB model circuits**

Implement `open_model_circuit`, `model_circuit_open`, `record_model_success`, and
safe half-open ownership. Replace the process-local-only overload decision in
the live path.

**Step 5: Make engine auditing cover new tables**

Add the new runtime tables to `IG_RUNTIME_TABLES` and migration/engine tests.

**Step 6: Run focused tests and verify GREEN**

```bash
/Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_gemini_keys management.tests_ig_engine_health \
  --settings=test_settings --verbosity=2
```

**Step 7: Commit**

```bash
git add twocomms/management/models.py twocomms/management/ig_bot_models.py \
  twocomms/management/migrations/0135_gemini_resilience_state.py \
  twocomms/management/services/gemini_keys.py \
  twocomms/management/services/ig_engine_health.py \
  twocomms/management/tests_gemini_keys.py \
  twocomms/management/tests_ig_engine_health.py
git commit -m "feat: add durable Gemini failover state"
```

### Task 3: Implement typed errors and the adaptive live planner

**Files:**
- Modify: `twocomms/management/services/call_ai_analysis.py`
- Modify: `twocomms/management/services/gemini_keys.py`
- Modify: `twocomms/management/services/gemini_probe.py`
- Modify: `twocomms/management/management/commands/probe_ig_gemini_pool.py`
- Test: `twocomms/management/tests_checker_gemini.py`
- Test: `twocomms/management/tests_gemini_probe.py`
- Test: `twocomms/management/tests_ig_bot_resilience.py`

**Step 1: Introduce one safe provider error parser**

Parse `error.code`, `error.status`, `ErrorInfo.reason`, `RetryInfo.retryDelay`,
and quota details into a bounded value object. Never retain the raw body. Map
`API_KEY_INVALID`, auth, project permission, model not found, quota, payload,
safety, transient HTTP, transport, timeout, and empty output separately.

**Step 2: Make `_gemini_call_once` raise typed errors**

Ensure a 400 key error rotates the key, a malformed-payload 400 terminates the
shared request, a 403 does not blacklist every model, a 404 opens a model
circuit, and transport timeout is logged as `read_timeout`, not 503.

**Step 3: Implement `_run_chat_with_pool`**

Use the task-specific deadline, protected fallback reserve, remaining-budget
timeout clipping, DB leases in `try/finally`, and error-driven transitions from
the design. Normal success must make one provider request; no live backoff sleep
or multi-round traversal remains.

**Step 4: Keep the generic runner for background roles**

Route only `role="chat"` through the new planner. Apply the shared typed error
parser and key leases to background requests without imposing the chat SLA.

**Step 5: Persist redacted attempt telemetry**

Write one `GeminiRequestAttempt` per provider call with outcome, decision,
latency, remaining deadline, and usage. Do not persist prompt/response content.

**Step 6: Unify probes with live classification**

Make `gemini_probe` use the same safe error parser and DB lease. Add explicit
3.6/3.5/Flash-Lite probing without customer messages.

**Step 7: Run focused tests**

```bash
/Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_checker_gemini management.tests_gemini_probe \
  management.tests_ig_bot_resilience --settings=test_settings --verbosity=2
```

**Step 8: Commit**

```bash
git add twocomms/management/services/call_ai_analysis.py \
  twocomms/management/services/gemini_keys.py \
  twocomms/management/services/gemini_probe.py \
  twocomms/management/management/commands/probe_ig_gemini_pool.py \
  twocomms/management/tests_checker_gemini.py \
  twocomms/management/tests_gemini_probe.py \
  twocomms/management/tests_ig_bot_resilience.py
git commit -m "feat: make Gemini chat failover deadline aware"
```

### Task 4: Add the durable AI reply recovery outbox

**Files:**
- Modify: `twocomms/management/ig_bot_models.py`
- Create: `twocomms/management/migrations/0136_ig_ai_reply_recovery.py`
- Create: `twocomms/management/services/ig_ai_reply_recovery.py`
- Create: `twocomms/management/tests_ig_ai_reply_recovery.py`
- Modify: `twocomms/management/services/ig_engine_health.py`

**Step 1: Write recovery RED tests**

Cover unique intent, leases, consent/epoch/floor/window revalidation, newer
inbound cancellation, persisted-draft reuse, one provider request, confirmed
receipt finalization, and terminal ambiguity.

**Step 2: Add `IgAiReplyRecoveryJob` and migration**

Use the statuses and fields in the design. Foreign keys to legacy IG tables must
set `db_constraint=False`. Add `(status, due_at, id)` and client-time indexes.

**Step 3: Implement claim and eligibility**

Acquire the shared client automation lease before the job lease. Revalidate all
customer consent and conversation boundaries both before Gemini and before
Meta. Never hold a DB transaction during provider I/O.

**Step 4: Implement generation and draft persistence**

Build history only through the source message and exclude the holding response.
Create one localized apology-plus-answer draft, strip service controls, cap it
to one Meta chunk, and persist it before changing `send_state` to `sending`.

**Step 5: Implement crash-safe delivery**

Pass both `return_receipt=True` and a durable provider-message callback to
`send_text`. Finalize a confirmed receipt transactionally; treat missing receipt,
timeout, or stale `sending` without receipt as terminal ambiguity with one
deduplicated manager notification.

**Step 6: Run tests and commit**

```bash
/Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_ai_reply_recovery --settings=test_settings --verbosity=2
git add twocomms/management/ig_bot_models.py \
  twocomms/management/migrations/0136_ig_ai_reply_recovery.py \
  twocomms/management/services/ig_ai_reply_recovery.py \
  twocomms/management/services/ig_engine_health.py \
  twocomms/management/tests_ig_ai_reply_recovery.py
git commit -m "feat: add durable Instagram AI reply recovery"
```

### Task 5: Integrate recovery and provider receipts into the live bot

**Files:**
- Modify: `twocomms/management/services/bot_reply_fallback.py`
- Modify: `twocomms/management/services/instagram_bot.py`
- Modify: `twocomms/management/services/ig_reply_boundary.py`
- Modify: `twocomms/management/management/commands/run_instagram_bot.py`
- Modify: `twocomms/management/tests_ig_live_reply_priority.py`
- Modify: `twocomms/management/tests_ig_daemon.py`
- Test: `twocomms/management/tests_ig_ai_reply_recovery.py`

**Step 1: Make fallback outcome structured**

Return text, true manager-handoff flag, and recovery eligibility. Keep factual
and genuine manager cases unchanged. Generic provider exhaustion uses localized
holding copy and must not enter `lead_manager` or promise a manager.

**Step 2: Persist all successful Meta receipts**

Call `send_text(return_receipt=True)`, require the provider message ID, write it
to the model history row, and update `last_bot_reply_at` in the post-send
transaction.

**Step 3: Prepare/activate recovery around the holding send**

Create the unique intent before Meta I/O. Activate it only with confirmed
receipt evidence. Missing receipt becomes ambiguous and is never retried as a
holding response.

**Step 4: Harden the central reply boundary**

Make active durable opt-out an explicit denial in `ig_reply_boundary`, not an
indirect consequence of `bot_paused`.

**Step 5: Start a maintenance-aware recovery worker**

Add a separate daemon thread that yields to pending live rows, closes old DB
connections, and processes one due recovery at a time.

**Step 6: Update regression expectations**

Assert generic fallback no longer causes manager handoff, genuine handoffs are
unchanged, provider IDs persist, and baseline follow-up copy remains semantically
equivalent.

**Step 7: Run and commit**

```bash
/Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_live_reply_priority \
  management.tests_ig_ai_reply_recovery \
  management.tests_ig_daemon --settings=test_settings --verbosity=2
git add twocomms/management/services/bot_reply_fallback.py \
  twocomms/management/services/instagram_bot.py \
  twocomms/management/services/ig_reply_boundary.py \
  twocomms/management/management/commands/run_instagram_bot.py \
  twocomms/management/tests_ig_live_reply_priority.py \
  twocomms/management/tests_ig_ai_reply_recovery.py \
  twocomms/management/tests_ig_daemon.py
git commit -m "feat: recover Gemini outage replies safely"
```

### Task 6: Add guarded legacy recovery and operator visibility

**Files:**
- Create: `twocomms/management/management/commands/recover_ig_ai_reply.py`
- Modify: `twocomms/management/services/instagram_bot.py`
- Modify: `twocomms/management/bot_views.py`
- Modify: `twocomms/management/templates/management/bot.html`
- Create: `twocomms/management/tests_recover_ig_ai_reply_command.py`
- Modify: `twocomms/management/tests_ig_category_ui.py`

**Step 1: Write command safety tests**

Default is status/dry-run. `--schedule` requires an eligible user source row;
`--process` still honors opt-out, takeover, newer messages, message floor, and
window checks. Legacy unreceipted fallback acknowledgment is explicit.

**Step 2: Implement the command**

Accept `--source-message-id`, `--schedule`, `--process`, and the narrowly named
legacy acknowledgment flag. Print job state and only redacted provider evidence.

**Step 3: Extend dashboard status**

Show all six key aliases, project-identity warnings, key leases, exact last
failure class/code, model circuits, recent redacted attempts, and pending/
ambiguous recovery counts. Never render secrets or provider bodies.

**Step 4: Run and commit**

```bash
/Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_recover_ig_ai_reply_command \
  management.tests_ig_category_ui --settings=test_settings --verbosity=2
git add twocomms/management/management/commands/recover_ig_ai_reply.py \
  twocomms/management/services/instagram_bot.py \
  twocomms/management/bot_views.py \
  twocomms/management/templates/management/bot.html \
  twocomms/management/tests_recover_ig_ai_reply_command.py \
  twocomms/management/tests_ig_category_ui.py
git commit -m "feat: expose Gemini recovery operations"
```

### Task 7: Full local verification and review

**Files:**
- Modify if required: `docs/instagram_bot_audit/00_PROGRESS.md`
- Modify if required: `docs/instagram_bot_audit/03_FINDINGS_REGISTER.md`

**Step 1: Run focused suites**

Run all suites named above and the related authority/model/priority/consent/
delivery/daemon/analysis suites.

**Step 2: Run system and migration checks**

```bash
/Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py check --settings=test_settings
/Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py makemigrations --check --dry-run
/Users/zainllw0w/TwoComms/site/.venv/bin/python -m compileall -q management
git diff --check
```

Expected: zero new failures, no migration drift, no syntax or whitespace errors.
The one pre-existing English follow-up assertion must be either fixed with
semantic evidence or explicitly reproduced unchanged before and after.

**Step 3: Run no-network fault matrix**

Exercise every typed HTTP/transport branch, six-key lease contention,
project-group cooldown, model-circuit expiry, recovery races, and ambiguous Meta
delivery without real customer sends.

**Step 4: Request independent code review**

Use `superpowers:requesting-code-review`; resolve critical/high findings and
rerun the affected suites.

**Step 5: Update audit records and commit**

```bash
git add docs/instagram_bot_audit
git commit -m "docs: record Gemini resilience verification"
```

### Task 8: Integrate, deploy, verify, and recover the affected conversation

**Files:**
- No new code expected.

**Step 1: Verify branch diff and commit scope**

```bash
git status --short
git diff --stat origin/main...HEAD
git log --oneline origin/main..HEAD
```

**Step 2: Integrate into current remote main safely**

Fetch, rebase or recreate only if `origin/main` advanced, rerun affected tests,
fast-forward the repository's `main`, and push `origin/main` without touching the
dirty primary checkout.

**Step 3: Deploy production**

Run the user-authorized SSH deployment with the password supplied out of band;
never echo or commit it. On the server run fast-forward pull, migrations,
`manage.py check`, static collection/compression, Passenger restart sentinel,
and `run_instagram_bot --ensure`.

**Step 4: Probe all six keys redacted**

Probe the three live-chain models with bounded parallelism and verify provider
status, latency, model circuits, leases, and project-group visibility. Do not
send any customer or ad test event.

**Step 5: Verify production state**

Prove deployed SHA, applied migrations, InnoDB runtime tables, daemon heartbeat,
webhook health, queue/recovery counts, and effective `gemini-3.6-flash` primary.

**Step 6: Recover source message 2468 exactly once operationally**

First run the recovery command in status mode, then schedule/process the legacy
incident with all guards enabled. Verify the generated message contains a brief
apology plus the substantive answer, stores a non-empty Meta message ID, updates
`last_bot_reply_at`, and leaves the job `sent`.

**Step 7: Prove idempotency**

Run the same command again in status/process mode. Expected: no Gemini call, no
second Meta request, the same terminal job and provider message ID.

**Step 8: Final production smoke**

Confirm no pending/processing orphan rows, no stale leases, no new manager
handoff for the recovered client, and the independent CRM-analysis worker still
operates with live-reply priority.
