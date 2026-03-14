# TwoComms Management Canonical Implementation Master File

> **For Claude/Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this file phase-by-phase. Use the repo-local `codex_skills/coding-agent/SKILL.md` only if you intentionally delegate isolated substeps to external agent CLIs.

**Goal:** Implement the 2026-03-13 canonical management analytics package as a safe evolution of the existing `management` app, preserving the current management, shop, CP email, payout, contract, reminder and Telegram workflows while adding shadow-first MOSAIC analytics, versioned snapshots, dedupe hardening, payroll-safe appealable logic, and later telephony readiness.

**Architecture:** Keep `twocomms/management/` as the single runtime surface. Extend existing models and workflows where reality already exists, add only the minimum new structural models required for readiness, snapshots, run logging, day-ledger and appeals, move new analytics into dedicated service modules, and keep legacy KPD live until shadow MOSAIC is validated.

**Tech Stack:** Python 3.13, Django 5.2.11, current `management` app, existing `orders` and `storefront` integrations, existing Telegram bot flows, Redis-backed cache in production but no new feature may require Redis/Celery to function, Django management commands + cron as the baseline execution model, SSH deploy on the hosted server.

---

## 1. How To Use This File

This is the execution-facing document for the future implementation agent. It replaces the need to reconstruct the system from older folders.

Use this file in this order:

1. Read sections `1-4.10` to load authority, code reality, explicit decisions, incident rules, stale-source barriers and the workstream source map.
2. Read section `5` before touching migrations or creating new modules.
3. Execute phases in section `9` strictly in order.
4. Use section `10` as the minimum verification contract before every phase close-out.
5. Use section `11` for deploy, rollback and post-deploy smoke verification.

Canonical refs:
- `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/00_INDEX_AND_AUTHORITY_MANIFEST.md:12-44`
- `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/01_EXECUTIVE_CANONICAL_SYNTHESIS.md:5-20`
- `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/13_IMPLEMENTATION_BLUEPRINT_AND_DEPENDENCY_ORDER.md:7-19`
- `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/14_AGENT_HANDOFF_BRIEF_FOR_IMPLEMENTATION_FILE.md:23-86`

## 2. Non-Negotiable Invariants

These rules are already decided. The implementation agent must not reopen them unless code reality proves them impossible.

1. `management` is evolved, not replaced. Do not build a new CRM app in parallel.
2. Verified money truth remains dominant. Shadow analytics never silently become payroll-final truth.
3. KPD stays live during transition. MOSAIC starts in `SHADOW`.
4. `VerifiedCommunication` stays `DORMANT` until telephony maturity exists in code and data.
5. Existing CP email, shop, payout, contract, parser and Telegram flows are extended, not re-invented.
6. Low-confidence or stale analytics must render as low-confidence or stale, never as precise truth.
7. Leave, sickness, force majeure, import burst, shared phone and telephony outage are explicit data states, not prose-only excuses.
8. The implementation must remain compatible with shared-hosting deployment and cron-based execution even if Redis/Celery are configured in settings.

Canonical refs:
- `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/00_INDEX_AND_AUTHORITY_MANIFEST.md:36-43`
- `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/01_EXECUTIVE_CANONICAL_SYNTHESIS.md:12-20`
- `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/02_SYSTEM_ARCHITECTURE_AND_INVARIANTS.md:90-130`
- `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/16_DECISION_LOG_REJECTED_IDEAS_AND_BACKLOG.md:35-54`

Current code refs:
- `twocomms/management/models.py:23-184`
- `twocomms/management/models.py:479-1159`
- `twocomms/management/stats_service.py:564-1171`
- `twocomms/management/views.py:179-224`
- `twocomms/management/views.py:657-860`
- `twocomms/management/management/commands/notify_test_shops.py:38-94`
- `twocomms/twocomms/settings.py:592-698`

## 3. Current Production Reality Map

The future agent must anchor every change to the current codebase.

### 3.1 Core domain models already exist

| Area | Existing anchors | What they already do | Implementation rule |
|---|---|---|---|
| Clients and leads | `twocomms/management/models.py:23-184` | `Client`, `ManagementLead`, parser job/results, `phone_normalized`, `points_override` | extend carefully; do not recreate lead/client core |
| CP email | `twocomms/management/models.py:352-613` | `CommercialOfferEmailSettings`, `CommercialOfferEmailLog` with mode/segment/pricing/send status | reuse as process and communication evidence |
| Shops | `twocomms/management/models.py:616-833` | `Shop`, phones, shipments, communications, inventory movement, test-to-full life cycle | portfolio logic must integrate this subsystem, not bypass it |
| Activity and follow-ups | `twocomms/management/models.py:835-956` | `ManagementDailyActivity`, `ClientFollowUp`, advice dismissal, config singleton | legacy KPD already depends on this; extend instead of replace |
| Payroll and payout | `twocomms/management/models.py:959-1071` | commission accruals, `frozen_until`, payout requests and rejection flows | payroll changes must layer on top of these tables |
| Contracts | `twocomms/management/models.py:1074-1159` | contract numbering, review, rejection request flow | preserve Telegram review patterns |

### 3.2 Core services and view flows already exist

| Area | Existing anchors | What they already do | Implementation rule |
|---|---|---|---|
| Legacy KPD and stats payload | `twocomms/management/stats_service.py:130-251`, `564-1171` | config defaults, KPD computation, source normalization, advice, shop/follow-up/invoice stats, cache | keep callable; extract new logic into new service modules |
| Stats views | `twocomms/management/stats_views.py:25-222` | manager stats page, admin stats list, admin manager stats page, activity pulse, advice dismissal | primary extension target for score UI |
| Management home and follow-up sync | `twocomms/management/views.py:179-224`, `463-638` | creates/updates clients, synchronizes follow-ups, renders manager home | dedupe hardening must hook here without rewriting the page |
| Reminders and daily counters | `twocomms/management/views.py:254-350`, `353-367` | in-page reminder feed, report reminder, daily points/processed stats | reminder ladder must reuse existing reminder/read models |
| Admin panel | `twocomms/management/views.py:657-860` | manager overview plus payout/invoice/admin aggregates | extend with health/readiness/economics widgets rather than parallel admin UI |
| Lead and parsing flows | `twocomms/management/lead_views.py:77-143`, `twocomms/management/parsing_views.py:127-311` | lead create/process, parser dashboard, moderation actions | dedupe/create-or-append logic must hook here |
| Shop flows | `twocomms/management/shop_views.py:277-937` | shop CRUD, next-contact, inventory, shipment download | portfolio ownership must prefer `managed_by` over `created_by` |
| Telegram command pattern | `twocomms/management/management/commands/notify_test_shops.py:38-94` | command + ReminderSent idempotency + Telegram send pattern | reuse for reminder/digest/incident alerts |

### 3.3 Current templates and assets already define the shell

| Area | Existing anchors | Current reality | Implementation rule |
|---|---|---|---|
| Base shell | `twocomms/management/templates/management/base.html:36-236` | navigation, reminders, profile modal, management shell data attrs | preserve shell; only extend nav/state surgically |
| Manager home | `twocomms/management/templates/management/home.html:11-369` | action table, lead base, client/lead/process modals | keep operational home focused on work, not analytics overload |
| Stats page | `twocomms/management/templates/management/stats.html:9-527` | legacy KPD spiral, advice, follow-up gauge, CP blocks, JSON payload injection | primary manager analytics extension target |
| Stats JS/CSS | `twocomms/twocomms_django_theme/static/js/management-stats.js:1-260`, `twocomms/twocomms_django_theme/static/css/management-stats.css:1-788` | direct-static asset loading, no bundler assumption for management UI | add plain static JS/CSS files; do not assume Vite/Webpack/Tailwind build |
| Admin panel template | `twocomms/management/templates/management/admin.html:1-260` | managers/invoices/payouts/shops tabs already live | extend in place; do not invent a separate admin app |

### 3.4 Current constants and environment facts

| Area | Existing anchors | Current reality | Implementation rule |
|---|---|---|---|
| Legacy points and daily targets | `twocomms/management/constants.py:1-23` | `POINTS`, `LEAD_ADD_POINTS`, `LEAD_BASE_PROCESSING_PENALTY`, `TARGET_CLIENTS_DAY`, `TARGET_POINTS_DAY`, `REMINDER_WINDOW_MINUTES` | preserve legacy KPD parity during transition |
| Cache and execution environment | `twocomms/twocomms/settings.py:592-698` | Redis-backed cache in prod, LocMem in debug, Celery settings present | new functionality must not require Redis/Celery to succeed; DB + cron remains the safe baseline |
| Timezone and host | `twocomms/twocomms/settings.py:92-93`, `507-511` | `management.twocomms.shop`, `Europe/Kiev`, `USE_TZ=True` | all day-ledger, reminders and snapshots must use local-day semantics |

### 3.5 Hidden cross-app couplings the future agent must respect

The `management` app is not isolated. Several flows depend on lazy imports and external models. The implementation agent must not accidentally break these edges while refactoring analytics.

