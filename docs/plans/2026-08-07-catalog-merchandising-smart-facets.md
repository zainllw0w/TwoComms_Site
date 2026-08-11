# Catalog Merchandising Smart Facets Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the Variant 3 Smart Selector and Product Catalog with truthful multi-dimensional merchandising that continues through catalog cards and the upper PDP decision zone, reliable mobile filters, curated brigade/collection SEO pages, and measurable mobile-first conversion UX.

**Architecture:** Keep the existing Django category branch, PDP purchase flow, and production header/footer. Add normalized Product Catalog audience and collection data, services that resolve validated catalog facets and PDP merchandising from real inventory/variant sources, server-rendered category/collection/PDP context, and scoped vanilla JavaScript enhancement. Keep arbitrary filters crawl-safe and make only curated collection URLs indexable.

**Tech Stack:** Django models/migrations, existing Product Catalog APIs and size-grid services, Django templates, scoped CSS, vanilla JavaScript, existing dataLayer/Meta adapters, Django TestCase, Node syntax checks, Playwright/agent-browser, Chrome DevTools Lighthouse and performance traces.

---

## Task 1: Freeze baseline and write regression contracts

**Files:**
- Create: `twocomms/storefront/tests/test_catalog_merchandising_facets.py`
- Create: `twocomms/product_catalog/tests/test_audience_taxonomy.py`
- Modify: `twocomms/storefront/tests/test_category_smart_selector.py`
- Reference: `docs/plans/2026-08-07-catalog-merchandising-smart-facets-design.md`

**Step 1: Capture current behavior**

Run the existing focused tests, Django checks, migration check, JavaScript syntax check, and a no-write browser snapshot of the current live/local selector. Record the current production SHA and preserve unrelated worktree changes.

```bash
cd /Users/zainllw0w/TwoComms/site
DJANGO_SETTINGS_MODULE=test_settings SECRET_KEY=test_local_secret \
  .venv/bin/python manage.py test storefront.tests.test_category_smart_selector --noinput
DJANGO_SETTINGS_MODULE=test_settings SECRET_KEY=test_local_secret \
  .venv/bin/python manage.py check
DJANGO_SETTINGS_MODULE=test_settings SECRET_KEY=test_local_secret \
  .venv/bin/python manage.py makemigrations --check --dry-run
node --check twocomms/twocomms_django_theme/static/js/catalog-smart-selector.js
```

Expected: the current suite passes and the worktree remains unchanged.

**Step 2: Write failing audience model tests**

Cover stable codes, translated labels, duplicate assignment prevention, product deletion behavior, and the rule that a published apparel product cannot be saved without at least one audience tag once the migration is active.

**Step 3: Write failing filter contract tests**

Cover repeated query keys, strict audience AND behavior, AND across facet groups, empty/invalid values, in-stock truth from variant rules, sellable size resolution excluding informational `3XL`, thermo detection from color variants, and stable canonical query ordering.

**Step 4: Write failing template/SEO tests**

Cover one H1, category tabs, collection H1, `ItemList`, `BreadcrumbList`, visible FAQ details, custom-print CTA, canonical/noindex behavior, pagination fallback, and the absence of Smart Selector markup on root catalog/search routes. Add a PDP regression contract proving that normalized audience/collection assignments reach the upper product context and that Product schema does not assert a merchandising theme without a real assignment.

**Step 5: Verify RED**

Run the new tests and confirm they fail for missing models/services/markup rather than fixture or settings errors.

---

## Task 2: Add Product Catalog audience taxonomy

**Files:**
- Modify: `twocomms/product_catalog/models.py`
- Create: `twocomms/product_catalog/migrations/0009_audience_taxonomy.py`
- Create: `twocomms/product_catalog/services_audience.py`
- Modify: `twocomms/product_catalog/views.py`
- Modify: `twocomms/product_catalog/templates/product_catalog/editor.html`
- Modify: `twocomms/product_catalog/static/product_catalog/editor.js`
- Modify: `twocomms/product_catalog/static/product_catalog/editor.css` if needed
- Test: `twocomms/product_catalog/tests/test_audience_taxonomy.py`

**Step 1: Implement the minimal normalized model**

