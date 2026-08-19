# Product Detail, Fit, Technology, and Size Localization Audit

## Scope and status

- **Owner:** primary localization program audit.
- **Scope:** public PDP variants, fit and size controls, technology/material
  narratives, restock dialog, product media, related products, and associated
  structured data on UA/RU/EN routes.
- **Status:** source and safe live GET audit complete; no application code,
  gettext catalog, database data, order, or analytics state was changed.
- **Live sample:** `/product/futbolka-pravyl-nemaie/`,
  `/ru/product/futbolka-pravyl-nemaie/`, and
  `/en/product/futbolka-pravyl-nemaie/`. The sample deliberately used GET
  only: no cart, restock, payment, or telemetry action was submitted.
- **Production data:** `TWOCOMMS_DEPLOY_PASSWORD` is unavailable, so MariaDB
  records are not inferred from local SQLite.

## Confirmed P0 findings

### PDP-P0-01: Variant and option changes overwrite RU/EN UI with Ukrainian copy

- **Routes/locales:** every PDP where a shopper changes colour, fit, material,
  or another product option on `/ru/` or `/en/`.
- **Source:** `static/js/product-detail.js` hard-codes Ukrainian dynamic
  messages for unavailable option combinations, price deltas, unavailable
  state, price-reason title/copy, thermochromic material story, and material
  labels around lines 1294-1537. It also fixes `Intl.NumberFormat` to
  `uk-UA` and appends `грн`.
- **Impact:** the initial server-rendered fit/size controls can be correct, but
  a normal shopper action replaces them with Ukrainian at the exact
  configuration and add-to-cart decision point.
- **Required boundary:** extend the server-owned PDP locale payload with all
  dynamic strings, the BCP-47 formatter locale, the currency label, and
  locale-aware endpoints. The module must consume that payload rather than
  keep per-branch Ukrainian fallbacks.
- **Verification:** DOM-level UA/RU/EN tests for colour, fit, fixed option,
  unavailable combination, thermochromic/ordinary material, price delta, and
  sticky price on desktop and `390x844` mobile.

### PDP-P0-02: Restock flow has Ukrainian client-side outcomes after a shopper acts

- **Routes/locales:** unavailable-size/restock flow on RU/EN PDPs.
- **Source:** `static/js/product-detail.js` builds Ukrainian selected-product
  labels, contact fields, validation/error states, and success outcomes around
  lines 2647-2844. The public restock modal template is initially localized,
  so the runtime code can undo it.
- **Impact:** an English or Russian shopper who asks to be notified about an
  unavailable size gets a mixed-language modal/error state.
- **Required boundary:** add the restock strings and current localized API URL
  to the same PDP payload; server errors must use gettext or stable error codes
  before the browser displays them. Preserve subscription idempotency and do
  not use a live subscription as a test fixture.
- **Verification:** mocked successful, duplicate, invalid contact, expired
  Telegram, network, and server-validation paths for all three locales.

## Confirmed P1 findings

### PDP-P1-01: Server-rendered related and sticky prices expose `грн` on EN/RU

- **Live evidence:** `/en/product/futbolka-pravyl-nemaie/` contains English
  main price `1090 UAH`, while related-product prices and the mobile sticky
  price use `грн`; RU has the same suffix. This produces mixed monetary
  terminology inside one purchase surface.
- **Source:** `templates/pages/product_detail.html` writes raw `грн` in the
  related-products block and sticky purchase bar around lines 817 and 842-843.
- **Required boundary:** use the reviewed existing gettext currency label,
  matching the PDP dynamic formatter and initial price output. Amounts stay
  numeric and server-authoritative.
- **Verification:** full PDP price surface on UA/RU/EN before and after a
  variant choice; no locale may mix `UAH` and Ukrainian currency text.

### PDP-P1-02: Product title fallback reaches the highest-intent PDP and size-guide captions

- **Live evidence:** the English sample renders Ukrainian `Футболка «Правил
  немає»` as the H1 and in size-chart captions. RU does the same for the
  sampled item. Related cards can repeat the same fallback.
- **Source:** `Product` title is modeltranslation-backed, but
  `MODELTRANSLATION_FALLBACK_LANGUAGES` intentionally falls back to Ukrainian;
  the template uses `product.title` in the H1, data payload, image alt
  fallback, size-guide captions, and JSON-LD contexts.
