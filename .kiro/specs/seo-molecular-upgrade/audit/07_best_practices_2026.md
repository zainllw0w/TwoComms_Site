# 07 — SEO + AI Search Best Practices 2026

> Дата: 2026-05-16
> Источники: Google Search Central docs, OpenAI/OAI-SearchBot docs,
> Anthropic Claude Search docs, Perplexity Crawler docs, llmstxt.org draft,
> Bing Webmaster guidance 2025-2026, отраслевые publications
> (Search Engine Land, Aleyda Solis blog, JR Oakes / Locomotive Agency).
>
> Назначение: фундамент для design.md / requirements.md в spec
> `seo-molecular-upgrade`. Это **не аудит TwoComms** — это перечень
> доказательно-полезных практик 2025-2026, к которым потом прикладывается
> наш текущий статус (`✅ есть`, `🟠 частично`, `🔴 нет`).

---

## 1. Классический SEO (Google / Bing)

### 1.1 Crawl access

| Правило | Best practice 2026 | Статус TwoComms |
|---|---|---|
| `robots.txt` | Минимум фильтров, явный allow для AI-ботов | ✅ есть |
| Crawl budget | Block UTM/gclid/fbclid (но НЕ `?color=`/`?fit=`) | ✅ есть |
| Sitemap freshness | `<lastmod>` обязателен для крупных сайтов | ✅ есть на products/categories, ❌ нет на static |
| Sitemap priority | Удалить `<priority>` и `<changefreq>` — Google игнорирует с 2017 | 🟠 надо проверить |
| 404 strategy | 404 → `noindex,follow` + canonical на `/` (а не self) | ✅ есть |

### 1.2 Canonicalization

| Правило | Best practice 2026 | Статус TwoComms |
|---|---|---|
| Self-canonical для каждой индексируемой страницы | Обязательно | ✅ есть |
| Pagination canonical | self-canonical (НЕ → page=1; обновлено Google 2019) | ✅ есть |
| Facets (`?color=`, `?size=`) | Лучшая практика 2025: noindex,follow + canonical → base | ✅ есть |
| `?sort=` | то же самое: noindex+canonical | ✅ есть |
| HTTPS / WWW canonical | Single host, single protocol | ✅ есть |

### 1.3 Hreflang

| Правило | Best practice 2026 | Статус TwoComms |
|---|---|---|
| Reciprocal hreflang между всеми локалями + `x-default` | Обязательно | ✅ есть |
| Use `uk-UA` / `ru-UA` / `en-UA` (regional) или `uk` / `ru` / `en` (language-only) | Регионально-консистентно | ✅ regional |
| `<html lang>` совпадает с активной локалью | Обязательно | ✅ есть |
| Sitemap `<xhtml:link>` для каждой локали | Желательно | ✅ есть |

### 1.4 Speed / CWV

| Правило | Best practice 2026 | Статус TwoComms |
|---|---|---|
| LCP < 2.5s mobile | Phase 18-22 серия достигла это | 🟠 проверить актуально на новых страницах |
| INP < 200ms | Заменил FID в марте 2024 | 🟠 проверить |
| CLS < 0.1 | Reserve space for images/iframes | ✅ есть |
| HTTP/3 / QUIC | LiteSpeed уже отдаёт `alt-svc` | ✅ есть |
| Preload LCP image | Через `{% block preload_hints %}` | ✅ есть |
| Inline critical CSS | Phase 21-22 — bootstrap + home-css inlined | ✅ есть |
| Defer 3rd-party JS | GTM/Pixel/Clarity/TikTok через interaction-trigger | ✅ есть |

---

## 2. Schema.org — entity graph

### 2.1 Глобальный граф (на каждой странице)

| Тип | Зачем | TwoComms |
|---|---|---|
| `Organization` (`#organization`) | Knowledge Graph entity, NAP, sameAs, founder, foundingDate | ✅ есть, обогащено в `4a60b4df` |
| `WebSite` (`#website`) | SearchAction для Sitelinks searchbox | ✅ есть |
| `WebPage` (`#webpage`) с `@id` | Связывает страницу с Organization/WebSite через `isPartOf`/`about` | 🟠 только home + pro-brand |
| `BreadcrumbList` | Sitelinks-style анкоры в SERP + AI navigation cue | ✅ почти везде |

### 2.2 Product

