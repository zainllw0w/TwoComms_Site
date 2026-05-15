# TwoComms SEO Audit — Part 4: H2 Hierarchy, Internal Links, Cache Issues, Recommendations
**Date:** 2026-05-15 | **Site:** https://twocomms.shop

---

## 16. HEADING HIERARCHY (H2/H3) — LIVE

### 16.1 Homepage H2s (5 шт)

| # | H2 | Ключові слова | Оцінка |
|---|----|--------------|--------|
| 1 | (survey block — complex HTML) | — | ⚠️ Не SEO-релевантний |
| 2 | `Категорії` | — | ⚠️ Загальне слово |
| 3 | `Обери за кольором` | — | ⚠️ Загальне |
| 4 | `Новинки` | — | ⚠️ Без ключів |
| 5 | `TWOCOMMS` (footer) | бренд | ⚠️ Uppercase |

**Проблема:** Жоден H2 на головній не містить SEO-ключів ("одяг", "streetwear", "купити").

**Рекомендація:**
- `Категорії` → `Категорії одягу TwoComms`
- `Новинки` → `Новинки каталогу — футболки, худі, лонгсліви`
- `Обери за кольором` → `Обери одяг за кольором`

### 16.2 PDP H2s (classic-tshirt, 9 шт)

| # | H2 | Ключові слова | Оцінка |
|---|----|--------------|--------|
| 1 | `Кому підійде` | — | ✅ Контентний |
| 2 | `Футболка базова` (size guide) | категорія | ✅ |
| 3 | `Доставка Футболка класична по Україні` | товар + доставка + geo | ✅✅ Відмінно |
| 4 | `Догляд за Футболка класична` | товар + догляд | ✅✅ Унікальний |
| 5 | `Відгуки про товар` | — | ⚠️ Загальне |
| 6 | `Схожі товари` | — | ⚠️ Загальне |
| 7 | `Нещодавно переглядали` | — | ⚠️ Загальне |
| 8 | `Футболка класична — деталі моделі` | товар + деталі | ✅✅ SEO landing |
| 9 | `TWOCOMMS` (footer) | бренд | ⚠️ |

**Позитив:** H2 #3, #4, #8 — product-scoped (унікальні для кожного товару). Це відмінна SEO-практика.

### 16.3 Catalog root H2s (6 шт)

| # | H2 | Ключові слова | Оцінка |
|---|----|--------------|--------|
| 1 | `Створи свій` (custom print CTA) | — | ⚠️ |
| 2 | `Купити одяг з принтом онлайн в Україні — доставка Києвом, Харковом, Львовом` | купити + принт + geo | ✅✅✅ Топ |
| 3 | `Замовити чоловічий або жіночий streetwear від українського бренду TwoComms` | замовити + streetwear + бренд | ✅✅✅ Топ |
| 4 | `Український патріотичний streetwear — авторські принти ЗСУ та колаборації` | streetwear + ЗСУ | ✅✅ |
| 5 | `Каталог одягу TwoComms — український стрітвір з характером` | каталог + одяг + бренд | ✅✅ |
| 6 | `TWOCOMMS` (footer) | — | ⚠️ |

**Результат:** Каталог root — найкращі SEO-H2 на сайті. Geo-ключі, commercial intent, brand name.

### 16.4 Category page H2s (tshirts, 7 шт)

| # | H2 | Оцінка |
|---|----|--------|
| 1 | `Створи свій` | ⚠️ |
| 2 | `Найкращі ціни на футболки в TwoComms` | ✅✅ ціна + категорія + бренд |
| 3 | `Футболки TwoComms — авторські принти ЗСУ та streetwear` | ✅✅✅ |
| 4 | `Купити чоловічу футболку з принтом — доставка по Києву, Харкову, Львову` | ✅✅✅ |
| 5 | `Замовити жіночу футболку онлайн в Україні` | ✅✅ |
| 6 | `Унісекс футболки TwoComms — патріотичні принти ЗСУ за справедливою ціною` | ✅✅ |
| 7 | `TWOCOMMS` (footer) | ⚠️ |

**Результат:** Category pages — дуже сильна H2-оптимізація. Gender-segmented, geo, commercial.

---

## 17. ВНУТРІШНЯ ПЕРЕЛІНКОВКА — LIVE

### 17.1 PDP → Support pages

PDP (classic-tshirt) містить прямі посилання на:
- ✅ `/delivery/` (trust badge)
- ✅ `/povernennya-ta-obmin/` (trust badge)
- ✅ `/rozmirna-sitka/` (trust badge + tab)
- ✅ `/custom-print/` (CTA card)
- ✅ `/contacts/`
- ✅ `/faq/`
- ✅ `/dopomoga/`
- ✅ `/pro-brand/`
- ✅ `/doglyad-za-odyagom/`

**Результат: 9/9** support pages linked from PDP. Відмінна перелінковка.

### 17.2 PDP → Related Products

На PDP "classic-tshirt" є 8 related product links + 4 variant links (color, fit).

### 17.3 Відсутні cross-links

