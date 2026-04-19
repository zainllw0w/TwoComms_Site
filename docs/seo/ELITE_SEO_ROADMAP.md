# ELITE SEO Roadmap для основного домена TwoComms

> Актуально на 2026-04-19.
> Область аудита: только основной домен `https://twocomms.shop`, без `dtf.*`, без внутренних management/admin-сценариев, кроме тех мест, где они влияют на публичный SEO-слой.

## 0. Контрольный блок

### Статус текущей ревизии

- [x] Проверен live-домен: `robots.txt`, `sitemap.xml`, главная, каталог, категория, товар, FAQ, поиск, B2B-страницы.
- [x] Проверены ключевые файлы кода: `base.html`, `catalog.html`, `product_detail.html`, `seo_utils.py`, `seo_tags.py`, `views/static_pages.py`, `views/catalog.py`, `storefront/urls.py`.
- [x] Сверены актуальные рекомендации по Django sitemap через Context7.
- [x] Сверены актуальные рекомендации по Schema.org через Context7.
- [x] Сверены актуальные рекомендации Google Search Central по Product/merchant listings, faceted navigation, title/snippets, image SEO.
- [x] Внешний трекер в Linear создан и синхронизирован.
  Master-checklist: [TwoComms SEO Deep Audit Master Checklist — 2026-04-19](https://linear.app/twocomms/document/twocomms-seo-deep-audit-master-checklist-2026-04-19-53c84a8811f3).

### Краткий вывод без иллюзий

После повторной сверки implementation plan, кода, live-домена и Bing/IndexNow слой технического SEO на основном домене уже не выглядит как `6.8/10`.

Более честная оценка на 2026-04-19:

- `8.1/10` по техническому SEO-фундаменту;
- `6.8/10` по контентному и semantic-cluster слою;
- `4.5/10` по authority/off-page и AI-brand visibility слою.

Ключевой вывод:

- большая часть самых токсичных технических проблем уже закрыта в коде и в live;
- часть roadmap устарела и больше не может считаться source-of-truth без переписывания верхних разделов;
- у сайта уже есть нормальный crawl/index foundation, но еще не дожаты category silos, apparel variant schema, trust/review layer, B2B semantic map и AI-facing brand assets;
- часть последних шаблонных и meta-фиксов уже внесена в репозиторий, но для live-подтверждения еще нужен деплой.

## 1. Что было проверено

### Live URLs

- `https://twocomms.shop/`
- `https://twocomms.shop/catalog/`
- `https://twocomms.shop/catalog/hoodie/`
- `https://twocomms.shop/catalog/hoodie/?page=2`
- `https://twocomms.shop/product/clasic-tshort/`
- `https://twocomms.shop/faq/`
- `https://twocomms.shop/search/?q=hoodie`
- `https://twocomms.shop/wholesale/`
- `https://twocomms.shop/pricelist/`
- `https://twocomms.shop/custom-print/`
- `https://twocomms.shop/delivery/`
- `https://twocomms.shop/about/`
- `https://twocomms.shop/contacts/`
- `https://twocomms.shop/povernennya-ta-obmin/`
- `https://twocomms.shop/polityka-konfidentsiynosti/`
- `https://twocomms.shop/umovy-vykorystannya/`
- `https://twocomms.shop/robots.txt`
- `https://twocomms.shop/sitemap.xml`

### Проверенные файлы

- `twocomms/twocomms/urls.py`
- `twocomms/storefront/urls.py`
- `twocomms/storefront/views/static_pages.py`
- `twocomms/storefront/views/catalog.py`
- `twocomms/storefront/views/product.py`
- `twocomms/storefront/sitemaps.py`
- `twocomms/storefront/seo_utils.py`
- `twocomms/storefront/templatetags/seo_tags.py`
- `twocomms/storefront/templatetags/seo_alt_tags.py`
- `twocomms/storefront/models.py`
- `twocomms/twocomms_django_theme/templates/base.html`
- `twocomms/twocomms_django_theme/templates/pages/index.html`
- `twocomms/twocomms_django_theme/templates/pages/catalog.html`
- `twocomms/twocomms_django_theme/templates/pages/product_detail.html`
- `twocomms/twocomms_django_theme/templates/pages/support_page.html`
- `twocomms/twocomms_django_theme/templates/partials/header.html`
- `twocomms/twocomms_django_theme/templates/partials/footer.html`

## 2. Сверка roadmap с реализацией

Ниже не гипотезы, а фактический статус после перепроверки implementation plan, screenshot checklist, кода и live.

### 2.1. Уже реально закрыто в коде и подтверждено live

- `sitemap.xml` уже обслуживается через Django sitemap framework, а не через старый кастомный `static_sitemap`.
- `search` уже исключен из sitemap и переведен в `noindex, follow`.
- у `sitemap.xml` уже есть честный `lastmod` для `Product` и `Category`.
- `Product` и `Category` уже имеют `created_at` / `updated_at`.
- `priceValidUntil` уже генерируется динамически.
- active product template уже рендерит один `Product` JSON-LD без synthetic `AggregateRating` и fake `review`.
- `product.seo_schema` уже мержится как override поверх generated schema.
- OG/Twitter image для product/category уже собираются как absolute URL.
- `catalog` и category pagination уже имеют self-canonical и `prev/next`.
- `category.description` уже возвращается полноценным нижним SEO-блоком.
- `wholesale/` уже включен в sitemap.
- `/opt/` уже отдает `301` на `/wholesale/`.
- `robots.txt` уже блокирует `search`, `api`, `debug`, `dev`, `admin-panel`, явно допускает `OAI-SearchBot`, `ChatGPT-User`, `Claude-SearchBot`, `Claude-User`, `PerplexityBot`, `Perplexity-User`, держит закрытыми `GPTBot`, `ClaudeBot`, `CCBot`, и явно открывает `Google-Extended` для Gemini grounding / AI-visibility use case.
- `hreflang="uk"` уже присутствует в `base.html`.
- `custom-print/` уже имеет page-level `Service` schema и отдельные meta/OG/Twitter overrides.

### 2.2. Уже исправлено в репозитории, но еще требует live-деплоя и повторной проверки

- убран literal template leakage на товарных страницах:
  - multiline `{% optimized_image %}` переведен в безопасный single-line вызов;
  - многострочные `{# ... #}` в `base.html` и `index.html` переведены в `{% comment %}`.
- `order_success` переведен в `noindex, nofollow`.
- `about`, `contacts`, `delivery` и `cooperation` получили page-specific social meta там, где еще оставались generic fallback.
- `product_detail_new.html` приведен к одному `Product` JSON-LD, чтобы не хранить stale-duplicate даже в неактивном шаблоне.
- `data-offer-id-map` на товаре больше не должен ломать HTML сырым JSON в атрибуте.
- category pages получили visible breadcrumbs через `partials/breadcrumbs.html`.
- главный header CTA переведен с `add-print/` на `custom-print/`, чтобы sitewide-вес шел в money-page configurator, а не во вторичную UGC-страницу.
- `add-print/` переведен в secondary UGC-сценарий с `noindex, follow` и более точным meta/social copy.
- `custom-print/` получил visible breadcrumbs, FAQ layer, `FAQPage` schema и дополнительную internal-link секцию на `delivery`, `wholesale` и `contacts`.
- `wholesale/` получил собственные breadcrumbs, visible FAQ layer и B2B-support links вместо “только schema без visible answers”.
- `cooperation/` доведен до page-specific SEO-слоя: meta/OG/Twitter, breadcrumbs, FAQ schema и visible FAQ block.
- `pricelist/` больше не считается самостоятельной landing page в репозитории: URL переведен в `301` на `wholesale/`.
- `wholesale/order-form/` и `test-analytics/` закрыты как utility URLs через `noindex, follow`.

### 2.3. Частично реализовано, но еще не доведено до целевого уровня

- `add-print/` уже переведен в правильный secondary role в репозитории, но live еще нужно подтвердить после деплоя.
- page-specific SEO для support cluster уже заметно лучше, но `faq` / legal / utility pages еще стоит проверить на полную консистентность соцсниппетов и intent mapping.
- `custom-print/` уже перестал быть “пустым SEO-URL” и получил FAQ/internal-link layer, но еще не доведен до полноценного money-page уровня по proof blocks, кейсам, срокам, материалам и full semantic cluster coverage.
- B2B слой уже заметно лучше, но после деплоя нужно live-подтвердить:
  - `301` `pricelist/ -> wholesale/`;
  - `noindex` на utility URLs;
  - что `wholesale/` и `cooperation/` реально отдают обновленный SEO-layer на проде.

## 3. Текущая оценка по слоям

| Слой | Оценка | Комментарий |
|---|---:|---|
| Crawl / index management | 8.5/10 | sitemap, `lastmod`, search noindex и `/opt/` normalization уже на месте; остались точечные utility/privacy cases |
| Snippets / CTR | 7.3/10 | product/category/meta уже сильнее, но не все support/B2B pages раскрыты одинаково хорошо |
| Structured data | 7.8/10 | больше нет synthetic rating/review на active product path; дальше нужен variant-aware apparel graph |
| Category SEO | 7.6/10 | canonical, full text и visible breadcrumbs уже выровнены; дальше нужны FAQ и silo expansion |
| Product SEO | 7.9/10 | strong base уже есть, но schema все еще partly hardcoded и нет real reviews / ProductGroup |
| Internal linking | 7.2/10 | support/footer хороши, но B2B/custom-print/category silos можно усилить кратно |
| Image SEO | 6.5/10 | alt layer и product imagery есть, но image sitemap и variant-aware image strategy еще не сделаны |
| Authority / growth / AI mentions | 4.8/10 | техоснова есть, но brand-entity, off-page, citations, UGC, editorial и LLM-facing assets еще слабые |

## 4. Подтвержденные оставшиеся проблемы

### P0. Live товарные страницы до деплоя все еще отдают template noise

Подтверждение до локального фикса:

- live product HTML все еще содержал literal `{% optimized_image ... %}`;
- live product HTML все еще содержал `{# ... #}` из многострочных template-комментариев;
- это уже просачивалось в text layer, который видят поисковики и AI systems.

Статус:

- в репозитории исправлено;
- на live нужно повторно проверить после деплоя:
  - source HTML товара;
  - URL Inspection;
  - snippets по `site:twocomms.shop`.

### P0. `order_success` был публичным indexable receipt page с PII

Подтверждение:

- `orders/success/<id>/` рендерил `index, follow`;
- страница выводит номер заказа, имя, телефон, город, отделение и состав заказа;
- это utility/receipt URL, а не landing page.

Статус:

- в репозитории переведен в `noindex, nofollow`;
- после деплоя проверить source HTML и response headers на реальном URL.

### P1. `add-print/` и `custom-print/` уже разведены в repo, но live еще надо подтвердить

Подтверждение:

- `https://twocomms.shop/add-print/` был публичной indexable-страницей;
- смысл страницы пересекается с custom order / print-intent, но коммерческий приоритет у бизнеса сейчас выше у `custom-print/`;
- до последнего repo-фикса самый сильный sitewide CTA вел именно на `add-print/`, что усиливало не ту страницу.

Почему это важно:

- возникает каннибализация между UGC / suggestion flow и реальной money-page configurator page;
- link equity и коммерческий intent распределяются не так точно, как нужно для роста `custom-print/`.

Статус:

- в репозитории strongest header CTA уже переведен на `custom-print/`;
- в репозитории `add-print/` уже переведен в `noindex, follow`;
- после деплоя нужно проверить, что live действительно перестал индексировать эту страницу и что canonical/social meta не конфликтуют с новым secondary role.

### P1. Structured data для одежды все еще недожата до variant-aware уровня

Подтверждение:

- active product path уже чистый;
- но schema все еще partly опирается на hardcoded/fallback values:
  - `Матеріал`
  - `Розміри`
  - часть apparel properties
- нет `ProductGroup` / `hasVariant` / `variesBy` / `productGroupID`.

Почему это важно:

- для apparel/e-commerce это следующий слой качества;
- именно он поможет лучше связать color/size/variant logic, Merchant listings и AI retrieval.

### P1. `pricelist/` больше не должен жить как отдельная SEO-посадочная

Подтверждение:

- самостоятельный `pricelist/` создавал duplicate / canonical drift риск относительно `wholesale/`;
- в репозитории URL уже переведен в `301` на `wholesale/`;
- значение этого URL теперь purely utility / legacy-entry, а не отдельный organic target.

Что нужно решить:

- после деплоя подтвердить redirect live и убрать `pricelist/` из любых внутренних стратегических списков;
- основной B2B-вес и перелинковку держать на `wholesale/`.

### P1. Legacy SEO helpers еще не полностью вычищены из codebase

Подтверждение:

- `google_merchant_schema` helper и legacy `product_rating_schema` еще существуют как старый API-слой;
- active path уже не зависит от них, но сам код все еще можно дочистить.

Почему это важно:

- это снижает точность roadmap и повышает риск regressions при будущих правках.

## 5. Аудит по типам страниц

## 5.1. Главная

### Текущее состояние

- canonical, базовые meta и internal linking уже в хорошем состоянии;
- home уже не требует emergency-fix уровня;
- главный пробел сейчас не технический, а semantic:
  - главная еще не является полноценным hub для category intent;
  - мало явных seasonal / style / B2B / custom-print entry points;
  - блок “часто ищут / подборки / сценарии выбора” можно усилить.

### Текущий приоритет

- `P1`: улучшать как semantic hub, а не чинить как broken SEO page.

## 5.2. Каталог root и категории

### Что уже хорошо

- self-canonical для пагинации уже реализован;
- `prev/next` уже отдается;
- full category description block уже есть;
- root/category OG/Twitter overrides уже реализованы.
- visible breadcrumbs уже добавлены в репозитории.

### Что осталось

- FAQ/intents layer;
- более сильный top intro для root catalog;
- mini-silo logic по модификаторам, стилю, теме принта, материалу, сценарию использования.

### Текущий приоритет

- `P1`: category cluster expansion.

## 5.3. Товары

### Что уже хорошо

- один active `Product` JSON-LD graph;
- dynamic `priceValidUntil`;
- `product.seo_schema` override merge;
- absolute social image URLs;
- breadcrumb schema;
- recommendation block;
- контентная база уже не токсична на уровне schema.

### Что осталось

- variant-aware apparel schema;
- честный review layer;
- более точные product attributes из данных;
- product support links возле CTA:
  - размеры
  - доставка
  - возврат
  - уход
- deploy текущего template cleanup.

### Текущий приоритет

- `P1`, а для `ProductGroup/hasVariant` — `P2`.

## 5.4. Search pages

### Текущее состояние

- search уже `noindex, follow`;
- search уже вне sitemap;
- current implementation больше не выглядит как emergency crawl-budget leak.

### Что дальше

- не превращать query-driven search в pseudo-landing pages;
- если понадобится indexable search-hub, делать отдельную страницу без query-параметров.

## 5.5. Support / FAQ / legal / service pages

### Что уже хорошо

- support cluster силен по trust-layer и внутренним ссылкам;
- часть страниц уже имеет strong title/description/schema;
- `custom-print/` уже вышел за пределы generic utility page.

### Что осталось

- довести meta-consistency на всех utility/legal/support URL;
- сильнее связать support pages между собой по query clusters;
- добавить more explicit answer-hub logic:
  - размер
  - уход
  - доставка
  - возврат
  - tracking
  - FAQ

### Текущий приоритет

- `P1`.

## 5.6. B2B / wholesale / pricelist / cooperation

### Что уже хорошо

- `wholesale/` уже в sitemap;
- `/opt/` уже нормализован через `301`;
- B2B hub перестал быть canonical mess;
- `wholesale/` уже можно считать main B2B URL.
- `cooperation/` уже перестал быть SEO-neglected page и получил полноценный page-level SEO layer.
- `pricelist/` в репозитории уже переведен в `301` на `wholesale/`, то есть duplicate-role для индекса больше не нужен.

### Что осталось

- сильнее долинковать B2B кластер с главной и support layer;
- live-подтвердить redirect и убрать остаточный акцент на `pricelist/` в аналитике/чеклистах;
- расширить B2B semantic core:
  - опт одягу
  - дропшипінг одягу
  - мерч для команд
  - кастомний принт оптом

### Текущий приоритет

- `P1` для semantic map, `P2` для content expansion.

## 5.7. Custom print на основном домене

### Что уже хорошо

- уникальные meta уже есть;
- `Service` schema уже есть;
- страница уже релевантна под custom-print intent;
- это один из главных organic growth assets бренда.

### Что осталось

- guide / use-cases / proof layer;
- более сильная перелинковка из home, category и B2B страниц;
- semantic expansion под:
  - свій принт
  - кастомний одяг
  - друк на худі
  - друк на футболках
  - мерч для бренду / команди / івенту
- event instrumentation для organic-to-lead tracking.

### Текущий приоритет

- `P1` с коммерческим приоритетом выше большинства support pages.
- page-level structured data:
  - `WebPage` / `Service`-style entity для самого configurator intent;
  - `BreadcrumbList`;
  - `FAQPage` только для реальных вопросов;
  - отдельный HowTo/guide-блок на visible page, если делаем реальную пошаговую инструкцию;
- отдельный semantic cluster под:
  - кастомний принт на футболках
  - принт на худі під замовлення
  - друк для брендів / команд / подій
  - мерч на замовлення в Україні
- добавить FAQ, кейсы, материалы, сроки, типовые объёмы, файлы/требования, ссылки на B2B;
- не откатывать header CTA обратно на `add-print`: в репозитории он уже переведен на `custom-print`, и после деплоя это нужно сохранить как новый baseline;
- развести intent:
  - `custom-print/` = коммерческая страница “сделать одежду/мерч со своим принтом”;
  - `add-print/` = UGC / community / reward page “предложить идею принта”.

## 6. Что нужно сделать в первую очередь

## P0. Следующий production-спринт

### 6.1. Выкатить и live-подтвердить уже готовые repo-фиксы

- задеплоить последние шаблонные и meta-изменения:
  - cleanup товарного HTML;
  - `order_success -> noindex, nofollow`;
  - page-specific social meta;
  - visible breadcrumbs на категориях;
  - header CTA -> `custom-print/`;
  - `add-print -> noindex, follow`;
  - `custom-print` FAQ/breadcrumb/internal-link layer;
- после выката вручную проверить:
  - source HTML товара;
  - source HTML category page;
  - source HTML `order_success` на реальном URL;
  - source HTML `add-print/` и `custom-print/`;
  - `site:twocomms.shop` snippets по товару и `custom-print/`.

### 6.2. Добить snippet hygiene после деплоя

- подтвердить, что в live больше нет:
  - literal `{% ... %}`;
  - `{# ... #}`;
  - поломанного `data-offer-id-map`;
  - generic OG/Twitter там, где уже подготовлены page-level overrides.
- отдельно прогнать `URL Inspection` и `Rich Results Test` по:
  - одному товару;
  - одной категории;
  - `custom-print/`;
  - `wholesale/`.

### 6.3. Финально развести `custom-print/` и `add-print/`

- зафиксировать стратегию:
  - `custom-print/` = основная коммерческая configurator / custom-orders page;
  - `add-print/` = secondary UGC / reward / suggestion page;
- не откатывать `add-print/` обратно в indexable state без отдельного SEO-решения;
- если когда-то вернуть его в индекс, переписать title/description/OG и page copy так, чтобы intent не дублировал `custom-print/`.

### 6.4. Довести `custom-print/` до уровня money-page, а не просто “интересной страницы”

- добавить real FAQ layer;
- добавить materials / сроки / минимальные тиражи / требования к файлам;
- добавить кейсы, social proof, links на `delivery/`, `contacts/`, `wholesale/`;
- настроить нормальный event layer для organic-to-lead tracking.

### 6.5. Product / apparel schema phase 2

- подготовить `ProductGroup` / `hasVariant` / `variesBy`;
- убрать hardcoded apparel-fallbacks там, где можно брать реальные данные;
- довести merchant/product attributes до data-driven состояния.

### 6.6. B2B cluster cleanup

- зафиксировать `pricelist/` как legacy utility URL с `301` на `wholesale/`;
- проверить после деплоя, что внутренние ссылки и внешние submit flows больше не пытаются качать `pricelist/` как отдельный search target;
- усилить `wholesale/` внутренними ссылками, proof-блоками и отдельным semantic layer под опт / мерч / команды.

### 6.7. Authority / AI-facing growth layer

- усилить brand-entity слой:
  - consistent mentions;
  - каталоги/профили/marketplaces;
  - editorial mentions;
  - UGC/reviews;
- создать страницы и блоки, которые легче цитируются AI systems:
  - custom-print FAQ;
  - brand/about proof;
  - wholesale capabilities;
  - turnaround / materials / printing requirements.

### 6.8. Bing / IndexNow enablement

- после следующего деплоя проверить live:
  - `https://twocomms.shop/{INDEXNOW_KEY}.txt`
  - `Bing Webmaster Tools -> Recommendations`
  - `Bing Webmaster Tools -> Sitemaps / URL Inspection`;
- использовать `submit_indexnow_urls` только для реально измененных URL, а не как re-submit всего сайта.

Статус на `2026-04-19`:

- production env для `IndexNow` уже задан и подтвержден в live `lswsgi`-процессе;
- `https://twocomms.shop/{INDEXNOW_KEY}.txt` уже отдает корректный key-file;
- первый live-submit уже был выполнен на старом core-set, а после вывода `pricelist/` из стратегических URL dry-run core-набора теперь собирает `18` URL основного домена;
- `Bing Webmaster Tools` может снимать `High severity` не мгновенно, а с лагом после первого успешного submit.

## P1. Сразу после P0

- page-specific OG/Twitter для всех публичных main-domain страниц;
- честная схема merchant/product attributes;
- FAQ на категориях и custom-print;
- image SEO upgrade;
- internal links между product -> support -> category -> B2B;
- выделение B2B-кластера.

## P2. Growth layer

- tag/collection landing pages;
- style guide / lookbook / editorial pages;
- UGC/reviews;
- creator/collab pages;
- editorial seasonal collections.

## 7. Семантическое ядро: как довести до уровня сильного одежного e-commerce

Не нужен безумный список из тысяч мусорных ключей. Нужна нормальная кластеризация по намерению.

### 7.1. Коммерческое ядро

- купить худи
- купить футболку
- купить лонгслив
- streetwear одежда Украина
- military clothing Ukraine / мілітарі одяг купити
- футболка с принтом купить
- худи оверсайз купить
- базова футболка купити
- чоловіче худі купити
- жіноча футболка купити

### 7.2. Модификаторы для коллекций

- по категории:
  - футболки
  - худі
  - лонгсліви
- по цвету:
  - чорні
  - білі
  - зелені
  - сірі
- по посадке:
  - оверсайз
  - класичні
  - relaxed fit
- по назначению:
  - на подарок
  - на каждый день
  - для команди
  - для мерчу
- по теме:
  - патріотичні
  - військова естетика
  - dark streetwear
  - принтовані

### 7.3. Информационное ядро

- как выбрать размер худи
- как стирать футболку с принтом
- чем отличается лонгслив от свитшота
- как носить streetwear
- как подобрать oversize hoodie
- как ухаживать за принтом
- какой материал лучше для футболки

### 7.4. B2B ядро

- оптовий одяг Україна
- дропшипінг одягу Україна
- друк на худі оптом
- мерч для бренду на замовлення
- футболки для команди оптом
- кастомний мерч для події

### 7.5. Что делать practically

- собрать master keyword map по кластерам, а не по страницам;
- у каждой indexable страницы должен быть свой primary intent;
- нельзя, чтобы `/search/`, `/catalog/`, `/catalog/hoodie/` и случайная tag page били в один и тот же кластер без разграничения.

## 8. Архитектура перелинковки

## 8.1. Базовый принцип

Перелинковка должна поддерживать 4 слоя:

- home hub
- category hub
- product pages
- support/B2B/editorial clusters

## 8.2. Что добавить

- на category pages:
  - related categories;
  - popular searches;
  - FAQ links;
  - support links;
- на product pages:
  - links в `size guide`, `delivery`, `returns`, `care guide`;
  - links в родительскую категорию и соседние подборки;
  - links на cluster pages по теме/цвету/посадке;
- на support pages:
  - links обратно в каталог и релевантные категории;
- на B2B pages:
  - links на custom print, wholesale, cooperation, contacts;
- на главной:
  - отдельный блок под B2B/кастом/опт/мерч.

## 8.3. Анкорная стратегия

Не делать анкор-лист помойкой.

Нужно:

- естественные анкорные комбинации;
- частичное разнообразие;
- привязка к intent, а не к тупому exact-match повторению.

Примеры хороших анкоров:

- `худі оверсайз`
- `футболки з принтом`
- `таблиця розмірів`
- `доставка та оплата`
- `кастомний принт`
- `оптові закупівлі`

## 9. Контентные стандарты по типам страниц

Google сам пишет, что нет «секретов», которые автоматически поднимут сайт на первое место. Значит фокус не на magic tricks, а на page quality, crawl clarity и entity consistency.

### 9.1. Category pages

Рекомендуемая структура:

- 1 сильный H1;
- 80-140 слов интро над товарной сеткой;
- 300-700 слов полезного блока внизу;
- 3-6 FAQ, если реально есть повторяющиеся вопросы;
- 5-10 внутренних ссылок, но только релевантных;
- никакой воды ради объема.

### 9.2. Product pages

Рекомендуемая структура:

- короткий коммерческий summary;
- 150-350 слов уникального описания;
- материал / состав / посадка / сезонность / уход;
- размеры и fit-советы;
- доставка / возврат / сроки;
- related items;
- если есть реальные отзывы, выводить их и на странице, и в schema.

### 9.3. Support / FAQ

- 700-1500 слов на страницу при реальной смысловой нагрузке;
- структурировать по реальным сценариям;
- использовать FAQ schema только там, где есть настоящие вопрос-ответ блоки.

### 9.4. B2B pages

- четкий коммерческий оффер;
- min order / сроки / материалы / процесс;
- примеры кейсов;
- FAQ;
- CTA;
- trust markers.

## 10. Structured data blueprint для одежды

## 10.1. Что оставить

- `Organization` на уровне сайта;
- `BreadcrumbList` на категориях и товарах;
- `FAQPage` только на реальных FAQ;
- `CollectionPage` / `ItemList` на листингах.

## 10.2. Что уже убрано и нельзя возвращать

- synthetic `AggregateRating`;
- synthetic `Review`;
- просроченный `priceValidUntil`.

## 10.3. Что добавить

- `ProductGroup` для вариантов одежды;
- `hasVariant`, `variesBy`, `productGroupID`;
- реальные `material`, `pattern`, `size`, `color`;
- точные `Offer.url` для выбранного варианта;
- merchant listing policy на основе реальных условий доставки/возврата.

## 10.4. Главное правило

Schema не должна «фантазировать».

Если данных нет в базе и на странице, лучше не выводить property, чем выводить красивую ложь.

## 11. Image SEO

Согласно Google, важен не только `alt`, но и сама image landing page, title/description страницы, structured data и контекст вокруг изображения.

### Что уже есть

- инфраструктура для alt text в коде есть;
- изображения в целом подаются нормально.

### Чего не хватает

- нет image sitemap;
- alt-стратегия не завязана на реальный variant context;
- product image landing pages не усиливаются текстовым контекстом;
- нет политики для названий файлов и variant-specific image labeling.

### Что делать

- добавить image sitemap или расширение image entries в основной sitemap;
- делать variant-aware alt:
  - тип товара
  - цвет
  - ракурс
  - коллекция/принт
- улучшить filename conventions;
- добавить подписи/контекст вокруг изображений там, где это оправдано;
- использовать absolute URLs в social image tags.

## 12. Что не является «секретом» и не должно пожирать время

### Не переоценивать

- `meta keywords`
- тупой рост объема текста без intent
- exact-match keyword stuffing
- механическое добавление `rel=prev/next` как якобы главного SEO-рычага
- фиктивные отзывы и рейтинги

### Почему

- Google прямо указывает, что `meta keywords` не использует;
- keyword stuffing противоречит нормальной SEO-практике;
- настоящее качество страницы важнее декоративных трюков.

## 13. Большой список идей для роста органики

## 13.1. Контент и посадочные

- сделать коллекции по intent:
  - black hoodies
  - oversized hoodies
  - graphic t-shirts
  - military-inspired apparel
  - gift ideas
  - made in Ukraine
- сделать style guide / lookbook;
- сделать cluster pages по уходу, размерам, подбору посадки;
- сделать тематические страницы под самые сильные принты/дропы;
- делать editorial pages под сезон:
  - весенние худи
  - летние футболки
  - осенние лонгсливы

## 13.2. Коммерческий траст

- реальные отзывы с фото;
- FAQ по доставке/возврату/размерам;
- user-generated looks;
- витрина bestsellers / new arrivals / limited drops;
- история бренда, производства, материалов, качества.

## 13.3. B2B и мерч

- отдельный organic кластер:
  - wholesale
  - dropshipping
  - merch for brands
  - custom print
  - team apparel
- кейсы и лендинги по типам клиентов.

## 13.4. Off-page и digital PR

- collab pages с артистами / командами / микроинфлюенсерами;
- публикации на локальных fashion/streetwear ресурсах;
- брендовые упоминания и интервью;
- Pinterest / visual search strategy;
- digital lookbook для естественных ссылок.

## 13.5. Search demand capture

- релизные страницы под новые drops;
- evergreen pages под базовый спрос;
- news pages связывать с товарами;
- support pages связывать с коммерческими страницами.

## 14. Метрики, по которым нужно судить успех

Не смотреть только на позиции.

### Основные KPI

- coverage / excluded / crawled-not-indexed в Search Console;
- merchant listings / product snippets health;
- impressions и clicks по:
  - category pages
  - product pages
  - support pages
  - B2B pages
- CTR по основным кластерам;
- количество индексируемых category/product/B2B URL;
- доля органических входов на support pages и их assisted conversion value;
- рост branded vs non-branded traffic;
- Google Images / merchant traffic.

### Отдельно отслеживать

- выпадение товаров из индекса;
- ошибки structured data;
- качество title/snippet rewrites;
- рост cannibalization между category/tag/search pages.

## 15. Практический roadmap по этапам

## Этап 1. Deploy и live-ревалидация

- выкатить уже подготовленные repo-фиксы;
- заново проверить товар, category, `custom-print/`, `order_success`, `wholesale/`;
- зафиксировать, что live совпадает с roadmap.

## Этап 2. Усиление money pages

- `custom-print/` как главный non-product money page;
- FAQ на категориях и `custom-print/`;
- product support links;
- B2B internal linking;
- финальное разведение `add-print/` и `custom-print/`.

## Этап 3. Merchant/apparel depth

- `ProductGroup` variants;
- реальные merchant attributes;
- image SEO upgrade;
- variant-aware metadata.

## Этап 4. Semantic expansion

- collections;
- intent pages;
- editorial / lookbook;
- B2B cluster growth.

## Этап 5. Authority growth

- reviews;
- UGC;
- collabs;
- PR;
- community-led link earning.

## 16. Финальная целевая картина

Идеальное состояние для main domain должно быть таким:

- sitemap отражает только нужные indexable URL и отдает реальные даты;
- search/filter/query pages не засоряют индекс;
- каждая категория является сильной landing page под свой intent;
- каждая товарная страница отдает честную и полную merchant/product schema;
- support pages работают как trust and answer hub;
- B2B pages не висят отдельно, а встроены в общую архитектуру;
- органика приходит не только на home и товары, но и на категории, help pages, B2B и visual search;
- все улучшения опираются на реальные данные, а не на «магические» SEO-легенды.

## 17. Источники, использованные при ревизии

### Context7

- Django sitemap framework:
  `https://docs.djangoproject.com/en/5.2/ref/contrib/sitemaps`
- Schema.org:
  `https://schema.org`

### Google Search Central / Google

- Product structured data:
  `https://developers.google.com/search/docs/appearance/structured-data/product`
- Merchant listing structured data:
  `https://developers.google.com/search/docs/appearance/structured-data/merchant-listing`
- Product variants support:
  `https://developers.google.com/search/blog/2024/02/product-variants`
- Managing crawling of faceted navigation URLs:
  `https://developers.google.com/search/docs/crawling-indexing/crawling-managing-faceted-navigation`
- Title links:
  `https://developers.google.com/search/docs/appearance/title-link`
- SEO Starter Guide:
  `https://developers.google.com/search/docs/fundamentals/seo-starter-guide`
- Image SEO:
  `https://developers.google.com/search/docs/appearance/google-images`
- Pagination historical note:
  `https://developers.google.com/search/blog/2011/09/pagination-with-relnext-and-relprev`
- AI features and your website:
  `https://developers.google.com/search/docs/appearance/ai-features`
- Google common crawlers / Google-Extended:
  `https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers`
- Search Console Sitemaps report:
  `https://support.google.com/webmasters/answer/7451001`
- GA4 Landing page report:
  `https://support.google.com/analytics/answer/14292358`
- Search Console API export:
  `https://support.google.com/webmasters/answer/12919192`

### OpenAI

- OpenAI crawlers:
  `https://developers.openai.com/api/docs/bots`
- Publishers and Developers FAQ:
  `https://help.openai.com/en/articles/12627856-publishers-and-developers-faq`

### Anthropic

- Claude / Anthropic crawler policy:
  `https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler`

### Perplexity

- Perplexity crawlers:
  `https://docs.perplexity.ai/docs/resources/perplexity-crawlers`
- Perplexity robots policy:
  `https://www.perplexity.ai/help-center/en/articles/10354969-how-does-perplexity-follow-robots-txt`

### Microsoft / Bing

- Clarity filters:
  `https://learn.microsoft.com/en-us/clarity/filters/clarity-filters`
- Clarity recordings overview:
  `https://learn.microsoft.com/en-us/clarity/session-recordings/recordings-overview`
- IndexNow:
  `https://www.bing.com/indexnow/getstarted`

### Search ecosystems / market context

- StatCounter Ukraine search engine market share:
  `https://gs.statcounter.com/search-engine-market-share/all/Ukraine/2025`
- DuckDuckGo result sources:
  `https://duckduckgo.com/duckduckgo-help-pages/results/sources`
- Ecosia search result providers:
  `https://support.ecosia.org/article/579-search-results-providers`
- Brave Search help / independence overview:
  `https://search.brave.com/help`

### Ukraine sanctions / operating context

- Указ Президента України №133/2017:
  `https://www.president.gov.ua/documents/1332017-21850`

## 18. Главное управленческое решение

Если цель действительно сделать SEO на уровне `12/10`, то следующий шаг не в том, чтобы “добавить еще пару meta tags”.

Следующий шаг:

- сначала закрыть P0;
- затем превратить категории и B2B-страницы в реальные search landing pages;
- затем включить variant/merchant/review/content growth layer;
- и только после этого масштабировать семантику и off-page.

Без этого любой дальнейший контент или линкбилдинг будет литься в систему, где часть базовых технических сигналов еще не выровнена.

## 19. Дополнительный deep-audit delta от 2026-04-19

### 19.1. Header продвигал не ту print-страницу, но это уже исправлено в repo

- до последнего repo-фикса global header CTA вел на `add-print/`;
- это означало, что самый сильный sitewide internal link по print-intent получала не `custom-print/`, а вторичная страница;
- в репозитории это уже исправлено: header CTA переведен на `custom-print/`;
- после деплоя нужно перепроверить live header и internal-link redistribution.

### 19.2. `add-print/` уже indexable и пересекается по смыслу с кастомизацией

- до последнего repo-фикса `https://twocomms.shop/add-print/` отдавал `200`, indexable, self-canonical;
- page title был уникальный, но meta description generic и не отражал реальный intent;
- OG был generic;
- page не находится в sitemap, а до выката последнего repo-фикса еще и получала sitewide link из header;
- это плохая комбинация:
  - Google и AI systems получают противоречивые сигналы о том, какая print-page главная;
  - часть внутренних ссылок уходит в неосновной URL;
  - возрастает риск intent cannibalization.

Текущий статус:

- в репозитории `add-print/` уже переведен в `noindex, follow` и перепозиционирован как secondary UGC URL;
- после деплоя нужно подтвердить live meta robots и убрать остаточный риск каннибализации в индексе.

### 19.3. `custom-print/` уже достаточно текстовая, но еще не достаточно search-grade

- live text layer страницы довольно плотный, то есть это уже не “пустой JS app”;
- на странице есть `H1` и серия `H2`, что хорошо;
- в репозитории page уже дополнительно усилена visible breadcrumbs, FAQ block, `FAQPage` schema и ссылками на `delivery`, `wholesale`, `contacts`;
- но page пока все равно не закрывает весь коммерческий intent:
  - нет блока “как подготовить файл”;
  - нет блока по срокам/тиражам/материалам;
  - нет кейсов;
  - нет сильного compare / proof layer;
  - нужна еще более явная B2B-подвязка по тиражам и сценариям.

### 19.4. AI-crawler readiness уже доведена до явной policy, но live-access все равно надо мониторить

- `robots.txt` больше не оставляет AI visibility на implicit `User-agent: *`:
  - явный `allow` есть для `OAI-SearchBot`, `ChatGPT-User`, `Claude-SearchBot`, `Claude-User`, `PerplexityBot`, `Perplexity-User`;
  - `GPTBot`, `ClaudeBot`, `CCBot` остаются закрытыми как training / non-search crawlers;
  - `Google-Extended` открыт осознанно, потому что для Google это не ranking-signal, но это control token для Gemini grounding / AI-use.
- добавлены `llms.txt` и `/.well-known/llms.txt` как compact map публичной brand/commercial surface;
- этого достаточно, чтобы убрать явные технические барьеры для ChatGPT / Claude / Perplexity / Gemini retrieval layer;
- но для полной уверенности все равно нужно:
  - проверить, не режет ли трафик CDN/WAF/hosting;
  - проверить access logs по `OAI-SearchBot`, `Claude-SearchBot`, `PerplexityBot`, Googlebot;
  - проверить, нет ли challenge/captcha/rate-limit именно для этих user-agent / IP ranges.

### 19.5. `llms.txt` теперь добавлен как secondary helper, а не как “секретный SEO-фактор”

- это не заменяет crawlability, indexability и content quality;
- для Google AI features отдельный AI-file сам по себе не нужен;
- реальная ценность `llms.txt` здесь узкая:
  - дать AI-agents и answer engines короткую canonical map сайта;
  - подсветить, что главные public money/support routes — это `catalog`, `custom-print`, `wholesale`, `about`, `contacts`, `delivery`, `faq`;
  - увести citations от utility-URL вроде `/search/`, `/cart/`, `/checkout/`, `/admin/`.
  - entity consistency;
  - хорошие public citations;
  - strong topical landing pages.

### 19.6. Freshness headers и cache-signals почти не используются

- у проверенных страниц и `sitemap.xml` не отдаются `Last-Modified`, `ETag`, `Cache-Control`;
- это не главный ranking factor сам по себе;
- но для технической гигиены и crawl efficiency лучше иметь понятную freshness strategy хотя бы для sitemap и критичных money pages.

## 20. GEO / LLMO / AI search strategy для TwoComms

### 20.1. Что подтверждают официальные документы

- для Google AI Overviews / AI Mode нет отдельного “секретного AI SEO”:
  - работают обычные SEO fundamentals;
  - страница должна быть индексируемой и eligible для snippet;
  - важны crawlability, internal links, text availability, page experience, корректная structured data, актуальный Merchant Center / Business Profile;
- `Google-Extended` не является ranking signal в Google Search:
  - это control token для Gemini training / grounding в части Google systems;
  - если бренд хочет видимость именно в Gemini answers, держать `Google-Extended` закрытым невыгодно;
- для ChatGPT Search критично не блокировать `OAI-SearchBot`;
- `GPTBot` и `OAI-SearchBot` — разные вещи:
  - `OAI-SearchBot` отвечает за появление в ChatGPT search results;
  - `GPTBot` связан с training use case;
- `ChatGPT-User` не определяет inclusion в Search;
- для Claude важны `Claude-SearchBot` и `Claude-User`, а не старый обобщенный `anthropic-ai`;
- для Perplexity важны `PerplexityBot` и, как user-triggered слой, `Perplexity-User`;
- Anthropic bots уважают `robots.txt`, умеют `Crawl-delay`, и сам Anthropic пишет, что IP-blocking не является надежной заменой корректному `robots.txt`.

### 20.2. Что реально даст попадание в ответы GPT / Gemini / Claude

- не “магические AI-файлы”, а чистый и понятный public web footprint;
- сильные, узко-интентные landing pages под конкретные вопросы пользователей;
- цитируемые и проверяемые страницы:
  - кто вы;
  - что именно делаете;
  - для кого делаете;
  - как заказать;
  - какие сроки;
  - какие материалы;
  - какие варианты кастома;
  - какая география и доставка;
- entity consistency:
  - один бренд-нэйм;
  - единые social profiles;
  - единые контакты;
  - единая формулировка специализации бренда;
- больше внешних упоминаний бренда в открытом интернете:
  - обзоры;
  - локальные подборки;
  - интервью;
  - кейсы клиентов;
  - Telegram / Instagram / YouTube / TikTok descriptions с brand mentions;
- страницы, которые хорошо отвечают на recommendation-style prompts:
  - “де замовити одяг зі своїм принтом”;
  - “який український бренд може зробити мерч для команди”;
  - “де зробити худі / футболку зі своїм дизайном”;
  - “оптовий український стріт одяг + дропшипінг”.

### 20.3. Что нужно сделать на TwoComms конкретно

- превратить `custom-print/` в полноценный recommendation-grade hub;
- усилить `wholesale/` как B2B proof page;
- развести `custom-print/` и `add-print/` по intent;
- подготовить public evidence pages:
  - “Як замовити кастомний принт на одязі в Україні”;
  - “DTF для худі, футболок, лонгслівів: вимоги до макета”;
  - “Мерч для бренду / команди / івенту під замовлення”;
  - “Опт і дропшипінг українського стріт-одягу від виробника”;
  - “Футболка / худі / лонгслів зі своїм принтом: що вибрати”;
- усилить brand entity page cluster:
  - `about/`
  - `contacts/`
  - `cooperation/`
  - `wholesale/`
  - `custom-print/`
  - профили Instagram / Telegram / любые публичные площадки.

### 20.4. Что не нужно считать «секретом»

- keyword stuffing под “AI SEO”;
- генерация отдельного мусорного контента “для нейросетей”;
- special AI schema, которого требует Google — его нет;
- вера в то, что один `llms.txt` поднимет бренд в GPT/Gemini/Claude;
- попытка “скормить” моделям бренд напрямую без сильного открытого web footprint.

### 20.5. Практическая AI-архитектура для бренда

- брендовый слой:
  - `about/`, `contacts/`, social profiles, policy/service pages, merchant/brand consistency;
- транзакционный слой:
  - `catalog/`, категории, товары, `custom-print/`, `wholesale/`;
- explanatory layer:
  - FAQ, help, delivery, size guide, care guide;
- recommendation layer:
  - статьи и лендинги под comparison / “best for” / “where to order” / “how to choose” intents;
- proof layer:
  - UGC, кейсы, внешние упоминания, партнёрства, обзоры, public testimonials.

### 20.6. Через какие search ecosystems реально стоит работать в Украине

По открытым данным `StatCounter` за март 2026 по Украине:

- `Google` — `89.57%`
- `bing` — `2.56%`
- `DuckDuckGo` — `0.39%`
- `Ecosia` — `0.02%`
- `Yandex` — `7.31%`

Практический вывод для TwoComms:

- главный фокус все равно остается на `Google`;
- вторым приоритетом становится не только сам `Bing`, а весь `Bing-powered layer`:
  - `DuckDuckGo` официально пишет, что традиционные links/images у них в основном идут из `Bing`;
  - `Ecosia` официально пишет, что результаты могут идти из `Microsoft Bing`, `Google` или `EUSP`, а в части запросов/регионов — главным образом из `Bing`;
- `Brave Search` стоит держать отдельным monitoring-track, потому что это независимый индекс, а не просто оболочка над Bing/Google;
- `Yandex`, несмотря на остаточную долю в open market-share data, не является для TwoComms рабочим стратегическим фокусом:
  - в украинском контексте он остается под длительными санкционными и доступностными ограничениями;
  - это не тот слой, куда сейчас разумно вкладывать главный SEO-ресурс.

Следствие:

- улучшения под `Bing Webmaster + IndexNow + clean crawlability` дают ценность шире, чем просто “ради Bing”;
- это усиливает шансы сайта быть более заметным в части non-Google ecosystem и в Microsoft-related search surfaces;
- но это не заменяет фундаментальный приоритет `Google + strong public web footprint`.

## 21. Приблизительная оценка видимости сейчас

Важно: это inference по sampled live SERPs и `site:`-проверкам, а не полноценный rank-tracking. Точные позиции нужно сверять уже по GSC.

### 21.1. Брендовый спрос

- по brand query `TwoComms` главная уже находится;
- бренд существует в индексе и не выглядит “невидимым” по собственному имени.

### 21.2. Non-brand custom print / custom clothing

- в sampled выдаче по generic custom-print intent доминируют конкуренты с отдельными service pages и configurator-style посадочными;
- TwoComms в этих sampled результатах сейчас не выглядит заметным игроком;
- значит, non-brand organic capture под кастомизацию пока слабый.

### 21.3. B2B / wholesale / dropshipping

- в sampled выдаче по общим B2B запросам доминируют специализированные wholesale / dropshipping suppliers;
- Twocomms как B2B entity пока не выглядит закрепившимся в top layer;
- при этом сторонние страницы уже ссылаются на `wholesale/`, значит external mention layer можно наращивать.

### 21.4. Что это означает practically

- бренд уже живет в индексе;
- товары индексируются активно;
- но категории, B2B и custom-print пока не перехватывают достаточно non-brand commercial demand;
- основной потенциал роста не в home, а в:
  - категориях;
  - `custom-print/`;
  - `wholesale/`;
  - контенте вокруг “свой принт / мерч / опт / дропшиппинг”.

## 22. Сервисы и инструменты, которые дадут максимум пользы

### 22.1. Обязательный бесплатный стек

- Google Search Console
  - реальная видимость, CTR, запросы, страницы, индексация, sitemap, URL Inspection;
- Google Analytics 4
  - посадочные страницы, revenue / purchases, вовлечение organic traffic;
- Microsoft Clarity
  - rage clicks, dead clicks, quickbacks, heatmaps, реальные проблемы UX на SEO-страницах;
- Bing Webmaster Tools
  - индексация в Bing ecosystem, search performance, URL inspection, IndexNow;
- Google Merchant Center
  - free listings diagnostics, product issues, image / price / availability problems;
- Google PageSpeed Insights
  - mobile/desktop performance и реальные performance bottlenecks;
- Rich Results Test + validator.schema.org
  - проверка schema и сниппетных сущностей.

### 22.2. Что стоит использовать дополнительно

- Search Console API
  - чтобы выгружать больше данных по запросам и страницам, чем видно в UI;
- IndexNow
  - особенно полезен после реальных изменений товаров / категорий / B2B страниц;
  - не как mass re-submit всего сайта, а как fast discovery для changed URLs;
- Google Business Profile
  - если у бренда есть реальная публичная точка, шоурум, самовывоз или офлайн-контактный слой.
- Bing Places
  - если есть публичная точка / самовывоз / шоурум и нужен local layer в Bing / Microsoft ecosystem.

### 22.3. Что из инженерного слоя поможет

- автоматическая проверка sitemap / canonical / robots в тестах;
- автоматическая проверка structured data на критичных шаблонах;
- регламентный crawl-audit после релиза:
  - home
  - category
  - product
  - `custom-print/`
  - `wholesale/`
  - redirect `pricelist/ -> wholesale/`
  - `faq/`

## 23. Дополнительные данные для следующей итерации

Этот раздел сокращен сознательно. В roadmap должны оставаться только данные, которые реально повышают точность решений, а не пошаговые инструкции “куда зайти”.

### 23.1. Минимальный data-pack, который нужен для следующего точного прохода

- `Google Search Console`
  - exports `Queries`, `Pages`, `Devices`, `Indexing reasons`;
- `GA4`
  - `Organic landing pages`, `key events`, `revenue by landing page`;
- `Microsoft Clarity`
  - записи и heatmaps по `custom-print/`, особенно `dead clicks`, `quick backs`, mobile friction;
- `Bing Webmaster Tools`
  - `Recommendations`, `Search Performance`, `URL Inspection`, `Sitemaps`;
- `Merchant Center`
  - `Diagnostics` и `Free listings` issues;
- `PageSpeed Insights` + `Rich Results Test`
  - home, category, product, `custom-print/`, `wholesale/`.

### 23.2. Что больше не нужно тащить в документ

- пошаговые “зайди туда -> сделай скрин” инструкции;
- скриншоты интерфейсов без цифр, export или actionable-вывода;
- дублирование одних и тех же показателей из нескольких мест, если есть CSV/export;
- чек-листы ради чек-листов, не меняющие приоритеты.

### 23.3. Что имеет смысл мониторить постоянно

- `Google Search Console`
- `GA4`
- `Microsoft Clarity`
- `Bing Webmaster Tools`
- `Merchant Center`
- `PageSpeed Insights`
- `Rich Results Test / validator.schema.org`

## 24. Подтвержденные live-данные, собранные 19 апреля 2026

Ниже не гипотезы, а факты из реальных интерфейсов `Google Search Console`, `GA4`, `Microsoft Clarity`, `Merchant / Shopping reports` и локальных экспортов из папки `SEOScreen`.

### 24.1. Search Console: organic visibility пока очень узкая

По данным за последние 3 месяца:

- `120 clicks`
- `1.67k impressions`
- `CTR 7.2%`
- `avg position 20.4`

По данным за последние 28 дней:

- `39 clicks`
- `465 impressions`
- `CTR 8.4%`
- `avg position 18.6`

Что уже видно по запросам:

- strongest layer сейчас — это бренд и локальный `Kharkiv / Харків` intent;
- примеры запросов, где уже есть клики:
  - `twocomms`
  - `twocoms`
  - `two coms`
  - `футболка харків`
  - `худі харків`
  - `харків футболка`
  - `футболка kharkiv`
- при этом широкий спрос по generic apparel intent пока почти не забирается:
  - `лонгслів` уже дает много показов, но почти без кликов;
  - это означает, что часть категорий и товаров видна слишком низко или не попадает в достаточно релевантный сниппет.

Практический вывод:

- сейчас SEO держится не на широком category coverage;
- сейчас SEO держится на:
  - бренде;
  - нескольких товарных страницах;
  - части локальных/нишевых apparel-intents.

### 24.2. Search Console: organic traffic слишком концентрирован в нескольких URL

Топовые страницы по экспорту за 3 месяца:

- `/` — `43 clicks`, `128 impressions`, `avg position 3.91`
- `/product/-225-tshirt-/` — `26 clicks`, `102 impressions`, `avg position 3.59`
- `/product/kha-edition-ts/` — `14 clicks`, `81 impressions`, `avg position 7.78`
- `/product/-225-hoodie-/` — `8 clicks`, `58 impressions`, `avg position 3.83`
- `/product/-v2-0_Pokrovsk/` — `6 clicks`, `37 impressions`, `avg position 3.92`
- `/catalog/hoodie/` — `4 clicks`, `86 impressions`, `avg position 4.23`
- `/catalog/tshirts/` — `3 clicks`, `74 impressions`, `avg position 2.74`

Это очень важный сигнал:

- organic demand capture пока не распределен по широкому ассортименту;
- money layer завязан на ограниченный набор URL;
- если эти 3-5 URL проседают, проседает и большая часть search visibility.

### 24.3. Search Console: mobile значительно сильнее desktop

По данным за 3 месяца:

- `Mobile` — `93 clicks`, `1084 impressions`, `avg position 12.25`
- `Desktop` — `26 clicks`, `579 impressions`, `avg position 35.96`
- `Tablet` — `1 click`, `11 impressions`, `avg position 5.27`

Это не просто “разница в устройствах”.

Это означает:

- desktop organic layer у сайта сейчас заметно слабее mobile;
- часть страниц может хуже выглядеть, хуже читаться или хуже удовлетворять desktop-intent;
- page layout, CTR-snippets, commercial blocks и usability desktop-версии надо считать отдельным приоритетом, а не вторичным хвостом mobile SEO.

### 24.4. Search Console: index coverage пока реально ограничивает рост

По indexing screen:

- `Indexed` — `42`
- `Not indexed` — `35`

Причины в excluded bucket:

- redirect pages — `3`
- server error `5xx` — `2`
- `Crawled, currently not indexed` — `25`
- `Discovered, currently not indexed` — `5`

Это одна из самых важных текущих проблем, потому что:

- excluded pages почти догоняют indexed pages;
- Google уже тратит crawl budget, но не видит достаточно ценности, качества или необходимости держать часть URL в индексе;
- проблема уже не только в “добавить еще контент”, а в качестве URL-set, internal links, canonical discipline и value-density страниц.

Отдельно тревожные примеры:

- среди `crawled, currently not indexed` есть товары;
- среди `discovered, currently not indexed` есть и важные публичные URL вроде `/catalog/` и `/catalog/long-sleeve/`.

Это поднимает crawl/indexation layer в уверенный `P0/P1`, а не в “потом улучшим”.

### 24.5. Search Console: backlink profile критически слабый, а internal links работают не на те страницы

По live report `Links`:

- внешних ссылок всего `3`;
- top linked page извне — главная страница;
- top linking sites:
  - `joblum.com`
  - `tiktok.com`
  - `work.ua`
- top anchor texts:
  - `twocomms shop`
  - `https twocomms shop`

Это значит:

- у домена пока почти нет внешнего authority layer;
- brand mentions и citations крайне слабые;
- без системного наращивания ссылочных и брендовых упоминаний non-brand growth будет ограничен даже при хорошем on-page.

По internal links report:

- `/` — `39`
- `/product/Idea-hd/` — `32`
- `/catalog/hoodie/` — `22`
- `/catalog/tshirts/` — `13`

При этом стратегические страницы:

- `custom-print/`
- `wholesale/`
- `add-print/`

не выглядят top internal targets в Search Console.

Практический вывод:

- текущая внутренняя паутина не прокачивает достаточно сильно revenue-intent pages;
- link equity размазан не так, как нужно для роста `custom print / wholesale / B2B`.

### 24.6. Merchant / Shopping layer не сломан, но сильно недоиспользован

Что подтверждено в live reports:

- `Product snippets` / `Описания товара` — `0 critical issues`, `10 valid items`;
- `Merchant listings` / `Данные о товарах продавца` — `0 critical issues`, `10 valid pages`;
- `Merchant Center opportunities` обновлены `19 апреля 2026`;
- товаров:
  - `336 approved and shown`
  - `0 disapproved`

Но при этом Google явно просит усилить merchant completeness:

- добавить shipping rules;
- добавить return rules;
- добавить payment methods;
- добавить store rating.

То есть:

- базовая eligibility уже есть;
- но commerce trust layer используется не на максимум;
- это хороший кандидат в `P1`, потому что это усиливает не только Shopping exposure, но и общую достоверность коммерческого сайта для Google systems.

### 24.7. GA4: organic трафик пока не конвертируется в деньги так, как должен

За период `22 марта 2026 — 18 апреля 2026` по `Traffic acquisition`:

- всего `321 sessions`
- `156 engaged sessions`
- engagement rate `48.6%`
- avg engagement time per session `2m 25s`
- total revenue `1650 грн`

По channel split:

- `Direct` — `225 sessions`, `1650 грн`
- `Organic Search` — `48 sessions`, `0 грн`
- `Organic Social` — `24 sessions`
- `Referral` — `13 sessions`
- `Unassigned` — `10 sessions`
- `Organic Shopping` — `1 session`

Это сильный бизнес-сигнал:

- organic сейчас не просто маленький;
- organic сейчас почти не участвует в revenue layer;
- значит задача не только в росте показов и кликов, но и в доведении SEO-страниц до коммерческого действия.

### 24.8. GA4: `custom-print/` уже одна из главных страниц сайта, но не доводит до целевого действия

По landing pages за тот же период:

- `/` — `146 sessions`
- `/custom-print` — `71 sessions`
- `/product/-225-tshirt-` — `12 sessions`
- `/product/kha-edition-ts` — `12 sessions`
- `/catalog` — `7 sessions`
- `/product/-225-hoodie-` — `7 sessions`, revenue `1650 грн`

Что особенно важно по `/custom-print`:

- `71 sessions`
- `36 active users`
- `31 new users`
- avg engagement `4m 08s`
- `0 key events`
- `0 revenue`

Это один из самых сильных сигналов всего аудита.

`custom-print/` уже доказал, что:

- способен привлекать пользователей;
- удерживает внимание намного дольше многих других страниц;
- воспринимается как важная входная точка.

Но он пока не доказал, что:

- переводит пользователя в заявку;
- переводит пользователя в корзину;
- переводит пользователя в measurable commercial event.

Следствие:

- `custom-print/` нужно рассматривать не как secondary content page, а как один из главных money-page candidates сайта;
- его UX, trust layer, CTA-архитектура, event tracking и SEO intent coverage должны быть в top-priority.

### 24.9. GA4 + Search Console linked report: SEO сидит на товарах, а не на service/B2B-cluster

По linked report `Google organic search traffic`:

- всего `37 clicks`
- `576 impressions`
- `CTR 6.42%`
- average position `16.40`
- `36 active users`
- `24 engaged sessions`
- `3 key events`

Топовые SEO landing pages в этом linked слое:

- `/product/kha-edition-ts/` — `13 clicks`, `68 impressions`, `CTR 19.12%`
- `/product/-225-tshirt-/` — `9 clicks`, `42 impressions`, `CTR 21.43%`
- `/` — `8 clicks`, `28 impressions`, `CTR 28.57%`
- `/product/-v2-0_Pokrovsk/` — `2 clicks`
- `/catalog/hoodie/` — `1 click`
- `/product/-225-hoodie-/` — `1 click`

Что это подтверждает:

- service-intent и B2B-intent страницы пока не доминируют в SEO-потоке;
- `custom-print/` уже важен по общему трафику, но еще не закрепился как сильный organic search winner;
- значит текущий потенциал роста находится именно в построении stronger service cluster, а не в бесконечном усилении уже видимых товаров.

### 24.10. Clarity: `custom-print/` реально является одной из самых важных страниц поведения

По dashboard `Microsoft Clarity` за последние 10 дней:

- `123 sessions`
- `40 unique users`
- `2.95 pages/session`
- scroll depth `63.61%`
- active time `2.9 min`
- returning sessions `69.92%`

Фрустрационные сигналы:

- dead clicks — `15.45%` / `19 sessions`
- quick backs — `19.51%` / `24 sessions`
- rage clicks — `0`

Smart events:

- checkout — `4 sessions`
- add to cart — `1 session`

Performance widget:

- score `82/100`
- `LCP 1.4s` — good
- `INP 410ms` — needs improvement
- `CLS 0` — good

Топовые страницы по Clarity:

- `/custom-print/` — `56`
- `/` — `47`
- `/catalog/tshirts/` — `15`
- `/catalog/` — `7`
- `/dopomoga/` — `5`

Практический вывод:

- `custom-print/` важен уже не только в GA4, но и в реальном поведенческом слое;
- users явно приходят туда и взаимодействуют;
- но часть взаимодействий неудобна или не приводит к быстрому продолжению пути;
- sitewide dead clicks и quick backs достаточно заметны, чтобы UX-аудит считался SEO-задачей, а не отдельной “дизайн-историей”.

### 24.11. Что это меняет в приоритетах roadmap

После live-проверки приоритеты нужно читать так:

- `P0`
  - index coverage cleanup;
  - sitemap freshness / `lastmod`;
  - canonical discipline;
  - cleanup raw template leakage в live HTML;
  - разведение `wholesale/` и `/opt/`;
- `P1`
  - радикальное усиление `custom-print/` как organic + commercial hub;
  - перенастройка internal linking на `custom-print/`, `wholesale/`, `cooperation/`;
  - Merchant completeness: shipping / returns / payment methods / store rating;
  - desktop UX / conversion diagnosis;
- `P2`
  - off-page authority growth;
  - GEO / LLMO / AI citation growth;
  - recommendation-style content layer.

Иными словами:

- раньше `custom-print/` можно было считать перспективной гипотезой;
- теперь это уже подтвержденный priority URL, который получает внимание пользователей, но недоиспользуется и в SEO, и в conversion architecture.

### 24.12. Техническая ремарка по Django sitemap, подтвержденная через Context7

Отдельно подтверждено по документации Django sitemap framework:

- `lastmod` в sitemap можно задавать как method/attribute;
- если sitemap items имеют `lastmod`, Django `views.sitemap()` может отдавать `Last-Modified` header по последнему изменению;
- для sitemap index предусмотрен `get_latest_lastmod()`.

Почему это важно именно для TwoComms:

- это объясняло, почему refactor sitemap-layer был обязателен, а не косметичен;
- для e-commerce сайта с товарами, категориями и B2B-страницами `lastmod` реально усиливает freshness signaling и техническую гигиену crawl-layer;
- на текущую дату этот блок уже закрыт в live, и задача теперь не “впервые добавить `lastmod`”, а не допустить отката при будущих правках sitemap.

### 24.13. Bing Webmaster: live-сигнал по Bing сейчас очень конкретный

По live-экрану `Recommendations` в `Bing Webmaster Tools` для `twocomms.shop` сейчас подтверждены две проблемы:

- `High severity` — `IndexNow не приймається`
- `Medium severity` — `Брак вхідних посилань із високоякісних доменів`

Что важно:

- это не абстрактный “совет из статьи”, а прямой сигнал из live Bing-интерфейса;
- он совпадает с кодовой реальностью:
  - до этой ревизии в проекте вообще не было `IndexNow`-слоя;
  - не было key-file;
  - не было submission-механизма по товарам/категориям;
  - не было инженерного инструмента для controlled submit changed URLs.

Что уже подготовлено в коде этой ревизией:

- env-gated `IndexNow` key-file по корневому пути `/{INDEXNOW_KEY}.txt`;
- post-commit submit для публичных `Product` и `Category` URL при save/delete;
- отдельная management-команда `submit_indexnow_urls` для controlled batch-submit changed URLs;
- защита от hardcode секретов:
  - ключ берется только из `env`;
  - без `INDEXNOW_KEY` механизм остается no-op;
- защита request lifecycle:
  - основной путь идет через Celery task;
  - sync fallback сделан best-effort и не должен ронять сохранение сущности.

Что подтверждено live уже после выката:

- `https://twocomms.shop/{INDEXNOW_KEY}.txt` реально доступен на основном домене;
- `python manage.py submit_indexnow_urls --core` на production уже успешно отправлял старый core-набор; после вывода `pricelist/` dry-run current core-set собирает `18` URL;
- значит, проблема больше не в отсутствии `IndexNow`-интеграции как таковой, а только в том, когда `Bing Webmaster` обновит свой recommendation state.

Отдельный технический root cause, который был найден в процессе live-fix:

- cPanel / CloudLinux Python app реально является частью production env-layer для `twocomms.shop`;
- при live-проверке `lswsgi`-процесса было подтверждено, что runtime берет `DJANGO_SETTINGS_MODULE` и `DJANGO_ENV_FILE` именно из hosting-layer;
- при этом в cPanel env изначально не было `SITE_BASE_URL` и `INDEXNOW_KEY`, поэтому для `IndexNow` слой был неполным;
- отдельно `DJANGO_ENV_FILE` указывал на repo-root `.env.production`, которого раньше не существовало как файла;
- из-за этой комбинации runtime и часть management-команд могли не подхватывать новые env-переменные надежно и предсказуемо;
- это уже исправлено:
  - через добавление `SITE_BASE_URL` и `INDEXNOW_KEY` в cPanel / CloudLinux env приложения;
  - через появление repo-root `.env.production`, указывающего на реальный production env;
  - через кодовый fallback в `manage.py` и `twocomms/production_settings.py`, чтобы отсутствующий explicit env-path больше не ломал env-loading.

Отдельно по dry-run:

- локально подтвержден `dry-run` для core pages;
- команда собрала `19` ключевых публичных URL основного домена;
- по рекомендациям Bing это нужно использовать не как “перепушить весь сайт”, а как fast-notify слой для реально измененных URL.

### 24.14. Поисковые системы, которые реально стоит учитывать для Украины

На уровне стратегии приоритет сейчас должен быть таким:

- `Tier 1` — `Google`
  - это доминирующий слой и основная точка роста organic revenue;
- `Tier 2` — `Bing ecosystem`
  - сам `Bing`;
  - `DuckDuckGo`, который официально largely sources traditional links/images from `Bing`;
  - часть `Ecosia`, которая официально может быть powered by `Bing` в зависимости от запроса, региона и consent-layer;
- `Tier 3` — `Brave Search`
  - отдельный независимый индекс, который нельзя улучшить только через Google/Bing hygiene.

Что это означает practically:

- `Bing Webmaster + IndexNow + clean crawlability` нужны не ради маленькой доли Bing как таковой;
- они усиливают заметность сайта в более широком non-Google search layer;
- для AI/search поведения это тоже полезно, потому что часть recommendation surfaces питается не только Google-index логикой.

При этом:

- `Yandex` нельзя считать нормальным рабочим target-market для TwoComms в Украине;
- даже если open market-share data показывает остаточную долю, в операционном смысле это не тот SEO-layer, куда сейчас стоит вкладывать основной ресурс;
- для бренда гораздо выгоднее усилить:
  - `Google`;
  - `Bing ecosystem`;
  - `Brave`;
  - открытый web footprint, который подхватывают `GPT / Gemini / Claude`.
