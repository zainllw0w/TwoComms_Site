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
- [ ] SSR-раздел `/blog/` и `/blog/<slug>/`
- [ ] Tracing Beam на списке статей
- [ ] Overlay “Cards on Click” с прогрессивным fallback
- [ ] Превью статей на главной в mixed grid
- [ ] SEO для статей: meta/canonical/schema/sitemap
- [ ] Документация SEO-базы (`SEO_BASELINE.md`) и обновление карты эффектов
