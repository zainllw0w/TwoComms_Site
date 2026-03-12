# Payroll, KPI and Client Portfolio

## 1. Роль этого файла
Этот документ фиксирует production-safe логику:
- KPI;
- зарплаты;
- repeat/new commission;
- portfolio health;
- ownership и retention;
- Earned Day / DMT;
- manager/admin surfaces вокруг денег и дисциплины.

Главный принцип: payroll-контур должен усиливать правильное поведение, а не делать систему карательной и хрупкой.

## 2. Неподвижные инварианты
- `2.5%` на первый заказ остаётся ядром мотивации.
- `5%` на повторный заказ остаётся ядром удержания и качества портфеля.
- verified money truth важнее любых вспомогательных score-метрик.
- KPI не могут противоречить реальной конверсии холодной базы.
- любой денежный штраф должен быть ограниченным, объяснимым и восстановимым.

## 3. KPI operating model

### 3.1 Operating modes

| Mode | Min daily contacts | Target contacts | New paid / week | Total orders / week |
|---|---:|---:|---:|---:|
| `TESTING` | 10 | 20 | 1 | 1 |
| `NORMAL` | 15 | 35 | 1 | 2 |
| `HARDCORE` | 20 | 50 | 2 | 3 |

Обоснование:
- при конверсии около `2.48%` требование `>=2 new/week` как universal default слишком агрессивно;
- разделение на `new paid` и `total orders` реалистичнее для текущего mix между новыми и повторными;
- `NORMAL` режим должен быть достижим для стабильного менеджера, а не только для звездного выброса.

### 3.2 Что считаем meaningful contact

Phase 0, без телефонии:
- CRM-лог контакта;
- изменение статуса, которое подтверждает реальную обработку;
- отправка сообщения / КП / email;
- постановка адекватного next step.

Phase 0 `Omni-Touch` считается как один meaningful contact, если в окне `30 минут` совпали:
- содержательный CRM update;
- outbound message / КП / email;
- зафиксированный next step.

Одинокая заметка без реального outreach не должна считаться meaningful contact. Двойной учёт одного и того же касания запрещён.

Phase 1+, с телефонией:
- meaningful call `>30s`;
- CRM update;
- подтверждённое follow-up действие.

Phase 1+ `Omni-Touch` может считаться через provider-confirmed call `>5s` + CRM update / next step в том же окне, но Phase-0/Payroll-safe DMT всё равно требует отдельного правила для meaningful calls `>30s`.

### 3.3 Базовые daily expectations
- `>=15` cold CRM contacts в `NORMAL`;
- `>=1` meaningful CRM update every working day;
- callback SLA `>=80%` на недельном окне;
- отчёт `on_time` или `late within grace`, но не `missing`.

## 4. Финансовое ядро

### 4.1 Общая структура зарплаты
Боевой payroll состоит из:
- base salary;
- commission за новые заказы;
- commission за повторные заказы;
- ограниченных bonus / spiff / correction entries;
- ручных admin adjustments с audit trail.

### 4.2 New commission
Новая клиентская выручка:
- `2.5%` на первый заказ;
- truth source — invoice/payment/approved admin workflow;
- не зависит от MOSAIC напрямую.

### 4.3 Repeat commission
Повторная выручка:
- базовая ставка `5%`;
- сохранена как главный retention incentive;
- не должна превращаться в источник финансового шока при одном KPI shortfall.

### 4.4 Repeat vs reactivation
Для payroll-safe контура повторные сделки делятся на два класса:
- `Repeat` — тот же клиент, новый заказ в пределах `180 дней` от прошлого оплаченного заказа -> базовая ставка `5.0%`;
- `Reactivation` — тот же клиент, но пауза больше `180 дней` -> базовая ставка `3.5%`.

`Reactivation` не исчезает из мотивации: она остаётся важной для portfolio recovery, accelerator evidence и rescue surfaces. Но она не должна маскироваться под "обычный healthy repeat".

## 5. Soft Floor Cap вместо cliff penalty

