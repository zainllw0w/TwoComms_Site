# TwoComms SEO Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** превратить три SEO-аудита TwoComms в единый порядок внедрения: что править, в какой последовательности, какими файлами, какими проверками и где смотреть подробный анализ.

**Architecture:** сначала чистим опасные сигналы, которые уже видны production HTML; затем сокращаем crawl waste и выравниваем canonical/schema; затем усиливаем категории и контент; после этого дорабатываем feed, image sitemap, IndexNow и мониторинг. Production считается источником истины для ассортимента, stock, FAQ, feed и sitemap.

**Tech Stack:** Django 5.2, Django templates, sitemap views, JSON-LD helpers, storefront services, production public crawl, Google Merchant feed, IndexNow.

---

## 1. Источники

Подробная аналитика лежит в трех файлах:

1. [TWOCOMMS_ECOMMERCE_SEO_AUDIT_2026-05-10.md](./TWOCOMMS_ECOMMERCE_SEO_AUDIT_2026-05-10.md)  
   Базовый e-commerce аудит: production sitemap/feed/HTML, техническое SEO, schema, robots, Merchant feed, support pages, backlog.

2. [TWOCOMMS_SEO_SUPPLEMENT_2026-05-10.md](./TWOCOMMS_SEO_SUPPLEMENT_2026-05-10.md)  
   Дополнение: опасные schema helpers, autofill thin content, duplicate FAQ, city doorway chips, internal links на noindex, IndexNow, E-E-A-T.

3. [TWOCOMMS_CATEGORY_VARIANT_AUDIT_2026-05-10.md](./TWOCOMMS_CATEGORY_VARIANT_AUDIT_2026-05-10.md)  
   Категории и variants: title/H1/meta категорий, size variants в sitemap, variant canonical strategy, PDP headings, быстрые победы.

Этот файл не заменяет аудиты. Он является рабочим планом внедрения и ссылается на них для аргументации.

## 2. Дополнительная проверка перед составлением плана

Проверено дополнительно:

- `product_rating_schema` в коде есть, но в текущих production product pages из проверенной выборки не рендерится: `aggregateRating` не найден, Product JSON-LD один. Это latent P0-риск, а не текущий rendered duplicate.
- Variant sitemap production: 418 URL, из них 349 size-only, 46 fit, 72 color/other. Size-only URL действительно основной источник crawl waste.
- `Category` уже имеет `seo_text_title` и `seo_intro_html`, но не имеет `seo_title`, `seo_h1`, `seo_description`. Добавлять нужно только недостающие поля.
- `general_catalog_seo.py` действительно содержит curated links на `?color=...`, которые ведут на noindex filter URLs.
- IndexNow не просто "есть": есть service, admin actions, management commands и tests. Нужно проверить production config/logs, а не писать заново.

## 3. Правила внедрения

- Не деплоить "SEO-правки" без post-deploy проверки production HTML, sitemap и feed.
- Не считать локальную SQLite доказательством production safety.
- Не использовать fake reviews, fake phone, fake business hours или claims, которые не подтверждаются production-данными.
- Не добавлять больше индексируемых URL, пока не сокращены size variants и parameter duplicates.
- Не превращать категории в блог: category pages должны продавать и помогать выбрать товар.
- Не писать city landing pages, пока нет реальной уникальной логистической/локальной ценности.
- Все schema должны соответствовать видимому контенту.

## 4. Приоритеты

### P0: убрать риск penalty / misleading / конфликтных сигналов

- Template comments `{# ... #}` в production HTML.
- Fake rating `4.9 (45 відгуків)`.
- Dangerous `product_rating_schema` helper.
- Dangerous `local_business_schema` с placeholder phone.
- Inline Organization без `@id` в `base.html`.
- Size-only variants в sitemap и self-canonical.
- Product schema URL, который конфликтует с canonical на variant pages.

### P1: усилить индексируемые коммерческие страницы

- Category `seo_title`, `seo_h1`, `seo_description`.
- Уникальные category titles/H1/descriptions для 3 категорий.
- Удаление `meta keywords`.
- Закрытие `/catalog/?q=...` и неизвестных query params.
- Curated links не должны вести на noindex URLs.
- Удаление city chips и SEO-visible text.
- Уникальная стратегия FAQ: support/category first, PDP только если FAQ уникальны.

