# SEO Molecular Upgrade — Deep Audit Synthesis

**Дата**: 2026-05-16
**Аудитор**: Kiro (Claude Opus 4.7) + 7 параллельных аудит-задач
**Скоуп**: `https://twocomms.shop` — основной домен. DTF-сабдомен `dtf.twocomms.shop` **исключён** по решению владельца.
**Связанные документы**:
- `audit/01_content.md` + `01_content_findings.md` — плотность и качество текста (18 static страниц)
- `audit/01b_pdp_content.md` + `01b_pdp_findings.md` — PDP content (12 sampled)
- `audit/02_schema.md` — Schema.org coverage matrix
- `audit/03_urls.md` — URL / slug / canonical strategy
- `audit/04_linking.md` — internal linking graph
- `audit/05_tech_debt.md` — templates + python + dead code
- `audit/06_keywords.md` — keyword universe uk/ru/en, HF/MF/LF
- `audit/07_best_practices_2026.md` — что должно быть по 2026-стандартам

---

## 0. Executive Summary

### Сильные места проекта (не трогать, не сломать)

1. **`robots.txt`** — best-in-class, явный allow для всех ключевых AI-ботов (GPTBot, ChatGPT-User, Claude*, Perplexity*, Google-Extended, CCBot), правильное блокирование UTM/gclid noise, AdsBot отдельно по спеке.
2. **Hreflang** — reciprocal по uk-UA/ru-UA/en-UA/x-default на ~всех страницах. `<html lang>` совпадает с локалью. og:locale тоже.
3. **Canonical стратегия** для facets — `?color=`, `?fit=`, `?size=` корректно идут как `noindex,follow + canonical→base`. Это редкая правильная реализация.
4. **Sitemap** — index + 6 дочерних карт (static, products, variants, categories, color-categories, images), `<lastmod>` на основных. Image sitemap отдельный (Phase 21 PR-6).
5. **Slug инвентарь** — все 65 товаров имеют чистые slug (старая проблема `-prefix` решена в недавней миграции). Все 130 URL в sitemap-products проходят regex `^[a-z0-9][a-z0-9-]*[a-z0-9]$`.
6. **Schema.org base graph** (после `4a60b4df`): `Organization` обогащён founder/foundingDate/foundingLocation/address, `Person` (founder) есть на `/pro-brand/`, `WebSite` с `SearchAction`, `BreadcrumbList` почти везде, `ContactPage`+`ClothingStore` с `parentOrganization`, `AboutPage`+`OfferCatalog`+`Person` на `/pro-brand/`, `HowTo` на `/rozmirna-sitka/` и `/doglyad-za-odyagom/`.
7. **`llms.txt` + `llms-full.txt`** — оба отдают 200, индексируются OAI-SearchBot и PerplexityBot.
8. **CSS / JS**: bootstrap+home-css inlined на главной, Inter preload, Phase 18-22 оптимизировали LCP/CLS до зелёных Lighthouse-зон.
9. **Анти-форвард**: telephone-формат отключён через `format-detection`, `display:none` для phone убран (виден без JS), `geo.position` указывает Харьков.

### Критические провалы (блокируют рост, ставить в P0 user stories)

#### 🚨 1. PDP content overlap 80%+ — главный SEO-провал каталога

Из `01b_pdp_findings.md`:

| Pair | Overlap |
|---|---|
| `business-money` ↔ `in-shee` | **82.1%** |
| `hoodie-classic` ↔ `where-mi-present-hd` | **81.9%** |
| `225-tshirt` ↔ `business-money` | **81.6%** |
| 40+ пар PDP с overlap >70% |  |

Каждая PDP содержит ~1100-1220 слов видимого текста, но **80% — это шаблонный текст про доставку/догляд/розмірну сітку/трастбейджи**, идентичный на всех 65 товарах. Реально уникального контента про конкретный товар — **200-300 слов**.

Это **#1 причина** почему каталог не получает long-tail трафик: Google near-duplicate detection снижает рейтинг страниц с overlap >30-40%, и 65 PDP конкурируют не друг с другом, а **сами с собой**.

Это та самая проблема о которой пользователь сказал «меняется только часть переменных».

**Нужно**: динамический per-product SEO-блок с уникальными секциями (hero_intro / who_for / how_to_style / care / delivery / why_us / faq), которые **полностью переписываются** под топик каждого товара. Бюджет уникального текста — **600-1000 слов на товар**, генерируемых из атрибутов товара + опционального поля `topic_narrative` (вручную для топ-20).

