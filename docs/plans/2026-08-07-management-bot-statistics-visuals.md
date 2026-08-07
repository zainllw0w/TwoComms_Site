# Management Bot Statistics Visuals Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the overloaded Instagram bot statistics table stack with a truthful, compact dashboard that communicates message volume, active conversations, verified payments, losses and funnel bottlenecks at a glance.

**Architecture:** Extend `bot_stats_api` additively, preserving every existing response field. New metadata and totals are derived from persisted messages, current client state, verified payment projections and canonical funnel facts. The frontend uses semantic HTML and CSS rails/bars in the existing Django template; no chart library, synthetic trends or client-invented data. A shared motion language makes state changes feel continuous and polished instead of abruptly replacing content; decorative polish is welcome when it reinforces hierarchy, focus or spatial continuity.

**Tech Stack:** Django 5, Django ORM, existing `management` models/services, vanilla JavaScript, semantic HTML/CSS, Django TestCase, responsive browser QA.

---

### Task 1: Truthful API metadata and message totals

**Files:**
- Create: `twocomms/management/tests_ig_stats_visuals.py`
- Modify: `twocomms/management/bot_views.py:5131`

**Step 1: Write failing API tests**

Add tests that create visible and hidden clients plus persisted `InstagramBotMessage` rows. Assert:

- `schema_version == 2` and `generated_at` is timezone-aware.
- `period` contains mode, label, timezone, local/UTC boundaries and an exclusive upper bound.
- `totals.messages`, `inbound_messages`, `bot_replies`, `manager_messages` match persisted rows in the selected period.
- `totals.unique_conversations` counts distinct visible clients/senders, never raw joined rows.
- Existing keys such as `conversations`, `qualified`, `paid`, `stages`, `funnel`, `products` and `ads` remain present.

**Step 2: Run RED**

Run:

```bash
python manage.py test management.tests_ig_stats_visuals.StatsApiVisualContractTests --settings=test_settings
```

Expected: FAIL because the new metadata and message totals do not exist.

**Step 3: Implement minimal additive contract**

In `bot_stats_api`:

- Build one visible message queryset using `created_at >= since` and `< until`.
- Count roles with filtered aggregates; do not count hidden-client rows.
- Add `schema_version`, `generated_at`, `period`, and the new totals without deleting or renaming current keys.
- Keep the currently verified `paid_in_range` calculation unchanged.

**Step 4: Run GREEN**

Run the Task 1 test class and confirm all assertions pass.

### Task 2: Honest qualification, loss and sparse datasets

**Files:**
- Modify: `twocomms/management/tests_ig_stats_visuals.py`
- Modify: `twocomms/management/bot_views.py:5131`

**Step 1: Write failing truth tests**

Assert:

- `qualified` keeps the existing explicit definition `buying_readiness >= 40` among visible period conversations.
- `lost_or_refused` counts distinct visible clients with an unrecovered durable `EXPLICIT_REFUSAL` or `SILENCE` funnel fact in the selected period.
- `OPT_OUT`, spam, technical unreachability and legacy stage/reason labels remain separate operational meanings and are not silently mixed into the primary loss KPI.
- Stage-only paid and historical archive-only clients are not counted as verified paid.
- Empty ranges return zeros and empty arrays, never fake percentages or deltas.
- A Kyiv custom date range uses local midnight and an exclusive next-day upper boundary.

**Step 2: Run RED**

Run the new individual tests and confirm failures are caused by missing `lost_or_refused` and metadata semantics.

**Step 3: Implement minimal query changes**

Use persisted `IgFunnelDropOff` rows for loss/refusal and filter by visible client, selected event-time range, unrecovered state and canonical kind. Use `distinct()` by client. Do not infer refusal from language, mutable stage labels, sentiment, opt-out state or missing data.

**Step 4: Run GREEN**

Run `management.tests_ig_stats_visuals`, `management.tests_ig_sales_automation`, and `management.tests_ig_funnel_analytics`.

### Task 3: RED visual contracts

**Files:**
- Modify: `twocomms/management/tests_ig_stats_visuals.py`
- Modify: `twocomms/management/templates/management/bot.html`

**Step 1: Add failing template assertions**

Require:

- Four primary KPI slots with stable semantic classes.
- Server freshness text from `generated_at`.
- A proportional funnel rail with visible count and percentage labels.
- Ranked horizontal bars for categories, products and ads.
- A `Детальні дані` disclosure for existing cohort/drop-off/time-on-step/manager/discount tables.
- Stable first-load skeleton, stale-data error banner and retry control.
- Interactive definition popovers that support click/tap, focus and Escape.
- Responsive 4/2/1-column KPI geometry and no fixed minimum width.
- A coherent animation contract: entrance, value change, bar resize, disclosure, tooltip, hover/tap and important-change emphasis.

**Step 2: Run RED**

Run the template contract tests and confirm they fail because the current UI still renders 11 equal boxes and a long table sequence.

### Task 4: GREEN dashboard composition

**Files:**
- Modify: `twocomms/management/templates/management/bot.html:60-90`
- Modify: `twocomms/management/templates/management/bot.html:867-891`
- Modify: `twocomms/management/templates/management/bot.html:2300-2410`

**Step 1: Implement the visual hierarchy**

