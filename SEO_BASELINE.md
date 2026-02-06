# SEO Baseline - Knowledge Base (DTF)

## Scope
- Subdomain: `dtf.twocomms.shop`
- Section: `Knowledge Base` (`/blog/`)
- Goal: indexable SSR-статьи + внутренняя перелинковка без ухудшения UX заказа

## Implemented
- SSR-страницы:
  - `/blog/` (индекс, таймлайн по месяцам)
  - `/blog/<slug>/` (детальная статья)
- Индексация:
  - Каждая статья имеет постоянный slug URL
  - `/sitemap.xml` включает индекс блога и опубликованные статьи
- Metadata:
  - `<title>` и `<meta name="description">` из SEO-полей/резюме статьи
  - canonical через базовый шаблон на текущий URL
  - JSON-LD `Article` на странице статьи
  - JSON-LD `BreadcrumbList` на `/blog/` и `/blog/<slug>/`
- Internal linking:
  - Блок Knowledge Base на главной
  - Ссылки из `requirements` и `quality` на релевантные статьи
  - Ссылка на блог в футере

## Initial Content (seed)
- `yak-pidhotuvaty-fail-dlia-dtf-druku`
- `dtf-vs-dtg-shcho-krashche-dlia-merchu-2026`
- `trendy-merchu-2026-shcho-realno-prodaietsia`
- `chomu-dtf-vyhidnishe-za-shovkohrafiiu`
- `yak-obraty-futbolku-pid-dtf-druk`
- `kolir-i-shchilnist-plivky-iak-unyknuty-siurpryziv`
- `dohliad-za-dtf-nanesenniam-prosti-pravyla`

## Technical Notes
- Overlay чтения (`Cards on Click`) является progressive enhancement:
  - с JS: открытие статьи в модальном слое
  - без JS: переход на полноценный SSR URL
- Tracing Beam отключается/упрощается на `prefers-reduced-motion` и мобильных
- Reading progress применяется только на странице статьи
