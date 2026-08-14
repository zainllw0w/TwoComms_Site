# TwoComms: детальный SEO/GEO-аудит презентации и текущего сайта

Дата начала: 2026-08-10
Статус: доказательный аудит завершен 2026-08-11; первый узкий internal-link fix развернут, остальные изменения выполняются только по implementation checklist
Область: публичный магазин twocomms.shop, код текущего checkout, production HTML/БД/маршруты и 86-слайдовая презентация «КП SEO + АІ - Twocomms.shop»
Исключение: Custom Print полностью исключен из content/variant/schema/metadata/canonical-аудита и из широких crawl-выборок. Уже исправленная ссылка `/catalog/custom-print/` относилась к внешней гигиене каталога и не дает права анализировать или менять сам Custom Print. Единственное допустимое продолжение — конкретно воспроизведенный дефект RU/EN локализации с минимальной locale-only правкой и неизменным UK/рабочим flow.

## 1. Как читать этот отчет

Каждый тезис презентации получает один из вердиктов:

- **Подтверждено** — проблема воспроизводится в актуальном production или однозначно следует из текущего выполняемого кода/данных.
- **Частично подтверждено** — наблюдение верное, но масштаб, причина или предложенное решение в презентации неточны.
- **Устарело / уже исправлено** — проблема могла существовать на момент скриншота, но сейчас не воспроизводится.
- **Не является ошибкой** — показанное поведение допустимо по документации поисковых систем либо не оказывает заявленного влияния.
- **Недостаточно доказательств** — скриншот или метрика без метода, даты, выборки и доступа к первичному источнику не позволяют сделать надежный вывод.
- **Дополнительная находка** — проблема обнаружена при независимой проверке, даже если ее нет в презентации.

Приоритеты:

- **P0** — индексирование/доступность/каноникализация системно сломаны; требуется немедленная реакция.
- **P1** — высокий потенциальный ущерб или высокий КПД исправления.
- **P2** — существенное улучшение качества, релевантности или crawl efficiency после P0/P1.
- **P3** — низкий риск и ограниченный эффект; выполнять пакетно после более ценных задач.

Для каждой подтвержденной находки требуются: URL или кодовый путь, наблюдаемое доказательство, механизм SEO-влияния, контрдоказательства, безопасная рекомендация и способ проверки результата. Само по себе совпадение с чек-листом стороннего аудитора доказательством не считается.

### 1.1. Жесткая матрица решений против переоптимизации

| Класс | Что входит | Что это дает напрямую | Ограничение |
|---|---|---|---|
| **Подтверждено, исправлять** | живые internal 404; RU/EN с украинским main content/schema; сломанный reciprocal hreflang; invalid/duplicate/empty facets и nonexistent pagination с `200`; variant URL с неверным selected image/price/availability/cart identity; ложные или конфликтующие claims; ненормализованные дубли пути | устраняет конкретные противоречивые crawl/index/user signals | обязательны RED/GREEN test, exact-SHA deploy и live proof |
| **Условно, только после данных** | отдельные indexable color/fit landing; variant allowlist; `page=1` redirect; city/local landing; robots policy после деиндексации | может улучшить ownership/discovery/UX | требуется GSC/query/backlink/inventory/media evidence; это стратегия сайта, не требование Google |
| **Отклонено как обязательное SEO-правило** | большой уникальный текст для каждого варианта; уникальные title/description для page 2; копия каждого variant URL во всех трех sitemap при корректном HTML hreflang; `noindex + canonical` для всех size/variant states; crawl-budget P1 для 1 354 URL без GSC/log evidence | гарантированного положительного эффекта не доказано | не входит в acceptance и не используется для оценки выполненности |
| **Не делать** | mass-301 на base/category; тексты ради n-gram/процента уникальности; Cartesian color×fit×size pages; keyword density/alt stuffing; списки городов и city pages без реальной локальной услуги; выдуманные SKU, GTIN, stock или фото | создает soft-404, scaled-content, misleading content и migration risk | запрещено до отдельного доказанного business/search intent и exact owner mapping |

Ни одно техническое исправление не гарантирует рост позиций. Допустимая формулировка результата: исправлен конкретный статус, язык, owner, selected state или факт и уменьшено число противоречивых сигналов. Рост оценивается только после релиза по GSC и аналитике с зафиксированным периодом сравнения.

## 2. Источники и ограничения

### 2.1. Проверяемые источники

1. Опубликованная Google Slides презентация: 86 слайдов, включая весь видимый текст и вставленные изображения.
2. Текущий код репозитория и существующие тесты.
3. Production-ответы twocomms.shop: HTTP-цепочки, HTML, заголовки, canonical/hreflang, robots, sitemap, schema.org, ссылки и мобильный рендер.
4. Production-БД и конфигурация через SSH только в read-only режиме.
5. Официальная документация Google Search Central, в том числе полученная через Context7.

### 2.2. Ограничения, которые нельзя маскировать уверенностью

- Published-презентация доступна публично, но Google Drive API в текущей среде не настроен: отсутствует локальный OAuth-файл. Поэтому слайды извлекаются из опубликованного viewer и проверяются визуально; это сохраняет вставленные скриншоты и не требует доступа на редактирование.
- Данные Google Search Console, GA4, Ahrefs/Serpstat и других закрытых кабинетов нельзя считать актуальными только по скриншоту. Для метрик обязательно фиксируются дата, период, фильтры, страна, устройство, тип поиска и источник.
- Рекомендация не объявляется гарантией роста позиций. Отчет отделяет техническую корректность и вероятный механизм влияния от прогнозов трафика, которые требуют семантики, конкуренции и последующего измерения.

### 2.3. Зафиксированный production-срез

Срез ниже снят 2026-08-10 около 22:57 по Киеву без авторизации и без изменения сервера.

- `https://twocomms.shop/robots.txt` — `200`, `text/plain`.
- `https://twocomms.shop/sitemap.xml` — `200`, восемь дочерних sitemap.
- `sitemap-products.xml` — 213 URL, то есть 71 опубликованный товар x 3 языка.
- `sitemap-product-variants.xml` — 210 URL; сейчас это только URL без языкового префикса. Внутри 78 URL цвета, 59 URL посадки и 73 комбинации `цвет x посадка` для 71 товара.
- `sitemap-categories.xml` — 9 URL, то есть 3 категории x 3 языка.
- `sitemap-color-categories.xml` — 12 URL, то есть 4 опубликованных landing page x 3 языка: черный для футболок/худи/лонгсливов и койот для футболок.
- `sitemap-thematic.xml` — 4 стабильных тематических owner URL (`military`, `streetwear`, `patriotic`, `kharkiv-edition`); каждый имеет самостоятельный path и языковой hreflang-кластер.
- `sitemap-static.xml` — 54 URL, то есть 18 маршрутов x 3 языка.
- Базовые `/catalog/`, `/catalog/tshirts/`, `/ru/catalog/`, `/en/catalog/` отвечают `200` и self-canonical.
- `/catalog/tshirts/?color=black` и `/catalog/tshirts/?fit=oversize` отвечают `200`, содержат `noindex, follow` и canonical на `/catalog/tshirts/`.

Локальный `HEAD`, `origin/main` и production checkout на момент начала аудита совпадают: `c6d8259320eb5fe336326072fa6470473b820b50`. Production-БД содержит 71 опубликованный товар, 3 активные категории, 4 опубликованных `CategoryColorLanding`, 67 активных `ProductFitOption` и 81 `ProductColorVariant`. Сервер проверялся только read-only; его существующий dirty worktree не изменялся.

Первый щадящий массовый проход по 210 variant URL дал 191 ответа `200`; все 191 были self-canonical. Еще 17 запросов завершились клиентским timeout, два вернули временный `503` во время прохода. Затем все 19 URL были повторно запрошены последовательно и каждый ответил `200`. Итоговая проверка доступности: **210 из 210 URL отвечают `200`**. Первичные timeout/`503` не воспроизвелись, поэтому они не считаются подтвержденной SEO-ошибкой; performance/capacity остается только гипотезой до серверных метрик или повторяемого нагрузочного сценария.

### 2.4. Нормативная база Google, сверенная через Context7