Create `AudienceTag` and `ProductAudience` with stable unique codes, ordering, active status, localized labels, and a unique `(product, tag)` constraint. Seed the three required tags in the migration. Keep audience selection at product level; variant color/fit remains responsible for sellability and thermo.

**Step 2: Add service-level normalization**

Implement `get_product_audience_codes(product)`, `set_product_audience_codes(product, codes)`, and `validate_published_apparel_audience(product)`. Reject unknown/inactive codes, normalize order, and make writes idempotent. Do not parse `target_audience` text.

**Step 3: Extend editor payload and save flow**

Expose `audience_codes` and `audience_labels` in the editor payload. Add a labelled three-control fieldset in the content/SEO panel. Save the list through the existing Product Catalog JSON endpoint and return validation errors inline. Make keyboard focus and mobile stacking match the current editor design.

**Step 4: Backfill T-shirts safely**

Add an idempotent management command or data migration that assigns `unisex` to every existing T-shirt without replacing explicit tags. Run it against a transactionally backed copy first, then verify counts and representative products. Leave hoodie/long-sleeve audience assignments untouched.

**Step 5: Verify**

Run the focused Product Catalog tests, editor payload tests, migration check, and Django check. Confirm repeated backfill runs are no-ops.

---

## Task 3: Add collections and brigade taxonomy

**Files:**
- Modify: `twocomms/product_catalog/models.py`
- Create: `twocomms/product_catalog/migrations/0010_merch_collections.py`
- Create: `twocomms/product_catalog/services_collections.py`
- Modify: `twocomms/product_catalog/views.py`
- Modify: `twocomms/product_catalog/templates/product_catalog/editor.html`
- Modify: `twocomms/product_catalog/static/product_catalog/editor.js`
- Modify: `twocomms/product_catalog/static/product_catalog/editor.css` if needed
- Test: `twocomms/product_catalog/tests/test_merch_collections.py`

**Step 1: Implement normalized collection models**

Add `MerchCollection` with `kind`, optional parent, localized display and SEO copy, cover media, accent token, order, active/indexable flags, and unique slugs. Add `ProductMerchCollection` with unique product/collection assignment and order.

**Step 2: Seed the existing taxonomy**

Create sibling root records for military, brigades, streetwear, and Kharkiv. Seed brigade children `225` and `127` beneath brigades. Only `225` starts indexable; keep `127` non-indexable until products and localized editorial content are reviewed. Seed only labels and safe fallback copy; do not fabricate military claims or brigade descriptions. Record which products are assigned by the existing theme resolver so staff can review them in Product Catalog.

**Step 3: Add editor controls**

Add a compact collection picker with search, type labels, parent breadcrumbs, and assigned chips. Support multiple assignments and drag/order only where the model stores order. Keep collection SEO fields in the same fallback hierarchy as existing product SEO.

**Step 4: Verify**

Test nested collection resolution, inactive/indexable rules, duplicate assignments, localized fallback behavior, and editor save/reload.

---

## Task 4: Build the authoritative facet resolver

**Files:**
- Create: `twocomms/storefront/services/catalog_facets.py`
- Modify: `twocomms/storefront/views/catalog.py`
- Reference: `twocomms/product_catalog/services.py`
- Reference: `twocomms/product_catalog/size_grid_services.py`
- Reference: `twocomms/storefront/services/size_guides.py`
- Test: `twocomms/storefront/tests/test_catalog_merchandising_facets.py`

**Step 1: Define facet constants and query normalization**

Define facet names, allowed values, stable output ordering, and repeated-key parsing. Preserve unrelated query parameters such as language/tracking only where existing canonical policy allows. Strip pagination when facet state changes.

**Step 2: Resolve product truth**

Build queryset filters from real product relations and annotate only what is needed for the first page. Use `variant_public_context()` for fit-aware prices, thermo markers, and availability. Use `resolve_effective_sizes()` plus enabled stock rules for sellable size facets. Treat an informational size-grid row without a sellable rule as non-filterable.

**Step 3: Implement strict AND semantics**

