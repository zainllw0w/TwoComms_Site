# Глубокий SEO-аудит TwoComms для e-commerce

Дата: 2026-05-10  
Проект: TwoComms, бренд одежды / интернет-магазин / DTF и кастомный принт  
Фокус: внутренняя оптимизация, техническое SEO, индексируемость, коммерческие страницы, schema.org, sitemap, robots, Merchant feed, контент, UX-сигналы доверия и риски для продаж.

## 1. Короткий вывод

SEO-фундамент у проекта уже сильнее среднего для небольшого e-commerce: есть отдельные sitemap, robots.txt, canonical, hreflang uk/x-default, Product schema, BreadcrumbList, FAQPage, Merchant feed, support-страницы, видимая перелинковка, оптимизация изображений и отдельные коммерческие посадочные блоки.

Но есть несколько проблем, которые нельзя считать косметикой:

1. В production HTML попадают Django template comments `{# ... #}`. Это подтверждено публичными страницами и локальным SEO regression test. Для поисковика это мусор в `<head>` и слабый сигнал качества HTML.
2. На всех production product pages виден рейтинг `4.9 (45 відгуків)`, но реальной модели отзывов/рейтинга для storefront не найдено. Это риск доверия, юридической корректности и rich results quality guidelines.
3. На главной есть два Organization JSON-LD блока: базовый из `base.html` и отдельный canonical Organization из `index.html`. Это не всегда ломает выдачу, но создает конфликтный entity graph.
4. Категории индексируются, но их SEO-мета слишком короткие и шаблонные: `Футболки — TwoComms`, `Худі — TwoComms`, `лонгсліви — TwoComms`. Для коммерческой органики этого мало.
5. Per-product SEO landing содержит признаки переоптимизации: городские запросы, city chips на одну и ту же категорию, видимый текст про "ключові слова сторінки для коректного індексу". Это нужно переписать под покупателя, а не под бота.
6. В sitemap есть 65 product URL и 418 variant URL, но image sitemap покрывает только 64 product pages. Один товар из product sitemap не представлен в image sitemap.
7. Merchant feed большой и рабочий, но все 384 item без `gtin`. Если у товаров есть штрихкоды или GTIN в production DB, это нужно отдавать.
8. `/search/?q=...` корректно `noindex`, но `/catalog/?q=...` и похожие произвольные query-дубли остаются `index, follow` с canonical на `/catalog/`. Лучше закрыть такие URL на уровне шаблона/редиректа.
9. Product variant pages self-canonical, но Product JSON-LD `url` на variant URL остается базовым product URL. Это смешивает сигнал "индексируемый вариант" и "товарная сущность базовой страницы".
10. Есть два источника robots: dynamic `/robots.txt` и статический `twocomms/static/robots.txt`, которые отличаются. Если хостинг когда-либо отдаст static-файл напрямую, правила будут другими.

Общая оценка: база хорошая, но проект находится в стадии "много SEO уже добавлено, часть добавлена слишком механически". Следующий этап должен быть не "добавить еще больше ключей", а очистить сигналы, убрать фейковые/SEO-видимые элементы, усилить категории и синхронизировать товарные данные production.

## 2. Что именно проверялось

Проверены:

- Django маршруты, views, templates, middleware, settings.
- Главная, каталог, категории, PDP, variant PDP, search, support pages, custom print, DTF.
- Structured data: Organization, WebSite, Product, Offer, BreadcrumbList, FAQPage, Service, WebPage.
- Sitemap: index, products, product variants, categories, images.
- Robots.txt и query/facet handling.
- Google Merchant feed.
- Production public HTML и XML endpoints на `https://twocomms.shop`.
- Локальные regression tests для SEO.
- Существующие SEO-документы проекта.
- Справочные требования Google Search Central для e-commerce/product/canonical/title/structured data.

Не выполнялись:

- Запись в production DB.
- Деплой.
- Миграции.
- Прямой SQL-аудит production DB через SSH. Пароль из инструкции не вставлялся в команды/файлы, чтобы не оставить секрет в истории. Production-данные проверялись через публичный слой, который фактически видит Google: sitemap, feed и HTML.

## 3. Production-факты

### 3.1 Sitemap

Публичный `https://twocomms.shop/sitemap.xml` отдает 5 секций:

- `sitemap-static.xml`
- `sitemap-products.xml`
- `sitemap-product-variants.xml`
- `sitemap-categories.xml`
- `sitemap-images.xml`

Фактические counts на 2026-05-10:

| Секция | Количество | Вывод |
|---|---:|---|
| Product URLs | 65 | Все 65 product pages дополнительно проверены и отдают 200 |
| Variant URLs | 418 | Большой слой индексируемых size/color/fit страниц |
| Category URLs | 3 | Категорий мало, их нужно усиливать как основные коммерческие landing pages |
| Image sitemap pages | 64 | Минус 1 товар относительно product sitemap |
| Image URLs | 64 | Сейчас image sitemap покрывает только основной image per product |

Проблема image sitemap:

- `https://twocomms.shop/product/HD-twocomms-reality-bends-future-2026/` есть в product sitemap, но отсутствует в image sitemap.
- Код image sitemap берет только `main_image`, хотя PDP/feed умеют использовать дополнительные и variant images.
- Рекомендация: включить `main_image`, дополнительные `ProductImage`, `display_image`, variant images, но только если URL реально доступен и относится к товару.

### 3.2 Product pages

Полный публичный обход 65 product URLs:

| Проверка | Результат |
|---|---:|
| Status 200 | 65 / 65 |
| Title present | 65 / 65 |
| Meta description present | 65 / 65 |
| Product schema present | 65 / 65 |
| Template comments leaked | 65 / 65 |
| Visible `4.9 (45 відгуків)` | 65 / 65 |
| Product schema `OutOfStock` | 16 / 65 |
| Title length | min 36, median 53, max 60 |
| Description length | min 139, median 153, max 160 |

Что хорошо:

- Все sitemap product URL живые.
- Title/meta description по длине в хорошем диапазоне.
- Product schema есть на всех проверенных product pages.
- Availability в schema действительно меняется между `InStock` и `OutOfStock`.

Что плохо:

- 100% product pages имеют HTML-мусор `{# ... #}`.
- 100% product pages показывают рейтинг/отзывы, которые не подтверждены данными.
- 16 product pages в sitemap доступны и индексируемы, но `OutOfStock`. Это не всегда плохо, но нужно решить стратегию: оставлять, если есть спрос/ожидается restock, или снижать акцент/убирать из feed/вариантов, если товар не вернется.

Примеры `OutOfStock` из production:

- `/product/-my-little-baby/`
- `/product/where-mi-present-ts/`
- `/product/kharkiv-district-ts/`
- `/product/-lord-of-the-lending/`
- `/product/-death-gbs-ass-ts/`
- `/product/pojuy-ts/`
- `/product/bentejne-ts/`
- `/product/longsleeve-limited-edition/`
- `/product/-225-tshirt-/`
- `/product/hool-ts/`
- `/product/Idea-hd/`
- `/product/HD-twocomms-reality-bends-future-2026/`
- `/product/-twocomms-reality-bends-future-2026/`
- `/product/-twocomms-reality-bends-dark-neon-edition/`
- `/product/ts-twocomms-reality-bends-mentol/`
- `/product/-twocomms-beliveidea-ts/`

### 3.3 Product slugs

Есть проблемы с URL hygiene:

- Leading hyphen: много URL вида `/product/-my-little-baby/`, `/product/-last-breath/`, `/product/-death-grabs-ass/`.
- Uppercase: `/product/HD-twocomms-reality-bends-future-2026/`, `/product/Idea-hd/`.
- Underscore: `/product/Hoodie_Silent_Winter/`, `/product/-v2-0_Pokrovsk/`.
- Trailing hyphen: `/product/-225-tshirt-/`.

SEO-эффект:

- Это не обязательно блокирует индексацию.
- Но URL выглядят менее аккуратно, хуже воспринимаются пользователем и слабее соответствуют "clean, readable, keyword-forward URL" из чеклиста.
- Исправлять нужно только через 301 redirects и с учетом уже проиндексированных URL, чтобы не потерять текущий вес.

Приоритет: средний. Не делать массово без карты редиректов.

### 3.4 Categories

Production categories:

- `/catalog/long-sleeve/`
- `/catalog/tshirts/`
- `/catalog/hoodie/`

Публичная проверка:

- Все 3 категории отдают 200.
- Canonical корректный.
- H1 один.
- Но title слишком короткие:
  - `лонгсліви — TwoComms`
  - `Футболки — TwoComms`
  - `Худі — TwoComms`

Проблема:

- Для e-commerce category pages это главные коммерческие landing pages.
- Сейчас они выглядят как навигационные страницы, а не как полноценные страницы спроса.
- Метаданные не раскрывают намерение "купить", пол, посадка, материал, принты, доставка, бренд, Украина, цена/ассортимент.

Рекомендация:

- Добавить в `Category` отдельные поля `seo_title`, `seo_description`, возможно `seo_h1`, `seo_intro_html`, `seo_faq`.
- Для каждой категории сделать уникальную структуру: короткий intro, 2-4 смысловых блока, FAQ, блок размеров/посадки, ссылки на релевантные товары и соседние категории.
- Не делать "водяные" SEO-тексты на 3000 слов. Для одежды лучше плотные коммерческие блоки и реальные ответы на вопросы покупателя.

### 3.5 Search и query duplicates

Хорошо:

- `/search/?q=худі` отдает `noindex, follow`.
- Canonical у search ведет на `/catalog/`.

Проблема:

- `/catalog/?q=худі`, `/catalog/?search=худі`, `/catalog/?query=худі` отдают `index, follow`, canonical на `/catalog/`.
- Это не полноценные search pages, но для Google это индексируемые parameter duplicates.

Рекомендация:

- Для любых неразрешенных query params на catalog/category ставить `noindex, follow` или делать 301/302 на чистый canonical URL.
- Оставлять индексируемыми только:
  - чистый `/catalog/`;
  - чистые category URL;
  - pagination URL, если стратегия индексации pagination осознанная;
  - выбранные landing filters, если для них есть уникальный контент и canonical self.

