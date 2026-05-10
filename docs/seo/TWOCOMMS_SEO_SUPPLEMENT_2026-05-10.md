# Дополнительный глубокий SEO-аудит TwoComms
## Дополнение к TWOCOMMS_ECOMMERCE_SEO_AUDIT_2026-05-10.md

Дата: 2026-05-10
Автор: Supplementary audit agent (Claude Opus 4.6)

---

## 1. Что упустил предыдущий аудит — критические находки

### P0-CRITICAL. Дублирование Product schema — два конфликтных JSON-LD блока

**Где:** `seo_tags.py:351-391` + `seo_tags.py:130-138`

Предыдущий аудит сказал: «Product schema не содержит aggregateRating». Это **неточно**.

В коде есть ДВА шаблонных тега:
- `{% product_schema product %}` — генерирует Product из `seo_utils.py` **БЕЗ** AggregateRating
- `{% product_rating_schema product 4.9 45 %}` — генерирует **ОТДЕЛЬНЫЙ** Product schema **С** AggregateRating

Тег `product_rating_schema` (строка 352) создаёт полноценный `@type: Product` с `aggregateRating: {ratingValue: 4.9, reviewCount: 45}`. Даже если PDP сейчас вызывает только `{% product_schema product %}`, сам тег доступен и потенциально опасен.

**Почему это хуже, чем думал предыдущий аудит:**
- Если тег используется — Google получает **ДВА** Product JSON-LD на одной странице с разными данными
- Один Product schema содержит shipping/return/offer details, другой — упрощённый с фейковым рейтингом
- Google может выбрать любой из них, и «фейковый» может попасть в rich results

**Что делать:**
- Удалить `product_rating_schema` полностью из `seo_tags.py`
- Если рейтинг реальный — добавить AggregateRating в основной `generate_product_schema()` в `seo_utils.py`
- Проверить на production, вызывается ли `product_rating_schema` через grep rendered HTML

---

### P0-CRITICAL. Organization schema без @id в base.html — конфликт entity graph

**Где:** `base.html:677-701` vs `seo_utils.py:772-804`

Предыдущий аудит заметил «два Organization блока», но не раскрыл **корневую причину**:

| Свойство | base.html (inline) | seo_utils.py (programmatic) |
|---|---|---|
| `@id` | **ОТСУТСТВУЕТ** | `https://twocomms.shop/#organization` |
| `telephone` | Отсутствует | `+380966543212` |
| `description` | «Магазин стріт & мілітарі одягу...» | «...український streetwear / military-adjacent бренд...» |
| `foundingDate` | `2024` | Отсутствует |
| `contactType` | `customer service` | `customer support` |

**Почему это критично:**
- Без `@id` Google **не может** понять, что это одна и та же сущность
- Разные `description`, разные `contactType`, наличие/отсутствие `telephone` — сигнал конфликта
- Google Knowledge Graph может создать **два** отдельных entity вместо одного

**Что делать:**
- Удалить inline Organization из `base.html:677-701`
- Использовать ТОЛЬКО `{% organization_schema %}` тег (который берёт данные из `seo_utils.py`)
- Добавить `foundingDate: "2024"` в `generate_organization_schema()`

---

### P0-CRITICAL. LocalBusiness с placeholder телефоном доступен для вызова

**Где:** `seo_tags.py:326-348`

```python
"telephone": "+380XXXXXXXXX",  # <-- PLACEHOLDER!
"openingHours": "Mo-Su 00:00-23:59",  # <-- 24/7? Нереально для маленького бренда
```

Предыдущий аудит упомянул это как P2. Это **P0** — если кто-то вызовет `{% local_business_schema %}` в любом шаблоне, Google получит:
- Фейковый телефон, нарушающий structured data guidelines
- Нереалистичные часы работы
- Тип LocalBusiness для онлайн-магазина без физической точки

**Что делать:**
- Удалить `local_business_schema` из `seo_tags.py` полностью
- ИЛИ заменить данные реальными (но только если есть физический магазин)

---

## 2. Тонкий/дублированный контент — то, что аудит пропустил

