# UI, UX and Management Console

## 1. Принцип

Management UI не должен быть “красивой статистикой”.
Он должен:
- показывать следующее лучшее действие,
- удерживать внимание на деньгах, клиентах и рисках,
- уменьшать трение,
- делать систему объяснимой,
- быть usable и на desktop, и на телефоне.

## 2. Что изменено после Opus-аудита

После аудита я добавил:
- mobile-first manager worklist spec,
- accessibility and states,
- progressive onboarding,
- real-time updates как optional later phase,
- более конкретный UI contract для admin and QA,
- anonymous peer benchmarks без токсичного leaderboard,
- communication timeline,
- contextual help and recovery-first copy rules,
- power-user shortcuts для admin.

## 3. Manager console

### 3.1 Верхний ряд
- `MOSAIC score today`
- `week KPI progress`
- `portfolio health`
- `current earnings`
- `callbacks due today`

### 3.2 Today Action Stack
Сортировка теперь должна учитывать не только просрочку, но и value-priority.

В верхних позициях:
1. overdue high-value callbacks,
2. rescue portfolio clients,
3. warm leads without next action,
4. duplicate/ownership resolutions,
5. calls flagged for QA follow-up.

### 3.3 Portfolio block
Идею `Tamagotchi` сохраняем, но в production-safe форме:
- живые клиентские карточки,
- цвет здоровья,
- маркер упущенных денег,
- один ясный next step.

### 3.4 Salary simulator
Сохраняем и усиливаем:
- new paid order impact,
- repeat order impact,
- reactivation impact,
- gross/net preview,
- what unlocks accelerator.

### 3.5 Heatmap and Golden Hour
На manager screen:
- monthly heatmap,
- top hours,
- trend,
- reason-quality trend,
- callback SLA trend,
- micro-feedback stream.

### 3.6 Advisory cards
Менеджер должен видеть не абстрактные “советы от ИИ”, а короткие evidence-cards:
- `conversion efficiency vs expected`,
- `response latency`,
- `portfolio churn risk`,
- `report integrity warnings`,
- `next best action`,
- `anonymous team median vs your level`.

Правило:
- один card = одна проблема + один action,
- не более `3` сильных cards одновременно,
- no generic motivation spam.

## 4. Mobile-first manager spec

Менеджерская работа часто идёт с телефона, поэтому mobile spec нельзя оставлять как “потом”.

### 4.1 Обязательные mobile требования
- bottom navigation,
- one-thumb action buttons,
- callback done/reschedule gestures,
- compact action stack,
- fast add/log flow,
- push-ready notification surface.

### 4.2 Что должно работать first-class на mobile
- today action stack,
- callback handling,
- quick call logging,
- portfolio rescue actions,
- no-touch report confirm,
- earnings snapshot.

PWA можно рассматривать как Phase-2 enhancement, но mobile-first worklist обязателен сразу.

## 5. Admin console

### 5.1 Верхний ряд
- team score snapshot,
- no-report count,
- QA risk count,
- duplicate queue,
- payroll risk count,
- portfolio churn risk.

### 5.2 Control center
Нужны отдельные очереди:
- `Coaching Needed`
- `QA Reviews`
- `Duplicate/Ownership Reviews`
- `KPI Breach`
- `Rescue/Reassign Candidates`

### 5.3 Team analytics
- team heatmap,
- source mix performance,
- conversion funnel,
- portfolio health by manager,
- payback and ROI,
- telephony quality.

### 5.4 Power-user admin features
Для admin нужны рабочие ускорители, а не только красивые таблицы:
- keyboard shortcuts,
- saved filters,
- queue presets,
- multi-select actions where safe,
- contextual evidence drawer.

## 6. QA / Supervisor console

Это отдельный режим, а не вкладка “где-то у админа”.

Нужны:
- live queue,
- recording player,
- scorecard panel,
- calibration mode,
- disagreement flag,
- outcome mismatch flag,
- coaching note and follow-up task.

## 7. Progressive onboarding

Система сложная. Новый менеджер не должен видеть сразу всё.

### 7.1 Режим раскрытия
- Day `1-3`: Action Stack + basic score + callback queue.
- Day `4-7`: + portfolio block + salary simulator.
- Day `8-14`: + heatmap + trend cards.
- Day `15+`: + achievements, seasonal ladder, deeper analytics.

Это уменьшает перегрузку и ускоряет adoption.

## 8. Client communication timeline

Для карточки клиента нужен единый timeline:
- звонки,
- email/CP,
- CRM notes,
- follow-ups,
- invoices/orders,
- ownership changes,
- QA flags when relevant.

Это снижает потерю контекста перед касанием и повышает качество следующего шага.

## 9. States and reliability

UI обязан описывать не только happy path.

Нужны states:
- loading,
- empty,
- partial data,
- error,
- offline/retrying.

Manager и admin не должны видеть blank blocks без объяснения.

## 10. Copy rules and contextual help

Нельзя строить интерфейс на shame-копирайте.

Финальные правила:
- показывать путь восстановления, а не только просадку,
- формулировать проблемы через actionability,
- избегать survivalist / humiliation wording,
- glossary и tooltip должны объяснять метрики простым языком,
- contextual help должен быть встроен рядом со сложной метрикой, а не спрятан в wiki.

Пример:
- вместо `ты потерял 8 баллов`
- писать `до вашего лучшего уровня не хватает: callbacks (+4), rescue actions (+2), clean reports (+2)`.

## 11. Accessibility and theme readiness

Нужны:
- contrast-safe colors,
- icon + color, а не только red/green,
- touch targets `>= 44x44`,
- keyboard navigation for admin,
- screen-reader-safe labels,
- light/dark/system readiness.

Это не “украшение”, а часть рабочего качества интерфейса.

## 12. Anonymous benchmarking

Чтобы у менеджера была точка сравнения без токсичности:
- показываем `ваше значение`,
- `медиану команды`,
- `верхний квартиль`,
- и `ваш тренд`.

Не показываем:
- публичный shame ranking,
- bottom-list,
- унижающие ярлыки.

## 13. Real-time updates

Real-time updates нужны, но не в первой фазе.

Финальное решение:
- real-time leaderboard and queue nudges only after score engine stabilized,
- transport = SSE or WebSocket only if monitoring shows real need,
- initial product can live on frequent targeted refresh without premature infra complexity.

## 14. Что из Gemini берём, но ослабляем

### Берём
- portfolio health metaphor,
- salary simulator,
- golden hour,
- no-touch report,
- shadow rival.

### Не берём в сыром виде
- `Shark Pool`,
- `Doomsday Screen`,
- public shame,
- survivalist copy.

## 15. What must never be lost

- explainability,
- clear next actions,
- portfolio visibility,
- supervisor visibility,
- separation of manager/admin/private finance,
- mobile-usable manager worklists,
- desktop-optimized admin and QA views,
- recovery-first copy,
- one-client one-timeline context.
