# TwoComms SEO Audit — Part 6: Autofill System, SEO Landing Blocks, Code Architecture
**Date:** 2026-05-15 | **Site:** https://twocomms.shop

---

## 29. AUTOFILL SEO SYSTEM — АРХІТЕКТУРНИЙ АУДИТ

### 29.1 Як працює `product_seo_autofill.py`

**Файл:** `storefront/services/product_seo_autofill.py` (323 рядки)

Система автозаповнення генерує SEO-поля для нових товарів за шаблоном:

| Поле | Builder | Шаблон |
|------|---------|--------|
| `seo_title` | `_build_seo_title()` | `Купити {title} ({accusative})  — TwoComms` (≤60 chars) |
| `seo_description` | `_build_seo_description()` | `{title} — авторський {nom} TwoComms з мілітарним ДНК...` (≤320 chars) |
| `seo_keywords` | `_build_seo_keywords()` | `{title}, купити {nom}, {nom} TwoComms, патріотичний...` (≤300 chars) |
| `main_image_alt` | `_build_main_image_alt()` | `{title} — {nom} TwoComms, авторський принт, DTF-друк` (≤200 chars) |
| `short_description` | `_build_short_description()` | `{title} — авторський {nom} TwoComms у мілітарно-streetwear ДНК` |
| `care_instructions` | `_build_care_instructions()` | Стандартний текст про прання при 30°C |
| `target_audience` | `_build_target_audience()` | Стандартний текст про цільову аудиторію |
| `full_description` | `_build_full_description()` | HTML з H3 блоками "Що ви отримуєте" + "Доставка" |

### 29.2 Позитивні аспекти

- ✅ **Ідемпотентність** — ніколи не перезаписує заповнені поля
- ✅ **Per-category templates** — `CATEGORY_LABEL` адаптує відмінки (футболка/худі/лонгслів)
- ✅ **SEO title ≤60 chars** — правильний ліміт для mobile SERP
- ✅ **FAQ generation** — 5 FAQ per product якщо немає жодного
- ✅ **Accusative case** — «купити футболку» а не «купити футболка»

### 29.3 Знайдені проблеми

| # | Проблема | Деталі | Вплив |
|---|----------|--------|-------|
| 1 | `seo_keywords` генерується | Google ігнорує meta keywords з 2009 | Витрати на генерацію марні |
| 2 | `care_instructions` однакова для всіх | Футболки: "190 г/м²", худі мають 320 г/м² | ⚠️ Неточна інформація |
| 3 | `target_audience` 100% однакова | Той самий текст для всіх 65 товарів | ⚠️ Near-duplicate |
| 4 | `full_description` шаблон: "не просвічується" | Некоректно для чорної тканини | ⚠️ Неточність |
| 5 | FAQ universal — 5 однакових питань | Google бачить 325 однакових FAQ (5×65) | ⚠️ Thin FAQ content |

### 29.4 Рекомендації

1. **Видалити `seo_keywords` builder** — марна генерація, Google ігнорує
2. **Per-category care instructions** — різні spec для tshirts (190 г/м²), hoodie (320 г/м²), longsleeve (200 г/м²)
3. **Per-product target audience** — хоча б 3 варіанти замість 1
4. **FAQ diversity** — додати 2-3 product-specific FAQ (про конкретний принт, колекцію, історію дизайну)

---

## 30. SEO LANDING BLOCKS — АУДИТ

### 30.1 Що це?

**Файл:** `storefront/services/product_seo_landing.py` (451 рядків)

Кожен PDP отримує SEO landing block під "Схожі товари" з:
- H2: `{Product Title} — деталі моделі`
- Theme intro paragraphs
- Color paragraph з internal links
- Fit paragraph з internal links
- City keywords paragraph
- SEO closing paragraph (brand + ZSU)
- Top queries chips (10-14 шт)

### 30.2 Позитивні аспекти

- ✅ **Per-product unique H2** — містить назву товару
- ✅ **Color variant links** — внутрішні посилання на color URLs
- ✅ **Fit variant links** — cross-linking між classic/oversize/regular
- ✅ **Fit-specific SEO paragraphs** — унікальний текст для кожної посадки
- ✅ **City chips removed** (Phase 21) — прибрали doorway-стиль geo chips
- ✅ **Support page chips** — замість city chips додали delivery/size/returns
- ✅ **Admin override** — `seo_bottom_html` дозволяє ручний HTML override

### 30.3 Проблема: City paragraph все ще присутній

Хоча city chips прибрали (Phase 21), `_city_paragraph()` все ще генерує текст:
```
Замовити футболку «Classic» можна по всій Україні: Київ, Харків, Львів, 
Одеса, Дніпро, Запоріжжя, Вінниця, Івано-Франківськ та інші міста.
```

Цей текст:
- ⚠️ Однаковий для всіх 65 товарів (тільки назва міняється)
- ⚠️ "Доставка день у день при замовленні до 14:00" — може бути неактуально
- ⚠️ Google може трактувати як keyword stuffing для geo-запитів

### 30.4 Top Queries Chips — структура

| Тип chips | Кількість | Destination |
|-----------|-----------|------------|
| Color variant | до 4 | `/product/{slug}/{color}/` |
| Fit variant | до 2 | `/product/{slug}/{fit}/` |
| Delivery | 1 | `/delivery/` |
| Size guide | 1 | `/rozmirna-sitka/` |
| Returns | 1 | `/povernennya-ta-obmin/` |
| Custom print | 2 | `/custom-print/` |
| All category | 1 | `/catalog/{cat}/` |
| Theme keywords | до 2 | `/catalog/{cat}/` |

