# Форензическая верификация SEO-аудита twocomms.shop

## SECTION 1 — EVIDENCE LEDGER

Ниже — нормализованный реестр по ID из приложенного аудита fileciteturn0file0. Для всех внешних источников дата получения одна и та же: **2026-05-11**. Там, где в документе сформулирована не проверяемая техническая неисправность, а гипотеза роста, я пометил это как **UNVERIFIED** и прямо указал `EVIDENCE: NOT FOUND`.

### Core backlog A–DD

| ID | Verdict | Confidence | Primary source | Date | Caveat / refinement |
|----|---------|-----------|---------------|------|---------------------|
| A | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/appearance/title-linkturn4search0 citeturn21view0 | 2025-12-10 | Уникальный и понятный `<title>` важен, но фиксированного «лимита символов» Google не дает; как CRIT приоритет завышен. |
| B | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/appearance/title-linkturn4search0 citeturn21view0 | 2025-12-10 | Уникальные category-title полезны, но это не автоматический CRIT; на живом `/catalog/tshirts/` тайтл уже выглядит лучше, чем в ранних версиях аудита. citeturn2view4 |
| C | REFUTED | high | urlhttps://developers.google.com/search/docs/appearance/title-linkturn4search0 citeturn21view0 | 2025-12-10 | Google не требует, чтобы H1 обязательно отличался от `<title>`; требование «развести во что бы то ни стало» — методологически неверно. |
| D | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Утверждение про вред повторения бренда в первом абзаце не подтверждено допустимыми первичными источниками 2023–2026. |
| E | PARTIALLY-CONFIRMED | low | urlhttps://developers.google.com/search/docs/fundamentals/creating-helpful-contentturn19search25 citeturn19search25turn16search7 | 2025-12-10 / n.d. | Полезный PLP-контент помогает понять раздел, но «обязательный стационарный SEO-блок под сеткой» не является нормой Google. |
| F | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/crawling-indexing/links-crawlableturn4search4 citeturn4search4turn16search24 | n.d. | Внутренняя перелинковка полезна для обхода и понимания сайта; термин и логика «AI-anchor links» в первичных источниках не закреплены. |
| G | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/appearance/title-linkturn4search0 citeturn21view0turn3view1 | 2025-12-10 | На `/custom-print/` действительно слабый поисковый сигнал в H1, но требование «сделать keyword-first H1» — это оптимизация, а не CRIT. |
| H | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/appearance/structured-data/faqpageturn16search16 citeturn23view0turn16search16 | n.d. / 2023-08-08 | FAQ-контент может быть полезен пользователю, но ожидание FAQ rich results для e-commerce в 2026 уже устарело. |
| I | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Growth-идея, а не верифицируемый технический дефект. |
| J | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Growth-идея, а не верифицируемый технический дефект. |
| K | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Growth-идея, а не верифицируемый технический дефект. |
| L | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Growth-идея, а не верифицируемый технический дефект. |
| M | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Growth-идея, а не верифицируемый технический дефект. |
| N | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Growth-идея, а не верифицируемый технический дефект. |
| O | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Наполнение `seo_keywords`/внутренних полей как отдельный SEO-требование 2026 не подтверждено допустимыми первичными источниками. |
| P | PARTIALLY-CONFIRMED | low | urlhttps://developers.google.com/search/docs/fundamentals/creating-helpful-contentturn19search25 citeturn19search25turn24search17 | n.d. | Контент-хаб может помочь, но список тем и приоритет публикаций не следует из первичных источников напрямую. |
| Q | PARTIALLY-CONFIRMED | low | urlhttps://developers.google.com/search/docs/appearance/ai-featuresturn6search16 citeturn21view5turn19search25 | 2025-12-10 | Полезный объясняющий контент поддерживает обычный поиск и AI Overviews, но конкретные «нужно 6 статей» не доказаны. |
| R | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Без допустимого первичного источника exact keyword/landing-page рекомендация остается гипотезой. |
| S | PARTIALLY-CONFIRMED | low | urlhttps://developers.google.com/search/docs/fundamentals/creating-helpful-contentturn19search25 citeturn19search25 | n.d. | Материал может быть полезен, но приоритет и точная семантика не доказаны первичными источниками. |
| T | PARTIALLY-CONFIRMED | low | urlhttps://developers.google.com/search/docs/fundamentals/creating-helpful-contentturn19search25 citeturn19search25 | n.d. | То же: допустимо как growth backlog, но не как техническая неисправность. |
| U | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/appearance/structured-data/product-snippetturn6search2 citeturn22view4 | 2025-12-10 | Product/Offer-разметка для PDP действительно важна, но без raw-head/JSON-LD извлечения нельзя подтвердить конкретный дефицит на каждой карточке. |
| V | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/appearance/structured-data/organizationturn5search29 citeturn21view6 | 2026-04-15 | Organization data на homepage полезны для merchant knowledge/brand profile; конкретная нехватка полей требует raw-schema проверки. |
| W | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/appearance/structured-data/product-variantsturn6search0 citeturn21view4 | 2025-12-10 | Если документ настаивает на сводке вариантов, это уже актуально в 2026 для apparel, но нужно подтверждать фактической схемой. |
| X | CONFIRMED | medium | urlhttps://developers.google.com/search/docs/appearance/structured-data/breadcrumbhttps://developers.google.com/search/docs/appearance/structured-data/breadcrumb | n.d. | На живом PDP есть breadcrumb в UI; если schema BreadcrumbList отсутствует, это реальный пробел для понимания и rich eligibility. citeturn2view5turn16search5 |
| Y | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/specialty/international/localized-versionsturn8search18 citeturn22view0 | 2025-12-22 | Hreflang-логика действительно критична для uk/ru/en, но приоритет зависит от реальной полноты матрицы alternates. |
| Z | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/appearance/google-imagesturn4search30 citeturn22view7 | 2026-03-02 | Image SEO важно для apparel, но утверждение нужно проверять реальным HTML `img`, `alt`, `srcset`, а не только аудиторским описанием. |
| AA | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/appearance/snippetturn6search29 citeturn22view6 | 2026-04-20 | Хорошие meta descriptions релевантны, но они не являются прямым ranking signal; приоритет не CRIT. |
| BB | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Social metadata/OG/Twitter в допустимом списке первичных источников пользователя не имеют достаточной базы. |
| CC | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | То же. |
| DD | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | То же. |

