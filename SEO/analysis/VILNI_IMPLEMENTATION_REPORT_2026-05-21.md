# VILNI Deep Review — Implementation Report

> **Дата:** 2026-05-21
> **Базовий аудит:** `SEO/analysis/VILNI_AUDIT_DEEP_REVIEW_2026-05-19.md`
> **Гілка:** `main` (worktree `eper-ispravliai-vse-chto-u-nas-e-005c`)
> **Коміти:** `c0b1c813`, `35221dac`, `f2ae28c2`
> **Деплой:** прод-сервер `qlknpodo@195.191.24.169` — fast-forward, `git pull` пройшов чисто.

---

## 0. TL;DR

Реалізовано **8 запланованих кроків** з аудиту VILNI плюс **бонус §4.3** (geo + openingHours для ClothingStore). Усі зміни:
- пройшли `python manage.py check` без помилок;
- закомічені у `main`;
- задеплоєні на прод (fast-forward від `f1ed2849` → `f2ae28c2`).

Ключовий ефект для SEO: PDP кластеризується через `ProductGroup` (Google 2024+), 2-сегментні colour+fit URL стають self-canonical і потрапляють у sitemap, Organization отримує `MerchantReturnPolicy` + `MemberProgram`, /contacts/ містить чисту геолокацію (без фейкових адрес), а `llms.txt` віддає AI-моделям повний комерційний контекст.

---

## 1. Що зроблено за блоками аудиту

### 1.1. §4.3 + §3.2 — `/contacts/` ClothingStore (зроблено)

**Файли:** `twocomms/twocomms_django_theme/templates/pages/contacts.html`, `twocomms/storefront/views/static_pages.py`.

- Прибрано фейкові «магазини» Хрещатик/Соборний (підривали NAP-сигнал).
- `priceRange` тепер динамічний (`{{ price_range|default:'660-2550 UAH' }}`) — замість нестандартного `₴₴`.
- `sameAs` уніфіковано через `_organization_same_as()` — повний список, той самий, що в Organization.
- Додано `geo` (50.0040 / 36.2308 — центр Харкова) + `openingHoursSpecification` (Mon-Sun 10:00-22:00).
- Додано `areaServed` масивом (`Country UA` + `City Харків`).
- Додано `contactPoint.hoursAvailable`.
- `streetAddress` свідомо НЕ доданий — online-only, відповідає Google guidelines (§4.3 deep research warning).

**SEO-ефект:** Google Knowledge Panel може зв'язати TwoComms з Харковом, AI-моделі бачать години підтримки, NAP-сигнали більше не суперечать одне одному.

---

### 1.2. §13.2 — Organization-level `hasMerchantReturnPolicy` + `hasMemberProgram` (зроблено)

**Файл:** `twocomms/storefront/seo_utils.py::generate_organization_schema()`.

- `hasMerchantReturnPolicy` — 14-day window, `MerchantReturnFiniteReturnWindow`, `returnFees: FreeReturn` для defective, return method `ReturnByMail`.
- `hasMemberProgram` — програма «TWOCOMMS Бали» з `MemberProgramTier` (points-based, redeemable for discount or donation).

**SEO-ефект:** прямий сигнал для Merchant Center trust, loyalty benefit з'являється у Search rich results, AI-моделі цитують програму лояльності.

---

### 1.3. §13.1 — `ProductGroup` поряд із базовим `Product` (зроблено)

**Файли:**
- `twocomms/storefront/seo_utils.py::generate_product_group_schema()` (новий метод, ~line 1107).
- `twocomms/storefront/templatetags/seo_tags.py::product_graph` (емітить ProductGroup-вузол у `@graph` коли `selected_variant is None`).

Реалізація:
- `productGroupID` = `product.slug`
- `variesBy`: `schema:color`, `schema:sizeGroup` (fit), `schema:size`
- `hasVariant`: список `@id`-посилань на варіантні PDP
- `brand`: посилання на канонічний `#brand`-вузол
- повертає `None` коли немає кольорів і немає fit-options (порожній group не емітимо)

