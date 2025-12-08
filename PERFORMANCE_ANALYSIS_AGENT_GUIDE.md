# Инструкция для аналитика производительности

Цель: дотошно проанализировать текущий фронт/статику, сформировать точечный список изменений для разработчика. Не менять код, а подготовить обоснованные правки, риски и точки контроля.

## 1) Контекст и отправная точка
- Текущий скоринг Lighthouse (mobile, 4G throttling, 1-page session): FCP ~5.2s, LCP ~13.9s, TBT ~370ms, CLS = 0.
- Недавние изменения: оптимизированы изображения в `twocomms/media/products` (качество 80, max-width 1400), FontAwesome загружается неблокирующе, `perf-lite` жёстко отключает фоновые эффекты/particles/hero-logo, основные стили переведены на preload+onload. `styles.purged.css` собран postcss-purgecss 7.0.2 (контент: templates + статический JS).
- Статика (главное): `twocomms/twocomms_django_theme/templates/base.html`, CSS в `twocomms/twocomms_django_theme/static/css/*.css`, JS в `twocomms/staticfiles/js/main.js` и `modules/optimizers.js`. Статика отдаётся через WhiteNoise + compressor (CompressedManifestStaticFilesStorage).

## 2) Метрики и что собрать
- Lighthouse/PSI mobile: снимки до/после для главной, каталога, карточки товара.
- WebPageTest или Chrome trace: waterfall, Largest Contentful Paint element, загрузка CSS/JS (кто блокирует render).
- Размеры и кэш: проверить заголовки Cache-Control для статики/медиа (ожидается immutable 180d для css/js/woff), валиден ли хеш (CompressedManifest).
- Critical Rendering Path: какие CSS остаются блокирующими (проверь preload→stylesheet, наличие старого blocking link).
- Network: список ресурсов >100 KB и долгие TTFB.

## 3) Гипотезы для улучшения (готовь план с обоснованием/рисками)
### CSS
- Удалить «мертвые» куски из `styles.purged.css` (320 KB). Проверить safelist в `postcss.config.js`: возможно, убрать лишние greedy маски или дробить CSS на critical + deferred (например, hero + навигация критические, остальное lazy).
- Проверить подключение Bootstrap CDN: сейчас preload+onload, но остаётся сеть с CDN. Рассмотреть локальный build + tree-shake компонентов или `media="print"` trick как дополнительный fail-safe для FOUC. Риск: поломка стилей компонентов, нужно smoke на формах/модалках.
- Проверить `cls-ultimate.css`: оценить нужность/объём; если частично используется — вынести необходимое, остальное lazy/conditional.

### JS / Forced reflow
- В отчёте упоминался forced layout из `main.js` и `modules/optimizers.js` (вызовы измерений offsetWidth/scrollTop). Найти участки, где чтение layout сразу после записи стиля/DOM, и предложить:
  - использовать `requestAnimationFrame`/`setTimeout 0` разделение;
  - кешировать размеры вне циклов скролла;
  - использовать passive listeners.
- Проверить инициализацию галереи в product detail (`main.js` около перемещения галереи) на предмет синхронных перестроек.
- Оценить TBT: найти длинные таски >50ms в trace, предложить расщепление/idle.

### Изображения и LCP
- Главный LCP элемент — hero или featured-блок на главной. Проверить:
  - Убедиться, что LCP image отдается в AVIF/WEBP через `optimized_image` с корректным `fetchpriority="high"` и `sizes`.
  - В hero отключить тяжелые фоновые градиенты/particles для всех мобильных (не только perf-lite) или заменить статику на лёгкий слой.
  - Проверить catalog/product_card: первых 2 карточек eager; убедиться, что `optimized_image` генерит srcset/avif/webp и не грузит оригиналы 5+ MB (должно быть после оптимизации, но нужно контроль).

### Шрифты
- `fonts.css` подключается прелоадом; проверить наличие лишних начертаний (Inter 400/500/600/700). Предложить сократить набор для мобильной версии или заменить на system stack как fallback. Риск: изменение визуала, проверять в хэдерах/кнопках.
- Кэш: убедиться в Cache-Control immutable.

### Сторонние скрипты
- GTM/FB/TikTok/Clarity: убедиться, что они грузятся после main content (data attributes в `<html>`). Предложить delay загрузки GTM до first interaction или с помощью `dataLayer` буфера. Риск: потеря части событий до загрузки — договориться с продакт/маркетинг.

### Блокирующие запросы
- Проверить, нет ли оставшихся `rel="stylesheet"` без onload (поиск в шаблонах).
- Посмотреть на локальный `fontawesome` — уже preload, но уточнить вес/нужность всего набора.

### Кэш и статика
- Проверить, что новые медиа-версии сжаты и отдаются (inspect реальных URLs/headers на проде). Если CDN/кеш отдает старые версии — нужно инвалидация/пересборка.
- Убедиться, что WhiteNoise headers (`cache_headers.py`) реально применяются (проверка ответа через curl).

## 4) Подводные камни/риски и где ловить баги
- CSS purge: возможен вынос динамических классов (modals, toasts, Bootstrap states). Проверять в `postcss.config.js` safelist; smoke-тесты: модалки, offcanvas, dropdown, toasts, tooltips, состояния `show/fade/collapsing`, а также кастомные классы типа `reveal-*`, `effects-high/lite`.
- Lazy/defer CSS: риск FOUC. Проверять первую отрисовку hero/navbar/buttons на мобилке (эмуляция Throttling 4G, Moto G).
- Отключение фоновых эффектов: может исчезнуть фирменный фон на desktop; проверить на десктопе/мобайл с/без `prefers-reduced-motion`.
- Изображения: после сжатия — визуальные артефакты; проверить hero, featured, product cards (первые 6), product detail main image.
- GTM delay: риск пропуска события pageview/конверсий. Нужен согласованный window of delay + фолбек.

## 5) Где смотреть и как фиксировать выводы
- Шаблоны: `twocomms/twocomms_django_theme/templates/base.html`, `templates/pages/index.html`, `pages/catalog.html`, `pages/product_detail.html`, `partials/product_card.html`.
- Статика: `twocomms/twocomms_django_theme/static/css/styles.purged.css`, `css/cls-ultimate.css`, `staticfiles/js/main.js`, `modules/optimizers.js`.
- Конфиг purge: `postcss.config.js`.
- Кеш/Headers: `twocomms/twocomms/cache_headers.py`, `production_settings.py` (WhiteNoise).
- Оптимизация изображений: `twocomms/storefront/templatetags/responsive_images.py`, `optimized_image.html`.

## 6) Формат результата аналитика
Подготовить отдельный файл (например, `PERFORMANCE_CHANGE_PLAN.md`) со структурой:
1. **Наблюдения** (данные из Lighthouse/trace: что блокирует, какой элемент LCP, какие CSS/JS блокируют).
2. **Предлагаемые изменения**: список шагов с файлами/строками, примером кода, ожидаемым эффектом (какой показатель улучшится), метрикой проверки и степенью риска.
3. **Риски и где тестировать**: конкретные страницы и сценарии (модалки, каталог, карточка товара, чек-аут, мобильная навигация).
4. **План проверки**: какие метрики снять после внедрения (LCP/FCP/TBT), какие ручные проверки.

Чем более детально и обоснованно — тем быстрее внедрим без регрессий.
