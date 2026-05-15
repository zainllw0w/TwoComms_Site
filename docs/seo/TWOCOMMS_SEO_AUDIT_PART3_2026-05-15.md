# TwoComms SEO Audit — Part 3: Live Production Verification
**Date:** 2026-05-15 | **Site:** https://twocomms.shop

---

## 8. TITLE / DESCRIPTION / H1 — LIVE PRODUCTION RESULTS

### 8.1 Все страницы сайта — полная проверка

| # | URL | HTTP | Title | H1 | Оцінка |
|---|-----|------|-------|-----|--------|
| 1 | `/` | 200 | `TwoComms — Стріт & Мілітарі Одяг \| Головна` (48 ch) | `TwoComms — бренд: Стріт & мілітарі одяг` (visually-hidden prefix) | ⚠️ "Головна" — зайве слово |
| 2 | `/catalog/` | 200 | `Каталог TwoComms — футболки, худі, лонгсліви з принтами` (56 ch) | `Каталог одягу` | ✅ |
| 3 | `/catalog/tshirts/` | 200 | `Футболки TwoComms — стрітвеар та мілітарі-принти від...` (~60 ch) | ✅ seo_h1 override | ✅ |
| 4 | `/catalog/hoodie/` | 200 | `Худі TwoComms — теплі толстовки зі стрітвеар-принтами та...` (~62 ch) | ✅ seo_h1 override | ✅ |
| 5 | `/catalog/long-sleeve/` | 200 | `Лонгсліви TwoComms — лаконічний стрітвеар з рукавами на...` (~62 ch) | ✅ seo_h1 override | ✅ |
| 6 | `/product/classic-tshirt/` | 200 | `Футболка класична — купити футболку TwoComms` (45 ch) | `{product.title}` | ✅ |
| 7 | `/faq/` | 200 | `FAQ — оплата, доставка, розміри і сервіс \| TwoComms` (52 ch) | `Поширені питання по покупці та сервісу` | ✅ |
| 8 | `/delivery/` | 200 | `Доставка і оплата — TwoComms` (28 ch) | `Доставка і оплата` | ⚠️ Title короткий |
| 9 | `/pro-brand/` | 200 | `TwoComms — харківський бренд одягу про характер...` (~70 ch) | (complex HTML, no plain text H1) | ⚠️ H1 складний |
| 10 | `/dopomoga/` | 200 | `Допомога — умови замовлення, оплата і підтримка \| TwoComms` (60 ch) | `Допомога та базові правила сайту` | ✅ |
| 11 | `/rozmirna-sitka/` | 200 | `Розмірна сітка і поради по посадці \| TwoComms` (47 ch) | `Розмірна сітка та поради по посадці` | ✅ |
| 12 | `/doglyad-za-odyagom/` | 200 | `Догляд за одягом TwoComms` (25 ch) | `Догляд за одягом` | ⚠️ Title короткий |
| 13 | `/contacts/` | 200 | `Контакти — TwoComms` (20 ch) | `Контакти` | ⚠️ Title дуже короткий |
| 14 | `/custom-print/` | 200 | `DTF-конфігуратор кастомного одягу — TwoComms` (46 ch) | `Створи річ,` (обрізаний) | ⚠️ H1 неповний |
| 15 | `/wholesale/` | 200 | `Оптові закупівлі та дропшипінг одягу — TwoComms` (49 ch) | (no plain text H1) | ⚠️ |
| 16 | `/novyny/` | 200 | `Новини, новинки та апдейти бренду \| TwoComms` (46 ch) | `Новини та апдейти бренду` | ✅ |
| 17 | `/povernennya-ta-obmin/` | 200 | `Повернення та обмін товарів \| TwoComms` (39 ch) | `Повернення та обмін` | ✅ |
| 18 | `/vidstezhennya-zamovlennya/` | 200 | `Відстеження замовлення, статуси і TTN \| TwoComms` (50 ch) | `Відстеження замовлення` | ✅ |
| 19 | `/polityka-konfidentsiynosti/` | 200 | `Політика конфіденційності \| TwoComms` (37 ch) | `Політика конфіденційності` | ✅ |
| 20 | `/umovy-vykorystannya/` | 200 | `Умови використання сайту \| TwoComms` (36 ch) | `Умови використання сайту` | ✅ |
| 21 | `/mapa-saytu/` | 200 | `Карта сайту TwoComms — каталог, підтримка та бренд` (51 ch) | — | ✅ |
| 22 | `/cooperation/` | 200 | `Співпраця з TwoComms` (21 ch) | — | ⚠️ Title короткий |

