# Final Codex Synthesis 2026-03-12

## Цель пакета
Эта папка фиксирует обновлённую, production-safe версию синтеза для `management` subdomain поверх baseline-пакета `final_codex_synthesis_2026_03_06`.

Новая версия нужна по трём причинам:
- 12 марта появился большой консолидированный отчёт с реальными аудиторскими исправлениями, codebase-сверкой и risk-revision;
- старый пакет хорошо задаёт каркас, но в нём уже есть устаревшие предположения про `Celery`, `Redis`, `pg_trgm`, веса MOSAIC и KPI;
- следующий шаг у команды будет не генерация новых идей, а построение детального implementation plan. Для этого нужен единый нормативный пакет без скрытых конфликтов.

## Что считается authoritative
Нормативными для дальнейшего planning и будущей имплементации считаются:
1. `01_MASTER_SYNTHESIS.md`
2. `02_MOSAIC_SCORE_SYSTEM.md`
3. `03_PAYROLL_KPI_AND_PORTFOLIO.md`
4. `04_ANTI_DUPLICATION_AND_FOLLOWUP_ENGINE.md`
5. `05_IP_TELEPHONY_QA_AND_SUPERVISOR.md`
6. `06_UI_UX_AND_MANAGER_CONSOLE.md`
7. `07_IMPLEMENTATION_ROADMAP.md`
8. `10_SOURCE_MAP_AND_EXTERNAL_BEST_PRACTICES.md`
9. `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md`
10. `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`
11. `13_CROSS_SYSTEM_GUARDRAILS.md`
12. `14_OPUS_SECOND_PASS_DECISION_LOG.md`
13. `15_ADMIN_ECONOMICS_AND_EARNED_DAY.md`
14. `17_TRACEABILITY_MATRIX_AND_CODE_IMPACT.md`
15. `18_PACKAGE_CHANGELOG_2026_03_12.md`
16. `19_MANAGEMENT_CODEBASE_ALIGNMENT_MAP.md`
17. `20_SECOND_PASS_AUDIT_2026_03_12.md`

## Что остаётся reference-слоем
Следующие файлы намеренно сохранены для полноты контекста, но не должны перевешивать authoritative docs:
- `08_CODEX_SUPERIORITY_ANALYSIS.md` — исторический decision-context, почему skeleton берётся у Codex.
- `09_RESEARCH_QUESTIONS_FOR_DEEP_AGENT.md` — исследовательский brief, а не финальная спецификация.
- `16_ADDITIONAL_RESEARCH_PROMPT.md` — дополнительный prompt-layer для future research.
- `deep-research-report.md`, `deep-research-report (2).md`, `Бриф для Deep Research по TwoComms Management.md`, `Оптимизация B2B Fashion Wholesale Системы.md` — первичные входные материалы, не финальный пакет для внедрения.

## Главный вывод этой версии
Итоговая система больше не описывается как "красивый future-state". Она описывается как безопасная эволюция текущего Django management, опирающаяся на реальный код, реальные данные и реальные ограничения хостинга.

Финальная north-star модель:
- `MOSAIC` остаётся ядром score-логики;
- `EWR` становится финальной реализацией оси `Result`;
- KPI и зарплата сохраняют `2.5% new / 5% repeat` как бизнес-инвариант, но получают мягкие и phase-aware guardrails;
- dedupe, follow-up, telephony и admin economics описываются только в том виде, в котором их реально можно внедрить на текущем стеке.

## Ключевые дельты против 2026-03-06
- Вместо `Celery + Redis` фиксируется `Django management commands + cron + FileBasedCache`.
- Вместо `pg_trgm + city blocking` фиксируется `SequenceMatcher + phone_last7 + normalized name blocking`.
- Вместо старого `Result` фиксируется `EWR`.
- Вместо неявного наказания за DORMANT-компоненты вводится `Component Readiness Registry`.
- Вместо cliff-пенальти по повторной комиссии вводится `Soft Floor Cap`.
- Вместо общего "возможно потом" появляется явная связь с текущими файлами `management/models.py`, `stats_service.py`, `stats_views.py`, `views.py`, `templates/management/*.html`.

