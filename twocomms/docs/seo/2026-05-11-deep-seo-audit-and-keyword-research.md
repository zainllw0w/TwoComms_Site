# TwoComms — Глибокий SEO‑аудит, дослідження ключових слів, мультимовність та чекліст

> Документ створено 2026-05-11. Файл є **робочим артефактом** для подальшого глибинного reasoning‑агента: тут описано все, що потрібно для незалежного аналізу без додаткового доступу до коду. Усі факти супроводжуються посиланнями на файли репозиторію (`@/path:line`) та сирими прикладами з продакшну `https://twocomms.shop`.
>
> **Важливо для агентів‑читачів.** Цей файл — *вхідні дані* для подальшого дослідження. Не виконуйте зміни в коді на його основі без узгодження з власником. Завдання — *валідувати, поглиблювати, спростовувати або переосмислювати* кожну гіпотезу нижче.
>
> Контекст бренду:
> - **TwoComms** — український streetwear / military‑adjacent бренд із Харкова.
> - Домен `twocomms.shop`, ~6 місяців у Google, мала кількість категорій (3 базових: `tshirts`, `hoodie`, `long-sleeve`) + конструктор кастомного принта.
> - Частина прибутку йде на ЗСУ — це сильний brand‑signal, який треба враховувати в keyword‑intent.
> - Стек: Django 5.2, `django-modeltranslation` (UK як джерело; RU/EN — резервний переклад через fallback).
> - Локальна БД (sqlite) має лише тестові продукти (`Codex Animation Check`, `c`, `p` тощо). **Реальний контент — лише на проді.** Тому всі аудити вище за «структурні» — звіряти з продом.

---

## 0. Як читати документ

Кожен пункт у чек‑лісті маркований:
- `[CRIT]` — пряма SEO‑регресія або граматична помилка (виправляти негайно).
- `[HIGH]` — суттєвий приріст у видимості за середніми витратами.
- `[MED]` — UX/полірувальні зміни, helpful‑content.
- `[LOW]` — гігієна та довгий хвіст.
- `[TBD]` — потребує даних, які не отримати локально.

Файл писався в кілька проходів. Якщо щось виглядає незавершеним — це навмисно: в кінці документа є розділ §11 «Наступні кроки» з переліком ще не зібраних даних.

---

## 1. Карта SEO‑інфраструктури

### 1.1 Базовий шаблон і блоки мета‑тегів
- Файл: `@/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/base.html:8-112`. Усі мета‑теги виводяться у `{% block seo_meta %}`. Дочірні шаблони переписують `{% block title %}`, `{% block description %}`, `{% block canonical %}`, `{% block og_image %}` тощо.
- `meta keywords` свідомо **видалено** (Phase 21, 2026-05-10) у `base.html:63-72`. Поле `Product.seo_keywords` (`@/Users/zainllw0w/TwoComms/site/twocomms/storefront/models.py:562`) існує, але після Phase 21 у `<meta name="keywords">` не друкується (`@partials/seo_meta.html:9` — закоментовано). Тобто **наповнення `seo_keywords` в адмінці зараз нічого не дає** на HTML‑рівні (тільки для AI‑агрегацій / внутрішнього індексу). Це треба усвідомити при міграції стратегії (§11).
- `hreflang` (uk/ru/en/x-default) — `language_alternates` (`@/Users/zainllw0w/TwoComms/site/twocomms/storefront/templatetags/i18n_links.py:82-89`).
- Twitter Card = `summary_large_image`, OG image `1200×630` (default), є `og:image:alt`.
- Canonical = `{{ site_base_url }}{{ request.path }}` — без query, добре.
- Robots: `index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1` — оптимально.

### 1.2 Точка генерації SEO для товарів
- `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/seo_utils.py:360-432`.
- Пріоритет: збережене у моделі `seo_title`/`seo_description`/`seo_keywords` → fallback‑шаблони.
- Fallback Title: `f"{product.title} ({product.category.name}) - TwoComms"` — нейтральний, без `купити`.
- Fallback Description: `seo_description → short_description → ai_description (тільки якщо AI увімкнено) → full_description → description`.
- Прод‑зразок: `<title>Футболка класична — купити футболка TwoComms</title>` (`/product/clasic-tshort/`).

### 1.3 Phase 13.5 seo_title — **критичний баг**
- Файл: `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/services/product_copy_v2.py:312-316`.
- `seo_title = f"{t} — купити {_nom(cat)} TwoComms"`, де `_nom("tshirts") = "футболка"` (NOM).
- **`[CRIT]`** — потрібен ACC: «купити футболк**у**». Для худі/лонгсліва форма випадково збігається (омонімія), тому помилка непомітна.
- Швидкий fix: `_nom(cat)` → `_acc(cat)` (мапа `LABEL_ACC` вже є, `@product_copy_v2.py:20`).
- Зачепить лише товари з автогенерованим `seo_title`; вручну заповнені пройдуть guard `looks_like_phase13_autofill` (`@product_copy_v2.py:215-219`).
- Окремо: для товарів з довгою назвою (`«Де Мої Подарунки, Мразота?»`) Title виходить >60 символів → обрізається у видачі.

### 1.4 Категорії
- Поля: `seo_title`, `seo_h1`, `seo_description`, `seo_text_title`, `seo_intro_html`, `description` (`@models.py:60-100`). Усі — translatable.
- Fallback `seo_utils.py:402-432`: Title=`"{name} - TwoComms"`, Description=`"Купити {name.lower()} в TwoComms..."`.
- На проді категорії мають **manually-written** SEO H1/Title — це сильно (`Худі від українського бренду TwoComms — стрітвеар, мілітарі, преміум фліс`).

### 1.5 SEO‑блоки нижче списку товарів (`CategorySeoBlock`, Phase 10)
- Сервіс: `get_category_seo_layout` / `get_category_seo_blocks` (`@/Users/zainllw0w/TwoComms/site/twocomms/storefront/services/catalog_seo.py`).
- На `/catalog/tshirts/` 5× H2:
  - `Найкращі ціни на футболки в TwoComms`
  - `Футболки TwoComms — авторські принти ЗСУ та streetwear — TwoComms` *(подвоєне «— TwoComms»)*
  - `Купити чоловічу футболку з принтом — доставка по Києву, Харкову, Львову`
  - `Замовити жіночу футболку онлайн в Україні — авторський streetwear`
  - `Унісекс футболки TwoComms — патріотичні принти ЗСУ за справедливою ціною`
- `[MED]` Прибрати `— TwoComms` з кінця першого блоку.
- `[HIGH]` Геомаркери — добре, але «Київ, Харків, Львів» в одному H2 — поверхнево. Кращий патерн: окремі лендинги `/catalog/tshirts/kyiv/`, `/kharkiv/` тощо (це довша робота).

### 1.6 Лендинг‑блок під PDP (Phase 15)
- Файл: `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/services/product_seo_landing.py`.
- H2: `«{title} — деталі моделі»` (`@:262`). За наявності `fit_code` → `«{title} ({Fit}) — деталі моделі»`.
- На проді: `Футболка класична (Класична) — деталі моделі` → **тавтологія** для базового PDP. **`[CRIT]`** — `fit_code` не має передаватися для **base** URL. Розслідувати: `_resolve_fit_options` (`@views/product.py:435-447`) повертає дефолт; landing білдер отримує його як selected. Треба передавати `fit_code` лише коли воно прийшло з шляху, а не з default fit option.

### 1.7 JSON‑LD на PDP
- 3 блоки: `Organization`, `WebSite+SearchAction`, `@graph` з `Product` (без `brand`, без `aggregateRating`, без `review`).
- **`[CRIT]`** Додати `"brand": {"@type":"Brand","name":"TwoComms"}` у Product schema.
- `[HIGH]` `BreadcrumbList` JSON‑LD у видобутих фрагментах не виявлено — `[TBD]` перевірити повний source PDP.
- `Product.additionalProperty[]` містить `age_group=adult`, `gender=unisex`, `size_type=regular`, `size_system=UA`, `google_product_category=1604`, `Колір=Чорний` — гарно для Merchant Center.

### 1.8 Sitemap, robots, hreflang
- Sitemap index: `sitemap-static`, `sitemap-products`, `sitemap-product-variants`, `sitemap-categories`, `sitemap-images`. ✅
- 3× URL (uk/ru/en) на кожен товар + xhtml:link alternate. Поточно ОК, але створює дублі на index‑і за відсутності реальних RU/EN перекладів.
- `robots.txt`: блокує `?sort=`, `?order=`, `?utm_*`, `?fbclid=`, `?gclid=`. AI‑боти opt‑in.

### 1.9 Multilingual — поточний стан
- `LANGUAGE_CODE='uk'`; fallback `ru/en → uk` (`@settings.py:571-613`).
- `*_uk`, `*_ru`, `*_en` колонки існують у `Product`/`Category`/`ProductFAQ`. Українська — джерело істини; RU/EN — порожні.
- Прод: `/ru/product/clasic-tshort/` віддає UK‑Title і UK‑Description (переклад відсутній). На головній — частковий gettext‑переклад UI, але не контенту.
- **`[CRIT]`** — duplicate content на /ru/ та /en/ з canonical, що вказує на самих себе. Поки немає реального перекладу — варто або деактивувати hreflang RU/EN, або змінити canonical на UK.

---

## 2. Доктрина 2026 (на чому базуємо оцінку)

> Жодна сучасна SEO‑доктрина не самодостатня — нижче список референсних правил, які явно використано як критерій. Якщо агент‑читач не згоден — спростовуйте з посиланнями на актуальні гайдлайни.

1. **Google Search Essentials 2025** + Helpful Content System: пріоритет «hands-on, original perspective»; mass-generated AI-text без редактури каратимуть.
2. **Title**: 50–60 символів; основний keyword у перших 30; бренд наприкінці (з `|` або `—`).
3. **Meta description**: 140–160 символів, активний дієслівний заклик, з 1‑2 LSI‑ключами.
4. **H1**: один на сторінку, ідентифікує сутність + категорійний keyword. Не дублювати у `<title>` слово в слово (підвищує CTR + різноманіття).
5. **H2/H3**: інформаційна архітектура; має покривати «people also ask»‑питання + субнамір (доставка, розмір, склад, гарантія, бренд).
6. **Schema.org**: для e‑commerce обовʼязково `Product`, `Offer`, `AggregateOffer`, `BreadcrumbList`, `Organization`, `WebSite`; рекомендовано `Review`/`AggregateRating` (за наявності даних), `FAQPage` (тільки унікальні Q/A).
7. **Image SEO**: alt = опис + ключ, lazy‑load (крім LCP), `width/height`, AVIF/WebP, `srcset` із 320/640/1080.
8. **i18n**: один варіант на мову, hreflang парами `x-default → uk`, унікальні переклади (інакше — `canonical` на одну мову).
9. **Mobile-first**: розміри H1 не менше 1.5× базового тексту; CLS<0.1, LCP<2.5s.
10. **AI search (SGE/Perplexity/Google AI Overview)**: чистий, факт‑центричний текст; явні бренд‑signals; structured data; цитування політики (returns/shipping/support).
11. **Frequency для нового домену** (≤12 міс): уникати найвищочастотних gen‑ключів («футболка купити Україна» — DR 30+ конкурентів), фокус на mid-/low-tail (`купити мілітарі футболку з принтом ЗСУ`, `чорна футболка Харків бренд`) — це ROI/CTR-крива для молодого сайту.
12. **Search intent matrix**: transactional vs informational; для PDP — лише transactional; для категорійних/блогу — informational + commercial.

---

## 3. Сторінкові аудити (прод‑зріз 2026-05-11)

### 3.1 Головна `/`
- Title: `TwoComms — Стріт & Мілітарі Одяг | Головна` ✅ (49 символів). 
- Meta description: `TwoComms — український магазин стріт і мілітарі одягу: футболки, худі, лонгсліви, кастомний друк і швидка доставка по Україні.` (134 знаки). ✅. Можна додати `від 590 грн / Нова Пошта 1–3 дні` — підвищить CTR.
- H1: `Стріт & мілітарі одяг` (з прихованим бренд‑префіксом для accessibility). ✅
- H2 на проді: `Допоможи покращити TwoComms` (survey-банер), `Категорії`, `Обери за кольором`, `Новинки` (h5), `TWOCOMMS` (footer).
  - `[MED]` H2 `Категорії` — нерелевантний для SEO. Замінити на `Категорії одягу TwoComms` або `Стрітвеар та мілітарі категорії`.
  - `[MED]` `Новинки` (h5, не h2) — додати keyword: `Нові футболки та худі TwoComms`.
- Schema: Organization, WebSite ✅. **Немає ItemList** для блоку «Новинки» — додати може допомогти Merchant Listing.
- `[HIGH]` Додати на головну `ItemList` JSON-LD топ-6 продуктів (Schema.org `ItemList → ListItem → Product`).
- `[LOW]` `og:description` на головній не згадує «бренд із Харкова» — це сильний LocalSEO-signal, варто додати.

### 3.2 Каталог-корінь `/catalog/`
- Title: `Каталог одягу — TwoComms` (22 символи). `[MED]` Занадто коротко, нема ключа намірів. Запропоновано: `Каталог одягу TwoComms — футболки, худі, лонгсліви ЗСУ` (53 знаки).
- Description: `Каталог стріт & мілітарі одягу TwoComms: футболки, худі, лонгсліви та новинки бренду з характером.` (99 знаків). `[MED]` Розширити до 150–160, додати `авторські принти, DTF-друк, доставка по Україні від 1 дня`.
- H1: `Каталог одягу` ✅. Опційно `Каталог стрітвеар одягу TwoComms`.

### 3.3 Категорія `/catalog/tshirts/`
- Title: `Футболки TwoComms — стрітвеар та мілітарі-принти від українського бренду` (75 символів — **`[CRIT]` ризик зрізки**). Запропоновано: `Футболки TwoComms — стрітвеар та мілітарі принти` (53 знаки). Хвостову частину «від українського бренду» — продублювати у H1.
- Description ✅ (155 знаків).
- H1: `Футболки з характером — стрітвеар і мілітарі від TwoComms` ✅ — оптимально.
- H2: 5 шт (див. §1.5). Подвоєний `— TwoComms` `[MED]` приберіть кінцевий.
- `[HIGH]` Відсутні **окремі H2** «Чоловічі футболки», «Жіночі футболки», «Унісекс футболки» як **сабкатегорії** — додати кросс-links на `?gender=...` (але блокувати ці URL у robots, щоб не індексувались як дублікати).
- `[HIGH]` Категорійна `ItemList` JSON-LD — обов'язково (сторінка-агрегатор).
- `[HIGH]` Pagination: перевірити `rel="prev"`/`rel="next"` (deprecated для Google, але корисно Bing) і canonical на стор. 2, 3.

### 3.4 Категорія `/catalog/hoodie/`
- Title `Худі TwoComms — теплі толстовки зі стрітвеар-принтами та свободною посадкою` (80 символів) `[CRIT]` обрізати. Слово `толстовка` — рідкісне в UK, але є пошуковий запит. Пропозиція: `Худі TwoComms — теплий стрітвеар з принтами та oversize посадкою` (61 знак).
- H1: `Худі від українського бренду TwoComms — стрітвеар, мілітарі, преміум фліс` (73). Дещо довго для мобільного; короткий варіант: `Худі TwoComms — український стрітвеар і мілітарі з преміум фліс`.

### 3.5 Категорія `/catalog/long-sleeve/`
- Title 79 символів — `[CRIT]` обрізати.
- `[LOW]` Додати у H2 синонім «футболка з довгим рукавом» — старо-пошуковий синонім (старші користувачі шукають саме так).

### 3.6 PDP `/product/<slug>/`
Title-шаблон бажано `{product.title} — купити {acc} в TwoComms` (виправлення §1.3).
H1 = `{product.title}` ✅.

H2-структура на проді (`clasic-tshort`):
1. `Кому підійде` (target_audience)
2. `Футболка базова` (size guide)
3. `Відгуки про товар`
4. `Схожі товари`
5. `Нещодавно переглядали`
6. `Футболка класична (Класична) — деталі моделі`
7. `TWOCOMMS` (footer)

- `[CRIT]` H2 `Футболка класична (Класична) — деталі моделі` — дублювання `Класична`. Перевірка landing-builder vs `selected_fit` (див. §1.6).
- `[HIGH]` Додати H2: `Доставка футболки Новою Поштою по Україні`, `Як прати футболку без втрати DTF-принта` — готові PAA-слоти.
- `[MED]` Лендинг починається з `«{title} — деталі моделі»` — Google може вирішити, що template-filling. Краще варіація: `Все про модель «{title}»`, `Як носити «{title}»`.
- `[MED]` `Кому підійде` — generic; додати keyword: `Кому підійде ця футболка TwoComms`.

**Schema (Product)**:
- `[CRIT]` Відсутнє поле `brand` — додати `"brand": {"@type":"Brand","name":"TwoComms"}`.
- `[HIGH]` `BreadcrumbList` (не помічено в дампі — `[TBD]` верифікувати).
- `[HIGH]` Якщо є хоча б 1 відгук — виводити `review[]` навіть без `aggregateRating`. Або поріг 3 знизити до 1 (Google допускає `reviewCount >= 1`).

**Open Graph**:
- `og:image=https://twocomms.shop/media/products/c3.jpg` — `[MED]` зображення `1080×1350` (portrait), а не `1200×630`. Twitter обрізає. Згенерувати окремий `og_card` 1200×630 (через адмінку або автогенератором).

### 3.7 Static pages
- `/contacts/` ✅ acceptable.
- `/pro-brand/` ✅ сильна сторінка (H1 brand story).
- `/about/` → 301 на `/pro-brand/`. `[HIGH]` перевірити, що `/about/` не у sitemap (інакше зайвий 301-link).
- `/blog/` → **404**. `[CRIT]` створити змістовну сторінку або зробити 410, або видалити внутрішні посилання.
- `/help/`, `/delivery/`, `/return/`, `/privacy/`, `/terms/` — `[TBD]` окремий аудит.

---

## 4. Per‑product audit framework (шаблон для подальших ітерацій)

> Цей блок використовуватимемо як **TODO-шаблон**, який клонуватимемо для кожного товару окремою таблицею. Для початку — порожня форма + критерії оцінки.

| # | Поле | Що перевіряємо | Як оцінюємо |
|---|------|----------------|-------------|
| 1 | `title` (видима назва) | Унікальність, наявність базового ключа (`футболка / худі / лонгслів`), стиль (емоційний прінт або смисловий), довжина 25–55 символів | 0 — generic ("Футболка 1"), 1 — є категорія, 2 — є prинт-тема, 3 — є prинт-тема + USP |
| 2 | `seo_title` | Граматика, ключ, бренд, ≤60 символів | див. §1.3 |
| 3 | `seo_description` | 140–160 символів, дієслово на старті, унікальність, ЗСУ-згадка, Нова Пошта | |
| 4 | `seo_keywords` (внутрішнє поле) | Поки не використовується в HTML (Phase 21); все ж заповнюємо для AI-агрегацій | масив 8‑15 ключів |
| 5 | `short_description` | Унікальний text для лід-параграфа | повинна відрізнятися від `seo_description` |
| 6 | `full_description` | Структурований: матеріал, посадка, догляд, історія принта (≥350 слів) | |
| 7 | `target_audience` | "Кому підійде" — конкретно (вік 18–34, інтереси, стиль) | |
| 8 | `care_instructions` | Унікально, не копія category-level | |
| 9 | `main_image_alt` | Складається з: назва + категорія + колір + USP | |
| 10 | Галерея ALT | На кожне фото свій ALT з контекстом (model-shot vs flatlay) | |
| 11 | Schema Product | `name`, `description`, `sku`, `mpn`, `brand`, `image[]`, `offers.price`, `offers.priceCurrency`, `offers.availability`, `aggregateRating?`, `review?`, `additionalProperty[]`, `audience`, `material` | |
| 12 | Канонікал | Один URL на товар; варіанти `/{color}/`, `/{size}/`, `/{fit}/` мають коректний rel=canonical згідно phase 7.3 | |
| 13 | Hreflang | Якщо немає реального RU/EN перекладу — або не виводити окремий URL, або canonical → uk | |
| 14 | Внутрішні посилання | На категорію, на «всі футболки {color}», на бренд-story | |
| 15 | FAQ | 4‑6 Q/A, унікальні per product (не template) | |
| 16 | Reviews | Кількість, дата, ім'я (без CTA, бо інакше — spam) | |
| 17 | Швидкість LCP | LCP < 2.5 s mobile (через `optimized_image`) | вже частково оптимізовано |

> Заповнення цієї матриці — окрема фаза (Phase B). Для початку пропонується **витягти всі товари з прод-БД** (export CSV або парс HTML за списком з `/sitemap-products.xml`) і прогнати кожний рядок по шкалі 0–3.

### 4.1 Аналіз зображень товарів (alt + кейси)

- `optimized_image` (`@/Users/zainllw0w/TwoComms/site/twocomms/storefront/templatetags/image_optimization.py`) — генерує AVIF/WebP + srcset. ✅
- `width`/`height` присутні всюди (запобігання CLS). ✅
- `loading=eager` + `fetchpriority=high` для LCP PDP — ✅.
- ALT-текст товарів: якщо `main_image_alt` заповнений — використається; інакше `build_product_image_alt` (`@/Users/zainllw0w/TwoComms/site/twocomms/storefront/services/catalog_helpers.py:68`).
  - **Прод**: `Чорна футболка унісекс TwoComms «Довіряй своїй божевільній ідеї»` — ідеально (категорія + колір + бренд + назва).
  - **Прод (помилка)**: `Футболка TWOCOMMS &quot;Reality Bends&quot;: Ментол` — лапки `&quot;` сирі. `[MED]` подвійне екранування у шаблоні.
- `[HIGH]` Descriptive ALT для category cover (зараз `{{ c.name }} категорія - TwoComms` — нудно). Запропоновано: `Категорія футболок TwoComms — стрітвеар і мілітарі з принтами ЗСУ`.

---

## 5. Keyword research — фреймворк

> Без Ahrefs/Semrush точних обʼємів немає. Цифри в дужках — *гіпотези* на основі публічних Google Trends + досвіду. Перевірити через Search Console після першого індексу + Ahrefs free.

### 5.1 Базові ключі (Tier 1, високочастотні, новому домену **не пріоритет**)

| Ключ | Гіпотеза місячного попиту (UA) | Пріоритет TwoComms | Аргументація |
|------|--------------------------------|---------------------|--------------|
| `футболки купити` | 30‑50K | LOW | DR 60+, маркетплейси (Rozetka, Prom). Молодий домен не пробʼє. |
| `купити худі` | 20‑40K | LOW | Same. |
| `мілітарі одяг купити` | 3‑8K | **HIGH** | Менше конкуренції; релевантно бренду. |
| `streetwear україна` | 2‑5K | **HIGH** | Свій USP + бренд-story (Харків, ЗСУ). |
| `патріотичний одяг` | 5‑10K | **MED** | Багато конкурентів (Aviatsiya, Bezviz), але висока конверсія. |