### 8.2 Знайдені проблеми з Title

**Занадто короткі title (< 30 chars):**
- `/contacts/` — 20 chars → Рекомендація: `Контакти TwoComms — телефон, Telegram, Instagram | Харків`
- `/cooperation/` — 21 chars → Рекомендація: `Співпраця з TwoComms — колаборації, B2B та партнерство`
- `/doglyad-za-odyagom/` — 25 chars → Рекомендація: `Догляд за одягом TwoComms — як прати, зберігати DTF-принт`
- `/delivery/` — 28 chars → Рекомендація: `Доставка і оплата TwoComms — Нова Пошта, 1-2 дні по Україні`

> [!NOTE]
> Google рекомендує title довжиною 50-60 символів. Коротші title — це втрачений простір у SERP.

---

## 9. CANONICAL / HREFLANG / OG TAGS — LIVE CHECK

### 9.1 Homepage meta tags

| Tag | Значення | Оцінка |
|-----|---------|--------|
| `rel="canonical"` | `https://twocomms.shop/` | ✅ |
| `hreflang="uk-UA"` | `https://twocomms.shop/` | ✅ |
| `hreflang="x-default"` | `https://twocomms.shop/` | ✅ |
| `og:title` | `TwoComms — стріт & мілітарі одяг з ексклюзивним дизайном` | ✅ |
| `og:description` | Містить "харківський стрітвеар-бренд" (LocalSEO) | ✅ |
| `og:image` | Вказано, з width=1200, height=630 | ✅ |
| `og:image:alt` | `TwoComms — стріт & мілітарі одяг` | ✅ |
| `twitter:card` | `summary_large_image` | ✅ |

### 9.2 PDP meta tags (classic-tshirt)

| Tag | Значення | Оцінка |
|-----|---------|--------|
| `rel="canonical"` | `https://twocomms.shop/product/classic-tshirt/` | ✅ Оновлений slug |
| `og:type` | `product` | ✅ |
| `product:price:amount` | `788` | ✅ |
| `product:price:currency` | `UAH` | ✅ |
| `product:availability` | `instock` | ✅ |
| `product:retailer_item_id` | `TC-1` | ✅ |
| `product:condition` | `new` | ✅ |
| `product:brand` | `TwoComms` | ✅ |

### 9.3 Проблема: Orphan hreflang для RU/EN

На головній сторінці виявлені hreflang-посилання на `ru` та `en` версії, але ці версії мають `noindex`. Google буде скаржитися на "missing reciprocal hreflang" в Search Console.

**Рекомендація:** Видалити hreflang для ru/en поки ці версії не мають унікального контенту.

---

## 10. STRUCTURED DATA — LIVE VERIFICATION

### 10.1 Кількість JSON-LD блоків по сторінках

| Сторінка | JSON-LD блоків | Типи |
|----------|---------------|------|
| `/` (homepage) | 3 | Organization, WebSite+SearchAction, WebPage+ItemList |
| `/product/classic-tshirt/` | 3 | Organization, WebSite, Product+BreadcrumbList (@graph) |
| `/faq/` | 4 | Organization, WebSite, FAQPage, BreadcrumbList |
| `/catalog/tshirts/` | 3 | Organization, WebSite, CollectionPage+BreadcrumbList (@graph) |

### 10.2 Organization schema (глобальний)

```json
{
  "@type": "Organization",
  "@id": "https://twocomms.shop/#organization",
  "name": "TwoComms",
  "url": "https://twocomms.shop/",
  "logo": "https://twocomms.shop/static/img/logo.svg",
  "sameAs": ["https://instagram.com/twocomms", "https://t.me/twocomms"],
  "contactPoint": { "telephone": "+380966543212", "contactType": "customer support" }
}
```
**Оцінка:** ✅ Стабільний @id, реальний телефон, sameAs з соцмережами.