| Поле | Best practice 2026 | TwoComms |
|---|---|---|
| `@id` (стабильный) | Обязательно для AI-граф | 🔴 нет на PDP |
| `name`, `description`, `image[]`, `url` | Обязательно | ✅ есть |
| `sku`, `mpn` | Желательно | ✅ есть |
| `gtin13`/`gtin12`/`gtin8` | Полезно для Google Shopping | 🔴 нет |
| `brand` (Brand object) | Обязательно | ✅ есть |
| `manufacturer` | Желательно | ✅ есть |
| `material` / `color` / `size` (top-level + `additionalProperty`) | Растёт важность 2025-2026 | ✅ есть material+color+size+style |
| `audience` (PeopleAudience) | Помогает gender-таргетингу | 🔴 нет |
| `releaseDate` / `dateModified` | Freshness signal | ✅ добавлено `4a60b4df` |
| `aggregateRating` + `review[]` | Star rich result | 🟠 только когда есть отзывы |
| `isVariantOf` / `hasVariant` (ProductGroup) | КЛЮЧЕВОЕ для path-URL вариантов | 🔴 нет |
| `Offer.priceValidUntil` | Обязательно | ✅ есть |
| `Offer.shippingDetails` (weight tiers) | Google Shopping eligibility | ✅ есть |
| `Offer.hasMerchantReturnPolicy` | Google Shopping eligibility | ✅ есть |
| `Offer.itemCondition` | Обязательно | ✅ есть |
| `Offer.availability` | InStock / MadeToOrder / OutOfStock | ✅ есть |
| `Offer.seller` (Organization ref) | Должно ссылаться на `#organization` | 🟠 inline вместо ref |

### 2.3 Категория / каталог

| Поле | Best practice 2026 | TwoComms |
|---|---|---|
| `CollectionPage` с `@id` | Обязательно | 🟠 без `@id` |
| `mainEntity = ItemList` с реальными товарами | Желательно | 🟠 показывает категории, не товары на root catalog |
| `breadcrumb` ref | Обязательно | ✅ есть |
| `inLanguage` | Обязательно | 🟠 не везде |

### 2.4 Поддерживающие страницы

| Страница | Schema 2026 | TwoComms |
|---|---|---|
| `/about/`, `/pro-brand/` | `AboutPage` + `Person` (founder) + `Organization` ref | ✅ есть |
| `/contacts/` | `ContactPage` + `ClothingStore` (parentOrganization → Organization) | ✅ есть |
| `/faq/` | `FAQPage` (но **не больше одной FAQPage на сайт** — Google deprecated rich result в May 2026, оставил только well-known authoritative) | ✅ есть |
| `/delivery/`, `/povernennya-ta-obmin/` | `WebPage` + локальный `FAQPage` (для AI extractive) | 🟠 broken JSON-LD до коммита `2476ba23`, после — ✅ |
| `/doglyad-za-odyagom/`, `/rozmirna-sitka/` | `HowTo` + `WebPage` | ✅ есть после `4a60b4df` |
| Blog post | `Article` или `BlogPosting` + author Person | 🔴 блога нет |
| `/wholesale/`, `/cooperation/` | `Service` или `OfferCatalog` + FAQPage | 🟠 частично |
| `/custom-print/` | `Service` (тип `ProfessionalService`) | ✅ есть |

### 2.5 Не использовать (не работают / deprecated)

- `WebsiteAction` — устарело, заменено на `WebSite.potentialAction.SearchAction`.
- `Article` без `image`, `author`, `datePublished`, `dateModified` — отбрасывается Rich Results.
- `FAQPage` для коммерческих сайтов как rich-result trigger — Google ограничил с 2023 (только authoritative gov/health). Но как **content marker для AI-extractive** работает.
- `LocalBusiness` без физического адреса и working hours — **misleading claims**, риск manual action. Использовать `OnlineStore` (TwoComms уже сделано).

---

## 3. AI Search Optimization (SGE / ChatGPT Search / Perplexity / Claude)

### 3.1 Crawler access

