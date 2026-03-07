# Payroll, KPI and Client Portfolio

## 1. Финансовое ядро

Сохраняем сильнейшую бизнес-идею из всего корпуса документов:
- `15 000 грн` базовой ставки,
- `2.5%` за первый оплаченный заказ,
- `5.0%` за повторный оплаченный заказ.

Это остаётся сердцем TwoComms-модели.

## 2. Что изменено после Opus-аудита

После аудита я:
- зафиксировал числовые KPI defaults,
- зафиксировал `Stage B = 14 рабочих дней`,
- формализовал accelerator,
- определил `meaningful contact`,
- добавил dispute workflow,
- добавил gross/net preview,
- уточнил portfolio cadence для fashion wholesale.

## 3. Dual probation

### 3.1 Stage A
`5 рабочих дней`

Цель:
- понять, способен ли человек работать дисциплинированно,
- не абузит ли CRM,
- умеет ли корректно вести follow-up,
- способен ли создавать осмысленный progressing pipeline.

### 3.2 Stage B
`14 рабочих дней`

Фиксирую жёстко, без размытых `10-14`.

Цель:
- увидеть реальный коммерческий ритм,
- оценить fairness по источникам,
- увидеть первые verified milestones,
- дать шанс cold B2B циклу проявиться без искусственного давления.

## 4. KPI operating modes

Все numbers ниже — стартовые presets. Их изменение допускается только через admin preset layer и журнал изменений.

| Mode | Daily meaningful contacts | Weekly new paid clients | Callback SLA | Report compliance | Duplicate abuse ceiling |
|---|---:|---:|---:|---:|---:|
| `TESTING` | `20` | `1` | `80%` | `85%` | `< 5%` |
| `NORMAL` | `35` | `2` | `85%` | `90%` | `< 3%` |
| `HARDCORE` | `50` | `3` | `90%` | `95%` | `< 2%` |

Для TwoComms по умолчанию:
- probation = `TESTING`,
- стандартный рабочий режим = `NORMAL`,
- `HARDCORE` включать только вручную, когда команда и рынок это оправдывают.

## 5. Что такое meaningful contact

Это больше не абстрактное понятие.

`Meaningful contact` считается только если выполнено хотя бы одно:
- answered call `>= 30 секунд`,
- клиент ответил в мессенджере или email,
- создана осмысленная `ShopCommunication`,
- есть confirmed callback completion,
- есть verified pipeline move,
- есть оплата или invoice approval milestone.

Простой miss, click или пустой status в это не входят.

## 6. KPI stack

### 6.1 Daily soft KPI
- meaningful contacts,
- callback SLA,
- data quality,
- report compliance,
- verified progress,
- low duplicate abuse,
- отсутствие систематического regression.

### 6.2 Weekly hard KPI
- новые оплаченные подключения,
- rescue/reactivation success,
- pipeline continuity,
- отсутствие критичного хвоста по callback и stale shops.

### 6.3 Monthly operating KPI
- revenue contribution,
- repeat share,
- portfolio health,
- QA quality,
- payback ratio,
- incident-free discipline.

## 7. Базовые требования менеджера

Менеджер считается выполняющим базовые требования месяца только если одновременно:
- report compliance `>= 90%`,
- callback on-time rate `>= 85%`,
- duplicate abuse rate `< 3%`,
- critical duplicate flags = `0`,
- critical QA incidents = `0`,
- rolling MOSAIC не находится длительно в red zone,
- есть подтверждённый объём meaningful работы.

## 8. Зарплатная модель

### 8.1 Формула
`monthly_total = base + first_order_commission + repeat_commission + repeat_accelerator - admin_verified_penalties`

### 8.2 Repeat accelerator
Теперь фиксирую жёстко:
- accelerator = `+0.5%` к repeat commission rate на следующий расчётный месяц.

То есть:
- стандартный repeat = `5.0%`,
- accelerated repeat = `5.5%`.

### 8.3 Условия accelerator
Менеджер получает accelerator только если одновременно:
- `portfolio_health >= 70`,
- `qa_avg >= 80`,
- `callback_sla >= 85%`,
- `critical_complaints = 0`,
- и выполнено одно из двух:
- `repeat_share >= 30%`,
- или `successful_reactivations >= 2` за месяц.

## 9. Gross / Net preview

В salary simulator нужно показывать не только начислено, но и:
- gross,
- expected deductions,
- estimated net.

Важно:
- gross/net не влияет на MOSAIC,
- это отдельный payroll UI layer,
- режим зависит от формы сотрудничества и хранится в профиле менеджера.

## 10. Commission dispute workflow

Это важное практическое усиление из Opus-аудита.

### 10.1 Flow
1. Менеджер нажимает `оспорить комиссию`.
2. Выбирает reason.
3. Спор идёт в admin review queue.
4. Админ видит:
- interaction log,
- CP log,
- call history,
- invoice chain,
- ownership history.
5. Решение:
- подтвердить,
- отклонить,
- split,
- reassign.
6. Всё логируется в audit trail.

## 11. Portfolio health

### 11.1 Базовые состояния
- `Healthy`
- `Watch`
- `Risk`
- `Rescue`
- `Reassign Eligible`

### 11.2 Fashion wholesale cadence
Для TwoComms по умолчанию используем:

| State | Days since meaningful contact |
|---|---:|
| `Healthy` | `0-21` |
| `Watch` | `22-35` |
| `Risk` | `36-45` |
| `Rescue` | `46-60` |
| `Reassign Eligible` | `61+` и/или repeated breaches |

### 11.3 Seasonal buyer modifier
Для сезонных клиентов применяем modifier, а не тупой единый cutoff.

Например:
- зимняя сезонная база не должна автоматически считаться `Risk` только потому, что летом у неё нет движения.

## 12. Ownership policy

Автоматическую кражу базы не включаем.

Финальное правило:
- reassign возможен только по сроку + сигналам neglect,
- ownership change логируется,
- спор уходит админу,
- rollback возможен в установленное окно.

## 13. Consequence ladder

### 13.1 Нормальная лестница
1. Первая KPI-просадка — coaching plan.
2. Вторая подряд — supervised review.
3. Третья подряд — решение по роли, ставке, очереди лидов или условиям работы.

### 13.2 Жёсткие меры
Только если есть:
- доказанный обман,
- тяжёлые клиентские жалобы,
- повторная манипуляция системой,
- систематический саботаж после предупреждения.

Это оставляет систему строгой, но не токсичной.

## 14. Что видит менеджер

В зарплатной части UI менеджер должен видеть:
- начислено,
- заморожено,
- что спорное,
- что можно добрать до конца месяца,
- сколько даст reactivation/new paid order/repeat order.

Именно здесь идея `salary simulator` превращается из красивой фичи в реальный управленческий рычаг.

## 15. Что видит админ

Админ видит:
- base vs commission vs penalty,
- repeat share,
- payback,
- portfolio risk,
- disputed commissions,
- кто силён в new business,
- кто силён в retention,
- кто делает вид, что работает.

## 16. Где лежат presets

Стартовые режимы, modifiers и другие конкретные числа сведены в:
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`
