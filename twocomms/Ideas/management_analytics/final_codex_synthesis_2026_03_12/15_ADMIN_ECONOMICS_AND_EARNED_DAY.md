# Admin Economics and Earned Day

## 1. Роль этого файла
Этот документ фиксирует admin-only экономический слой и production-safe версию `Earned Day`.

Здесь соединяются:
- analytics;
- payout truth;
- дневная дисциплина;
- admin review and exception handling.

Главный принцип: admin economics помогают понимать систему, но не имеют права silently превращаться в карательный механизм.

## 2. Admin Economics Dashboard

### 2.1 Что это такое
Admin economics — это не "ещё один leaderboard", а слой для понимания:
- сколько денег приносит менеджер;
- как устроен mix `new/repeat`;
- как score correlates with money;
- где система помогает, а где только создаёт шум.

### 2.2 Что видит только админ
- new vs repeat contribution;
- accrual decomposition;
- payout state;
- repeat soft-floor impact;
- shadow score decomposition;
- score-to-money divergence;
- cost of rescue / reactivation patterns.

### 2.3 Cost model
Базовая admin-модель стоимости менеджера должна быть выражена явно:

`manager_monthly_cost = fixed_salary_component + commissions + workspace_cost + management_overhead + onboarding_amortization`

Это admin accounting view.
Его нельзя показывать менеджеру как псевдо-вердикт "ты стоишь столько-то".

### 2.4 Contribution proxy
Если в контуре нет честной gross-margin модели, нельзя называть revenue-показатели прибылью.

Минимально корректный слой:
- `attributed_revenue`
- `direct_commission_cost`
- `fixed_manager_cost`
- `commercial_contribution_proxy = attributed_revenue - direct_commission_cost - fixed_manager_cost`

Если позже появится доказуемая margin model, admin economics можно расширять, но текущий пакет не должен симулировать precision, которой нет.

### 2.5 Break-even and payback
Admin dashboard должен отдельно показывать:
- monthly break-even point;
- current payback progress;
- estimated payback day;
- risk of not reaching break-even by month end.

Это managerial signal для coaching / lead-mix / staffing decisions, а не silent payroll rule.

### 2.6 Forecast scenarios
Нужны минимум три сценария:
- optimistic;
- base;
- pessimistic.

Основание прогноза:
- current month pace;
- recent trend;
- current weighted pipeline через stage-weight model;
- confidence level of the projection.

### 2.7 Optional workload consistency diagnostic
Если команда позже захочет добавить `workload consistency` / `active tab time`, это допустимо только как:
- explicit admin-only metric;
- disclosed diagnostic layer;
- coaching / workload signal, а не payroll truth;
- privacy-reviewed feature without silent surveillance semantics.

## 3. Score-to-money validation

### 3.1 Зачем нужно
Нельзя включать новые score-formulas в payroll-adjacent процессы, не понимая, коррелируют ли они хотя бы разумно с фактическими деньгами и verified outcomes.

### 3.2 Какие сигналы сравниваем
- current `KPD`;
- shadow `MOSAIC`;
- `EWR`;
- `Wilson` conversion diagnostic;
- repeat/new revenue;
- portfolio health distribution;
- follow-up discipline;
- report integrity.

### 3.3 Где хранить
Для этого нужен nightly snapshot layer:
- `manager`
- `date`
- `mosaic_score`
- `ewr_score`
- `conversion_kpi_wilson`
- `trust_diagnostic`
- `pipeline_value`
- `churn_avg`
- `score_confidence`
- `portfolio_health_pct`
- `raw_data` / explainability payload
- `computed_at`

UI и admin-analytics читают прежде всего последний snapshot, а не пересчитывают тяжёлые `Weibull / Wilson` формулы на каждый page load.

### 3.4 Confidence label и validation protocol
Каждый admin-only score-sensitive snapshot должен сопровождаться confidence label:
- `HIGH (>=0.80)` — допустим для кадровых/KPI escalation discussions;
- `MEDIUM (0.50-0.79)` — coaching, pipeline review, targeted support;
- `LOW (<0.50)` — только наблюдение и сбор данных.

Confidence structure должна быть объяснимой:
- volume of data;
- verified coverage;
- score stability;
- recency;
- sample sufficiency.

Validation protocol не должен ограничиваться абстрактным "посмотрим на корреляцию":
- Bootstrap confidence intervals для `KPD/MOSAIC/EWR -> revenue`;
- realistic `CV-R²` bands instead of fantasy thresholds;
- bounded Ridge recalibration;
- sensitivity check via Dirichlet jitter + rank stability.

После перехода на `EWR` validation window должен стартовать заново:
- старые `KPD -> revenue` correlation snapshots не считаются доказательством для `EWR`;
- первые `90` дней после включения нового result-layer трактуются как fresh validation period.

## 4. Earned Day

### 4.1 Зачем он нужен
`Earned Day` нужен не как новая форма наказания, а как понятная operational rhythm system.

Он отвечает на вопрос:
"сделал ли менеджер минимально достаточную и корректно зафиксированную работу за этот день?"

