# Manual Order Garment Fit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Preserve classic, oversize, and thermo garment routing from manual-order entry through order editing, Nova Poshta quantity description, and warehouse write-off.

**Architecture:** Reuse `OrderItem.fit_option_*`, ProductCatalog variant rules, `ColorProfile.is_thermo`, and `VariantBlankLink`. Enrich the existing admin JSON payload and both JavaScript editors, validate posted color+fit server-side, and provide a safe management command for production warehouse-link backfill.

**Tech Stack:** Django 5, Django ORM, server-rendered templates with vanilla JavaScript, Django `TestCase`, MariaDB production.

---

### Task 1: Build Fit-Aware Product Payload

**Files:**
- Modify: `twocomms/storefront/views/manual_orders.py`
- Test: `twocomms/storefront/tests/test_manual_orders.py`

1. Add failing tests that product JSON includes active fits, fit-specific sizes, variant allowed fits, thermo flag, and fit-specific price.
2. Run the focused tests and confirm the new assertions fail.
3. Add payload helpers using ProductCatalog public services and size-grid comparison data.
4. Run the focused tests and confirm they pass.

### Task 2: Validate and Persist Fit on Create and Edit

**Files:**
- Modify: `twocomms/storefront/views/manual_orders.py`
- Test: `twocomms/storefront/tests/test_manual_orders.py`
- Test: `twocomms/storefront/tests/test_order_edit_view.py`

1. Add failing tests for two same-size classic/oversize lines, edit-data fit serialization, edit round-trip, and invalid variant-fit rejection.
2. Run the focused tests and verify the expected fit assertions fail.
3. Serialize `fit_option_code`/`fit_option_label` and validate the selected fit against the variant rules.
4. Run the focused tests and confirm they pass.

### Task 3: Add Fit Controls to Manual Create and Edit UI

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/pages/admin_manual_order.html`
- Modify: `twocomms/twocomms_django_theme/templates/partials/admin_orders_section.html`
- Test: `twocomms/storefront/tests/test_manual_orders.py`
- Test: `twocomms/storefront/tests/test_order_edit_view.py`

1. Add failing render assertions for fit selectors, thermo markers, and fit values in submitted payload construction.
2. Run the render tests and confirm failure.
3. Add compact fit selectors to both item editors, normalize fit/size/price on color or fit changes, and submit `fit_option_code`.
4. Run render and backend tests and confirm success.

### Task 4: Backfill Variant-to-Warehouse Links

**Files:**
- Create: `twocomms/product_catalog/management/commands/backfill_tshirt_blank_links.py`
- Create: `twocomms/product_catalog/tests/test_backfill_tshirt_blank_links.py`

1. Add failing command tests covering dry-run, classic/oversize/thermo mapping, disabled fits, existing-link preservation, and idempotency.
2. Run the command tests and confirm the command is missing.
3. Implement explicit slug-based mapping with `--apply` and optional product scope.
4. Run command tests and confirm success.

### Task 5: Verify Warehouse Matching and Nova Poshta Quantity

**Files:**
- Modify: `twocomms/warehouse/tests/test_write_off.py`
- Modify: `twocomms/storefront/tests/test_nova_poshta_delivery.py`
- Modify only if tests expose a defect: `twocomms/warehouse/services/matching.py`

1. Add failing or characterization tests for classic, oversize, and thermo linked candidates.
2. Add a regression test proving two fit-separated items produce a Nova Poshta description with quantity two.
3. Run the focused tests and fix only demonstrated defects.
4. Re-run both suites.

### Task 6: Full Verification and Production Data Apply

**Files:**
- No new production files expected.

1. Run `git diff --check` and `python manage.py check`.
2. Run manual order, edit, warehouse, ProductCatalog, Nova Poshta, and Telegram order-action regressions.
3. Run `makemigrations --check --dry-run` and compilation checks.
4. Commit and push the feature branch and `main` after rebasing on current `origin/main`.
5. Deploy with fast-forward pull, migrations check, `collectstatic`, `compress`, `check`, and Passenger restart.
6. Run the backfill command first in dry-run, inspect counts and mapping, then run with `--apply`.
7. Verify production mapping counts, representative classic/oversize/thermo candidates, deployed SHA, and anonymous staff-route protection without creating TTNs or changing stock.