### Research / TBD EE–LL and expansion MM–SS

| ID | Verdict | Confidence | Primary source | Date | Caveat / refinement |
|----|---------|-----------|---------------|------|---------------------|
| EE | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Исследовательский тикет, не finding. |
| FF | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Исследовательский тикет, не finding. |
| GG | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Исследовательский тикет, не finding. |
| HH | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Исследовательский тикет, не finding. |
| II | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Исследовательский тикет, не finding. |
| JJ | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Исследовательский тикет, не finding. |
| KK | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Исследовательский тикет, не finding. |
| LL | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Исследовательский тикет, не finding. |
| MM | PARTIALLY-CONFIRMED | low | urlhttps://developers.google.com/search/docs/crawling-indexing/links-crawlableturn4search4 citeturn4search4turn16search24 | n.d. | Любая рекомендация по усилению внутренних ссылок — directionally correct, но не автоматически HIGH/CRIT. |
| NN | PARTIALLY-CONFIRMED | low | urlhttps://developers.google.com/search/docs/fundamentals/creating-helpful-contentturn19search25 citeturn19search25 | n.d. | Контентная гипотеза может быть разумной, но не доказана как must-have. |
| OO | PARTIALLY-CONFIRMED | low | urlhttps://developers.google.com/search/docs/fundamentals/creating-helpful-contentturn19search25 citeturn19search25 | n.d. | То же. |
| PP | OUTDATED | high | urlhttps://developers.google.com/search/blog/2023/08/howto-faq-changesturn4search3 citeturn23view0 | 2023-08-08 | Если тикет продвигал FAQPage как способ получить FAQ rich results для ecommerce/PDP — это устарело. |
| QQ | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/appearance/structured-data/organizationturn5search29 citeturn21view6 | 2026-04-15 | Merchant/brand-detail расширения полезны, но требуют фактической проверки схемы. |
| RR | PARTIALLY-CONFIRMED | low | urlhttps://developers.google.com/search/docs/appearance/ai-featuresturn6search16 citeturn21view5 | 2025-12-10 | Для AI visibility важна доступность, полезность и структурированность, а не сам факт существования отдельного хаба. |
| SS | PARTIALLY-CONFIRMED | low | urlhttps://developers.google.com/search/docs/appearance/ai-featuresturn6search16 citeturn21view5 | 2025-12-10 | То же. |

### Appendix / addenda TT–LLL and B2–B23

