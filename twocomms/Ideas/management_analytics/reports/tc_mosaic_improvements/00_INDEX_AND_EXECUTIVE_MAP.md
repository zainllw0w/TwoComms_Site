# TwoComms Management / MOSAIC — пакет углублённых улучшений

## Что это за пакет
Этот пакет — не пересказ исходных markdown-файлов, а **надстройка над ними**.
Я исходил из того, что authoritative-слой уже собран качественно, но у него остаются три типа задач:

1. перевести сильные идеи в более точные implementation contracts;
2. закрыть тонкие баги и edge-cases, которые легко проявятся уже в коде;
3. сделать систему устойчивее к ложным тревогам, абузу, отпускным/выходным/сбоям и low-sample noise.

## На чём основан анализ
Я опирался прежде всего на authoritative-файлы:
- `00_INDEX.md`
- `01_MASTER_SYNTHESIS.md`
- `02_MOSAIC_SCORE_SYSTEM.md`
- `03_PAYROLL_KPI_AND_PORTFOLIO.md`
- `04_ANTI_DUPLICATION_AND_FOLLOWUP_ENGINE.md`
- `05_IP_TELEPHONY_QA_AND_SUPERVISOR.md`
- `06_UI_UX_AND_MANAGER_CONSOLE.md`
- `07_IMPLEMENTATION_ROADMAP.md`
- `10_SOURCE_MAP_AND_EXTERNAL_BEST_PRACTICES.md`
- `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md`
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`
- `13_CROSS_SYSTEM_GUARDRAILS.md`
- `15_ADMIN_ECONOMICS_AND_EARNED_DAY.md`
- `17_TRACEABILITY_MATRIX_AND_CODE_IMPACT.md`
- `19_MANAGEMENT_CODEBASE_ALIGNMENT_MAP.md`
- аудиты `20/21/22/23`

Reference-файлы `08/09/16` я использовал только как контекст открытых вопросов, а не как production truth.

## Главный вывод по системе целиком
MOSAIC в текущем пакете уже выглядит как **очень сильная safe-by-default архитектура**.
Её сила не в “магической формуле”, а в комбинации:
- verified outcomes > self-reported activity;
- shadow-first rollout;
- DORMANT-компоненты не наказывают за своё отсутствие;
- payroll не переводится целиком на score;
- хостинговые ограничения учтены заранее;
- manager/admin surfaces разнесены по ролям и power level.

Главная зона роста теперь не в придумывании ещё одной красивой идеи, а в:
- явной формализации неоднозначных участков формул;
- confidence-aware интерпретации результатов;
- KPI/DMT proration по рабочим дням, отпускам и неполному доступному времени;
- превращении эвристик в versioned contracts;
- снижении ложных тревог при tiny N.

## 15 самых ценных улучшений, которые я рекомендую вынести в верхний приоритет

1. **Ввести machine-readable authority layer**: manifest authoritative/reference, formula_version, defaults_version, snapshot_version.
2. **Жёстко развести current authoritative formulas и exploratory formulas из `09/16`**, чтобы будущая реализация не взяла устаревшие веса/trust bounds.
3. **Прорейтить KPI, soft-floor и weekly expectations по working days / leave / force majeure / partial capacity**.
4. **Добавить `capacity_factor` на day-ledger** для half-day, training, internal meeting, reintegration после долгого отсутствия.
5. **Формализовать axis-to-slice mapping в MOSAIC**, иначе два разработчика реализуют trust/gate по-разному.
6. **Ввести `score_confidence` как явную формулу**, а не только как текстовую идею в admin-layer.
7. **Сделать EWR-v2 shadow-variant**, где effort credit мягко зависит от rolling verified progress, а revenue term использует более мягкую saturation-функцию.
8. **Сделать source-fairness зависимым только от meaningful/resolved attempts и разделить assigned-source fairness и self-selected source mix**.
9. **Сильно улучшить dedupe normalization**: transliteration, legal suffix stripping, shared-phone registry, cross-owner background scan.
10. **Ввести отдельную burst/grace semantics** для follow-up после import/reassign, чтобы система не наказывала за технически импортированный перегруз.
11. **Сделать anti-abuse rules per-action, а не generic max_per_hour**.
12. **В telephony добавить provider health snapshot + outage-to-tech-failure bridge**, чтобы сбои телефонии не ломали DMT/trust.
13. **В QA добавить rubric versioning, stratified sampling и blind double-review на старте**.
14. **В manager UI добавить confidence/freshness visibility**: stale snapshot banner, confidence badges, “почему изменилось сегодня”.
15. **В admin economics добавить concentration risk, forecast aging penalty и rescue ROI**, иначе admin-panel останется слишком плоской.

## Что я считаю главными остаточными рисками

### 1. Риск смешения authoritative и reference-чисел
Самый неприятный баг здесь не математический, а управленческий:
если при реализации взять не тот документ, можно случайно вернуть старые веса, старый trust clamp, старые validation thresholds.

### 2. Риск неполной формализации “тонких” мест
В пакете есть сильные принципы, но некоторые зоны ещё слишком описательные:
- точный split `verified_slice / evidence_sensitive_slice`;
- score confidence calculation;
- KPI proration logic;
- follow-up behavior after reassignment/import overload;
- QA sampling contract.

### 3. Риск ложной punitive-semantics через edge-cases
Даже safe-by-default система может стать несправедливой, если не формализовать:
- отпуск/болезнь/праздники;
- partial day / training day;
- telephony outage;
- long leave reintegration;
- snapshot staleness;
- shared phone duplicates.

## Как читать мои файлы
- сначала `01_ARCHITECTURE_AND_AUTHORITY.md`
- затем `02_SCORE_MOSAIC_AND_FORMULAS.md`
- затем `03_PAYROLL_KPI_PORTFOLIO_EARNED_DAY.md`
- затем `04_DEDUPE_FOLLOWUP_ANTI_ABUSE.md`
- затем `05_TELEPHONY_QA_SUPERVISOR.md`
- затем `06_UI_UX_MANAGER_ADMIN.md`
- затем `07_ADMIN_ECONOMICS_VALIDATION_FORECAST.md`
- затем `08_GOVERNANCE_DATA_MODEL_ROLLOUT.md`
- затем `09_EDGE_CASES_AND_SCENARIOS.md`

## Карта сгенерированных файлов
- `01_ARCHITECTURE_AND_AUTHORITY.md` — как устроен пакет, где authority, где drift-risk, что нужно жёстко зафиксировать.
- `02_SCORE_MOSAIC_AND_FORMULAS.md` — глубокие улучшения формул, confidence layer, EWR/trust/source fairness/churn.
- `03_PAYROLL_KPI_PORTFOLIO_EARNED_DAY.md` — KPI, payout, prorating, leave logic, reintegration, portfolio/rescue economics.
- `04_DEDUPE_FOLLOWUP_ANTI_ABUSE.md` — dedupe, reminders, anti-gaming, overload, import safety.
- `05_TELEPHONY_QA_SUPERVISOR.md` — provider health, reconciliation, QA sampling, rubric versioning, supervisor logic.
- `06_UI_UX_MANAGER_ADMIN.md` — manager/admin surfaces, explainability, confidence, benchmark safety, mobile-first details.
- `07_ADMIN_ECONOMICS_VALIDATION_FORECAST.md` — score-to-money validation, forecast hardening, cohort and contribution analytics.
- `08_GOVERNANCE_DATA_MODEL_ROLLOUT.md` — config/versioning, commands, audit, tests, rollout gates, safe refactor map.
- `09_EDGE_CASES_AND_SCENARIOS.md` — реальные сценарии, где система может дать ложную несправедливость, и как это закрыть.
