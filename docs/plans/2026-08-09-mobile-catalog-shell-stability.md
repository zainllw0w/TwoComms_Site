# Mobile Catalog Shell Stability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Stabilize the approved mobile catalog on iPhone, add real all-catalog filters, refine the mobile mini-cart and brand alignment, improve homepage hero-logo LCP, and keep Custom Print marks gently animated.

**Architecture:** Extend the existing Django catalog view with normalized root-only aggregate facet state and render a mobile GET filter sheet in the existing catalog template. Keep category pages delegated to the existing Smart Selector, scope all mini-cart and catalog geometry to the current mobile shell CSS, and make the homepage LCP change asset-discovery-only.

**Tech Stack:** Django templates and querysets, existing `catalog_facets` service, vanilla JavaScript, scoped responsive CSS, Django TestCase, browser QA.

---

### Task 1: Add RED catalog-filter contracts

**Files:**
- Modify: `twocomms/storefront/tests/test_catalog.py`
- Modify: `twocomms/storefront/tests/test_category_smart_selector.py`

**Steps:**

1. Add a root response contract asserting the accessible filter sheet, garment controls, canonical size/color controls, reset/apply actions, and active-count source.
2. Add a queryset contract with products in T-shirt, hoodie, and long-sleeve categories; submit multiple `category` values and an inventory facet; assert every matching category can appear and unrelated products do not.
3. Assert root filters set `show_category_cards=False` and preserve the standard product-grid rendering.
4. Assert a category route still renders and opens the existing Smart Selector rather than the root sheet.
5. Run the focused tests and record the expected pre-implementation failures.

Run:

```bash
SECRET_KEY=test_local_secret .venv/bin/python twocomms/manage.py test storefront.tests.test_catalog storefront.tests.test_category_smart_selector --settings=test_settings --keepdb
```

### Task 2: Implement normalized root filters

**Files:**
- Modify: `twocomms/storefront/views/catalog.py`
- Modify: `twocomms/twocomms_django_theme/templates/pages/catalog.html`
- Modify: `twocomms/twocomms_django_theme/static/js/mobile-shell.js`

**Steps:**

1. Parse repeated root `category` values and the existing normalized inventory facets only when `cat_slug` is absent.
2. Restrict category values to the three primary public garment slugs and reuse `filter_products_by_facets()` for size, availability, color, and fit behavior.
3. Apply the existing sort contract to the aggregate result queryset and disable category cards whenever root facet state is active.
4. Build template options from `categories`, `available_colors`, canonical size order, and current normalized state.
5. Render the root bottom sheet as a GET form; keep the standard product grid for filtered results.
6. In `mobile-shell.js`, prefer the root sheet when present and otherwise delegate to the category Smart Selector. Implement focus return, Escape/backdrop close, body locking, and active-count sync.
7. Run RED tests until green and run `node --check`.

### Task 3: Fix Safari document geometry and Custom Print motion

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/css/catalog-redesign.css`
- Modify: `twocomms/twocomms_django_theme/static/css/mobile-shell.css`

**Steps:**

1. Give route-level `html`, `body`, `main`, root shell, and mobile reference one continuous black background.
2. Use `100svh` plus a `100dvh` enhancement and safe-area-aware bottom space; remove page-level clipping that can truncate the painted surface.
3. Style the filter sheet with fixed header/footer, scrollable content, 44px controls, stable tracks, and safe-area padding.
4. Give each Custom Print mark a distinct slow keyframe path and keep all marks behind the media/empty-right zone.
5. Freeze decorative motion under reduced-motion preference.

### Task 4: Refine mobile mini-cart

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/partials/mini_cart.html`
- Modify: `twocomms/twocomms_django_theme/templates/base.html`
- Modify: `twocomms/twocomms_django_theme/static/css/mobile-shell.css`

**Steps:**