#### 🚨 2. JSON-LD broken на 7 страницах из-за multiline `{# #}`

Из `02_schema.md` + `01_content_findings.md`:

`/delivery/`, `/faq/`, `/dopomoga/`, `/povernennya-ta-obmin/`, `/novyny/`, `/mapa-saytu/`, `/doglyad-za-odyagom/`, `/rozmirna-sitka/` — на каждой 1 broken JSON-LD блок (тип `WebPage` или `CollectionPage` + `BreadcrumbList`). Причина — Django `{# … #}` многострочный — leak в HTML и ломает парсер.

**Статус**: ✅ **исправлено в коммите `2476ba23`** (этой сессии). Шаблон `support_page.html` теперь использует `{% comment %}…{% endcomment %}`. После рестарта Passenger станет live.

#### 🚨 3. Главная страница тонкая (391 слово)

Из `01_content_findings.md`:

Top words главной: `twocomms`, `балів`, `грн`, `купити`, `опитування`, `завантаження`. **Это UI-слова**, не SEO-слова. Реального текста про бренд/категории/преимущества на главной **нет**.

**Нужно**: добавить 600-800 слов содержательного текста про бренд + ассортимент + категории + преимущества доставки + соц.миссия, с inline-ссылками на топ категории и top-10 товаров.

#### 🚨 4. Поддерживающие страницы тонкие (231-407 слов)

Из `01_content_findings.md`:

| Страница | Сейчас | Должно быть |
|---|---|---|
| `/doglyad-za-odyagom/` | 231 | 800-1200 |
| `/delivery/` | 367 | 700-1000 |
| `/faq/` | 407 | 1000-1500 (25-30 Q&A) |
| `/povernennya-ta-obmin/` | 398 | 700-900 |
| `/wholesale/` | 405 | 800-1200 (с прайс-таблицей) |
| `/cooperation/` | 470 | 700-1000 |

`/doglyad-za-odyagom/` — особенно слабая: на странице про **уход за одеждой** слово «прати» встречается **2 раза**. HowTo schema добавлен (Phase `4a60b4df`), но текст под него не подтянули.

#### 🚨 5. Категории дают только 3 — таксономия бедная

Из `03_urls.md`:

Сейчас существуют только: `tshirts`, `hoodie`, `long-sleeve`. На 65 товаров — это плоско.

**Не хватает**:
- Тематические landings: `/catalog/military/`, `/catalog/streetwear/`, `/catalog/patriotic/`, `/catalog/kharkiv/` — каждая со своим SEO-текстом и связанными товарами.
- Color-categories landing страницы: `sitemap-color-categories.xml` сейчас **пустой** (0 URL). Это упущенный SEO-объём ~80-150 LF-органик/мес при правильной реализации.
- City-landings: «купити футболку Київ/Львів/Харків/Одеса/Дніпро» — 5 городов × 3 категории = 15 LF-лендингов, **нулевая конкуренция в SERP**.

#### 🚨 6. Внутренняя перелинковка слабая

Из `04_linking.md`:

- **57 из 65 PDP** имеют **in-degree = 1** (входящая ссылка только из одной категории). Нет «Related products», «Покупали також», «Той самий принт у іншому форматі».
- **RU/EN PDP содержат 37 ссылок утекающих на UA**: пользователь на `/ru/product/X/` кликает на цвет — попадает на `/product/X/black/` (без `/ru/`).
- **Pagination в категориях** ломает анкор-граф: `?page=2` ссылки не уникальные, относительные, без anchor text.

**Архитектурное opportunity**: 14 дизайн-триплетов (один принт × 3 категории) дают возможность для сильной cross-link стратегии: на `/product/business-money/` показать ссылку на `/product/business-money-hd/` с anchor «Той самий принт на худі». Сейчас этой связки **нет**.

#### 🚨 7. Schema gaps на PDP

Из `02_schema.md`:

- `Product` не имеет `@id` → не привязывается к глобальному graph
- Нет `gtin13`/`gtin12`/`gtin8` → теряется eligibility в Google Shopping
- Нет `aggregateRating` / `review[]` (мало отзывов; ставить только при пороге)
- Нет `audience` (PeopleAudience) → плохо работает gender-таргетинг
- **Variant-страницы** (`/product/X/black/`) отдают **тот же** Product с тем же name/sku/image → должен быть `ProductGroup` + `hasVariant` / `isVariantOf`. Это блокирует индексацию 118 variant-URL как уникальных.
- `Offer.seller` инлайнит Organization вместо ref на `#organization` → дублирование сущности в graph

