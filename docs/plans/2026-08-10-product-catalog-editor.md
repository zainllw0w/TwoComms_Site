# Product Catalog Editor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the renamed `product_catalog` app the single product editor, remove only the obsolete duplicate CRUD/editor stack, and deliver a truthful, desktop-first catalog/editor workflow without losing production data or existing storefront behavior.

**Architecture:** The retained catalog editor is retained functionally and becomes the canonical `product_catalog` Django app. Its existing migration sequence `0001` through `0011` remains intact, while a guarded one-time maintenance command adopts the already populated production tables, migration rows, ContentTypes, permissions, identifiers, and persisted media paths from the previous app identity. The custom admin catalog receives a scoped presentation layer that preserves existing drag-and-drop data hooks and public URLs, while taxonomy, audience, print, and indexing contracts are made explicit and testable.

**Tech Stack:** Django 5, Python 3.13, SQLite test settings, MySQL production, Django migrations/management commands, existing custom admin templates/CSS/JS, Font Awesome icons already bundled, and Playwright desktop browser checks.

---

### Task 1: Establish red tests for the new editor contracts

**Files:**
- Create: `twocomms/product_catalog/tests/test_product_catalog_contracts.py`
- Modify: `twocomms/product_catalog/tests/test_audience_taxonomy.py`
- Modify: `twocomms/product_catalog/tests/test_merch_collections.py`
- Modify: `twocomms/product_catalog/tests/test_editor_generic_options.py`
- Modify: `twocomms/product_catalog/tests/test_editor.py`

**Step 1: Write failing tests**

Cover one behavior per test: `unisex` resolves to `unisex`, `men`, and `women` for catalog filtering while preserving canonical persistence; selecting a collection child exposes derived ancestors; print preview never returns a finished-product image; both new and existing editor requests render `Основне` as the first active panel; and the renamed route names render the same editor.

**Step 2: Run the focused suite and verify RED**

Run:
`SECRET_KEY=test_local_secret /Users/zainllw0w/TwoComms/site/.venv/bin/python twocomms/manage.py test --settings=test_settings product_catalog.tests.test_product_catalog_contracts product_catalog.tests.test_audience_taxonomy product_catalog.tests.test_merch_collections product_catalog.tests.test_editor_generic_options product_catalog.tests.test_editor --verbosity 1`

Expected: the new contract tests fail because the resolver, route identity, print fallback, and tab state do not yet meet the contract.

### Task 2: Implement audience and collection implication services

**Files:**
- Modify: `twocomms/product_catalog/services_audience.py`
- Modify: `twocomms/product_catalog/services_collections.py`
- Modify: `twocomms/product_catalog/views.py`
- Modify: `twocomms/product_catalog/tests/test_audience_taxonomy.py`
- Modify: `twocomms/product_catalog/tests/test_merch_collections.py`

**Step 1: Implement minimal resolvers**

Add a shared effective-audience resolver used by save/bootstrap/public facet consumers. Keep `unisex` as the canonical stored assignment and expose `men`/`women` as derived effective codes. Return collection dictionaries with ancestor metadata and a derived/locked parent marker for the editor; keep persistence leaf-specific through the existing `_without_implied_parents` contract.

**Step 2: Run the focused tests and verify GREEN**

Run the Task 1 command and the catalog facet tests. Expected: audience and collection contract tests pass without changing unrelated merchandising behavior.

### Task 3: Remove the finished-product print fallback and redesign print selection data

**Files:**
- Modify: `twocomms/product_catalog/views.py`
- Modify: `twocomms/product_catalog/static/product_catalog/editor.js`
- Modify: `twocomms/product_catalog/templates/product_catalog/editor.html`
- Modify: `twocomms/product_catalog/tests/test_editor_generic_options.py`

**Step 1: Keep the failing canonical-artwork test active**

Assert that previews use `Print.main_image`, then `PrintColorVariant.image`, otherwise `image_source="missing"`; a related `Product.main_image` must never be used.

**Step 2: Implement the canonical picker**

Remove `default_products` prefetch and the `image_source="product"` fallback. Return selected prints first, searchable/grouped by Storage metadata, with selected count and explicit missing-artwork state. Update the editor to show thumbnail/logo metadata and an unambiguous selected shelf.

**Step 3: Run print/editor tests**

Run the focused editor suite and confirm the updated fallback test passes.

### Task 4: Rename the active app and all runtime namespaces

