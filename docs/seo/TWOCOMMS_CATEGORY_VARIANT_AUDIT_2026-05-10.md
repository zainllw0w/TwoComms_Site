# Аудит категорий, вариативности и индексации TwoComms
## Третий документ глубокого SEO-аудита

Дата: 2026-05-10

---

## ЧАСТЬ 1: Категории — title, description, H1, H2, H3, keywords

### 1.1 Анализ шаблона catalog.html

**Title tag (строка 18):**
```
{% if category %}{{ category.name }} — TwoComms
{% else %}Каталог одягу — TwoComms{% endif %}
```

| Категория | Текущий title | Проблема | Рекомендуемый title |
|---|---|---|---|
| Футболки | `Футболки — TwoComms` | Нет "купити", нет intent-keyword | `Купити футболки з принтом — TwoComms \| Стріт & мілітарі` |
| Худі | `Худі — TwoComms` | Нет "купити", нет intent-keyword | `Купити худі з авторським принтом — TwoComms \| Україна` |
| Лонгсліви | `Лонгсліви — TwoComms` | Нет "купити", нет intent-keyword | `Купити лонгсліви TwoComms — мілітарі streetwear \| DTF-друк` |
| /catalog/ | `Каталог одягу — TwoComms` | Нормально, но можно лучше | `Каталог стріт & мілітарі одягу TwoComms — футболки, худі, лонгсліви` |

**Рекомендация:** Добавить поле `seo_title` в модель Category и использовать его:
```django
{% if category.seo_title %}{{ category.seo_title }}
{% elif category %}Купити {{ category.name|lower }} — TwoComms
{% else %}Каталог одягу — TwoComms{% endif %}
```

---

**Meta description (строка 20):**
```
Купити {{ category.name|lower }} в TwoComms. Якісний стріт & мілітарі одяг
з ексклюзивним дизайном і швидкою доставкою по Україні.
```

| Категория | Текущий description | Проблема |
|---|---|---|
| Футболки | «Купити футболки в TwoComms. Якісний стріт...» | Шаблонный, одинаковый формат для всех |
| Худі | «Купити худі в TwoComms. Якісний стріт...» | Нет уникального USP категории |
| Лонгсліви | «Купити лонгсліви в TwoComms. Якісний стріт...» | Нет цены, нет материала |

**Рекомендация:** Добавить `seo_description` в Category и написать уникальные:

| Категория | Рекомендуемый description |
|---|---|
| Футболки | `Футболки TwoComms з авторськими принтами від ₴899. Щільна бавовна 190 г/м², DTF-друк 50+ прань. Класика та оверсайз. Доставка по Україні 1-3 дні.` |
| Худі | `Худі TwoComms — теплий streetwear з мілітарним ДНК. Бавовна 320 г/м², флісова підкладка, DTF-друк. Від ₴1699. Безкоштовна доставка від 2000₴.` |
| Лонгсліви | `Лонгсліви TwoComms з авторськими принтами. Щільна бавовна, DTF-друк, зроблено в Україні. Від ₴999. Класика та оверсайз посадки.` |

---

**H1 (строка 140-148):**
```html
<h1>{{ category.name }}</h1>  <!-- "Футболки", "Худі", "Лонгсліви" -->
```

**Проблема:** H1 — просто название категории. Нет ключевого слова "купити", нет бренда.

| Категория | Текущий H1 | Рекомендуемый H1 |
|---|---|---|
| Футболки | `Футболки` | `Футболки TwoComms з авторськими принтами` |
| Худі | `Худі` | `Худі TwoComms — стрітвеар з характером` |
| Лонгсліви | `Лонгсліви` | `Лонгсліви TwoComms — мілітарний streetwear` |
| /catalog/ | `Каталог одягу` | `Каталог одягу TwoComms` ✅ нормально |

**Рекомендация:** Добавить `seo_h1` поле в Category.

---

**H2 на категориях (строка 181, 301, 397):**

На каждой категории есть 3 H2:
1. `Створи свій дизайн` — из print panel (на КАЖДОЙ категории)
2. `Результати пошуку` — только если search page
3. `{{ category.seo_text_title|default:category.name }} — TwoComms` — SEO-блок внизу

