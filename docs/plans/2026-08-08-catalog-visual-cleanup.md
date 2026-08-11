# Catalog Visual Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the deployed catalog's visual noise and align filter controls with the Instagram hosted checkout while preserving all filtering and merchandising behavior.

**Architecture:** Keep the backend context and JavaScript state model intact. Make a narrow template/CSS correction: remove duplicated presentation, retain accessible data, and restyle the existing controls and sheet using established checkout tokens.

**Tech Stack:** Django templates, CSS, vanilla JavaScript, Django TestCase.

---

### Task 1: Lock the product-first render contract

**Files:**
- Modify: `twocomms/storefront/tests/test_category_smart_selector.py`
- Modify: `twocomms/storefront/tests/test_catalog_merchandising_facets.py`

**Steps:**
1. Add assertions that rendered cards omit `smart-product-card__decision-meta` and `smart-product-card__color-label`.
2. Add an assertion that the permanent `smart-selector__quick-facets` row is absent.
3. Add an assertion that a thermochromic icon is inside `smart-product-card__swatch-dot`.
4. Run the focused tests and confirm the new assertions fail for the expected markup.

### Task 2: Remove duplicated card and quick-filter presentation

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/partials/catalog_smart_product_card.html`
- Modify: `twocomms/twocomms_django_theme/templates/partials/catalog_smart_selector.html`

**Steps:**
1. Remove the visible decision metadata `<dl>` only.
2. Remove the visible `Колір` label while preserving the color row accessible label.
3. Nest the thermo icon inside the swatch-dot element.
4. Remove the permanent quick-facet navigation only.
5. Keep applied-filter chips and all data/filter hooks.
6. Run focused tests and confirm the render contract passes.

### Task 3: Align controls and mobile sheet with hosted checkout

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/css/catalog-smart-selector.css`

**Steps:**
1. Replace selector purple tokens with the `instagram-checkout.css` neutral/warm palette.
2. Replace the filled purple checkbox dot with a warm checkmark state.
3. Restyle the sheet with a drag handle, 22px top radii, neutral lifted surface and warm footer action.
4. Keep 44px targets, safe areas, scroll lock, reduced motion and desktop rail behavior.
5. Place the thermo icon within the 22px swatch circle.
6. Remove now-unused card metadata and quick-facet CSS.

### Task 4: Verify and publish

**Files:**
- Test: focused storefront/Product Catalog suites

**Steps:**
1. Run focused Django tests, `manage.py check`, migration drift, JS syntax and `git diff --check`.
2. Capture production-like mobile and desktop screenshots and open/close the filter sheet.
3. Confirm no horizontal overflow and no console errors.
4. Commit, push `main`, deploy static assets, restart Passenger and verify live URLs.
