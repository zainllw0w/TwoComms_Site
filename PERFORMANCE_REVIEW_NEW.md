# Новый отчёт Lighthouse (mobile) — что искать и как анализировать

Цель: передать агенту полный список находок и точек внимания, чтобы не тратить токены на «разведку». Агент сам решает, как чинить, но понимает суть проблем и где копать.

## 1. Блокирующий CSS / неиспользуемый CSS
- Проблема: `output.adfe271c0bd0.css` блокирует отрисовку (экономия ~2.72s, 51.8 KiB). Неиспользуемый CSS: ~89 KiB (output + all.min.css + bootstrap.min.css).
- Где смотреть:
  - Подключения в `twocomms/twocomms_django_theme/templates/base.html` (compress block).
  - Содержимое `twocomms/twocomms_django_theme/static/css/styles.purged.css`, `cls-ultimate.css`, `staticfiles/css/all.min.css`, Bootstrap CDN.
- Что выяснить: можно ли выделить critical CSS (above-the-fold) и отложить остальное; есть ли дублирующие/мертвые стили (priceGradientFlow, glow, particles, admin/unused компоненты).
- Риски: FOUC при агрессивном отложении, потеря динамических классов при purge.

## 2. Неиспользуемый JS / уменьшить размер JS
- Проблема: неиспользуемый JS ~221 KiB (GTM/FB/TikTok), отдельная экономия ~12 KiB на собственных (`main.js`, `analytics-loader.js`).
- Где смотреть:
  - Подключения в `base.html` (GTM, FB, TikTok, Clarity), `static/js/analytics-loader.js`, `static/js/main.js`.
  - Проверить, нет ли повторной загрузки gtag/gtm, дублирующих метрик.
- Что выяснить: можно ли отложить сторонние скрипты (после взаимодействия/после LCP), урезать `analytics-loader.js` (поллифилы, лишние проверки), дробить main.js (lazy функционал, не нужен на первом экране).

## 3. Принудительная компоновка (Forced Reflow)
- Проблема: источники main.js?v=40 (~1248:47, 453:29) и `modules/optimizers.js:38:18`, суммарно 94 ms.
- Где смотреть:
  - В main.js найти места чтения layout (offsetWidth/scrollTop) сразу после записи; обернуть в rAF/idle или разделить чтение/запись.
  - В `modules/optimizers.js` проверить scroll/touch обработчики и измерения DOM, кешировать размеры/лимитировать частоту.
- Что выяснить: можно ли убрать синхронные перестановки галереи/миникарты до первого рендера.

## 4. Дерево зависимостей (критический путь)
- Проблема: цепочка до 3.2s: main.js → cart/summary + favorites/count → modules (optimizers/product-media/homepage) → output.css → 4 шрифта Inter (110 KiB каждый).
- Где смотреть:
  - main.js: запросы cart/summary и favorites/count — отложить/делать после idle/interaction?
  - Подключение modules (homepage/product-media/optimizers) — можно ли грузить позже или по условию страницы?
  - Шрифты: уменьшить набор/вес, font-display swap, система fallback.
- Что выяснить: какие элементы LCP требуют шрифта (hero title?), можно ли использовать system stack для LCP-текста.

## 5. LCP
- Проблема: LCP ~10.5s, LCP элемент — текст hero-title-main (“Стріт & мілітарі”). Задержка отрисовки элемента 2350 ms.
- Где смотреть:
  - CSS/JS, которые блокируют первый paint: output.css + main.js цепочка.
  - Шрифты Inter (4 файла ~110 KiB каждый) — влияют на текст LCP; проверить font-display и fallback.
  - Картинка hero: проверить fetchpriority/srcset/sizes (не на скриншоте, но обычно влияет).
- Что выяснить: ускорение текста LCP через system font на старте + критический CSS для hero.

## 6. Длинные задачи (TBT)
- Проблема: 6 долгих задач, основные виновники — GTM (gtag.js, gtm.js), FB (config, fbevents), Clarity, main.js.
- Где смотреть:
  - Отложенная загрузка/инициализация сторонних: запустить после взаимодействия или после load с debounce.
  - main.js: разбить инициализацию на чанки (setTimeout/idle), отключить ненужное на главной.
