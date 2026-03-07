# Final Codex Synthesis 2026-03-06

## Цель пакета
Этот пакет собирает лучшие идеи из:
- базового набора `01..08` в `management_analytics`,
- папки `Gemini Analytics`,
- папки `codex-analysis`,
- перекрёстных репортов в `reports`,
- дополнительного внешнего ресерча по CRM, дедупликации, call QA, reminder design, dashboard best practices и `Django`/`Celery`.

Это не архив мыслей. Это рабочий пакет для подготовки внедрения на management subdomain.

## Главный вывод
Лучшей основой для внедрения является не один агент, а гибрид:
- каркас внедрения, governance, risk control и rollout берём у `Codex`,
- B2B-калибровку, heatmap и дисциплину follow-up берём у `Opus/HES`,
- EV-справедливость, retention-first мотивацию и сильные UX-триггеры берём у `Gemini`,
- токсичные, слишком жёсткие или статистически хрупкие идеи убираем.

## Финальная north star модель
Я фиксирую новую итоговую систему как `MOSAIC`:
- `M`ulti-source fairness,
- `O`perational discipline,
- `S`ales outcomes,
- `A`nti-abuse,
- `I`ntelligent coaching,
- `C`lient portfolio management.

`MOSAIC` лучше предыдущих пакетов по трём причинам:
- не ломает B2B-реальность холодных баз,
- не даёт набивать высокий score без реального прогресса,
- уже разложен в формат, пригодный к поэтапной имплементации.

## Порядок чтения
1. `01_MASTER_SYNTHESIS.md`
2. `02_MOSAIC_SCORE_SYSTEM.md`
3. `03_PAYROLL_KPI_AND_PORTFOLIO.md`
4. `04_ANTI_DUPLICATION_AND_FOLLOWUP_ENGINE.md`
5. `05_IP_TELEPHONY_QA_AND_SUPERVISOR.md`
6. `06_UI_UX_AND_MANAGER_CONSOLE.md`
7. `07_IMPLEMENTATION_ROADMAP.md`
8. `08_CODEX_SUPERIORITY_ANALYSIS.md`
9. `09_RESEARCH_QUESTIONS_FOR_DEEP_AGENT.md`
10. `10_SOURCE_MAP_AND_EXTERNAL_BEST_PRACTICES.md`
11. `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md`
12. `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`
13. `13_CROSS_SYSTEM_GUARDRAILS.md`

## Карта файлов
- `01_MASTER_SYNTHESIS.md` — единый отбор лучших идей всех агентов.
- `02_MOSAIC_SCORE_SYSTEM.md` — финальная система score, fairness, gates, trust и ladders.
- `03_PAYROLL_KPI_AND_PORTFOLIO.md` — зарплата, KPI, retention, ownership клиентов.
- `04_ANTI_DUPLICATION_AND_FOLLOWUP_ENGINE.md` — антидубли, identity graph, reminders, callback ladder.
- `05_IP_TELEPHONY_QA_AND_SUPERVISOR.md` — телефония, supervisor mode, прослушка, QA, call statistics.
- `06_UI_UX_AND_MANAGER_CONSOLE.md` — финальная структура интерфейсов manager/admin/QA.
- `07_IMPLEMENTATION_ROADMAP.md` — реализация поверх текущего Django/Celery/Redis.
- `08_CODEX_SUPERIORITY_ANALYSIS.md` — почему Codex как база сильнее Gemini и Opus.
- `09_RESEARCH_QUESTIONS_FOR_DEEP_AGENT.md` — self-contained research brief для следующего deep-research агента: контекст проекта, baseline numbers, scope guardrails, file map и 5 исследовательских вопросов.
- `10_SOURCE_MAP_AND_EXTERNAL_BEST_PRACTICES.md` — источник решений и внешние best practices.
- `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md` — модульный backlog для прямой разработки.
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md` — единый источник стартовых чисел, пресетов и thresholds.
- `13_CROSS_SYSTEM_GUARDRAILS.md` — audit/security/backup/performance/i18n guardrails.

## Ground truth по текущему коду
Текущий проект уже даёт основу, на которую можно опираться:
- есть `Client`, `ManagementLead`, `ClientFollowUp`, `Shop`, `ShopCommunication`,
- есть `CommercialOfferEmailLog`,
- есть `ManagementDailyActivity`,
- есть `ManagerCommissionAccrual` и `ManagerPayoutRequest`,
- есть `ReminderSent`,
- есть `Celery`, `Redis`, Django `JSONField`,
- activity и follow-up уже частично реализованы.

Поэтому этот пакет предлагает не абстрактную новую CRM, а реалистичную эволюцию текущей management-системы.
