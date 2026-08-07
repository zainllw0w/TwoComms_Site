# Catalog Merchandising Smart Facets Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the Variant 3 Smart Selector and Fable 5 with truthful multi-dimensional merchandising, reliable mobile filters, curated brigade/collection SEO pages, and measurable mobile-first conversion UX.

**Architecture:** Keep the existing Django category branch and production header/footer. Add normalized Fable 5 audience and collection data, a service that resolves validated facet state from real inventory/fit/size sources, server-rendered category/collection pages, and a scoped Smart Selector UI enhanced by vanilla JavaScript. Keep arbitrary filters crawl-safe and make only curated collection URLs indexable.

**Tech Stack:** Django models/migrations, existing Fable 5 APIs and size-grid services, Django templates, scoped CSS, vanilla JavaScript, existing dataLayer/Meta adapters, Django TestCase, Node syntax checks, Playwright/agent-browser, Chrome DevTools Lighthouse and performance traces.

---

## Task 1: Freeze baseline and write regression contracts

**Files:**
- Create: `twocomms/storefront/tests/test_catalog_merchandising_facets.py`
- Create: `twocomms/fable5/tests/test_audience_taxonomy.py`
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

Cover one H1, category tabs, collection H1, `ItemList`, `BreadcrumbList`, visible FAQ details, custom-print CTA, canonical/noindex behavior, pagination fallback, and the absence of Smart Selector markup on root catalog/search routes.

**Step 5: Verify RED**

Run the new tests and confirm they fail for missing models/services/markup rather than fixture or settings errors.

---

## Task 2: Add Fable 5 audience taxonomy

**Files:**
- Modify: `twocomms/fable5/models.py`
- Create: `twocomms/fable5/migrations/0009_audience_taxonomy.py`
- Create: `twocomms/fable5/services_audience.py`
- Modify: `twocomms/fable5/views.py`
- Modify: `twocomms/fable5/templates/fable5/editor.html`
- Modify: `twocomms/fable5/static/fable5/editor.js`
- Modify: `twocomms/fable5/static/fable5/editor.css` if needed
- Test: `twocomms/fable5/tests/test_audience_taxonomy.py`

**Step 1: Implement the minimal normalized model**

Create `AudienceTag` and `ProductAudience` with stable unique codes, ordering, active status, localized labels, and a unique `(product, tag)` constraint. Seed the three required tags in the migration. Keep audience selection at product level; variant color/fit remains responsible for sellability and thermo.

**Step 2: Add service-level normalization**

Implement `get_product_audience_codes(product)`, `set_product_audience_codes(product, codes)`, and `validate_published_apparel_audience(product)`. Reject unknown/inactive codes, normalize order, and make writes idempotent. Do not parse `target_audience` text.

**Step 3: Extend editor payload and save flow**

Expose `audience_codes` and `audience_labels` in the editor payload. Add a labelled three-control fieldset in the content/SEO panel. Save the list through the existing Fable 5 JSON endpoint and return validation errors inline. Make keyboard focus and mobile stacking match the current editor design.

**Step 4: Backfill T-shirts safely**

Add an idempotent management command or data migration that assigns `unisex` to every existing T-shirt without replacing explicit tags. Run it against a transactionally backed copy first, then verify counts and representative products. Leave hoodie/long-sleeve audience assignments untouched.

**Step 5: Verify**

Run the focused Fable 5 tests, editor payload tests, migration check, and Django check. Confirm repeated backfill runs are no-ops.

---

## Task 3: Add collections and brigade taxonomy

**Files:**
- Modify: `twocomms/fable5/models.py`
- Create: `twocomms/fable5/migrations/0010_merch_collections.py`
- Create: `twocomms/fable5/services_collections.py`
- Modify: `twocomms/fable5/views.py`
- Modify: `twocomms/fable5/templates/fable5/editor.html`
- Modify: `twocomms/fable5/static/fable5/editor.js`
- Modify: `twocomms/fable5/static/fable5/editor.css` if needed
- Test: `twocomms/fable5/tests/test_merch_collections.py`