| ID | Verdict | Confidence | Primary source | Date | Caveat / refinement |
|----|---------|-----------|---------------|------|---------------------|
| TT | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Уточняющий append-only finding, недостаточно воспроизводимых данных. |
| UU | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | То же. |
| VV | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | То же. |
| WW | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | То же. |
| XX | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | То же. |
| YY | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | То же. |
| ZZ | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | То же. |
| AAA | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | То же. |
| BBB | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | То же. |
| CCC | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/crawling-indexing/block-indexingturn5search4 citeturn22view1turn22view2 | 2025-12-10 | Если finding касается noindex/robots interplay, он стандартообразен, но требует raw-head и `robots.txt` проверки. |
| DDD | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/crawling-indexing/robots-meta-tagturn5search9 citeturn5search9turn24search11 | n.d. | То же. |
| EEE | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urlsturn24search5 citeturn24search5 | n.d. | Каноникализация важна, но без ответов raw HTML/headers это не подтверждено постранично. |
| FFF | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/specialty/international/localized-versionsturn8search18 citeturn22view0 | 2025-12-22 | Если finding про hreflang reciprocity/self-reference — это валидно, но нужна матрица alternates. |
| GGG | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/specialty/international/localized-versionsturn8search18 citeturn22view0turn24search1 | 2025-12-22 | `x-default` полезен как fallback, но не обязателен для каждого кейса. |
| HHH | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | В приложении есть гипотеза, но недостаточно стандартообразной базы. |
| III | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | То же. |
| JJJ | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | То же. |
| KKK | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | То же. |
| LLL | CONFIRMED | high | urlhttps://developers.google.com/search/docs/specialty/international/localized-versionsturn8search18 / urlhttps://docs.djangoproject.com/en/5.2/topics/i18n/translation/turn12view0 citeturn22view0turn13view1turn13view2turn0view3 | 2025-12-22 / 5.2 docs | Hreflang + Django language-prefix root cause выглядит реальным: `/ru/...` уже сейчас не воспроизводится корректно во внешнем рендере, что повышает доверие к finding. |
| B2 | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/appearance/title-linkturn4search0 citeturn21view0turn0view0 | 2025-12-10 | Домашний title нужно держать ясным и брендовым, но не оценивать по «магическим» лимитам длины. |
| B3 | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/appearance/title-linkturn4search0 citeturn21view0turn2view4 | 2025-12-10 | Категорийные тайтлы должны быть уникальны; часть проблемы уже выглядит смягченной на живом сайте. |
| B4 | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/appearance/title-linkturn4search0 citeturn21view0turn3view1 | 2025-12-10 | `/custom-print/` действительно может быть яснее сформулирован для поиска, но H1 rewrite — не CRIT. |
| B5 | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/blog/2023/08/howto-faq-changesturn4search3 / urlhttps://developers.google.com/search/docs/appearance/structured-data/faqpageturn16search16 citeturn23view0turn16search16 | 2023-08-08 / n.d. | FAQ как контент допустим; как rich-result tactic для магазина — нет. |
| B6 | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Формулировка приложения не имеет достаточной первичной базы или не воспроизводится по текущему HTML-срезу. |
| B8 | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/appearance/structured-data/product-snippetturn6search2 / urlhttps://developers.google.com/search/docs/appearance/structured-data/merchant-listingturn5search7 citeturn22view4turn21view1 | 2025-12-10 | Если finding про product structured data, он направление верное; без raw JSON-LD нельзя дойти до CONFIRMED. |
| B9 | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/appearance/structured-data/organizationturn5search29 citeturn21view6 | 2026-04-15 | Organization structured data на homepage — актуально в 2026. |
| B10 | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/appearance/structured-data/review-snippetturn6search3 citeturn22view5turn1view0 | 2025-12-10 | Отзывы и aggregateRating релевантны, но только если контент реально присутствует и видим пользователю. |
| B11 | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/specialty/international/localized-versionsturn8search18 citeturn22view0turn24search1 | 2025-12-22 | Hreflang/x-default тема подтверждается, но нужно подтверждать всей матрицей языков. |
| B12 | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Недостаточно первичной стандартообразной базы. |
| B13 | PARTIALLY-CONFIRMED | medium | urlhttps://web.dev/articles/top-cwvturn7search8 / urlhttps://web.dev/blog/common-misconceptions-lcpturn7search3 / urlhttps://developers.google.com/search/docs/appearance/page-experienceturn16search13 citeturn7search8turn7search3turn21view2 | 2024-10-31 / 2024-08-20 / 2025-12-10 | Если finding про LCP image priority, он современный и обоснованный; но ranking-эффект надо не переоценивать. |
| B14 | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/appearance/google-imagesturn4search30 citeturn22view7 | 2026-03-02 | Если finding об image alt/srcset/HTML-image discoverability — это валидно. |
| B15 | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basicsturn16search18 citeturn21view3 | 2026-03-04 | Если finding касается JS-rendered content/meta, он актуален, особенно для Django + динамических блоков. |
| B16 | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Недостаточно первичной базы. |
| B17 | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/crawling-indexing/block-indexingturn5search4 / urlhttps://developers.google.com/search/docs/crawling-indexing/robots/introturn5search14 citeturn22view1turn22view2 | 2025-12-10 | Если finding про технические страницы, noindex/robots logic подтверждается официальной документацией. |
| B18 | UNVERIFIED | low | EVIDENCE: NOT FOUND | n.d. | Недостаточно первичной базы. |
| B19 | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/appearance/ai-featuresturn6search16 citeturn21view5 | 2025-12-10 | Если finding про готовность к AI Overviews, общая логика верна, но конкретные механики для Perplexity/ChatGPT первично не документированы в допустимом списке источников. |
| B20 | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/specialty/ecommerce/help-google-understand-your-ecommerce-site-structureturn16search7 / urlhttps://developers.google.com/search/docs/crawling-indexing/links-crawlableturn4search4 citeturn16search7turn16search24 | n.d. | Если finding про сайтовую архитектуру и promoted categories/products — подтверждается как best practice. |
| B21 | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/crawling-indexing/links-crawlableturn4search4 citeturn4search4turn0view0turn2view4 | n.d. | Если finding про crawlable text links/navigation, это актуально; нужна live-проверка source HTML. |
| B22 | PARTIALLY-CONFIRMED | medium | urlhttps://developers.google.com/search/docs/appearance/google-imagesturn4search30 citeturn22view7 | 2026-03-02 | Если finding про image discoverability/asset format на variant pages — валидно, но не стоит обещать прямой SEO-эффект только из-за смены PNG/WebP. |
| B23 | PARTIALLY-CONFIRMED | medium | urlhttps://web.dev/articles/top-cwvturn7search8 / urlhttps://developers.google.com/search/docs/appearance/page-experienceturn16search13 citeturn7search8turn21view2 | 2024-10-31 / 2025-12-10 | Performance finding обоснован, но должен опираться на field CWV/CrUX, а не только на lab scores. |