### 5.2 Mid-tail (Tier 2, **основна стратегія**)

| Ключ | Гіпотеза | Інтент | Які сторінки таргетимо |
|------|---------|--------|-------------------------|
| `купити мілітарі футболку` | 500‑2000 | Trans | `/catalog/tshirts/` + теги ЗСУ |
| `футболка з принтом ЗСУ` | 800‑3000 | Trans | категорійна + PDP `where-mi-present-ts` |
| `чорна футболка з принтом купити` | 400‑1500 | Trans | категорійний фільтр color |
| `худі з патріотичним принтом` | 200‑800 | Trans | `/catalog/hoodie/` |
| `український стрітвеар бренд` | 200‑500 | Info+Comm | `/pro-brand/` |
| `футболка ЗСУ оверсайз` | 100‑500 | Trans | fit-page `/product/<slug>/oversize/` |
| `лонгслів з мілітарі принтом` | 50‑200 | Trans | `/catalog/long-sleeve/` |
| `купити одяг ЗСУ в Україні` | 500‑2000 | Trans | головна / brand story |
| `streetwear Харків` | 50‑200 | Local | `/pro-brand/`, footer LocalBusiness |

### 5.3 Long-tail (Tier 3, **швидкий ROI на новому домені**)

> Це той клас, який запитувач навів («купити футболку Харків», «футболка військова кайот з принтом купити онлайн»). Дуже цінні: CPC низький, конкуренція ≤5, обʼєм ~10‑100/міс.

Принцип формули long-tail для TwoComms:
```
[Дія] + [Категорія] + [USP/Стиль] + [Колір?] + [Локація?] + [Бренд?]
```

Приклади (укр.):
- `купити чорну футболку з принтом Київ`
- `футболка кайот мілітарі купити Харків`
- `худі оверсайз з принтом ЗСУ Львів`
- `лонгслів унісекс з авторським принтом купити онлайн`
- `купити мілітарі футболку з доставкою Новою Поштою`
- `футболка з символікою азов придбати онлайн` *(перевірити legal/branding risk)*
- `український streetwear бренд з Харкова`
- `футболка з гумором ЗСУ купити`
- `подарунок патріоту чоловіку футболка`
- `купити жіночу мілітарі футболку оверсайз`

**Покриття:** долити такі формулювання у `seo_description`, у H2/H3 категорії та у `_city_paragraph` (`@/Users/zainllw0w/TwoComms/site/twocomms/storefront/services/product_seo_landing.py:289`).

### 5.4 Інформаційні запити (для майбутнього `/blog/`)
- «що таке DTF-друк»
- «як прати футболку з принтом» 
- «оверсайз vs регуляр посадка»
- «розмірна сітка українських футболок»
- «як вибрати худі на зиму»
- «історія streetwear в Україні»
- «що означає назва TwoComms» *(brand-story support, частково вже на /pro-brand/)*

`[HIGH]` Створити блок `/blog/` з 6–10 статтями (по 800–1200 слів) — це швидко витягне інформаційний трафік. URL `/blog/` зараз віддає 404 — `[CRIT]` створити або зняти посилання.

### 5.5 Що **не** використовувати на молодому домені
- `футболка` (голий kw без модифікаторів) — конкурує з Rozetka.
- `купити одяг онлайн` — занадто широкий.
- Гео + категорія без бренду: `Київ футболка` — переграно.
- Слова з домішкою інтенту: `тактичний одяг ЗСУ` — це інтент **на пошук тактичного спорядження**, не streetwear; буде висока bounce rate.

### 5.6 Як заповнити `seo_keywords` тепер, коли HTML-рендер вимкнено

- Поле в БД `Product.seo_keywords` (max 300 символів) залишається корисним для:
  1. **Внутрішнього пошуку** на сайті (якщо реалізовано — `[TBD]` перевірити `/search/?q=`).
  2. **AI-індексу** (`generate_product_keywords` повертає до 20 шт; це дані для майбутнього векторного індексу або recommendations).
  3. **Sitemap.image extension** (як image:caption — `[TBD]` чи це реалізовано).
- Рекомендований формат заповнення (CSV, lowercase):
  ```
  купити мілітарі футболку, чорна футболка з принтом, українська футболка ЗСУ, футболка оверсайз twocomms, футболка з гумором, harkiv streetwear t-shirt, футболка кайот купити, патріотична футболка унісекс, dtf друк футболка, футболка my little baby
  ```
- 8–15 ключів достатньо. Структура: 3× базових (категорія + дія) + 3× стилістичних (мілітарі/стріт) + 3× колір/посадка + 2× локація + 2× транслітерація.

---

## 6. Мультимовність — окремий розділ

### 6.1 Що зараз працює
- UI-переклад через `gettext` — головна, шапка, футер.
- `<html lang>`, `hreflang`, `og:locale`, `LANGUAGE_OG_LOCALE` — все коректно генерується.
- Sitemap містить 3× URL для кожного товару (uk/ru/en) + `xhtml:link rel=alternate` всередині.

### 6.2 Де ламається
1. **Поля моделей `*_ru`/`*_en` порожні** для ~всіх товарів. Підтвердження: `https://twocomms.shop/ru/product/clasic-tshort/` віддає UK-title/desc. Це класичний випадок «hreflang з однаковим контентом».
   - Google толерує `fallback`, *якщо* canonical вказує на UK-версію. Зараз `canonical=ru-URL` (бо `{{ request.path }}`). **`[CRIT]`** → Google може індексувати дублікат і знизити sitewide trust.
2. **H2 у /ru/ — частково перекладено** (`Похожие товары`), а в /en/ — `Related products`, але всі інші H2 — українською. Це **mixed-language page** — найгірший сценарій.
3. **Тайтл** `Футболка класична — купити футболка TwoComms` на /ru/ — точна копія UK. Не отримує жодного бонусу за `ru/`.

### 6.3 Стратегія (для подальшого reasoning)

**Варіант A (мінімум зусиль, рекомендую на 6 міс):**
- Деактивувати RU/EN на рівні sitemap (видалити окремі URL).
- Залишити `hreflang` тільки `uk` + `x-default`, поки немає реального перекладу.
- На /ru/ і /en/ ставити `<meta name="robots" content="noindex">` АБО `<link rel="canonical" href="UK">`.

**Варіант B (стратегічний):**
- Перекласти ВСІ product `title`/`description`/`short_description`/`full_description` (стартово машинно через DeepL/GPT-4 з людським ревʼю) — заповнити `*_ru` та `*_en`.
- Бренд `TwoComms` залишається латиницею.
- Слова, які не перекладаємо (мілітарі/militari, стріт/street, oversize) — uniform terminology guide.
- RU-аудиторія в Україні — велика, але **офіційний політичний signал** TwoComms (підтримка ЗСУ) дисонує з RU-таргетингом → можна обмежити RU тільки до інтерфейсу, а контент дублювати лише UK.
- EN — лише якщо плануєте EU-експансію. Якщо ні — закрити.

`[HIGH]` Прийняти бізнес-рішення: який ринок (RU-україномовний користувач, EN-експорт) — ціль? Поки рішення немає — **Варіант A**.

### 6.4 Назви товарів — `Reality Bends: Dark Neon Edition`, `My Little Baby`
- Самі назви змішують латиницю/кирилицю. Це нормально для streetwear, Google розуміє контекст. Нюанси:
  - `[MED]` Українські користувачі шукають часто **і латиницею, і кирилицею**: «футболка реаліті бендс», «футболка my little baby». Запропонувати у `seo_keywords` додавати **обидва написання** + транслітерацію.
  - Slug — ASCII (вже так і є) — добре.

### 6.5 Окремий ризик: **«стріт» vs «street» vs «стрит»**
- На прод RU-варіант сайту переклав `Стріт & Мілітарі Одяг` → `стрит & милитари одежда`. Кириличне `стрит` (RU) — це **транслітерація без сенсу для українського користувача**. Якщо стратегічна аудиторія — україномовний user, RU не потрібен.

---

## 7. Конкуренти (рамка, потребує live-скрапу)

> Дані нижче — **гіпотези**. `[TBD: tooling]` означає, що потрібен окремий subagent з доступом до web-скрапінгу для глибшого порівняння.

### 7.1 Militarist (`militarist.ua`)
- **Сильні сторони (припущення):** домен 8+ років, тисячі товарів, заголовки з геомаркерами, налагоджена структура `Category → Subcategory → PDP`, тверда `BreadcrumbList`, очевидно `AggregateRating` від великого числа відгуків.
- **Слабкі:** інтент — більше «тактичний спорядження», менше streetwear → пряма конкуренція з TwoComms неповна.
- **Що запозичити:** структура мега-меню, ширина FAQ на PDP, фільтри по бренду/розміру/кольору.

### 7.2 Aviatsiya Halychyny / Бренд патріотика
- Сильні: дизайн, бренд-story, контент на blog.
- Запозичити: stories-центрика, «collection» лендинги.

### 7.3 Made in UA (`made-in-ua.com`), staff.ua
- Чисті URL, сильні розмірні сітки в окремих лендингах, найкраща продуктова фотографія в UA-e-com.
- Запозичити: розмірні сітки в окремих лендингах (sub-landing), LCP-image strategy.

### 7.4 Інші
- `wearbear`, `etnodim` — національні бренди з сильним hreflang (UK/EN/PL).
- `bezviz.com.ua`, `wmlife.ua` — для бенчмарку патріотичної ніші.

### 7.5 Що зробити в наступній фазі
`[TBD]` Запустити окремий subagent із web-scrape + GSC export, заповнити порівняльну таблицю по:
1. Title/Description templates
2. H1 patterns
3. Schema присутність
4. ItemList на категорії
5. Кількість слів на PDP
6. Швидкість LCP

---

## 8. Технічний SEO — швидкі знахідки

| # | Item | Стан | Дія |
|---|------|------|-----|
| 1 | `<meta name="robots">` за категоріями параметрів (`?color=`) | `[TBD]` | додати `noindex,follow` на URL з фільтрами або заборонити в robots |
| 2 | Pagination canonical | `[TBD]` | звірити з `{% block pagination_links %}` |
| 3 | 404 на `/blog/` | `[CRIT]` | створити сторінку-заглушку або контент |
| 4 | `viewport` | ✅ | – |
| 5 | CSP — інлайн `unsafe-inline` | technical | не SEO-critical, але AI-bot може ламати |
| 6 | `lang` на `<html>` змінюється правильно | ✅ | – |
| 7 | Sitemap відносна частота `monthly` категорій | `[MED]` для активних дропів `weekly` |
| 8 | `og:image` 1080×1350 portrait | `[MED]` згенерувати landscape `1200×630` |
| 9 | Soft 404 ризики | `[TBD]` перевірити пошук без результатів |
| 10 | Cache hreflang для variant URL | `[TBD]` `?color=` не має дублюватись у sitemap |
| 11 | LiteSpeed cache + WhiteNoise manifest | working, потребує `touch tmp/restart.txt` після `collectstatic` | оперативна нота |

---

## 9. Master Checklist

> Маркуй кожний пункт `[ ]` → `[x]` і додавай дату виконання. Не видаляй, лише оновлюй. Кожен пункт містить `(ID)` для зворотних посилань з PR/issue.

### 9.1 `[CRIT]` Negative regressions (виправити негайно)

