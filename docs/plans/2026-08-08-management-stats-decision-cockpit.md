# Management Statistics Decision Cockpit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the text-heavy Instagram management statistics with a truthful, linked decision cockpit for activity, funnel loss, advertising efficiency, product demand and verified commercial outcome.

**Architecture:** Keep the existing Django API and vanilla JavaScript page, but add an explicit metric/source contract and render each analytical question with the visual form that matches its unit. A shared selection state links the funnel, loss, campaign and product modules. Advertising spend is stored in an audited daily ledger; calculations remain unavailable until spend and attributed revenue share a valid period and identity scope.

**Tech Stack:** Django 5, MariaDB-compatible ORM, vanilla JavaScript and CSS in the existing management template, Django TestCase/SimpleTestCase, Playwright browser QA, atomic release deploy.

**Design:** `docs/plans/2026-08-08-management-stats-decision-cockpit-design.md`

---

## Global Delivery Rules

- Work only in `codex/management-stats-decision-cockpit` until integration.
- Preserve all unrelated WIP in the primary checkout.
- Every behavioral slice starts with a failing test.
- Every percentage field names its numerator and denominator in the API contract.
- Do not send live Meta test events or mutate production analytics for QA.
- Do not display spend, ROAS or cost metrics when the spend source is absent or misaligned.
- Do not use the word profit for revenue minus advertising spend.
- Treat legacy/current-client advertising attribution as independent period signals, never as a causal funnel.
- Keep unknown payment amounts out of currency totals while retaining their verified payment count.
- For the representative uncached 30-day response, enforce no more than 20 SQL queries, 2,000 materialized raw message rows and 350 KiB; record wall time against a 750 ms local target.
- After each independently deployable stage: focused tests, commit, push branch, integrate into current `main`, push `main`, deploy exact SHA, verify deployed SHA and live statistics endpoint.
- Keep the previous valid UI when a refresh fails.

## Stage 1: Data Semantics And Source Contracts

### Task 1: Add explicit module metric contracts

**Files:**

- Modify: `twocomms/management/bot_views.py:5131-6121`
- Modify: `twocomms/management/tests_ig_stats_visuals.py`

**Step 1: Write failing API contract tests**

Add tests that require:

```python
self.assertEqual(payload["schema_version"], 3)
self.assertEqual(payload["scope"]["timezone"], "Europe/Kiev")
self.assertEqual(payload["modules"]["activity"]["time_basis"], "message_event")
self.assertEqual(payload["modules"]["funnel"]["time_basis"], "event_cohort")
self.assertEqual(payload["modules"]["current_stages"]["time_basis"], "current_snapshot")
self.assertEqual(
    payload["modules"]["funnel"]["metrics"]["conversion"]["denominator"],
    "entered",
)
```

Require every percentage-capable metric to expose:

- unit;
- basis;
- time field;
- population;
- numerator;
- denominator;
- completeness;
- time basis;
- source kind;
- availability.

**Step 2: Run the focused tests and confirm RED**

Run:

```bash
DEBUG=1 SECRET_KEY=codex-local-test-only python manage.py test \
  management.tests_ig_stats_visuals.StatsApiVisualContractTests.test_stats_modules_expose_time_basis_and_denominators \
  --settings=test_settings
```

Expected: FAIL because schema version 2 has no module contract.

**Step 3: Implement the additive schema**

Add a `scope` object and `modules` metadata without removing existing response keys. Build metadata through small helpers rather than embedding repeated dictionaries in the response.

Example shape:

```python
def metric_contract(*, unit, numerator="", denominator="", time_basis, source, available=True):
    return {
        "unit": unit,
        "numerator": numerator,
        "denominator": denominator,
        "time_basis": time_basis,
        "source": source,
        "available": bool(available),
    }
```

**Step 4: Run the complete stats API contract suite**

Run:

```bash
DEBUG=1 SECRET_KEY=codex-local-test-only python manage.py test \
  management.tests_ig_stats_visuals.StatsApiVisualContractTests \
  --settings=test_settings
```

Expected: PASS.

**Step 5: Commit**

```bash
git add twocomms/management/bot_views.py twocomms/management/tests_ig_stats_visuals.py
git commit -m "feat(management): expose statistics metric contracts"
```

### Task 1A: Reconcile funnel cohorts and right-censoring

**Files:**

- Modify: `twocomms/management/services/ig_funnel_analytics.py:704-882`
- Modify: `twocomms/management/bot_views.py`
- Modify: `twocomms/management/tests_ig_funnel_analytics.py`
- Modify: `twocomms/management/tests_ig_stats_visuals.py`

