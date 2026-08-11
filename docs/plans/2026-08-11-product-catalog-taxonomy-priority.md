# Product Catalog Taxonomy Priority Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish the compact audience and merchandising hierarchy workflows first, safely backfill production assignments, and close all previously discovered editor defects before deployment.

**Architecture:** Keep garment categories separate from the self-referential `MerchCollection` tree. Persist only canonical audience codes and selected taxonomy leaves, derive effective audiences and ancestors for filters/UI, and use dry-run-first management commands for production MariaDB data changes.

**Tech Stack:** Django 5, Python 3.13/3.14, MariaDB 11.4, vanilla JavaScript, existing custom-admin templates/CSS, Node test runner, Playwright desktop QA.

---

### Task 1: Lock the approved hierarchy contracts with tests

**Files:**
- Modify: `twocomms/product_catalog/tests/test_audience_taxonomy.py`
- Modify: `twocomms/product_catalog/tests/test_merch_collections.py`
- Modify: `twocomms/product_catalog/tests/test_editor.py`

**Step 1: Write failing tests**

Add focused assertions that:

- `unisex` persists alone and resolves to `unisex`, `women`, and `men`;
- `225` and `127` derive only `brigades`;
- `military` remains unselected unless explicitly submitted;
- removing a derived parent is impossible while a selected child remains;
- the editor presents grouped hierarchy metadata rather than a flat ambiguous list.

**Step 2: Run tests and verify RED**

Run:

`SECRET_KEY=test_local_secret /Users/zainllw0w/TwoComms/site/.venv/bin/python twocomms/manage.py test --settings=test_settings product_catalog.tests.test_audience_taxonomy product_catalog.tests.test_merch_collections product_catalog.tests.test_editor --verbosity 1`

Expected: any missing manual-military or grouped-hierarchy contract fails for the intended reason.

**Step 3: Implement the minimal contract fixes**

Modify only the resolver/bootstrap/rendering code needed to satisfy the tests. Do not add a `brigades -> military` implication.

**Step 4: Run tests and verify GREEN**

Run the Step 2 command and all four product-catalog Node test files.

### Task 2: Refine the `Основне` desktop taxonomy workspace

**Files:**
- Modify: `twocomms/product_catalog/templates/product_catalog/editor.html`
- Modify: `twocomms/product_catalog/static/product_catalog/editor.js`
- Modify: `twocomms/product_catalog/static/product_catalog/editor.css`
- Modify: `twocomms/product_catalog/views.py`
- Test: `twocomms/product_catalog/tests/test_editor.py`

**Step 1: Add markup/behavior tests**

Assert compact audience tiles, explicit derived labels, grouped top-level taxonomy rows, nested child rows, stable selected summaries, and no light-theme fallback styles.

**Step 2: Implement the compact layout**

Keep garment category in the identity card. Render merchandising nodes as compact parent groups with inline children, clear manual versus derived states, and stable controls that do not resize when counts change.

**Step 3: Verify keyboard and save/reload behavior**

Test checkbox operation, search, dirty state, save payload, editor reload, and future third-level descendants.

