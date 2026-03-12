# Product Backlog for Management Subdomain

## 1. Роль этого файла
Этот backlog нужен не как wish-list, а как структурированный список модулей, которые реально следуют из authoritative docs и current codebase.

Каждый модуль описан так, чтобы его можно было позже перевести в:
- implementation tasks;
- migrations;
- services;
- UI blocks;
- background commands.

## 2. Core modules

### Module A: Analytics Core
Состав:
- `EWR`
- shadow `Weibull` churn
- admin/shadow `Wilson` diagnostic
- shadow `MOSAIC`
- readiness registry
- nightly snapshots
- current `KPD` bridge

Статус: `HIGH PRIORITY`

Основные кодовые зоны:
- `management/stats_service.py`
- `management/models.py`
- `management/stats_views.py`

### Module B: Identity / Dedup Core
Состав:
- duplicate warning flow
- review queue
- append-first behavior
- batch import dry-run
- merge audit / rollback
- ownership-safe dedupe

Статус: `HIGH PRIORITY`

Кодовые зоны:
- `management/models.py`
- `management/lead_views.py`
- `management/parsing_views.py`
- `management/views.py`

### Module C: Follow-Up and Reminder Engine
Состав:
- `MAX_FOLLOWUPS_PER_DAY`
- new reminder ladder
- overload handling
- low-noise delivery
- rate limiting

Статус: `HIGH PRIORITY`

Кодовые зоны:
- `ClientFollowUp`
- reminder models
- `views.py`
- `stats_service.py`
- command layer

### Module D: Payroll and KPI Core
Состав:
- KPI modes
- repeat/reactivation split
- repeat soft-floor
- rescue `SPIFF`
- payout decomposition
- phase-aware DMT
- earned-day ledger

Статус: `HIGH PRIORITY`

Кодовые зоны:
- payout models
- payout APIs
- `views.py`
- payout templates

### Module E: Portfolio / Retention Core
Состав:
- portfolio health
- reactivation priority
- snooze
- expected next order
- planned-gap guard
- rescue queue

Статус: `HIGH PRIORITY`

Кодовые зоны:
- `Client`
- stats payload
- manager/admin portfolio surfaces

### Module F: Telephony and QA Core
Состав:
- `CallRecord`
- webhook inbox
- provider adapter
- QA review queue
- supervisor analytics

Статус: `MEDIUM PRIORITY`

Кодовые зоны:
- new models
- webhook views
- commands
- admin/supervisor UI

### Module G: Manager Console
Состав:
- Radar
- shadow MOSAIC card
- salary simulator
- rescue top-5
- scaled `SPIFF` cue
- rescue-load cap / `DQ grace` messaging
- hold-harmless shadow badge
- portfolio status block

Статус: `HIGH PRIORITY`

Кодовые зоны:
- `stats.html`
- related JS/CSS

### Module H: Admin Control Center
Состав:
- manager overlay
- freeze/review controls
- readiness badges
- admin economics
- score confidence labels
- payout/admin risk views

Статус: `HIGH PRIORITY`

Кодовые зоны:
- `admin.html`
- `stats_admin_*`
- payout admin APIs

### Module I: Background Jobs Layer
Состав:
- nightly score computation
- reminder send
- duplicate queue scan
- telephony webhook processing

Статус: `HIGH PRIORITY`

Кодовые зоны:
- `management/management/commands/`

### Module J: Calibration and Governance
Состав:
- defaults registry
- thresholds
- phase guards
- audit of formula changes

Статус: `HIGH PRIORITY`

Кодовые зоны:
- config models
- code constants
- docs and audit layer

### Module K: Safety / Exception Handling
Состав:
- day status
- force majeure
- Red Card / freeze
- appeals
- data integrity exceptions

Статус: `HIGH PRIORITY`

Кодовые зоны:
- models
- admin controls
- audit trail

## 3. Model backlog

### 3.1 New or extended models
- `Client.is_test`
- `Client.expected_next_order` or equivalent field
- `Client.normalized_name_hash` or equivalent exact-precheck helper
- `ClientSnoozeStatus`
- `ManagerDayStatus` or equivalent ledger model
- `ForceMajeureEvent`
- `NightlyScoreSnapshot`
- `ScoreAuditLog`
- `MergeAuditLog` or equivalent rollback-safe merge snapshot
- `CallRecord`
- `TelephonyWebhookLog`
- `CallQAReview`
- lightweight duplicate dispute / audit record if existing audit trail is insufficient

### 3.2 Existing models to reuse
- `Client`
- `ManagementLead`
- `LeadParsingJob`
- `LeadParsingResult`
- `ClientFollowUp`
- `Report`
- `ManagementDailyActivity`
- `ReminderSent`
- `ReminderRead`
- `ManagerCommissionAccrual`
- `ManagerPayoutRequest`

## 4. Service backlog
- `compute_ewr`
- `compute_conversion_kpi_wilson`
- `compute_churn_weibull`
- shadow `compute_mosaic`
- `compute_trust_production`
- `compute_trust_diagnostic`
- `compute_score_confidence`
- `compute_followup_state`
- `find_duplicates_safe`
- `preview_batch_import`
- `check_rate_limit`
- `compute_portfolio_health`
- `compute_reactivation_priority`
- `build_rescue_top5`
- `compute_rescue_spiff`
- `classify_repeat_vs_reactivation`
- `build_radar_payload`
- `build_salary_simulation_payload`

## 5. Command backlog
- `compute_nightly_scores`
- `send_management_reminders`
- `check_duplicate_queue`
- `process_telephony_webhooks`
- `reconcile_call_records`

## 6. UI backlog

### 6.1 Manager UI
- Radar
- shadow score decomposition
- salary simulator
- top-5 rescue
- scaled `SPIFF` hint
- rescue-load cap / `DQ grace` state
- portfolio health summary
- earned day explanation

### 6.2 Admin UI
- readiness registry surface
- freeze / Red Card controls
- duplicate review queue
- payout decomposition
- admin economics panel
- score confidence labels
- telephony / QA review queue

## 7. Dependency order
1. safety fields and status layers
2. dedupe/follow-up hardening
3. analytics core and snapshots
4. manager/admin UI
5. payroll-safe rollout
6. telephony prep
7. telephony and QA soft launch
8. validation and calibration

## 8. What counts as implementation error
- реализовать high-risk formulas без phase guards;
- делать telephony prerequisite для первой боевой фазы;
- строить cron/command logic так, как будто Redis/Celery already exist;
- переносить shadow analytics в payroll before validation;
- внедрять модуль без привязки к существующим файлам `management`.