**Step 1: Write failing cohort tests**

Create episodes where entry, next step and drop-off fall on different sides of the selected period. Require each stage to derive `advanced`, `drop_off` and `in_progress` from one `entered_episode_ids` set and assert:

```python
self.assertTrue(step["reconciled"])
self.assertEqual(
    step["entered"],
    step["advanced"] + step["drop_off"] + step["in_progress"],
)
self.assertEqual(step["cohort_basis"], "entry_event_same_window")
```

Require an explicit `right_censored_count` for entries that cannot have been observed through the cutoff.

**Step 2: Confirm RED**

Run the new tests. Expected: FAIL because the current builder independently filters events and drop-offs and can create a false denominator.

**Step 3: Implement one cohort per stage**

For each canonical stage, collect entry events in the period, order later events per episode, exclude recovered terminal losses and derive mutually exclusive sets. Include `observation_cutoff`, `reconciled`, `right_censored_count`, `time_field` and `completeness` in each row. Suppress conversion when reconciliation fails or the sample is below the existing low-sample threshold.

**Step 4: Run funnel and stats tests**

Expected: PASS for same-window semantics, cross-boundary events, recovered losses and low samples.

**Step 5: Commit**

```bash
git add twocomms/management/services/ig_funnel_analytics.py \
  twocomms/management/bot_views.py \
  twocomms/management/tests_ig_funnel_analytics.py \
  twocomms/management/tests_ig_stats_visuals.py
git commit -m "fix(management): reconcile funnel cohorts and censoring"
```

### Task 2: Separate client objections from signal volume

**Files:**

- Modify: `twocomms/management/bot_views.py:5452-5468`
- Modify: `twocomms/management/tests_ig_stats_visuals.py`

**Step 1: Write a failing semantic test**

Create one client with a primary objection and three matching signal events. Assert:

```python
self.assertEqual(payload["objection_clients"]["price"], 1)
self.assertEqual(payload["objection_signals"]["price_objection"], 3)
```

Also assert the legacy `objections` field remains additive/backward compatible during rollout but is not used by the new UI.

**Step 2: Confirm RED**

Run the single test. Expected: FAIL because the existing response merges client and signal counts.

**Step 3: Implement two named collections**

Return separately sorted client and event data. Attach distinct units and denominators to the module contract.

**Step 4: Run focused and full stats tests**

Expected: PASS with no change to verified payment behavior.

**Step 5: Commit**

```bash
git add twocomms/management/bot_views.py twocomms/management/tests_ig_stats_visuals.py
git commit -m "fix(management): separate objection clients from signals"
```

### Task 3: Add hourly one-day activity buckets

**Files:**

- Modify: `twocomms/management/bot_views.py:5237-5360`
- Modify: `twocomms/management/tests_ig_stats_visuals.py`

**Step 1: Write failing tests**

For a one-day range with messages in three hours, require `message_series.hourly_items` with 24 local-hour buckets and reconciled totals. Require an empty day to return 24 zero buckets with `has_data=False` and no synthetic events.

**Step 2: Confirm RED**

Run the two new tests. Expected: FAIL because only daily/weekly/monthly items exist.

**Step 3: Implement local hourly aggregation**

Reuse the already-normalized application-time rows. Do not reintroduce MariaDB timezone conversion. Only serialize hourly buckets when density is `single`.

**Step 4: Run activity regression tests**

Include provider-time fallback, DST-safe local labels, total reconciliation and empty range.

**Step 5: Commit**

```bash
git add twocomms/management/bot_views.py twocomms/management/tests_ig_stats_visuals.py
git commit -m "feat(management): add one-day activity pulse data"
```

### Task 3A: Establish analytics query and payload budgets

**Files:**

- Create: `twocomms/management/services/ig_stats_cockpit.py`
- Modify: `twocomms/management/bot_views.py`
- Modify: `twocomms/management/tests_ig_stats_visuals.py`

**Step 1: Write failing budget tests**

Use query capture and a representative fixture to measure 1, 7, 30 and all-time ranges. Require the uncached 30-day response to stay at or below 20 SQL queries, 2,000 materialized raw message rows and 350 KiB. Record response time after one warm-up run against a 750 ms local target without making noisy wall time the sole correctness assertion.

**Step 2: Confirm RED**

Run the new tests and record the current all-time regression if it exceeds the target.

**Step 3: Extract bounded domain builders**

