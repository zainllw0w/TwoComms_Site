# Dashboards Spec: Manager vs Admin

## 1. Принцип разделения
Менеджер видит мотивационную и операционную аналитику.
Админ видит контрольную и финансовую аналитику.

## 2. Manager dashboard

### 2.1 Top metrics
1. Daily final manager score.
2. Paid conversions (day/week).
3. Follow-up discipline.
4. Trust level.
5. KPI status (week target progress).

### 2.2 Worklist blocks
1. Due callbacks.
2. Duplicates to resolve.
3. Clients requiring reason completion.
4. Suggested next actions.

### 2.3 Advice panel
1. Evidence-backed recommendations.
2. Comparison vs yesterday and rolling 7-day.
3. Clear "what to do today" block.

## 3. Admin dashboard

### 3.1 Top metrics
1. Final admin score per manager.
2. ROI score and payback.
3. Team ELO ladder.
4. No-report and discipline flags.
5. Incident summary (verified only).

### 3.2 Control views
1. Manager comparison table.
2. Conversion funnel by manager.
3. Trust anomalies and abuse indicators.
4. Payroll impact panel.

### 3.3 Action center
1. Coaching required.
2. KPI breach escalation.
3. Incident review queue.
4. Promotion candidates.

## 4. Visibility matrix
| Метрика | Manager | Admin |
|---|---|---|
| Final manager score | yes | yes |
| Final admin score | no | yes |
| ROI detailed components | no | yes |
| Team comparison ranking | partial | full |
| Incident raw details | no | yes |
| Advice dismissal state | own only | all (supervision) |

## 5. DTF separation in UI
1. Brand tab и DTF tab имеют отдельные summary cards.
2. DTF показатели не участвуют в brand score cards.
3. В cross-view допускаются только reference links и сводный статус.

## 6. UX constraints
1. Admin экран не должен перегружать manager деталями зарплаты и penalties.
2. Manager должен видеть прямую связь "действие -> результат -> совет".
3. Важные алерты отображаются выше decorative charts.