### Follow-up on refuted and partially-confirmed items

По **C / B2 / B3 / B4** автор аудита местами подменяет официальную логику Google «понятный основной заголовок и качественный title link» более старым чеклистом про обязательное разведение H1 и `<title>` и про фиксированные ограничения длины. В текущей документации Google такого правила нет: система использует разные сигналы для title link, а задача владельца сайта — сделать основной заголовок страницы ясным, а не искусственно разводить H1 и title ради самого разведения. Поэтому здесь корректная формулировка — **“улучшить ясность и уникальность”**, а не **“исправить критическую ошибку”**. citeturn21view0turn24search9

По **E / F / MM / NN / OO / RR / SS / B20 / B21** документ слишком свободно смешивает полезную внутреннюю перелинковку, IA и контент-рост с якобы обязательными техтребованиями. Официальные источники подтверждают важность crawlable links и связности сайта для понимания структуры, но не подтверждают терминологию вроде «AI-anchor links» и не дают основания поднимать это до уровня CRIT без факта проблем обхода, индексации или каноникализации. Для e-commerce это backlog роста, а не «форензически доказанный дефект». citeturn16search7turn16search24turn21view5

По **H / PP / B5** документ частично устарел: FAQ-контент как таковой может помогать пользователю и AI systems, но ставка на **FAQPage rich results** для магазина в 2026 неверна. Google еще в августе 2023 официально ограничил FAQ rich results фактически well-known government и health sites и прямо написал, что для прочих сайтов этот результат больше не показывается регулярно. Значит, рекомендацию надо переписать как **UX/semantic content**, а не как SERP-feature tactic. citeturn23view0turn16search16

По **U / V / W / X / Y / Z / AA / QQ / B8 / B9 / B10 / B11 / B14 / B15 / B17** общая траектория документа сильная, но автор часто пишет так, будто наличие разметки или метатегов само по себе гарантирует показ. Официальные Google docs повторяют обратное: rich result eligibility требует не только синтаксически валидной разметки, но и соблюдения технических и quality guidelines, а показ не гарантируется. Поэтому практически все schema-related finding’и стоит переквалифицировать из «обязательного показа» в «повышение eligibility и понимания контента». citeturn21view1turn22view4turn22view5turn16search8

По **LLL / FFF / GGG / B11** проблема уже выглядит не теоретической, а практической: Google требует complete alternate matrix, self-referencing links, fully qualified URLs и рекомендует `x-default` как fallback; Django 5.2, в свою очередь, явно документирует поведение `i18n_patterns()` и `prefix_default_language=False`. На живом external render `/ru/product/clasic-tshort/` уже отдает ошибку, а это делает finding о language alternates одним из самых надежных во всем документе. Для украино-/русско-/англоязычного магазина это действительно может бить и по каноникализации, и по правильному языковому показу. citeturn22view0turn24search1turn13view1turn13view2turn0view3

По **B13 / B23** логика про LCP и image priority в 2026 уже вполне современная, но автору следовало жестче отделить **field CWV** от lab-индикаторов. Google прямо пишет, что Core Web Vitals используются ranking systems, но хорошая page experience не заменяет релевантность, а web.dev отдельно подчеркивает: приоритет LCP ресурса, отсутствие lazy-loading на LCP image и `fetchpriority="high"` помогают, но действовать нужно по данным CrUX/field, а не по одному Lighthouse прогону. citeturn21view2turn7search4turn7search8turn7search14

## SECTION 2 — CRITICAL HOLES THE AUTHOR MISSED

### Loyalty program structured data for bonus points

На homepage и PDP уже видны бонусы/баллы, но в аудите нет сильного фокуса на **`MemberProgram`** для merchant visibility. В 2026 это уже не экзотика: Google прямо документирует loyalty benefits в Search и knowledge panels. Для магазина, где баллы — реальная часть value proposition, это сильнее, чем декоративные FAQ-блоки. citeturn21view8turn18search0turn18search2turn18search3

**Primary source**: urlhttps://developers.google.com/search/docs/appearance/structured-data/loyalty-programturn18search0; urlhttps://schema.org/MemberProgramturn18search2

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "@id": "https://twocomms.shop/#org",
  "name": "TWOCOMMS",
  "url": "https://twocomms.shop/",
  "hasMemberProgram": {
    "@type": "MemberProgram",
    "name": "TWOCOMMS Бали",
    "description": "Бали за покупки, обмін на промокоди або донати.",
    "url": "https://twocomms.shop/faq/"
  }
}
```

### Merchant shipping policy on Organization

Аудит много говорит о доставке в тексте, но не дожимает тему **`ShippingService`** / shipping policy structured data на уровне организации. Для UA e-commerce это особенно важно: доставка и SLA — один из ключевых факторов конверсии и merchant listing completeness. Google официально рекомендует задавать shipping policy для бизнеса отдельно. citeturn21view7turn18search20

**Primary source**: urlhttps://developers.google.com/search/docs/appearance/structured-data/shipping-policyturn17search0

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "@id": "https://twocomms.shop/#org",
  "hasShippingService": {
    "@type": "ShippingService",
    "name": "Доставка TWOCOMMS по Україні",
    "areaServed": "UA",
    "shippingDestination": {
      "@type": "DefinedRegion",
      "addressCountry": "UA"
    }
  }
}
```

