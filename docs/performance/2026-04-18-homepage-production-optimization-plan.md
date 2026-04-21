# План ускорения production homepage `twocomms.shop` без заметной потери визуала

Дата: `2026-04-18`  
База: выводы из `docs/performance/2026-04-18-homepage-production-audit.md`

## Цель

Сделать главную страницу ощутимо легче и стабильнее на слабых телефонах, не превращая ее в “голую” страницу и не ломая визуальный стиль бренда.

Ключевая идея:

- не резать дизайн топором
- убирать не визуал, а лишнюю цену за визуал
- тяжелые вещи делать адаптивно: современный image pipeline, умная доставка шрифтов, меньше startup JS, меньше бесполезного third-party, меньше live blur/animation там, где устройство слабое

## Ограничения

- Анализ и оптимизация должны опираться на production behavior.
- Нельзя считать local успех доказательством безопасности.
- После каждого блока изменений нужен повторный production audit.
- Изменения для home нельзя оценивать только по score; важны реальный cold-start, субъективная плавность и отсутствие поздних подлагиваний.

## Целевые ориентиры

Реалистичные production targets для homepage:

| Метрика | Сейчас | Цель после P0/P1 |
| --- | --- | --- |
| Mobile Performance | `56–74` | `80+` |
| Mobile LCP | `8.7–13.1 s` | `< 4.5 s`, затем стремиться к `< 3.5 s` |
| Mobile TTI | `11.3–14.6 s` | `< 6 s` |
| Initial page weight | `~3.35 MB` | `< 2.0 MB`, затем `< 1.5 MB` |
| Fonts on cold load | `~679 KB` | `< 250–350 KB` |
| Third-party transfer on initial path | `~726–730 KB` | `< 200–300 KB` |
| First-screen image payload | `> 1.4 MB` worst case | `< 250–400 KB` |

Это не полностью аддитивные цифры. Часть улучшений перекрывает друг друга.

## Карта нагрузки: что именно нужно лечить

| Тип нагрузки | Что сейчас давит сильнее всего | Что это лечит |
| --- | --- | --- |
| Network / LCP | fallback JPEG, duplicate fonts, early analytics/ads stack, inline code | снижает вес первого экрана и время до нормального LCP |
| CPU / main thread | `main.js`, equalization, staged reveal logic, delayed analytics init | уменьшает лаги, TTI и post-load подвисания |
| GPU / compositor / video memory | `backdrop-filter`, `filter`, `box-shadow`, fixed translucent UI, большие decoded JPEG | уменьшает frame drops, нагрев, drain battery и лаги при scroll |
| RAM / DOM | hidden modal shells, декоративные wrappers, inline SVG, heavy first DOM | уменьшает parse/style cost и pressure на слабых телефонах |

Практическое правило:

- если задача лечит только TTFB, но не уменьшает shipped scene на клиенте, это не главный рычаг для home
- если задача уменьшает одновременно bytes + DOM + layout work, это почти всегда высокий приоритет

## Главный принцип: сохранить образ, убрать цену

### Что оставляем

- контрастный hero
- брендовый логотип и характер секций
- градиенты и атмосферу
- карточки товаров
- ощущение “живой” страницы

### Что переводим в дешевую форму

- blur и backdrop blur -> статичные полупрозрачные подложки или предсчитанный градиент
- floating/particles -> статичный декоративный фон или animation только на мощных устройствах
- тяжелые SVG-графики -> более компактная версия или lazy mount
- общие JS-фичи -> page-specific imports
- full analytics stack -> позже, умнее, по согласию/интеракции

## P0. Самые сильные и безопасные изменения

### P0.1. Закрыть пробоины image optimization pipeline

Что сделать:

- найти все homepage cards, которые рендерятся без AVIF/WebP responsive variants
- сгенерировать для них `320/640/768w` AVIF/WebP
- убедиться, что home никогда не уходит в original JPG для карточек первого экрана
- отдельно проверить top products на главной, не только generic pipeline

Почему это важно:

- сейчас два JPEG дают примерно `1.47 MB` transfer
- это крупнейший single-hit bottleneck home

Ожидаемый эффект:

- выигрыш порядка `1.2–1.4 MB` на плохом кейсе
- сильное улучшение LCP
- меньше decode cost и memory pressure

Визуальный риск:

- практически нулевой, если использовать AVIF/WebP с нормальным quality target

Пути:

- `twocomms/storefront/templatetags/responsive_images.py`
- `twocomms/twocomms_django_theme/templates/optimized_image.html`
- production media assets для товаров, попадающих на home

### P0.2. Убрать дубли загрузки Inter

Что сделать:

- оставить один источник truth для Inter
- не грузить одновременно inline critical fonts и версионированные URL тех же весов
- либо:
  - оставить только preloaded/inline `400 + 700`
  - а `500 + 600` догружать только если реально используются выше фолда
- либо перевести на один variable font с аккуратной проверкой визуального соответствия

Почему это важно:

- cold load сейчас грузит `6` font requests на `~679 KB`
- `Regular` и `Bold` дублируются разными URL

Ожидаемый эффект:

- моментальный cold-start win примерно `225 KB` только на дублях
- при более глубокой шрифтовой чистке `300–450 KB`

Дополнительный вывод из аудита:

- home уже использует `font-weight: 800/900`, но отдельных файлов этих весов не существует
- визуал уже опирается на nearest/synthetic behavior браузера
- значит переход на более жесткую схему `400 + 600 + 700` или на один Inter Variable гораздо менее рискованный, чем кажется

Практический план по шрифтам:

- шаг 1: убрать duplicate `400/700`
- шаг 2: проверить схему `400 + 600 + 700` против текущей
- шаг 3: отдельно сравнить один Inter Variable против набора из `4` woff2
- шаг 4: если будет отдельная генерация subset, делать `unicode-range` для `latin` и `cyrillic`, а не грузить один тяжелый универсальный файл

Визуальный риск:

- низкий при аккуратной настройке font-display и metric-compatible fallback

Пути:

- `twocomms/twocomms_django_theme/templates/base.html`
- `twocomms/twocomms_django_theme/static/css/fonts.css`

### P0.3. Радикально облегчить initial third-party path на home

Что сделать:

- разделить “обязательно сейчас” и “можно позже”
- GTM, GA4, Meta, TikTok, Clarity не должны все стартовать в один визитный путь через несколько секунд после открытия home
- внедрить одно из двух:
  - consent-first model
  - much-later interaction model

Практически:

- homepage pageview для рекламы/ретаргета не грузить до первого осознанного действия пользователя
- Clarity не грузить на первом экране home автоматически
- TikTok/Meta не грузить без необходимости на анонимном первом визите
- проверить, нужен ли одновременно и `gtag.js`, и `gtm.js`, и ad conversion stack на home

Почему это важно:

- сейчас third-party transfer `~726–730 KB`
- unused JS savings `~208–211 KB`
- именно third-party scripts дают поздние long tasks и “догоняющие” подлагивания

Ожидаемый эффект:

- `0.5–0.7 MB` меньше initial/early transfer
- меньше post-load jank
- заметно стабильнее TTI и субъективная плавность

Визуальный риск:

- нулевой

Бизнес-риск:

- средний, потому что затрагивает аналитику и маркетинг
- нужен явный договор: что действительно необходимо на landing visit

Пути:

- `twocomms/twocomms_django_theme/templates/base.html`
- `twocomms/twocomms_django_theme/static/js/analytics-loader.js`

### P0.4. Разрезать startup JS для home

Что сделать:

- перестать отдавать на home универсальный `main.js` как главный entry со всем сайтом внутри
- выделить home-specific entry, который содержит только:
  - reveal logic
  - homepage pagination
  - продуктовые color dots только для home
  - минимум header/cart/favorite integration
- все не-home фичи вынести из initial path

Особенно важно:

- `main.js` сейчас содержит много не-home логики
- `bootstrap.bundle.min.js` почти весь unused для home
- inline fallback JS в `base.html` почти весь unused
- duplicate import path для `survey.js` уже подтвержден
- `optimizeMobileImages()` сейчас фактически no-op для home
- `PerformanceOptimizer.scrollThreshold` сейчас не влияет ни на что
- текущий `PERF_LITE` вычисляется слишком рано и не является надежным source of truth

