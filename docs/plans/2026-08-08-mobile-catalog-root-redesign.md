# Mobile Catalog Root Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the mobile `/catalog/` page category-first with one-tap access to T-shirts, hoodies, and long sleeves, while demoting custom print and preserving the current desktop catalog.

**Architecture:** Keep the Django view data, URLs, structured content, and desktop markup contract intact. Add a mobile-first category gateway and compact custom-print CTA in the existing catalog template, scope presentation changes to `max-width: 767px`, and reuse the current showcase context and real catalog assets. Do not alter concrete category pages or product cards.

**Tech Stack:** Django templates, scoped CSS, existing vanilla JavaScript analytics hooks, Django TestCase, browser QA.

---

### Task 1: Build and compare three standalone mobile prototypes

**Files:**
- Create: `/Users/zainllw0w/.codex/visualizations/2026/08/08/019fe28f-7087-7a23-a7aa-24160dd0bcbb/twocomms-mobile-catalog-concepts/variant-1-visual-triptych/index.html`
- Create: `/Users/zainllw0w/.codex/visualizations/2026/08/08/019fe28f-7087-7a23-a7aa-24160dd0bcbb/twocomms-mobile-catalog-concepts/variant-2-smart-tabs/index.html`
- Create: `/Users/zainllw0w/.codex/visualizations/2026/08/08/019fe28f-7087-7a23-a7aa-24160dd0bcbb/twocomms-mobile-catalog-concepts/variant-3-editorial-deck/index.html`

**Step 1: Implement each concept from its dedicated brief**

Use the live 390x844 `/catalog/` and `/catalog/tshirts/` screenshots as layout truth. Use local TwoComms catalog images, not generic stock media.

**Step 2: Verify mobile geometry**

Open each prototype at 320x568, 375x812, 390x844, and 430x932. Expected: all three categories are visible without horizontal scrolling and no fixed navigation overlaps the custom-print CTA.

**Step 3: Evaluate and correct each concept**

Check visual hierarchy, tap clarity, brand consistency, text fit, media crops, and distinction among variants. Apply priority corrections before presenting screenshots.

### Task 2: Add failing mobile root catalog contracts

**Files:**
- Modify: `twocomms/storefront/tests/test_catalog.py`

**Step 1: Write the failing template contract test**

Assert that the root catalog renders a mobile gateway with exactly three real category links, a compact secondary custom-print link, and no duplicate category names inside the gateway.

**Step 2: Run the focused test to verify it fails**

Run:

```bash
SECRET_KEY=test_local_secret /Users/zainllw0w/TwoComms/site/.venv/bin/python twocomms/manage.py test storefront.tests.test_catalog.CatalogViewTests --settings=test_settings --keepdb
```

Expected: the new mobile-gateway assertion fails before implementation.

### Task 3: Implement the selected mobile gateway

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/pages/catalog.html`
- Modify: `twocomms/twocomms_django_theme/static/css/catalog-redesign.css`

**Step 1: Add semantic mobile gateway markup**

Render one `nav` with three category anchors using the existing `catalog_showcase_cards` context. Render one compact custom-print anchor below it. Keep the current desktop hero and showcase markup available for desktop.

**Step 2: Add strictly scoped responsive CSS**

At `max-width: 767px`, show the new gateway and compact print CTA, hide only the redundant mobile hero/showcase surfaces, preserve the page H1 for accessibility, and keep fixed dimensions for the three-column row.

**Step 3: Run the focused test**

Run the command from Task 2. Expected: the new contracts pass; record any pre-existing failures separately.

### Task 4: Preserve behavior, SEO, and desktop parity

**Files:**
- Modify: `twocomms/storefront/tests/test_catalog.py`
- Modify only if required: `twocomms/twocomms_django_theme/static/js/catalog-redesign.js`

**Step 1: Add regression assertions**

Assert one H1, crawlable category URLs, preserved color filters and SEO blocks, and no mobile gateway on search/category templates where the Smart Selector already owns the experience.

**Step 2: Add analytics only if no existing delegated link tracking covers the gateway**

Emit a non-blocking category-selection event with category slug and `catalog_root_mobile`. Do not add a new request or navigation delay.

**Step 3: Run focused regression suites**

```bash
SECRET_KEY=test_local_secret /Users/zainllw0w/TwoComms/site/.venv/bin/python twocomms/manage.py test storefront.tests.test_catalog storefront.tests.test_category_smart_selector --settings=test_settings --keepdb
node --check twocomms/twocomms_django_theme/static/js/catalog-redesign.js
SECRET_KEY=test_local_secret /Users/zainllw0w/TwoComms/site/.venv/bin/python twocomms/manage.py check --settings=test_settings
git diff --check
```

Expected: no new failures. The current baseline has two known failures in `test_category_smart_selector` that must either be independently reconciled with current live behavior or explicitly separated from this change.

### Task 5: Browser QA and production delivery

**Files:**
- Create: `output/playwright/catalog-root-mobile-selected-320.png`
- Create: `output/playwright/catalog-root-mobile-selected-390.png`
- Create: `output/playwright/catalog-root-desktop-selected-1440.png`

**Step 1: Verify local responsive behavior**

Exercise all three category links and the custom-print link at the acceptance viewports. Confirm no horizontal overflow, broken images, console errors, or bottom-nav collisions.

**Step 2: Commit the selected implementation**

```bash
git add docs/plans/2026-08-08-mobile-catalog-root-redesign-design.md docs/plans/2026-08-08-mobile-catalog-root-redesign.md twocomms/storefront/tests/test_catalog.py twocomms/twocomms_django_theme/templates/pages/catalog.html twocomms/twocomms_django_theme/static/css/catalog-redesign.css
git commit -m "feat(catalog): simplify mobile root category choice"
```

**Step 3: Integrate to current main and push**

Re-read both worktree statuses, preserve unrelated user changes, fast-forward or cherry-pick the isolated commit onto current `main`, then push `origin/main`. Verify `main...origin/main` is `0 0` for the shipped commit.

**Step 4: Deploy through the authorized SSH command**

Run the user-provided production pull command. Then run the repository's static/template deployment steps: `collectstatic --no-input`, `compress --force`, `check`, and Passenger restart.

**Step 5: Verify production**

Confirm the deployed SHA, live 320/390 mobile category gateway, unchanged desktop layout, working category/custom-print URLs, zero overflow, and no console or image failures.