### Merchant return policy markup

Возвраты и обмены на сайте есть в навигации, но в audit backlog это не поставлено как один из наиболее сильных merchant-surface сигналов. В 2026 **`MerchantReturnPolicy`** — это не nice-to-have, а прямой способ сделать merchant data более полным в Search. Особенно для apparel, где возвраты и обмен размеров критичны. citeturn17search8turn17search2turn17search3turn17search21

**Primary source**: urlhttps://developers.google.com/search/docs/appearance/structured-data/return-policyturn17search8; urlhttps://schema.org/MerchantReturnPolicyturn17search2

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "@id": "https://twocomms.shop/#org",
  "hasMerchantReturnPolicy": {
    "@type": "MerchantReturnPolicy",
    "applicableCountry": "UA",
    "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
    "merchantReturnDays": 14,
    "returnMethod": "https://schema.org/ReturnByMail",
    "returnFees": "https://schema.org/FreeReturn"
  }
}
```

### ProductGroup / variant clustering for fit, color, size

Судя по PDP, у товара есть как минимум fit/посадка и цветовые/размерные варианты. Для apparel это уже textbook-case для **`ProductGroup` + `hasVariant`**. Без этого Google хуже понимает, что variant URLs — семейство одного продукта, а не несвязанные карточки. В аудите это звучит недостаточно жестко. citeturn21view4turn2view5turn1view1

**Primary source**: urlhttps://developers.google.com/search/docs/appearance/structured-data/product-variantsturn6search0

```json
{
  "@context": "https://schema.org",
  "@type": "ProductGroup",
  "productGroupID": "clasic-tshort",
  "name": "Футболка класична",
  "variesBy": [
    "https://schema.org/size",
    "https://schema.org/color",
    "https://schema.org/sizeGroup"
  ],
  "hasVariant": [
    {
      "@type": "Product",
      "sku": "CLASIC-TSHORT-BLACK-S-CLASSIC",
      "color": "Чорний",
      "size": "S"
    }
  ]
}
```

### Separate article markup and real publication metadata for `/novyny/`

Сейчас `/novyny/` выглядит как brand-updates hub со ссылками на карточки, а не как полноформатный новостной раздел. Если раздел остается, ему нужны либо настоящие article-detail URLs с `BlogPosting`/`Article`, датой, автором и canonical, либо его лучше не позиционировать как «новини». Иначе это thin brand page под новостным лейблом. citeturn3view3turn24search17

**Primary source**: urlhttps://developers.google.com/search/docs/appearance/structured-data/articleturn24search17

```json
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "{{ article.title }}",
  "datePublished": "{{ article.published_at|date:'c' }}",
  "dateModified": "{{ article.updated_at|date:'c' }}",
  "author": {
    "@type": "Organization",
    "name": "TWOCOMMS"
  }
}
```

### `x-default` fallback and strict BCP 47 hygiene

В аудите есть hreflang-разбор, но не видно жесткого акцента на `x-default` как fallback и на дисциплину кодов языка/региона по BCP 47. Для uk/ru/en-магазина это особенно важно, потому что здесь легко получить смесь `uk`, `uk-UA`, `ru`, `ru-UA`, `en`, `en-UA` без ясной логики. Google рекомендует `x-default`, а RFC/MDN закрепляют правила language tags и назначение `hreflang`. citeturn22view0turn24search1turn13view5turn14view0turn14view1

**Primary source**: urlhttps://developers.google.com/search/docs/specialty/international/localized-versionsturn8search18; urlhttps://www.rfc-editor.org/rfc/rfc5646turn12view3

```html
<link rel="alternate" hreflang="uk" href="https://twocomms.shop/product/clasic-tshort/">
<link rel="alternate" hreflang="ru" href="https://twocomms.shop/ru/product/clasic-tshort/">
<link rel="alternate" hreflang="en" href="https://twocomms.shop/en/product/clasic-tshort/">
<link rel="alternate" hreflang="x-default" href="https://twocomms.shop/product/clasic-tshort/">
```

### Locale-adaptive behavior must be ruled out explicitly

Если сервер где-либо меняет язык по `Accept-Language`, cookie или IP без отдельного URL, это уже отдельная зона риска. Google прямо предупреждает, что locale-adaptive pages могут не быть полноценно crawl/indexed, потому что Googlebot ходит без `Accept-Language`. Для рынка UA это критично: нельзя смешивать `/ru/` и auto-redirect по языку. citeturn24search7turn22view0

**Primary source**: urlhttps://developers.google.com/search/docs/specialty/international/locale-adaptive-pagesturn24search7

```python
# Django middleware guardrail:
# no auto-redirect by Accept-Language for crawlers or first-time anonymous users.
if request.path.startswith(("/ru/", "/en/")):
    return get_response(request)