### P2: рост качества и rich commerce signals

- Image sitemap покрывает все product images.
- Product/color variant schema использует правильный image.
- Merchant feed: GTIN при наличии, custom labels, out-of-stock strategy.
- IndexNow production verification.
- Product/support cross-linking.
- Trust signals near CTA вместо рейтинга.
- Accessibility/Lighthouse checks.

## 5. Этап 0: read-only production inventory

**Цель:** перед изменениями зафиксировать baseline из production DB/HTML, чтобы после деплоя сравнить факты.

**Источники:** основной аудит, раздел "Production DB-аудит"; supplement, раздел IndexNow.

**Files:**

- Read-only: `twocomms/storefront/models.py`
- Read-only: `twocomms/productcolors/models.py`
- Read-only: `twocomms/storefront/services/marketplace_feeds.py`
- Optional create: `docs/seo/production-inventory-YYYY-MM-DD.md`

- [ ] **Step 0.1: Production public crawl baseline**

Run locally against production public endpoints:

```bash
.venv/bin/python - <<'PY'
import requests, xml.etree.ElementTree as ET
BASE='https://twocomms.shop'
NS={'sm':'http://www.sitemaps.org/schemas/sitemap/0.9'}
for path in ['/sitemap-products.xml','/sitemap-product-variants.xml','/sitemap-categories.xml','/sitemap-images.xml','/google_merchant_feed.xml']:
    r=requests.get(BASE+path, timeout=30, headers={'User-Agent':'TwoCommsSEOPlan/1.0'})
    print(path, r.status_code, len(r.content), r.headers.get('content-type'))
PY
```

Expected: all endpoints return `200`.

- [ ] **Step 0.2: Production DB report, read-only**

Use a safe read-only management shell/query on the server. Do not run migrations, imports, autofill, or save operations.

Report:

- published products count;
- products without main image/display image;
- products without SEO title/description/alt;
- products with ProductFAQ;
- products out of stock but in sitemap/feed;
- active categories and category SEO field coverage;
- variant count by size/color/fit;
- GTIN/barcode availability in DB.

- [ ] **Step 0.3: Save baseline note**

If production DB access is used, save only counts and non-secret findings. Do not save credentials, raw secrets, or private commands.

## 6. Этап 1: P0 technical cleanup

### Task 1: Убрать Django template comments из public HTML

**Why:** production HTML и SEO regression test показывают `{# ... #}` в rendered pages.

**Details:** основной аудит, раздел "P0. Убрать утечку Django template comments из HTML".

**Files:**

- Modify: `twocomms/twocomms_django_theme/templates/base.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/index.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/catalog.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/product_detail.html`
- Test: `twocomms/storefront/tests/test_seo_regressions.py`

- [ ] **Step 1.1: Replace bad comments**

Replace multi-line `{# ... #}` template comments with `{% comment %} ... {% endcomment %}` or remove them.

- [ ] **Step 1.2: Run SEO regression tests**

```bash
DEBUG=True SECRET_KEY=test .venv/bin/python twocomms/manage.py test storefront.tests.test_seo_regressions --keepdb --noinput
```

Expected: the previous `test_product_page_does_not_leak_template_syntax` failure passes.

- [ ] **Step 1.3: Production check after deploy**

```bash
curl -fsSL https://twocomms.shop/product/clasic-tshort/ | rg '\{#|#\}' || true
```

Expected: no output.

### Task 2: Убрать fake rating и опасный rating schema helper

**Why:** visible `4.9 (45 відгуків)` есть на всех product pages, но реального review source не найдено. `product_rating_schema` может создать fake AggregateRating, если его случайно вызовут.

**Details:** основной аудит "P0. Убрать или легализовать рейтинг"; supplement "P0-CRITICAL. Дублирование Product schema"; category/variant audit "PDP — фейковый рейтинг".

**Files:**

- Modify: `twocomms/twocomms_django_theme/templates/pages/product_detail.html`
- Modify: `twocomms/storefront/templatetags/seo_tags.py`
- Test: add/adjust SEO regression tests in `twocomms/storefront/tests/test_seo_regressions.py`