Move activity, funnel, attribution, products and economics into a versioned cockpit service. Keep one API response but avoid a monolithic view. Add a cache key for identical scope/basis requests. If the all-time message row budget is exceeded, add a daily role rollup/read model and a bounded distinct-conversation query before exposing the long range by default.

**Step 4: Run budgets and regression tests**

Expected: query count and materialization stay within documented limits, or the QA document records the rollup activation as a prerequisite.

**Step 5: Commit**

```bash
git add twocomms/management/services/ig_stats_cockpit.py \
  twocomms/management/bot_views.py twocomms/management/tests_ig_stats_visuals.py
git commit -m "refactor(management): isolate statistics cockpit builders"
```

### Task 3B: Normalize detail cohorts and revenue completeness

**Files:**

- Modify: `twocomms/management/services/ig_funnel_analytics.py`
- Modify: `twocomms/management/services/ig_stats_cockpit.py`
- Modify: `twocomms/management/bot_views.py`
- Modify: `twocomms/management/tests_ig_funnel_analytics.py`
- Modify: `twocomms/management/tests_ig_stats_visuals.py`

**Step 1: Write failing semantic tests**

Require response ownership to partition episodes into mutually exclusive `bot_only`, `shared` and `manager_only`, with their sum equal to `episodes_with_response_evidence`. Keep episodes without response evidence outside the denominator.

Create discount offers and stage transitions on both sides of the selected date boundary. Require discount analysis to start from offer events in-range and observe purchases through one declared cutoff. Require stage duration to start from entries in-range, observe a later transition through the same cutoff and report completed versus right-censored samples.

Create two verified payments, one priced and one without a trustworthy amount. Require:

```python
self.assertEqual(revenue["verified_payment_count"], 2)
self.assertEqual(revenue["priced_payment_count"], 1)
self.assertEqual(revenue["unpriced_payment_count"], 1)
self.assertEqual(revenue["known_net_revenue"], "1090.00")
self.assertEqual(revenue["amount_coverage_percent"], 50)
```

**Step 2: Confirm RED**

Run the new test cases. Expected: overlapping ownership, out-of-window discount misclassification, censored durations omitted and missing payment amount collapsed into an incomplete total.

**Step 3: Implement the versioned detail contracts**

Derive all ownership sets from one response-evidence population. Return discount `offered`, `bought_after_offer`, `still_open` and the independent `bought_without_known_offer` baseline with cutoff metadata. Return duration median/P90 only for completed pairs plus `right_censored_count`. Return revenue completeness alongside every amount.

**Step 4: Run funnel, commerce and statistics regression tests**

Expected: PASS, including cross-boundary and paid-without-amount cases.

**Step 5: Commit**

```bash
git add twocomms/management/services/ig_funnel_analytics.py \
  twocomms/management/services/ig_stats_cockpit.py \
  twocomms/management/bot_views.py \
  twocomms/management/tests_ig_funnel_analytics.py \
  twocomms/management/tests_ig_stats_visuals.py
git commit -m "fix(management): align detail analytics cohorts"
```

### Task 4: Stage 1 release gate

**Files:**

- Create: `docs/qa/2026-08-08-management-stats-decision-cockpit-stage1.md`

**Step 1: Run backend regression suites**

```bash
DEBUG=1 SECRET_KEY=codex-local-test-only python manage.py test \
  management.tests_ig_stats_visuals \
  management.tests_ig_funnel_analytics \
  management.tests_ig_commerce_state \
  --settings=test_settings
git diff --check
```

**Step 2: Record schema evidence and compatibility**

Document schema version, old keys retained, new module contracts and exact test counts.

**Step 3: Commit and push the stage**

```bash
git add docs/qa/2026-08-08-management-stats-decision-cockpit-stage1.md
git commit -m "docs(management): record stats contract verification"
git push -u origin codex/management-stats-decision-cockpit
```

**Step 4: Integrate and deploy exact main SHA**

Fetch current `origin/main`, verify the stage can fast-forward or rebase cleanly in an isolated integration worktree, push `main`, then run:

```bash
./deploy.sh --target-sha <40-character-main-sha>
```

**Step 5: Production smoke**

Verify deployed SHA, `bot/health/`, authenticated `bot/api/stats/?days=1`, schema version 3 and absence of 5xx errors. Do not claim stage completion from deploy stdout alone.

## Stage 2: Core Cockpit And Linked Diagnostics

### Task 5: Replace primary KPI hierarchy

**Files:**

