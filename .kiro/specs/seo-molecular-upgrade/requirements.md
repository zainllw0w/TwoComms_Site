# Requirements Document

**Spec:** `seo-molecular-upgrade`
**Status:** Draft v1 (для review владельцем)
**Дата:** 2026-05-16
**Скоуп:** основной домен `https://twocomms.shop` (DTF-сабдомен `dtf.twocomms.shop` исключён)
**Языки:** uk-UA (canonical), ru-UA, en-UA
**Фундамент:** 7 audit-документов в `audit/` + `SEO_DEEP_AUDIT_2026-05-16.md` + `SEO/napolke-veteran-brands-2026.md`

## Introduction

Этот документ описывает требования к комплексному SEO-апгрейду TwoComms на молекулярном уровне — от исправления критического 80%+ overlap'а PDP до построения тематических лендингов, расширения support pages, обогащения schema-графа и оптимизации внутренней перелинковки. Цель — поднять сайт с уровня «технически правильный, но контентно-плоский» до уровня «cited by AI-search, ранжируется по нишевым кластерам, имеет уникальный контент на каждом из 65 PDP и поддерживающих страниц».

Документ построен на основе глубокого 7-частного аудита (все 7 закрыты), keyword universe на трёх языках (uk/ru/en), brand frame'а из `SEO/napolke-veteran-brands-2026.md` (ветеранский streetwear из Харькова, founder Артем Синіло) и best-practices 2026 года (Google Core Web Vitals, AI-search optimization, schema.org graph).

Спека содержит **15 user stories** в EARS-формате, каждый с измеряемыми correctness properties. Из 15 — два уже DONE (US-1 audit, US-2 vocab), 13 ждут реализации в порядке зависимостей (см. §5).

## Brand frame и стратегическая рамка

Этот раздел задаёт рамки для всех user stories ниже. Каждый story должен соответствовать этой рамке.

### Brand essence (для всех текстов сайта)

- **Кто**: TwoComms — украинский streetwear-бренд из Харькова, основанный 1 июля 2025 года боевым ветераном **Артемом Синіло** (разведчик, харьковское направление; ранение осколком 120-мм мины).
- **Имя**: «дві коми» — символ продолжения после критической точки. Не «крапка», а «кома».
- **Позиционирование**: streetwear с **внутренним кодом**, military-adjacent эстетика без военного косплея и без патриотического шума. «Принт як код» — каждый принт имеет причину существования и документированное авторство.
- **Верификация (E-E-A-T anchors)**:
  - Связь с 225-м окремим штурмовим полком (интерес командира — Героя України Олега Ширяєва).
  - Спонсор чемпіонату «Перший Постріл», Київ.
  - Колаборація з Євгеном Клопотенком (через Український ветеранський фонд).
  - Сюжети на «1+1», «Громадському».
- **Ассортимент**: футболки, худи, лонгсливы, кастомный DTF-друк. Цены 880–2 550 грн.
- **Конкурентный контур** (для дифференциации в текстах): M-Tac (тактический масс-маркет), RIOT DIVISION (techwear премиум), Aviatsiya Halychyny / Saint Javelin (patriotic merch), STLV Club (military-adjacent без veteran founder), Hate CLUB (provocation streetwear), Militarist (тактический ритейлер).
- **UVP в одной строке**: «Єдиний харківський streetwear-бренд із підтвердженим ветеранським корінням і власною системою смислових кодів».

### Метрики успеха (Q1 default)

В течение 90 дней после полного деплоя всех user stories из этой спеки:

- **MS-1**: Organic impressions в GSC (uk-UA + ru-UA + en-UA, основной домен) — **+150%** относительно 30-дневного baseline на старте.
- **MS-2**: Organic clicks в GSC — **+100%** относительно baseline.
- **MS-3**: Average position по топ-30 эталонным запросам (см. §2.6) — **топ-15** (сейчас оценочно топ-25–60).
- **MS-4**: Indexed PDP в Google Search Console — **65 из 65** (100%) с раздельным ranking каждого товара.
- **MS-5**: AI-citation share — на 30 эталонных запросов в ChatGPT Search, Claude Search, Perplexity, Google AI Overviews — **TwoComms цитируется в ≥10 из 30** ответов (baseline = 0–2).
- **MS-6**: PDP content overlap (5-gram shingle Jaccard) между любыми двумя PDP — **≤30%** (сейчас 80%+).
- **MS-7**: Core Web Vitals — **LCP <2.5s mobile, INP <200ms, CLS <0.1** на топ-15 страницах сайта (поддерживать текущий статус, не регрессировать).

### Стратегия наполнения контентом (Q2 default)

**Гибрид B+C**: template-генератор плюс ручной narrative для топ-20 товаров.

- **Template-генератор** для всех 65 PDP — сервис `product_seo_block`, который из атрибутов товара (category, color_variants, sizes, fit, material, slug, title) собирает уникальный контентный блок на 600–1000 слов на каждом из трёх языков. Гарантирует overlap ≤30% (см. MS-6).
- **Manual narrative** (`topic_narrative` на товаре) — короткое поле 50–200 слов про конкретный принт/тему, заполняется вручную для топ-20 товаров (по обороту/новизне). Подмешивается в hero_intro и who_for секции.
- **Категории, support pages, главная** — единоразовое создание content (генерация Kiro + pre-approval владельцем) на трёх языках.

### Authoring и approval (Q3 default)

- **AI-генерация с pre-approval**: Kiro (через шаблоны и `product_seo_block` сервис) предлагает draft. Владелец одобряет / правит.
- **Локальный draft** перед коммитом: для каждой категории / support page / нового лендинга Kiro складывает draft в `.kiro/specs/seo-molecular-upgrade/drafts/<slug>.md`, владелец одобряет в чате, после одобрения — коммит в template / fixture.
- **Source of truth для динамического PDP** — код шаблона + поле `topic_narrative` в БД. Drafts хранятся только до commit'а.

### Объём ключевых слов на товар (Q4 default)

**Средний (15–20 ключей на PDP)**: brand + name + category + colors + sizes + fit + material + 5–8 long-tail (купити X в [city], X на колір [color], {category} з принтом [topic], {title} TwoComms). Реализуется в `SEOKeywordGenerator.generate_product_keywords` (расширение существующего метода).

### Noindex map (Q5 default)

Изменения индексации публичных страниц:

- `/dropshipper/` → **noindex,follow** (партнёрский SEO-value=0, шум для основного индекса).
- `/orders/track/?ttn=…` → **noindex,follow**.
- `/novyny/` → пока пустая лента — **noindex,follow** до момента, когда наполнение даст ≥10 публикаций. Авто-снятие noindex по threshold.
- `/accounts/login/`, `/accounts/register/` → **noindex,follow**.
- `/mapa-saytu/` → **остаётся index** (UX value).
- `/search/?q=` → уже noindex ✅, не трогаем.

---

## Requirements

Используется EARS-формат (Easy Approach to Requirements Syntax):
- **Ubiquitous**: «The system shall …»
- **Event-driven**: «When [trigger], the system shall …»
- **State-driven**: «While [state], the system shall …»
- **Optional**: «Where [feature is included], the system shall …»
- **Unwanted**: «If [condition], then the system shall …»

Каждый user story имеет:
- **As / I want / So that** (контекст)
- **Acceptance Criteria** (numbered, EARS-style)
- **Correctness Properties** (verifiable invariants)
- **Multilingual contract** (что обязательно для трёх языков)
- **Out-of-scope** (что НЕ делаем в рамках story)

---

### US-1: Deep SEO audit framework