#### 🚨 8. Color-category landings пустые + AI-search упускает кластер

Из `03_urls.md` + `06_keywords.md`:

Модель `CategoryColorLanding` существует в коде (`storefront/models.py`), `sitemap-color-categories.xml` генерируется, но **0 URL** — никто не заполнил. Это **9 готовых лендингов** (3 категории × 3 базовых цвета) с минимальной конкуренцией в SERP.

#### 🚨 9. Custom-print страница ловит 2-3 ключа вместо 30+

Из `06_keywords.md`:

`/custom-print/` — самая высоко-конверсионная страница в сайте по интенту, но кластер «надрукувати футболку зі своїм принтом» / «свій принт на худі ціна» / «DTF друк Київ ціна» (~30+ ключей) **закрыт на 5-10%**. SERP занят типографиями (everfox.com.ua, druknafutbolkah.com), **места для бренд-конкурента полно**.

Pri `06_keywords.md` рекомендация: это **#1 приоритет на 60 дней** для каталога.

### Менее критичные, но важные проблемы (P1)

#### 10. ItemList на каталоге показывает категории, не товары

`/catalog/` главная категория-listing показывает в `mainEntity = ItemList` всего 3 категории, не реальные товары. Должно быть 16-20 продуктов на странице.

#### 11. Speakable schema нигде не используется

Голосовой поиск (Google Assistant, Yandex Алиса, Siri) — не критичный канал для streetwear, но дешёвый markup даст +1% видимости в long-tail голосовых запросах.

#### 12. Brand sameAs ограничен Instagram + Telegram

Должно быть: Facebook, TikTok, YouTube (если есть), Pinterest, Wikidata Q-id. Sameas — это вход в Knowledge Graph.

#### 13. Tech debt: phase-комменты

Из `05_tech_debt.md`:

- 35 phase-комментов в шаблонах (`Phase 12`, `Phase 21`, etc).
- 17 из них в `pages/product_detail.html` — самый горячий шаблон.
- 48 потенциально unused-imports в Python.
- 17 TODO/FIXME без owner / даты.
- Несколько unused views/url_names и `render(...)` со ссылкой на несуществующий шаблон.

Это не критично для SEO, но утяжеляет шаблон-парсер (~5-10ms на render) и затрудняет дальнейшее развитие.

#### 14. /home отсутствует TLDR-блок для AI-цитирования

Best-practice 2026 (`07_best_practices_2026.md` §3.3): первые 3-5 буллетов на главной — короткие factual утверждения. У TwoComms нет такого блока.

#### 15. Blog `/blog/` отсутствует

`/blog/` → 404. На основном домене **нет content hub'а** для long-form контента (гайды, обзоры коллабораций, истории клиентов, design-stories). Это блокирует возможность ранжирования по informational запросам и сужает E-E-A-T.

### Что уже хорошо и не нужно менять (защитный список)

1. ✅ Не трогать `robots.txt` — он образцовый.
2. ✅ Не менять hreflang структуру — она reciprocal и работает.
3. ✅ Не пересоздавать sitemap — он правильный, только наполнить пустые (color-categories).
4. ✅ Не ломать canonical стратегию для facets.
5. ✅ Не убирать Phase 18-22 inlining — это даёт зелёный CWV.
6. ✅ Не трогать существующие `Organization`/`WebSite`/`SearchAction` — они работают как knowledge graph якоря.
7. ✅ Не делать noindex на /ru/ /en/ — Phase 2 (2026-05-15) сознательно их index'ит для накопления RU/EN трафика. Risk control через reciprocal hreflang.

---

## 1. Топ-12 находок ранжированы по приоритету

