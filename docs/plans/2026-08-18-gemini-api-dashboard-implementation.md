# Gemini API Health Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship a discoverable `API` tab in the Instagram bot that reports six-key Gemini health, model observations, and proven 3.7 -> 3.6 fallbacks without background provider polling.

**Architecture:** Keep the existing redacted `GeminiRequestAttempt` ledger as the only history source. Add a small `gemini_health` service that performs bounded aggregation and fallback-sequence classification, admin-only GET/POST bot endpoints, and a lazy tab module that reads the GET endpoint only while visible. A manual probe uses the existing probe client with a minimal budget, records a redacted `health_probe` attempt, and is protected by model/key allowlists and cache locks; no migration is needed.

**Tech Stack:** Django 6.1, Python 3.14, existing management services/models, server-rendered Django template, vanilla JavaScript/CSS, Django TestCase.

---

### Task 1: Add the bounded health aggregator and regression tests

**Files:**
- Create: `twocomms/management/services/gemini_health.py`
- Create: `twocomms/management/tests_gemini_health.py`

**Step 1: Write the failing tests**

Add tests for a deterministic `build_snapshot()` contract using `GeminiRequestAttempt` rows and patched key state:

- six stable aliases are returned even when there are no attempts;
- 24 buckets contain gray `no_observation` entries rather than invented uptime;
- succeeded, recovered retry, and terminal failure map to green, amber, and red;
- a request with failed 3.7 followed by succeeded 3.6 emits a normalized reason and never raw provider detail;
- records outside the bounded window and over the query cap are ignored;
- model summaries report `insufficient_observations` when empty.

Run from `twocomms/`:

```bash
SECRET_KEY=test_local_secret "$TWC_PYTHON" manage.py test management.tests_gemini_health --settings=test_settings -v 2
```

Expected: FAIL because the service and snapshot contract do not exist.

**Step 2: Implement the minimal aggregator**

Implement constants for the two displayed models, 24-hour window, bucket count,
and query cap. Query only `GeminiRequestAttempt` fields needed for rendering,
order by request/id, and group in memory by key/model/request. Derive current
state from `gemini_keys.pool_status()` and map `GEMINI_API` through
`GEMINI_API6` to `API key 1` through `API key 6`. Normalize only known failure
kinds and decisions. Return a versioned dictionary with `generated_at`,
`window`, `summary`, `fallback`, and six `keys`.

**Step 3: Run the focused tests**

```bash
SECRET_KEY=test_local_secret "$TWC_PYTHON" manage.py test management.tests_gemini_health --settings=test_settings -v 2
```

Expected: PASS.

**Step 4: Commit**

```bash
git add twocomms/management/services/gemini_health.py twocomms/management/tests_gemini_health.py
git commit -m "feat: aggregate Gemini API health evidence"
```

### Task 2: Make manual probes tiny, explicit, and auditable

**Files:**
- Modify: `twocomms/management/services/gemini_probe.py`
- Modify: `twocomms/management/tests_gemini_probe.py`
- Create: `twocomms/management/services/gemini_health.py` (probe helper additions)

**Step 1: Write failing tests**

Test that the health-probe payload has a small bounded output budget and that a
probe result is recorded through `gemini_keys.record_attempt()` with role
`health_probe`, a redacted status/failure kind, and no response body.

**Step 2: Implement**

Lower the health-probe output budget to a small constant while preserving the
existing model normalization. Add a helper that maps the existing probe
classification to `succeeded`/`failed` and persists only bounded fields. Keep
the existing management command behavior compatible; it may continue updating
`GeminiKeyState` while the helper adds history.

**Step 3: Run tests**

```bash
SECRET_KEY=test_local_secret "$TWC_PYTHON" manage.py test management.tests_gemini_probe management.tests_gemini_health --settings=test_settings -v 2
```

Expected: PASS with no network calls.

**Step 4: Commit**

```bash
git add twocomms/management/services/gemini_probe.py twocomms/management/tests_gemini_probe.py twocomms/management/services/gemini_health.py
git commit -m "feat: record bounded Gemini health probes"
```

### Task 3: Expose read and manual-probe bot APIs

**Files:**
- Modify: `twocomms/management/bot_views.py`
- Modify: `twocomms/management/urls.py`
- Create or modify: `twocomms/management/tests_gemini_health.py`

**Step 1: Write failing endpoint tests**

Cover admin GET success, non-admin denial, reviewer denial, stable response
shape, no secret value leakage, invalid alias/model rejection, probe cache-lock
behavior, and mocked probe persistence. Assert that GET never calls
`gemini_probe.probe_key`.

**Step 2: Implement GET**