### P1. Автогенерированный SEO-контент — фабрика thin content

**Где:** `product_seo_autofill.py`

Предыдущий аудит НЕ анализировал этот файл. `autofill_product()` генерирует для КАЖДОГО товара:

```python
seo_title:       "Купити {title} ({nom}) — TwoComms"
seo_description: "{title} — авторський {nom} TwoComms з мілітарним ДНК..."
short_description: "{title} — авторський {nom} TwoComms у мілітарно-streetwear ДНК..."
full_description:  "<p>{title} — авторський {nom} TwoComms..."
```

**Проблема:** 65 товаров получают ОДИНАКОВЫЙ шаблон с единственной разницей — `{title}`. Для Google это:
- Thin content — одинаковая структура, минимальная вариация
- Шаблонный контент, который не отвечает на уникальный поисковый интент
- Снижает crawl quality всего домена

**Что делать:**
- Для ТОП-20 товаров по трафику — написать уникальные description вручную
- Для остальных — хотя бы добавить в шаблон переменные: цвет, материал, плотность, принт
- Убрать `seo_keywords` из autofill (Google не использует meta keywords)

### P1. Идентичные FAQ на всех товарах — 5 одинаковых вопросов

**Где:** `product_seo_autofill.py:168-204`

Все 65 товаров получают ТОЧНО ОДНИ И ТЕ ЖЕ 5 FAQ:
1. «Як обрати розмір {nom}?»
2. «Чи можна прати {nom_acc} в машинці?»
3. «Скільки триває доставка?»
4. «Як повернути або обміняти товар?»
5. «Чи можна замовити з власним принтом?»

**Почему это проблема:**
- Google FAQPage rich results guidelines **явно предупреждают** против одинаковых FAQ на множестве страниц
- Это может привести к **manual action** или потере FAQ rich results для ВСЕГО сайта
- FAQ schema на 65+ страницах с идентичным контентом = spam signal

**Что делать:**
- Оставить FAQ schema ТОЛЬКО на support pages (где FAQ уникальный)
- Для товаров — либо писать уникальные FAQ, либо убрать FAQPage schema
- Оставить FAQ видимыми (полезно для UX), но убрать JSON-LD markup

### P1. City chips — все ведут на одну URL (doorway pattern)

**Где:** `product_seo_landing.py:340-345`

```python
city_url = _category_url(cat_slug)  # Одна URL для всех!
for city in CITY_KEYWORDS[:4]:
    items.append({
        "label": f"Купити {acc} {city}",
        "url": city_url,  # ВСЕ ведут на /catalog/tshirts/
    })
```

4 чипа с текстом «Купити футболку Київ», «Купити футболку Харків», «Купити футболку Львів», «Купити футболку Одеса» — все ведут на `/catalog/tshirts/`.

**Почему это проблема:**
- Google Webmaster Guidelines: «Doorway pages are created to rank for similar search queries... each page funnels users to the same destination»
- Множественные anchor-тексты с городами, ведущие на одну URL = манипуляция
- Предыдущий аудит упомянул это, но не показал **конкретный код** и масштаб (4 города × 65 товаров = 260 doorway-like ссылок)

**Что делать:**
- Удалить city chips полностью
- ИЛИ создать реальные city landing pages с уникальным контентом (сроки доставки, отделения НП и т.д.)

---

## 3. Внутренняя перелинковка — потерянный link equity

### P1. Ссылки на noindex-страницы из SEO-блоков

**Где:** `general_catalog_seo.py:67-82`

```python
{"label": "Купити худі ЗСУ", "url": "/catalog/hoodie/?color=black"},  # noindex!
{"label": "Тризуб футболка", "url": "/catalog/tshirts/?color=black"},  # noindex!
{"label": "Кайот худі", "url": "/catalog/hoodie/?color=coyote"},  # noindex!
```

Каталог `/catalog/` содержит curated top queries, которые ведут на URL с `?color=...`. Но `?color=` filter pages имеют `noindex, follow`!

**Почему это проблема:**
- Link equity с главной категории уходит на noindex страницы — по сути теряется
- Внутренние ссылки на noindex = сигнал Google, что сайт сам не уверен, какие страницы важны

