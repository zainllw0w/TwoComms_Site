# Implementation Roadmap

## 1. Принцип внедрения

Нельзя выкатывать такую систему одним куском.
Opus был прав: первой версии roadmap не хватало durations, migration detail и phase-specific rollback.

Текущий стек позволяет реалистичную поэтапную реализацию:
- `Django 5.2.x`,
- `Celery`,
- `Redis`,
- уже существующие management models и stats pieces.

## 2. Phase map with durations

| Phase | Scope | Duration | Team need |
|---|---|---:|---|
| `0` | freeze decisions | `1 неделя` | PO + tech lead |
| `1` | data foundation | `2-3 недели` | backend |
| `2` | duplicate + callback engine | `3-4 недели` | backend + frontend |
| `3` | MOSAIC shadow mode | `2-3 недели` | backend |
| `4` | dashboards + UX | `4-6 недель` | frontend + backend |
| `5` | payroll activation | `2-3 недели` | backend |
| `6` | telephony + QA | `4-6 недель` | backend |
| `7` | AI coaching | `4+ недели` | backend/ML |
| `8` | DTF bridge | `1-2 недели` | backend |

Итог:
- realistic first production wave = `~3-4 месяца`,
- full mature contour = `~6-9 месяцев`.

## 3. Phase 0: freeze decisions

Зафиксировать:
- MOSAIC formula,
- KPI rules,
- ownership rules,
- duplicate levels,
- reminder ladder,
- QA rubric,
- role visibility,
- presets file as single numeric source of truth.

Выход:
- пакет становится canonical spec.

## 4. Phase 1: data foundation

### Сделать
- identity layer,
- interaction attempt layer,
- daily score snapshot model,
- QA review entities,
- ownership transfer log,
- follow-up escalation log,
- central audit log.

### Технические правила
- `UniqueConstraint` и lookup indexes,
- JSON only for snapshots/breakdowns,
- every manual override goes to audit log,
- performance budget must be set before backfill.

## 5. Phase 2: duplicate and callback engine

### Сделать
- duplicate pre-check API,
- create-or-append flow,
- fuzzy suggestion layer,
- merge strategy with rollback window,
- batch import preview,
- reminder ladder,
- admin queues.

### Celery rules
- one `beat`,
- overlap-sensitive jobs under lock,
- idempotent jobs,
- rerun does not duplicate notifications.

## 6. Phase 3: MOSAIC shadow mode

### Что считаем
- daily manager score,
- admin score,
- portfolio health,
- source fairness,
- trust,
- micro-feedback stream,
- comparative seasonal ladder.

### Что НЕ делаем
- не меняем зарплату автоматически,
- не включаем punitive logic,
- не делаем full public ranking,
- не делаем telephony-dependent conclusions.

### Цель
Проверить:
- понятность score,
- устойчивость формулы,
- ложные провалы,
- cold B2B fairness,
- anomaly behaviour,
- admin trust in explanation.

## 7. Phase 4: dashboards and UX

### Сделать
- manager console,
- admin action center,
- QA console shell,
- mobile-first manager worklist,
- heatmap,
- salary simulator,
- no-touch report,
- explicit states.

### Acceptance
- manager sees next best action in `<= 5 секунд`,
- admin sees queues without spam,
- report compliance increases,
- mobile usage does not degrade core workflows.

## 8. Phase 5: payroll and KPI activation

### Сделать
- dual KPI engine,
- accelerator logic,
- payroll preview,
- gross/net display,
- dispute workflow,
- portfolio health impact.

### Ограничение
Жёсткие меры включать только после:
- shadow validation,
- manager onboarding,
- written rules,
- admin workflow rehearsal.

## 9. Phase 6: telephony and QA

### Сделать
- provider integration,
- call webhooks,
- recordings,
- post-call modal,
- QA scorecard,
- supervisor tools,
- calibration workflow,
- IRR checks.

### После стабилизации
- trust recalibration,
- verified call weighting,
- DNA-like analytics only if data quality proves sufficient.

## 10. Phase 7: AI coaching

Только после хорошего verified data:
- next best action,
- at-risk client nudges,
- objection coaching,
- low-quality pattern detection,
- top-hour recommendations.

## 11. Phase 8: DTF bridge

DTF:
- только `read-only`,
- отдельная вкладка,
- отдельные cards,
- не участвует напрямую в wholesale manager score.

## 12. Data migration plan

### 12.1 Backfill order
1. `ManagementLead` and `Client` → `ClientIdentityKey`
2. `ShopPhone` → identity keys
3. historical interactions → `ClientInteractionAttempt`
4. follow-up history → escalation and status normalization
5. initial portfolio health classification

### 12.2 Migration rules
- migration dry-run first,
- compare old counts vs new counts,
- exact duplicate merges previewed before apply,
- rollback script ready before real migration,
- audit all merge actions.

## 13. Rollback criteria by phase

| Signal | Action |
|---|---|
| score explainability rejected by admins | pause score rollout |
| duplicate false positive `> 20%` | relax thresholds |
| reminder complaints `> 3/manager/day` | reduce cadence and rebalance digests |
| p95 API latency `> 500ms` | optimize before next phase |
| QA kappa `< 0.60` | stop score-sensitive QA use |
| manager trust/NPS sharply negative | pause penalties and gather evidence |

## 14. Success metrics

- duplicate rate down,
- callback SLA up,
- report compliance up,
- repeat order share up,
- portfolio health up,
- admin review time down,
- false alert volume down,
- explainability acceptance up,
- manager complaint rate about unfair score down.

## 15. Where the cross-cutting rules live

Numeric presets:
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`

Audit/security/backup/performance rules:
- `13_CROSS_SYSTEM_GUARDRAILS.md`
