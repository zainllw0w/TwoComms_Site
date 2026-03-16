# Decision Matrix (A/B/C) and Locked Choices

## 1. Цель матрицы
Зафиксировать ключевые развилки архитектуры и бизнес-логики, чтобы исключить повторные дискуссии на этапе имплементации.

## 2. Список принятых решений

### 2.1 Score Gate
- A: Hard gate.
- B: Soft gate.
- C: Weekly-only gate.
- Выбор: A (Hard gate).
- Причина: без оплаченной конверсии система не должна позволять "набить" высокий score за счёт активности.

### 2.2 Trust Layer
- A: Trust coefficient.
- B: Strict verify only.
- C: No trust layer.
- Выбор: A (Trust coefficient).
- Причина: strict-only ломает рабочий процесс без телефонии, no-trust повышает риск абуза.

### 2.3 KPI mode
- A: Dual KPI.
- B: Weekly only.
- C: Daily only.
- Выбор: A (Dual KPI).
- Причина: weekly KPI задает бизнес-результат, daily KPI удерживает ритм работы.

### 2.4 ROI in score
- A: Include in score.
- B: Admin-only metric.
- C: Separate report.
- Выбор: A (Include in score).
- Причина: убыточный менеджер должен быть заметен в оценке, но с ограниченным весом.

### 2.5 Alerts delivery
- A: TG + in-app.
- B: In-app only.
- C: Telegram only.
- Выбор: A (TG + in-app).
- Причина: in-app без push теряет реактивность, TG без UI теряет контекст.

### 2.6 No-report policy
- A: Admin получает no-report флаг.
- B: Никто не получает.
- C: Оба получают.
- Выбор: A.
- Причина: нужен контроль дисциплины без "фиктивного" manager digest.

### 2.7 DTF scope v1
- A: Read-only bridge.
- B: Partial write.
- C: Full control.
- Выбор: A.
- Причина: безопасный старт при возможной отдельной БД dtf и отсутствии cross-DB FK.

### 2.8 Disciplinary layer
- A: Admin-verified only.
- B: Auto from manager data.
- C: Outside scoring.
- Выбор: A.
- Причина: снижение false-positive и злоупотреблений.

## 3. Rejected options log
1. Soft gate отклонен: стимулирует имитацию бурной деятельности.
2. Strict verify only отклонен: текущая операционная среда без call recording не позволит полноценно работать.
3. Full DTF control v1 отклонен: высокий риск архитектурных и ролевых ошибок.

## 4. Locked defaults
- Timezone: Europe/Kiev.
- Daily report baseline deadline: 19:00 local.
- No-answer maximum attempts: 3.
- Manager salary baseline: 15000 грн.
- Commission: 2.5% first, 5% repeat.

## 5. Governance
Любое изменение locked choices требует отдельного RFC в формате:
- Изменяемый пункт матрицы.
- Риски и tradeoffs.
- Влияние на тесты и отчеты.
- План миграции данных/метрик.
