# SEO/GEO and Database-backed Localization Audit

## Scope and Status

- Owner: SEO/GEO contract and public database-backed product content only.
- Status: audit complete, read-only. No application code, gettext catalog,
  migration, test, production database, or deployment change has been made.
- Excludes: catalog control copy, Custom Print UI, cart/checkout overlays, and
  static-page body copy owned by the parallel audits. This file records only
  cross-cutting crawler contracts and public data ownership that affect those
  surfaces.
- Live evidence: anonymous HTTPS GET requests to `https://twocomms.shop` on
  2026-08-19. No forms, lead submissions, cart mutations, payments, or test
  analytics events were sent.
- Production MariaDB is authoritative. `TWOCOMMS_DEPLOY_PASSWORD` is absent in
  this execution environment, so no SSH or database assertion has been made.
  A password pasted into chat was not used.

## Verified Baseline to Preserve

- `/`, `/ru/`, and `/en/` return `Content-Language: uk`, `ru`, and `en`
  respectively. Their `html[lang]` values are `uk-UA`, `ru-UA`, and `en-UA`.
- The shared shell emits self locale canonicals, reciprocal `uk-UA`, `ru-UA`,
  `en-UA`, and `x-default` alternates, and the correct Open Graph locale on the
  sampled home routes. Do not replace this shared mechanism with manually
  concatenated paths.
- Product schema already derives `inLanguage` from the active Django locale and
  carries the locale-prefixed canonical URL when the view provides one. The
  correction work must keep those behaviors intact.

## Confirmed Findings

### DATA-P0-01: Selection-state data overwrites EN/RU PDPs with Ukrainian

- **Routes/locales:** confirmed on
  `https://twocomms.shop/en/product/futbolka-boiova-kvitochka/`; the matching
  RU route returns the same database-owned selection model under
  `Content-Language: ru`.
- **Live evidence:** an anonymous production GET on 2026-08-19 returned
  `Content-Language: en`, but the page still contained
  `alt="Product — Термо-зелена — product photo 1 TwoComms"`,
  `термохромна тканина`, and `Для цього кольору доступний лише оверсайз`.
  The same source is serialized in `#variant-data`, then reused by the PDP
  after a selection change. The product's title, meta, Open Graph, Product
  JSON-LD name, breadcrumb leaf, and variant SEO fields are also Ukrainian
  where their reviewed EN rows are absent.
- **Important refinement:** the initially rendered colour swatch is not proof
  that every colour is broken. The template applies `translate_color`, and
  `productcolors/color_i18n.py` already knows `Термо-зелена -> Thermo green`.
  The leak occurs because `get_detailed_color_variants()` constructs its JSON
  `name` with `_display_color_name()` (a different bare-gettext path) and
  passes that value directly to image-alt generation. `product-detail.js`
  later writes `variant.name` into the dynamic size-guide header and restock
  dialog. Thus a switch can regress a correctly rendered static label back to
  Ukrainian.
- **Source evidence:** `Color.name`, `ColorProfile.thermo_note`,
  `ColorProfile.description`, `ProductFitOption.description`,
  `ProductFitNote.reason`, and `VariantFitRule.reason` are single-language
  fields. `product_catalog/services.py` returns raw thermo defaults, raw
  material copy, and raw fit-rule reasons; its one-fit fallback is itself a
  Ukrainian f-string. `storefront/services/catalog_helpers.py` lines 90-95 and
  519-598 use the incomplete colour path and build image alts from it;
  `product-detail.js` lines 1518-1546 and 1595-1606 consume the raw payload.
  The generic `classic`/`oversize` option labels do have a gettext path, but
  free-text descriptions and availability reasons do not. The sparse
  merchandising resolver only localizes its own i18n rows, not these fields.
- **Impact:** P0 conversion and P1 SEO/GEO. A shopper sees a mixed-language
  fit/colour/price decision surface; crawlers receive `inLanguage: en-UA` with
  Ukrainian Product name/properties.
