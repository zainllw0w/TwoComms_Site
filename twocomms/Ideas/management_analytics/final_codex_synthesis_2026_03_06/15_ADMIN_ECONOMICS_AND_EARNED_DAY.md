# Admin Economics and Earned Day

## 1. Зачем нужен этот файл

`Opus 4.8` поднял сильную тему:
админу нужен не только score и не только UI, а понятная экономика менеджера и дисциплинарный daily-work contour.

Я принимаю это направление, но разделяю его на две части:
- `Admin Economics Dashboard` как безопасный admin-only BI layer,
- `Earned Day` только в production-safe варианте, без автоматического удержания всей дневной ставки по умолчанию.

## 2. Admin Economics Dashboard

### 2.1 Что видит только админ
Dashboard должен показывать:
- attributed revenue,
- manager direct cost,
- commission cost,
- fixed monthly overhead,
- break-even progress,
- payback speed,
- revenue forecast,
- score confidence,
- score-to-money validation.

Менеджер этого слоя по умолчанию не видит.

### 2.2 Cost model
Базовая admin-модель стоимости менеджера:

`manager_monthly_cost = fixed_salary_component + commissions + workspace_cost + management_overhead + onboarding_amortization`

Важно:
- это admin accounting view,
- эти числа не должны бездумно показываться менеджеру как “ты стоишь столько-то”.

### 2.3 Revenue / contribution model
Нужно быть точным в терминах.

Если в системе есть только revenue и commission, то без данных о марже нельзя честно называть это “прибылью”.

Поэтому по умолчанию использовать:
- `attributed_revenue`,
- `direct_commission_cost`,
- `fixed_manager_cost`,
- `commercial_contribution_proxy = attributed_revenue - direct_commission_cost - fixed_manager_cost`

Если позже появится корректная gross-margin model, можно строить более точный contribution view.

### 2.4 Break-even and payback

Admin должен видеть:
- monthly break-even point,
- current payback progress,
- estimated payback day,
- risk of not reaching break-even by month end.

Это admin-only managerial signal.
Он не должен автоматически менять зарплату менеджера.

### 2.5 Profitability zones
Нужны управленческие зоны:
- `critical under-break-even`,
- `approaching break-even`,
- `break-even reached`,
- `profitable`,
- `highly profitable`.

Но интерпретировать их нужно через `contribution proxy`, а не через наивное “revenue = profit”.

### 2.6 Forecast
Admin dashboard должен показывать:
- optimistic,
- base,
- pessimistic scenario.

Основание:
- current month pace,
- recent trend,
- current weighted pipeline,
- confidence level of the projection.

### 2.7 Score validation
Одна из самых сильных идей `Opus 4.8`: сам MOSAIC должен валидироваться о бизнес-результат, а не жить как красивый абстрактный рейтинг.

Финальное правило:
- после `>= 90` дней shadow или production history считаем связь `rolling MOSAIC ↔ attributed revenue`,
- если зависимость слабая, weights и thresholds нельзя считать “доказанными”.

Стартовая интерпретация:
- `r² < 0.30` = recalibration needed,
- `0.30 <= r² < 0.50` = medium validity,
- `r² >= 0.50` = strong enough for admin confidence.

### 2.8 Score-to-money map
Идею “1 балл = примерно сколько денег” принимаю, но только при guardrails:
- только admin-only,
- только после достаточного исторического окна,
- только с confidence label,
- только по real TwoComms data.

Без этого такой mapping будет притворяться точным, не будучи точным.

### 2.9 Confidence score
Админ должен видеть не только score, но и насколько ему можно верить.

Пример структуры confidence:
- volume of data,
- verified coverage,
- score stability,
- recency,
- sample sufficiency.

Использование:
- кадровые решения нельзя опирать на low-confidence score,
- aggressive action запрещена при confidence ниже agreed threshold.

## 3. Precision admin signals from 4.8

### 3.1 Persistence score
Идея сильная, но не как зарплатная ось.

Принимаю как admin/coaching metric:
- сколько осмысленных попыток делается до конверсии,
- умеет ли менеджер вести длинный B2B цикл,
- как работает с rescue/reactivation.

### 3.2 Daily processing capacity
Принимаю только как admin workload metric.

Не использовать как payroll truth.
Иначе система начнёт награждать volume without quality.

### 3.3 Payback speed
Очень полезный admin metric.

Показывает:
- кто быстро окупается в месяце,
- кто тянет команду вниз,
- где нужен coaching или перераспределение базы.

Это не manager-facing humiliation layer.

## 4. Earned Day: safe variant

