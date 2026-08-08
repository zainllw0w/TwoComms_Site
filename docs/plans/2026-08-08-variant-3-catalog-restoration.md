# Variant 3 Catalog Restoration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore the approved Variant 3 category catalog visual and interaction model while preserving all current merchandising, filtering, SEO, analytics and inventory functionality.

**Architecture:** Keep the current Django view context and canonical query filtering. Restore the prototype hierarchy in the scoped Smart Selector template and stylesheet, then adapt the existing overlay JavaScript to focused quick-selector modes and advanced-filter mode. No model or migration changes are required.

**Tech Stack:** Django templates, scoped CSS, vanilla JavaScript, Django TestCase, Playwright CLI.

---

### Task 1: Lock the Variant 3 render contracts

**Files:**
- Modify: `twocomms/storefront/tests/test_category_smart_selector.py`

**Step 1: Write failing assertions**

Add focused tests that require:

- the mobile quick selector dock with `theme`, `fit`, and `color` triggers;
- focused sheet sections for theme, fit, color and sort;
- the advanced sheet still contains audience, availability, size, thermo and nested collection controls;
- the base category H1 renders the compact category label instead of the long SEO marketing sentence;
- the product card renders a quiet fit marker beside price;
- the root stylesheet does not create a sticky-breaking overflow context;
- the desktop rail uses a right divider rather than an enclosing card;
- the product card has no external panel background, border, shadow or inset padding;
- the favorite control has no visible circular background.

**Step 2: Run the focused tests and verify RED**

Run:

```bash
python manage.py test storefront.tests.test_category_smart_selector -v 2
```

Expected: the newly added Variant 3 restoration assertions fail against the current production markup/CSS.

**Step 3: Commit the failing contracts**

```bash
git add twocomms/storefront/tests/test_category_smart_selector.py
git commit -m "test(catalog): lock Variant 3 visual contracts"
```

### Task 2: Restore the Variant 3 page hierarchy and focused sheets

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/partials/catalog_smart_selector.html`

**Step 1: Restore the command and selector structure**

Render the compact command row with filter trigger, result count and mobile sort trigger. Add the three quick selector controls directly below it. Each trigger must expose its current value and use `data-smart-open-filters` plus `data-smart-focus-filter`.

**Step 2: Extend the existing sheet semantically**

Keep one accessible overlay. Add mode metadata and a sort section. Mark every sheet fieldset with `data-smart-filter-section`. Keep the advanced footer for `all` mode and allow focused modes to show only their target section.

**Step 3: Preserve all enhanced facets**

Do not remove theme children, collections, audience, availability, size, thermo or color URLs. Keep real category links, crawlable pagination and SEO blocks unchanged.

**Step 4: Run the render tests**

Run the focused Django test module and verify the template assertions pass or fail only on the not-yet-restored CSS/JavaScript contracts.

### Task 3: Restore the Variant 3 visual system and product cards

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/css/catalog-smart-selector.css`
- Modify: `twocomms/twocomms_django_theme/templates/partials/catalog_smart_product_card.html`

**Step 1: Restore the product-first first viewport**

Use the prototype's compact spacing, short category H1, command shelf and three selector controls. At 320px preserve two product columns and expose the first product media as early as the prototype.

**Step 2: Restore the desktop rail**

Remove the rail's enclosing surface, full border and radius. Use `position: sticky`, a right divider, compact groups and transparent option rows. Remove root overflow behavior that changes the sticky containing block.

**Step 3: Restore open product tiles**

Remove card padding, background, enclosing border and shadow. Keep a media border/radius, lower divider and stable image aspect ratio. Restore the fit marker beside price. Keep accurate variant price and thermo swatches.

**Step 4: Reduce favorite visual weight**

Keep a 44px hit area but remove visible circle fill, border and large shadow. Render the heart at the prototype scale with only a small legibility shadow.

**Step 5: Style focused sheets from the screenshots**

Use the Variant 3 handle, header, option rows, icon/swatch column, counts and selected warm outline. Advanced mode may be denser but must share the same sheet language.

### Task 4: Restore focused selector behavior

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/js/catalog-smart-selector.js`

**Step 1: Add sheet modes**

On open, read the trigger mode, set the sheet heading, expose only the relevant section for focused modes and expose all sections for advanced mode. Preserve inert background, scroll lock, focus trap, history close and analytics.

**Step 2: Add sort actions**

Handle `data-smart-sort-value` buttons by writing the validated existing sort query parameter and navigating. Keep the desktop select behavior.

**Step 3: Keep repeatable facets unchanged**

Do not change `buildFacetUrl` AND semantics or canonical query validation.

**Step 4: Verify JavaScript syntax**

```bash
node --check twocomms/twocomms_django_theme/static/js/catalog-smart-selector.js
```

### Task 5: Full verification and visual comparison

**Files:**
- Create screenshots under: `output/playwright/variant3-restoration/`

**Step 1: Run automated checks**

```bash
python manage.py test storefront.tests.test_category_smart_selector storefront.tests.test_fable5_variant_merchandising -v 2
python manage.py check
python manage.py makemigrations --check --dry-run
node --check twocomms/twocomms_django_theme/static/js/catalog-smart-selector.js
git diff --check
```

**Step 2: Run browser QA**

Verify at 320, 390, 768, 1024 and 1440px:

- no horizontal overflow or console errors;
- quick theme, fit, color and sort sheets open and close;
- advanced filter exposes all enhanced facets;
- multiple facets remain in the URL together;
- brigade disclosure works;
- desktop rail remains sticky while scrolling;
- cards and heart match the Variant 3 hierarchy;
- product links, progressive load and SEO content remain present.

**Step 3: Compare screenshots**

Compare new 320px and 1440px captures against:

- `output/playwright/catalog-variant3-comparison/variant3-original-320.png`
- `output/playwright/catalog-variant3-comparison/variant3-original-1440.png`

Do not deploy until the local comparison is visibly closer to the original Variant 3 than current production.
