# Пакет задания: глубокий аудит и улучшение Instagram-бота TwoComms

Этот пакет — единое техническое задание для агента, который должен сначала полностью изучить Instagram-бота в management-субдомене и все связанные компоненты, затем провести доказательный аудит, подготовить implementation plan и только после этого безопасно внедрять изменения.

## Как использовать

Передайте агенту `01_MASTER_PROMPT.md` как главный промпт и всю папку как обязательные приложения. Исходное голосовое задание сохранено без сокращений в `99_ORIGINAL_REQUEST_VERBATIM.txt`.

## Файлы

- `01_MASTER_PROMPT.md` — главный исполняемый промпт.
- `02_REQUIRED_OUTPUTS_AND_GATES.md` — обязательные результаты и ворота качества.
- `03_AUDIT_CHECKLIST_120_TASKS.md` — 120 отдельных задач аудита.
- `04_SYSTEM_ARCHITECTURE_AND_CODE.md` — архитектура, код, API-ключи и технический долг.
- `05_AI_MEMORY_SALES_AND_FOLLOWUPS.md` — AI, память, инструкции, продажи и таймеры.
- `06_FUNNELS_EVENTS_PAYMENTS_NOVA_POSHTA_META.md` — события, оплаты, Nova Poshta и Meta.
- `07_SCORING_CLASSIFICATION_AND_ANALYTICS.md` — скоринг и точная аналитика.
- `08_ADMIN_UX_UI_AUDIT.md` — desktop-first UX/UI-аудит.
- `09_FINDINGS_REGISTER_TEMPLATE.md` — реестр находок.
- `10_IMPLEMENTATION_PLAN_TEMPLATE.md` — план внедрения.
- `11_EXECUTION_TEST_COMMIT_DEPLOY_PROTOCOL.md` — red-green-refactor, commit, push, deploy, rollback.
- `12_ACCEPTANCE_TEST_MATRIX.md` — приёмочные сценарии.
- `13_TRACEABILITY_MAP.md` — проверка, что требования не потеряны.

> Сначала глубочайший анализ и подтверждение причин. Затем план. Только затем изменение кода. Качество важнее скорости.