| External app / surface | Existing anchors | Why it matters | Safe rule |
|---|---|---|---|
| `accounts.UserProfile` | `twocomms/management/views.py:49` | manager profile, Telegram binding and profile data already depend on it | do not duplicate profile state inside `management` |
| `orders.WholesaleInvoice` | `twocomms/management/views.py:726`, `1063-1102`, `2553`, `3714-4011`, `5313`; `twocomms/management/stats_service.py:779`, `1238`; `twocomms/management/shop_views.py:18` | invoices, accruals, admin payout context, shop shipment docs and stats use wholesale invoice truth | analytics must read invoice truth, not invent a parallel revenue source |
| `storefront.Product` / `Category` | `twocomms/management/views.py:1039`, `2780`, `3252`, `3403`, `4749`; `twocomms/management/shop_views.py:406` | CP email, contracts, invoices and shop flows already depend on storefront catalog entities | avoid import-cycle-heavy service placement; keep lazy import pattern where current code already uses it |
| `storefront.views.monobank` helpers | `twocomms/management/views.py:4011-4012` | payment creation flow has external dependency already | do not entangle score/payroll services with payment transport helpers |
| `twocomms_django_theme` static assets | `twocomms/twocomms_django_theme/static/js/management-stats.js:1-260`, `twocomms/twocomms_django_theme/static/css/management-stats.css:1-788` | management analytics UI is not isolated in a separate frontend package | new UI assets should follow current static loading conventions |

## 4. Explicit Decisions Resolved In This File

These items were left unresolved in the canonical package. This document resolves them so the future agent does not stall.

### 4.1 `xml_connected` points drift

Decision:
- keep `POINTS["xml_connected"] = 15` for legacy KPD and all current daily counters in Phase 0-5;
- do not retroactively rewrite historical KPD semantics;
- treat the drift as a calibration backlog item for shadow analytics validation, not as a migration blocker.

Reason:
- current runtime truth is `twocomms/management/constants.py:1-16`;
- MOSAIC/EWR should not depend on the legacy points table for verified-result truth anyway;
- changing it now would create needless KPD divergence during the shadow period.

### 4.2 `Client.is_test`

Decision:
- do not add `Client.is_test`;
- `Shop.shop_type` remains the only persisted test/full truth;
- if client-level helper logic is needed, derive it in service code via shop relations or explicit tagged flows, not via a duplicated boolean on `Client`.

Reason:
- `Shop` already owns test/full lifecycle and test-specific fields at `twocomms/management/models.py:616-669`;
- duplicating that truth on `Client` invites drift and bad joins.

### 4.3 Appeal storage shape

Decision:
- create a standalone `ScoreAppeal` model in Phase 5 for score-sensitive disputes;
- keep payout disputes inside the existing payout workflow and reason models;
- connect payout and score disputes in the UI through a shared evidence drawer/service layer, not by collapsing them into one table.

Reason:
- score appeals need snapshot/version fields and confidence context;
- existing payout rejection flow already has its own operational semantics at `twocomms/management/models.py:996-1071`.

### 4.4 Snapshot granularity

Decision:
- store one canonical daily snapshot per manager per local day as the durable source of heavy analytics;
- daily snapshots hold typed summary fields plus a compact JSON payload;
- week/month/custom-range shadow views aggregate daily snapshots instead of storing separate weekly/monthly snapshot tables in Phase 1-5.

Reason:
- current UI periods are day/week/month/range, but daily snapshots are enough to aggregate them;
- this keeps idempotency, storage growth and rollback simpler.

### 4.5 Phone normalization scope

Decision:
- keep the existing UA-first `normalize_phone()` behavior as the authoritative auto-block basis;
- add secondary review-only helpers for last-7 and broader permissive matching;
- do not introduce international auto-merge semantics until real data proves the need.

Reason:
- current runtime scope is explicit at `twocomms/management/models.py:8-20`;
- safe review suggestions are allowed, aggressive international auto-block is not.

### 4.6 Redis/Celery dependency level

Decision:
- treat Redis/Celery as optional infrastructure that may exist, not as a required runtime dependency for the new analytics contour;
- every new command and state transition must remain correct with plain DB + cache + cron.

Reason:
- canonical contract explicitly rejects hard Redis/Celery dependency;
- production hosting/deploy model remains Git + SSH + cron.

Canonical refs:
- `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/16_DECISION_LOG_REJECTED_IDEAS_AND_BACKLOG.md:46-54`
- `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/03A_CANONICAL_DEFAULTS_REGISTRY.md:13-28`
- `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/09_CODE_REALITY_MODEL_SERVICE_ENDPOINT_MAP.md:115-123`

### 4.7 Workstream Authority Map

Use this table when a future implementation step needs both the canonical idea source and the current code landing point immediately.

| Workstream | Canonical source refs | Current code anchors | Implementation note |
|---|---|---|---|
| Score, MOSAIC, EWR, confidence | `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/03_SCORE_MOSAIC_EWR_CONFIDENCE.md:12-259` | `twocomms/management/stats_service.py:130-251`, `twocomms/management/stats_service.py:564-1171`, `twocomms/management/constants.py:1-23` | keep legacy KPD callable; new score logic lands in `services/score.py`, `services/trust.py`, `services/churn.py`, `services/snapshots.py` |
| Payroll, KPI, portfolio, earned day | `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/04_PAYROLL_KPI_PORTFOLIO_EARNED_DAY.md:11-247` | `twocomms/management/models.py:959-1071`, `twocomms/management/views.py:5302-5852`, `twocomms/management/views.py:657-860` | preserve verified revenue truth and payout flow; add ledger-aware interpretation around it |
| Identity, dedupe, follow-up, anti-abuse | `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/05_IDENTITY_DEDUPE_FOLLOWUP_ANTI_ABUSE.md:7-219` | `twocomms/management/models.py:8-184`, `twocomms/management/models.py:867-915`, `twocomms/management/views.py:179-224`, `twocomms/management/views.py:254-350`, `twocomms/management/lead_views.py:77-143`, `twocomms/management/parsing_views.py:311-354`, `twocomms/management/shop_views.py:433-809` | implement create-or-append and review-first dedupe without rewriting home, leads or parser flows |
| Telephony, QA, supervisor, verified communication | `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/06_TELEPHONY_QA_SUPERVISOR_VERIFIED_COMMUNICATION.md:7-169` | `twocomms/management/stats_service.py:553-561`, `twocomms/twocomms/settings.py:592-698` | existing code has only weak call-result semantics; all telephony truth is later-phase and readiness-gated |
| Manager/admin UX and explainability | `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/07_MANAGER_ADMIN_UX_EXPLAINABILITY.md:11-208` | `twocomms/management/templates/management/stats.html:9-527`, `twocomms/management/templates/management/admin.html:1-260`, `twocomms/management/templates/management/base.html:36-236`, `twocomms/twocomms_django_theme/static/js/management-stats.js:1-260`, `twocomms/twocomms_django_theme/static/css/management-stats.css:1-788` | extend the current shell; do not replace management UI architecture |
| Admin economics and forecast | `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/08_ADMIN_ECONOMICS_FORECAST_DECISION_SAFETY.md:7-132` | `twocomms/management/views.py:657-860`, `twocomms/management/templates/management/admin.html:1-260`, `twocomms/management/models.py:959-1071` | admin-only initially; never let forecast blocks masquerade as payroll-final truth |
| Governance, snapshots, jobs, rollout | `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/10_GOVERNANCE_DATA_MODEL_JOBS_ROLLOUT.md:7-146`, `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/13_IMPLEMENTATION_BLUEPRINT_AND_DEPENDENCY_ORDER.md:7-167` | `twocomms/management/management/commands/notify_test_shops.py:38-94`, `twocomms/twocomms/settings.py:592-698`, `twocomms/management/stats_views.py:25-222` | use command-run logging, readiness rows, daily snapshots, and staged rollout; do not hide stale states |
| Edge cases and failure semantics | `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/11_EDGE_CASES_FAILURE_MODES_AND_SCENARIOS.md:7-78` | `twocomms/management/views.py:254-350`, `twocomms/management/views.py:2246-2284`, `twocomms/management/stats_service.py:260-532` | make failure states explicit in DB/UI instead of burying them in advice text |
| Tests, golden cases, activation metrics | `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/12_TEST_STRATEGY_VALIDATION_ACCEPTANCE.md:7-140`, `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/15_TRACEABILITY_MATRIX_AND_SOURCE_COVERAGE.md:14-66` | `twocomms/management/tests.py` and future `twocomms/management/tests/` package | migrate tests into package first, then grow coverage by workstream and phase gate |

### 4.8 Incident persistence and health-source decision

Decision:
- do not create a standalone `OperationalIncident` model in Phase 1-5 unless real implementation pressure proves the derived approach unreadable;
- instead derive active incidents deterministically from `CommandRunLog`, snapshot freshness, duplicate queue age, reminder backlog and later `TelephonyHealthSnapshot`;
- expose those incidents through admin health payloads using stable incident keys.

