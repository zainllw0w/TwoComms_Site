# Аудит производительности главной страницы `twocomms.shop` на production

Дата: `2026-04-18`  
Область: только production homepage `https://twocomms.shop/`  
Локальная среда как источник истины не использовалась для выводов о поведении страницы. Код репозитория использовался только для объяснения уже подтвержденной production-нагрузки.

## Что именно анализировалось

- `https://twocomms.shop/` как реальная production-страница.
- Cold и semi-cold загрузка страницы в мобильном профиле.
- HTML, сеть, CSS, JS, шрифты, изображения, main thread, third-party, DOM и декоративные эффекты.
- Реальный рендер storefront home:
  - `twocomms/storefront/views/catalog.py`
  - `twocomms/twocomms_django_theme/templates/pages/index.html`
  - `twocomms/twocomms_django_theme/templates/base.html`
  - `twocomms/twocomms_django_theme/templates/partials/product_card.html`
  - `twocomms/twocomms_django_theme/static/js/main.js`
  - `twocomms/twocomms_django_theme/static/js/analytics-loader.js`
  - `twocomms/twocomms_django_theme/static/js/modules/homepage.js`
  - `twocomms/twocomms_django_theme/static/js/modules/survey.js`
  - `twocomms/storefront/templatetags/responsive_images.py`

## Использованные инструменты

- `curl` по production URL и по production assets.
- `lighthouse` CLI, mobile x3 и desktop x1.
- Chrome DevTools MCP:
  - performance trace
  - network list
  - console/issues
  - DOM snapshot
  - runtime `evaluate_script`
- Параллельные subagents для code audit и asset audit.
- Sequential Thinking MCP для разбиения исследования.

## Артефакты

Сырые артефакты сохранены в `output/perf_audit/`:

- `curl_home_timing.txt`
- `curl_home_headers.txt`
- `lighthouse_mobile_1.json`
- `lighthouse_mobile_2.json`
- `lighthouse_mobile_3.json`
- `lighthouse_desktop_1.json`
- `chrome_trace_mobile_reload.json`
- `home_snapshot.txt`
- `home_mobile.png`

## Короткий вывод

Проблема главной страницы не в backend TTFB. Production HTML приходит быстро. Основная просадка формируется на клиенте и складывается из пяти больших источников:

1. На home отдается слишком тяжелый first-view payload: примерно `3.35 MB` в mobile Lighthouse, из них основную долю составляют изображения, шрифты и third-party JS.
2. Часть карточек товаров не проходит через современный responsive pipeline и уходит в fallback на оригинальные JPEG до `925 KB` и `546 KB`.
3. Страница тянет слишком тяжелую шрифтовую схему: `6` font requests примерно на `679 KB`, причем веса `400` и `700` грузятся повторно двумя разными URL.
4. Главная страница перегружена декоративной CSS-композицией и DOM-слоями: на живой странице обнаружено около `71` элементов с `backdrop-filter`, `55` с анимациями, `87` с `box-shadow`, `76` inline SVG.
5. На старте приходит и исполняется слишком много общего и стороннего JS: `main.js`, `analytics-loader.js`, Bootstrap bundle, GTM/GA/Meta/TikTok/Clarity. Самый тяжелый first-party long task идет из `main.js` и достигает `286 ms`.

На десктопе страница выглядит заметно лучше, но mobile-проблема реальна и выраженная. Это совпадает с жалобой про подвисания на слабых телефонах.

## Production-метрики

### 1. Базовый HTTP-ответ production homepage

`curl` по `https://twocomms.shop/`:

| Метрика | Значение |
| --- | --- |
| HTTP status | `200` |
| HTML decoded size | `175,839 B` |
| `time_starttransfer` | `0.180 s` |
| `time_total` | `0.217 s` |
| `remote_ip` | `195.191.24.169` |
| `server` | `LiteSpeed` |

Вывод: origin отвечает нормально. Главный bottleneck не в первом байте.

### 2. Lighthouse desktop

