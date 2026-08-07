# Category Smart Selector Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement the implementation tasks task-by-task.

**Goal:** Port the approved Variant 3 Smart Selector into the Django storefront for concrete product category pages while preserving existing catalog/search behavior and SEO contracts.

**Architecture:** Add a category-scoped Smart Selector context in the catalog view and render a dedicated partial branch from `pages/catalog.html`. Reuse `product_card.html`, existing color/SEO services, real category URLs, and the server-rendered pagination as the progressive-loading fallback. Add scoped CSS/JS assets for the Smart Selector; the root catalog and search remain on the current markup and scripts.

**Tech Stack:** Django templates/views, Django TestCase, existing storefront CSS/JS, native IntersectionObserver/Fetch, Playwright CLI.

---

### Task 1: Add the RED contract tests

**Files:**
- Create: `twocomms/storefront/tests/test_category_smart_selector.py`
- Reference: `twocomms/storefront/tests/test_catalog.py`

**Step 1: Write failing tests**

Cover these independent behaviors:

- the three supported category routes render `data-smart-selector`, compact category tabs, desktop rail, mobile filter sheet, semantic product item wrappers, and the existing pagination fallback;
- t-shirts and hoodies expose classic/oversize context while long sleeves expose only standard;
- the category tabs use `catalog_by_cat` URLs and keep the selected category active;
- `/catalog/` and `/search/` do not render the Smart Selector branch;
- existing category SEO title/H1/description/SEO block content remains in the response;
- a valid `theme=military` and `fit=oversize` query is reflected in context and invalid values are ignored;
- a category page still renders real product detail URLs and no unpublished products.

**Step 2: Run the focused tests to verify RED**

Run:

```bash
DJANGO_SETTINGS_MODULE=test_settings SECRET_KEY=test_local_secret \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  storefront.tests.test_category_smart_selector --noinput
```

Expected: failure because the Smart Selector context/template branch does not yet exist.

### Task 2: Implement the server context and rendering branch

**Files:**
- Modify: `twocomms/storefront/views/catalog.py`
- Modify: `twocomms/twocomms_django_theme/templates/pages/catalog.html`
- Create: `twocomms/twocomms_django_theme/templates/partials/catalog_smart_selector.html`

**Step 1: Add a narrow supported-category resolver and validated facet context**

Keep the supported slugs explicit. Build category tabs from the configured real categories, compute fit options from active product fit options with the standard fallback for long sleeves, and reuse the existing thematic keyword config and color service. Preserve existing `category_seo_layout`, description, JSON-LD, canonical, robots, and pagination context.

**Step 2: Render the branch only for concrete category pages**

Include the production header/footer via `base.html`, keep one H1, render the approved command shelf/rail/grid/sheet structure, include `product_card.html` for each product, and leave the existing root/search branch untouched.

**Step 3: Run the focused tests**

Run the Task 1 command and expect all new tests to pass while the legacy catalog tests remain green.

### Task 3: Add scoped visual styles and interactions

**Files:**
- Create: `twocomms/twocomms_django_theme/static/css/catalog-smart-selector.css`
- Create: `twocomms/twocomms_django_theme/static/js/catalog-smart-selector.js`
- Modify: `twocomms/twocomms_django_theme/templates/pages/catalog.html`

**Step 1: Implement the approved layout**

Match Variant 3's dense mobile-first command shelf, stable product media, compact desktop rail, four-column desktop grid, purple accent, 44px controls, reduced-motion support, and bottom-sheet states. Scope all selectors under `[data-smart-selector]`.

**Step 2: Implement interactions**

Support category navigation, URL-state facets, sort, reset, mobile filter sheet open/close/escape/focus return/page lock, guarded quick-view delegation, and IntersectionObserver progressive loading. Keep normal pagination links visible to no-JS users and crawlers.

**Step 3: Run syntax and focused regression checks**

Run `node --check` on the new JS, the focused Smart Selector tests, and `storefront.tests.test_catalog`.

### Task 4: Review and browser QA

**Files:**
- Modify only files identified by review findings.
- Artifacts: `twocomms/output/playwright/category-smart-selector-*`.

**Step 1: Request code review**

Review the branch against `origin/main`, focusing on scope leakage to root/search, URL/SEO regressions, template cache correctness, unsafe HTML, and filter/data truth.

**Step 2: Run browser QA**

Start the local Django server and exercise `/catalog/tshirts/`, `/catalog/hoodie/`, `/catalog/long-sleeve/`, `/catalog/`, and search at 320, 375, 430, 768, and 1440px. Verify no overflow, broken images, console errors, request failures, or overlay overlap; verify category tabs, filters, reset, sort, sheet Escape, product links, SEO blocks, and progressive loading.

**Step 3: Apply evaluation fixes and rerun all checks**

Resolve every critical/important finding, rerun the full verification set, and report the branch and artifacts. Do not push or deploy without explicit authorization.
