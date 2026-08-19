# Catalog Localization Audit

## Scope and Audit Status

- Owner: catalog workstream.
- Status: audit complete. CATALOG-P0-01 through CATALOG-P0-03 are source-complete,
  independently reviewed, and live-confirmed through final code SHA
  `3de4c6a7d`. The historical interaction matrix ran on `f239538c6`; the
  post-fix selector-note asset and route checks ran on `3de4c6a7d`.
  Production product content was not changed.
- Safe live GET checks covered: /catalog/, /en/catalog/, /ru/catalog/,
  /catalog/tshirts/, /en/catalog/tshirts/, /ru/catalog/tshirts/,
  /en/catalog/theme/military/, /ru/catalog/theme/military/,
  /en/catalog/tshirts/black/, and /ru/catalog/tshirts/black/.
- Device surface: desktop HTML and `390x844` mobile selector interaction checks
  cover UA/RU/EN. No analytics/pixel event was deliberately generated.
- Production MariaDB was queried read-only for migration/schema/counters only;
  translation inventory and product-content writes remain deferred. Credentials
  are loaded locally and never copied into this ledger.

## Confirmed P0

### CATALOG-P0-01: Smart Selector is mixed-language before and after interaction

- Release status: live-confirmed on `f239538c6` for the selector interaction
  matrix, then rechecked on `3de4c6a7d` after the localized quick-note fix;
  the fresh hashed CSS/JS assets returned `200`.

- Locales: en, ru; routes: category catalog pages for T-shirts, hoodies, and
  longsleeves.
- User effect: mobile discovery filters are a primary conversion path, but an
  English/Russian shopper sees Ukrainian sheet headings, quick facets, filter
  groups, empty state, pagination feedback, and close/apply actions.
- Live evidence on /en/catalog/tshirts/ and /ru/catalog/tshirts/: Підібрати модель,
  Швидкий вибір, Сортування, Показати всі, Будь-який крій, Усі, Будь-який,
  Обрані фільтри, Доступність, and Технологія are emitted in Ukrainian.
- Server cause:
  [catalog_smart_selector.html](../twocomms/twocomms_django_theme/templates/partials/catalog_smart_selector.html)
  uses trans tags, but EN/RU PO files lack the new selector labels, filter
  sections, empty-result copy, progressive-load copy, pages label, and sheet
  actions.
- Client cause:
  [catalog-smart-selector.js](../twocomms/twocomms_django_theme/static/js/catalog-smart-selector.js)
  hard-codes Ukrainian sheetModes at lines 52-56, quick-facet defaults at line
  310, and the selected-count suffix at line 320. JS overwrites localized
  template values after interaction.
- Required implementation: expose a complete locale payload from the template,
  make JS consume only that payload, add EN/RU gettext entries, compile messages,
  and bump the versioned selector asset.
- Acceptance: static and interaction-driven selector UI contain only the selected
  language on desktop/mobile; filter routes preserve the /en/ or /ru/ prefix.

### CATALOG-P0-02: root catalog filter CTA remains Ukrainian in EN/RU

- Release status: live-confirmed on `f239538c6` for the EN/RU root filter CTA;
  the final SHA retained the locale-owned `Show products` and `Показать товары`
  strings on desktop and mobile.

- Locales: en, ru; routes: /en/catalog/ and /ru/catalog/.
- Live evidence: the root filter dialog is otherwise localized, but its submit
  button is Показати товари on both pages.
- Source:
  [catalog.html](../twocomms/twocomms_django_theme/templates/pages/catalog.html)
  wraps the CTA in trans 'Показати товари', while neither EN nor RU PO contains
  that msgid.
- Acceptance: EN says Show products; RU says Показать товары; locale-aware form
  action and reset continue to use reverse('catalog').

### CATALOG-P0-03: root catalog SEO rail loses both language and locale route

- Release status: live-confirmed on `f239538c6` for all synthetic rail targets;
  final safe GET probes on `3de4c6a7d` returned `200` for the UA/RU/EN root and
  T-shirt catalog routes without a new `Unknown column` log entry.

- Locales: en, ru; route: root catalog pages.
- Live evidence: /en/catalog/ and /ru/catalog/ emit six Ukrainian labels:
  Військовий streetwear, Стрітвір з кодом, Патріотичний одяг,
  Харківська лінія, Кастомний DTF-друк, and Співпраця з брендами. Every rail
  link, including translated support links, points to an unprefixed URL such as
  /catalog/theme/military/, /delivery/, /custom-print/, or /pro-brand/.