- **Safe fix boundary:** define one explicit locale-owned variant-presentation
  contract. Generic stable codes (for example `classic`, `oversize`, and
  thermo defaults) may resolve through reviewed gettext. Editorial/truthful
  values (colour names, material story, price reasons, disabled-fit reason,
  image alt, per-variant title/SEO) require RU/EN database rows, never an
  automatic Ukrainian copy. Extend existing sparse i18n rows where suitable;
  do not translate prices or availability by string substitution.
- **Verification:** render a thermo and a non-thermo product at UA/RU/EN on
  desktop and mobile; inspect initial DOM and post-selection `#variant-data`,
  Product/Breadcrumb JSON-LD, meta, image alts, and price/fit controls. Verify
  a missing locale row degrades to a truthful non-owner/noindex state rather
  than presenting a false translated owner.

### DATA-P1-02: Translation coverage reports omit public selection data

- **Live evidence:** this is an operational-quality package rather than a
  direct page defect. The confirmed PDP leakage above is absent from both
  built-in coverage outputs, so the programme could report high product
  translation coverage while the buyer still sees Ukrainian variant content.
- **Source evidence:**
  `storefront/management/commands/check_translation_coverage.py` only iterates
  the eleven `ProductTranslationOptions` fields. `audit_translations.py` only
  scans `Category`, `Product`, and `ProductFAQ`. Neither command inventories
  `VariantDetailsI18n`, `ProductOptionProfileI18n`,
  `VariantCombinationProfileI18n`, `VariantImageAltI18n`,
  `ProductImageAltI18n`, colour profiles, fit rules, size grids, or public
  option values.
- **Impact:** P1 delivery control. The user-requested completion percentage
  cannot be trusted without counts for buyer-visible variant and fit data;
  it also leaves a false-positive SEO/GEO readiness signal.
- **Safe fix boundary:** keep the existing product reports backward-compatible
  and add a separate, read-only locale-ownership report for public selection
  data. It must distinguish: generic gettext-owned labels, reviewed RU/EN
  database rows, deliberately non-indexable fallback routes, and raw
  single-language fields. It must never infer a translation merely because a
  Ukrainian fallback is non-empty.
- **Verification:** fixtures must include a translated base product with a
  missing variant EN row, a known runtime-colour mapping, and an untranslated
  fit reason. The report must flag the latter two selection owners while the
  existing base-product report remains unchanged.

### SEO-P1-01: Home WebPage JSON-LD points RU/EN pages back to the Ukrainian root URL

- **Routes/locales:** `/ru/` and `/en/`.
- **Live evidence:** both pages have locale-correct canonical and `html[lang]`,
  but their page-level `WebPage` node reports `@id` and `url` as
  `https://twocomms.shop/`. The node's `inLanguage` is correctly `ru-UA` or
  `en-UA`, so the URL/language pair is internally inconsistent.
- **Source evidence:** `pages/index.html` builds the home `WebPage` and
  `BreadcrumbList` with hard-coded `{{ site_base_url }}/` paths instead of the
  current locale-aware request/canonical URL.
- **Impact:** P1 SEO/GEO. Search and AI crawlers receive an entity identity
  that conflicts with the page canonical and its localized ItemList links.
- **Safe fix boundary:** use the same locale-aware canonical path for
  `WebPage.@id`, `WebPage.url`, breadcrumb item, and paginated home variants.
  Keep organization-level `@id`/`url` at the stable root; only page nodes must
  be locale-specific.
- **Verification:** parse all three home JSON-LD payloads; each WebPage `url`
  and `@id` must equal its canonical URL, while Organization/WebSite IDs remain
  stable intentionally.

### SEO-P1-02: Static sitemap and generic hreflang publish non-owned language pages