**Проблема:** H2 "Створи свій дизайн" появляется на КАЖДОЙ категории одинаково. Это дублирование H2 контента.

**Рекомендация:** Заменить H2 print panel на `<div>` с `<strong>` — это не заголовок раздела каталога, а CTA-баннер. Либо сделать H2 уникальным: «Свій принт на {category.name|lower}».

---

**H3 на категориях:**
В текущем шаблоне H3 не используются вообще. Это упущение — H3 можно использовать для подкатегорий, популярных запросов, FAQ.

---

### 1.2 Ключевые слова (meta keywords, строка 22-23)

```django
{% if category %}{{ category.name|lower }}, {% endif %}стріт одяг, мілітарі одяг,
футболки, худі, лонгсліви, TwoComms, ексклюзивний дизайн, якісний одяг, каталог одягу
```

**Проблема:** Google официально не использует meta keywords. Но есть более серьёзная проблема — ключевые слова ОДИНАКОВЫЕ для всех категорий, кроме `{{ category.name|lower }}`. Это не помогает и не вредит, но код можно удалить.

**Рекомендация:** Убрать `{% block keywords %}` из catalog.html полностью. Очистить meta keywords из base.html.

---

### 1.3 Structured Data на категориях

**CollectionPage + ItemList (строки 60-82):**
```json
{
  "@type": "CollectionPage",
  "name": "{{ category.name }} — TwoComms",
  "description": "Категорія {{ category.name|lower }} з авторськими принтами від TwoComms."
}
```

**Проблемы:**
1. `description` шаблонный — одинаковый формат для всех категорий
2. Нет `@id` — Google не может связать CollectionPage с другими сущностями
3. Нет `publisher` ссылки на Organization
4. `ItemList` ограничен первыми 20 товарами (`|slice:":20"`), но Google показывает до 100

**Рекомендация:** Добавить `@id`, `publisher`, уникальный `description` из Category model.

---

### 1.4 OG/Twitter tags на категориях

```django
og:title — "{{ category.name }} — TwoComms"  ← слишком коротко
og:description — "{{ category.name }} з авторськими принтами від TwoComms. Стріт & мілітарі одяг."
og:image — {{ category.cover.url }}  ← ✅ хорошо, но проверить что cover есть у всех
```

**Проблема:** OG title не содержит "купити" — при шейринге в соцсетях нет призыва к действию.

---

## ЧАСТЬ 2: Индексация вариантов — цвет, размер, посадка

### 2.1 Архитектура variant URL (Phase 7)

| URL паттерн | Пример | Canonical | В sitemap | Статус |
|---|---|---|---|---|
| Base product | `/product/eagle/` | Self | ✅ Да | ✅ Правильно |
| 1 segment — color | `/product/eagle/black/` | Self | ✅ Да | ✅ Правильно |
| 1 segment — size | `/product/eagle/m/` | Self | ✅ Да | ⚠️ Проблема (см. ниже) |
| 1 segment — fit | `/product/eagle/oversize/` | Self | ✅ Да | ✅ Правильно |
| 2 segments | `/product/eagle/black/m/` | → Base | ❌ Нет | ✅ Правильно |
| 3 segments | `/product/eagle/black/m/oversize/` | → Base | ❌ Нет | ✅ Правильно |

### 2.2 ⚠️ КРИТИЧЕСКАЯ ПРОБЛЕМА: Size variants в sitemap

**Файл:** `sitemaps.py:149-161`

Каждый размер (S, M, L, XL, XXL, XXXL) получает **собственный URL** в sitemap с **self-canonical**:
- `/product/eagle/s/` — self-canonical
- `/product/eagle/m/` — self-canonical
- `/product/eagle/l/` — self-canonical
- `/product/eagle/xl/` — self-canonical
- и т.д.

**Почему это ПЛОХО для SEO:**

1. **Thin content:** Страницы `/product/eagle/s/` и `/product/eagle/m/` имеют **идентичный контент**:
   - Одно и то же описание товара
   - Те же фотографии
   - Та же цена
   - Единственная разница — pre-selected radio button на размере

