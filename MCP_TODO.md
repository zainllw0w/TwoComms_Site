# MCP TODO (Linear Sync Draft)

## Done
- `DTF-001` [Done] Добавлен `Flip Words` на home hero.
- `DTF-002` [Done] Добавлен `Background Beams` на home hero.
- `DTF-003` [Done] Внедрены stateful-кнопки в ключевые формы/CTA.
- `DTF-004` [Done] Созданы журналы проекта (`DTF_CHECKLIST`, `EFFECTS_MAP`, `MCP_TODO`).
- `DTF-101` [Done] Реализованы маршруты Knowledge Base (`/blog/`, `/blog/<slug>/`) и SSR-шаблоны.
- `DTF-102` [Done] Добавлен Tracing Beam таймлайн на индекс блога.
- `DTF-103` [Done] Реализован overlay "Cards on Click" с fallback на обычную страницу.
- `DTF-104` [Done] Встроены карточки статей на главной (mixed grid).
- `DTF-105` [Done] Включен SEO-пакет блога: sitemap, canonical, Article JSON-LD.
- `DTF-106` [Done] Создан `SEO_BASELINE.md`.
- `DTF-301` [Done] Внедрён Part 3 runbook-контур (execution/QA/evidence/rollback).
- `DTF-302` [Done] Обновлены артефакты и индексы: `CHANGELOG_CODEX.md`, `EVIDENCE.md`, `DEPLOY.md`.
- `DTF-303` [Done] Прогнаны quality gates и зафиксированы артефакты (`tests`, `pip-audit`, `curl`, `lighthouse`).
- `DTF-401` [Done] Добавлены стабильные data-ui anchors и новый component pack (effects init + HTMX re-init).
- `DTF-402` [Done] Реализован Free Sample flow: CTA + `/sample/` + `DtfSampleLead` + admin.
- `DTF-403` [Done] Обновлены WOW-эффекты Home/Order/Requirements/Status/Templates (encrypted, dotted, pointer, loader, vanish, tabs).
- `DTF-404` [Done] Реализован Constructor MVP (`/constructor/*`) с preflight и 2D preview compositing.
- `DTF-405` [Done] Добавлены `/products/` и `/about/` страницы для направления “ready products”.
- `DTF-406` [Done] Реализован Cabinet MVP (`/cabinet/`, `/cabinet/orders/`, `/cabinet/sessions/`) с loyalty summary.
- `DTF-407` [Done] Расширен тестовый набор `dtf` под Part 4 (33 теста, green).

## Todo
- `DTF-201` [Todo] Добавить редакционный workflow для ежемесячной публикации через админку.
- `DTF-202` [Todo] Подключить отчёт Search Console/Lighthouse по страницам Knowledge Base.
- `DTF-304` [Todo] Подготовить автоматизированный браузерный smoke (desktop/mobile) в Playwright.
- `DTF-305` [Todo] Разобрать server warning: model changes not reflected in migrations (`accounts`, `dtf`, `management`) и синхронизировать migration state.
- `DTF-408` [Todo] Добавить persistent export CSV для `DtfSampleLead`/`DtfBuilderSession` из admin actions.
- `DTF-409` [Todo] Расширить constructor preview до нескольких mock-пресетов (front/back assets per product).
