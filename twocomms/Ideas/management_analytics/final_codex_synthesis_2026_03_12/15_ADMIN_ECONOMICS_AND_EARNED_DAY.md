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

## 3. Score-to-money validation

### 3.1 Зачем нужно
Нельзя включать новые score-formulas в payroll-adjacent процессы, не понимая, коррелируют ли они хотя бы разумно с фактическими деньгами и verified outcomes.

### 3.2 Какие сигналы сравниваем
- current `KPD`;
- shadow `MOSAIC`;
- `EWR`;
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
- `trust_diagnostic`
- `portfolio_health_pct`
- raw payload for explainability

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
- `EXCUSED`
- `TECH_FAILURE`
- `FORCE_MAJEURE`

### 5.2 Правила по статусам
- `WORKING` -> DMT активен
- `WEEKEND` -> DMT не проверяется, но действия могут учитываться в weekly context
- `EXCUSED` -> trust and discipline neutralized for the day
- `TECH_FAILURE` -> punitive checks disabled
- `FORCE_MAJEURE` -> system-wide or broad exemption window

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

## 10. Admin-only economics insights

### 10.1 Что полезно видеть
- какой share repeat revenue держит систему;
- сколько стоит rescue effort;
- у каких managers score растёт без денег, а у каких деньги растут без score;
- где повторная комиссия завязана на unhealthy portfolio concentration.

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