**Step 1: Implement normalized collection models**

Add `MerchCollection` with `kind`, optional parent, localized display and SEO copy, cover media, accent token, order, active/indexable flags, and unique slugs. Add `ProductMerchCollection` with unique product/collection assignment and order.

**Step 2: Seed the existing taxonomy**

Create records for military, streetwear, Kharkiv, and the first brigade collection `225`. Seed only labels and safe fallback copy; do not fabricate military claims or brigade descriptions. Record which products are assigned by the existing theme resolver so staff can review them in Fable 5.

**Step 3: Add editor controls**

Add a compact collection picker with search, type labels, parent breadcrumbs, and assigned chips. Support multiple assignments and drag/order only where the model stores order. Keep collection SEO fields in the same fallback hierarchy as existing product SEO.

**Step 4: Verify**

Test nested collection resolution, inactive/indexable rules, duplicate assignments, localized fallback behavior, and editor save/reload.

---

## Task 4: Build the authoritative facet resolver

**Files:**
- Create: `twocomms/storefront/services/catalog_facets.py`
- Modify: `twocomms/storefront/views/catalog.py`
- Reference: `twocomms/fable5/services.py`
- Reference: `twocomms/fable5/size_grid_services.py`
- Reference: `twocomms/storefront/services/size_guides.py`
- Test: `twocomms/storefront/tests/test_catalog_merchandising_facets.py`

**Step 1: Define facet constants and query normalization**

Define facet names, allowed values, stable output ordering, and repeated-key parsing. Preserve unrelated query parameters such as language/tracking only where existing canonical policy allows. Strip pagination when facet state changes.

**Step 2: Resolve product truth**

Build queryset filters from real product relations and annotate only what is needed for the first page. Use `variant_public_context()` for fit-aware prices, thermo markers, and availability. Use `resolve_effective_sizes()` plus enabled stock rules for sellable size facets. Treat an informational size-grid row without a sellable rule as non-filterable.

**Step 3: Implement strict AND semantics**

For audience and collection tags, apply one existence condition per selected value. For fit/theme/brigade/availability, apply all selected constraints. For size/color alternatives, use the documented availability semantics and expose counts that reflect the resulting queryset. Add tests for mixed combinations and zero-result recovery.

**Step 4: Produce view metadata**

Return selected state, facet counts, disabled values, applied-chip labels, result count, collection identity, canonical URL, robots directive, and structured-data input. Do not compute a card price from `Product.price` when fit/color overrides exist.

**Step 5: Verify**

Run service tests with representative classic, oversize-only, thermo, out-of-stock, multi-audience, and multi-collection fixtures. Add a query-count assertion for the initial page where practical.

---

## Task 5: Implement category and collection routing with SEO-safe output

**Files:**
- Modify: `twocomms/storefront/urls.py`
- Modify: `twocomms/fable5/urls.py` only if the existing public app boundary requires it
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

Place audience and availability near the top of the sheet. Show size counts from sellable combinations, fit controls only when supported, color swatches with text labels, and a visually distinct flame marker for thermo. Brigade choices appear under Collections and do not compete with the primary category tabs.

**Step 3: Add contextual editorial block**

Render the category/collection-specific At-a-glance, Explore, How-to-choose, FAQ, and Create-your-print modules after the grid. Keep content in the DOM regardless of accordion state.

**Step 4: Preserve no-JS behavior**

Every category, collection, product, pagination, and internal SEO link remains navigable with JavaScript disabled.

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

At 320, 375, 390, 430, 768, and 1024 widths exercise every theme, collection, fit, audience, availability, size, color, reset, close, Escape, browser-back, and progressive-load path. Inspect computed `pointer-events`, stacking contexts, inert state, and loaded JS URL when any action fails.

**Step 6: Protect the fixed mobile navigation area**