- [ ] **Step 2.1: Remove visible fake rating**

Remove:

- PDP rating block with `4.9 (45 відгуків)`;
- related products `tc-related-rating` hardcoded `4.9`.

Replace with factual trust badges only if true:

- `Зроблено в Україні`
- `DTF-друк`
- `Доставка Новою поштою`
- `Обмін/повернення за умовами`

- [ ] **Step 2.2: Remove `product_rating_schema`**

Delete or disable the `product_rating_schema` template tag. Do not add AggregateRating until a real verified reviews model/source exists.

- [ ] **Step 2.3: Add regression assertions**

Test rendered PDP does not contain:

- `45 відгуків`
- hardcoded `4.9`
- `aggregateRating`

Command:

```bash
DEBUG=True SECRET_KEY=test .venv/bin/python twocomms/manage.py test storefront.tests.test_seo_regressions --keepdb --noinput
```

### Task 3: One Organization schema source, no placeholder LocalBusiness

**Why:** inline Organization in `base.html` lacks `@id`; programmatic Organization has stable `@id`. LocalBusiness helper contains placeholder phone and unrealistic business hours.

**Details:** основной аудит "P1. Свести Organization schema"; supplement "P0-CRITICAL. Organization schema без @id" and "LocalBusiness placeholder".

**Files:**

- Modify: `twocomms/twocomms_django_theme/templates/base.html`
- Modify: `twocomms/storefront/templatetags/seo_tags.py`
- Modify: `twocomms/storefront/seo_utils.py`
- Test: `twocomms/storefront/tests/test_seo_regressions.py` or a focused schema test

- [ ] **Step 3.1: Remove inline Organization from base**

Remove the hardcoded Organization script in `base.html`.

- [ ] **Step 3.2: Use one programmatic Organization**

Render `{% organization_schema %}` once where needed, with stable `@id`.

- [ ] **Step 3.3: Delete or neutralize `local_business_schema`**

If there is no physical store with real phone/address/hours, remove `local_business_schema`.

- [ ] **Step 3.4: Validate JSON-LD count**

Production after deploy:

```bash
.venv/bin/python - <<'PY'
import requests, re, json, html
t=requests.get('https://twocomms.shop/', timeout=20).text
blocks=re.findall(r'<script[^>]+type=["\\']application/ld\\+json["\\'][^>]*>(.*?)</script>', t, re.S|re.I)
org=0
for b in blocks:
    obj=json.loads(html.unescape(b).strip())
    nodes=obj.get('@graph', [obj]) if isinstance(obj, dict) else obj
    for n in nodes:
        if isinstance(n, dict) and n.get('@type') == 'Organization':
            org += 1
print('organization_count', org)
PY
```

Expected: one canonical Organization entity, with stable `@id`.

### Task 4: Remove public `meta keywords`

**Why:** Google не использует `meta keywords`; текущие списки шаблонные и создают HTML noise.

**Details:** основной аудит "P1. Убрать meta keywords"; category/variant audit "Ключевые слова".

**Files:**

- Modify: `twocomms/twocomms_django_theme/templates/base.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/index.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/catalog.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/product_detail.html`

- [ ] **Step 4.1: Remove `<meta name="keywords">` from public output**

Keep DB/admin fields only if needed internally.

- [ ] **Step 4.2: Verify production HTML**

```bash
curl -fsSL https://twocomms.shop/ | rg 'name="keywords"' || true
curl -fsSL https://twocomms.shop/catalog/tshirts/ | rg 'name="keywords"' || true
curl -fsSL https://twocomms.shop/product/clasic-tshort/ | rg 'name="keywords"' || true
```

Expected: no output.

## 7. Этап 2: variants, canonical, sitemap

### Task 5: Убрать size-only variants из sitemap

**Why:** production variant sitemap имеет 418 URL, из них 349 size-only. Это thin content и crawl waste.

**Details:** category/variant audit "КРИТИЧЕСКАЯ ПРОБЛЕМА: Size variants в sitemap"; supplement "Crawl Budget".

**Files:**

- Modify: `twocomms/storefront/sitemaps.py`
- Test: `twocomms/storefront/tests/test_seo_regressions.py` or new sitemap test

