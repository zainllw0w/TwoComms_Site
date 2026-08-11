# Product Catalog Card Grid Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the regressed one-column catalog rows with a dark, compact, draggable four-column product card grid, a three-column garment-category grid, a compact taxonomy board, and a balanced desktop editor main tab without changing canonical backend contracts.

**Architecture:** Keep the existing Django context, canonical Product Catalog routes, DOM data hooks, status/index endpoints, and reorder implementation. Change only the scoped custom-admin markup and presentation where necessary. Add a grouped taxonomy view-model only if the flat context cannot represent parent panels.

**Tech Stack:** Django templates and tests, vanilla JavaScript, existing custom-admin CSS, Node test runner, authenticated desktop browser QA, production MariaDB release gate.

---

### Task 1: Lock the catalog card contracts

**Files:**
- Modify: twocomms/product_catalog/tests/test_product_catalog_contracts.py
- Modify: twocomms/product_catalog/static/product_catalog/editor-catalog.test.js

**Step 1: Write failing template-contract tests**

Assert dedicated product-card media, compact icon metrics, a fixed action footer, category-card media, accessible icon actions, four-product and three-category desktop tracks, plus the existing product/order/drag data hooks.

**Step 2: Run the focused Django test and verify RED**

Run the ProductCatalogContractsTests suite. Expected: the new media, metric, footer, and grid contracts fail against the current row layout.

**Step 3: Add a pure reorder regression test**

Cover moving an item across a four-column visual row and prove the persisted sequence remains linear and deterministic.

### Task 2: Restore visual product and category cards

**Files:**
- Modify: twocomms/twocomms_django_theme/templates/pages/admin_panel.html
- Modify: twocomms/twocomms_django_theme/static/css/styles.css
- Modify: twocomms/twocomms_django_theme/static/css/styles.purged.css

**Step 1: Refine existing markup without changing data hooks**

Move the drag and order control onto product media. Render title, category, and price in a compact body. Convert colors, photos, views, and unique visits to icon metrics. Place status, indexing, edit, and delete controls in a stable footer. Preserve every endpoint, select, action name, product ID, order position, and drag handle.

**Step 2: Add dark scoped grid styles**

At wide desktop use four product columns and three category columns. Use graphite surfaces, radii no larger than 8px, fixed media proportions, two-line title clamps, fixed-size icon controls, visible focus states, and desktop reductions that prevent overflow.

**Step 3: Run contract tests and verify GREEN**

Run the focused Django and Node tests, then git diff --check.

### Task 3: Turn taxonomy into a compact hierarchy board

**Files:**
- Modify: twocomms/storefront/views/admin.py only if grouped context is required
- Modify: twocomms/twocomms_django_theme/templates/pages/admin_panel.html
- Modify: twocomms/twocomms_django_theme/static/css/styles.css
- Modify: twocomms/product_catalog/tests/test_taxonomy_admin.py

**Step 1: Add a failing presentation test**

Assert root collections are visually grouped while descendants retain correct aria-level, IDs, media, counts, SEO state, reorder, edit, and archive controls.

**Step 2: Implement the smallest grouped presentation**

Reuse authoritative parent, depth, and path data. Do not change taxonomy persistence, arbitrary depth, cycle prevention, archive rules, derived brigades, or manual military semantics.

**Step 3: Run taxonomy tests**

Run taxonomy admin, audience taxonomy, and merchandise collection suites.

### Task 4: Balance the editor main tab

**Files:**
- Modify: twocomms/product_catalog/templates/product_catalog/editor.html
- Modify: twocomms/product_catalog/static/product_catalog/editor.css
- Modify: twocomms/product_catalog/tests/test_editor.py

**Step 1: Add a failing layout contract**

Assert equal identity and commerce panels, equal audience and taxonomy panels, and a regular Storage artwork grid while preserving every form ID and the active main panel.

**Step 2: Implement CSS-first balancing**

Prefer existing markup and scoped grid areas. Do not change save payloads, audience derivation, collection selection, print artwork source, or tab behavior.

**Step 3: Run editor Django and Node tests**

### Task 5: Fix confirmed cross-category collection regression

**Files:**
- Modify: twocomms/storefront/tests/test_category_smart_selector.py
- Modify: twocomms/storefront/views/catalog.py

**Step 1: Add a failing regression test**

Create one 225 T-shirt and one 225 hoodie and assert the merch landing includes both rather than reducing the queryset to the first garment category.

**Step 2: Verify RED, implement union behavior, and verify GREEN**

Keep explicitly selected garment-category pages and selector URL semantics unchanged.

### Task 6: Visual and interaction QA

**Step 1: Build and syntax-check assets**

Run Product Catalog Node tests, JavaScript syntax checks, CSS build or compression commands used by the repository, Django check, migration drift check, focused Django suites, and git diff --check.

**Step 2: Run authenticated desktop browser QA**

At 1280x900 and 1440x1000 verify grid density, image framing, text clamps, status and indexing controls, tooltips, taxonomy hierarchy, keyboard focus, pointer drag, keyboard reorder, save transitions, and zero horizontal overflow.

**Step 3: Run external read-only visual review**

Resolve every mandatory finding and repeat browser QA until the catalog and editor pass.

### Task 7: Finish retained defects and release gates

**Step 1: Verify variant images last**

Test provisional preview without reload, circular upload and optimization progress, WebP, AVIF, responsive, save and verify states, retry, error, delete, superseded jobs, and reload-safe polling.

**Step 2: Run rename and recovery gates**

Prove zero runtime Fable or Fable5 references, schema resume and rollback behavior, external MyISAM db_constraint=False, migration state, and all focused suites.

**Step 3: Integrate current origin/main safely**

Preserve incoming PDP gallery changes and rerun verification. Exclude .serena/project.yml, local browser settings, screenshots, .playwright-cli, QA databases and media, and secrets.

**Step 4: Commit, push, and deploy only after MariaDB proof**

Take and validate a production MySQL backup, inspect real table engines, collations, and constraints, run guarded schema adoption and migrations, dry-run and apply reviewed taxonomy data, collect and compress static assets, restart Passenger, verify deployed SHA, and perform authenticated staff plus public catalog QA.