| Crawler | Цель | TwoComms |
|---|---|---|
| `OAI-SearchBot` | ChatGPT Search inclusion (НЕ training) | ✅ allow |
| `ChatGPT-User` | User-agent от ChatGPT при следовании ссылкам | ✅ allow |
| `GPTBot` | Training data (опционально, разные стратегии) | ✅ allow |
| `Claude-SearchBot` / `Claude-User` | Claude Search & user-triggered fetch | ✅ allow |
| `PerplexityBot` / `Perplexity-User` | Search Engine + user fetch | ✅ allow |
| `Google-Extended` | Gemini grounding (отдельно от Googlebot) | ✅ allow |
| `CCBot` | Common Crawl — training data | ✅ allow |
| `anthropic-ai` | Старый Claude crawler, deprecated | ✅ allow (до сих пор бывает) |
| `Bytespider` | TikTok / Doubao | 🔴 не упомянут (TwoComms TikTok-релевантен) |
| `Diffbot` | KG providers | 🔴 не упомянут |

### 3.2 llms.txt / llms-full.txt

| Файл | Best practice 2026 | TwoComms |
|---|---|---|
| `/llms.txt` (compact) | Compact map для AI retrieval | ✅ есть |
| `/llms-full.txt` (extended) | Полный brand context + FAQ + ассортимент | ✅ есть после `4a60b4df` |
| `/.well-known/llms.txt` | Альтернативный путь по llmstxt.org draft | ✅ есть |

### 3.3 Контентные практики для AI-цитирования

**Что AI-системы любят цитировать:**

1. **Factbox / TL;DR блок** в начале страницы с короткими утверждениями. Маркер: список из 3-5 буллетов с фактами в форме «{X} is {Y}, founded in {Z}, located in {city}».
2. **Q&A структура** с явно выделенными вопросами как H2/H3. Не обязательно `FAQPage` schema — достаточно семантической HTML-разметки `<details><summary>`.
3. **Definitional sentences**: «{Term} — это {definition}». LLM специально ищут такие конструкции при ответах на «що таке X».
4. **Числа и конкретика**: цены, размеры, процентные показатели, сроки. AI любит цитировать предложения с цифрами.
5. **Уникальность контента**: 50%+ overlap с другими страницами сайта → AI считает страницу low-value, не цитирует.
6. **Author authority**: имя автора + ссылка на профиль. Без `Person` schema или `<address class="author">` AI считает контент анонимным.
7. **Date markers**: `datePublished`, `dateModified` + видимая дата на странице. Свежесть = шанс цитирования.

**Что AI-системы избегают:**

1. **Hallucination-bait**: эмоциональные заявления без подтверждения. AI учится отсеивать.
2. **Дубль FAQ** через сайт: одинаковые Q&A на 5+ страницах → LLM выбирает одну, остальные "не существуют" в его модели.
3. **Walls of text**: 10+ параграфов без подзаголовков и списков. Плохо парсится.
4. **JS-only контент**: основные AI-боты сейчас рендерят JS, но не все. Server-side render для критичного контента всегда лучше.

### 3.4 Speakable schema (для голосовых ассистентов)

```json
{
  "@type": "WebPage",
  "speakable": {
    "@type": "SpeakableSpecification",
    "cssSelector": ["h1", ".tldr p", "[data-speakable]"]
  }
}
```

**Где применять:**
- Главная (TLDR + H1)
- Pro-brand (TLDR + первый параграф)
- FAQ-страницы (Q + первое предложение A)
- Блог-посты (заголовок + первый параграф)

**TwoComms**: 🔴 Speakable пока нигде не используется.

---

## 4. Контент

### 4.1 Длина / плотность

| Тип страницы | Минимальная длина 2026 | TwoComms текущая |
|---|---|---|
| Home | 800-1200 слов | 391 слов 🔴 |
| Категория | 600-1000 слов + product list | 937-1048 слов ✅ |
| PDP | 600-1200 слов **уникальных** | 200-300 слов уникальных 🔴 (остальное 80% дубль) |
| Support / FAQ / Care / Delivery | 700-1500 слов | 231-407 слов 🔴 |
| About / Brand | 1000-2500 слов | 1153 слов ✅ |
| Blog post | 1200-3000 слов | n/a (блога нет) |

### 4.2 Заголовочная иерархия

- Один H1 на страницу — обязательно.
- H2/H3 разделы каждые 200-400 слов.
- Без skip-levels (H2 → H4 без H3).
- Анкоры (`<a href="#section">`) для глубоких разделов.

### 4.3 Внутренняя перелинковка

- 3-5 контекстных in-content ссылок на каждой странице (сверх navigation/footer).
- Anchor text — keyword-rich, не «click here» / «детальніше».
- Cross-language linking — все ссылки внутри `/ru/` ведут только на `/ru/` (НЕ на UA fallback).
- Каждый товар должен получать 2+ in-degree (категория + хаб / related products).