**Что делать:**
- Либо создать indexable landing pages для популярных цветовых комбинаций (как path-URL, не query)
- Либо перенаправить эти chips на чистые category URL без параметров

### P2. Отсутствие cross-linking между product → support pages

Предыдущий аудит рекомендовал добавить, но не показал, где именно и как. Конкретный план:

| Откуда | Куда | Anchor text | Где в коде |
|---|---|---|---|
| PDP (delivery tab) | `/delivery/` | «Детальніше про доставку» | `product_detail.html` delivery section |
| PDP (size selector) | `/rozmirna-sitka/` | «Розмірна сітка» | рядом с size buttons |
| PDP (care tab) | `/doglyad-za-odyagom/` | «Повний догляд» | care instructions section |
| Category intro | `/custom-print/` | «Замовити зі своїм принтом» | category SEO blocks |
| Support pages | `/catalog/{category}/` | «Переглянути {category}» | support_content.py |

---

## 4. Structured Data — недоработки entity graph

### P1. Отсутствие @graph для связывания entities

Сейчас каждый JSON-LD — отдельный `<script>` блок без связей:
- Organization → отдельно
- WebSite → отдельно
- Product → отдельно
- BreadcrumbList → отдельно
- FAQPage → отдельно

**Что теряется:**
- Google не знает, что Product.brand → Organization — тот же entity
- Product.seller → Organization — другой блок, нет `@id` ссылки
- WebSite.publisher → Organization — не связан

**Как исправить (один объединённый @graph на PDP):**
```json
{
  "@context": "https://schema.org",
  "@graph": [
    {"@type": "Organization", "@id": "https://twocomms.shop/#organization", ...},
    {"@type": "WebSite", "@id": "https://twocomms.shop/#website", "publisher": {"@id": "https://twocomms.shop/#organization"}},
    {"@type": "BreadcrumbList", ...},
    {"@type": "Product", "brand": {"@id": "https://twocomms.shop/#organization"}, ...}
  ]
}
```

### P2. Product schema url не меняется на variant pages

Предыдущий аудит отметил это, но не показал код. Вот он:

`seo_utils.py:590`:
```python
"url": _build_absolute_url(f"product/{product.slug}/"),  # Всегда base URL!
```

Даже на `/product/clasic-tshort/black/` (self-canonical) schema.url = `/product/clasic-tshort/`. Это conflicting signal:
- Canonical: self (variant URL)
- Schema URL: base product URL
- Google не знает, какой URL canonical

---

## 5. Crawl Budget — 418 variant URLs

### P1. Размерные variant pages — thin content с раздутым crawl budget

**Факт:** 418 variant URL в sitemap. Из них:
- ~65 × 6 sizes = ~390 size variants (типа `/product/x/s/`, `/product/x/m/`)
- ~28 color variants
- Несколько fit variants

**Проблема с size variants:**
- Контент на `/product/x/s/` и `/product/x/m/` ИДЕНТИЧЕН, кроме pre-selected size
- Title может отличаться: «Купити X — розмір S — TwoComms» vs «...розмір M...»
- Description тоже шаблонная с size suffix
- Визуально — та же страница, тот же товар

**Рекомендация:**
- Убрать size variants из sitemap (оставить color и fit)
- Это сократит sitemap с 418 до ~50-80 URL
- Оставить size pages доступными, но с canonical на base product
- Экономия crawl budget: ~340 URL × ~2 crawls/week = 680 меньше crawl requests

---

## 6. IndexNow — неиспользованное преимущество

### P2. IndexNow настроен, но не упомянут в аудите

**Где:** `services/indexnow.py`

IndexNow полностью реализован:
- Batch submission до 100 URL
- Retry logic для 5xx ошибок
- Автоматический submit при product/category save (через signals)

**Что проверить:**
- Настроен ли `INDEXNOW_KEY` в production settings
- Работает ли `/INDEXNOW_KEY.txt` endpoint
- Логируются ли submissions (проверить production logs)

