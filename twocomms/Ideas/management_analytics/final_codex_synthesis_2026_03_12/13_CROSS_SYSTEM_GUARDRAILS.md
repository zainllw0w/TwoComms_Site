# Cross-System Guardrails

## 1. Роль этого файла
Этот документ фиксирует технические и операционные ограничения, которые должны сопровождать любую реализацию management analytics.

Guardrails существуют, чтобы:
- не дать формуле тихо стать истиной без контроля;
- не превратить shared hosting в узкое место;
- не потерять audit trail по деньгам, ownership и score;
- иметь понятный recovery path при сбое.

## 2. Central Audit Log

### 2.1 Что обязано логироваться
- payout approvals / rejections / manual adjustments;
- ownership disputes and reassignment;
- Red Card / freeze actions;
- Force Majeure activation;
- duplicate resolution;
- formula/config changes;
- snooze approval and removal.

### 2.2 Минимальный состав записи
- actor;
- target entity;
- action type;
- reason;
- timestamps;
- before/after snapshot where applicable.

## 3. Access rules
- manager не должен иметь доступ к destructive admin actions;
- admin-only analytics должны быть физически отделены в UI и API;
- shadow metrics нельзя выдавать как payroll-final truth вне admin-approved flow;
- review / freeze / payout actions должны требовать role check.

## 4. Formula governance

### 4.1 Любая формула — это конфигурация с последствиями
Следовательно:
- нельзя менять вес или threshold тихим hotfix without documentation;
- нельзя смешивать research draft и production defaults;
- каждый change-set должен иметь reason, changelog entry и rollout mode.

### 4.2 Что обязательно версионировать
- MOSAIC weights;
- trust bounds;
- gates;
- dampener rules;
- KPI thresholds;
- points table;
- portfolio thresholds;
- any score-to-money mapping.

## 5. Shared-hosting guardrails

### 5.1 Нормативный стек
- `management commands + cron`
- `FileBasedCache`
- DB-backed snapshots / queues

### 5.2 Что не должно считаться базовым допущением
- `Redis` availability;
- `Celery` workers;
- `Docker`;
- `pg_trgm` extension.

## 6. Cache and broker recovery

### 6.1 FileBasedCache recovery
Если `FileBasedCache` повреждён или раздулся:
- иметь отдельную cache directory;
- иметь явные `MAX_ENTRIES` / `CULL_FREQUENCY` limits на уровне settings;
- иметь documented clean-up procedure;
- логировать cache-related failures;
- не терять verified financial truth из-за очистки кэша.

`FileBasedCache` допустим для rate limiting, ephemeral reminder locks и lightweight broker-substitutes. Он не должен использоваться как хранилище финансовой истины, snapshots или единственный audit source.

### 6.2 Cron health
Каждая команда должна иметь:
- timeout expectation;
- last run timestamp;
- error visibility для admin/dev;
- retry strategy, не приводящую к storm-effect.

## 7. Snapshot safety
Nightly snapshot layer обязана:
- быть идемпотентной по дате и менеджеру;
- сохранять raw decomposition;
- не перезаписывать silently critical historical data;
- использовать unique constraints where appropriate.

## 8. Force Majeure protocol

### 8.1 Когда нужен
- технический сбой;
- массовый сбой провайдера;
- экстремальная внешняя ситуация;
- день, когда система не имеет права оценивать performance как обычно.

Каноническая модель:
- `ForceMajeureEvent` — это системное событие с окном действия, reason и initiator;
- day-ledger уже отражает event в виде `TECH_FAILURE` или `FORCE_MAJEURE` на affected dates;
- event является source of truth, а day-status — производным operational marker.

### 8.2 Что делает
- ставит affected period в special status;
- отключает punitive checks for that window;
- замораживает trust and DMT degradation;
- требует явного reason and initiator.
- по умолчанию действует `24 часа`, затем требует extend/cancel action;
- отключает batch-logging penalties и KPI/DMT auto-fail за этот период;
- не уничтожает existing verified payouts, а только останавливает новые punitive derivations.

## 9. Red Card / freeze protocol

### 9.1 Когда допустим
Только при обоснованном fraud / severe integrity concern.

### 9.2 Что делает
- freeze score-sensitive surfaces;
- freeze payroll-related automatic progress if needed;
- не опускает trust "в ноль" автоматически;
- создаёт review/investigation state.

### 9.3 Что обязан видеть менеджер
- факт review/freeze;
- понятный статус;
- канал escalation / communication.

## 10. Backup and restore
- verified money truth и payout records must be restorable independently of analytics cache;
- snapshots and config changes should be exportable;
- duplicate/ownership disputes should leave enough history for replay and investigation.

## 11. Performance budgets

### 11.1 Минимальные требования
- avoid N+1 on major stats/admin pages;
- use `select_related` / `prefetch_related` where needed;
- limit expensive loops in stats payload;
- no expensive fuzzy dedupe on full table scan without blocking.

Target budgets:
- API latency (`p95`) `< 200ms`;
- dashboard load `< 2s`;
- nightly jobs `< 30 min`;
- duplicate check `< 500ms`.

### 11.2 Query-sensitive areas
- `stats_service.py`
- large admin pages
- duplicate review and queue processing
- nightly snapshots

## 12. i18n and copy safety
- status copy must remain consistent between manager/admin surfaces;
- punitive wording should be avoided in manager-facing copy;
- if multilingual expansion happens, score labels and states must be stable enough for translation.

## 13. Release safety

### 13.1 What must go through shadow first
- MOSAIC itself;
- trust-heavy logic;
- new payout-adjacent formulas;
- telephony-linked score logic;
- seasonality.

### 13.2 What may ship earlier
- data fields;
- duplicate warnings;
- reminder quality improvements;
- UI labels and explainability improvements;
- non-destructive admin surfaces.

## 14. Incident handling
Если новый модуль ведёт себя нестабильно:
- переводить его в `SHADOW` или `DORMANT`;
- сохранять входные данные и audit trail;
- не ломать существующую verified operational truth;
- фиксировать incident in decision log/changelog.

## 15. Приземление в текущий код

### 15.1 Основные зоны
- `management/models.py`
- `management/views.py`
- `management/stats_service.py`
- `management/management/commands/`
- admin/payout templates and APIs

### 15.2 Что guardrails прямо запрещают
- скрыто менять формулы в коде без обновления defaults и docs;
- включать DORMANT-компоненты как источник production punishment;
- делать stateful background logic зависимой от недоступной инфраструктуры.
