# Catalog Card Direct Color Swatches Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the catalog card's square color toggle with up to three direct circular color links matching the homepage and Variant B spacing.

**Architecture:** Keep color data server-rendered in `catalog_smart_product_card.html`; each preview variant becomes a direct anchor using its existing public URL. Remove only the obsolete card-level toggle/menu styling and click handling, while preserving the existing discount, heart, thermo flame, price, fit, and `4 / 5` media treatment.

**Tech Stack:** Django templates, scoped catalog CSS, vanilla catalog selector JavaScript, Django template tests, Playwright screenshots.

---

### Task 1: Lock the card contract with a failing regression test

**Files:**
- Modify: `twocomms/storefront/tests/test_category_smart_selector.py`

1. Replace the square-toggle assertions with expectations for a single color stack containing at most three `smart-product-card__color-choice` anchors, no `data-smart-color-toggle`, no `smart-product-card__color-menu`, and the real variant URLs.
2. Assert that ordinary and thermochromic swatches use the circular dot markup and that the flame stays nested in the dot.
3. Run the focused test and confirm it fails against the current square implementation.

### Task 2: Implement direct circular swatches

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/partials/catalog_smart_product_card.html`
- Modify: `twocomms/twocomms_django_theme/static/css/catalog-smart-selector.css`
- Modify: `twocomms/twocomms_django_theme/static/js/catalog-smart-selector.js`

1. Render `p.colors_preview|slice:':3'` as direct anchors under the heart, with `aria-label`, `title`, `aria-current` for the default variant, and the existing `public_url` fallback.
2. Give each anchor a compact circular swatch using the homepage's split-color gradient and a centered black thermo flame; do not add a square well, count badge, text label, or extra card copy.
3. Remove the unused toggle/menu selectors and event branches, leaving filter-sheet behavior unchanged.
4. Keep dimensions stable at desktop and mobile, including the B-aligned discount marker and outlined heart.
5. Bump the catalog smart-selector stylesheet cache key to `20260808-v15`.
6. Re-run the focused test suite and the full catalog smart-selector tests.

### Task 3: Visual verification

1. Capture the real catalog card at 320 px, 390 px, and 1440 px.
2. Confirm circles sit directly below/near the heart, thermo flame is centered and black, no square remains, variant links navigate correctly, and B spacing/price treatment is unchanged.
3. Run `git diff --check` and inspect the tracked diff for scope creep.

### Task 4: Ship

1. Commit only the card/template/CSS/JS/test/plan files.
2. Push `main` to `origin/main`.
3. On production, fast-forward pull, collect static files, compress, touch `tmp/restart.txt`, and verify the deployed SHA plus live circular swatches.