For audience and collection tags, apply one existence condition per selected value. A selected root theme matches direct assignments and assignments to any active descendant, so a product assigned only to `225` is truthfully part of `brigades` without a duplicate stored assignment. Multiple explicit child collections such as `225` and `127` use strict AND. Canonicalize redundant parent+child state to the child. For fit/theme/brigade/availability, apply all selected constraints. For size/color alternatives, use the documented availability semantics and expose counts that reflect the resulting queryset. Add tests for mixed combinations and zero-result recovery.

**Step 4: Produce view metadata**

Return selected state, facet counts, disabled values, applied-chip labels, result count, collection identity, canonical URL, robots directive, and structured-data input. Do not compute a card price from `Product.price` when fit/color overrides exist.

**Step 5: Verify**

Run service tests with representative classic, oversize-only, thermo, out-of-stock, multi-audience, and multi-collection fixtures. Add a query-count assertion for the initial page where practical.

---

## Task 5: Implement category and collection routing with SEO-safe output

**Files:**
- Modify: `twocomms/storefront/urls.py`
- Modify: `twocomms/product_catalog/urls.py` only if the existing public app boundary requires it
- Modify: `twocomms/storefront/views/catalog.py`
- Create or modify: `twocomms/storefront/views/merch.py`
- Modify: `twocomms/twocomms_django_theme/templates/pages/catalog.html`
- Create: `twocomms/twocomms_django_theme/templates/pages/merch_collection.html`
- Create: `twocomms/twocomms_django_theme/templates/partials/catalog_structured_data.html`
- Test: `twocomms/storefront/tests/test_catalog_merchandising_facets.py`

**Step 1: Preserve category URL contracts**

Keep the three existing Smart Selector slugs and category tabs. Add validated facet state without changing product/detail URL shape. Root catalog/search remain on their legacy branch.

**Step 2: Add `/merch/<slug>/`**

Resolve only active collections. Use language-aware localized fields and return a normal 404 for unknown/inactive collection slugs. The page reuses the same product grid and filter resolver with collection constraint pre-applied.

**Step 3: Render crawlable semantic content**

Render one H1, category/collection breadcrumbs, product `article` elements, normal pagination links, visible FAQ `<details>`, internal links, and the custom-print CTA in initial HTML. Keep decorative labels out of heading hierarchy.

**Step 4: Apply canonical/indexation policy**

Base category and curated collection URLs are indexable. Arbitrary facet combinations canonicalize to the nearest curated page and receive `noindex,follow` unless a collection explicitly opts into that facet landing state. Ensure language alternates and canonical URLs never include tracking parameters.

**Step 5: Verify**

Assert response status, title/H1 parity, canonical/robots, hreflang, JSON-LD validity, pagination, and no duplicate H1 on all supported languages.

---

## Task 6: Redesign the Smart Selector markup for mobile-first interaction

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/partials/catalog_smart_selector.html`
- Modify: `twocomms/twocomms_django_theme/templates/partials/catalog_smart_product_card.html`
- Create or modify: `twocomms/twocomms_django_theme/templates/partials/catalog_merch_editorial.html`
- Test: `twocomms/storefront/tests/test_category_smart_selector.py`

**Step 1: Add stable semantic controls**

Use labelled `fieldset` groups, `button` controls with `aria-pressed`, explicit `aria-controls`, and stable `data-*` hooks. Represent selected repeated values as chips that can be removed independently.

**Step 2: Add audience, availability, sizes, collections, and thermo controls**

Place audience and availability near the top of the sheet. Show size counts from sellable combinations, fit controls only when supported, color swatches with text labels, and a visually distinct flame marker for thermo. `Бригади` is a first-level theme disclosure; its `225` and `127` children open inline on desktop and in the same mobile sheet section, with clear parent context, independent 44px check targets, selected counts, and no nested modal.

**Step 3: Add contextual editorial block**

Render the category/collection-specific At-a-glance, Explore, How-to-choose, FAQ, and Create-your-print modules after the grid. Keep content in the DOM regardless of accordion state.

**Step 4: Preserve no-JS behavior**

Every category, collection, product, pagination, and internal SEO link remains navigable with JavaScript disabled.

**Step 5: Recompose the product card meta zone**

Keep title, visible price, fit/audience/availability facts, the most specific theme/brigade assignment, and color swatches in one semantic body flow. Remove the detached post-price color dot treatment from the prototype and live page. Render a labelled color row with stable swatch hit areas, a contrast ring for light colors, a flame marker for thermo, and a `+N` overflow affordance only when needed. Do not duplicate an implied parent (`Бригади`) beside a specific child (`225 ОШП`). Add a template contract test for this exact DOM order and a screenshot check for card-bottom alignment at mobile and desktop widths.

---

## Task 7: Fix mobile filter reliability and implement restrained motion

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/js/catalog-smart-selector.js`
- Modify: `twocomms/twocomms_django_theme/static/css/catalog-smart-selector.css`
- Modify: `twocomms/twocomms_django_theme/templates/pages/catalog.html`
- Test: `twocomms/storefront/tests/test_category_smart_selector.py`
- Test: `twocomms/twocomms_django_theme/static/js/tests/catalog-smart-selector.test.js` if the existing JS harness supports it