**Что дополнить:**
- При массовом обновлении цен — batch IndexNow submit
- При удалении товара — submit updated sitemap URL
- Мониторинг: отслеживать `IndexNow accepted X/Y URLs` в логах

---

## 7. E-E-A-T сигналы — что чеклист рекомендует для e-commerce

На основе загруженного on-page SEO чеклиста (15 категорий, 80+ пунктов):

### Что уже есть ✅
- Title tags, meta descriptions ✅
- Canonical URLs ✅
- OG/Twitter tags ✅
- Breadcrumbs ✅
- Product schema ✅
- FAQ schema ✅
- Responsive layout ✅
- Skip-to-content link ✅
- Lazy loading images ✅
- Semantic HTML5 ✅

### Что отсутствует и нужно добавить ❌

| Пункт чеклиста | Статус | Приоритет | Где добавить |
|---|---|---|---|
| «Last updated» дата на товарах | ❌ Нет | P2 | PDP — показывать updated_at |
| Контактный телефон видимый | ❌ Только в footer? | P2 | Header / PDP near buy button |
| Back-to-top кнопка | ❌ Нет | P3 | base.html — JS scroll button |
| Trust signals near CTA | ⚠️ Фейковый рейтинг | P0 | Заменить: «Виробництво UA», «DTF-друк», «14 днів обмін» |
| Business hours display | ❌ Нет | P3 | Footer / contacts page |
| Physical address (если есть) | ❌ Нет | P3 | Contacts page + schema |
| Реальные testimonials | ❌ Нет | P2 | Интегрировать отзывы из НП/Google |
| Service area/coverage | ⚠️ Частично | P3 | Delivery page — карта покрытия |
| Table of contents (на длинных страницах) | ❌ Нет | P3 | Support pages with jump-links |
| Color contrast verification | ❌ Не проверено | P2 | Lighthouse accessibility audit |
| Touch targets 48x48 minimum | ❌ Не проверено | P2 | Mobile variant selectors, cart buttons |
| Body text ≥16px | ⚠️ Не проверено | P3 | CSS verification |
| Focus indicators on forms | ❌ Не проверено | P2 | Cart, checkout, search input |
| Descriptive link text | ⚠️ City chips = плохие | P1 | Заменить generic на descriptive |

---

## 8. Адаптация on-page SEO чеклиста для e-commerce TwoComms

Чеклист изначально для service pages. Вот e-commerce адаптация:

### Категория 4: «Answer the query, fast»
- **Primary keyword в первых 100 словах** — На category pages intro text начинается с общего «Купити...». Нужно: включить category keyword + «купити» + бренд в первое предложение
- **Direct answer в 2-4 предложениях** — На PDP нет короткого summary above the fold. Добавить: 1-2 предложения с ключевыми характеристиками (материал, принт, цена) сразу под H1
- **FAQ schema** — Есть, но templated. Исправить: уникальные FAQ per product

### Категория 6: «Every image is a ranking signal»
- **Alt text** — Autofill: `"{title} — {nom} TwoComms, авторський принт, DTF-друк"` — слишком шаблонный. Нужно: описывать КОНКРЕТНО что на изображении (цвет, принт, ракурс)
- **Filenames** — Не проверены. Если файлы = `IMG_20240312.jpg` вместо `twocomms-hoodie-black-oversize.jpg`, это потерянный ranking signal
- **WebP** — Optimizer поддерживает WebP, но проверить production: `<picture>` с WebP source есть в `optimized_image.html`, но пользовательские uploaded images могут не иметь WebP fallback
- **Responsive srcset** — Есть для static images, но product images из admin — проверить

### Категория 9: «Schema Markup — JSON-LD in head»
Чеклист рекомендует: Article, LocalBusiness, Service, FAQ, BreadcrumbList, Organization, Author/Person

Для e-commerce замена:
- ~~Article~~ → **Product** ✅
- ~~LocalBusiness~~ → **Organization** ✅ (но дублируется)
- **Service** → для Custom Print ✅
- **FAQ** ✅ (но templated)
- **BreadcrumbList** ✅
- **Organization** ✅ (но без @id в base.html)
- ~~Author/Person~~ → не нужно для e-commerce

