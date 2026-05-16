# Schema.org Audit — TwoComms

> Глубокий аудит JSON-LD сайта `https://twocomms.shop` по 32 страницам
> (homepage, catalog-root, 3 категории, 6 PDP, 3 PDP-варианта,
> RU/EN PDP-локали, 14 support pages).
> Дата фиксации: 2026-05-16.
>
> Артефакты:
> - `/tmp/seo_audit/schema/raw/<slug>.html` — сырые HTML-снимки страниц
> - `/tmp/seo_audit/schema/parsed/<slug>.json` — массивы блоков JSON-LD
>   (`raw`, `parsed`, `parse_error`)
> - `/tmp/seo_audit/schema/summary.json` — сводка по типам/идентификаторам
> - Вспомогательные скрипты:
>   - `audit/_tools/fetch_and_parse.py` — fetcher + JSON-LD extractor
>   - `audit/_tools/analyze.py` — матрица типов, конфликты @id, дубли FAQ
>   - `audit/_tools/og_check.py` — проверка OG/canonical/title

---

## Executive Summary

TwoComms имеет **достаточно зрелый базовый JSON-LD** (Organization, WebSite,
WebPage/AboutPage/CollectionPage, BreadcrumbList, Product+Offer с
shippingDetails и hasMerchantReturnPolicy, FAQPage, HowTo, Person,
OfferCatalog), и это сильно опережает большинство Shopify/WordPress-сторов
из той же ниши. Но есть **критические дефекты**, которые либо ломают
graph-консистентность для AI-search, либо вообще делают часть JSON-LD
невалидной для Google.

Статус по основным блокам:

| Блок                  | Статус        | Ключевая проблема |
|-----------------------|---------------|-------------------|
| Organization          | ⚠️ есть, но недотянут | sameAs только 2 канала (мин. 5), нет founder.@id-целевого узла на 30/31 страниц, дубль с конкурирующими полями на `/pro-brand/` |
| WebSite + SearchAction| ✅ ок          | дублируется упрощённый WebSite на `/pro-brand/` |
| WebPage / AboutPage   | ⚠️ частично    | отсутствует `@id` у CollectionPage и большинства WebPage; не везде есть `breadcrumb`/`isPartOf`/`primaryImageOfPage`/`dateModified` |
| BreadcrumbList        | ⚠️ почти ок    | на категориях нет `@id`, отсутствует обратная ссылка из CollectionPage через `breadcrumb` |
| Product               | 🔴 **критично**| variant-страницы (`/<slug>/<color>/<fit>/`) НЕ обновляют `name`/`image`/`description`/`color`/`size`/`sku`/`price` относительно canonical; нет `@id`, `aggregateRating`, `review`, `audience`, `gtin*`, `hasVariant`/`isVariantOf`/`ProductGroup`; `manufacturer`/`seller` дублируют Organization вместо `@id`-ссылки |
| FAQPage (PDP)         | 🔴 **критично**| на всех 11 PDP — 13 пунктов, из них **только 5 уникальных**, остальное буквальные повторы; FAQ-блок без `@id`; в SERP уже не отображается (Google retired FAQ rich results May 2026), но дубли создают шум для AI-индексаторов |
| HowTo                 | ✅ ок          | один из двух блоков на странице ломается (см. ниже) |
| Service / OfferCatalog| ⚠️ ок, без @id | дочерние OfferCatalog без `@id`, без `provider/inLanguage` |
| Person (founder)      | ✅ ок          | определён только на `/pro-brand/`, остальные 30 страниц ссылаются по `@id` на несуществующий на этой странице узел |
| ContactPage           | 🔴 **отсутствует** | страница `/contacts/` отдаёт **HTTP 500**, типа `ContactPage` нигде нет |

🔥 **Топ-5 проблем, которые точно режут видимость в AI-поиске:**