**Step 1: Add a delegated interaction boundary**

Attach one listener to the selector root for open/close/filter/reset/accordion actions. This prevents stale NodeList bindings after progressive HTML insertion and ensures mobile and desktop controls share behavior.

**Step 2: Implement robust dialog state**

Use a single source of truth for `open`, `aria-hidden`, `aria-expanded`, inert siblings, scroll lock, focus trap, Escape, backdrop, and browser-back close. Do not rely on CSS visibility alone for keyboard state. Bump the static asset version whenever JS changes.

**Step 3: Add accordion transitions**

Animate only opacity and a bounded grid/clip transition. Keep closed groups in the DOM and avoid measuring product layout during the transition. Respect `prefers-reduced-motion`.

**Step 4: Add progressive reveal**

Insert incoming product items into a document fragment, assign stable order, and animate only the new items. Preserve reserved image geometry and do not announce every card individually to screen readers.

**Step 5: Verify the previous failure mode**

At 320, 375, 390, 430, 768, and 1024 widths exercise every theme, collection, fit, audience, availability, size, color, reset, close, Escape, browser-back, and progressive-load path. Verify that `Бригади` reveals `225` and `127` in place and that several child selections remain independent. Inspect computed `pointer-events`, stacking contexts, inert state, and loaded JS URL when any action fails.

**Step 6: Protect the fixed mobile navigation area**

Expose a CSS custom property for the measured bottom-navigation height plus the safe-area inset. Apply it to the selector shell, progressive sentinel, pagination, and editorial block. Assert in browser QA that the last visible card controls and the SEO CTA are not inside the navigation bounding box, and that the open filter sheet footer remains above both navigation and the device safe area.

---

## Task 8: Continue merchandising into the upper PDP decision zone

**Files:**
- Create: `twocomms/storefront/services/product_merchandising.py`
- Modify: `twocomms/storefront/views/product.py`
- Modify: `twocomms/twocomms_django_theme/templates/pages/product_detail.html`
- Create: `twocomms/twocomms_django_theme/templates/partials/product_merchandising_context.html`
- Modify: `twocomms/twocomms_django_theme/static/css/product-detail.css`
- Modify: `twocomms/twocomms_django_theme/static/js/product-detail.js`
- Modify: `twocomms/storefront/seo_utils.py`
- Create: `twocomms/storefront/tests/test_product_merchandising.py`
- Test: `twocomms/storefront/tests/test_product.py`
- Test: `twocomms/twocomms_django_theme/static/js/product-detail.test.js`

**Step 1: Write and verify the RED PDP continuity contracts**

Create fixtures with multiple audience tags, a root `brigades` theme with `225`/`127` child assignments, an active curated collection, a non-public collection, an ordinary color, and a thermochromic color. Assert that the initial PDP context preserves assignment order and localized labels, collapses implied parents in favor of the most specific assigned fact, links only to real public collection routes, renders audience as a fact, and derives thermo only from the selected variant. Add a template-order assertion that the compact context belongs to the existing title/meta region without replacing the title, price, variant selectors, or primary purchase action.

**Step 2: Build one presentation-safe PDP resolver**