### 3.6 Merchant feed

Production `google_merchant_feed.xml`:

| Метрика | Значение |
|---|---:|
| Items | 384 |
| `in_stock` | 267 |
| `out_of_stock` | 117 |
| Brand | TwoComms, 384 / 384 |
| Description length | min 341, median 1280.5, max 2350 |
| Missing `gtin` | 384 / 384 |
| `mpn` present | 384 / 384 |
| `item_group_id` present | 384 / 384 |
| `color` present | 384 / 384 |
| `size` present | 384 / 384 |
| `google_product_category` present | 384 / 384 |
| `product_type` present | 384 / 384 |
| `product_highlight` count | 1920 |

Что хорошо:

- Feed реальный, большой, variant-aware.
- У товаров есть color/size/item_group_id, что важно для одежды.
- Есть availability и sale_price.
- Titles в выборке не дублируются.
- Описания не тонкие.

Что проверить:

- Если production DB содержит barcode/GTIN, нужно отдавать `g:gtin`.
- Если GTIN нет физически, MPN допустим, но Merchant Center может дать "Limited performance" для части товаров.
- 117 out_of_stock item в feed: нужно понять, это временный stock или устаревшие варианты.
- `custom_label_0` не используется. Для рекламы полезны labels: category, margin tier, bestseller/new, print collection, military/streetwear, stock tier.

## 4. Что сделано хорошо

### 4.1 Техническое SEO

Сильные стороны:

- Root crawler endpoints стоят явно: `/sitemap.xml`, секционные sitemap, `/robots.txt`, `/llms.txt`, verification txt.
- Sitemap index сделан вручную и стабильно использует `SITE_BASE_URL`, а не случайный host из request.
- Product sitemap фильтрует только `status='published'`.
- Category sitemap фильтрует только active categories.
- Variant sitemap есть отдельно, это полезно для long-tail спроса по size/color/fit.
- Canonical есть в базовом шаблоне и переопределяется для home/catalog/product.
- HTTP -> HTTPS работает.
- www -> non-www работает через 301.
- Есть `hreflang="uk"` и `x-default`.
- Есть viewport, charset, favicon, manifest, OG/Twitter tags.
- Есть skip link и semantic layout elements.
- Есть width/height/lazy/fetchpriority/preload для изображений.
- Есть WhiteNoise, compressed manifest static, GZip и cache headers.

Ключевые файлы:

- `twocomms/twocomms/urls.py`
- `twocomms/storefront/views/static_pages.py`
- `twocomms/storefront/sitemaps.py`
- `twocomms/twocomms/middleware.py`
- `twocomms/twocomms/settings.py`
- `twocomms/twocomms/production_settings.py`
- `twocomms/twocomms_django_theme/templates/base.html`

### 4.2 Product SEO

Сильные стороны:

- Product model содержит много полезных SEO-полей:
  - `seo_title`
  - `seo_description`
  - `seo_keywords`
  - `seo_bottom_html`
  - `seo_schema`
  - `short_description`
  - `full_description`
  - `details_text`
  - `target_audience`
  - `care_instructions`
  - `main_image_alt`
  - `size_grid`
  - `ProductFAQ`
- PDP рендерит:
  - H1
  - price
  - variant selectors
  - size/fit/color
  - delivery/care/FAQ tabs
  - related products
  - breadcrumbs
  - Product schema
  - FAQ schema
- Product schema содержит:
  - `Product`
  - `Offer`
  - price
  - currency UAH
  - availability
  - shippingDetails
  - return policy
  - brand/manufacturer
  - material/country/color/sizes при наличии

Это хорошая база для merchant listings.

### 4.3 Каталог и фильтры

Сильные стороны:

- `/catalog/` и `/catalog/<category>/` разделены.
- Есть breadcrumbs.
- Есть CollectionPage + ItemList schema.
- Color filter закрывается `noindex, follow`.
- Search route закрывается `noindex, follow`.
- В карточках есть color preview и preferred image для выбранного цвета.

### 4.4 Trust/support страницы

Сильные стороны:

- Есть отдельные страницы:
  - `/delivery/`
  - `/faq/`
  - `/rozmirna-sitka/`
  - `/doglyad-za-odyagom/`
  - `/povernennya-ta-obmin/`
  - `/contacts/`
  - `/mapa-saytu/`
- Support template выводит WebPage, BreadcrumbList, FAQPage.
- Контент поддерживает реальные вопросы покупателя: доставка, оплата, размеры, уход, возврат.

Для fashion e-commerce это важно, потому что покупатель до покупки проверяет посадку, размер, условия возврата, оплату и доставку.

### 4.5 Custom print и DTF

Сильные стороны:

- `/custom-print/` покрыт как коммерческий funnel: конфигуратор, lead, cart, moderation.
- Есть Service schema и FAQPage.
- DTF-секция имеет отдельные коммерческие маршруты: price/order/delivery-payment/requirements/returns.
- DTF может быть отдельным organic-кластером, но его нужно отделять от основного бренда одежды по интентам.

## 5. Главные проблемы и рекомендации

### P0. Убрать утечку Django template comments из HTML

