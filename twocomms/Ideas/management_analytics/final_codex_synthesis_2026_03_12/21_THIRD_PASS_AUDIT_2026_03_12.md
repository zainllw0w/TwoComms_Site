# Third Pass Audit 2026-03-12

## 1. Цель
Этот аудит был сделан после второго прохода, чтобы проверить не только явные большие блоки, но и semantic losses внутри уже переписанных authoritative docs.

Фокус:
- не выпал ли принятый `Weibull` churn из `§37.1`;
- не ослабилась ли rescue economics из `§37.5`;
- не исчезли ли важные validation/diagnostic элементы из `§35`.

## 2. Что реально было найдено

### 2.1 Critical: churn model оказался незафиксированным
После второго прохода пакет ссылался на `P(churn)` и `Expected LTV Loss`, но нигде авторитетно не фиксировал:
- что primary модель = `Weibull`;
- что при `<5` заказах нужен logistic fallback;
- что planned gap через `expected_next_order` должен возвращать near-neutral churn;
- что `k` нужно cap-ить, чтобы не получить overflow / ложную уверенность.

Это было semantic loss, потому что source report принял эту идею явно.

### 2.2 High: rescue economics была недоопределена
`Top-5 rescue` остался в пакете, но:
- scaled `SPIFF (500-2000 грн)` не был зафиксирован;
- не был сохранён guard `max 3 rescue-leads/day`;
- не был сохранён `DQ grace`, чтобы rescue-widget не перегружал менеджера.

### 2.3 Medium: conservative conversion diagnostic пропал
`EWR` был зафиксирован корректно, но `Wilson` lower-bound diagnostic из финальной консолидации отчёта пропал совсем. Это не ломало production logic, но ослабляло admin validation layer.

### 2.4 Medium: anti-gaming semantics ослабилась
Rate limiting был переписан в hard-block style, хотя source report требовал более safe semantics:
- action всё ещё пишется в CRM / audit trail;
- но перестаёт приносить points / score-credit при лимите.

Hard-block был бы уже не anti-gaming guard, а риск потери операционного следа.

### 2.5 Medium: change-management и explainability были слишком общими
Пакет уже содержал shadow mode, но терял:
- bi-weekly DICE review;
- effort cap `<= +10%` для менеджера;
- explicit waterfall requirement для score-sensitive UI.

Это не ломало формулы, но делало rollout менее управляемым и менее faithful к source.

## 3. Что было дозакрыто
- `02_MOSAIC_SCORE_SYSTEM.md`: добавлены `Weibull` churn, logistic fallback, planned-gap guard, `k`-cap и `Wilson` diagnostic как admin/shadow metric.
- `03_PAYROLL_KPI_AND_PORTFOLIO.md`: добавлены rescue `SPIFF`, rescue attribution rules и `max 3/day` guard.
- `06_UI_UX_AND_MANAGER_CONSOLE.md`: rescue widget теперь нормативно показывает correct churn model assumptions, scaled `SPIFF` и overload guard.
- `07_IMPLEMENTATION_ROADMAP.md`, `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md`, `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`, `17_TRACEABILITY_MATRIX_AND_CODE_IMPACT.md`, `19_MANAGEMENT_CODEBASE_ALIGNMENT_MAP.md`: обновлены так, чтобы эти элементы больше не выпадали между planning-слоями.
- `15_ADMIN_ECONOMICS_AND_EARNED_DAY.md`: nightly snapshots теперь удерживают `Wilson` diagnostic рядом с `EWR`.
- `04_ANTI_DUPLICATION_AND_FOLLOWUP_ENGINE.md`: rate limit теперь описан как soft score-cap, а не как потеря самого действия.
- `06_UI_UX_AND_MANAGER_CONSOLE.md` и `07_IMPLEMENTATION_ROADMAP.md`: добавлены waterfall UX contract и DICE rollout guardrails.

## 4. Итог после третьего прохода
После дозакрытия критичных semantic losses я не вижу новых выпадений уровня `§37.1 / §37.5` из latest synthesis.

Оставшиеся риски уже implementation-shaped, а не package-shaped:
- точная формализация rescue attribution в модели/таблицах;
- конкретный snapshot schema для `Weibull` / `Wilson`;
- кодовое решение, где именно будет жить `build_rescue_top5`.
- payload versioning / compat-layer для перехода `KPD -> MOSAIC` в текущем `stats.html`;
- telephony как отдельный ingress/reconciliation subsystem, а не "маленькое добавление рядом с current routes".

Это уже нормальный следующий этап implementation planning, а не признак потерянного контекста в пакете.
