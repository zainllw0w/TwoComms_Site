# 02 — Schema.org Coverage Matrix (live re-audit, 2026-05-16, post-commit `4a60b4df`)

> Полный реестр всех `<script type="application/ld+json">`-блоков на 32-х страницах
> live-сайта `https://twocomms.shop`. Источник данных — fresh fetch
> (`python3 audit/_tools/fetch_and_parse.py`) после коммита `4a60b4df`
> *(seo(geo): close P0/P1 GEO findings — llms-full.txt, founder Person,
> breadcrumbs, HowTo, Kharkiv NAP)*.
>
> Артефакты:
>
> - `/tmp/seo_audit/schema/raw/<slug>.html` — сырые HTML-снимки
> - `/tmp/seo_audit/schema/parsed/<slug>.json` — массив блоков `{index, raw, parsed, parse_error}`
> - `/tmp/seo_audit/schema/summary.json` — типы и `@id`-ы по каждому slug
> - `02_schema_raw.json` (этот каталог) — компактный реестр всех блоков с `@type / @id / top_keys`
>
> ⚠️ **Что изменилось vs. предыдущая итерация (commit `98924999`):**
> live уже отдаёт `founder` в Organization, Person на `/pro-brand/`, BreadcrumbList
> на home, WebPage с `@id` на home, releaseDate/dateModified в Product,
> ContactPage+ClothingStore на `/contacts/` (HTTP-200 восстановлен), HowTo на
> `/rozmirna-sitka/` и `/doglyad-za-odyagom/`, FAQPage на PDP только при наличии
> `product.faqs`. То есть **бóльшая часть P0/P1 предыдущего отчёта закрыта**.
>
> ⚠️ **Что НЕ задеплоено** (передано в задаче — passenger не перезапущен):
> локальные изменения совпадают с тем, что мы видим на live (passenger таки
> подобрал коммит `4a60b4df`). Все находки ниже — это то, что ВИДИТ AI-парсер
> прямо сейчас.

---

## Executive Summary

После коммита `4a60b4df` граф значительно подтянулся: `Organization` обогащён
NAP/founder/foundingDate, появился `Person` (founder), ContactPage+ClothingStore
с `parentOrganization → #organization`, BreadcrumbList на home,
HowTo на двух care-страницах, releaseDate/dateModified в Product. Но **5 из 7
"топ-критичных" находок прошлого отчёта живы**:

| Блокер | Статус |
|---|---|
| 11 страниц с broken JSON-LD (Django `{# ... #}`-комменты) | 🔴 **не исправлено** — то же количество страниц падает |
| FAQ-дубликаты на PDP (13 пунктов = 5 уникальных + 8 повторов) | 🔴 **не исправлено** — на всех 11 PDP |
| Variant-страницы PDP отдают идентичный Product schema canonical-у | 🔴 **не исправлено** — нет `ProductGroup`/`hasVariant`/`isVariantOf` |
| Product без `@id` / `aggregateRating` / `review` / `gtin*` | 🔴 **не исправлено** |
| WebPage отсутствует на PDP, на категориях `CollectionPage` без `@id`/`isPartOf` | 🟠 **не исправлено** |
| `/contacts/` 500 + нет ContactPage/ClothingStore | ✅ **закрыто** (HTTP 200, ContactPage + ClothingStore с parentOrganization) |
| Person founder отсутствует на не-/pro-brand/ страницах при наличии ref-а | 🟠 **частично** (ref-ы остались orphan на 31 странице) |

🔥 **Топ-5 проблем, которые продолжают резать видимость в AI-поиске:**

1. **11 страниц со сломанным JSON-LD на live** (`/delivery/, /faq/, /dopomoga/, /povernennya-ta-obmin/, /rozmirna-sitka/, /doglyad-za-odyagom/, /vidstezhennya-zamovlennya/, /mapa-saytu/, /novyny/, /polityka-konfidentsiynosti/, /umovy-vykorystannya/`). Шаблон `templates/pages/support_page.html` содержит **многострочный** Django-коммент `{# ... #}`, который Django парсит **только в пределах одной строки**, поэтому строки 2–10 каждого коммента уходят в HTML и валят парсер на `Expecting property name enclosed in double quotes: line 8 column 7`. Лечится `{% comment %} ... {% endcomment %}`.
2. **FAQ-дубликаты на PDP**: на каждом из 11 PDP в `FAQPage.mainEntity` лежит ровно 13 `Question`-узлов, из которых уникальных по `name` всего 5 (т.е. 8 буквальных повторов в одном блоке). Источник — двойная склейка product-specific FAQ с self-overlap при рендере шаблона. Google `FAQ rich result` deprecated с May 2026, но FAQ остаётся источником для extractive citations Perplexity/ChatGPT/Claude — буквальные дубли там очень шумят.
3. **Variant-страницы дублируют canonical Product schema**: `/product/classic-tshirt/black/`, `/product/classic-tshirt/oversize/`, `/product/my-little-baby/coyote/` отдают **тот же** Product (та же `name`, `image`, `color`, `sku`, `price`, тот же `BreadcrumbList @id`). Меняется только `Product.url` и canonical/og-meta. Нет `ProductGroup`/`hasVariant`/`isVariantOf`. У Google → 118 variant-URL в `sitemap-product-variants.xml` идут как почти-дубли canonical-PDP.
4. **Product без `@id`** (на всех 11 PDP). Соответственно: нет `aggregateRating`, нет `review[]`, нет `gtin13`/`gtin12`, `manufacturer` и `Offer.seller` инлайнят `Organization` вместо ref-а на `#organization`.
5. **WebPage отсутствует на PDP**, на категориях `CollectionPage` без `@id` / `isPartOf` / `breadcrumb`-ref. Только `/` (home) и `/pro-brand/` имеют полностью прошитый `WebPage`/`AboutPage` с `@id`, `inLanguage`, `isPartOf`, `about`, `breadcrumb`, `mainEntity`, `primaryImageOfPage`. На остальных 30 страницах граф разорван.

---

## 1. Сводная таблица: что есть на каждой странице

`Y` = тип присутствует на странице (top-level или внутри `@graph`-блока).
`broken` = страница имеет сломанный JSON-LD-блок, который должен был содержать соответствующий тип.