Evidence:

- Production product pages: 65 / 65 содержат `{# ... #}`.
- Локальный тест `storefront.tests.test_seo_regressions` падает: `test_product_page_does_not_leak_template_syntax`.
- Источники найдены в:
  - `twocomms/twocomms_django_theme/templates/base.html`
  - `twocomms/twocomms_django_theme/templates/pages/index.html`
  - `twocomms/twocomms_django_theme/templates/pages/catalog.html`
  - `twocomms/twocomms_django_theme/templates/pages/product_detail.html`

Причина:

- В Django `{# ... #}` нельзя безопасно использовать как многострочный comment в таком виде. Он рендерится буквально.

Что сделать:

- Заменить многострочные `{# ... #}` на `{% comment %} ... {% endcomment %}`.
- Или удалить такие комментарии из templates.
- После исправления прогнать:
  - `DEBUG=True SECRET_KEY=test .venv/bin/python twocomms/manage.py test storefront.tests.test_seo_regressions --keepdb --noinput`
  - production spot-check HTML на `/`, `/catalog/`, 2 категории, 5 товаров.

Ожидаемый эффект:

- Чище HTML.
- Проходит существующий SEO regression test.
- Меньше технического мусора в `<head>`.

### P0. Убрать или легализовать рейтинг `4.9 (45 відгуків)`

Evidence:

- `twocomms/twocomms_django_theme/templates/pages/product_detail.html`
- На production 65 / 65 product pages содержат `45 відгуків`.
- Модель реальных review/rating для storefront не найдена.
- Product schema не содержит `aggregateRating`, то есть сайт показывает рейтинг пользователю, но не подкрепляет его структурно.

Почему это риск:

- Если отзывы не реальные, это доверительный и юридический риск.
- Google structured data guidelines отдельно предупреждают против misleading/fake review content.
- Даже без AggregateRating в schema, видимый fake trust signal плохо влияет на качество страницы.

Что сделать:

Вариант A, быстрый:

- Убрать `4.9 (45 відгуків)` с PDP и related cards.
- Заменить на реальные нейтральные trust signals:
  - "Виробництво в Україні"
  - "Друк DTF"
  - "Обмін/повернення за умовами"
  - "Доставка Новою поштою"

Вариант B, правильный:

- Ввести модель verified reviews.
- Показывать рейтинг только при наличии реальных отзывов.
- Добавить AggregateRating в Product schema только если rating и count подтверждены.

### P0. Убрать SEO-видимый текст из product SEO landing

Evidence:

- `twocomms/storefront/services/product_seo_landing.py`
- Видимый текст: "Перемикання між посадками змінює текст і ключові слова сторінки для коректного індексу пошуковими системами."
- City paragraph и top queries массово генерируют городские запросы.

Проблема:

- Это текст для SEO-оператора, а не для покупателя.
- Для пользователя такая фраза снижает доверие.
- Для поисковика это выглядит как механическая оптимизация.

Что сделать:

- Удалить все упоминания "ключові слова", "індекс", "пошукові системи" из видимого UI.
- Переписать блоки в buyer-first формате:
  - посадка;
  - материал;
  - плотность;
  - сезонность;
  - как выбрать размер;
  - как ухаживать;
  - когда подойдет oversize/classic;
  - что с доставкой и возвратом.
- City-блок оставить только если есть реальная логистика/сроки/условия по городам. Иначе не делать city doorway.

### P1. Свести Organization schema к одному canonical entity graph

Evidence:

- `base.html` выводит Organization почти на всех страницах.
- `index.html` дополнительно выводит canonical Organization + WebSite через tags.
- На главной production `ld_types`: `Organization`, `Organization`, `WebSite`, `WebPage`.

Что сделать:

- Оставить один Organization graph со стабильным `@id`, например `https://twocomms.shop/#organization`.
- WebSite graph: `https://twocomms.shop/#website`.
- На всех страницах ссылаться на этот `@id` через publisher/brand/seller.
- Не дублировать Organization разными блоками.

### P1. Усилить category pages

Evidence:

- Production categories всего 3.
- Titles короткие и шаблонные.
- Description хорошей длины, но шаблонная.
- Root catalog тоньше категорий и не имеет такого же SEO-блока, как category pages.

Что сделать:

Для каждой категории:

- Unique `seo_title`:
  - "Футболки TwoComms з авторськими принтами - купити в Україні"
  - "Худі TwoComms: streetwear, oversize та DTF-принти"
  - "Лонгсліви TwoComms: базові й авторські моделі"
- Unique `seo_description`: 140-160 символов, без одинаковых шаблонов.
- H1 можно оставить коротким, но intro должен раскрывать ассортимент.
- Добавить FAQ:
  - как выбрать размер;
  - чем отличаются classic/oversize;
  - какие материалы;
  - сколько идет доставка;
  - можно ли вернуть/обменять;
  - как ухаживать за DTF-принтом.
- Добавить internal links:
  - футболки -> худі/лонгсліви/custom print;
  - худі -> футболки/лонгсліви/розмірна сітка;
  - лонгсліви -> худі/догляд/custom print.

Важно:

- Не превращать категории в блог.
- Для e-commerce категории должны помогать выбрать и купить.

### P1. Уточнить strategy для product variant URLs

Текущая стратегия:

- 1-сегментные variants self-canonical:
  - `/product/clasic-tshort/s/`
  - `/product/clasic-tshort/classic/`
- 2+ сегмента canonical на base product.
- Variant sitemap содержит 418 URL.

Проблема:

- Product JSON-LD `url` на variant pages остается base product URL.
- Если variant URL self-canonical, schema `url` желательно синхронизировать с canonical variant URL или явно использовать variant structured data strategy.

Что сделать:

- Решить, какие variants реально должны индексироваться:
  - size pages почти всегда слабые и могут быть duplicate;
  - color pages могут быть полезны, если есть разные фото/спрос;
  - fit pages могут быть полезны, если есть classic/oversize интент.
- Для индексируемых variant pages:
  - уникальный title/description;
  - уникальный visible selection state;
  - Product schema `url` = canonical variant URL;
  - при возможности `isVariantOf` / `hasVariant` структура.
- Для слабых variants:
  - canonical на base product;
  - убрать из variant sitemap.

### P1. Синхронизировать image sitemap с реальными product images

Проблема:

- Product sitemap: 65.
- Image sitemap pages: 64.
- Сейчас image sitemap, судя по коду, использует только `main_image`.

Что сделать:

- Для каждого товара брать:
  - `main_image`;
  - `display_image`;
  - `ProductImage`;
  - variant images;
  - но дедуплицировать URL.
- Если у товара нет image, не отдавать image entry, но отдельно репортить в админке.
- Проверить `image:title` и `image:caption`, чтобы они были buyer-friendly.

### P1. Уточнить noindex/canonical для parameter duplicates

Проблема:

- `/catalog/?color=black` корректно `noindex, follow`.
- `/search/?q=худі` корректно `noindex, follow`.
- `/catalog/?q=худі` отдает `index, follow`, хотя canonical `/catalog/`.

Что сделать:

- На catalog/category, если есть неизвестные query params, ставить `noindex, follow`.
- Для `utm_*`, `gclid`, `fbclid`, `ref` лучше 301/302 на clean URL, если это не ломает аналитику. Альтернатива: canonical clean + robots noindex.
- Pagination links должны сохранять разрешенные фильтры только там, где это нужно UX. Сейчас pagination для color filter может терять `color`.

### P1. Убрать `meta keywords`

Evidence:

- `base.html`
- `index.html`
- `catalog.html`
- `product_detail.html`

Проблема:

- Google не использует `meta keywords` для ranking.
- В e-commerce это часто выглядит как keyword stuffing.
- Поле можно оставить в admin как внутреннюю подсказку, но не выводить в HTML.

Что сделать:

- Удалить `<meta name="keywords">` из public templates.
- Если поле нужно для AI/autofill или внутренней аналитики, оставить только в DB/admin.

### P1. Убрать/синхронизировать статический `robots.txt`

Evidence:

- Dynamic route: `twocomms/storefront/views/static_pages.py`
- Static file: `twocomms/static/robots.txt`

Проблема:

- Они отличаются.
- Если сервер отдаст static file раньше Django route, правила изменятся.

Что сделать:

- Оставить один canonical source.
- Если static file нужен как fallback, генерировать его из той же функции или держать полностью синхронным.
- Повторить query-noise rules для specific bot blocks, если сознательно управляем AI/AdsBot behavior.

### P2. Доработать Merchant feed

Что хорошо:

- Feed покрывает 384 variant items.
- Все items имеют brand, size, color, item_group_id, product_type, google_product_category.

Что улучшить:

- Если есть GTIN/barcode, отдавать `g:gtin`.
- Проверить, почему product variant sitemap 418, а Merchant feed 384.
- Проверить 117 out_of_stock feed items: нужны ли они в feed.
- Добавить custom labels:
  - `custom_label_0`: category
  - `custom_label_1`: stock tier
  - `custom_label_2`: margin/price tier
  - `custom_label_3`: collection/print theme
  - `custom_label_4`: bestseller/new/drop

### P2. Улучшить ItemList schema на category pages

Сейчас:

- CollectionPage + ItemList есть.
- ItemList содержит URL/name.

Что можно улучшить:

- Добавить Product/Offer summary для карточек, если это не раздувает HTML чрезмерно.
- Минимум: `url`, `name`, `image`, `offers.price`, `offers.priceCurrency`, `availability`.
- Следить, чтобы schema соответствовала видимому контенту и не была "богаче" реальной карточки.

### P2. Полировать support pages

Что хорошо:

- Support pages есть и индексируемы.
- FAQ schema есть.

Что улучшить:

- Убрать технические/внутренние формулировки, если они видны пользователю.
- Проверить единый язык: украинский как основной. Не смешивать English UI chips вроде "manual format", если это не брендовый стиль.
- Для `/rozmirna-sitka/` добавить больше конкретики по размерным сеткам для футболок/худи/лонгсливов.
- Для `/doglyad-za-odyagom/` добавить конкретику по DTF-принтам, стирке, температуре, сушке, глажке.
- Для `/povernennya-ta-obmin/` синхронизировать с MerchantReturnPolicy в schema.

