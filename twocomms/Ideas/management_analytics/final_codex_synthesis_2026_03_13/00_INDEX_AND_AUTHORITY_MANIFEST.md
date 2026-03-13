# TwoComms Management Canonical Synthesis 2026-03-13

## Purpose

Этот пакет является новым canonical handoff-пакетом для management analytics и supersedes роль `final_codex_synthesis_2026_03_12` как основной входной папки для следующего агента, который будет собирать единый implementation file.

Главная цель пакета:
- собрать в одном месте authoritative rules, accepted improvements и code-reality constraints;
- убрать необходимость повторно синтезировать три папки;
- исключить semantic loss при переходе к implementation planning.

## Authority Manifest

### Canonical package status

| Layer | Status | Rule |
|---|---|---|
| Текущий Django-код `management/` | `ground truth for current reality` | показывает, что уже существует и что нельзя дублировать |
| Эта папка `final_codex_synthesis_2026_03_13` | `authoritative planning contract` | главный пакет для следующего шага |
| `final_codex_synthesis_2026_03_12` | `superseded but mandatory reference` | baseline ideas, old structure, legacy audits |
| `reports/tc_mosaic_improvements` | `delta/improvement source` | accepted hardening and precision upgrades |
| `reports/i1` | `code-reality and implementation audit source` | blockers, maps, helper context |
| deep research and report docs | `reference-only evidence layer` | нельзя импортировать как production defaults напрямую |

### Status vocabulary

| Status | Meaning |
|---|---|
| `authoritative` | production-safe rule for planning and later implementation |
| `shadow/admin-only` | safe to compute or display, but not payroll-final truth |
| `dormant` | explicitly not active in current phase |
| `backlog` | accepted idea, but later-phase only |
| `reference-only` | useful context, but not a direct spec |
| `rejected` | intentionally excluded from the target design |

### Non-negotiable rules

1. Ни одна формула не читается из reference docs напрямую.
2. Ни один score-sensitive payload не существует без `formula_version`, `defaults_version` и freshness semantics.
3. Ни один shadow/admin-only signal не masquerades as payroll-final truth.
4. Ни один новый модуль не должен дублировать уже существующие production models, workflows или Telegram patterns.
5. Ни один leave / tech failure / import burst case не должен silently превращаться в manager fault.

## What This Package Adds Over 2026-03-12

- единый authority manifest;
- встроенный code-reality layer;
- явный KPD -> MOSAIC transition contract;
- capacity-aware KPI and reintegration semantics;
- `score_confidence` как shared safety key;
- telephony health and reconciliation contract;
- testing, migration, rollout and acceptance contract;
- agent handoff brief для следующего implementation-step.

## Reading Order

1. `00_INDEX_AND_AUTHORITY_MANIFEST.md`
2. `01_EXECUTIVE_CANONICAL_SYNTHESIS.md`
3. `02_SYSTEM_ARCHITECTURE_AND_INVARIANTS.md`
4. `03`-`08` thematic contracts
5. `09_CODE_REALITY_MODEL_SERVICE_ENDPOINT_MAP.md`
6. `10_GOVERNANCE_DATA_MODEL_JOBS_ROLLOUT.md`
7. `11_EDGE_CASES_FAILURE_MODES_AND_SCENARIOS.md`
8. `12_TEST_STRATEGY_VALIDATION_ACCEPTANCE.md`
9. `13_IMPLEMENTATION_BLUEPRINT_AND_DEPENDENCY_ORDER.md`
10. `14_AGENT_HANDOFF_BRIEF_FOR_IMPLEMENTATION_FILE.md`
11. `15_TRACEABILITY_MATRIX_AND_SOURCE_COVERAGE.md`
12. `16_DECISION_LOG_REJECTED_IDEAS_AND_BACKLOG.md`
13. `17_PACKAGE_CHANGELOG_AND_SUPERSESSION.md`

## Package Map

| File | Role |
|---|---|
| `01_EXECUTIVE_CANONICAL_SYNTHESIS.md` | one-pass executive contract |
| `02_SYSTEM_ARCHITECTURE_AND_INVARIANTS.md` | layers, rollout states, versioning, KPD coexistence |
| `03_SCORE_MOSAIC_EWR_CONFIDENCE.md` | MOSAIC, EWR, trust, gates, confidence |
| `04_PAYROLL_KPI_PORTFOLIO_EARNED_DAY.md` | money-safe rules, KPI proration, portfolio, appeals |
| `05_IDENTITY_DEDUPE_FOLLOWUP_ANTI_ABUSE.md` | identity, dedupe, reminder ladder, abuse review |
| `06_TELEPHONY_QA_SUPERVISOR_VERIFIED_COMMUNICATION.md` | telephony maturity, QA, supervisor, verified comms |
| `07_MANAGER_ADMIN_UX_EXPLAINABILITY.md` | manager/admin surfaces, freshness, fairness perception |
| `08_ADMIN_ECONOMICS_FORECAST_DECISION_SAFETY.md` | admin-only analytics and confidence-aware reading |
| `09_CODE_REALITY_MODEL_SERVICE_ENDPOINT_MAP.md` | extend vs keep vs create map grounded in real code |
| `10_GOVERNANCE_DATA_MODEL_JOBS_ROLLOUT.md` | versions, snapshots, jobs, incidents, rollout safety |
| `11_EDGE_CASES_FAILURE_MODES_AND_SCENARIOS.md` | explicit scenario handling |
| `12_TEST_STRATEGY_VALIDATION_ACCEPTANCE.md` | tests, validation windows, acceptance conditions |
| `13_IMPLEMENTATION_BLUEPRINT_AND_DEPENDENCY_ORDER.md` | phase plan and strict build order |
| `14_AGENT_HANDOFF_BRIEF_FOR_IMPLEMENTATION_FILE.md` | instructions for the next agent |
| `15_TRACEABILITY_MATRIX_AND_SOURCE_COVERAGE.md` | anti-loss matrix across all source docs |
| `16_DECISION_LOG_REJECTED_IDEAS_AND_BACKLOG.md` | accepted, partial, rejected, later-phase ideas |
| `17_PACKAGE_CHANGELOG_AND_SUPERSESSION.md` | what changed and why this package supersedes the old one |

## Ground Truth About Current Code

Пакет explicitly assumes:
- `management/models.py` already contains `Client`, `ManagementLead`, `Shop`, `ManagementDailyActivity`, `ClientFollowUp`, `ManagementStatsConfig`, `ManagerCommissionAccrual`, `ManagerPayoutRequest`, reminder models, contract workflows and CP email logs;
- `stats_service.py` already computes current KPD, advice cards, shop metrics, source normalization and caches payloads;
- `views.py` already contains large Telegram-heavy admin workflows and payout flows;
- `stats_views.py` and `stats.html` are the primary extension targets for manager/admin score surfaces;
- current code already uses cron-friendly patterns and short-lived caching.

## Real Infrastructure Constraints

- shared hosting;
- no baseline assumption of Celery, Redis or `pg_trgm`;
- commands + cron + cache + DB snapshots are the normative execution stack;
- deploy path remains `git push` + server-side `git pull`.

## Usage Rule

Следующий агент не должен строить implementation file по старым папкам напрямую. Старые папки читаются только через `15_TRACEABILITY_MATRIX_AND_SOURCE_COVERAGE.md` и только для проверки, что ничего не потеряно.