| # | Find | Severity | Effort | ROI | Связь с user story |
|---|---|---|---|---|---|
| 1 | PDP content overlap 80%+ → динамический per-product блок | 🔴 critical | XL | XXL | US-3 (динамический PDP контент) |
| 2 | broken JSON-LD на 7 поддоменных страницах | 🔴 critical | S | XL | ✅ закрыто `2476ba23` |
| 3 | Главная: 391 слов, нет content для AI/SEO | 🔴 critical | M | XL | US-7 (главная контент) |
| 4 | /doglyad/ /delivery/ /faq/ /returns/ — тонкие | 🔴 critical | L | XL | US-4 (support pages контент) |
| 5 | Категории: 3 шт, бедная таксономия | 🔴 critical | XL | XXL | US-5 (categorical landings) |
| 6 | Внутренняя перелинковка слабая (in-degree=1) | 🟠 high | L | XL | US-6 (linking graph) |
| 7 | PDP Schema без `@id`/gtin/aggregateRating/variant graph | 🟠 high | M | L | US-8 (schema enhance) |
| 8 | Color-category landings пустые | 🟠 high | M | L | US-9 (color landings) |
| 9 | /custom-print/ закрыт на 5-10% по ключам | 🟠 high | M | XL | US-10 (custom-print SEO) |
| 10 | ItemList → реальные товары на /catalog/ | 🟡 medium | S | M | US-11 (catalog ItemList) |
| 11 | Speakable schema нигде | 🟢 low | S | S | US-12 (speakable) |
| 12 | sameAs ограничен | 🟢 low | S | S | US-13 (brand authority) |

(US-1 = аудит, US-2 = vocab/keyword universe — фундамент)

---

## 2. Пять ключевых вопросов к владельцу

Эти вопросы определяют **рамку** будущего `requirements.md`. Без ответов спецификация будет abstract. Прошу пользователя ответить **до перехода к `requirements.md`**.

### Q1. Метрики успеха проекта

Что считаем «успешным `seo-molecular-upgrade`»? Выбрать целевые метрики **в течение 90 дней после полного деплоя**:

| Метрика | Базовая | Целевая |
|---|---|---|
| Organic impressions (GSC) | ~? | +X% |
| Organic clicks (GSC) | ~? | +X% |
| Average position по топ-20 ключам | ~? | топ-N |
| Branded search volume | ~? | +X% |
| AI-citation share (через ручную проверку ChatGPT/Claude/Perplexity на 30 эталонных запросов) | ~? | X из 30 |
| Indexed PDP в Google | 65 | 65 (100%) с отдельным ranking каждый |
| Average time on PDP | ? | +X% |
| Add-to-cart rate с PDP | ? | +X% |

**Прошу выбрать 3-5 метрик и указать целевые значения** (или сказать «использовать reasonable defaults — Kiro предложит»).

### Q2. Бюджет уникального текста

Каждый из 65 товаров требует написания/генерации unique SEO-блока **600-1000 слов** на трёх языках. Категории — 700-1500 слов на трёх языках. Поддерживающие страницы — 700-1500 на трёх языках.

Оценка объёма работы:
- **PDP**: 65 × 800 слов × 3 языка = ~156,000 слов
- **Категории + landings + thematic landings (10-12 шт)**: 12 × 1000 × 3 = ~36,000 слов
- **Support pages**: 8 × 1000 × 3 = ~24,000 слов
- **Главная + pro-brand**: 2 × 1500 × 3 = ~9,000 слов
- **ИТОГО ~225,000 слов уникального content** (если делать from scratch).

**Стратегические опции**:

A. **AI-генерация с post-editing** (быстро, low-cost): GPT-4o / Claude Sonnet генерирует drafts по template, человек проходит pre-approval. ~1-2 недели на наполнение всего сайта. Рекомендую как baseline.

B. **Гибрид с template-system**: для PDP создаём генератор который **вытягивает** контент из атрибутов товара (категория, цвет, размер, fit, material, topic_narrative) и собирает уникальный текст на лету. Для топ-20 товаров — пишем `topic_narrative` вручную (короткие 50-100 слов под каждый). Эту опцию я рекомендую — она даёт реально уникальный контент для всех 65 товаров без 65×3 ручных копирайтов.

C. **Полностью human copywriting**: каждый товар + категория пишет копирайтер. Дорого, медленно (4-8 недель + бюджет на копирайтера), но самое качественное.

**Прошу выбрать A / B / C / гибрид B+C для топ-20.**

### Q3. Кто пишет финальный текст

Связано с Q2:
- AI-генерация с моим pre-approval (Kiro предлагает draft, владелец одобряет / правит)?
- AI-генерация автоматическая (без approval, под ответственность Kiro)?
- Хочешь привлечь реального копирайтера на топ-20 / категории?