- Header: literal title, server freshness, icon refresh button.
- Period selector: compact preset segmented control; custom dates inside a disclosure on narrow screens.
- View selector: `Огляд`, `Реклама`, `Товари`; switch locally from one successful payload with a short directional transition and preserve period/error state.
- KPI row: Messages, Conversations, Verified payments, Losses/refusals.
- Activity chart: real persisted message buckets split by inbound, bot and manager roles; no smoothing or synthetic series.
- Secondary metrics: compact disclosure strip, not eleven permanent cards.
- Main grid: proportional funnel and category bars.
- Optional grid: product performance rows with real thumbnails and separate interest/verified-paid rails, plus linked ad conversation/payment performance; omit a section when its dataset is empty.
- Advertising view: attributed conversations, real ad-only event funnel, paylinks issued, verified payments/revenue, campaign ranking, advertised products and canonical drop-off reasons.
- Detailed data: keep the existing cohort and operational tables inside one disclosure.

**Step 2: Implement interaction and motion states**

- Use a consistent `180-280 ms` motion scale with a calm ease-out curve.
- On first successful load, reveal KPI and chart groups with a restrained short stagger, opacity and 4-6 px translation.
- Animate KPI value replacement with a short vertical crossfade; do not block reading with a long count-up.
- Animate proportional/ranked bar widths from their previous real value to the new real value.
- Animate stacked activity columns from their previous real bucket heights and expose exact bucket values by hover/focus/tap.
- Fade real product images into stable thumbnail frames and keep a no-shift fallback for missing/broken media.
- Give important verified-payment or loss changes one brief semantic emphasis, then return to the stable state.
- Expand disclosures through a smooth grid/opacity transition instead of an abrupt content jump.
- Fade/scale help popovers from the invoking control and return focus cleanly on close.
- Add precise hover, focus-visible, press, refresh-running and retry feedback so controls never feel inert.
- Preserve the last successful dashboard during refresh/network failure.
- Show first-load skeletons with stable dimensions.
- Definition popovers work on hover/focus/tap and close on Escape with focus returned.
- All bars retain labels, exact values and percentages; zero values render an empty rail.
- Product interest and verified-paid item quantities remain explicitly separate; do not invent a conversion rate from different cohorts.
- Highlight the largest real stage-to-stage funnel drop as the current bottleneck; never present it as a forecast.
- `prefers-reduced-motion` removes translation/stagger and keeps instant-but-clear state feedback.

**Step 3: Run GREEN**

Run the new stats tests, existing sales/funnel/client UI tests, JavaScript syntax extraction, `manage.py check`, migration drift and `git diff --check`.

### Task 5: Browser and design evaluation

**Files:**
- Browser QA: `twocomms/output/playwright/management-stats-*.png`
- Update: `docs/plans/2026-08-05-management-bot-visual-selection-final.md`

**Step 1: Seed sparse and populated local fixtures**

Exercise zero, the production-like sparse shape (6 conversations, no ads, no paid) and a populated ranked-data fixture.

**Step 2: Verify viewports**

- 1440 px: four KPI columns, two-column chart grid.
- 768 px: two KPI columns, single-column charts.
- 375 and 320 px: one column, no horizontal overflow or clipped labels.
- Keyboard/touch: help popovers, details disclosure, custom range and retry.
- Motion: entrance, value update, bar resize, disclosure and tooltip transitions are smooth and do not cause layout jumps.
- Reduced motion: translation and stagger are removed while state remains understandable.

**Step 3: Run mandatory external design evaluation**

Use the frontend-design evaluator. Address every priority issue and repeat up to three attempts.

**Step 4: Update the master checklist**

Mark only evidence-backed Release 2 items complete. Also close the already deployed Release 1.5 delivery item with its verified SHA.

### Task 6: Release

**Files:**
- Commit only the plan, stats tests, `bot_views.py`, `bot.html`, and master checklist.

**Step 1: Verify before commit**

Run focused/adjacent tests, Django checks, migration drift, JavaScript parse, browser matrix and `git diff --check`.

**Step 2: Commit and push feature branch**

Commit with a scoped message and push `codex/management-bot-statistics-visuals`.

**Step 3: Integrate and deploy**

Safely integrate into current local `main`, push `origin/main`, deploy through the established management-bot sequence, then verify server SHA, migrations, `manage.py check`, static compression, daemon heartbeat and a read-only live stats response shape.

### Release evidence addendum (2026-08-07)

- Advertising attribution remains explicitly labeled as `current_client_snapshot`; the API does not invent historical attribution that is not persisted.
- `verified_paid` and per-campaign `paid` count distinct confirmed `IgDeal` rows, so repeat purchases by one attributed client are visible as separate purchases while revenue remains a separate money field.
- Campaigns keep the first eight rows visible and expose the remaining API rows through a closed `Ще N кампаній` disclosure.
- Mobile activity labels use a compact day/month representation at `<=390px`; the full bucket and exact role totals remain in the button `aria-label`, `title`, and tap tooltip.
- Activity columns support hover/focus plus a tap-pinned tooltip (`aria-expanded`), with clean close on repeat tap, outside click, or `Escape` and focus restoration.
- Browser evidence: `management-stats-final-1440.png`, `management-stats-final-768.png`, `management-stats-final-375.png`, `management-stats-final-320.png`; no document overflow at all four viewports and the active main tab is centered on 375/320px.
- Focused/adjacent gate after the addendum: `242` tests passed across `management.tests_ig_stats_visuals`, `management.tests_ig_funnel_analytics`, `management.tests_ig_sales_automation`, and `management.tests_ig_clients_ui`; inline JavaScript syntax test, `manage.py check`, migration drift and `git diff --check` passed.