- [ ] **Step 5.1: Change ProductVariantSitemap**

Keep only:

- color variants;
- active fit variants.

Remove size-only entries from sitemap generation.

- [ ] **Step 5.2: Add sitemap regression test**

Test product with sizes and colors:

- `/product/x/black/` exists in variant sitemap;
- `/product/x/oversize/` exists if active fit;
- `/product/x/m/` does not exist.

- [ ] **Step 5.3: Production expected result**

After deploy, variant sitemap should drop from 418 to roughly 118 or less based on current production breakdown: 72 color/other + 46 fit.

### Task 6: Size-only canonical must point to base product

**Why:** `/product/x/m/` is the same page with selected size. It should remain accessible for UX but not self-canonical/index-priority.

**Details:** category/variant audit "Canonical strategy"; main audit "variant URL strategy".

**Files:**

- Modify: `twocomms/storefront/services/variant_meta.py`
- Test: `twocomms/storefront/tests/test_seo_regressions.py` or `test_phase16_fit_seo.py`

- [ ] **Step 6.1: Detect size-only 1-segment URL**

When `segments_count == 1` and selected segment is size only:

- `canonical_path = base_path`
- `is_self_canonical = False`

Color-only and fit-only stay self-canonical.

- [ ] **Step 6.2: Test canonical**

Expected:

- `/product/x/m/` canonical `/product/x/`
- `/product/x/black/` canonical self
- `/product/x/oversize/` canonical self
- `/product/x/black/m/` canonical base

### Task 7: Product schema URL should match canonical strategy

**Why:** color/fit variant pages can be self-canonical, but Product schema currently always uses base product URL.

**Details:** main audit "Product schema url does not account for canonical variant"; supplement "Product schema url"; category/variant audit "Product schema на variant pages".

**Files:**

- Modify: `twocomms/storefront/seo_utils.py`
- Modify: `twocomms/storefront/templatetags/seo_tags.py`
- Modify: `twocomms/storefront/views/product.py`
- Modify: `twocomms/twocomms_django_theme/templates/pages/product_detail.html`
- Test: schema regression test

- [ ] **Step 7.1: Pass canonical path into product schema**

Allow `generate_product_schema(product, canonical_path=None, selected_variant=None)` or equivalent.

- [ ] **Step 7.2: Render Product schema with current canonical**

On self-canonical color/fit pages, schema `url` should equal variant canonical URL. On size-only pages after Task 6, schema `url` should equal base product URL.

- [ ] **Step 7.3: Add color image support**

If selected variant has a specific image, use it for:

- Product schema `image`;
- OG image;
- Twitter image;
- hero image alt if applicable.

## 8. Этап 3: catalog/category pages

### Task 8: Add missing Category SEO fields

**Why:** categories are main commercial landing pages, but current title/H1/description are short and templated.

**Details:** main audit "P1. Усилить category pages"; category/variant audit "ЧАСТЬ 1: Категории".

**Files:**

- Modify: `twocomms/storefront/models.py`
- Modify: `twocomms/storefront/admin.py`
- Create: new migration in `twocomms/storefront/migrations/`
- Modify: `twocomms/twocomms_django_theme/templates/pages/catalog.html`
- Test: category template/schema tests

- [ ] **Step 8.1: Add fields**

Add to `Category`:

- `seo_title = models.CharField(max_length=160, blank=True, ...)`
- `seo_h1 = models.CharField(max_length=160, blank=True, ...)`
- `seo_description = models.CharField(max_length=320, blank=True, ...)`

Do not duplicate existing `seo_text_title` and `seo_intro_html`.

- [ ] **Step 8.2: Add admin fields**

Expose new fields in `CategoryAdmin`.

- [ ] **Step 8.3: Use fields in catalog template**

Fallback rules:

- title: `category.seo_title` -> `Купити {{ category.name|lower }} — TwoComms`
- description: `category.seo_description` -> current fallback
- H1: `category.seo_h1` -> `category.name`
- OG/Twitter title/description use SEO fields too.

- [ ] **Step 8.4: Test migration and template**

```bash
DEBUG=True SECRET_KEY=test .venv/bin/python twocomms/manage.py makemigrations --check --dry-run
DEBUG=True SECRET_KEY=test .venv/bin/python twocomms/manage.py test storefront.tests.test_seo_regressions --keepdb --noinput
```