1. **11 страниц со сломанным JSON-LD** (parse error). Источник — Django-комментарии `{# ... #}` внутри `<script type="application/ld+json">` в `support_page.html`. Эти комментарии в Django **многострочно не работают** (`{#` парсится только в пределах одной строки), часть идёт в HTML и валит JSON. Это **/delivery/, /faq/, /dopomoga/, /povernennya-ta-obmin/, /rozmirna-sitka/, /doglyad-za-odyagom/, /vidstezhennya-zamovlennya/, /mapa-saytu/, /novyny/, /polityka-konfidentsiynosti/, /umovy-vykorystannya/**.
2. **Variant-страницы PDP отдают тот же Product schema, что и canonical** — но при этом отдают разные `<title>`, `og:title`, `og:description`, `og:image` (для color-variant). Несоответствие OG ↔ JSON-LD путает AI-парсеры; каноникал на самой variant-странице (а не на родителе) делает их фактически дублями PDP в индексе.
3. **Нет ProductGroup / hasVariant / isVariantOf**. Google и AI-search ожидают граф `ProductGroup → has variants`. У нас 118 variant-URL в `sitemap-product-variants.xml`, и они формально не связаны с базовыми Products.
4. **FAQ-дубликаты на всех PDP** (8 повторов из 13). Google deprecated FAQ rich results, но FAQPage остаётся источником данных для Perplexity/ChatGPT-search; дубли там — антисигнал.
5. **`/contacts/` отдаёт 500** — нет ни `ContactPage`, ни `LocalBusiness`/`Place`, что критично для бренда с физической локацией в Харкове.

---

## 1. @type × Page matrix

Колонка `@id?` фиксирует наличие **хотя бы одного** `@id` на любом узле страницы.
`@id top?` — есть ли `@id` у **главного** узла страницы (WebPage/CollectionPage/AboutPage/Product).

| Slug | URL | Blocks | @types (top-level) | Has @id? | @id top? | Has Breadcrumb | Has FAQ | Has HowTo | Has Product | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| home | `/` | 4 | Organization, WebSite, WebPage, BreadcrumbList | ✅ | ✅ `#webpage` | ✅ | ❌ | ❌ | ❌ | образцовая страница: WebPage связан с Organization и WebSite через @id |
| catalog-root | `/catalog/` | 3 | Organization, WebSite, [BreadcrumbList + CollectionPage] | ⚠️ | ❌ | ✅ | ❌ | ❌ | ❌ | CollectionPage без @id, `mainEntity.ItemList` содержит лишь 3 категории; нет `breadcrumb` ref-а |
| cat-tshirts | `/catalog/tshirts/` | 3 | Organization, WebSite, [BreadcrumbList + CollectionPage] | ⚠️ | ❌ | ✅ | ❌ | ❌ | ❌ | то же; ItemList c 16 PDP-ссылок, но без image/Product mini-объектов |
| cat-hoodie | `/catalog/hoodie/` | 3 | Organization, WebSite, [BreadcrumbList + CollectionPage] | ⚠️ | ❌ | ✅ | ❌ | ❌ | ❌ | как cat-tshirts |
| cat-long-sleeve | `/catalog/long-sleeve/` | 3 | Organization, WebSite, [BreadcrumbList + CollectionPage] | ⚠️ | ❌ | ✅ | ❌ | ❌ | ❌ | как cat-tshirts |
| pdp-classic-tshirt | `/product/classic-tshirt/` | 4 | Organization, WebSite, [Product + BreadcrumbList], FAQPage | ⚠️ | ❌ Product без @id | ✅ | ✅ дубли | ❌ | ✅ | FAQ 13 пунктов, 5 уник.; Product без `aggregateRating/review/gtin*/audience/hasVariant` |
| pdp-hoodie-classic | `/product/hoodie-classic/` | 4 | как pdp-classic-tshirt | ⚠️ | ❌ | ✅ | ✅ дубли | ❌ | ✅ | то же |
| pdp-longsleeve-classic | `/product/longsleeve-classic/` | 4 | как pdp-classic-tshirt | ⚠️ | ❌ | ✅ | ✅ дубли | ❌ | ✅ | то же |
| pdp-my-little-baby | `/product/my-little-baby/` | 4 | как pdp-classic-tshirt | ⚠️ | ❌ | ✅ | ✅ дубли | ❌ | ✅ | image — массив (3 шт.), что хорошо |
| pdp-where-mi-present-ts | `/product/where-mi-present-ts/` | 4 | как pdp-classic-tshirt | ⚠️ | ❌ | ✅ | ✅ дубли | ❌ | ✅ | image — массив |
| pdp-in-shee | `/product/in-shee/` | 4 | как pdp-classic-tshirt | ⚠️ | ❌ | ✅ | ✅ дубли | ❌ | ✅ | image — string (одна) |
| var-classic-tshirt-black | `/product/classic-tshirt/black/` | 4 | как pdp-classic-tshirt | ⚠️ | ❌ | ✅ | ✅ дубли | ❌ | ✅ | **дубль PDP, тот же Product schema, только url отличается** |
| var-classic-tshirt-oversize | `/product/classic-tshirt/oversize/` | 4 | как pdp-classic-tshirt | ⚠️ | ❌ | ✅ | ✅ дубли | ❌ | ✅ | дубль PDP |
| var-my-little-baby-coyote | `/product/my-little-baby/coyote/` | 4 | как pdp-classic-tshirt | ⚠️ | ❌ | ✅ | ✅ дубли | ❌ | ✅ | дубль PDP, image-array отличается порядком |
| pdp-ru-classic-tshirt | `/ru/product/classic-tshirt/` | 4 | как pdp-classic-tshirt | ⚠️ | ❌ | ✅ | ✅ дубли | ❌ | ✅ | description на русском, FAQ-блок остался украинским (mismatch) |
| pdp-en-classic-tshirt | `/en/product/classic-tshirt/` | 4 | как pdp-classic-tshirt | ⚠️ | ❌ | ✅ | ✅ дубли | ❌ | ✅ | description на английском, FAQ-блок остался украинским |
| delivery | `/delivery/` | 4 | Organization, WebSite, **[broken]**, FAQPage | ❌ | ❌ | — | ✅ | ❌ | ❌ | block#3 не парсится (Django-комменты в JSON) |
| pro-brand | `/pro-brand/` | 9 | Organization, WebSite, AboutPage, **Organization (dup)**, **WebSite (dup)**, OfferCatalog, Person, BreadcrumbList, FAQPage | ✅ | ✅ `#about-page` | ✅ | ✅ | ❌ | ❌ | образцовая страница, но дубли Organization/WebSite с разным набором полей |
| contacts | `/contacts/` | 0 | — | — | — | — | — | — | — | **HTTP 500**: ни ContactPage, ни LocalBusiness, ни schema |
| cooperation | `/cooperation/` | 5 | Organization, WebSite, WebPage, BreadcrumbList, FAQPage | ⚠️ | ❌ WebPage | ✅ | ✅ | ❌ | ❌ | WebPage без @id; **второй Organization внутри WebPage.publisher без @id** |
| custom-print | `/custom-print/` | 5 | Organization, WebSite, Service, BreadcrumbList, FAQPage | ⚠️ | — | ✅ | ✅ | ❌ | ❌ | Service есть, но без @id, без `serviceOutput`, `offers`, `provider` ref-ом по @id |
| wholesale | `/wholesale/` | 5 | Organization, WebSite, WebPage, BreadcrumbList, FAQPage | ⚠️ | ❌ | ✅ | ✅ | ❌ | ❌ | как cooperation; в WebPage.publisher новый ImageObject вместо ссылки на logo |
| dopomoga | `/dopomoga/` | 4 | Organization, WebSite, **[broken]**, FAQPage | ❌ | ❌ | — | ✅ | ❌ | ❌ | block#3 broken |
| faq | `/faq/` | 4 | Organization, WebSite, **[broken]**, FAQPage | ❌ | ❌ | — | ✅ | ❌ | ❌ | block#3 broken (страница главного FAQ) |
| rozmirna-sitka | `/rozmirna-sitka/` | 4 | Organization, WebSite, HowTo, **[broken]** | ⚠️ | — | — | ❌ | ✅ | ❌ | block#3 broken — но это блок [WebPage, BreadcrumbList], а HowTo (block#2) валиден |
| doglyad-za-odyagom | `/doglyad-za-odyagom/` | 4 | Organization, WebSite, HowTo, **[broken]** | ⚠️ | — | — | ❌ | ✅ | ❌ | как rozmirna-sitka |
| vidstezhennya | `/vidstezhennya-zamovlennya/` | 3 | Organization, WebSite, **[broken]** | ❌ | — | — | ❌ | ❌ | ❌ | block#2 broken — единственный «контентный» блок страницы |
| mapa-saytu | `/mapa-saytu/` | 3 | Organization, WebSite, **[broken]** | ❌ | — | — | ❌ | ❌ | ❌ | block#2 broken; нет SiteNavigationElement |
| novyny | `/novyny/` | 3 | Organization, WebSite, **[broken]** | ❌ | — | — | ❌ | ❌ | ❌ | block#2 broken; нет Blog/CollectionPage |
| povernennya | `/povernennya-ta-obmin/` | 4 | Organization, WebSite, **[broken]**, FAQPage | ❌ | — | — | ✅ | ❌ | ❌ | broken; должна была быть `MerchantReturnPolicy` (отдельный JSON-LD) |
| privacy | `/polityka-konfidentsiynosti/` | 3 | Organization, WebSite, **[broken]** | ❌ | — | — | ❌ | ❌ | ❌ | broken |
| terms | `/umovy-vykorystannya/` | 3 | Organization, WebSite, **[broken]** | ❌ | — | — | ❌ | ❌ | ❌ | broken |

**Сводная статистика:**

- Всего страниц проверено: **32** (31 успешно, 1 в 500-ой ошибке)
- Страниц с **broken JSON-LD**: **11** (≈35%)
- Страниц с **дублями Question внутри FAQPage**: **11** (все PDP+варианты+RU/EN)
- Страниц без `@id` на главном узле: **24** (все категории, все PDP, FAQPage всех типов, WebPage cooperation/wholesale)
- Страниц с `Product`: 11 (включая 3 цветовых variant и 2 локали)
- Страниц с `HowTo`: 2

---

## 2. Schema completeness per @type

Для каждого встретившегося типа: какие свойства есть, какие критичные отсутствуют, и приоритет фикса (🔴 critical / 🟠 high / 🟡 medium / 🟢 low).

### 2.1 Organization (`https://twocomms.shop/#organization`) — встречается на 31 странице