- **Routes/locales:** all `StaticViewSitemap` routes; confirmed examples include
  `/en/cooperation/`, `/ru/cooperation/`, `/en/contacts/`, and
  `/en/rozmirna-sitka/`, where the parallel static-page audit has live
  Ukrainian content evidence.
- **Live/source evidence:** `sitemap-static.xml` publishes UA, RU, and EN URL
  entries with reciprocal alternates for every static route. `StaticViewSitemap`
  unconditionally sets `i18n = alternates = x_default = True`; the base shell
  similarly emits generic alternates unless a view supplies a special owner
  policy. Unlike products, there is no per-route content-ownership gate.
- **Impact:** P1 SEO/GEO. A localized `hreflang` cluster claims equivalent
  Russian/English content even where the visible body and FAQ still fall back
  to Ukrainian.
- **Safe fix boundary:** introduce a small explicit publication registry for
  static routes, based on translated head, H1/body, and structured data
  ownership. First localize the P0/P1 source copy; until a route is owned,
  remove it from foreign-language sitemap/alternate clusters and emit a
  non-owner policy deliberately. Do not globally remove all RU/EN routes or
  alter the product-specific policy.
- **Verification:** one sitemap and one head matrix for every registry route;
  each advertised alternate must respond 200 with matching visible language,
  canonical, JSON-LD, and `Content-Language`.

### SEO-P1-03: Product publication eligibility ignores variant-owned content

- **Source evidence:** `locale_publication.py` decides RU/EN product ownership
  from product title, SEO title/description, one editorial field, and generic
  ProductFAQ rows. It does not inspect `VariantDetailsI18n`,
  `VariantCombinationProfileI18n`, `VariantFAQ`, `ColorProfile`, fit rules, or
  image-alt rows. The public variant context emits those values on selected
  PDPs.
- **Impact:** P1 SEO/GEO. A base product can be treated as an indexable RU/EN
  owner while a colour/fit selection inserts Ukrainian user-facing text and
  Product JSON-LD properties.
- **Safe fix boundary:** keep the base product gate, but add an explicit
  selection-level ownership rule before advertising a locale-specific variant
  canonical/hreflang/sitemap URL. The rule must distinguish non-editorial
  generic gettext labels from database-owned claims.
- **Verification:** fixture matrix with translated base product and deliberately
  missing variant RU/EN data; assert the base policy and every selected variant
  cannot become a false locale owner.

### SEO-P2-01: Product variant sitemap is Ukrainian-only while public variant URLs may self-canonicalize

- **Source evidence:** `ProductVariantSitemap` has no i18n/alternates flags and
  constructs `/product/<slug>/<variant>/` entries under the default locale.
  The PDP/schema code can generate locale-prefixed self-canonical colour/fit
  URLs when locale-owned content exists.
- **Impact:** P2 crawl-discovery policy gap. This is not a request to multiply
  the sitemap today; it needs a deliberate decision after variant localization
  coverage is known.
- **Safe fix boundary:** either keep foreign language variants non-indexable
  until fully owned, or emit only locale-owned variants using the same
  selection-level policy as SEO-P1-03. Never publish all three variants from a
  generic fallback.
- **Verification:** compare generated sitemap rows with live canonical URLs and
  `locale_publication` eligibility for a translated and untranslated product.

## Database Localization Inventory

### Existing good primitives

- `Product`, `Category`, and `ProductFAQ` use modeltranslation; products have
  `title`, descriptions, audience/care copy, image alt, and core SEO fields.
- Sparse `VariantDetailsI18n`, `ProductOptionProfileI18n`, and
  `VariantCombinationProfileI18n` already provide RU/EN merchandising fields.
- `VariantFAQ`, `AudienceTag`, and `MerchCollection` already have explicit
  per-language columns. Reuse these instead of inventing parallel JSON blobs.

### Gaps requiring a production-first report