**As** SEO-команда (Kiro + владелец)
**I want** воспроизводимый набор аудит-инструментов и raw datasets
**So that** любые изменения далее могли быть проверены против baseline и regressed back в случае регрессии.

**Status:** ✅ **DONE** (закрыт фазой `audit/` + `SEO_DEEP_AUDIT_2026-05-16.md`)

**Acceptance Criteria:**
1. The system shall иметь 7 завершённых аудитов в `.kiro/specs/seo-molecular-upgrade/audit/` (content, PDP, schema, URL, linking, tech debt, keywords, best-practices).
2. The system shall иметь executive synthesis с топ-12 находками и привязкой к user stories.
3. When владелец требует обновить аудит, Kiro shall перезапустить соответствующий subtask и обновить `_findings.md`.

**Correctness Properties:**
- Все 7 audit-документов существуют в репозитории.
- `_INDEX.md` ссылается на каждый из них и помечает status=done.

**Out-of-scope:**
- Аудит DTF-сабдомена.
- Конкурентный аудит SERP (отдельная активность).

---

### US-2: Vocabulary и keyword universe

**As** автор контента (Kiro / владелец / копирайтер)
**I want** структурированную базу ключевых слов uk/ru/en c HF/MF/LF классификацией и mapping на конкретные страницы
**So that** все тексты сайта писались с явной целевой keyword-set, и не было keyword stuffing'а или keyword cannibalization.

**Status:** ✅ **DONE** (закрыт `audit/06_keywords.md` + `audit_data/06_keywords_raw.json`)

**Acceptance Criteria:**
1. The system shall иметь keyword universe в `06_keywords.md` с разбивкой по 18 кластерам (6 категорий × 3 языка).
2. The system shall иметь raw JSON в `audit_data/06_keywords_raw.json` для программного использования.
3. Where используется новая страница / новый PDP, автор shall выбрать целевую keyword-set из этого universe и зафиксировать её в frontmatter draft / в коде template.

**Correctness Properties:**
- Каждый кластер содержит ≥3 HF, ≥10 MF, ≥15 LF.
- Каждый ключ привязан к exactly one главной целевой странице (нет cannibalization).

**Out-of-scope:**
- Платный keyword research (Ahrefs / Serpstat) — оценки volumes остаются «Limited data» до владельца.

---

### US-3: Динамический per-product SEO-блок (overlap ≤30%)

**Главная цель спеки.** Закрывает **критическую находку #1** аудита: PDP overlap 80%+.

**As** Google / Bing / AI-search bot
**I want** видеть на каждой PDP **уникальный** контентный блок с уникальной комбинацией ключей, тематикой принта и стилистических деталей
**So that** каждая из 65 PDP имела самостоятельный ranking signal и не считалась near-duplicate.

**Acceptance Criteria:**

1. The system shall иметь сервис `storefront/services/product_seo_block.py` с функцией `build_product_seo_block(product, language_code) -> dict`, возвращающей секции `hero_intro`, `who_for`, `how_to_style`, `care`, `delivery`, `why_us`, `faq`, каждая с уникальным текстом 80–200 слов.

2. When шаблон `pages/product_detail.html` рендерится, then шаблон shall использовать секции из `build_product_seo_block` вместо текущих статичных блоков «Доставка», «Догляд», «Розмірна сітка», «Чому варто купити в TwoComms».

3. The system shall иметь поле `Product.topic_narrative` (TextField, blank=True, modeltranslation для uk/ru/en) для опционального ручного narrative по принту (50–200 слов).

4. The system shall иметь поле `Product.topic_keywords` (CharField, blank=True, modeltranslation) для дополнительных тематических LF-ключей (строка через запятую).

5. When `topic_narrative` заполнен, then `hero_intro` shall включать его как первый параграф; иначе — генерируется из title-парсинга и категории.

6. When PDP ранжируется AI-search (ChatGPT/Claude/Perplexity), then первый видимый параграф (TLDR-блок) shall содержать: название товара, категорию, ключевые материальные характеристики (material, weight class), один key fact о принте (через `topic_narrative` или topic-парсинг), указание «бренд TwoComms, Харків».

7. While пользователь видит PDP в режиме `?color=…`, then SEO-блок shall динамически переписывать `hero_intro` с указанием выбранного цвета (но canonical остаётся base PDP).

8. If `topic_narrative` пуст и title содержит однозначно идентифицируемую тему (через keyword match: «kharkiv», «225», «pokrovsk», «business», «glory of ukraine», «reality bends» и т.д.), then template shall выбрать заранее заготовленный topic-template и использовать его.

9. When заполняется topic_narrative для нового товара, **Kiro shall** предложить draft на трёх языках через chat-interaction перед фиксацией.

**Correctness Properties:**

- **CP-3.1 (overlap)**: для всех 65 PDP, попарный overlap текста SEO-блока (5-gram shingle Jaccard) ≤30%. Тестируется автоматическим скриптом `scripts/check_pdp_overlap.py` (создаётся в задачах).
- **CP-3.2 (length)**: каждый SEO-блок генерирует 600–1000 слов **уникального** контента на каждом из трёх языков.
- **CP-3.3 (locale)**: при language_code='ru' все секции отдаются на русском; при 'en' — на английском; при 'uk' — на украинском. Никакого fallback-mixing внутри одной отдачи.
- **CP-3.4 (semantics)**: каждая секция содержит keyword из target keyword-set товара ≥1 раз, но keyword density по любому ключу ≤2.5% (anti-stuffing).
- **CP-3.5 (no UI words leak)**: top-20 слов каждого PDP **не содержат** UI-стопворды («баллов», «грн», «опитування», «завантаження», «корзина») вне контекстуального употребления.
- **CP-3.6 (visible date markers)**: блок содержит видимый text-маркер «Оновлено: {date}» (форматированная `dateModified`).

**Multilingual contract:**
- Обязательно: hero_intro, who_for, how_to_style, care, delivery, why_us, faq — **полностью на трёх языках**.
- topic_narrative: рекомендуется на трёх языках, но допустим uk-only fallback с пометкой «UK-only narrative» в admin (UX hint, не SEO penalty).

**Out-of-scope:**
- Полностью ручной copywriting для всех 65 товаров.
- AI-генерация topic_narrative автоматическая (без approval) — owner pre-approval обязателен (Q3).

**Привязка к best-practice:** §3.3 (Factbox/TL;DR), §4.1 (длина PDP), §2.2 (Schema audience/material/color), §1.2 (canonical стратегия).

---

### US-4: Расширение поддерживающих страниц

**As** AI-search bot и потенциальный покупатель
**I want** видеть подробные, структурированные ответы на вопросы про доставку, уход, возврат, кооперацию, опт
**So that** AI цитировал TwoComms на informational запросы, а покупатель получал ответы без отказа от покупки.

**Acceptance Criteria:**

1. The system shall расширить `/doglyad-za-odyagom/` до **800–1200 слов** на каждом из трёх языков. Содержание: разбивка по типам тканей (бавовна, трьохнитка, поліестер), пошагово прання + сушіння + прасування + зберігання, что НЕ делать с DTF-друком, как восстановить «уставшую» ткань. Подкреплено `HowTo` schema с **≥7 step'ами**.

2. The system shall расширить `/delivery/` до **700–1000 слов**. Содержание: NP / Укрпошта / DPD / самовивіз Харків, точные сроки доставки по регионам, тарифы по весу, что делать при потере посылки, переадресація, безопасний платёж, ссылка на форму tracking. Подкреплено `WebPage` + локальный `FAQPage` (≥6 Q&A).

