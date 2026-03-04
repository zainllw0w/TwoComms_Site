# KPI, Payroll and Unit Economics Spec

## 1. Бизнес-правила
1. Test period: 5 дней.
2. Если не выполнено: разбор + доп. 3 дня.
3. KPI weeks 1-2: минимум 1 подключенный магазин/неделя.
4. KPI week 3+: минимум 2 подключенных магазина/неделя.
5. Подключенным считается только полностью оплаченный клиент.

## 2. Компенсация
- Base salary: 15000 грн/месяц (после test period).
- Commission first paid order: 2.5%.
- Commission repeat paid order: 5.0%.

## 3. KPI framework (Dual)

### 3.1 Weekly hard KPI
Основной контроль: выполнены ли минимальные нормы по подключенным магазинам.

### 3.2 Daily soft KPI
Операционный контроль: эффективность дня (score, дисциплина, обработка, follow-up).

## 4. Payroll model
```python
def calculate_payroll(month_data):
    base = 15000 if month_data.eligible_for_base else 0
    first_commission = month_data.first_paid_turnover * 0.025
    repeat_commission = month_data.repeat_paid_turnover * 0.05
    penalties = month_data.admin_verified_penalties_total
    total = base + first_commission + repeat_commission - penalties
    return max(0, total)
```

## 5. Unit economics model

### 5.1 Inputs
- Revenue attributable to manager.
- Margin coefficient by product mix.
- Salary and commission cost.
- Incident-related loss adjustments (optional admin layer).

### 5.2 Key indicators
1. `payback_ratio = contribution_margin / payroll_cost`
2. `net_contribution = contribution_margin - payroll_cost`
3. `roi_ratio = net_contribution / payroll_cost`

## 6. ROI in score
ROI напрямую добавляется только в admin score (через долю 15%).

Причина:
- Менеджерский score должен оставаться в первую очередь поведенческим инструментом.
- Админский score должен отражать экономическую устойчивость.

## 7. KPI escalation rules
1. Неделя не выполнена -> статус KPI breach.
2. 2 недели подряд breach -> mandatory coaching review.
3. 3 недели подряд breach -> кадровое решение по роли/системе оплаты.

## 8. Promotion readiness
Повышение рассматривается при одновременном выполнении:
1. Stable weekly KPI over rolling window.
2. High trust trajectory.
3. Положительный ROI.
4. Нет критических admin-verified incidents.

## 9. Reporting artifacts
Каждую неделю admin dashboard должен содержать:
1. KPI fact vs target.
2. Подключенные и повторные оплаты.
3. Ставка/комиссии/penalty.
4. ROI summary.
5. Решение: keep, coach, review for promotion.

## 10. Assumptions
- Без записей звонков качество коммуникации оценивается косвенно через outcome discipline.
- Margin коэффициент на старте задается админом в конфиге и корректируется ежемесячно.