Expected: migrations are intentional; tests pass after migration file exists.

### Task 9: Seed category metadata for 3 production categories

**Why:** production has 3 categories. This is small enough to write manually and avoid generic autofill.

**Details:** category/variant audit provides recommended titles/descriptions.

**Files:**

- Create or modify migration/data command depending on deployment policy.
- Data affected: categories `tshirts`, `hoodie`, `long-sleeve`.

- [ ] **Step 9.1: Prepare copy**

Use Ukrainian buyer-first copy:

- `tshirts`: футболки з принтом, DTF, посадки, доставка.
- `hoodie`: худі, фліс/тепло only if true, DTF, доставка.
- `long-sleeve`: лонгсліви, посадки, DTF, сезонность.

Do not include prices/material density unless production product data confirms them.

- [ ] **Step 9.2: Apply safely**

Prefer admin/data migration only if it will not overwrite manual production edits. If production already has better copy, preserve production.

- [ ] **Step 9.3: Verify production**

Check:

- `/catalog/tshirts/`
- `/catalog/hoodie/`
- `/catalog/long-sleeve/`

Each should have unique title, description, H1, canonical, CollectionPage description.

### Task 10: Fix category heading hierarchy and root catalog links

**Why:** repeated H2 "Створи свій дизайн" is not a category heading; curated links point to noindex color query URLs.

**Details:** supplement "Ссылки на noindex-страницы"; category/variant audit "H2 на категориях".

**Files:**

- Modify: `twocomms/twocomms_django_theme/templates/pages/catalog.html`
- Modify: `twocomms/storefront/services/general_catalog_seo.py`
- Test: `twocomms/storefront/tests/test_general_catalog_seo.py`

- [ ] **Step 10.1: Fix print panel heading**

Either:

- change generic H2 to non-heading CTA text; or
- make it category-specific: `Свій принт на {{ category.name|lower }}`.

- [ ] **Step 10.2: Fix curated links**

No curated SEO link should point to a `noindex` URL unless it is intentionally a UX filter and not in SEO block.

Options:

- point chips to clean category URLs;
- create future path-based color landing pages in a separate strategic task;
- keep color filters in UI, but remove them from SEO "popular queries" block.

- [ ] **Step 10.3: Add regression test**

Assert `get_general_catalog_seo_layout()` top query URLs do not contain `?color=`.

## 9. Этап 4: product content and FAQ

### Task 11: Remove city doorway chips and SEO-visible text

**Why:** city chips all funnel to the same category URL; visible text mentions keywords/indexing/search engines.

**Details:** main audit "P0. Убрать SEO-видимый текст"; supplement "City chips"; category/variant audit quick wins.

**Files:**

- Modify: `twocomms/storefront/services/product_seo_landing.py`
- Test: `twocomms/storefront/tests/test_phase15_product_seo_landing.py`

- [ ] **Step 11.1: Delete city chips**

Remove `CITY_KEYWORDS` usage from product landing `top_queries`.

- [ ] **Step 11.2: Replace SEO wording**

Remove visible phrases:

- `ключові слова`
- `індекс`
- `пошуковими системами`

Replace with buyer-facing fit/material/care guidance.

- [ ] **Step 11.3: Test**

Assert generated landing copy contains no SEO-operational wording and no city query labels.

### Task 12: Stop duplicate FAQPage schema on PDP unless FAQ is unique

**Why:** universal 5 FAQ repeated across products is weak/spammy. FAQ can stay visible for UX, but schema should not mark duplicated boilerplate as page-specific FAQ.

**Details:** supplement "Идентичные FAQ на всех товарах"; main audit "FAQ".

**Files:**

- Modify: `twocomms/storefront/services/product_seo_autofill.py`
- Modify: `twocomms/twocomms_django_theme/templates/pages/product_detail.html`
- Modify: `twocomms/storefront/templatetags/seo_tags.py` if needed
- Test: `twocomms/storefront/tests/test_phase13_product_autofill.py`
- Test: `twocomms/storefront/tests/test_seo_regressions.py`

- [ ] **Step 12.1: Do not auto-create universal ProductFAQ by default**

