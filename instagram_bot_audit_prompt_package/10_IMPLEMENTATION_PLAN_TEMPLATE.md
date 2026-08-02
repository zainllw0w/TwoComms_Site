# IMPLEMENTATION_PLAN — шаблон

## Принципы

Вертикальные проверяемые изменения; task решает ограниченные findings; P0→P1→P2→P3; не объединять migration state machine, UI redesign и provider refactor в один deploy; каждая задача безопасно продолжима другим агентом.

## Сводка

| Task ID | Название | Priority | Findings | Depends on | Risk | Status |
|---|---|---:|---|---|---|---|

## Карточка задачи

### IMP-<NNN>: <название>

- **Priority/Status:**
- **Findings:**
- **Цель:**
- **Не входит:**
- **Dependencies:**
- **Components/files:**
- **Data/schema:**
- **External API:**
- **Feature flags:**
- **Backward compatibility:**
- **Шаги:**
- **Red tests:**
- **Implementation:**
- **Regression tests:**
- **Observability:**
- **Security/privacy:**
- **UX acceptance:**
- **Migration/backfill:**
- **Rollback:**
- **Acceptance criteria:**
- **Docs:**
- **Commit strategy:**
- **Deploy target:**
- **Post-deploy smoke:**
- **Completion evidence:**

## Волны

- Wave 0: baseline, logs, event IDs, test harness, flags, rollback.
- Wave 1: sources of truth, state machines, payment/order/shipment/idempotency.
- Wave 2: context, memory, AI contracts, prompts, multilingual.
- Wave 3: scheduler, suppression, sales and discount rules.
- Wave 4: scoring, event factors, analytics glossary/dashboard.
- Wave 5: client card, order binding, funnel, timers, states, accessibility.
- Wave 6: performance, animation, cleanup, cost optimisation.