### 5.1 Почему cliff запрещён
Если повторная комиссия обваливается с `5%` до `3.5%` на весь оборот, менеджер получает непропорциональный и демотивирующий удар.

При обороте `500 000 грн` это означает потерю `7 500 грн` одним движением. Такая логика противоречит recovery-first модели.

### 5.2 Финальная логика
Используется `Graduated Soft Floor Cap`:
- KPI выполнен -> `5.0%` на весь repeat revenue;
- shortfall `=1` -> `4.5%` на первые `120 000 грн`, далее `5.0%`;
- shortfall `>=2` -> `3.5%` на первые `120 000 грн`, далее `5.0%`.

Эта логика применяется к `active repeat revenue`, то есть к повторным заказам внутри окна `<=180 дней`. Reactivation revenue остаётся отдельным классом с собственной базовой ставкой.

### 5.3 Нормативная формула
```python
def compute_repeat_commission(
    repeat_revenue: float,
    new_clients_this_week: int,
    *,
    target_new_clients: int = 1,
) -> float:
    base_rate = 0.05
    cap_amount = 120_000
    shortfall = max(0, target_new_clients - new_clients_this_week)

    if shortfall == 0:
        return round(repeat_revenue * base_rate, 2)

    penalty_rate = 0.045 if shortfall == 1 else 0.035
    penalized = min(repeat_revenue, cap_amount)
    regular = max(0, repeat_revenue - cap_amount)

    return round(penalized * penalty_rate + regular * base_rate, 2)
```

Примечание:
- `target_new_clients` зависит от operating mode;
- максимальная потеря должна оставаться ограниченной и заранее понятной менеджеру.

## 6. Accelerator и bounded bonuses

### 6.1 Repeat accelerator
Accelerator допустим только как bounded incentive.

Нормативная eligibility-логика:

```python
accelerator_eligible = (
    portfolio_health >= 70
    and callback_sla >= 0.85
    and critical_complaints == 0
    and (repeat_share >= 0.30 or successful_reactivations >= 2)
)
```

Если QA уже `ACTIVE`, добавляется условие `qa_avg >= 80`.

Если QA ещё `DORMANT`, QA-condition заменяется на `report_integrity >= 0.70` / `data_integrity` fallback.

### 6.2 Portfolio bonus
Вне commission допускается небольшой score bonus за качественную реактивацию:
- bounded;
- не заменяет деньги;
- проходит через `dampener`;
- не должен награждать хаотичный rescue without discipline.

## 7. Portfolio Health

### 7.1 Default thresholds

| State | Days since expected order |
|---|---:|
| `Healthy` | 0-35 |
| `Watch` | 35-55 |
| `Risk` | 55-75 |
| `Rescue` | 75+ |

### 7.2 Dynamic thresholds
Индивидуальные пороги разрешены только если у клиента накоплено минимум `5` исторических заказов.

Иначе используется default matrix above.

### 7.3 Что влияет на portfolio health
- days since last order;
- expected next order;
- повторные касания и их качество;
- client snooze;
- seasonality only when it becomes ACTIVE;
- reactivation success, но не как единственный фактор.

Если `expected_next_order` явно находится в будущем и зафиксирован как planned gap, система не должна преждевременно тащить клиента в `Risk/Rescue`.

### 7.4 Client Snooze
`Client Snooze` обязателен как guardrail:
- отпуск клиента;
- сезонная пауза;
- временный stop due to logistics / renovation / relocation.

Snooze:
- не должен silently скрывать клиента навсегда;
- должен иметь reason и срок;
- после длинной паузы требует admin review.
- по умолчанию ограничен `30` днями в год на клиента;
- после `14` суммарных дней требует явного admin approval;
- по окончании snooze возвращает клиента в обычный health/follow-up контур без потери audit trail.

## 8. Ownership и disputes

### 8.1 Базовое правило
Ownership не должен превращаться в свободную охоту на базу.

Финальная логика:
- ownership начинается с автора / закреплённого менеджера;
- rescue/reassign возможен только по правилу;
- любые спорные кейсы идут через audit log и admin resolution.

