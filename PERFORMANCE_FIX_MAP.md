# Карта проблем Lighthouse и подсказки для фикса

Цель файла: дать агенту максимум контекста и точек поиска, чтобы не тратить токены на разведку. Решения агент прорабатывает сам.

## 1) Блокирующие запросы рендеринга (CSS)
- Отчёт: блокирующий CSS `/static/CACHE/css/output.adfe271c0bd0.css` (~52 KiB, ~930 мс).
- Точки поиска:
  - `twocomms/twocomms_django_theme/templates/base.html` — как подключён бандл (сейчас через `{% compress css %}` -> `output.*.css`). Проверить возможность разделить на critical + deferred или добавить `media="print"` hack, но без ломки offline compressor.
  - Вес/unused: Lighthouse даёт неиспользуемый CSS 89 KiB (output + all.min.css + bootstrap.min.css). Проверить `styles.purged.css`, `all.min.css`, Bootstrap.
  - Purge: `postcss.config.js` safelist/greedy; возможно, критический CSS вынести инлайн, остальное отложить.

## 2) Неиспользуемый CSS (экономия ~89 KiB)
- Источники: `output.adfe271c0bd0.css`, `all.min.css`, `bootstrap.min.css`.
- Где смотреть:
  - `twocomms/twocomms_django_theme/static/css/styles.purged.css`
  - `twocomms/twocomms_django_theme/static/css/cls-ultimate.css`
  - `staticfiles/css/all.min.css` (если используется)
  - Подключение Bootstrap CDN в base.html — проверить, нет ли дублей/лишних компонентов.

## 3) JS: длинные задачи / принудительная компоновка / неиспользуемый JS
- Длинные задачи (TBT): GTM (gtag.js, gtm.js), FB (fbevents.js), TikTok, clarity.js, main.js (6 KB), homepage.js, product-media.js, optimizers.js.
- Принудительная компоновка: main.js?v=40 (строки ~1248:47, 453:29) и modules/optimizers.js:38:18.
- Где смотреть:
  - `twocomms/staticfiles/js/main.js` — найти участки чтения layout (offsetWidth/scrollTop) сразу после записи стилей/DOM; отложить/разделить, кешировать измерения, использовать rAF/idle.
  - `twocomms/staticfiles/js/modules/optimizers.js` — scroll handler, optimizeTouchEvents; проверить, где запрашиваются размеры.
  - Подумать о lazy загрузке homepage/product-media/optimizers вместо modulepreload.
- Неиспользуемый JS (Lighthouse: экономия ~314 KiB, в основном сторонние скрипты):
  - GTM/FB/TikTok: отложить загрузку позже, использовать consent/trigger после интеракции или после LCP; возможно, убрать дубликаты gtag (несколько загрузок).
  - Проверить, не грузится ли gtag трижды (разные ID).

## 4) Сеть / чрезмерная нагрузка
- Собственные ресурсы: крупные PNG/JPG продуктов (до 5 MB) и шрифты Inter (по 110–112 KiB x4).
- Где смотреть:
  - `/twocomms/media/products/**` — проверить, нет ли необработанных оригиналов >500 KiB (оптимизация/конверсия в AVIF/WebP + downscale).
  - Шрифты: `static/fonts/Inter-*.woff2` — можно ограничить набор начертаний (400/700) или subsetting.
  - Проверить, что `optimized_image` реально отдаёт AVIF/WEBP и не тянет исходники.

## 5) Некомбинированные анимации / фильтры
- Lighthouse показывает 15+ анимированных элементов с фильтрами/box-shadow: priceGradientFlow, featuredLineGlow, featuredBadgeGlow, categoryCardCompactAppear, accentLineGlow.
- Где смотреть:
  - CSS анимации в `styles.purged.css` (правила с `priceGradientFlow`, `featured*`, `category-card-compact`, `title-accent-line`).
  - Принять решение: отключить/упростить анимации для mobile/perf-lite (убрать фильтры/box-shadow/gradient animations), или сделать их transform/opacity-only.

## 6) Fetchpriority / LCP
- Сейчас LCP всё ещё высокий. Проверить:
  - Какие элементы являются LCP (hero image/featured блок?). Убедиться, что у LCP картинки `fetchpriority="high"` и правильные `sizes/srcset`. В недавних правках fetchpriority у карточек/featured был снижен до auto — убедиться, что главный LCP (hero/featured) остаётся high.
  - Проверить preconnect/dns-prefetch (минимизировать в head, оставить только критичные?).

## 7) Цепочки критических запросов
- Lighthouse дерево: main.js -> cart summary -> favorites count -> modules/* -> output.css -> шрифты Inter (4 запроса ~110 KB каждый).
- Варианты улучшения:
  - Отложить cart/favorites запросы (не на critical path).
  - Шрифты: использовать font-display: swap и preconnect только если нужно; рассмотреть system font fallback на старт.
  - main.js: дробление/отложенная загрузка функционала, который не нужен на первом экране.

## 8) Кэш / TTL
- Скриншот: 7 дней кеш для многих ресурсов (изображения, JS, CSS). Возможно, WhiteNoise ставит 7d? Проверить `cache_headers.py`/`production_settings.py` — если TTL короткий, увеличить для immutable статики (css/js/woff → 180d). Медиа можно 30d+, если URL с версией/оптимизацией.

## 9) Доступность / неподдерживаемые свойства
- Lighthouse показывает “Неподдерживаемое свойство CSS” для ряда элементов (box-shadow, background-position-x/y). Это в UI hints: можно убрать из критического CSS или заменить на кроссбраузерные варианты.

## 10) Что проверить руками (после правок)
- Главная (hero, featured, категории) на мобильном throttling: нет FOUC, нет смещения, картинки подгружаются быстро.
 - Каталог: первые карточки отображаются с webp/avif, без скачков, lazy для остальных.
 - Карточка товара: галерея/миниатюры не блокируют первый рендер; принудительные reflow отсутствуют.
 - Модалки/корзина/offcanvas/dropdown — стили на месте (после возможного purge/lazy CSS).

## Файлы/директории для агента
- Шаблоны: `twocomms/twocomms_django_theme/templates/base.html`, `templates/pages/index.html`, `templates/partials/product_card.html`.
- JS: `twocomms/staticfiles/js/main.js`, `twocomms/staticfiles/js/modules/optimizers.js`, `modules/homepage.js`, `modules/product-media.js`.
- CSS: `twocomms/twocomms_django_theme/static/css/styles.purged.css`, `cls-ultimate.css`, `staticfiles/css/all.min.css`, Bootstrap CDN.
- Оптимизация изображений: `twocomms/storefront/templatetags/responsive_images.py`, `optimized_image.html`; медиа файлы в `twocomms/media/**`.
- Кэш/заголовки: `twocomms/twocomms/cache_headers.py`, `production_settings.py`.
- Трекинг: GTM/FB/TikTok/Clarity включения в `base.html`.