**Files:**
- Rename directory: previous editor package -> `twocomms/product_catalog/`
- Modify: `twocomms/twocomms/settings.py`
- Modify: `twocomms/twocomms/urls.py`
- Modify: every tracked Python/template/static/test reference returned by the Serena/`rg` namespace scan
- Create: `twocomms/product_catalog/apps.py`
- Create: `twocomms/product_catalog/migrations/0001_initial.py`

**Step 1: Use structure-aware rename/search**

Rename imports, app config, template/static namespaces, reverse names, URL paths, related names, upload prefixes, verbose labels, constraint names, logger text, and JavaScript bootstrap identifiers to `product_catalog`/`catalog`. User-facing labels become `Керування каталогом`, `Редактор товару`, `Додати товар`, and `Редагувати товар`.

**Step 2: Preserve the renamed migration sequence**

Keep the renamed `0001`-`0011` migration files as the canonical state. Before normal `migrate`, the guarded command adopts every known table, index, constraint, migration record, ContentType, permission, and persisted path from the explicitly supplied previous identity to `product_catalog`. On a fresh database, Django creates the canonical tables directly from this migration sequence. Preserve `db_constraint=False` for links to legacy MyISAM `storefront_product` and `productcolors_*` tables.

**Step 3: Run import/system checks**

Run `SECRET_KEY=test_local_secret /Users/zainllw0w/TwoComms/site/.venv/bin/python twocomms/manage.py check --settings=test_settings` and the namespace import tests. Expected: no import references or URL reversing errors.

### Task 5: Add production identity/data adoption command

**Files:**
- Create: `twocomms/product_catalog/management/commands/adopt_product_catalog_schema.py`
- Create: `twocomms/product_catalog/tests/test_schema_adoption.py`
- Modify: `twocomms/product_catalog/migrations/0001_initial.py`

**Step 1: Write failing adoption tests**

Test table-name mapping, row-count and physical metadata invariants, idempotent reruns, migration recorder adoption, ContentType/permission app-label adoption, and replacement of persisted values from the supplied previous identity in JSON/text columns without touching unrelated values.

**Step 2: Implement guarded adoption**

Require explicit application/database/SHA/maintenance confirmations, take a private preflight snapshot of tables/counts/engine/collation/AUTO_INCREMENT/constraints, checkpoint after every irreversible DDL step, refuse partial mappings and drifted rollback values, and emit a machine-readable report. Rename only known catalog tables and known identifiers; rewrite only allow-listed persisted fields. The command must support `--check`, `--apply`, and `--rollback-snapshot` paths.

**Step 3: Run adoption tests**

Run the command tests against SQLite fixtures and a production-schema dry run. Expected: no writes in `--check`, deterministic counts, and clear refusal on missing/extra tables.

### Task 6: Remove obsolete product CRUD and builder surfaces

**Files:**
- Modify: `twocomms/storefront/urls.py`
- Modify: `twocomms/storefront/views/__init__.py`
- Modify: `twocomms/storefront/views/admin.py`
- Modify: `twocomms/storefront/api_urls.py`
- Modify: `twocomms/storefront/viewsets.py`
- Modify: `twocomms/storefront/views.py.backup`
- Delete: `twocomms/storefront/services/product_builder.py`
- Delete: `twocomms/twocomms_django_theme/templates/pages/add_product.html`
- Delete: `twocomms/twocomms_django_theme/templates/pages/add_product_new.html`
- Delete: `twocomms/twocomms_django_theme/templates/pages/admin_product_form.html`
- Delete: `twocomms/twocomms_django_theme/templates/pages/admin_product_edit_simple.html`
- Delete: `twocomms/twocomms_django_theme/templates/pages/admin_product_edit_unified.html`
- Delete: `twocomms/twocomms_django_theme/templates/pages/admin_product_colors.html`
- Delete: `twocomms/twocomms_django_theme/templates/pages/product_builder.html`
- Delete: `twocomms/twocomms_django_theme/static/js/product-builder.js`
- Delete: `twocomms/twocomms_django_theme/static/css/product-builder.css`
- Modify/Delete: tests that only exercise removed builder behavior after their contracts are ported

**Step 1: Port missing contracts first**

Move YouTube URL canonicalization, product priority assignment, POST-only staff deletion, and CSRF/403 behavior into the canonical editor/API tests before deleting the legacy forms.

**Step 2: Remove only product CRUD symbols**

Delete the listed routes, lazy-loader names, builder viewset/service, templates, and assets. Preserve the legacy loader and functions used by orders, categories, wholesale, `api_colors`, product reorder, and product status.

