# TwoComms SEO Audit — Part 5: Content Depth, Image ALT, Performance, Duplicates
**Date:** 2026-05-15 | **Site:** https://twocomms.shop

---

## 22. КОНТЕНТ ГЛИБИНА — АНАЛІЗ ПО ТОВАРАХ

### 22.1 Content depth scoring

Оцінка загального об'єму контенту кожного товару (description + full_description + details + care + target_audience):

| Рівень | Criteria | Товарів | % |
|--------|----------|---------|---|
| **RICH** (> 800 chars) | Повний контент | 64 | 98.5% |
| **OK** (200-800 chars) | Базовий контент | 1 | 1.5% |
| **THIN** (< 200 chars) | Тонкий контент | 0 | 0% |

### 22.2 Проблемний товар

| ID | Slug | Total chars | Проблема |
|----|------|------------|---------|
| 1 | `classic-tshirt` | 636 | desc=73 chars, full_desc=73 chars — найменше контенту |

> [!NOTE]
> `classic-tshirt` — єдиний товар з рівнем OK. Його full_description = description (73 chars), тоді як решта товарів мають 1000+ chars в full_description.

### 22.3 Контент-лідери (Top 5)

| ID | Slug | Total chars |
|----|------|------------|
| 104 | `twocomms-reality-bends-dark-neon-edition` | 4,679 |
| 103 | `twocomms-reality-bends-future-2026` | 4,522 |
| 102 | `hd-twocomms-reality-bends-future-2026` | 4,401 |
| 106 | `twocomms-beliveidea-ts` | 3,793 |
| 105 | `ts-twocomms-reality-bends-mentol` | 3,455 |

### 22.4 Поле details_text

| Метрика | Значення |
|---------|---------|
| Товарів з details_text | 1/65 (лише `twocomms-beliveidea-ts`) |
| Товарів без details_text | 64/65 |

**Проблема:** Коли `details_text` порожній, PDP показує шаблонний блок з однаковими specs для всіх товарів:
```
Матеріал: 95% бавовна, 5% еластан — преміум якість, 190 г/м²
```
Це неправильно для худі (320 г/м² трикотаж) і лонгслівів (200 г/м²).

---

## 23. ДУБЛІКАТИ ОПИСІВ

### 23.1 Знайдені дублікати description (перші 50 chars)

| Кількість | Спільний текст | Slug-и |
|-----------|---------------|--------|
| 3 | `«Череп З Трояндою» — мінімалістичний принт про ост...` | last-breath, last-breath-hd, last-breath-ls |
| 3 | `«Серце Та Грощі» — англомовний мем-принт TwoComms...` | death-grabs-ass, death-grabs-ass-hd, death-grabs-ass-ls |
| 3 | `«Це Моя Посадка» — сатиричний англомовний принт Tw...` | lord-of-the-lending, lord-of-the-lending-hd, lord-of-the-lending-ls |
| 2 | `«І На Той Світ З Собою Візьму» — рядок, який звучи...` | death-gbs-ass-ts, death-gbs-ass-ls |
| 2 | `Не пафос. Не мода. Це — вулична правда...` | kha-edition-ls, kha-style-ls |

### 23.2 SEO Title — унікальність

| Метрика | Значення |
|---------|---------|
| Унікальних SEO title | **65/65 (100%)** |
| Дубльованих SEO title | **0** |

✅ Відмінно — кожен товар має унікальний SEO title.

### 23.3 Ризик дублікатів description

**Проблема:** 13 товарів (5 груп) мають однаковий початок description. Google може класифікувати це як near-duplicate content між ts/hd/ls варіантами одного дизайну.

**Рекомендація:** Для кожного варіанту (ts/hd/ls) description повинен починатися з унікального речення, що згадує тип одягу:
- TS: "Ця **футболка** з принтом «Череп» — ..."
- HD: "Це **худі** з принтом «Череп» — теплий варіант для ..."
- LS: "Цей **лонгслів** з принтом «Череп» — мінімалізм ..."

---

## 24. IMAGE ALT TEXTS — АУДИТ

### 24.1 PDP (classic-tshirt) — ALT аналіз

| Зображення | Alt текст | Оцінка |
|-----------|-----------|--------|
| Hero product | `Футболка класична TwoComms - стильний базовий одяг для повсякденного комфортного носіння.` | ✅ Descriptive |
| Logo (navbar) | `TwoComms логотип — стріт & мілітарі одяг` | ✅ |
| Decorative icons | `""` (empty) | ✅ Правильно — aria-hidden |
| Related product 1 | `Футболка «MY LITTLE BABY» TwoComms...` | ✅ Descriptive |
| Related product 2 | `Футболка «ДЕ МОЇ ПОДАРУНКИ, МРАЗОТА?» від TwoComms...` | ✅ Descriptive |
| Footer logo | `TWOCOMMS` | ⚠️ Коротке |

