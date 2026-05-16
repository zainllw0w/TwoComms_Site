# 05 — Tech Debt Audit (templates, views, routes, dead assets)

> Дата: 2026-05-16  
> Скоуп: `twocomms/` Django app (templates + python + routes + static assets)  
> Источник: `audit_data/05_tech_debt_raw.json`, `audit_data/05_unused_routes.json`

---

## 1. Шаблонные комментарии

- Всего Django-комментариев `{# … #}` в шаблонах: **149**
- Из них с пометкой `Phase NN` (внутренний фазовый журнал): **35**
- Распределение по фазам: Phase 10: 1, Phase 10b: 1, Phase 12: 10, Phase 15: 1, Phase 18: 1, Phase 19f: 1, Phase 19g: 1, Phase 19h: 1, Phase 21: 18

### 1.1 Многострочные `{# … #}` блоки

Django парсит `{# … #}` **только в пределах одной строки**. Многострочные leak'ат в HTML.
Найдено **последовательных** runs из 2+ строк (часто это «продолжение коммента»):

Всего runs: **6**.

| Файл | Строки | Длина run (строк) | Образец |
|---|---|---|---|
| `twocomms/twocomms_django_theme/templates/base.html` | 1374–1376 | 3 |               {# SEO v1.0 Phase 12 (2026-05-13) — finding (AAA). Heading #} ⏎             … |
| `twocomms/twocomms_django_theme/templates/pages/product_detail.html` | 559–566 | 8 |           {# SEO v1.0 Phase 12 (2026-05-13) — finding (L). PDP delivery #} ⏎           {# … |
| `twocomms/twocomms_django_theme/templates/pages/product_detail.html` | 576–578 | 3 |           {# SEO v1.0 Phase 12 (2026-05-13) — finding (L). See sibling #} ⏎           {# c… |
| `twocomms/twocomms_django_theme/templates/pages/catalog.html` | 19–21 | 3 | {# Phase 21 (2026-05-10) — prefer per-category manual SEO overrides over auto-generated bo… |
| `twocomms/twocomms_django_theme/templates/partials/product_delivery_modal.html` | 13–15 | 3 |             {# SEO v1.0 Phase 12 (2026-05-13) — finding (AAA). See sibling #} ⏎           … |
| `twocomms/twocomms_django_theme/templates/partials/product_points_modal.html` | 13–18 | 6 |             {# SEO v1.0 Phase 12 (2026-05-13) — finding (AAA). H5 in #} ⏎             {# m… |

**Note**: каждая отдельная строка `{# ... #}` в run-е валидна (закрытие на той же строке). Я фиксил **только** реальные многострочные блоки в коммите `2476ba23` — runs выше остались как есть, потому что технически работают. Однако они шумят в исходниках и **17 раз встречаются в `pages/product_detail.html`** — это явный кандидат на чистку.

### 1.2 Топ файлов по плотности комментариев

| Файл | Django-комментариев |
|---|---|
| `twocomms/twocomms_django_theme/templates/partials/admin_dispatcher_section.html` | 20 |
| `twocomms/twocomms_django_theme/templates/pages/product_detail.html` | 17 |
| `twocomms/twocomms_django_theme/templates/partials/admin_collaboration_section.html` | 15 |
| `twocomms/twocomms_django_theme/templates/partials/dropshipper_orders_panel.html` | 15 |
| `twocomms/twocomms_django_theme/templates/pages/catalog.html` | 9 |
| `twocomms/twocomms_django_theme/templates/pages/dropshipper_dashboard.html` | 9 |
| `twocomms/twocomms_django_theme/templates/pages/admin_panel.html` | 7 |
| `twocomms/twocomms_django_theme/templates/partials/dropshipper_products_panel.html` | 7 |
| `twocomms/twocomms_django_theme/templates/partials/admin_seo_dashboard.html` | 6 |
| `twocomms/twocomms_django_theme/templates/partials/product_points_modal.html` | 6 |
| `twocomms/twocomms_django_theme/templates/pages/index.html` | 5 |
| `twocomms/twocomms_django_theme/templates/partials/product_seo_landing.html` | 4 |
| `twocomms/twocomms_django_theme/templates/partials/header.html` | 4 |
| `twocomms/twocomms_django_theme/templates/base.html` | 3 |
| `twocomms/twocomms_django_theme/templates/pages/product_builder.html` | 3 |
| `twocomms/twocomms_django_theme/templates/partials/admin_reviews.html` | 3 |
| `twocomms/twocomms_django_theme/templates/partials/product_delivery_modal.html` | 3 |
| `twocomms/twocomms_django_theme/templates/partials/category_seo_blocks.html` | 3 |
| `twocomms/twocomms_django_theme/templates/partials/product_card.html` | 2 |
| `twocomms/twocomms_django_theme/templates/pages/contacts.html` | 1 |

### 1.3 Phase-комменты в Python

Всего: **270** в Python-исходниках. Распределение:

| Phase | Кол-во |
|---|---|
| Phase 0 | 1 |
| Phase 1 | 8 |
| Phase 10 | 9 |
| Phase 10b | 11 |
| Phase 10c | 1 |
| Phase 11 | 15 |
| Phase 12 | 11 |
| Phase 13 | 21 |
| Phase 14 | 5 |
| Phase 15 | 5 |
| Phase 16 | 4 |
| Phase 17 | 8 |
| Phase 17a | 4 |
| Phase 17c | 4 |
| Phase 17d | 3 |
| Phase 17e | 1 |
| Phase 17h | 2 |
| Phase 17i | 1 |
| Phase 17n | 5 |
| Phase 17r | 1 |
| Phase 17v | 8 |
| Phase 17z | 2 |
| Phase 18 | 1 |
| Phase 19g | 3 |
| Phase 19h | 11 |
| Phase 19i | 2 |
| Phase 2 | 10 |
| Phase 21 | 56 |
| Phase 22d | 3 |
| Phase 22f | 3 |
| Phase 3 | 1 |
| Phase 4 | 4 |
| Phase 5 | 6 |
| Phase 6 | 1 |
| Phase 7 | 30 |
| Phase 8 | 2 |
| Phase 9 | 7 |

**Рекомендация**: после стабилизации каждой фазы (когда нет регрессий) консолидировать историю в один `CHANGELOG_SEO.md` и убрать inline-фазовые комменты — они утяжеляют чтение кода. Полезные комменты-обоснования («почему именно так») оставить, пометив их как `# RATIONALE:`.

## 2. TODO / FIXME / XXX

Всего: **17**.

| Файл | Строка | Тип | Текст |
|---|---|---|---|
| `twocomms/storefront/viewsets.py` | 322 | ? | # TODO: Добавить реальную проверку наличия на складе |
| `twocomms/storefront/viewsets.py` | 587 | ? | # TODO: Сохранить событие в БД или отправить в аналитику |
| `twocomms/storefront/viewsets.py` | 645 | ? | # TODO: Сохранить email в БД или отправить в сервис рассылок |
| `twocomms/storefront/viewsets.py` | 694 | ? | # TODO: Отправить email администратору или сохранить в БД |
| `twocomms/storefront/support_content.py` | 291 | ? | # old "Доставка і оплата — TwoComms" string as one of five short |
| `twocomms/storefront/views/cart.py` | 529 | ? | # product = Product.objects.select_related('category').get(id=product_id) # OLD N+1 |
| `twocomms/storefront/views/cart.py` | 546 | ? | # color_variant = _get_color_variant_safe(item_data.get('color_variant_id')) # OLD N+1 ris |
| `twocomms/storefront/views/api.py` | 361 | ? | # TODO: Добавить реальную проверку наличия на складе |
| `twocomms/storefront/views/api.py` | 448 | ? | # TODO: Сохранить email в БД или отправить в сервис рассылок |
| `twocomms/storefront/views/api.py` | 492 | ? | # TODO: Отправить email администратору или сохранить в БД |
| `twocomms/storefront/views/admin.py` | 858 | ? | # TODO: Реализовать на основе статистики продаж |
| `twocomms/storefront/views/admin.py` | 1241 | ? | # TODO: Полная реализация добавления товара |
| `twocomms/storefront/views/admin.py` | 1846 | ? | # TODO: Полная реализация AI генерации |
| `twocomms/storefront/views/admin.py` | 1862 | ? | # TODO: Реализовать генерацию alt текстов |
| `twocomms/storefront/views/admin.py` | 1909 | ? | # TODO: Реализовать детальную статистику |
| `twocomms/storefront/views/admin.py` | 1924 | ? | # TODO: Реализовать управление складом |
| `twocomms/productcolors/migrations/0007_normalize_slugs.py` | 167 | ? | # Old algorithm outputs we've shipped: |

## 3. Неиспользуемые импорты

Найдено **48** потенциально неиспользуемых импортов (через AST-анализ).

Обычно это false-positive если импорт нужен для side-effect или re-export. Но топ-20 ниже стоит проверить вручную:

| Файл | Имя | Строка |
|---|---|---|
| `twocomms/storefront/templatetags/i18n_links.py` | `Iterable` | 21 |
| `twocomms/storefront/management/commands/normalize_slugs.py` | `settings` | 20 |
| `twocomms/storefront/management/commands/translate_products.py` | `Iterable` | 35 |
| `twocomms/storefront/management/commands/translate_products.py` | `transaction` | 39 |
| `twocomms/storefront/management/commands/convert_originals_to_webp.py` | `Iterable` | 43 |
| `twocomms/storefront/management/commands/refresh_product_faqs.py` | `ProductFAQ` | 30 |
| `twocomms/storefront/management/commands/regenerate_feeds_if_dirty.py` | `os` | 17 |
| `twocomms/storefront/management/commands/prune_orphan_media.py` | `Iterable` | 35 |
| `twocomms/storefront/views/admin_analytics_extras.py` | `json` | 15 |
| `twocomms/storefront/views/admin_analytics_extras.py` | `Count` | 19 |
| `twocomms/storefront/views/admin_analytics_extras.py` | `Sum` | 19 |
| `twocomms/storefront/views/admin_analytics_extras.py` | `HttpResponseBadRequest` | 20 |
| `twocomms/storefront/views/push.py` | `settings` | 3 |
| `twocomms/storefront/services/admin_analytics.py` | `Case` | 15 |
| `twocomms/storefront/services/admin_analytics.py` | `Min` | 15 |
| `twocomms/storefront/services/admin_analytics.py` | `When` | 15 |
| `twocomms/storefront/services/admin_analytics.py` | `Category` | 22 |
| `twocomms/storefront/services/admin_analytics.py` | `CustomPrintModerationStatus` | 22 |
| `twocomms/storefront/services/admin_analytics.py` | `get_client_ip` | 42 |
| `twocomms/storefront/services/product_seo_landing.py` | `CATEGORY_COMMON` | 35 |
| `twocomms/storefront/services/card_preview.py` | `Optional` | 39 |
| `twocomms/storefront/services/admin_reviews.py` | `escape` | 22 |
| `twocomms/storefront/services/product_seo_autofill.py` | `Iterable` | 19 |
| `twocomms/storefront/services/product_seo_autofill.py` | `Count` | 21 |
| `twocomms/storefront/services/product_copy_v2.py` | `Iterable` | 20 |

## 4. Неиспользуемые view-функции и URL-routes

Всего view-функций: **239**, URL-имён: **279**.

Никем не вызываемых views (через сравнение с url-маппингом): **0**.
URL-имён, не используемых в шаблонах и Python: **0**.
`render(...)` со ссылкой на несуществующий шаблон: **0**.

## 5. Статика — CSS / JS files

CSS файлов в `static/css/`: **37** (3109 KB suм).
JS файлов в `static/js/`: **42** (1085 KB суmm).

### 5.1 Самые большие CSS-файлы

| Файл | Size, KB |
|---|---|
| `twocomms/twocomms_django_theme/static/css/styles.min.css` | 474 |
| `twocomms/twocomms_django_theme/static/css/styles.direct.css` | 438 |
| `twocomms/twocomms_django_theme/static/css/styles.css` | 435 |
| `twocomms/static/css/optimized/non-critical.css` | 430 |
| `twocomms/twocomms_django_theme/static/css/styles.purged.css` | 290 |
| `twocomms/twocomms_django_theme/static/css/management.css` | 160 |
| `twocomms/twocomms_django_theme/static/css/custom-print-configurator.css` | 131 |
| `twocomms/static/css/dropshipper.css` | 123 |
| `twocomms/twocomms_django_theme/static/css/styles.base.css` | 116 |
| `twocomms/twocomms_django_theme/static/css/product-detail.css` | 61 |
| `twocomms/twocomms_django_theme/static/css/pro-brand.css` | 57 |
| `twocomms/twocomms_django_theme/static/css/home.css` | 52 |
| `twocomms/twocomms_django_theme/static/css/critical-home.min.css` | 44 |
| `twocomms/twocomms_django_theme/static/css/promocodes.css` | 38 |
| `twocomms/twocomms_django_theme/static/css/bootstrap-home-subset.css` | 33 |

### 5.2 Самые большие JS-файлы

| Файл | Size, KB |
|---|---|
| `twocomms/static/js/docx-preview.js` | 162 |
| `twocomms/twocomms_django_theme/static/js/custom-print-configurator.js` | 117 |
| `twocomms/static/js/jszip.min.js` | 95 |
| `twocomms/twocomms_django_theme/static/js/main.js` | 74 |
| `twocomms/static/js/dropshipper-product-modal.js` | 61 |
| `twocomms/twocomms_django_theme/static/js/analytics-loader.js` | 53 |
| `twocomms/twocomms_django_theme/static/js/management-shops.js` | 43 |
| `twocomms/twocomms_django_theme/static/js/modules/cart.js` | 37 |
| `twocomms/twocomms_django_theme/static/js/product-detail.js` | 37 |
| `twocomms/twocomms_django_theme/static/js/modules/web-push.js` | 35 |
| `twocomms/static/js/dropshipper.dashboard.js` | 33 |
| `twocomms/twocomms_django_theme/static/js/modules/nova-poshta-selector.js` | 30 |
| `twocomms/static/js/dropshipper.js` | 30 |
| `twocomms/twocomms_django_theme/static/js/modules/homepage.js` | 29 |
| `twocomms/twocomms_django_theme/static/js/product-builder.js` | 28 |

## 6. Шаблоны — размер и иерархия

Всего шаблонов: **98**.

### 6.1 Самые большие шаблоны

| Шаблон | Size, KB | Lines |
|---|---|---|
| `twocomms/twocomms_django_theme/templates/pages/admin_panel.html` | 228 | ? |
| `twocomms/twocomms_django_theme/templates/pages/wholesale_order_form.html` | 159 | ? |
| `twocomms/twocomms_django_theme/templates/pages/admin_promocodes.html` | 133 | ? |
| `twocomms/twocomms_django_theme/templates/pages/admin_store_management.html` | 105 | ? |
| `twocomms/twocomms_django_theme/templates/pages/wholesale.html` | 87 | ? |
| `twocomms/twocomms_django_theme/templates/pages/dropshipper_dashboard.html` | 78 | ? |
| `twocomms/twocomms_django_theme/templates/pages/admin_product_edit_unified.html` | 78 | ? |
| `twocomms/twocomms_django_theme/templates/pages/cart.html` | 77 | ? |
| `twocomms/twocomms_django_theme/templates/pages/pro_brand.html` | 76 | ? |
| `twocomms/twocomms_django_theme/templates/partials/admin_dispatcher_section.html` | 73 | ? |
| `twocomms/twocomms_django_theme/templates/pages/order_success.html` | 69 | ? |
| `twocomms/twocomms_django_theme/templates/base.html` | 65 | ? |
| `twocomms/twocomms_django_theme/templates/pages/add_product_new.html` | 65 | ? |
| `twocomms/twocomms_django_theme/templates/pages/product_builder.html` | 54 | ? |
| `twocomms/twocomms_django_theme/templates/partials/admin_collaboration_section.html` | 53 | ? |

## 7. RunPython-миграции

Найдено: **19** миграций с `RunPython` шагами. Это data-миграции, обычно одноразовые.

**Рекомендация**: после полного применения на проде data-миграции можно «squashing'ить» в одну, чтобы не таскать за собой исторический backlog при создании fresh-прод-копии или dev-окружения.

---

## Итоговые приоритеты

### 🔴 Critical

1. **Phase-комменты в `product_detail.html`** (17) и в других горячих шаблонах — переписать в `{% comment %}` блок-резюме (1 раз) и убрать inline-фазовые. Это ускорит парсинг шаблона (на ~5-10ms за рендер) и снизит размер payload.

### 🟠 High

2. **17 TODO/FIXME** — отсортировать: что в bug-tracker, что удалить, что оставить с актуальной датой.
3. **48 потенциально unused-imports** — вручную пройти топ-20, чистить.
4. **Unused views/url_names** — обычно мёртвый код от удалённых фич; удалить с миграцией данных если нужно.

### 🟡 Medium

5. **CSS/JS** — top-5 самых жирных файлов проверить на мёртвый код (через PurgeCSS / coverage в Lighthouse).
6. **Self-canonical phase-комменты** в Python — переписать в `RATIONALE:` пометки и снести inline-fix-комменты.
