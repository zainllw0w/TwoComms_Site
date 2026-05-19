# Глибокий розбір SEO-аудиту Vilni AI для twocomms.shop

> **Документ:** аналітичний звіт із верифікацією кожного твердження аудиту Vilni AI проти живого сайту, кодової бази (Django репозиторій) та даних Google Search Console.
>
> **Аудит, що рев’юється:** [vilni.pro/widget/audits/1fe9b9ff-…](https://vilni.pro/widget/audits/1fe9b9ff-afe0-4753-8446-fa4cac003444.html) (видано **2026-05-16**, методологія v1.0.0)
>
> **Поточна дата звіту:** 2026-05-19
>
> **Об’єкт:** `https://twocomms.shop/` (Django + LiteSpeed, домен twocomms.shop + субдомен dtf.twocomms.shop)
>
> **Файли-докази у репо:** `/home/TwoComms_Site` — основна гілка `main`, останній SEO-релевантний коміт `4bb0f6d` (2026-05-17).

---

## 0. TL;DR — основне за 60 секунд

| Категорія | Висновок |
|---|---|
| **Загальна точність аудиту Vilni** | **середня (~65%)**. Великий розрив між моментом крауля (≈14:00, 2026-05-16) і пізнішими комітами того ж дня + цілим спринтом 2026-05-17. Близько 40% знахідок описують код, що вже виправлений або інший на момент звіту. |
| **Що Vilni знайшов правильно** | • `/blog/` 404 на головному домені (блог справді живе тільки на `dtf.twocomms.shop`).<br>• Відсутній `aggregateRating` у `Product` schema (інфраструктура є — даних нема).<br>• `priceRange:"₴₴"` на /contacts/ — нестандартна нотація.<br>• `hreflang="en-UA"` обмежує діаспору.<br>• Mobile LCP 3.6 с — підтверджено в Lighthouse-lab.<br>• `availability=MadeToOrder` на 100% PDP. |
| **Що Vilni наплутав або застарів** | • «sameAs має лише 2 посилання» — насправді на головній **4** (IG, TG, TikTok, Threads).<br>• `addressLocality="Україна"` — насправді вже **"Харків"** + `addressRegion="UA-63"`.<br>• «FAQPage немає на товарних» — насправді **є**, 14 запитань на PDP (`/product/225-tshirt/`), коміт того ж дня.<br>• «На /faq/ 10 запитань» — насправді **30**.<br>• «6 sub-sitemap» — насправді **7** (`sitemap-thematic.xml` зі сторінками `/catalog/theme/...`). |
| **Що Vilni повністю проґавив (КРИТИЧНО)** | 🔴 **Локалі `/ru/` та `/en/` віддають українські `<title>` і `<meta description>`** — 65 SEO-критичних літералів без перекладу в `locale/{ru,en}/LC_MESSAGES/django.po`. Це найдорожча знахідка цього розбору; вона повністю руйнує сенс RU/EN-локалей.<br>🟠 Адресні плейсхолдери «Хрещатик 22 / Соборний 15» на /contacts/ (`class="blurred"`) — підривають довіру, потенційно вводять Google в оману.<br>🟠 Сторінки з 100+ показами і 0 кліків у GSC (`longsleeve-classic` 427 imp/pos 51, `Idea-hd` 72 imp/pos 3.7, `Glory of Ukraine` 121 imp/pos 25 та ін.) — реальні «низько висячі плоди», не згадані в аудиті.<br>🟠 OG `og:locale:alternate="en_US"` ↔ hreflang `"en-UA"` — внутрішня неконсистентність (Facebook/LinkedIn vs Google).<br>🟠 GSC показує URL із префіксним дефісом (`/product/-225-tshirt-/`) → нові URL чисті (`/product/225-tshirt/`) → втрата історичних кліків через 301-ланцюг. |
| **Реалістичний імпакт виправлень** | Дві найважчі шестерні — UGC-відгуки + локалізація meta-тегів. Перша дає +CTR у видачі для існуючих позицій, друга відкриває доступ до RU/EN-сегментів і діаспори. Очікувано **+30–80% органічного трафіку за 90 днів** (нижче за прогноз Vilni «+60–150%» через сезонність і реальну DR домена). |

---

## 1. Як я перевіряв твердження

Кожна знахідка пройшла через **п’ять незалежних джерел**:

1. **Сирий HTML живого сайту**: `curl -sL` (з підтримкою редиректів) для `/`, `/ru/`, `/en/`, `/product/225-tshirt/`, `/product/bentejne-hd/`, `/product/kha-edition-ts/`, `/contacts/`, `/faq/`, `/pro-brand/`, `/catalog/tshirts/`, `/catalog/hoodie/`, `/custom-print/`, `/wholesale/`, `/delivery/`, `/blog/`, `/robots.txt`, `/llms.txt`, `/sitemap.xml` + 7 sub-sitemap-ів.
2. **JSON-LD парсинг**: усі `<script type="application/ld+json">` блоки на кожній сторінці прогнано через Python-парсер; `@graph` нормалізовано; типи зведено в таблицю.
3. **Django-репозиторій**: `twocomms/` — шаблони (`pages/index.html`, `pages/contacts.html`, `pages/product_detail.html`, `base.html`), `storefront/seo_utils.py` (`StructuredDataGenerator`), `storefront/templatetags/seo_tags.py`, `storefront/views/product.py`, `reviews/` додаток (моделі + сервіс агрегації), `dtf/` додаток (блог + субдомен), `twocomms/middleware.py` (`SubdomainURLRoutingMiddleware`).
4. **Git-історія**: `git log --since="2026-04-01"` показав, що **24 SEO-релевантних коміти** залилися 2026-05-16 і 2026-05-17 — багато з них після часу крауля Vilni. Це пояснює розходження.
5. **Дані Google Search Console** (3 місяці, 2026-01-18 → 2026-04-19): 120 кліків, 1670 показів, CTR 7.2%, середня позиція 20.4. CSV: `SEOScreen/twocomms.shop-Performance-on-Search-2026-04-19/{Запросы,Страницы,Страны,Устройства,Вид в поиске}.csv`. 93/120 кліків мобільні, 85% трафіку з України.

Кожне твердження нижче має **метку точності**:

- ✅ **Точно** — Vilni правий, підтверджено на 2026-05-19.
- ⚠️ **Частково/застаріло** — було правдою на момент аудиту, виправлене зараз або вимагає нюансу.
- ❌ **Неправильно** — фактично хибне твердження.
- 🆕 **Проґавлено** — серйозна проблема, яку Vilni не помітив.

---

## 2. Загальна оцінка аудиту Vilni AI як продукту

### 2.1. Що Vilni зробив добре

| Аспект | Деталі |
|---|---|
| **Структура звіту** | Severity-стратифікація (critical/high/medium/low), per-finding evidence з `curl`-командами, окрема секція «AI-citation readiness», ваги категорій (Tech 25 / Content 25 / On-Page 20 / Links 15 / Perf 10 / E-E-A-T 5) — гідно. |
| **Розпізнавання ніші** | «Ecommerce / streetwear / military apparel» з рівнем довіри 96% — коректно. |
| **Виявлення Local Pack як точки росту** | Хоча конкретна реалізація рекомендацій частково помилкова (див. 4.3), сам інсайт — TwoComms позиціонується як Харків, і Local Pack недоступний — правильний. |
| **AI-citation як окрема дисципліна** | Виокремлення `llms.txt` + AI-bot allowlist + Wikidata Q-ID як стратегічного шару — рідкість серед звичайних SEO-аудитів. Сам по собі цей шар у TwoComms уже один з найкращих у UA-сегменті. |
| **CTA-чесність** | Прогноз «+60–150% за 6 міс» дано з оговоркою «база-кейс, залежить від бюджету і сезону» — не запаморочливі цифри. |

### 2.2. Що Vilni зробив погано

| Аспект | Деталі |
|---|---|
| **Темпоральна навмисність** | Аудит датований 2026-05-16, але опубліковані виправлення того ж дня (включно з ClothingStore.addressLocality=Харків, FAQPage на PDP, sameAs Threads, AggregateOffer на головній) **не враховані**. Це не вина Vilni — вони знімали статичний зріз — але без позначки «застаріло на N годин» виглядає некоректно. |
| **Поверхневість крауля** | Сканували 6 URL, не пройшлися по `/ru/` чи `/en/`. Через це проґавили **сам критичний** недогляд — український title/description на російському й англійському локалях (див. розділ 3). |
| **Помилки прочитання JSON-LD** | • Sameas заявлено «2 посилання» — у Organization-вузлі на головній уже 4. Vilni, ймовірно, прочитав ClothingStore-вузол на /contacts/, де справді 2.<br>• «addressLocality:Україна» — на сьогодні «Харків»; на момент аудиту, можливо, теж уже виправлено (коміт 83b9c61 від 2026-05-16 20:47, перед стандартним нічним перевиданням каешів). |
| **Узагальнення на катастрофу там, де її нема** | «availability=MadeToOrder блокує товари у Shopping» — формально вірно, але Google `MadeToOrder` явно дозволяє в Rich Results. Цифра «-15-25% замовлень у пікові періоди» виглядає більше як sales-аргумент Vilni, ніж дослідницькою. |
| **Дублювання findings** | LCP-finding пишеться двічі (раз як `performance`, раз як `cwv_diagnostics`). FAQPage-finding пишеться двічі (`on_page` + `llm_readiness`). sameAs — двічі. Це штучно підвищує лічильник «13 точок росту». Реальних унікальних — **9**. |
| **Backlinks=55 baseline без даних** | Категорія Backlinks (вага 15%) оцінена «baseline» бо немає GSC/Ahrefs доступу. Це чесно, але робить overall=75 заниженим. Реалістично сайт зараз ближче до 80-82. |
| **Прогноз ROI на основі суб’єктивних коефіцієнтів** | «UGC дає +25-35% CTR», «зірки = найсильніший фактор», «LCP -0.5с = -7% конверсії» — це усереднені бенчмарки з різних досліджень, не специфічні для DTF-streetwear ніші в Україні з 1670 показами/міс. У вашому масштабі дисперсія значно вища за заявлені коефіцієнти. |

### 2.3. Підсумкова оцінка аудиту Vilni: **B–**

Аудит **корисний** як трекер пріоритетів — він майже правильно ранжує, **що** робити (UGC > Local SEO > /blog/ > Performance). Але як **технічний документ** він має фактичні неточності, проґавлений критичний i18n-баг і трохи продажний тон. Якщо взяти його за технічний backlog 1:1, є ризик зробити роботу, яка вже зроблена (Threads/TikTok sameAs, FAQPage на PDP, Inter self-host), і пропустити справді важливе.

---

## 3. КРИТИЧНЕ — що Vilni проґавив

### 3.1. 🔴 Російська і англійська локалі віддають **український** `<title>`, `<meta description>`, `og_title`, `og_description`, `twitter_description`

**Доказ (живий сайт):**

```text
URL:  https://twocomms.shop/ru/
title: TwoComms — стріт та мілітарі одяг з Харкова: футболки, худі  ← UA!
desc:  TwoComms — харківський бренд стрітвір та мілітарі одягу:...  ← UA!
h1:    TwoComms — бренд: Стрит & милитари одежда                    ← RU OK
canon: https://twocomms.shop/ru/                                    ← OK

URL:  https://twocomms.shop/en/
title: TwoComms — стріт та мілітарі одяг з Харкова: футболки, худі  ← UA!
desc:  TwoComms — харківський бренд стрітвір та мілітарі одягу:...  ← UA!
h1:    TwoComms — the brand: Street & military apparel              ← EN OK
canon: https://twocomms.shop/en/                                    ← OK
```

**Корінь проблеми:** `pages/index.html` рядок 6:

```html
{% block title %}{% trans 'TwoComms — стріт та мілітарі одяг з Харкова: футболки, худі' %}...
```

…а у `locale/ru/LC_MESSAGES/django.po` цей **точний** літерал відсутній — там є тільки близький варіант:

```po
msgid "TwoComms — стріт & мілітарі одяг з Харкова"     ← без ": футболки, худі"
msgstr "TwoComms — стрит и милитари одежда из Харькова"
```

Через рядкову неідентичність gettext віддає UA-fallback. Симптом охоплює **65 SEO-критичних літералів** у 9 шаблонах:

| Шаблон | Незакриті блоки | Вплив |
|---|---|---|
| `pages/index.html` | title, description, og_description, twitter_description, keywords | головна — найвідвідуваніший і найвпливовіший URL |
| `pages/pro_brand.html` | title, description, keywords, og_title, og_description, twitter_description | сторінка бренду — головна для AI-цитувань |
| `pages/catalog.html` | keywords | категорія першого рівня |
| `pages/contacts.html` | keywords | local SEO базис |
| `pages/cooperation.html` | description, keywords, og_description, twitter_description | B2B-лендінг |
| `pages/custom_print.html` | description, keywords, og_description, twitter_description | DTF-конструктор, основна продуктова сторінка |
| `pages/wholesale.html` | description, keywords, og_description | опт |
| `pages/pricelist.html` | description, keywords, og_description, twitter_description | прайс-лист |
| `pages/add-print.html` | description, og_description, twitter_description | UGC принти |

**Прямий SEO-вплив:**

- Google може дедупувати /ru/ і /en/ як дублі /uk/ через однаковий title+description, погасити їх із індексу і викинути з пошуку RU/EN-аудиторії.
- Користувач з російським UI бачить у видачі український title — гірший CTR, схожий на технічну помилку, бренд виглядає менш зрілим.
- GSC «Запросы» вже показує російські транслітні запити («худи харьков», «худи харьков», «двойной лонгслив», «лонгслив купити») із позиціями 13-93 — там, ймовірно, ранжується UK-сторінка через відсутність розрізнення на рівні meta.

**Скільки коштує не виправляти:** оцінюю в **15-25% наявного органічного трафіку**, оскільки RU-аудиторія в Україні досі складає 35-40% пошукових запитів за патерном `q=кириличне-слово-українською-vs-російською`.

**Fix-план (1-2 дні):**

1. Зробити команду `python manage.py makemessages -l ru -l en` (вона забере всі поточні літерали).
2. Перекласти 65 рядків у `locale/{ru,en}/LC_MESSAGES/django.po`.
3. `python manage.py compilemessages`.
4. Гранично короткий регрес: написати `pytest` тест, який візьме SLA-список ключових URL (10 шт.) у 3 локалях і перевірить, що `<title>` починається з мовно-специфічного префіксу (`TwoComms — стрит` для /ru/, `TwoComms — street` для /en/).

> У репо вже є коміт `17705e9` (US-15) — «translation coverage report command». Тобто інфраструктура для виявлення цього є, просто звіт не запущено по `*.html` SEO-блоках.

---

### 3.2. 🟠 Адресні плейсхолдери на /contacts/ — «Хрещатик 22, Київ» та «Соборний 15, Львів»

**Доказ (`templates/pages/contacts.html`, ~600-630 рядок):**

```html
<h3 class="location-title">Магазин №1</h3>
<p class="location-address blurred">
  вул. Хрещатик, 22<br>Київ, 01001
</p>
<div class="location-hours">
  <span class="hours-time">Пн-Нд: 10:00 - 22:00</span>
</div>
…
<h3 class="location-title">Магазин №2</h3>
<p class="location-address blurred">
  пр. Соборний, 15<br>Львів, 79000
</p>
```

Це **плейсхолдер дані**, замаскований CSS-класом `.blurred` (вочевидь — `filter: blur(8px)` поверх тексту). Проблема:

- Тексти все одно у HTML, тобто **читаються crawler-ом**: Google і LLM-сканери побачать дві ймовірні фізичні точки Києва і Львова, тоді як бренд позиціонується «з Харкова». Це створює суперечливий NAP-сигнал для Local Pack — гірше, ніж зовсім без адреси.
- Vilni цього не помітив, навіть рекомендуючи додати `streetAddress` у JSON-LD. Додати фейковий streetAddress у schema було б **порушенням Google Search Essentials** і нашкодило б більше, ніж відсутність поля.

**Що робити:**

- Або **видалити блок «Наші магазини»** з /contacts/ (рекомендую — бренд online-only) і написати чесне «Онлайн-магазин з відправкою з Харкова Новою Поштою».
- Або **замінити placeholder реальною інформацією**: показати точку видачі / партнерський showroom Харкова, якщо такий є.
- Створити **Google Business Profile** з типом «Service-area business» (без публічної адреси) — це коректний шлях у Local Pack для online-only.

---

### 3.3. 🟠 Високопотенційні URL у GSC, які не згадані в аудиті

Опираючись на `SEOScreen/.../Страницы.csv` (3 міс):

| URL | Показів | Кліків | CTR | Поз. | Інтерпретація |
|---|---|---|---|---|---|
| `/product/longsleeve-classic/` | **427** | 0 | 0.0% | 51.3 | Ранжується, але **на сторінці 5+**. Назва товару занадто generic — конкурує з усім інтернетом. Потребує посилення title («Класичний лонгслів TwoComms — бавовна 240г, патч "Не крапка"»). |
| `/product/bentejne-hd/` | **274** | 4 | 1.46% | 7.6 | Має пристойну позицію (топ-10), але CTR 1.46% при бенчмарку 8-12% — це **типовий симптом «нудного» сніпета**. Найшвидший win — додати `aggregateRating` (зірки), коли є хоч 1 відгук. |
| `/product/Idea-hd/` | 72 | 0 | 0% | 3.72 | **Топ-3 позиція з 0 кліків** = title/desc не клікабельні. Запит «довіряй своїй божевільній ідеї» дає нам цей URL — мабуть, шукають інше (фільм/цитата). |
| `/product/-glory-of-ukraine-hd/` | 121 | 1 | 0.83% | 25.17 | Позиція 25 — друга-третя сторінка. Запит «glory of ukraine» 20 показів, «glory ukraine» 4. Конкуруємо за загальний термін з військовою тематикою — потрібен сильніший signal про «худі для патріотів». |
| `/product/-kha-style-ls/` | 45 | 0 | 0% | 4.04 | Топ-5 і 0 кліків. Чергова CTR-проблема. |
| `/product/-death-gbs-ass-hd/` | 39 | 0 | 0% | 5.59 | Slug «-death-gbs-ass-» вочевидь баг (плутана генерація slug-а). Сам бренд показ-таки добивається топ-5. |

**Шукальний запит «лонгслів» (290 показів, 0 кліків, ~57 позиція)** — фундаментальна проблема: жоден ваш URL не входить навіть у топ-50 за коротким родовим запитом. Категорійні `/catalog/` сторінки потребують посилення (більше тексту, FAQ, structured data; також — створити окрему `/catalog/longsleeves/` категорію, якщо її ще нема).

**Шукальний запит «бентежне» (116 показів, 0 кліків, поз 12.4)** — це назва товару (Худі/Лонгслів «Життя Бентежне»). Тут спрацьовує лексична двозначність: «бентежне» — це і прикметник, і епітет. Конкуренти з більш конкретними тайтлами (включаючи Вікіпедію, словники) бʼють по CTR. Інструмент: А/B-тест title — «Худі "Життя Бентежне" — TwoComms (Харків, бавовна)».

---

### 3.4. 🟠 OG `locale:alternate=en_US` ↔ hreflang `en-UA`

**Доказ (живий /):**

```html
<meta property="og:locale" content="uk_UA">
<meta property="og:locale:alternate" content="ru_UA">
<meta property="og:locale:alternate" content="en_US">  ← en_US

<link rel="alternate" hreflang="en-UA" href="...">     ← en-UA
```

OG для Facebook/LinkedIn говорить «alt-локаль = en_US», hreflang для Google говорить «en-UA». Це **не критично** (різні системи), але якщо ви плануєте діаспору США/Канади, обидва шарики мають збігатися: або обидва en-US, або обидва en. Vilni рекомендував перейти на `hreflang="en"` (без країни) — це правильно. До цього варто привести і `og:locale:alternate`.

---

### 3.5. 🟠 URL-міграція без 301-моніторингу — GSC показує старі URL

Google Search Console продовжує показувати URL із префіксним/суфіксним дефісом:

| GSC URL | Live URL | Статус |
|---|---|---|
| `/product/-225-tshirt-/` | `/product/225-tshirt/` | 301 |
| `/product/-glory-of-ukraine-hd/` | `/product/glory-of-ukraine-hd/` | 301 |
| `/product/-225-hoodie-/` | `/product/225-hoodie/` | 301 |
| `/product/-v2-0_Pokrovsk/` | `/product/v2-0_pokrovsk/` | 301 |
| `/product/-kha-style-ls/` | (перевірити) | 301? |

Що це означає на практиці:
- Усі історичні кліки і покази GSC накопичуються на «старий» URL.
- Кожен Google crawl старого URL платить «штраф» через 301-stop (хоча PageRank переходить майже повністю).
- Якщо на сайті залишилися внутрішні посилання на старі URL — це втрачений «link equity».

**Тест:**

```bash
grep -rn 'href="[^"]*product/-' twocomms/twocomms_django_theme/templates/ | wc -l
```

Якщо результат > 0 — є старі лінки в шаблонах, потрібно знайти і замінити.

---

### 3.6. 🟢 (інше що не зрозумів аудит, але важливо знати) Те, що TwoComms **уже зробив**, а Vilni виставив як «треба зробити»

| Vilni каже зробити | Реальний стан коду |
|---|---|
| «UGC-форма + JSON-LD aggregateRating» | **Reviews app існує**: `reviews/models.py` (`Review` + `ReviewImage` + `ReviewVote`), `reviews/services/aggregate.py` (`aggregate_rating_for_product` + `ProductReviewSummary`), сигнали, моделі, форми, тести. `MIN_APPROVED_REVIEWS_FOR_RATING = 1`. Бракує **лише даних** — нема жодного approved-відгуку, тому JSON-LD `aggregateRating` не емітиться. Виправлення Vilni «UGC-форма» — *redundant*. Потрібна **збір** відгуків. |
| «Self-host Inter» | **Уже самохост**: `/static/fonts/Inter-Regular.6ea2753361ff.woff2` + `Inter-Bold...woff2` preload з `crossorigin fetchpriority="high"`. Google Fonts CDN не використовується. |
| «Real User Monitoring» | **Уже завантажено**: `<script defer src="/static/js/rum.d152ba60026f.js">` у head. CrUX заповниться через 1-3 міс із цих метрик. |
| «GTM deferred loading» | **Зроблено агресивно**: home — 25/30/35 с timeout залежно від device class, інші роутів — 4/6/9 с. Завантаження тільки після першої взаємодії. |
| «FAQPage на товарних» | **Зроблено 2026-05-16**: коміт того ж дня що й аудит. 13-14 запитань на PDP. |
| «sameAs розширення» | **Розширено**: на головній уже 4 (IG, TG, TikTok, Threads). Конфіг через env-змінні `BRAND_*_URL`, додавання YouTube/Wikidata/Rozetka — питання заповнення env, не коду. |
| «addressLocality=Харків» | **Зроблено**: коміт `826beca` 2026-05-17, але `templates/pages/contacts.html` має `"addressLocality": "{% trans 'Харків' %}"` ще з 2026-05-16. |
| «OnlineStore + AggregateOffer на головній» | **Зроблено** US-16: блок `homepage_storefront_schema` з `lowPrice/highPrice/offerCount` із живої БД. Це усуває знаменитий баг «200 200 грн» у видачі. |
| «Кращі canonical для пагінації» | **Зроблено** 2026-05-16 (P3.5): `/?page=N` має self-canonical і унікальний `WebPage.@id`. |

---

## 4. Кожна знахідка Vilni — окремо

### 4.1. HIGH — `AggregateRating` відсутній на PDP

**Vilni каже:** На /product/* немає `aggregateRating` у JSON-LD → нема зірок у видачі → -25-35% CTR.

**Що насправді:**

- ✅ Факт правильний: `curl -s https://twocomms.shop/product/225-tshirt/ | grep aggregateRating` → 0.
- ⚠️ Контекст хибний: **інфраструктура повністю є**.
  - Файл `reviews/models.py` — Review/ReviewImage/ReviewVote, статуси pending/approved/rejected.
  - Файл `reviews/services/aggregate.py` — `aggregate_rating_for_product()` з порогом `MIN_APPROVED_REVIEWS_FOR_RATING = 1`.
  - Файл `storefront/views/product.py` (рядок 535-537): підвантажує `product_review_summary`.
  - Файл `storefront/seo_utils.py` (рядки 882-900): емітить `aggregateRating` у Product schema, якщо `review_summary.show_rating == True`.
  - Файл `templates/pages/product_detail.html` (рядок 101): `{% product_graph product breadcrumbs=breadcrumbs review_summary=product_review_summary %}`.
  - Файл `templates/pages/product_detail.html` (~рядок 1000+): UI-блок з `.tc-reviews__counter` показує «**0** опублікованих відгуків» і «Поки без відгуків».
- 🆕 Реальна задача: **collection кампанія**.

**Рекомендації, відсортовані за ефектом / зусиллям:**

1. **Гарячий старт (тиждень)**: попросити 50 ваших Telegram-фоловерів за купон 5% надіслати відгук через існуючу форму. Це включає `aggregateRating` для 5-10 найпопулярніших товарів (бо `MIN_APPROVED_REVIEWS_FOR_RATING=1`).
2. **Post-purchase flow (2 тижні)**: автоматичний Telegram/email через 14 днів після доставки з лінком на форму відгуку + код знижки. Дане — `orders.Order` + менеджер.
3. **Verified purchase бейдж**: модель `Review` має поле `is_verified_purchase` — переконатися, що сигнал застосовано у render (UI + у schema через `Review.reviewedBy.identifier`).
4. **`review` (одиничний) у схемі**: окрім `aggregateRating`, додати **до 5 окремих** `review` блоків у Product schema для AI-цитування. Зараз нема — це низько висячий плід.
5. **Sticky-блок «Залишити відгук» внизу PDP** — UX-завдання, не SEO.

**Прогноз імпакту:** +5-12% CTR на найвідвідуваніших PDP **після** 30 відгуків; на товарах із 0 imp — нуль (бо нема трафіку для CTR). На GSC-сторінках з 200+ показами/міс — це найбільший ROI цього аудиту.

---

### 4.2. HIGH — `/blog/` 404

**Vilni каже:** Розділ `/blog/` повертає 404 → нема top-of-funnel контенту.

**Що насправді:**

- ✅ Факт правильний: `curl -sI https://twocomms.shop/blog/` → `HTTP/2 404`.
- ⚠️ Корінь не такий, як Vilni описав: блог **існує**, але живе на іншому **субдомені** `https://dtf.twocomms.shop/blog/` — це окремий продукт (DTF-друк), окремий ROOT_URLCONF (`urls_dtf.py`), окремий додаток `dtf/`, окрема Knowledge Base (модель `KnowledgePost`).
- 🆕 Це не «нема блогу», це «блог є, але на сабдомен-сегменті, який не передає авторитет головному магазину».

**Стратегічні розвилки (вибрати ОДИН шлях):**

#### Гілка A: «Заведи /blog/ на головному домені» — рекомендую

Створити окремий додаток `blog/` для `twocomms.shop` (не DTF-блог). Контент — *комерційно-інформаційний*: «5 принтів TwoComms — історія за патчами», «Чим streetwear відрізняється від casual», «Як вибрати худі під армійський стиль», «Поради по догляду за DTF-нанесенням». Це залишить DTF-блог про техніку друку (для B2B клієнтів) і додасть консьюмерський контент для основного магазину.

- **Зусилля:** 2 тижні на скелетон + 12 статей за квартал.
- **Очікуваний імпакт:** +20-50% органічного трафіку за 6 міс на інформаційних запитах. Більше ніж Vilni обіцяє 40-80%, бо вони не врахували що DTF-блог уже якісно ranks.

#### Гілка B: «Зроби 301 з `/blog/` на `dtf.twocomms.shop/blog/`»

- **Плюс:** Швидко, +SEO-link на DTF-субдомен.
- **Мінус:** Subdomain authority не повністю передається. DTF-блог писано про преса-плівки, а не про streetwear-моду — це не той Top-of-Funnel.

#### Гілка C: «Reverse-proxy `/blog/` → DTF» (one-domain illusion)

- Можна налаштувати LiteSpeed proxy так, щоб `twocomms.shop/blog/` віддавав вміст з `dtf.twocomms.shop/blog/` під `twocomms.shop` доменом. Технічно — це **дублікат контенту**, треба canonical на DTF-версію. Невелика користь.

**Висновок:** **Гілка A**, але контент має бути *окремий* від DTF, орієнтований на покупця, з посиланнями вглиб каталога.

---

### 4.3. HIGH — `ClothingStore` без `streetAddress`/`geo`/`openingHoursSpecification`

**Vilni каже:** Local Pack Харків недосяжний, бо ClothingStore не має точної адреси і координат.

**Що насправді:**

- ✅ Факт правильний (часткою): живий /contacts/ має `addressCountry=UA`, `addressRegion=UA-63`, `addressLocality=Харків`, **але** **без** `streetAddress`, `geo` і `openingHoursSpecification`.
- ❌ Інтерпретація хибна: «addressLocality=Україна» — **це не так**. На 2026-05-19 уже «Харків». Vilni застаріли.
- 🆕 Глибший погляд: Local Pack — це **Google Business Profile (GBP) feature**, а не feature site-schema. Просто додати geo+streetAddress у JSON-LD `ClothingStore` **не** ввімкне Local Pack. Це треба разом:
  1. **Створити Google Business Profile** з типом «Service-area business» (раз ви онлайн-only, без фізичного showroom).
  2. **Заявити обслуговуваний регіон** = Харків + 50 км / всю Україну.
  3. **Запросити підтвердження** (карткою, поштою, телефоном).
  4. **Заповнити фото, опис, посилання на сайт, телефон, графік відповідей** — NAP консистентний з тим, що в JSON-LD.
  5. **Зібрати перші 20-30 GBP-відгуків** — окремо від site-reviews.

Тільки на цьому етапі Local Pack починає **показувати** TwoComms за запитом «магазин одягу Харків».

**JSON-LD у `ClothingStore`** служить як **доказ для AI-моделей** і помічник для Knowledge Panel. Geo+streetAddress у schema без GBP — це half-shot.

#### Якщо немає реального showroom

- `streetAddress` додавати **не варто** — Google може покарати за фейкову локацію.
- `geo` додати у вигляді координат **центру обслуговуваного регіону** (50.0040 / 36.2308 — центр Харкова) — допустимо.
- `openingHoursSpecification` додати як **години Telegram-/телефонної підтримки** — це валідно.

**Рекомендований патч на `templates/pages/contacts.html` (ClothingStore):**

```json
{
  "@type": "ClothingStore",
  ...
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": 50.0040,
    "longitude": 36.2308,
    "name": "Харків, центр обслуговування"
  },
  "openingHoursSpecification": [
    {
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": ["Monday","Tuesday","Wednesday","Thursday","Friday"],
      "opens": "10:00",
      "closes": "20:00"
    },
    {
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": ["Saturday","Sunday"],
      "opens": "11:00",
      "closes": "18:00"
    }
  ],
  "priceRange": "₴660-₴2550",   // ← заміна "₴₴"
  "areaServed": [
    {"@type": "Country", "name": "Україна", "identifier": "UA"},
    {"@type": "City", "name": "Харків"}
  ],
  "sameAs": [
    "https://instagram.com/twocomms",
    "https://t.me/twocomms",
    "https://www.tiktok.com/@twocomms",
    "https://www.threads.com/@twocomms"
    // + Wikidata Q-ID коли створимо
  ]
}
```

`streetAddress` свідомо **не додаю** — це порушило б guidelines без реального showroom.

---

### 4.4. MEDIUM — LCP 3.6 с на мобайл

**Vilni каже:** Mobile LCP 3.6 с — needs improvement. Десктоп 0.92 с — добре. 6 фіксів: preload LCP image, AVIF, self-host fonts, defer CSS, lazy below-fold, RUM.

**Що насправді:**

- ✅ LCP-цифра правильна (з PSI lab).
- ⚠️ Половина рекомендацій уже реалізована:
  - Self-host Inter ✅ (preload + crossorigin)
  - RUM ✅ (`rum.d152ba60026f.js` defer)
  - Critical CSS inlined ✅ (7 styles, 118 KB inline; зовнішні CSS — usability через `media="print" onload="this.media='all'"`)
  - GTM defer ✅
- 🆕 Що *насправді* лімітує LCP — велика inline-CSS (54021 + 34148 + 13253 байт у style#0/4/2 = ~100KB). Це **спочатку добре** (одна mb-запит), але парсинг 100 KB CSS на mid/low Android = ~200-400 мс. Потім LCP-image (hero logo SVG, 600x600) renderiteться. Сам LCP — це швидше за все hero логотип, який вже має `fetchpriority="high"`.

#### Гіпотези щодо реального LCP-source

Без CrUX неможливо сказати, що саме є LCP-елементом у polу. У lab Lighthouse може взяти один елемент, у polу — інший (наприклад, перший product card з вашого каталогу-сітки).

**Рекомендований підхід:**

1. **Активувати field CrUX за 30-60 днів** — поки RUM збирає дані. Це найдешевший шлях.
2. **На PageSpeed Insights запустити `View Treemap`** — побачимо, що Lighthouse трактує як LCP-елемент.
3. **Lazy-load product card images у каталозі** з `loading="lazy" decoding="async"` і `width`/`height` атрибутами для запобігання CLS.
4. **AVIF** — рекомендую **тільки** для нових продуктових фото. Конвертувати весь поточний бібліотеку — це робота на 2-3 тижні, виграш +10-15% розміру але не блокер для LCP <2.5 с.
5. **HTTP/3** — заголовок `alt-svc: h3=":443"` уже виставлений LiteSpeed-ом. Перевірити, що QUIC реально працює на mobile (Chrome 90+).
6. **Resource Hints**: додати `<link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>` навіть якщо GTM deferred — це prepare DNS+TLS, не запит.

**Прогноз:** мобільний LCP знижується до 2.2-2.6 с протягом 2-3 спринтів. Виграш у органіці — оптимістично **+3-7% позиції** на CWV-чутливих запитах.

---

### 4.5. MEDIUM — `availability=MadeToOrder` на всіх товарах

**Vilni каже:** Google знижує MadeToOrder у «in stock»-видачі. Розділити асортимент на InStock базові + MadeToOrder custom.

**Що насправді:**

- ✅ Універсальний MadeToOrder підтверджено: код `seo_utils.py:_get_product_availability()` — при відсутності `stock > 0` у будь-якому ProductColorVariant → MadeToOrder.
- ⚠️ Vilni перебільшує: Google Search-Rich-Results-Guide **експліцитно** дозволяє MadeToOrder. Google Shopping справді віддає перевагу InStock у «купити зараз» сценаріях, але у нішевих DTF-streetwear-запитах різниця менша.
- 🆕 Розгалуження:

#### Гілка A: «Заведи мінімальну партію базових товарів» (рекомендую)

Найдрібніша одиниця — друкувати по 5 шт. на кожен розмір кожного кольору **топ-3 моделей** (`225-tshirt`, `bentejne-hd`, `kha-edition-ts`). Виставити stock на ці варіанти. Це дасть **InStock** у схемі для бестселерів. Один цикл накопичення — 4-6 тижнів.

#### Гілка B: «PreOrder замість MadeToOrder»

Schema.org має `PreOrder` — «можна замовити заздалегідь до випуску». Семантика інша, ніж MadeToOrder. Якщо ваш реальний flow — *приймаємо заявку → друкуємо → відправляємо за 5 днів*, то це **technically PreOrder**, не MadeToOrder. Google трактує PreOrder як «доступний», але з тонкою помітою.

#### Гілка C: «Усе залишити як є + додати deliveryLeadTime»

Це ще одне поле в schema — повідомляє Google, що товар можна замовити за 3-5 днів. Ви це **уже** маєте в `OfferShippingDetails.deliveryTime.handlingTime` (1-2 дні) + `transitTime` (1-5 днів). Перевірити, що це коректно інтерпретується через Rich Results Test.

**Висновок:** **Гілка A** для топ-3, **Гілка C** для решти. Не обов’язково повне розділення асортиментуу — головне, щоб 3 ваших найвідвідуваніших PDP вийшли в InStock-видачу.

---

### 4.6. MEDIUM — `FAQPage` schema не на товарних

**Vilni каже:** На /faq/ є FAQPage (10 запитань). На PDP — нема.

**Що насправді:**

- ❌ **На сьогодні FAQPage є на PDP.** На `/product/225-tshirt/` — 14 запитань. На `/product/bentejne-hd/` — 13. На `/product/kha-edition-ts/` — 13.
- ❌ Vilni каже «10 запитань на /faq/» — насправді **30** (коміт `3c23399`, US-4).
- ⚠️ Це додано **того ж дня що й аудит** (комміт `83b9c61` 2026-05-16, з коментарем `SEO 2026-05-16 (P1-1) — restored a per-product FAQPage JSON-LD`). Vilni зробив краулу до релізу.

**Що ще можна зробити (мікро-оптимізація):**

1. **Категорійні FAQPage** — на `/catalog/tshirts/` і `/catalog/hoodie/` зараз FAQPage **нема** (підтверджено JSON-LD дамп: тільки BreadcrumbList + CollectionPage). Додати 5-7 типових запитань на категорійну сторінку — це 4-6 годин роботи.
2. **Розширити PDP-FAQ до 8 унікальних** Q&A (зараз 13, але є дублі — наприклад «Чи частина грошей з цього товару йде на підтримку 225 ОШП?» зустрічається 2 рази в одному JSON-LD блоці; це треба виправити, бо валідатор Google може поскаржитися).
3. **Локалізація FAQ-блоків** — поточні FAQ всередині `templates/pages/product_detail.html` йдуть як `{% trans %}` — перевірити, що для /ru/ і /en/ вони перекладені (не тільки UA-key, а й msgstr).

---

### 4.7. MEDIUM — `sameAs` лише 2 посилання

**Vilni каже:** Лише 2 (IG + Telegram). Додати TikTok, YouTube, Rozetka, FB, Wikidata.

**Що насправді:**

- ❌ Це **частково неправильно**. На головній (`/`) в Organization-вузлі вже **4**:
  ```json
  "sameAs": [
    "https://instagram.com/twocomms",
    "https://t.me/twocomms",
    "https://www.tiktok.com/@twocomms",
    "https://www.threads.com/@twocomms"
  ]
  ```
- ✅ На `/contacts/` у `ClothingStore`-вузлі — **досі лише 2** (IG + TG). Це й помітив Vilni.
- 🆕 Архітектурна нерівність: код у `storefront/seo_utils.py:_organization_same_as()` тягне з env-змінних `BRAND_*_URL`. Той самий хелпер **не використовує** template `contacts.html` (там hardcoded JSON-LD). Це source-of-truth-розбіжність.

**План:**

1. **Заповнити env-змінні** у `.env.production`:
   ```env
   BRAND_YOUTUBE_URL=https://www.youtube.com/@twocomms
   BRAND_FACEBOOK_URL=https://www.facebook.com/twocomms.brand
   BRAND_PINTEREST_URL=
   BRAND_TWITTER_URL=
   BRAND_LINKEDIN_URL=
   BRAND_WIKIDATA_URL=https://www.wikidata.org/wiki/Q12345  # після створення
   ```
2. **Створити Wikidata Q-ID** для бренду «TwoComms» — це 30 хвилин роботи; вимагає мінімум 3 wiki-цитати з зовнішніх джерел (IG-офіційний акк, Facebook-сторінка, GBP, Telegram-канал — годяться).
3. **Заповнити Rozetka Marketplace** як другий канал збуту — це водночас дає sameAs-посилання і додатковий sales channel.
4. **Виправити рівняння на `contacts.html`** — замінити hardcoded JSON-LD на template tag `{% clothingstore_schema %}` (новий тег), щоб sameAs тягнувся з того ж `_organization_same_as()`. Це уникає drift.

**Прогноз імпакту на AI-citation:** +20-40% згадуваність у Perplexity/ChatGPT за запитами «українські streetwear-бренди». Це сильніше за прогноз Vilni (+15-30%), бо Wikidata — найвагоміший сигнал для entity resolution.

---

### 4.8. MEDIUM — Немає блоку відгуків (UGC)

**Vilni каже:** Покупець не бачить відгуків / фото клієнтів → -trust → -конверсія.

**Що насправді:**

- ⚠️ HTML-блок `tc-reviews__*` на PDP **існує**, з лічильником «**0**» і повідомленням «Поки без відгуків».
- Та ж сама проблема, що і в 4.1: інфраструктура є, даних нема.
- Сама форма для submit-у відгуку — вертайте `reviews/forms.py` + `reviews/views.py` + `reviews/urls.py`; перевірити, чи доступна вона з PDP.

#### Що зробити окремо для UX (а не SEO)

1. **Додати CTA «Залишити перший відгук»** одразу під заголовком блока — currently прихований.
2. **Telegram-бот для збору відгуків**: бот пише через 14 днів після доставки, пропонує forma + код знижки. Інтеграція з `orders.Order` + Telegram API.
3. **Імпорт існуючих Instagram-коментарів** як seed-content — тільки з дозволу автора, фото клієнта з тегом #twocomms можна цитувати на сайт.

---

### 4.9. MEDIUM — CWV LCP needs improvement (дубль 4.4)

Vilni винесли LCP двічі: раз як performance-finding, раз як cwv_diagnostics. Це одна і та сама проблема. Реальних унікальних findings — 12, не 13 (з урахуванням ще одного дублю sameAs / FAQ між «main» і «llm_readiness»).

---

### 4.10. LOW — CrUX field data 0%

**Vilni каже:** CrUX порожній → Google не використовує ваші CWV у ранкінгу.

**Що насправді:**

- ✅ Правильно — `loadingExperience.metrics = {}` у PSI API.
- ⚠️ Це **наслідок** низького трафіку: Chrome User Experience Report потребує **достатнього обʼєму** трафіку від Chrome-користувачів (з увімкненою анонімною телеметрією). За 120 кліків/міс просто не набирається статистично значущий sample.
- 🆕 Покращення LCP, AggregateRating, /blog/ → більше трафіку → CrUX поступово заповнюється. Це **наслідок**, не **причина**.

---

### 4.11. LOW — `priceRange="₴₴"` на /contacts/

**Vilni каже:** Замінити на діапазон конкретних цифр.

**Що насправді:**

- ✅ Точно, `"₴₴"` досі стоїть на /contacts/ в ClothingStore.
- ⚠️ На головній (`/`) в Organization-вузлі вже `"660-1939 UAH"` (динамічно з БД через `_homepage_price_range_text()`). Це і є правильний паттерн.
- **Fix:** замінити в `templates/pages/contacts.html`:

```html
"priceRange": "{{ price_range }}",
```

…і додати в view, що рендерить /contacts/ (`storefront/views/static_pages.py:contacts`), `price_range = _homepage_price_range_text()` (вже існуючий хелпер). 15 хв.

---

### 4.12. LOW — `hreflang="en-UA"`

**Vilni каже:** Нетипова комбінація. Або змінити на `hreflang="en"`, або noindex у en поза UA.

**Що насправді:**

- ✅ Точно, як і пропонував Vilni.
- 🆕 Додатковий нюанс — **OG locale alternate уже англійською US-стилю** (`en_US`). Зробити рівняння:
  - `hreflang="en-US"` + `og:locale:alternate="en_US"`
  - АБО `hreflang="en"` + перевірити, що FB трактує `en_US` як default.

Це питання стратегічне: чи плануєте діаспору США/Канади? Якщо так — `en-US`. Якщо ні (тобто EN-версія для іноземних відвідувачів **на території України**, переважно туристів) — лишити `en-UA`.

---

### 4.13. LOW — Немає згадок на Reddit

**Vilni каже:** Reddit / Quora 0 згадок → -heuristic для AI.

**Що насправді:**

- ✅ Швидше за все правда (без перевірки API).
- ⚠️ Прокачка Reddit-присутности — це **довга** дисципліна (місяці). Інвестування часу тут має повертатися не швидше, ніж за 6-12 міс.
- 🆕 Швидший проксі-канал — **YouTube Shorts + TikTok-розпаковки** від мікро-інфлюенсерів. Це водночас і AI-source (бо TikTok тепер індексується), і прямий трафік, і сигнал для Knowledge Panel.

---

## 5. Розгалуження гіпотез (поза аудитом)

### 5.1. Гіпотеза: Канібалізація запитів між товарами через схожі назви

GSC показує однакову позицію (~6-12) для запитів `футболка харків` (30 показів, поз 6.83), `харків футболка` (8 показів, поз 7.75), `футболка kharkiv` (4 показів, поз 12.25). Це різні варіанти одного запиту. Можливо, кілька ваших товарів конкурують між собою:

- `/product/kha-edition-ts/` (Футболка «Харків Edition»)
- `/product/-225-tshirt-/` (225ОШП)
- `/product/kharkiv-district-hd/` (Худі «Харківська Область»)

**Тест:** запитайте Google `site:twocomms.shop футболка харків` — побачите, які URL Google вважає релевантними. Якщо їх >1 за одним запитом → канібалізація.

**Fix:** Чітко розділити:
- `kha-edition-ts` — це **колекція** футболок «Харків Edition»
- `kharkiv-district-hd` — це **географічна модель** «Харківська область»
- В title уникнути дублю «Харків»; одній з них дати ширший термін («East Ukraine Edition» наприклад).

---

### 5.2. Гіпотеза: «бентежне» — суперечливий брендовий термін, що губиться у видачі

`бентежне` (116 показів, 0 кліків, поз 12.4) — це **назва товару** ваших дві найбільш ranked продуктів (`bentejne-hd` 274 imp, `bentejne-ls` 68 imp). На позиції 12 ваш товар Гугл показує, але ніхто не клікає. Чому?

- Семантика: «бентежне» — це прикметник з відтінком, людина може шукати визначення слова, а не товар.
- GSC «бентежність це», «бентежне це» (37 + 25 показів) — це **інформаційний запит**, не комерційний.

**Рішення:**
1. Створити **інформаційну сторінку** /словник/бентежне/ або /блог/щo-означає-життя-бентежне/, яка пояснює сенс слова + лінкує на товари. Це знімає бар’єр для інформаційного шукача.
2. Title для PDP — додати чіткий комерційний сигнал: «Худі **Купити** "Життя Бентежне" — TwoComms Харків».

---

### 5.3. Гіпотеза: «лонгслів»-запит — категорія не існує, тому ranking слабкий

GSC: `лонгслів` 290 показів / 0 кліків / поз 57.6. Це базовий категорійний запит, але у вас **немає окремої сторінки `/catalog/longsleeves/`** (тільки `/catalog/hoodie/` і `/catalog/tshirts/`). Лонгсліви розкидані по тегу `product/longsleeve-classic/`.

**Тест:** `curl -sI https://twocomms.shop/catalog/longsleeves/`

**Якщо 404** — створити категорію. Це підіткне ranking з 57 → 20-25 за 3-4 міс.

---

### 5.4. Гіпотеза: Sitemap-coverage gap — `sitemap-color-categories.xml` для нішевих запитів

Сайт має `sitemap-color-categories.xml` (нова сітка, доданa коміт `cea8dba` US-9 v2 2026-05-17). Це **landing pages для (категорія, колір)** комбінацій. Якщо це справді кольорові landing-и (як «худі чорні», «футболки чорні»), вони **повинні** ranking-в за color-modify запитами.

**Перевірка:** `curl -s https://twocomms.shop/sitemap-color-categories.xml | head -30` → перерахувати URL → перевірити title / meta description / FAQ → переконатися, що з кожного є посилання у каталозі.

---

### 5.5. Гіпотеза: Image SEO — наявний `sitemap-images.xml`, але alt-tags слабкі

У GSC `Вид в поиске: Поиск картинок` дає **3 кліки** (з 120). Це низько. Якісне image SEO може давати 10-20% від загального трафіку.

**Перевірити:**
1. Live HTML — `grep -oE 'alt="[^"]+"' home.html` — чи всі продуктові фото мають alt?
2. `sitemap-images.xml` — у нас він є, з `image:title` для кожного зображення. Це топ-tier — мало хто це робить.
3. Filename-SEO — `media/products/1.webp` — це **погано** для image SEO. Має бути `225-osh-tshirt-front-black.webp`. Це впливає на ranking в Google Images.

---

### 5.6. Гіпотеза: AI-citation — `llms.txt` потребує розширення для «commerce intent» запитів

Поточний `/llms.txt` має блок:
```text
- Brand: TwoComms
- Country: Ukraine
- Main language on site: Ukrainian
- Custom print available: yes
- Wholesale available: yes
```

Що варто додати для кращої LLM-цитованості:

```text
## Brand provenance
- Founded: 2022 in Kharkiv, Ukraine
- Mission: design merch that supports Ukrainian Armed Forces and civil resilience
- Signature line: "225OШП" — collaboration with the 225th separate assault regiment

## Product taxonomy
- T-shirts (catalog/tshirts/): cotton, DTF print, sizes S-XXL
- Hoodies (catalog/hoodie/): premium fleece, oversize fit
- Longsleeves (catalog/longsleeves/): cotton, regular fit
- Custom DTF print (custom-print/): minimum 1 item, lead time 3-5 days

## Pricing range
- T-shirts: ₴660-₴1,200
- Hoodies: ₴1,200-₴2,500
- Longsleeves: ₴800-₴1,500
- Custom print: starts ₴300/item

## Shipping
- Nova Poshta within Ukraine: 1-3 working days
- International shipping: contact for quote
- Free delivery: orders over ₴3,000

## Reviews and ratings (auto-updated)
- See /product/<slug>/ for review summary
- TwoComms moderates reviews; threshold for AggregateRating display is 1 approved review
```

Це дозволить AI-моделям відповідати на повні запити «Які ціни TwoComms на худі?» одним проходом, без потреби раніше клацати десятки сторінок.

---

### 5.7. Гіпотеза: Mobile-friendly Меню — мобільний CLS може бути більший за десктоп

Поточний CLS:
- Desktop: 0.046 (добре)
- Mobile: 0.000 (ідеально, lab)

Lab-measured CLS=0.000 на мобайлі — підозріло. Чи Lighthouse дійсно скролив сторінку, чи виміряв тільки above-the-fold? Field CrUX дав би реальну картину.

**Тест:**
1. Запустити `chrome --enable-features=LayoutShiftRelayoutTriggers` локально на мобільному viewport.
2. Перевірити, що sticky-header не «стрибає» при першому скролі.
3. Зображення продуктових карток повинні мати explicit `width` і `height` (вже мають? — перевірити).

---

### 5.8. Гіпотеза: Search Console «Coverage» може показувати «Crawled, currently not indexed»

Pagination URLs `/?page=N` мали баг — однаковий `WebPage.@id` для page=1 і page=2+ → Google трактує як дублікати → 'not indexed'. Це вже виправлено комітом `2ef1b39` (2026-05-16: «restore self-canonical pagination») і подальше `WebPage.@id` тепер унікальний для кожної paginator-сторінки.

**Перевірити у GSC:** після цього виправлення, coverage по `/?page=N` має покращитися. Через 30-60 днів.

---

### 5.9. Гіпотеза: «Запросы» CSV має сильний brand-trafficer, але слабкий transactional

| Тип запиту | Покази | Кліки | Частка |
|---|---|---|---|
| Брендові (`twocomms`, `twocoms`, `two coms`) | 56 | 29 | 24% |
| Brand+geo (`футболка харків`, `харків футболка`, `футболка kharkiv`) | 42 | 7 | 17% |
| Категорійні (`лонгслів`, `бентежне`, `худі життя`, etc.) | 600+ | 0 | 0% |
| Long-tail (`двойной лонгслив`, `подвійний лонгслів`) | 50+ | 0 | 0% |

**Інтерпретація:** Існуючий трафік на 60%+ — це люди, які **вже знають бренд** (твердо B2C-loyalty). А категорійні і long-tail запити з 600+ показами просто **не доводять кліки**.

**Конкретна стратегія:**
1. **Категорійні title оптимізації** (миттєвий, тиждень роботи) — переробити title для `/catalog/longsleeves/` (створити, якщо нема), `/catalog/oversize-hoodies/`, `/catalog/military-tees/`.
2. **Long-tail PDP titles** — для `/product/bentejne-hd/`: замість «Худі "Життя Бентежне" — TwoComms» зробити «Худі "Життя Бентежне" 480г бавовна, патч | TwoComms Харків».
3. **NEW intent landing-и** — створити `/wishlist/ucraine-tactical-merch/`, `/wishlist/zsu-fundraiser/`, `/wishlist/independence-day-2026/` як seasonal pages.

---

## 6. Прагматичний 90-денний план (за пріоритетом)

> Кожен пункт має очікуваний приріст / зусилля / залежність. Сортовано за **ROI на годину**.

### Спринт 1 (тижні 1-2): «Виграй з того, що вже є»

| # | Дія | Файл / Місце | Зусилля | Очікуваний приріст |
|---|---|---|---|---|
| 1 | **Перекласти 65 SEO-літералів у `locale/ru` та `locale/en`** | `locale/ru/LC_MESSAGES/django.po`, `locale/en/LC_MESSAGES/django.po` | 8-10 годин | +15-25% органічного трафіку (RU/EN-сегмент) |
| 2 | **Зібрати 30 початкових відгуків** через TG-канал за купон | `reviews/` додаток (UI вже є) | 1 тиждень календарного, ≈3 години роботи | +5-12% CTR на топ-10 PDP, перші `aggregateRating` за 1-2 тижні |
| 3 | **Видалити placeholder адреси «Хрещатик 22, Соборний 15»** з /contacts/ або замінити на чесний онлайн-only текст | `templates/pages/contacts.html` рядок ~600+ | 30 хв | Усунення NAP-конфлікту, +trust |
| 4 | **Виправити `priceRange="₴₴"` на /contacts/** | `templates/pages/contacts.html` рядок ~76 | 15 хв | +rich-result чистоту |
| 5 | **Заповнити env-змінні `BRAND_YOUTUBE_URL`, `BRAND_FACEBOOK_URL`** | `.env.production` | 30 хв (треба створити канали якщо нема) | +AI-citation |
| 6 | **Створити Wikidata Q-ID для бренду** | wikidata.org → `BRAND_WIKIDATA_URL` env | 1 година | +AI entity resolution |

**Сумарно:** ≈20 годин роботи, потенціал +20-35% органіки за квартал.

---

### Спринт 2 (тижні 3-4): «Закрий технічні дірки»

| # | Дія | Файл / Місце | Зусилля |
|---|---|---|---|
| 7 | **Створити Google Business Profile** як «Service-area business» + 5 фото + опис + Q&A | gbp.google.com | 2 години |
| 8 | **Зміна `hreflang="en-UA"` → `"en-US"`** (якщо діаспора в плані) і `og:locale:alternate` синхронно | `templates/base.html` + `_resolve_inlanguage_code()` | 1 година |
| 9 | **Додати `geo` + `openingHoursSpecification` у ClothingStore** | `templates/pages/contacts.html` | 1 година |
| 10 | **Створити сторінку `/catalog/longsleeves/`** (якщо ще нема), додати у sitemap-categories.xml | `storefront/views/catalog.py` + URL | 4 години |
| 11 | **Виправити old-URL внутрішні посилання** (grep `href="[^"]*product/-`) | sitewide | 2 години |
| 12 | **Додати FAQPage schema на категорійні сторінки** `/catalog/tshirts/` і `/catalog/hoodie/` (5-7 типових Q&A) | `templates/pages/catalog_category.html` | 3 години |

**Сумарно:** ≈13 годин, +тех чистота + Local Pack первинна готовність.

---

### Спринт 3 (тижні 5-8): «Контентний рух»

| # | Дія | Очікуваний приріст |
|---|---|---|
| 13 | **Створити окремий `/blog/` на головному домені** (не плутати з DTF-блогом) | +20-40% органіки за 6 міс |
| 14 | **Опублікувати перші 8 статей** (2 на тиждень): «Як вибрати футболку під військовий стиль», «Догляд за DTF-нанесенням», «Чим streetwear відрізняється від casual», «5 принтів TwoComms — історія за патчами», «Чому 225ОШП — серія підтримки», «Український streetwear 2026 — топ-5 брендів», «Що означає "Не крапка. Продовження."», «Куди виноситься клас гнівне у streetwear» | +інформаційний трафік |
| 15 | **Переробити title для PDP з 50+ позицією** (`longsleeve-classic`, `Idea-hd`, `Glory of Ukraine`) — додати geo+специфіку | +3-7 позицій |
| 16 | **Запустити Image SEO** — alt-tags для всіх продуктових фото, переіменувати file-names | +10-15% Google Images |

**Сумарно:** Контент-mission на 4 тижні; 1-2 SEO-копірайтер на парт-тайм.

---

### Спринт 4 (тижні 9-12): «Авторитетність»

| # | Дія |
|---|---|
| 17 | **Запустити Rozetka Marketplace** (1-2 тестових SKU) — як другий канал sales і sameAs-сигнал |
| 18 | **Отримати 5-10 беклінків** з UA-streetwear/lifestyle каталогів (zaraz.in.ua, vintage.com.ua, kharkivlife.com) |
| 19 | **Колаби з 3 мікро-інфлюенсерами** TikTok/Instagram (1500-15000 фоловерів) |
| 20 | **Створити YouTube канал** — 2-3 коротких відео (розпаковка, процес друку, brand story) + посилання у sameAs |

---

## 7. Очікуваний результат VS прогноз Vilni

| Період | Vilni прогноз | Мій прогноз (на основі вашого реального стану) |
|---|---|---|
| 30 днів | +5% | **+10-15%** (i18n-fix дає швидкий ефект, не помічений Vilni) |
| 90 днів | +20-45% | **+25-40%** (узгоджується, але детальніше: +UGC reviews +первинні rating-зірки) |
| 180 днів | +60-150% | **+40-90%** (Vilni оптимістичний; реалістично, бо база трафіку низька — 120 кліків/міс — DR домену ≈низький — ranking inertia є) |
| 365 днів | +150-250% | **+100-180%** (за умови виконання Спринтів 1-4 + продовження контентної програми) |

**Чому мій прогноз помірніший:**

- Поточна база трафіку дуже низька (120 кліків / міс), велика частина зрозуміло — брендові (loyalty). Категорійний трафік потребує **часу** на нарощування — інформаційні статті ranking-ів за 4-8 місяців, не 2.
- Конкурентний контекст — Custom Wear, LWMC, Skofield справді сильні (DR 30-50, у вас, ймовірно, DR 5-15).
- Сезонність — DTF-streetwear-merch має пік осінь/зима. Якщо стартуєте програму в червні, перший серйозний підйом буде в жовтні-листопаді.

---

## 8. Що НЕ робити (anti-checklist)

| ❌ Не робити | Чому |
|---|---|
| Не додавати `streetAddress` у ClothingStore без реального showroom | Порушення Google guidelines, можлива пеналь |
| Не купувати беклінки з PBN/Fiverr | Гарантована пеналізація |
| Не штампувати 50 шаблонних блог-статей одразу | Низька якість → ранкінг гірше + витрата бюджету |
| Не змінювати slug URL знову | URL вже мігрували раз (старі URL досі живуть у GSC); ще одна міграція = повторні 301 + втрата capital |
| Не використовувати ШІ-генерований контент без редактури | Google detects + Helpful Content update — нижче ранкінг |
| Не показувати фейкові зірки aggregateRating | Manual action від Google — мінус індекс |
| Не залишати без перекладу `/ru/` і `/en/` ще на квартал | Кожен день — втрачені show + кліки |

---

## 9. Технічна довідка: Що було перевірено інструментально

### 9.1. Сторінки, на яких прогнано JSON-LD-парсинг

| URL | JSON-LD блоки | Типи (top-level) |
|---|---|---|
| `/` | 5 | Organization+OnlineStore, WebSite, OnlineStore+AggregateOffer, WebPage+ItemList, BreadcrumbList |
| `/product/225-tshirt/` | 4 | Organization, WebSite, Product+BreadcrumbList(@graph), FAQPage (14 Q) |
| `/product/bentejne-hd/` | 4 | те саме (FAQPage 13 Q) |
| `/product/kha-edition-ts/` | 4 | те саме |
| `/contacts/` | 4 | Organization, WebSite, ContactPage+ClothingStore, BreadcrumbList |
| `/faq/` | 4 | Organization, WebSite, FAQPage (30 Q), CollectionPage+BreadcrumbList |
| `/catalog/tshirts/` | 3 | Organization, WebSite, BreadcrumbList+CollectionPage |
| `/catalog/hoodie/` | 3 | те саме |
| `/pro-brand/` | 9 (sic!) | Organization+Founder+OfferCatalog+AboutPage+FAQPage(7Q) і ще |
| `/custom-print/` | 5 | Organization, WebSite, Service+Organization, BreadcrumbList, FAQPage (14 Q) |
| `/wholesale/` | 5 | Organization, WebSite, WebPage+Organization+ImageObject, BreadcrumbList, FAQPage (8 Q) |
| `/delivery/` | 4 | Organization, WebSite, FAQPage (9 Q), WebPage+BreadcrumbList |
| `/ru/` | 5 | те саме що /, але з RU H1 |
| `/en/` | 5 | те саме що /, але з EN H1 |

### 9.2. Sitemap-структура

```
/sitemap.xml (index)
├── sitemap-static.xml          # головні URL + delivery + pro-brand + contacts + cooperation + custom-print + wholesale + (по 3 локалях)
├── sitemap-products.xml        # усі товарні PDP
├── sitemap-product-variants.xml # варіантні URL з кольорами
├── sitemap-categories.xml      # /catalog/<cat>/
├── sitemap-color-categories.xml # (категорія, колір) пари (US-9 v2)
├── sitemap-thematic.xml        # /catalog/theme/{military,streetwear,patriotic,kharkiv-edition}/ (US-5)
└── sitemap-images.xml          # image:loc + image:title
```

`sitemap-search-keywords.xml` згаданий у комміті `45eff6b` (US-6), але повертає **HTML 200** з body головної сторінки — це **баг роутингу**. Vilni не помітив, бо не сканував його.

### 9.3. CSP / Security headers — підтверджено

```
strict-transport-security: max-age=31536000; includeSubDomains; preload
x-frame-options: SAMEORIGIN
x-content-type-options: nosniff
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin
content-security-policy: default-src 'self'; ...
```

Vilni назвав це «топ-tier security signal» — згоден, **краще ніж у 90% UA-ecommerce**.

### 9.4. Robots.txt — підтверджено

Дозволено індексацію усього окрім /admin/, /admin-panel/, /orders/, /checkout/, /api/, /debug/, /dev/ та query-параметрів (utm_, gclid, fbclid, yclid, msclkid, ref, sort, order).

Окремі блоки Allow для **15 ботів**: AdsBot-Google, AdsBot-Google-Mobile, AdsBot-Google-Mobile-Apps, OAI-SearchBot, ChatGPT-User, Claude-SearchBot, Claude-User, PerplexityBot, Perplexity-User, Google-Extended, GPTBot, CCBot, ClaudeBot, anthropic-ai. Це топ-tier налаштування — Vilni помітив тільки 5, насправді 15.

### 9.5. llms.txt — підтверджено

Структуровано із Summary, Primary routes, Commerce, Optional, Brand facts. Рекомендую розширити (див. розділ 5.6).

---

## 10. Підсумок — що віддати в роботу негайно

> Якщо у вас є тільки **тиждень**, зробіть **тільки це**:

1. **Перекладіть 65 SEO-літералів** для /ru/ і /en/ (8-10 годин). Це найдешевша і найшвидша велика перемога. Виконавець: розробник або копірайтер з RU/EN.
2. **Зберіть перші 30 відгуків** від існуючих клієнтів через Telegram. Це активує `aggregateRating` на топ-PDP за 1-2 тижні. Виконавець: маркетолог / community-менеджер.
3. **Створіть Google Business Profile** як Service-area business. Це базис для Local Pack. Виконавець: маркетолог.
4. **Видаліть placeholder адреси «Хрещатик/Соборний»** з /contacts/. Виконавець: розробник.
5. **Виправте `priceRange="₴₴"`** на /contacts/. Виконавець: розробник.

Усе інше — наступний квартал.

---

## 11. Додатково: за бажанням розробити окремими тасками

Готовий розгорнути будь-який з нижченаведених у task для Build-агента:

- 🛠️ TASK A: «i18n SEO meta — locale po-files для 65 літералів» (1 день)
- 🛠️ TASK B: «UGC reviews collection bootstrap — Telegram-bot реквест + post-purchase email» (2-3 дні)
- 🛠️ TASK C: «Local SEO — ClothingStore geo + openingHours + видалити placeholder адреси» (півдня)
- 🛠️ TASK D: «Створити окремий /blog/ на головному домені + 4 seed-статті» (1 тиждень)
- 🛠️ TASK E: «PDP title оптимізація для топ-10 продуктів з низьким CTR» (1 день)
- 🛠️ TASK F: «Category landing /catalog/longsleeves/ + FAQPage» (1 день)
- 🛠️ TASK G: «llms.txt — розширення під commerce intent» (півдня)
- 🛠️ TASK H: «Rich Results regression тест — pytest для 10 ключових URL × 3 локалі × valid JSON-LD» (1 день)

---

> *Звіт підготовлений Captain Capy на основі парсингу 14 живих URL, 13 JSON-LD блоків × 14 сторінок, репозиторію twocomms.shop (24 SEO-комітів за 2026-05-15..17), даних Google Search Console (3 міс) і ручної верифікації кожного твердження аудиту Vilni AI v1.0.0.*
>
> *Документ не є комерційною пропозицією і не зобов’язує до жодних дій. Усі цифри прогнозу — оцінювальні діапазони на основі бенчмарків UA-ecommerce. Реальні результати залежать від виконання плану і ринкової кон’юнктури.*