### Task 3: Finish the custom-admin taxonomy manager

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/pages/admin_panel.html`
- Modify: `twocomms/twocomms_django_theme/static/css/styles.css`
- Modify: `twocomms/twocomms_django_theme/static/css/styles.purged.css`
- Modify: `twocomms/storefront/views/admin.py`
- Modify: `twocomms/product_catalog/views.py`
- Test: `twocomms/product_catalog/tests/test_taxonomy_admin.py`

**Step 1: Add failing depth and dark-theme tests**

Cover arbitrary hierarchy depth, accurate `aria-level`, compact desktop density, dark-only colors, icon/cover previews, SEO indicators, cycle rejection, reorder, and archive protection.

**Step 2: Implement exact-depth rows and editor dialog**

Compute depth/path server-side, render parents before descendants, keep icon actions minimal, and preserve localized content, PNG/icon/cover, SEO, indexability, and active-state editing.

**Step 3: Run focused taxonomy tests**

Run `product_catalog.tests.test_taxonomy_admin` and custom-admin template contract tests.

### Task 4: Add a dry-run-first production assignment command

**Files:**
- Create: `twocomms/product_catalog/management/commands/backfill_product_catalog_taxonomy.py`
- Create: `twocomms/product_catalog/tests/test_backfill_product_catalog_taxonomy.py`

**Step 1: Write failing command tests**

Cover:

- missing audience gets `unisex`;
- existing `women`, `men`, or `unisex` remains unchanged;
- T-shirt and hoodie products whose title/slug identifies `225` receive the `225` leaf;
- `brigades` is not stored redundantly and `military` is never added;
- dry-run writes nothing;
- repeated `--apply` is idempotent;
- output reports exact candidate and created counts.

**Step 2: Implement the command**

Use one transaction for `--apply`, lock candidate assignment rows, validate required tags/collections and `225.parent.slug == "brigades"`, and refuse to run against an inconsistent taxonomy.

**Step 3: Verify local RED/GREEN and production dry-run**

Run the command tests locally. After schema adoption on production, run dry-run and require the reviewed target set before `--apply`.

### Task 5: Close previously discovered defects without changing priority

**Files:**
- Existing changed files under `twocomms/product_catalog/`
- Existing changed image pipeline files under `twocomms/storefront/`
- Existing adoption/recovery tests

**Step 1: Re-run the retained defect suites**

Verify schema adoption/rollback/resume, MySQL metadata checks, bounded image workers, lease ownership, completed-job derivative verification, polling terminal errors, cleanup bounds, print artwork source, main-tab default, indexing truth states, and removed-editor reference scans.

**Step 2: Fix only reproducible remaining failures using TDD**

Do not reopen broad unrelated management/Instagram failures. Compare any broad-suite failure to `origin/main` before treating it as part of this release.

### Task 6: Finish variant-color image upload last

**Files:**
- Modify: `twocomms/product_catalog/static/product_catalog/editor-upload.js`
- Modify: `twocomms/product_catalog/static/product_catalog/editor.js`
- Modify: `twocomms/product_catalog/static/product_catalog/editor.css`
- Modify: `twocomms/product_catalog/views.py`
- Test: `twocomms/product_catalog/static/product_catalog/editor-upload.test.js`
- Test: `twocomms/product_catalog/tests/test_editor.py`

**Step 1: Reproduce no-refresh behavior**

Upload a color image and assert the provisional preview appears immediately, then transitions through persisted optimization states without a full page reload.

**Step 2: Fix any remaining UI/backend boundary defect**

Keep the existing upload -> WebP -> AVIF -> responsive -> save -> verify job contract. Fix only confirmed stale rendering, polling, or job-addressing issues.

### Task 7: Verify, review, publish, and deploy

**Files:**
- All intended files in the isolated worktree

**Step 1: Run focused and cross-app verification**

Run product-catalog Django tests, changed storefront/management tests, all Node tests, `manage.py check`, `makemigrations --check`, syntax checks, static lookup, cron-installer tests, zero-reference scans, and `git diff --check`.

**Step 2: Run desktop browser QA**

At 1280px and 1440px verify `Основне`, audience derivation, hierarchy selection, taxonomy administration, category/product rows, index controls, drag-and-drop, and variant image upload.

**Step 3: Request final read-only code review**

Fix all P1/P2 findings and rerun affected checks.

**Step 4: Commit and push `main` safely**

Stage only intended files from the isolated worktree, update from `origin/main`, rerun verification, integrate into `main`, and push.

**Step 5: Deploy with guarded MariaDB adoption**

Enable maintenance, take and validate a full MySQL backup, run adoption `--check`, apply the resumable schema adoption with the expected SHA, migrate, run the taxonomy backfill dry-run, review exact rows, apply it, collect/compress static assets, restart Passenger, and verify the deployed SHA and live staff/public flows.
