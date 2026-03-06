# Implementation Roadmap

## 1. Принцип внедрения

Брать весь объём сразу в production нельзя.
Здесь Codex был прав: нужен rollout c shadow mode и feature flags.

Текущий стек это позволяет:
- `Django 5.2.x`,
- `Celery`,
- `Redis`,
- уже существующие модели management app,
- уже существующие reminder и stats pieces.

## 2. Phase 0: freeze decisions

Зафиксировать:
- score formula,
- KPI rules,
- ownership rules,
- duplicate levels,
- reminder ladder,
- QA rubric,
- role visibility.

Выход:
- этот пакет становится source of truth.

## 3. Phase 1: data foundation

### Сделать
- добавить identity layer,
- добавить interaction attempt layer,
- добавить daily score snapshot model,
- добавить QA review entities,
- добавить ownership transfer log,
- добавить follow-up escalation log.

### Технические правила
- использовать `UniqueConstraint` и индексы на lookup-heavy поля,
- использовать `JSONField` только для snapshot/breakdown, не как замену нормальной модели,
- каждый manual override логировать.

## 4. Phase 2: duplicate and callback engine

### Сделать
- duplicate pre-check API,
- create-or-append flow,
- follow-up ladder,
- shop contact cadence,
- dedupe keys для reminders,
- admin queues.

### Celery правила
- один `beat`,
- overlap-sensitive jobs под lock,
- задачи идемпотентны,
- повторный запуск не создаёт дубликаты уведомлений.

## 5. Phase 3: MOSAIC shadow mode

### Что считать
- daily manager score,
- admin score,
- portfolio health,
- source fairness,
- trust.

### Что пока НЕ делать
- не менять зарплату автоматически,
- не менять leaderboard публично,
- не применять penalties в production flow.

### Цель
Сначала проверить:
- понятность score,
- устойчивость формулы,
- отсутствие ложных провалов,
- поведение на cold B2B данных.

## 6. Phase 4: dashboards and report UX

### Сделать
- manager action console,
- admin action center,
- heatmap,
- salary simulator,
- no-touch report,
- explainability blocks.

### Acceptance
- менеджер понимает, что делать дальше,
- админ видит риски без спама,
- отчёты и worklists реально начинают использоваться.

## 7. Phase 5: payroll and KPI activation

### Сделать
- dual KPI engine,
- accelerator logic,
- portfolio health impact,
- admin review ladder,
- payroll preview mode,
- payroll final mode.

### Ограничение
Штрафы и harsh consequences только после:
- shadow validation,
- обучения менеджеров,
- письменной фиксации правил.

## 8. Phase 6: telephony and QA

### Сделать
- provider integration,
- webhooks,
- recordings,
- post-call outcome modal,
- QA scorecard,
- supervisor view,
- calibration workflow.

### После стабилизации
- trust recalibration,
- verified call weighting,
- coaching prompts,
- top-hour analytics.

## 9. Phase 7: AI advice and advanced coaching

Только после качественных данных.

### Сделать
- next best action,
- at-risk client nudges,
- golden hour recommendations,
- objection coaching,
- low-quality pattern detection.

AI без хорошего verified data сначала будет просто красиво ошибаться.

## 10. Phase 8: DTF bridge

DTF подключать как:
- `read-only`,
- отдельную вкладку,
- отдельные summary cards,
- без смешивания raw metrics в core management score.

DTF нужен как управленческий обзор, не как причина ломать brand management core.

## 11. Release safeguards

Обязательные safeguards:
- feature flags,
- rollback path,
- backup before schema migrations,
- backfill plan,
- reindex windows,
- alert on job duplication,
- audit sampling.

## 12. Метрики rollout success

- duplicate rate down,
- callback SLA up,
- report compliance up,
- repeat order share up,
- portfolio health up,
- admin review time down,
- false alert volume down,
- manager complaint rate about “unfair score” down.

Если эти метрики не улучшаются, внедрение считается неполным даже при красивом UI.