Required incident keys:
- `SNAPSHOT_STALE`
- `CACHE_PRESSURE`
- `TELEPHONY_OUTAGE`
- `REMINDER_STORM`
- `DUPLICATE_QUEUE_BACKLOG`
- `PAYOUT_REVIEW_BLOCK`

Reason:
- the canonical docs require incidents to be visible and behavior-driving, but they do not force a separate table;
- derived incidents keep the foundation lean while still satisfying admin visibility and downstream safety routing;
- if later implementation shows the derived approach is too opaque, Phase 6+ may introduce a dedicated persistence model with a forward migration.

### 4.9 Migration numbering rule

Decision:
- treat migration numbers in this file as ordered placeholders relative to the current migration head, not as immutable literals;
- preserve the sequence and dependency intent, but always inspect the real graph before generating files;
- as of this audit the current local head is `0019_client_phone_normalized_client_points_override_and_more.py`.

Reason:
- another agent may execute this plan after unrelated migrations land;
- the implementation file must describe order, not encourage broken hard-coded numbering assumptions.

### 4.10 Stale-source precedence barrier

Decision:
- treat helper/audit files as review inputs, not as authority, unless this file explicitly adopts a detail from them;
- if `reports/i1/*`, old synthesis folders, or `CODEX_FIX_GUIDE.md` conflict with the canonical package, the canonical package wins;
- if the canonical package itself contains both thematic contracts and this execution master file, thematic contracts define the business rule and this file defines the implementation-facing decision.

When conflicts appear, these anchors win immediately:

| Topic | Authoritative winner |
|---|---|
| MOSAIC weights | `Result 0.40`, `SourceFairness 0.10`, `Process 0.20`, `FollowUp 0.10`, `DataQuality 0.10`, `VerifiedCommunication 0.10` from `03` and `03A` |
| Production EWR | `outcome + effort + revenue_progress` formula from `03`, not older helper variants using `source_quality` wording |
| `score_confidence` reading bands | `HIGH >= 0.80`, `MEDIUM 0.50-0.79`, `LOW < 0.50` from `03` |
| Onboarding constants | `14` full-protection days, `14` decay days, `40` floor from `03A` |
| Manager benchmark suppression | no manager-facing peer benchmark below `N < 5` from `07` and `03A` |

Rule:
- do not lift numeric examples from helper or audit docs into code if they contradict the formulas and defaults above;
- use helper/audit docs to discover missing nuance, then resolve it here or in the thematic canonical files before implementation.

## 5. Final Target File-System Map

The implementation must keep the current app shape recognizable while decomposing the new logic into stable places.

### 5.1 Python modules

Modify in place:
- `twocomms/management/models.py`
- `twocomms/management/admin.py`
- `twocomms/management/urls.py`
- `twocomms/management/stats_service.py`
- `twocomms/management/stats_views.py`
- `twocomms/management/views.py`
- `twocomms/management/lead_views.py`
- `twocomms/management/parsing_views.py`
- `twocomms/management/shop_views.py`
- `twocomms/management/constants.py`

Create new service package:
- `twocomms/management/services/__init__.py`
- `twocomms/management/services/config_versions.py`
- `twocomms/management/services/score.py`
- `twocomms/management/services/trust.py`
- `twocomms/management/services/churn.py`
- `twocomms/management/services/snapshots.py`
- `twocomms/management/services/dedupe.py`
- `twocomms/management/services/followups.py`
- `twocomms/management/services/payroll.py`
- `twocomms/management/services/forecast.py`
- `twocomms/management/services/advice.py`
- `twocomms/management/services/appeals.py`
- `twocomms/management/services/telephony.py`

Create dedicated view modules instead of growing `views.py` further:
- `twocomms/management/appeal_views.py`
- `twocomms/management/admin_analytics_views.py`
- later `twocomms/management/telephony_views.py`

Rule:
- keep old modules as compatibility/orchestration surfaces first;
- do not start with a big move/rename refactor;
- new modules land first, existing callers migrate gradually.

### 5.2 Management commands

Create:
- `twocomms/management/management/commands/seed_management_defaults.py`
- `twocomms/management/management/commands/compute_nightly_scores.py`
- `twocomms/management/management/commands/send_management_reminders.py`
- `twocomms/management/management/commands/check_duplicate_queue.py`
- later `twocomms/management/management/commands/process_telephony_webhooks.py`
- later `twocomms/management/management/commands/reconcile_call_records.py`

Command rules, aligned with Django docs and current code:
- subclass `BaseCommand`;
- use `self.stdout.write()` and style helpers for operator-visible output;
- add explicit idempotency/lock handling in app code, not just in operator discipline;
- write a `CommandRunLog` record for every run;
- never report success if the command finished partially but left stale or corrupted state.

Context7/Django refs:
- custom command patterns from official Django docs (`BaseCommand`, `self.stdout.write`, organization under `app/management/commands`)
- migration workflow via `makemigrations`, `migrate`, `sqlmigrate`
- tests via `TestCase`, `setUpTestData`, `Client`, `reverse`

### 5.3 Templates and static assets

Modify in place:
- `twocomms/management/templates/management/base.html`
- `twocomms/management/templates/management/stats.html`
- `twocomms/management/templates/management/stats_admin_list.html`
- `twocomms/management/templates/management/admin.html`
- `twocomms/management/templates/management/payouts.html`

Create template includes:
- `twocomms/management/templates/management/components/score_hero.html`
- `twocomms/management/templates/management/components/radar_chart.html`
- `twocomms/management/templates/management/components/why_changed_today.html`
- `twocomms/management/templates/management/components/action_stack.html`
- `twocomms/management/templates/management/components/rescue_top5.html`
- `twocomms/management/templates/management/components/salary_simulator.html`
- `twocomms/management/templates/management/components/client_timeline.html`
- `twocomms/management/templates/management/components/freshness_badges.html`
- `twocomms/management/templates/management/components/admin_health_widget.html`
- `twocomms/management/templates/management/components/admin_queue_presets.html`
- `twocomms/management/templates/management/components/admin_economics_summary.html`
- `twocomms/management/templates/management/components/appeal_drawer.html`

Create static assets:
- `twocomms/twocomms_django_theme/static/css/management-mosaic.css`
- `twocomms/twocomms_django_theme/static/css/management-admin-analytics.css`
- `twocomms/twocomms_django_theme/static/js/management-mosaic.js`
- `twocomms/twocomms_django_theme/static/js/management-admin-analytics.js`

Rule:
- keep asset loading template-driven;
- do not introduce a bundler-only frontend architecture for management pages;
- reuse `json_script` payload injection on stats surfaces.

### 5.4 Test layout

Important:
- do not keep both `twocomms/management/tests.py` and a new `twocomms/management/tests/` package for long;
- migrate existing tests out of `tests.py` first, then remove or rename `tests.py`, otherwise Python import/discovery becomes ambiguous.

Target test package:
- `twocomms/management/tests/__init__.py`
- `twocomms/management/tests/test_legacy_kpd.py`
- `twocomms/management/tests/test_foundation_models.py`
- `twocomms/management/tests/test_dedupe.py`
- `twocomms/management/tests/test_followups.py`
- `twocomms/management/tests/test_ewr.py`
- `twocomms/management/tests/test_mosaic.py`
- `twocomms/management/tests/test_trust.py`
- `twocomms/management/tests/test_churn_weibull.py`
- `twocomms/management/tests/test_score_confidence.py`
- `twocomms/management/tests/test_snapshot_schema.py`
- `twocomms/management/tests/test_snapshot_idempotency.py`
- `twocomms/management/tests/test_payload_versioning.py`
- `twocomms/management/tests/test_soft_floor.py`
- `twocomms/management/tests/test_commission.py`
- `twocomms/management/tests/test_rescue_spiff.py`
- `twocomms/management/tests/test_day_status.py`
- `twocomms/management/tests/test_reintegration.py`
- `twocomms/management/tests/test_appeals.py`
- `twocomms/management/tests/test_admin_analytics.py`
- `twocomms/management/tests/test_telephony.py`

## 6. Target Data Model Plan

### 6.1 Extend `ManagementStatsConfig` instead of bypassing it

Modify `twocomms/management/models.py` and add fields to `ManagementStatsConfig`:
- `legacy_kpd_formula_version`
- `shadow_mosaic_formula_version`
- `defaults_version`
- `payload_version`
- `mosaic_config` JSONField
- `payroll_config` JSONField
- `forecast_config` JSONField
- `telephony_config` JSONField
- `ui_config` JSONField
- `validation_state` JSONField

Do not remove:
- `kpd_weights`
- `advice_thresholds`

Implementation rule:
- keep old fields working for current KPD/advice;
- seed new JSON config fields from canonical defaults;
- never read runtime constants from markdown docs after Phase 1 is coded.

### 6.2 Create `ComponentReadiness`

