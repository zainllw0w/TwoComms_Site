# Management Statistics Visual Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Instagram management statistics truthful, compact and visually legible for any selected date range, including one-day and zero-attribution periods.

**Architecture:** Normalize event timestamps into explicit local-date buckets in the backend before serialization, then render a density-aware vanilla-JS dashboard. The frontend uses one composition ring, one adaptive activity visualization, a stepped event funnel, compact ranked rows and progressive disclosures. Existing API fields remain backward-compatible; new metadata describes chart density and data availability.

**Tech Stack:** Django 5 ORM, MariaDB-compatible queries, vanilla JavaScript/CSS in `management/templates/management/bot.html`, Django TestCase, browser screenshots and production API smoke checks.

---

### Task 1: Capture the MariaDB bucket regression

**Files:**
- Modify: `twocomms/management/tests_ig_stats_visuals.py`
- Modify: `twocomms/management/bot_views.py:5260-5315`

**Step 1: Write the failing test**

Create visible messages where `provider_created_at` is set for some rows and null for others. Request a seven-day range and assert every series row has a non-null ISO `bucket`, and the sum of `messages`, `inbound_messages`, `bot_replies` and `manager_messages` matches the API totals.

**Step 2: Run the focused test**

Run `DEBUG=1 SECRET_KEY=codex-local-test-only python manage.py test management.tests_ig_stats_visuals.StatsApiVisualContractTests.test_message_series_buckets_never_null_and_reconcile_totals`.

Expected: FAIL because MariaDB groups the `Coalesce` annotation as `bucket=None`.

**Step 3: Implement the smallest root fix**

Replace database-side truncation of the `Coalesce` expression with a two-stage approach: query rows grouped by `provider_created_at` and `created_at` using the existing time filter, then normalize the selected timestamp and bucket in Python. Keep the queryset bounded by the selected period and preserve day/week/month density rules.

**Step 4: Run the focused test**

Run the same test and confirm it passes on SQLite. Run the equivalent production shell query on MariaDB and confirm no null buckets.

**Step 5: Commit**

Commit `fix(management): normalize statistics time buckets`.

### Task 2: Add explicit visualization metadata

**Files:**
- Modify: `twocomms/management/bot_views.py`
- Modify: `twocomms/management/tests_ig_stats_visuals.py`

**Step 1: Write failing contract tests**

Assert `message_series` and `ad_analytics.message_series` contain `has_data`, `max_total`, `density`, `granularity` and a stable `items` array. Empty ranges must return `has_data=false`, `max_total=0` and no fake value rows.

**Step 2: Implement metadata**

Derive metadata from normalized items and the selected period. `density` is `single`, `compact`, `daily`, `weekly` or `monthly`; it is descriptive, not a client guess.

**Step 3: Run tests**

Run the API visual contract tests and funnel analytics tests.

**Step 4: Commit**

Commit `feat(management): expose chart density metadata`.

### Task 3: Build the activity visual system

**Files:**
- Modify: `twocomms/management/templates/management/bot.html`
- Modify: `twocomms/management/tests_ig_stats_visuals.py`

**Step 1: Add RED template contracts**

Assert the template contains the `single/compact/daily` activity classes, a zero-state class, `data-tooltip-placement`, and a ring component contract.

**Step 2: Implement the visual states**

- `single`: 64px pulse strip with three role counters and one day label.
- `compact`: 96px seven-day stacked bars.
- `daily/weekly/monthly`: density-aware bars with selected labels.
- zero state: baseline dot and concise scope line; no full-height dark stack.
- tooltip: calculate a clamped placement inside the chart scroll element; on touch it toggles and on Escape/outside click it closes.

**Step 3: Implement the composition ring**

Use a CSS conic-gradient ring with CSS custom properties, a centered total, three legend rows and keyboard/touch segment focus. Do not add a chart library for one ring.

**Step 4: Run template/JS tests**

Run `management.tests_ig_stats_visuals`, `management.tests_ig_clients_ui.ClientWorkspaceTemplateContractTests` and the inline JavaScript syntax test.

**Step 5: Commit**

Commit `feat(management): redesign activity and composition visuals`.

### Task 4: Recompose funnel, advertising and detail states

**Files:**
- Modify: `twocomms/management/templates/management/bot.html`
- Modify: `twocomms/management/tests_ig_stats_visuals.py`

**Step 1: Add RED visual contracts**

Require a funnel bottleneck marker, entered/advanced/drop-off labels, an attribution diagnostic state, compact campaign rails, compact product rows and a single section-level sparse-data note.

**Step 2: Implement the layout**

Place the composition ring beside the funnel on desktop and stack them on mobile. Keep advertising permanently visible with a campaign/organic/unknown attribution split. Keep detail tables in disclosures with count badges and no repeated `Мало даних` cells.

**Step 3: Implement interaction**

Clicking a funnel step highlights its evidence row; campaign/product rows retain the existing disclosure behavior. Focus must move to opened content and Escape must close it.

**Step 4: Run tests**

Run focused template tests and all statistics/funnel/sales UI tests. Include a fixture with an attributed campaign and a fixture with zero attribution.

**Step 5: Commit**

Commit `feat(management): clarify funnel and advertising states`.

### Task 5: Browser QA and regression sweep

**Files:**
- Modify: `twocomms/management/tests_ig_stats_visuals.py` only if a regression is found.
- Create: `docs/qa/2026-08-08-management-stats-visual-qa.md`

**Step 1: Start isolated QA server**

Use the test fixture with visible messages, non-monotonic funnel events, one campaign, two products, zero-attribution clients and empty custom dates.

**Step 2: Capture required viewports**

Capture `1440`, `1024`, `768`, `390`, `375`, `320` for `1`, `7`, `30` and custom periods.

**Step 3: Exercise interactions**

Tap/hover activity bars, focus ring segments, open/close disclosures, change periods, use Escape, click outside tooltips and enable reduced motion.

**Step 4: Verify invariants**

Assert no horizontal overflow, no tooltip occlusion, no null/NaN labels, totals reconcile with visible bars, and empty states do not create tall dead space.

**Step 5: Commit**

Commit `test(management): record statistics visual QA`.

### Task 6: Ship and verify production

**Step 1: Run final gates**

Run the complete focused suite, Django check, migration drift check, compileall and `git diff --check`.

**Step 2: Push the feature branch**

Push every implementation commit to `origin/codex/management-bot-statistics-redesign`.

**Step 3: Integrate `main`**

Fast-forward the primary checkout to the verified branch, push `origin/main`, and restore unrelated WIP without overwriting it.

**Step 4: Deploy**

On `/home/qlknpodo/TWC/TwoComms_Site/twocomms`, run `git pull --ff-only origin main`, migrations, check, collectstatic, compress, Passenger restart and `run_instagram_bot --ensure`.

**Step 5: Verify live**

Compare local/origin/server SHA, call `/bot/health/`, run the authenticated stats API against production MySQL for 1/7/30/custom ranges, and record the result in the QA report.
