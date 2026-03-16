# Hybrid Score Spec (HES + Gate + Trust + ROI + ELO)

## 1. Назначение
Единая формула оценки эффективности менеджера для дневного, недельного и сравнительного анализа.

## 2. Компоненты
1. Base day score: качество работы за день (0..100).
2. Hard gate: ограничение ceiling без конверсий.
3. Trust coefficient: поправка на верифицируемость и дисциплину.
4. ROI component: бизнес-окупаемость.
5. Weekly ELO: стабильный сравнительный рейтинг команды.

## 3. Базовая дневная формула
`base = 0.45*Result + 0.25*Quality + 0.15*Pipeline + 0.15*Discipline`

Оси нормализуются до 0..100.

### 3.1 Result (0..100)
Фокус: hard outcomes.
- Paid conversions/day.
- Revenue/day vs target.
- Repeat paid orders contribution.
- Conversion ratio processed->paid.

### 3.2 Quality (0..100)
Фокус: корректность обработки.
- Not-interested reason completeness.
- Reason diversity and anti-copy patterns.
- Callback completion rate.
- CP linkage correctness.

### 3.3 Pipeline (0..100)
Фокус: движение лида по обязательным этапам.
- Timely follow-up coverage.
- Stalled pipeline percentage.
- Mandatory next-action compliance.

### 3.4 Discipline (0..100)
Фокус: режим исполнения.
- Report discipline (on-time, late, missing).
- Overdue callback penalties.
- Admin-verified incidents (влияние преимущественно в admin score).

## 4. Hard gate
Если:
- `paid_conversions_day >= 1` -> `gate_cap = 100`
- `paid_conversions_day == 0` -> `gate_cap = 60`
- `zero_conversions_streak >= 3 days` -> `gate_cap = 45`

`gated = min(base, gate_cap)`

## 5. Trust coefficient
Диапазон: `0.55..1.05`

### 5.1 Trust inputs
1. Verified action ratio.
2. CP verification ratio (email-log linked).
3. Callback completion consistency.
4. Reason quality score.
5. Suspicious velocity/anomaly score.

### 5.2 Trust formula (v1)
`trust_coeff = clamp(0.55, 1.05, 0.75 + 0.30*verified_ratio + 0.10*reason_quality - 0.15*anomaly_penalty)`

Где:
- `verified_ratio` в диапазоне 0..1.
- `reason_quality` в диапазоне 0..1.
- `anomaly_penalty` в диапазоне 0..1.

## 6. Финальные дневные баллы
`final_manager_day = gated * trust_coeff`

`final_admin_day = 0.85*final_manager_day + 0.15*roi_score`

## 7. ROI score (0..100)
### 7.1 Inputs
- Revenue manager period.
- Contribution margin estimate.
- Salary cost (15000 monthly pro-rata).
- Commission payouts.

### 7.2 Normalization
`roi_ratio = (gross_margin_contrib - payroll_cost) / max(1, payroll_cost)`

`roi_score = normalize(roi_ratio, floor=-0.5, target=0.3, stretch=1.0)`

## 8. Weekly ELO layer
ELO не заменяет дневной score. Он стабилизирует сравнение в команде.

### 8.1 Weekly source
`S_week = normalize(average(final_manager_day_week))`

### 8.2 Expected score
`E = 1 / (1 + 10^((median_team_elo - manager_elo)/400))`

### 8.3 Delta
`delta = K * (S_week - E)`

K-фактор:
- Test period: `K = 32`
- Regular: `K = 20`
- High-stability (senior): `K = 16`

## 9. Псевдокод расчета
```python
def compute_daily_score(inputs):
    base = 0.45*inputs.result + 0.25*inputs.quality + 0.15*inputs.pipeline + 0.15*inputs.discipline

    if inputs.paid_conversions_day >= 1:
        gate_cap = 100
    elif inputs.zero_conversions_streak >= 3:
        gate_cap = 45
    else:
        gate_cap = 60

    gated = min(base, gate_cap)
    trust = clamp(0.55, 1.05, 0.75 + 0.30*inputs.verified_ratio + 0.10*inputs.reason_quality - 0.15*inputs.anomaly_penalty)

    final_manager = gated * trust
    final_admin = 0.85*final_manager + 0.15*inputs.roi_score
    return final_manager, final_admin
```

## 10. Анти-абуз инварианты
1. Без оплаченной конверсии нельзя выйти в high zone.
2. Self-reported активность без verification не компенсирует low trust.
3. Массовые "пустые" статусы и пропущенные callback автоматически снижают результат.

## 11. Сценарии валидации
1. Высокая активность, 0 paid conversion -> capped + lowered trust.
2. Средняя активность, 1 paid conversion, высокий trust -> высокий финальный score.
3. Высокая выручка при 1 крупной сделке -> strong admin score через ROI.
4. Системные нарушения с admin-verified incidents -> admin score проседает сильнее manager score.