Purpose:
- DB-backed source of truth for `ACTIVE` / `SHADOW` / `DORMANT` / `ADMIN_ONLY` component state.

Recommended fields:
- `component_key` unique
- `state`
- `effective_from`
- `effective_to`
- `notes`
- `changed_by`
- `meta`
- `updated_at`

Seed initial rows:
- `shadow_mosaic = SHADOW`
- `verified_communication = DORMANT`
- `telephony_health = ADMIN_ONLY`
- `qa_reviews = ADMIN_ONLY`
- `admin_economics = ADMIN_ONLY`

### 6.3 Create `NightlyScoreSnapshot`

Purpose:
- version-bearing daily analytics source of truth.

Recommended fields:
- `manager`
- `snapshot_date`
- `formula_version`
- `defaults_version`
- `snapshot_schema_version`
- `payload_version`
- `readiness_state`
- `job_run` FK to `CommandRunLog`
- `legacy_kpd_value`
- `shadow_mosaic_value`
- `ewr_value`
- `score_confidence`
- `verified_coverage`
- `sample_sufficiency`
- `stability`
- `recency`
- `working_day_factor`
- `capacity_factor`
- `trust_factor`
- `gate_level`
- `gate_value`
- `dampener_value`
- `portfolio_health_state`
- `freshness_seconds`
- `payload` JSONField
- timestamps

Unique constraint:
- `(manager, snapshot_date, formula_version, defaults_version)`

Rule:
- keep typed summary columns for filtering/sorting;
- keep detailed breakdown in `payload`;
- avoid storing massive raw event dumps here.

### 6.4 Create `CommandRunLog`

Purpose:
- command observability, idempotency trace and admin health source.

Recommended fields:
- `command_name`
- `run_id` UUID
- `status`
- `started_at`
- `finished_at`
- `lock_key`
- `rows_processed`
- `warnings_count`
- `error_excerpt`
- `scope_date_from`
- `scope_date_to`
- `formula_version`
- `defaults_version`
- `meta`

### 6.5 Create `ManagerDayStatus`

Purpose:
- explicit working-day ledger for capacity-aware KPI, DMT and reintegration.

Recommended fields:
- `manager`
- `date`
- `status` enum (`WORKING`, `WEEKEND`, `HOLIDAY`, `VACATION`, `SICK`, `EXCUSED`, `TECH_FAILURE`, `FORCE_MAJEURE`)
- `capacity_factor`
- `source_reason`
- `subtype`
- `reintegration_flag`
- `approved_by`
- `approved_at`
- `meta`

Unique constraint:
- `(manager, date)`

### 6.6 Extend identity models conservatively

Extend `Client` and `ManagementLead` with:
- `phone_last7`
- `normalized_name_key`
- `normalized_name_display`
- `is_shared_phone`
- `phone_group_key`
- `shared_phone_reason`

Rules:
- populate in `save()` or service-layer normalizer;
- keep `phone_normalized` as-is for current parity;
- do not add `Client.is_test`.

For `Shop`:
- do not add persisted duplicate helper fields in the first pass unless performance measurements prove the need;
- compute normalized shop keys in service code initially.

### 6.7 Extend `ClientFollowUp` carefully

Use the existing model and existing `meta` JSON as the primary extension surface.

Only add indexed columns that are operationally necessary:
- `grace_until`
- `last_notified_at`
- `escalation_level`

Keep in `meta`:
- import burst labels
- digest bucketing state
- overload redistribution notes
- source tags like `client.next_call_at`, `parser_import`, `bulk_import`

### 6.8 Create `DuplicateReviewCase`

Purpose:
- conservative review queue for ambiguous identity collisions.

Recommended fields:
- `left_entity_type`
- `left_entity_id`
- `right_entity_type`
- `right_entity_id`
- `score`
- `zone`
- `status`
- `evidence`
- `created_by`
- `reviewed_by`
- `resolution`
- `resolved_at`

Rule:
- no auto-merge on fuzzy name alone;
- `AUTO_BLOCK` reserved for strong exact identity only.

### 6.9 Create `OwnershipChangeLog`

Purpose:
- explicit audit trail for ownership-sensitive movements.

Recommended fields:
- `entity_type`
- `entity_id`
- `from_user`
- `to_user`
- `reason`
- `changed_by`
- `created_at`
- `review_case` FK optional
- `meta`

### 6.10 Phase-5 payroll additions

Extend `ManagerCommissionAccrual` with:
- `accrual_type` (`new`, `repeat`, `reactivation`, `rescue_spiff`, `manual`)
- `source_snapshot` FK nullable
- `freeze_reason_code`
- `freeze_reason_text`
- `working_factor_applied`
- `evidence_payload`

Create `ScoreAppeal` with:
- `manager`
- `snapshot`
- `appeal_type`
- `status`
- `opened_at`
- `due_at`
- `resolved_at`
- `reason_code`
- `manager_note`
- `resolution_note`
- `resolved_by`
- `evidence_payload`

### 6.11 Later telephony models

Create only in Phase 6+:
- `CallRecord`
- `TelephonyWebhookLog`
- `TelephonyHealthSnapshot`
- `CallQAReview`
- `SupervisorActionLog`

Do not ship them earlier than the non-telephony phases unless you need the migrations ready for an inactive feature flag.

## 7. Service and API Contracts

### 7.1 Authoritative math anchors

These are copied inline because they are already canonical elsewhere and the implementation agent should not need to jump between files for core math or key ambiguity barriers.

Authoritative MOSAIC weights:

| Axis | Weight |
|---|---:|
| `Result` | `0.40` |
| `SourceFairness` | `0.10` |
| `Process` | `0.20` |
| `FollowUp` | `0.10` |
| `DataQuality` | `0.10` |
| `VerifiedCommunication` | `0.10` |

Authoritative production `EWR`:

```python
def compute_ewr(
    orders: int,
    contacts_processed: int,
    revenue: float,
    *,
    conversion_baseline: float = 0.0248,
    target_weekly_revenue: float = 50_000,
    target_contacts: int = 80,
) -> float:
    expected_orders = contacts_processed * conversion_baseline

    if expected_orders >= 1:
        outcome = min(2.0, orders / expected_orders)
    elif orders > 0:
        outcome = 2.0
    else:
        outcome = 0.5

    normalized_outcome = min(1.0, outcome / 2.0)
    effort = min(1.0, contacts_processed / max(1, target_contacts))
    revenue_progress = min(1.0, revenue / max(1, target_weekly_revenue))

    return round(min(1.0, 0.40 * normalized_outcome + 0.35 * effort + 0.25 * revenue_progress), 4)
```

Authoritative `score_confidence`:

```python
def compute_score_confidence(
    verified_coverage: float,
    sample_sufficiency: float,
    stability: float,
    recency: float,
) -> float:
    score = (
        0.35 * verified_coverage
        + 0.25 * sample_sufficiency
        + 0.20 * stability
        + 0.20 * recency
    )
    return round(max(0.0, min(1.0, score)), 4)
```

Adopted onboarding-floor interpretation for execution:

```python
def compute_onboarding_floor_score(tenure_days: int) -> float:
    if tenure_days <= 14:
        return 40.0
    if tenure_days >= 28:
        return 0.0
    return round(40.0 * (1.0 - ((tenure_days - 14) / 14.0)), 2)
```

Adopted working-factor and Phase-0 DMT defaults for execution:

```python
def compute_working_factor(capacity_factors: list[float], nominal_workdays: int = 5) -> float:
    usable = sum(max(0.0, min(1.0, x)) for x in capacity_factors)
    return round(usable / max(1, nominal_workdays), 4)


def effective_phase0_dmt(capacity_factor: float) -> tuple[int, int]:
    effective_dmt_contacts = max(1, math.ceil(5 * capacity_factor))
    effective_dmt_updates = 1 if capacity_factor >= 0.5 else 0
    return effective_dmt_contacts, effective_dmt_updates
```

Shadow/admin-only rule:
- `EWR-v2`, `Wilson`, `churn_confidence` and similar report-derived helpers may be implemented only as explicitly versioned shadow/admin-only diagnostics;
- do not let a helper or audit document silently override the production anchors above.

### 7.2 Service split

Implement these as pure or near-pure services wherever possible:

| Service | Responsibility | Notes |
|---|---|---|
| `config_versions.py` | load runtime config and version registry from `ManagementStatsConfig` | single code authority, no doc parsing |
| `score.py` | `compute_ewr`, `compute_mosaic`, axis composition, gate/dampener pipeline | pure functions + typed outputs |
| `trust.py` | production and diagnostic trust calculations | production trust only touches evidence-sensitive slice |
| `churn.py` | `Weibull`, logistic fallback, planned-gap neutrality | pure math + portfolio helpers |
| `snapshots.py` | build daily snapshot payloads, aggregate range views, stale semantics | central source for shadow analytics |
| `dedupe.py` | normalization, candidate prefilter, score zones, review case creation | no blind writes inside fuzzy search |
| `followups.py` | ladder, overload redistribution, grace windows, digest bucketing | reuses `ReminderSent` / `ReminderRead` |
| `payroll.py` | working-factor KPI, repeat/reactivation/rescue accruals, soft floor | must preserve verified money truth |
| `forecast.py` | bands, cohort retention, concentration, aging penalty, rescue ROI | admin-only |
| `advice.py` | merge legacy advice with MOSAIC-aware cards | reuse dismissal keys and TTL semantics |
| `appeals.py` | submit, SLA, resolve, recalc hooks | connects payouts and score evidence drawers |
| `telephony.py` | provider adapters, reconciliation, health aggregation, QA helpers | later-phase only |