### P2. LocalBusiness / Organization / trust

Сейчас:

- Есть Organization schema.
- Есть helper для LocalBusiness, но он не используется.
- В helper найден placeholder telephone вида `+380XXXXXXXXX`.

Что сделать:

- Если есть физический адрес/самовывоз/официальные часы, добавить корректный LocalBusiness/Store/ClothingStore.
- Если физического магазина нет, не притворяться LocalBusiness.
- Телефон, email, social profiles, legal name, return policy должны быть реальными и одинаковыми в footer/schema/support pages.

### P2. DTF subdomain/section SEO

Сильные стороны:

- Есть отдельные DTF маршруты, sitemap/robots, price/order/requirements.

Проблемы:

- DTF canonical в base использует `request.build_absolute_uri`, значит query string может попасть в canonical.
- DTF sitemap/robots строят origin из request host/scheme, а не из canonical setting.
- `delivery_payment.html` дублирует карточки "Оплата/Доставка".
- DTF pages имеют меньше structured data, чем main storefront.

Что сделать:

- В DTF добавить clean canonical без query.
- Зафиксировать canonical host.
- Добавить Service/FAQ/Breadcrumb schema для ключевых DTF pages.
- Убрать дублирующиеся blocks.
- Разделить интенты:
  - одежда TwoComms;
  - DTF-печать;
  - кастомная печать на одежде.

## 6. Адаптация чеклиста под TwoComms

### 6.1 Head & metadata

Сейчас хорошо:

- Есть title/description/canonical/robots/OG/Twitter.
- Есть favicon/viewport/charset.
- Есть social preview fallback.

Доработать:

- Удалить meta keywords.
- Убрать duplicate Organization на главной.
- Сделать category-specific title/description.
- Проверить, что every indexable page имеет один canonical self или осознанный canonical target.
- Убрать template comments из head.

### 6.2 URL structure

Сейчас хорошо:

- Чистая структура `/catalog/<slug>/`, `/product/<slug>/`, `/product/<slug>/<variant>/`.
- Query variants редиректятся в path variants.

Доработать:

- Исправлять новые slugs до публикации: lowercase, hyphen, no underscores, no leading/trailing hyphen.
- Для старых slugs сделать карту 301, если решите чистить.
- Не плодить city/facet URL без уникального контента.

### 6.3 Headings

Сейчас хорошо:

- В проверенных production pages H1 один.
- H1 совпадает с основным объектом страницы.

Доработать:

- Для категорий H1 можно оставить коротким, но добавить сильный intro.
- Для variant pages H1 сейчас остается базовым product title. Если variant self-canonical, стоит добавить selected modifier рядом с H1 или в подзаголовке.

### 6.4 Copy & body

Сейчас хорошо:

- Product pages не пустые.
- Merchant feed descriptions плотные.
- Support content закрывает buyer questions.

Доработать:

- Переписать product SEO landing так, чтобы он был полезен человеку.
- Убрать SEO-for-SEO формулировки.
- Для категорий добавить buyer-first блоки.
- Для товаров добавить фактические параметры: состав, плотность, крой, посадка, принт, уход.

### 6.5 FAQ

Сейчас хорошо:

- FAQPage schema есть на PDP и support pages.

Доработать:

- Проверить, что FAQ виден пользователю и совпадает с JSON-LD.
- Не дублировать одинаковые FAQ на сотнях страниц без адаптации.
- Для categories FAQ должен быть category-specific.

### 6.6 Images

Сейчас хорошо:

- Есть responsive images, width/height, lazy/eager/fetchpriority.
- PDP main image получает LCP hints.

Доработать:

- Image sitemap покрыть всеми важными images.
- Проверить alt: не повторять шаблонно бренд в каждом alt.
- Декоративные повторяющиеся logo images должны иметь empty alt.
- Для product images alt должен описывать товар, цвет, тип изделия, принт.

### 6.7 Internal links

Сейчас хорошо:

- Breadcrumbs есть.
- Footer содержит коммерческие/support links.
- Product pages имеют related products.

Доработать:

- Добавить cross-links из категорий на support pages:
  - размерная сетка;
  - уход;
  - доставка;
  - кастомный принт.
- Добавить ссылки из support pages обратно на категории.
- Не делать city chips, которые все ведут на одну category URL.

### 6.8 External links

Сейчас:

- В e-commerce не обязательно иметь много external links.

Доработать:

- Для trust можно ссылаться на official social profiles, marketplace profiles, policies.
- Для внешних соцсетей использовать `rel="noopener noreferrer me"` уже местами сделано.

### 6.9 Schema markup

Сейчас хорошо:

- Product, Offer, Breadcrumb, FAQ, WebSite, Organization, Service.

Доработать:

- One canonical Organization graph.
- Variant schema alignment.
- Real AggregateRating only after real reviews.
- LocalBusiness только при реальных данных.
- Shipping/return policy синхронизировать между schema, support pages и Merchant Center.

### 6.10 E-E-A-T / trust

Сейчас хорошо:

- Есть страницы доставки, возврата, ухода, контактов, размера.
- Есть brand page.