- Что выяснить: какие функции main.js дают 62 ms (по отчёту); разделить их по страницам/условиям.

## 7. Некомбинированные анимации
- Проблема: 8 элементов с анимациями (priceGradientFlow и пр.), фоновые filter/box-shadow.
- Где смотреть:
  - В `styles.purged.css` для классов `.priceGradientFlow` и сопутствующих.
- Что выяснить: отключить/упростить для мобильного/perf-lite или полностью убрать filter/background-position анимации, заменить на transform/opacity.

## 8. Избыточная нагрузка на сеть
- Проблема: общая полезная нагрузка ~8.3 MB; основные: крупные product PNG/JPG (до 5 MB), шрифты Inter (4x110 KiB), сторонние GTM/FB/TikTok.
- Где смотреть:
  - `twocomms/media/products/` — проверить наличие необработанных крупных исходников, убедиться, что выдаются AVIF/WebP/уменьшенные размеры.
  - Шрифты — оптимизировать набор начертаний или subsetting.
  - Сторонние — отложить загрузку/trim config.
- Что выяснить: нет ли регрессии в отдаче оригиналов вместо optimized версий.

## 9. Кэш / TTL
- Проблема: ожидаемая экономия 944 KiB на кешировании (многие ресурсы 7d).
- Где смотреть:
  - `twocomms/twocomms/cache_headers.py`, `production_settings.py` — убедиться, что статика/медиа получают длинный max-age (180d для css/js/woff), медиа — 30d+.
- Что выяснить: реально ли отправляются правильные заголовки (проверить curl -I на css/js/fonts/media).

## 10. Оптимизация DOM
- Проблема: общее число элементов 720, глубина 12 (не критично), но стоит проверить SVG/icons.
- Где смотреть:
  - Компоненты с иконками/звёздами (points-icon-small svg path).
- Что выяснить: можно ли заменить SVG на sprite/inline меньшего объёма или использовать иконшрифт/emoji где приемлемо.

## 11. Устаревший JS (Facebook)
- Проблема: полифилы от FB (Array.* и Object.*), потеря 43 KiB.
- Где смотреть:
  - Нельзя менять у Facebook, но можно отложить загрузку fb скриптов или грузить только при необходимости/после согласия.
- Что выяснить: есть ли возможность lazy-load FB SDK после user interaction.

## 12. Конкретные файлы/точки для анализа
- Шаблоны: `twocomms/twocomms_django_theme/templates/base.html` (CSS/JS подключение), `pages/index.html` (hero/LCP), `partials/product_card.html`.
- JS: `twocomms/twocomms_django_theme/static/js/main.js`, `static/js/analytics-loader.js`, `modules/optimizers.js`, `modules/homepage.js`, `modules/product-media.js`.
- CSS: `twocomms/twocomms_django_theme/static/css/styles.purged.css`, `cls-ultimate.css`, `staticfiles/css/all.min.css`, Bootstrap CDN.
- Кеш: `twocomms/twocomms/cache_headers.py`, `production_settings.py`.
- Изображения: медиа директория + `responsive_images.py`/`optimized_image.html` для выдачи AVIF/WebP.

## 13. Риски при будущих правках
- Compressor offline: любые изменения CSS/JS подключения требуют `python manage.py compress --force` и перезапуск lswsgi, иначе 500.
- Aggr. defer CSS/JS: возможен FOUC/потеря функционала (модалки/offcanvas/hover). Нужен smoke-тест на главной/каталоге/карточке/модалках.

## 14. Метрики для контроля после фиксов
- LCP < ~4–5s, FCP < 2s, TBT < 150–200ms на mobile 4G эмуляции.
- Вес CSS < ~150–200 KiB (gz) в критическом пути.
- Сторонние скрипты: загрузка после интеракции или после load с задержкой; отсутствие длинных задач >50–100ms.