# show language switcher, don't force redirect
```

### Merchant Center + structured data dual-feed strategy

Аудит недооценивает официальный путь: для product visibility Google рекомендует не только on-page structured data, но и Merchant Center / feeds. Для e-commerce с меняющимися ценами и остатками сочетание feed + schema устойчивее, чем ставка только на JSON-LD. citeturn17search28turn18search26

**Primary source**: urlhttps://developers.google.com/search/docs/appearance/structured-data/productturn17search28

```python
# Django management command pseudocode
# export products feed daily for Merchant Center
for product in Product.objects.filter(is_active=True):
    yield {
        "id": product.sku,
        "title": product.name_uk,
        "link": product.get_absolute_url(),
        "price": f"{product.price} UAH",
        "availability": "in stock" if product.in_stock else "out of stock",
    }
```

### OfferShippingDetails on offers, not only prose

Shipping terms should live not only on static pages, but also inside product offers where applicable. Google’s merchant docs explicitly mention shipping information as part of richer product experiences. Для UA apparel магазина это полезно и пользователю, и merchant listing eligibility. citeturn21view1turn6search9turn5search1turn5search6

**Primary source**: urlhttps://developers.google.com/search/docs/appearance/structured-data/merchant-listingturn5search7; urlhttps://schema.org/OfferShippingDetailsturn5search1

```json
{
  "@type": "Offer",
  "priceCurrency": "UAH",
  "price": "788",
  "availability": "https://schema.org/InStock",
  "shippingDetails": {
    "@type": "OfferShippingDetails",
    "shippingDestination": {
      "@type": "DefinedRegion",
      "addressCountry": "UA"
    }
  }
}
```

### Verified first-party review strategy

На PDP уже есть секция отзывов, но audit не поднимает до CRIT/HIGH вопрос **first-party visible reviews + valid review markup**. Для apparel это крайне практичный кусок Product/Review eligibility. Важно именно то, что reviews должны быть видимы пользователю и не агрегироваться с чужих сайтов. citeturn22view5turn1view0

**Primary source**: urlhttps://developers.google.com/search/docs/appearance/structured-data/review-snippetturn6search3

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "{{ product.name_uk }}",
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "4.8",
    "reviewCount": "23"
  }
}
```

### Homepage Organization markup should expose merchant admin details

Google in 2026 explicitly расширил рекомендации по `Organization` для merchant knowledge/brand details, включая return policy, address, contact information и loyalty program. Если у TWOCOMMS есть брендовая, сервисная и контактная навигация, homepage schema должна это отражать. Это сильнее, чем косметические title tweaks. citeturn21view6turn18search25

**Primary source**: urlhttps://developers.google.com/search/docs/appearance/structured-data/organizationturn5search29

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "@id": "https://twocomms.shop/#org",
  "name": "TWOCOMMS",
  "url": "https://twocomms.shop/",
  "contactPoint": [{
    "@type": "ContactPoint",
    "contactType": "customer support",
    "availableLanguage": ["uk", "ru", "en"]
  }]
}
```

### AI visibility guardrail: no accidental snippet suppression on key commerce pages

Google’s AI features use the same indexing and accessibility principles, and snippet-control directives (`nosnippet`, restrictive robots, inaccessible content) can suppress how content is consumed. Аудит говорит про AI visibility, но не формализует проверку на случайные suppressors на PDP/PLP. Для AI Overviews это must-check. citeturn21view5turn16search19turn22view1

**Primary source**: urlhttps://developers.google.com/search/docs/appearance/ai-featuresturn6search16; urlhttps://developers.google.com/search/docs/crawling-indexing/robots-meta-tagturn16search19

```html
<!-- key PLP/PDP pages: avoid accidental suppression -->
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large,max-video-preview:-1">
```

### Favorites / cart / account / tracking pages need explicit indexation policy review

`/favorites/` открывается как обычная HTML-страница. Если она индексируема и не закрыта корректно, это типичный low-value page pattern для e-commerce. Google и Yandex оба рекомендуют именно `noindex`/meta or auth, а не путать это с robots-only блокировкой. Для UA рынка это особенно важно, потому что часть аудитории все еще пересекается с Yandex ecosystem. citeturn2view1turn22view1turn22view2turn9search3turn9search6turn9search7

**Primary source**: urlhttps://developers.google.com/search/docs/crawling-indexing/block-indexingturn5search4; urlhttps://yandex.com/support/webmaster/en/controlling-robot/metatagsturn9search7

```html
<meta name="robots" content="noindex,follow">
```

### News/updates hub should either become a real content entity or a noindex utility page

Текущая `/novyny/` выглядит как utility hub со ссылками на новые товары, а не как полноценный editorial раздел. Если раздел не будет развиваться в реальные article-detail pages, нормальнее либо переименовать его как utility updates hub, либо исключить из index. Иначе получается thin page, которая в AI/organic hardly wins. citeturn3view3turn19search25turn24search17

**Primary source**: urlhttps://developers.google.com/search/docs/fundamentals/creating-helpful-contentturn19search25; urlhttps://developers.google.com/search/docs/appearance/structured-data/articleturn24search17

```html
<!-- if kept as utility hub and not expanded editorially -->
<meta name="robots" content="noindex,follow">
```

## SECTION 3 — DEEP TECHNICAL CHALLENGES TO VERIFY ON-SITE

Эти проверки нужны, чтобы **подтвердить или опровергнуть** самые спорные мои выводы: language alternates, canonical/noindex interplay, Product/Organization schema completeness, JS-rendered head tags и performance claims. Для live-index state используйте URL Inspection API; для schema — Rich Results Test и validator.schema.org; для JS расхождений — raw HTML vs rendered DOM. citeturn20search0turn20search9turn16search8turn21view3

### Canonical, title, robots, hreflang on key URLs

```bash
urls=(
  "https://twocomms.shop/"
  "https://twocomms.shop/catalog/tshirts/"
  "https://twocomms.shop/product/clasic-tshort/"
  "https://twocomms.shop/custom-print/"
  "https://twocomms.shop/favorites/"
  "https://twocomms.shop/novyny/"
  "https://twocomms.shop/ru/product/clasic-tshort/"
  "https://twocomms.shop/en/product/clasic-tshort/"
)