| Метрика | Значение |
| --- | --- |
| Performance | `77` |
| FCP | `0.7 s` |
| LCP | `3.2 s` |
| Speed Index | `2.3 s` |
| TTI | `3.3 s` |
| TBT | `0 ms` |
| CLS | `0` |
| Total byte weight | `3,245 KiB` |
| Root document time | `140 ms` |

Вывод: на desktop страница тяжелая по байтам, но терпимая по CPU.

### 3. Lighthouse mobile, 3 production runs

| Run | Score | FCP | LCP | Speed Index | TBT | TTI | CLS | Total bytes | Root doc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `56` | `3.64 s` | `10.59 s` | `5.70 s` | `310 ms` | `11.30 s` | `0.0049` | `3.36 MB` | `272 ms` |
| 2 | `74` | `1.41 s` | `8.72 s` | `2.60 s` | `98 ms` | `13.31 s` | `0.00015` | `3.36 MB` | `452 ms` |
| 3 | `74` | `1.38 s` | `13.14 s` | `2.14 s` | `86 ms` | `14.58 s` | `0.0020` | `3.35 MB` | `91 ms` |

Медианы:

- Performance: `74`
- FCP: `1.41 s`
- LCP: `10.59 s`
- TBT: `98 ms`
- TTI: `13.31 s`

Ключевой вывод:

- LCP на mobile нестабилен и плохой: `8.7–13.1 s`.
- TTI стабильно плохой: `11.3–14.6 s`.
- TBT не ужасный по score, но это не отменяет jank: страница долго “доходит до спокойного состояния”.
- Главная проблема не сводится к одному большому blocking script. Это суммарный клиентский старт, тяжелая визуальная сцена и поздняя сторонняя активность.

## Что именно “ест” производительность

### 1. Изображения

Mobile Lighthouse resource summary:

- Images: `22 requests`, `1,758–1,759 KB`
- Scripts: `19 requests`, `728–732 KB`
- Fonts: `6 requests`, `678–679 KB`
- Stylesheets: `3 requests`, `109–110 KB`
- Third-party transfer: `726–730 KB`

Самые тяжелые network ресурсы на mobile:

| Ресурс | Тип | Transfer |
| --- | --- | --- |
| `/media/products/худі3.jpg` | Image | `925,724 B` |
| `/media/products/худі4-upscale-1x---2.jpg` | Image | `546,057 B` |
| `gtag.js` | Script | `183,154 B` |
| `gtm.js` | Script | `147,892 B` |
| `Inter-SemiBold.woff2` | Font | `114,695 B` |
| `Inter-Bold.woff2` | Font | `114,335 B` |
| `Inter-Medium.woff2` | Font | `114,090 B` |
| TikTok main pixel JS | Script | `112,349 B` |
| `Inter-Regular.woff2` | Font | `110,775 B` |
| `fbevents.js` | Script | `98,862–101,397 B` |

#### Что реально сломано в image pipeline

Через production HTML подтверждено:

- часть карточек использует корректный `<picture>` с `AVIF/WebP + fallback`
- часть карточек уходит сразу в оригинальный `<img src="/media/products/...jpg">`

Пример production markup:

- `Футболка "Печатка Хулігана"` получает `AVIF/WebP` и fallback `H2.jpg`
- `Худі "Glory of Ukraine"` получает только fallback `/media/products/худі4-upscale-1x---2.jpg`
- `Худі "Silent Winter"` получает только fallback `/media/products/худі3.jpg`

Причина видна в `twocomms/storefront/templatetags/responsive_images.py` и `templates/optimized_image.html`:

- если optimized variants существуют, генерируются `source srcset=...avif/webp`
- если optimized variants отсутствуют, `img src` остается оригиналом

То есть для части карточек optimization path не покрывает production-изображения, и home платит полную цену оригинальных JPG.

#### Эффект

Два изображения выше дают примерно `1.47 MB` transfer. Это один из крупнейших single-hit факторов mobile LCP и общей тяжести первого экрана/первых карточек.

### 2. Шрифты

На production home одновременно грузятся:

- `/static/fonts/Inter-Regular.woff2`
- `/static/fonts/Inter-Bold.woff2`
- `/static/fonts/Inter-Regular.woff2?30b2259ef43d`
- `/static/fonts/Inter-Bold.woff2?17df9edfac15`
- `/static/fonts/Inter-Medium.woff2?859198087881`
- `/static/fonts/Inter-SemiBold.woff2?cdaafcd49f7e`

Итого:

- `6` font requests
- `~679 KB` encoded body

Почему это происходит:

- `base.html` содержит inline critical `@font-face` для `400` и `700`
- compressed CSS path подтягивает версионированные `400/500/600/700`

Итог:

- веса `400` и `700` грузятся дважды разными URL
- `500` и `600` грузятся дополнительно

#### Эффект

Дубли только по `Regular + Bold` дают лишние примерно `225 KB` cold-transfer.  
Вместе со всем font set homepage тратит почти `0.68 MB` только на шрифты.

### 3. CSS

Подтвержденные размеры из репозитория:

| Файл | Размер на диске |
| --- | --- |
| `static/css/styles.purged.css` | `330,567 B` |
| `static/vendor/fontawesome/css/all.min.css` | `103,009 B` |
| `static/css/cls-ultimate.css` | `11,001 B` |
| `static/css/fonts.css` | `880 B` |

Lighthouse mobile:

- unused CSS savings: `~92 KiB`
- own bundled CSS: `41,812–41,867 B wasted`, `~81.3%`
- Bootstrap CSS: `30,444 B wasted`, `~91.5%`
- Font Awesome CSS: `22,009 B wasted`, `~99.7%`

Дополнительные признаки перегруза визуального слоя:

- `styles.purged.css`: `106` `@keyframes`
- `115` `animation:`
- `300` `transition:`
- `69` `backdrop-filter`
- `137` `filter:`
- `314` `box-shadow`

На живой странице по computed styles:

- `71` элементов с `backdrop-filter`
- `24` элементов с `filter`
- `55` анимируемых элементов
- `87` элементов с `box-shadow`

#### Что это означает

Home не просто большая по CSS. Она еще и дорого рисуется:

- blur / backdrop blur
- glow / shadow
- particles
- floating logos
- большие декоративные блоки hero / survey / categories

Это особенно болезненно на слабых мобильных GPU.

### 4. JS и main thread

Подтвержденные размеры first-party JS:

| Файл | Размер на диске |
| --- | --- |
| `static/js/main.js` | `105,041 B` |
| `static/js/analytics-loader.js` | `52,740 B` |
| `static/js/modules/homepage.js` | `8,350 B` |
| `static/js/modules/survey.js` | `15,038 B` |
| `static/js/modules/product-media.js` | `3,860 B` |
| `static/js/modules/optimizers.js` | `6,242 B` |

Lighthouse treemap и unused JS:

| Ресурс | Resource bytes | Unused bytes |
| --- | --- | --- |
| `gtag.js` | `566,608` | `162,940–163,735` |
| TikTok main | `481,562` | `248,264–262,714` |
| `gtm.js` | `424,446–424,457` | `198,425` |
| `fbevents.js` | `374,518` | `127,964` |
| `main.js?v=42` | `98,571` | `67,024` |
| `clarity.js` | `81,659` | `25,566–26,827` |
| `bootstrap.bundle.min.js` | `80,721` | `66,651` |
| `analytics-loader.js?v=3` | `49,256` | `25,253–25,914` |
| inline fallback JS | `20,588` | `19,372` |
| `modules/survey.js` | `14,907` | `12,889` |

#### Long tasks

Mobile Lighthouse зафиксировал:

- `main.js?v=42` long task `286 ms`
- `main.js?v=42` second long task `55 ms`
- `gtag.js` long task `129–133 ms`
- TikTok main long task `77–100 ms`
- `fbevents.js` long task `56–60 ms`
- `gtm.js` long task `51 ms`

Это важный момент:

- крупнейший first-party stall идет из `main.js`
- после него страницу продолжают догружать и тормошить сторонние пиксели

#### Main thread breakdown

Mobile run 1:

- total main-thread work: `3.8 s`
- Style & Layout: `977 ms`
- Script Evaluation: `545 ms`
- Rendering: `205 ms`

Mobile run 2:

- total main-thread work: `9.2 s`
- Style & Layout: `3.75 s`
- Script Evaluation: `535 ms`
- Rendering: `684 ms`

То есть jitter на слабых устройствах идет не только от JS, а от сочетания:

- layout recalculation
- rendering
- тяжелой визуальной сцены
- поздних сторонних инициализаций

### 5. Third-party

Chrome trace insight `ThirdParties`:

- Google Tag Manager: `991.3 kB`
- TikTok: `642.2 kB`
- Facebook: `542.6 kB`
- JSDelivr: `313.5 kB`
- Clarity: `83.1 kB`

Main thread time from third parties по trace:

- GTM: `41 ms`
- Clarity: `28 ms`
- Facebook: `11 ms`
- TikTok: `10 ms`

Lighthouse/treemap показывает, что даже при умеренном trace main-thread времени эти third-party скрипты создают большой parse/compile/resource footprint и заметный unused JS.

На production home после no-cache reload видно около `66` network requests, и большая доля хвоста уходит именно в analytics/ads vendors.

#### Что происходит по коду

`base.html`:

- GTM загружается после interaction или через `setTimeout(loadGTM, 4000)`
- `analytics-loader.js` грузится всегда

`analytics-loader.js`:

- грузит Meta
- грузит TikTok
- планирует GA4
- планирует Clarity
- содержит hashing и event bridge логику

Следствие:

- даже если initial paint уже произошел, через `2–4 s` страница получает поздние дополнительные скрипты, запросы и long tasks
- это хорошо объясняет субъективное “подвисает чуть позже”, особенно на телефонах

### 6. DOM и декоративная композиция

Из runtime и HTML:

- DOM elements: `868`
- inline SVG: `76` в runtime, `79` в HTML
- `logo.svg` occurrences в HTML: `16`
- `14` script tags
- `2` module scripts
- `8` stylesheet links
- `8` product cards на стартовой выборке
- `8` picture tags
- `25` img tags

Конкретные тяжелые зоны шаблона:

- `templates/pages/index.html:1197+` hero block
- `templates/pages/index.html:1247+` survey block
- `templates/pages/index.html:1419+` categories block
- `templates/pages/index.html:1548+` products grid
- `templates/base.html:819+` скрытые мобильные панели
- `templates/base.html:1570+` глобальная points modal

Особенно дорогие визуальные паттерны:

- `hero-glow`
- `hero-particles`
- `featured-particles`
- `dark-particles`
- `featured-glow`
- `dark-glow`
- `floating-logo(s)`
- `toggle-btn-glow`
- `card-glow-dark`
- большие inline SVG-графики в survey-блоке

### 7. Критическая цепочка и вспомогательные запросы

Chrome trace `NetworkDependencyTree`:

- max critical path latency: `2,462 ms`
- цепочка включает:
  - root document
  - `main.js`
  - `cart/summary/`
  - `favorites/count/`
  - dynamic imports `homepage.js`, `survey.js`, `product-media.js`, `optimizers.js`

Отдельный `curl` к этим endpoint:

| Endpoint | TTFB/total |
| --- | --- |
| `/cart/summary/` | `~263 ms` |
| `/favorites/count/` | `~76 ms` |

Вывод:

- сами endpoint не выглядят тяжелыми по серверу
- проблема в том, что они входят в цепочку startup-work после `main.js`
- это не главный bottleneck, но это лишний шум на пути к “страница успокоилась”

## Что грузится, но почти не помогает home

### 1. Font Awesome CSS

- `103 KB` на диске
- `~99.7%` unused CSS на home

### 2. Bootstrap bundle JS

- `80,721` resource bytes
- `66,651` unused bytes

### 3. `survey.js`