**Есть:**
`@context, @id, @type, name, url, logo, description, foundingDate, foundingLocation{Place→PostalAddress}, address{PostalAddress}, founder{@id ref}, sameAs[], contactPoint{ContactPoint(telephone, contactType, availableLanguage[])}`

**Чего не хватает (важно для AI search 2026):**

| Поле | Приоритет | Почему |
|---|---|---|
| `sameAs` — нужно ≥5 каналов | 🔴 | Сейчас только Instagram + Telegram. AI-парсеры (Perplexity, ChatGPT Search) используют sameAs для верификации сущности и сшивки с Knowledge Graph. Должно быть: Instagram, Telegram, **Facebook, TikTok, YouTube/Threads, Wikidata, GitHub (если есть), Pinterest, X/Twitter, любой каталог брендов** — минимум 5–7 |
| `email` (внутри ContactPoint или Organization) | 🟠 | Нет email-канала, при том что у бренда наверняка есть |
| `legalName` | 🟡 | Юридическое название (ФОП ...) — для validators и Google Knowledge Panel |
| `vatID` / `taxID` / `iso6523Code` | 🟡 | Для commerce-бизнеса в UA — VAT/ЄДРПОУ |
| `numberOfEmployees`, `slogan` | 🟢 | Микро-бонус для AI-обоснованности бренда |
| `knowsAbout` | 🟠 | Бренд позиционируется на узкой нише (streetwear/military). Список knowsAbout помогает Knowledge Graph стянуть бренд к нужным концептам |
| `brand` (рекурсивно — Organization → brand: Brand) | 🟡 | На PDP `brand` уже есть как Brand-узел, но Org не объявляет себя как `brand-of` |
| `award`, `award`, `event`, `subjectOf` | 🟢 | Если есть пресса/коллабы — можно тянуть |
| `parentOrganization` / `subOrganization` | 🟢 | Если есть юрлицо отдельно — связать |
| Дополнительный `@type: ClothingStore` (multi-typing) | 🟠 | `@type: ["Organization", "ClothingStore"]` или отдельный узел `ClothingStore` с `parentOrganization → #organization`. Сейчас типа `ClothingStore` нет нигде — это упускает classification «магазин одежды» |

**Дополнительная находка:** на `/pro-brand/` появляется второй Organization-блок с тем же `@id`, но **другим набором полей** (нет address/foundingDate/foundingLocation/founder, другой logo по версии). Это backward-compatible (последний выиграет в graph-объединении), но делает страницу шумной.

---

### 2.2 WebSite (`https://twocomms.shop/#website`) — встречается на 31 странице

**Есть:**
`@context, @id, @type, name, url, description, potentialAction{SearchAction(target=EntryPoint(urlTemplate), query-input)}`

**Чего не хватает:**

| Поле | Приоритет | Почему |
|---|---|---|
| `inLanguage` (массив `["uk-UA","ru-UA","en-UA"]` или per-locale) | 🟠 | AI-парсеры понимают мультиязычность сайта |
| `publisher` → ref на Organization @id | 🟡 | Связка website → publisher → org |
| `copyrightHolder`, `copyrightYear` | 🟢 | Прозрачность для AI |
| `alternateName` (TwoComms / Two Comms / Тукоммс?) | 🟡 | Помогает в matching при разных написаниях |
| Второй `WebSite`-блок на `/pro-brand/` (упрощённый, без description / SearchAction) | 🟠 | Удалить дубль |

---

### 2.3 WebPage / AboutPage — встречается фрагментарно

| Поле | home | catalog* | pdp* | cooperation/wholesale | pro-brand | support |
|---|---|---|---|---|---|---|
| `@id` | ✅ | ❌ | ❌ нет вообще WebPage | ❌ | ✅ | ❌ (broken) |
| `name` | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| `description` | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| `url` | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| `inLanguage` | ✅ uk-UA | ❌ | — | ❌ | ✅ uk-UA | ❌ |
| `isPartOf` ref-ом по @id | ✅ | ❌ (inline WebSite) | — | ❌ (inline) | ✅ ref | ❌ (inline) |
| `about` | ✅ ref на Org | ❌ | — | ❌ | ✅ ref | ❌ |
| `breadcrumb` ref-ом | ✅ ref | ❌ | — | ❌ | ❌ (отдельный блок без обратной ссылки) | ❌ |
| `mainEntity` | ✅ ItemList | ✅ ItemList (inline) | — | ❌ | ❌ | ❌ |
| `primaryImageOfPage` | ✅ | ❌ | — | ❌ | ❌ | ❌ |
| `datePublished` | ❌ | ❌ | — | ❌ | ✅ | условно |
| `dateModified` | ❌ | ❌ | — | ❌ | ✅ | условно |
| `speakable` | ❌ | ❌ | — | ❌ | ❌ | ❌ |
| `lastReviewed` / `reviewedBy` | ❌ | ❌ | — | ❌ | ❌ | ❌ |
| `significantLink` (для AI-нав) | ❌ | ❌ | — | ❌ | ❌ | ❌ |

**Критично для AI search 2026:**

- 🔴 У PDP вообще **нет узла WebPage**. Граф устроен так: `Product` живёт сам по себе, `BreadcrumbList` рядом, но узла, который представляет «эту страницу», нет. AI-парсеры (особенно Perplexity, ChatGPT Search) ищут `WebPage → primaryImageOfPage / breadcrumb / mainEntity → Product` — у нас этой обвязки нет, Product «висит в воздухе».
- 🔴 На категориях (`CollectionPage`) нет `@id`, нет связи с WebSite через `isPartOf`, нет `breadcrumb` ref-а на BreadcrumbList (хотя BreadcrumbList объявлен в том же `@graph`).
- 🟠 `dateModified` есть только на `/pro-brand/`. Для AI-search это сильный signal свежести.
- 🟠 `speakable` (для голосового поиска и SGE) нигде.
- 🟡 `primaryImageOfPage` есть только на home; для всех остальных — теряем картинку в knowledge panel.

---

### 2.4 BreadcrumbList — есть на 14 страницах

**Есть:**
- top-level `BreadcrumbList` со списком `ListItem` с `@type, position, name, item, @id` (на PDP — есть `@id` у ListItem, что хорошо).

**Дефекты:**

| Где | Проблема | Приоритет |
|---|---|---|
| catalog/categories | top-level `BreadcrumbList` без `@id` | 🟠 |
| home | `BreadcrumbList` есть, но содержит только 1 элемент `[Головна]` — это formally валидный, но в Search Console часто помечается как недополненный | 🟢 |
| pdp variants | те же crumbs, что и canonical (Каталог → Футболки → Футболка класична) — без указания варианта | 🟠 |
| cat-* | в `CollectionPage` нет ref-а на BreadcrumbList через `breadcrumb` | 🟠 |

---

### 2.5 Product (на 11 PDP/variants/locale-копиях)

**Есть:**
`@context, @type, inLanguage (только на PDP RU/EN/canonical), name, description, sku, mpn, url, image (str | str[]), material, countryOfOrigin{Country}, additionalProperty[10 PropertyValue], brand{Brand(name,url)}, manufacturer{Organization(name,url)}, offers{Offer(...)}, releaseDate, dateModified, category, color, size`