Дополнительно нужно:
- **CollectionPage + ItemList** — есть на categories ✅
- **WebSite + SearchAction** — есть ✅
- **MerchantReturnPolicy** — есть внутри Product ✅
- **OfferShippingDetails** — есть ✅

---

## 9. Обновлённый backlog (дополнение к основному аудиту)

| # | Приоритет | Задача | Файл | Проверка |
|---|---|---|---|---|
| S1 | P0 | Удалить `product_rating_schema` из seo_tags.py | `seo_tags.py:351-391` | grep production HTML на второй Product JSON-LD |
| S2 | P0 | Удалить inline Organization из base.html | `base.html:677-701` | Один Organization JSON-LD на странице |
| S3 | P0 | Удалить `local_business_schema` или заменить данные | `seo_tags.py:326-348` | Нет placeholder phone в HTML |
| S4 | P1 | Уникализировать product descriptions (ТОП-20) | `product_seo_autofill.py` | Минимум 20 уникальных description |
| S5 | P1 | Убрать FAQPage schema с PDP (оставить visible FAQ) | `product_detail.html` + `seo_tags.py` | Нет FAQPage JSON-LD на PDP |
| S6 | P1 | Удалить city chips из product landing | `product_seo_landing.py:340-345` | Нет city doorway ссылок |
| S7 | P1 | Исправить internal links на noindex URLs | `general_catalog_seo.py:67-82` | Все curated links → indexable URLs |
| S8 | P1 | Убрать size variants из sitemap | `sitemaps.py:149-161` | Sitemap variants < 100 |
| S9 | P1 | Добавить @id в Product schema | `seo_utils.py:590` | Product.url = canonical URL |
| S10 | P2 | Объединить schemas в @graph | `seo_utils.py` + `seo_tags.py` | Один @graph block per page |
| S11 | P2 | Проверить IndexNow в production | `services/indexnow.py` | Логи показывают успешные submits |
| S12 | P2 | Добавить updated_at на PDP | `product_detail.html` | Видимая дата обновления |
| S13 | P2 | Уникализировать alt text | `product_seo_autofill.py:91-96` | Alt описывает конкретное изображение |
| S14 | P2 | Trust signals near buy button | `product_detail.html` | Реальные badges вместо fake rating |
| S15 | P3 | Touch targets / contrast / focus audit | CSS + templates | Lighthouse accessibility ≥ 90 |

---

## 10. Что предыдущий аудит сделал хорошо

Для полноты картины — предыдущий аудит корректно идентифицировал:

- ✅ Template comments leak ({# ... #}) — P0
- ✅ Fake rating visible on UI — P0 (но не нашёл второй schema)
- ✅ SEO-visible text «ключові слова» — P0
- ✅ Category titles слишком короткие — P1
- ✅ Parameter duplicates (/catalog/?q=) — P1
- ✅ Image sitemap gaps (64 vs 65) — P1
- ✅ Meta keywords removal — P1
- ✅ Robots.txt dual source — P1
- ✅ Merchant feed GTIN/custom labels — P2
- ✅ Pagination rel=prev/next — реализовано (аудит не упомянул, но это есть в `catalog.html:34`)

---

## 11. Рекомендуемая очередность (дополнение к основному аудиту)

### Перед Этапом 1 основного аудита (техническая очистка):
1. Удалить `product_rating_schema` из seo_tags.py
2. Удалить inline Organization из base.html (оставить только `{% organization_schema %}`)
3. Удалить `local_business_schema` или убрать placeholder данные

### Параллельно с Этапом 2 (entity correctness):
4. Убрать size variants из sitemap (сократить с 418 до ~80)
5. Исправить Product schema url на variant pages
6. Убрать FAQPage schema с PDP (оставить FAQ visible)

### Параллельно с Этапом 3 (контент):
7. Уникализировать ТОП-20 product descriptions
8. Удалить city chips
9. Исправить curated links на noindex URL

### Новый Этап 5: Trust & E-E-A-T:
10. Trust signals near buy button
11. Visible updated_at на товарах
12. Контактный телефон в header
13. Accessibility audit (touch targets, contrast, focus)