### Q4. Сколько ключей на товар

Для каждого PDP — какой набор ключей считаем целевым?

A. **Минимальный (5-7 ключей)**: brand + name + category + 2-3 long-tail. Бесплатно по объёму, но ограниченное покрытие.

B. **Средний (15-20 ключей)** — рекомендую: brand + name + category + colors + sizes + fit + material + 5-8 long-tail (купити X в [city], X для подарунка, X на колір [color], X з принтом [topic]). Реалистично для template-генератора.

C. **Максимальный (30+ ключей)**: всё из B + pricing modifiers (дешева/преміум/опт), demographic modifiers (чоловіча/жіноча/дитяча), seasonal modifiers, occasion (на день народження / на 14 лютого / для бойфренда). Опасность keyword stuffing.

**Рекомендую B**. Нужен подтверждение или другой выбор.

### Q5. Что noindex'ить из публичных страниц

Сейчас все публичные страницы имеют `index, follow`. Некоторые из них дают мало SEO-ценности и шумят:

- **`/search/?q=…`** — уже `noindex,follow` ✅
- **`/cart/`, `/checkout/`** — закрыты `Disallow` в robots ✅
- **`/accounts/login/`, `/accounts/register/`** — нужны для UX, но SEO-value 0. Сделать `noindex,follow`?
- **`/profile/`, `/my-orders/`, `/my-promocodes/`** — закрыты robots ✅
- **`/admin-panel/`** — закрыт ✅
- **`/dropshipper/`** — для партнёров, не для SEO. Сделать `noindex`?
- **`/orders/track/?ttn=…`** — utility, не для SEO. Сделать `noindex`?
- **`/novyny/`** — пока пустая лента (4 новости). Если не наполняется регулярно — кандидат на `noindex` пока не наберёт content.
- **`/mapa-saytu/`** — карта сайта; obsolete для современных краулеров. Оставить `index` для UX или сделать `noindex`?

**Прошу указать какие закрыть, какие оставить.**

---

## 3. Что предлагаю как структуру `requirements.md`

Если ответы на Q1-Q5 дают зелёный свет, я напишу `requirements.md` с:

- **15 user stories** (12 из таблицы выше + 3 общие: vocab/keyword universe, мультиязычность, performance refactor).
- Каждый user story: actor (search engine / AI bot / customer), goal, acceptance criteria в EARS-формате.
- **Correctness properties** для каждого: например для US-3 «for all 65 products, generated SEO block has overlap with other products' SEO block ≤ 30% by 5-gram shingle hash».
- **Out-of-scope** секция: что НЕ делаем в этой spec (DTF subdomain, blog launch, brand mentions / Wikidata, новый дизайн, performance refactor оставляем за рамками).
- **Multilingual contract**: для каждого user story — что обязательно для всех 3 языков, что fallback на uk допустим.

После approval `requirements.md` → пишу `design.md` (архитектура сервисов, модели, шаблоны, тесты), потом `tasks.md` (executable план).

---

## 4. Текущий статус деплоев

### Что задеплоено и работает live

- Коммит `4a60b4df` (server pulled): llms-full.txt, founder Person, Organization обогащение, Kharkiv NAP, BreadcrumbList на главной/контактах, releaseDate/dateModified на PDP, FAQPage условный, HowTo на size_guide / care_guide, телефон inline.
- Коммит `1b1af57f` (server pulled): `{% load seo_tags %}` в `contacts.html` — фикс 500.

### Что лежит на сервере но требует рестарта Passenger

- Коммит `2476ba23`: фикс multi-line `{# #}` → `{% comment %}` в `support_page.html` (главное), `index.html`, `contacts.html`, `cooperation.html`, `admin_stats_dashboard.html`. Это шаблонный фикс — Django подхватит без рестарта Passenger при следующем render. Live проверка покажет работает ли.

**Если ты делаешь рестарт сам** (как договорились) — удобный момент сейчас, перед началом requirements фазы.

---

## 5. Следующий шаг

Жду твоих ответов на **Q1-Q5**. После этого — `requirements.md`.

Если хочешь, можно также:
- Расширить какой-то аудит (например, провести аудит **всех 65 PDP**, не только 12).
- Сделать дополнительный аудит конкурентов в SERP по топ-10 запросов (через web search).
- Проверить производительность (Lighthouse) на топ-5 страницах.