3. The system shall расширить `/faq/` до **1000–1500 слов** с **25–30 Q&A**, разбитыми по категориям: про бренд (5), про товар и качество (8), про оплату (4), про доставку (5), про возврат (3), про опт и кооперацию (3), про кастом-друк (3). Подкреплено `FAQPage` schema (учитывая, что Google deprecated rich result для коммерческих FAQ — это для AI-extractive).

4. The system shall расширить `/povernennya-ta-obmin/` до **700–900 слов** с пошаговым процессом возврата, обмена, гарантийных случаев. Подкреплено `WebPage` + `FAQPage` (≥5 Q&A).

5. The system shall расширить `/wholesale/` до **800–1200 слов** с прайс-ступенями (от 10/30/50/100 единиц), условиями кооперации, ссылкой на B2B-форму, FAQ для оптовиков. Подкреплено `Service` или `OfferCatalog` schema.

6. The system shall расширить `/cooperation/` до **700–1000 слов** с разделами: collab brief, для блогеров и инфлюенсеров, для магазинов-партнёров, для волонтёрских организаций (с примером Український ветеранський фонд). Подкреплено `Service`.

7. When владелец одобряет драфт каждой страницы, Kiro shall сложить готовый текст в template (`templates/pages/<page>.html` или fixture в `support_content.py`).

**Correctness Properties:**

- **CP-4.1**: каждая страница содержит ≥1 H2 на каждые 200 слов, без skip-levels.
- **CP-4.2**: каждая страница имеет валидный JSON-LD (проверяется через Google Rich Results Test или эквивалентный validator).
- **CP-4.3**: каждая страница имеет canonical, hreflang reciprocal на трёх языках, og:locale соответствует html lang.
- **CP-4.4**: word count проверяется в CI-скрипте `scripts/check_support_pages_length.py` (создаётся в задачах).
- **CP-4.5**: «прати»/«wash»/«стирать» появляется ≥5 раз на `/doglyad-za-odyagom/` (anti-thin-content).

**Multilingual contract:** все 6 страниц переведены полностью на uk/ru/en. Никакого fallback на uk внутри ru/en версии.

**Out-of-scope:**
- `/blog/` (отдельная инициатива US-15).
- `/novyny/` контент-наполнение (вне SEO-скоупа).

**Привязка:** §4.1 (длина), §2.4 (Schema поддержки), §3.3 (AI-extractive Q&A).

---

### US-5: Тематические category landings + city landings

**As** customer ищущий по нишевым LF-запросам и AI-search
**I want** видеть отдельные лендинги под темы (military / streetwear / patriotic / kharkiv-edition) и под географические запросы (купити футболку Харків / Київ / Львів / Одеса / Дніпро)
**So that** TwoComms ранжировался на ниши и города, где сейчас SERP занят prom.ua-листингами без UX.

**Acceptance Criteria:**

1. The system shall иметь модель `ThematicLanding` (или расширение `Category`) с полями: `slug`, `theme_key`, `title_uk/ru/en`, `intro_uk/ru/en`, `seo_keywords_uk/ru/en`, `related_products` (M2M), `related_categories` (M2M), `cover_image`, `display_order`.

2. The system shall создать **4 тематических landings** на каждом из трёх языков:
   - `/catalog/military/` — military-adjacent одяг (footer-описание + ассортимент с тегом military).
   - `/catalog/streetwear/` — общий streetwear-хаб (свзяь с Brand frame §1.1 «принт як код»).
   - `/catalog/patriotic/` — патріотичний одяг с принтами ЗСУ / Украина.
   - `/catalog/kharkiv-edition/` — харьковская тема (Pokrovsk, Kharkiv District, харьковские отсылки).
   Каждый — **800–1200 слов** уникального контента, ItemList с реальными товарами, BreadcrumbList, CollectionPage schema.

3. The system shall создать **15 city landings** (5 городов × 3 категории):
   - Города: Київ, Харків, Львів, Одеса, Дніпро.
   - Категории: футболки, худи, лонгсливы.
   - URL pattern: `/catalog/<category>/<city-slug>/` (например `/catalog/tshirts/kyiv/`).
   - Каждый landing 600–900 слов на одном из языков (приоритет — uk-UA; ru-UA генерируется через template-fallback с заменой city tokens; en-UA — топ-3 city: Kyiv, Kharkiv, Lviv).
   - Содержание: вступление о городе и доставке, ассортимент категории, особенности доставки в город (НП-отделения / самовивіз — если применимо).

4. When city landing запрашивается с `?fit=oversize` или другим фасетом, then canonical shall указывать на base city landing (тот же подход что для категорий).

5. The system shall обновить `sitemap-categories.xml` чтобы включал тематические лендинги и city landings.

6. The system shall гарантировать что каждый city landing имеет **уникальный** intro (overlap с другими city landings ≤40%).

**Correctness Properties:**

- **CP-5.1**: 4 тематических + 15 city = **19 новых лендингов**, все возвращают 200 OK на трёх локалях (где применимо).
- **CP-5.2**: каждый landing имеет hreflang reciprocal, canonical self.
- **CP-5.3**: каждый имеет CollectionPage schema с ItemList (≥6 продуктов).
- **CP-5.4**: pairwise overlap city landings ≤40% (Jaccard 5-gram).
- **CP-5.5**: каждый landing получает ≥3 incoming internal links (из главной, footer, related categories).

**Multilingual contract:**
- Тематические landings: полные uk/ru/en.
- City landings: uk обязательно; ru — обязательно; en — топ-3 (Kyiv, Kharkiv, Lviv) обязательно, остальные могут быть noindex en-UA.

**Out-of-scope:**
- Города кроме топ-5 (Запоріжжя, Чернігів, Полтава и т.д.) — отдельная фаза при подтверждённом ROI.
- Динамический парсинг отделений НП per-city (статически указываем major hubs).

**Привязка:** §1.1 (стратегия), §06_keywords (city LF cluster), §4.3 (linking).

---

### US-6: Internal linking graph (related products, design triplets, cross-language)

**As** Google / customer / AI-bot
**I want** видеть связную сеть internal links между товарами, между триплетами одного принта, между категориями и темой
**So that** crawl-budget распределялся равномерно, in-degree каждого PDP был ≥3, и AI-bot мог построить knowledge graph бренда из internal references.

**Acceptance Criteria:**

1. The system shall на каждой PDP отображать блок «Related products» с **6–8 товарами**, выбранными по приоритету: (a) другие позиции того же design triplet (один принт — три категории), (b) товары той же категории + тематического тега, (c) товары той же темы (military/patriotic/kharkiv) из других категорий.

2. The system shall на каждой PDP, входящей в design triplet, отображать блок «Той самий принт у іншому форматі» с прямыми ссылками на 1–2 sibling-товара. Anchor text — keyword-rich (например «той самий принт «Business Money» на худі» вместо «детальніше»).

3. The system shall на каждой категории отображать блок «Підкатегорії» с ссылками на:
   - тематические landings (где категория представлена),
   - color-categories landings (где есть в US-9),
   - city landings относящиеся к этой категории.

4. The system shall на главной странице добавить навигационный блок «Тематичні розділи» с inline-ссылками на 4 тематических landings + 5 city landings (топ-5).

5. The system shall в RU-локали гарантировать что **все internal links** ведут на `/ru/...` URL (а не на UA fallback). Аналогично для EN.

6. The system shall в pagination (`?page=2`) использовать abs URL с anchor text «Сторінка N» вместо relative number-only links.