| URL | Org | WebSite | WebPage* | BC | Product | FAQ | HowTo | Article | Speakable | Other |
|---|---|---|---|---|---|---|---|---|---|---|
| `/` (home) | Y | Y | WebPage | Y | – | – | – | – | – | ItemList |
| `/catalog/` | Y | Y | CollectionPage | Y | – | – | – | – | – | ItemList |
| `/catalog/tshirts/` | Y | Y | CollectionPage | Y | – | – | – | – | – | ItemList(16) |
| `/catalog/hoodie/` | Y | Y | CollectionPage | Y | – | – | – | – | – | ItemList(16) |
| `/catalog/long-sleeve/` | Y | Y | CollectionPage | Y | – | – | – | – | – | ItemList(16) |
| `/product/classic-tshirt/` | Y | Y | – | Y | Y | Y | – | – | – | Brand, Offer, MerchantReturnPolicy, OfferShippingDetails×3 |
| `/product/hoodie-classic/` | Y | Y | – | Y | Y | Y | – | – | – | как выше |
| `/product/longsleeve-classic/` | Y | Y | – | Y | Y | Y | – | – | – | как выше |
| `/product/my-little-baby/` | Y | Y | – | Y | Y | Y | – | – | – | как выше |
| `/product/where-mi-present-ts/` | Y | Y | – | Y | Y | Y | – | – | – | как выше |
| `/product/in-shee/` | Y | Y | – | Y | Y | Y | – | – | – | как выше |
| `/product/classic-tshirt/black/` | Y | Y | – | Y | Y | Y | – | – | – | как canonical PDP |
| `/product/classic-tshirt/oversize/` | Y | Y | – | Y | Y | Y | – | – | – | как canonical PDP |
| `/product/my-little-baby/coyote/` | Y | Y | – | Y | Y | Y | – | – | – | как canonical PDP |
| `/ru/product/classic-tshirt/` | Y | Y | – | Y | Y | Y | – | – | – | FAQ переведён на RU ✅ |
| `/en/product/classic-tshirt/` | Y | Y | – | Y | Y | Y | – | – | – | FAQ переведён на EN ✅ |
| `/contacts/` | Y | Y | ContactPage | Y | – | – | – | – | – | ClothingStore (parentOrganization → #organization ✅) |
| `/pro-brand/` | Y×2 | Y×2 | AboutPage | Y | – | Y | – | – | – | OfferCatalog, Person (founder) |
| `/cooperation/` | Y | Y | WebPage(no@id) | Y | – | Y | – | – | – | – |
| `/wholesale/` | Y | Y | WebPage(no@id) | Y | – | Y | – | – | – | ImageObject(publisher.logo) |
| `/custom-print/` | Y | Y | – | Y | – | Y | – | – | – | Service (no @id) |
| `/delivery/` | Y | Y | broken | broken | – | Y | – | – | – | – |
| `/faq/` | Y | Y | broken | broken | – | Y | – | – | – | – |
| `/dopomoga/` | Y | Y | broken | broken | – | Y | – | – | – | – |
| `/povernennya-ta-obmin/` | Y | Y | broken | broken | – | Y | – | – | – | – |
| `/rozmirna-sitka/` | Y | Y | broken | broken | – | – | Y | – | – | HowTo с 6 шагами |
| `/doglyad-za-odyagom/` | Y | Y | broken | broken | – | – | Y | – | – | HowTo с 7 шагами |
| `/vidstezhennya-zamovlennya/` | Y | Y | broken | broken | – | – | – | – | – | – |
| `/mapa-saytu/` | Y | Y | broken | broken | – | – | – | – | – | (нет SiteNavigationElement) |
| `/novyny/` | Y | Y | broken | broken | – | – | – | – | – | (нет Blog/CollectionPage) |
| `/polityka-konfidentsiynosti/` | Y | Y | broken | broken | – | – | – | – | – | – |
| `/umovy-vykorystannya/` | Y | Y | broken | broken | – | – | – | – | – | – |

*WebPage* = WebPage / CollectionPage / AboutPage / ContactPage в зависимости от назначения.

---

## 2. Поломанные JSON-LD блоки

### 2.1 Список (11 страниц)

| Slug | URL | Какой блок ломается | Тип, который должен был быть |
|---|---|---|---|
| delivery | `/delivery/` | block #3 | `[WebPage, BreadcrumbList]` |
| faq | `/faq/` | block #3 | `[WebPage, BreadcrumbList]` |
| dopomoga | `/dopomoga/` | block #3 | `[WebPage, BreadcrumbList]` |
| povernennya | `/povernennya-ta-obmin/` | block #3 | `[WebPage, BreadcrumbList]` |
| rozmirna-sitka | `/rozmirna-sitka/` | block #3 | `[WebPage, BreadcrumbList]` |
| doglyad-za-odyagom | `/doglyad-za-odyagom/` | block #3 | `[WebPage, BreadcrumbList]` |
| vidstezhennya | `/vidstezhennya-zamovlennya/` | block #2 | `[WebPage, BreadcrumbList]` |
| mapa-saytu | `/mapa-saytu/` | block #2 | `[WebPage, BreadcrumbList]` |
| novyny | `/novyny/` | block #2 | `[WebPage, BreadcrumbList]` |
| privacy | `/polityka-konfidentsiynosti/` | block #2 | `[WebPage, BreadcrumbList]` |
| terms | `/umovy-vykorystannya/` | block #2 | `[WebPage, BreadcrumbList]` |

Все падают с одной и той же ошибкой:
`Expecting property name enclosed in double quotes: line 8 column 7`.

### 2.2 Причина

В шаблоне `templates/pages/support_page.html` (или его include-блоке) внутри
`<script type="application/ld+json">` стоит **многострочный** Django-коммент:

```django
{# SEO v1.0 Phase 12 (2026-05-12) — finding (BBB). AboutPage and
   CollectionPage entries (e.g. /pro-brand/, /novyny/) were
   missing both datePublished and dateModified, ... #}
{# Dates are ISO-8601 strings declared by us in support_content.py
   — they contain no JSON-special chars, so we skip escapejs ... #}
```

Django однострочный комментарий `{# ... #}` **закрывается на конце строки**,
а не на `#}`. Поэтому начиная со 2-й строки и до строки с `#}` весь текст
улетает в HTML как обычная строка прямо посреди JSON. Sample raw output (из
`/tmp/seo_audit/schema/parsed/delivery.json`, block #3):

```jsonc
[
    {
      "@context": "https://schema.org",
      "@type": "WebPage",
      "name": "Доставка і оплата",
      "description": "...",
      "url": "https://twocomms.shop/delivery/",
      {# SEO v1.0 Phase 12 (2026-05-12) — finding (BBB). AboutPage and
         CollectionPage entries (e.g. /pro-brand/, /novyny/) were
         ... #}
      ...
      "isPartOf": {
        "@type": "WebSite",
        "name": "TwoComms",
        "url": "https://twocomms.shop"
      }
    },
    ...
]
```

Линия `line 8 column 7` — это первая буква `S` в `SEO` после `,` ⇒ JSON-парсер
ждёт `"property"`, а получает идентификатор. Поэтому **всё содержимое блока**
не парсится.

### 2.3 Фикс

Заменить `{# ... #}` (многострочный) → `{% comment %} ... {% endcomment %}` в
`templates/pages/support_page.html`. Никакого другого источника broken
JSON-LD на live нет.

---

## 3. Полнота полей: топ-25 пробелов

Severity: 🔴 critical / 🟠 high / 🟡 medium / 🟢 low.

| # | Page | Schema | Missing field | Severity | Recommended action |
|---|---|---|---|---|---|
| 1 | 11 support pages | WebPage + BreadcrumbList | **block parses as broken JSON** | 🔴 | заменить `{# … #}` на `{% comment %}` в `support_page.html` |
| 2 | Все 11 PDP | Product | `@id` | 🔴 | `@id: <canonical-url>#product` (или сохранить уже принятый `<url>#product` стиль) |
| 3 | Все 11 PDP | Product | `aggregateRating` | 🔴 | даже 5 отзывов лучше чем 0; источник — UGC/Trustpilot/Google |
| 4 | Все 11 PDP | Product | `review[]` (≥3) | 🔴 | то же |
| 5 | Все 11 PDP | Product | `gtin13`/`gtin12`/`gtin8` | 🔴 | если не присваиваем GTIN, использовать `productID="MPN:..."` явно |
| 6 | Все 11 PDP (canonical+variant) | Product | `hasVariant`/`isVariantOf`/`ProductGroup` | 🔴 | внедрить `ProductGroup` для родителя, ref-ы из вариантов |
| 7 | 3 variant-PDP | Product | разные `name`/`image`/`color`/`sku`/`price` для variants | 🔴 | либо `<link rel=canonical>` на родителя (выкинуть из индекса), либо полностью перетереть Product per-variant |
| 8 | Все 11 PDP | Product.manufacturer | ref-by-`@id` на `#organization` | 🟠 | сейчас инлайн Org-объект |
| 9 | Все 11 PDP | Offer.seller | ref-by-`@id` на `#organization` | 🟠 | то же |
| 10 | Все 11 PDP | Product | WebPage-обёртка (`@id`, `mainEntity → Product`, `breadcrumb → BC`) | 🟠 | Product сейчас "висит" внутри `@graph` без WebPage-узла |
| 11 | 4 категории + catalog-root | CollectionPage | `@id`, `isPartOf → #website`, `breadcrumb → #breadcrumbs`, `inLanguage` | 🟠 | граф разорван, AI-парсер не сшивает страницу с сайтом |
| 12 | 4 категории | CollectionPage.mainEntity.itemListElement[] | каждый ListItem `image` + ref-by-`@id` на Product (вместо string url) | 🟠 | сейчас только `position/url/name` |
| 13 | Все 11 PDP | FAQPage | удалить дубли (8 из 13 повторяются буквально) | 🔴 | дедуп при склейке product-specific + general FAQ |
| 14 | Все 11 PDP | FAQPage | `@id`, `inLanguage`, `isPartOf → #webpage` | 🟠 | FAQPage висит вне графа |
| 15 | `/cooperation/`, `/wholesale/` | WebPage | `@id`, `inLanguage`, `isPartOf → #website` (`wholesale` — частично есть), `about → #organization`, `dateModified` | 🟠 | сейчас инлайн `publisher: Organization` и нет `@id` |
| 16 | `/custom-print/` | Service | `@id`, `provider` ref-by-`@id`, `offers` (диапазон цен), `audience`, `serviceOutput`, `availableChannel` | 🟠 | сейчас Service без `@id`, provider — инлайн дубль Org |
| 17 | `/contacts/` | ContactPage | `@id` (например `<url>#contact-page`), `inLanguage` | 🟡 | живёт без `@id`, не ссылается на `breadcrumb` через ref |
| 18 | `/contacts/` | ClothingStore | `geo` (`GeoCoordinates`), `openingHoursSpecification`, `hasMap` | 🟡 | для LocalBusiness rich result |
| 19 | Organization (на всех страницах) | Organization | `sameAs[]` ≥5 каналов | 🔴 | сейчас 2 (Instagram + Telegram) |
| 20 | Organization (везде) | Organization | `email`, `legalName`, `vatID`/`taxID`, `knowsAbout[]`, `slogan` | 🟠 | для AI knowledge graph и Bing Places |
| 21 | Organization (везде) | Organization | дополнить `@type: ["Organization", "ClothingStore"]` или связать `#organization` ↔ `#store` через `subOrganization`/`hasPOS` | 🟠 | сейчас на `/contacts/` есть отдельный `#store`, но Organization его не упоминает |
| 22 | WebSite (везде) | WebSite | `inLanguage` (массив), `publisher → #organization`, `alternateName` | 🟡 | – |
| 23 | Все Person ref-ы (31 страница) | Person | узел Person `#founder` определён только на `/pro-brand/`; на 31 странице ref остаётся orphan | 🟠 | вынести Person в base.html либо принять, что AI достанет Person через graph crawl /pro-brand/ |
| 24 | `/novyny/` | Blog / BlogPosting | вообще отсутствует | 🟠 | при появлении контента создать Blog + BlogPosting per-post |
| 25 | Все WebPage-узлы | Speakable | `cssSelector[]` или `xpath[]` | 🟡 | для голосового поиска; целиться на h1 + intro |

---

## 4. Граф связей через `@id`

### 4.1 Что реально есть на live (на хорошо собранных страницах)

```
                           #organization (Organization)
                           ├─ founder        ──┐
                           ├─ contactPoint     │
                           ├─ foundingLocation │
                           ├─ address          │
                           └─ sameAs[2]        │
                                               │
       ┌── about ─┐                            │
       ▼          │                            │
 #webpage         │                            ▼
 (home)           │                       #founder (Person)
 (pro-brand →     │                       (определён ТОЛЬКО
  #about-page)    │                        на /pro-brand/!)
       │          │
       │ isPartOf │
       ▼          │
 #website (WebSite)
       │
       └─ potentialAction → SearchAction

 home: #webpage ── breadcrumb ──▶ #breadcrumbs (BreadcrumbList)
 pro-brand: #about-page ── (нет breadcrumb-ref!) ─ #breadcrumbs
                       └── about → #organization (ref-ом ✅)
                       └── isPartOf → #website (ref-ом ✅)
                       └── datePublished, dateModified ✅

 contacts: ContactPage (без @id)
              ├── isPartOf → #website (ref-ом ✅)
              ├── about    → #organization (ref-ом ✅)
              └── mainEntity → ClothingStore (#store)
                                       └── parentOrganization → #organization (ref-ом ✅)
```

### 4.2 Где граф разрывается (PDP, категории, support)

```
PDP /product/<slug>/  (11 страниц)
─────────────────────
 [Organization] (block#0, base.html)            # @id есть
 [WebSite]      (block#1, base.html)            # @id есть
 [@graph]:                                       # block#2
    Product             ❌ no @id
       ├─ brand           — Brand inline (без @id)
       ├─ manufacturer    — Organization inline (без @id-ref!)
       ├─ offers.seller   — Organization inline (без @id-ref!)
       └─ offers.shippingDetails ×3 inline
    BreadcrumbList      ✅ @id = <url>#breadcrumbs
                          (но никто на него не ссылается через breadcrumb!)
 [FAQPage]      ❌ no @id, no isPartOf, no inLanguage

 ⛔  Нет узла "WebPage" → Product, BreadcrumbList, FAQPage висят
     вне графа сайта; AI-парсер должен догадываться, что это одна
     страница.

Categories /catalog/, /catalog/<cat>/  (4 страницы)
─────────────────────────────
 [Organization]                                  # @id
 [WebSite]                                       # @id
 [@graph]:
    BreadcrumbList    ❌ no @id
    CollectionPage    ❌ no @id, no isPartOf, no breadcrumb-ref,
                         no about, no inLanguage
       └─ mainEntity → ItemList
                       ├─ itemListOrder
                       └─ itemListElement[16]  (string url, no @id-ref на Product)

 ⛔  CollectionPage висит сама по себе. ListItem.url — голая строка,
     а не ref-by-@id на Product.

Support /delivery/, /faq/ ... (11 страниц)
────────────────────────────────
 [Organization]                                  # @id
 [WebSite]                                       # @id
 [FAQPage] (только на части)                     ❌ no @id
 [WebPage + BreadcrumbList]  ⛔ broken JSON (см. п.2)
```

### 4.3 Желаемый граф

```
#organization (Organization, дополнительно ClothingStore через @type-array)
   ├── founder            → #founder (Person — определён 1 раз)
   ├── brand              → #brand (Brand)
   ├── hasMerchantReturnPolicy → #return-policy (вынесен из каждого Offer)
   ├── shippingDetails[]  → [#ship-ua-np, #ship-ua-courier, #ship-intl]
   ├── contactPoint[]     → [#cp-support, #cp-wholesale, #cp-press]
   ├── hasPOS / subOrganization → #store (ClothingStore на /contacts/)
   └── sameAs[] ≥5

#website
   ├── inLanguage [uk-UA, ru-UA, en-UA]
   ├── publisher  → #organization
   └── potentialAction → SearchAction

любая страница: #webpage|#collection-page|#about-page|#contact-page|#product-page
   ├── isPartOf  → #website
   ├── about     → #organization
   ├── breadcrumb → <url>#breadcrumbs
   ├── primaryImageOfPage → ImageObject
   ├── inLanguage / datePublished / dateModified / speakable
   └── mainEntity → (Product | ProductGroup | ItemList | FAQPage | HowTo)

PDP canonical:
  #product (Product)
   ├── @id = <canonical>#product
   ├── isVariantOf → #productgroup-<slug>
   ├── manufacturer → #organization (ref)
   ├── offers → #offer-<slug>
   │      ├── seller → #organization (ref)
   │      ├── hasMerchantReturnPolicy → #return-policy (ref)
   │      └── shippingDetails[]    → [ship-* ref]
   ├── aggregateRating → #aggrating-<slug>
   └── review[] → #review-<id>

PDP variant /<slug>/<color>/:
  либо <link rel=canonical> → родитель + 0 schema (рекомендация),
  либо #product-<slug>-<color>
       ├── isVariantOf → #productgroup-<slug>
       ├── color/size/sku/image — РАЗНЫЕ от canonical
       └── url, name, description — переписаны под цвет
```

---

## 5. Дубликаты сущностей (одинаковый `@id`, разные поля)

| Где | `@id` | Дубль | Severity |
|---|---|---|---|
| `/pro-brand/` | `https://twocomms.shop/#organization` | block#0 (полный: foundingDate, foundingLocation, address, founder, contactPoint) vs block#3 (стрипанный: только sameAs/contactPoint) | 🟠 |
| `/pro-brand/` | `https://twocomms.shop/#website` | block#1 (с potentialAction, description) vs block#4 (только name+url) | 🟠 |
| Все 11 PDP | (нет `@id`) Product, FAQPage | сами Product/FAQ повторяются 3 раза в variant-paths без isVariantOf-обёртки | 🔴 |

При graph-merge AI-парсер берёт "последний" — но это лишний шум и мешает
Google Rich Results Test (он часто ругается на duplicate `@id`).

---

## 6. Orphan `@id` ref-ы (ссылается, но узла нет на той же странице)

| Page | Orphan ref | Узел определён на | Severity |
|---|---|---|---|
| 31 страница (всё кроме `/pro-brand/`) | `Organization.founder.@id = #founder` | только `/pro-brand/` block#6 | 🟠 |

Технически JSON-LD-парсер AI-сёрча может склеить узлы из нескольких URL, но
это требует отдельного crawl-pass. Безопаснее — определить Person в `base.html`
рядом с Organization (чтобы появлялся на всех страницах).

---

## 7. `@id` отсутствует там, где нужен

| Узел | Где | Шаблон ID |
|---|---|---|
| Product | все 11 PDP (canonical + variants + RU/EN) | `<canonical-url>#product` |
| ProductGroup | canonical PDP (новый узел) | `<canonical-url>#productgroup` |
| FAQPage | все 11 PDP + `/cooperation/, /custom-print/, /wholesale/, /pro-brand/, /delivery/, /faq/, /dopomoga/, /povernennya/` | `<page-url>#faq` |
| CollectionPage | `/catalog/`, `/catalog/tshirts/`, `/catalog/hoodie/`, `/catalog/long-sleeve/` | `<page-url>#collection-page` |
| BreadcrumbList | все 4 категории и `/catalog/` (top-level в `@graph`) | `<page-url>#breadcrumbs` |
| WebPage | `/cooperation/`, `/wholesale/` (на live сейчас inline без `@id`) | `<page-url>#webpage` |
| ContactPage | `/contacts/` (есть тип, нет `@id`) | `<page-url>#contact-page` |
| Service | `/custom-print/` | `<page-url>#service-dtf` |
| HowTo | `/rozmirna-sitka/`, `/doglyad-za-odyagom/` | `<page-url>#howto` |
| OfferCatalog (children) | `/pro-brand/` block#5 — у parent есть `@id`, у 3 детей нет | `<root>#offer-catalog-tshirts/...` |
| ListItem.item | категории mainEntity.ItemList — сейчас `url` строкой, нужно `@id`-ref на Product | – |

---

## 8. Special findings (фокус-список из задачи)

### 8.1 На каких страницах нет `BreadcrumbList`?

**Live (после `4a60b4df`):** BreadcrumbList отсутствует на:

- `/delivery/` — должен быть, но JSON-LD-блок broken
- `/faq/` — broken
- `/dopomoga/` — broken
- `/povernennya-ta-obmin/` — broken
- `/rozmirna-sitka/` — broken
- `/doglyad-za-odyagom/` — broken
- `/vidstezhennya-zamovlennya/` — broken
- `/mapa-saytu/` — broken
- `/novyny/` — broken
- `/polityka-konfidentsiynosti/` — broken
- `/umovy-vykorystannya/` — broken

То есть **все 11 пропусков объясняются одной фикс-точкой** (broken JSON в
`support_page.html`). На остальных 21 странице BreadcrumbList присутствует.

### 8.2 Где Product schema не содержит `aggregateRating` несмотря на наличие отзывов?

`aggregateRating` отсутствует на **всех 11 PDP** (canonical + variants + RU/EN).
На странице `/product/classic-tshirt/` в HTML видны блоки с UGC-отзывами
(см. content-audit), но в JSON-LD они не выведены. Это блокирует star-rating
в SERP и убирает социальное доказательство для AI-сёрча.

### 8.3 Где `FAQPage` дублируется (одинаковые Q на разных страницах)?

**Внутри одной страницы (PDP):** на каждом из 11 PDP в `mainEntity[]` лежит
**13 Question-узлов**, из которых уникальных по `name` — **5**. То есть 8
буквальных повторов в одном блоке. Образцы:

```
pdp-classic-tshirt:
  - Чи доступна ця футболка без принту?              (×3)
  - Як прати футболку, щоб принт не зіпсувався?      (×3)
  - Як швидко доставимо футболку?                     (×3)
  - Чи можна замовити футболку зі своїм принтом?      (×3)
  - Як обрати розмір футболки?                        (×1)
```

**Между разными страницами:** между PDP и `/faq/` пересечений по дословному
тексту вопроса **0** (PDP-FAQ полностью продукт-ориентированы, root FAQ —
service-ориентирован). Между `/faq/` и `/delivery/` — 1 общий вопрос (`Як
відстежити замовлення?`), что норм.

То есть проблема **дубль-внутри-одной-страницы**, не дубль-между-страницами.

### 8.4 Где `WebPage` без `@id` / `inLanguage` / `isPartOf` / `about`?

| Page | `@id` | `inLanguage` | `isPartOf → #website` | `about → #organization` | `breadcrumb → #breadcrumbs` |
|---|---|---|---|---|---|
| `/` (home) | ✅ `#webpage` | ✅ uk-UA | ✅ | ✅ | ✅ |
| `/pro-brand/` | ✅ `pro-brand/#about-page` | ✅ uk-UA | ✅ | ✅ | ❌ (BC лежит отдельно) |
| `/contacts/` | ❌ | ❌ | ✅ | ✅ | ❌ (BC лежит отдельно) |
| `/cooperation/` | ❌ | ❌ | ✅ inline | ❌ | ❌ |
| `/wholesale/` | ❌ | ❌ | ❌ (есть inline `publisher`) | ❌ | ❌ |
| 4 категории `/catalog/...` | ❌ | ❌ | ❌ | ❌ | ❌ |
| 11 PDP | n/a (нет WebPage) | n/a | n/a | n/a | n/a |
| 11 support broken | (broken — не парсится) | – | – | – | – |

### 8.5 Есть ли `hasVariant` / `isVariantOf` для path-URL вариантов товара?

**Нет**, ни на одной странице.
3 проверенных variant-URL:

- `/product/classic-tshirt/black/`
- `/product/classic-tshirt/oversize/`
- `/product/my-little-baby/coyote/`

Каждый отдаёт идентичный canonical-PDP `Product`-узел (та же `name`, `image`,
`description`, `color`, `sku`, `price`, тот же `BreadcrumbList @id`). Меняется
только `Product.url` и canonical/og-meta. Соответственно нет ни
`ProductGroup`-родителя, ни `isVariantOf`-ссылки наверх.

### 8.6 Есть ли `Speakable` где-нибудь?

**Нет**, ни на одной странице. Поиск по grep на parsed-блокам — 0 совпадений.

### 8.7 Есть ли `Article` или `BlogPosting` на /pro-brand/, /wholesale/, /cooperation/, /custom-print/, /faq/?

**Нет**, ни на одной из перечисленных. `/novyny/` (блог-раздел) тоже без Blog
schema (плюс broken JSON-LD). Это потенциально большая возможность для
content-led seo: помечать каждую длинноформатную страницу `Article` (или
`BlogPosting` для `/novyny/<slug>/`) с `headline, datePublished, dateModified,
author, publisher, mainEntityOfPage`.

### 8.8 Связан ли `ClothingStore` с `Organization` через `parentOrganization`?

**Да, теперь связан.** На `/contacts/` block#2:

```jsonc
"mainEntity": {
  "@type": "ClothingStore",
  "@id": "https://twocomms.shop/#store",
  "parentOrganization": {
    "@id": "https://twocomms.shop/#organization"
  },
  ...
}
```

⚠️ Обратной связи (`Organization.subOrganization → #store` или `hasPOS`) пока
нет. Для AI-парсера это OK (parentOrganization — нормальная связь), но для
полноты графа стоит добавить и обратную сторону.

---

## 9. Полнота полей по типам (быстрая ссылка)

### 9.1 Organization (на всех 32 страницах)

✅ Есть: `@id, @type, name, url, logo, description, foundingDate (2022),
foundingLocation (Place→PostalAddress, Харків), address (PostalAddress, Харків
UA-63), founder (ref → #founder), sameAs[] (Instagram + Telegram), contactPoint
(ContactPoint, telephone, customer support, [uk,ru,en]).`

❌ Не хватает:
- `sameAs[]` ≥5 каналов (Facebook, TikTok, X, YouTube, Wikidata) — 🔴
- `email`, `legalName`, `vatID/taxID`, `knowsAbout[]`, `slogan`,
  `numberOfEmployees`, `award`, `subjectOf`, `parentOrganization`, `subOrganization` — 🟠/🟢
- multi-typing `@type: ["Organization", "ClothingStore"]` или `hasPOS → #store` — 🟠
- `MerchantReturnPolicy` на уровне Organization (Google требует с 2024) — 🟠

### 9.2 WebSite (на 32 страницах)

✅ Есть: `@id, @type, name, url, description, potentialAction (SearchAction
target → EntryPoint, query-input)`.

❌ Не хватает: `inLanguage[]`, `publisher → #organization`, `alternateName`,
`copyrightHolder/Year` — 🟡.

### 9.3 WebPage / AboutPage / CollectionPage / ContactPage

| Поле | home | pro-brand | contacts | cooperation | wholesale | catalog-* | PDP |
|---|---|---|---|---|---|---|---|
| `@id` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | n/a |
| `inLanguage` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | n/a |
| `isPartOf` ref | ✅ | ✅ | ✅ | ✅ inline | ❌ | ❌ | n/a |
| `about` ref | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | n/a |
| `breadcrumb` ref | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | n/a |
| `mainEntity` | ✅ ItemList | ❌ | ✅ ClothingStore | ❌ | ❌ | ✅ ItemList(16) | n/a |
| `primaryImageOfPage` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | n/a |
| `datePublished` | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | n/a |
| `dateModified` | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | n/a |
| `speakable` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | n/a |

🔴 **На PDP узла WebPage вообще нет** — Product и BreadcrumbList лежат внутри
`@graph`-блока без обёртки страницей.

### 9.4 Product (11 PDP/variants/locales)

✅ Есть: `@type, inLanguage, name, description, sku, mpn, url, image (str|str[]),
material, countryOfOrigin{Country}, additionalProperty[10 PropertyValue], brand{Brand},
manufacturer{Organization-inline}, offers{Offer ...}, releaseDate, dateModified,
category, color, size`.

✅ Offer богатая: `price, priceCurrency, availability=MadeToOrder, itemCondition,
url, priceValidUntil, hasMerchantReturnPolicy{MerchantReturnPolicy(...)},
seller{Organization-inline}, shippingDetails[3 OfferShippingDetails],
priceSpecification{CompoundPriceSpecification}`.

❌ Не хватает (🔴 — must, 🟠 — strong):
- `@id` — 🔴
- `aggregateRating`, `review[]` — 🔴
- `gtin13/gtin12` — 🔴
- `hasVariant` / `isVariantOf` / `ProductGroup` — 🔴
- `audience{PeopleAudience(suggestedGender,...)}` — 🟠 (сейчас в additionalProperty)
- `manufacturer` ref-by-`@id` на `#organization` — 🟠
- `offers.seller` ref-by-`@id` — 🟠
- `size`/`color` нормализовать (массив или enum, не строка `"S, M, L, XL, XXL"`) — 🟡
- `priceValidUntil` синхронизировать с `dateModified` (сейчас рассинхрон) — 🟡

### 9.5 Offer (внутри Product)

✅ Все required: `@type, price, priceCurrency, availability`.
✅ Сильные сигналы: `priceValidUntil, itemCondition, url, seller, hasMerchantReturnPolicy, shippingDetails[3], priceSpecification`.
❌ Не хватает: `seller` ref-by-`@id`, `hasMerchantReturnPolicy` ref-by-`@id` на корневой `#return-policy`, `shippingDetails[]` ref-by-`@id` (сейчас 3 OfferShippingDetails inline-объявляются 11 раз — лучше один раз в Organization и потом ref).

### 9.6 BreadcrumbList

| Где | `@id` | itemListElement | Severity |
|---|---|---|---|
| home | `<root>#breadcrumbs` ✅ | 1 элемент (Головна) | 🟢 |
| pro-brand | `<url>#breadcrumbs` ✅ | 2 элемента | OK |
| contacts | `<url>#breadcrumbs` ✅ | 2 элемента | OK |
| 11 PDP | `<canonical-url>#breadcrumbs` ✅ (тот же `@id` для variant-страниц!) | 3 элемента | 🟠 (variant использует canonical-`@id`) |
| 4 категории | ❌ нет `@id` (в `@graph` без `@id`) | 2-3 элемента | 🟠 |
| 11 support broken | n/a | n/a | 🔴 |

### 9.7 FAQPage

| Где | `@id` | inLanguage | unique Qs | total Qs | Severity |
|---|---|---|---|---|---|
| 11 PDP (uk) | ❌ | ❌ | 5 | 13 | 🔴 (8 повторов) |
| `/ru/.../classic-tshirt/` | ❌ | ❌ | 5 (на ru) | 13 | 🔴 |
| `/en/.../classic-tshirt/` | ❌ | ❌ | 5 (на en) | 13 | 🔴 |
| `/faq/` | ❌ | ❌ | 9 | 9 | OK (нет дублей) |
| `/delivery/` | ❌ | ❌ | 4 | 4 | OK |
| `/dopomoga/` | ❌ | ❌ | 5 | 5 | OK |
| `/povernennya-ta-obmin/` | ❌ | ❌ | 3 | 3 | OK |
| `/cooperation/` | ❌ | ❌ | 3 | 3 | OK |
| `/wholesale/` | ❌ | ❌ | 3 | 3 | OK |
| `/custom-print/` | ❌ | ❌ | 5 | 5 | OK |
| `/pro-brand/` | ❌ | ❌ | 7 | 7 | OK |

✅ FAQ-блоки на RU/EN PDP — переведены на нужный язык (это улучшение vs.
прошлый аудит).

❌ Везде нет `@id`, `inLanguage`, `isPartOf → #webpage`. Авторов в Answer тоже
нет (хотя Google не требует, но AI любят `Answer.author → #organization`).

### 9.8 HowTo (`/rozmirna-sitka/`, `/doglyad-za-odyagom/`)

✅ Есть: `name, description, totalTime (PT10M / PT20M), tool[], supply[], step[]`
(6 шагов на rozmirna-sitka, 7 на doglyad).

❌ Не хватает: `@id`, `image` per-step, `isPartOf → #webpage`,
`estimatedCost`, `yield`, `video`. 🟠

⚠️ Google deprecated HowTo rich result (Aug 2023), но AI-сёрч продолжает
использовать.

### 9.9 OfferCatalog (только `/pro-brand/`)

✅ Parent: `@id = #offer-catalog, name, url, provider → #organization,
itemListElement[3]`.

❌ Дочерние OfferCatalog-узлы (Футболки/Худі/Лонгсліви) **без `@id`**, **без
`provider`**, **без `numberOfItems`/`inLanguage`/`image`**. 🟠

### 9.10 Person (founder, на `/pro-brand/`)

✅ Есть: `@id = #founder, name (Bohdan), jobTitle, worksFor → #organization,
url, image, description, knowsAbout[4], nationality{Country}`.

❌ Не хватает: `sameAs[]`, `birthDate/birthPlace`, `gender`, `alumniOf`. 🟢

⚠️ **Узел существует только на `/pro-brand/`**. Все остальные 31 страница
содержат orphan ref `Organization.founder.@id = #founder` без определения. См.
п.6.

### 9.11 ContactPage / ClothingStore (`/contacts/`)

✅ ContactPage: `name, url, isPartOf → #website, about → #organization,
mainEntity → ClothingStore`.

✅ ClothingStore: `@id = #store, parentOrganization → #organization, name,
alternateName, url, logo, image, description, telephone, email, address (Харків),
areaServed (Україна), currenciesAccepted (UAH), paymentAccepted (Cash, Credit
Card, Apple Pay, Google Pay, Bank transfer), priceRange (₴₴), contactPoint[1],
sameAs[2]`.

❌ Не хватает: ContactPage `@id, inLanguage, breadcrumb-ref`; ClothingStore
`geo (GeoCoordinates 49.9935, 36.2304)`, `hasMap`, `openingHoursSpecification`.

### 9.12 Service (`/custom-print/`)

✅ Есть: `name, provider{Organization-inline}, description, url, areaServed=UA,
serviceType="DTF Printing"`.

❌ Не хватает: `@id`, `provider` ref-by-`@id`, `offers` (диапазон цен),
`serviceOutput`, `audience`, `availableChannel`, `hoursAvailable`. 🟠

### 9.13 ItemList

| Где | itemListElement | `@id` | numberOfItems | itemListOrder | items have `@id`-ref | Severity |
|---|---|---|---|---|---|---|
| home (mainEntity) | 3 ListItem | ❌ | ❌ | ❌ | ❌ url-string | 🟡 |
| catalog-root | 3 ListItem | ❌ | ❌ | ❌ | ❌ | 🟡 |
| catalog-tshirts | 16 ListItem | ❌ | ❌ | ✅ Unordered | ❌ url-string | 🟠 |
| catalog-hoodie | 16 ListItem | ❌ | ❌ | ✅ | ❌ | 🟠 |
| catalog-long-sleeve | 16 ListItem | ❌ | ❌ | ✅ | ❌ | 🟠 |

### 9.14 Что нужного типа НЕТ совсем

| Тип | Где должен быть | Severity |
|---|---|---|
| `ProductGroup` | canonical PDP для variant-моделей | 🔴 |
| `AggregateRating` / `Review` | Product PDP | 🔴 |
| `Article` / `BlogPosting` / `Blog` | `/novyny/`, `/pro-brand/`, `/wholesale/`, `/custom-print/` (длинноформатные landing) | 🟠 |
| `Speakable` | все WebPage-узлы (особенно `/faq/`, `/pro-brand/`, PDP intro) | 🟡 |
| `MerchantReturnPolicy` (top-level в Organization) | `#organization`. Сейчас только внутри Offer | 🟠 |
| `SiteNavigationElement` / `WebSite.hasPart` | `/mapa-saytu/` | 🟡 |
| `QAPage` (single-question pages) | для топ-3 long-tail вопросов | 🟢 |
| `VideoObject` | если есть промо-ролики | 🟢 |
| `WebApplication` | конфигуратор кастомного принта на `/custom-print/` | 🟢 |
| `OpeningHoursSpecification` / `GeoCoordinates` | внутри ClothingStore на `/contacts/` | 🟡 |
| `ImageGallery` | PDP с массивом `image[]` | 🟢 |

---

## 10. Что критично добавить (приоритизация)

### 🔴 P0 (немедленно)

1. **Починить broken JSON-LD на 11 страницах.** Заменить `{# … #}` (многострочный) на `{% comment %} … {% endcomment %}` в `templates/pages/support_page.html`. Эффект — на всех 11 страницах появятся валидные WebPage + BreadcrumbList.
2. **Дедуп FAQ на PDP.** Уникализировать вопросы в `mainEntity[]` по `name` при склейке product-specific + general FAQ.
3. **Внедрить ProductGroup для variant-PDP.** Canonical отдаёт `ProductGroup{@id, name, productGroupID, variesBy:["color","size","fit"], hasVariant[#product-<sku>-...]}`. Variant-страницы либо получают `<link rel=canonical>` на родителя (выкинуть из индекса) либо собственный Product с `isVariantOf → #productgroup`.
4. **Добавить `@id` на Product** (все 11 PDP) + перевести `manufacturer`/`Offer.seller` на ref-by-`@id` вместо inline-дублей.
5. **Добавить `aggregateRating` + `review[]` на Product**, даже если 5 отзывов.
6. **Расширить `Organization.sameAs[]`** до ≥5 каналов (Facebook, TikTok, X, YouTube, Wikidata-страница).

### 🟠 P1 (1–2 недели)

7. **Добавить узел `WebPage` на каждый PDP** с `@id`, `mainEntity → Product`, `breadcrumb → BreadcrumbList`, `isPartOf → #website`, `about → #organization`, `primaryImageOfPage`, `dateModified`, `inLanguage`.
8. **Добавить `@id` + `isPartOf` + `breadcrumb-ref` + `inLanguage` на CollectionPage** для 4-х категорий.
9. **`ListItem.item` ref-by-`@id` на Product** в категориях `mainEntity.itemListElement[]` (вместо string url).
10. **Объединить все JSON-LD на странице в один `@graph`-блок** (вместо 4–9 отдельных `<script>`).
11. **Добавить Person `#founder` в base.html** (либо смириться с orphan-ref на 31 странице).
12. **Добавить Service `@id` + `offers` + `audience` + `provider` ref-by-`@id`** на `/custom-print/`.
13. **Добавить top-level `MerchantReturnPolicy` в Organization** + ref-by-`@id` из Offer-ов.

### 🟡 P2 (1–2 месяца)

14. **`inLanguage` per-locale на FAQPage / WebPage / Product**.
15. **Speakable cssSelector** на главные WebPage (h1, intro).
16. **Article schema на /pro-brand/, /custom-print/, /wholesale/** (длинноформатные landing-страницы) — `headline, datePublished, dateModified, author, publisher, articleBody`.
17. **Blog + BlogPosting на /novyny/** + per-post страницы.
18. **`size`/`color` нормализовать** в Product (массив вместо строки `"S, M, L, XL, XXL"`).
19. **Добавить `legalName, vatID, knowsAbout, slogan, email`** в Organization.
20. **`geo (GeoCoordinates)` в ClothingStore** на `/contacts/`.

### 🟢 P3 (nice-to-have)

21. SiteNavigationElement на `/mapa-saytu/`.
22. QAPage для топ-3 long-tail вопросов.
23. VideoObject если есть видео.
24. WebApplication на конфигуратор кастомного принта.
25. `image` per-HowToStep.

---

## Сырые данные

- `02_schema_raw.json` — массив всех 32 страниц с компактным реестром каждого блока (`@type`, `@id`, `top_keys`, `parse_error`).
- `/tmp/seo_audit/schema/parsed/<slug>.json` — полный распарсенный JSON по каждой странице (для глубокого drill-down).
- `/tmp/seo_audit/schema/raw/<slug>.html` — сырые HTML-снимки страниц.
- `/tmp/seo_audit/schema/summary.json` — глобальная сводка типов и `@id`-ов.

Воспроизводимость:

```bash
python3 .kiro/specs/seo-molecular-upgrade/audit/_tools/fetch_and_parse.py
python3 .kiro/specs/seo-molecular-upgrade/audit/_tools/analyze.py
python3 .kiro/specs/seo-molecular-upgrade/audit/_tools/og_check.py
```

---

## Appendix. Что улучшилось vs. предыдущая итерация (commit `98924999`)

| Изменение | Live до `4a60b4df` | Live после `4a60b4df` |
|---|---|---|
| `Organization.founder` | ❌ | ✅ (ref на `#founder`) |
| `Organization.foundingDate` | ❌ | ✅ "2022" |
| `Organization.foundingLocation` | ❌ | ✅ Place→Харків UA-63 |
| `Organization.address` | ❌ | ✅ Харків UA-63 |
| Person узел `#founder` на `/pro-brand/` | ❌ | ✅ |
| `/contacts/` HTTP status | 500 | **200** ✅ |
| `ContactPage` schema | ❌ | ✅ (без `@id`) |
| `ClothingStore` + `parentOrganization` | ❌ | ✅ `#store → #organization` |
| BreadcrumbList на `/contacts/` | ❌ | ✅ |
| BreadcrumbList на home | ❌ | ✅ |
| WebPage `@id` на home | ❌ | ✅ `#webpage` |
| `Product.releaseDate` / `dateModified` | ❌ | ✅ |
| HowTo на `/rozmirna-sitka/` | ❌ | ✅ (6 шагов) |
| HowTo на `/doglyad-za-odyagom/` | ❌ | ✅ (7 шагов) |
| FAQ на RU/EN PDP | ❌ остался украинским | ✅ переведён |
| Broken JSON-LD на 11 support pages | 11 страниц | **11 страниц (не исправлено)** ❌ |
| FAQ-дубли на PDP (8 из 13) | дубли | **дубли (не исправлено)** ❌ |
| ProductGroup / hasVariant / isVariantOf | ❌ | **❌ (не исправлено)** |
| Product.aggregateRating | ❌ | **❌ (не исправлено)** |
| Product.@id | ❌ | **❌ (не исправлено)** |

То есть `4a60b4df` закрывает ~7 P0/P1 пунктов из прошлого отчёта; остаётся 5
крупных открытых блоков (broken JSON, FAQ-дубли, ProductGroup, Product.@id,
aggregateRating).