Ожидаемый эффект:

- убрать первый first-party long task `286 ms`
- снизить parse/eval и startup complexity
- уменьшить unused JS

Консервативный выигрыш:

- `30–60 KB` transfer
- `150+ KB` лишнего parsed resource space
- заметное уменьшение main-thread stalls

Визуальный риск:

- нулевой, если оставить поведение прежним

Пути:

- `twocomms/twocomms_django_theme/static/js/main.js`
- `twocomms/twocomms_django_theme/templates/base.html`
- `twocomms/twocomms_django_theme/static/js/modules/homepage.js`

### P0.5. Вынести homepage inline CSS/JS в кешируемые page-scoped assets

Что сделать:

- вынести тяжелый inline CSS из `pages/index.html` в отдельный home-only stylesheet
- вынести bulky inline fallback JS из `base.html` в отдельный asset или удалить, если реально не нужен
- оставить inline только действительно критический ранний detector с очень маленьким размером

Почему это важно:

- home сейчас несет около `46.2 KB` inline CSS
- и еще около `34.2 KB` inline JS
- этот код раздувает сам HTML и хуже переиспользуется браузерным кешем

Ожидаемый эффект:

- легче root document
- меньше HTML parse cost
- чище кеширование между переходами и повторными визитами

Визуальный риск:

- нулевой

Пути:

- `twocomms/twocomms_django_theme/templates/base.html`
- `twocomms/twocomms_django_theme/templates/pages/index.html`
- `twocomms/twocomms_django_theme/static/css/`
- `twocomms/twocomms_django_theme/static/js/`

### P0.6. Убрать или радикально ослабить mobile layout equalization

Что сделать:

- отключить на мобильных:
  - `equalizeCardHeights`
  - `equalizeProductTitles`
- отказаться от частых `getBoundingClientRect()` для карточек на small screens
- не делать forced reflow ради cosmetics

Почему это важно:

- main thread layout time на mobile доходит до `3.75 s`
- код делает явные измерения и есть forced reflow через `offsetHeight`

Ожидаемый эффект:

- меньше layout thrash
- меньше jank при загрузке и догрузке карточек
- smoother scroll на слабых телефонах

Визуальный риск:

- минимальный
- иногда карточки будут чуть менее “идеально” выровнены по высоте, но это почти всегда стоит того на low-end mobile

Пути:

- `twocomms/twocomms_django_theme/static/js/main.js`
- `twocomms/twocomms_django_theme/static/js/modules/homepage.js`

## P1. Сильные улучшения с очень малым визуальным отличием

### P1.1. Сократить CSS именно для homepage

Что сделать:

- отдать home отдельный, реально page-scoped stylesheet
- не тянуть на home почти бесполезный Font Awesome CSS
- проверить, нужен ли весь Bootstrap CSS, или на home можно оставить subset
- вынести часть тяжёлых home-only стилей из глобального бандла

Почему это важно:

- `~92 KiB` unused CSS на mobile audit
- `Font Awesome` почти целиком бесполезен на home
- большое количество animation/shadow/filter правил раздувает style recalculation

Ожидаемый эффект:

- меньше CSS transfer
- меньше style parsing
- стабильнее layout

Визуальный риск:

- низкий, если делать через route-specific bundle

Пути:

- `twocomms/twocomms_django_theme/templates/base.html`
- `twocomms/twocomms_django_theme/static/css/styles.purged.css`
- `twocomms/twocomms_django_theme/static/vendor/fontawesome/css/all.min.css`

### P1.2. Упростить дорогие визуальные эффекты только на слабых устройствах

Что сделать:

- оставить brand visuals, но перевести их в cheaper mode:
  - `backdrop-filter` -> pre-baked translucent layers
  - particles -> static dots or pseudo-elements
  - floating logos -> 1-2 статичных слоя вместо нескольких анимированных
- glow -> более легкая тень или градиент без filter blur
- не выключать всё подряд, а облегчать только самое дорогое

По секциям это означает:

- `hero-particles`: на `low` удалить, на `mid` оставить `1-2` статичных слоя, full animation только на `high`
- `featured-particles`, `dark-particles`, `floating-logo(s)`: для mobile заменить на статичный background/pseudo-element
- `toggle-btn-glow`, `toggle-btn-ripple`, `card-glow-dark`, `favorite-btn-glow`: удалить совсем или оставить только на desktop hover-state
- `backdrop-filter` на fixed mobile UI: заменить на полупрозрачную подложку без live blur
- большой survey SVG с drop-shadow: облегчить или отложенно монтировать

Почему это важно:

- на живой странице `71` элементов с `backdrop-filter`
- `55` анимируемых элементов
- `87` элементов с `box-shadow`

Ожидаемый эффект:

- лучше GPU behavior
- меньше repaint/compositing pressure
- ниже риск late jank и frame drops

Визуальный риск:

- низкий, если сохранить форму, цвет и композицию

### P1.3. Упростить survey-path на home

Что сделать:

- убрать redundant import path для `survey.js`
- не рендерить тяжелую survey DOM-конструкцию, пока пользователь не проявил интерес
- оставить CTA и лениво монтировать modal shell только при первом взаимодействии

Почему это важно:

- `survey.js` почти полностью unused на initial path
- survey block на странице содержит heavy decorative structure и большой inline SVG

Ожидаемый эффект:

- меньше initial DOM и JS
- меньше layout/render work на старте

Визуальный риск:

- нулевой, если CTA и баннер остаются прежними

Пути:

- `twocomms/twocomms_django_theme/templates/pages/index.html`
- `twocomms/twocomms_django_theme/static/js/modules/survey.js`
- `twocomms/twocomms_django_theme/static/js/main.js`

### P1.4. Лениво монтировать скрытые global UI shells

Что сделать:

- не держать на home в initial DOM тяжелые hidden блоки, которые не нужны до клика:
  - `#survey-modal`
  - `#pointsInfoModal`
  - `#user-panel-mobile`
- вместо этого:
  - оставить легкий placeholder или template
  - монтировать shell только при первом реальном открытии

Почему это важно:

- эти блоки уже parsed, styled и участвуют в общей DOM-композиции
- они не помогают first paint, но увеличивают RAM/DOM pressure

Ожидаемый эффект:

- меньше initial DOM
- меньше style/layout работы
- чище mobile startup path

Визуальный риск:

- нулевой

### P1.5. Отложить non-critical home requests

Что сделать:

- `/cart/summary/` и `/favorites/count/` не дергать на самом раннем startup path homepage
- переносить на idle или после первого user interaction
- если пользователь не авторизован, часть этого вообще можно не запрашивать сразу

Почему это важно:

- сами endpoint быстрые
- но они попадают в startup chain после `main.js`

Ожидаемый эффект:

- чище старт
- меньше конкуренции за главный поток и очередь network scheduling

Визуальный риск:

- нулевой

## P2. Более глубокие улучшения

### P2.1. Home-specific visual budget system

Что сделать:

- ввести device-class budget:
  - `high`
  - `standard`
  - `lite`
- но budget должен влиять не только на CSS, а на доставку:
  - fewer images
  - fewer animated layers
  - fewer decorative DOM nodes
  - lighter JS path

Почему текущий `perf-lite` недостаточен:

- он в основном гасит эффекты уже после того, как страница shipped
- core payload при этом остается слишком большим

Как это должно выглядеть в архитектуре:

- один ранний inline detector выставляет `<html data-device-class="low|mid|high">`
- detector учитывает:
  - `hardwareConcurrency`
  - `deviceMemory`
  - `navigator.connection.effectiveType`
  - `saveData`
  - `prefers-reduced-motion`
  - mobile viewport
- JS и CSS читают один и тот же `data-device-class`, а не живут в двух разных механизмах

Что именно меняется по классам:

- `high`: можно оставить почти весь визуал, но без duplicate payload и лишнего JS
- `mid`: статичные particles, меньше glow, без expensive equalization на initial path
- `low`: без backdrop blur, без floating logos, без staged card reveal, без ранних auxiliary requests, с урезанным первым viewport payload

Платформенные уточнения:

- Android low-end:
  - важнее уменьшать DOM, количество слоев и initial image count
  - aggressive blur/filter почти всегда нужно убирать
- iOS Safari:
  - особенно избегать `position: fixed` + `backdrop-filter` поверх scrolling content
  - blur радиуса и полупрозрачные overlay лучше сильно упрощать даже на не самых слабых iPhone

### P2.2. Перейти на иконки по месту использования

Что сделать:

- если на home реально нужны 3-5 иконок, не тянуть весь Font Awesome CSS
- заменить на inline SVG sprite или локальные SVG components

Ожидаемый эффект:

- убрать бесполезный CSS
- упростить render tree

### P2.3. Пересмотреть hero/logo strategy

Что сделать:

- оставить hero logo, но:
  - убрать `decoding="sync"`
  - не делать его high-cost участником стартовой сцены без причины
- проверить, не дешевле ли часть повторяющихся logo instances отдавать через CSS background или reuse-паттерн вместо множественных `<img>`

Эффект:

- небольшой сам по себе
- полезен в сочетании с cleanup всей декоративной композиции

### P2.4. Аккуратно применить `content-visibility` и containment

Что сделать:

- после удаления aggressive layout reads применить `content-visibility: auto` к нижним, не первым секциям
- для таких блоков задавать `contain-intrinsic-size`
- использовать containment только там, где JS не форсит layout скрытого subtree

Почему это не P0:

- сейчас home еще содержит equalization и другие layout reads
- если наложить `content-visibility` до refactor, часть выигрыша исчезнет или логика станет нестабильной

Ожидаемый эффект:

- дешевле offscreen rendering
- лучше scroll/initial render на mobile

Основание:

- это совпадает с рекомендациями MDN/web.dev, но только после того, как DOM subtree не насилуется частыми измерениями

### P2.5. Backend-safe ускорения без Redis и Celery

Что сделать:

- посадить anonymous homepage на page cache, если это не ломает персонализацию
- для дорогих секций использовать fragment cache
- держать cached template loader
- заранее генерировать optimized media и derivatives через management command / cron, если Celery/Redis пока отсутствуют
- при необходимости использовать conditional GET / ETag / Last-Modified для части asset-like ответов

Почему это полезно:

- уменьшает серверную работу и делает home стабильнее под нагрузкой
- помогает TTFB и повторным анонимным заходам

Почему это не главный рычаг:

- текущая боль home в первую очередь клиентская
- эти меры не уберут mobile jank от blur, шрифтов, DOM и startup JS

Вывод по стеку:

- Python `3.14` сам по себе не даст “магического” ускорения home
- миграция на Django `6` ради этой задачи не является оправданным приоритетом
- если искать безопасный backend win сейчас, то это кэширование и pre-generation, а не framework upgrade

## Что оптимизировать в первую очередь, если нужен максимальный эффект за минимум риска

### Набор A. Самый прагматичный

1. Исправить missing optimized product images.
2. Убрать duplicate font loads.
3. Отложить heavy third-party stack.
4. Отключить mobile height/title equalization.

Этот набор должен дать самый заметный прирост без редизайна.

### Набор B. Следом

1. Разрезать `main.js`.
2. Убрать почти ненужные `Font Awesome` и `Bootstrap JS` с home.
3. Упростить survey startup path.
4. Вынести inline CSS/JS в отдельные home assets.
5. Лениво монтировать hidden modal/panel shells.

### Набор C. Доводка

1. Перевести эффекты в cheaper visual mode.
2. Упростить global DOM и hidden panels.
3. Пересобрать page-scoped CSS.
4. Добавить `data-device-class` и tiered behavior.
5. После refactor аккуратно внедрить `content-visibility`.

## Что можно почти наверняка оставить визуально таким же

Эти изменения дают эффект без заметной потери образа:

- optimized AVIF/WebP для всех карточек
- font cleanup и dedupe
- аналитика позже и умнее
- smaller JS entry
- отключение forced equalization на mobile
- удаление ненужного Font Awesome на home
- ленивая инициализация survey modal
- вынос bulky inline CSS/JS в кешируемые assets
- lazy mount для hidden global UI shells