### 7.3 Do not let `stats_service.py` continue to grow

Implementation rule:
- keep `compute_kpd()` in `twocomms/management/stats_service.py:182-251` intact for legacy parity;
- keep `get_stats_payload()` alive as the current public entry point at first;
- gradually turn `get_stats_payload()` into a thin orchestrator that calls new snapshot/advice helpers instead of hosting all new logic inline.

### 7.4 New view modules and endpoints

Do not add new appeals/economics/readiness endpoints to the already large `views.py` unless the action is directly coupled to an existing payout/contract flow.

Preferred endpoint landing:

In `twocomms/management/stats_views.py`:
- `stats/mosaic/shadow/` -> shadow payload for compare drawers
- `stats/score/explain/` -> decomposition payload
- `stats/rescue-top/` -> rescue queue payload for dynamic cards

In `twocomms/management/appeal_views.py`:
- `appeals/`
- `appeals/api/submit/`
- `appeals/api/<id>/detail/`
- `appeals/api/<id>/resolve/` (admin-only)

In `twocomms/management/admin_analytics_views.py`:
- `admin-panel/readiness/`
- `admin-panel/readiness/api/toggle/`
- `admin-panel/health/`
- `admin-panel/economics/`
- `admin-panel/freeze/`

In `twocomms/management/telephony_views.py` later:
- provider webhook ingest
- reconciliation review queue
- QA review actions

Minimum response shapes:

For `GET stats/score/explain/`:

```json
{
  "manager_id": 5,
  "period": "2026-W11",
  "formula_version": "1.0",
  "defaults_version": "1.0",
  "readiness_state": "SHADOW",
  "base_mosaic": 0.62,
  "final_mosaic": 0.60,
  "score_confidence": {"value": 0.58, "band": "MEDIUM"},
  "gate": {"level": "CRM-timestamped", "value": 60},
  "axes": {
    "Result": {"value": 0.65, "weight": 0.444, "status": "ACTIVE"},
    "VerifiedCommunication": {"value": null, "weight": 0.0, "status": "DORMANT"}
  },
  "freshness": {"seconds": 3600, "stale": false},
  "top_drivers": ["followup_recovery", "verified_progress"]
}
```

For `POST appeals/api/submit/`:

```json
{
  "id": 42,
  "status": "pending",
  "appeal_type": "score",
  "sla_deadline": "2026-03-16T18:00:00Z"
}
```

For `GET admin-panel/economics/`:

```json
{
  "managers": [
    {
      "id": 5,
      "cost_total": 30000,
      "contribution_proxy": 125000,
      "concentration_top3": 0.45,
      "rescue_roi": 3.2
    }
  ],
  "forecast": {
    "optimistic": 280000,
    "base": 210000,
    "pessimistic": 155000,
    "confidence": "MEDIUM",
    "drivers": ["pipeline_aging", "verified_coverage"]
  }
}
```

### 7.5 Snapshot-backed range behavior

Implement this exact reading order for manager/admin stats pages:

1. Legacy KPD and current operational counters remain available live.
2. Shadow MOSAIC and related heavy diagnostics come from aggregated daily snapshots.
3. If one or more daily snapshots are missing for a requested range:
   - render shadow sections as `STALE` or `PARTIAL`;
   - keep legacy live sections visible;
   - never recompute the full heavy shadow pipeline inline just to fake freshness.

### 7.6 Minimum snapshot payload contract

`NightlyScoreSnapshot.payload` must stay compact but deterministic. At minimum it should contain these top-level keys once the relevant phase lands:

- `versions`
  - `formula_version`
  - `defaults_version`
  - `payload_version`
  - `snapshot_schema_version`
- `score`
  - `legacy_kpd`
  - `shadow_mosaic`
  - `ewr`
  - `score_confidence`
  - `gate_level`
  - `gate_value`
  - `dampener_value`
- `confidence`
  - `verified_coverage`
  - `sample_sufficiency`
  - `stability`
  - `recency`
- `axes`
  - `production_volume`
  - `repeat_quality`
  - `pipeline_discipline`
  - `portfolio_health`
  - `source_fairness_assignment`
  - `source_fairness_self_selected`
  - `trust_sensitive_slice`
- `working_context`
  - `day_status`
  - `capacity_factor`
  - `reintegration_flag`
  - `working_day_factor`
- `dmt_earned_day`
  - `minimum_achieved`
  - `target_pace_achieved`
  - `recovery_needed`
  - `meaningful_calls`
  - `meaningful_call_seconds_threshold`
  - `gap_category`
- `portfolio`
  - `portfolio_health_state`
  - `rescue_candidates`
  - `churn_basis`
- `ops`
  - `snapshot_freshness_seconds`
  - `incident_keys`
  - `stale_reason`
- `advice_context`
  - `top_drivers`
  - `top_recovery_actions`
  - `explainability_tokens`

Rules:
- do not dump raw event history into snapshot payloads;
- keep manager-safe and admin-only details separable inside the payload;
- any payload shape change must bump `payload_version` and trigger a validation reset when semantics changed materially.

### 7.7 Health and incident contract

Admin health/readiness widgets must compute their state from deterministic sources, not ad hoc template logic.

Required incident derivation sources:
- `SNAPSHOT_STALE` from latest expected `NightlyScoreSnapshot` freshness window;
- `CACHE_PRESSURE` from repeated cache misses/timeouts or fallback-to-live recomputation behavior if implemented;
- `TELEPHONY_OUTAGE` from `TelephonyHealthSnapshot` once telephony exists;
- `REMINDER_STORM` from reminder volume/backlog thresholds;
- `DUPLICATE_QUEUE_BACKLOG` from aged unresolved `DuplicateReviewCase` queue;
- `PAYOUT_REVIEW_BLOCK` from payout queue age/freeze backlog thresholds.

Required behavior:
- incident keys must be visible in admin;
- any active incident that suppresses punitive interpretation must also suppress it in service code, not only in copy;
- manager-facing pages may show softer wording, but the underlying state must remain exact.

### 7.8 Preserve / Extend / Replace / Retire map

Use this table to avoid vague refactors.

| Current runtime element | Action | Rule |
|---|---|---|
| `compute_kpd()` in `stats_service.py` | `PRESERVE` | keep for transition parity |
| `get_stats_payload()` in `stats_service.py` | `EXTEND -> ORCHESTRATE` | progressively thin it out and move heavy logic to services |
| `generate_advice()` and dismissal flow | `EXTEND` | keep keys/TTL semantics; add MOSAIC-aware cards on top |
| `ManagementStatsConfig` | `EXTEND` | canonical runtime config owner, never bypass with markdown/runtime constants |
| `ManagementDailyActivity` | `PRESERVE` | current activity truth remains input; do not orphan it |
| `ClientFollowUp` | `EXTEND` | ladder/grace/escalation live here, not in a replacement model |
| `Shop` subsystem | `PRESERVE + EXTEND` | portfolio logic must read it directly |
| payout request + accrual flows | `PRESERVE + EXTEND` | evidence/freeze/appeal enrichment only |
| contract and invoice Telegram review flows | `PRESERVE` | do not re-invent approval transport |
| monolithic `views.py` additions | `LIMIT / SPLIT` | new analytics endpoints go to focused modules |
| monolithic template blocks in `stats.html` / `admin.html` | `SPLIT` | use includes, not page rewrites |
| legacy-only assumptions after activation | `RETIRE LATER` | only after shadow validation and explicit readiness switch |

### 7.9 Advice merge rule

Use the existing advice engine as the base layer.

Required behavior:
- keep current advice families for source comparison, follow-up discipline, report discipline and shop health;
- add MOSAIC-aware cards on top of them;
- reuse `ManagementStatsAdviceDismissal` for cooldown and dismiss TTL;
- do not build a second disconnected tip engine.

## 8. Django-Specific Guardrails

These are implementation guardrails derived from official Django docs and repo reality.

### 8.1 Migration discipline

- keep migrations small;
- one structural idea per migration where practical;
- separate schema and data backfill if the change is risky;
- use reversible `RunPython` for backfills where possible;
- inside data migrations use historical models, not direct runtime model imports;
- review generated SQL for risky migrations with `python3 twocomms/manage.py sqlmigrate management <migration_number>`.
- before generating a migration, inspect the real current head (`0019` at the time this file was audited) and adapt numbering accordingly.

### 8.2 Test discipline