- на home есть и inline dynamic import в `index.html`
- и import из `main.js`
- модуль защищен `modal.dataset.surveyInit === '1'`, поэтому двойной init не срабатывает
- но сам факт двойного import path означает лишнюю сложность и redundant startup-work

### 4. Inline fallback JS в `base.html`

- `20,588` resource bytes
- `19,372` unused bytes

### 5. `perf-lite`

В проекте уже существует большой perf-lite слой:

- раннее определение low-RAM / low-CPU / save-data
- крупный inline CSS, который отключает blur/particles/animations

Но:

- он shipped’ится всем
- core payload от этого не исчезает
- missing optimized images, font duplication, general JS/third-party старт он не лечит

То есть perf-lite полезен, но не закрывает главную проблему production home.

## Дополнительный deep dive: CSS, DOM, mobile stack

### 1. Секционная композиция страницы

Подтверждено по production HTML:

| Узел | Descendants | SVG | Комментарий |
| --- | --- | --- | --- |
| `hero-section` | `26` | `2` | сам hero не гигантский, но содержит glow/particles |
| survey banner `.survey-container-v3` | `70` | `3–4` | тяжелый рекламно-опросный блок уже в initial DOM |
| hidden `#survey-modal` | `21` | `1` | не виден сразу, но уже parsed и живет в DOM |
| `categories-section` | `86` | `3+` | много декоративных слоев и кнопочных эффектов |
| `#products-container` | `260` | `32` | основная масса DOM на home |
| hidden `#user-panel-mobile` | `25` | `несколько` | глобальный mobile panel на home всегда в DOM |
| hidden `#pointsInfoModal` | `41` | `несколько` | глобальный modal на home всегда в DOM |
| `.bottom-nav` | `33` | `4+` | fixed mobile UI, всегда присутствует на mobile |

Дополнительно:

- `fontawesome` реально грузится, но на production home найдено `0` Font Awesome nodes.
- на карточках товаров уже на первом HTML есть `8` overlay buttons для `pointsInfoModal`.
- всего на странице уже при старте присутствуют hidden/inert глобальные UI-блоки, которые не помогают first view, но увеличивают parse/style cost.

### 2. Inline payload внутри HTML

Это отдельная проблема, потому что этот код не переиспользуется браузерным кешем так же эффективно, как обычные static assets.

Подтверждено по шаблонам:

- inline CSS в `base.html`: `18,362 B`
- inline CSS в `pages/index.html`: `27,856 B`
- суммарный inline CSS для home: `46,218 B`
- inline JS в `base.html`: `33,510 B`
- inline JS в `pages/index.html`: `698 B`
- суммарный inline JS для home: `34,208 B`

Итого home shipped’ит около `80.4 KB` inline code еще до учета внешних CSS/JS.  
На фоне decoded HTML `175,839 B` это очень большая доля.

Вывод:

- home перегружена не только external assets, но и самим HTML payload
- крупный inline survey/categories CSS в `pages/index.html` делает document тяжелее
- крупный inline fallback JS в `base.html` раздувает parse/compile путь на любой странице, включая home

### 3. CSS-композиция и слои

Подтверждено по `styles.purged.css`:

- `69` вхождений `backdrop-filter`
- `137` вхождений `filter:`
- `314` вхождений `box-shadow`
- `115` вхождений `animation:`
- `106` `@keyframes`
- `0` `content-visibility`
- `0` `contain-intrinsic-size`

Подтверждено по live page:

- `71` элементов с `backdrop-filter`
- `24` элементов с `filter`
- `55` анимируемых элементов
- `87` элементов с `box-shadow`

Это означает, что home дорогая не только по bytes, но и по rendering path:

- blur/backdrop blur и glow увеличивают paint/compositing cost
- fixed/sticky UI с blur создают дорогое наложение поверх scrolling content
- glow/particles/floating logos добавляют compositor work без пользы для конверсии

Особенно тяжелые места в коде:

- `pages/index.html:1231-1241` — `hero-glow` и `hero-particles`
- `pages/index.html:1248-1269` — `featured-particles`, `featured-glow`, `featured-gradient-*`, `featured-floating-logos`
- `pages/index.html:1424-1450` — `dark-particles`, `dark-glow`, `dark-gradient-*`, `floating-logos`
- `pages/index.html:1469-1480` — `toggle-btn-glow` и `toggle-btn-ripple`
- `partials/product_card.html:45` — `favorite-btn-glow`

### 4. Что грузит CPU, что грузит GPU/compositor, что грузит RAM

#### CPU / main thread

Главный mobile bottleneck по trace и Lighthouse:

- `Style & Layout` до `3.75 s`
- `Script Evaluation` около `0.53–0.55 s`
- first-party long task из `main.js` до `286 ms`

Кодовые причины:

- `main.js:2058-2169` — `equalizeCardHeights` и `equalizeProductTitles` делают `getBoundingClientRect()` и повторные измерения
- `main.js:2460` — forced reflow через `offsetHeight`
- `homepage.js:56-82` — staged card animation через `setTimeout`
- `homepage.js:85-103` — staged reveal color dots через `setTimeout`
- `analytics-loader.js:1345-1433` — delayed startup нескольких third-party stacks

#### GPU / compositor / video memory

Это inference из CSS/DOM и браузерной модели рендера, но она хорошо совпадает с trace и mobile symptoms.

Главные подозреваемые:

- множественные `backdrop-filter`
- `filter: blur()` / `drop-shadow()`
- много `box-shadow`
- fixed `navbar`, fixed mobile bottom nav, modal overlays
- крупные JPEG fallback images без modern variants

Почему это важно:

- каждый blur/filter-heavy слой может требовать отдельную offscreen surface
- фиксированные полупрозрачные слои поверх скролла особенно неприятны на mobile GPU
- одно изображение формата `1080x1350` в RGBA — это примерно `5.6 MiB` decoded surface
- два problem JPEG первого списка потенциально дают `>11 MiB` только decoded image surfaces до учета доп. картинок, blur surfaces и font glyph atlases

На слабых Android это чаще бьет в GPU memory / raster, на iPhone Safari особенно неприятна комбинация `fixed + backdrop-filter + scrolling`.

#### RAM / DOM memory

Подтверждено косвенно:

- decoded HTML `175,839 B`
- `~80.4 KB` inline CSS/JS
- `~3.35 MB` page weight
- `~679 KB` fonts
- `260` descendants только в product container
- hidden survey modal, points modal и user mobile panel уже существуют в DOM

Это не memory leak, а тяжелая стартовая сцена.  
Проблема в том, что страница сразу держит много DOM, декоративных узлов, шрифтов, картинок и UI-shells, которые пользователь еще не использует.

### 5. Шрифты: более глубокий разбор

Подтверждено по коду:

- в `fonts.css` реально объявлены только веса `400`, `500`, `600`, `700`
- `unicode-range` не используется
- `local()` не используется
- variable font не используется
- `font-display` есть, везде `swap`

Подтверждено по home CSS:

- `index.html` и `styles.purged.css` активно используют `700`, `800`, `900`
- но отдельных font files для `800/900` нет

Следствие:

- текущий home и так уже живет без настоящих `800/900` файлов
- браузер использует ближайший доступный вес / synthetic bold behavior
- поэтому переход к более жесткой схеме `400 + 600 + 700` или к одному Inter variable font гораздо менее рискованный визуально, чем могло казаться

Что уже точно не оптимально:

- duplicated `400` и `700` через inline `@font-face` в `base.html` и через `fonts.css`
- почти `0.68 MB` шрифтов на cold load для home — слишком дорого

Практический вывод:

- сначала нужно убрать дубли `400/700`
- потом проверить, можно ли жить на `400 + 600 + 700`
- затем отдельно сравнить Inter variable font против текущих четырех файлов
- fallback в `system-ui` для low-end режима можно ввести через custom device class, а не через `prefers-reduced-data`, потому что этот media feature пока нельзя считать надежной production-опорой