- **Ownership:** production DB content, not a string-replacement defect.
- **Required boundary:** query production published PDPs for blank
  `title_ru`/`title_en`, prioritise product and homepage-visible rows, and
  editorially backfill titles before descriptions. Do not manufacture titles
  from local data or hide an in-stock product without an agreed publication
  policy.
- **Verification:** production report shows coverage for the selected product
  cohort; live UA/RU/EN H1, title, breadcrumb, alt text, caption, and JSON-LD
  name match the requested locale.

### PDP-P1-03: Fit, size-grid, technology, and reason data lack a complete locale ownership model

- **Source:** `SizeGrid.name`, `description`, and `guide_data` are single
  fields in `storefront/models.py`; `ProductFitOption.label` and `description`
  are also single-language. `product_catalog` additionally stores single-value
  `ColorProfile.thermo_note`/`description`, `ProductFitNote.reason`,
  `VariantFitRule.reason`, `VariantSizeRule.note`, and
  `ProductMerchCollection.display_label`.
- **Live evidence:** the English sample has localized source-owned guide
  chrome, but the product-titled captions remain Ukrainian; the static size
  audit separately found live production `SizeGrid` records leaking Ukrainian
  and English strings across locales.
- **Impact:** the very modules users rely on for fit and technology can become
  mixed-language even after generic UI gettext is complete.
- **Required boundary:** inventory the live rows first, then adopt the already
  existing localized merchandising row pattern (`VariantDetailsI18n`) or a
  scoped equivalent for public fit/size/technology content. Backfill only
  reviewed per-language values. A schema/data decision is required before a
  migration.
- **Verification:** every active fit/guide/technology record is rendered and
  checked across UA/RU/EN, including button labels, unavailable reason, notes,
  image alt/caption, HowTo/product schema, and mobile size sheet.

### PDP-P1-04: Variant technology SEO is only as localized as the data row

- **Source:** `VariantDetails` has an established `VariantDetailsI18n` model,
  but the base `display_name`, price reason, marketing HTML, and SEO fields can
  still be Ukrainian when an RU/EN row is absent. The PDP updates title/meta
  dynamically from that payload.
- **Risk:** a selected colour can change the browser title/description and
  material narrative to Ukrainian after a client-side selection, creating a
  crawler and shopper language mismatch.
- **Required boundary:** production report for active variant details and
  locale rows; complete only priority visible variants, then retain
  noindex/owner safeguards for gaps.
- **Verification:** parse title/meta/JSON-LD and material narrative before and
  after each selected variant for each language.

## Confirmed P2 findings

### PDP-P2-01: Gallery, video, description-collapse, lightbox, and recently-viewed fallbacks are Ukrainian

- **Source:** `product-detail.js` supplies Ukrainian fallback labels for
  gallery status, video, description expansion, lightbox controls, recently
  viewed cards, and modal fields around lines 243-247, 662-668, 2099-2100,
  2434-2513, and 2647-2844.
- **Required boundary:** include these accessible dynamic labels in the PDP
  locale payload. Existing template `data-*` labels should remain the primary
  source whenever present.
- **Verification:** keyboard and screen-reader-name checks after gallery/video
  open, description toggle, lightbox, and recently-viewed rendering on UA/RU/EN.

## Existing coverage and test gaps

- `storefront/tests/test_product.py` already proves standard classic/oversize
  labels through gettext but does not exercise dynamic price/technology/restock
  rewrite paths.
- `storefront/tests/test_product_size_guides.py` verifies structured guide
  selection but not a three-locale presentation matrix for database-owned
  guide copy.
- `storefront/tests/test_rendered_locale_matrix.py` protects selected static
  PDP shell and schema output, but not option mutations or the above data
  model coverage.

## Implementation order

1. Build the shared locale contract and cover P0 dynamic variant/restock
   behavior with red-green tests.
2. Correct static price labels and all dynamic accessible fallbacks.
3. Obtain production MariaDB inventory for Product/SizeGrid/fit/technology
   data; approve schema and editorial backfill separately.
4. Re-run UA/RU/EN desktop/mobile browser checks after deployment.