Implement `resolve_product_merchandising_context(product, selected_variant=None, fit_code="", language="uk")`. Reuse `services_audience`, `services_collections`, and `variant_public_context()`; do not query or parse `target_audience`, product titles, descriptions, or category names. Return normalized codes, localized labels, safe public URLs, a primary collection, overflow count, and selected-variant thermo/material state. Prefetch assignments in `product_detail()` so the resolver does not create per-marker queries.

**Step 3: Render the compact server-first context rail**

Insert one semantic partial in the current upper product panel next to the H1/category/meta region. Render collection/brigade assignments as normal links and audience as a labelled characteristic. On mobile keep one stable horizontal row with 44px link hit areas and a compact `+N` disclosure/scroll affordance; on desktop keep the rail aligned to the existing buy box. Do not add a hero, duplicate the category switcher, wrap into a badge wall, or push the first price and primary action out of the expected decision area.

**Step 4: Synchronize selected-variant facts without layout shift**

Expose normalized static product assignments and per-variant `is_thermo`, material story, and price delta through the existing product payload. Extend the existing delegated color/fit update path to toggle only the variant-dependent marker in place. Verify initial HTML, path-selected color, query-selected color, and client selection agree; selecting a non-thermo color removes the flame and explanation without leaving an empty gap.

**Step 5: Make Product schema truthful**

Replace the unconditional `Стріт & Мілітарі` `additionalProperty` in `generate_product_schema()` with values from active normalized assignments. Use normalized audiences instead of category-name inference. Emit `suggestedGender` only when the structured assignment can be represented without loss; preserve multiple audiences as explicit visible/schema values rather than collapsing them to a false single value. Tests must prove an untagged product has no invented style/brigade and a tagged product's HTML and schema agree.

**Step 6: Reuse the existing PDP analytics event**

After tracing the current consent and deduplication path, enrich the existing `view_item` and variant-selection dataLayer payloads with normalized collection and audience codes. Do not emit a second `view_item`, do not change Meta content IDs or price semantics, and do not send PII. Add serialization-only JavaScript tests with no network calls.

**Step 7: Verify responsive hierarchy and performance**

At 320/375/390/430/768/1024/1440 widths verify the product media, H1, price, and main action retain prominence; the context rail never overlaps panel actions, never creates horizontal page overflow, and has accessible focus/labels. Measure CLS while changing variants, inspect query counts, test reduced motion, and verify Ukrainian/Russian/English labels plus no-JS links.

---

## Task 9: Integrate analytics without polluting attribution

**Files:**
- Reference and modify only the existing analytics/dataLayer adapter files after tracing them
- Modify: `twocomms/twocomms_django_theme/static/js/catalog-smart-selector.js`
- Test: existing analytics tests plus `twocomms/storefront/tests/test_catalog_merchandising_facets.py`

**Step 1: Map existing event vocabulary**

Find current GTM, Meta Pixel, Clarity, and TikTok dispatch helpers. Reuse their consent, deduplication, and language handling. Do not send live test events.

**Step 2: Emit state-change events**

Emit `view_item_list`, `catalog_filter_apply`, `catalog_filter_clear`, sheet open/close, `select_item`, `quick_view_open`, collection view, progressive load, and custom-print CTA events with category/collection/facet metadata and no PII.

**Step 3: Test serialization only**

Use mocked dataLayer/Pixel adapters and assert payload shape, event IDs where applicable, and no network calls in tests.

---

## Task 10: Run Frontend Design and performance review

**Files:**
- Artifacts: `twocomms/output/playwright/catalog-smart-facets/`
- Modify only task-scoped CSS/templates/JS after findings

**Step 1: Capture geometry matrix**

Use browser automation at 320x568, 375x812, 390x844, 430x932, 768x1024, 1024x900, 1280x900, and 1440x1000. Capture initial, sheet-open, accordion-open, filtered, empty, and collection states.

**Step 2: Check visual quality**

Verify header/footer parity, first-viewport product visibility, symmetry, card rhythm, typography wrapping, flame marker clarity, 44px controls, no horizontal overflow, no overlay collision, and no visual overload. Review light/dark OS settings and reduced motion.

Also verify that the fixed mobile navigation never occludes card content, pagination, the progressive-loading status, or the Create-your-print CTA at any target height.