Expose a CSS custom property for the measured bottom-navigation height plus the safe-area inset. Apply it to the selector shell, progressive sentinel, pagination, and editorial block. Assert in browser QA that the last visible card controls and the SEO CTA are not inside the navigation bounding box, and that the open filter sheet footer remains above both navigation and the device safe area.

---

## Task 8: Integrate analytics without polluting attribution

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

## Task 9: Run Frontend Design and performance review

**Files:**
- Artifacts: `twocomms/output/playwright/catalog-smart-facets/`
- Modify only task-scoped CSS/templates/JS after findings

**Step 1: Capture geometry matrix**

Use browser automation at 320x568, 375x812, 390x844, 430x932, 768x1024, 1024x900, 1280x900, and 1440x1000. Capture initial, sheet-open, accordion-open, filtered, empty, and collection states.

**Step 2: Check visual quality**

Verify header/footer parity, first-viewport product visibility, symmetry, card rhythm, typography wrapping, flame marker clarity, 44px controls, no horizontal overflow, no overlay collision, and no visual overload. Review light/dark OS settings and reduced motion.

Also verify that the fixed mobile navigation never occludes card content, pagination, the progressive-loading status, or the Create-your-print CTA at any target height.

**Step 3: Measure Core Web Vitals**

Record LCP element and timing, CLS sources, INP for filter open/apply, TTFB, image sizes, console errors, failed requests, and long tasks. Correct root causes rather than masking metrics.

**Step 4: Run accessibility/SEO audits**

Run Lighthouse mobile/desktop, inspect accessibility tree, validate JSON-LD, canonical/robots/hreflang, visible FAQ correspondence, and keyboard-only dialog flow.

---

## Task 10: Production-like data verification and rollout gates

**Files:**
- Create: `twocomms/fable5/management/commands/backfill_tshirt_audience.py` if a command is preferred over a data migration
- Create: `docs/plans/2026-08-07-catalog-merchandising-smart-facets-rollout.md` only after QA findings are known

**Step 1: Verify real data**

Against the server-backed database, compare product/category counts, audience assignments, active fit rules, sellable sizes, thermo variants, and collection assignments. Local fixtures are not production truth.

**Step 2: Run idempotent backfill**

Dry-run, review counts, apply, rerun dry-run, and verify zero unexpected changes. Keep an explicit report of products skipped because they are not T-shirts or already have assignments.

**Step 3: Rebuild/cache safely**

After code and migration checks, collect static assets, invalidate only affected catalog/fragment caches, and verify static JS versioning. Do not clear unrelated caches broadly.

**Step 4: Live verification**

Check all language/category/collection URLs, filter URLs, product links, schema, robots/canonical, and browser interactions. Record deployed SHA and persisted data evidence.

**Step 5: Integration gate**

Commit only task-scoped files. Push/deploy only after the user explicitly requests shipping this implementation slice; deployment is not part of this planning step.

---

## Verification command set

```bash
cd /Users/zainllw0w/TwoComms/site
DJANGO_SETTINGS_MODULE=test_settings SECRET_KEY=test_local_secret \
  .venv/bin/python manage.py test \
  fable5.tests.test_audience_taxonomy \
  fable5.tests.test_merch_collections \
  storefront.tests.test_catalog_merchandising_facets \
  storefront.tests.test_category_smart_selector --noinput
DJANGO_SETTINGS_MODULE=test_settings SECRET_KEY=test_local_secret \
  .venv/bin/python manage.py check
DJANGO_SETTINGS_MODULE=test_settings SECRET_KEY=test_local_secret \
  .venv/bin/python manage.py makemigrations --check --dry-run
node --check twocomms/twocomms_django_theme/static/js/catalog-smart-selector.js
git diff --check
```

Expected: all focused tests pass, no migration drift is reported, JavaScript parses, and the diff contains no whitespace errors. Browser and live evidence are required before calling the implementation complete.