**Step 3: Verify zero references**

Run targeted route-resolution tests plus tracked-source scans for obsolete editor branding, removed route families, builder services/assets, and old-editor labels. There must be no runtime or user-facing references; compatibility identifiers may exist only inside the guarded schema-adoption boundary and its tests.

### Task 7: Redesign the custom admin catalog without breaking DnD

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/pages/admin_panel.html`
- Modify: `twocomms/twocomms_django_theme/static/css/styles.css`
- Modify: `twocomms/twocomms_django_theme/static/js/catalog-redesign.js` or the existing scoped catalog script location
- Create/modify: focused custom-admin template tests

**Step 1: Write markup/accessibility tests**

Assert the catalog has one canonical create/edit entry, no legacy links, scoped catalog class, stable DnD data attributes, icon-only edit/delete buttons with labels/tooltips, compact Google/IndexNow controls, taxonomy sections, and no nested decorative cards.

**Step 2: Implement scoped desktop composition**

Use a dense catalog row with fixed 80px media, taxonomy path, status/price, compact index cluster, drag handle, and isolated action cluster. Add calm category/collection cards with child counts and SEO/indexability indicators. Keep existing `.products-grid`, `.product-card`, `data-product-id`, `data-order-position`, `[data-drag-handle]`, and reorder API hooks unchanged.

**Step 3: Implement truthful indexing states**

Render `Не надсилали`, `Надсилання…`, `Прийнято API`, and `Помилка` with small check/error icons and tooltips that distinguish API acceptance from actual Search Console indexing. Preserve existing confirmation and retry behavior.

**Step 4: Run template/static tests and browser screenshots**

Use Playwright at 1280px and 1440px. Verify no compressed text/overlap, edit/delete tooltips, DnD drag/rollback, filter/search stability, index-state transitions, and editor navigation.

### Task 8: Improve the editor workspace and taxonomy manager

**Files:**
- Modify: `twocomms/product_catalog/templates/product_catalog/editor.html`
- Modify: `twocomms/product_catalog/static/product_catalog/editor.js`
- Modify: `twocomms/product_catalog/static/product_catalog/editor.css`
- Modify: `twocomms/product_catalog/views.py`
- Modify/create taxonomy endpoints, forms, templates, and tests in `twocomms/product_catalog/`

**Step 1: Make `Основне` unconditional**

Set the initial panel and `aria-selected` state to `Основне` for both new and existing products; preserve left navigation to variants, inventory, feeds, SEO, and media.

**Step 2: Reorganize the main workspace**

Separate identity/publication, garment category, audience, collection tree, Storage prints, media, and SEO/AEO fields into readable desktop sections with selected summaries and save-state feedback.

**Step 3: Add taxonomy management**

Expose garment categories separately from merchandising collections. Support add/edit/archive, parent-child reorder, PNG/icon/cover uploads, localized names/descriptions, SEO title/H1/description/keywords, indexability, and preview metadata while preserving existing public `/category/` and `/merch/` semantics.

**Step 4: Verify save/reload behavior**

Test create/edit/reload, audience and collection implication, Storage print selection, SEO fields, variants, inventory, feeds, and dirty-state navigation.

### Task 9: Final verification, commit, push, and deployment

**Files:**
- Modify: `docs/plans/2026-08-10-product-catalog-editor.md` only if acceptance evidence needs recording

**Step 1: Run full local verification**

Run focused suites, the full Django suite under `--settings=test_settings`, `manage.py check`, static collection/compression, and a zero-reference tracked-source scan.

**Step 2: Commit the isolated branch**

Stage only intended tracked changes and commit with a descriptive message. Do not stage existing unrelated untracked artifacts.

**Step 3: Integrate into `main` and push**

Fast-forward/merge the verified branch into `main`, verify `HEAD...origin/main`, and push `main`.

**Step 4: Deploy through SSH**

On the server: fetch/pull the pushed SHA, run the guarded product-catalog adoption command during maintenance, `migrate`, `check`, `collectstatic --noinput`, `compress --force`, and `touch tmp/restart.txt`. Verify deployed SHA, schema/table counts, ContentTypes/permissions, old/new route behavior, staff editor/catalog, public PDP/cart/checkout, and indexing audit states.

**Step 5: Record evidence**

Report exact commit SHA, pushed branch, deploy SHA, migration/adoption report, test counts, browser screenshots, and any residual non-runtime historical references.