## Порядок чтения
1. `01_MASTER_SYNTHESIS.md`
2. `07_IMPLEMENTATION_ROADMAP.md`
3. `17_TRACEABILITY_MATRIX_AND_CODE_IMPACT.md`
4. `19_MANAGEMENT_CODEBASE_ALIGNMENT_MAP.md`
5. `02_MOSAIC_SCORE_SYSTEM.md`
6. `03_PAYROLL_KPI_AND_PORTFOLIO.md`
7. `04_ANTI_DUPLICATION_AND_FOLLOWUP_ENGINE.md`
8. `05_IP_TELEPHONY_QA_AND_SUPERVISOR.md`
9. `06_UI_UX_AND_MANAGER_CONSOLE.md`
10. `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md`
11. `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`
12. `13_CROSS_SYSTEM_GUARDRAILS.md`
13. `14_OPUS_SECOND_PASS_DECISION_LOG.md`
14. `15_ADMIN_ECONOMICS_AND_EARNED_DAY.md`
15. `18_PACKAGE_CHANGELOG_2026_03_12.md`

## Карта файлов
- `01_MASTER_SYNTHESIS.md` — единое описание того, что сохраняем, что меняем и почему.
- `02_MOSAIC_SCORE_SYSTEM.md` — финальная score-архитектура, готовая к shadow-mode реализации.
- `03_PAYROLL_KPI_AND_PORTFOLIO.md` — зарплатная логика, KPI, portfolio health, ownership и Snooze/Force-Majeure rules.
- `04_ANTI_DUPLICATION_AND_FOLLOWUP_ENGINE.md` — dedupe, follow-up, rate limiting, ownership guards и reminder engine.
- `05_IP_TELEPHONY_QA_AND_SUPERVISOR.md` — telephony roadmap, QA contour, maturity gating и manual Phase 0.
- `06_UI_UX_AND_MANAGER_CONSOLE.md` — manager/admin UX, Radar, rescue surfaces, salary simulator и recovery-first copy.
- `07_IMPLEMENTATION_ROADMAP.md` — поэтапный rollout с учётом shared hosting и current codebase.
- `10_SOURCE_MAP_AND_EXTERNAL_BEST_PRACTICES.md` — source-of-truth по входным документам и внешним best practices.
- `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md` — модульный backlog по моделям, сервисам, командам, API и UI.
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md` — единый список констант, baseline-чисел и guards.
- `13_CROSS_SYSTEM_GUARDRAILS.md` — audit, backup, cache recovery, Red Card, Force Majeure, formula governance.
- `14_OPUS_SECOND_PASS_DECISION_LOG.md` — теперь это consolidated decision log, legacy filename сохранён ради continuity.
- `15_ADMIN_ECONOMICS_AND_EARNED_DAY.md` — admin-only economics, snapshots, DMT, Earned Day и appeals.
- `17_TRACEABILITY_MATRIX_AND_CODE_IMPACT.md` — полный traceability от идей и report-sections к файлам пакета и будущим кодовым точкам.
- `18_PACKAGE_CHANGELOG_2026_03_12.md` — что именно изменилось относительно версии 2026-03-06.
- `19_MANAGEMENT_CODEBASE_ALIGNMENT_MAP.md` — срез текущей кодовой базы management и ожидаемых точек будущего внедрения.
- `20_SECOND_PASS_AUDIT_2026_03_12.md` — второй аудит пакета: что было найдено как недоинтегрированное и как это было дозакрыто.

## Ground Truth по текущему коду
Реальный `management` уже даёт достаточный фундамент:
- модели: `Client`, `ManagementLead`, `Report`, `ClientFollowUp`, `Shop`, `ShopCommunication`, `ManagementDailyActivity`, `ManagerCommissionAccrual`, `ManagerPayoutRequest`;
- сервисы: `stats_service.py` уже считает `KPD`, follow-ups, advice, source analysis и report discipline;
- UI: уже есть `stats.html`, `admin.html`, spiral chart, KPI cards, advice cards, follow-up sections;
- background entry point: в приложении уже есть `management/commands/`, значит путь для cron-команд архитектурно естественный;
- проект на `Django==5.2.11`.

## Реальные инфраструктурные ограничения
Нормативно считаем true следующее:
- shared hosting не гарантирует нормальную эксплуатацию `Redis`, `Celery`, `Docker` и `pg_trgm`;
- фоновые задачи нужно проектировать вокруг `django-admin/manage.py` commands и cron;
- кэш и rate limiting проектируются вокруг `django.core.cache.backends.filebased.FileBasedCache`;
- любой компонент, которого ещё нет в проде, не может штрафовать менеджера просто фактом своего отсутствия.

Этот пакет описывает не абстрактную новую CRM, а безопасную и поэтапную эволюцию текущего management-контекста.
