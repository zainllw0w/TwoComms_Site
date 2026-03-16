# 03. KPI, payroll, portfolio, leave-semantics и Earned Day

## 1. Что здесь уже хорошо в пакете
- сохранены `2.5%` new / `5%` repeat как business invariants;
- cliff penalty заменён на `Soft Floor Cap`;
- есть `repeat vs reactivation` split;
- есть rescue `SPIFF` и portfolio health;
- day statuses расширены;
- DMT phase-aware;
- weekend/force-majeure logic не смешана с onboarding.

Это уже выглядит намного безопаснее, чем типичная “палочная” CRM-логика.

## 2. Главный gap этого слоя
Пакет хорошо описал **какие статусы бывают**, но ещё не до конца формализовал:
- **как weekly KPI и soft-floor должны пересчитываться при неполной доступности менеджера**;
- как вести себя после недели отпуска / болезни / force majeure;
- как учитывать half-day / training day / field day / internal-meeting day;
- как не превратить soft-floor в случайную календарную лотерею.

Именно это я считаю главной доработкой payroll-safe слоя.

## 3. Ключевая рекомендация: ввести `capacity-aware KPI contract`

### 3.1 Что должно появиться
У day-ledger кроме `day_status` нужен ещё один безопасный параметр:
- `capacity_factor` в диапазоне `0.0 .. 1.0`

Примеры:
- `WORKING` = `1.0`
- approved half-day = `0.5`
- training/internal day = `0.4 .. 0.7`
- `WEEKEND / VACATION / SICK / FORCE_MAJEURE / TECH_FAILURE` = `0.0`

Это не ломает current model, а делает её пригодной для реальных сценариев.

### 3.2 Зачем это нужно
Без этого система вынуждена или:
- штрафовать за неполный день как за полный;
- или прятать слишком много кейсов в `EXCUSED`.

Оба варианта ухудшают точность.

## 4. Как я бы перерассчитал KPI и DMT

### 4.1 Weekly KPI proration
```python
def compute_working_factor(capacity_factors: list[float], nominal_workdays: int = 5) -> float:
    usable = sum(max(0.0, min(1.0, x)) for x in capacity_factors)
    return round(usable / max(1, nominal_workdays), 4)
```

```python
effective_contact_target = base_weekly_contact_target * working_factor
effective_new_target = base_weekly_new_target * working_factor
effective_total_orders_target = base_total_orders_target * working_factor
```

Практический смысл:
- неделя с 2 днями отпуска не должна требовать те же weekly targets, что полная;
- soft-floor и KPI должны видеть одну и ту же proration-реальность;
- это особенно важно для small-team B2B, где один отсутствующий день сильно искажает картину.

### 4.2 Phase-0 DMT тоже должен знать capacity
```python
effective_dmt_contacts = max(1, math.ceil(5 * capacity_factor))
effective_dmt_updates = 1 if capacity_factor >= 0.5 else 0
```

Это безопаснее, чем force-ить одинаковый минимум на любой рабочий день.

## 5. Reintegration mode после длинного отсутствия
Сейчас пакет разделяет onboarding и leave, и это правильно.
Но после:
- `VACATION >= 5` рабочих дней,
- `SICK >= 5` рабочих дней,
- `FORCE_MAJEURE >= 3` рабочих дней,

нужен **reintegration buffer**, а не мгновенное возвращение к полному KPI.

### Рекомендация
- первые `2` рабочих дня после возврата -> `capacity_factor = 0.6`
- следующие `3` рабочих дня -> `capacity_factor = 0.8`
- затем normal mode

Это не “поблажка”, а защита качества метрик.

## 6. Soft Floor Cap: что ещё стоит улучшить

### 6.1 Главный остаточный риск
Soft-floor уже сильно лучше cliff penalty, но пока остаётся чувствительным к календарной границе недели.

Например:
- один verified new order в понедельник vs в пятницу
- неделя с праздником vs обычная неделя
- отпуск по средам и четвергам