- `Color`, `ColorProfile`, `ProductFitOption`, `ProductFitNote`,
  `VariantFitRule`, `VariantSizeRule.note`, `SizeGrid.name`,
  `SizeGrid.description`, `SizeGrid.guide_data`, `CatalogOption`, and
  `CatalogOptionValue` have public strings but no complete locale ownership
  model.
- `ProductColorImage.alt_text` and `ProductImage.alt_text` are single-language.
  `VariantImageAltI18n` and `ProductImageAltI18n` already exist, but no public
  reader queries them: the current `build_product_image_alt()` deliberately
  ignores legacy stored alt text outside Ukrainian and synthesizes a fallback.
  This is protective for arbitrary stored copy, but the fallback receives the
  incomplete `_display_color_name()` result, which explains the confirmed
  thermochromic EN alt leak. Reuse these i18n rows for reviewed rich media alt
  rather than creating another alt schema.
- `ProductMerchCollection.display_label` is single-language and can override
  already localized `MerchCollection` names.
- Product long descriptions and per-product SEO remain a deferred editorial
  backfill. Do not mass-copy from Ukrainian or local SQLite.

## Production MariaDB Read-only Plan (Blocked Pending Safe Credential)

Run only after `TWOCOMMS_DEPLOY_PASSWORD` is provided through the environment,
using the approved SSH path and the production Django virtualenv. Capture
counts and IDs/slugs, not customer data.

1. Run `manage.py check_translation_coverage --json` and
   `manage.py audit_translations` on production as a base-product baseline,
   explicitly recording that neither report covers selection data.
2. Query published products whose raw `title_ru`/`title_en`, `seo_title_*`,
   `seo_description_*`, and all editorial fields are blank; rank by homepage,
   catalog, sitemap, and order/view traffic if already available without adding
   tracking.
3. Count `VariantDetailsI18n`, `ProductOptionProfileI18n`,
   `VariantCombinationProfileI18n`, `VariantImageAltI18n`, and
   `ProductImageAltI18n` rows by `lang`; join only published product IDs and
   identify selected variant rows with missing language ownership.
4. Report non-empty public single-language fields for `ColorProfile`, fit
   rules/notes, `SizeGrid`, option labels, image alts, and merchandising
   `display_label`; include the affected published product IDs/slugs.
5. Produce a route-level owner matrix: base PDP, each colour/fit canonical,
   category, colour landing, thematic landing, and static route. Compare it to
   `sitemap-*.xml`, canonical, hreflang, robots, and JSON-LD before any data
   update.

## Final Package Tally

| Priority | Packages | Count | State |
| --- | --- | ---: | --- |
| P0 | `DATA-P0-01` | 1 | Confirmed live and source-mapped |
| P1 | `DATA-P1-02`, `SEO-P1-01`, `SEO-P1-02`, `SEO-P1-03` | 4 | Confirmed source-mapped; static-route ownership uses parallel live evidence |
| P2 | `SEO-P2-01` | 1 | Confirmed policy gap |
| Total | All discrete packages above | 6 | 0 / 6 implemented in this workstream |

## Exact Blocker

There is no blocker to source-level implementation or test design. The sole
blocker is production MariaDB inventory and editorial backfill validation:
`TWOCOMMS_DEPLOY_PASSWORD` is not present in this process, so the approved
SSH-only production read path cannot be used yet. No password from chat was
used or retained. Until that read-only inventory is available, do not claim a
database completion percentage or mass-fill RU/EN product, variant, or SEO
fields from local SQLite.

## Completion Criteria for This Workstream

- Every public UA/RU/EN page has matching HTTP language, `html[lang]`, title,
  H1, meta, canonical/hreflang, Open Graph/Twitter, visible data, internal
  links, and JSON-LD page identity/language.
- Only content actually owned in a locale is indexable or advertised as an
  alternate/sitemap owner.
- Product and variant data backfills are reviewed editorially and verified in
  production; no local SQLite inference or automatic Ukrainian copying.