**❌ Немає cross-links між варіантами одного дизайну:**
- `/product/my-little-baby/` (футболка) не посилається на `/product/my-little-baby-hd/` (худі)
- Це SEO-Cocon gap — кожен дизайн має 3 варіанти (ts/hd/ls), але вони не пов'язані

**Рекомендація:** Додати блок "Також доступно у: Худі | Лонгслів" на кожну PDP.

---

## 18. CACHE ISSUE — STALE SLUG LINKS

### 18.1 Проблема

Після нормалізації slug, PDP cached fragments ("Схожі товари") ще містять старі URL:

**Знайдені stale links на PDP classic-tshirt:**
```
/product/-225-hoodie-/      → повинно бути /product/225-hoodie/
/product/-225-tshirt-/       → повинно бути /product/225-tshirt/
/product/-my-little-baby/    → повинно бути /product/my-little-baby/
/product/-v2-0_Pokrovsk/     → повинно бути /product/v2-0-pokrovsk/
```

### 18.2 Вплив

- 301 redirects працюють, тому користувачі потраплять на правильну сторінку
- Але пошукові роботи будуть слідувати redirect-ланцюгу замість прямого посилання
- Це додає ~50ms latency і витрачає crawl budget

### 18.3 Рішення

Потрібно очистити Django fragment cache після slug-міграції:
```bash
python manage.py shell -c "from django.core.cache import caches; caches['fragments'].clear()"
```

**Статус:** НЕ ЗАСТОСОВАНО (тільки рекомендація)

---

## 19. ROBOTS.TXT — ДЕТАЛІ

### 19.1 Поточні блокування

| Правило | Оцінка |
|---------|--------|
| `Disallow: /admin/` | ✅ |
| `Disallow: /admin-panel/` | ✅ |
| `Disallow: /accounts/` | ✅ |
| `Disallow: /orders/` | ✅ |
| `Disallow: /cart/` | ✅ |
| `Disallow: /checkout/` | ✅ |
| `Disallow: /api/` | ✅ |
| `Disallow: /*?utm_*` | ✅ UTM tracking |
| `Disallow: /*?gclid=` | ✅ Google Ads |
| `Disallow: /*?fbclid=` | ✅ Facebook |
| `Disallow: /*?sort=` | ✅ Sort params |
| `Disallow: /*?order=` | ✅ Order params |

### 19.2 Відсутні блокування (рекомендація)

| Правило | Причина |
|---------|---------|
| `Disallow: /*?color=` | Color filter створює дублі — вже noindex, але краще не витрачати crawl budget |
| `Disallow: /*?fit=` | Fit param — той самий контент |
| `Disallow: /*?size=` | Size param — канонікал вже на base URL |
| `Disallow: /en/` | EN версія noindex, але crawler все одно заходить |
| `Disallow: /ru/` | RU версія noindex |

### 19.3 AI-боти

Сайт дозволяє всі основні AI-боти: GPTBot, ClaudeBot, PerplexityBot, ChatGPT-User, CCBot та інші. Це правильна стратегія для e-commerce — дозволяє AI-пошуковикам цитувати продукти.

---

## 20. HREFLANG ПРОБЛЕМА

### 20.1 Поточний стан

На кожній сторінці є:
```html
<link rel="alternate" hreflang="uk-UA" href="...">
<link rel="alternate" hreflang="x-default" href="...">
<!-- Плюс в base.html language switcher: -->
hreflang="uk"
hreflang="ru"
hreflang="en"
```

### 20.2 Проблема

RU та EN версії сторінок мають `noindex, follow`. Google не може одночасно:
1. Побачити hreflang → "ось RU-версія цієї сторінки"
2. Побачити noindex → "не індексуй цю сторінку"

Результат: Search Console покаже помилку "Excluded by 'noindex' tag" + "Missing reciprocal hreflang".

### 20.3 Рекомендація

Видалити hreflang-атрибути для `ru` та `en` з мовного перемикача, або прибрати мовний перемикач повністю з `<head>`, залишивши тільки `uk-UA` та `x-default`.

---

## 21. ПІДСУМКОВА ТАБЛИЦЯ РЕКОМЕНДАЦІЙ

| # | Проблема | Пріоритет | Складність | Вплив |
|---|----------|-----------|-----------|-------|
| 1 | ~~Slug normalization~~ | ~~P0~~ | ~~Easy~~ | ~~Зроблено ✅~~ |
| 2 | Cache clear (stale slug links) | P0 | 1 min | Прибере redirect-ланцюги |
| 3 | Homepage title — прибрати "Головна" | P1 | 5 min | +5-10% CTR |
| 4 | Short titles на 5 сторінках | P1 | 15 min | Більше тексту в SERP |
| 5 | Hreflang fix (ru/en) | P1 | 30 min | Прибере GSC warnings |
| 6 | robots.txt — додати color/fit/size | P1 | 5 min | Crawl budget |
| 7 | Homepage H2 keywords | P2 | 15 min | Semantic signals |
| 8 | Cross-links ts↔hd↔ls | P2 | 2 hrs | SEO-Cocon |
| 9 | Шаблонні FAQ → унікальні | P2 | 4 hrs | E-E-A-T |
| 10 | Шаблонний PDP lead text | P2 | 4 hrs | Thin content fix |