### 8.2 Что запрещено
- automatic shark-pool без логов;
- немедленное изъятие клиента за единичный weak week;
- скрытая переклейка ownership ради commission capture.

### 8.3 Single-manager-safe режим
Когда почти весь портфель фактически ведёт один менеджер, comparisons и reassign decisions должны быть особенно осторожными:
- default = сохранить ownership;
- rescue logic only after repeated silence or explicit admin action;
- admin-created test data must not засорять боевой портфель.

## 9. Earned Day и DMT

### 9.1 Зачем это нужно
`Earned Day` и `DMT` нужны как ритм дисциплины, но не должны ломаться о отсутствие телефонии или о нерабочие дни.

### 9.2 DayStatus enum
Нормативно фиксируются следующие статусы дня:
- `WORKING`
- `WEEKEND`
- `HOLIDAY`
- `VACATION`
- `SICK`
- `EXCUSED`
- `TECH_FAILURE`
- `FORCE_MAJEURE`

`ONBOARDING` не должен смешиваться с day absence. Для onboarding используется отдельная protection-layer логика поверх `WORKING` дня.

### 9.3 Phase-aware DMT
Phase 0, без телефонии:
- `>=5` CRM contacts;
- `>=1` CRM update;
- report submitted or valid exception.

Phase 1+, с телефонией:
- Phase 0 rules stay;
- дополнительно `>=2 meaningful calls >30s`.

### 9.4 Earned Day ledger
День считается `earned`, если:
- DMT выполнен для данного phase;
- нет критического нарушения дисциплины;
- нет frozen fraud review.

День не должен считаться проваленным автоматически, если статус дня:
- `WEEKEND`
- `EXCUSED`
- `TECH_FAILURE`
- `FORCE_MAJEURE`

### 9.5 Recovery logic
Система должна поддерживать восстановление:
- partial streak recovery;
- explicit reason capture;
- понятное объяснение, что именно не добрал менеджер до earned-state;
- appeals для data-integrity ошибок.

## 10. Weekly and monthly interpretation
- KPI оцениваются прежде всего на weekly окне;
- payroll decisions опираются на agreed payroll period, а не на one bad day;
- daily logic нужна для дисциплины и hints, а не для хаотичных денежных качелей.

## 11. Manager и admin surfaces

### 11.1 Что должен видеть менеджер
- текущие new/repeat accruals;
- раздельное `repeat vs reactivation` начисление;
- expected payout window;
- salary simulator / what-if;
- shadow-mode `hold harmless` delta, если новая логика дала бы менеджеру больше, чем текущая;
- KPI status by `new` and `total`;
- portfolio health distribution;
- earn-day explanation;
- freeze / review reason if any financial item is paused.

### 11.2 Что должен видеть админ
- accrual decomposition by manager;
- requests, approvals, rejections and paid states;
- DMT / earned-day ledger;
- portfolio risk and reactivation queues;
- manual adjustments with audit trail;
- score-to-money correlation in admin-only mode.

## 12. Границы automation
- score не должен автоматически списывать деньги без explainability;
- any freeze must be reviewable;
- manual payout / adjustment actions must remain explicit admin actions;
- payroll math must continue to respect verified order truth over shadow score.

## 13. Приземление в текущий код

### 13.1 Основные модели
- `management/models.py`: `Client`, `Report`, `ManagerCommissionAccrual`, `ManagerPayoutRequest`, payout-related models;
- `management/views.py`: payout request flow, admin approve/reject/paid, manual create and adjust;
- `management/templates/management/payouts.html` и `admin.html`: surfaces для выплат и accrual visibility.

### 13.2 Что нужно будет добавить
- `is_test` на `Client`;
- optional day-status model / ledger;
- optional snooze model;
- snapshot fields или отдельные models для score-to-money validation;
- more explicit payout decomposition APIs if the UI grows.

### 13.3 Что нельзя делать
- нельзя переводить payroll truth исключительно на score;
- нельзя включать жесткую телефонию-зависимую дисциплину до появления телефонии;
- нельзя внедрять cliff penalties.