### 4.4 Мультиязычность

- `<html lang>` совпадает с локалью.
- `og:locale` совпадает с локалью.
- Полный перевод критичных полей (title, description, H1) — НЕ fallback.
- Если перевод неполный — `noindex,follow` на этой локали (Path A) ИЛИ полный перевод (Path B). Гибрид с partial-fallback допустим, но Google помечает как low-quality cluster.

---

## 5. Performance / Web Vitals 2026

### 5.1 LCP

- Оптимизировать LCP image: AVIF/WebP, preload, fetchpriority="high".
- Лимит — 2.5s mobile.
- Inline critical CSS обязательно.
- Self-host fonts (TwoComms делает).

### 5.2 INP (interaction to next paint)

- Заменил FID в марте 2024.
- Лимит — 200ms.
- Самые опасные источники: heavy GTM scripts, third-party widgets.
- Стратегия TwoComms (defer GTM/Pixel via interaction-trigger) — ✅ современная.

### 5.3 CLS

- 0.1 max.
- Reserve dimensions (width/height) для всех images, iframes, ads.
- Avoid late-loaded fonts с font-swap (use font-display: swap + preload).

---

## 6. Security / Trust signals

| Сигнал | TwoComms |
|---|---|
| HTTPS + HSTS preload | ✅ |
| Strict CSP | ✅ |
| `Referrer-Policy` | ✅ `strict-origin-when-cross-origin` |
| `X-Content-Type-Options: nosniff` | ✅ |
| `X-Frame-Options: SAMEORIGIN` | ✅ |
| Privacy policy + Terms (visible footer link) | ✅ |
| Contact info visible without JS | ✅ (после фикса) |
| Real ratings + reviews | 🟠 (есть инфраструктура, мало отзывов) |
| Wikidata / Wikipedia mention | 🔴 (бренд молодой) |

---

## 7. Что менялось в 2025-2026 (важные deprecations и шифты)

1. **March 2024**: INP заменил FID в Core Web Vitals.
2. **November 2023 — May 2024**: Google ограничил FAQPage rich result только для well-known gov/health сайтов. Коммерческие FAQ остались valid markup, но без rich-result в SERP.
3. **2024**: Google AI Overviews (SGE) запущен в US, расширение на UA в 2025-2026.
4. **2024-2025**: ChatGPT Search, Claude Search, Perplexity получили distinct user-agents (`OAI-SearchBot`, `Claude-SearchBot`, `PerplexityBot`).
5. **2025**: llmstxt.org draft, поддерживается всеми major AI-search engines de-facto.
6. **2025**: `Google-Extended` стал отдельным opt-in для Gemini grounding, отделён от training (`GPTBot`-like).
7. **2025**: Bing Webmaster Tools интегрировался с ChatGPT Search referrals.
8. **2026 (May)**: Google deprecated `HowTo` rich result для веб-страниц (только app-видимость остаётся). HowTo schema ещё валидна для AI-extractive, но не даёт visual rich-result.

---

## 8. Что **НЕ работает** в 2026 (но многие ещё пишут об этом)

- **Meta keywords** — Google игнорирует с 2009. TwoComms их выпиливал в Phase 21 — ✅ правильно.
- **Backlinks count > Link quality** — алгоритм давно прежнего. Качество > количество.
- **Keyword density 2-5%** — старая мифология. Сейчас работает entity coverage и semantic completeness.
- **Exact-match anchor text** — overuse даёт Penguin-like штраф. Естественные вариации лучше.
- **SEO-only страницы под ключи** (doorway pages) — manual action.
- **PageRank sculpting через `nofollow` на внутренние ссылки** — давно не работает.

---

## Связь с проектом TwoComms

Этот документ — фундамент для:

1. **`requirements.md`**: каждый user story должен ссылаться на конкретное правило best-practice (например: "соответствие правилу 2.2 — `isVariantOf`/`hasVariant` для variant-PDP").
2. **`design.md`**: архитектура решений должна учитывать deprecations из §7 и `НЕ работает`-список из §8.
3. **`tasks.md`**: каждая задача проверяется acceptance-критерием против §1-6.

Гэпы выделены 🔴/🟠 — они напрямую формируют список задач.