### 6. Уже существующий `perf-lite`: что он реально делает и почему этого мало

В проекте уже есть две линии perf-lite логики:

- ранний inline detector в `base.html:103-133`
- поздний `MobileOptimizer` в `optimizers.js:67-82`

Плюсы:

- на действительно слабых устройствах он умеет выключать blur/particles/animation
- это полезно для subjective smoothness

Но есть четыре важных ограничения:

1. Страница все равно shipped’ится тяжелой.  
   `perf-lite` убирает эффект уже после того, как DOM, CSS, fonts и значительная часть JS уже приехали.

2. Он почти не уменьшает DOM.  
   survey modal, points modal, hidden mobile panel, category/survey decorative wrappers все равно parsed.

3. Есть логические дыры.  
   `shared.js:62-68` вычисляет `PERF_LITE` один раз при module evaluation.  
   Если поздний `MobileOptimizer` добавит `perf-lite` позже, ранние ветки `main.js`, которые проверяют `PERF_LITE`, уже не переоценятся.

4. Есть no-op / low-value pieces:
   - `optimizers.js:71` пишет `PerformanceOptimizer.scrollThreshold = 20`, но это свойство больше нигде не используется
   - `optimizers.js:160-181` ждет `data-src`, а в текущем theme таких изображений не найдено; `optimizeMobileImages()` для home фактически не делает ничего полезного

Вывод:

- `perf-lite` не нужно удалять
- но его нельзя считать полноценным решением mobile проблемы
- следующий refactor должен сделать один ранний source of truth для `device-class`, а не два partially overlapping механизма

### 7. Что можно удалить, что деградировать, что точно refactor

#### Можно удалить почти без визуальной потери

- Font Awesome на home: CSS грузится, иконки на page не используются
- duplicate survey import path:
  - `index.html:1651-1654`
  - `main.js:2544-2552`
- decorative particles в hero / featured / categories
- glow/ripple around categories toggle

#### Лучше деградировать только на low-end mobile

- `equalizeCardHeights` и `equalizeProductTitles`
- `animateNewCards` и `revealColorDots`
- floating logos, glows, gradients with live animation
- blur/backdrop blur на `navbar`, `bottom-nav`, modal surfaces
- survey modal mount до первого клика

#### Нужен именно refactor, а не точечный cosmetic fix

- `main.js` должен перестать быть route-agnostic mega-entry
- hidden global UI shells должны монтироваться по требованию
- home needs page-scoped CSS/JS split
- нужен единый `device-class = low|mid|high`, который понимают и CSS, и JS

### 8. Backend/runtime reality: где есть смысл, где нет

Подтверждено по репозиторию:

- pinned version: `Django==5.2.11`
- явного production-proof, что runtime уже везде на Python `3.14`, в репо нет; артефакты смешанные
- helper для anon page cache уже существует, но home на него сейчас не посажена

Практический вывод:

- Python `3.14` и потенциальный Django `6` не являются главным рычагом для этой home
- для home server-side смысл есть в:
  - anonymous page cache
  - fragment cache
  - cached template loader
  - pre-generated optimized media / cron
- для client jank это вторичный слой, но для TTFB и стабильности он полезен

### 9. Cross-check с Context7 и официальными best practices

Проверено по Context7 и официальной документации:

- [web.dev: How to create high-performance CSS animations](https://web.dev/articles/animations-guide)
  - анимировать безопасно в первую очередь `transform` и `opacity`
  - свойства, которые вызывают layout/paint, почти неизбежно будут лагать
  - `will-change` нужно использовать sparingly, а не массово
- [web.dev: content-visibility](https://web.dev/articles/content-visibility)
  - offscreen sections можно сильно удешевить
  - но DOM APIs, которые форсят rendering/layout на скрытом subtree, ломают выгоду
  - это важно для home, потому что current equalization code уже использует layout reads
- [web.dev: Best practices for fonts](https://web.dev/articles/font-best-practices)
  - fewer fonts и variable fonts могут дать большой win
  - preload нужен осторожно, иначе он конкурирует с более важными ресурсами
  - `font-display` влияет на LCP/FCP и текстовый рендер
- [Chrome for Developers: real-world DevTools debugging](https://developer.chrome.com/blog/devtools-grounded-real-world)
  - effect-heavy styling может выглядеть нормально на dev machine, но неожиданно замедлять mobile
  - box-shadows и blur filters часто проявляются именно как mobile-only pain
- Django docs через Context7
  - `cache_page`, template fragment cache и cached loader помогают server latency
  - Django 6 tasks framework — это не решение client-side mobile rendering bottleneck и не причина мигрировать ради home perf

## Уже проверено и не требует повторного аудита до рефакторинга

Следующему агенту нет смысла заново тратить время на повторную проверку этих гипотез, если implementation еще не менялся:

- Font Awesome на home сейчас бесполезен
- duplicate font loads `400/700` реально существуют
- duplicate survey import path реально существует
- `optimizeMobileImages()` сейчас no-op для home
- `scrollThreshold` в `MobileOptimizer` не влияет ни на что
- `content-visibility` сейчас вообще не используется
- проблема Python/Django version не является главным источником mobile подвисаний
- основные mobile bottlenecks уже локализованы: images, fonts, third-party, startup JS, visual layer, layout reads

## Ранжированный список bottlenecks

| Приоритет | Узкое место | Доказательство | Какой тип нагрузки |
| --- | --- | --- | --- |
| P0 | Missing optimized variants для части карточек | два JPG по `925 KB` и `546 KB` в mobile Lighthouse | сеть, LCP, decode |
| P0 | Перегруженный third-party stack | `726–730 KB` transfer, большие treemap resource bytes, long tasks после загрузки | сеть, parse, long tasks, поздний jank |
| P0 | Двойная/избыточная шрифтовая схема | `6` font requests, `~679 KB`, duplicated `Regular/Bold` | сеть, text render |
| P0 | Слишком общий startup JS | `main.js` long task `286 ms`, `67 KB` unused | main thread, TTI |
| P1 | Слишком много shipped CSS | `~92 KiB` unused CSS, bootstrap/fontawesome почти не нужны | transfer, style calc |
| P1 | Тяжелый визуальный слой | `71` backdrop-filter, `55` animated elements, `87` box-shadow | paint, compositing, battery |
| P1 | Layout work на карточках | `equalizeCardHeights`, `equalizeProductTitles`, `getBoundingClientRect`, forced reflow | layout, jank |
| P2 | Startup auxiliary requests | `cart/summary`, `favorites/count`, dynamic imports в chain | шум, завершенность загрузки |

## Production-safe вывод

Главная страница production-сайта реально тяжелая именно для слабых устройств, и это подтверждено несколькими независимыми слоями данных:

- server отвечает быстро
- mobile Lighthouse consistently плох по LCP/TTI
- network payload слишком велик
- важная часть веса уходит в изображения, шрифты и third-party
- первый significant first-party long task идет из `main.js`
- декоративная CSS-композиция очень дорогая по paint/layout

Главная производительная проблема homepage сейчас не одна. Это композиция:

`неоптимизированные карточки + тяжёлая шрифтовая схема + общий JS bundle + третьи стороны + дорогая визуальная сцена`

Именно поэтому на мощных устройствах страница кажется “нормальной”, а на слабых телефонах может ощутимо подвисать.

## Ограничения исследования

- CrUX field data для страницы в trace не было.
- Google PageSpeed API вернуть данные не смог из-за external quota `429 RESOURCE_EXHAUSTED`; этот канал исключен из выводов.
- DevTools performance trace использовался для dependency tree, third-party и request-chain, но не как основной источник абсолютных lab metrics, потому что trace summary получился на warmed state и без надежной корреляции с Lighthouse mobile.

## Что делать дальше

Следующий документ:

- `docs/performance/2026-04-18-homepage-production-optimization-plan.md`

В нем описан конкретный план ускорения home без заметной потери визуального образа.