7. While пользователь на PDP, then блок «Related products» shall быть server-rendered (не lazy-loaded после JS), чтобы crawler видел.

**Correctness Properties:**

- **CP-6.1 (in-degree)**: для всех 65 PDP, in-degree из internal links ≥3 (тестируется скриптом `scripts/check_linking.py` или повтором audit/04).
- **CP-6.2 (no cross-locale leak)**: на любой странице `/ru/X/`, все `<a href="/...">` ведут только на `/ru/...` (или на абсолютные URL без локали). Проверяется E2E тестом или ssh+curl скриптом.
- **CP-6.3 (anchor diversity)**: anchor text «детальніше», «дізнатися більше», «click here», «тут» появляется в internal-links **0 раз**. Все anchors keyword-rich.
- **CP-6.4 (triplet coverage)**: для каждого из 14 design triplets, все 3 PDP взаимно связаны (3 пары × 2 направления = 6 links на triplet).

**Multilingual contract:**
- Все блоки рендерятся на трёх языках; anchor text локализован.
- Если related product не имеет ru-перевода — он либо переводится (US-15), либо не показывается в /ru/ блоке (выбор fallback на usability).

**Out-of-scope:**
- Динамическая ML-based рекомендация (категория-based достаточно).
- Personalization based on user history.

**Привязка:** §4.3 (linking), audit/04 findings.

---

### US-7: Главная страница — content + TLDR

**As** AI-search bot, посетитель и Google
**I want** видеть на главной TwoComms содержательный текст про бренд, ассортимент, ценности, доставку, плюс TLDR-блок для AI-extractive
**So that** главная не была «UI shell» с 391 словом, а ранжировалась по brand+category комбинациям и цитировалась AI-системами.

**Acceptance Criteria:**

1. The system shall иметь на главной странице (`/`, `/ru/`, `/en/`) содержательный контент **600–800 слов** уникального текста на каждом из трёх языков, разбитый на:
   - **TLDR-блок** (3–5 буллетов: «TwoComms — український streetwear-бренд із Харкова», «Заснований 1 липня 2025 року бойовим ветераном Артемом Синіло», «Ассортимент: футболки, худі, лонгсліви, кастомний DTF-друк», «Ціни 880–2 550 грн», «Доставка по Україні Новою поштою / Укрпоштою / DPD»).
   - **Про бренд** (~200 слов).
   - **Категорії** з inline-links на 3 главные + 4 тематические + 9 color-categories.
   - **Чому TwoComms** (~150 слов): 4 USP включая ветеранське походження, харьковська локалізація, авторські принти-коди, кастомний друк.
   - **Соц.міс ия** (~100 слов): связь з 225 ОШП, спонсорство «Перший Постріл», колаборації.

2. The system shall иметь **Speakable schema** (US-12 пересекается) с cssSelector на TLDR блок и H1.

3. When AI-bot цитирует главную TwoComms, then TLDR-блок shall быть структурирован так чтобы первое предложение было самостоятельным фактом, который можно процитировать без обрезки.

4. The system shall в TLDR использовать factual statements с конкретными данными (даты, имена, цифры) без маркетинговых клише («найкращий», «унікальний», «лідер ринку»).

**Correctness Properties:**

- **CP-7.1**: word count главной страницы (видимый текст в `<main>`) ≥600 на каждой из трёх локалей.
- **CP-7.2**: Top-20 слов главной не содержат UI-стопвордов («баллов», «грн», «опитування») в качестве top-3.
- **CP-7.3**: TLDR-блок содержит ≥4 буллета, каждый — самостоятельное предложение длиной 8–25 слов.
- **CP-7.4**: страница содержит ≥10 internal in-content links (вне navigation/footer).

**Multilingual contract:** полный uk/ru/en, без fallback.

**Out-of-scope:**
- Hero-видео или интерактивные элементы (вне SEO-скоупа).
- A/B-тестирование TLDR форматов.

**Привязка:** §3.3 (TLDR), §4.1 (длина home), §1.1 (brand frame).

---

### US-8: PDP Schema enhance (@id, gtin, audience, ProductGroup)

**Status:** 🟡 **PARTIAL DONE** (stable `@id` + `audience` PeopleAudience + brand/manufacturer/seller refs на Organization добавлены в коммите [hash]. Остаются: gtin поля per-product (требует БД), ProductGroup для variant URLs).

**As** Google Shopping bot и AI-search
**I want** видеть на PDP полный entity graph с stable @id, gtin, audience, ProductGroup (для variant-страниц)
**So that** товары попадали в Shopping eligibility, variant-URL индексировались как уникальные, и AI мог linking-вать продукт к Organization в knowledge graph.

**Acceptance Criteria:**

1. The system shall в `StructuredDataGenerator.generate_product_schema` добавить **stable @id** в формате `{absolute_url}#product` (например `https://twocomms.shop/product/business-money/#product`).

2. The system shall где модель `Product` имеет поле `gtin` (или эквивалент) — добавить `gtin13`/`gtin12`/`gtin8` в schema. Если gtin отсутствует — пропустить (не пустить пустую строку).

3. The system shall добавить `audience` (PeopleAudience) с `suggestedGender` основанным на категории и target_audience товара (или обоих если унисекс).

4. The system shall заменить inlined `Offer.seller` Organization на ref `{"@id": "https://twocomms.shop/#organization"}`. Это требует чтобы Organization schema на странице была с `@id` (уже есть в global graph).

5. The system shall на variant-URL (`/product/<slug>/<color>/`) генерировать **ProductGroup** schema с `hasVariant` массивом всех color-variants и `isVariantOf` ref на base PDP. Это позволит variant-URL'ам индексироваться отдельно с правильной hierarchy.

6. The system shall на всех PDP включить (если ещё нет): `material`, `color` (top-level), `size`, `releaseDate`, `dateModified`, `additionalProperty[]` для fit/style/composition.

7. The system shall на PDP с `aggregateRating` (когда total_reviews ≥3) — включать `aggregateRating` и `review[]` (top-5 reviews). Если <3 reviews — пропустить блок (не пустить fake rating).

8. When Schema валидируется через Google Rich Results Test, **0 ошибок** на 65 PDP.

**Correctness Properties:**

- **CP-8.1**: для всех 65 PDP, JSON-LD имеет stable @id, brand ref на Organization @id, seller ref на Organization @id.
- **CP-8.2**: для всех variant-URL, ProductGroup schema валиден (`hasVariant` массив > 1, `isVariantOf` существует).
- **CP-8.3**: 0 ошибок в Rich Results Test (тестируется автоматическим скриптом `scripts/validate_schema.py`).
- **CP-8.4**: все PDP имеют `dateModified` обновлённый при последнем изменении товара.

**Multilingual contract:** schema generates с `inLanguage` соответствующим locale запроса. Все language variants отражены в schema через `@language` ноды (где применимо).

**Out-of-scope:**
- Реальные `gtin13` per-product (зависит от наличия в БД).
- Sync gtin с поставщиком (вне скоупа).

**Привязка:** §2.2 (Product schema), §2.5 (deprecations).

---

### US-9: Color-category landings (заполнить пустой sitemap)

**As** Google и customer ищущий «чорна футболка з принтом» / «худі чорний оверсайз»
**I want** видеть отдельные landings по комбинации категория × цвет
**So that** TwoComms закрывал color-LF cluster (~80–150 LF-органик/мес), который сейчас полностью свободен в SERP.

**Acceptance Criteria:**