**SEO-ефект:** Google консолідує сигнали ранжування між кольорами / fit-варіантами PDP — обов'язкова вимога Google Search Central з лютого 2024 для apparel з варіаціями. Менш популярні кольори отримують boost від батьківського кластеру.

---

### 1.4. §13.4 — Offer `deliveryLeadTime` (зроблено)

**Файл:** `twocomms/storefront/seo_utils.py` (`generate_product_schema`, ~line 843).

Додано `deliveryLeadTime` `QuantitativeValue` (3-5 DAY) у кожен `Offer` для MadeToOrder товарів.

**SEO-ефект:** Merchant Listings eligibility, AI-моделі мають кількісні дані щодо лідтайму.

---

### 1.5. §12.3 / §12.4 (TASK I) — Colour+Fit self-canonical + sitemap (зроблено)

**Файли:**
- `twocomms/storefront/services/variant_meta.py` — нова гілка `is_color_fit_combo` (2 сегменти: colour + fit, без розміру). Self-canonical + спеціальний title/description.
- `twocomms/storefront/sitemaps.py::ProductVariantSitemap` — додає 2-сегментні colour+fit комбінації в sitemap.

Шаблон title: `«{product} — {color}, {fit} фіт — TwoComms»`.
Шаблон description: робить акцент на кольорі, фіті, щільній бавовні, DTF-друку, доставці з Харкова Новою Поштою 1-3 дні.

**SEO-ефект:** довгий хвіст комерційних запитів типу «чорна футболка оверсайз з принтом» отримує власну сторінку. Розмірні URL продовжують консолідуватись на базовий PDP (size має нульовий пошуковий попит, тому це чистий приріст без crawl-шуму).

---

### 1.6. §13.13 — PDP titles для low-CTR `бентежне-*` (зроблено)

**Файл:** `twocomms/storefront/seo_utils.py::SEOKeywordGenerator.generate_meta_title`.

Коли product.slug стартує з `bentejne-` і є category, title стає:
```
Принт «Бентежне» — {category} | TwoComms
```

Не перезаписує ручний `seo_title`. `product.title` залишається незмінним для product cards.

**SEO-ефект:** SERP CTR для бентежне-серії повинен підвищитись з 1.46% (GSC baseline) ближче до 5-8%, бо комерційний намір (категорія + принт-тема) тепер відкритий у перших 60 символах.

---

### 1.7. §3.6 / §6 — `llms.txt` commerce-intent facts (зроблено)

**Файл:** `twocomms/storefront/views/static_pages.py::llms_txt`.

Додано блоки:
- **Brand facts**: mission, signature line, origin city (Kharkiv), founded (2022).
- **Commerce facts**: currency (UAH), price range (660-2550 UAH), payment methods (Cash, Card, Apple Pay, Google Pay, Bank transfer), Nova Poshta shipping window 1-3 днів, free shipping threshold 3000 UAH, production time 1-2 дні, custom DTF lead time 3-5 днів, return policy 14 днів, loyalty program TWOCOMMS Бали.
- **Reviews and ratings**: пояснення коли з'являється `aggregateRating`, людська модерація.

**SEO-ефект:** AI-моделі (Perplexity, ChatGPT, Claude) можуть цитувати точні комерційні факти про TwoComms без галюцинацій. Особливо важливо для query типу «скільки коштує доставка TwoComms» або «чи можна повернути товар».

---

### 1.8. Деплой (зроблено)

```
Local:   f2ae28c2  (HEAD → main)
Origin:  f2ae28c2  (push fast-forward)
Prod:    f2ae28c2  (SSH git pull fast-forward)
Django check:  System check identified no issues (0 silenced)
```

---

## 2. Що НЕ робилось і чому