2. **Crawl budget waste:** ~65 товаров × ~6 размеров = **~390 лишних URL** в sitemap

3. **Каннибализация:** Google видит 6 self-canonical страниц с одинаковым контентом → не знает какую показывать → может понизить все

4. **Title отличается минимально:**
   - Base: `Купити Eagle — TwoComms`
   - Size variant: `Купити Eagle — розмір M — TwoComms`
   - Это не unique content, это просто suffix

**Что нужно исправить:**

```python
# sitemaps.py — УБРАТЬ size variants из sitemap:
# Оставить только color + fit variants
for cv in product.color_variants.all():
    if cv.slug:
        entries.append({'loc': f'{base_path}/{cv.slug}/', 'lastmod': lastmod})

# УБРАТЬ этот блок:
# try:
#     size_ctx = resolve_product_size_context(product)
#     for size in size_ctx.get('sizes', []):
#         ...
```

**А так же:** Изменить canonical для size-only URLs на base product:
```python
# variant_meta.py — size-only = NOT self-canonical
if inputs.segments_count == 1:
    if inputs.size_code and not inputs.color_name and not inputs.fit_label:
        canonical_path = inputs.base_path  # Size → base
        is_self_canonical = False
    else:
        canonical_path = inputs.current_path  # Color/Fit → self
        is_self_canonical = True
```

---

### 2.3 ✅ Color variants — реализовано правильно

Color variants (напр. `/product/eagle/black/`) — это **правильно** для индексации:
- Разные фотографии (другой цвет товара)
- Разный alt text
- Title содержит название цвета: `Купити Eagle — чорна — TwoComms`
- Product schema может (и должен!) содержать другой image URL
- **Уникальный визуальный контент = уникальная страница для Google**

**Рекомендации для усиления:**
1. Product schema на color variant должен иметь `image` = фото именно этого цвета (сейчас используется `product.display_image` — это default image!)
2. OG image также должен меняться на фото выбранного цвета
3. Alt text на hero image должен включать название цвета

---

### 2.4 ✅ Fit variants (classic/oversize) — реализовано хорошо

Fit variants (`/product/eagle/classic/`, `/product/eagle/oversize/`) — **правильная** индексация:

**Что уже хорошо:**
- Уникальный title: `Класична Eagle — купити в TwoComms`
- Уникальный description с fit-specific text
- Уникальный SEO-блок внизу страницы (`FIT_SEO_COPY` в `product_seo_landing.py:69-107`)
- Self-canonical (1 segment)
- В sitemap

**Рекомендации для усиления:**
1. Добавить `<h3>` с fit-specific заголовком в основной контент (не только в SEO landing block)
2. H1 сейчас: `{{ product.title }}` — одинаковый для base и fit. Для fit variant можно: `{{ product.title }} (Оверсайз)` или `{{ product.title }} — класична посадка`
3. Добавить cross-link между fit variants: «Також доступно в [оверсайз](/product/eagle/oversize/)»

---

### 2.5 Canonical strategy — таблица правильности

| Сценарий | Текущий canonical | Правильный | Статус |
|---|---|---|---|
| `/product/x/` | `/product/x/` | `/product/x/` | ✅ |
| `/product/x/black/` | `/product/x/black/` | `/product/x/black/` | ✅ |
| `/product/x/m/` | `/product/x/m/` | `/product/x/` | ❌ Нужно base |
| `/product/x/oversize/` | `/product/x/oversize/` | `/product/x/oversize/` | ✅ |
| `/product/x/black/m/` | `/product/x/` | `/product/x/` | ✅ |
| `/product/x/black/oversize/` | `/product/x/` | `/product/x/` | ✅ |
| `?size=M&color=123` | 301 → path URL | 301 → path URL | ✅ |

---

### 2.6 Product schema на variant pages

**Проблема (файл `seo_utils.py:590`):**
```python
"url": _build_absolute_url(f"product/{product.slug}/")  # Всегда base!
```

На `/product/eagle/black/` schema.url = `https://twocomms.shop/product/eagle/` — НЕ variant URL.

