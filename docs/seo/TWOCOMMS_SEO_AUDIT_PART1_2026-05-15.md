# TwoComms SEO Audit — Part 1: Technical & URL Infrastructure
**Date:** 2026-05-15 | **Site:** https://twocomms.shop

---

## 1. КРИТИЧНІ ПРОБЛЕМИ З URL (SLUG) — P0

### 1.1 Слаги з початковим дефісом (32 товари з 65 — 49%)

**Проблема:** ~49% опублікованих товарів мають slug що починається з `-`, створюючи URL виду `/product/-my-little-baby/`. Це порушує URL best practices, знижує CTR у SERP і може спричинити проблеми з URL-парсерами.

**Уражені товари (32 шт):**

| Slug | Проблеми |
|------|----------|
| `-my-little-baby`, `-my-little-baby-hd`, `-my-little-baby-ls` | starts_with_hyphen |
| `-last-breath`, `-last-breath-hd`, `-last-breath-ls` | starts_with_hyphen |
| `-death-grabs-ass`, `-death-grabs-ass-hd`, `-death-grabs-ass-ls` | starts_with_hyphen |
| `-lord-of-the-lending`, `-lord-of-the-lending-hd`, `-lord-of-the-lending-ls` | starts_with_hyphen |
| `-red-leaves-ts`, `-red-leaves-hd`, `-red-leaves-ls` | starts_with_hyphen |
| `-death-gbs-ass-ts`, `-death-gbs-ass-hd`, `-death-gbs-ass-ls` | starts_with_hyphen |
| `-kha-style-ts`, `-kha-style-hd`, `-kha-style-ls` | starts_with_hyphen |
| `-225-tshirt-`, `-225-hoodie-` | starts + ends with hyphen |
| `-v2-0_Pokrovsk` | hyphen, underscore, UPPERCASE |
| `-20-twocomms-Legend` | hyphen, UPPERCASE |
| `Hoodie_Silent_Winter` | underscore, UPPERCASE |
| `Idea-hd`, `HD-twocomms-reality-bends-future-2026` | UPPERCASE |
| `-glory-of-ukraine-hd`, `-twocomms-reality-bends-future-2026` | starts_with_hyphen |
| `-twocomms-reality-bends-dark-neon-edition`, `-twocomms-beliveidea-ts` | starts_with_hyphen |

**Рекомендація:**
1. Management command: `slug = slug.strip('-').lower().replace('_', '-')`
2. 301-redirect зі старого slug на новий
3. Оновити sitemap + запросити re-crawl в GSC

### 1.2 Помилки в написанні slug

| Поточний slug | Проблема | Рекомендований |
|---------------|----------|----------------|
| `clasic-tshort` | classic→clasic, tshirt→tshort | `classic-tshirt` |
| `buisness-money` | business→buisness | `business-money` |

### 1.3 Відсутність семантичної структури

Рекомендація: `{design-name}-{category}` pattern:
- `my-little-baby-tshirt` замість `-my-little-baby`
- `my-little-baby-hoodie` замість `-my-little-baby-hd`

---

## 2. TITLE, DESCRIPTION, H1

### 2.1 Загальна статистика

| Метрика | Значення | Оцінка |
|---------|---------|--------|
| Товарів з SEO title | 65/65 (100%) | ✅ |
| Товарів з SEO description | 65/65 (100%) | ✅ |
| Товарів без main_image | 1/65 | ⚠️ Виправити |
| Категорій з seo_title | 3/3 (100%) | ✅ |
| Категорій з seo_description | 3/3 (100%) | ✅ |
| Категорій з cover | 3/3 (100%) | ✅ |

### 2.2 Аналіз по сторінках

**Головна:** Title `TwoComms — Стріт & Мілітарі Одяг | Головна` (48 chars) — ⚠️ "Головна" зайве, краще додати geo-сигнал "з Харкова"

**Каталог root:** Title `Каталог TwoComms — футболки, худі, лонгсліви з принтами` (56 chars) — ✅ Ідеально

**Категорії:** Всі мають ручні SEO title — ✅

**PDP pattern:** `{Назва} — купити {категорія} TwoComms` — ✅ Включає "купити" (комерційний intent)

---

## 3. ХЛІБНІ КРОШКИ

| Сторінка | Breadcrumbs | JSON-LD | Оцінка |
|----------|------------|---------|--------|
| Каталог | ✅ `Головна › Каталог` | ✅ | OK |
| Категорія | ✅ `Головна › Каталог › {Кат}` | ✅ | OK |
| PDP | ✅ `Головна › Каталог › {Кат} › {Товар}` | ✅ @graph | OK |
| Support pages | ❌ Відсутні | ❌ | **Додати** |

**Рекомендація:** Додати breadcrumbs на support pages: `Головна › Підтримка › {Сторінка}`

---

## 4. ROBOTS.TXT

**Позитивне:** ✅ UTM, gclid, fbclid, sort заблоковані. AI-боти дозволені. Sitemap вказано.

**Проблеми:**
- ⚠️ Відсутній `Disallow: /*?color=` (crawl budget waste)
- ⚠️ Відсутній `Disallow: /*?fit=` і `/*?size=`

---

## 5. SITEMAP

**Структура:** 5 sub-sitemaps (static, products, variants, categories, images) — ✅

**Критично:** Sitemap містить URL з початковими дефісами та uppercase:
```
/product/-my-little-baby/
/product/-v2-0_Pokrovsk/
/product/Hoodie_Silent_Winter/
```

---

## 6. STRUCTURED DATA

| Schema | Де | @id | Оцінка |
|--------|-----|-----|--------|
| Organization | base.html (глобально) | `#organization` | ✅ |
| WebSite+SearchAction | base.html (глобально) | `#website` | ✅ |
| Product (@graph) | PDP | — | ✅ Повний |
| BreadcrumbList | PDP, catalog | стабільний | ✅ |
| AggregateRating | PDP (умовний) | — | ✅ Тільки при реальних відгуках |
| CollectionPage | catalog | — | ✅ |
| FAQPage | support pages only | — | ✅ Видалений з PDP |

**⚠️ Залишковий `product_rating_schema` tag** (seo_tags.py:462) — спрощений Product schema без shipping/returns. Ризик дублікату. Позначити як deprecated.

---

## 7. FAQ

- **836 FAQ items** на 65 товарів (~12.9/товар)
- **Проблема:** Шаблонні FAQ з автозаповнення — однакові питання для різних товарів
- **Support page FAQ** — ✅ всі унікальні (9+4+5+7 items на різних сторінках)
- **Рекомендація:** Замінити шаблонні product FAQ на унікальні для топ-20 товарів

---

*Продовження в Part 2*