1. The system shall иметь в `CategoryColorLanding` (модель уже существует в коде) **9 заполненных лендингов**:
   - tshirts × {black, khaki, white}
   - hoodie × {black, khaki, gray}
   - long-sleeve × {black, khaki, olive}

2. The system shall для каждого color-landing генерировать **600–900 слов** уникального контента на uk/ru. EN — топ-3 (tshirts/black, hoodie/black, long-sleeve/black).

3. The system shall в `sitemap-color-categories.xml` отдавать все 9 URL'ов на трёх локалях (или 9×2+3 = 21 URL минимум).

4. When пользователь на color-landing, then ItemList в schema shall содержать только товары с этим цветом среди color_variants.

5. The system shall гарантировать canonical color-landing на самого себя; faceted URLs (`?size=...`) → canonical на base color-landing.

**Correctness Properties:**

- **CP-9.1**: 9 заполненных color-landings все возвращают 200 OK.
- **CP-9.2**: каждый имеет уникальный intro (overlap с другими ≤30%).
- **CP-9.3**: ItemList содержит ≥3 товара (если в каталоге <3 товаров с этим цветом — landing создаётся, но в задачах помечается как low-priority и в админке скрыт).
- **CP-9.4**: hreflang reciprocal на доступных локалях.

**Multilingual contract:** uk + ru обязательно; en опционально для топ-3.

**Out-of-scope:**
- Все возможные комбинации (54 product × все цвета) — выбираем только 9 priority.

**Привязка:** §03 URL audit, §06 keywords (color-cluster).

---

### US-10: /custom-print/ SEO — закрыть кластер 30+ ключей

**As** customer ищущий «надрукувати футболку зі своїм принтом» / «свій принт на худі ціна» / «DTF друк Київ»
**I want** видеть на `/custom-print/` развёрнутый landing с FAQ, прайсингом, портфолио, схемой Service
**So that** TwoComms ранжировался в топ-5 по всему custom-print кластеру и брал highest-conversion трафик от типографий.

**Acceptance Criteria:**

1. The system shall расширить `/custom-print/` до **1500–2200 слов** уникального текста на трёх языках.

2. Содержание strona:
   - Hero TLDR (5 буллетов: что мы печатаем, технология DTF, диапазон тиражей, сроки, ценовой диапазон).
   - Технология DTF — что это, чем отличается от шёлкография / трансфер / прямой печати.
   - Что можно печатать (футболки/худі/лонгсліви + аксесуари если применимо).
   - Параметры макета — DPI, формат, размер, что НЕ напечатается.
   - Прайсинг — таблица «единицы → цена за единицу + setup fee».
   - Сроки — производственный цикл по этапам.
   - Кейсы / портфолио (3–5 примеров для команд / событий).
   - Минимальный тираж и опции (от 1 единицы по премиум до 100 по опту).
   - FAQ (≥10 Q&A) — про макет, гарантию, оплату, доставку, повторный заказ, корпоративные условия.

3. The system shall иметь Schema `Service` (или `ProfessionalService`) с `serviceType: "Custom DTF Printing"`, `provider` ref на Organization, `areaServed: Country (UA)`, `offers` с pricing tier (если применимо).

4. The system shall иметь FAQPage schema с ≥10 Q&A (для AI-extractive).

5. The system shall иметь ≥3 internal links с `/custom-print/` на:
   - `/wholesale/` (B2B-кросс-сейл),
   - `/cooperation/` (для брендов),
   - `/catalog/` (показать базовый ассортимент на котором печатаем).

6. When customer заходит на `/custom-print/?tier=team`, then canonical → base `/custom-print/`.

**Correctness Properties:**

- **CP-10.1**: word count страницы ≥1500 на uk; ≥1300 на ru/en.
- **CP-10.2**: ≥10 Q&A на страничке.
- **CP-10.3**: keyword coverage — `custom-print` keyword cluster из audit/06 покрыт ≥80% (LF-ключей в тексте).
- **CP-10.4**: Service schema валиден.
- **CP-10.5**: страница имеет CTA-блок «Замовити кастомний друк» с явным form/contact-link.

**Multilingual contract:** полный uk/ru/en; en критичен для diaspora-trafика.

**Out-of-scope:**
- Online-калькулятор стоимости (вне SEO-скоупа, отдельная фича).
- Online макет-конструктор.

