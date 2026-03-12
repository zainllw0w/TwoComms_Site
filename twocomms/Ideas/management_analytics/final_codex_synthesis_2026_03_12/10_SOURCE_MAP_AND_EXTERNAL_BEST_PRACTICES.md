# Source Map and External Best Practices

## 1. Роль этого файла
Этот документ фиксирует, откуда именно взялись ключевые решения пакета и какой вес у каждого источника.

Главный принцип: authoritative решение появляется только после трёх фильтров:
- бизнес-совместимость;
- инфраструктурная реализуемость;
- совместимость с текущим `management` codebase.

## 2. Основные группы источников

### 2.1 Внутренний baseline
- `final_codex_synthesis_2026_03_06`
- старые `management_analytics` документы
- прошлые decision logs и research prompts

### 2.2 Новые консолидированные отчёты
- `reports/COMPREHENSIVE_REPORT_2026-03-12.md`
- `reports/INTEGRATION_PLAN_FOR_CODEX_SYNTHESIS.md`

Эти документы принесли:
- full risk audit;
- codebase alignment;
- hosting constraints;
- formula corrections;
- safer rollout logic.

### 2.3 Реальный код проекта
Самый важный фильтр:
- `management/models.py`
- `management/stats_service.py`
- `management/stats_views.py`
- `management/views.py`
- `management/urls.py`
- `management/templates/management/*.html`

Именно codebase решает, что является эволюцией текущей системы, а что остаётся только красивой идеей.

### 2.4 Внешние best practices
В пакете остаются только те best practices, которые прошли through-project filtering:
- composite scoring and validation;
- duplicate management;
- action-first dashboards;
- call QA and calibration;
- reminder fatigue prevention;
- safe rollout and governance.

## 3. External patterns, которые действительно пережили фильтр

### 3.1 Composite scoring
Берём:
- dominant result axis;
- bounded modifiers;
- validation-before-activation;
- low-sample caution.

Не берём:
- aggressive opaque ranking math;
- direct punitive magic formulas;
- noisy recalibration as default.

### 3.2 Duplicate management
Берём:
- exact / possible / review split;
- conservative merge philosophy;
- append-first and review-first behavior.

Не берём:
- auto-merge on fuzzy similarity alone;
- database extensions as hard dependency.

### 3.3 Dashboard design
Берём:
- actionability over vanity;
- progressive disclosure;
- manager/admin role separation.

Не берём:
- decorative analytics without workflow value;
- shame-driven leaderboards.

### 3.4 Call monitoring and QA
Берём:
- phased rollout;
- calibration before money impact;
- review queue and evidence preservation.

Не берём:
- instant punitive QA scoring;
- telephony-heavy truth before telephony exists.

## 4. Django-specific planning anchors

### 4.1 Management commands
Через Context7 и актуальную документацию Django подтверждён базовый паттерн:
- команды кладутся в `app/management/commands/*.py`;
- Django автоматически регистрирует их как `manage.py` commands;
- это делает `management commands + cron` естественным решением для shared hosting.

### 4.2 FileBasedCache
Через Context7 и документацию Django подтверждено:
- `FileBasedCache` конфигурируется через `CACHES["default"]`;
- ему можно задать `LOCATION`, `TIMEOUT`, `MAX_ENTRIES`;
- это реальная замена Redis для ограниченного набора задач текущего management.

### 4.3 Вывод для проекта
Лучший практический стек для текущей фазы:
- `management command + cron`;
- `FileBasedCache`;
- DB-backed logs and snapshots;
- no hard dependency on unavailable infra.

## 5. Какие источники стали authoritative по подсистемам

| Подсистема | Главный источник | Усиление / корректировка |
|---|---|---|
| MOSAIC / EWR | `COMPREHENSIVE_REPORT` + codebase audit | `02_MOSAIC_SCORE_SYSTEM.md` |
| Payroll / KPI | `COMPREHENSIVE_REPORT` + business invariants | `03_PAYROLL_KPI_AND_PORTFOLIO.md` |
| Dedupe / Follow-up | integration plan + `models.py` reality | `04_ANTI_DUPLICATION_AND_FOLLOWUP_ENGINE.md` |
| Telephony / QA | prior research + phase safety rules | `05_IP_TELEPHONY_QA_AND_SUPERVISOR.md` |
| UI / UX | current templates + report radar/manager ideas | `06_UI_UX_AND_MANAGER_CONSOLE.md` |
| Rollout | codebase + hosting audit + Django docs | `07_IMPLEMENTATION_ROADMAP.md` |
| Defaults | corrected formulas + stress tests | `12_CALIBRATION_DEFAULTS_AND_PRESETS.md` |
| Guardrails | risk registry + hosting limits | `13_CROSS_SYSTEM_GUARDRAILS.md` |

## 6. Что намеренно понижено до reference-only
- старые sections, где `Redis`, `Celery`, `pg_trgm` фигурируют как базовые зависимости;
- любые формулы без phase-awareness;
- seasonal tables без достаточной исторической калибровки;
- продуктовые идеи, не имеющие прямой привязки к current codebase.

## 7. Практическое правило чтения
Если между источниками есть конфликт, приоритет такой:
1. current codebase reality
2. `COMPREHENSIVE_REPORT_2026-03-12.md`
3. `INTEGRATION_PLAN_FOR_CODEX_SYNTHESIS.md`
4. baseline `2026-03-06`
5. older research and historical analysis

## 8. Итог
Пакет строится не на слепом доверии одному отчёту и не на желании сохранить все идеи любой ценой.

Он строится на фильтрации:
- что доказано полезно;
- что реально реализуемо на этом проекте;
- что не уничтожит пользовательскую и бизнес-логику при внедрении.