1. Add semantic row/media/copy/title/meta/action/price/remove classes without changing cart data or click handlers.
2. Make the mobile panel a header/content/footer grid between shell header and dock, overriding conflicting `vh-100` runtime utilities with `height:auto`.
3. Make content independently scrollable and preserve checkout visibility on short screens.
4. Use a three-track item grid, two-line title clamp, wrapping metadata, tabular price, and fixed remove target.
5. Verify empty, one-item, multi-item, long-title, custom-item, and mono-checkout states.

### Task 5: Align header branding and improve homepage LCP

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/partials/header.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/index.html`
- Modify: `twocomms/twocomms_django_theme/static/css/mobile-shell.css`
- Modify: `twocomms/twocomms_django_theme/static/css/home.css`
- Modify: `twocomms/storefront/tests/test_catalog.py`

**Steps:**

1. Add a dedicated desktop brand class and a separate name span.
2. Move the mobile brand group two pixels left and set a 10px mark/name gap.
3. Add a homepage `preload_hints` block for `img/logo.svg`.
4. Change the hero image to `decoding="async"`; remove its redundant filter and `will-change` while keeping dimensions.
5. Add a rendered-home regression test for the preload, decode mode, dimensions, and single hero image URL.

### Task 6: Verification, evaluation, and delivery

**Files:**
- Update static cache-busting query strings only where a modified standalone asset requires it.

**Steps:**

1. Run focused Django suites, `manage.py check`, `node --check`, and `git diff --check`.
2. Start the local server and verify 320x568, 375x667, 390x844, 430x932, and desktop. Exercise filter apply/reset, mini-cart open/close/scroll, long titles, menu/search, and all category links.
3. Run external frontend evaluation and apply priority fixes, up to three rounds.
4. Commit only task files, push `main`, verify `main...origin/main` is `0 0`.
5. Deploy via the authorized SSH pull, then run `collectstatic --noinput`, `compress --force`, `check`, and Passenger restart.
6. Verify production SHA, cache-busted assets, filter interactions, mini-cart, catalog height, header alignment, and homepage hero markup.

## Execution Status (2026-08-09)

- [x] Task 1: aggregate root-filter RED contracts were added and observed failing before implementation.
- [x] Task 2: repeated garment categories, normalized inventory facets, server-rendered aggregate results, focus handling, body lock, Escape/backdrop close, apply/reset, and legacy comma-separated color URLs are implemented.
- [x] Task 3: continuous `svh`/`dvh` catalog geometry, filter-sheet geometry, four distinct Custom Print motion paths, the `effects-lite` cascade exception, and a route-scoped reduced-motion freeze are implemented.
- [x] Task 4 implementation: semantic mini-cart tracks, stable panel rows, long-copy wrapping, a 64px action track, compact summary, primary checkout CTA, and short-height reductions are implemented.
- [x] Task 5: global brand groups, mobile alignment, homepage logo preload, async decode, and redundant hero-image work removal are implemented.
- [x] Browser geometry: 320x568, 375x667, 390x844, 430x932, and 1280x900 have zero horizontal overflow; the mobile header is 64px, the dock is 72px, and desktop keeps the existing non-mobile grid.
- [x] Aggregate result grid: mobile results use two stable tracks without Bootstrap negative gutters; an only child spans both tracks.
- [x] Focused verification: all nine new acceptance tests pass; `manage.py check`, `node --check`, and `git diff --check` pass.
- [ ] Full affected suites are not entirely green: 77/80 pass. Three untouched Smart Selector expectations remain failing (`white-space: nowrap`, the old color-group aria label, and legacy SEO copy).
- [x] Populated mini-cart browser verification: a real server session with two products, long and short titles, stable price tracks, summary, primary checkout CTA, and mono checkout was verified at 320x568 and 390x844 with zero horizontal overflow and no console errors.
- [ ] A populated custom-print mini-cart item remains a separate follow-up scenario because it requires a valid Custom Print lead and moderation state; its semantic row uses the same stable grid contract.
- [ ] Commit, push, deploy, and production verification are intentionally not performed in this local-only phase.