- Modify: `twocomms/management/templates/management/bot.html:40-440`
- Modify: `twocomms/management/templates/management/bot.html:2826-3408`
- Modify: `twocomms/management/tests_ig_clients_ui.py`
- Modify: `twocomms/management/tests_ig_stats_visuals.py`

**Step 1: Write failing template contract tests**

Require stable hooks for:

```text
data-stats-decision-rail
data-stats-primary="conversations"
data-stats-primary="messages"
data-stats-primary="paylinks"
data-stats-primary="paid"
data-stats-primary="revenue"
data-stats-basis
data-stats-quality
```

Assert the old primary message count is not duplicated as a competing KPI. Require `data-stats-basis`, `data-stats-time-field` and `data-stats-completeness` on each slot. Qualified must be a secondary current-snapshot module, not a homogeneous primary KPI.

**Step 2: Confirm RED**

Run the new template test. Expected: FAIL on missing hooks.

**Step 3: Implement the decision rail**

Refactor `renderKpis` to produce five fixed slots grouped by Activity, Funnel event and Payment time, plus one derived diagnostic chip. Keep every label short. The quality/basis button opens source details; it does not add another paragraph. For payment amounts, show known net revenue and amount coverage instead of zero when paid rows are unpriced.

**Step 4: Run template and inline-JS syntax tests**

```bash
DEBUG=1 SECRET_KEY=codex-local-test-only python manage.py test \
  management.tests_ig_clients_ui.ClientWorkspaceTemplateContractTests \
  management.tests_ig_clients_ui.ClientsPageRenderTests.test_bot_page_inline_scripts_have_valid_javascript_syntax \
  management.tests_ig_stats_visuals.StatsDashboardTemplateContractTests \
  --settings=test_settings
```

**Step 5: Commit**

```bash
git add twocomms/management/templates/management/bot.html \
  twocomms/management/tests_ig_clients_ui.py \
  twocomms/management/tests_ig_stats_visuals.py
git commit -m "feat(management): add statistics decision rail"
```

### Task 6: Build the adaptive activity visual

**Files:**

- Modify: `twocomms/management/templates/management/bot.html`
- Modify: `twocomms/management/tests_ig_stats_visuals.py`

**Step 1: Write failing rendering contracts**

Require:

- one-day pulse with hourly sparkline;
- zero day without a false full-height column;
- 2-7 day stacked columns;
- daily/weekly/monthly density classes;
- clamped tooltip placement hooks;
- touch-locked tooltip state;
- full date/value in `aria-label`.

**Step 2: Confirm RED**

Run the template contract tests.

**Step 3: Implement `renderActivity` modes**

Keep DOM/CSS rendering. Do not add a chart dependency. Compute dimensions from API metadata, not viewport font scaling. The one-day module must stay within 120 px before header/legend.

**Step 4: Add JavaScript state tests/contracts**

Assert tooltip open/close, Escape handling and pointer/touch parity. Interpolate from previous values only for a refresh of the same period, basis and view; use a crossfade for scope changes.

**Step 5: Run focused tests and commit**

```bash
git add twocomms/management/templates/management/bot.html twocomms/management/tests_ig_stats_visuals.py
git commit -m "feat(management): adapt activity visual to date density"
```

### Task 7: Convert the funnel to continued/lost/in-progress rails

**Files:**

- Modify: `twocomms/management/templates/management/bot.html`
- Modify: `twocomms/management/tests_ig_stats_visuals.py`

**Step 1: Write failing funnel visual tests**

Require each non-empty stage to expose:

```text
data-funnel-entered
data-funnel-advanced
data-funnel-lost
data-funnel-progress
data-funnel-denominator="entered"
```

Assert the conversion badge is absent for low sample and that the largest loss receives one bottleneck marker.

**Step 2: Confirm RED**

Run the new tests.

**Step 3: Implement a linked selection state**

Create one `selection` object owned by the statistics module:

```javascript
const selection = { kind: '', id: '', basis: '' };
```

Stage selection updates the loss/duration/detail modules without changing period. An explicit details button or Enter opens the drawer. Escape closes the drawer before clearing selection; outside click closes the drawer but never clears selection. Selection persists across refresh only when `{kind, id, basis}` remains in the new payload.

**Step 4: Implement desktop and mobile funnel layouts**

Desktop/tablet uses two rows of five stages with explicit flow between rows. At 560 px and below use a vertical timeline with readable labels and stable widths. Render an integrity warning and no conversion percentage when the API says the entered cohort did not reconcile.

**Step 5: Run tests and commit**