- use `django.test.TestCase` and `setUpTestData()` for reusable test data;
- use `reverse()` for URLs;
- use Django `Client` for HTML and JSON endpoint coverage;
- keep pure formula helpers separately unit-testable without HTTP or DB when possible.

### 8.3 Command discipline

- every command must be idempotent or lock-protected;
- every command must record a `CommandRunLog`;
- every command must have a deterministic exit state on partial failure;
- operator-visible output goes through `self.stdout.write`.

### 8.4 Data backfill playbook

Backfills must be explicit and phase-bounded. Do not improvise them inside unrelated commands.

Phase-1 backfills:
- seed `ManagementStatsConfig` version/default fields;
- seed `ComponentReadiness` rows;
- do not create fake historical score snapshots just to populate tables.

Phase-2 backfills:
- backfill `phone_last7` and normalized-name helpers for existing `Client` and `ManagementLead` rows;
- do not backfill a duplicated `Client.is_test` field because that field is explicitly rejected in section `4.2`.

Phase-3 backfills:
- default policy is forward-only snapshot collection from rollout date;
- if historical backfill is later desired, do it through a separate admin command with explicit scope and performance review;
- do not insert placeholder all-null/low-confidence snapshots merely to fill calendar continuity.

Phase-5 backfills:
- backfill `ManagerCommissionAccrual.accrual_type` and freeze metadata only where it is deterministically derivable from verified invoice/payout context;
- if deterministic derivation is impossible, mark the record for manual review rather than guessing.

## 9. Phase-By-Phase Execution Plan

### Phase 0: Contract Freeze and Preflight

**Goal:** start implementation from one fixed contract and one fixed file map.

**Files to read before code:**
- `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/00_INDEX_AND_AUTHORITY_MANIFEST.md`
- `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/18_IMPLEMENTATION_MASTER_FILE.md`
- `twocomms/management/models.py`
- `twocomms/management/stats_service.py`
- `twocomms/management/stats_views.py`
- `twocomms/management/views.py`

**Mandatory preflight tasks:**
1. Confirm the repo state and avoid overwriting unrelated uncommitted work.
2. Confirm the current branch that is intended to be deployed.
3. Record the currently deployed commit or branch before changing runtime code.
4. Create the new `services/` and `tests/` package plan before moving logic.
5. Record the current migration head and current `management/urls.py` surface before introducing new files and routes.
6. Record the cross-app coupling points listed in section `3.5` so later service extraction does not sever them.
7. Freeze the resolved decisions in section `4`; do not silently reopen them while coding.

**Verification commands:**
```bash
git status --short --branch
git branch --show-current
python3 - <<'PY'
import django
print(django.get_version())
PY
```

**Exit condition:** no open ambiguity remains around `xml_connected`, `Client.is_test`, appeal shape, snapshot granularity, phone normalization scope, incident derivation source, or migration sequence intent.

### Phase 1: Foundation, Versions, Readiness, Day Ledger

**Goal:** build the minimum structural base required before any shadow score or payroll-sensitive work.

**Create:**
- `twocomms/management/services/__init__.py`
- `twocomms/management/services/config_versions.py`
- `twocomms/management/services/snapshots.py`
- `twocomms/management/management/commands/seed_management_defaults.py`
- `twocomms/management/tests/`

**Modify:**
- `twocomms/management/models.py`
- `twocomms/management/admin.py`
- `twocomms/management/tests.py`
- `twocomms/management/urls.py` only if a readiness admin page lands early

**Migrations, in order:**
1. `0020_extend_management_stats_config_versions.py`
2. `0021_component_readiness.py`
3. `0022_nightly_score_snapshot.py`
4. `0023_command_run_log.py`
5. `0024_manager_day_status.py`

**Implementation tasks:**
1. Move existing `tests.py` content into the new test package before the package becomes the long-term test entry point.
2. Extend `ManagementStatsConfig` with version-bearing and runtime-config JSON fields.
3. Create `ComponentReadiness`.
4. Create `NightlyScoreSnapshot`.
5. Create `CommandRunLog`.
6. Create `ManagerDayStatus`.
7. Define the derived admin-health incident contract early so the future widget has exact inputs and keys.
8. Register new models in Django admin for inspection and emergency edits.
9. Implement `seed_management_defaults` so the database receives the canonical defaults without runtime markdown parsing.
10. Seed readiness states and config versions as part of the post-migrate or one-shot seed workflow.

**Do not do in Phase 1:**
- do not compute MOSAIC yet;
- do not touch payroll math yet;
- do not add telephony models;
- do not rewrite stats UI yet.

**Verification commands:**
```bash
python3 twocomms/manage.py makemigrations management
python3 twocomms/manage.py migrate
python3 twocomms/manage.py sqlmigrate management 0020
python3 twocomms/manage.py test management.tests.test_foundation_models -v 2
python3 twocomms/manage.py shell -c "from management.models import ManagementStatsConfig, ComponentReadiness, NightlyScoreSnapshot, CommandRunLog, ManagerDayStatus; print(ManagementStatsConfig.objects.count(), ComponentReadiness.objects.count(), NightlyScoreSnapshot.objects.count(), CommandRunLog.objects.count(), ManagerDayStatus.objects.count())"
python3 twocomms/manage.py check
```

**Commit boundary:**
- `feat: add management analytics foundation models`

### Phase 2: Dedupe, Follow-Up Ladder, Reminder Hardening

**Goal:** harden identity, ownership and callback pressure before score consequences exist.

**Create:**
- `twocomms/management/services/dedupe.py`
- `twocomms/management/services/followups.py`
- `twocomms/management/management/commands/send_management_reminders.py`
- `twocomms/management/management/commands/check_duplicate_queue.py`
- `twocomms/management/tests/test_dedupe.py`
- `twocomms/management/tests/test_followups.py`
- `twocomms/management/tests/test_import_burst_grace.py`
- `twocomms/management/tests/test_shared_phone_policy.py`

**Modify:**
- `twocomms/management/models.py`
- `twocomms/management/views.py`
- `twocomms/management/lead_views.py`
- `twocomms/management/parsing_views.py`
- `twocomms/management/shop_views.py` only if ownership/portfolio hooks need adjustment
- `twocomms/management/templates/management/home.html` only for explicit dedupe warnings or review affordances

**Migrations, in order:**
1. `0025_identity_helper_fields.py`
2. `0026_followup_hardening.py`
3. `0027_duplicate_review_and_ownership_log.py`

**Implementation tasks:**
1. Add identity helper fields to `Client` and `ManagementLead`.
2. Build a normalization pipeline that outputs `phone_normalized`, `phone_last7`, `normalized_name_display`, `normalized_name_key`.
3. Create a conservative duplicate candidate scorer with `AUTO_BLOCK`, `REVIEW`, `SUGGESTION`, `CLEAR`.
4. Create `DuplicateReviewCase` and `OwnershipChangeLog`.
5. Hook dedupe checks into:
   - manager home client create/update flow
   - lead create/process flow
   - parser moderation flow
6. Extend `ClientFollowUp` with ladder/digest/grace semantics using existing `meta`.
7. Implement overload handling with `MAX_FOLLOWUPS_PER_DAY = 25`.
8. Build `send_management_reminders` using existing Telegram and `ReminderSent` patterns.
9. Build `check_duplicate_queue` for background review surfacing.
10. Ensure anti-gaming suppression removes score credit only, never the CRM/audit trace.

**Critical rules:**
- imported backlog gets `24-48h` grace and its own label;
- exhausted anti-gaming budgets must remove score credit before deleting operational traces;
- no ownership transfer without explicit log entry.

**Verification commands:**
```bash
python3 twocomms/manage.py test management.tests.test_dedupe management.tests.test_followups management.tests.test_import_burst_grace management.tests.test_shared_phone_policy -v 2
python3 twocomms/manage.py shell -c "from management.models import Client; print(Client.objects.filter(phone_normalized__gt='', phone_last7='').count())"
python3 twocomms/manage.py shell -c "from management.models import DuplicateReviewCase; print(DuplicateReviewCase.objects.count())"
python3 twocomms/manage.py check
```

**Commit boundary:**
- `feat: harden management dedupe and followups`

### Phase 3: Shadow MOSAIC, EWR, Confidence, Daily Snapshots

**Goal:** add the full shadow score engine with zero payroll impact.

**Create:**
- `twocomms/management/services/score.py`
- `twocomms/management/services/trust.py`
- `twocomms/management/services/churn.py`
- `twocomms/management/services/advice.py`
- `twocomms/management/management/commands/compute_nightly_scores.py`
- `twocomms/management/tests/test_ewr.py`
- `twocomms/management/tests/test_mosaic.py`
- `twocomms/management/tests/test_trust.py`
- `twocomms/management/tests/test_churn_weibull.py`
- `twocomms/management/tests/test_score_confidence.py`
- `twocomms/management/tests/test_snapshot_schema.py`
- `twocomms/management/tests/test_snapshot_idempotency.py`
- `twocomms/management/tests/test_payload_versioning.py`