Доработать:

- Реальные отзывы вместо hardcoded rating.
- Больше фактов о производстве, материалах, DTF, уходе.
- Контакты, юридическая информация, условия возврата должны быть легко доступны.
- Если часть покупки поддерживает ЗСУ, это должно быть точно, прозрачно и подтверждено.

### 6.11 Accessibility

Сейчас хорошо:

- Есть skip link.
- Есть semantic tags.
- У многих SVG есть `aria-hidden`.

Доработать:

- Проверить alt decorative images.
- Проверить focus states и keyboard path для variant selectors, cart, size guide.
- Проверить contrast на mobile.

### 6.12 Mobile & CWV

Сейчас хорошо:

- Есть preload fonts/images.
- Есть width/height у критических изображений.
- Есть lazy loading.
- Есть device-class performance logic.

Доработать:

- После правок прогнать Lighthouse/PageSpeed по:
  - `/`
  - `/catalog/`
  - `/catalog/tshirts/`
  - 2 PDP с image-heavy gallery
  - `/custom-print/`
- Не перегружать PDP schema/HTML дополнительным SEO-контентом, если это ухудшает LCP/INP.

### 6.13 Social preview

Сейчас хорошо:

- OG/Twitter есть.
- Fallback social image есть.

Доработать:

- Для товаров использовать product image, цветовой variant image при variant URL.
- Проверить, что OG image 1200x630 или допустимый крупный ratio.
- Для категорий использовать category cover, если он реально качественный.

### 6.14 Conversion elements

Сейчас хорошо:

- На PDP есть price, size/color/fit, delivery/care, add to cart, related.
- Support pages закрывают возражения.

Доработать:

- Рейтинг заменить реальным.
- Доставка/возврат должны быть кратко видны near buy button.
- Если товар out of stock, добавить понятный CTA: уведомить, похожие товары, выбрать другой цвет/размер.
- Не давать Google и пользователю видеть "в наличии" там, где stock не подтвержден.

## 7. Backlog исправлений

| Приоритет | Задача | Где | Проверка |
|---|---|---|---|
| P0 | Заменить многострочные `{# ... #}` на `{% comment %}` или удалить | `base.html`, `index.html`, `catalog.html`, `product_detail.html` | SEO regression tests, production HTML grep |
| P0 | Убрать hardcoded `4.9 (45 відгуків)` | `product_detail.html` | PDP без fake rating; schema без fake aggregate |
| P0 | Удалить видимый SEO-for-SEO текст | `product_seo_landing.py` | PDP copy review |
| P1 | Один Organization schema graph | `base.html`, `seo_tags.py`, `index.html` | Rich Results Test, JSON-LD count |
| P1 | Category SEO fields/content | `Category` model/admin/templates | 3 категории с уникальными title/description/intro/FAQ |
| P1 | Parameter noindex/redirect policy | `catalog.py`, `catalog.html`, robots | `/catalog/?q=x` noindex или redirect |
| P1 | Image sitemap расширить | `static_pages.py` или sitemap service | product image coverage 65/65+ |
| P1 | Variant schema/canonical strategy | `variant_meta.py`, `seo_utils.py`, `product.py` | variant URL schema matches strategy |
| P1 | Убрать meta keywords | `base.html`, page templates | No public `<meta name="keywords">` |
| P1 | Robots static/dynamic sync | `static_pages.py`, `static/robots.txt` | One canonical policy |
| P2 | Merchant GTIN/custom labels | `marketplace_feeds.py`, product data | Feed diagnostics, Merchant Center |
| P2 | Category ItemList richer | `catalog.html` / schema helper | Valid structured data |
| P2 | Support pages polish | `support_content.py`, templates | No internal/technical wording |
| P2 | LocalBusiness only if real | `seo_tags.py`, base/schema | No placeholder phone |
| P2 | DTF canonical/schema cleanup | `dtf/base.html`, `dtf/views.py` | Query-free canonical, schema test |
| P3 | Slug cleanup with redirects | product slugs + redirects | 301 map, Search Console monitoring |

## 8. Production DB-аудит, который стоит сделать отдельно

Публичный слой показывает, что индексируется, но не отвечает на все вопросы по данным. Отдельно нужно сделать read-only production DB report:

Product coverage:

- total products;
- published products;
- draft/archived products;
- published without main image;
- published without display image;
- published without `seo_title`;
- published without `seo_description`;
- published without `main_image_alt`;
- published with short `full_description`;
- published without category;
- published without ProductFAQ;
- published without size grid;
- out of stock but in sitemap;
- out of stock but in Merchant feed.

Category coverage:

- active categories;
- categories without cover;
- categories without `seo_intro_html`;
- categories without SEO blocks;
- categories with too few published products.

Variant coverage:

- variant URLs in sitemap;
- variants with stock 0;
- variants without color/size;
- variants without images;
- feed variants vs sitemap variants.

Feed coverage:

- GTIN/barcode fields present in DB but missing in feed;
- sale price consistency;
- availability consistency;
- image availability;
- item_group_id consistency.

Важно: этот отчет должен быть read-only. Не запускать миграции, импорты, autofill или генерацию без явного решения.