Add `management_bot_gemini_health_api` beside existing bot APIs. Require login
and `_require_admin_json`; call the aggregator only. Return JSON with schema
version and bounded freshness metadata.

**Step 3: Implement POST**

Add `management_bot_gemini_health_probe_api`. Validate `key_name` against
`gemini_keys.ALL_KEYS`, model against the two display models, require a present
key, acquire a cache lock for a short bounded period, call the probe with a
short timeout, record the redacted attempt, update `GeminiKeyState` probe
fields, and return only the sanitized result. Release the lock in `finally`.

**Step 4: Run endpoint tests**

```bash
SECRET_KEY=test_local_secret "$TWC_PYTHON" manage.py test management.tests_gemini_health --settings=test_settings -v 2
```

Expected: PASS.

**Step 5: Commit**

```bash
git add twocomms/management/bot_views.py twocomms/management/urls.py twocomms/management/tests_gemini_health.py
git commit -m "feat: expose admin Gemini API health endpoints"
```

### Task 4: Build the API tab with accessible history rails

**Files:**
- Modify: `twocomms/management/templates/management/bot.html`
- Modify: `twocomms/management/tests_ig_clients_ui.py`

**Step 1: Write failing template/JS contract tests**

Assert the `data-tab="api"` tab and panel exist for normal admins, the
reviewer template excludes the panel and endpoint URLs, the six-row container,
model labels, legend text, and no-secret safeguards are present, and the
existing JavaScript syntax check still parses the template script.

**Step 2: Implement markup and CSS**

Add an `API` tab and sibling panel using the existing dark surface. Render a
summary strip, fallback explanation region, six-row mount point, legend, and
manual row probe controls. Use fixed 24-segment rails with explicit labels and
ARIA descriptions, responsive stacking at existing breakpoints, horizontal
overflow on narrow screens, and reduced-motion-safe styles.

**Step 3: Implement lazy client module**

Add a self-contained `GeminiHealth` module to the existing IIFE. Load on API
tab activation, refresh only while the tab is active and document visible,
pause timers on visibility changes, and use a conservative read-only interval.
Render stale/error/no-data states without replacing the rest of the page. The
manual probe posts a selected alias/model with the existing CSRF helper, then
reloads the read snapshot; it must not start a global poll.

**Step 4: Run focused UI tests**

```bash
SECRET_KEY=test_local_secret "$TWC_PYTHON" manage.py test management.tests_ig_clients_ui management.tests_ig_reviewer_sandbox --settings=test_settings -v 2
```

Expected: PASS.

**Step 5: Commit**

```bash
git add twocomms/management/templates/management/bot.html twocomms/management/tests_ig_clients_ui.py
git commit -m "feat: add Gemini API health tab"
```

### Task 5: Reconcile implementation documentation

**Files:**
- Modify: `docs/instagram_bot_audit/14_IMPLEMENT2.md`
- Modify if needed: `docs/instagram_bot_audit/15_IMPLEMENT2_EMERGENT_FINDINGS.md`

Record the new API tab as a bounded IMP-044 follow-up, state that it uses real
attempt evidence and manual probes only, and leave unrelated IMP-044 timeout/
lease work marked partial. Include the exact endpoint, privacy boundary, and
verification evidence; do not mark the whole IMP-044 closed.

Run `git diff --check` and commit:

```bash
git add docs/instagram_bot_audit/14_IMPLEMENT2.md docs/instagram_bot_audit/15_IMPLEMENT2_EMERGENT_FINDINGS.md
git commit -m "docs: record Gemini API dashboard release scope"
```

### Task 6: Release gate and production proof

Run the smallest complete local gate from `twocomms/`:

```bash
SECRET_KEY=test_local_secret "$TWC_PYTHON" manage.py test management.tests_gemini_health management.tests_gemini_probe management.tests_ig_clients_ui management.tests_ig_reviewer_sandbox --settings=test_settings -v 1
SECRET_KEY=test_local_secret "$TWC_PYTHON" manage.py check --settings=test_settings
SECRET_KEY=test_local_secret "$TWC_PYTHON" manage.py makemigrations --check --dry-run --settings=test_settings
"$TWC_PYTHON" -m compileall -q twocomms/management
git diff --check
```

Run one desktop and one narrow browser check of `/bot/?section=api` (or the
stored tab state), verifying six rows, no secret values, no provider request
on read refresh, and a usable no-data/error state.

Push the scoped branch to GitHub, fast-forward `main` as required by the
project workflow, and deploy only with the approved SSH `git pull --ff-only
origin main` command. On production verify exact `HEAD`, `manage.py check`,
the API GET shape/counts as an admin, reviewer denial, and that a read-only GET
does not change `GeminiRequestAttempt` count. Record all evidence in
`14_IMPLEMENT2.md` before finalizing.