```bash
git add twocomms/management/templates/management/bot.html twocomms/management/tests_ig_stats_visuals.py
git commit -m "feat(management): link funnel loss diagnostics"
```

### Task 8: Replace detailed tables with visual modules and drawer

**Files:**

- Modify: `twocomms/management/templates/management/bot.html`
- Modify: `twocomms/management/tests_ig_clients_ui.py`
- Modify: `twocomms/management/tests_ig_stats_visuals.py`

**Step 1: Write failing contracts for the seven replacements**

Require hooks for:

- ranked recoverable/irreversible loss bars;
- median/P90 interval plot;
- bot/manager split;
- discount bridge;
- current-stage distribution;
- objection-client ranked bars;
- contextual details drawer/mobile sheet.
- `data-detail-drawer`, `data-detail-drawer-title`, `data-detail-drawer-close`, `aria-describedby` and focus-return hooks.

Assert `renderDetails` and the default `bot-stats-table` detail output no longer exist.

**Step 2: Confirm RED**

Run focused template tests.

**Step 3: Implement pure render helpers**

Create small functions with one analytical purpose each. Do not create a generic card abstraction that hides semantics. Each helper reads module metadata for unit/basis.

**Step 4: Implement drawer behavior**

Drawer requirements:

- focus moves to the heading on open;
- Escape and close icon return focus to the trigger;
- outside click closes only on desktop;
- mobile sheet is capped at `min(86dvh, 720px)`, has internal scroll, safe-area padding, body scroll lock, focus trap and an explicit close control;
- exact values and source appear only in the drawer;
- stale selection is cleared safely after refresh.

**Step 5: Run UI contracts and commit**

```bash
git add twocomms/management/templates/management/bot.html \
  twocomms/management/tests_ig_clients_ui.py \
  twocomms/management/tests_ig_stats_visuals.py
git commit -m "feat(management): replace stats detail tables with visuals"
```

### Task 9: Stage 2 browser QA and release

**Files:**

- Create: `docs/qa/2026-08-08-management-stats-decision-cockpit-stage2.md`

**Step 1: Start the local server with representative fixtures**

Use test/dev data only. Cover one-day non-zero, one-day zero, seven-day, thirty-day, custom sparse, all-time and API failure states.

**Step 2: Playwright visual checks**

Capture 1440, 1280, 768, 390 and 320 px screenshots. Verify:

- no page overflow;
- no overlap;
- one-day chart remains compact;
- tooltip stays within viewport;
- vertical mobile funnel remains readable;
- drawer/sheet focus and dismissal work;
- default view contains no full detail table.

**Step 3: Run pixel/geometry assertions**

Check `scrollWidth <= clientWidth`, chart nonblank pixels, stable KPI dimensions and drawer viewport bounds.

**Step 4: Run the frontend-design evaluator loop**

Use the design brief at `/tmp/management-stats-decision-cockpit-vLP00pgy/brief.md`. Address every priority issue, rerun screenshots and stop only on PASS or the documented third-round limit.

**Step 5: Commit, push, integrate and deploy**

Record screenshots, viewport sizes, test commands and evaluator verdict. Push feature branch, integrate current `origin/main`, deploy exact main SHA and verify the authenticated live page.

## Stage 3: Advertising Spend, Efficiency And Products

### Task 10: Persist immutable advertising entry facts

**Files:**

- Modify: `twocomms/management/ig_bot_models.py`
- Create: `twocomms/management/migrations/0147_ig_ad_conversation_fact.py`
- Create: `twocomms/management/services/ig_ad_attribution.py`
- Modify: `twocomms/management/services/ig_webhook.py`
- Modify: `twocomms/management/tests_ig_stats_visuals.py`
- Create: `twocomms/management/tests_ig_ad_attribution.py`

**Step 1: Write failing fact and capture tests**

Define `IgAdConversationFact` as the append-only acquisition fact for the first eligible visible inbound/referral event. Require a stable source-event identity, client, entry message/event, occurred-at, reporting timezone, normalized account/campaign/ad-set/ad/creative IDs, raw referral identity, payload hash and `exact` or `backfilled` provenance. An optional commercial-episode link may be assigned exactly once by a deterministic service and never rebound. Duplicate webhook delivery must create one fact.

**Step 2: Confirm RED**

Run the new test file. Expected: model/service missing.

**Step 3: Implement capture and one-time episode binding**