**Результат:** ✅ Відмінна структура внутрішньої перелінковки. Кожен chip — реальне внутрішнє посилання.

---

## 31. SUPPORT CONTENT — FAQ QUALITY

### 31.1 FAQ на support pages (support_content.py)

| Сторінка | Set name | FAQ count | Унікальність |
|----------|----------|-----------|-------------|
| `/faq/` | `HELP_FAQ_ITEMS` | 9 | ✅ Унікальні |
| `/delivery/` | `DELIVERY_FAQ_ITEMS` | 4 | ✅ Унікальні |
| `/dopomoga/` | `HELP_CENTER_FAQ_ITEMS` | 5 | ✅ Перефразовані |
| `/pro-brand/` | `PRO_BRAND_FAQ_ITEMS` | 7 | ✅ Brand-specific |

### 31.2 Анти-канібалізація FAQ

Коментар в коді (рядок 88-99) явно пояснює стратегію:
> "Google only surfaces a FAQ rich result for *one* URL per cluster of identical questions — duplicating the same questions on two pages cannibalises whichever one Google picks."

Тому `/dopomoga/` FAQ спеціально перефразовані відносно `/faq/`:
- `/faq/`: "Як оформити замовлення на TwoComms?"
- `/dopomoga/`: "З чого почати оформлення замовлення на TwoComms?"

**Результат:** ✅ Грамотна анти-канібалізація. Кожна сторінка має шанс на окремий FAQ rich result.

### 31.3 Product FAQ (autofill UNIVERSAL_FAQS)

| # | Питання | Тип |
|---|---------|-----|
| 1 | Як обрати розмір {nom}? | Шаблонний ← однаковий для всіх |
| 2 | Чи можна прати {nom_acc} в машинці? | Шаблонний ← однаковий |
| 3 | Скільки триває доставка? | Шаблонний ← 100% однаковий |
| 4 | Як повернути або обміняти товар? | Шаблонний ← 100% однаковий |
| 5 | Чи можна замовити з власним принтом? | Шаблонний ← 100% однаковий |

**Проблема:** FAQ #3, #4, #5 — абсолютно ідентичні для ВСІХ товарів. Різниця лише в #1 і #2 де {nom} = футболка/худі/лонгслів.

**Вплив:**
- Google бачить 65 сторінок з ідентичними FAQ #3-#5
- Це thin/duplicate content signal
- FAQ rich results для product pages будуть пригнічені

**Рекомендація:**
1. FAQ #3-#5 — видалити або замінити product-specific питаннями
2. Додати: "Який принт на {title}?" → відповідь про конкретний дизайн
3. Додати: "Яка тканина у {title}?" → відповідь з реальними specs

---

## 32. PRODUCT_COPY_V2 — ТЕМАТИЧНА СИСТЕМА

### 32.1 Що це?

`storefront/services/product_copy_v2.py` — система тематичних "теми" (themes) для кожного товару. Кожна тема визначає:
- `intro_short` / `intro_long` — тексти для SEO landing
- `kw` — ключові слова для chips
- Тематичний "голос" бренду

### 32.2 Як це впливає на SEO

SEO landing block використовує `build_copy(product)` для генерації `full_description` параграфів. Це означає, що кожен товар може мати тематично різний SEO-текст.

**Позитив:** Якщо theme правильно присвоєні — кожен PDP має унікальний landing text.

---

## 33. ЗВЕДЕНА КАРТА ПРОБЛЕМ

### 33.1 Критичні (P0) — Вже виправлено

| # | Проблема | Статус |
|---|----------|--------|
| 1 | 38 slug з дефісами/uppercase | ✅ Виправлено + 301 redirects |

### 33.2 Важливі (P1) — Потребують уваги

| # | Проблема | Файл | Зусилля |
|---|----------|------|---------|
| 1 | Cache stale links (PDP related products) | Django cache | 1 min |
| 2 | 5 коротких title (< 30 chars) | seo_utils.py / admin | 15 min |
| 3 | Hreflang ru/en конфлікт з noindex | base.html | 30 min |
| 4 | robots.txt — додати ?color=, ?fit=, ?size= | robots.txt view | 5 min |
| 5 | Homepage title — прибрати "Головна" | index.html | 5 min |

### 33.3 Покращення (P2) — Зміцнять SEO

| # | Проблема | Зусилля |
|---|----------|---------|
| 1 | Homepage H2s без ключових слів | 15 min |
| 2 | Шаблонні FAQ #3-#5 (ідентичні на 65 PDP) | 4 hrs |
| 3 | `classic-tshirt` — єдиний товар з thin full_description | 30 min |
| 4 | 13 товарів з duplicate description start | 2 hrs |
| 5 | Per-category care instructions | 30 min |
| 6 | City paragraph однаковий на всіх PDP | 1 hr |
| 7 | Cross-links між ts↔hd↔ls одного дизайну | 2 hrs |

### 33.4 Стратегічні (P3) — Довгостроковий ріст

| # | Проблема | Зусилля |
|---|----------|---------|
| 1 | Content hub / blog | 2+ weeks |
| 2 | Look-book сторінки | 1 week |
| 3 | Google Business Profile | 2 hrs |
| 4 | UGC-фото у review system | 1 week |
