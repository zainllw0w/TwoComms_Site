# 08. Governance, data model, jobs, rollout and safe implementation

## 1. Что пакет уже делает правильно в governance
- есть cross-system guardrails;
- формулы трактуются как configuration with consequences;
- snapshots and audit trail уже признаны обязательными;
- rollout split into phases;
- rollback и SHADOW/DORMANT semantics уже введены;
- stack реалистичен для shared hosting.

По сути foundation уже взрослый. Но его ещё можно сделать менее хрупким.

## 2. Главное улучшение: превратить governance в executable contract
Сейчас governance mostly textual.
Нужны дополнения, которые помогут не только “знать”, но и автоматически ловить отклонения.

## 3. Что я бы добавил в data/model layer

### 3.1 `NightlyScoreSnapshot` fields
Помимо уже описанных полей рекомендую хранить:
- `formula_version`
- `defaults_version`
- `snapshot_schema_version`
- `score_confidence`
- `snapshot_freshness_seconds`
- `job_run_id`
- `working_day_factor`
- `capacity_factor_avg_period`

### 3.2 `ManagerDayStatus` / day-ledger enhancement
Добавить:
- `capacity_factor`
- `source_reason` (manual/admin/system)
- `derived_from_force_majeure_event`
- `reintegration_flag`

### 3.3 `CommandRunLog`
Очень полезный lightweight model:
- command_name
- started_at / finished_at
- status
- rows_processed
- warnings_count
- traceback_excerpt
- snapshot_version affected

Это сильно улучшит observability без тяжёлой инфраструктуры.

## 4. Command execution layer: что стоит формализовать

### 4.1 Idempotency and lock semantics
Для команд вроде:
- `compute_nightly_scores`
- `send_management_reminders`
- `process_telephony_webhooks`

нужен одинаковый контракт:
- acquire lock
- run id
- safe retry
- idempotent writes
- after-run health record

### 4.2 Stale snapshot policy
Если nightly command не отработала:
- score-sensitive SHADOW surfaces остаются видимыми,
- но получают `STALE` state,
- admin health widget загорается,
- payout-adjacent simulations не pretending current truth.

### 4.3 Incident class registry
Полезно ввести короткие system incident classes:
- `SNAPSHOT_STALE`
- `CACHE_PRESSURE`
- `TELEPHONY_OUTAGE`
- `REMINDER_STORM`
- `DUPLICATE_QUEUE_BACKLOG`
- `PAYOUT_REVIEW_BLOCK`

## 5. Code-structure improvements

### 5.1 Не расширять `views.py` бесконечно
Alignment map уже правильно предупреждает про god file risk.
Я бы заранее заложил:
- dedicated helpers for payout decomposition
- dedicated score payload builders
- duplicate/review services
- telephony reconciliation service

### 5.2 `stats_service.py` тоже нужен modular split
Особенно для:
- `compute_ewr`
- `compute_source_fairness`
- `compute_churn_weibull`
- `build_rescue_top5`
- `compute_score_confidence`

Это важно и для тестов, и для explainability.

## 6. Testing: чего сейчас не хватает как отдельного контракта
Нужен scenario regression suite минимум по кейсам:
- vacation week
- sick day
- tech failure day
- onboarding day 10 / day 20 / day 30
- long leave reintegration
- import burst
- shared phone dedupe
- reactivation at 179 vs 181 days
- stale snapshot
- telephony outage
- accepted appeal recalculation

Без такого suite система может быть логически красивой, но operationally хрупкой.

## 7. `Doc -> code -> snapshot` chain should be auditable
Я рекомендую один дополнительный guard:
- любое изменение defaults имеет changelog entry;
- тест подтверждает that current constants match doc registry;
- snapshot stores version;
- admin health surface shows version.

## 8. Что ещё полезно добавить как governance hardening

### 8.1 `reference_only` header прямо в reference docs
Не только в index, а в самих `08/09/16`.

### 8.2 Manager-facing no-surprise rule
Если меняется то, что визуально влияет на score/payout simulation:
- manager видит note `формула обновлена`;
- admin видит version delta and reason.

### 8.3 Data backfill playbook
Для новых полей:
- `is_test`
- `expected_next_order`
- `normalized_name_hash`
- day-ledger data

нужен отдельный backfill plan, чтобы внедрение не оказалось ручным болотом.

## 9. Наиболее вероятные bugs без этих улучшений

### Bug 1 — silent config drift
Формула уже изменилась, а UI и historical snapshots продолжают сравниваться как будто нет.

### Bug 2 — команда cron отработала частично, но surface выглядит normal
Потому что нет unified run log + stale policy.

### Bug 3 — rollout идёт по roadmap, но без regression scenarios
И edge-cases начинают ломаться по одному.

### Bug 4 — reference docs снова случайно оживают как specification
Если у них нет явного machine-readable статусного барьера.

## 10. Что менять в каких файлах
- `13_CROSS_SYSTEM_GUARDRAILS.md` — CommandRunLog, stale policy, incident classes
- `07_IMPLEMENTATION_ROADMAP.md` — regression suite and backfill playbooks
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md` — versioning constants / stale limits
- `19_MANAGEMENT_CODEBASE_ALIGNMENT_MAP.md` — explicit service split plan
- code: models, command layer, stats service helpers, admin health widget

## 11. Приоритет внедрения
1. snapshot versioning
2. CommandRunLog
3. stale snapshot policy
4. regression scenario suite
5. service decomposition plan
6. manager/admin version visibility