for u in "${urls[@]}"; do
  echo "===== $u ====="
  curl -sL "$u" | \
    grep -Eio '<title>.*</title>|<meta[^>]+name="robots"[^>]*>|<link[^>]+rel="canonical"[^>]*>|<link[^>]+rel="alternate"[^>]+hreflang[^>]*>'
  echo
done
```

**Подтверждает**: C/LLL/B11/B17.  
**Ломает мои выводы**, если `/ru/` и `/en/` отдают корректные 200, self-referencing alternate links, `x-default`, canonical на себя и ожидаемую robots policy. citeturn22view0turn24search1turn22view1

### Проверка locale-adaptive behavior against `Accept-Language`

```bash
for lang in "uk" "ru" "en-US,en;q=0.9"; do
  echo "===== Accept-Language: $lang ====="
  curl -I -H "Accept-Language: $lang" https://twocomms.shop/product/clasic-tshort/
done
```

**Подтверждает**: риск locale-adaptive routing или unwanted redirects.  
**Ломает мои выводы**, если ответ стабилен и не перекидывает пользователя/бота без отдельного URL. citeturn24search7

### Raw HTML vs rendered DOM for head tags and injected JSON-LD

```bash
node <<'JS'
const { chromium } = require('playwright');

(async() => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const urls = [
    'https://twocomms.shop/',
    'https://twocomms.shop/product/clasic-tshort/',
    'https://twocomms.shop/custom-print/',
    'https://twocomms.shop/novyny/'
  ];

  for (const url of urls) {
    await page.goto(url, { waitUntil: 'networkidle' });
    const data = await page.evaluate(() => ({
      title: document.title,
      robots: document.querySelector('meta[name="robots"]')?.content || null,
      canonical: document.querySelector('link[rel="canonical"]')?.href || null,
      alternates: [...document.querySelectorAll('link[rel="alternate"][hreflang]')].map(x => [x.hreflang, x.href]),
      jsonld: [...document.querySelectorAll('script[type="application/ld+json"]')].map(x => x.textContent)
    }));
    console.log(JSON.stringify({ url, data }, null, 2));
  }

  await browser.close();
})();
JS
```

**Подтверждает**: schema/head теги реально попадают в rendered DOM, а не остаются только в шаблонных ожиданиях.  
**Ломает мои выводы**, если Product/Organization/Breadcrumb уже полностью и корректно присутствуют. citeturn21view3turn16search5turn16search8

### Извлечение JSON-LD и проверка на Product / ProductGroup / Organization / Article

```bash
curl -sL https://twocomms.shop/product/clasic-tshort/ \
| pup 'script[type="application/ld+json"] text{}' \
| jq .
```

Если schema рендерится JS-ом, используйте Playwright-версию:

```bash
node -e "
const { chromium } = require('playwright');
(async()=>{const b=await chromium.launch();
const p=await b.newPage();
await p.goto('https://twocomms.shop/product/clasic-tshort/',{waitUntil:'networkidle'});
const data=await p.$$eval('script[type=\"application/ld+json\"]',els=>els.map(e=>e.textContent));
console.log(data.join('\n\n'));
await b.close();})();
"
```

**Подтверждает**: U/W/X/B8/B9/B10.  
**Ломает мои выводы**, если видны полноценные `Product`, `Offer`, `BreadcrumbList`, `Organization`, `AggregateRating`, `ProductGroup`. citeturn22view4turn21view1turn21view4turn21view6turn22view5

### URL Inspection API for live index status

```bash
ACCESS_TOKEN="$(gcloud auth print-access-token)"
SITE_URL="sc-domain:twocomms.shop"

curl -s \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -X POST \
  "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect" \
  -d "{
    \"inspectionUrl\": \"https://twocomms.shop/product/clasic-tshort/\",
    \"siteUrl\": \"${SITE_URL}\",
    \"languageCode\": \"en-US\"
  }" | jq .