## Что может едва заметно отличаться, но сильно помочь

- blur заменить на полупрозрачные слои без live backdrop blur
- floating logos сделать статичными на low-end
- particles оставить только на desktop/high devices
- reduce glow intensity на mobile
- первые 1-2 карточки и first fold оставить максимально качественными, а остальной visual budget ужимать по `device-class`

Пользователь визуально почти не заметит это, а слабый телефон заметит очень сильно.

## Что можно удалить уже в рефакторинге почти без споров

- duplicate import path для `survey.js`
- dead/no-op куски в mobile optimizer:
  - `scrollThreshold`
  - логика `data-src`, если она не будет реально использована
- Font Awesome на home
- glow/ripple-обвязку у category toggle
- декоративные particles, если они не несут смысл и не видны в first-value interaction

## Что не является главным приоритетом, хотя может звучать привлекательно

- апгрейд на Django `6` только ради home perf
- надежда, что Python `3.14` сам решит mobile тормоза
- попытка “выделить больше оперативной памяти” телефону со стороны сайта
- серверные micro-оптимизации без уменьшения shipped payload

Это не бесполезно совсем, но это не решает корневую боль production homepage.

## Предлагаемый порядок внедрения

### Этап 1

- image pipeline holes
- font dedupe
- delayed third-party
- mobile equalization off
- убрать dead/no-op startup pieces
- вынести bulky inline home code

### Этап 2

- home JS split
- survey lazy path
- remove Font Awesome from home
- rethink Bootstrap JS on home
- lazy mount hidden modals/panels
- ввести единый `data-device-class`

### Этап 3

- visual cheaper mode
- page-scoped CSS
- cleanup hidden global UI and modal payload
- careful containment / `content-visibility`
- anonymous page cache / fragment cache where safe

## Как измерять успех после каждого этапа

Повторять тот же production loop:

1. `curl` на `https://twocomms.shop/`
2. `lighthouse` mobile x3
3. `lighthouse` desktop x1
4. Chrome trace / network list / console
5. проверка первых карточек в production HTML
6. сравнение:
   - LCP
   - TTI
   - total bytes
   - images transfer
   - fonts transfer
   - third-party transfer
   - long tasks
   - число элементов с `backdrop-filter`
   - число animated elements
   - initial DOM size
   - наличие heavy hidden shells в initial HTML

## Итоговый приоритет

| Приоритет | Действие | Ожидаемый эффект | Визуальный риск |
| --- | --- | --- | --- |
| P0 | Починить missing optimized images | очень высокий | нулевой |
| P0 | Убрать duplicate font loads | высокий | низкий |
| P0 | Отложить/сузить third-party stack | очень высокий | нулевой |
| P0 | Упростить mobile layout work | высокий | низкий |
| P1 | Split `main.js` и home startup path | высокий | нулевой |
| P1 | Убрать лишний CSS/Font Awesome/Bootstrap JS | средне-высокий | нулевой |
| P1 | Lazy survey modal | средний | нулевой |
| P1 | Убрать inline payload из HTML | средний | нулевой |
| P1 | Lazy mount hidden UI shells | средний | нулевой |
| P2 | Cheaper visual mode для weak devices | средне-высокий | низкий |
| P2 | Unified `data-device-class` architecture | высокий на mobile | низкий |
| P2 | Anonymous cache / fragment cache | средний | низкий |

## Вывод

Главную страницу можно сильно ускорить без заметной потери визуального образа.  
Самый большой выигрыш дадут не “мелкие чистки”, а четыре системных изменения:

1. закрыть дырки image optimization
2. перестать платить за duplicate fonts
3. перестать тянуть полный marketing/analytics stack в ранний home-path
4. сделать home легче по startup JS и layout work

Если делать именно в этом порядке, можно получить реальное ускорение на всех устройствах, а на слабых телефонах разница будет очень заметной даже без визуального редизайна.

Дополнительный вывод после deep dive:

- следующий агент не должен повторно тратить время на доказательство того, что главные проблемы уже локализованы
- основной следующий шаг теперь не аудит, а аккуратный рефакторинг delivery path, visual layers и mobile startup behavior