**Привязка:** §06 keywords (custom-print кластер #1 priority), §3.3 (TLDR).

---

### US-11: ItemList на /catalog/ → реальные товары

**Status:** 🟡 **PARTIAL DONE** (homepage WebPage.mainEntity = ItemList с реальными товарами добавлено в коммите `ad748adf`; для `/catalog/` основного listing — отдельный коммит).

**As** Google и customer
**I want** видеть на `/catalog/` (главный каталог-listing) ItemList с реальными товарами вместо 3 категорий
**So that** schema корректно описывала каталог и Google понимал что на странице 65 продуктов, а не 3 рубрики.

**Acceptance Criteria:**

1. The system shall в `CollectionPage` schema на `/catalog/` рендерить `mainEntity = ItemList` с **первыми 16–20 товарами** (по `display_order` или `is_featured` priority).

2. The system shall каждый item в ItemList иметь `position`, `url`, `name`, `image`, `offers.price`, `offers.priceCurrency`.

3. When страница пагинирована (`?page=2`), then ItemList shall обновлять с position offset (page 2 → positions 17-32).

4. The system shall имитировать тот же подход на тематических landings и city landings.

**Correctness Properties:**

- **CP-11.1**: ItemList в schema /catalog/ содержит ≥16 items.
- **CP-11.2**: каждый item имеет валидный URL и абсолютную image URL.
- **CP-11.3**: positions начинаются с 1 на странице 1 и идут sequentially.

**Multilingual contract:** ItemList локализуется (URLs ведут на /ru/ для RU-locale и т.д.).

**Out-of-scope:**
- Динамическая сортировка (sort=...) — отражается через canonical на base.

**Привязка:** §2.3 (Category schema).

---

### US-12: Speakable schema на ключевых страницах

**Status:** 🟡 **PARTIAL DONE** (homepage WebPage.speakable + pro-brand AboutPage.speakable добавлены в коммите `ad748adf`; FAQPage.speakable + top-3 PDP — отдельная под-задача).

**As** Google Assistant / Yandex Алиса / Siri (голосовой поиск)
**I want** иметь Speakable hints на главной, /pro-brand/, /faq/, top-3 PDP
**So that** TwoComms цитировался в голосовых ответах по информационным запросам.

**Acceptance Criteria:**

1. The system shall на главной странице иметь Speakable schema с `cssSelector: ["h1", ".tldr p", "[data-speakable]"]`.

2. The system shall на `/pro-brand/` иметь Speakable с указанием на TLDR и первый параграф.

3. The system shall на `/faq/` иметь Speakable с указанием на каждое Q + первое предложение A.

4. The system shall на топ-3 PDP (по обороту, owner-defined в админке через `is_speakable=True` поле) иметь Speakable с указанием на H1 и hero_intro первое предложение.

5. The system shall пометить элементы для Speakable атрибутом `data-speakable` для CSS-target stability.

**Correctness Properties:**

- **CP-12.1**: Speakable schema валиден на 4+ страницах.
- **CP-12.2**: cssSelector указывает на реально существующие элементы DOM (тестируется E2E).

**Multilingual contract:** Speakable существует на каждой локали с локализованным контентом target.

**Out-of-scope:**
- Speakable на всех 65 PDP (только топ-3).

**Привязка:** §3.4 (Speakable).

---

### US-13: Brand authority — sameAs, Wikidata, brand mentions

**Status:** 🟡 **PARTIAL DONE** (Organization.sameAs стало конфигурируемым через env vars `BRAND_FACEBOOK_URL`/`BRAND_TIKTOK_URL`/`BRAND_YOUTUBE_URL`/`BRAND_PINTEREST_URL`/`BRAND_TWITTER_URL`/`BRAND_WIKIDATA_URL` в коммите `ad748adf`. Owner добавит реальные handles в `.env` сервера).

**As** AI-search и Knowledge Graph builders
**I want** видеть TwoComms как entity с расширенным `sameAs` (Instagram, Telegram, Facebook, TikTok, Pinterest, YouTube, Wikidata)
**So that** бренд попадал в knowledge graph и AI-системы могли cross-reference.

**Acceptance Criteria:**

1. The system shall в Organization schema `sameAs` иметь ВСЕ активные social profiles бренда + Wikidata Q-id (когда заведут).

2. The system shall иметь на `/pro-brand/` factbox-секцию с brand entities (founder, founding date, location, revenue tier, target audience, product range) — для AI-extractive.

3. The system shall иметь disambiguation секцию на `/pro-brand/`: «TwoComms — український streetwear-бренд з Харкова, не плутати з Two Comms Communications».

4. When владелец заводит Wikidata Q-id для бренда, **Kiro shall** обновить sameAs и добавить `identifier` schema property.

5. The system shall на `/pro-brand/` иметь schema `Person` (founder Артем Синіло) с `sameAs` на его соцсети (когда даст ссылки) + `affiliation` ref на 225 ОШП и Український ветеранський фонд (как entities).

**Correctness Properties:**

- **CP-13.1**: `sameAs` на главной/Organization ≥5 ссылок (Instagram, Telegram, Facebook (или почему нет), TikTok (если есть), YouTube (если есть)).
- **CP-13.2**: Person founder имеет ≥2 affiliation links.
- **CP-13.3**: factbox на /pro-brand/ начинается в первых 200 символах HTML body для AI-extract priority.

**Multilingual contract:** все three locales имеют тот же factbox (с локализованным текстом, теми же sameAs).

**Out-of-scope:**
- Создание Wikidata entry (это отдельная инициатива, требует независимых submitters).
- Wikipedia article (не работа Kiro).

**Привязка:** §1.1 brand frame, §3.3 AI-citation.

---

### US-14: Tech debt cleanup (phase comments, unused imports/views)

**As** разработчик и template-парсер
**I want** убрать `Phase X` комменты, mertvyye `{# … #}` блоки, unused imports/views, FIXME без owner
**So that** template render был на 5–10 ms быстрее, кодовая база была чище, и не было риска повторения broken JSON-LD bug'а.

**Acceptance Criteria:**

1. The system shall удалить **все 35 `Phase X` комментов** в шаблонах. Где comment описывает рабочий код — переписать в neutral inline comment без phase-маркера.

2. The system shall заменить **все** оставшиеся multiline `{# … #}` блоки на `{% comment %} … {% endcomment %}`. Скрипт `scripts/check_django_comments.py` в CI блокирует коммиты с многострочным `{# #}`.

3. The system shall удалить **48 unused imports** в Python (audit/05).

4. The system shall удалить **unused views и url_names** (audit/05 §3.5).

5. The system shall закрыть или переписать **17 TODO/FIXME без owner**: каждый TODO либо удаляется (если устарел), либо обрастает owner+date+ticket-link.

6. The system shall удалить `render(...)` со ссылкой на несуществующий шаблон (если есть — заменить на 404 или удалить view).

7. When new phase-style comment добавляется, then pre-commit hook (или линтер) shall блокировать коммит.

**Correctness Properties:**

- **CP-14.1**: `grep -r "Phase " templates/ | wc -l` = 0.
- **CP-14.2**: `grep -rE '\{#[^#]*\n' templates/ | wc -l` = 0 (multiline `{# #}`).
- **CP-14.3**: Pyflakes / Ruff report 0 unused imports в `storefront/`.
- **CP-14.4**: 0 broken JSON-LD на всех публичных страницах (тестируется через `scripts/validate_schema.py`).

**Multilingual contract:** N/A (technical refactor).

**Out-of-scope:**
- Полный рефакторинг архитектуры views (вне скоупа).
- Замена Django template engine на jinja2.

**Привязка:** §05 tech debt audit.

---

### US-15: Multilingual contract — полный перевод критичных полей

**As** /ru/ и /en/ посетитель + AI-search bot
**I want** видеть на ru/en страницах полный перевод критичных SEO-полей (title, description, H1, hero_intro, FAQ, related-blocks)
**So that** Google не считал ru/en версии «duplicate-of-uk» и не понижал их рейтинг.

**Acceptance Criteria:**

1. The system shall гарантировать что для **всех 65 товаров** все критичные поля (`title`, `seo_title`, `seo_description`, `description`, `target_audience`, `topic_narrative`, `topic_keywords`, FAQ items) переведены на ru-UA и en-UA.

2. The system shall иметь админ-индикатор «Translation completeness: 75%» на каждом товаре (показывает % заполненных translation полей).

3. The system shall в админке предупреждать при сохранении товара с `<70%` translation completeness.

4. The system shall иметь admin action «Suggest translation» который вызывает Kiro / GPT-API на отсутствующие переводы (с pre-approval).

5. When товар имеет `<50%` translation на ru-UA, then шаблон ru-PDP shall возвращать `<meta name="robots" content="noindex,follow">` (Path A — анти-«duplicate cluster» защита).

6. The system shall провести **bulk translation pass** на текущие 65 товаров, поднять completeness до **>90%** на всех трёх языках.

7. The system shall гарантировать перевод всех 4 тематических landings, всех 6 support pages, главной, /pro-brand/, /custom-print/.

**Correctness Properties:**

- **CP-15.1**: average translation completeness ≥85% на ru-UA, ≥75% на en-UA по всему каталогу.
- **CP-15.2**: 0 PDP с completeness <50% (либо переведён, либо noindex).
- **CP-15.3**: title и H1 на ru-PDP отличаются от uk-PDP в ≥80% случаев (тестируется diff-скриптом).

**Multilingual contract:** само определение этого story.

**Out-of-scope:**
- Полная локализация даты и валюты (это уже работает).
- Локализация форм оплаты (вне SEO-скоупа).

**Привязка:** §1.3 hreflang, §4.4 multilingual contract из best-practices.

---

### US-16: Homepage commerce signals (kill price-snippet hallucination)

**Главная цель story:** убрать ложную цену «200 200 грн» из Google SERP-сниппета главной (ru-UA).

**As** Google SERP renderer + потенциальный покупатель, видящий главную в выдаче
**I want** видеть в snippet'е главной либо **корректный диапазон цен бренда** (`880–2 550 грн`), либо отсутствие цены вообще
**So that** не было дезинформации (фейковая «200 200 грн» цена), и приходящий трафик не отваливался от шока.

**Status:** ✅ **DONE** (fixed 2026-05-16, ждёт рестарта Passenger / распространения в Google index).

**Root cause analysis:**

На rendered главной (`/ru/`, `/`, `/en/`) в DOM существуют **три** числа `200`:
- `<span class="sl-amount">-200 грн</span>` (бонус за фідбек, левая панель опроса).
- `ВИГРАЙ 200 ГРН ЗА ОПИТУВАННЯ!` (заголовок правой панели опроса).
- `<text>200</text>` дважды в SVG-иконке банкноты.

Главная при этом **не имела ни одного явного price-сигнала** в schema (только `WebPage` + `ItemList` категорий, без `Offer`/`AggregateOffer`/`priceRange`). Google fall-back-эвристика берёт ближайшие числа в гривневом контексте → склеивает `200 + 200` → выдаёт `200 200,00 грн` как «домашняя цена».

**Acceptance Criteria:**

1. The system shall на главной странице эмитить новый schema-узел `OnlineStore @id=#storefront` с явным `priceRange` (например `"880-2550 UAH"`), `currenciesAccepted: "UAH"`, `paymentAccepted` и опциональным `makesOffer: AggregateOffer` (lowPrice / highPrice / offerCount, посчитанные по live `Product.objects`).
2. The system shall расширить `Organization` schema (single source of truth, генерируется в `StructuredDataGenerator.generate_organization_schema`) полями: `@type: ["Organization", "OnlineStore"]`, `priceRange`, `currenciesAccepted`, `paymentAccepted`, `image`, `slogan`, `knowsLanguage`, `brand` (Brand-сублинг), `areaServed`. Это второй ortho-сигнал для KG.
3. The system shall переписать тексты survey banner так, чтобы между двумя «200» был **non-numeric token** ("Промокод на" / "ВИГРАЙ ПРОМОКОД на"), что разрывает heuristic-склейку.
4. The system shall убрать из SVG-иконки банкноты все `<text>200</text>` элементы; заменить на валютный символ `₴` и слово `BONUS` (decoupling в визуальном уровне тоже важен — Google рендерит SVG-текст как обычный текстовый узел).
5. When `Product.objects.aggregate` падает (DB unreachable / migration in progress), then helper shall использовать fallback на published catalogue range (`880-2550 UAH`) и не ронять homepage view.
6. The system shall гарантировать что новый `#storefront` node не конфликтует с legacy `#online-store` (на /contacts/) и `#organization` (global) — все три имеют разные стабильные `@id`.

**Correctness Properties:**

- **CP-16.1**: `curl -s https://twocomms.shop/ | grep -c "priceRange"` → ≥2 (один в `Organization`, один в `#storefront`).
- **CP-16.2**: на странице (rendered DOM) последовательность токенов "200 ... 200 ... 200" больше не существует. После 14 дней distribution в Google SERP сниппет `/ru/` показывает либо `880-2 550 грн`, либо ничего (но не `200 200 грн`).
- **CP-16.3**: Schema проходит Google Rich Results Test без ошибок.
- **CP-16.4**: AggregateOffer.offerCount соответствует `Product.objects.filter(price__isnull=False).count()` ±10% (toleration for soft-deleted products).

**Multilingual contract:** Schema эмитится одинаковая на uk/ru/en (Schema language-neutral), а вот survey banner копи переведены на все три локали (через `{% blocktrans %}`).

**Out-of-scope:**
- Полное удаление survey banner (он несёт UX-функцию).
- Изменение реальной цены товаров.

**Привязка:** §3.3 (factbox), §2.2 (price/Offer schema), live SERP screenshot 2026-05-16.

---

### US-17: Localized social previews

**Главная цель story:** уйти от единственной uk-UA картинки `social-preview.jpg` к 3 локализованным версиям (uk/ru/en).

**As** ru-UA и en-UA пользователь, видящий twocomms.shop в Google SERP / Facebook / Twitter / Telegram embeds
**I want** видеть превью на **своём** языке (а не на украинском, который не родной)
**So that** превью увеличивало CTR и не выглядело как «не для меня».

**Status:** 🟡 **PARTIAL DONE** (2026-05-16) — switching внедрён, SVG-шаблоны созданы; JPG-конвертация ожидает запуска `scripts/render_social_previews.py` (требует `cairosvg` + `Pillow`).

**Acceptance Criteria:**

1. The system shall иметь three SVG-шаблона: `static/img/social-preview-uk.svg`, `social-preview-ru.svg`, `social-preview-en.svg` — единый layout с локализованным заголовком.
2. The system shall иметь Python-скрипт `scripts/render_social_previews.py`, который рендерит каждый SVG в JPG 1200×630 (quality=88, optimized).
3. The system shall иметь template-tag `localized_social_image_path` в `i18n_links.py`, маппирующий `LANGUAGE_CODE → static path`.
4. The system shall в `base.html` использовать локализованный путь как default для `og:image` и `twitter:image` блоков.
5. The system shall в child-templates (`wholesale`, `cooperation`, `custom_print`, `catalog`, `category_color_landing`) подменить хардкод `social-preview.jpg` на `og_locale_image_path` (наследуется через context).
6. The system shall сохранить переопределения для конкретных контекстов: PDP (`product_detail.html` использует `seo_og_image` с variant), category-cover (если задан), product-cover.
7. The system shall иметь `og:image:type: image/jpeg` в base.html (helps Facebook scraper).
8. When локальный JPG-файл не существует, fall-back на `social-preview.jpg` (uk-UA canonical card) — реализуется через ManifestStaticFilesStorage с предварительной CI-проверкой существования файлов.

**Correctness Properties:**

- **CP-17.1**: после запуска `scripts/render_social_previews.py` все 3 файла `social-preview-{uk,ru,en}.jpg` присутствуют в `static/img/` и каждый ≤ 250 KB.
- **CP-17.2**: для `/ru/`-страницы `og:image` в HTML head заканчивается на `social-preview-ru.jpg`. Аналогично для uk и en.
- **CP-17.3**: image dimensions = 1200×630 (Facebook/Twitter Cards required).
- **CP-17.4**: каждое изображение содержит видимый локализованный sub-header (`СТРІТ & МІЛІТАРІ ОДЯГ` / `СТРИТ & МИЛИТАРИ ОДЕЖДА` / `STREET & MILITARY APPAREL`).

**Multilingual contract:** само определение этого story.

**Out-of-scope:**
- Per-product / per-category локализованные cards (только глобальные).
- Squared 1080×1080 secondary card для Google SERP sidebar (отдельная sub-task если KG profile того требует).

**Привязка:** §1.3 (multilingual signals), §4.4 (best-practices), screenshot 2026-05-16 (uk-text on /ru/ snippet).

---

## Out-of-scope (что НЕ делаем в этой спеке)

Чтобы рамки были чёткие — следующие активности **не** входят в этот scope:

- **DTF-сабдомен** (`dtf.twocomms.shop`) — никаких изменений; возможно `noindex` отдельной задачей вне этой spec.
- **Blog launch** (`/blog/`) — отдельная feature spec. Эта spec оптимизирует существующий контент.
- **Performance refactor** — Phase 18-22 уже сделали LCP/INP/CLS зелёными. Поддерживаем (не регрессируем) через CP-MS-7. Дополнительной оптимизации в этой spec не делаем.
- **Замена Django CMS / template engine / DB** — не трогаем.
- **Email-marketing / push-notifications / loyalty programs** — не SEO-скоуп.
- **Платный keyword research** (Ahrefs/Serpstat) — оценки volumes остаются «Limited data». Если владелец купит — обновим audit/06.
- **Реальный copywriting human-команды** — Q3 default = Kiro + pre-approval.
- **Wikipedia/Wikidata article создание** — описано в US-13 как зависимость от внешнего процесса.
- **Новый дизайн / UX / визуальные изменения** — не SEO-скоуп. SEO-блок встраивается в существующий дизайн PDP.

---

## Cross-cutting requirements (применяются ко всем US)

### Verification и testing

**CR-V-1**: Каждый user story должен иметь автоматический verification скрипт в `scripts/seo_verify/` который проверяет соответствие correctness properties. Скрипты складываются по мере реализации задач.

**CR-V-2**: При закрытии каждого story — запуск `scripts/seo_verify/all.sh` который прогоняет все verifiers; статус «green» — необходимое условие закрытия story.

**CR-V-3**: Перед финальным деплоем — manual sanity на 30 эталонных запросов (см. §2.6) в ChatGPT Search, Claude, Perplexity, Google AI Overviews. Каждый запрос проверяется на «упоминается ли TwoComms» и «корректна ли ссылка». Результат складывается в `audit/manual_check_<date>.md`.

### Backward compatibility

**CR-BC-1**: Все существующие URL на сайте остаются работающими. Изменения в URL-структуре только additive (новые URL добавляются, старые НЕ перенаправляются и НЕ удаляются).

**CR-BC-2**: Существующие canonical / hreflang отношения сохраняются. Любые изменения в hreflang проходят через test `scripts/check_hreflang_reciprocity.py`.

**CR-BC-3**: Существующее robots.txt не модифицируется кроме добавления новых allow rules для дополнительных AI-ботов (Bytespider, Diffbot — опционально, по решению владельца).

### Releases и rollback

**CR-R-1**: Деплой выполняется поэтапно — по 1–3 user stories за релиз. Каждый релиз сопровождается коммит-сообщением с явным reference на user story (например `feat(seo): US-3 dynamic PDP block`).

**CR-R-2**: Каждый релиз проверяется на сервере через ssh + curl smoke tests (топ-10 URL → 200 OK + JSON-LD валиден).

**CR-R-3**: При регрессии CWV (LCP > 2.5s, INP > 200ms, CLS > 0.1) на топ-15 страницах — автоматический rollback или быстрый hotfix.

### Documentation

**CR-D-1**: Каждый user story при закрытии получает запись в `CHANGELOG.md` со ссылкой на спеку и коммиты.

**CR-D-2**: `seo_utils.py`, `services/product_seo_block.py` и связанные модули покрыты docstrings с указанием конкретного US (например `"""Generates product schema. See US-8 in seo-molecular-upgrade spec."""`).

---

## Зависимости между user stories

Граф зависимостей (что должно быть готово раньше других):

- **US-1, US-2** — фундамент, уже DONE, ничего не блокируют.
- **US-15** (multilingual) — блокирует US-3 на трёх языках, US-7, US-4. Должен идти **раньше** или параллельно с US-3, US-4, US-7.
- **US-3** (dynamic PDP) — blockируется на US-15 (нужен ru/en перевод полей `topic_narrative`).
- **US-8** (Product schema) — независим, но желательно после US-3 (чтобы schema учитывала новые поля).
- **US-9** (color-categories) — независим, но useful после US-3 (для cross-linking).
- **US-5** (thematic + city landings) — блокирует US-6 (linking) частично (нужны URL для линковки).
- **US-6** (linking) — желательно после US-3, US-5, US-9 (тогда есть куда линковать).
- **US-7** (главная) — независим, но useful после US-5 (можно линковать на тематические landings).
- **US-4** (support pages), **US-10** (custom-print), **US-11** (ItemList), **US-12** (speakable), **US-13** (authority), **US-14** (tech debt) — независимы друг от друга.

**Рекомендуемый порядок реализации**:
1. US-14 (tech debt — расчищаем поле)
2. US-15 (multilingual contract — фундамент)
3. US-8 (PDP schema — параллельно с US-3 design)
4. US-3 (dynamic PDP — главный story)
5. US-9 (color-categories) + US-11 (ItemList)
6. US-5 (thematic + city landings)
7. US-7 (главная) + US-13 (brand authority)
8. US-4 (support pages) + US-10 (custom-print)
9. US-6 (linking — последний, когда всё уже создано)
10. US-12 (speakable — финальный полишинг)

---

## 30 эталонных запросов для AI-citation testing (MS-5)

Регулярно прогоняются в ChatGPT, Claude, Perplexity, Google AI Overviews.
Цель: TwoComms цитируется в ≥10 из 30 ответов.

### Brand & disambiguation (5)
1. Який український streetwear-бренд має ветеранське походження?
2. Що таке TwoComms?
3. Хто заснував TwoComms?
4. Український streetwear-бренд із Харкова — який?
5. Бренд одягу заснований ветераном в Україні

### Custom print cluster (4)
6. Де надрукувати футболку зі своїм принтом в Україні?
7. DTF друк ціна Київ
8. Кастомний друк на худі для команди
9. Власний логотип на футболці маленький тираж

### City + category (6)
10. Купити чорну футболку оверсайз Харків
11. Купити худі streetwear Київ
12. Український бренд лонгслівів Львів
13. Where to buy Ukrainian streetwear hoodie online
14. Купить мужское худи с принтом Одесса
15. Buy patriotic Ukrainian t-shirt online

### Thematic (5)
16. Український патріотичний streetwear бренд
17. Мілітарі футболка з принтом ЗСУ
18. Альтернатива RIOT DIVISION в Україні
19. Військовий streetwear від ветерана
20. Streetwear vs мерч — в чому різниця?

### Informational (5)
21. Як прати худі з DTF принтом?
22. Який розмір футболки обрати оверсайз?
23. Що таке streetwear?
24. Що таке DTF друк?
25. Який матеріал краще для худі — флис чи трьохнитка?

### Comparison (5)
26. TwoComms vs Saint Javelin
27. M-Tac vs RIOT DIVISION vs TwoComms
28. Найкращий ветеранський бренд одягу в Україні 2026
29. Український стрітвір від бойового ветерана
30. Streetwear бренди Харкова

---

## Glossary

| Термин | Расшифровка |
|---|---|
| **PDP** | Product Detail Page (`/product/<slug>/`) |
| **PLP** | Product Listing Page (`/catalog/`, `/catalog/tshirts/`) |
| **TLDR** | Top-Layer Description (компактный factbox в начале страницы) |
| **Speakable** | Schema.org markup для голосового поиска |
| **HF / MF / LF** | High / Mid / Low Frequency keyword cluster |
| **DTF** | Direct-to-Film printing technology |
| **UVP** | Unique Value Proposition |
| **CWV** | Core Web Vitals (LCP/INP/CLS) |
| **EARS** | Easy Approach to Requirements Syntax |
| **Design triplet** | Один и тот же принт реализованный в 3 категориях (футболка + худи + лонгслив) |
| **Topic narrative** | Короткий 50–200 слов textovyy блок про конкретный принт/тему товара |

---

## Open questions (для validation владельцем)

Несмотря на reasonable defaults — следующие пункты желательно подтвердить:

1. **Q-OWN-1**: Гибрид B+C для PDP narrative (template + manual для топ-20) — устраивает?
2. **Q-OWN-2**: city landings 5 городов × 3 категории = 15 — какие города пропускать если SEO impact низкий (Дніпро? Одеса?). Default список: Київ, Харків, Львів, Одеса, Дніпро.
3. **Q-OWN-3**: Translation completeness threshold 50% для noindex / 70% для warning — устраивает или строже?
4. **Q-OWN-4**: Wikidata Q-id для TwoComms — есть в планах? Если нет, US-13 закрывается на sameAs без Wikidata.
5. **Q-OWN-5**: Топ-20 товаров для manual `topic_narrative` — фиксируем по обороту (нужен SQL-запрос на сервере) или по subjective priority владельца?
6. **Q-OWN-6**: bytespider / Diffbot crawlers в robots.txt — добавлять или нет?

---

**Конец `requirements.md` v1.**

После approval владельцем → `design.md` (архитектура: модели, сервисы, шаблоны, тесты, deployment plan).