```

Проверяйте минимум:
- homepage
- category
- PDP
- `/custom-print/`
- `/favorites/`
- `/novyny/`
- `/ru/...`
- `/en/...`

**Подтверждает**: индексируемость, каноникал, mobile usability, rich result detection, blockade from noindex/robots. citeturn20search0turn20search9turn20search3

### Search Console API for country-language segmentation

```bash
ACCESS_TOKEN="$(gcloud auth print-access-token)"
PROPERTY="sc-domain:twocomms.shop"

curl -s \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -X POST \
  "https://www.googleapis.com/webmasters/v3/sites/${PROPERTY}/searchAnalytics/query" \
  -d '{
    "startDate": "2026-04-01",
    "endDate": "2026-05-10",
    "dimensions": ["query","page","country","device"],
    "rowLimit": 25000
  }' | jq .
```

Это нужно, чтобы проверить, реально ли есть uk-UA / ru-UA / en demand mismatch и бьет ли hreflang/locale routing по показам и CTR. citeturn20search5turn19search22

### Rich Results Test manual runs

```text
https://search.google.com/test/rich-results?url=https://twocomms.shop/
https://search.google.com/test/rich-results?url=https://twocomms.shop/product/clasic-tshort/
https://search.google.com/test/rich-results?url=https://twocomms.shop/custom-print/
https://search.google.com/test/rich-results?url=https://twocomms.shop/novyny/
```

Смотрите отдельно:
- Product snippets
- Merchant listing warnings
- Organization
- Breadcrumbs
- Article/FAQ if any

**Подтверждает**: что разметка не просто присутствует, а распознается инструментом Google. citeturn16search8turn21view1turn22view4turn22view5

### Schema.org validator runs

```text
https://validator.schema.org/#url=https://twocomms.shop/
https://validator.schema.org/#url=https://twocomms.shop/product/clasic-tshort/
https://validator.schema.org/#url=https://twocomms.shop/custom-print/
https://validator.schema.org/#url=https://twocomms.shop/novyny/
```

Это не равно Google eligibility, но быстро выявляет синтаксис и типы (`ProductGroup`, `MerchantReturnPolicy`, `MemberProgram`, `OfferShippingDetails`). citeturn18search16turn17search2turn18search2turn5search1

### Проверка noindex / robots.txt interplay for utility pages

```bash
for u in \
  "https://twocomms.shop/favorites/" \
  "https://twocomms.shop/cart/" \
  "https://twocomms.shop/account/" \
  "https://twocomms.shop/faq/" \
  "https://twocomms.shop/track-order/"; do
  echo "===== $u ====="
  curl -I "$u"
  curl -sL "$u" | grep -Eio '<meta[^>]+name="robots"[^>]*>'
done

curl -sL https://twocomms.shop/robots.txt
```

Если utility pages завязаны только на robots.txt без `noindex`, finding о слабой indexation policy усиливается; если там уже `noindex,follow` или auth/403, мой риск-профиль снижается. citeturn22view1turn22view2turn9search6turn9search7

### Проверка `x-default` и полной hreflang-матрицы из sitemap

```bash
curl -sL https://twocomms.shop/sitemap.xml | \
  grep -Eo 'hreflang="[^"]+"|<loc>[^<]+' | sed 's/<loc>//'
```

Если используется sitemap-level hreflang, каждая версия URL должна перечислять **все** alternates, включая себя. Это самый быстрый способ поймать half-matrix. citeturn22view0turn19search19

### LCP / image priority verification

```bash
lighthouse https://twocomms.shop/product/clasic-tshort/ \
  --preset=desktop \
  --only-categories=performance \
  --view

lighthouse https://twocomms.shop/ \
  --preset=desktop \
  --only-categories=performance \
  --view
```

Параллельно проверьте в rendered DOM:

```bash
node <<'JS'
const { chromium } = require('playwright');
(async() => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('https://twocomms.shop/', { waitUntil: 'networkidle' });
  const imgs = await page.$$eval('img', els => els.map(e => ({
    src: e.currentSrc || e.src,
    alt: e.alt,
    loading: e.getAttribute('loading'),
    fetchpriority: e.getAttribute('fetchpriority'),
    width: e.getAttribute('width'),
    height: e.getAttribute('height')
  })));
  console.log(JSON.stringify(imgs, null, 2));
  await browser.close();
})();
JS
```

Это покажет, есть ли фактический `fetchpriority="high"` на candidate LCP image, не ленится ли она, и заданы ли intrinsic dimensions. citeturn7search8turn7search3turn21view2

### News/updates hub reality check

```bash
curl -sL https://twocomms.shop/novyny/ | \
  grep -Eio '<title>.*</title>|<meta[^>]+name="robots"[^>]*>|<link[^>]+rel="canonical"[^>]*>|application/ld\+json'
```

Если это действительно editorial section, должны быть article-detail URLs, публикационные даты, authorship and/or `BlogPosting`/`Article`. Если нет — section should be recast as utility hub or deindexed. citeturn3view3turn24search17