### 24.2 Статистика

| Метрика | Значення |
|---------|---------|
| Images with descriptive alt | 10+ | ✅ |
| Images with empty alt (decorative) | 3 | ✅ Правильно |
| Images without alt attribute | 0 | ✅ |

**Результат: 9/10** — Alt texts добре оптимізовані, product images мають розгорнуті описи.

---

## 25. PAGE PERFORMANCE — TTFB & SIZE

### 25.1 Server Response Time (TTFB)

| Сторінка | HTTP | Size | TTFB | Total | Оцінка |
|----------|------|------|------|-------|--------|
| Homepage | 200 | 244 KB | 188ms | 252ms | ✅ Excellent |
| Catalog | 200 | 99 KB | 121ms | 171ms | ✅ Excellent |
| PDP | 200 | 157 KB | 109ms | 147ms | ✅ Excellent |
| FAQ | 200 | 82 KB | 152ms | 186ms | ✅ Excellent |

### 25.2 Оцінка

- ✅ Всі TTFB < 200ms (Google рекомендує < 600ms)
- ✅ Homepage найбільший (244 KB) — все одно під 300ms
- ✅ PDP 157 KB — оптимально для product page з structured data
- ✅ HTTP/2 + LiteSpeed — правильний стек

### 25.3 HTML Size concern

| Сторінка | Raw HTML | Рекомендація |
|----------|---------|-------------|
| Homepage | 244 KB | ⚠️ Великий — можливо через інлайн CSS + SVG survey |
| PDP | 157 KB | OK |
| Catalog | 99 KB | ✅ Нормальний |
| FAQ | 82 KB | ✅ Нормальний |

> [!NOTE]
> Homepage 244 KB — на межі. Google рекомендує HTML < 100 KB для mobile. Але оскільки CSS інлайнується (Phase 22c), ефективний розмір менший.

---

## 26. ROBOTS META TAG — PER-PAGE CHECK

### 26.1 Indexable pages

| Сторінка | robots meta | Оцінка |
|----------|------------|--------|
| Homepage | `index, follow` (default) | ✅ |
| Catalog root | `index, follow, max-image-preview:large` | ✅ |
| Category | `index, follow, max-image-preview:large` | ✅ |
| PDP (ua) | `index, follow, max-image-preview:large, max-snippet:-1` | ✅ |
| FAQ | `index, follow` (default) | ✅ |
| Delivery | `index, follow` | ✅ |

### 26.2 Noindex pages (правильно)

| Сторінка | robots | Причина |
|----------|--------|---------|
| PDP (ru/en) | `noindex, follow` | ❌ Немає унікального RU/EN контенту |
| PDP (?color=X) | `noindex, follow` | ✅ Дублікат canonical |
| PDP (?size=X) | `noindex, follow` | ✅ Дублікат |
| Catalog (?sort=X) | `noindex, follow` | ✅ Sorting дублікат |
| Search | `noindex, follow` | ✅ Dynamic content |

---

## 27. OPEN GRAPH IMAGE DIMENSIONS

### 27.1 Production check

| Сторінка | og:image | width×height | Оцінка |
|----------|---------|-------------|--------|
| Homepage | `social-preview.jpg` | 1200×630 | ✅ Ідеальний формат |
| PDP | Product main image | Auto | ✅ |
| Category | `category.cover` | — | ⚠️ Перевірити dimensions |

### 27.2 Рекомендація

og:image повинен бути 1200×630px (1.91:1 ratio) для всіх сторінок. Product images зазвичай 1080×1350 (portrait) — це обрізається в social previews.

---

## 28. ВНУТРІШНЯ СТРУКТУРА FOOTER

Footer містить 4 секції навігації:

| Секція | Посилання | SEO-вплив |
|--------|----------|-----------|
| Покупка | Каталог, Футболки, Худі, Лонгсліви, Custom Print | ✅ Category deep links |
| Підтримка | Доставка, FAQ, Повернення, Відстеження, Розмірна сітка | ✅ Support page boost |
| Бренд | Про бренд, Новини, Співпраця, Контакти | ✅ E-E-A-T signals |
| Юридичне | Політика, Умови, Карта сайту | ✅ Trust signals |

**Результат:** ✅ Footer дуже добре структурований для SEO — всі важливі сторінки доступні з footer, що розподіляє PageRank рівномірно.