Capture exact facts on the normal webhook transaction without changing message delivery. Preserve legacy `IgClient` campaign fields only as a separately labeled current snapshot. Do not reconstruct historical exact facts from mutable state; any controlled backfill is marked `backfilled` and excluded from causal ROAS by default.

**Step 4: Add cohort join tests**

Prove an exact entry fact can join one commercial episode, verified payment and product item; prove an unbound, partial or backfilled fact remains a period signal and cannot produce acquisition conversion/ROAS.

**Step 5: Run webhook, attribution and commerce regressions and commit**

```bash
git add twocomms/management/ig_bot_models.py \
  twocomms/management/migrations/0147_ig_ad_conversation_fact.py \
  twocomms/management/services/ig_ad_attribution.py \
  twocomms/management/services/ig_webhook.py \
  twocomms/management/tests_ig_ad_attribution.py \
  twocomms/management/tests_ig_stats_visuals.py
git commit -m "feat(management): persist advertising entry facts"
```

### Task 11: Add the audited advertising spend ledger

**Files:**

- Modify: `twocomms/management/ig_bot_models.py`
- Create: `twocomms/management/migrations/0148_ig_ad_spend_daily.py`
- Create: `twocomms/management/services/ig_ad_spend.py`
- Modify: `twocomms/management/bot_views.py`
- Modify: `twocomms/management/urls.py`
- Modify: `twocomms/management/tests_ig_stats_visuals.py`

**Step 1: Write failing model/service tests**

Specify `IgAdSpendDaily` with:

```python
class Source(models.TextChoices):
    META_API = "meta_api", "Meta API"
    MANUAL = "manual", "Manual"
```

Required fields: source, normalized account/campaign/ad-set/ad IDs, entity level and entity ID, report date, reporting timezone, currency, spend, nullable Meta result count, exact result `action_type`, attribution window, placement scope, external row ID, payload hash, revision, superseded-row reference, entered/imported by and timestamps.

Require database uniqueness for source/account/entity-level/entity/report-date/currency/attribution-window/action-type/revision. Corrections append an audited revision and supersede the prior active row. Require idempotent external-row import. Manual input accepts daily rows only and rejects an unallocated range total.

**Step 2: Confirm RED**

Run the new test class. Expected: import/model failure.

**Step 3: Implement model, migration and aggregation service**

Aggregate only active revisions. Preserve measured zero, but return the following when no aligned row exists:

```python
{
    "available": False,
    "status": "missing_source",
    "currency": "UAH",
    "spend": None,
    "coverage": {"date_from": "", "date_to": "", "days": 0},
}
```

when no aligned rows exist. Never return numeric zero for missing source.

**Step 4: Add staff-only manual upsert endpoint**

Use POST, CSRF, staff authorization, exact date, normalized entity identity, Decimal validation, non-negative spend, reporting timezone, explicit currency, attribution window, action type and audit user. Require an expected revision and return 409 on stale editing. Never silently prorate a range total.

**Step 5: Run migration/model/API tests and commit**

```bash
git add twocomms/management/ig_bot_models.py \
  twocomms/management/migrations/0148_ig_ad_spend_daily.py \
  twocomms/management/services/ig_ad_spend.py \
  twocomms/management/bot_views.py \
  twocomms/management/urls.py \
  twocomms/management/tests_ig_stats_visuals.py
git commit -m "feat(management): persist audited advertising spend"
```

### Task 12: Add a Meta Ads Insights adapter without assuming access

**Files:**

- Create: `twocomms/management/services/ig_meta_ads_insights.py`
- Create: `twocomms/management/management/commands/sync_ig_meta_ad_spend.py`
- Create: `twocomms/management/tests_ig_meta_ad_spend.py`
- Modify: `twocomms/twocomms/settings.py`
- Modify: `twocomms/twocomms/production_settings.py`

**Step 1: Write no-network adapter tests**

Mock Graph responses and require:

- account and date parameters;
- daily increment;
- account/campaign/ad-set/ad IDs and entity level preserved;
- pagination;
- reporting timezone, currency, result action type, attribution window and placement scope captured;
- stable external row identity;
- retryable versus permanent error classification;
- no import when required settings or scope evidence is absent.

**Step 2: Confirm RED**

Run the new test file. Expected: module missing.

**Step 3: Implement the adapter seam**

Use explicit settings for ad account and spend token source. Do not reuse the Instagram messaging token merely because it exists. A preflight request must prove account access; otherwise the command exits without changing spend rows.

**Step 4: Implement idempotent daily sync command**

Support `--date-from`, `--date-to` and `--dry-run`. Default automatic scheduling is out of scope until production credentials and frequency are approved.

