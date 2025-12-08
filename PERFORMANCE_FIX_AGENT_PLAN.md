# План для агента по исправлению производительности

Цель: самостоятельно найти и устранить проблемы производительности, отражённые в последнем отчёте Lighthouse (мобильный профиль: FCP ~5.2s, LCP ~13.9s, TBT ~370ms, Speed Index ~7.6s, CLS 0) и скриншотах. Достичь заметного прироста (ориентиры: FCP < 2.5s, LCP < 4–5s, TBT < 200ms на мобильной 4G эмуляции), минимизировать блокирующие запросы, уменьшить полезную нагрузку сети и устранить forced reflow.

## 1. Быстрый baseline перед правками
- Прогнать Lighthouse/PSI mobile (4G throttling) по страницам: главная (`/`), каталог (`/catalog/`), карточка товара (`/product/<slug>`).
- Зафиксировать: LCP-элемент, список блокирующих CSS/JS, вес и TTFB крупных ресурсов, Total Blocking Time (длинные задачи >50ms).
- Снять Chrome trace / DevTools Performance для главной: найти длинные таски и layout thrash.

## 2. CSS: блокировки и неиспользуемый код
- Проверить подключение в `twocomms/twocomms_django_theme/templates/base.html`:
  - `styles.purged.css`, `cls-ultimate.css`, `fonts.css` — убедиться, что нет блокирующих `<link rel="stylesheet">` без onload/preload.
  - Выявить неиспользуемые блоки (Lighthouse совет “Remove unused CSS”). Если purge недостаточен: сократить safelist в `postcss.config.js`, разбить CSS на critical (hero, navbar, above-the-fold) и deferred (карточки, анимации, админ-части).
  - Оценить необходимость `cls-ultimate.css`: если используется частично — вынести нужное, остальное грузить лениво.
- Пересобрать CSS и проверить вес итогового бандла (<150–200 KB gz).
- Риск: удаление динамических классов (modals/offcanvas/toasts/tooltips). Перед вырезанием — убедиться, что safelist покрывает их.

## 3. Изображения и LCP
- Главный LCP-элемент: hero/featured изображение на главной. Проверить:
  - Использование `{% optimized_image %}` с корректным `fetchpriority="high"` и `sizes` для LCP-изображений.
  - Реальный ответ сервера: отдаётся AVIF/WEBP, нет загрузки исходника >500KB.
  - В hero отключить/заменить тяжелые фоновые градиенты/particles для мобильных (не только `perf-lite`), либо сделать лёгкий фон для `<768px`.
- Каталог/карточки: убедиться, что первые карточки eager действительно тянут сжатые версии из `media/products/optimized`. Проверить размеры/формат в реальном waterfall.
- Повторно оптимизировать большие category covers/hero (если остались >200KB).

## 4. JS и принудительная компоновка
- Найти источники forced reflow (отчёт: `main.js`, `modules/optimizers.js`). Проверить:
  - Чтение layout (offsetWidth/scrollTop) сразу после записи стилей/DOM; обернуть в `requestAnimationFrame` или разделить чтение/запись.
  - Инициализацию галереи на карточке товара: убедиться, что перестановка DOM не блокирует первый рендер (отложить после first paint или idle).
  - Использовать passive listeners для scroll/touch, кешировать размеры в scroll-обработчиках.
- Снизить TBT: разбить длинные синхронные таски >50ms (по trace) на чанки/idle.

## 5. Шрифты
- Проверить набор в `fonts.css`: Inter 400/500/600/700. Оценить сокращение начертаний для мобильной первой загрузки или добавить system stack fallback для первых кадров.
- Убедиться в Cache-Control immutable (WhiteNoise) и наличии preconnect/dns-prefetch при необходимости.

## 6. Сторонние скрипты
- GTM/FB/TikTok/Clarity: отложить загрузку после main content, рассмотреть lazy GTM с буфером dataLayer. Риск: потеря части событий — согласовать с маркетингом.
- Убедиться, что сторонние скрипты не блокируют основное дерево (defer/async).

## 7. Кэш и заголовки
- Проверить реальные ответы статики/медиа: Cache-Control immutable для css/js/woff, долгое хранение для изображений. Файлы отдаются с актуальными хешами (CompressedManifest).
- Если CDN/прокси отдаёт старые версии — задокументировать необходимость инвалидации.

## 8. Perf-lite и тяжёлые эффекты
- Уже отключены hero particles/logo в `perf-lite`. Рассмотреть автоматическое включение `perf-lite` для мобильных (<768px) или по `save-data`, чтобы облегчить фон и убрать blur/backdrop.
- Проверить, не осталось ли heavy backdrop-filter в мобильных блоках.

## 9. План работы и проверок
- Сначала: измерить baseline (п.1). Затем: по приоритету — CSS блокировки → LCP-изображение → JS forced reflow → сторонние скрипты.
- После каждого шага: короткий Lighthouse run (mobile) + ручная проверка FOUC/стилей на главной/каталоге/карточке, smoke модалки/offcanvas/dropdown.
- Финал: снять контрольные метрики (LCP/FCP/TBT/Speed Index), зафиксировать LCP элемент и размеры.

## 10. Ожидаемый результат
- FCP заметно < 3s, LCP < 5s на моб. 4G эмуляции; TBT < 200ms; уменьшенный CSS вес; отсутствие крупных блокирующих запросов; LCP-изображение отдаётся в AVIF/WEBP; нет FOUC/регрессий UI.

## Файлы и области внимания
- Шаблоны: `twocomms/twocomms_django_theme/templates/base.html`, `templates/pages/index.html`, `pages/catalog.html`, `pages/product_detail.html`, `partials/product_card.html`.
- Статика CSS: `twocomms/twocomms_django_theme/static/css/styles.purged.css`, `css/cls-ultimate.css`.
- JS: `twocomms/staticfiles/js/main.js`, `twocomms/staticfiles/js/modules/optimizers.js`.
- Purge/config: `postcss.config.js`.
- Кеш/headers: `twocomms/twocomms/cache_headers.py`, `production_settings.py`.
- Изображения: `twocomms/storefront/templatetags/responsive_images.py`, `optimized_image.html`, реальные файлы в `twocomms/media/**`.