### 10.3 PDP Product schema highlights

- ✅ Product + BreadcrumbList в одному `@graph`
- ✅ Offers з shippingDetails та hasMerchantReturnPolicy
- ✅ AggregateRating — тільки при реальних відгуках (≥1)
- ✅ Availability: `MadeToOrder` (правильно для DTF)
- ✅ Brand, SKU, MPN — заповнені

---

## 11. TEMPLATE COMMENT LEAKS — LIVE CHECK

| Сторінка | `{# ... #}` leaks | Оцінка |
|----------|-------------------|--------|
| Homepage | 0 | ✅ |
| PDP | 0 | ✅ |
| Catalog | 0 | ✅ |

**Результат:** Всі Django template comments коректно приховані. Витік усунуто в Phase 21.

---

## 12. SECURITY HEADERS

Перевірено на production:

| Header | Значення | Оцінка |
|--------|---------|--------|
| `strict-transport-security` | `max-age=31536000; includeSubDomains; preload` | ✅ HSTS Preload |
| `x-content-type-options` | `nosniff` | ✅ |
| `x-xss-protection` | `1; mode=block` | ✅ |
| `x-frame-options` | `SAMEORIGIN` | ✅ |
| `referrer-policy` | `strict-origin-when-cross-origin` | ✅ |
| `content-security-policy` | Повний CSP з whitelist | ✅ |
| Protocol | HTTP/2 | ✅ |
| Server | LiteSpeed | ✅ |

**Результат: 10/10** — Всі security headers на місці.

---

## 13. SLUG FIX VERIFICATION (Applied 2026-05-15)

### 13.1 Результат нормалізації

**38 slug нормалізовано** з 301 redirects:

| Тип проблеми | Кількість | Приклад |
|-------------|-----------|---------|
| Початковий дефіс | 28 | `-my-little-baby` → `my-little-baby` |
| Підкреслення | 4 | `Hoodie_Silent_Winter` → `hoodie-silent-winter` |
| Uppercase | 5 | `Idea-hd` → `idea-hd` |
| Typo fix | 3 | `clasic-tshort` → `classic-tshirt` |

### 13.2 Live verification

| Перевірка | Результат |
|-----------|----------|
| `/product/my-little-baby/` | HTTP 200 ✅ |
| `/product/-my-little-baby/` | HTTP 301 → `/product/my-little-baby/` ✅ |
| `/product/classic-tshirt/` | HTTP 200 ✅ |
| `/product/clasic-tshort/` | HTTP 301 → `/product/classic-tshirt/` ✅ |
| Sitemap оновлений | Всі URL чисті, без дефісів ✅ |

---

## 14. SITEMAP — LIVE STRUCTURE

### 14.1 Sitemap Index

| Sub-sitemap | Last Modified | URLs |
|------------|---------------|------|
| `sitemap-static.xml` | — | 18 |
| `sitemap-products.xml` | 2026-05-14 | 65 |
| `sitemap-product-variants.xml` | 2026-05-14 | ~100+ |
| `sitemap-categories.xml` | 2026-05-10 | 3 |
| `sitemap-images.xml` | 2026-05-14 | 65 |

### 14.2 Static sitemap — всі URL працюють

Всі 18 URL в `sitemap-static.xml` повертають HTTP 200. Жодних 404.

---

## 15. BREADCRUMBS — LIVE CHECK

| Сторінка | Видимі breadcrumbs | JSON-LD BreadcrumbList | Оцінка |
|----------|-------------------|----------------------|--------|
| Homepage | ❌ (не потрібні) | ❌ | ✅ |
| Catalog root | ✅ `Головна › Каталог` | ✅ | ✅ |
| Category page | ✅ `Головна › Каталог › {Категорія}` | ✅ | ✅ |
| PDP | ✅ `Головна › Каталог › {Кат} › {Товар}` | ✅ (@graph) | ✅ |
| FAQ | ✅ `Головна / ...` | ✅ BreadcrumbList | ✅ |
| Delivery | ✅ `Головна / ...` | ✅ | ✅ |
| Help Center | ✅ | ✅ | ✅ |

**Результат:** Breadcrumbs присутні на всіх ключових сторінках, включаючи support pages.