**Step 5: Run tests and commit**

```bash
git add twocomms/management/services/ig_meta_ads_insights.py \
  twocomms/management/management/commands/sync_ig_meta_ad_spend.py \
  twocomms/management/tests_ig_meta_ad_spend.py \
  twocomms/twocomms/settings.py twocomms/twocomms/production_settings.py
git commit -m "feat(management): add Meta ad spend import adapter"
```

### Task 13: Add truthful advertising economics to the stats API

**Files:**

- Modify: `twocomms/management/bot_views.py`
- Modify: `twocomms/management/tests_ig_stats_visuals.py`

**Step 1: Write failing calculation tests**

Test missing, measured-zero, partial-date, currency-mismatch, timezone-mismatch, attribution-window-mismatch and complete spend coverage. Test verified payments with fully known, partially known and entirely unknown amounts. For complete compatible operational-period coverage assert:

```python
self.assertEqual(economics["spend"], "1000.00")
self.assertEqual(economics["known_net_revenue"], "2500.00")
self.assertEqual(economics["amount_coverage_percent"], 100)
self.assertEqual(economics["result_after_ads"], "1500.00")
self.assertEqual(economics["operational_period_roas"], "2.50")
self.assertEqual(economics["cost_per_conversation"], "100.00")
self.assertEqual(economics["cost_per_verified_payment"], "500.00")
self.assertNotIn("profit", economics)
```

**Step 2: Confirm RED**

Run the new tests.

**Step 3: Implement Decimal-only calculations**

Calculate ratios only when spend coverage, reporting timezone, currency, identity level, action type and attribution window match the named basis. Set an explicit unavailable status for every mismatch. `result_after_ads` uses known net revenue and is unavailable when amount coverage is incomplete.

**Step 4: Add campaign-level economics only for stable identities**

Legacy/current-snapshot campaign rows expose independent period signals without causal connectors or stage conversion. They may expose clearly warned operational-period ROAS only when the compatible period join is complete. Acquisition-cohort conversion/ROAS is returned separately only for exact immutable entry facts bound to episodes and payments under a declared cutoff/maturity contract. Unmatched spend stays in an explicit unallocated bucket.

**Step 5: Run tests and commit**

```bash
git add twocomms/management/bot_views.py twocomms/management/tests_ig_stats_visuals.py
git commit -m "feat(management): calculate advertising efficiency honestly"
```

### Task 14: Redesign advertising and product views

**Files:**

- Modify: `twocomms/management/templates/management/bot.html`
- Modify: `twocomms/management/tests_ig_clients_ui.py`
- Modify: `twocomms/management/tests_ig_stats_visuals.py`

**Step 1: Write failing visual contracts**

Require:

- spend state button;
- unavailable/partial/ready economics states;
- attribution ring with absolute counts;
- campaign period signal strips with no causal arrows or stage conversion;
- acquisition cohort rail only for exact immutable facts with common cutoff;
- unallocated spend row;
- verified revenue and result-after-ads labels;
- no `profit` label;
- product image, interest rail, paid rail and selected-stage context.

**Step 2: Confirm RED**

Run focused template tests.

**Step 3: Implement advertising economics panel**

The manual spend form opens in the existing drawer/sheet. It displays exact date coverage and source. Successful save refreshes the dashboard without page reload and animates only changed values.

**Step 4: Implement campaign and product linked visuals**

Keep eight campaign rows visible and disclose the rest. A signal strip and a true cohort rail have visibly different labels and shapes. Product rows use independent scales and a visible unknown bucket. Product conversion remains absent until immutable interest/payment facts share a cohort. No broken external image placeholder.

**Step 5: Run tests and commit**

```bash
git add twocomms/management/templates/management/bot.html \
  twocomms/management/tests_ig_clients_ui.py \
  twocomms/management/tests_ig_stats_visuals.py
git commit -m "feat(management): connect advertising spend and product outcomes"
```

### Task 15: Stage 3 production data-source verification

**Files:**

- Create: `docs/qa/2026-08-08-management-stats-decision-cockpit-stage3.md`

**Step 1: Verify migrations and no-network tests**

Verify migrations 0147/0148 and no-network tests, the full stats tests and Meta adapter mocks.

**Step 2: Verify production authority before import**

On production, read-only check the configured ad account, token type/scopes and currency. If proof is absent, leave Meta sync disabled and verify the UI says source unavailable. Do not infer permission from the messaging integration.

**Step 3: Verify manual source safely**