Change autofill behavior so it does not create identical FAQ for every product unless explicitly requested.

- [ ] **Step 12.2: Keep visible FAQ if useful**

For duplicated generic FAQ, show as UI content or link to support pages, but do not output FAQPage JSON-LD.

- [ ] **Step 12.3: Move FAQ schema focus**

Use FAQPage schema on:

- `/faq/`
- `/delivery/`
- `/povernennya-ta-obmin/`
- category pages with unique category-specific FAQ.

### Task 13: Product support cross-linking

**Why:** product pages should pass users and link equity to high-trust support pages.

**Details:** supplement "product → support pages cross-linking"; main audit "Internal links".

**Files:**

- Modify: `twocomms/twocomms_django_theme/templates/pages/product_detail.html`
- Possibly modify: `twocomms/storefront/support_content.py`

- [ ] **Step 13.1: Add PDP support links**

Add contextual links:

- delivery tab -> `/delivery/`
- size selector area -> `/rozmirna-sitka/`
- care section -> `/doglyad-za-odyagom/`
- return/exchange mention -> `/povernennya-ta-obmin/`

- [ ] **Step 13.2: Add support to category links**

On support pages, add links back to relevant categories where natural.

### Task 14: Unique product descriptions for top products

**Why:** `product_seo_autofill.py` is structurally repetitive. Do not solve this by adding more template text.

**Details:** supplement "Автогенерированный SEO-контент"; main audit "Copy & body".

**Files/Data:**

- Data: top 20 products by traffic/revenue/ads.
- Optional modify: `twocomms/storefront/services/product_seo_autofill.py`

- [ ] **Step 14.1: Identify top 20**

Use production analytics/orders/Search Console, not local DB.

- [ ] **Step 14.2: Write manual copy**

For each top product, write unique:

- SEO title if missing/weak;
- SEO description;
- short description;
- full description;
- image alt;
- optional unique FAQ.

- [ ] **Step 14.3: Reduce autofill scope**

Autofill should fill blanks conservatively and avoid universal FAQ/keywords.

## 10. Этап 5: schema, feed, images, IndexNow

### Task 15: Move toward connected `@graph` JSON-LD

**Why:** current JSON-LD blocks are separate. A connected graph improves entity clarity.

**Details:** supplement "Отсутствие @graph"; main audit schema sections.

**Files:**

- Modify: `twocomms/storefront/seo_utils.py`
- Modify: `twocomms/storefront/templatetags/seo_tags.py`
- Modify templates that render schema blocks

- [ ] **Step 15.1: Do after Tasks 2, 3, 7**

Do not build @graph until fake rating, inline Organization and variant schema URL are fixed.

- [ ] **Step 15.2: One graph per page type**

For PDP graph include:

- Organization with `@id`;
- WebSite with publisher `@id`;
- BreadcrumbList;
- Product with brand/seller `@id`;
- optional FAQPage only if unique and visible.

### Task 16: Expand image sitemap

**Why:** production product sitemap has 65 URLs, image sitemap covers 64 pages and only one image per product.

**Details:** main audit "Image sitemap"; Lovelace findings in first audit context.

**Files:**

- Modify: `twocomms/storefront/views/static_pages.py`
- Test: sitemap image test

- [ ] **Step 16.1: Include all relevant product images**

Include:

- main image;
- display image;
- product gallery images;
- color variant images.

Deduplicate URLs.

- [ ] **Step 16.2: Report missing images**

Add a read-only admin/report command later if products in sitemap have no image.

### Task 17: Merchant feed cleanup

**Why:** feed is strong but missing GTIN and custom labels; 117 items are out of stock.

**Details:** main audit "Merchant feed"; supplement feed/stock notes.

**Files:**

- Modify: `twocomms/storefront/services/marketplace_feeds.py`
- Test: `twocomms/storefront/tests/test_marketplace_feeds.py`

- [ ] **Step 17.1: GTIN/barcode mapping**

If production variant/product barcode exists and is valid, output `g:gtin`.

- [ ] **Step 17.2: Custom labels**

Add optional labels:

- category;
- stock tier;
- price tier;
- collection/theme;
- new/bestseller if data exists.