For representative PDPs, verify that the merchandising rail visually belongs to the existing title/meta block, real collection links remain distinguishable from the audience fact, a `225` or `127` child is not repeated with its implied `Бригади` parent, `+N`/horizontal overflow is understandable, and changing between ordinary and thermochromic colors updates the marker without moving the title, price, selectors, or primary action.

**Step 3: Measure Core Web Vitals**

Record LCP element and timing, CLS sources, INP for filter open/apply, TTFB, image sizes, console errors, failed requests, and long tasks. Correct root causes rather than masking metrics.

**Step 4: Run accessibility/SEO audits**

Run Lighthouse mobile/desktop, inspect accessibility tree, validate JSON-LD, canonical/robots/hreflang, visible FAQ correspondence, and keyboard-only dialog flow.

**Step 5: Complete the molecular surface checklist**

Review the design contract's quality matrix line by line. For each surface record a screenshot/DOM assertion proving its job: shared shell parity, category recognition, first product visibility, quick-row density, command-shelf behavior, dialog focus/inert state, rail density, card truthfulness, empty-state recovery, progressive status, collection identity, editorial SEO usefulness, and bottom-navigation safe-area clearance. Remove any decorative element that has no measurable user, SEO, accessibility, or performance purpose.

Include a dedicated relationship audit for every card: image-to-title continuity, price-to-thermo explanation, fit/audience/availability alignment, and color-row attachment. Verify there is no horizontal divider that visually makes a color swatch look like metadata from another product.

**Step 6: Validate decision psychology without adding noise**

Confirm recognition-before-choice, progressive disclosure, immediate state feedback, postponed commitment, and trust-preserving motion at each viewport. In particular, verify that campaign landing traffic can choose its collection in one tap, that audience/availability/size filters are discoverable without scrolling through product cards, and that the custom-print CTA appears only after ready-made discovery content.

---

## Task 11: Production-like data verification and rollout gates

**Files:**
- Create: `twocomms/product_catalog/management/commands/backfill_tshirt_audience.py` if a command is preferred over a data migration
- Create: `docs/plans/2026-08-07-catalog-merchandising-smart-facets-rollout.md` only after QA findings are known

**Step 1: Verify real data**

Against the server-backed database, compare product/category counts, audience assignments, active fit rules, sellable sizes, thermo variants, and collection assignments. Local fixtures are not production truth.

**Step 2: Run idempotent backfill**

Dry-run, review counts, apply, rerun dry-run, and verify zero unexpected changes. Keep an explicit report of products skipped because they are not T-shirts or already have assignments.

**Step 3: Rebuild/cache safely**

After code and migration checks, collect static assets, invalidate only affected catalog/fragment caches, and verify static JS versioning. Do not clear unrelated caches broadly.

**Step 4: Live verification**

Check all language/category/collection URLs, filter URLs, representative tagged and untagged PDPs, selected-color PDP states, product links, schema, robots/canonical, and browser interactions. Confirm Product Catalog assignments match catalog-card and PDP output, then record deployed SHA and persisted data evidence.

**Step 5: Integration gate**

Commit only task-scoped files. Push/deploy only after the user explicitly requests shipping this implementation slice; deployment is not part of this planning step.

---

## Verification command set

```bash
cd /Users/zainllw0w/TwoComms/site
DJANGO_SETTINGS_MODULE=test_settings SECRET_KEY=test_local_secret \
  .venv/bin/python manage.py test \
  product_catalog.tests.test_audience_taxonomy \
  product_catalog.tests.test_merch_collections \
  storefront.tests.test_catalog_merchandising_facets \
  storefront.tests.test_product_merchandising \
  storefront.tests.test_category_smart_selector --noinput
DJANGO_SETTINGS_MODULE=test_settings SECRET_KEY=test_local_secret \
  .venv/bin/python manage.py check
DJANGO_SETTINGS_MODULE=test_settings SECRET_KEY=test_local_secret \
  .venv/bin/python manage.py makemigrations --check --dry-run
node --check twocomms/twocomms_django_theme/static/js/catalog-smart-selector.js
git diff --check
```

Expected: all focused tests pass, no migration drift is reported, JavaScript parses, and the diff contains no whitespace errors. Browser and live evidence are required before calling the implementation complete.