- Source:
  [general_catalog_seo.py](../twocomms/storefront/services/general_catalog_seo.py)
  uses raw catalog and support paths at lines 76-105. The six EN/RU gettext
  msgstr values are blank.
- User and SEO/GEO effect: a localized visitor is silently taken to the
  Ukrainian funnel; anchors and linked content do not match the page language.
- Required implementation: build every item with Django reverse under the active
  locale and translate the six missing labels. Do not prefix URLs manually.
- Acceptance: every root SEO-rail label uses the active language and every
  target retains the active locale prefix. Editorial language, canonical, and
  hreflang ownership inside the linked thematic landing remains CATALOG-P0-04.

### CATALOG-P0-04: thematic catalog landings are Ukrainian on EN/RU routes

- Locales: en, ru; all four themes share the same source: military, streetwear,
  patriotic, and kharkiv-edition.
- Live evidence on /en/catalog/theme/military/ and /ru/catalog/theme/military/:
  H1 is Військовий стрітвір TwoComms — мілітарі-одяг із харківським кодом;
  title and meta description are Ukrainian; the page is noindex, follow, while
  canonical, Open Graph, and Twitter URLs point to /catalog/theme/military/.
  Structured breadcrumb calls the thematic route Catalog rather than the theme.
- Source:
  [catalog.py](../twocomms/storefront/views/catalog.py) stores all title, H1,
  intro, description, and keyword text in a Ukrainian-only
  THEMATIC_LANDINGS_CONFIG (lines 2459 onward). The render context inserts it
  without locale selection around lines 2648-2700 and hard-codes Ukrainian
  breadcrumb names plus an unprefixed canonical path.
- Required implementation: add an explicit editorial locale structure for all
  four landing records; localize H1/title/meta/intro/keywords/breadcrumbs and
  make canonical/JSON-LD follow the active locale. Make RU/EN indexable only
  after approved localized editorial content exists.
- Acceptance: all primary SEO fields and visible landing copy agree with the
  requested language; no EN/RU page emits a Ukrainian canonical or schema owner.

## Confirmed P1

### CATALOG-P1-01: product title fallback leaks Ukrainian through cards and linked PDPs

- Locales: en, ru; routes: /en/catalog/tshirts/ and /ru/catalog/tshirts/.
- Live evidence: examples include Футболка «Правил немає» and
  Футболка «Бойова квіточка» in EN card titles and ARIA labels. Following the
  localized URL preserves the Ukrainian H1/breadcrumb/title when the product
  lacks an English/Russian record.
- Source: Ukrainian fallback is configured in
  [settings.py](../twocomms/twocomms/settings.py) around line 942; product
  fields are registered in [translation.py](../twocomms/storefront/translation.py)
  around line 69.
- Data policy: do not infer translations from local SQLite or mass-copy source
  strings. First run a read-only production report of published products with
  blank title_en/title_ru and priority SEO fields, then editorially backfill
  high-traffic products.
- Acceptance: prioritized cards and PDPs have approved localized titles and
  SERP-facing metadata; remaining gaps are measurable instead of hidden by
  fallback.

### CATALOG-P1-02: color-category landing pages serve Ukrainian content on EN/RU URLs

- Routes /en/catalog/tshirts/black/ and /ru/catalog/tshirts/black/ return 200,
  but title, H1, meta description, FAQ/editorial content, and schema are
  Ukrainian (for example Чорні футболки TwoComms...).
- Source: CategoryColorLanding has one-language seo_title, seo_h1,
  seo_description, editorial_html, and faq_items fields in
  [models.py](../twocomms/storefront/models.py) around lines 3255-3324. The view
  renders those fields unchanged in [catalog.py](../twocomms/storefront/views/catalog.py)
  around lines 2302-2438 and declares EN/RU variants noindex via
  uk_only_publication_context.
- Recommendation: treat this as a schema/editorial migration, not a gettext
  patch. Until localized owners exist, canonicalize or redirect direct EN/RU
  requests to the Ukrainian owner rather than presenting mismatched content.
- SEO/GEO: do not add multilingual hreflang/indexability until content and
  structured data are locale-owned.

### CATALOG-P1-03: locale-less merchandising display labels can override taxonomy

- Source:
  [catalog.py](../twocomms/storefront/views/catalog.py) prefers
  ProductMerchCollection.display_label over the localized collection name when
  building card context (around lines 996-1060). display_label is a single field
  in [product_catalog/models.py](../product_catalog/models.py) line 219.
- Risk: an administrator-entered Ukrainian label can appear in EN/RU filter
  context or cards even though MerchCollection name_uk/name_ru/name_en and
  AudienceTag label fields are localized.
