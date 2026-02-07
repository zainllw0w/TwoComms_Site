# DTF Checklist

## Part 1 - Implementation Strategy
- [x] Работы изолированы в DTF-контуре (`dtf.twocomms.shop` urlconf)
- [x] Heavy/medium/micro стратегия оформлена в коде и карте эффектов
- [x] `Flip Words` добавлен в hero-блок главной (`/`)
- [x] `Background Beams` добавлен как medium-слой на главной (`/`)
- [x] Stateful submit/CTA-кнопки добавлены на ключевых сценариях (order/status/preflight/fab/header/home CTA)
- [x] Учитывается `prefers-reduced-motion` для новых эффектов (flip/beams/stateful)
- [x] Добавлены проектные журналы: `DTF_CHECKLIST.md`, `EFFECTS_MAP.md`, `MCP_TODO.md`

## Part 2 - Knowledge Base + SEO
- [x] SSR-раздел `/blog/` и `/blog/<slug>/`
- [x] Tracing Beam на списке статей
- [x] Overlay “Cards on Click” с прогрессивным fallback
- [x] Превью статей на главной в mixed grid
- [x] SEO для статей: meta/canonical/schema/sitemap
- [x] Документация SEO-базы (`SEO_BASELINE.md`) и обновление карты эффектов

## Part 3 - Execution Protocol / QA / Evidence / Rollback
- [x] Обновлены обязательные артефакты: `CHECKLIST`, `QA`, `DEPLOY`, `EVIDENCE`, `CHANGELOG_CODEX`
- [x] Прогнаны quality gates: compileall, `manage.py test dtf`, `pip-audit`
- [x] Обновлена post-deploy curl матрица для DTF + проверка main-domain изоляции
- [x] Снят lighthouse baseline (mobile) для `/`, `/order/`, `/price/`, `/quality/`
- [x] Обновлены rollback/deploy протоколы и индексация артефактов в корне проекта

## Part 4 - WOW Visuals + Constructor + Sample + Products + Cabinet
- [x] Добавлены стабильные `data-ui` anchors для DTF секций (home/order/gallery/requirements/status/templates + новые страницы)
- [x] Реализован Free Sample flow: `/sample/` + `DtfSampleLead` + форма + anti-spam + admin
- [x] Добавлен component pack (`dtf/static/dtf/js/components`, `dtf/static/dtf/css/components`) и global init (`DTF.init` + `initEffects` + HTMX re-init)
- [x] Усилен home WOW-набор: encrypted line, 3rd CTA sample, dotted/pointer/sparkles/floating dock
- [x] Усилен order/status/requirements/templates UX: multi-step loader, vanish inputs, tracing beam, tabs download
- [x] Реализован Constructor MVP: `/constructor/`, `/constructor/app/`, `/constructor/submit/`, sessions, preflight и 2D preview
- [x] Добавлены `/products/`, `/about/` и cabinet MVP: `/cabinet/`, `/cabinet/orders/`, `/cabinet/sessions/`
- [x] Обновлены тесты `dtf` (33 test cases, все зелёные)