Если это не формализовать, менеджер может получить разный repeat impact при одинаковом качестве работы.

### 6.2 Что улучшить безопасно
- считать eligibility для soft-floor по **working-factor-adjusted weekly target**;
- считать shortfall в виде progress ratio, а не только absolute count;
- для payroll-adjacent explainability хранить `shortfall_reason`:
  - low verified new business
  - low working capacity week
  - freeze/review week
  - force majeure adjusted week

## 7. Portfolio layer: что стоит усилить

### 7.1 Manual cadence classes для low-history клиентов
Сейчас dynamic thresholds разрешены только с `>=5` заказами.
Это правильно.
Но между “полностью дефолтный клиент” и “полностью персонализированный Weibull” нужна промежуточная ступень:

- `weekly`
- `biweekly`
- `monthly`
- `seasonal`
- `project-based`

Это не production payroll truth, а operational helper для:
- expected next order;
- snooze semantics;
- rescue false-positive reduction.

### 7.2 Planned-gap contract
Нужно отдельно хранить:
- `planned_gap_reason`
- `planned_gap_until`
- `approved_by`
- `confidence`

Иначе `expected_next_order` будет слишком “магическим” полем.

### 7.3 Rescue attribution trail
Для `SPIFF` и fairness нужен явный объект или payload:
- когда клиент попал в rescue queue;
- по какому rule;
- кто был owner;
- кто сделал rescue-touch;
- какой touch считается decisive;
- почему начислен `SPIFF`.

## 8. Earned Day: где его стоит сделать ещё справедливее

### 8.1 Развести три уровня, а не один
Сейчас у пакета есть earned/not-earned логика.
Я рекомендую добавить UI и admin-layer distinction:
- `Minimum achieved` — DMT minimum covered
- `Target pace achieved` — KPI pace healthy
- `Recovery needed` — below minimum or integrity issue

Это нужно, чтобы менеджер не начал жить по правилу “сделал 5 контактов -> день хороший”.

### 8.2 Разделить performance miss и data-integrity miss
Даже если оба влияют на earned-state, recovery path должен быть разным:
- `performance_gap`
- `reporting_gap`
- `system_gap`

Иначе appeals будут путать реальную дисциплину и технические ошибки.

## 9. Appeal SLA и payout freeze semantics
Пакет уже ввёл appeals, и это сильное решение.
Я бы усилил его через SLA:
- scoring appeal -> review within `2` working days
- payout dispute -> preliminary response within `1` working day
- frozen payout item -> visible reason immediately
- accepted appeal -> slot restores automatically and recalculation queued

## 10. Наиболее вероятные баги без этих улучшений

### Bug 1 — неделя отпуска будет выглядеть как weak KPI week
Даже если daily days marked correctly, weekly target без proration всё равно создаст скрытую несправедливость.

### Bug 2 — half-day cases уйдут в ручной хаос
Потому что enum status alone не описывает частичную доступность.

### Bug 3 — manager optimizes to DMT minimum
Если в UI не показать distinction между minimum day и target pace.

### Bug 4 — repeat soft-floor станет зависеть от календаря сильнее, чем от сути работы
Если не сделать working-factor adjusted eligibility.

## 11. Что менять в каких файлах
- `03_PAYROLL_KPI_AND_PORTFOLIO.md` — proration, reintegration, target/minimum distinction
- `15_ADMIN_ECONOMICS_AND_EARNED_DAY.md` — ledger details, appeal SLA, gap categories
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md` — new constants: `REINTEGRATION_DAYS`, `CAPACITY_FACTOR_DEFAULTS`
- `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md` — day-ledger and rescue-attribution extensions
- models -> `ManagerDayStatus`, optional `ClientSnoozeStatus`, rescue attribution fields

## 12. Приоритет внедрения
1. weekly KPI proration
2. capacity_factor
3. reintegration mode
4. soft-floor working-factor alignment
5. rescue attribution trail
6. appeal SLA
