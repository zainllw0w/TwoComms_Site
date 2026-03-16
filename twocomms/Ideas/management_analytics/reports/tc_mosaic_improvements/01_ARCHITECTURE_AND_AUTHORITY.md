# 01. Архитектура, authority layer и системные зависимости

## 1. Что пакет уже делает правильно
Авторитетный пакет уже зафиксировал главное:
- это **эволюция текущего `management`**, а не новая CRM с нуля;
- truth строится вокруг текущего Django-кода;
- инфраструктура подчинена shared-hosting reality;
- rollout идёт через `ACTIVE / SHADOW / DORMANT`;
- verified money truth не смешивается с shadow analytics.

В терминах архитектуры это очень взрослое решение: сначала основание, потом shadow, потом UI, потом bounded consequences.

## 2. Как реально проходит зависимость между идеями, кодом и формулами

### 2.1 Score-layer
`02_MOSAIC_SCORE_SYSTEM.md` + `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`
-> `stats_service.py`
-> `NightlyScoreSnapshot`
-> `stats_views.py`
-> `stats.html` / `admin.html`

### 2.2 Payroll-layer
`03_PAYROLL_KPI_AND_PORTFOLIO.md` + `15_ADMIN_ECONOMICS_AND_EARNED_DAY.md`
-> payout models / accruals / payout requests
-> `views.py`
-> `payouts.html`, admin payout surfaces

### 2.3 Dedupe/follow-up layer
`04_ANTI_DUPLICATION_AND_FOLLOWUP_ENGINE.md`
-> `Client`, `ManagementLead`, `LeadParsingJob`, `LeadParsingResult`, `ClientFollowUp`
-> reminder send / duplicate queue commands
-> lead/parsing/admin surfaces

### 2.4 Telephony/QA layer
`05_IP_TELEPHONY_QA_AND_SUPERVISOR.md`
-> `CallRecord`, webhook log, QA review, supervisor action log
-> webhook endpoints + command processing
-> future supervisor/admin queue

### 2.5 Governance layer
`13_CROSS_SYSTEM_GUARDRAILS.md` + `07_IMPLEMENTATION_ROADMAP.md`
-> audit tables / config versioning / snapshot safety / rollback rules

## 3. Главный structural risk пакета
Технически самый опасный баг — **не взять слишком слабую идею**, а случайно взять **не тот источник истины**.

В пакете уже есть разделение:
- authoritative docs;
- reference docs;
- audit docs;
- backlog/traceability/alignment docs.

Но этого мало для реальной имплементации, потому что:
- reference-документы всё ещё содержат старые веса и старые исследовательские формулы;
- разработчик или будущий ИИ может открыть `09`/`16` и реализовать устаревшее число как production default;
- часть “тонких” решений уже исправлена только через audits, но не превращена в machine-readable manifest.

## 4. Что я рекомендую добавить на архитектурном уровне

### 4.1 `AUTHORITY_MANIFEST`
Сделать один явный файл, например `management_analytics_authority_manifest.json` или `00_AUTHORITY_MANIFEST.md`, где будет:
- `authoritative_files`
- `reference_only_files`
- `superseded_rules`
- `active_formula_version`
- `active_defaults_version`
- `last_alignment_audit`

Это особенно важно потому, что пакет уже пережил несколько проходов hardening.

### 4.2 `FORMULA_VERSION` и `SNAPSHOT_SCHEMA_VERSION`
Любой score snapshot и payout-adjacent simulation должны хранить:
- `formula_version`
- `defaults_version`
- `snapshot_schema_version`
- `readiness_state`

Иначе через 2-3 месяца невозможно будет понять, по каким правилам был посчитан historical snapshot.

### 4.3 Жёсткое правило: reference-formulas never imported into code
Нужна отдельная защита от дрейфа:
- никакой код не читает значения из reference docs;
- production defaults живут только в code constants/config + authoritative defaults registry;
- research docs разрешены только для planning/shadow experiments.

### 4.4 `DOC-CODE DRIFT CHECK`
Нужен очень простой сервисный тест:
- ожидаемые значения из authoritative defaults;
- фактические значения в code constants;
- warning если есть расхождение по весам/gates/trust bounds/portfolio thresholds.

Это один из самых дешёвых способов не сломать систему “тихой” правкой.

## 5. Где package сильный, но всё ещё не полностью формализован

### 5.1 `verified_slice` vs `evidence_sensitive_slice`
Логика в пакете правильная, но пока недостаточно детерминирована.
Нужно явно описать:
- какая часть `Result` идёт в verified slice;
- куда попадает revenue term;
- считается ли admin-confirmed milestone verified enough;
- как slice mapping меняется по phase.

### 5.2 `score_confidence`
Confidence label уже есть как идея и числовые bands, но нет единой полной формулы.
Это создаёт риск, что front-end label и admin-decision logic будут рассчитывать confidence по-разному.

### 5.3 `working day semantics`
Day statuses расширены, но weekly KPI proration, partial capacity и long-leave reintegration ещё не стали жёстким контрактом.

### 5.4 `telephony health`
Пакет хорошо разделяет telephony maturity, но ещё не формализует health model провайдера.
Это опасно: без health-bridge сбой провайдера может выглядеть как плохая дисциплина менеджера.

## 6. Что ещё стоит зафиксировать как неизменяемые принципы
Я рекомендую дополнить authoritative слой такими explicit invariants:

1. **Ни одна формула не может зависеть от reference-file напрямую.**
2. **Ни один score-sensitive UI-block не показывается без snapshot freshness state.**
3. **Ни один admin decision не опирается на score без confidence label и formula_version.**
4. **Ни один leave/force-majeure/tech-failure день не портит weekly KPI без явного prorating contract.**
5. **Ни один import/reassign burst не трактуется как личная follow-up negligence без overload grace.**

## 7. Наиболее вероятные implementation-bugs, если ничего не усиливать

### Bug A — “Wrong source of truth bug”
Разработчик реализует старую формулу из `09`/`16` вместо authoritative `02/12`.

### Bug B — “Invisible config drift”
Вес или gate меняются в коде, но docs и snapshots не знают об этом.

### Bug C — “Snapshot ambiguity”
Через 2 месяца невозможно интерпретировать historical score, потому что нет formula_version.

### Bug D — “Phase confusion”
UI показывает SHADOW как будто это payroll-final truth.

### Bug E — “Tech outage becomes manager fault”
Нет bridge между provider failure и `TECH_FAILURE`/`FORCE_MAJEURE` operational layer.

## 8. Что менять в каких файлах
- новый manifest / version contract -> рядом с `00_INDEX.md`, `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`, `13_CROSS_SYSTEM_GUARDRAILS.md`
- `NightlyScoreSnapshot` fields -> `models.py`
- score/payout/admin payloads -> `stats_service.py`, `stats_views.py`, `views.py`
- UI states -> `stats.html`, `admin.html`, `payouts.html`

## 9. Приоритет
Сначала:
1. authority manifest
2. formula/defaults versioning
3. score confidence formula
4. KPI proration contract
5. command health / snapshot freshness

Только после этого стоит углублять новые аналитические поверхности.