**Конфликт:** canonical = self (`/product/eagle/black/`), schema.url = base (`/product/eagle/`).

Google видит: «страница говорит что она canonical, но Product entity ссылается на другую страницу».

**Что делать:** Передавать `canonical_path` из view в `generate_product_schema()` и использовать его как `url`.

---

## ЧАСТЬ 3: Heading hierarchy на PDP

### 3.1 Текущая структура H1-H3 на product_detail.html

```
H1: {{ product.title }}          (строка 178)
  H2: Деталі                    (строка 328, если details_text)
  H2: Кому підійде              (строка 342, если target_audience)
  H2: [size guide title]        (строка 373)
  H2: Підбір розміру            (строка 446, fallback)
  H2: Схожі товари              (строка 527)
  H2: Нещодавно переглядали     (строка 565)
  H2: [product landing title]   (из product_seo_landing.html)
```

**Проблемы:**
1. H1 = просто `{{ product.title }}` — нет category keyword. Google не знает что это футболка/худі без разбора страницы
2. H2 «Деталі» — слишком generic. Лучше: «Деталі {product.title}»
3. H2 «Схожі товари» и «Нещодавно переглядали» — это навигационные блоки, не контентные. Можно оставить H2, но aria-label важнее
4. Нет H3 вообще в основном контенте — плоская иерархия

**Рекомендация для H1 на PDP:**
```django
<h1>{% if variant_page_title %}{{ variant_page_title }}
    {% else %}{{ product.title }}{% endif %}</h1>
```
Это сделает H1 на fit variants уникальным: `Класична Eagle — купити в TwoComms`

---

### 3.2 PDP — фейковый рейтинг (строка 183)

```html
<strong>4.9</strong> <span>(45 відгуків)</span>
```

Также на related products (строка 548):
```html
<span class="tc-related-rating">4.9</span>
```

**Это P0 — удалить немедленно.** Google Guidelines: «Do not... include fake reviews or misleading structured data.» Даже visible fake reviews без schema всё равно вводят в заблуждение.

**Замена:** Реальные trust signals:
```html
<span class="tc-trust-signal">
  <svg>✓</svg> Зроблено в Україні
</span>
<span class="tc-trust-signal">
  <svg>✓</svg> DTF-друк 50+ прань
</span>
```

---

## ЧАСТЬ 4: Нереализованные бусты — быстрые победы

### 4.1 Quick Wins (1-2 дня кодинга, большой эффект)

| # | Что | Почему бустит | Трудозатраты |
|---|---|---|---|
| QW1 | Убрать size variants из sitemap | -390 URL, -70% crawl waste | 15 мин |
| QW2 | Добавить seo_title + seo_h1 в Category model | Уникальные title/H1 на категориях | 1 час |
| QW3 | Убрать fake rating 4.9 с PDP + related | Убирает risk of manual action | 30 мин |
| QW4 | Product schema url → canonical URL | Устраняет conflicting signal | 30 мин |
| QW5 | Убрать inline Organization из base.html | Один Organization entity | 15 мин |
| QW6 | OG image на color variant = фото этого цвета | Лучший CTR из соцсетей | 1 час |
| QW7 | Cross-links между fit variants на PDP | Усиление internal linking | 30 мин |
| QW8 | Удалить meta keywords из всех шаблонов | Чистый HTML, нет шума | 30 мин |

### 4.2 Medium Wins (3-5 дней, ощутимый эффект)

| # | Что | Почему бустит | Трудозатраты |
|---|---|---|---|
| MW1 | Уникальные category descriptions (3 шт) | E-E-A-T, уникальный контент на ≤3 страницах | 2 часа копирайтинг |
| MW2 | Уникальные product descriptions (ТОП-20) | Убирает thin content с главных страниц | 3 часа копирайтинг |
| MW3 | FAQ per-category вместо per-product | Уникальные FAQ, меньше дублирования | 2 часа |
| MW4 | @graph JSON-LD вместо отдельных blocks | Явные entity connections | 3 часа разработка |
| MW5 | Color variant images в Product schema | Rich results с правильным фото | 2 часа разработка |
| MW6 | Breadcrumb на PDP с variant info | Показывает путь: Каталог > Футболки > Eagle > Чорний | 1 час |

