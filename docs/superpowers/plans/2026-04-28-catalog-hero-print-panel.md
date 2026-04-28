# Catalog Hero Print Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the catalog hero and custom-design panel closer to the supplied reference by improving hero image framing and adding a visible selectable print-zone overlay.

**Architecture:** Keep the existing catalog page and image assets. Add code-native overlay controls to the print panel, scoped CSS for the dashed print zone/glow/smoke effects, and a small route-local script for selectable mode state.

**Tech Stack:** Django templates, static CSS/JS, existing WebP catalog assets, Django template regression tests, Playwright screenshots.

---

### Task 1: Lock Markup Expectations

**Files:**
- Modify: `twocomms/storefront/tests/test_catalog.py`

- [x] Add assertions that catalog HTML renders selectable print controls, the preview overlay, and the catalog script.
- [x] Run `python manage.py test --settings=test_settings --keepdb --parallel 1 storefront.tests.test_catalog.CatalogViewTests.test_catalog_root_renders_print_zone_selector`.

### Task 2: Implement Print Panel And Hero Refinement

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/pages/catalog.html`
- Modify: `twocomms/twocomms_django_theme/static/css/catalog-redesign.css`
- Create: `twocomms/twocomms_django_theme/static/js/catalog-redesign.js`

- [x] Convert the three print-panel stage tiles to buttons with `data-print-mode` and `aria-pressed`.
- [x] Add an absolutely positioned dashed zone overlay with corner handles and a short zone label over the hoodie preview.
- [x] Add scoped JS to toggle the active stage and preview `data-print-mode`.
- [x] Refine `catalog-hero__backdrop` background sizing and gradient overlays so the person is smaller and wall text is more visible.
- [x] Add reduced-motion handling for the zone animation.

### Task 3: Verify Locally

**Files:**
- No new files beyond implementation files.

- [x] Run targeted catalog/SEO tests.
- [x] Run `python manage.py check --settings=test_settings`.
- [x] Run `python manage.py collectstatic --dry-run --noinput --settings=test_settings`.
- [x] Run `git diff --check`.
- [x] Capture local desktop/mobile screenshots for `/catalog/` and inspect with `view_image`.

### Task 4: Commit And Deploy

**Files:**
- Commit only tracked implementation/test/plan/static files.

- [ ] Confirm `newCatalog/` and untracked JPEG files are not staged.
- [ ] Commit with a focused message.
- [ ] Push `main`.
- [ ] Deploy with manual server `git pull --ff-only`, `compress --force`, `collectstatic`, and restart marker.
- [ ] Verify production HTML, asset responses, and screenshots.