## 4.1 Почему идею нельзя брать в сыром виде
Сырой вариант “не заработал день = не платим дневную ставку” опасен:
- юридически,
- культурно,
- мотивационно,
- и operationally при спорных днях.

Поэтому production-safe решение такое:
- идея `Earned Day` принимается,
- но не как дефолтное автоматическое удержание всей дневной base salary.

## 4.2 Что именно принимается
Принимается:
- `Earned Day Ledger`,
- `Daily Minimum Threshold`,
- recovery logic,
- legitimate absence exclusions,
- progressive escalation,
- admin override with audit log.

Не принимается как default:
- автоматическое списание полной дневной ставки,
- необратимое удержание,
- скрытая санкционная механика без review.

## 4.3 Daily Minimum Threshold

`DMT` нужен, чтобы система понимала:
- был ли это реальный рабочий день,
- выполнил ли менеджер минимальную дисциплину,
- есть ли повод для coaching escalation.

Стартовый DMT для standard mode:
- `>= 5` verified meaningful contacts,
- callback completion or clean reschedule `>= 80%`,
- `0` critical abuse flags,
- CRM day not empty,
- no critical duplicate / fake-activity evidence.

Для probation можно использовать сниженный порог.

### 4.4 Earned Day Ledger
Ledger хранит статусы дней:
- `earned`,
- `missed`,
- `recovered`,
- `excused`,
- `manual_override`.

Он нужен для:
- manager transparency,
- admin discipline tracking,
- escalation,
- later payroll policy if business consciously chooses stricter model.

### 4.5 Recovery logic
Если policy активна, missed day не должен быть необратимым default punishment.

Production-safe правило:
- следующий qualified day может закрыть oldest recoverable miss,
- sustained recovery can close more than one suspended day only if policy explicitly allows it,
- every recovery must be auditable.

### 4.6 Legitimate absence rules
DMT не применяется к:
- approved leave,
- holidays,
- documented sick leave,
- confirmed infrastructure incident,
- approved training or offsite day.

### 4.7 Progressive escalation
Если DMT не выполняется подряд:
- `3` дня = coaching alert,
- `5` дней = mandatory admin review,
- `7` дней = policy escalation review.

Но это review flow, а не automatic money cut by default.

## 5. Payroll-safe implementation of Earned Day

### 5.1 Default mode
По умолчанию `Earned Day` влияет на:
- discipline ledger,
- admin review,
- coaching,
- monthly compliance narrative.

И не влияет напрямую на contractual base salary.

### 5.2 Optional stricter mode
Если бизнес сознательно захочет monetary linkage, production-safe варианты только такие:
- `discipline reserve` как отдельная переменная часть fixed pay,
- `earned-day bonus pool`,
- explicit contract/policy wording,
- manager acknowledgment,
- legal review before rollout.

Это допустимо только после:
- shadow testing,
- policy documentation,
- auditability,
- dispute workflow,
- and clear legitimate-absence handling.

### 5.3 What must never happen
- no silent automatic deduction,
- no irreversible same-day punishment,
- no policy activation without written rule,
- no day-loss due to CRM outage or verified operational incident.

## 6. UI contract

### 6.1 Manager view
Manager может видеть:
- earned days count,
- missed days count,
- excused days,
- what to do today to qualify the day,
- whether recovery is available.

Manager не должен видеть:
- raw cost-to-company analytics,
- humiliating loss framing,
- “ты убыточный сотрудник” copy.

### 6.2 Admin view
Admin видит:
- earned / missed / excused / recovered days,
- attributed revenue,
- break-even status,
- confidence score,
- forecast,
- coaching recommendations,
- DMT abuse risk.

## 7. Что принято из Opus 4.8

Принято:
- admin economics dashboard,
- break-even and payback tracking,
- profitability zones,
- forecast scenarios,
- score-to-revenue validation,
- confidence score,
- score-to-money map after enough data,
- persistence and processing metrics as admin-only,
- Earned Day as policy-aware safe variant.

Не принято в сыром виде:
- default withholding of full day-rate from base salary,
- overly simplistic “revenue = profit” framing,
- aggressive manager-facing economic pressure copy.

## 8. Где это влияет на остальные файлы

Связанные документы:
- `03_PAYROLL_KPI_AND_PORTFOLIO.md`
- `06_UI_UX_AND_MANAGER_CONSOLE.md`
- `07_IMPLEMENTATION_ROADMAP.md`
- `09_RESEARCH_QUESTIONS_FOR_DEEP_AGENT.md`
- `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md`
- `14_OPUS_SECOND_PASS_DECISION_LOG.md`