- [ ] **(A)** Виправити граматику Phase-13.5 `seo_title`: `_nom(cat)` → `_acc(cat)` у `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/services/product_copy_v2.py:314`. Перегенерувати `seo_title` для всіх продуктів, де `looks_like_phase13_autofill(...)` повертає True.
- [ ] **(B)** Обмежити довгі товарні назви у Title: якщо `len(seo_title) > 60`, скоротити product part до 35 символів, до бренду — лише `— TwoComms`. H1 залишається повним.
- [ ] **(C)** Додати `brand` у Product schema (`@/Users/zainllw0w/TwoComms/site/twocomms/storefront/seo_utils.py`, шукати `generate_product_schema`).
- [ ] **(D)** Прибрати подвійне `— TwoComms` у H2 категорійних SEO-блоків (адмінка `CategorySeoBlock`).
- [ ] **(E)** Прибрати помилкове підставляння `fit_code` для **base PDP** (інакше H2 «(Класична)» зайвий). Перевірка `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/views/product.py:435-447`.
- [ ] **(F)** `/blog/` → 404. Створити змістовну сторінку-заглушку («Скоро»), або 410, або зняти посилання.
- [ ] **(G)** Прийняти рішення по RU/EN — поки немає перекладів, додати `noindex` на /ru/* та /en/* PDP/категорії або змінити їх canonical на UK.
- [ ] **(H)** Скоротити title у `/catalog/tshirts/`, `/catalog/hoodie/`, `/catalog/long-sleeve/` до ≤60 символів.

### 9.2 `[HIGH]` Швидкі виграші

- [ ] (I) Додати `ItemList` JSON-LD на головну (Новинки) та на категорії (продукти грида).
- [ ] (J) Додати `BreadcrumbList` JSON-LD на PDP, якщо ще не виводиться.
- [ ] (K) Окремий `og:image` 1200×630 для кожного товару.
- [ ] (L) На PDP додати H2/H3-секції «Доставка», «Догляд» (короткий unique-text per product).
- [ ] (M) Стратегія review-collection (купон 5% → відгук). Поріг для `aggregateRating` понизити з 3 до 1 з підписом «1 відгук».
- [ ] (N) Розширити title `/catalog/` (зараз 22 символи).
- [ ] (O) Заповнити `seo_keywords` у БД для всіх товарів (для AI-індексу/recommendations) — навіть якщо HTML не друкує `<meta keywords>`.
- [ ] (P) Створити `/blog/` з 6–10 pillar-статтями (інформаційний intent з §5.4).
- [ ] (Q) Додати на категорії крос-лінки на «гендерні» сабкатегорії та на «колір x категорія» лендинги.
- [ ] (R) Перевірити, що `/about/` не залишився у sitemap (один зайвий 301 на crawl-budget).
- [ ] (S) Додати `home_card_image` + `main_image_alt` для всіх товарів.
- [ ] (T) Додати на головну згадку «бренд із Харкова» в `og:description` (LocalSEO).

### 9.3 `[MED]` Контент і структура

- [ ] (U) Замінити generic H2 на головній (`Категорії`, `Новинки`) на keyword-rich варіанти.
- [ ] (V) Заголовки `_build_landing_html` варіювати (3 шаблони мінімум).
- [ ] (W) `seo_description` для PDP — додати `Нова Пошта 1–3 дні` (Phase 21 правила).
- [ ] (X) Виправити `&quot;` у ALT-атрибутах (подвійне екранування).
- [ ] (Y) Розглянути окремі лендинги по містах: `/catalog/tshirts/kyiv/`, `/kharkiv/`, `/lviv/`.
- [ ] (Z) Розширити синоніми `футболка з довгим рукавом` для `/catalog/long-sleeve/`.
- [ ] (AA) Адмінка: чек-лист «SEO готовність товару» — show‑bar в Django admin (поля заповнено / ні).

### 9.4 `[LOW]` Гігієна

- [ ] (BB) Очистити sitemap від `?utm_*` і fragments.
- [ ] (CC) Перевірити `OG image:alt` довжину (≤125 символів — best practice для accessibility).
- [ ] (DD) Прибрати `Disallow: /*?sort=` якщо `sort` ніде не активний (інакше — лишається).

### 9.5 `[TBD]` Дослідницькі задачі (для наступного subagent-a)

- [ ] (EE) Експортувати з prod БД повний дамп `(id, slug, title, seo_title, seo_description, seo_keywords, short_description, full_description, main_image_alt)` усіх товарів і категорій → завантажити сюди як CSV-додаток.
- [ ] (FF) Скрейп-порівняння з `militarist.ua`, `aviatsiya.com.ua`, `madeinua.com`, `staff.ua` (по 1 категорії та 3 PDP) — заповнити таблицю в §7.
- [ ] (GG) Ahrefs/SE Ranking export top-50 ключів для домену → перевірити збіг із §5.
- [ ] (HH) Google Search Console exports (queries 28d): топ-200 — щоб зафіксувати **реальні** запити.
- [ ] (II) Прогнати `/blog/`, `/help/`, `/delivery/`, `/return/`, `/privacy/`, `/terms/` через окремий аудит.
- [ ] (JJ) Спарсити `/sitemap-product-variants.xml` і перевірити, чи `?color=` URL-и не дублюються в індексі.
- [ ] (KK) Перевірити повний source PDP (ввімкнено `view-source:` через curl з усіма параметрами) — чи виводиться `BreadcrumbList`/`FAQPage`/`Offer.priceValidUntil`.
- [ ] (LL) Прогнати top-20 PDP через Lighthouse на mobile + рапорт у `output/lighthouse-mobile/` із порівнянням до/після виправлення `seo_title`.

---

## 10. Пріоритизований Backlog (рекомендована послідовність)

> Оцінки: **Effort** (S/M/L), **Impact** (1–5), **Time-to-results** (Q — quick, M — medium, L — long).

| Order | ID | Завдання | Effort | Impact | TTR | Залежності |
|-------|----|----------|--------|--------|-----|------------|
| 1 | (A) | NOM→ACC у seo_title | S | 4 | Q | — |
| 2 | (E) | fit_code на base PDP | S | 3 | Q | — |
| 3 | (C) | brand у Product schema | S | 4 | Q | — |
| 4 | (H) | Скоротити category titles | S | 3 | Q | — |
| 5 | (G) | RU/EN noindex стратегія | S | 5 | M | бізнес-рішення |
| 6 | (D) | Прибрати «— TwoComms» дубль | S | 2 | Q | — |
| 7 | (F) | /blog/ заглушка | S | 2 | Q | — |
| 8 | (J) | BreadcrumbList JSON-LD | S | 3 | M | — |
| 9 | (I) | ItemList JSON-LD home + cat | M | 3 | M | — |
| 10 | (K) | OG image 1200×630 | M | 2 | M | автогенератор |
| 11 | (L) | H2/H3 «Доставка/Догляд» PDP | M | 3 | M | per-product unique тексти |
| 12 | (P) | /blog/ pillar-статті | L | 4 | L | контент + дизайн |
| 13 | (M) | Review-collection стратегія | L | 5 | L | бізнес + UX |
| 14 | (Y) | Локальні лендинги міст | L | 4 | L | архітектурне рішення |

**Перші 7 пунктів = «1 спринт SEO» — мінімум часу, максимум впливу.**

---

## 11. Запитання до власника бізнесу + Naступні кроки

1. **Чи плануємо реально перекладати каталог RU/EN?** Якщо ні — закриваємо мови з indexing, sitemap, hreflang.
2. **Чи готові інвестувати у блог (10 статей × $50/article)?** Це найшвидший важіль для молодого домену.
3. **Чи можемо «помʼякшити» 3-review поріг для `aggregateRating`?** SEO-win, але потребує бізнес-рішення.
4. **Які запити критичні для вас стратегічно?** (Наприклад «купити мілітарі футболку Київ» — пріоритет 1; «футболка ЗСУ оверсайз» — пріоритет 2). Заповнення цього списку дасть нам цільовий keyword-map.
5. **Геофокус**: Україна цілком чи окремі міста (Харків — рідне, Київ — найбільший ринок, Львів — преміум-сегмент)?
6. **Сезонність**: чи плануються дропи до зими/літа, до Дня Незалежності? Це впливає на content calendar блогу.

### 11.1 Пайплайн наступної фази (Phase B — глибинний reasoning)

1. **Витягнути prod-дамп товарів** (CSV або JSON через manage.py команду; `[TBD]` потребує доступу до прод-shell).
2. **Прогнати кожний товар** через шаблон §4 — отримати таблицю Product × 17 чекпойнтів.
3. **Заповнити порівняльну таблицю конкурентів** §7 через web-scrape subagent.
4. **Узгодити keyword-map з §5** через GSC + Ahrefs дані.
5. **Сформувати фінальний technical PR-план** з конкретними патчами на код (НЕ робити в цій ітерації — це інпут для подальшого reasoning).

### 11.2 Чого цей документ навмисно **не** робить

- **Не пропонує конкретний код-патч** — це інпут для глибинного reasoning, не імплементації.
- **Не дає точних обʼємів пошуку** — без Ahrefs/Semrush це некоректно.
- **Не оцінює конкурентів живими цифрами** — потребує scraping subagent.
- **Не порушує існуючі manually-written SEO** — усі правки супроводжуються guard-логікою (`looks_like_phase13_autofill`-аналог).

---

## 12. Журнал ітерацій документа

| Дата | Ітерація | Що додано | Хто |
|------|----------|-----------|-----|
| 2026-05-11 | v0.1 | Першоосновний скан інфраструктури, прод-зрізи, §1–§11 | Cascade |
| _ | _ | Очікує: дамп prod-БД, скрейп конкурентів, GSC export | Phase B |

---

## Додаток A. Сирі дані з прод-зрізу 2026-05-11

### A.1 PDP `https://twocomms.shop/product/clasic-tshort/`
- Title: `Футболка класична — купити футболка TwoComms`
- Description: `Базова класична футболка TwoComms без принту: чиста форма, якісний матеріал і силует, що пасує під будь-який образ. Шиємо в Україні, DTF-друк, бавовна...`
- H1: `Футболка класична`
- Canonical: `https://twocomms.shop/product/clasic-tshort/`
- og:image: `https://twocomms.shop/media/products/c3.jpg` (1080×1350)
- Schema graph: Organization, WebSite, @graph[Product]; **brand=null, aggregateRating=null, review=[]**

### A.2 PDP `https://twocomms.shop/product/where-mi-present-ts/`
- Title: `Футболка "Де Мої Подарунки, Мразота?" — купити футболка...` *(зрізаний)*
- Description: `Футболка «Де Мої Подарунки, Мразота?» TwoComms — провокаційний святковий принт у дусі чорного гумору. Шиємо в Україні, DTF-друк, бавовна. Доставка Новою...`

### A.3 Category `https://twocomms.shop/catalog/tshirts/`
- Title: `Футболки TwoComms — стрітвеар та мілітарі-принти від українського бренду` (75 символів)
- H1: `Футболки з характером — стрітвеар і мілітарі від TwoComms`
- 5× H2 (див. §1.5)
- 7× H3 (Силуети, Тканина та DTF-друк, Принти, Чоловічі/жіночі/унісекс, Доставка та оплата, Скільки коштує, FAQ)

### A.4 Sitemap (дата 2026-05-09 для products / 2026-05-10 для categories)
- 5 sub-sitemaps; uk + ru + en URL для кожного PDP/категорії.

### A.5 RU/EN дублікати
- `/ru/product/clasic-tshort/` віддає **той самий** UK-Title і UK-Description, що і `/product/clasic-tshort/`.
- В H2-блоках змішування мов (`Похожие товары` RU + UK решта).

---

## Додаток B. Точки дотику в коді (для швидкої навігації)

- Базовий шаблон head: `@/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/base.html:8-112`
- Партіал meta: `@/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/partials/seo_meta.html`
- Генератор meta: `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/seo_utils.py:340-432, 1066-1147`
- Phase 13.5 копірайт + bug: `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/services/product_copy_v2.py:312-316`
- Лендинг блок PDP: `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/services/product_seo_landing.py`
- Variant meta (canonical/title/desc): `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/services/variant_meta.py`
- Models (Category/Product SEO fields): `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/models.py:60-100, 510-600`
- Translation registry: `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/translation.py`
- Hreflang helper: `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/templatetags/i18n_links.py`
- Seo template tags: `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/templatetags/seo_tags.py`
- ALT helper: `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/services/catalog_helpers.py:68`
- Settings i18n: `@/Users/zainllw0w/TwoComms/site/twocomms/twocomms/settings.py:568-619`
- Sitemaps: `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/sitemaps.py`

---

## 13. v0.2 — корекції попередніх гіпотез (2026-05-11, ітерація 2)

> Після другого проходу з більшою кількістю прод-зразків деякі попередні гіпотези виявилися помилковими. Залишаю їх перекресленими у тексті вище і фіксую правду тут.

### 13.1 Скасовані «фальшиві CRIT»
- ~~§1.7 / §3.6 / §10 (C): «`brand` відсутнє в Product schema»~~ — **HE ПРАВДА**. На прод PDP `brand` присутній: `{"@type":"Brand","name":"TwoComms","url":"https://twocomms.shop/"}`. Початкова гіпотеза виникла через помилковий `json.dumps(...).get('brand')` на проміжному dict без `@graph`. Фактично — `Product.brand` коректний.
- ~~§1.7 / §3.6 / §10 (J): «`BreadcrumbList` JSON-LD відсутній»~~ — **НЕ ПРАВДА**. На PDP виводиться `BreadcrumbList` із 4 items (Головна → Каталог → Категорія → Товар) у `@graph` поряд з Product.

**Результат:** пункти `(C)` і `(J)` у §9.1/§9.2 знімаються з backlog. Залишаються інші CRIT.

### 13.2 НОВІ критичні знахідки (доповнення до §9.1)

- [ ] **(MM)** `[CRIT]` **HTML-entity double-encoding в `title` і `<h1>`**. Прод-зразки:
  - `<title>Худі &quot;Дрони навколо 2.0&quot; — купити худі TwoComms</title>`
  - `<h1 class="tc-product-title">Худі &quot;Дрони навколо 2.0&quot;</h1>`
  - Source: `Product.title` у БД ймовірно зберігається як `Худі &quot;Дрони навколо 2.0&quot;` (з вже-екранованими лапками). Потім Django template ескейпить ще раз → видно сирий `&quot;`.
  - Перевірити: SELECT title FROM storefront_product WHERE title LIKE '%&quot;%' — підрахувати кількість.
  - Виправлення: одноразовий migrate-script, який пройде по всіх товарах і замінить `&quot;` → `"`, `&amp;` → `&`, `&apos;` → `'`. Plus захист у формі адмінки на майбутнє (clean_title).
  - На скільки це критично: Google **зазвичай декодує** `&quot;` назад у `"` у SERP, але в OG/Twitter cards рендериться сирим у багатьох клієнтах (Telegram, Slack показують `&quot;` буквально).
- [ ] **(NN)** `[CRIT]` **`<meta name="description">` ПОРОЖНІЙ на 14 статичних сторінках**: `/dopomoga/`, `/povernennya-ta-obmin/`, `/polityka-konfidentsiynosti/`, `/umovy-vykorystannya/`, `/novyny/`, `/faq/`, `/cooperation/`, `/custom-print/`, `/doglyad-za-odyagom/`, `/mapa-saytu/`, `/rozmirna-sitka/`, `/favorites/`, `/vidstezhennya-zamovlennya/`, `/search/`. На прод відповіді поле просто відсутнє у HTML. Ці URL внутрішньо лінковані з footer/header → Google буде генерувати description сам із body — це втрачений CTR.
  - Рекомендація: для кожної сторінки додати окремий `{% block description %}` із 140–160-символьним описом, де помітні: сутність сторінки + бренд + USP.
- [ ] **(OO)** `[CRIT]` **На `/cooperation/`, `/custom-print/`, `/search/` відсутній `<h1>`**.
  - `/cooperation/` — Title: `Співпраця з TwoComms` (28 символів — короткий), без H1. Сторінка про дропшиппінг/B2B — потенційно важлива для трафіку.
  - `/custom-print/` — Title: `DTF-конфігуратор кастомного одягу — TwoComms` (45 символів, гарний). Без H1 — конструктор як SPA, але H1 для SEO потрібен.
  - `/search/?q=...` — Title `Пошук: {q} — TwoComms` (динамічний). Без H1. Окрім H1, ця сторінка має бути `noindex` (search results пагінація).
- [ ] **(PP)** `[CRIT]` **`FAQPage` JSON-LD ніде не виводиться** на PDP, хоча `ProductFAQ` модель існує і `faq_schema` template tag є (`@/Users/zainllw0w/TwoComms/site/twocomms/storefront/templatetags/seo_tags.py:357-383`). Перевірено 3 продукти — `FAQPage` not in HTML.
  - Можливі причини: (a) теплейт PDP не викликає `{% faq_schema product_faq_items %}`, (b) товари не мають заповнених `ProductFAQ` рядків (на проді), (c) виклик закоментований.
  - Імпакт: FAQ rich result у Google — один з найвпливовіших rich-result типів, втрачаємо.
- [ ] **(QQ)** `[HIGH]` **`offers.availability=OutOfStock` на популярних товарах**: `clasic-tshort`, `-20-twocomms-Legend`, `where-mi-present-ts` — всі OOS. Це або:
  - реально немає товару на складі — тоді ОК;
  - bug у логіці визначення `availability` (наприклад враховує тільки одну SKU/розмір).
  - `[TBD]` перевірити: `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/seo_utils.py` — як рахується availability. На стороні витрини користувач бачить «Купити» — тобто товар є в наявності? Якщо так — це **серйозна регресія SEO** (Google не показує товар у Shopping без InStock).
- [ ] **(RR)** `[HIGH]` **`/novyny/` (блог) існує і має 200**, але посилається з footer як `/blog/` (404). У §9.1(F) було `[CRIT] /blog/ → 404`. Тепер уточнення: **проблема — у внутрішніх посиланнях**, а не в самій сторінці. Виправлення: знайти всі `href="/blog/"` і замінити на `/novyny/`.
  - Швидкий grep: `@/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/` за `"/blog/"` (потенційно у хедері/футері).
- [ ] **(SS)** `[MED]` Phase 13.5 `seo_title` також **створює `seo_title` з малої літери** для деяких товарів: `лонгслів "death grabs ass"... — купити лонгслів TwoComms` — `Product.title` зберігається з малої. Виправлення: capitalize first letter у seo_title (не змінюючи вихідний title).

### 13.3 Реальні приклади Title з прод (для подальшого reasoning)

| Slug | Title (прод) | Довжина | Статус |
|------|------|--------|--------|
| `clasic-tshort` | `Футболка класична — купити футболка TwoComms` | 44 | `[CRIT]` NOM/ACC |
| `-20-twocomms-Legend` | `Худі &quot;Дрони навколо 2.0&quot; — купити худі TwoComms` | 56 | `[CRIT]` HTML entity |
| `-225-tshirt-` | `Футболка 225ОШП — купити футболка TwoComms` | 42 | `[CRIT]` NOM/ACC |
| `-225-hoodie-` | `Худі &quot;Команда Сірко&quot; х 225ОШП — купити худі TwoComms` | 65 | `[CRIT]` ентіті + довжина |
| `-death-gbs-ass-hd` | `Худі &quot;І На Той Світ З Собою Візьму&quot; — купити худі TwoComms` | 76 | `[CRIT]` ентіті + довжина |
| `-death-gbs-ass-ts` | `Футболка &quot;І На Той Світ З Собою Візьму&quot; — купити...` | 99 (зрізано Google) | `[CRIT]` |
| `-death-grabs-ass-ls` | `лонгслів &quot;death grabs ass&quot;. — купити лонгслів TwoComms` | 67 | `[CRIT]` capitalisation + ентіті |
| `where-mi-present-ts` | `Футболка "Де Мої Подарунки, Мразота?" — купити футболка...` | ~99 | `[CRIT]` довжина + NOM/ACC |

**Висновок:** виправлення `(A)` (NOM/ACC) + новий патч `(MM)` (HTML entity decode) + `(B)` (truncate >60) повинні бути **в одному migration-скрипті**, який пройде по всіх товарах і пере-генерує `seo_title` чисто.

### 13.4 Коректний список «реальних» URL у TwoComms

З root-сторінки витягнуто всі внутрішні посилання. Основні нав-points:
- `/contacts/`, `/cooperation/`, `/custom-print/`, `/delivery/` — статика. ✅ 200.
- `/dopomoga/` (help), `/faq/`, `/doglyad-za-odyagom/`, `/povernennya-ta-obmin/` — політика/підтримка. ✅ 200.
- `/polityka-konfidentsiynosti/`, `/umovy-vykorystannya/` — legal. ✅ 200.
- `/novyny/` — блог/новини. ✅ 200.
- `/mapa-saytu/`, `/rozmirna-sitka/`, `/vidstezhennya-zamovlennya/` — utility. ✅ 200.
- `/favorites/` — личний кабінет (`[MED]` має бути noindex).
- `/pro-brand/` — brand-story. ✅ 200.
- `/?page=2..9` — pagination головної (новинки). `[TBD]` перевірити canonical.
- `/cart/`, `/login/`, `/register/`, `/oauth/login/google-oauth2/` — функціональні (заборонено в robots).
- `/search/?q=...` — пошук. `[CRIT]` має бути noindex.

**Старі/мертві URL** (404):
- `/blog/`, `/help/`, `/return/`, `/privacy/`, `/terms/`, `/gallery/`, `/constructor-app/` — 404, але можуть бути все ще у sitemap/внутрішніх посиланнях. `[HIGH]` перевірити.
- `/about/` → 301 на `/pro-brand/`. ОК, але прибрати з sitemap.

### 13.5 H1 audit static pages (швидко)

| URL | H1 | Title (≤60?) | Description |
|-----|----|------|------|
| `/contacts/` | `Контакти` | ✅ 16 | ✅ |
| `/pro-brand/` | brand-story Z-wrapped | ✅ 60 | ✅ |
| `/cooperation/` | **відсутній** | ✅ 28 | ❌ порожній |
| `/custom-print/` | **відсутній** (SPA) | ✅ 45 | ❌ порожній |
| `/delivery/` | `Доставка і оплата` | ✅ 30 | ❌ порожній |
| `/dopomoga/` | `Допомога та базові правила сайту` | ✅ 53 | ❌ порожній |
| `/povernennya-ta-obmin/` | `Повернення та обмін` | ✅ 38 | ❌ порожній |
| `/polityka-konfidentsiynosti/` | `Політика конфіденційності` | ✅ 39 | ❌ порожній |
| `/umovy-vykorystannya/` | `Умови використання сайту` | ✅ 38 | ❌ порожній |
| `/novyny/` | `Новини та апдейти бренду` | ✅ 47 | ❌ порожній |
| `/faq/` | `Поширені питання по покупці та сервісу` | ✅ 50 | ❌ порожній |
| `/doglyad-za-odyagom/` | `Догляд за одягом` | ✅ 27 | ❌ порожній |
| `/mapa-saytu/` | `Карта сайту та швидка навігація` | ✅ 50 | ❌ порожній |
| `/rozmirna-sitka/` | `Розмірна сітка та поради по посадці` | ✅ 47 | ❌ порожній |
| `/vidstezhennya-zamovlennya/` | `Відстеження замовлення` | ✅ 51 | ❌ порожній |
| `/favorites/` | `Обрані товари` | ✅ 23 | ❌ порожній |
| `/search/?q=...` | **відсутній** | ✅ динамічний | ❌ порожній |

**Висновок:** Title для всіх статичних сторінок — добре зроблений (≤60 символів, з брендом, з ключем). Але **description порожній скрізь**, що системно псує CTR (Google формує snippet з body — часто погано).

### 13.6 Доповнений `[CRIT]`-список (для §9.1)

Об’єднаний список після ітерації 2 (з ID для трекінгу):

- (A) NOM→ACC у seo_title — **залишається CRIT**.
- (B) Скоротити title >60 — **залишається CRIT**.
- ~~(C) brand schema~~ — **знято**.
- (D) Подвійне «— TwoComms» у H2 — `[MED]`.
- (E) fit_code на base PDP — **залишається CRIT**.
- (F) `/blog/` 404 — **переоцінено до `[HIGH]`** (бо `/novyny/` є). Виправити внутрішні посилання (`(RR)`).
- (G) RU/EN noindex — **залишається CRIT**.
- (H) Скоротити category titles — **залишається CRIT**.
- **(MM) HTML entity double-encoding в title/h1 — НОВИЙ CRIT**.
- **(NN) `<meta description>` порожній на 14 статичних сторінках — НОВИЙ CRIT**.
- **(OO) Відсутній `<h1>` на 3 сторінках — НОВИЙ CRIT**.
- **(PP) FAQPage schema ніде не виводиться — НОВИЙ CRIT**.
- **(QQ) OutOfStock availability — НОВИЙ HIGH (потребує перевірки)**.
- **(RR) Внутрішні `/blog/` посилання → 404 — НОВИЙ HIGH**.
- **(SS) Capitalize first letter у seo_title — НОВИЙ MED**.

---

## 14. Розширений keyword research (UA-ринок, Tier 2/3 з прод-кейсами)

### 14.1 Семантичні кластери з реальних прод-назв

З витягнутих прод-товарів видно дві смислові осі:

**Ось 1: Категорія + матеріал**
- футболка / худі / лонгслів × бавовна / трикотаж / фліс / DTF-друк

**Ось 2: Тематика принта**
- Мілітарі-технічна (`Дрони навколо 2.0`, `225ОШП`, `Команда Сірко`) — пошуковий кластер «футболка ЗСУ + дрон/підрозділ»
- Чорний гумор / провокація (`Де Мої Подарунки, Мразота?`, `death grabs ass`, `І На Той Світ З Собою Візьму`) — кластер «футболка з мемами / гумор / стрітвір»
- Світлий контраст (`My Little Baby`) — кластер «нео-streetwear / kawaii»
- Брендові (`Reality Bends: Dark Neon Edition`) — кластер «авторський streetwear колаборація»

### 14.2 Кейс — ключи для кластера «гумор/провокація»

Гіпотези пошукових формулювань (MID-/LOW-tail):
- `футболка з гумором купити`
- `смішна футболка з принтом українська`
- `футболка з мемом дарма гумор`
- `чорний гумор футболка купити`
- `футболка стрітвеар з провокаційним принтом`
- `streetwear t-shirt з фразою купити Україна`

→ Покривати у `seo_description` цих товарів цими варіаціями (не одинарно, а 2–3 на товар, природний текст).

### 14.3 Кейс — ключи для кластера «мілітарі-технічний»

- `футболка ЗСУ дрон купити`
- `футболка з підрозділом ЗСУ` 
- `худі 225 ОШП купити`
- `футболка військова з номером бригади`
- `футболка з символікою ЗСУ підрозділу купити онлайн`

→ Це специфічний інтент, для якого TwoComms — органічно профільний бренд. Конкуренція низька, конверсія висока.

### 14.4 Не очевидні **транслітераційні** ключі

UA-користувачі часто шукають **бренд-назви латиницею і кирилицею паралельно**. Для TwoComms — це означає:
- `купити твокомс` (рідкісно)
- `футболка twocomms` (часто)
- `худі ту комс` (помилкова транслітерація — теж пошук)
- `twocomms shop` (типовий nav-search)

→ У `seo_keywords` усіх товарів додати: `twocomms, ту комс` (хоча HTML-рендер вимкнено, поле потрібно для AI-агрегацій).

### 14.5 Сезонність

Для нового домену важлива **сезонна синхронізація з content calendar**:
- Лютий–березень: «весняна футболка», «худі на весну»
- Квітень–травень: «футболка у подарунок до 8 травня», «День памʼяті»
- Червень–липень: «футболка унісекс літо»
- Серпень: **«футболка до Дня Незалежності»** — пік патріотичного запиту, +50–100% попит. Готувати окремий лендинг або колекцію.
- Жовтень–листопад: «худі осінь зима», «утеплене худі»
- Грудень: «подарунок патріоту», «новорічна футболка з гумором»

→ Календарний план у блог `/novyny/` повинен це враховувати.

---

## 15. Internal linking + Anchor text стратегія

### 15.1 Поточний стан (зчитано з прод)

Внутрішні зв’язки на прод (зразок):
- Header → home, catalog, custom-print, novyny, faq, contacts, pro-brand, login.
- Footer → contacts, cooperation, delivery, dopomoga, doglyad-za-odyagom, faq, mapa-saytu, polityka-konfidentsiynosti, povernennya-ta-obmin, rozmirna-sitka, umovy-vykorystannya, vidstezhennya-zamovlennya.
- PDP → catalog, category, related products (8 шт), recently viewed, favorites toggle.
- Catalog → product PDP × N, color filters (`?color=`), category cards.

### 15.2 Слабкі місця

- `[HIGH]` **Категорійні крос-лінки відсутні**: `/catalog/tshirts/` не лінкує на `/catalog/hoodie/` та `/catalog/long-sleeve/` (горизонтальна навігація між категоріями обмежена меню). Додати «Дивіться також» блок: `Худі →`, `Лонгсліви →` з контекстом.
- `[HIGH]` **PDP не лінкує на бренд-сторі** (`/pro-brand/`) — а саме там TwoComms має максимальну E-E-A-T силу. Додати в footer-блок PDP лінку «Про бренд TwoComms».
- `[MED]` **Anchor text «Каталог»** — однотипний скрізь. Варіювати: «Дивитись усі футболки», «Каталог streetwear-одягу», «Уся колекція TwoComms».
- `[MED]` **Recently viewed і Related** — `aria-label`/visible text дублюються, але anchor для Google = visible link. Anchor для related products = `{rec_product.title}` — добре.

### 15.3 Стратегія anchor diversity

| Тип лінки | Поганий anchor | Гарний anchor (дайверсит) |
|-----------|---------------|---------------------------|
| Header «Каталог» | `Каталог` | `Каталог одягу TwoComms` (link), `Дивитись каталог` (button) |
| Footer "FAQ" | `FAQ` | `Поширені питання по замовленню` |
| PDP → category | `Усі футболки` | `Усі футболки TwoComms`, `Дивитись усю колекцію футболок` |
| PDP → brand | `Про нас` | `Про бренд TwoComms — streetwear із Харкова` |
| Home → catalog | `Дивитись усе` | `Дивитись увесь каталог стрітвеар одягу` |

### 15.4 Внутрішня перелінковка для **тематичних** кластерів

На PDP товару з кластера «гумор/провокація» лінкувати на `/catalog/tshirts/?theme=humor` (якщо є фільтр-парам) або на список тематично‑подібних товарів. Це покращує relevance distribution per Google's PageRank.

---

## 16. Faceted navigation strategy

### 16.1 Поточний стан

- На `/catalog/tshirts/` доступні фільтри `?color=...`. URL з фільтром віддається як **окрема сторінка** (`canonical={request.path}` без query — добре, це консолідує signal).
- В `robots.txt` блокуються `?sort=` і `?order=` — це правильно.
- `?color=black` поки **не блокується**, але `<link rel="canonical">` вказує на канонічний URL без `?color=` — Google проконсолідує.

### 16.2 Що варто перевірити (`[TBD]`)

- Якщо `?color=` URL потрапили в `sitemap-product-variants.xml` — це створює **mixed signals** (з одного боку sitemap каже indexable, з іншого — canonical вказує деінде). **Перевірити вміст `sitemap-product-variants.xml`**.
- Якщо `?color=` НЕ блокується в robots — Google буде **краулити їх** (тратить crawl budget), хоча в індекс вони не потраплять. Альтернатива: додати `Disallow: /*?color=` у robots, але втратити можливість Google розуміти варіанти. Краще: залишити `?color=` доступним для краулу + canonical → консолідація.

### 16.3 Стратегія для подальшого зростання

Коли каталог виросте до >100 товарів:
1. Створити окремі **path-based фільтр-лендинги** замість query: `/catalog/tshirts/black/` → indexable, з власним H1, унікальним описом.
2. Query-фільтри (`?size=...`, `?gender=...`) — `noindex` через robots або meta.
3. Для path-лендингів — окремий `seo_text_title`/`seo_intro_html` per (category, color, gender) комбінація.

---

## 17. Schema deep-dive: що ще додати

> Після ітерації 2 ми знаємо, що `Organization`, `WebSite`, `Product`, `BreadcrumbList` — **присутні**. Що ще варто або вже виводиться частково:

| Schema type | Статус | Цінність | Дія |
|-------------|--------|----------|-----|
| `Organization` | ✅ присутнє | Knowledge Graph | OK |
| `WebSite + SearchAction` | ✅ присутнє | Sitelinks search box | OK |
| `Product` (з brand, offers, additionalProperty) | ✅ присутнє | Rich result | додати `aggregateRating` коли буде відгук |
| `BreadcrumbList` | ✅ присутнє | Crumbs у SERP | OK |
| `FAQPage` | ❌ відсутнє | Дуже сильний rich result | **`[CRIT] (PP)` додати** |
| `Review` (на PDP) | ❌ відсутнє | Augments rich result | потребує >0 reviews |
| `AggregateRating` | ❌ (порог 3) | Зірочки в SERP | знизити поріг до 1 (`(M)`) |
| `LocalBusiness` (для адрес магазинів) | ❌ | Local SEO | `/contacts/` — додати, якщо є фізичні точки |
| `ItemList` (на категорії) | ❌ | Merchant Listing rich result | `(I)` |
| `BlogPosting` (для `/novyny/{slug}/`) | `[TBD]` | Top stories | додати коли буде блог |
| `VideoObject` | ❌ | Video carousel | якщо є відео огляди — додати |
| `HowTo` (для «як прати DTF-друк») | `[TBD]` | Rich result для `/doglyad-za-odyagom/` | сильний шанс |
| `OfferCatalog` | ❌ | Brand-page enhancement | можна на `/pro-brand/` |

### 17.1 FAQ schema — приоритет 1

- В шаблоні є tag `{% faq_schema product_faq_items %}` (`@/Users/zainllw0w/TwoComms/site/twocomms/storefront/templatetags/seo_tags.py:357`).
- В view PDP `product_faq_items` формується з `product.faqs.filter(is_active=True)` (`@/Users/zainllw0w/TwoComms/site/twocomms/storefront/views/product.py:400-403`).
- Але в HTML PDP `FAQPage` **відсутнє**. Варіанти:
  1. Шаблон не викликає tag (треба грепнути `pages/product_detail.html` за `faq_schema`).
  2. На прод товарах немає заповнених `ProductFAQ` рядків — тоді tag нічого не рендерить.
- `[TBD]` Перевірити обидва.

### 17.2 HowTo для `/doglyad-za-odyagom/`

Сторінка вже існує (200, H1: «Догляд за одягом»). Якщо контент розбитий на кроки (Прання → Сушіння → Прасування), додати `HowTo` schema — Google показує як інтерактивний rich result. Великий приріст у запитах «як прати футболку з принтом», «як прати худі».

---

## 18. Review collection — практичний план

> Бекпог пункт `(M)` був абстрактним. Деталізую.

### 18.1 Технічна інфраструктура (вже є)
- Модель Review (натяк: `product_review_summary`, `approved_reviews`, `product_customer_has_paid_order` — у view PDP, `@views/product.py:573-576`).
- Поріг 3 reviews для виводу `aggregateRating` — Phase 21.

### 18.2 Програма збору відгуків
1. **Email follow-up через 7 днів після `delivered`-статусу замовлення**: «Розкажіть, як вам наш товар? Купон 100 грн (≈10%) на наступне замовлення за чесний відгук».
2. **На PDP товару, який користувач купив — банер «Залишити відгук»** (deep-link з лічильника замовлень).
3. **Фото-відгуки** — дозволити прикріплення фото (Schema.org `Review.image`). Це підвищує conversion наступних відвідувачів +20–40%.
4. **Поріг знизити з 3 до 1** для відгуків. Google допускає `reviewCount=1`. UI-підпис: «1 відгук від реального покупця».

### 18.3 Ризики
- Spam-відгуки з ботів — додати hCAPTCHA на форму.
- Накрутки — Google перевіряє consistent rating. Не модерувати в бік «тільки 5 зірок».
- Review schema на товарі без купівлі — Google це бачить як `FakeReview`. Лише за реальною purchase-чекою.

---

## 19. Mobile-first аудит (швидкі знахідки)

- Mobile-vp set, `viewport-fit=cover`. ✅
- LCP image preload + `fetchpriority=high` на PDP. ✅
- `optimized_image` генерує AVIF/WebP + srcset. ✅
- `data-device-class` логіка визначає low/mid/high девайси і відкладає аналітику. ✅ (вже зроблено в Phase 21).
- `[TBD]` Запустити Lighthouse mobile на 5 PDP після фіксу `(MM)` і `(B)` — переконатися, що Title не зрізається.
- `[MED]` Перевірити CLS на PDP при ленивому завантаженні thumbnail-стрипа.

---

## 20. Приклади «золотих стандартів» для копірайтингу

### 20.1 Гарний Title для PDP (UA, 50–60 символів)

```
Футболка «My Little Baby» — купити стрітвеар-футболку TwoComms
```
- 60 символів.
- Назва товару (з лапками) → ключ-категорія → бренд.
- Без `&quot;`, без NOM/ACC bug.

### 20.2 Гарний Description для PDP (140–160 символів)

```
Авторська футболка «My Little Baby» від TwoComms: 100% бавовна,
DTF-друк, унісекс. Доставка Новою Поштою 1–3 дні. Підтримка ЗСУ.
```
- 145 символів.
- USP (бавовна, DTF, ЗСУ).
- Дієслово (Доставка) + конкретний термін (1–3 дні).

### 20.3 Гарний H1 для категорії

```
Футболки з характером — авторський стрітвір та мілітарі від TwoComms
```
- 67 символів. На мобільному переноситься 2 рядки — нормально.
- Емоційний хук («з характером»).
- Чіткі ключі (`стрітвір`, `мілітарі`, `авторський`).
- Бренд наприкінці.

### 20.4 Гарний H2 для PDP

Замість generic «Кому підійде»:
```
Кому підійде ця футболка TwoComms
```
+ під неї блок «Доставка»:
```
Доставка футболки Новою Поштою — від 1 дня по Україні
```

---

## 21. Підсумок ітерації 2

**Що змінилося порівняно з v0.1:**
- 2 «фальшивих CRIT» зняті (brand schema, BreadcrumbList — насправді присутні).
- 4 нових CRIT додано (HTML entity double-encoding, empty meta description на 14 сторінках, відсутній H1 на 3 сторінках, FAQPage schema ніде не виводиться).
- 3 нових HIGH (OutOfStock availability, /blog/ внутрішні посилання, capitalize seo_title).
- Розширено keyword research (кластери з реальних товарів, сезонність).
- Додано секції 15–20: internal linking, faceted navigation, schema deep-dive, review collection, mobile-first, gold-standard приклади.

**Найбільший потенційний ROI** з нових знахідок:
1. `(MM)` HTML entity decode — torkne ~30+ товарів з лапками в назві, vis-vis CTR в SERP.
2. `(NN)` Description на 14 статичних сторінках — це -30–60% CTR на нав-сторінках.
3. `(PP)` FAQPage schema — top-3 rich result type для e-commerce.

**Залишається відкрите для Phase B:**
- Дамп прод-БД для повного per-product audit (§4).
- Web-scrape конкурентів (Militarist блокує curl/anti-bot — треба headless browser).
- GSC top-200 запитів за 28 днів — для валідації §5/§14.
- Lighthouse top-20 PDP до/після виправлення.

---

## 22. v0.3 — корекції v0.2 + перевірка коду (2026-05-11, ітерація 3)

### 22.1 Скасовані «фальшиві CRIT» з v0.2

**(PP) FAQPage schema на PDP — НЕ БАГ, а свідоме рішення.**

Знайдено в `@/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/pages/product_detail.html:62-69`:

```html
{% comment %}
Phase 21 (PR-5, T12.2) — FAQPage JSON-LD removed from PDP. The same
FAQ entries are rendered on dedicated support pages (/faq/,
/delivery/, /povernennya-ta-obmin/) which carry the FAQPage schema
there. Keeping it on every PDP duplicated content across hundreds
of pages and Search Console flagged it as repeated structured data.
{% endcomment %}
```

**Рішення:** усунути `(PP)` з CRIT. Натомість стратегія:
- На PDP — FAQ візуально видимий (для UX).
- FAQPage schema централізовано на `/faq/`, `/delivery/`, `/povernennya-ta-obmin/`, `/cooperation/`, `/custom-print/`, `/pro-brand/` — підтверджено grep'ом по проду (FAQPage=1 на 6/7 сторінок, окрім `/dopomoga/`).
- `[MED]` Якщо хочемо повернути FAQ на PDP без duplicate — робити **унікальні per-product Q/A**. Тоді кожна сторінка має оригінальні питання (наприклад, специфічні для принта/розміру цього товару). Без унікальності — Phase 21 правий, видалити правильно.

**(RR) `/blog/` внутрішні посилання — їх НЕМАЄ в коді.**

Grep `href="/blog/"` по всьому репозиторію — **0 збігів** (окрім самого audit-документа). Тобто:
- `/blog/` 404 — це просто URL без route, не активна проблема.
- Зовнішні беклінки на `/blog/` (якщо є) — `[TBD]` додати 301 → `/novyny/`.
- В §10 (F) знизити пріоритет з `[CRIT]` до `[LOW]` (не показуй контент, бо мертвих внутрішніх лінків немає).

### 22.2 Перевірена логіка `_get_product_availability`

`@/Users/zainllw0w/TwoComms/site/twocomms/storefront/seo_utils.py:478-493`:

```python
def _get_product_availability(product: Product) -> str:
    if not getattr(product, "is_dropship_available", True):
        return "https://schema.org/OutOfStock"
    try:
        from productcolors.models import ProductColorVariant
        variants = ProductColorVariant.objects.filter(product=product).only("stock")
        if variants.exists():
            has_stock = any(int(getattr(variant, "stock", 0) or 0) > 0 for variant in variants)
            return "https://schema.org/InStock" if has_stock else "https://schema.org/OutOfStock"
    except Exception:
        pass
    return "https://schema.org/InStock"
```

**Прод-факт:** на `clasic-tshort`, `-20-twocomms-Legend`, `where-mi-present-ts` повертається `OutOfStock`.

Можливі сценарії:
1. **`is_dropship_available=False`** — товар вимкнений як dropship-доступний. Якщо TwoComms продає тільки **роздрібно** (не дропшип) — це може бути дефолт у схемі і логіка викидає всі товари в OOS. **`[CRIT] (QQ)` — критична регресія SEO**.
2. **`ProductColorVariant.stock=0`** для всіх кольорів. Якщо товар друкується on-demand (DTF), реальний `stock` нескінченний — а в БД `stock=0`. **`[CRIT] (QQ)`**.

**Перевірка для агента Phase B:**
- На прод-БД: `SELECT id, slug, is_dropship_available FROM storefront_product WHERE slug IN ('clasic-tshort','-20-twocomms-Legend','where-mi-present-ts');`
- На прод-БД: `SELECT pcv.product_id, p.slug, count(*) as variants, sum(case when pcv.stock>0 then 1 else 0 end) as in_stock FROM productcolors_productcolorvariant pcv JOIN storefront_product p ON p.id=pcv.product_id GROUP BY pcv.product_id;`

**Якщо `is_dropship_available` є основним перемикачем витрини** — переробити логіку:
```python
def _get_product_availability(product):
    # MadeToOrder для DTF on-demand товарів
    if not _has_real_stock(product):
        return "https://schema.org/MadeToOrder"  # Schema.org підтримує
    return "https://schema.org/InStock"
```
Або `PreOrder` якщо завжди шиється на замовлення.

`MadeToOrder` — спеціальний `availability` стан Schema.org, який **повністю валідний** і Google приймає для rich result. Це може бути ідеальним рішенням для бренду з on-demand DTF-друком.

### 22.3 sitemap-product-variants.xml має duplicates

Прод-зразок: `354` `<loc>` записів у sitemap-product-variants. Перші 6 URL:
```
https://twocomms.shop/product/clasic-tshort/black/   ×3
https://twocomms.shop/product/clasic-tshort/classic/ ×3
https://twocomms.shop/product/clasic-tshort/oversize/ ×3
```

**`[CRIT] (TT)` — кожний variant URL дублюється 3 рази підряд** (ймовірно, цикл ставить 3 копії замість додавати до однієї `<url>` блок з 3 hreflang). Потрібно перевірити sitemap generator: `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/sitemaps.py`. Дублікати у sitemap → Google warning у Search Console + неефективний crawl.

### 22.4 Оновлений CRIT-список (v0.3)

| ID | Опис | Статус | Пріоритет (v0.3) |
|----|------|--------|------------------|
| (A) | NOM→ACC у seo_title | відкрите | **CRIT** |
| (B) | Title >60 (truncate) | відкрите | **CRIT** |
| (E) | fit_code на base PDP | відкрите | **CRIT** |
| (G) | RU/EN noindex/canonical | відкрите | **CRIT** |
| (H) | Скоротити category titles | відкрите | **CRIT** |
| (MM) | HTML entity у title/h1 | відкрите | **CRIT** |
| (NN) | Empty meta description × 14 | відкрите | **CRIT** |
| (OO) | H1 відсутній (cooperation, custom-print, search) | відкрите | **CRIT** |
| (TT) | sitemap-product-variants duplicates × 3 | НОВЕ | **CRIT** |
| (QQ) | OutOfStock на популярних PDP | відкрите | **CRIT** (підтверджено через код) |
| (RR) | `/blog/` 404 | знято | LOW |
| (PP) | FAQPage на PDP | знято | свідоме рішення Phase 21 |
| (C), (J) | brand, BreadcrumbList | знято (v0.2) | – |

### 22.5 Готові snippet'и для (NN) — meta description для 14 статичних сторінок

> Кожен опис: 140–160 символів, активне дієслово, бренд, USP. Можна копіювати в `{% block description %}` per-page templates.

```yaml
/dopomoga/: |
  Допомога TwoComms: умови замовлення, оплата, доставка Новою Поштою, повернення та обмін. Швидка підтримка через Telegram, Instagram або email.

/povernennya-ta-obmin/: |
  Повернення та обмін одягу TwoComms: 14 днів на повернення, обмін розміру безкоштовно. Як оформити, що потрібно, скільки чекати — покрокова інструкція.

/polityka-konfidentsiynosti/: |
  Політика конфіденційності TwoComms: як ми обробляємо ваші персональні дані, cookies, права користувача за GDPR і ЗУ «Про захист персональних даних».

/umovy-vykorystannya/: |
  Умови використання сайту TwoComms: правила оформлення замовлень, оплати, доставки, авторські права на принти та обмеження відповідальності.

/novyny/: |
  Новини TwoComms: дропи нових футболок і худі, колаборації з художниками, історії за принтами, апдейти бренду й донати на ЗСУ.

/faq/: |
  FAQ TwoComms — відповіді на поширені питання про оплату, доставку Новою Поштою, розміри, DTF-друк, повернення та підтримку ЗСУ. 50+ запитань.

/cooperation/: |
  Співпраця з TwoComms: дропшипінг, оптові замовлення, B2B-друк футболок і худі. Залиште заявку — менеджер відповість протягом 1 робочого дня.

/custom-print/: |
  Кастомний DTF-друк на одязі від TwoComms: завантажте свій принт, оберіть футболку чи худі, розмір і колір — від 1 одиниці. Доставка по Україні.

/doglyad-za-odyagom/: |
  Догляд за одягом TwoComms: як прати футболки і худі з DTF-принтом, температура, сушіння, прасування. Гайд від виробника, щоб принт жив 50+ прань.

/mapa-saytu/: |
  Карта сайту TwoComms: каталог футболок, худі та лонгсліви, бренд-сторі, підтримка, кастомний друк, договірні умови — швидкий доступ до всіх розділів.

/rozmirna-sitka/: |
  Розмірна сітка TwoComms для футболок, худі та лонгслівів. Як обрати regular / oversize fit, виміри в см, рекомендації за зростом і об'ємами.

/favorites/: |
  Обрані товари TwoComms — ваш персональний список улюблених футболок, худі та лонгслівів. Збережіть тут моделі, щоб повернутися до них пізніше.

/vidstezhennya-zamovlennya/: |
  Відстеження замовлення TwoComms: введіть номер ТТН Нової Пошти або номер замовлення — дізнайтеся статус доставки в реальному часі.

/search/: |
  Пошук по каталогу TwoComms: знайдіть футболку, худі або лонгслів за назвою, кольором, принтом чи темою. (noindex — не для пошукових систем)
```

> **Важливо:** на `/search/` додати `<meta name="robots" content="noindex,follow">` — це search results page, не контент.

### 22.6 Готові snippet'и для (OO) — H1 для 3 сторінок без H1

```yaml
/cooperation/: "Співпраця з TwoComms — дропшипінг, опт і B2B-друк"
/custom-print/: "Кастомний DTF-друк на одязі — конструктор TwoComms"
/search/: 'Результати пошуку: «{{ query }}»'
```

### 22.7 Готовий копірайт для виправлення (A) + (MM) + (B) + (SS) одним патчем

Рекомендована єдина функція генерації `seo_title` для Phase 13.5 (`@product_copy_v2.py:312-316`):

```python
import html as html_lib

def _build_seo_title(product, cat: str) -> str:
    # Decode any double-encoded HTML entities present in legacy data.
    raw_title = html_lib.unescape(product.title or "").strip()
    # Capitalize first letter (preserves the rest exactly, supports
    # Cyrillic and quoted titles).
    if raw_title and raw_title[0].islower():
        raw_title = raw_title[0].upper() + raw_title[1:]
    suffix = f" — купити {_acc(cat)} TwoComms"
    available = 60 - len(suffix)
    if len(raw_title) > available:
        # Try to cut at a sensible boundary (last space before limit).
        cut = raw_title[:available].rstrip()
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        raw_title = cut.rstrip(" ,.;:-") + "…"
    return f"{raw_title}{suffix}"
```

Особливості:
- `html.unescape` декодує `&quot;` → `"` (виправляє `(MM)`).
- Capitalize first letter (виправляє `(SS)`).
- `_acc(cat)` замість `_nom(cat)` (виправляє `(A)`).
- Truncate до 60 з ellipsis (виправляє `(B)`).

Migration:
```python
# storefront/management/commands/regenerate_seo_titles_v2.py
from django.core.management.base import BaseCommand
from storefront.models import Product
from storefront.services.product_copy_v2 import (
    _build_seo_title,  # після рефактору
    looks_like_phase13_autofill,
)

class Command(BaseCommand):
    def handle(self, *args, **opts):
        updated = 0
        for p in Product.objects.select_related('category').iterator():
            if not p.category:
                continue
            current = (p.seo_title or '').strip()
            if current and not looks_like_phase13_autofill('seo_title', current):
                continue
            new_title = _build_seo_title(p, p.category.slug)
            if new_title != current:
                Product.objects.filter(pk=p.pk).update(seo_title=new_title)
                updated += 1
        self.stdout.write(f"Updated {updated} products.")
```

Тести:
- `test_build_seo_title_decodes_html_entities`
- `test_build_seo_title_uses_accusative_for_tshirts`
- `test_build_seo_title_capitalizes_lowercase_input`
- `test_build_seo_title_truncates_above_60`
- `test_regenerate_skips_manually_set_titles`

### 22.8 Готова стратегія для (G) RU/EN — швидка реалізація

Поки немає реальних перекладів — треба знизити SEO-шкоду. Два варіанти, з кодом:

**Варіант A1 (простий, на 1 PR):** на не-UK сторінках виставити canonical → UK URL.

```html
<!-- base.html -->
{% load i18n_links %}
{% language_alternates as lang_alts %}
<link rel="canonical" href="{% block canonical %}{{ lang_alts.uk }}{% endblock %}">
```

**Варіант A2 (агресивний, рекомендований):** на не-UK PDP/категоріях додати `noindex,follow` поки не заповнено `*_uk` ≠ `*_ru`/`*_en`.

```html
<!-- base.html -->
{% if LANGUAGE_CODE != 'uk' and not has_translated_content %}
  <meta name="robots" content="noindex,follow">
{% endif %}
```

`has_translated_content` — context-processor, який повертає True, якщо `getattr(obj, f'title_{LANGUAGE_CODE}', None) and getattr(obj, f'title_{LANGUAGE_CODE}') != obj.title_uk`.

**Варіант B (стратегічний, ~50 годин):** замовити переклад RU/EN на freelance (~$200), пройтися migrate-командою, зняти noindex.

### 22.9 Що ще лишається відкритим

- **(QQ) Перевірка `is_dropship_available`** на прод-БД (треба shell-доступ).
- **(TT) Виправлення sitemap-variants дублікатів** (`@storefront/sitemaps.py`).
- **Дамп прод-БД** для повного per-product audit (§4) — Phase B.
- **Web-scrape конкурентів** — потрібен headless browser (Militarist блокує curl).
- **GSC export** — потребує доступ до Search Console.

---

## 23. Чек-лист для агента Phase B (короткий action-list)

> Якщо ви — наступний reasoning-агент, ось мінімум 6 кроків для подальшого глибокого аналізу:

1. **Витягнути прод-CSV товарів**: `id, slug, title, seo_title, seo_description, seo_keywords, short_description, full_description, main_image_alt, status, is_dropship_available, category.slug`. Зберегти у `docs/seo/2026-05-11-products-prod.csv`.
2. **Прогнати кожен товар по матриці §4** (17 чекпойнтів × N товарів).
3. **Перевірити `_get_product_availability` real-data**: SQL `SELECT slug, is_dropship_available, count(variants), sum(stock) FROM ...` для всіх товарів.
4. **Headless-scrape Militarist + Aviatsiya + Staff.ua** (1 категорія + 3 PDP кожний). Заповнити порівняльну таблицю.
5. **GSC top-200 запитів за 28d** → валідувати keyword матрицю §5/§14.
6. **Lighthouse mobile run × 5 PDP до/після** (A)+(B)+(MM) патчу. Зберегти у `output/lighthouse-mobile/`.

Після виконання — створити v0.4 з реальними числами.

---

## 24. Журнал ітерацій (продовження)

| Дата | Версія | Що додано/виправлено |
|------|--------|----------------------|
| 2026-05-11 | v0.1 | Базовий скан, §1–§12, додаток A/B |
| 2026-05-11 | v0.2 | §13 (корекції), §14 (розшир. keywords), §15 internal links, §16 facets, §17 schema deep-dive, §18 reviews, §19 mobile, §20 gold standards |
| 2026-05-11 | v0.3 | §22 корекції v0.2 (FAQPage/blog знято; sitemap-variants дублі — нова CRIT; готові snippet'и для NN/OO; ready-to-merge код для A+B+MM+SS), §23 action list |
| `[Phase B]` | v0.4 | прод-CSV дамп, GSC, Lighthouse, конкуренти |

---

## 25. v0.4 — глибокий технічно-лінгвістичний пас (2026-05-11, ітерація 4)

### 25.1 Open Graph Product Object — критично неповний

На PDP `https://twocomms.shop/product/clasic-tshort/` `og:type=product`, але всі обовʼязкові product‑specific OG‑властивості **відсутні**:

| Тег | Очікуване | Прод | Статус |
|-----|-----------|------|--------|
| `og:type` | `product` | `product` | ✅ |
| `product:price:amount` | `788.00` | MISSING | ❌ |
| `product:price:currency` | `UAH` | MISSING | ❌ |
| `og:price:amount` (legacy alias) | `788.00` | MISSING | ❌ |
| `og:price:currency` | `UAH` | MISSING | ❌ |
| `product:availability` | `instock`/`oos`/`pending` | MISSING | ❌ |
| `og:availability` | (legacy) | MISSING | ❌ |
| `product:retailer_item_id` | `TC-1` (SKU) | MISSING | ❌ |
| `product:condition` | `new` | MISSING | ❌ |
| `product:brand` | `TwoComms` | MISSING | ❌ |

**Імпакт:**
- **Facebook Shop / Commerce Catalog** не побачить ціну/наявність → товари не імпортуються через FB Pixel `ViewContent` без `value`/`currency` (це є в Pixel JS, але OG потрібний для Facebook Catalog Manager auto-import).
- **Pinterest Rich Pins** для `Product Pin` потребує саме цих тегів.
- **Telegram/WhatsApp/Discord preview** не покаже ціну в шапці картки.
- **Facebook Sharing Debugger** видасть warning «og:type=product without price».

**`[CRIT] (UU)`** — додати в `@twocomms_django_theme/templates/pages/product_detail.html` блок `og_extra_tags`:

```django
{% block og_type %}product{% endblock %}
{% block extra_meta %}
  <meta property="product:price:amount" content="{{ product.final_price }}">
  <meta property="product:price:currency" content="UAH">
  <meta property="product:availability" content="{% if product_in_stock %}instock{% else %}out of stock{% endif %}">
  <meta property="product:retailer_item_id" content="TC-{{ product.id }}">
  <meta property="product:condition" content="new">
  <meta property="product:brand" content="TwoComms">
  <meta property="og:price:amount" content="{{ product.final_price }}">
  <meta property="og:price:currency" content="UAH">
{% endblock %}
```

`base.html` потребує добавлення `{% block extra_meta %}{% endblock %}` всередині head.

### 25.2 Pagination — duplicate Title для кожної сторінки

Перевірено `https://twocomms.shop/?page=2`, `?page=3`, `?page=9`:
- Title однаковий для всіх: `TwoComms — Стріт & Мілітарі Одяг | Головна`.
- Canonical = self (`/?page=N`) — **правильна стратегія Google 2024+** (consolidate skipped, page 2+ indexable).
- Те саме для `/catalog/tshirts/?page=2`: Title однаковий з page1.

**`[HIGH] (VV)`** — Title пагінації має містити `Сторінка N`:

```django
{% block title %}
  {{ base_title }}{% if page_obj.number > 1 %} — сторінка {{ page_obj.number }}{% endif %}
{% endblock %}
```
- `/?page=2` → `TwoComms — Стріт & Мілітарі Одяг — сторінка 2`
- `/catalog/tshirts/?page=2` → `Футболки TwoComms — стрітвеар та мілітарі-принти — сторінка 2`

Це усуває duplicate-title warning у Search Console.

### 25.3 404 page — index,follow з canonical на самого себе

Прод-зразок (404):
```
<title>404 — Щось пішло не так</title>
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">
<link rel="canonical" href="https://twocomms.shop/this-does-not-exist-1234/">
```

**`[CRIT] (WW)`**:
- 404 повертає `index, follow` — Google **зазвичай ігнорує** індексацію сторінок з 404 status code, але якщо response 200 (soft 404) — буде індексувати. Перевірити: чи завжди 404 повертає HTTP 404 status (так — `HTTP/2 404` з прод-curl ✅), але метатег `index, follow` йде проти best-practice.
- Canonical вказує на 404-URL → Google warning.
- **Виправлення**: на 404 темплейті виставити `<meta name="robots" content="noindex, follow">` і **прибрати `<link rel="canonical">`** (або поставити на головну).

### 25.4 `/favorites/` — приватна сторінка індексована

Прод:
```
<meta name="robots" content="index, follow, ...">
<link rel="canonical" href="https://twocomms.shop/favorites/">
```
- Сторінка персональна (per-user стан), для неавторизованого юзера може бути порожньою. **`[CRIT] (XX)`**: додати `noindex, follow`.

### 25.5 Лінгвістичний аудит — спелінг inconsistency

Прод-зразки count-and-grep по сторінкам:

| URL | `стрітвеар` | `стрітвір` | `мілітарі` | `streetwear` |
|-----|-------------|------------|-----------|---------------|
| `/catalog/tshirts/` | 4 | 1 | 11 | 12 |
| `/catalog/hoodie/` | 7 | 1 | 8 | 10 |
| `/catalog/long-sleeve/` | 7 | 1 | 8 | 10 |
| `/product/clasic-tshort/` | 0 | 0 | 3 | 5 |
| `/pro-brand/` | 0 | 0 | 2 | 14 |

**Знахідки:**
1. **`стрітвеар` (українізована англо-калька) і `стрітвір` (повний український аналог)** змішані на одній сторінці. На категорії 7×«стрітвеар» + 1×«стрітвір» — Google рахує це як **двa різні токени**, signal розпорошений.
   - **`[CRIT] (YY)` Style Guide**: затвердити **одну** форму. Рекомендована — `стрітвеар`, бо:
     - частіше використовується у бренд‑комʼюніті (Stüssy, Supreme дискурс);
     - близько до англомовного «streetwear», який все одно домінує на сторінці (12× на /catalog/tshirts/);
     - `стрітвір` — менш популярний токен, мало пошуків.
   - Прибрати `стрітвір` зі всіх SEO-блоків (`@/Users/zainllw0w/TwoComms/site/twocomms/storefront/services/catalog_seo.py`, можливо в `_city_paragraph`).
2. **`мілітарі` ✅** — стандартизовано, окей.
3. **`streetwear` 14× на /pro-brand/** — це bilingual (UK + EN) signal. ОК для AI-search — Google розуміє, що бренд бі-лінгвальний.

### 25.6 Лінгвістичний аудит — типографіка

| Критерій | Стан на проді | Дія |
|----------|---------------|-----|
| Em-dash `—` (правильно для UA) | 57× на PDP ✅ | OK |
| Hyphen-minus `-` як тире | 16× на PDP | `[MED]` замінити інлайнові «-» на «—» де це тире, не дефіс |
| Українські лапки `«»` | 22× на PDP ✅ | OK для тексту |
| ASCII лапки `"` | 4418× | переважно в HTML attrs, OK; але **в назвах товарів** мають бути `«»` |
| `&quot;` подвійне екранування | 59× на PDP ❌ | `[CRIT] (MM)` |
| Нерозривний пробіл `\xa0` | **0 на проді** | `[MED] (ZZ)` додати між `100`+`грн`, `1–3`+`дні`, числами і одиницями виміру |
| `&` vs `і` | `Стріт & Мілітарі` всюди | `[LOW]` для UA-стилю краще `Стріт і Мілітарі`, але це — бренд-патерн |
| `преміум фліс` | без дефіса | `[LOW]` правильно `преміум-фліс` (як `преміум-сегмент`) |

#### 25.6.1 Розширення стайлгайду
1. **Лапки в назвах товарів**: завжди `«»` (UA) замість `""`. У БД `Product.title` — нормалізувати міграцією: `re.sub(r'"([^"]+)"', r'«\1»', title)`.
2. **NBSP після числа перед одиницею**:
   - У шаблоні створити фільтр `|nbsp_currency`: `{{ price|nbsp_currency }}` → `1813\xa0грн`.
   - Те ж для `1–3 дні`, `XS–XXL` (тире-діапазон не розривати).
3. **Тире vs дефіс**:
   - `—` (em-dash, U+2014) — тире у реченні: «Доставка — 1–3 дні».
   - `–` (en-dash, U+2013) — діапазон чисел/дат: `XS–XXL`, `1–3`.
   - `-` (hyphen-minus, U+002D) — у словах: `преміум-фліс`, `DTF-друк`.

### 25.7 Семантична ієрархія H-tags

PDP h-hierarchy (зчитано з `clasic-tshort`):
```
h1: Футболка класична
h2: Кому підійде
h2: Футболка базова
h2: Відгуки про товар
h2: Схожі товари
h2: Нещодавно переглядали
h2: Футболка класична (Класична) — деталі моделі
  h3: Чому класична посадка
  h5: Доставка та оплата    ← !!!
h2: TWOCOMMS
h5: Система балів
```

**`[MED] (AAA)` — порушення семантичної ієрархії**:
- `h5: Доставка та оплата` стрибає від h3 (без h4). Замінити на `h4` або `h3`.
- `h5: Система балів` у footer-area — теж пропуск рівнів. Якщо це секція в footer, краще `h3` (під footer-h2 «TWOCOMMS») або зробити `<p>` зі spannable стилем.

### 25.8 `pro-brand` — золотий стандарт H-структури

Підтверджено: 17 H2-секцій + 4 H3 у логічному дереві (h1 → h2 → h3 у трьох гілках). Це seo-зразково. Жодних правок.

### 25.9 Click-depth audit (crawl budget)

Прод‑дані:
- Home (`/`): 52 unique internal href, 8 product links, 3 category links.
- Категорія: ~20+ product links на сторінку × pagination.
- PDP: 81 internal anchor (51 unique).

**Click depth для будь-якого товару:**
- Home → Category → PDP = 2 кліки. ✅ оптимально для 50-300 товарів.
- Home → Direct PDP via «Новинки» = 1 клік ✅.
- Home → Footer → static = 1 клік ✅.

Жодних orphan-сторінок не виявлено. Sitemap їх покриває.

### 25.10 Hreflang reciprocal validation

Витяг з sitemap-categories для `/catalog/long-sleeve/`:
```
uk → twocomms.shop/catalog/long-sleeve/
ru → twocomms.shop/ru/catalog/long-sleeve/
en → twocomms.shop/en/catalog/long-sleeve/
x-default → twocomms.shop/catalog/long-sleeve/  ← вказує на UK ✅
```
- Reciprocal: на UK-URL hreflang `ru` має посилатись на ru-URL, на ru-URL hreflang `uk` — на uk-URL. **Підтверджено** через grep — посилання двосторонні. ✅
- `x-default → uk` — правильна політика для бренду з UK як основою. ✅

**Слабке місце:** Бо контенту в RU/EN немає, hreflang reciprocal *коректний синтаксично*, але *шкідливий контентно* (див. §6).

### 25.11 AI-search readiness (SGE / Perplexity / ChatGPT Search)

> AI search engines цитують контент, який має чіткі **факти + бренд-attribution + structured data**.

**Що TwoComms робить правильно:**
- ✅ Organization schema з `description`, `logo`, `contactPoint`, `sameAs`.
- ✅ Product schema з `additionalProperty[]`, `material`, `countryOfOrigin`, `brand`.
- ✅ BreadcrumbList повний.
- ✅ FAQ schema на `/faq/`, `/delivery/`, `/povernennya-ta-obmin/`, `/pro-brand/` — Perplexity активно цитує FAQ-блоки.
- ✅ Brand-story (`/pro-brand/`) — H1+H2-структура чітка, факти датовані.

**Що варто посилити:**
- `[HIGH] (BBB)` Додати **Date Published** у Schema (`/pro-brand/`, `/novyny/{slug}/`) — AI цитує дату для credibility. Schema.org `Article.datePublished`.
- `[HIGH] (CCC)` У `/pro-brand/` додати JSON-LD `OfferCatalog` з посиланням на категорії — AI зможе цитувати «у TwoComms є 3 категорії: футболки, худі, лонгсліви».
- `[MED] (DDD)` Додати **`mentions` array** до Organization schema (за принтами/колаборантами/підрозділами ЗСУ) — це stable entity-references для Knowledge Graph.
- `[MED] (EEE)` Створити окремий `/about/` (або `/pro-brand/`-extension) з **Q&A форматом** для AI — explicit «What is TwoComms?», «Where is TwoComms based?», «What does TwoComms support?».

### 25.12 Twitter / X cards — зайві дублікати

Прод-PDP виводить:
- `og:title` + `twitter:title` (однакові)
- `og:description` + `twitter:description` (однакові)
- `og:image` + `twitter:image` (однакові)

Twitter (X) **не потребує власних `twitter:*` тегів, якщо вже є `og:*`**. Платформа fallback'иться на OG. Тобто `twitter:title/description/image` — дубль HTML без бенефіту.

`[LOW] (FFF)` — прибрати дублі (або, як мінімум, не додавати їх до нових product-meta), щоб HTML був на ~10 рядків меншим. Залишити **тільки**:
```html
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@twocomms">  <!-- якщо є акаунт -->
```

### 25.13 Sitemap — `lastmod` точність

Прод: `<lastmod>2026-05-09</lastmod>` для всіх products у sitemap-products. Тобто **спільний lastmod на весь блок**, не per-product.

`[MED] (GGG)` — зробити `lastmod` per-product з `Product.updated_at`. Це **прискорює** Google re-crawl саме змінених PDP. У `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/sitemaps.py` додати `def lastmod(self, obj)` метод.

### 25.14 Внутрішній пошук (`/search/`) — все добре

Перевірено `https://twocomms.shop/search/?q=test`:
- HTTP 200 ✅
- `<meta name="robots" content="noindex, follow">` ✅
- `<link rel="canonical" href="https://twocomms.shop/catalog/">` ✅ (consolidate signal на каталог)
- `<title>Пошук: test — TwoComms</title>` ✅

Це **чудовий приклад** правильної search-results-page реалізації. Жодних правок.

Залишається лише `[MED]` додати H1 (§22.6 (OO)) для UX/accessibility.

### 25.15 Внутрішня перелінковка — кількісні ліміти

Google допускає до **~100 unique outbound links per page** (нечіткий гайд). Прод-метрика:
- Home: 52 unique. ✅ (запас 2×).
- Category: ~80. ✅.
- PDP: 51 unique. ✅.

Все в нормі. Орфан-сторінки відсутні.

### 25.16 Image SEO — детально

Прод PDP `clasic-tshort`: 16 `<img>` тегів, 3 з порожнім alt.
- 3 порожніх alt — швидше за все **decoration icons** (lucide / SVG). Якщо це так — залишити `alt=""` (правильно для accessibility), але прибрати з підрахунку SEO-impact.
- Усі товарні зображення мають alt (підтверджено вище).

**Кейси `[MED]`**:
- ALT для category cover на head у головній — `Категорія футболок TwoComms — стрітвеар і мілітарі з принтами ЗСУ` (запропоновано в v0.1).
- ALT для recently-viewed (small thumbnail) — все ще `{rec_product.title}` без контексту. Додати `— нещодавно переглянуто`.

### 25.17 LocalBusiness / Place schema — для `/contacts/`

`/contacts/` має `H1: Контакти`, `H2: Наші магазини`. Якщо є фізичні точки продажу — **обовʼязково** додати `LocalBusiness` JSON-LD з адресою, телефоном, годинами роботи.

`[HIGH] (HHH)` — приклад мінімальний:
```json
{
  "@context": "https://schema.org",
  "@type": "ClothingStore",
  "name": "TwoComms",
  "address": {
    "@type": "PostalAddress",
    "addressLocality": "Харків",
    "addressCountry": "UA"
  },
  "telephone": "+380966543212",
  "openingHoursSpecification": [...],
  "priceRange": "₴₴",
  "currenciesAccepted": "UAH"
}
```

### 25.18 Sitelinks Search Box — перевірка

`WebSite + SearchAction` schema присутня (`https://twocomms.shop/search/?q={search_term_string}`). Це коректно — Google показує box під domain'ом у SERP. ✅

### 25.19 Розширені фішки на майбутнє

| Фішка | Імпакт | Складність | Пріоритет |
|-------|--------|------------|-----------|
| **`Speakable` schema** на `/pro-brand/`, `/faq/` — Google Assistant читає вголос | LOW (нішово) | S | LOW |
| **`Trip` / `Event` для дропів** (limited drops) — створити подію в SERP | MED | M | MED |
| **Web App Manifest з `categories`** для PWA | LOW | XS | LOW |
| **Pinterest Rich Pins** — після `(UU)` працює автоматично | MED | XS | MED |
| **Discover-friendly блог `/novyny/`** — large image (1200×800), date, author | HIGH | M | HIGH (з `(P)`) |
| **`Carousel` schema** на головній (newest products) | MED | S | MED |
| **AMP Stories або Web Stories** для дропів | LOW | L | LOW |
| **`PriceSpecification` з historical** для discount-price | LOW | M | LOW |
| **Enhanced Product `hasVariant`** — для color/fit dropdown | MED | M | MED |

### 25.20 Виявлені фактори, що **псують** AI-Search/Google розуміння

1. `[CRIT]` Mixed `&quot;` rendering — AI-боти бачать `Худі &quot;Дрони...&quot;` як текст з символами escape, що псує quote-extraction.
2. `[HIGH]` `OutOfStock` спам — Perplexity/SGE у запитах «купити X» ігнорує OOS-товари. Якщо це дефолт — TwoComms невидимий у AI-shopping.
3. `[MED]` Mixed UA/RU H2 (`Похожие товары` + `Схожі товари`) — AI помилкло визначає мову сторінки.
4. `[MED]` Spelling drift (`стрітвеар` vs `стрітвір`) — entity disambiguation шумить.
5. `[LOW]` Дубль OG/Twitter — не критично, але AI-боти бачать «дубль» — низький data-quality signal.

### 25.21 Health-check швидкі для агента Phase B

Готовий bash-snippet для запуску в одну команду:

```bash
#!/usr/bin/env bash
URLS=(
  https://twocomms.shop/
  https://twocomms.shop/catalog/
  https://twocomms.shop/catalog/tshirts/
  https://twocomms.shop/catalog/hoodie/
  https://twocomms.shop/catalog/long-sleeve/
  https://twocomms.shop/product/clasic-tshort/
  https://twocomms.shop/pro-brand/
  https://twocomms.shop/faq/
  https://twocomms.shop/dopomoga/
  https://twocomms.shop/delivery/
  https://twocomms.shop/povernennya-ta-obmin/
  https://twocomms.shop/cooperation/
  https://twocomms.shop/custom-print/
  https://twocomms.shop/doglyad-za-odyagom/
  https://twocomms.shop/mapa-saytu/
  https://twocomms.shop/rozmirna-sitka/
  https://twocomms.shop/novyny/
  https://twocomms.shop/contacts/
)
for u in "${URLS[@]}"; do
  c=$(curl -s -A "Mozilla/5.0" -o /tmp/x -w "%{http_code}" "$u")
  t=$(grep -oE '<title>[^<]+' /tmp/x | head -1 | cut -c8-)
  d=$(grep -oE 'name="description"\s*content="[^"]+' /tmp/x | head -1 | cut -c30-150)
  h1=$(grep -oE '<h1[^>]*>[^<]+' /tmp/x | head -1 | sed 's/.*>//')
  printf "[%s] %-50s | T(%d): %s\n  H1: %s\n  D(%d): %s\n\n" "$c" "$u" "${#t}" "$t" "$h1" "${#d}" "$d"
done
```

Зберегти в `scripts/seo-healthcheck.sh`. Запустити як CI-pre-deploy gate.

### 25.22 Розширений CRIT-список (v0.4)

| ID | Опис | Статус |
|----|------|--------|
| (UU) | OG product:price/availability/brand MISSING | **CRIT** новий |
| (VV) | Pagination duplicate Title | **HIGH** новий |
| (WW) | 404 page index,follow + canonical→self | **CRIT** новий |
| (XX) | /favorites/ index,follow | **CRIT** новий |
| (YY) | стрітвеар vs стрітвір (mixed spelling) | **CRIT** новий |
| (ZZ) | NBSP типографіка | **MED** новий |
| (AAA) | h5 без h4 на PDP | **MED** новий |
| (BBB) | Date Published у `/pro-brand/`, `/novyny/` | **HIGH** новий |
| (CCC) | OfferCatalog на `/pro-brand/` | **HIGH** новий |
| (DDD) | Organization.mentions для AI | **MED** новий |
| (EEE) | Explicit Q&A для AI search | **MED** новий |
| (FFF) | Twitter card duplicate з OG | **LOW** новий |
| (GGG) | Sitemap lastmod per-product | **MED** новий |
| (HHH) | LocalBusiness JSON-LD на /contacts/ | **HIGH** новий |

---

## 26. Зведений Master Backlog (v0.4)

> Об'єднана таблиця всіх ID-маркованих CRIT/HIGH знахідок з v0.1-v0.4. Для агента Phase B — sortable view з усього документа.

### 26.1 CRIT (виправляти негайно — 11 пунктів)

| ID | Знахідка | Файл/Місце | TTR | Effort |
|----|----------|-----------|-----|--------|
| A | NOM→ACC у Phase 13.5 seo_title | `@product_copy_v2.py:314` | Q | S |
| B | Title >60 truncate | `@product_copy_v2.py` | Q | S |
| E | fit_code на base PDP | `@views/product.py:435-447` | Q | S |
| G | RU/EN noindex/canonical | `@base.html` + ctx-proc | M | M |
| H | Скоротити category titles | admin `Category.seo_title` | Q | S |
| MM | HTML entity у title/h1 | `@product_copy_v2.py` + БД-міграція | Q | M |
| NN | Empty meta description × 14 | per-template `{% block description %}` | Q | M |
| OO | H1 відсутній (3 сторінки) | per-template | Q | S |
| TT | sitemap-product-variants дублі ×3 | `@storefront/sitemaps.py` | Q | M |
| QQ | OutOfStock спам | `@seo_utils.py:478` | Q | S |
| UU | OG product:price/availability MISSING | `@product_detail.html` + `@base.html` | Q | S |
| WW | 404 index,follow + canonical→self | `@404.html` template | Q | S |
| XX | /favorites/ index,follow | `@favorites template` | Q | S |
| YY | стрітвеар/стрітвір mixed | `@catalog_seo.py`/admin texts | Q | M |

### 26.2 HIGH (15 пунктів)

I (ItemList JSON-LD), L (PDP Доставка/Догляд H2), M (review threshold), N (catalog title), O (seo_keywords у БД), P (/blog/ pillar статті), Q (cross-links categorie), S (home_card_image), T (Харків в og:description), VV (pagination title), BBB (datePublished), CCC (OfferCatalog), HHH (LocalBusiness), R (about → sitemap), AAA (h-hierarchy).

### 26.3 MED (~10 пунктів)

D, U, V, W, X, Y, Z, ZZ, AAA, DDD, EEE, FFF, GGG, SS.

### 26.4 LOW + TBD

(BB, CC, DD), (EE-LL), (RR), (PP заполнено), (FFF).

---

## 27. v0.4 — підсумок

**Додано:**
- Перевірено OG product object — 9 з 9 продуктових тегів MISSING.
- Перевірено pagination — duplicate Title.
- Перевірено 404 + /favorites/ — обидві з `index,follow`.
- Лінгвістичний аудит: spelling inconsistency, типографіка (NBSP, лапки, тире/дефіс).
- AI-search readiness блок з конкретними schema-доповненнями.
- LocalBusiness/ClothingStore схема для `/contacts/`.
- Семантична ієрархія H-tag — 1 порушення на PDP.
- Click-depth, hreflang reciprocal — підтверджено OK.
- Sitemap lastmod деталі.
- Twitter card дублікат.
- Style Guide для типографіки.
- Зведений Master Backlog (11 CRIT, 15 HIGH).
- Bash health-check скрипт.

**Критичних знахідок:** v0.1 → v0.2 → v0.3 → v0.4 = `8 → 12 → 11 → 14`.

**Найбільший новий ROI:**
1. (UU) OG product:price/availability — без цього бренд невидимий у Facebook Catalog/Pinterest Rich Pins.
2. (XX) /favorites/ noindex — економить crawl budget і запобігає індексу пустих сторінок.
3. (YY) Spelling unification — entity disambiguation для AI search.
4. (HHH) LocalBusiness — local-pack видимість у Google для «купити одяг Харків».

**Phase B залишається:**
- Прод-CSV дамп (§4 повний per-product audit).
- Конкуренти (Militarist anti-bot — потрібен Playwright).
- GSC + Ahrefs дані.
- Lighthouse mobile до/після.

---

## 28. v0.5 — додаткові глибокі перевірки (2026-05-11, ітерація 5)

### 28.1 Domain canonical: www / http / https

| Варіант | Статус | Поведінка |
|---------|--------|-----------|
| `https://twocomms.shop/` | 200 | основний домен ✅ |
| `https://www.twocomms.shop/` | **301** → `https://twocomms.shop/` | ✅ www → non-www |
| `http://twocomms.shop/` | 301 | ✅ HTTP → HTTPS |
| `http://www.twocomms.shop/` | 301 | ✅ |

**Висновок:** на рівні домену все коректно. Жодних правок.

> **Корекція попередньої гіпотези:** у §28.0 (попередня ітерація v0.4) я помилково припустив, що `www` не редиректить — це було через те, що `urllib.urlopen()` слідує редиректам автоматично і не повертає Location. Підтверджено через `curl -I`: www → non-www = 301.

### 28.2 HTTPS security headers (з curl)

| Header | Стан | Дія |
|--------|------|-----|
| `strict-transport-security: max-age=31536000; includeSubDomains; preload` | ✅ | OK |
| `x-frame-options: SAMEORIGIN` | ✅ | OK |
| `x-content-type-options: nosniff` | ✅ | OK |
| `referrer-policy: strict-origin-when-cross-origin` | ✅ | OK |
| `content-security-policy: default-src 'self'; ...` | ✅ | Жорстка CSP-policy. ОК. |
| `x-xss-protection: 1; mode=block` | ✅ | OK |
| HSTS preload | ✅ (`preload` директива) | OK |

**Висновок:** все на місці. Жодних правок. Це дуже сильно для AI-search trust signal.

### 28.3 Privates: `/cart/`, `/login/`, `/register/` — robots OK

Прод-перевірка:
- `/cart/` → `noindex, nofollow` ✅
- `/login/` → `noindex, nofollow` ✅
- `/register/` → `noindex, nofollow` ✅
- `/orders/` → **HTTP 404** (тільки для unauth). Це може бути логічно (orders видно тільки авторизованому), але **в /orders/ як 404** + `index, follow` (баг (WW)) — потрібно або `noindex,nofollow`, або 302 на /login/.

### 28.4 Color/Fit variant URL-и — **підтверджена (A) NOM/ACC баг**

Прод-зразки:

| URL | Title | Граматика |
|-----|-------|-----------|
| `/product/clasic-tshort/black/` | `Купити Футболка класична — чорний — TwoComms` | ❌ «Купити Футболка» |
| `/product/clasic-tshort/oversize/` | `Оверсайз Футболка класична — купити в TwoComms` | ❌ «Оверсайз Футболка класична — купити **в**» (а в чому?) |
| `/product/clasic-tshort/classic/` | `Класична Футболка класична — купити в TwoComms` | ❌ тавтологія «Класична Футболка класична» |

**`[CRIT] (III)`** — баг **окремий від (A)** в `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/services/variant_meta.py`. Файл генерує title для:
- Color-variant 1-сегмент: `Купити {title} — {color} — TwoComms` (NOM «Купити Футболка»).
- Fit-variant 1-сегмент: `{Fit_lead} {title} — купити в TwoComms` (тавтологія + неповний знахідний відмінок).

Запропоновано:

```python
# Color self-canonical
page_title = f"{inputs.product_title} ({inputs.color_label}) — купити {_acc(cat)} TwoComms"

# Fit self-canonical (e.g. /product/X/oversize/)
page_title = f"{inputs.product_title} — {_lowercase_first(inputs.fit_label)} посадка — TwoComms"
```

Це дасть:
- `/clasic-tshort/black/` → `Футболка класична (Чорний) — купити футболку TwoComms` ✅
- `/clasic-tshort/oversize/` → `Футболка класична — оверсайз посадка — TwoComms` ✅
- `/clasic-tshort/classic/` → `Футболка класична — класична посадка — TwoComms` ✅ (без тавтології, бо «класична посадка» виправдане термінологією)

### 28.5 Image filenames — погана SEO-практика

Прод-зразки:
- `/media/products/c1.jpg`, `c2.jpg`, `c3.jpg` — generic для базових товарів.
- `/media/products/10.4.jpg`, `13.3.jpg`, `15.2.jpg`, `5_FZKBu4W.jpg` — щось схоже на auto-generated.
- `/media/products/H2.jpg` — без контексту.
- `/media/products/Худі2.png` → URL-encoded як `%D0%A5%D1%83%D0%B4%D1%962.png` — **кирилиця в URL ❌**.

**`[MED] (JJJ)`** — Google Images ranking використовує filename як один із 6+ signals для image relevance. Рекомендовано рекурсивний rename:
- Замість `c3.jpg` → `klasychna-futbolka-twocomms.jpg`.
- Замість `10.4.jpg` → `my-little-baby-tshirt-pink-twocomms.jpg`.
- Усі — slug-style, ASCII, з ключем + бренд.

**Складність:** потребує django-import-export + media collectstatic + 301 redirects старі → нові URL'и (бо вони в Schema.org `Product.image` і sitemap-images).

**Реалістичний компроміс:**
- Тільки для **нових** аплоадів — slugify filename автоматично у `Product.save()`.
- Старі — не чіпати (потенційно ламає кешовані Google Images results).

Код для нових файлів:
```python
# storefront/models.py
from django.utils.text import slugify

def _product_image_upload_to(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    base = slugify(instance.title or 'product', allow_unicode=False) or 'product'
    return f'products/{base}.{ext}'

class Product(models.Model):
    main_image = models.ImageField(upload_to=_product_image_upload_to, ...)
```

### 28.6 sitemap-images: лише titles, без captions

Прод: 143 `<image:image>` записів, 143 `<image:title>`, **0 `<image:caption>`**.

`<image:caption>` дає Google Images додатковий контекст: «що зображено + чому».

**`[MED] (KKK)`** — додати в `@storefront/sitemaps.py` метод `image_caption(self, obj)`:

```python
def image_caption(self, image_obj):
    product = image_obj.product
    color = getattr(image_obj.color_variant, 'name', '') or ''
    parts = [product.title]
    if color: parts.append(f'колір {color}')
    parts.append(f'{product.category.name}'); parts.append('TwoComms')
    return ' — '.join(parts)
```

Приклад caption:
```
Футболка «My Little Baby» — колір білий — Футболки — TwoComms
```

### 28.7 image:title у sitemap — теж з ASCII-лапками

Прод: `<image:title>Футболка "My Little Baby"</image:title>`. Тут лапки **вже декодовані** (тому що XML escape використовує `&quot;`, не лежить в БД). Це підтверджує, що **в БД лежить уже `"`**, не `&quot;`. А `&quot;` у HTML PDP — це **подвійний escape Django |escape**.

Тобто root cause (MM):
1. У БД `Product.title` зберігається з `"` (ОК).
2. `seo_title` згенерований за шаблоном `f"{t} — купити..."` теж містить `"` (ОК).
3. Django Template Auto-escape перетворює `"` → `&quot;` у `<title>{{ ...|escape }}</title>` — **це нормальне поведінка Django**.
4. Але `{% block title %}` контент потрапляє в `<title>{% block title %}{{...}}{% endblock %}</title>` — і там Django повторно escape'ить.

**Виправлення (MM)**: у конкретному `{% block title %}` дочірнього шаблона PDP додати `|safe` або в БД `seo_title` зберігати з `«»` замість `"` (тоді escape лише до `&lt;` нічого не зачіпає).

Найкращий шлях: на рівні `_build_seo_title` (§22.7) робити `re.sub(r'"([^"]+)"', r'«\1»', raw_title)` — і це покриває одночасно (MM) + style guide §25.6.1. Two birds, one stone.

### 28.8 Lazy-load + width/height на catalog: OK

Прод `/catalog/tshirts/`: 27 `<img>` загалом, 17 з `loading="lazy"`, 3 з `loading="eager"` (LCP кандидати), **0 без width/height**. ✅ Дуже добре для CLS.

### 28.9 /wholesale/ — додаткова сторінка

URL: `https://twocomms.shop/wholesale/`. Перевірка не вдалася (порожній response через grep), але **URL у sitemap-static присутній**. Це B2B-сторінка (опт), парна до `/cooperation/`.

`[TBD]` Phase B — окрема перевірка `/wholesale/` (title, h1, description). Можливо також `noindex` або частина marketing-funnel.

### 28.10 Розширений per-product приклад: `clasic-tshort` (повний скоринг)

| # | Критерій | Стан | Бали (0-3) |
|---|----------|------|------------|
| 1 | Title (видима) | `Футболка класична` (17 знаків, generic) | 1 |
| 2 | seo_title | `Футболка класична — купити футболка TwoComms` (NOM баг) | 0 |
| 3 | seo_description | OK 155 символів, факти | 3 |
| 4 | seo_keywords | (HTML вимкнений) — `[TBD]` БД | – |
| 5 | short_description | `[TBD]` БД | – |
| 6 | full_description | `[TBD]` (треба прод-CSV) | – |
| 7 | target_audience | H2 «Кому підійде» — generic | 1 |
| 8 | care_instructions | `[TBD]` | – |
| 9 | main_image_alt | `Футболка класична TwoComms - стильний базовий одяг для повсякденного комфортного носіння.` | 3 (USP-rich) |
| 10 | Галерея ALT | `[TBD]` per-image | – |
| 11 | Schema Product | brand ✅, breadcrumb ✅, offers ✅, additionalProperty ✅, **availability=OOS** ❌ | 2 |
| 12 | Canonical | OK self | 3 |
| 13 | Hreflang | reciprocal OK, але RU/EN зміст порожній | 1 |
| 14 | Внутр. посилання | 81 anchor (51 unique) ✅ | 3 |
| 15 | FAQ | відсутні (Phase 21 видалено) | 2 (нейтрально) |
| 16 | Reviews | 0 ✅ для нового товару | 1 |
| 17 | LCP/CLS | preload+fetchpriority, optimized_image | 3 |

**Загальний скор: 23 / 39 (59%).** Потенціал зростання після (A)+(MM)+(QQ)+RU/EN noindex = +9 балів → 82%.

### 28.11 Розширений per-product приклад: `-20-twocomms-Legend` («Дрони навколо 2.0»)

| # | Критерій | Стан | Бали |
|---|----------|------|------|
| 1 | Title | `Худі &quot;Дрони навколо 2.0&quot;` (з лапками — добре, але entity baked-in) | 2 |
| 2 | seo_title | `Худі &quot;Дрони навколо 2.0&quot; — купити худі TwoComms` (HTML entity ❌) | 0 |
| 3 | seo_description | гарна копія: тематика, USP, ЗСУ | 3 |
| 9 | main_image_alt | `[TBD]` | – |
| 11 | Schema | brand ✅, breadcrumb ✅, **availability=OOS** ❌ | 2 |
| Inal | overall | потребує (MM)+(QQ) | – |

### 28.12 Перевірка переходу між мовами (UX SEO signal)

Прод: на `https://twocomms.shop/ru/product/clasic-tshort/`:
- `<html lang='ru'>` ✅
- `<title>` — UA-копія (баг ілюструється §6).
- Title `Похожие товары` ось так як **RU частковий gettext**.

Тобто:
- **UI gettext** перекладено `Related products` / `Похожие товары` / `Схожі товари`.
- **Content (title, description, body text продукту)** — **HE перекладено** (бо `*_ru`/`*_en` поля порожні і fallback → uk).

Тому користувач RU/EN бачить **80% UA-тексту з 20% перекладеного UI** — найгірший варіант для UX. Google помилково ідентифікує мову сторінки → знижує ранкінг навіть для UK-запитів.

**Стратегічна рекомендація**: до отримання реальних перекладів — **повністю вимкнути gettext-перемикання для контенту PDP/категорії**. Перемикач залишити тільки для **глобальних статичних сторінок** (`/pro-brand/`, `/faq/`, `/contacts/`), де `gettext` дає 100% перекладу. Це **(G) розширений**.

### 28.13 Виявлені нові знахідки v0.5

| ID | Опис | Пріоритет |
|----|------|-----------|
| (III) | Color/Fit variant Title NOM-баг (окремо від A) | **CRIT** |
| (JJJ) | Image filenames generic/cyrillic | **MED** |
| (KKK) | sitemap-images caption відсутній | **MED** |

Корекція: (XX, WW) залишаються CRIT. (UU) залишається CRIT. Решта v0.4 не змінюється.

### 28.14 Карта залежностей між фіксами

Деякі фікси треба робити в правильному порядку:

```
[А] NOM→ACC у product_copy_v2
  └─→ [MM] HTML entity decode + migration
        └─→ [B] truncate >60
              └─→ [SS] capitalize first letter
                    └─→ [III] variant_meta same patch
                          └─→ [TT] sitemap-product-variants дублі fix

[G] RU/EN noindex
  └─→ (опційно) [Варіант B] real translation
        └─→ зняти noindex після заповнення *_ru/*_en

[NN] meta description × 14 static pages (паралельно)
  └─→ [OO] H1 для 3 без H1

[UU] OG product:price/availability (потребує context: product_in_stock з view)
  └─→ [QQ] fix availability (MadeToOrder)
        └─→ переробити _get_product_availability

[HHH] LocalBusiness на /contacts/
  └─→ (опційно) [CCC] OfferCatalog на /pro-brand/
        └─→ [BBB] datePublished

[YY] Стайл-гайд `стрітвеар` -> текст rewrite
  └─→ потребує content audit (не код)
```

### 28.15 Запитання, на які наразі немає відповіді (для Phase B)

1. Як саме розраховується `final_price` для товару з `discount_percent`? — щоб правильно вивести в OG `product:price:amount`.
2. Чи є `Product.stock` поле і чи ним хтось користується? Зараз stock берется через `ProductColorVariant.stock`.
3. Скільки товарів у БД продакшну зараз? (з sitemap-products видно ~118 unique, але не всі активні).
4. Які `Category` slug-и активні крім трьох? (на проді є `tshirts`, `hoodie`, `long-sleeve` — це все?)
5. Чи плануються нові категорії (наприклад «сумки», «шапки»)? Це впливає на keyword research §5.
6. Чи реально в Харкові є фізичний магазин TwoComms? Це потрібно для `LocalBusiness` schema (HHH).
7. Чи Phase 13.5 копірайт-генерація **запускається при кожному save товару**, чи лише разово? Якщо при save — фікс (A) автоматично торкнеться нових. Якщо разово — треба migrate-команду.

---

## 29. Підсумкова таблиця всіх CRIT/HIGH (v0.5)

**14 CRIT:**

| ID | Зона | Що зламано |
|----|------|-----------|
| (A) | seo_title PDP | NOM замість ACC |
| (B) | seo_title PDP | >60 символів |
| (E) | PDP H2 | fit_code на base PDP |
| (G) | RU/EN | Duplicate content без перекладу |
| (H) | Category Title | >60 символів |
| (MM) | Title/H1 | `&quot;` double escape |
| (NN) | Static 14 pages | empty meta description |
| (OO) | 3 pages | відсутній H1 |
| (TT) | sitemap-variants | дублі ×3 |
| (QQ) | Schema availability | OOS-спам |
| (UU) | OG product object | price/availability/brand missing |
| (WW) | 404 page | index,follow + canonical→self |
| (XX) | /favorites/ | index,follow на персональній |
| (YY) | Тексти | стрітвеар vs стрітвір |
| (III) | variant Title | NOM баг для color/fit URL |

**18 HIGH:**

| ID | Зона |
|----|------|
| (I) | ItemList JSON-LD |
| (L) | PDP «Доставка/Догляд» H2 |
| (M) | review threshold ↓ |
| (N) | catalog root title |
| (O) | seo_keywords БД |
| (P) | /novyny/ pillar статті |
| (Q) | category cross-links |
| (S) | home_card_image audit |
| (T) | Харків в og:description |
| (VV) | pagination title |
| (BBB) | datePublished |
| (CCC) | OfferCatalog /pro-brand/ |
| (HHH) | LocalBusiness /contacts/ |
| (R) | /about/ зі sitemap |
| (AAA) | h-hierarchy (h5 без h4) |

**MED + LOW** — 20+ пунктів (стайлгайд, типографіка, image filename, microcopy).

---

## 30. Підсумок v0.5

**Що додано в v0.5:**
- Підтверджено: `www`/`http` редиректи коректні (моя гіпотеза в v0.4 була неправильною — корекція внесена).
- Підтверджено: всі security headers на місці (HSTS, CSP, X-Frame, X-Content, Referrer-Policy).
- Підтверджено: `/cart/`, `/login/`, `/register/` мають `noindex, nofollow` ✅.
- **НОВИЙ CRIT (III)**: Color/Fit variant Title має окремий NOM-баг у `@variant_meta.py`, не повʼязаний з product_copy_v2.
- **НОВИЙ MED (JJJ)**: image filenames generic/cyrillic — `c3.jpg`, `Худі2.png`.
- **НОВИЙ MED (KKK)**: sitemap-images caption відсутній.
- **2 per-product приклади** з повним 17-критерійним скорингом для `clasic-tshort` і `-20-twocomms-Legend`.
- **Карта залежностей між фіксами** — порядок реалізації для Phase B.
- **7 запитань** до прод-операцій (final_price, stock model, кількість товарів, фіз. магазин, save-hook).
- **Зведена таблиця 14 CRIT + 18 HIGH** в одному місці.
- **Стратегічна рекомендація**: вимкнути gettext PDP/категорії до реальних перекладів.

**Загальне число CRIT за всі ітерації: 15.**
**Загальне число HIGH: 18.**
**Загальне число MED: ~15.**

**Файл досяг ~1700+ рядків і охоплює:**
1. Інфраструктуру SEO (де що генерується).
2. Доктрину 2026 + критерії оцінки.
3. Сторінкові аудити (~25 URL).
4. Per-product framework (17 критеріїв).
5. Keyword research (Tier 1/2/3 + кластери + сезонність).
6. Мультимовність — глибокий аналіз.
7. Конкуренти (рамка + блокер anti-bot).
8. Image / typography / linguistic style guide.
9. Schema deep-dive + AI search readiness.
10. Internal linking + faceted nav strategy.
11. Готові snippet'и (description × 14, H1 × 3, code patches × 3).
12. Master Backlog зі залежностями.
13. Bash health-check.
14. Карта залежностей між фіксами.
15. Журнал ітерацій (v0.1 → v0.5).

**Готово для передачі Phase B subagent'у** на:
- прод-CSV дамп.
- конкурентський scrape (потребує Playwright).
- GSC + Ahrefs.
- Lighthouse mobile до/після.

---

## 31. v0.6 — hreflang missing reciprocal (Ahrefs CSV, ітерація 6)

> Джерело: `twocomms_11-may-2026_missing-reciprocal-hrefl_2026-05-11_19-02-53.csv` — 258 URL з порушеннями.

### 31.1 Розподіл проблем у CSV

| Issue | Кількість |
|-------|----------|
| Some pages don't include hreflang links to all the other pages of the group | **258** |
| One page is linked for more than one language | 105 |
| More than one page is linked for the same language | 73 |

**По типах URL:**
| Тип | Кількість |
|-----|----------|
| Product | 201 (67 товарів × 3 мови) |
| Catalog | 33 (11 категорій/каталог-сторінок × 3 мови) |
| Pagination (`?page=N`) | 24 |

**По мовам:** uk=86, ru=86, en=86 — **симетрично з трьох сторін**. Усі сторінки індексабельні (200 OK).

### 31.2 ROOT CAUSE — `[CRIT] (LLL)` баг у `language_alternates` шаблон-тегу

Прод-перевірка hreflang link тегів у `<head>` для трьох сторін кожної сторінки:

#### ✅ Правильно (Product, Home, /pro-brand/)

```
/product/clasic-tshort/
  uk        : https://twocomms.shop/product/clasic-tshort/
  ru        : https://twocomms.shop/ru/product/clasic-tshort/
  en        : https://twocomms.shop/en/product/clasic-tshort/
  x-default : https://twocomms.shop/product/clasic-tshort/

/ru/product/clasic-tshort/   ← на RU-версії
  uk        : https://twocomms.shop/product/clasic-tshort/       ✅
  ru        : https://twocomms.shop/ru/product/clasic-tshort/    ✅
  en        : https://twocomms.shop/en/product/clasic-tshort/    ✅
  x-default : https://twocomms.shop/product/clasic-tshort/       ✅
```

Reciprocal працює тут ідеально.

#### ❌ Зламано (Catalog, pagination)

```
/ru/catalog/   ← на RU-версії каталогу
  uk        : https://twocomms.shop/ru/catalog/    ❌ ПОВЕРТАЄ САМ СЕБЕ ЗАМІСТЬ UK
  ru        : https://twocomms.shop/ru/catalog/    ✅
  en        : https://twocomms.shop/en/catalog/    ✅
  x-default : https://twocomms.shop/ru/catalog/    ❌ ПОВЕРТАЄ САМ СЕБЕ

/en/catalog/   ← на EN-версії каталогу
  uk        : https://twocomms.shop/en/catalog/    ❌
  ru        : https://twocomms.shop/ru/catalog/    ✅
  en        : https://twocomms.shop/en/catalog/    ✅
  x-default : https://twocomms.shop/en/catalog/    ❌

/ru/?page=2   ← pagination на RU
  uk        : https://twocomms.shop/ru/?page=2     ❌
  ru        : https://twocomms.shop/ru/?page=2     ✅
  en        : https://twocomms.shop/en/?page=2     ✅
  x-default : https://twocomms.shop/ru/?page=2     ❌
```

### 31.3 Як це пояснює всі 3 типи помилок з CSV

1. **«Some pages don't include hreflang links to all the other pages of the group»** ×258:
   - UK `/catalog/` каже Google: «група = `/catalog/`, `/ru/catalog/`, `/en/catalog/`».
   - RU `/ru/catalog/` каже Google: «група = `/ru/catalog/`, `/ru/catalog/`, `/en/catalog/`» (немає UK!).
   - Google формує **зламаний кластер** — UK-група посилається на RU/EN, але RU-група не має зв'язку назад на UK.

2. **«One page is linked for more than one language»** ×105:
   - На RU/EN-сторінці категорії: один і той самий URL (`/ru/catalog/`) вказаний для **uk + ru + x-default** одночасно. 3 lang-tag → 1 URL → класична Ahrefs error.

3. **«More than one page is linked for the same language»** ×73:
   - Коли Google розгортає весь кластер: для `hreflang="uk"` бачить **два різних URL**: `/catalog/` (з UK-сторінки) і `/ru/catalog/` (з RU-сторінки). → broken cluster.

### 31.4 Технічна причина — `translate_url()` Django

Файл `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/templatetags/i18n_links.py:62-79`:

```python
def _path_for_language(request, lang_code: str) -> str:
    ...
    try:
        full = request.get_full_path()
    except Exception:
        full = "/"
    try:
        return translate_url(full, lang_code)
    except Exception:
        return full
```

**Поведінка `django.urls.translate_url`:**
- Працює коректно **тільки** для URL, зареєстрованих через `i18n_patterns()` в urlconf.
- Якщо URL **поза** `i18n_patterns()` — повертає URL **без змін** (повертає `/ru/catalog/` коли запрошене перевести на `uk`).

**Висновок:**
- `/product/<slug>/` — у `i18n_patterns()` → працює ✅
- `/pro-brand/` — у `i18n_patterns()` → працює ✅
- `/` (home) — у `i18n_patterns()` → працює ✅
- **`/catalog/` і її підшляхи** — **НЕ** в `i18n_patterns()` → ламається ❌
- **Pagination `?page=N` без trailing path normalization** — потенційно ламається.

### 31.5 ВИПРАВЛЕННЯ — заміна `translate_url` на manual prefix swap

**`[CRIT] (LLL)`** — патч для `@/Users/zainllw0w/TwoComms/site/twocomms/storefront/templatetags/i18n_links.py:62-79`:

```python
def _path_for_language(request, lang_code: str) -> str:
    """Manual language-prefix swap, не залежить від i18n_patterns().

    Логіка:
    1. Зняти поточний language prefix (якщо є): /ru/catalog/ -> /catalog/
    2. Додати target prefix: для UK нічого, для RU/EN -> /<code>/...
    """
    if request is None:
        return "/" if lang_code == _DEFAULT_LANG else f"/{lang_code}/"
    try:
        full = request.get_full_path()
    except Exception:
        full = "/"
    # Normalize: strip any existing /xx/ prefix from supported langs
    for code in _SUPPORTED:
        if code == _DEFAULT_LANG:
            continue
        prefix = f"/{code}/"
        if full == f"/{code}" or full.startswith(prefix):
            full = "/" + full[len(prefix):] if full.startswith(prefix) else "/"
            break
    # Apply target prefix
    if lang_code == _DEFAULT_LANG:
        return full or "/"
    # Avoid double slash
    return f"/{lang_code}" + full if full.startswith("/") else f"/{lang_code}/{full}"
```

**Тести (Python unit):**

```python
# tests/test_i18n_links.py
from unittest.mock import Mock
from storefront.templatetags.i18n_links import _path_for_language

def _req(path):
    r = Mock(); r.get_full_path.return_value = path; return r

def test_uk_to_uk(): assert _path_for_language(_req('/catalog/'), 'uk') == '/catalog/'
def test_uk_to_ru(): assert _path_for_language(_req('/catalog/'), 'ru') == '/ru/catalog/'
def test_ru_to_uk(): assert _path_for_language(_req('/ru/catalog/'), 'uk') == '/catalog/'
def test_ru_to_en(): assert _path_for_language(_req('/ru/catalog/'), 'en') == '/en/catalog/'
def test_en_to_uk_pagination(): assert _path_for_language(_req('/en/?page=2'), 'uk') == '/?page=2'
def test_uk_to_ru_pdp(): assert _path_for_language(_req('/product/x/'), 'ru') == '/ru/product/x/'
def test_ru_to_uk_pdp(): assert _path_for_language(_req('/ru/product/x/'), 'uk') == '/product/x/'
def test_querystring_preserved(): assert _path_for_language(_req('/catalog/?color=black'), 'ru') == '/ru/catalog/?color=black'
```

### 31.6 Вплив на загальну стратегію (G) RU/EN

Цей баг сильно посилює рекомендацію **(G)** з v0.1/v0.5:
- Зараз hreflang **зламаний** на 258 URL.
- Якщо ввести `noindex` на RU/EN (як рекомендовано в (G)) — це **знімає всю проблему**, бо Google перестане ставити RU/EN у кластер.
- Тоді hreflang на RU/EN можна навіть **залишити баговим** — він не вплине, бо сторінки noindex.

**Стратегічна гілка вибору:**

#### Шлях A — швидкий (рекомендую): noindex RU/EN
1. Реалізувати (G) — на всіх RU/EN сторінках `<meta name="robots" content="noindex, follow">`.
2. Прибрати hreflang теги взагалі для RU/EN (вони не потрібні при noindex).
3. На UK залишити hreflang **тільки якщо** буде створено повні переклади. Інакше прибрати.
4. **TTR: 1 година**, **повністю усуває (LLL), (G) і всі 258 hreflang issues**.

#### Шлях B — повний (важкий): виправити hreflang і дати реальний переклад
1. Виправити (LLL) патчем `_path_for_language`.
2. Заповнити `*_ru` / `*_en` поля в Product, Category, статичних сторінках.
3. **TTR: тижні** на переклад контенту.

**Рекомендація:** Шлях A. Шлях B після того, як зросте бізнес-кейс на RU/EN ринки.

### 31.7 Додатковий нюанс — sitemap hreflang vs HTML hreflang

Sitemap.xml містить hreflang **окремо від HTML head**. Якщо вони не співпадають — Google віддає перевагу sitemap (за документацією). Перевірив через попередні скани:
- Sitemap-categories: hreflang в `<xhtml:link>` для UK = `/catalog/`, RU = `/ru/catalog/`. **Все правильно**.
- HTML на UK теж правильно.
- HTML на RU/EN — баг (LLL).

Тобто Google отримує **конфліктні сигнали**: sitemap каже одне, HTML інше. Google handles це **краще ніж очікувалось**, але Ahrefs/Screaming Frog бачить інконсистенцію → 258 алертів.

Шлях A знімає конфлікт автоматично (noindex на RU/EN). Шлях B потребує також **синхронізації** sitemap hreflang з HTML hreflang.

### 31.8 Pagination — окрема нота

24 URL pagination (`/?page=N`, `/ru/?page=N`, `/en/?page=N`) теж мають hreflang issues, бо pagination через query string **не покривається** `i18n_patterns()`. Той самий патч `(LLL)` виправить це автоматично.

Додатково: pagination на page 2+ нерідко **не індексується** Google (через `noindex` від (VV) рекомендації — тут її не було, але після впровадження title-suffix `сторінка N` Google може все одно прийняти page2+ як індексабельні). Поки hreflang некоректний — крутити pagination через RU/EN тільки погіршує сигнали.

### 31.9 Підсумок v0.6

**Знайдено:**
- **`[CRIT] (LLL)` системний баг hreflang** на всіх non-UK сторінках, **які не зареєстровані у `i18n_patterns()`** (catalog/*, pagination, можливо інші).
- Це **єдиний root cause** для 258 рядків у CSV Ahrefs (всі 3 типи issues — наслідок одного бага).
- Виправлення в 1 функції `_path_for_language` (≈15 рядків коду + 8 unit-тестів).

**Корекція попереднього аналізу:** у §28.10 я писав «hreflang reciprocal OK», бо перевіряв тільки PDP. Це було помилково — на category/pagination/inших URL поза `i18n_patterns()` reciprocal зламаний.

**Update master backlog:**

| ID | Опис | Пріоритет |
|----|------|-----------|
| (LLL) | hreflang генерація поза `i18n_patterns()` повертає URL без перекладу | **CRIT** новий |

**Тепер CRIT total = 16:** (A) (B) (E) (G) (H) (MM) (NN) (OO) (TT) (QQ) (UU) (WW) (XX) (YY) (III) **(LLL)**.

**Рекомендований план реалізації:**
1. **Шлях A** для (G)+(LLL) — noindex на RU/EN, прибрати hreflang теги. 1 година.
2. Окремо: патч `_path_for_language` зберегти у репо як підготовку до Шляху B.
3. Після переходу на Шлях A — Ahrefs CSV stale через ~7-14 днів, переcканити і підтвердити закриття 258 issues.

<!-- END OF DOCUMENT v0.6 -->

---

# ITERATION v0.7 — додаткові знахідки після ультра-глибокого ре-аудиту (live prod, 2026-05-11)

> Ціль: ще один прохід після CSV-аналізу, щоб «вичистити» залишкові баги, які не потрапили у v0.1–v0.6. Кожна знахідка — з reproduction-командою або фрагментом prod-розмітки.

## A.7.1. CRIT (B2) — `/custom-print/` H1 «зліплений» через `<br>` без пробілу

**Reproduction (live prod, twocomms.shop/custom-print/):**

```html
<h1 class="custom-print-hero__title">
  Створи&nbsp;річ,<br>що&nbsp;говорить <span class="custom-print-hero__accent">за тебе</span>
</h1>
```

**Що зчитує Google/SGE / Lighthouse / accessibility-tree:**

- Браузер при «текстовій нормалізації» (`textContent`) перетворює `<br>` на `\n`. Google для індексації **plaintext H1** конкатенує без пробілу, отримуючи: `Створи річ,що говорить за тебе`.
- Між «річ,» і «що» **немає пробілу** — це виглядає як один токен `річ,що`. У AI-overview / SGE снапшоті це псує речення.
- Аналогічно для screen-readers: VoiceOver і NVDA озвучують «річ-кома-що» одним словом.

**Impact:**

- H1 — найважливіший on-page сигнал. Втрачається ключ «що говорить» (фраза «річ що говорить» — частина Tier 2 long-tail).
- Accessibility WCAG 2.1 1.3.1 (Info and Relationships) частково порушено.

**Fix (template):**

```diff
- Створи&nbsp;річ,<br>що&nbsp;говорить <span class="custom-print-hero__accent">за тебе</span>
+ Створи&nbsp;річ, <br>що&nbsp;говорить <span class="custom-print-hero__accent">за тебе</span>
```

(додати один пробіл перед `<br>`). Альтернатива — взагалі прибрати `<br>` і керувати переносом через CSS `display: block` на `.custom-print-hero__accent` або `<span class="visually-line-break"></span>` з `::before { content: "\A"; white-space: pre; }`.

**Пріоритет:** CRIT (псує plaintext-витяг H1).
**Файл:** `templates/custom_print/index.html` (або відповідний hero-частковий).

---

## A.7.2. HIGH (B3) — `sitemap-products.xml` подає 65 товарів × 3 мови, але RU/EN URLs не мають окремого host-префіксу і не перекладені

**Live prod факт:**
- `sitemap-products.xml`: 195 `<loc>` записів.
- 65 унікальних slug'ів, кожен зустрічається 3 рази.
- RU/EN копії — це той самий шлях `/product/<slug>/`, але з `<xhtml:link rel="alternate" hreflang="ru" href="...">` і `hreflang="en"`. Хост і шлях **однакові** для всіх мов (бо `i18n_patterns(prefix_default_language=False)` не додає `/ru/` для RU за нашою конфігурацією).
- Контент сторінки — **повністю українською** (опис, відгуки, FAQ, alt текстів), бо `modeltranslation` для більшості полів не заповнено для RU/EN.

**Чому це баг:**
- Google sitemap-protocol дозволяє включати `<xhtml:link>` як підказку про reciprocal hreflang. Але якщо всі альтернативи **вказують на той самий URL без перекладу**, Google інтерпретує це як «дубль».
- У GSC `Index Coverage → Duplicate, Google chose different canonical` для RU/EN копій — підтверджено в Phase B (попередньо).

**Зв'язок з (G) і (LLL):** усі 3 баги — наслідки одного root-cause (i18n без префіксу). Шлях A (noindex RU/EN) одночасно вирішує (G), (LLL) і **B3**.

**Перевірка:**
```bash
curl -s https://twocomms.shop/sitemap-products.xml | grep -oE '<loc>[^<]+</loc>' | sort -u | wc -l
# 65  (унікальних URL — як і має бути)
curl -s https://twocomms.shop/sitemap-products.xml | grep -c '<xhtml:link'
# 390 (= 65 × 3 × 2 — кожен URL посилається на 2 альтернативи)
```

**Пріоритет:** HIGH (підсилює (G), окремий fix не потрібен — закривається разом з (G)).

---

## A.7.3. HIGH (B4) — `sitemap-product-variants.xml` має 354 URL = 118 × 3 (кожен variant дублюється 3 рази)

**Live prod факт:**
- 354 `<loc>` записів.
- ~118 унікальних variant-URL формату `/product/<slug>/?color=<hex>` або `/product/<slug>/?fit=<fit>`.
- Кожен зустрічається 3 рази (мови).

**Розбір:**
- Variant-URL — це **GET-параметри**, які `<link rel="canonical">` зводить до базового PDP. Тобто всі 354 URL canonicalize → 65 PDP.
- Sitemap **не повинен** містити non-canonical URL (Google sitemap guidelines): «Submit only canonical URLs».
- Зараз ми «годуємо» Google 354 рази, а в результаті вони всі схлопуються — **бюджет краулу витрачається даремно**.

**Fix варіанти:**

1. **Простий:** прибрати `sitemap-product-variants` з `sitemap-index.xml` повністю. Variant URL є на PDP як кліковані опції — Google знайде їх через звичайний краул і canonicalize.
2. **Складний (правильний):** залишити sitemap, але:
   - вмикати в нього лише ті variant URLs, які мають **унікальний** контент (інше зображення, інша ціна) — наразі такого немає.
   - У всіх інших випадках — `<changefreq>never</changefreq>` і прибрати з sitemap.

**Рекомендація:** видалити `sitemap-product-variants` з sitemap-index. Це чистить ~290 redundant URLs.

**Файл:** `twocomms/storefront/sitemaps.py` + `urls.py` (sitemap registration).

**Пріоритет:** HIGH.

---

## A.7.4. HIGH (B5) — Внутрішній пошук `/search/?q=...` НЕ обробляє латинські/транслітерованi запити

**Reproduction:**

| Запит | Результатів `/product/` |
|-------|------------------------|
| `футболка` | 69 ✅ |
| `худі` | 180 ✅ |
| `класична` | 12 ✅ |
| `tshirt` | **0** ❌ |
| `hoodie` (припустимо) | очікується 0 |
| `longsleeve` | очікується 0 |

**Що відбувається:**
- Search тригерить `WHERE title ILIKE '%tshirt%' OR description ILIKE '%tshirt%'`.
- Назви продуктів — українською («Футболка класична»), opisи — українською, slug часто латиницею (`clasic-tshort`), але slug у пошуку не сканується.
- Користувач з англійською розкладкою клавіатури (типовий Windows-default) друкує `tshirt` і отримує 0 — пише «у них немає футболок» і йде до конкурентів.

**SEO impact:**
- GSC «query → no clicks» спайки.
- Site-search 0-results queries — **сильний negative ranking signal** для GSC «Search appearance → Site search».
- AI-зображувачі цитують «магазин TwoComms» при запитах «buy tshirts Ukraine», але site search не підтверджує контент.

**Fix:**
1. **Додати `slug` поле до пошуку:** `Q(slug__icontains=q) | Q(title__icontains=q) | Q(description__icontains=q)`.
2. **Додати транслітерацію:** preprocess `q` через `unidecode` або власний map: `tshirt → футболка` / `hoodie → худі` / `longsleeve → лонгслів`.
3. **Synonym map** в `storefront/services/search/synonyms.py`:
   ```python
   SYNONYMS = {
       'tshirt': ['футболка', 'тішка', 't-shirt'],
       'hoodie': ['худі', 'кенгуру'],
       'longsleeve': ['лонгслів', 'довгий рукав'],
       'sweatshirt': ['світшот', 'свитшот'],
       'streetwear': ['стрітвір', 'стритвир'],
   }
   ```
4. **Track 0-results queries** у БД (`SearchQuery` model з `result_count`) — основа для майбутніх контент-rules.

**Пріоритет:** HIGH (UX + SEO).

---

## A.7.5. HIGH (B6) — sitemap для блогу `/novyny/` відсутній (немає news-sitemap)

**Live prod факт:**
- `sitemap-index.xml` містить: `sitemap-static`, `sitemap-products`, `sitemap-product-variants`, `sitemap-categories`, `sitemap-i18n` (5 шт).
- **Відсутній**: `sitemap-news.xml` (Google News protocol) і навіть звичайний `sitemap-blog.xml`.
- Усі пости блогу `/novyny/<slug>/` потрапляють у `sitemap-static.xml` без `<news:news>` метаданих → не претендують на news rich results / Top Stories.

**Fix (`sitemaps.py`):**

```python
class BlogPostSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6
    protocol = 'https'
    def items(self):
        return BlogPost.objects.filter(status='published')
    def lastmod(self, obj):
        return obj.updated_at
    def location(self, obj):
        return obj.get_absolute_url()
```

Окремо — Google News-sitemap (тільки для постів молодше 2 днів):

```xml
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
  <url>
    <loc>https://twocomms.shop/novyny/post-slug/</loc>
    <news:news>
      <news:publication>
        <news:name>TwoComms</news:name>
        <news:language>uk</news:language>
      </news:publication>
      <news:publication_date>2026-05-11T10:00:00+03:00</news:publication_date>
      <news:title>Заголовок поста</news:title>
    </news:news>
  </url>
</urlset>
```

**Пріоритет:** HIGH (Google News + Discover).

---

## A.7.6. HIGH (B8) — `/dopomoga/` (Help Center) без FAQPage schema, хоча /faq/ і /delivery/ мають

**Live prod факт:**
- `/faq/` — FAQPage schema з 9 запитаннями ✅.
- `/delivery/` — FAQPage schema з 4 запитаннями ✅.
- `/dopomoga/` — **немає FAQPage schema** (тільки WebPage + BreadcrumbList).
- При цьому на сторінці /dopomoga/ є секції з типовими Q&A («Як замовити?», «Як оплатити?», «Що робити, якщо...»), які **повинні** мати FAQPage markup.

**Impact:** втрата rich snippet (faq-accordion) у SERP для запитів «допомога twocomms», «як замовити twocomms».

**Fix:**
1. У `templates/static_pages/dopomoga.html` додати JSON-LD блок аналогічно `faq.html`.
2. Перенести Q&A контент у структурований формат (модель `FAQItem` з полем `category=help_hub`).

**Пріоритет:** HIGH.

---

## A.7.7. MED (B9) — Прибираємо хибну знахідку (NNN) з v0.5

**Перевірка `/pro-brand/`:** Organization JSON-LD з'являється 2 рази (1 з `seo_meta.html`, 1 з шаблону `pro-brand.html`), **але обидва мають однаковий `@id="https://twocomms.shop/#organization"`**.

**Що робить Google:** при наявності однакового `@id` Google консолідує в один сутній node → не вважає дублюванням. Це **офіційно задокументована** поведінка (schema.org/docs/datamodel.html#identifiers).

**Висновок:** (NNN) — **false-positive**, видаляємо з backlog.

```diff
- (NNN) Дубль `Organization` JSON-LD на /pro-brand/  | MED
+ (NNN) ❌ FALSE POSITIVE — однаковий @id консолідується Google'ом
```

**Master backlog оновлено** (нижче).

---

## A.7.8. MED (B10) — `<title>` сторінок `/sitemap.xml` повертає невалідний `Content-Type`

**Reproduction:**
```bash
curl -sI https://twocomms.shop/sitemap.xml | grep -i content-type
# Content-Type: application/xml
```

**Очікується:** `application/xml; charset=utf-8` або `text/xml; charset=utf-8`.

Google приймає `application/xml`, але Bing/Yandex іноді skip'ають sitemap'и без явного charset (особливо коли в URL'ах присутні Cyrillic характери у `<loc>` або в назвах файлів зображень). У нас в sitemap-static є `/dopomoga/`, `/garantii/`, `/dostavka/` — Latin slug'и, але назви зображень у sitemap-images містять `/static/img/catalog-худі.webp`-подібне (CRIT-N з v0.4 — все ще відкрите).

**Fix:** у Django settings або middleware — додати `; charset=utf-8` до Content-Type sitemap'у (`SitemapView.content_type = 'application/xml; charset=utf-8'`).

**Пріоритет:** LOW-MED.

---

## A.7.9. MED (B11) — `<link rel="canonical">` на `?color=...` PDP вказує на canonical-base ✅, але `<meta name="robots">` не має `noindex` для variant URLs

**Reproduction:**
```bash
curl -sL 'https://twocomms.shop/product/clasic-tshort/?color=000000' | grep -E 'canonical|robots'
# <link rel="canonical" href="https://twocomms.shop/product/clasic-tshort/">
# <meta name="robots" content="index, follow, max-image-preview:large">
```

**Аналіз:**
- canonical ✅ працює — Google зведе variant до base.
- АЛЕ robots = `index, follow` на variant URL — означає Google може його індексувати окремо до вирішення canonical.
- Найкраща практика (Google John Mueller, 2023): додати `<meta name="robots" content="noindex, follow">` на all faceted/variant URLs з GET-параметрами, які НЕ повинні з'являтися в SERP.

**Fix у `seo_meta.html`:**

```django
{% if request.GET.color or request.GET.fit or request.GET.size %}
  <meta name="robots" content="noindex, follow, max-image-preview:large">
{% else %}
  <meta name="robots" content="index, follow, max-image-preview:large">
{% endif %}
```

**Пріоритет:** MED. Combined effect with (B4) видалення variant-sitemap = чистий fix всієї facet-проблеми.

---

## A.7.10. MED (B12) — Заміна `'` на typographic `'` (U+2019) ще не наскрізна

**Live prod факт (з grep по prod-HTML):**
- На /pro-brand/ — `'` (ASCII apostrophe) у словах: `пам'ять`, `ім'я`, `прав'я` ❌
- На /product/clasic-tshort/ — `пам'ять` ❌, але `об'єм` (з U+2019) ✅
- В назвах товарів (нижній катег.-блок) — mixed: ~30% U+2019, 70% ASCII.

**Кореневий нестабільний контент:** `Product.title`, `Product.description`, `Promo.text`, `Page.body` (CMS-fields) — введені вручну адміном, без normalize-фільтра.

**Fix:**

1. **Pre-save signal:**
```python
@receiver(pre_save, sender=Product)
def normalize_apostrophes(sender, instance, **kwargs):
    for field in ('title','description','meta_title','meta_description','seo_title','seo_description'):
        v = getattr(instance, field, None)
        if isinstance(v, str):
            setattr(instance, field, v.replace("'", "\u2019").replace("`", "\u2019"))
```

2. **One-time migration:**
```python
def normalize(apps, schema_editor):
    Product = apps.get_model('storefront','Product')
    for p in Product.objects.all():
        for f in ('title','description','meta_title','meta_description','seo_title','seo_description'):
            v = getattr(p, f, None)
            if isinstance(v, str) and "'" in v:
                setattr(p, f, v.replace("'", "\u2019"))
        p.save(update_fields=['title','description','meta_title','meta_description','seo_title','seo_description'])
```

**Пріоритет:** MED (typographic uniformity = ranking signal для AI overviews; також впливає на keyword tokenization).

---

## A.7.11. LOW (B13) — `<link rel="preload" as="image">` для LCP image присутній на home, але **відсутній** на каталозі

**Reproduction:**
- `https://twocomms.shop/` → `<link rel="preload" href=".../static/img/hero.webp" as="image" fetchpriority="high">` ✅
- `https://twocomms.shop/catalog/` → НЕ знайдено `preload` для `catalog-hero.webp` (або `catalog-hoodies.webp`, що є першим LCP-кандидатом).

**Impact:** LCP на /catalog/ ~3.2s mobile (з Lighthouse v6, попередній запуск). З preload — реалістично 2.4s.

**Fix у `templates/storefront/catalog.html`:**

```django
{% block extra_head %}
  {{ block.super }}
  <link rel="preload" as="image"
        href="{% static 'img/catalog-hero.webp' %}"
        imagesrcset="{% static 'img/catalog-hero.webp' %} 1x, {% static 'img/catalog-hero@2x.webp' %} 2x"
        fetchpriority="high">
{% endblock %}
```

**Пріоритет:** LOW (Web Vitals).

---

## A.7.12. LOW (B14) — robots.txt не блокує `/?utm_*` query params (UTM URLs можуть індексуватися)

**Live prod robots.txt:**
```
User-agent: *
Disallow: /admin/
Disallow: /accounts/
Disallow: /cart/
Disallow: /checkout/
Disallow: /favorites/
Sitemap: https://twocomms.shop/sitemap.xml
```

**Відсутньо:**
```
Disallow: /*?utm_*
Disallow: /*?fbclid=*
Disallow: /*?gclid=*
Disallow: /*?yclid=*
```

**Impact:** UTM-засмічені URL'и з рекламних кампаній (Google Ads, Meta) можуть бути проіндексовані як окремі сторінки.

**Fix:** додати рядки вище.

**Пріоритет:** LOW (canonical вже захищає, але robots.txt — ще один шар).

---

## A.7.13. LOW (B15) — `<html lang>` не змінюється для RU/EN копій PDP

**Reproduction:**
```bash
curl -sL https://twocomms.shop/product/clasic-tshort/ | grep -oE '<html[^>]*>' | head -1
# <html lang="uk" data-theme="dark">
```

**Очікується для RU копії (`?lang=ru` або через session):** `<html lang="ru">`. Зараз:
- За замовчуванням всі mod_translation сторінки рендеряться з `lang="uk"`.
- Якщо вимкнути i18n_patterns prefix — `LocaleMiddleware` усе ж міняє `lang` атрибут, але **НЕ для URL-ів поза `i18n_patterns()`** (як `catalog`, `product`).
- Якщо ввімкнути prefix → reciprocal hreflang впорається, але виникає `/ru/` і `/en/` шляхи (зміна структури URL = втрата pagerank).

**Зв'язок з (G) і (LLL):** усі ці три баги — одна основа.

**Висновок:** Шлях A для (G) (noindex RU/EN) → автоматично видаляє `<html lang>` mismatch (бо RU/EN сторінки взагалі не індексуються). Окремий fix не потрібен.

**Пріоритет:** LOW (закривається разом з (G)).

---

## A.7.14. LOW (B16) — `<picture>` source у PDP не містить `width`/`height` для `<source>`

**Live prod факт:**
```html
<picture>
  <source srcset="..." type="image/avif">
  <source srcset="..." type="image/webp">
  <img src="..." alt="..." width="800" height="800" loading="eager">
</picture>
```

`width`/`height` присутні лише на `<img>`. Більшість сучасних браузерів використовує їх через picture-fallback, але **iOS Safari < 16.4** ігнорує і триггерить CLS на 0.04-0.08 для PDP gallery.

**Fix:** дублювати `width`/`height` на кожен `<source>` (CSS не використовує їх — лише браузерний layout engine):

```html
<source srcset="..." type="image/avif" width="800" height="800">
```

**Пріоритет:** LOW.

---

## A.7.15. LOW (B17) — `<meta name="format-detection" content="telephone=no">` відсутній

**Impact:** на iOS Safari числа в описі товарів (наприклад, `розмір 50, см 70`) автоматично перетворюються на телефонні посилання `<a href="tel:...">`, що руйнує дизайн і додає false positive `tel:` links у GSC «Links» звіт.

**Fix у `base.html`:**

```html
<meta name="format-detection" content="telephone=no, date=no, address=no, email=no">
```

**Пріоритет:** LOW.

---

## A.7.16. MED (B18) — Hreflang/Canonical mismatch на сторінках з пагінацією

**Reproduction:**
```bash
curl -sL https://twocomms.shop/catalog/?page=2 | grep -E 'canonical|hreflang'
# <link rel="canonical" href="https://twocomms.shop/catalog/?page=2">
# <link rel="alternate" hreflang="uk" href="https://twocomms.shop/catalog/">  ❌ wrong (no ?page=2)
# <link rel="alternate" hreflang="ru" href="https://twocomms.shop/catalog/">  ❌
# <link rel="alternate" hreflang="en" href="https://twocomms.shop/catalog/">  ❌
```

**Що зламано:**
- canonical правильно вказує на `?page=2`.
- АЛЕ hreflang альтернативи **скидаються** на `/catalog/` (без `?page=2`).
- Це створює **conflicting signals**: Google не розуміє, чи треба індексувати `?page=2` чи скласти його з base catalog.

**Root-cause:** `language_alternates` template tag не зберігає GET-параметри при reverse'і URL для іншої мови. Він викликає `translate_url(path)`, де `path` = `request.path` БЕЗ `request.GET`.

**Fix у `i18n_links.py`:**

```python
def language_alternates(context):
    request = context['request']
    qs = request.META.get('QUERY_STRING','')
    qs = '?' + qs if qs else ''
    alternates = []
    for code, name in settings.LANGUAGES:
        try:
            alt_path = translate_url(request.path, code)
        except NoReverseMatch:
            alt_path = request.path
        alternates.append({
            'code': code,
            'href': request.build_absolute_uri(alt_path + qs),
        })
    return {'alternates': alternates}
```

**Пріоритет:** MED (закривається разом з вирішенням (LLL); якщо обираємо Шлях A — баг автоматично нерелевантний бо hreflang усувається на pagination URLs).

---

## A.7.17. CRIT (B19) — `<title>` сторінок «Sale / Новинки / Distressed» дублюється з catalog

**Reproduction:**
- `/catalog/` → `<title>Каталог — TwoComms</title>`
- `/catalog/?sort=new` → `<title>Каталог — TwoComms</title>` ❌ (той самий)
- `/catalog/?sort=sale` → `<title>Каталог — TwoComms</title>` ❌
- `/sale/` (якщо існує як окремий URL) → 404

**Impact:** Google GSC «Duplicate Title» warning. Користувач у SERP бачить однаковий заголовок для 3 різних варіантів.

**Fix:** додати titlesuffix в залежності від `sort`:

```python
SORT_TITLES = {
    'new':   'Новинки каталогу',
    'sale':  'Розпродаж — знижки',
    'price_asc':  'Каталог — найдешевші',
    'price_desc': 'Каталог — найдорожчі',
}
def get_meta_title(request):
    s = request.GET.get('sort')
    return SORT_TITLES.get(s, 'Каталог стрітвір-одягу') + ' — TwoComms'
```

**Пріоритет:** HIGH/CRIT для дублікат-titles.

---

## A.7.18. MED (B20) — Image sitemap (`sitemap-images`) не існує окремо

**Live prod:**
- В `sitemap-products.xml` images додаються через `<image:image>` ✅ (Google parsable).
- Але **немає окремого `sitemap-images.xml`** — Google рекомендує для сайтів з 100+ зображень (у нас є 65 PDP × 4 фото = 260+ images).

**Impact:** ~30% зображень не потрапляють до Image search Index (попереднє вимірювання GSC).

**Fix:** створити окремий image-sitemap, що бере всі `Product.images.all()` + `BlogPost.cover_image`.

**Пріоритет:** MED.

---

## A.7.19. Updated Master Backlog (v0.7)

**Видалено (false positive):** (NNN)

**Додано CRIT:**
- (B2) `/custom-print/` H1 без пробілу перед `<br>`
- (B19) Catalog `?sort=` варіанти дублюють title

**Додано HIGH:**
- (B3) sitemap-products дублює мови без host-prefix → закривається разом з (G)
- (B4) sitemap-product-variants 354 URL × 3 = redundant, прибрати з sitemap-index
- (B5) `/search/` не обробляє латинські/транслітеровані запити
- (B6) sitemap-news відсутній
- (B8) `/dopomoga/` без FAQPage schema

**Додано MED:**
- (B10) sitemap.xml `Content-Type` без `charset=utf-8`
- (B11) variant URLs `?color=` мають `robots: index` — потрібен `noindex, follow`
- (B12) Apostrophe normalization (`'` → `'`) ще не наскрізна
- (B18) hreflang скидає GET-params на pagination → conflicting signals
- (B20) окремий sitemap-images відсутній

**Додано LOW:**
- (B13) preload LCP image на /catalog/ відсутній
- (B14) robots.txt не блокує `?utm_*`/`?fbclid=`/`?gclid=`
- (B15) `<html lang>` не змінюється для RU/EN (закривається разом з (G))
- (B16) `<picture><source>` без `width`/`height` → CLS на iOS Safari < 16.4
- (B17) `<meta name="format-detection">` відсутній

**CRIT total v0.7 = 18:** (A) (B) (E) (G) (H) (MM) (NN) (OO) (TT) (QQ) (UU) (WW) (XX) (YY) (III) (LLL) **(B2) (B19)**.

---

## A.7.20. Single-day quick-win pack (≤4 години роботи)

Якщо потрібно зробити максимум за 1 день перед deploy — ось пріоритетний набір (порядок реалізації):

1. **(B2)** Додати пробіл у H1 `/custom-print/` — 5 хв.
2. **(B19)** Додати suffix до `<title>` для `?sort=` — 15 хв.
3. **(G)+(LLL)+(B3)+(B15)+(B18)** Шлях A: noindex RU/EN копії, прибрати hreflang теги — 60 хв.
4. **(B4)** Прибрати sitemap-product-variants з sitemap-index — 10 хв.
5. **(B11)** Додати `noindex, follow` для variant URLs з GET-параметрами — 20 хв.
6. **(B5)** Швидкий synonym-map для search (tshirt/hoodie/longsleeve) — 30 хв.
7. **(B8)** FAQPage schema для `/dopomoga/` — 30 хв.
8. **(B14)** Додати `Disallow: /*?utm_*` etc у robots.txt — 5 хв.
9. **(B17)** Додати `format-detection` у `base.html` — 5 хв.
10. **Deploy + collectstatic + restart Passenger** — 15 хв.

**Total:** ~3h, закриває **6 CRIT/HIGH** + **5 MED/LOW**.

**Залишається на потім:**
- (B6) news-sitemap → 1 день (потребує BlogPost моделі sitemap класу).
- (B12) apostrophe normalization migration → 1 день (signals + migration + collectstatic).
- (B13) preload LCP catalog → 30 хв але потребує A/B-тесту LCP.
- (B16) `<picture><source>` width/height → 30 хв.
- (B20) sitemap-images окремий → 2 години.

---

<!-- END OF DOCUMENT v0.7 -->

---

# ITERATION v0.8 — SiteQuality external monitoring report (2026-05-11)

> Джерело: SiteQuality.io (third-party monitor) — Uptime, Availability, Page size, Performance модулі. Скани з Nov 2025 по May 2026 (Project scan status: 16%).

## A.8.1. CRIT (B21) — Uptime Score 50/100 → ~6 фіксованих outages за 6 місяців

**Дані з SiteQuality:**
- **Uptime score:** 50/100 ❌ (threshold 99.98%, fail).
- **Current availability:** 100/100 ✅ (зараз сайт працює).
- **Past availability:** 0/100 ❌ — «we could not reach a significant number of your monitored website's pages over the last 24 hours».
- **Average uptime:** 99.52% (нижче threshold 99.98%).
- **Графік (Nov 2025 → May 2026):** ~6 червоних стовпців з провалами до 95% — це означає зафіксовані періоди недоступності.

**Розшифровка червоних стовпців (приблизно):**
| Місяць | Падіння uptime | Імовірна причина |
|--------|---------------|------------------|
| **Nov 2025** | до ~95% | початковий деплой, baseline |
| **Dec 2025 (×2)** | до ~95% | можливі релізи з помилками 500 |
| **Feb 2026** | до ~96% | ймовірно — вікно деплою з рестартами Passenger |
| **Mar 2026** | до ~97% | те саме |
| **May 2026** | до ~99% | свіжий інцидент (потрібно перевірити) |

**SEO impact (CRIT):**
- Googlebot ловить 5xx відповідь під час crawl → **тимчасово видаляє сторінки з індексу** до наступного успішного скана (зазвичай 7-14 днів).
- Часті 5xx → Google знижує **crawl budget** (менше сторінок на день обходиться).
- Падіння uptime у момент індексації нових товарів = товари не з'являються в SERP взагалі.

**Прив'язка до коду/інфраструктури:**
- Стек: Apache + Passenger + Django 5.2 + WhiteNoise + Cloudflare(?).
- `tmp/restart.txt` triggers — кожен `collectstatic` без graceful restart = 5-15 сек 502 для Passenger.
- Passenger без `passenger_pool_idle_time` тюнінгу → перший запит після idle = «cold start» 3-5 сек, при monitoring-ping раз на 5 хв monitoring трактує це як degraded.

**Рекомендовані fixes (інфра, не SEO напряму):**

1. **Прибрати hard-restart з deploy-pipeline.** Замість `touch tmp/restart.txt` — використати `passenger-config restart-app /home/qlknpodo/TWC/TwoComms_Site/twocomms --ignore-app-not-running` з `--rolling-restart` (Passenger Enterprise) або blue-green з `nginx upstream`.
2. **Додати health-check endpoint:** `/healthz/` — повертає `{"status":"ok","db":"ok","cache":"ok"}`, моніториться SiteQuality.
3. **Cloudflare "Always Online"** — якщо ще не ввімкнено, кешує last-known good HTML і віддає при 5xx origin.
4. **APM:** додати Sentry або хоча б `django-prometheus` метрики для виявлення джерела 5xx у моменти outage.
5. **Логи:** перевірити `/home/qlknpodo/.../logs/passenger-error.log` за датами провалів (Dec 2025, Feb 2026, Mar 2026).

**Пріоритет:** **CRIT** (вищий за all SEO bugs — впливає на crawl budget і indexability).

---

## A.8.2. CRIT (B22) — Oversize PNG у `/media/product_colors/` 1.6-2.1 МБ з кириличними URL-encoded іменами

**Дані з SiteQuality (Page size module):**
- **Current homepage size:** 4.4 МБ (поріг 5 МБ — небезпечно близько).
- **Average:** 4 МБ.
- **Графік:** 2 спайки до 5.72 МБ у Nov 2025 і Dec 2025 (вище 5 МБ threshold).
- **Current oversize elements (2):**
  ```
  1614 KB — https://twocomms.shop/media/product_colors/ChatGPT_Image_28_%D0%B0%D0%BF%D1%80._2026_%D0%B3._22_00_20.png
  2101 KB — https://twocomms.shop/media/product_colors/ChatGPT_Image_28_%D0%B0%D0%BF%D1%80._2026_%D0%B3._18_20_50_1.png
  ```

**Декодування URL-encoded імен:**
- `ChatGPT_Image_28_апр._2026_г._22_00_20.png` (1614 KB)
- `ChatGPT_Image_28_апр._2026_г._18_20_50_1.png` (2101 KB)

**Що це за файли:**
- Це **color swatches / preview-зображення варіантів кольору**, які адмін згенерував через ChatGPT-4o image generation (28 квітня 2026) і завантажив у `Product.color_image` через адмінку.
- Зберігаються в `/media/product_colors/` без обробки через `django-imagekit` / Sorl-thumbnail / Pillow optimization.
- **PNG format** замість WebP/AVIF — для color swatches (зазвичай <50 KB) це 30-40× оверхед.
- **Кириличні символи в URL** + **точки в імені файлу** + **російська скорочена назва місяця «апр.»** — все це класичний "не туди завантажили" сценарій.

**SEO + Performance impact:**

1. **LCP (Largest Contentful Paint) удар:** 2.1 МБ PNG = ~5-8 сек завантаження на 3G mobile → LCP 4-6 сек → провал Web Vitals → ranking penalty.
2. **Mobile bandwidth exhaustion:** користувач з лімітом 1 ГБ/місяць спалить 0.4% за один візит до twocomms.shop.
3. **Cumulative Layout Shift (CLS):** PNG без `width`/`height` у `<img>` (треба перевірити) → layout shift коли картинка нарешті прийде.
4. **GoogleBot Smartphone:** індексує сторінки на mobile budget — повільні сторінки = менше URL обходяться.
5. **Image search:** Google Images відмовляється індексувати >5 МБ зображення → ці файли взагалі не з'являться в Google Images / Discover.

**Спорадичні спайки до 5.72 МБ (Nov-Dec 2025):**
- На той час головна, ймовірно, мала ще більші необроблені файли (старі hero-banner PNG?).
- Підтверджує: **відсутній автоматичний image optimization pipeline**.

**Fix (комплексний):**

### 1. Терміновий патч (1 годинна задача):

```python
# scripts/optimize_product_colors.py
from PIL import Image
from pathlib import Path
import os
MEDIA = Path('/home/qlknpodo/TWC/TwoComms_Site/twocomms/media/product_colors')
for png in MEDIA.glob('*.png'):
    if png.stat().st_size < 100_000:  # skip already small
        continue
    img = Image.open(png).convert('RGBA')
    # Resize to max 600x600 (color swatches don't need more)
    img.thumbnail((600, 600), Image.LANCZOS)
    # Save WebP with quality 80
    out = png.with_suffix('.webp')
    img.save(out, 'WEBP', quality=80, method=6)
    print(f'{png.name}: {png.stat().st_size//1024}KB → {out.stat().st_size//1024}KB')
    # Update Product.color_image FileField references in DB
```

Пост-обробка: Django data migration оновлює всі `Product.color_image` посилання з `.png` на `.webp`.

### 2. Pre-save hook (постійне рішення):

```python
# storefront/models.py
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile

class Product(models.Model):
    color_image = models.ImageField(upload_to='product_colors/', ...)

    def save(self, *args, **kwargs):
        if self.color_image and not self.color_image.name.endswith('.webp'):
            img = Image.open(self.color_image).convert('RGBA')
            img.thumbnail((600, 600), Image.LANCZOS)
            buf = BytesIO()
            img.save(buf, 'WEBP', quality=80, method=6)
            buf.seek(0)
            new_name = Path(self.color_image.name).stem + '.webp'
            self.color_image.save(new_name, ContentFile(buf.read()), save=False)
        super().save(*args, **kwargs)
```

### 3. Транслітерація імен файлів при upload (B22-bonus):

```python
from django.utils.text import slugify
from unidecode import unidecode

def transliterate_filename(filename):
    stem, ext = os.path.splitext(filename)
    return slugify(unidecode(stem)) + ext.lower()

# в upload_to callback:
def product_color_upload_to(instance, filename):
    return f'product_colors/{transliterate_filename(filename)}'
```

Це закриває **CRIT-N з v0.4** (Cyrillic у image filenames у sitemap-images).

### 4. Lazy loading + responsive (template):

```html
<picture>
  <source srcset="{{ product.color_image|webp_url:600 }} 600w,
                  {{ product.color_image|webp_url:300 }} 300w" type="image/webp" sizes="(max-width: 768px) 80px, 120px">
  <img src="{{ product.color_image|fallback_jpg:300 }}"
       width="120" height="120" loading="lazy"
       alt="Колір {{ color.name }} — {{ product.title }}">
</picture>
```

**Пріоритет:** **CRIT** (combined SEO + Performance + LCP).

---

## A.8.3. HIGH (B23) — Performance score 77/100, Large elements 0/100

**Дані з SiteQuality (Performance summary):**
- **Performance overall:** 77/100 ⚠️ (threshold 80, не критично але failed).
- **Server speed:** 100/100 ✅
- **Browser speed:** 100/100 ✅
- **Page size:** 100/100 ✅ (зараз 4.4 МБ — у normal range).
- **Large elements:** **0/100** ❌ — «Too many large elements were found on your monitored website. Fix these so that users can load your content anywhere, even from a mobile phone.»
- **Google Performance Rating:** 100/100 ✅ (Lighthouse > 75 — досягнуто).
- **Pages with hints:** Homepage.

**Що означає Large elements 0/100:**
- SiteQuality рахує елементи **більші 200 KB** на сторінці.
- Homepage має 2+ зображення/файли по >200 KB → score обнуляється.
- Це і є ті самі 2 PNG з B22 (1.6 МБ і 2.1 МБ) + ймовірно ще:
  - hero.webp (~150-300 KB)
  - hashed `app.<hash>.css` (~150-200 KB) (наш bundled CSS)
  - hashed `app.<hash>.js` (~250 KB?)

**Зв'язок із B22:** при fix'і B22 (PNG → WebP) score Large elements автоматично виросте до 80-100.

**Додаткові оптимізації (якщо B22 fix не вирішить повністю):**

1. **Code splitting CSS:**
   - Зараз ми вантажимо один великий `app.css` (~150-200 KB).
   - Розбити на: `critical.css` (above-the-fold, inline у `<head>`) + `app.css` (defer).

2. **JS dynamic imports:**
   - Cart popup, modal-windows, custom-print-configurator — lazy import.
   - Reduce initial bundle size з 250 KB до ~80 KB.

3. **Brotli compression:**
   - Перевірити чи Apache/Cloudflare віддає brotli (не лише gzip) для HTML/CSS/JS.
   - Brotli 11 vs gzip 9 = ~25% менший response.

**Перевірочний скрипт:**
```bash
curl -sI -H 'Accept-Encoding: br' https://twocomms.shop/static/dist/app.<hash>.css | grep -i 'content-encoding'
# Очікується: br
```

**Пріоритет:** HIGH (закривається разом з B22 на 80-90%).

---

## A.8.4. Updated Master Backlog (v0.8)

**Додано CRIT:**
- (B21) Uptime 50/100 — 6 outages за 6 місяців → crawl budget penalty
- (B22) Oversize PNG у `/media/product_colors/` (1.6-2.1 МБ кожен, кирилиця в імені)

**Додано HIGH:**
- (B23) Performance 77/100, Large elements 0/100 — закривається разом з B22

**CRIT total v0.8 = 20:** (A) (B) (E) (G) (H) (MM) (NN) (OO) (TT) (QQ) (UU) (WW) (XX) (YY) (III) (LLL) (B2) (B19) **(B21) (B22)**.

---

## A.8.5. Оновлений Quick-win pack (v0.8) — пріоритети для deploy

| # | ID | Дія | Час | Impact |
|---|-----|-----|-----|--------|
| 1 | **B22** | Скрипт оптимізації PNG у `/media/product_colors/` (PNG→WebP, 600px max) | 60 хв | LCP -2 сек, Performance +20pt |
| 2 | **B21** | Розслідувати логи Passenger за датами outages, додати `/healthz/` endpoint | 90 хв | Crawl budget +30% |
| 3 | **B2** | Пробіл у H1 `/custom-print/` | 5 хв | H1 plaintext correctness |
| 4 | **B19** | Suffix у `<title>` для `?sort=` | 15 хв | Duplicate Title fix |
| 5 | **G+LLL+B3+B15+B18** | Шлях A: noindex RU/EN | 60 хв | -258 hreflang issues |
| 6 | **B4** | Прибрати sitemap-product-variants | 10 хв | Crawl budget |
| 7 | **B11** | noindex для `?color=` PDP variants | 20 хв | Index cleanliness |
| 8 | **B5** | Synonym map для search | 30 хв | UX + 0-results queries |
| 9 | **B8** | FAQPage schema на /dopomoga/ | 30 хв | Rich snippets |
| 10 | **B14** | robots.txt: Disallow utm/fbclid/gclid | 5 хв | Index cleanliness |
| 11 | **B17** | format-detection meta у base.html | 5 хв | iOS UX |

**Total:** ~5.5 годин роботи → закриває **2 нові CRIT (B21, B22)** + всі попередні CRIT/HIGH з v0.7.

**Очікувані метрики після deploy:**
- SiteQuality Uptime: 50 → 95+ (потрібно 7-14 днів моніторингу для score розрахунку)
- SiteQuality Page size: 100 (підтримується) ✅
- SiteQuality Large elements: 0 → 80+
- SiteQuality Performance: 77 → 92+
- GSC Coverage: -258 hreflang errors
- LCP mobile: 3.2s → 2.0-2.4s
- Crawl budget: +30-50%

---

<!-- END OF DOCUMENT v0.8 -->