### 4.3 Strategic Wins (1-2 недели, долгосрочный рост)

| # | Что | Почему бустит |
|---|---|---|
| SW1 | Реальная система отзывов (интеграция НП/Google Reviews API) | Легитимный AggregateRating в schema |
| SW2 | Color landing pages: `/catalog/tshirts/black/` (path, не query) | Indexable color+category combos |
| SW3 | Blog / Content hub с how-to guides | Topical authority, long-tail traffic |
| SW4 | City landing pages с уникальным контентом | Local SEO без doorway pattern |
| SW5 | Structured data testing pipeline (CI/CD) | Автоматическая проверка schema на каждый deploy |

---

## ЧАСТЬ 5: Общий чеклист правильности по страницам

### Категория: Футболки (`/catalog/tshirts/`)

| Элемент | Текущее | Правильное | Статус |
|---|---|---|---|
| Title | `Футболки — TwoComms` | `Купити футболки з принтом — TwoComms` | ❌ |
| Description | Шаблонный | Уникальный с ціною | ❌ |
| H1 | `Футболки` | `Футболки TwoComms з авторськими принтами` | ❌ |
| H2 | `Створи свій дизайн` (не для category) | `Свій принт на футболці` | ⚠️ |
| Canonical | `/catalog/tshirts/` | ✅ Правильно | ✅ |
| Robots | `index, follow, max-image-preview:large` | ✅ | ✅ |
| CollectionPage schema | Есть, шаблонный desc | Уникальный desc | ⚠️ |
| OG image | category.cover | ✅ Если cover есть | ✅ |
| Internal links to products | Через card links | ✅ | ✅ |
| Color filter noindex | `?color=black` → noindex | ✅ | ✅ |
| Pagination rel=prev/next | Есть | ✅ | ✅ |

### Категория: Худі (`/catalog/hoodie/`)

| Элемент | Статус | Комментарий |
|---|---|---|
| Title | ❌ | `Худі — TwoComms` — слишком коротко |
| H1 | ❌ | Просто `Худі` |
| Canonical | ✅ | Правильный |
| Schema | ⚠️ | Шаблонный description |

### Категория: Лонгсліви (`/catalog/long-sleeve/`)

| Элемент | Статус | Комментарий |
|---|---|---|
| Title | ❌ | `Лонгсліви — TwoComms` |
| H1 | ❌ | Просто `Лонгсліви` |
| Canonical | ✅ | Правильный |
| Schema | ⚠️ | Шаблонный description |

---

## ЧАСТЬ 6: Итоговый backlog по приоритетам

### P0 — Сделать СЕЙЧАС (риск penalty)
1. ❌ Убрать size variants из sitemap (`sitemaps.py:149-161`)
2. ❌ Размерные variant canonical → base product (`variant_meta.py`)
3. ❌ Удалить fake rating 4.9 с PDP (`product_detail.html:183, 548`)
4. ❌ Product schema url → canonical path (`seo_utils.py:590`)

### P1 — Сделать на этой неделе (конкурентное преимущество)
5. ❌ Добавить `seo_title`, `seo_h1`, `seo_description` в Category model
6. ❌ Написать уникальные title/H1/desc для 3 категорий
7. ❌ Убрать дублирование H2 "Створи свій дизайн" с категорий
8. ❌ Cross-links между fit variants на PDP
9. ❌ OG image = фото выбранного цвета на color variant pages
10. ❌ Убрать meta keywords из всех шаблонов

### P2 — Сделать в этом месяце (рост органики)
11. ⏳ Уникальные product descriptions для ТОП-20
12. ⏳ @graph JSON-LD
13. ⏳ Color variant images в Product schema
14. ⏳ FAQ per-category вместо per-product duplicates
15. ⏳ H1 на PDP = variant-aware title

### P3 — Стратегические инициативы (следующий квартал)
16. 📋 Реальная система отзывов
17. 📋 Color landing pages (path-based)
18. 📋 Blog / Content hub
19. 📋 Schema testing CI/CD pipeline