## 9. Что лучше убрать

Убрать полностью:

- Видимые фразы про "ключові слова", "індекс", "пошукові системи".
- Hardcoded рейтинг и count отзывов.
- Public `meta keywords`.
- Placeholder LocalBusiness telephone.
- Duplicate Organization JSON-LD.
- City keyword chips, если они не ведут на реальные уникальные city landing pages с реальной логистической ценностью.

Убрать или переработать:

- Массовые city paragraphs на PDP.
- Claims вида "кожен товар..." если это не подтверждается для каждого товара.
- Слишком длинные механические SEO-блоки на PDP, если они ухудшают UX.

Оставить, но улучшить:

- Product schema.
- FAQ schema.
- Merchant feed.
- Variant URLs, но после стратегии.
- Support pages.
- Category SEO blocks.

## 10. Рекомендуемая очередность работ

### Этап 1: техническая очистка

1. Убрать template comment leaks.
2. Убрать fake rating.
3. Убрать meta keywords.
4. Свести Organization schema.
5. Закрыть `/catalog/?unknown=params` от индексации или редиректить.
6. Синхронизировать robots sources.

Цель: убрать слабые/опасные сигналы без изменения бизнес-логики.

### Этап 2: e-commerce entity correctness

1. Variant schema/canonical strategy.
2. Image sitemap coverage.
3. Merchant feed GTIN/custom labels/availability.
4. Out-of-stock strategy.
5. Product review system или полное удаление review UI.

Цель: чтобы товарные данные совпадали между HTML, schema, sitemap и feed.

### Этап 3: категории и контент

1. Добавить category SEO fields.
2. Написать сильные category intros/FAQ.
3. Переписать product SEO landing.
4. Усилить root `/catalog/`.
5. Добавить внутреннюю перелинковку category -> support -> product.

Цель: получить коммерческие landing pages, которые реально отвечают на покупательский интент.

### Этап 4: monitoring

1. Search Console:
   - indexed pages;
   - duplicate without user-selected canonical;
   - crawled currently not indexed;
   - product snippets;
   - merchant listings;
   - sitemap discovered/indexed.
2. Merchant Center:
   - diagnostics;
   - item disapprovals;
   - limited performance;
   - price/availability mismatch.
3. Production crawl раз в неделю:
   - sitemap URL status;
   - canonical;
   - robots;
   - schema parse;
   - title/meta coverage.

## 11. Проверки, выполненные в рамках аудита

Команды/проверки:

- `git status --short`
- `rg --files`
- `rg` по `canonical`, `robots`, `sitemap`, `schema`, `Product`, `FAQPage`, `Organization`, `rating`, `4.9`, `keywords`
- `DEBUG=True SECRET_KEY=test .venv/bin/python twocomms/manage.py check --settings=test_settings`
- `DEBUG=True SECRET_KEY=test .venv/bin/python twocomms/manage.py test storefront.tests.test_seo_regressions --keepdb --noinput --verbosity 1`
- Production HTTP checks:
  - `https://twocomms.shop/robots.txt`
  - `https://twocomms.shop/sitemap.xml`
  - `https://twocomms.shop/sitemap-products.xml`
  - `https://twocomms.shop/sitemap-product-variants.xml`
  - `https://twocomms.shop/sitemap-categories.xml`
  - `https://twocomms.shop/sitemap-images.xml`
  - `https://twocomms.shop/google_merchant_feed.xml`
  - выборочные product/category/variant/support pages
  - полный polite check 65 product URLs из production sitemap

Результат локальных тестов:

- `manage.py check`: passed.
- `storefront.tests.test_seo_regressions`: 46 tests, 1 failure.
- Failure: `test_product_page_does_not_leak_template_syntax`, потому что rendered PDP HTML содержит `{#`.

## 12. Справочные источники

- Google Search Central: Product structured data  
  https://developers.google.com/search/docs/appearance/structured-data/product
- Google Search Central: Product snippets  
  https://developers.google.com/search/docs/appearance/structured-data/product-snippet
- Google Search Central: Canonical URLs  
  https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls
- Google Search Central: Title links  
  https://developers.google.com/search/docs/appearance/title-link
- Google Search Central: Ecommerce URL structure  
  https://developers.google.com/search/docs/specialty/ecommerce/designing-a-url-structure-for-ecommerce-sites
- Google Search Central: Structured data quality guidelines  
  https://developers.google.com/search/docs/appearance/structured-data/sd-policies

## 13. Definition of done для SEO-исправлений

Считать следующий SEO-этап завершенным только когда:

- HTML production не содержит `{#` / `#}`.
- На PDP нет fake rating.
- Schema валидна и не дублирует Organization.
- Product pages, category pages, sitemap и Merchant feed согласованы по URL, stock, price, image.
- `/catalog/?unknown=params` не индексируется как дубль.
- Image sitemap покрывает все published products с доступными изображениями.
- Category pages имеют уникальные title/description/intro/FAQ.
- Product SEO landing не содержит SEO-видимых фраз и doorway-like city blocks.
- SEO regression tests проходят.
- После деплоя проверены production URL, а не только локальная БД.