**Offer внутри Product:**
`@type, price, priceCurrency, availability=MadeToOrder, itemCondition=NewCondition, url, priceValidUntil, hasMerchantReturnPolicy{MerchantReturnPolicy(returnPolicyCategory=FiniteReturnWindow, merchantReturnDays=14, returnMethod=ByMail, returnFees=ReturnShippingFees, returnShippingFeesAmount{MonetaryAmount}, applicableCountry=UA)}, seller{Organization(name,url,address)}, shippingDetails[3 OfferShippingDetails(shippingRate, shippingDestination, deliveryTime{ShippingDeliveryTime(businessDays, cutoffTime, handlingTime, transitTime)}, shippingWeight{QuantitativeValue})], priceSpecification{CompoundPriceSpecification}`

Это **уровень merchant listing «выше среднего»**. Но не хватает того, что Google и AI-поиск уже считают must-have:

| Поле | Приоритет | Почему |
|---|---|---|
| `@id` (например `https://twocomms.shop/product/<slug>/#product`) | 🔴 | Обязательно для cross-page references (CollectionPage → mainEntity → Product) и для linked-data graph |
| `aggregateRating{ratingValue, reviewCount, bestRating}` | 🔴 | Без рейтинга нет звёзд в SERP; для AI это «нет социального доказательства» |
| `review[]` (≥3 структурированных Review) | 🔴 | Дополняет AggregateRating, увеличивает шанс citation в AI |
| `gtin13` / `gtin12` / `gtin8` (или `gtin`) | 🔴 | После апдейта 2024 Google активно требует GTIN/MPN/brand-комбинацию для merchant listing. У нас есть только `mpn=sku` и `brand`, что иногда проходит, но **GTIN-13** у textile production часто и не ассайнится — нужно тогда явно указывать `productID="MPN:TC-1"` в Merchant Center и не подсовывать `mpn=sku` |
| `audience{PeopleAudience(suggestedGender, suggestedMinAge, suggestedMaxAge)}` | 🟠 | Сейчас age_group/gender — внутри `additionalProperty` (полу-кастомно). Лучше — typed `audience` |
| `hasVariant` / `isVariantOf` / `ProductGroup` | 🔴 | См. раздел 5 |
| `size` как `[Size]` или вложенный `additionalProperty` per-size | 🟡 | сейчас `size: "S, M, L, XL, XXL"` строкой — Google этот формат **не парсит** (https://schema.org/size ожидает QuantitativeValue или один Size). Нужно либо отдать массив, либо вынести в отдельные ProductGroup variants |
| `color` — то же самое | 🟡 | `color: "Чорний"` — нужно `color: "black"` или массив на ProductGroup |
| `weight` (типа `QuantitativeValue`) | 🟢 | если знаем |
| `pattern` | 🟢 | для streetwear-марки (printed/solid) — полезно |
| `productID` | 🟡 | Можно дублировать sku в стандартный productID |
| `nsn` / `productCode` | 🟢 | – |
| `keywords`, `awards` | 🟢 | – |
| `subjectOf` (ссылка на /novyny/ статью про конкретный дроп) | 🟠 | помогает связать продукт с контентом |
| `additionalType` (`https://schema.org/Clothing`) | 🟡 | – |
| `availableAtOrFrom` (точка выдачи / магазин) | 🟢 | – |
| `Offer.itemOffered` ref на Product через @id (если Offer вынесен) | 🟡 | – |
| `Offer.priceSpecification.eligibleQuantity`, `validFrom`, `validThrough` | 🟢 | – |
| `Offer.checkoutPageURLTemplate` | 🟢 | – |
| `MerchantReturnPolicy.refundType` (`https://schema.org/FullRefund`) | 🟠 | – |
| `MerchantReturnPolicy.applicableCountry` массивом или ref-ом на Country | 🟢 | – |
| `OfferShippingDetails.@id` (для повторного использования) | 🟡 | сейчас 3 OfferShippingDetails определяются inline 11 раз — лучше один раз в Organization → `shippingDetails[]` и потом ref-ом по @id |

**Дополнительные дефекты:**

- 🔴 `manufacturer` и `seller` дублируют Organization данными (`{type, name, url, address}`) вместо ссылки `{"@id": "https://twocomms.shop/#organization"}`.
- 🔴 `image` единственная на canonical-PDP (типа `c3.webp`) — для AI-поиска нужен **массив** ≥3 (front, back, detail). Только 2 PDP имеют image-array.
- 🟠 `availability=MadeToOrder` — это легитимно для производственного сценария, но AI-search может «не считать» товар в наличии. Если есть готовый сток — указывать `InStock`.
- 🟠 `priceValidUntil` фиксирован на `+90 дней`, но `dateModified` не синхронизирован — у `/product/classic-tshirt/` `dateModified=2026-05-15`, `priceValidUntil=2026-08-14`. Нужна автоматическая ротация или сделать без priceValidUntil (если цена «всегда актуальна»).

---

### 2.6 FAQPage (на 11 PDP, на pro-brand, cooperation, wholesale, custom-print, dopomoga, faq, delivery (broken), povernennya (broken))

**Есть:**
`@context, @type, mainEntity[Question(name, acceptedAnswer{Answer(text)})]`

**Дефекты:**

| Дефект | Где | Приоритет |
|---|---|---|
| 🔴 **Дубли вопросов**: 13 пунктов = 5 уникальных + 8 повторов | все 11 PDP/variants/locales | 🔴 |
| 🔴 На PDP RU/EN — **FAQ остался украинским**, при том что Product description перевёлся | pdp-ru, pdp-en | 🔴 |
| 🟠 У FAQPage нет `@id`, нет `inLanguage`, нет `isPartOf` ref-а на WebPage/Product | везде | 🟠 |
| 🟠 У `Question` нет `dateCreated`, `answerCount`, `upvoteCount` | везде | 🟢–🟠 |
| 🟠 У `Answer` нет `author` (ref на Organization #organization) | везде | 🟠 |
| 🟡 Часть вопросов лучше выносить в `QAPage` (сценарий «один вопрос — один URL») для long-tail | везде | 🟡 |
| 🟡 У FAQPage Google **deprecated rich result с May 2026** — для extractive citations (Perplexity/ChatGPT) FAQPage всё ещё работает, но FAQ ради звёздочки в SERP больше не имеет смысла | стратегия | 🟡 |

**Анализ 13/5 дублей** — на каждом PDP в FAQ-блок попадают вопросы:
1. «Чи доступна ця футболка без принту?» — 3 раза
2. «Як прати футболку, щоб принт не зіпсувався?» — 3 раза
3. «Як швидко доставимо футболку?» — 3 раза
4. «Чи можна замовити футболку зі своїм принтом?» — 3 раза
5. «Як обрати розмір футболки?» — 1 раз

Похоже, что они склеиваются из «общих» FAQ + «product-specific» FAQ (см. комментарий в `templates/pages/product_detail.html:103+`), и дедуп при склеивании отсутствует.

---

### 2.7 HowTo (на rozmirna-sitka, doglyad-za-odyagom)

**Есть:**
`@context, @type, name, description, totalTime (PT10M / PT20M), tool[HowToTool], supply[HowToSupply], step[HowToStep(position, name, text)]`

**Чего не хватает:**

| Поле | Приоритет |
|---|---|
| `@id` | 🟠 |
| `image` (для каждого step) | 🟠 |
| `video` для HowToStep | 🟡 |
| `estimatedCost` | 🟢 |
| `yield` | 🟢 |
| `isPartOf` → WebPage @id | 🟠 |

⚠️ Google **deprecated HowTo rich result** ещё в августе 2023 (как и FAQ). В SERP HowTo звёздочек больше нет, но AI-search их любит для extractive answers — оставлять имеет смысл.

---

### 2.8 OfferCatalog (только на /pro-brand/)

**Есть:**
`@context, @id (для родителя), @type, name, url, provider{ref}, itemListElement[OfferCatalog (без @id, без provider)]`

**Чего не хватает:**

| Поле | Приоритет |
|---|---|
| `@id` у дочерних OfferCatalog | 🟠 |
| `numberOfItems` | 🟡 |
| `inLanguage` | 🟡 |
| `itemListElement[].image` | 🟡 |
| Связь с CollectionPage категорий через `@id` ref-ом (вместо инлайна `url`) | 🟠 |

---

### 2.9 Person (founder, только на /pro-brand/)

**Есть:**
`@context, @id, @type, name (Bohdan), jobTitle, worksFor{ref}, url, image, description, knowsAbout[], nationality{Country}`

**Чего не хватает:**

| Поле | Приоритет |
|---|---|
| `sameAs` (Instagram/Twitter/LinkedIn основателя) | 🟠 |
| `birthDate` / `birthPlace` | 🟢 |
| `gender` | 🟢 |
| `alumniOf` | 🟢 |

⚠️ На остальных 30 страницах есть **только ref `{@id: #founder}` без определения узла**. Это синтаксически валидно, но в JSON-LD-парсинге без union-graph узел будет «висячим». На каждой странице, где появляется ref, узел Person тоже должен быть либо определён, либо граф должен быть собран в один блок с `@graph`.

---

### 2.10 ContactPoint (вложен в Organization, на 31 странице)

**Есть:**
`@type, telephone (+380966543212), contactType (customer support), availableLanguage[]`

**Чего не хватает:**

| Поле | Приоритет |
|---|---|
| `email` | 🟠 |
| `areaServed` (UA или массив) | 🟡 |
| `hoursAvailable` | 🟡 |
| Несколько ContactPoint (отдельный для wholesale, dropshipping, support) | 🟠 |

---

### 2.11 Service (только на /custom-print/)

**Есть:**
`@context, @type, name, provider{Organization(name,url)}, description, url, areaServed=UA, serviceType=DTF Printing`

**Чего не хватает:**

| Поле | Приоритет |
|---|---|
| `@id` | 🟠 |
| `provider` ref-ом по `@id` | 🟠 |
| `offers` (диапазон цен) | 🟠 |
| `serviceOutput` | 🟡 |
| `audience` | 🟡 |
| `hoursAvailable` | 🟢 |
| `availableChannel` (Telegram/email) | 🟡 |

---

### 2.12 ItemList (на home как mainEntity и в CollectionPage)

**Есть:**
`@type, itemListElement[ListItem(position, name, url)]` (на home — 3 категории; на cat-* — 16 ListItem из top-products)

**Чего не хватает:**

| Поле | Приоритет |
|---|---|
| `@id` | 🟠 |
| `numberOfItems` | 🟠 |
| `itemListOrder` (на home) | 🟡 |
| `ListItem.item` ref-ом на Product через `@id` (на cat-*) — сейчас `url` строкой, что менее графово | 🟠 |
| `ListItem.image` | 🟠 |
| `ListItem.offers.price` | 🟡 |

---

### 2.13 Brand (вложен в Product)

**Есть:**
`@type, name, url`

**Чего не хватает:**

| Поле | Приоритет |
|---|---|
| `@id` (или ref на Organization) | 🟠 |
| `logo` | 🟢 |
| `slogan` | 🟢 |

---

### 2.14 НЕ найдено вообще (хотя должны быть)

| Тип | Где должно быть | Приоритет |
|---|---|---|
| `ContactPage` | `/contacts/` (сейчас 500) | 🔴 |
| `LocalBusiness` или `ClothingStore` | Org-узел или отдельная сущность для физической точки | 🟠 |
| `MerchantReturnPolicy` (top-level в Organization) | теперь Google требует return policy в Organization уровне | 🔴 |
| `ProductGroup` | для variant-страниц | 🔴 |
| `Article` / `BlogPosting` / `NewsArticle` | `/novyny/` (сейчас broken и нет Blog) | 🟠 |
| `CollectionPage` для `/novyny/` (Blog) и для `/mapa-saytu/` | сейчас broken; нужна замена | 🟠 |
| `SiteNavigationElement` для `/mapa-saytu/` | sitemap-страница | 🟡 |
| `QAPage` | как альтернатива FAQPage для long-tail | 🟡 |
| `VideoObject` | если есть видео-материалы (custom-print, pro-brand) | 🟢 |
| `ImageGallery` / `ImageObject[]` | для PDP (3+ image) | 🟡 |
| `WebApplication` | конфигуратор кастомного принта | 🟢 |
| `AggregateOffer` | если в каталоге показываются разные цены | 🟢 |

---

## 3. Entity relationship graph

Текстовая диаграмма связей через `@id`. Стрелка `→` — это `{"property": {"@id": "..."}}` в исходном JSON-LD.

### Текущий граф (что есть)

```
                       ┌─────────────────────────────────┐
                       │ #organization (Organization)    │
                       │  + sameAs[2]                    │
                       │  + contactPoint                 │
                       │  + foundingLocation→Place→Addr  │
                       └────────────┬───────┬────────────┘
                                    │       │
                  founder           │       │ about (только на home, pro-brand)
                  ▼                 │       │
        ┌─────────────────┐         │       │
        │ #founder        │         │       ▼
        │ (Person)        │         │  ┌──────────────────────────┐
        │ только на       │         │  │ #webpage  (home)         │
        │ /pro-brand/     │         │  │ #about-page (pro-brand)  │
        └─────────────────┘         │  └────────────┬─────────────┘
                                    │               │ isPartOf
                                    ▼               ▼
                          ┌─────────────────────────────────┐
                          │ #website (WebSite)              │
                          │  + potentialAction (SearchAction)│
                          └─────────────────────────────────┘
                                    │
                                    │ (нет связи!)  ──╳──> CollectionPage / Product / WebPage других страниц
                                    ▼
                              ⛔ висячие узлы:
                              ─ Product (нет @id, не привязан)
                              ─ CollectionPage (нет @id, нет isPartOf)
                              ─ FAQPage (нет @id)
                              ─ BreadcrumbList на категориях (нет @id)
                              ─ Person ref-ы на 30 страницах без узла-определения
```

### Желаемый граф (рекомендация)

```
                                          #organization (Organization, ClothingStore)
                                         ┌─ sameAs[≥5]: IG, TG, FB, TikTok, X, ...
                                         ├─ founder → #founder (Person ✓ на каждой странице)
                                         ├─ brand → #brand (Brand)
                                         ├─ hasMerchantReturnPolicy → #return-policy (MerchantReturnPolicy)
                                         ├─ contactPoint[] → #cp-support, #cp-wholesale, #cp-custom
                                         └─ subOrganization (optional)

#website ────isPartOf─── #webpage / #collection-page / #product-page / #about-page / ...

#webpage(any) ───┬── breadcrumb → #breadcrumbs
                 ├── about → #organization
                 ├── isPartOf → #website
                 ├── primaryImageOfPage → #og-image
                 ├── mainEntity → (Product | ItemList | FAQPage | HowTo)
                 └── inLanguage / datePublished / dateModified

#product (canonical) ───┬── @id: /product/<slug>/#product
                        ├── isVariantOf → #productgroup-<slug>
                        ├── offers → #offer-<slug>-<variant>
                        ├── aggregateRating → #aggrating-<slug>
                        ├── review[] → #review-<id>
                        ├── manufacturer → #organization (ref)
                        └── brand → #brand

#productgroup-<slug> (ProductGroup) ─── hasVariant[] → variants
                                      ─ variesBy: ["color", "size", "fit"]
                                      ─ productGroupID: parent SKU
```

---

## 4. Errors found

### 4.1 Сломанный JSON-LD (parse errors)

**11 страниц** не парсят основной WebPage/CollectionPage блок из-за **Django `{# ... #}`-комментариев на двух строках** в `templates/pages/support_page.html` (строки 54–63 и 64–67):

```django
{# SEO v1.0 Phase 12 (2026-05-12) — finding (BBB). AboutPage and
   CollectionPage entries (e.g. /pro-brand/, /novyny/) were ... #}
```

Django однострочный комментарий `{# ... #}` **закрывается на конце строки**, а не на `#}`. Это значит, что строки 55–63 и 65–67 уезжают как обычный текст в HTML, разбивая JSON.

**Список страниц со сломанным JSON-LD:**

| Slug | URL | Какой блок ломается |
|---|---|---|
| delivery | `/delivery/` | block#3 (WebPage + BreadcrumbList) |
| doglyad-za-odyagom | `/doglyad-za-odyagom/` | block#3 (WebPage + BreadcrumbList; **HowTo block#2 валиден**) |
| dopomoga | `/dopomoga/` | block#3 (WebPage + BreadcrumbList) |
| faq | `/faq/` | block#3 (WebPage + BreadcrumbList) |
| mapa-saytu | `/mapa-saytu/` | block#2 (WebPage + BreadcrumbList) |
| novyny | `/novyny/` | block#2 (WebPage + BreadcrumbList) |
| povernennya | `/povernennya-ta-obmin/` | block#3 (WebPage + BreadcrumbList) |
| privacy | `/polityka-konfidentsiynosti/` | block#2 (WebPage + BreadcrumbList) |
| rozmirna-sitka | `/rozmirna-sitka/` | block#3 (WebPage + BreadcrumbList; HowTo валиден) |
| terms | `/umovy-vykorystannya/` | block#2 (WebPage + BreadcrumbList) |
| vidstezhennya | `/vidstezhennya-zamovlennya/` | block#2 (WebPage + BreadcrumbList) |

**Фикс:** заменить `{# ... #}` (многострочный) на `{% comment %} ... {% endcomment %}`.

### 4.2 Дублирующиеся блоки

| Что | Где | Описание |
|---|---|---|
| Organization | /pro-brand/ | два узла с одинаковым `@id`, но разным набором полей (block#0 — full, block#3 — стрипанный). При graph-merge это терпимо, но Google Rich Results может ругнуться |
| WebSite | /pro-brand/ | то же — два узла с одинаковым `@id` |
| FAQ Question (одинаковые `name`) | все PDP | 13 вопросов = 5 уникальных + 8 дубликатов внутри одного `mainEntity` |
| OfferShippingDetails (3 шт.) | все PDP | inline-объявление 3 политик доставки повторяется на каждом из 11 PDP/variants — лучше вынести в Organization+ref |
| WebPage.publisher → Organization (без @id) | wholesale, cooperation | дубль Organization вместо ref-а на `#organization` |
| Product.manufacturer / Product.offers.seller | все PDP | дубль Organization без @id-ссылки |
| Product schema на canonical и на /<color>/, /<fit>/ variant | все variant URL | идентичный контент, отличается только `url` |

### 4.3 Конфликты @type на @id

По данным `analyze.py` — конфликтов **не найдено** (один `@id` всегда имеет один тип). Это хорошая новость, но это потому что одинаковые `@id` ссылаются на одинаковые `@type` в всех местах.

### 4.4 Отсутствие @id там, где нужно

| Узел | Где | Что добавить |
|---|---|---|
| CollectionPage | catalog-root, cat-tshirts, cat-hoodie, cat-long-sleeve | `@id: <url>#collection-page` |
| Product | все PDP (включая variants и locales) | `@id: <url>#product` |
| FAQPage | все 11 страниц с FAQ | `@id: <url>#faq` |
| WebPage | cooperation, wholesale, custom-print (Service вместо WebPage) | `@id: <url>#webpage` |
| BreadcrumbList | catalog-* | `@id: <url>#breadcrumbs` |
| OfferCatalog (children) | /pro-brand/ | `@id: <url>#offer-catalog-tshirts` и т.д. |
| Service | /custom-print/ | `@id: <url>#service-dtf` |
| HowTo | /rozmirna-sitka/, /doglyad-za-odyagom/ | `@id: <url>#howto` |
| ListItem.item (cat-*) | cat-* в `mainEntity.itemListElement` | сейчас `url` строкой; добавить `@id` ref-ом на Product |

### 4.5 Прочие странности

- 🟠 На `/contacts/` — **HTTP 500** (`server: LiteSpeed`, `content-language` выставлен, но рендер падает). Полностью отсутствует ContactPage / LocalBusiness schema, при том что у бренда есть Харьков как место.
- 🟠 На `/mapa-saytu/` — нет `SiteNavigationElement` / `WebPage.mainEntity → ItemList` со списком всех URL (страница sitemap есть, schema нет).
- 🟠 На `/novyny/` — broken + нет `Blog` / `CollectionPage(itemList[BlogPosting])`.
- 🟠 На `/povernennya-ta-obmin/` — broken WebPage и **нет отдельного top-level `MerchantReturnPolicy`** (хотя бренду надо публиковать его как часть Organization).
- 🟠 `image` на canonical PDP — единичная (только 2 PDP имеют массив). 
- 🟢 На home `BreadcrumbList` содержит только 1 ListItem (Головна → сама себе) — формально валидно, но в Search Console часто помечается как «underdeveloped».

---

## 5. Variant page schema behavior

**Тест:** сравнили canonical PDP `/product/classic-tshirt/` и его варианты `/black/`, `/oversize/` (path-URL). Также `/product/my-little-baby/` и `/coyote/`.

| Поле | Canonical | Variant `/black/` | Variant `/oversize/` | Variant `/coyote/` (другое товар) |
|---|---|---|---|---|
| `<title>` | «Футболка класична — купити футболку TwoComms» | «Футболка класична — чорний — TwoComms» | «Футболка класична — оверсайз фіт — TwoComms» | «Футболка «My Little Baby» — кайот — TwoComms» |
| `og:title` | то же, что title | **меняется** | **меняется** | **меняется** |
| `og:url` | canonical-URL | variant-URL | variant-URL | variant-URL |
| `og:image` | `/media/products/c3.webp` | то же `c3.webp` | то же `c3.webp` | **меняется** на `/media/product_colors/10.4.webp` |
| `og:description` | базовое | переписан под цвет | переписан под fit | переписан под цвет |
| `<link rel=canonical>` | self | **self** (на variant URL) | **self** | **self** |
| **Product.name** в JSON-LD | «Футболка класична» | то же | то же | то же |
| **Product.url** в JSON-LD | canonical | variant URL | variant URL | variant URL |
| **Product.image** в JSON-LD | `c3.webp` | то же | то же | **меняется на `product_colors/10.4.webp`** |
| **Product.description** | full UA description | то же | то же | то же |
| **Product.color** | «Чорний» | «Чорний» | «Чорний» | «Чорний» (хотя URL = coyote) |
| **Product.size** | «S, M, L, XL, XXL» | то же | то же | то же |
| **Product.sku** | TC-1 | TC-1 | TC-1 | (то же что у canonical my-little-baby) |
| **Offer.price** | 788 | 788 | 788 | (то же) |
| **Offer.url** | canonical | variant URL | variant URL | variant URL |
| **isVariantOf / hasVariant** | ❌ | ❌ | ❌ | ❌ |
| **FAQPage** | full | то же | то же | то же |

**Выводы:**

1. 🔴 **OG-теги меняются, JSON-LD Product почти не меняется.** Это рассинхрон: AI-парсер видит «новую страницу с другим og:title и og:image, но тем же Product entity» — это либо дубль, либо непонятно, какой product canonical.
2. 🔴 **`<link rel=canonical>` на variant-странице указывает на саму себя** (а не на canonical PDP). Это значит, что Google индексирует все 118 variant URLs как полноценные страницы, и у них совпадает большая часть контента → **дубли в индексе**.
3. 🔴 **Нет `ProductGroup`** и связки через `hasVariant` / `isVariantOf` / `variesBy: ["color","size","fit"]`. Согласно [developers.google.com/search/docs/appearance/structured-data/product-variants](https://developers.google.com/search/docs/appearance/structured-data/product-variants), это рекомендуемый паттерн с 2023 года, и он напрямую влияет на показ карусели «варианты товара» в Google Shopping и AI-search.
4. 🟠 **`Product.color` не следует за URL**. На `/my-little-baby/coyote/` Product.color остаётся «Чорний» (видимо, default-вариант продукта), хотя URL и og — про cayote.
5. 🟠 **`Product.image` для variant `/black/` — тот же `c3.webp`**, что и canonical. То есть мы фактически не отдаём изображение конкретного цвета, хотя на variant `/coyote/` оно отдаётся (`product_colors/10.4.webp`). Несогласованно между продуктами.

**Рекомендация (минимум):**

- Все `/<slug>/<color>/<fit>/`-URL должны иметь `<link rel=canonical>` на canonical PDP. Это убирает дубли в индексе.
- Если нужны variant-страницы для AI-поиска — переходить на ProductGroup-модель: canonical PDP отдаёт `ProductGroup` + `hasVariant[Product]`; variant-страницы остаются как «views» с canonical на родителя, либо с собственным canonical — но тогда их Product **обязан** меняться полно (color, image, sku).

---

## 6. Best-practices gap по 2026

### 6.1 Google Rich Results requirements (актуально на 2026-05)

| Категория | Требование | Статус TwoComms |
|---|---|---|
| Product Snippets | image, name, offers, aggregateRating, review, brand | ⚠️ нет aggregateRating, review |
| Merchant Listings | + GTIN/MPN/brand, hasMerchantReturnPolicy, shippingDetails, priceValidUntil | ⚠️ нет gtin*, есть только mpn=sku (что Google **может** счесть валидным combo с brand+name, но риск) |
| Product Variants | ProductGroup + hasVariant + variesBy + productGroupID | 🔴 нет |
| Breadcrumbs | BreadcrumbList ≥2 элементов, valid `item` URL | ✅ ок |
| FAQ rich result | **Deprecated с May 2026** — больше не отображается в SERP | ⚠️ FAQ всё ещё в ld+json — оставить можно для AI-search, но не оптимизировать |
| HowTo rich result | **Deprecated с Aug 2023** | ⚠️ всё ещё в ld+json — можно оставить для AI |
| Sitelinks Search Box | WebSite + SearchAction | ✅ есть |
| Logo / Knowledge Panel | Organization + logo + sameAs | ⚠️ sameAs только 2 канала |
| Local Business / Address | LocalBusiness or Organization + address | ⚠️ есть address, нет LocalBusiness type |
| Article / News | Article + headline + datePublished + author | 🔴 `/novyny/` без structured |
| Video | VideoObject (если есть видео) | — |
| Q&A | QAPage (одно главное question per page) | — (могло бы быть на /faq/) |

### 6.2 Bing structured data (2026)

Bing использует JSON-LD аналогично Google + ещё активнее парсит `Organization` + `sameAs` (для построения knowledge graph через Wikidata). Поскольку Bing — основа Copilot/ChatGPT Search, упор на:

- 🔴 sameAs ≥5 (особенно с Wikidata / Crunchbase / OpenCorporates если бренд там есть)
- 🟠 LocalBusiness (Bing Places для физических точек)
- 🟠 Multiple ContactPoint (sales / support / press)

### 6.3 Что любят ChatGPT Search / Perplexity / Claude Search (extractive citations)

По состоянию на 2026 (Search Engine Journal, Perplexity dev docs, Pixelmojo / Geneo):

1. **Чёткие entity-узлы с @id** — AI-парсеры строят internal knowledge graph, где `@id` нужен для merge между страницами. Сейчас у нас нет `@id` на Product/CollectionPage/WebPage категорий — каждый PDP/категория «новая сущность» в их графе.
2. **Direct quotation-friendly answer text** — поэтому FAQPage всё ещё ценен (но **уникальные** Question/Answer без буквальных дублей). У нас 8/13 Question дублируются — это сильный анти-сигнал.
3. **Свежесть** — `dateModified` и `priceValidUntil` помогают AI оценить актуальность данных. У нас `dateModified` только на /pro-brand/.
4. **ProductGroup** для variant-моделей — напрямую цитируется в Google AI Overviews и Perplexity Shopping, чтобы ответить «какие цвета/размеры есть».
5. **Граф связан, а не разрознен** — желательно эмитить **один `@graph`-блок** на страницу со всеми сущностями + ref-ами, вместо 4–9 отдельных `<script>` (как сейчас на /pro-brand/ — 9 блоков).
6. **Speakable** для голосовых поисков (всё ещё работает в Bing/Alexa).
7. **Citation-friendly Author/Publisher** — `Article.author` + `Article.publisher` + `Article.datePublished` обязательно для `/novyny/`.
8. **Q&A long-tail** — лучше выносить хитовые вопросы в отдельный `QAPage` URL (один вопрос — один URL, mainEntity = Question), чем складывать всё в FAQPage.

---

## 7. Top 15 schema improvements (приоритизированно)

### 🔴 Critical (немедленно)

1. **Починить broken JSON-LD на 11 страницах.** Заменить `{# ... #}` (многострочный) на `{% comment %} ... {% endcomment %}` в `templates/pages/support_page.html` (строки 54 и 64). Срабатывает на: `/delivery/, /faq/, /dopomoga/, /povernennya-ta-obmin/, /rozmirna-sitka/, /doglyad-za-odyagom/, /vidstezhennya-zamovlennya/, /mapa-saytu/, /novyny/, /polityka-konfidentsiynosti/, /umovy-vykorystannya/`.
2. **Восстановить `/contacts/` (HTTP 500) + добавить ContactPage + LocalBusiness/ClothingStore.** Сейчас вся страница в ошибке 500, что критично и для UX, и для SEO.
3. **Implement ProductGroup для variant-URL.** Canonical PDP отдаёт `ProductGroup{@id, name, productGroupID, variesBy:["color","size","fit"], hasVariant[Product@id]}`. Variant-страницы либо: (а) делают `<link rel=canonical>` на родителя и уходят из индекса, (б) остаются с собственным `Product` + `isVariantOf{@id}` + полностью отличающимися полями (image/color/sku/price).
4. **Дедуп FAQ на PDP.** Удалять повторы по `Question.name` при склеивании общих + product-specific FAQ. Перевести FAQ на RU/EN PDP.
5. **Добавить `@id` всем главным узлам страниц.** CollectionPage, FAQPage, WebPage (категории/cooperation/wholesale), Product, OfferCatalog, Service, HowTo. Шаблон: `<canonical-url>#<type-suffix>` (`#product`, `#webpage`, `#faq`, `#breadcrumbs` и т.д.).

### 🟠 High (в течение 1–2 недель)

6. **Расширить sameAs Organization до ≥5 каналов.** Минимум: Instagram, Telegram, Facebook, TikTok, X/Twitter, YouTube/Threads, Wikidata-страница (если есть). Без этого нет шанса попасть в Knowledge Panel.
7. **Добавить `aggregateRating` + ≥3 `review` на каждый Product.** Даже если 5 отзывов — это >> 0 отзывов в SERP. Можно подсасывать из Google Reviews / Trustpilot / собственного UGC.
8. **Перевести `manufacturer` / `seller` / `publisher` Product на `{@id: #organization}` ref-ы** вместо inline-дублирования.
9. **Добавить `WebPage` узел на каждый PDP** (с `@id: <url>#webpage`, `mainEntity → Product (ref)`, `breadcrumb → BreadcrumbList (ref)`, `isPartOf → #website`, `about → #organization`, `primaryImageOfPage`, `dateModified`).
10. **Объединить все JSON-LD на странице в один `@graph`-блок** (вместо 4–9 отдельных `<script>`). AI-парсеры тогда будут видеть единый граф, а не несколько разрозненных deserializations.
11. **Добавить `inLanguage` per-locale на WebSite, WebPage, FAQPage, Product.** Сейчас inLanguage есть только на Product (на canonical+RU+EN), и эпизодически на WebPage.

### 🟡 Medium (1–2 месяца)

12. **Перевести `Product.size` и `Product.color` в нормализованные форматы.** `size: ["S","M","L","XL","XXL"]` (массив) или вообще убрать с canonical и положить в ProductGroup.variesBy + per-variant Product.size.
13. **Вытащить `OfferShippingDetails` и `MerchantReturnPolicy` в Organization уровень** (с `@id`), а в Offer ref-ом по `@id`. Снимет 3×11 дубликатов и упростит обновление политик.
14. **Добавить structured-data на `/novyny/` и каждый news/blog-пост: `Blog` + `BlogPosting` (`headline, datePublished, dateModified, author, publisher, image, articleBody`).** Без этого новостной раздел не существует для AI.
15. **Speakable + `dateModified` на всех WebPage-узлах** + `lastReviewed`/`reviewedBy` для legal-страниц (privacy, terms, povernennya-ta-obmin). Для AI это сигнал «страница свежая и проверена».

### 🟢 Low / nice-to-have

- Добавить `legalName`, `vatID`, `taxID`, `numberOfEmployees`, `slogan`, `knowsAbout` на Organization
- Добавить `SiteNavigationElement` на `/mapa-saytu/`
- Добавить `Service.offers` (диапазон цен) на `/custom-print/`
- Добавить `WebApplication` schema на конфигуратор кастомного принта
- Добавить `VideoObject` если есть промо-ролики
- Добавить `Person.sameAs` для founder
- Добавить `image` для каждого `HowToStep` (на rozmirna-sitka, doglyad-za-odyagom)
- Добавить `QAPage` для топ-3 long-tail вопросов с собственным URL

---

## Appendix A. Источники, использованные в аудите

- [Google: Intro to Product Structured Data](https://developers.google.com/search/docs/appearance/structured-data/product) (актуализовано 2025-12)
- [Google: Product Variant Structured Data (ProductGroup, Product)](https://developers.google.com/search/docs/appearance/structured-data/product-variants)
- [Google: Merchant Return Policy Structured Data](https://developers.google.com/search/docs/appearance/structured-data/return-policy)
- [Google: Merchant Shipping Policy Structured Data](https://developers.google.com/search/docs/appearance/structured-data/shipping-policy)
- [Google: Mark Up FAQs with Structured Data — deprecation banner from May 2026](https://developers.google.com/search/docs/appearance/structured-data/faqpage)
- [Google: Changes to HowTo and FAQ rich results (2023)](https://developers.google.com/search/blog/2023/08/howto-faq-changes)
- [Google: Schema for Q&A Pages (QAPage)](https://developers.google.com/search/docs/appearance/structured-data/qapage)
- [Schema.org — ProductGroup, isVariantOf, hasVariant](https://schema.org/ProductGroup)
- [Search Engine Journal — Google Drops FAQ Rich Results From Search (May 2026)](https://www.searchenginejournal.com/google-drops-faq-rich-results-from-search/574429/)
- [Search Engine Journal — SERP FAQ Removal & New Data Challenge Schema's AI Search Value](https://www.searchenginejournal.com/serp-faq-removal-new-data-challenge-schemas-ai-search-value/574993/)
- [Stackmatix — Schema Markup Guide (2026)](https://www.stackmatix.com/blog/structured-data-ai-search)
- [Pixelmojo Labs — How to Get Cited by ChatGPT, Perplexity, and Claude](https://labs.pixelmojo.io/blogs/how-to-get-cited-by-chatgpt-perplexity-claude)
- [Geneo — Best Practices for Answer Engine Optimization (AEO) in 2025](https://geneo.app/blog/best-practices-answer-engine-optimization-aeo-2025/)

> Контент с внешних источников был переформулирован для соответствия лицензионным требованиям; цитат >30 слов не использовалось.

---

## Appendix B. Артефакты аудита

В `/tmp/seo_audit/schema/`:

- `raw/<slug>.html` (32 файла) — полный HTML-снимок каждой страницы
- `parsed/<slug>.json` (32 файла) — массив `{index, raw, parsed, parse_error}` для каждого `<script type="application/ld+json">`
- `summary.json` — глобальная сводка `{slug, url, types[], ids[], blocks_count, errors[]}`

Скрипты в `audit/_tools/`:
- `fetch_and_parse.py` — fetcher (не модифицирует сайт)
- `analyze.py` — матрица типов, конфликты @id, дубли FAQ
- `og_check.py` — проверка OG-meta на variant pages

Запуск (для воспроизводимости):

```bash
python3 .kiro/specs/seo-molecular-upgrade/audit/_tools/fetch_and_parse.py
python3 .kiro/specs/seo-molecular-upgrade/audit/_tools/analyze.py
python3 .kiro/specs/seo-molecular-upgrade/audit/_tools/og_check.py
```