- Follow-up: run a production read-only audit of non-empty display labels; either
  make them localizable or use them only for Ukrainian presentations.

## Confirmed P2

### CATALOG-P2-01: fit and thermochromic accessibility labels leak Ukrainian

- Live evidence: EN/RU smart cards have aria-label="Доступні крої" while visible
  fit labels are localized. EN thermochromic swatches render
  Thermo green, термохромний колір; RU renders
  Термо-зелёная, термохромний колір.
- Source:
  [catalog_smart_product_card.html](../twocomms/twocomms_django_theme/templates/partials/catalog_smart_product_card.html)
  uses missing gettext keys Доступні крої, Термохромний колір, and
  термохромний колір around lines 93-128. Standard
  [product_card.html](../twocomms/twocomms_django_theme/templates/partials/product_card.html)
  additionally hard-codes термохромна тканина in title and aria-label around
  lines 82 and 89.
- Acceptance: all visible and assistive card text is UA/RU/EN as selected;
  screen-reader text never uses a different language than the control.

## Verified Safe Paths

- Root mobile showcase, category links, category card titles, availability,
  color labels, and root filter groups are localized on sampled EN/RU routes.
  Existing reverse links preserve the locale.
- Standard EN/RU category SEO rail uses the locale-safe branch in
  get_locale_safe_product_seo_layout() and live links stay under /en/ or /ru/.
  Do not replace it with the root catalog raw URL builder.
- Smart-card color trigger and color group labels are translated; only fit and
  thermochromic labels above are missing.

## Final Release Evidence

- The historical browser matrix covered 24 UA/RU/EN catalog desktop/mobile
  probes and the conversion matrix covered six cart plus six mini-cart probes.
  The final post-fix checks also covered the three localized Monobank return
  messages and the locale-prefixed cart redirects.
- Localization runtime evidence is anchored to `3de4c6a7d`; later `main`
  commits do not alter this localization code. The only schema remediation was
  the exact `python manage.py migrate storefront 0097 --noinput` command after
  a read-only duplicate preflight; no broad migration or ReviewVote canary ran.
- `storefront.0097` is applied. `default_product_identity` is a STORED generated
  `bigint` with the expected unique BTREE, and the web-push endpoint is
  `varchar(1000)` with a unique HASH index. Production counters remain
  `orders=64`, `payment_attempts=12`.
- A stale in-memory WhiteNoise map required terminating the exact old `lswsgi`
  master PID after the pull. The fresh runtime returned health, CSS, and JS
  assets with `200`; no new `Unknown column` error appeared in the resulting
  `stderr.log` delta.

## Test Gaps and Required Regression Coverage

1. The thematic landing H1/title/meta/canonical/JSON-LD ownership still lacks a
   complete locale matrix; the root SEO-rail label and prefixed-URL contract is
   covered by `test_rendered_locale_matrix.py`.
2. Add direct tests for color-landing EN/RU behavior after product direction is
   chosen: localized owner or explicit Ukrainian redirect, never a localized URL
   with Ukrainian content.

## Verification Protocol

1. Run the focused Django locale tests plus new regression cases with the
   project CPython 3.14/Django 6.1 runtime.
2. Inspect rendered HTML for UA, RU, and EN catalog root, T-shirt category, and
   each thematic landing: Content-Language, html lang, title, H1, visible
   controls, canonical, hreflang, Open Graph URL, and JSON-LD owner must agree.
3. Use a no-click mobile/browser or DOM check for the selector sheet and quick
   facets after open, apply, reset, sort, empty-result, and load-more states.
4. Verify every synthetic root SEO rail link retains the active locale. Verify
   EN/RU color landings follow the chosen product policy rather than returning a
   mismatched 200 page.
5. After each approved release, repeat safe live GET checks on production before
   marking any finding verified live; this gate is satisfied for P0-01..03 in
   the current batch.

## Implementation Order

1. P0-01 Smart Selector server/JS copy and P0-02 root apply CTA.
2. P0-03 locale-safe root SEO rail and its gettext gaps.
3. P0-04 thematic landings with editorially reviewed UA/RU/EN SEO copy.
4. P1 production report/backfill for product and merchandising data, then a
   separately approved color-landing schema strategy.
5. P2 accessibility copy in shared card templates.

## Handoff

- Cart/checkout/minicart findings belong to 04-conversion-and-overlays.md; no
  cart code is included in this catalog workstream.
- PDP size-grid, fit descriptions, technologies, and variant detail data belong
  to 02-product-detail.md; catalog evidence only records where those gaps first
  become visible in discovery.
