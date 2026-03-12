# Management Codebase Alignment Map

## 1. Роль этого файла
Этот документ связывает новый пакет синтеза с текущей реальной кодовой базой `management`.

Он нужен, чтобы implementation planning опирался на конкретные файлы, а не на абстрактные модули.

## 2. Current code anchors

### 2.1 Models

| Файл / сущность | Что уже есть | Что вероятно добавится |
|---|---|---|
| `Client` | owner, phone normalization, `next_call_at`, current CRM data | `is_test`, `expected_next_order`, optional `normalized_name_hash`, snooze hooks |
| `ManagementLead` | pre-conversion lead layer | dedupe warnings, better source normalization |
| `LeadParsingJob` / `LeadParsingResult` | parsing batches and moderation trail | dry-run preview, duplicate counters, safer import confirm flow |
| `ClientFollowUp` | current follow-up status machine | capacity-aware logic, overload interpretation |
| `Report` | discipline/reporting layer | stronger tie to day-status / earned day |
| `ManagementDailyActivity` | activity tracking | better use for shadow analytics |
| `ReminderSent` / `ReminderRead` | reminder dedupe/read state | richer reminder-key strategy and alert hygiene |
| future `ForceMajeureEvent` / `ScoreAuditLog` | system-wide exception and formula audit layers | exemption windows, formula-change traceability |
| `ManagerCommissionAccrual` | payout truth | richer decomposition / freeze metadata |
| `ManagerPayoutRequest` | payout workflow | clearer admin economics linkage |

### 2.2 Services

| Файл | Что уже есть | Что вероятно добавится |
|---|---|---|
| `stats_service.py` | KPD, advice, source smoothing, follow-up stats | EWR, shadow MOSAIC, trust, radar payload, snapshot payload |
| `lead_services.py` | lead/points helpers | source cleanup, dedupe support, website copy from leads |

### 2.3 Views and endpoints

| Файл | Что уже есть | Что вероятно добавится |
|---|---|---|
| `stats_views.py` | stats, admin stats, advice dismiss | shadow score payloads, readiness widgets |
| `views.py` | manager/admin, reports, reminders, payouts, invoices, contracts | admin freeze/review actions, richer payout/admin economics |
| `lead_views.py` | lead create/detail/process | duplicate warnings and review-safe conversion |
| `parsing_views.py` | parsing dashboard and moderation | pre-conversion dedupe and source quality surfaces |
| `urls.py` | current management routes | telephony webhook / review routes if needed |

### 2.4 Templates

| Файл | Что уже есть | Что вероятно добавится |
|---|---|---|
| `templates/management/stats.html` | hero, spiral, KPI cards, follow-ups, advice | Radar, shadow decomposition, rescue/top-5, salary simulator |
| `templates/management/admin.html` | admin overview and payout blocks | readiness registry, duplicate review, freeze/review controls, admin economics |
| `templates/management/base.html` | shell and layout | new navigation/state badges if needed |
| `templates/management/payouts.html` | payout views | clearer accrual decomposition |

### 2.5 Commands
Текущее наличие `management/commands/` означает, что команда уже архитектурно готова к cron-driven jobs.

Уже есть:
- `notify_test_shops.py` — полезный якорь, показывающий что cron/command pattern в проекте не является чужеродным.

Вероятные новые команды:
- `compute_nightly_scores`
- `send_management_reminders`
- `check_duplicate_queue`
- `process_telephony_webhooks`

## 3. Where each big subsystem lands

### 3.1 MOSAIC / EWR
- primary home: `stats_service.py`
- support models: snapshots / day status
- surfaces: `stats.html`, admin stats

### 3.2 Payroll / Earned Day
- primary home: payout models and `views.py`
- support models: day ledger / review statuses
- surfaces: `payouts.html`, admin payout blocks

### 3.3 Dedupe / reminders
- primary home: `Client`, `ManagementLead`, `ClientFollowUp`
- service/helpers: duplicate detection + reminder scheduling
- surfaces: `lead_views.py`, `parsing_views.py`, reminder feed, admin review queue
- import-safety layer: `LeadParsingJob` / `LeadParsingResult` for dry-run preview and moderation-safe confirm

### 3.4 Telephony / QA
- primary home: new models + webhook handlers
- support services: processing commands
- surfaces: future supervisor/admin queue

## 4. Known codebase constraints
- `views.py` already carries a lot of responsibility, so future planning should avoid making it an even larger god file;
- stats payload construction is already non-trivial, so new analytics should be added carefully, ideally through dedicated helpers;
- manager/admin templates already contain meaningful UI structure, so replacement should be incremental.

## 5. Safe insertion strategy
- start with models and services;
- then add commands and snapshots;
- then expose admin-facing shadow surfaces;
- only then broaden manager-facing analytics;
- only after stable shadow behaviour connect payout-adjacent consequences.

## 6. What this map protects against
- "идея есть, но непонятно куда она пойдёт в код";
- "реализация размазывается по случайным файлам";
- "новый planning шаг снова начинает с нуля искать точки внедрения".