**Modify:**
- `twocomms/management/stats_service.py`
- `twocomms/management/stats_views.py`
- `twocomms/management/models.py` only if snapshot fields need polishing after first iteration

**Implementation tasks:**
1. Implement `compute_ewr()` using the canonical production formula.
2. Implement MOSAIC axis composition with readiness filtering and verified/evidence-sensitive slice split.
3. Implement production trust with narrow clamp and evidence-sensitive-only impact.
4. Implement `compute_score_confidence()`.
5. Implement churn helpers with `Weibull` primary, logistic fallback under `<5` orders, planned-gap neutrality and `k` cap.
6. Implement snapshot builder for one manager + one local day.
7. Implement `compute_nightly_scores`:
   - per-manager daily run
   - idempotent upsert by `(manager, snapshot_date, formula_version, defaults_version)`
   - `CommandRunLog` creation
8. Encode `assignment_fairness` and `self_selected_mix` as separate values with authoritative vs shadow semantics preserved.
9. Update `get_stats_payload()` so legacy KPD remains live while shadow blocks come from snapshots.
10. Extend the advice system by merging legacy cards with MOSAIC-aware cards, not by replacing the current generator wholesale.

**Critical rules:**
- `points_override` stays legacy-only unless there is a separately designed MOSAIC mapping;
- `VerifiedCommunication` remains dormant;
- stale or missing snapshots render stale state, not fake live analytics;
- no payroll switch, no payout impact, no freeze logic from MOSAIC in this phase.

**Verification commands:**
```bash
python3 twocomms/manage.py test management.tests.test_ewr management.tests.test_mosaic management.tests.test_trust management.tests.test_churn_weibull management.tests.test_score_confidence management.tests.test_snapshot_schema management.tests.test_snapshot_idempotency management.tests.test_payload_versioning -v 2
python3 twocomms/manage.py compute_nightly_scores --date=$(date +%F)
python3 twocomms/manage.py shell -c "from management.models import NightlyScoreSnapshot; s=NightlyScoreSnapshot.objects.order_by('-snapshot_date').first(); print(bool(s), getattr(s, 'formula_version', None), getattr(s, 'score_confidence', None))"
python3 twocomms/manage.py check
```

**Commit boundary:**
- `feat: add shadow management scoring and snapshots`

### Phase 4: Manager/Admin Analytics UI and Explainability

**Goal:** render new analytics in a way that is operationally useful, explicit about state, and still safe.

**Create:**
- template components under `twocomms/management/templates/management/components/`
- `twocomms/twocomms_django_theme/static/css/management-mosaic.css`
- `twocomms/twocomms_django_theme/static/css/management-admin-analytics.css`
- `twocomms/twocomms_django_theme/static/js/management-mosaic.js`
- `twocomms/twocomms_django_theme/static/js/management-admin-analytics.js`

**Modify:**
- `twocomms/management/templates/management/stats.html`
- `twocomms/management/templates/management/stats_admin_list.html`
- `twocomms/management/templates/management/admin.html`
- `twocomms/management/templates/management/base.html`
- `twocomms/twocomms_django_theme/static/js/management-stats.js`
- `twocomms/twocomms_django_theme/static/css/management-stats.css`
- `twocomms/management/stats_views.py`
- `twocomms/management/urls.py`

**Implementation tasks:**
1. Split `stats.html` into components without breaking the current page.
2. Add manager score hero with:
   - legacy KPD
   - shadow MOSAIC
   - delta vs previous period
   - freshness state
   - main recovery hint
3. Add `why changed today` and decomposition drawer.
4. Add radar preview with conservative tiny-team handling.
5. Add rescue top-5 block with value-at-risk, urgency, confidence and churn basis.
6. Add salary simulator with current truth vs shadow candidate and freeze items.
7. Add manager action stack: overdue follow-ups, best opportunities, blockers.
8. Extend admin UI with readiness/health/economics widgets, queue presets and confidence-aware aging-penalized forecast surfaces.
9. Add manager/admin no-surprise copy when versioned score semantics changed materially.
10. Add new lightweight JSON endpoints for explanation/radar/rescue if the page needs progressive enhancement.

**Critical rules:**
- every shadow value needs a shadow label;
- stale sections must show stale badges;
- low confidence must show lower visual authority;
- manager-facing peer benchmark must stay suppressed or self-only when team size is tiny.

**Verification commands:**
```bash
python3 twocomms/manage.py test management.tests.test_admin_analytics -v 2
python3 twocomms/manage.py check
```

Manual smoke:
- manager stats page loads
- admin stats list loads
- admin manager stats page loads
- stale and shadow badges render visibly
- no JavaScript error in the browser console on stats page

**Commit boundary:**
- `feat: add management analytics ui surfaces`

### Phase 5: Payroll-Safe Logic, Day Ledger Usage, Appeals

**Goal:** connect analytics to money-adjacent interpretation safely without letting shadow logic become payroll truth.

**Create:**
- `twocomms/management/services/payroll.py`
- `twocomms/management/services/appeals.py`
- `twocomms/management/appeal_views.py`
- `twocomms/management/tests/test_soft_floor.py`
- `twocomms/management/tests/test_commission.py`
- `twocomms/management/tests/test_rescue_spiff.py`
- `twocomms/management/tests/test_day_status.py`
- `twocomms/management/tests/test_reintegration.py`
- `twocomms/management/tests/test_appeals.py`

**Modify:**
- `twocomms/management/models.py`
- `twocomms/management/views.py`
- `twocomms/management/templates/management/payouts.html`
- `twocomms/management/templates/management/admin.html`
- `twocomms/management/templates/management/stats.html`
- `twocomms/management/urls.py`

**Migrations, in order:**
1. `0028_payroll_accrual_extensions.py`
2. `0029_score_appeal.py`

**Implementation tasks:**
1. Implement working-factor-aware KPI using `ManagerDayStatus`.
2. Implement reintegration curve after long leave.
3. Preserve base salary and verified revenue truth.
4. Separate new/repeat/reactivation/rescue accrual classes.
5. Add freeze reason code/text on accruals where needed.
6. Implement soft-floor logic with working-factor-aware thresholding.
7. Add `ScoreAppeal`.
8. Add manager appeal CTA and admin appeal queue/SLA tracking.
9. Extend earned-day logic so `Minimum achieved`, `Target pace achieved` and `Recovery needed` are separately visible.
10. Extend existing payout/admin payloads with evidence drawer data instead of replacing the payout workflow.

**Critical rules:**
- MOSAIC remains non-payroll-final unless explicit activation later says otherwise;
- freeze reasons must never be hidden;
- payout disputes and score appeals share UI patterns but not necessarily the same persistence model.

**Verification commands:**
```bash
python3 twocomms/manage.py test management.tests.test_soft_floor management.tests.test_commission management.tests.test_rescue_spiff management.tests.test_day_status management.tests.test_reintegration management.tests.test_appeals -v 2
python3 twocomms/manage.py check
```

**Commit boundary:**
- `feat: add payroll-safe management appeals and ledger logic`

### Phase 6: Telephony Preparation

**Goal:** add the data structures and ingestion contract without making telephony a required performance dependency.

**Create:**
- telephony models
- `twocomms/management/services/telephony.py`
- `twocomms/management/telephony_views.py`
- `twocomms/management/management/commands/process_telephony_webhooks.py`
- `twocomms/management/management/commands/reconcile_call_records.py`
- `twocomms/management/tests/test_telephony.py`

**Implementation tasks:**
1. Create webhook inbox/storage model with idempotency keys.
2. Create `CallRecord`.
3. Create `TelephonyHealthSnapshot`.
4. Create reconciliation status flow.
5. Add provider adapter interface and webhook authentication.
6. Keep `VerifiedCommunication` dormant in readiness.

**Critical rules:**
- no provider outage may be interpreted as manager underperformance;
- missing talk seconds means duration is not equivalent to talk quality;
- telephony failures map to incidents, stale flags and possibly `TECH_FAILURE`, not silent blame.

### Phase 7: Telephony / QA Soft Launch

**Goal:** expose telephony and QA in admin/shadow/coaching mode only.

**Implementation tasks:**
1. Turn telephony health and call reconciliation visible in admin.
2. Keep `VerifiedCommunication` in `SHADOW` or `ADMIN_ONLY`, not `ACTIVE`.
3. Add QA sampling, rubric versioning and calibration cycle storage.
4. Add supervisor action log and evidence drawer support.
5. Keep AI assist draft-only.
6. Apply the meaningful-call threshold (`>30s`, minimum count per defaults) only after readiness and health conditions allow it.

**Critical rules:**
- QA is coaching-first until reliability proves otherwise;
- AI output never wins over raw record/timeline evidence.

### Phase 8: Validation, DICE Checkpoints, Activation Decisions

**Goal:** decide whether any shadow component becomes active.