### 4.2 Что не должно происходить
- день не должен проваливаться только потому, что телефония ещё не внедрена;
- день не должен проваливаться в выходной, отпуск, force majeure или tech failure;
- система не должна требовать то, чего физически не может измерить.

## 5. Day Status model

### 5.1 Нормативные статусы
- `WORKING`
- `WEEKEND`
- `HOLIDAY`
- `VACATION`
- `SICK`
- `EXCUSED`
- `TECH_FAILURE`
- `FORCE_MAJEURE`

### 5.2 Правила по статусам
- `WORKING` -> DMT активен
- `WEEKEND` -> DMT не проверяется, но действия могут учитываться в weekly context
- `HOLIDAY / VACATION / SICK` -> excused day without punitive logic
- `EXCUSED` -> trust and discipline neutralized for the day
- `TECH_FAILURE` -> punitive checks disabled
- `FORCE_MAJEURE` -> system-wide or broad exemption window

Onboarding protection живёт отдельным layer и не должна маскироваться под отпуск/болезнь.

Если действует `ForceMajeureEvent`, он становится source of truth, а конкретная daily-marking стратегия (`TECH_FAILURE` или `FORCE_MAJEURE`) остаётся производным operational выбором.

## 6. Phase-aware DMT

### 6.1 Phase 0, без телефонии
Минимум на earned day:
- `>=5` CRM contacts;
- `>=1` meaningful CRM update;
- daily report submitted or valid exception.

### 6.2 Phase 1+, с телефонией
К Phase 0 conditions добавляется:
- `>=2` meaningful calls `>30s`.

### 6.3 Дополнительные guards
- no tech-failure day punishment;
- no weekend punishment;
- no frozen-review auto-fail without explicit reason.

## 7. Earned Day ledger

### 7.1 Что хранить
- manager;
- date;
- day status;
- DMT result;
- reason for fail if any;
- override / review info;
- recovery notes;
- payout relevance if day affected money-sensitive logic.

### 7.2 Recovery-first rules
- partial recovery and explanations are allowed;
- data-integrity errors are appealable;
- repeated misses may escalate, but one failed day should not create payroll shock.

## 8. Progressive escalation

### 8.1 Нормальный контур
- first miss -> manager-visible explanation;
- repeated miss -> manager + admin attention;
- pattern of misses -> structured review.

### 8.2 Что запрещено
- automatic hard payroll collapse after one weak day;
- hidden freeze without visible reason;
- mixing data error with performance failure.

## 9. Freeze, Red Card, appeals

### 9.1 Freeze logic
Freeze разрешён только when explicitly triggered:
- payout review;
- fraud suspicion;
- data-integrity investigation.

### 9.2 Red Card
`Red Card` — это review/freeze protocol:
- freeze score-sensitive and payout-sensitive automation;
- not automatic trust annihilation;
- explicit admin reason;
- visible status for manager.

### 9.3 Appeals
Appeals делятся на:
- scoring dispute;
- data-integrity dispute;
- payout dispute.

Data-integrity appeals не должны быть ограничены так же жёстко, как обычные performance appeals.

### 9.4 Appeal record
Каждый appeal должен хранить:
- affected period / entity;
- appeal type;
- manager reason;
- linked evidence;
- admin resolution;
- resolved_at / resolved_by.

## 10. Admin-only economics insights

### 10.1 Что полезно видеть
- какой share repeat revenue держит систему;
- сколько стоит rescue effort;
- у каких managers score растёт без денег, а у каких деньги растут без score;
- где повторная комиссия завязана на unhealthy portfolio concentration.
- кто застрял ниже break-even despite nominal activity;
- где прогноз payback уходит вправо из-за weak follow-up discipline.
- где weighted pipeline выглядит сильным, но фактическая конверсия не подтверждает optimism;
- где optional workload consistency diagnostic показывает перегрузку или неравномерный ритм работы.

### 10.2 Что нельзя делать
- нельзя интерпретировать admin-only correlation как instant production policy;
- нельзя превращать explanatory analytics в silent payout rule.

## 11. Связь с payout flows
Current payout flows already exist in code. Новый слой должен:
- усиливать explainability;
- раскладывать выплаты на части;
- хранить cause-of-adjustment;
- не ломать текущие approve/reject/paid APIs.

## 12. Приземление в текущий код

### 12.1 Основные зоны
- `management/models.py`: payout models, activity models, future day-ledger/snapshot models
- `management/views.py`: payout request flow, admin approve/reject/paid, manual create and adjust
- `management/templates/management/payouts.html` и `admin.html`

### 12.2 Что нужно будет добавить
- explicit day-ledger model or extension;
- `NightlyScoreSnapshot`;
- optional freeze / review metadata on payout-sensitive entities;
- richer admin economics payload in stats/admin views.

### 12.3 Что нельзя делать
- нельзя делать Earned Day зависимым от ещё не внедрённой телефонии;
- нельзя путать admin economics с payroll truth;
- нельзя включать скрытые наказания без audit trail и visible reasoning.