- [ ] **Step 17.3: Out-of-stock strategy**

Decide whether out-of-stock variants stay in feed. Align feed, Product schema, PDP CTA and sitemap.

### Task 18: IndexNow production verification

**Why:** implementation exists; value depends on production config/logs.

**Details:** supplement "IndexNow".

**Files:**

- Read-only: `twocomms/storefront/services/indexnow.py`
- Read-only: `twocomms/storefront/management/commands/reindex_indexnow.py`
- Read-only: production logs/settings

- [ ] **Step 18.1: Verify config**

Check whether `INDEXNOW_ENABLED` and `INDEXNOW_KEY` are set in production.

- [ ] **Step 18.2: Dry run first**

Use dry-run command where available before submitting.

- [ ] **Step 18.3: Log monitoring**

Confirm logs contain accepted submissions after product/category updates.

## 11. Этап 6: trust, UX, accessibility

### Task 19: Trust signals near CTA

**Why:** fake rating must be replaced with factual conversion signals.

**Details:** supplement E-E-A-T table; main audit conversion elements.

**Files:**

- Modify: `twocomms/twocomms_django_theme/templates/pages/product_detail.html`
- CSS if needed

- [ ] **Step 19.1: Add factual badges**

Only use claims that are true for the specific product or store-wide policy.

- [ ] **Step 19.2: Link policies**

Where possible, link trust badges to support pages.

### Task 20: Accessibility and mobile SEO checks

**Why:** checklist includes touch targets, contrast, focus. These were not deeply verified.

**Files:**

- Templates/CSS touched by previous tasks.

- [ ] **Step 20.1: Browser/Lighthouse check**

Check:

- `/`
- `/catalog/`
- `/catalog/tshirts/`
- one base PDP;
- one color variant PDP;
- `/custom-print/`

- [ ] **Step 20.2: Manual mobile checks**

Verify:

- size/color/fit controls have usable tap targets;
- focus visible;
- product CTA not shifted by new trust links;
- category text does not push products too far below fold.

## 12. Verification checklist before deploy

- [ ] `git diff` contains only intended files.
- [ ] No secrets/credentials in diffs.
- [ ] `DEBUG=True SECRET_KEY=test .venv/bin/python twocomms/manage.py check --settings=test_settings`
- [ ] `DEBUG=True SECRET_KEY=test .venv/bin/python twocomms/manage.py test storefront.tests.test_seo_regressions --keepdb --noinput`
- [ ] Relevant focused tests:
  - sitemap variant tests;
  - category SEO tests;
  - marketplace feed tests;
  - IndexNow tests if touched.
- [ ] Production public crawl after deploy:
  - `/`
  - `/catalog/`
  - `/catalog/tshirts/`
  - `/catalog/hoodie/`
  - `/catalog/long-sleeve/`
  - 5 base PDPs;
  - 3 color variant PDPs;
  - 3 size-only PDPs;
  - `/robots.txt`
  - `/sitemap.xml`
  - `/sitemap-product-variants.xml`
  - `/sitemap-images.xml`
  - `/google_merchant_feed.xml`

## 13. Expected measurable outcomes

After P0/P1 implementation:

- Rendered HTML has no `{#` / `#}` leaks.
- PDP has no fake visible review count.
- Public HTML has no `meta keywords`.
- Organization entity is single and stable.
- No placeholder LocalBusiness schema helper.
- Product variant sitemap drops from 418 to roughly 118 or less.
- Size-only pages canonicalize to base product.
- Color/fit pages keep self-canonical where content is meaningfully different.
- Product schema `url` matches canonical strategy.
- Category titles/H1/descriptions are unique.
- Root catalog SEO links do not point to noindex `?color=` URLs.
- Product landing has no city doorway chips and no SEO-operational wording.

## 14. What not to do yet

- Do not add AggregateRating until real verified reviews exist.
- Do not create city landing pages just to capture "Київ/Харків/Львів/Одеса" keywords.
- Do not create indexable color category pages until size variants and query duplicates are cleaned.
- Do not bulk rewrite all product slugs without a 301 redirect map and Search Console monitoring.
- Do not run autofill against production without dry-run and review of generated copy.
- Do not deploy schema changes without validating rendered JSON-LD.