**Implementation tasks:**
1. Run shadow period for at least 8 weeks.
2. Log bi-weekly DICE checkpoints.
3. Measure manager overhead and keep it within `+10%`.
4. Validate score-to-money and ranking stability.
5. If and only if acceptance conditions pass, flip selected `ComponentReadiness` rows from `SHADOW` to `ACTIVE`.

**Critical rules:**
- activation is per-component, not global;
- every activation must have logged rationale, rollback path and version delta note;
- if validation is weak, extend shadow mode rather than forcing activation.

### Phase 9: Optional DTF Read-Only Bridge

**Goal:** late-phase convenience bridge only.

Rules:
- read-only first;
- separate from wholesale truth;
- no DTF metrics mixed into MOSAIC/payroll truth.

## 10. Test, Validation and Acceptance Matrix

### 10.1 Mandatory automated test families

Use the canonical test list from section `5.4`. Minimum gates:

1. Formula tests:
   - `test_ewr.py`
   - `test_mosaic.py`
   - `test_trust.py`
   - `test_churn_weibull.py`
   - `test_score_confidence.py`
2. Foundation tests:
   - readiness/config/version model tests
   - snapshot schema/idempotency/versioning tests
3. Dedupe/follow-up tests:
   - exact phone
   - shared phone
   - import burst grace
   - overload redistribution
4. Payroll/day-ledger tests:
   - working-factor proration
   - reintegration
   - soft floor
   - rescue SPIFF
5. UI/integration tests:
   - stale banner
   - shadow badges
   - appeal CTA visibility
   - admin health widgets
6. Later telephony tests:
   - webhook idempotency
   - reconciliation states
   - outage suppression

### 10.2 Golden-case requirements

Create fixed-input, fixed-output golden cases for:
- EWR
- MOSAIC composition
- score confidence
- repeat commission
- rescue SPIFF
- churn aggregation

Every golden case must store:
- the input block
- the expected output
- tolerance if floating point
- the formula version it belongs to

Seed golden cases that are already fixed by the current canonical formulas:

EWR:

| orders | contacts | revenue | Expected EWR | Formula version |
|---:|---:|---:|---:|---|
| `3` | `120` | `40000` | `0.7516` | `v1` |
| `0` | `5` | `0` | `0.1219` | `v1` |
| `1` | `80` | `50000` | `0.7008` | `v1` |

`score_confidence`:

| verified_cov | sample_suf | stability | recency | Expected | Band |
|---:|---:|---:|---:|---:|---|
| `0.90` | `0.70` | `0.60` | `0.80` | `0.7700` | `MEDIUM` |
| `0.30` | `0.20` | `0.40` | `0.60` | `0.3550` | `LOW` |
| `0.60` | `0.50` | `0.55` | `0.70` | `0.5850` | `MEDIUM` |

Working factor:

| capacity_factors | Expected |
|---|---:|
| `[1.0, 1.0, 0.0, 1.0, 0.5]` | `0.7000` |
| `[0.0, 0.0, 0.0, 0.0, 0.0]` | `0.0000` |
| `[1.0, 1.0, 1.0, 1.0, 1.0]` | `1.0000` |

Onboarding floor score:

| tenure_days | Expected floor |
|---:|---:|
| `7` | `40.0` |
| `21` | `20.0` |
| `28` | `0.0` |

Commission examples:

| revenue | class | rate | Expected |
|---:|---|---:|---:|
| `100000` | `new` | `2.5%` | `2500` |
| `100000` | `repeat` | `5.0%` | `5000` |
| `100000` | `reactivation` | `3.5%` | `3500` |

### 10.3 Phase close-out gates

| Phase | Minimum gate |
|---|---|
| 1 | migrations apply cleanly, readiness/version models exist, seeds are readable |
| 2 | duplicate flow is deterministic and conservative, imported backlog is not instant debt |
| 3 | KPD and shadow MOSAIC coexist, snapshot idempotency holds, stale policy works |
| 4 | shadow and stale states render correctly, manager action flow stays usable |
| 5 | payroll truth stays verified-revenue-based, freeze reason and appeal path are visible |
| 6-7 | provider/webhook failure cannot create performance blame, QA remains coaching-first |
| 8 | 8-week shadow evidence, DICE notes, overhead <= `+10%`, explicit admin sign-off |

### 10.4 Validation metrics for activation review

Required metrics:
- `CV-R²`
- bootstrap confidence intervals
- `Kendall tau`
- top-bucket lift
- adjacent-window ranking stability

Interpretation rule:
- correlation alone is insufficient;
- if rankings are unstable or confidence remains low, extend shadow mode.

### 10.5 Phase artifacts the future agent must leave behind

Each phase should leave explicit evidence so the next agent or reviewer does not need to infer what happened.

| Phase | Minimum artifacts |
|---|---|
| 0 | short preflight note with current branch, deployed branch, migration head, and no-reopen decision list |
| 1 | migration list, seed command output, admin model registrations, config/readiness dump |
| 2 | duplicate-zone examples, follow-up ladder examples, reminder command dry-run or sample output |
| 3 | golden cases, one example snapshot payload, snapshot idempotency evidence, stale-case evidence |
| 4 | screenshots or HTML proof of manager/admin surfaces, shadow/stale/no-surprise badge evidence |
| 5 | appeal flow sample, freeze reason sample, earned-day example with gap-category split |
| 6-7 | telephony health sample, reconciliation status examples, QA reliability evidence |
| 8 | DICE log, overhead estimate, activation/hold recommendation with rationale |

## 11. Deploy, Rollback and Post-Deploy Verification

### 11.1 Local pre-push checklist

Before every code push:
```bash
git status --short
python3 twocomms/manage.py check
python3 twocomms/manage.py test management.tests -v 2
```

For migration-bearing phases:
```bash
python3 twocomms/manage.py makemigrations management
python3 twocomms/manage.py migrate
python3 twocomms/manage.py sqlmigrate management <migration_number>
```

### 11.2 Git and push checklist

Rule:
- commit only the intended phase files;
- do not accidentally stage unrelated working-tree edits;
- push the same branch the server is expected to pull, or verify the server branch first.

Recommended pattern:
```bash
git branch --show-current
git add <phase files>
git commit -m "<phase-specific message>"
git push origin $(git branch --show-current)
```

### 11.3 Server deploy command

Canonical server path from the current project instructions:

```bash
sshpass -p 'trs5m4t1' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc '
source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate &&
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms &&
git pull &&
python manage.py migrate &&
python manage.py collectstatic --noinput &&
python manage.py compress --force &&
touch tmp/restart.txt
'"
```

Rule:
- keep `collectstatic` / `compress` in deploys that touch templates or static assets;
- keep `migrate` in deploys that touch models;
- if the phase is docs-only, these runtime steps may be skipped, but implementation phases should assume they are needed.

### 11.4 Post-deploy smoke verification

At minimum verify:
1. login works on `management.twocomms.shop`
2. manager home loads
3. stats page loads
4. admin panel loads
5. payouts page loads
6. reminders panel opens
7. `activity/pulse/` still returns `200` for authenticated management users
8. invoice and contract review pages still load
9. parser dashboard still loads
10. if a phase added commands, the latest `CommandRunLog` entries look sane

Recommended smoke commands when safe:
```bash
python manage.py check
python manage.py showmigrations management
python manage.py compute_nightly_scores --date=$(date +%F)
```

### 11.5 Rollback rules

1. Record the deployed commit hash before migration-heavy deploys.
2. Record new migration names before running `migrate`.
3. If a deploy fails at the template/static layer only, revert to the prior commit and redeploy.
4. If a migration must be rolled back, only reverse migrations that were designed reversible; otherwise ship a forward fix.
5. If shadow analytics misbehave but data is safe, first flip readiness state back to `DORMANT` or `SHADOW` before touching schema.

## 12. Anti-Regression Checklist

Do not do any of the following:

- turn KPD off before shadow validation is complete
- make `score_confidence` a cosmetic badge only
- let stale snapshots look current
- use `Shop.created_by` as the live portfolio owner when `managed_by` is the operational truth
- rebuild CP, Telegram, payout or reminder workflows under new names
- add `Client.is_test`
- auto-merge fuzzy duplicates
- punish import burst debt immediately
- use telephony or QA as payroll truth before maturity
- keep expanding `views.py` and `stats_service.py` as monoliths after the new service package exists
- create a `management/tests/` package while leaving `tests.py` in place without a migration plan
- assume bundler-based frontend tooling for management assets
- assume Redis/Celery are always available for correctness-critical behavior

## 13. Repo-Local Helper Worth Knowing

The only repo-local skill discovered inside this workspace is:
- `codex_skills/coding-agent/SKILL.md`

Use it only if the future implementation is intentionally delegated to external agent CLIs in isolated workdirs. It is not required for normal direct implementation of this plan.

## 14. Final Execution Note

If the future agent follows this file correctly, it should not need to reopen the old synthesis folders for basic meaning. The only allowed reason to revisit older layers is to confirm that a detail was already absorbed through the traceability matrix, not to rediscover architecture from scratch.