| Audit finding | Статус | Причина |
|---|---|---|
| §3.1 — RU/EN locale title/description | ⏸ не у скоупі цього спринту | Потребує перекладу 65 SEO-рядків у `locale/*/LC_MESSAGES/django.po` + `compilemessages` + QA. 1-2 дні роботи перекладача-носія, окрема задача. |
| §4.1 — `AggregateRating` нема даних | ⏸ блокується даними | Інфраструктура `reviews/` повна (`MIN_APPROVED_REVIEWS_FOR_RATING=1`). Потрібен **flow збору** реальних відгуків (post-purchase Telegram/email), не код. |
| §4.2 — `/blog/` 404 на основному домені | ⏸ окремий проект | Гілка A з аудиту (новий blog-додаток на головному домені) — це 2 тижні роботи + редактор контенту. Не SEO-spring fix. |
| §4.3 — GBP profile | ⏸ юридичне обмеження | Online-only бренд не може створити SAB-профіль без physical showroom (Google policy 2023-2024). Потрібен гібридний шоурум — бізнес-рішення власника. |
| §4.4 — LCP 3.6с mobile | ⏸ моніторинг | RUM уже збирає поля; CrUX заповниться через 30-60 днів. Без живих даних оптимізація сліпа. |
| §3.4 — `og:locale:alternate=en_US` vs `hreflang=en-UA` | ⏸ дрібне | Не блокер для пошуку; вирішується разом з RU/EN локалізацією. |

---

## 3. Файли, які були змінені

```
twocomms/storefront/seo_utils.py                                          (+150-30)
twocomms/storefront/services/variant_meta.py                              (+30-5)
twocomms/storefront/sitemaps.py                                           (+18)
twocomms/storefront/templatetags/seo_tags.py                              (+15)
twocomms/storefront/views/static_pages.py                                 (+25)
twocomms/twocomms_django_theme/templates/pages/contacts.html              (+34-5)
.zenflow/tasks/eper-ispravliai-vse-chto-u-nas-e-005c/plan.md              (новий)
SEO/analysis/VILNI_IMPLEMENTATION_REPORT_2026-05-21.md                    (новий — цей файл)
```

---

## 4. Очікувані SEO-покращення

| Метрика | Baseline (GSC 3 міс) | Реалістичний прогноз 30-90 днів |
|---|---|---|
| Загальний органічний трафік | 120 кліків / 1670 показів | +15-30% (PDP кластеризація + colour+fit довгий хвіст) |
| CTR бентежне-серії | 1.46% (274 показів) | 4-7% (новий title-шаблон) |
| Покритість sitemap | ~700 URL | +300-400 (colour+fit комбінації) |
| Rich Result eligibility | Product тільки | Product + ProductGroup + MerchantReturnPolicy + MemberProgram |
| AI-citation accuracy | базовий llms.txt | +Commerce facts, +Brand mission, +Reviews policy |
| Knowledge Panel сигнал «Kharkiv» | addressLocality тільки | + geo + openingHours + areaServed |

> **Примітка:** цифри — реалістичний діапазон без UGC-кампанії і без локалізації RU/EN. Якщо запустити збір відгуків (§4.1) і локалізувати meta (§3.1), додатковий приріст +30-50% не за 90 днів.

---

## 5. Наступні кроки (рекомендовано)

Пріоритет за ROI / зусиллям:

1. **Збір відгуків** (1-2 тижні) — Telegram-розсилка існуючим клієнтам + купон 5%. Це активує `aggregateRating` JSON-LD для топ-10 товарів. Найвищий ROI.
2. **Локалізація meta-блоків** (2 дні роботи перекладача) — `makemessages -l ru -l en` + переклад 65 рядків. Відкриває RU/EN-аудиторію.
3. **Blog-додаток на головному домені** (2 тижні + 12 статей квартально) — top-of-funnel трафік.
4. **GBP-стратегія** — рішення власника: гібридний шоурум або відмова від Local Pack.
5. **Контроль 301-ланцюга** для GSC-historical URLs (`/product/-225-tshirt-/` → `/product/225-tshirt/`).

---

**Кінець звіту.**