1. [Managing crawling of faceted navigation URLs](https://developers.google.com/search/docs/crawling-indexing/crawling-managing-faceted-navigation): параметры фильтров способны создавать почти бесконечное URL-пространство и замедлять обнаружение полезных страниц. Если faceted URL не должны индексироваться, Google рекомендует ограничивать их crawl; если должны — использовать стабильный порядок параметров и отдавать `404` для пустых, бессмысленных, повторных и несуществующих комбинаций.
2. На той же странице Google отдельно предупреждает, что `rel=canonical` и `rel=nofollow` менее эффективны для управления crawl, чем предотвращение ненужного обхода. Из этого не следует, что надо немедленно закрыть уже известные URL в robots.txt: сначала нужно убрать внутренние SEO-ссылки и убедиться, что старые URL исключены из индекса, иначе Google перестанет видеть их `noindex`.
3. [Product variant structured data](https://developers.google.com/search/docs/appearance/structured-data/product-variants): допустимы и один canonical ProductGroup URL, и отдельные URL вариантов. Для multi-page варианта каждый URL должен предвыбирать правильный товарный вариант и показывать согласованные изображение, цену и наличие; `ProductGroup`, `variesBy`, `hasVariant`/`isVariantOf` и устойчивые идентификаторы связывают варианты, но сами по себе не доказывают, что каждую комбинацию полезно индексировать.
4. [Loyalty Program structured data](https://developers.google.com/search/docs/appearance/structured-data/loyalty-program): `hasTierBenefit` у `MemberProgramTier` принимает значения `TierBenefitEnumeration`, например `https://schema.org/TierBenefitLoyaltyPoints`; при таком benefit Google также ожидает `membershipPointsEarned`. Произвольный объект типа `MemberProgramTierBenefit` не соответствует документированному контракту.
5. [Spam policies for Google web search](https://developers.google.com/search/docs/essentials/spam-policies): keyword stuffing, doorway abuse и scaled content abuse запрещены независимо от того, создан текст человеком или автоматикой. Поэтому длина, keyword density, n-gram uniqueness и количество городов/FAQ не являются целями реализации.
6. [Managing multi-regional and multilingual sites](https://developers.google.com/search/docs/specialty/international/managing-multi-regional-sites): Google определяет язык прежде всего по видимому тексту; страница и навигация должны явно использовать один язык. Отдельный URL-префикс или `lang` не компенсирует украинский основной контент на RU/EN странице.
7. [Localized versions](https://developers.google.com/search/docs/specialty/international/localized-versions): hreflang-кластер должен быть reciprocal и self-inclusive. Это технический контракт выбора локали, а не гарантия ранжирования.
8. Context7 Django 5.2 подтверждает реализацию этого контракта: `translation.override()` устанавливает активный язык для тестов/URL generation, а language-dependent template cache fragments должны включать `LANGUAGE_CODE`; per-site cache включает активный язык при включенной i18n. Это руководство по корректной реализации, не SEO ranking evidence.
9. [Canonical consolidation](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls): redirect и `rel=canonical` являются canonical signals; Google прямо не рекомендует использовать `noindex` для выбора canonical. Поэтому `noindex + canonical` не вводится как blanket variant policy.
10. [Pagination](https://developers.google.com/search/docs/specialty/ecommerce/pagination-and-incremental-page-loading): каждая реальная page 2+ должна иметь свой URL и self-canonical; Google не требует distinct title/description для каждой страницы последовательности. Невалидная pagination должна возвращать `404` по faceted-navigation guidance.
11. [Sitemaps](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap): sitemap должен перечислять intended canonical URLs, которые владелец хочет видеть в поиске, но является только слабым canonical signal. По localized-versions guidance из пункта 7 HTML, HTTP header и sitemap являются равнозначными способами hreflang; отсутствие отдельного RU/EN variant `<loc>` не является ошибкой само по себе при корректном HTML cluster.
12. [Crawl budget for large sites](https://developers.google.com/search/docs/crawling-indexing/large-site-managing-crawl-budget): отдельная crawl-budget оптимизация предназначена прежде всего для очень больших или быстро меняющихся сайтов. Для текущих 1 354 URL это P1 только при подтверждении через GSC Crawl Stats, server logs или повторяемую нагрузку.
13. [Ecommerce URL structure](https://developers.google.com/search/docs/specialty/ecommerce/designing-a-url-structure-for-ecommerce-sites): variant states могут иметь отдельные path/query URL, но URL/canonical/internal-link/sitemap usage должны быть последовательны. Это не требование индексировать каждый selector state и не требование писать длинный уникальный текст.

## 3. Реестр слайдов презентации

- **Слайды 1–9:** исключены из детального аудита по прямому указанию владельца; это вводно-коммерческий блок без результатов проверки сайта.
- **Слайды 10–40:** весь текст и 73 извлеченных содержательных asset были визуально проверены. Ниже дан полный реестр; технические тезисы дополнительно сверяются с текущим production и кодом.
- **Слайды 41–46:** общие тезисы об SEO/GEO, ROI, AI Overviews и генеративной выдаче. Ни URL TwoComms, ни первичных данных магазина нет; это не доказанные ошибки сайта.
- **Слайды 47–51:** цены, сроки и квоты пакетов агентства. Это коммерческое предложение, а не аудит. Квоты `10–15 текстов`, `50–75 тыс. символов` и заданное число crowd/«вечных»/«трастовых» ссылок оцениваются как риск scaled content и link spam, если выполняются ради объема без demand map и проверки доноров.
- **Слайды 52–55:** экспертность агентства и методические примеры. Восстановленные скриншоты 53–55 относятся к чужому сайту `5watt.ua`/`new.5watt.ua`, Wordstat/seowork и шаблону E-E-A-T-чеклиста; они не показывают состояние TwoComms.
- **Слайды 56–67:** партнерские бонусы, отзывы, обещания, команда и разделитель кейсов. Утверждения `64% в Top 3`, `100% в Top 10`, `100 -> 3 000/сутки`, `>40%`, `x2`, `50+ лет`, `24/7` не имеют достаточного baseline, периода, знаменателя и первичного отчета; это не benchmark для TwoComms.
- **Слайды 68–86:** 19 сторонних портфолио-кейсов (`rezervist.com.ua`, `pancer.com.ua`, `suzie.ua` и другие). В них нет данных `twocomms.shop`; отсутствуют период, поисковик, регион, устройство, brand/non-brand split, URL строк и источник метрик. Некоторые отдельные запросы на самих слайдах ухудшились, а значения `101`, `0` и `–` не имеют легенды. Все 19 слайдов классифицированы как «не является находкой по TwoComms».

### 3.1. Полный реестр слайдов 10–40

| Слайд | Что фактически показано | Текущий доказательный вердикт |
|---:|---|---|
| 10 | Google Trends: Украина, web, один год, пять терминов; в тексте остались шаблонные «1», «2», «5» | Относительная динамика видна, но абсолютный спрос, конверсия и устойчивый рост не доказаны. Шаблонные значения нельзя переносить в семантику. |
| 11 | Similarweb Engagement по пяти доменам | Скриншот не содержит каналов, поэтому не доказывает тезис «SEO — главный канал конкурентов». |
| 12 | Semrush traffic share, branded mix, overlap и доменные суммы | Исторический сторонний snapshot; `N/A`/`0` не равны нулю в GSC. Пригоден только как гипотеза для нормализованного gap-анализа. |
| 13 | Интерпретация тех же данных Semrush | Возможность content gap правдоподобна, но запросы, интенты и URL не показаны; массовое копирование тем создаст каннибализацию. |
| 14 | Ahrefs referring domains: TwoComms 345 и конкуренты | Count прочитан корректно, но не является самостоятельным ranking factor; качество и редакционная природа важнее количества. |
| 15 | Проценты видимости `50/20/20` без списка запросов и методики | Недостаточно доказательств: отсутствуют оставшиеся 10%, SERP, база, страна, язык, устройство и доля трафика. |
| 16 | Ahrefs AI/ChatGPT counters и Google AI Overview с упоминанием TwoComms | Не доказывает «активную AI-оптимизацию» или клиентов конкурентов; собственный asset одновременно показывает цитирование TwoComms. |
| 17 | Разделитель «Пункти для виправлення» | Не содержит находки или evidence. |
| 18 | Rich Results Test от 29.07.2026: невалидный `MemberProgram` на PDP | Подтверждено и сейчас: production все еще отдает неподдерживаемый `MemberProgramTierBenefit`; см. FIND-009. |
| 19 | Media URL с кириллицей и Screaming Frog с 1 289 parameter URL | Кириллица в media path допустима; реальный сигнал — большое фасетное URL-пространство, уже подтвержденное FIND-001/FIND-002. |
| 20 | Исторический crawl 2 026 URL: 534 duplicate title и длины | Исторический масштаб нельзя переносить буквально. Текущие дубли на indexable color-fit URL подтверждены отдельно в FIND-006. Порог длины — эвристика. |
| 21 | 206 duplicate descriptions и 652 duplicate H1 | Историческая группа, а не 858 самостоятельных ошибок. Важны indexability, canonical, locale и intent; текущие вариантные дубли подтверждены FIND-006. |
| 22 | Missing alt и 26 client-error URL, включая numeric PDP и `/catalog/custom-print/` | Завершённый sitemap + one-hop crawl подтвердил 25 URL с `404` и живыми внутренними ссылками: `/catalog/custom-print/` (36 inlinks) и 24 legacy numeric PDP; все отсутствуют в sitemap. См. FIND-017. Пустой `alt` у декора корректен; keyword stuffing в alt не нужен. |
| 23 | Redirect report и `?page=1` | Полный sitemap + one-hop crawl обнаружил 15 redirect responses: публичные SEO-нормализации были одношаговыми, а двухшаговая внешняя Google OAuth-цепочка относится к auth flow. Категорийный `?page=1` по direct check остаётся `200` с canonical на clean URL; см. FIND-011. |
| 24 | Пустой H2 в историческом DOM | Сам пустой динамический/скрытый heading не доказывает SEO-потерю. Текущий source содержит пустой H2 языкового modal, который заполняется JS; оценивать нужно rendered visibility и accessibility tree. |
| 25 | Непереведенные английские meta/страницы | Основные EN meta сейчас переведены, но mixed-language shared components остаются; тезис частично устарел и частично подтвержден FIND-005. |
| 26 | EN PDP с украинским текстом и исторически отображавшейся HTML-разметкой | Literal escaped HTML на контрольном PDP сейчас не воспроизведен, но крупный нижний SEO-блок и modal остаются смешанными по языку; FIND-005. |
| 27 | Требование добавить универсальный SEO-текст на главную | Не является обязательным правилом. Нужен полезный уникальный контент по intent, а не блок ради объема. |
| 28 | Mobile Lighthouse opportunities | Это lab snapshot, не field CWV. Требует повторного mobile trace и CrUX/GSC; не является самодостаточным доказательством ущерба. |
| 29 | Резкий исторический backlink spike | Сам всплеск на скриншоте реален; покупка/спам и algorithmic action не доказаны без lost/new links, anchors, targets и GSC manual actions. |
| 30 | TLD распределение `.com/.org/.xyz/...` названо географией | Методологическая ошибка: TLD не определяет страну аудитории или хостинга. |
| 31 | Шаблонные/низкокачественные доноры | Список дает сильный spam-сигнал, но каждый домен и target URL нужно проверить до disavow; удаление ссылок предпочтительнее необоснованного массового disavow. |
| 32 | Анкоры ссылок | Профиль выглядит неестественно, но penalty не доказан. Нельзя отвечать закупкой «правильных процентов» анкоров; нужен URL-level review. |
| 33 | Ahrefs organic traffic `0` | Это отсутствие оценки в базе инструмента, а не доказательство нулевых показов/кликов в Google. Нужны GSC/GA4. |
| 34 | Все buckets позиций равны `0` | Один snapshot не доказывает негативную динамику; нет списка запросов, страны, устройства или второй точки времени. |
| 35 | `/catalog/hoodie/` якобы «близко к Top 10» при нулевых backlinks | Главный тезис не подтвержден: на слайде нет запроса, позиции, показов или SERP. |
| 36 | Большой SEO-блок на `/catalog/hoodie/?page=2` | Подтверждено в текущем production: page 2 self-canonical/indexable, но повторяет тот же большой city/benefit boilerplate; см. FIND-010. |
| 37 | Сравнение meta TwoComms и конкурента; «Keywords are missing» | Отсутствие meta keywords не ошибка. Title 50 и description 146 сами по себе нормальны; коммерческие слова добавлять только по реальному intent. |
| 38 | Видеоотзывы конкурента | Опционная CRO/E-E-A-T возможность, не найденный дефект. Только реальные отзывы, consent, transcript и lazy loading. |
| 39 | Mega-menu Futbolka.ua как образец структуры | IA может быть полезна, но копирование taxonomy без спроса/ассортимента создаст index bloat и doorway/cannibalization risk. |
| 40 | Google Business/карта конкурента | GBP полезен только при реальной eligible location или service-area business. Фиктивный адрес или карта ради SEO недопустимы. |

Подробные визуальные журналы с ID слайда, именами asset, транскрипциями и границами доказательств хранятся в `output/seo-audit-2026-08-10/agent-slides-10-40.md`, `agent-slides-41-67.md` и `agent-slides-68-86.md`. Основной отчет содержит все site-specific вердикты; вспомогательные журналы сохраняют воспроизводимость чтения каждого изображения.

## 4. Подтвержденные и опровергнутые тезисы презентации

Слайды 18, 23, 25–26 и 36 содержат проблемы, которые полностью или частично воспроизводятся на текущем production. Слайды 19–22 отражают исторические crawl-группы, отдельные механизмы которых подтверждены независимым текущим аудитом; их старые абсолютные количества нельзя считать актуальными. Ни один тезис слайдов 41–86 не подтверждает конкретную ошибку TwoComms. Их доказательная ценность ограничена общими направлениями и требованиями к будущему подрядчику:

1. Структура и семантика должны строиться через demand/intent clustering и явный URL ownership, но пример 5watt нельзя копировать как разрешение индексировать все теги и фасеты.
2. Wordstat — дополнительный источник, а не замена данным Google для Украины; нужны GSC, локальная SERP-проверка, Keyword Planner/Trends, конверсия и маржинальная ценность.
3. Фиксированная месячная норма текстов и ссылок не является KPI. Нужны brief и acceptance criteria для каждого URL, реальная редакционная ценность, проверка доноров и корректные `sponsored`/`ugc`-атрибуты там, где они требуются.
4. AI/GEO-видимость измеряется воспроизводимым набором запросов, языком, страной, моделью, датой и цитируемыми URL. Схема или FAQ не гарантируют цитирование.
5. Геостраницы и Google Business Profile допустимы только при реальной локальной сущности/ценности. Массовая подмена города в шаблоне создает doorway-риск.
6. Позиции, трафик и отзывы из сторонних кейсов нельзя использовать как прогноз роста TwoComms без baseline, стабильной выборки, периода и коммерческого результата.

## 5. Независимый технический аудит

### 5.1. Индексируемость, HTTP и crawl paths

#### FIND-001 — редакционные SEO-блоки системно направляют crawler на noindex-фасеты

- **Вердикт:** подтверждено в production.
- **Приоритет:** P1 по совокупному crawl/архитектурному эффекту; исправлять без отключения пользовательских фильтров.
- **Evidence:** базовый `/catalog/` содержит 28 ссылок с параметром `color` и 16 уникальных цветовых URL; `/catalog/tshirts/` — 34 такие ссылки и 9 уникальных цветовых URL. Среди них `/catalog/?color=black`, `/catalog/hoodie/?color=coyote`, `/catalog/tshirts/?color=black` и другие. При открытии `/catalog/tshirts/?color=black` production отдает `noindex, follow` и canonical на `/catalog/tshirts/`. На самом цветном фильтре найдено 59 ссылок с `color`, включая комбинации `black,coyote`, `black,white` и пагинацию.
- **Кодовая причина:** `services/general_catalog_seo.py::_build_top_filters_items()` всегда создает `/catalog/?color=<slug>`, а `services/color_seo_copy.py` содержит десятки HF/MF/LF-чипов, также ведущих на query-фильтры. При этом комментарий рядом с `_CURATED_TOP_QUERIES` прямо признает, что `?color=` — `noindex, follow` и SEO-visible навигация не должна передавать туда вес. Тест `test_seo_regressions.py` защищает только curated top queries, но не `top_filters` и не `color_seo_copy`.
- **Почему это проблема:** `noindex` решает вопрос попадания в индекс, но не предотвращает обход. Сайт сам повышает in-degree URL, которые затем просит не индексировать. Комбинации нескольких цветов, fit, size, theme и page расширяют пространство обхода, а полезных indexable color landing pages сейчас только четыре.
- **Дополнительная проверка policy:** sitemap + one-hop crawl обнаружил 752 query URL: 734 `noindex` и 18 `index,follow`. Восемь исключений — `?color=grey|olive` на `/catalog/`, `/catalog/tshirts/`, `/catalog/hoodie/` и `/catalog/long-sleeve/` с canonical на clean owner; еще десять — home pagination URL. Следовательно, query-state policy неоднородна и должна нормализоваться отдельно по route family; эти исключения не считаются утвержденными landing owners.
- **Контрдоказательство:** само существование URL фильтра не является ошибкой; они нужны UX и позволяют делиться состоянием. Ошибка — смешение пользовательского фасета с SEO-перелинковкой и отсутствие четкой границы между ограниченным набором indexable landing pages и всеми остальными состояниями.
- **Безопасное решение:** оставить фильтры рабочими, но разделить URL на два класса. Редакционные ссылки и SEO-чипы должны вести только на опубликованные path landing pages с доказанным спросом и уникальной ценностью (`/catalog/<category>/<color>/`). Неутвержденные комбинации остаются UX-состояниями `noindex`; их нельзя массово размещать в нижних SEO-блоках. После удаления внутренних SEO-ссылок и проверки деиндексации определить закрываемые параметрические паттерны для Googlebot; не закрывать их robots.txt раньше, чем Google увидит `noindex`.
- **Acceptance check:** crawl из indexable URL не находит editorial links на неиндексируемые фасеты; все разрешенные landing pages self-canonical, `200`, содержат уникальный интент/товары/копирайт; пустые и бессмысленные комбинации возвращают `404`, а не мягкий `200`; Search Console показывает сокращение обхода параметров без выпадения товаров.

#### FIND-002 — noindex-фильтры публикуют hreflang на другие noindex-фильтры, хотя canonical указывает на базовую категорию

- **Вердикт:** подтверждено в production.
- **Приоритет:** P2.
- **Evidence:** `/catalog/tshirts/?color=black` отдает canonical `https://twocomms.shop/catalog/tshirts/`, но `hreflang` ведут на `.../catalog/tshirts/?color=black`, `.../ru/catalog/tshirts/?color=black` и `.../en/catalog/tshirts/?color=black`. Аналогично ведет себя `?fit=oversize`. Все эти URL получают `noindex, follow`.
- **Кодовая причина:** глобальный `language_alternates` сохраняет query string для всех страниц, а `base.html` безусловно выводит четыре alternate-ссылки. `catalog.html` меняет robots/canonical для фасета, но не подавляет hreflang.
- **Почему это проблема:** одна страница одновременно сообщает: «не индексировать», «канонический документ — базовая категория» и «языковые аналоги — эти же параметрические URL». Google в итоге игнорирует часть сигналов, а диагностические инструменты могут считать кластер непоследовательным. Это не P0 и не причина автоматической санкции, но создает лишний граф URL и затрудняет анализ hreflang.
- **Безопасное решение:** для `noindex` search/facet страниц не выводить SEO-hreflang вовсе либо выводить только canonical indexable эквиваленты, если это подтверждено правилами выбранной архитектуры. Пользовательский переключатель языка можно оставить: UI-ссылки и SEO `rel=alternate` — разные контракты.
- **Acceptance check:** на фасетах остается `noindex, follow` + canonical на базовую страницу, но нет alternates на неканонические noindex URL; на всех indexable UA/RU/EN страницах reciprocal hreflang остается полным и self-consistent.

#### FIND-011 — `?page=1` категорий отвечает `200` как дубль чистого URL вместо прямой нормализации

- **Связь с презентацией:** подтверждает актуальную часть слайда 23, но не доказывает показанные там цепочки редиректов.
- **Вердикт:** подтверждено для `https://twocomms.shop/catalog/hoodie/?page=1` и home `/?page=1`; `/catalog/`, остальные категории и locale route families требуют отдельной матрицы.
- **Приоритет:** P3 самостоятельно, P2 в составе очистки pagination/crawl paths.
- **Evidence:** URL с `?page=1` отвечает `200`, `index,follow`, отдает тот же title/description/H1 и тот же большой SEO-блок, что `/catalog/hoodie/`, а canonical указывает на чистый `/catalog/hoodie/`. Следовательно, canonical консолидация есть, но crawler все равно загружает полный HTML-дубль. `?page=2` при этом корректно self-canonical и имеет page-specific title/description.
- **Кодовая причина:** canonical-шаблон правильно исключает `page=1`, но ранняя нормализация `page=1 -> clean URL`, существующая в части catalog view, не применяется ко всем category routes.
- **Почему это влияет:** canonical является подсказкой, а не предотвращением обхода. Внутренние/внешние `?page=1` ссылки добавляют лишний crawl hop и отдельный URL в отчетах, хотя самостоятельного состояния страницы нет. Это не duplicate-content penalty и не P0.
- **Безопасное решение:** постоянным одноступенчатым redirect нормализовать только валидный `page=1` на тот же path без этого параметра, сохранив остальные допустимые фильтры в утвержденном порядке. Не перенаправлять `page>=2` на первую страницу и не каноникалить их на page 1: они содержат другие товары.
- **Acceptance check:** все category/home/catalog routes дают один переход `?page=1 -> clean equivalent`; `page=2+` остаются доступными, self-canonical и связаны crawlable pagination; redirect не теряет разрешенные параметры и не создает цепочку.

### 5.2. Canonical, hreflang, пагинация, фасеты и варианты

#### FIND-006 — реальная индексируемая variant-поверхность втрое больше sitemap и не имеет единого owner-контракта

- **Вердикт:** подтверждено в production и коде для масштаба, discovery и несогласованной variant identity. Сам формат отдельного variant URL не является ошибкой; решение, какие варианты должны оставаться самостоятельными owner URL, условно и требует demand/inventory/media evidence.
- **Приоритет:** P1 для инвентаризации и единого owner/resolver contract; не удалять и не индексировать URL массово по одному duplicate-report.
- **Масштаб sitemap:** live `sitemap-product-variants.xml` содержит 210 URL: 78 color-only, 59 fit-only и 73 color-fit. Это 71 товар; 41 товар имеет один variant URL, 22 — пять, семь — восемь и один — три. Sitemap содержит только украинские URL, хотя каждая страница публикует UA/RU/EN hreflang.
- **Полный crawl scale:** crawl `output/seo-remediation-2026-08-11/task1-live-e20ec393-20260811T005452Z/crawl/pages.json` содержит 843 indexable `200` self-canonical product URL: 213 base PDP (71 UK + 71 RU + 71 EN) и 630 variant PDP (210 UK + 210 RU + 210 EN). То есть RU/EN variant URL не заявлены в variant sitemap как `loc`, но доступны через hreflang/internal discovery и являются самостоятельными self-canonical index targets.
- **Ownership inventory:** 64/78 color paths принадлежат товарам с единственным/default color и эквивалентны base state. Все 59 fit-only URL не имеют fit-owned media и полноценного locale layer. Все 73 color×fit URL — Cartesian states без `VariantCombinationProfile`, combination-owned content/media и устойчивого combination ID. Следовательно, **196/210 UK paths и 588/630 locale URL сейчас доказанно UI-only/base-owned** по product-data contract, независимо от duplicate counts.
- **Только кандидаты:** 14 UK color paths у семи multi-color товаров (`bentejne-ts`, `death-gbs-ass-ts`, `kharkiv-district-ts`, `lord-of-the-lending`, `my-little-baby`, `pojuy-ts`, `where-mi-present-ts`, каждый в `black` и `coyote`) имеют color media и могут рассматриваться как 42 locale multi-page candidates. Ни один пока не approved owner: GSC/query/backlink demand отсутствует. Прямая перепроверка SSR payload подтверждает неверный initial hero ровно на семи URL: `bentejne-ts/coyote`, `death-gbs-ass-ts/coyote`, `kharkiv-district-ts/coyote`, `lord-of-the-lending/black`, `my-little-baby/black`, `pojuy-ts/black`, `where-mi-present-ts/black`; OG и selected variant payload при этом уже указывают другой color asset.
- **Непересекающаяся формула множеств:** `210 semantic paths × 3 locales = 630 current self-canonical locale URLs`. Из них `196 UI/base-owned paths × 3 = 588 locale URLs`; остаток `14 candidate color paths × 3 = 42 locale URLs`. Число `7` — не новое подмножество owners и не вычитается из `14`: это семь вручную проверенных UK URL внутри candidate set с доказанным wrong initial SSR hero. Их соответствующие RU/EN instances должны пройти отдельную matrix-проверку, а не считаться автоматически подтвержденными.
- **Duplicate diagnostics:** среди 630 variant URL 383 URL входят в 93 duplicate-title clusters (max 9), те же 383 — в 93 duplicate-description clusters (max 9), 507 — в 72 duplicate-H1 clusters (max 16). Двадцать один title cluster охватывает более одной локали и содержит 92 URL. Это диагностические показатели ownership/localization drift, а не пороги или автоматическая санкция Google.
- **Контрольный пример:** `/product/classic-tshirt/black/`, `/product/classic-tshirt/black/classic/` и `/product/classic-tshirt/black/oversize/` имеют разные self-canonical URL, но одинаковые title «Футболка класична — купити футболку TwoComms», description и H1. Fit-only `/classic/` и `/oversize/` получают разные fit-meta, то есть проблема проявляется именно при активном цвете.
- **Кодовая причина:** `services.variant_meta.build_variant_meta()` сначала создает комбинированные meta для `color + fit`, после чего `views/product.py` может заменить их color-owned `active_variant_entry.seo_*`. `ProductVariantSitemap` включает Cartesian product, а `index_targets.build_product_variant_urls()` строит только 137 one-segment paths × 3 locales и пропускает все 73 combos × 3. Meta, sitemap, internal target, schema and cart therefore do not share one exact variant snapshot.
- **Почему это влияет:** self-canonical и hreflang сообщают Google, что каждая комбинация является самостоятельным документом, но sitemap, metadata, selected state и locale ownership описывают поверхность по-разному. Это увеличивает число конкурирующих owner candidates и объем обхода. Совпадающие title/H1 сами по себе не доказывают санкцию: проблема подтверждается только там, где URL обещает отдельный color/fit/locale state, а metadata/media/schema/state его не отличают или описывают неверно.
- **Контрдоказательство:** отдельные URL вариантов разрешены Google и полезны, если реально предвыбирают согласованные изображения, цену, наличие и содержат самостоятельную ценность. Поэтому решение «все варианты закрыть» было бы таким же необоснованным, как нынешнее «все комбинации индексировать».
- **Безопасное решение:** текущий доказанно безопасный owner для 196/210 paths — base PDP; селектор может сохранять UI state без отдельного search intent. Решение по 14 кандидатам заморозить до GSC/query/backlink review. Если они подтверждены, публиковать только exact color owners с truthful short facts и full SSR/schema/identifier parity; не возвращать Cartesian rule. Только после owner mapping менять sitemap, internal links, canonical or redirects.
- **Acceptance check:** owner inventory охватывает все 630 locale URL; ни один URL не меняет статус без GSC/backlink review; каждый отдельный owner предвыбирает и честно описывает заявленные оси уже в SSR, использует real stable identifiers и согласованные image/price/availability/cart/schema/feed; duplicate-report остается regression diagnostic, а не требованием переписать все title/H1/body.

#### FIND-029 — девять variant URL используют один keyword-stuffed украинский title во всех локалях

- **Вердикт:** подтверждено по live crawl; это конкретная ошибка source metadata, а не эвристика длины title.
- **Приоритет:** P1 как узкий low-risk locale/content fix после regression test.
- **Evidence:** UK/RU/EN URL `/product/futbolka-posmikhnys/beige/`, `/beige/classic/` и `/beige/oversize/` — всего девять self-canonical indexable URL — имеют один и тот же title длиной 160 символов: `молочна футболка з написом, футболка, футболка з принтом, купити футболку, футболка oversize, бежева футболка, унісекс футболка, футболка з написом, молочна фут`. EN и RU версии сохраняют украинский comma-list без локализации.
- **Почему это проблема:** title выглядит как список запросов, повторяет одни и те же слова, обрывается внутри слова и не сообщает четко product/color/fit owner. На RU/EN он одновременно является wrong-language metadata. Ошибка подтверждается содержанием; сам по себе предел 160 символов не является универсальным правилом Google.
- **Безопасное решение:** исправить исходное variant SEO-поле один раз, затем генерировать короткий описательный title из реального product/color/fit owner в активной локали. Не запускать sitewide rewrite по длине и не добавлять синонимы ради плотности/уникальности.
- **Acceptance check:** девять URL больше не содержат comma-list/обрыв; UK/RU/EN title соответствует локали и фактически выбранным осям; остальные title не меняются; browser-selected state, canonical, price, image и cart identity сохраняются.

#### FIND-031 — порядок и регистр variant-сегментов создают дополнительные self-canonical owners

- **Вердикт:** подтверждено live GET и parser code; это независимый URL-normalization defect.
- **Приоритет:** P1/P2, потому что исправление детерминировано и не требует решения, какие variants индексировать.
- **Evidence:** `/product/my-little-baby/black/oversize/` и `/product/my-little-baby/oversize/black/` оба отвечают `200` и self-canonical на себя. Варианты с uppercase `/BLACK/OVERSIZE/` и `/OVERSIZE/BLACK/` также отвечают `200` и self-canonical. Parser распознает сегменты независимо от порядка, а canonical наследует raw `request.path`.
- **Вторичный риск:** color slugs резервируют size tokens, но не fit tokens; parser priority `size -> color -> fit` делает будущие collisions неоднозначными. Internal links используют основной порядок, но внешняя или ручная ссылка способна создать новые owner aliases.
- **Безопасное решение:** один shared path normalizer определяет lower-case и стабильный порядок `color/fit/size`; любой эквивалентный alternate path дает один-hop `301` на normalized URL с сохранением выбранного состояния. Невалидные, повторные или конфликтующие сегменты дают `404`, а не частично примененный variant.
- **Acceptance check:** для каждой перестановки/регистра существует ровно один final owner; canonical совпадает с normalized final URL; redirect одношаговый; duplicate/ambiguous segments `404`; selected image/price/availability/cart state после нормализации не меняются.

#### FIND-007 — size UI-state публикует hreflang как самостоятельный locale owner, а legacy redirect теряет выбранный цвет

- **Вердикт:** частично подтверждено для `/product/classic-tshirt/m/` и кода общего маршрута. `index,follow` с canonical на base сам по себе допустим как duplicate consolidation; подтвержденные дефекты — hreflang на noncanonical size states и потеря валидной оси legacy redirect.
- **Приоритет:** P2.
- **Evidence:** `?size=M` отвечает постоянным redirect на `/product/classic-tshirt/m/`. Конечный URL отвечает `200`, публикует title с размером M и `robots=index, follow`, но canonical указывает на `/product/classic-tshirt/`. Hreflang при этом ведет на `/m/`, `/ru/.../m/` и `/en/.../m/`, то есть повторяет неканонический URL в трех языковых кластерах. Size URL отсутствуют в sitemap, но остаются crawlable.
- **Дополнительный legacy-дефект:** redirect-код принимает цвет только как числовой ID. Запрос `?color=black&fit=oversize` молча теряет `color=black` и перенаправляет только на `/oversize/`. Это не доказывает проблему современного path-селектора, но ломает ожидаемое состояние старых/внешних slug-query ссылок.
- **Почему это влияет:** canonical объявляет base владельцем, а hreflang одновременно формирует отдельный кластер `/m/` в трех языках. Это затрудняет ownership diagnostics и размножает non-owner locale states. Потеря `color=black` меняет товарное состояние для пользователя и может вести внешнюю ссылку не на тот вариант.
- **Безопасное решение:** выбрать один контракт. Для UI-only size deep link допустим `200`, ordinary crawlability и canonical base, но без SEO-hreflang на non-owner paths; blanket `noindex + canonical` не применять, потому что Google не рекомендует `noindex` как способ выбора canonical. Indexable size owner возможен только при самостоятельном спросе, точном offer/availability/identifier contract и полезной ценности. Legacy resolver должен сохранить все валидные оси или явно отклонить запрос.
- **Acceptance check:** canonical owner и hreflang cluster не противоречат друг другу; все size-bearing paths используют одну policy; legacy redirect сохраняет color/fit/size либо возвращает однозначный ответ; тест не требует `noindex` там, где canonical consolidation достаточно.

#### FIND-018 — восемь RU/EN color landing индексируются с украинским основным контентом

- **Вердикт:** подтверждено на всех восьми `/ru/` и `/en/` URL из `sitemap-color-categories.xml`.
- **Приоритет:** P1, потому что дефект затрагивает весь неукраинский кластер четырех опубликованных color landing.
- **Evidence:** страницы для black tshirts, black hoodie, black long-sleeve и coyote tshirts отвечают `200`, `index,follow` и self-canonical в трех языках. Но у всех RU/EN версий title, description, H1, editorial-текст и FAQ совпадают с украинской версией. `html lang` и `Content-Language` меняются, видимый основной контент — нет. Google определяет язык прежде всего по видимому содержимому, а не по префиксу URL или атрибуту `lang`.
- **Почему это влияет:** `/ru/` и `/en/` обещают самостоятельный языковой документ, но не выполняют это обещание. Возможны выбор неправильной языковой версии, слабая релевантность англо- и русскоязычным запросам, игнорирование части hreflang-кластера и плохой post-click UX. Это не доказательство duplicate-content penalty.
- **Безопасное решение:** сделать публикацию locale независимым состоянием. Для каждой indexable версии обязательны локализованные title, description, H1, основной editorial, фактические характеристики и FAQ. Переводить интент и понятные покупателю формулировки, не названия бренда и не выдуманные характеристики. До готовности конкретную locale-версию нельзя включать в sitemap как равноправную indexable страницу.
- **Acceptance check:** для всех 12 landing `html lang`, HTTP language, title, description, H1, editorial, FAQ и schema согласованы; автоматический language detector определяет целевой язык по main content; normalized body не совпадает между UK/RU/EN; publish gate не выпускает непереведенную locale.

#### FIND-019 — HTML hreflang color landing ломает UK/x-default на RU и EN версиях

- **Вердикт:** подтверждено на всех восьми RU/EN color landing; XML sitemap при этом содержит правильную матрицу.
- **Приоритет:** P1 в связке с FIND-018.
- **Evidence:** UK-страница правильно указывает `uk-UA` на unprefixed URL, `ru-UA` на `/ru/`, `en-UA` на `/en/`, `x-default` на UK. На RU-странице и `uk-UA`, и `x-default` ошибочно указывают на RU URL; на EN — на EN URL. Следовательно, reverse annotations несимметричны, а HTML и sitemap сообщают разные кластеры.
- **Кодовая причина:** `category_color_landing.html` переопределяет `hreflang_uk` и `hreflang_x_default` текущим `canonical_url`, хотя общий `language_alternates` уже строит locale paths. Существующий тест проверяет sitemap, но не HTML каждой локали.
- **Почему это влияет:** Google может проигнорировать несогласованный hreflang-кластер или выбрать не ту языковую страницу. Hreflang не повышает ranking сам по себе, но помогает отдавать правильный локализованный URL.
- **Безопасное решение:** использовать один генератор абсолютной матрицы alternates для HTML и sitemap; `x-default` стабильно указывает на утвержденную default UK-страницу. Не строить alternates из текущего canonical без перевода locale path.
- **Acceptance check:** каждый из 12 URL публикует один и тот же набор четырех абсолютных адресов; self-reference присутствует ровно один раз; reciprocity UK/RU/EN полная; HTML и XML byte-for-byte согласованы после нормализации порядка.

#### FIND-020 — black color landing разных категорий почти не имеют самостоятельного контента

- **Вердикт:** подтверждено exact-hash и near-duplicate сравнением production HTML.
- **Приоритет:** P1/P2 после исправления языков и hreflang.
- **Evidence:** editorial у black tshirts и black hoodie является exact duplicate во всех трех языках; similarity tshirts против long-sleeve равна `0.998` и отличается в основном устаревшим числом моделей. FAQ идентичен на девяти black URL и одновременно рассказывает о футболках, лонгсливах и худи на каждой узкой странице. В текстах остаются межкатегорийные фразы про хлопок или трехнитку для худи, общий диапазон regular/oversize и S–XXL, который не вычисляется по конкретному ассортименту.
- **Кодовая причина:** seed получает `cat_slug`, но банки lead/production/wear и FAQ почти не используют категорию; повторный `seed_color_landings --apply` способен перезаписать ручной approved copy. Guard проверяет длину raw HTML, а не язык, фактическую уникальность и смысл.
- **Почему это влияет:** отдельные URL конкурируют за близкий intent, не объясняя различие категории, ткани, посадки и ассортимента. Наиболее вероятный эффект — слабая индексация, кластеризация и каннибализация, а не автоматическая санкция.
- **Безопасное решение:** строить brief по матрице `category × color`: реальный ассортимент и темы принтов, материал именно категории, доступные fit/size из БД, поведение цвета на этой ткани, уход и 2–4 уместных вопроса. Полезный короткий текст лучше длинного шаблона. Seed должен создавать draft и не перезаписывать approved copy без явного флага; exact duplicate должен блокировать publish, высокий similarity — отправлять на ручную проверку.
- **Acceptance check:** между indexable landing разных `category × color` нет exact duplicate; редакционный similarity-report и fact lint пройдены; FAQ относится только к выбранной категории; изменение ассортимента не оставляет ложных универсальных claims.

#### FIND-021 — сохраненные числа товаров расходятся с live queryset, а publish eligibility не единообразна

- **Вердикт:** подтверждено на 9 из 12 landing; это content-truth и архитектурный defect.
- **Приоритет:** P1/P2.
- **Evidence:** в editorial указано 24 black tshirts, 24 black hoodie и 18 black long-sleeve, тогда как live paginator и `ItemList.numberOfItems` показывают 23, 23 и 17. Coyote tshirts пока совпадает: 7. Seed агрегирует варианты без того же полного published-scope, что использует view; sitemap eligibility и view eligibility также опираются на разные условия.
- **Почему это влияет:** видимый текст противоречит товарной выдаче и schema, устаревает после publish/unpublish и снижает доверие. Разные eligibility-правила способны оставить URL в sitemap после исчезновения допустимого ассортимента либо, наоборот, скрыть живой landing.
- **Безопасное решение:** не сохранять mutable count внутри prose; выводить число из того же authoritative queryset, что карточки и schema, с корректной pluralization. Один policy/service должен решать `published/indexable/sitemap/internal-link eligible`; операция publish/unpublish обязана атомарно обновлять все surfaces.
- **Acceptance check:** visible count, paginator, ItemList и DB published scope равны после добавления/снятия товара без reseed; URL с недостаточным ассортиментом получает предсказуемый статус и исчезает из sitemap/SEO rails; тесты используют одну eligibility-функцию.

#### FIND-022 — пагинация color landing canonical-ится на page 1, а заведомо несуществующие страницы отвечают `200`

- **Вердикт:** подтверждено на black landing с двумя страницами и `?page=999999`.
- **Приоритет:** P1/P2 для crawl correctness.
- **Evidence:** `?page=2` отвечает `200`, показывает другой набор товаров, но canonical указывает на первую clean страницу. `?page=999999` также отвечает `200` и фактически показывает последнюю страницу. Это позволяет генерировать неограниченное множество успешных URL одного состояния.
- **Почему это влияет:** Google рекомендует self-canonical для каждой полезной страницы пагинации. Canonical на page 1 может скрыть товары второй страницы как самостоятельный crawl document, а infinite `200` раздувает URL-space и создает soft-duplicate behavior.
- **Безопасное решение:** valid `page>=2` оставлять `200`, indexable и self-canonical с crawlable previous/next links; `page=1` нормализовать на clean URL; ноль, отрицательные, нечисловые и сверхдиапазонные pages возвращать `404`, не clamping к последней странице. Большой editorial показывать только на page 1.
- **Acceptance check:** каждая реальная страница серии имеет self-canonical и уникальный набор карточек; `page=1` дает один redirect на clean URL; `page=999999`, `0`, отрицательные и нечисловые значения дают `404`; crawler достигает каждого товара без infinite URL family.

### 5.3. Каталоги, категории и внутренняя перелинковка

#### FIND-017 — внутренние ссылки на 25 dead destinations устранены; external redirect mapping остается отдельным условным исследованием

- **Вердикт:** исходная проблема была подтверждена crawl 2026-08-10 и исправлена/развернута в `e20ec393`; текущий live crawl подтверждает `0 linked 404`.
- **Историческое evidence:** crawl 2026-08-10T21:11:36Z обработал 1 787 страниц и нашел 25 `404` с внутренними ссылками: stale `/catalog/custom-print/` и 24 legacy `/product/{33,36,39,42,45,46,48,49,50,51,52,91-106}/`. Ни один не находился в sitemap.
- **Текущее evidence:** crawl `output/seo-remediation-2026-08-11/task1-live-e20ec393-20260811T005452Z/crawl/` получил 1 354 ответа `200`, zero linked `404`, а stale numeric/custom-print destinations больше не имеют internal inlinks. Product references разрешаются в текущий locale-aware slug; missing/draft/malformed rows не рендерятся.
- **Граница исправления:** Custom Print не менялся; исправлена только внешняя ссылка каталога. Для 24 numeric URL external backlink/GSC/analytics history не исследована, поэтому redirect decision отсутствует. Это не блокирует и не отменяет завершенный internal-link fix.
- **Оставшееся условное действие:** только при наличии external history построить exact `old ID -> published successor` mapping. Exact successor может получить one-hop `301`; без successor остается честный `404/410`. Blanket redirect на base/category запрещен.
- **Acceptance achieved:** `0 linked 404`; sitemap не содержит `404`; internal fix deployed. External redirect mapping имеет отдельный open status и не используется для формулировки, будто Task 1 не выполнен.

#### FIND-023 — clean color landing почти не получают ссылок из соответствующих категорий, а locale-ссылки возвращают RU/EN пользователя на UK

- Вердикт: подтверждено по девяти категориям, 12 color landing и соответствующим query-фасетам.
- Приоритет: P1/P2; исправлять после определения URL ownership, не меняя работу Smart Selector.
- Evidence: в категориях tshirts, hoodie, long-sleeve на UK/RU/EN найдено ноль прямых ссылок на четыре опубликованных clean landing. Вместо них UK tshirts публикует 34 ссылки ?color=, RU/EN — по 32; hoodie и long-sleeve — по 20–22. На соответствующих color-фасетах также ноль clean-landing links и 43–57 параметрических ссылок. Color landing не полностью orphan: на них ссылаются части PDP SEO chips, но helper строит unprefixed URL; sibling/cross-category ссылки RU/EN также ведут на UK и используют украинские anchors.
- Кодовая причина: для Smart Selector caller передает category=None в build_available_colors, отключая предусмотренный сервисом переход на landing. CategoryColorLanding.get_absolute_url() жестко строит URL без locale; PDP keyword helper делает то же самое.
- Почему это влияет: crawl и внутренний вес направляются на noindex query URL, а утвержденные self-canonical страницы получают слабый contextual in-degree. Языковой переход на UK нарушает пользовательский путь и ослабляет locale-кластер. Это не означает, что весь новый мобильный selector нужно отменить.
- Безопасное решение: сохранить интерактивные query-state controls, но добавить отдельные crawlable contextual links к опубликованным same-locale landing из category intro/SEO navigation и уместных PDP. Одиночную ?color= SEO-ссылку заменять clean path только когда landing опубликован и проходит eligibility. URL строить через locale-aware reverse; комбинации color x fit x city не создавать автоматически.
- Acceptance check: каждый clean landing имеет хотя бы одну обычную ссылку из соответствующей same-locale категории; RU/EN sibling и PDP links остаются в том же языке; editorial crawl не находит ссылку на single-color noindex facet, если существует утвержденный landing; Smart Selector и back/forward state работают без регрессий.

#### FIND-003 — главный H1 общего каталога меняет intent между desktop и mobile-first рендером

- **Вердикт:** подтверждено реальным browser render; первоначальная гипотеза «два одновременно видимых H1» опровергнута.
- **Приоритет:** P2 из-за mobile-first семантики и недавнего редизайна общего каталога.
- **Evidence desktop 1440×900:** source DOM содержит H1 «Нова колекція вже тут» и H1 «Каталог одягу TwoComms», но первый имеет нулевую геометрию и отсутствует в accessibility snapshot. Единственный видимый/доступный H1 — «Каталог одягу TwoComms».
- **Evidence mobile 390×844:** ситуация зеркальная. H1 «Нова колекція вже тут» видим и является единственным H1 accessibility tree; `catalog-hero__title` «Каталог одягу TwoComms» имеет нулевую геометрию. Основной список категорий подписан только H2 «Каталог».
- **Нюанс:** несколько H1 в source сами по себе допустимы, а responsive `display:none` не является скрытым-text spam, если контент честно соответствует разным layout. Проблема здесь конкретнее: URL, title и canonical принадлежат каталогу, но мобильный основной heading принадлежит временной промо-кампании. Google использует mobile-first indexing, поэтому важный on-page intent на мобильном рендере слабее и нестабилен при смене кампании.
- **Безопасное решение:** сохранить один стабильный H1 «Каталог одягу TwoComms» в обеих responsive-композициях. «Нова колекція вже тут» оставить визуально сильным промо-H2/текстом. Не требуется визуально унифицировать desktop и mobile или ломать компактный mobile layout.
- **Acceptance check:** при 390×844 и 1440×900 accessibility tree содержит стабильный H1 каталога; промо остается видимым, но не перехватывает document-level heading; category cards, hero и first viewport не получают layout regressions.

### 5.4. Карточки товаров, цвета, посадки и размеры

#### FIND-024 — active swatch в отфильтрованных карточках иногда противоречит изображению и URL

- Вердикт: подтверждено в 15 карточках на шести query-фасетах; основной image и PDP URL при этом выбирают правильный цвет.
- Приоритет: P2 как UX/accessibility defect, P3 по прямому SEO-влиянию.
- Evidence: на black tshirts два товара в каждом языке отмечают coyote как aria-pressed=true; на coyote tshirts три товара в каждом языке отмечают black. Всего пять уникальных product/color states и 15 locale instances. Hoodie black и long-sleeve black контроль ошибки не показали.
- Кодовая причина: карточка считает active через v.is_default или первый элемент, а не сравнивает v.slug с рассчитанным p.preferred_color_slug. Основная ссылка карточки использует preferred slug корректно.
- Почему это влияет: изображение и URL обещают один цвет, доступное имя/pressed state — другой. Это ухудшает доверие, выбор варианта и доступность.
- Безопасное решение: выбрать единственный authoritative selected-color slug и использовать его для image, href, swatch state, label, analytics payload и schema. Default применять только если явного state нет.
- Acceptance check: на каждой карточке ровно один aria-pressed=true; его slug, main image, card href и выбранное состояние PDP совпадают; проверены UK/RU/EN, чистая категория, query-фасет и clean landing.

#### FIND-025 — variant-specific content layer существует, но фактически пуст и всегда наследует base product

- Вердикт: подтверждено production-БД и resolver chain.
- Приоритет: P1/P2 вместе с FIND-006; это основание определить owners, а не требование заполнить контентом все 210 semantic paths или 630 locale URL.
- Evidence: в публичном scope 78 color variants. VariantDetails существует только для трех записей, но display_name, marketing_html, seo_title, seo_description и seo_keywords пусты во всех; VariantDetailsI18n=0, VariantFAQ=0, ProductOptionProfileI18n=0, VariantCombinationProfile=0. Эффективные display/description/marketing/SEO/OG значения наследуются из base product. Шесть непереведенных families создают 28 semantic paths, поэтому украинский fallback затрагивает 56 RU/EN indexable variant URL, а не только шесть страниц.
- Почему это влияет: путь, sitemap и self-canonical утверждают самостоятельность варианта, но content ownership отсутствует. Это усиливает дубли meta/H1 и делает массовый color-fit long-tail формальным. Само наследование корректно для UI-варианта; дефект возникает, когда state объявлен отдельной indexable страницей.
- Безопасное решение: сначала утвердить owner decision. Для подтвержденного multi-page owner заполнить только реальные variant facts, изображение, offer/availability и краткий полезный ответ на запрос. Остальные состояния сохранить в selector и согласовать с base owner после GSC/backlink review. Не генерировать фиктивные тексты, SKU или GTIN.
- Acceptance check: у каждого отдельного owner есть запись intent/owner/source и самостоятельный selected-state payload; UI-only комбинации не продвигаются sitemap/editorial links как отдельные long-tail pages; никакой процент text uniqueness не является gate.

#### FIND-026 — 48 из 78 color variants не имеют color-specific image, а alt-локализация почти отсутствует

- Вердикт: подтверждено production-БД; критично только для variant URL, оставленных indexable.
- Приоритет: P1 для indexable variant allowlist, P2 для общего merchandising/accessibility.
- Evidence: только 30 из 78 color variants имеют хотя бы один ProductColorImage; 48 не имеют ни одного. Из 82 color-image rows только 29 содержат непустой direct alt_text, 32 имеют NULL, 21 — пустую строку; VariantImageAltI18n=0. Fallback alt может быть синтезирован шаблоном, но это не создает фотографию выбранного цвета. Даже среди 14 strongest multi-color candidates семь alternate-color URLs до выполнения JS показывают server-rendered base/default hero, тогда как OG/JSON-LD уже используют selected color media.
- Почему это влияет: отдельный color URL должен показывать выбранный variant. Base image снижает image relevance и доверие, а синтетический alt может неверно описывать фотографию. Пустой alt у декоративного изображения допустим.
- Безопасное решение: утверждать отдельный color/fit owner только при правдивом selected-state media или документированной визуальной идентичности. Alt описывает конкретное informative image на языке страницы, а не список ключей; декоративное изображение может иметь пустой alt. SSR hero, hydrated gallery, OG и Product JSON-LD используют тот же approved asset.
- Acceptance check: каждый отдельный variant owner имеет корректное selected image уже в SSR, accurate localized alt where informative, согласованные hero/OG/schema assets и visual QA; отсутствие variant media означает UI/base ownership, если нет доказанной визуальной эквивалентности.

#### FIND-027 — fit selector включен у всех товаров, хотя fit data есть менее чем у половины

- Вердикт: подтверждено как data/UX defect; само по себе не является ошибкой индексации.
- Приоритет: P2.
- Evidence: в public published scope 59 active ProductFitOption rows распределены только по 30 из 71 товаров; 13 rows не имеют description. У всех 71 товаров fit_selector_enabled=True, включая 41 товар без fit rows. Модель fit не зарегистрирована для полноценной modeltranslation-локализации. Общий DB count 67 относится к более широкому scope и не противоречит public count 59.
- Почему это влияет: пустой или формальный selector создает ложное ожидание доступного offer. Индексируемый fit URL без inventory, размеров, media и описания не получает самостоятельной ценности.
- Безопасное решение: включать selector только при реальных sellable rows; хранить localized label/description, измерения, availability и media. Fit URL включать в indexable allowlist только при отдельном спросе и полной selected-state согласованности; иначе fit остается состоянием base PDP.
- Acceptance check: ни один товар не показывает selector при нуле rows; каждый sellable fit имеет локализованные данные, измерения, наличие и media; sitemap содержит только approved fit owners.

#### FIND-008 — Product schema связывает цветовой вариант с объектом Product, а не ProductGroup; fit-варианты в группу не включены

- **Вердикт:** подтверждено на representative PDP; влияет на качество variant structured data, но не является автоматическим нарушением Product rich result.
- **Приоритет:** P2/P3 после решения FIND-006.
- **Evidence:** base `/product/classic-tshirt/` публикует `@type: Product` с `@id .../#product`; variant pages могут ссылаться `isVariantOf` на base Product, а fit-only не моделирует fit identity. Отдельный ProductGroup builder включен только для семи multi-color products, но его `hasVariant` содержит только два color nodes, хранит все sizes одной строкой и не моделирует fit combinations. Live `my-little-baby` group использует synthetic `TC-4-coyote`/`TC-4-black`, тогда как реальные `/coyote/` и `/black/` Product pages обе отдают `sku=TC-4`, `mpn=TC-4`. Один URL/entity получает несовместимые identifiers в двух графах.
- **Почему это важно:** Google допускает single-page и multi-page варианты, но ожидает согласованную модель группы: устойчивый `ProductGroup`/`productGroupID`, `variesBy`, `hasVariant` или `isVariantOf`, а variant URL должен выбирать соответствующее состояние. Текущий граф моделирует только цвет, пропускает fit и указывает `isVariantOf` на сущность другого типа; Google может проигнорировать группировку, даже если обычный Product rich result остается валидным.
- **Безопасное решение:** сначала утвердить variant ownership. Затем либо публиковать один canonical ProductGroup с реальными concrete purchasable combinations and stable identifiers, либо для exact approved color pages моделировать только реально отличающийся color и не заявлять неподтвержденные fit/size entities. Product page и ProductGroup обязаны использовать один identifier source. Не генерировать фиктивные SKU/GTIN/MPN.
- **Acceptance check:** Rich Results/schema validator не показывает типовые несоответствия; все indexable варианты одной группы используют один group ID, корректные variant URLs и согласованные color/fit/image/offer/availability; неиндексируемые состояния не раздувают `hasVariant` без пользы.

#### FIND-015 — self-canonical oversize PDP предвыбирает посадку, но показывает изображение с маркировкой classic

- **Вердикт:** подтверждено в mobile browser на `/product/classic-tshirt/black/oversize/`.
- **Приоритет:** P1/P2 для indexable variant-архитектуры: исправлять вместе с FIND-006, не генерируя фиктивные изображения.
- **Evidence:** URL отвечает `200`, `index,follow`, self-canonical; radio `Оверсайз` действительно checked. Одновременно основной визуал совпадает с base/classic (`/media/products/optimized/c3_480w.avif`), на самом изображении написано `T-SHIRT CLASSIC STYLE`, а alt остается общим «Футболка класична…». Product JSON-LD также использует `/media/products/c3.webp`, имя «Футболка класична», SKU `TC-1` и тот же Offer price. То есть URL утверждает самостоятельный oversize variant, но image/alt/schema не подтверждают выбранную посадку.
- **Почему это влияет:** Google прямо требует, чтобы отдельный multi-page variant URL предвыбирал и показывал соответствующий вариант. Несогласованный hero снижает доверие покупателя, ухудшает image relevance и лишает страницу самостоятельной ценности; тот же дефект усиливает дубли title/H1 из FIND-006.
- **Контрдоказательство:** пользователь заранее сообщил, что отдельные фото посадок еще есть не везде. Это объясняет данные, но не делает конкретный oversize URL качественной индексируемой landing page. Селектор функционально выбирает правильный fit, поэтому это не ошибка cart-state.
- **Безопасное решение:** индексировать color-fit URL только после появления согласованного media set и variant copy. До этого конкретную комбинацию оставить UX-состоянием с canonical на ближайшую правдивую сущность либо не публиковать в sitemap. Когда фото готово, хранить fit-aware gallery/alt/schema image в одном источнике варианта и использовать его во всех UI/schema/feed surfaces.
- **Acceptance check:** каждый indexable `/color/fit/` URL визуально отличается в hero/gallery, selected state, alt и Product image; контрольный oversize URL больше не показывает asset с маркировкой classic; отсутствующие media не заменяются вводящей в заблуждение картинкой.

### 5.5. Title, description, H1-H3 и поисковые интенты

#### FIND-004 — шаблон цветного SEO-H2 генерирует грамматически неверное «Чорне футболки»

- **Вердикт:** подтверждено в production для `/catalog/tshirts/?color=black`.
- **Приоритет:** P2 для шаблона/данных, P3 для текущего URL, потому что он `noindex`.
- **Evidence:** видимый H2 в production: «Чорне футболки TwoComms — український стрітвір з принтом».
- **Почему это важно:** ошибка показывает, что шаблон склеивает цвет и категорию без согласования числа/рода/падежа. Такой генератор нельзя безопасно использовать для будущих indexable color landing pages и масштабирования семантики.
- **Безопасное решение:** не пытаться автоматически склонять произвольные строки. Хранить локализованные формы категории и цвета для конкретного шаблона (`чорні футболки`, `чорне худі`, `чорний лонгслів`) либо полностью редакционный H1/title/H2 у каждой утвержденной landing page.
- **Acceptance check:** матрица `3 категории x все публичные цвета x 3 языка` проходит snapshot/grammar review; не остается шаблонов вида «цвет + категория» без языковой формы.

### 5.6. Тексты, шаблонность, каннибализация и переоптимизация

#### FIND-005 — RU/EN catalog имеют локализованные meta и SEO-тексты, но HTML остается частично украинским

- **Вердикт:** подтверждено в production; первоначальное предположение о полностью дублирующихся языковых копиях уже устарело, но перевод не завершен.
- **Приоритет:** P1/P2: общие EN/RU locale остаются индексируемыми, а на mobile смешанный язык занимает основной first viewport.
- **Evidence:** `/ru/catalog/` и `/en/catalog/` self-canonical, indexable и имеют локализованные title, description и основные SEO-H2. Одновременно обе страницы содержат украинские H1 «Нова колекція», H2 «Фільтри» и тексты Telegram-модала «Підтвердження Telegram», «Очікуємо ваш контакт у боті…», «Сесія завершилась». На `/ru/catalog/` основной H1 «Каталог одежды TwoComms», на `/en/catalog/` — «TwoComms clothing catalog», поэтому это не полный дубликат UA.
- **PDP evidence:** `/ru/product/classic-tshirt/` и `/en/product/classic-tshirt/` имеют локализованные title, description, H1 и основные коммерческие H2, но нижний SEO-блок и модал содержат украинские «Детальніше про…», «деталі моделі», «Повідомити про наявність», «Підтвердження Telegram». Следовательно, дефект общий для shared components, а не только каталога.
- **Rendered mobile evidence:** на self-canonical `/en/catalog/` при 390×844 title и `html lang=en-UA` корректны, но единственный видимый H1 — украинский «НОВА КОЛЕКЦІЯ ВЖЕ ТУТ». В first viewport украинскими остаются eyebrow, hero-copy, «Фільтри», badges «ХІТ/НОВИНКА», «Від … ₴», «В наявності», весь custom-print promo, три преимущества и половина bottom navigation. На английский переведены в основном `CATALOG`, названия трех категорий и `Favorites/Profile`. Это не единичная footer-строка, а основной mobile experience.
- **Почему это важно:** hreflang — не замена переводу. Смешанный язык ухудшает UX и снижает ясность языкового таргетинга; повторяющиеся глобальные компоненты также раздувают межъязыковое сходство.
- **Контрдоказательство:** отдельные непереведенные UI-строки не делают всю страницу автоматически некачественной и не требуют закрывать RU/EN от индекса. Значимы доля, расположение и повторяемость.
- **Безопасное решение:** инвентаризировать все видимые строки через message catalogs и DB-поля, отделить брендовые/непереводимые токены, заполнить RU/EN для навигации, фильтров, модалей, alt/aria и динамических сообщений. Не создавать машинно-шаблонные city pages ради объема.
- **Acceptance check:** language-specific crawl не находит UA-фразы в видимом тексте RU/EN, кроме утвержденного allowlist; `html lang`, title, H1, description, canonical и hreflang согласованы.

#### FIND-012 — шесть публичных товаров не имеют самостоятельной RU/EN-локализации и незаметно используют украинский fallback

- **Вердикт:** подтверждено production-БД и реальной цепочкой modeltranslation/Product Catalog.
- **Приоритет:** P1 для заполнения контента, P2 для контроля публикации.
- **Масштаб:** основные украинские поля заполнены у `71/71` опубликованных товаров. Самостоятельные RU и EN значения title, описаний, SEO title/description/keywords и большей части alt присутствуют только у `65/71`. Пустой перевод не обязательно оставляет страницу пустой: `django-modeltranslation` читает оригинальный атрибут через активный язык и настроенный fallback, поэтому посетитель видит украинский canonical content под RU/EN URL.
- **Кодовое доказательство:** `storefront/translation.py` регистрирует поля `Product` и прямо документирует fallback к украинскому. `product_catalog/content_resolution.py::_resolve_content_field()` для RU/EN последовательно проверяет выбранный язык, затем UK и в последнюю очередь `product:canonical`. В production для шести variant-контекстов источником локализованного содержимого становится `product:canonical`, а не самостоятельный RU/EN слой.
- **Почему это влияет:** URL, `html lang`, canonical и hreflang заявляют отдельную языковую версию, но основной товарный документ может остаться украинским. Это ухудшает понятность для пользователя, снижает различимость языкового кластера и дает Google слабое основание выбирать RU/EN URL для соответствующих запросов. Это не «duplicate penalty» и не повод закрывать все RU/EN от индекса; это незавершенная локализация индексируемых страниц.
- **Безопасное решение:** сделать заполненность обязательной на уровне publish-quality gate: title, короткое/полное описание, SEO title/description, ключевые фактические характеристики и основной alt должны иметь самостоятельные UK/RU/EN значения. Fallback оставить как аварийный UX-механизм, но не считать его готовым SEO-контентом. Не переводить названия коллекций и бренда механически, а продуктовые факты переводить редакционно и единообразно.
- **Acceptance check:** production-отчет по `71 x 3` продуктовым локалям показывает ноль fallback для обязательных полей; выборочная проверка RU/EN HTML не обнаруживает украинские абзацы в главном контенте; тест блокирует публикацию/индексацию локали с незаполненным обязательным набором.

#### FIND-012a — selected-color alt берется из одной украинской строки для всех локалей

- **Вердикт:** подтверждено текущим кодом и production HTML; это системный дефект локали, а не проблема отдельной фотографии.
- **Цепочка:** `get_detailed_color_variants()` передает `ProductColorImage.alt_text` в `build_product_image_alt()`. Helper без проверки активного языка немедленно возвращает сохраненный `alt_text`, поэтому RU/EN не используют локализованный `Product.main_image_alt` и не получают locale-safe fallback. Тот же payload используется для SSR hero, OG/Twitter alt и клиентского выбора цвета.
- **Production evidence:** `/ru/product/lord-of-the-lending/black/` и `/en/product/bentejne-ts/coyote/` отдают украинский selected-color alt (`Чорна футболка ...`, `Футболка ... кольору кайот ...`) при русской/английской странице. Это расходится с `lang`, title/H1 и hreflang.
- **SEO/GEO impact:** alt не является самостоятельным ranking lever, но это сигнал языка и описания изображения. Несогласованность ухудшает доступность, image-search relevance и доверие к locale cluster; она также дублируется в социальных preview metadata. Это не доказывает штраф или потерю позиций.
- **Безопасное исправление:** для RU/EN использовать reviewed locale-owned alt, если он существует; иначе строить короткий фактический fallback из уже локализованных `product.title`, color label и номера изображения. Не переводить SKU/brand names, не добавлять keyword lists и не переписывать украинский editorial alt для UK.
- **Acceptance:** rendered matrix сравнивает SSR `<img>`, OG и Twitter alt на representative color routes; RU/EN не содержат украинского stored alt, UK сохраняет редакторское значение, а selected asset/URL/price/cart identity не меняются.

#### FIND-012b — generated variant metadata публикует украинский текст и неподтвержденные claims на RU/EN

- **Вердикт:** подтверждено исходным кодом и live route examples; это общий generator defect, не задача `futbolka-posmikhnys`.
- **Цепочка:** `services/variant_meta.py` формирует title/description для fit и color+fit URL литеральными украинскими строками (`фіт`, `щільна бавовна`, `DTF-друк`, `доставка ... за 1–3 дні`, `Український streetwear`). `product_detail()` передает туда active RU/EN product title, поэтому одна страница смешивает локализованный title с украинским generated suffix/description. `page_keywords` дополнительно строит keyword list, хотя публичный `meta keywords` уже удален.
- **Production evidence:** `/ru/product/classic-tshirt/oversize/` title is `Футболка классическая — оверсайз фіт — TwoComms`, а description содержит украинские `щільна бавовна`, `DTF-друк` и `1–3 дні`; EN route contains the same Ukrainian suffix and description. The route is currently `index,follow` and self-canonical, so this is an indexable locale mismatch.
- **SEO/GEO impact:** Google documents localized alternates as fully translated page versions; untranslated main content is treated as duplicate/incorrect alternate rather than a ranking advantage. The claims also conflict with the unresolved fact-owner decision for delivery and material. This can create wrong-language snippets and makes hreflang less trustworthy; no ranking loss is asserted without GSC evidence.
- **Приоритет исправления:** first remove generated descriptions/keyword strings that have no reviewed source and make generated variant titles locale-aware; only then decide which variant URLs are approved owners. Do not replace them with paraphrases or a city/color/fit keyword matrix.
- **Acceptance:** UK variant behavior remains covered; RU/EN variant title/description contain no generated Ukrainian literals or unowned delivery/material claims, and the page falls back to the product's reviewed locale metadata when no variant-owned localized override exists.

#### FIND-012c — locale-safe size-grid comparison requires bounded code ownership

- **Вердикт:** standard PDP size-grid comparison had a confirmed RU/EN locale
  defect: active `classic` / `oversize` rows and color labels were read from
  Ukrainian storage and propagated into tabs, H3, image alt/figcaption and
  hidden table caption. This was fixed only for the two stable standard fit
  codes and known color vocabulary in `bde21af63`, production-proven in the
  subsequent `cf5108780` checkpoint.
- **Граница исправления:** `ProductFitOption` currently has only one
  editor-owned `label` and no persisted `label_ru` / `label_en` contract.
  Therefore an arbitrary custom fit must not be translated by guessing or by
  keyword substitutions. Unknown fit/color labels deliberately pass through
  until a real locale-owned editorial field and admin workflow exist.
- **Открытый связанный defect:** `_guide_copy()` still describes every guide
  as a T-shirt. For a non-T-shirt product with an active comparison this can
  make image alt/caption/note factually wrong even when language is correct.
  This is a separate garment-factuality task: first inventory active
  non-T-shirt grids and their garment owner, then add product-specific wording
  from an owned field. Do not mass-replace text with generic keyword copy.
- **SEO/GEO impact:** the shipped correction aligns existing localized page
  semantics and accessibility metadata; it does not create new index targets
  and is not a ranking guarantee. The open custom-fit/non-T-shirt items remain
  relevant only where those data configurations are published.

#### FIND-013 — каждый PDP получает два длинных SEO-блока, а второй fallback содержит смешанный язык, служебный SEO-текст и фактические противоречия

- **Вердикт:** подтверждено кодом и production HTML.
- **Приоритет:** P1: это одновременно content quality, доверие, локализация и риск переоптимизации.
- **Двойной рендер:** `templates/pages/product_detail.html` подряд вызывает `{% product_seo_block product %}` и подключает `partials/product_seo_landing.html`. Это два независимых генератора длинного body content после коммерческой части PDP. Поле `seo_bottom_html` пусто у `71/71` опубликованных товаров во всех языках, поэтому второй блок всегда строится программно через `product_seo_landing.build_landing()`.
- **Повторяемость не равна качеству:** `build_product_seo_block()` документирует целью снижение 5-gram overlap, выбирает альтернативные формулировки и порядок абзацев детерминированным hash по slug. Поэтому `71/71` exact-hash уникальны, а максимальный pairwise 5-gram Jaccard равен `0.295` UK, `0.293` RU и `0.327` EN. Это не положительный SEO-контроль: лексическая уникальность была достигнута независимо от достоверности фактов. Второй `build_landing()` имеет 15 пар `>=0.70`; 10 UK/RU и 11 EN пар превышают `0.80`, максимум `0.85/0.85/0.86`. Все значения — внутренний diagnostic, не пороги Google и не доказательство санкции.
- **Первый генератор также фактически небезопасен:** его variant pools без product-specific owner могут утверждать пять стадий контроля, личную проверку основателем, founder/veteran narrative, производство/упаковку в Харькове, усадку `1–2%` и предварительную декатировку, DTF и число стирок, отправку `1–2` дня и courier same-day, дополнительные цвета без доплаты, бесплатную доставку/обмен и фиксированный material. Если `product.material` пуст, код подставляет `трьохнитка` для hoodie и `бавовна` для остальных категорий. Hash выбирает не истинный факт, а одну из неподтвержденных альтернатив.
- **Смешанный язык:** `_city_paragraph`, `_color_paragraph`, `_fit_paragraph`, `_seo_closing_paragraph` и H2 в `_build_landing_html` содержат жестко записанные украинские литералы. На `/en/product/classic-tshirt/` после английских продуктовых абзацев идут «Ця t-shirt доступна…», «Замовити t-shirt…», список украинских городов и украинский brand paragraph. На RU происходит то же самое с русским названием товара внутри украинской грамматики.
- **Служебная фраза в публичном контенте:** fit URL показывает покупателю: «Перемикання між посадками змінює текст і ключові слова сторінки для коректного індексу пошуковими системами». Это описание внутренней SEO-механики, а не полезность товара. Оно делает текст искусственным и прямо сообщает о манипулятивной цели шаблона.
- **Фактические противоречия на контрольном товаре:** страница `classic-tshirt` сначала говорит «Без принту», а следующий абзац утверждает, что принт нанесен DTF и выдерживает `50+` стирок. Базовый блок называет плотность `180–220 г/м²`, а fit-copy классической посадки — `280–320 г/м²`. Color paragraph утверждает, что каждый вариант является отдельной посадкой, хотя color и fit — разные оси. Формы «цю футболка», «Замовити Футболка», «Кожна Футболка» грамматически неверны.
- **Почему это влияет:** Google не штрафует страницу просто за длину, повторяемую структуру или два блока. Проблема в совокупности: оба генератора способны публиковать неподтвержденные product/policy facts, один дополнительно оптимизирован под искусственное n-gram различие, а второй размножает смешанный язык и city/SEO phrasing. Уникальный HTML-hash не компенсирует misinformation и слабую самостоятельную ценность.
- **Безопасное решение:** оставить один содержательный editorial-компонент PDP и исправлять оба сервиса, а не только `product_seo_landing.py`. Базовые факты получать только из проверяемых product/variant/policy полей; не генерировать material, DTF, плотность, посадку, усадку, срок службы, QA, сроки, courier, обмен, упаковку или пожертвования без соответствующего owner. Удалить публичную фразу про индексацию и hash-selected factual alternatives. Все литералы провести через локализацию, а языковые формы категории/цвета/посадки хранить редакционно вместо склейки.
- **Выполненный узкий срез 2026-08-13:** Product JSON-LD больше не публикует heuristic `material`, материал `PropertyValue` или безусловный `Offer.deliveryLeadTime=3–5 дней`, поскольку в стандартной модели `Product` нет авторитетных полей для этих утверждений. Проверенные policy-owned `hasMerchantReturnPolicy` и weight-based `shippingDetails` сохранены. Commit `f654e0985e67bf442e26c785ce0a8e83b7f0f6ac`; production UK/RU/EN PDP проверены после pull/restart. Видимый merchandising-блок материала и остальной persisted copy этим срезом намеренно не изменялись; полный fact registry и cleanup persisted/generated copy остаются открытыми.
- **Acceptance check:** один long-form блок на PDP; факт-матрица `material/weight/print/fit/care/warranty` не содержит конфликтов между hero, description, FAQ, generated copy и schema; RU/EN не содержат UA-фразы; выборка всех `71 x 3` PDP проходит grammar/fact lint; 5-gram detector используется как regression metric, но не как искусственная цель «перефразировать ради процента».

#### FIND-014 — FAQ-слой системно раздут и почти полностью повторяется между товарами

- **Вердикт:** подтверждено production-БД; это не самостоятельный spam penalty.
- **Приоритет:** P2 после исправления фактических противоречий FIND-013.
- **Масштаб:** в production `836` активных `ProductFAQ` у `65` товаров; у шести FAQ отсутствует. Медиана и максимум — `13` вопросов на товар. В каждой языковой выборке среди 836 строк только `47` уникальных вопросов и `44` уникальных ответа; `832` ответные строки входят в exact-duplicate кластеры.
- **Интерпретация:** одинаковый ответ о доставке, уходе или оплате допустим, если факты действительно общие. Ошибка — считать 13 повторяющихся пар уникальным SEO-контентом каждого товара или автоматически расширять их ради объема. Для обычного ecommerce Google в большинстве случаев не показывает FAQ rich results; FAQ schema не является обещанием дополнительного сниппета.
- **Риск:** большой повторяющийся слой увеличивает шум страницы, затрудняет поддержку цен, сроков и гарантий, а при расхождении с policy/checkout/schema создает misinformation. Механическая «уникализация» фактических правил ухода будет хуже точного общего текста.
- **Безопасное решение:** разделить global support facts и product-specific questions. Общие доставка/оплата/возврат должны иметь один канонический источник и компактное представление; на PDP оставлять только вопросы, которые реально меняются из-за материала, принта, посадки, дизайна или конкретного варианта. Schema размечать только для видимого FAQ и только если он соответствует актуальным правилам Google.
- **Acceptance check:** у каждого FAQ есть owner (`global policy` или конкретный product/variant fact), дубликаты не размножаются в БД без причины, visible FAQ и JSON-LD совпадают дословно, изменение политики обновляет все surfaces из одного источника.
- **Статус 2026-08-13, P1.3:** оба standard-Product генератора больше не
  создают FAQ с неподтвержденными сроком `1–3 дня`, тарифами `85/180 грн` или
  отправкой до `14:00`. Коммит `b6fc9960` прошел TDD и production deploy;
  `/delivery/` остается единственным публичным owner delivery policy. В
  production подтверждены `64` ранее сгенерированные строки с тремя точными
  legacy signatures. Они не удалялись этим release: следующая задача обязана
  выполнить только exact-signature dry-run, создать backup и удалить только
  подтвержденные строки. Это не доказывает ranking effect и не оправдывает
  удаление вручную написанных FAQ о доставке.
- **Статус 2026-08-13, P1.4:** после exact-signature production cleanup
  удалил ровно `64` строки из опубликованных стандартных товаров (`22`
  футболки, `24` худи, `18` лонгслівів). Совпадение требовало все base/UK/RU/EN
  поля и `order=2`; DTF, Custom Print, drafts, inactive, другие порядки и
  измененные редактором строки не входили в область. Backup сохранен на
  production host; повторный dry-run и DB check дали `0` кандидатов. Это
  удаляет устаревшие данные, но не является обещанием ranking/rich-result
  эффекта и не оправдывает массовое удаление других FAQ о доставке.
- **Статус 2026-08-13, P1.4 hardening:** commit `b9fb9e977` усилил stale-plan
  защиту: перед потенциальным удалением блокируется и сверяется весь узкий
  standard `published/order=2` scope, а не только первоначальные ID. Live
  `manage.py check` и повторный dry-run дали `0`; новых данных не удалялось.
- **Статус 2026-08-13, P1.5:** standard PDP support anchors больше не обещают
  неподтвержденное окно доставки `1–3` дней и тарифы. `/delivery/` остается
  ссылкой, но label нейтрален (`Доставка та оплата`). Live UK/RU/EN PDP proof
  на `5a2ee244c` подтвердил отсутствие старого anchor и сохранение ссылки на
  Custom Print. Это factuality cleanup, не обещание ranking uplift.
- **Статус 2026-08-13, P1.5 locale hardening:** commit `8c3ac0a09` расширил
  regression на полную UK/RU/EN матрицу standard PDP и запрещает шесть старых
  локализованных обещаний срока доставки. Свежий локальный gate прошел `39/39`;
  production был обновлен до полного SHA
  `8c3ac0a09079e182b4cfa539c40399e72ecc46c` и Passenger перезапущен через
  `tmp/restart.txt`. No-cache live requests к `/healthz/` и трем locale URL
  `classic-tshirt` вернули `200`: старые claims отсутствуют, нейтральные
  localized labels и `/delivery/`, `/ru/delivery/`, `/en/delivery/`
  присутствуют. DTF и Custom Print не изменялись; это подтвержденная
  factuality/locale consistency, а не обещание роста позиций.

#### FIND-030 — общий каталог прямо оптимизирован под вставку keywords/cities и публикует неowned claims

- **Вердикт:** подтверждено кодом и live `/catalog/`; это content/factuality defect, а не ошибка из-за самого наличия H2 или длинного текста.
- **Приоритет:** P1 вместе с fact registry; исправлять на page 1 отдельно от удаления boilerplate на pagination.
- **Evidence:** комментарий `twocomms_django_theme/templates/pages/catalog.html:652-660` сообщает, что три commercial H2 содержат high-frequency keywords и top cities «for stronger ranking on local queries». Live UK/RU/EN `/catalog/` рендерят этот блок. Первый абзац перечисляет 15 городов и обещает доставку `1–2 дні`/бесплатный обмен; второй заявляет производство из premium cotton/knit `200–320 г/м²`, мужские прямые, женские зауженные и unisex cuts, размеры `XS–XXL`, DTF и `30+` стирок; третий утверждает военные коллаборации и перечисление части прибыли с каждого заказа на ЗСУ.
- **Почему это проблема:** перечисление городов не доказывает отдельную локальную услугу и не превращает общий каталог в city landing. Жестко заданные ассортиментные/policy claims могут расходиться с DB, delivery/returns и реальными товарами. Механическая замена формулировок или городов увеличит scaled/doorway risk. Это не означает, что слова «купить», города или три H2 запрещены; проблема — манипулятивная цель и неподтвержденные утверждения.
- **Безопасное решение:** определить одну задачу page-1 editorial: помочь выбрать категорию и понять фактические условия покупки. Оставить только подтвержденные, локализованные и полезные факты из registry; delivery/returns вести на canonical policy URLs. Убрать keyword/city insertion как acceptance и не создавать городские варианты блока. Если локальная ценность ограничивается отправкой из Харькова по Украине, сказать это один раз правдиво.
- **Acceptance check:** page-1 UK/RU/EN не содержит списков городов/keyword repetition ради ranking; каждый material/weight/fit/size/wash/delivery/exchange/donation/location claim имеет owner/source/effective date; нет неподтвержденных женских cuts или диапазонов; page 2+ не повторяет блок; category links same-locale и canonical.

#### FIND-010 — индексируемая page 2 повторяет большой SEO-boilerplate первой страницы категории

- **Связь с презентацией:** текущая production-проверка подтверждает основной механизм слайда 36.
- **Вердикт:** подтверждено для `/catalog/hoodie/?page=2`; выполненный sitemap + one-hop crawl не покрывает полную матрицу category `page>=2` по всем route families и локалям, поэтому масштаб требует отдельного recursive/hash crawl.
- **Приоритет:** P2, потому что дефект одновременно затрагивает качество текста, пагинацию, локализацию и проверяемость коммерческих утверждений.
- **Evidence:** page 2 отвечает `200`, `index,follow`, self-canonical и имеет корректно дополненные title/description «сторінка 2». Однако под товарной выдачей повторно публикуется тот же длинный блок с `twc-sales-seo-h2:v1`, перечнем 15 городов, ценой «від 1490 грн», доставкой «1–2 дні», бесплатным обменом 14 дней, тканью 320 г/м², `30+` стирок, гарантией 6 месяцев, пожертвованиями ЗСУ и ссылками на другие категории. Тот же блок присутствует на page 1.
- **Нюанс:** page 2 не следует закрывать или canonical-ить на page 1 автоматически: на ней другие карточки товаров, и crawler должен иметь путь к ним. Проблема не в существовании пагинации, а в повторе редакционного/коммерческого текста и в завышенной семантической нагрузке на каждую страницу серии.
- **Почему это влияет:** boilerplate снижает различимость paginated documents, увеличивает межстраничное сходство, повторяет десятки geo/commerce terms вне отдельного локального intent и размножает любые устаревшие обещания. Это не автоматический penalty, но плохое распределение контента и crawl-signals.
- **Безопасное решение:** основной editorial SEO-блок показывать только на первой странице чистой категории либо вынести действительно самостоятельные темы в ограниченные demand-backed landing pages. На `page>=2` оставить компактный heading, товары, полезную навигацию и crawlable pagination. Все числовые claims привязать к единому источнику политики/данных и регулярно валидировать.
- **Acceptance check:** normalized text hash после удаления header/footer/cards не находит большой editorial-блок на `page>=2`; page 2 остается `200`, indexable, self-canonical и содержит crawlable товары; claims первой страницы совпадают с актуальными ценами, доставкой, возвратами и гарантиями. Distinct title/description можно оставить для UX, но это не hard Google gate.

### 5.7. Schema.org, Merchant surfaces и сущности

#### FIND-009 — текущий `MemberProgram` не соответствует типам и обязательным значениям Google

- **Связь с презентацией:** слайд 18 показал критически невалидную сущность `TWOCOMMS Бали` в Rich Results Test 29.07.2026; текущий production содержит ту же структурную причину.
- **Вердикт:** подтверждено в production HTML и коде.
- **Приоритет:** P2 для корректности merchant/loyalty eligibility; не трактовать как общую потерю ranking.
- **Evidence:** representative PDP `/product/twocomms-beliveidea-ts/` публикует Organization/OnlineStore с `hasMemberProgram`. Внутри `MemberProgramTier.hasTierBenefit` находится объект `{"@type":"MemberProgramTierBenefit","name":"Бали за покупки та промокоди"}`. Официальная документация Google требует повторяемое значение `TierBenefitEnumeration`, например `https://schema.org/TierBenefitLoyaltyPoints`; для points-benefit также указывается `membershipPointsEarned`. Текущий tier не содержит ни поддерживаемого enumeration, ни количества points per currency unit.
- **Кодовая причина:** `storefront/seo_utils.py` вручную создает неподдерживаемый тип `MemberProgramTierBenefit`, а тест проверяет только, что `hasTiers` непустой. Он не валидирует контракт Google, enum, tier URL/id или points semantics.
- **Контрдоказательство:** Product, Merchant listing, Breadcrumb и другие сущности на историческом скриншоте были распознаны; одна невалидная loyalty entity не означает, что вся schema страницы бесполезна или что обычные позиции падают.
- **Безопасное решение:** сначала подтвердить реальную механику программы баллов: как начисляются баллы, есть ли фиксированное число за 1 UAH, где видимы условия и как пользователь вступает. Затем либо разметить фактический tier по документированному `TierBenefitLoyaltyPoints` + `membershipPointsEarned` и связать с видимой policy page, либо временно убрать `MemberProgram`, если точную программу нельзя правдиво выразить. Не выдумывать коэффициент ради валидатора.
- **Acceptance check:** Rich Results Test/Schema validator на Organization и representative PDP не показывает ошибку MemberProgram; JSON-LD совпадает с видимой программой и backend-правилами; regression test проверяет точный enum и points value либо подтверждает отсутствие сущности, когда программа выключена.

### 5.8. Изображения, alt, производительность и мобильный рендер

#### FIND-016 — mobile фильтр показывает badge `1` на чистом URL без выбранного фильтра

- **Вердикт:** подтверждено в browser на `/catalog/tshirts/` при 390×844; SEO-влияние косвенное, это mobile UX/CRO-дефект.
- **Приоритет:** P3.
- **Evidence:** чистый self-canonical URL без query показывает «29 моделей», quick facets `Тема: Усі`, `Крій: Будь-який`, `Колір: Показати всі`, но оба triggers отображают «Фільтри 1». В открытом dialog единственными pressed defaults являются sorting «Рекомендовані», «Показати всі» и «Будь-який крій»; ни color, size, audience, availability, theme или technology не выбраны. После выбора `color=black` badge остается тем же `1`, теперь уже совпадая с одним реальным фильтром.
- **Почему это важно:** ложный active-count заставляет пользователя предполагать, что ассортимент уже ограничен, и делает состояние фильтра менее предсказуемым. Это не ranking defect, но каталог — коммерческий landing; неверное состояние может снизить исследование ассортимента и конверсию.
- **Безопасное решение:** не считать default sort и all/any sentinels активными фильтрами. Badge должен быть скрыт/`0` на чистом URL и считать только реально примененные ограничения; сортировку при необходимости показывать отдельно.
- **Acceptance check:** fresh session и чистый URL показывают 0/no badge; каждый добавленный facet увеличивает count ровно на одну логическую ось; reset возвращает 0; desktop/mobile и URL/back-forward state совпадают.

#### FIND-028 — подтвержденные mobile lab bottleneck-и требуют отдельного CWV/RUM цикла

- **Вердикт:** подтверждено как лабораторная техническая opportunity; полевой Core Web Vitals failure и ranking penalty не доказаны.
- **Приоритет:** P2 после исправления P0/P1 indexability, URL ownership, localization и factual consistency.
- **Evidence:** последовательные Lighthouse 13.4.1 mobile traces сохранены в output/seo-audit-2026-08-10/performance/. Для /catalog/ LCP 8.2 s, для /catalog/tshirts/ 6.5 и 9.1 s в повторных прогонах; PDP CLS 0.248 в обоих прогонах; каталог имеет 111–118 запросов и 2.19–2.45 MiB transfer; Lighthouse оценивает около 101 KiB unused CSS, 331–332 KiB unused JS и 0.72–1.64 s render-blocking.
- **Ограничение:** это Moto G Power-like emulation, RTT 150 ms, throughput около 1.47 Mbps и CPU slowdown 4x. PSI API вернул 429 RESOURCE_EXHAUSTED с quota 0, поэтому CrUX/field LCP, INP и CLS недоступны. Home main-thread 24.6 s и единичный Lighthouse root-document timing 13.73 s для category были аномалиями и не считаются точной production latency.
- **Механизм влияния:** медленный первый экран и layout shift могут ухудшать мобильный UX, просмотр каталога и конверсию; Google использует page experience как один из сигналов при прочих равных, но этот набор замеров не показывает потерю позиций.
- **Безопасное решение:** сначала зафиксировать размеры/аспект gallery и места под цену, badges и fit controls; затем coverage-guided разделить critical и deferred CSS/JS, оптимизировать responsive images и проверить third-party tags. Не откладывать LCP-изображение, не удалять variant media и не ломать filters, mini-cart, consent, attribution или purchase path.
- **Acceptance check:** минимум три последовательных cold/warm runs на каждом representative URL с median/p75; PDP CLS <0.1 в lab median и без видимого shift; category LCP target согласован с бизнесом; field CrUX/Search Console/RUM проверен отдельно; browser flows add-to-cart, variant price/image/availability, mini-cart and tracking проходят.

### 5.9. GEO / локальная релевантность

#### GEO-001 — устойчивое entity grounding является положительным контролем, а не ошибкой

Стабильные Organization, Website, Storefront и Founder identifiers с reciprocal sameAs и внешним официальным источником обнаружены в сохранённых home/PDP/color captures. Это полезная основа entity resolution. Нельзя обещать Knowledge Panel или AI citation. @id нельзя менять без миграционного плана; внешние ссылки, роль основателя и social claims следует проверять ежемесячно.

#### GEO-002 — EN/RU JSON-LD частично остаётся на украинском языке

Сохранённые EN/RU home, PDP и color HTML содержат украинские slogan, description, founder description и MemberProgram text при заявленных RU/EN hreflang. Это не санкция, но смешивает языковой сигнал, ухудшает intent matching и цитируемость. Schema должна строиться из того же locale-aware источника, что и видимый текст; в acceptance matrix нужно запретить украинские fallback strings в RU/EN, кроме утверждённых proper nouns. Evidence: output/seo-audit-2026-08-10/performance/home.html, pdp.html и color-landings-live/*.html.

**Статус 2026-08-13:** founder `Person.description` исправлен для RU/EN через
существующие gettext-переводы и live-проверен на стандартных PDP/catalog
страницах в commit `78b75c0720`. Остальные GEO-002 поверхности (Organization,
WebSite, color landing и отключенный MemberProgram/fact parity) остаются
отдельными открытыми задачами; этот срез не объявляет GEO-002 полностью
закрытым.

**Статус 2026-08-13, gallery locale slice:** стандартная RU/EN PDP gallery
теперь получает accessibility/status templates из активной локали. Исправлены
SSR fallback, thumbnail/dot labels и live-region text; production browser proof
на пяти изображениях подтвердил позиции `1…5` и обновление статуса после выбора.
Коммит `5c564f9e0`; полный locale matrix, остальные mixed-language PDP strings
и общий fact/content audit остаются открытыми.

**Статус 2026-08-13, shared PDP shell locale slice:** устранены RU/EN
украинские fallback-строки в стандартном model-context label и существующей
PDP promotion card. Production browser proof на RU/EN подтвердил локальный
текст и отсутствие украинских markers; commit `830f99f60`. Это не аудит и не
изменение Custom Print route/configurator, а только локализация родительской
standard PDP.

#### GEO-003 — ClothingStore с координатами не подтверждён видимой физической точкой

Contacts page одновременно описывает online-only магазин с отправкой из Харькова и публикует ClothingStore, координаты 50.0040, 36.2308, postalCode 61061 и часы 10:00–22:00 без streetAddress. Это риск ложного Local Pack/Maps ожидания, но не доказанный ranking loss. Если staffed location и часы реальны, те же NAP должны быть видимы и подтверждены GBP; если нет, оставить ContactPage/Organization/OnlineStore и описать Харьков как операционный origin без LocalBusiness coordinates.

#### GEO-004 — порог бесплатной доставки противоречит сам себе

Contacts и llms.txt заявляют 3000 UAH, PDP/product SEO blocks и color/FAQ copy — 2500 UAH. Это фактический commerce/trust конфликт, который может попасть в сниппеты и AI answers. Нужно выбрать policy owner, effective date и генерировать видимые блоки, FAQ, JSON-LD, feeds, llms, письма и checkout из одной версии. Acceptance: один актуальный threshold на locale, старое значение удалено или явно датировано.

#### GEO-005 — конфликт даты основания бренда 2022 против 2025

Organization и llms.txt утверждают `foundingDate`/`Founded: 2022`; AboutPage отдельно публикует `datePublished: 2022-09-01`, что является датой документа и само по себе не доказывает основание бренда. Текущие editorial/PDP материалы при этом содержат утверждение об основании 1 июля 2025. Нельзя выбирать дату ради SEO. Сначала определить, относится ли каждая дата к юридическому лицу, запуску бренда, публикации страницы или текущей линии; затем публиковать один подтверждённый founding fact во всех surfaces. Если truth не подтверждён, `foundingDate` лучше убрать, чем выдумывать.

#### GEO-006 — dateModified меняется ежедневно без изменения статьи

pro_brand.html фиксирует datePublished 2022-09-01, но выводит dateModified как текущую дату при каждом запросе. Это ложный freshness signal. Нужен editorial updated_at/revision, меняющийся только при существенном видимом изменении; два render-а неизменённой страницы должны дать одинаковое dateModified.

#### GEO-007 — AggregateOffer.offerCount 74 не совпадает с 71 публичным товаром

Домашний JSON-LD считает только price__isnull=False и отдаёт offerCount 74, тогда как production sitemap/storefront scope содержит 71 опубликованный товар в активных категориях. Structured data тем самым заявляет три лишних или непубличных offer. Нужно переиспользовать тот же eligibility queryset и variant price resolver, что и storefront/sitemap; acceptance — offerCount равен тому же snapshot scope и мониторится против sitemap.

#### GEO-008 — MemberProgramTierBenefit не соответствует документированному контракту

Live JSON-LD помещает произвольный тип MemberProgramTierBenefit под hasTierBenefit. Официальная документация Google [Loyalty Program structured data](https://developers.google.com/search/docs/appearance/structured-data/loyalty-program), зафиксированная также в разделе 2.4, ожидает документированный `TierBenefitEnumeration`, например `TierBenefitLoyaltyPoints`, и `membershipPointsEarned` для points benefit. Не следует выдумывать коэффициент баллов: либо выразить реальную программу поддерживаемой моделью и видимой policy, либо временно убрать MemberProgram. Проверить Rich Results Test и Schema Markup Validator.

#### GEO-009 — llms.txt и AI-crawler Allow не дают самостоятельного ranking boost

/llms.txt и /llms-full.txt отдаются 200, robots перечисляет OAI-SearchBot, ChatGPT-User, Claude, Perplexity, Google-Extended и другие агенты. Само opt-in допустимо при согласованной legal/business policy, но обычные crawl/index требования остаются обязательными. llms сейчас повторяет изменяемые claims (3000 threshold, price range 660–2550), поэтому его нужно генерировать из общей fact registry и разрешать только canonical/indexable URL без query/private paths. Измерять AI visibility воспроизводимым query set с языком, страной, моделью, датой и цитируемыми URL.

#### GEO-010 — масштабируемые SEO-блоки создают scaled-content и doorway-риск

Production evidence насчитывает 73 Cartesian color×fit URL без combination-owned data, 836 FAQ rows, сводящихся к 47 уникальным вопросам и 44 ответам, hash-selected PDP paraphrases, созданные ради снижения 5-gram overlap, и повторяемые category blocks с geo/commerce claims. Повтор FAQ или общий policy text сам по себе не является spam; подтвержденный риск возникает, когда страницы/перефразы масштабируются ради поискового покрытия без нового buyer value либо содержат неподтвержденные facts. Google scaled-content guidance оценивает added value, а не происхождение текста. Нельзя массово создавать city/color/fit pages простыми заменами. Отдельный owner требует реальный intent, assortment/state, media, locale-correct facts and parity; UI-only states консолидируются по выбранной canonical policy без blanket `noindex + canonical`.

#### GEO-011 — OfferCatalog на RU/EN pro-brand содержит украинские URL

pro_brand.html генерирует /catalog/tshirts/, /catalog/hoodie/ и /catalog/long-sleeve/ независимо от LANGUAGE_CODE, хотя видимые ссылки/hreflang локализованы. Украинский fallback допустим только если это явно выбранная canonical policy; иначе OfferCatalog должен использовать matching locale URLs. Acceptance: RU/EN child URLs 200, self-canonical и reciprocal hreflang в той же локали.

#### GEO-012 — entity/fact drift нужно контролировать как единый граф

Один и тот же live set одновременно содержит украинскую Organization schema на EN/RU, foundingDate 2022, offerCount 74, delivery threshold 3000 и 2500 в разных слоях, а также разные price-range fallbacks (660–2550 в llms и 880–2550 в seo_utils). Исправление одного тега недостаточно. Нужна versioned fact/entity registry и nightly rendered-locale matrix, сравнивающая visible text, JSON-LD, canonical/hreflang, sitemap и llms; релиз блокируется при расхождениях, кроме approved proper nouns.

#### GEO-013 — массовые city pages без локальной услуги не оправданы (дополнительная синтезированная находка)

Текущие SEO-блоки перечисляют много городов (в том числе Киев, Харьков, Одесса и другие) в общем коммерческом тексте, но evidence не показывает отдельные точки, локальные условия, сроки, отзывы, pickup или иной city-specific service contract. Подмена города в шаблоне не создаёт локальной ценности и может выглядеть как doorway/scaled content. Безопасная стратегия — один правдивый entity narrative «отправка из Харькова, доставка по Украине» с ссылками на contacts/delivery/returns; отдельный город — только при реальной услуге, спросе, уникальных доказательствах и owner URL.

### 5.10. AI/GEO для ответных систем

Под GEO здесь понимается понятность entity/fact graph и воспроизводимая цитируемость, а не отдельный магический фактор ранжирования.

- **Что сохранять:** обычную crawlability/indexability, точные visible facts, стабильные @id, reciprocal hreflang, canonical/indexable sitemap и согласованные Product/Organization/LocalBusiness entities.
- **Что не считать доказательством:** наличие llms.txt, FAQ schema, AI user-agent Allow, backlinks, отдельное упоминание в одном ChatGPT/AI Overview или обещание агентства. Никакая из этих вещей не гарантирует citation или рост позиций.
- **Measurement contract:** зафиксировать 30–50 запросов по языкам UK/RU/EN и интентам category/product/color/fit/local; хранить дату, страну, устройство, модель/поисковик, ответ, cited URL, факт ошибки и конкурентные упоминания; повторять ежемесячно после изменений. Не отправлять искусственные рекламные/покупочные события ради измерения.
- **Content contract:** каждый публичный claim должен иметь owner, source URL/DB field, effective date и locale. Ответные страницы должны ссылаться на canonical product/category/contact/delivery URLs, а не на query facets или несуществующие numeric PDP.

### 5.11. Вторичные цепочки, которые нельзя исправлять изолированно

Следующие зависимости были проверены после первичных FIND/GEO и добавлены в implementation order. Они не являются новыми автоматическими санкциями Google; это причинные цепочки, из-за которых локальный фикс без соседнего слоя может оставить противоречие или создать новый URL-bloat.

| Chain ID | Первичная причина | Вторичный эффект | Безопасная граница исправления | Gate |
|---|---|---|---|---|
| CHAIN-001 | stale SEO links на `/catalog/custom-print/` и numeric `/product/{id}/` | 404-страницы повторяются в RU/EN, facets и pricing tables; исправление только одного шаблона оставит старые DB rows | Сначала production DB mapping `old_id -> published slug/status`; `/custom-print/` только заменить на рабочий owner, configurator не менять; 301 только для exact successor | category locale matrix + one-hop crawl: 0 linked 404 |
| CHAIN-002 | SEO rail links ведут на noindex query facets | noindex URL получают высокий in-degree, hreflang и новые combinations; robots.txt раньше noindex скроет сигнал деиндексации | Сначала убрать editorial links и разделить UI links/SEO links; затем allowlist clean landings; robots policy принимать после наблюдения | no editorial link targets `noindex`; invalid/empty facet 404 |
| CHAIN-003 | 18 query URL имеют `index,follow` при non-self canonical | grey/olive filters и home `page=` образуют неодинаковую route policy и возвращают в crawl старый bloat | Утвердить policy по route family: page>=2 self-canonical, page=1 one-hop clean, UI filters noindex/follow или approved landing; не blanket-canonical page 2 | status/robots/canonical matrix for home, category, locale, color |
| CHAIN-004 | color x fit URLs строятся Cartesian product | duplicate meta, orphan landings, variant schema/feed links не совпадают с selected state | Сначала URL allowlist и demand/inventory/media evidence; затем один resolver для sitemap, canonical, meta, schema, feed и UI | approved owners only; exact selected image/price/availability |
| CHAIN-005 | ProductGroup/selected variant resolver неполный | base, color, fit, size URLs и merchant feed могут заявлять разные variant identity, image, offer URL и canonical | Не менять ProductGroup до CHAIN-004; после ownership использовать один snapshot resolver и проверять `variesBy/hasVariant/isVariantOf` против visible state | validator + feed + representative browser/schema matrix |
| CHAIN-006 | RU/EN fallback на UA в visible text и JSON-LD | hreflang promises fail, title/H1/body/schema entity language diverges; category blocks are not locale-aware | Locale publication gate: indexable RU/EN only with translated title/H1/editorial/FAQ/alt/schema; missing fields flagged, not silently copied | rendered locale diff: no UA fallback except approved proper nouns |
| CHAIN-007 | два PDP SEO blocks, repeated FAQ and mutable template facts | contradictory print/weight/wash/delivery claims; 836 FAQ rows collapse to 47 questions/44 answers; scaled-content risk | One editorial block per PDP; FAQ source dedupe; fact registry with owner/effective date; custom print excluded | visible text, JSON-LD, llms, feed and checkout claim parity |
| CHAIN-008 | variant media/alt/fit rows incomplete | 48/78 colors lack images, localized alt rows are absent, fit selector appears where fit rows missing; indexable URL promises a state it cannot show | Index only variants with sellable rows, matching media, measurements and locale alt; UI may still select non-indexed state | URL selected state == image/price/availability/media/alt |
| CHAIN-009 | public eligibility differs across sitemap/feed/home schema | 71 public products vs homepage `offerCount=74`; feed and sitemap can disagree on offers and availability | Introduce one eligibility predicate/query snapshot shared by catalog, sitemap, schema, feeds and llms | offerCount/feed/sitemap equality |
| CHAIN-010 | unsupported MemberProgram and unverified ClothingStore/founding facts | rich-result contract warnings and entity graph drift across locale pages; coordinates/hours contradict online-only claim | Remove unsupported schema or map only to documented truthful types; confirm business facts before emitting LocalBusiness/foundingDate | validator clean; visible/entity facts identical |
| CHAIN-011 | `dateModified=now()` and hardcoded locale URLs in pro-brand OfferCatalog | every request looks like content change; RU/EN schema points to UA URLs, weakening recrawl and hreflang interpretation | Use source `updated_at` and locale-aware URL builder; add rendered-locale/entity drift test | stable dateModified; same-locale child URLs and reciprocal hreflang |
| CHAIN-012 | mobile filter badge/performance lab bottlenecks | clean URL can look filtered to users; lab regressions can hide real field state and affect conversion even without proven ranking loss | Fix state derivation separately from SEO policy; measure 3-run lab median and obtain CrUX/GSC/RUM before claiming CWV impact | clean badge=0; no purchase-path regression; dated lab/field evidence |
| CHAIN-013 | variant parser принимает регистр и любой порядок сегментов | exact-equivalent state получает несколько `200` self-canonical owners до решения allowlist | Normalize lowercase and stable segment order first; one-hop 301 only for exact equivalents, ambiguous/repeated segments 404 | one final URL; selected state unchanged; no redirect chain |

**Dependency rule:** CHAIN-001 was the first release slice because it removed confirmed dead ends without changing URL ownership. CHAIN-013 may follow independently because it normalizes only exact-equivalent paths. CHAIN-004 ownership decisions must precede CHAIN-005/008/009. CHAIN-006/007 must precede mass content or city landing work. No backlink acquisition is recommended before CHAIN-001, CHAIN-013, CHAIN-004 and the critical locale/factuality gates are live-verified.

### 5.12. Дополнительные вторичные проверки и ограничения evidence

- **Pagination soft-200:** `/catalog/tshirts/?page=abc`, `?page=0`, `?page=999999` and equivalent color-landing URLs currently return `200` by `Paginator.get_page()` fallback/clamping. This creates aliases and can make a nonexistent page appear canonical. Valid `page>=2` must remain a distinct self-canonical product slice; malformed, duplicate or out-of-range values must 404 or undergo one deterministic normalization.
- **Facet/page canonical mismatch:** `/catalog/tshirts/?page=2&color=black` is `noindex,follow`, but canonical points to unfiltered `/catalog/tshirts/?page=2` while the filtered document contains a different product slice and different PDP links. A facet URL must either canonicalize to an equivalent clean owner with no SEO hreflang, or become an approved self-canonical owner; it must never canonicalize to an unrelated page-N.
- **Invalid facet soft-200:** unsupported `fit`, `size`, `theme` and `availability` values are silently dropped and render the unfiltered category with `200`. This is a body-equivalent crawl alias, not a useful page. Reject or deterministically normalize invalid values and test repeated/combined parameters.
- **SEO rail amplification:** the same pricing/editorial blocks render on clean category pages and many facets/pages. Fixing a stale row in one template is insufficient unless the row resolver, locale URL builder and page-1/editorial gating prevent it from reappearing in every locale/facet copy.
- **Cache/backend consequence:** anonymous catalog caching keys include the normalized query string. Hundreds of noindex combinations can therefore multiply cache entries and render/database work. Measure cache cardinality, query timing and UX selector behavior after URL-policy changes; do not block valid filters blindly.
- **Crawler evidence limitation:** the audit crawler's `canonicalize_crawl_url` resolved relative/query-only hrefs against the site root instead of the source page. Absolute 404 targets and their status are valid, but pagination inlink attribution must be re-run with `urljoin(source_final_url, raw_href)` before using route-level inlink counts for prioritization.

## 6. Семантическая архитектура без раздувания сайта

Рекомендуемый URL ownership и indexability policy:

| Сущность/намерение | Владелец URL | Индексация | Условия допуска |
|---|---|---|---|
| Общий каталог | /catalog/ и локальные /ru/catalog/, /en/catalog/ | index, self-canonical | Один общий catalog intent; locale-correct H1/meta, main content и навигация |
| Категория товара | /catalog/tshirts/, /catalog/hoodie/, /catalog/long-sleeve/ плюс locale paths | index, self-canonical | Активный ассортимент, category copy и честные цены/наличие |
| Базовый PDP | /product/{slug}/ плюс locale paths | index, self-canonical | Опубликованный товар, product-specific truthful facts, media, Offer и schema |
| Одобренный цветовой landing | /catalog/{category}/{color}/ | index только owner decision | Спрос, достаточный ассортимент, color-specific media, locale-correct useful facts и links |
| Одобренный fit landing/PDP | /product/{slug}/{fit}/ или отдельный category owner | index только allowlist | Sellable fit rows, measurements, fit media, availability и fit intent |
| Одобренный color×fit | /product/{slug}/{color}/{fit}/ | редкий allowlist | Только при подтверждённом спросе и самостоятельной ценности обеих осей; не Cartesian product |
| Одобренный thematic landing | `/catalog/theme/{slug}/` плюс locale paths | index только owner decision | Самостоятельный intent, ассортимент, локализованные полезные facts/schema и internal links; без text-uniqueness quota |
| Theme query/filter state, размер, сортировка, multi-filter | query или state URL | не самостоятельный owner | UI-only; canonical/noindex policy выбирается по эквивалентности, но URL не размещается в sitemap и editorial SEO links |
| Pagination page 1 | clean owner | index, self-canonical | Один URL без page=1 |
| Pagination page 2+ | тот же path с page=N | index, self-canonical | Другой товарный набор, crawlable prev/next; без копии длинного SEO-блока |
| Invalid/empty pagination и facet combination | не создавать owner | 404 | Никакого soft-200 последней страницы или пустого результата |
| City/local landing | отдельный /delivery/{city}/ или approved owner | только при доказанной локальной ценности | Реальная услуга/условия/доказательства, не простая замена города |
| Custom print | существующий `/custom-print/` | вне remediation policy | Не анализировать и не менять content/variant/schema/metadata/canonical. Уже выполненная нормализация внешней ссылки каталога не создает follow-up scope; допустима только конкретно воспроизведенная RU/EN localization-only правка. |

Правила перехода из UI-state в indexable landing: сначала demand map и URL owner; затем проверка inventory/availability, media, localized content, schema/feed, internal links и canonical/hreflang; только после этого URL добавляется в sitemap. Color, fit и size — независимые оси: наличие selector или query state не означает право на индексируемую страницу. Для вариантов допустимы и один canonical ProductGroup, и отдельные URLs, но каждый отдельный URL обязан предвыбирать именно заявленный вариант и показывать согласованные image, price, availability и copy.

## 7. Приоритизированный backlog

| Порядок | Работа | Effect / risk | Dependencies | Acceptance |
|---:|---|---|---|---|
| 1 — выполнено | Удалить internal links на 25 dead destinations | P1 crawl/UX | Deployed `e20ec393`; Custom Print flow не менялся | Достигнуто: live crawl 1 354 URL, 0 linked 404 |
| 1b — выполнено | Убрать неутвержденный fallback SEO-блок с чистого корня каталога | P0 factuality / scaled-content hygiene | Active `CatalogColorSeoOverride(scope="general")`; cache invalidation | Deployed `6ce8466bf` (2026-08-14): production DB has 0 active general rows; UK/RU/EN `/catalog/` render 0 `catalog-color-seo` sections and 0 legacy markers; UK/RU/EN `?color=black` retain the colour block and `noindex, follow` |
| 1a — условно | Проверить external history 24 numeric PDP перед redirect decision | P3/P2 только при реальных backlinks/traffic | GSC, logs, backlink/analytics history, exact successor | Exact successor -> one-hop 301; иначе 404/410; не блокирует выполненный пункт 1 |
| 2 | Нормализовать exact-equivalent variant paths | P1/P2 URL ownership hygiene | Current parser/state tests; ownership policy не требуется | Lowercase stable order; exact permutations one-hop 301; ambiguous/repeated segments 404; selected state identical |
| 3 | Утвердить variant ownership и single-page/multi-page policy | P1 canonical/state consistency | Demand/GSC/backlinks, inventory, media, locale fact matrix | Все 630 locale URL классифицированы; owners и UI states согласованы с sitemap/internal links/schema; mass changes запрещены без history review |
| 4 | Исправить locale content, hreflang и localized schema | P1 relevance/entity | Message catalog, DB translation, hreflang policy | RU/EN title/H1/main content/critical UI/FAQ/schema locale-correct; reciprocal self-inclusive hreflang; proper nouns разрешены |
| 5 | Оставить один правдивый PDP editorial block и fact policy registry | P1 trust/scaled-content | Owners для material/weight/print/fit/care/shipping/founding facts | Hero, copy, FAQ, schema, llms, feeds и checkout согласованы; служебная SEO-фраза удалена |
| 6 | Проверить полную route/locale matrix, затем нормализовать подтвержденные facets/pagination defects | P1/P2 crawl correctness | Сейчас page-2 boilerplate подтвержден на `/catalog/hoodie/?page=2`, color pagination/canonical — на black landing, invalid soft-200 — на representative routes; остальные families сначала воспроизвести | Для проверенной matrix: no editorial links на UI-only facets; valid page>=2 self-canonical; invalid/duplicate/empty pages 404; page=1 redirect остается P3 cleanup |
| 7 | Добавить clean landing internal links только для approved color/fit owners | P2 discoverability | Steps 3–4 and editorial briefs | Category links ведут на matching locale path landing; query links остаются UX-only |
| 8 | Заполнить variant media, alt и fit data | P1 commerce/image relevance | Production photography, measurements, sellable rows | Every approved owner has matching SSR/gallery/schema media, accurate localized alt where informative, availability and applicable dimensions |
| 9 | Исправить ProductGroup/MemberProgram/Offer counts и feeds | P2 structured-data/merchant trust | Variant model and eligibility source of truth | Validator clean; offerCount equals public snapshot; no unsupported MemberProgram type |
| 10 | Исправить mobile filter state and performance bottlenecks | P2/P3 CRO/CWV | Browser regression and consent/analytics contract | Filter badge 0 on clean URL; PDP CLS <0.1 lab median; category LCP and asset budget improve without commerce regressions |
| 11 | GEO/AI monitoring and local policy | P2 long-term factuality | Fact registry, query set, legal confirmation of entity/location | Monthly citation matrix; one truthful Kharkiv/Ukraine narrative; no unapproved city pages |

Не следует начинать закупку ссылок до выполнения пунктов 1–5 и повторной проверки production: внешние ссылки не исправят неверный canonical, 404, смешанный язык или противоречивую цену и могут усилить неверные URL.

### 7.1. Release log: root catalog editorial fallback

- [x] **P0-Facts-RootCatalog (2026-08-14):** `6ce8466bf` removes `GENERAL_CATALOG_SEO_COPY` as a fallback for clean `/catalog/`. `build_catalog_color_seo()` now returns `None` unless production has an active, explicitly populated `general` override; a partial override never inherits retired claims. The template suppresses empty H2/body wrappers, and the versioned anonymous catalog page cache was bumped to `catalog-seo-v7-20260814-root-editorial` so cached root HTML cannot survive the release.
- [x] **Regression boundary:** 24 focused Django tests pass for root/no-override, active/inactive/empty/query-only general overrides, coloured catalog rendering, clean editorial links, and cache identity. `manage.py check`, `py_compile`, `makemigrations --check --dry-run`, and `git diff --check` passed before commit. The broader historical catalog/SEO batch still has pre-existing unrelated failures in tracking-pagination expectations, swatch test expectations, and home/product schema cache fixtures; none are caused by this release and they remain separate work.
- [x] **Production proof:** server checkout is `6ce8466bf960b02606c1a54600e8062c46994e41`; an authoritative MariaDB query returned `0` active `general` override rows. Fresh HTTP HTML checks confirmed `section=0`, `legacy=0` on `/catalog/`, `/ru/catalog/`, `/en/catalog/`; and `section=1`, `noindex=1` on the matching `?color=black` URLs. Custom Print, the DTF subdomain, blog, variant ownership, canonical, hreflang, and colour-filter policy were not changed in this release.

### 7.2. Release log: locale-owned catalog ItemList schema

- [x] **P1-Catalog-locale-schema (2026-08-14):** `9ed640b06` removes a
  contradiction between the established locale-publication gate and root/category
  `CollectionPage` JSON-LD. A RU/EN card can remain useful to a shopper while
  its fallback-language PDP correctly responds `noindex, follow`; that PDP is
  no longer emitted as an `ItemList` owner. UK keeps the exact visible-card
  list, and thematic catalog landings explicitly keep their visible product
  list too.
- [x] **Implementation and test boundary:** only `catalog_schema_products`
  differs from the rendered card queryset. The locale projection reuses
  `locale_is_indexable()` with a bounded product/FAQ prefetch, so it does not
  introduce per-card database queries. Fresh isolated regressions on the
  production virtualenv passed `4/4` for locale schema, empty prefetched FAQ
  and query count, plus `2/2` for thematic-schema preservation and cache
  namespace invalidation. Context7's Django `Prefetch(..., to_attr=...)`
  contract was used to make an empty prefetched FAQ list remain query-free.
- [x] **Production proof:** at SHA `9ed640b06c7324f610330d2d9b40fd3cd0e8c2b0`,
  live root ItemLists contain `16` UK and `10` RU/EN items. Every inspected
  RU/EN ItemList URL is a `200` indexable PDP; a visible fallback card is not
  silently removed, only omitted from the conflicting schema list. This is
  crawl/locale-signal hygiene, not a claim of ranking, traffic or rich-result
  growth. No Custom Print, DTF subdomain/module/blog, catalog text, product
  data, variant ownership or canonical policy changed.

## 8. Матрица проверки после будущих исправлений

| Контур | Что проверять | Проходной критерий | Evidence |
|---|---|---|---|
| HTTP/crawl | sitemap + one-hop/internal crawl, status, redirect chain, linked 404 | 0 linked 404; public indexable/internal SEO redirects только intentional one-hop; внешние auth/OAuth flows исключены из SEO-chain критерия и проверяются отдельно; invalid facets/pages 404 | run.json, pages.json, inlinks.json, pages.csv |
| Sitemap/URL owner | products, categories, colors, thematic owners, variants, static/blog, pagination | Каждый sitemap URL 200, indexable owner, self-canonical; нет UI-only query URLs | sitemap XML + rendered headers |
| Canonical/hreflang | UK/RU/EN representative matrix | self-inclusive reciprocal alternates; x-default policy explicit; noindex facet не публикует hreflang на query/noindex URLs либо указывает только approved canonical indexable equivalents | HTML parser report + screenshots |
| Localization | visible H1/body, meta, alt/aria, JSON-LD | Нет UA fallback в RU/EN кроме approved proper nouns; language and URL agree | rendered locale diff + translation completeness report |
| Facts/entity | price, shipping threshold, founding date, address/hours, donation, material/weight/print | Один versioned owner fact на всех surfaces; unsupported claims removed | fact registry diff; HTML/schema/llms/checkout |
| Variants/media | color, fit, size selected state; images, alt, price, stock | Только allowlisted variants indexable; URL предвыбирает заявленный state; no classic media on oversize | Playwright screenshots, DB query, JSON-LD |
| Schema/feeds | ProductGroup, Product, Organization, Offer, MemberProgram, merchant feeds | Validator/Rich Results clean for supported types; values match visible public snapshot | validator exports + feed XML |
| Mobile UX | filter badge, language switch, gallery, cart/mini-cart, consent | Clean URL badge 0; no overlap/shift; purchase path and analytics events preserved | browser traces/screenshots, non-polluting mocked checks |
| Performance lab | Lighthouse mobile repeatability | 3 sequential runs/URL; report median/p75; PDP CLS target <0.1; no critical JS regression | raw Lighthouse JSON/HTML |
| Performance field | CrUX/Search Console/RUM | Segment by device/country/locale; do not infer from PSI quota error | dated field export |
| GEO/AI | fixed UK/RU/EN query set, model/search engine, cited URL | Monthly reproducible baseline; factual answers cite canonical pages; no promise of citation boost | query ledger and citation snapshots |
| GSC observation | coverage, canonical selection, hreflang, crawl stats, enhancements | Compare 7/28/90-day windows after deploy; inspect sample URLs before broad conclusions | GSC exports with date/filter |

## Evidence index

- output/seo-audit-2026-08-10/agent-slides-10-40.md, agent-slides-41-67.md, agent-slides-68-86.md — slide text/image interpretation and third-party-case boundaries.
- output/seo-audit-2026-08-10/agent-crawl-architecture/production-crawl-evidence.md, pages.json, sitemap-records.json, inlinks.json — status, inlinks, sitemap, canonical and query evidence.
- output/seo-audit-2026-08-10/agent-production-content.md — DB-backed product, variant, fit, media, FAQ and SEO-block counts.
- output/seo-audit-2026-08-10/agent-color-landings.md and color-landings-live/*.html — color landing locale, schema, pagination and duplicate evidence.
- output/seo-audit-2026-08-10/agent-geo-ai.md — GEO/entity/fact evidence package GEO-001–GEO-012.
- GEO-013 синтезирован из production geo-boilerplate в FIND-010/FIND-013, contacts/delivery evidence и official scaled-content/local factuality guidance; это не отдельный пункт agent-geo-ai.md.
- output/seo-audit-2026-08-10/agent-performance-cwv.md and performance/*.json — Lighthouse lab, request graph and field-data limitations.
- twocomms/storefront/seo_utils.py, twocomms/storefront/services/variant_meta.py, twocomms/storefront/views/product.py, templates and translation modules — code paths cited inline in findings.

## Context7 query record

SEO policy source is the linked primary Google Search Central documentation; Context7 was used as a retrieval/cross-check layer, not as an independent ranking authority. Queried IDs: `/websites/developers_google_search` and `/websites/developers_google_search_appearance_structured-data`. Django implementation contracts were checked separately through `/websites/djangoproject_en_5_2` for `translation.override()`, locale-aware URL generation and language-sensitive cache behavior. No third-party marketing claim was treated as a Google requirement.