Use an administrator-confirmed real spend row only if authorized. Otherwise validate the endpoint with local fixtures and do not mutate production.

**Step 4: Commit, push, integrate and deploy**

Deploy the exact `main` SHA using `./deploy.sh --target-sha ...` and verify migration, health, API economics status and live UI.

## Stage 4: Global Refinement And Acceptance

### Task 16: Motion, responsive and failure-state polish

**Files:**

- Modify: `twocomms/management/templates/management/bot.html`
- Modify: `twocomms/management/tests_ig_clients_ui.py`

**Step 1: Write failing contracts**

Require stable hooks/classes for previous-to-new value transitions, selected state, stale snapshot, retry, reduced motion, drawer bounds and 320 px vertical funnel.

**Step 2: Confirm RED and implement**

Use the durations from the design document. Remove any transition that delays interaction or creates layout shift.

**Step 3: Run JS syntax and contract tests**

Expected: PASS.

**Step 4: Commit**

```bash
git add twocomms/management/templates/management/bot.html twocomms/management/tests_ig_clients_ui.py
git commit -m "fix(management): refine statistics responsive motion"
```

### Task 17: Full browser and semantic acceptance matrix

**Files:**

- Create: `docs/qa/2026-08-08-management-stats-decision-cockpit-final.md`

**Step 1: Run the complete focused backend/frontend suite**

```bash
DEBUG=1 SECRET_KEY=codex-local-test-only python manage.py test \
  management.tests_ig_stats_visuals \
  management.tests_ig_clients_ui \
  management.tests_ig_funnel_analytics \
  management.tests_ig_meta_ad_spend \
  --settings=test_settings
git diff --check
```

**Step 2: Browser state matrix**

For overview, ads and products, test:

- one-day zero/non-zero;
- seven-day sparse/dense;
- thirty-day;
- custom one day;
- custom multi-day;
- all time;
- partial attribution;
- no attribution;
- spend missing/partial/ready;
- payment with and without reliable amount;
- API refresh failure with stale snapshot.

**Step 3: Viewport matrix**

Capture and inspect 1440x900, 1280x800, 1024x768, 768x1024, 390x844 and 320x568. Assert the first-viewport and mobile DOM/overflow geometry from the design, plus tooltip, drawer, focus, touch and reduced-motion behavior.

**Step 4: Independent design evaluation**

Run up to three evaluator rounds. Treat 320 px readability, information priority, whitespace, clipping and visual semantics as blocking.

**Step 5: Record exact evidence**

Document test counts, screenshots, evaluator verdict, remaining limitations and every metric source state.

### Task 18: Final review, main integration and production verification

**Files:**

- Modify: `docs/qa/2026-08-08-management-stats-decision-cockpit-final.md`

**Step 1: Request code and design review**

Use `superpowers:requesting-code-review`. Review API correctness, denominator integrity, spend idempotency, responsive behavior and regression risk.

**Step 2: Resolve all blocking findings**

For each fix: write/adjust a failing regression test, implement, rerun focused tests and update QA evidence.

**Step 3: Verify branch state**

```bash
git status --short
git log --oneline origin/main..HEAD
git diff --check origin/main...HEAD
```

Expected: only intended files, clean worktree, all commits present.

**Step 4: Push and integrate current main**

Push feature branch, integrate onto the latest `origin/main` in a clean integration worktree, rerun the acceptance suite and push `main`.

**Step 5: Deploy exact SHA**

```bash
./deploy.sh --target-sha <40-character-main-sha>
```

**Step 6: Production proof**

Verify:

- server and `origin/main` SHA equality;
- migrations 0147 and 0148 applied;
- bot health and Passenger response;
- stats API schema and period metadata;
- message series reconciliation;
- funnel denominator metadata;
- attribution quality state;
- spend state truthfulness;
- authenticated browser rendering at desktop and mobile;
- no new relevant server errors;
- Instagram bot daemon/heartbeat still healthy.

**Step 7: Mark complete only after proof**

Update the final QA document with deployed SHA and live evidence. Do not mark complete if spend authority, live rendering or server SHA remains unverified.

---

## Explicitly Deferred

- Profit after full cost of goods and fulfillment, until cost coverage is proven.
- Automatic sound alerts, until a user preference and anomaly contract exist.
- Drag-and-drop dashboard customization.
- Synthetic trends or extrapolated advertising performance.
- Automatic production Meta spend scheduling before credentials, scopes, account and rate-limit behavior are verified.
- Historical reconstruction of campaign identity without durable evidence.
