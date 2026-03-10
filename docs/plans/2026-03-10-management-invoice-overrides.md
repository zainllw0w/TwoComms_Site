# Management Invoice Overrides Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add per-item manual price override and extra description to management invoices while keeping totals server-validated and improving Excel readability.

**Architecture:** Keep `WholesaleInvoice.order_details` as the storage contract, but normalize every invoice item on the server before saving or exporting. The UI sends pricing mode, optional manual price, and extra description; the backend recalculates base tier prices from basket totals, applies optional overrides, and generates Excel from normalized rows only.

**Tech Stack:** Django, openpyxl, vanilla JavaScript, Django TestCase

---

### Task 1: Add failing tests for item normalization

**Files:**
- Create: `twocomms/management/test_invoices.py`

**Step 1: Write the failing test**

Add a test for a mixed basket where:
- auto-priced T-shirts get the recalculated tier price from the total T-shirt quantity
- manual-priced items keep the override
- extra description is appended in square brackets only when present

**Step 2: Run test to verify it fails**

Run: `SECRET_KEY=test DEBUG=1 python twocomms/manage.py test management.test_invoices.InvoiceItemNormalizationTests -v 2`
Expected: FAIL because the normalization service does not exist yet.

**Step 3: Write minimal implementation**

Create a normalization service that validates incoming rows, recalculates base prices per product type, applies overrides, and returns normalized rows plus totals.

**Step 4: Run test to verify it passes**

Run: `SECRET_KEY=test DEBUG=1 python twocomms/manage.py test management.test_invoices.InvoiceItemNormalizationTests -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add docs/plans/2026-03-10-management-invoice-overrides.md twocomms/management/test_invoices.py twocomms/management/invoice_service.py
git commit -m "test: cover management invoice item normalization"
```

### Task 2: Add failing tests for invoice generation and Excel output

**Files:**
- Modify: `twocomms/management/test_invoices.py`
- Modify: `twocomms/management/views.py`

**Step 1: Write the failing test**

Add an API test for `/invoices/api/generate/` that asserts:
- normalized items are saved into `WholesaleInvoice.order_details`
- totals are recomputed on the server
- generated Excel contains wrapped title cells, numeric currency cells, and the extra description in the product title

**Step 2: Run test to verify it fails**

Run: `SECRET_KEY=test DEBUG=1 python twocomms/manage.py test management.test_invoices.ManagementInvoiceApiTests -v 2`
Expected: FAIL because the endpoint still trusts raw payload and writes plain string currency cells.

**Step 3: Write minimal implementation**

Update the invoice generation view to call the normalization service and build the workbook from normalized rows with improved formatting.

**Step 4: Run test to verify it passes**

Run: `SECRET_KEY=test DEBUG=1 python twocomms/manage.py test management.test_invoices.ManagementInvoiceApiTests -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add twocomms/management/test_invoices.py twocomms/management/views.py
git commit -m "feat: normalize management invoice export data"
```

### Task 3: Add failing test for downstream invoice summary consumption

**Files:**
- Modify: `twocomms/management/test_invoices.py`
- Modify: `twocomms/management/shop_views.py`

**Step 1: Write the failing test**

Add a test for `_invoice_summary_from_wholesale_invoice()` that prefers normalized item fields such as final display title and recomputed totals.

**Step 2: Run test to verify it fails**

Run: `SECRET_KEY=test DEBUG=1 python twocomms/manage.py test management.test_invoices.InvoiceSummaryTests -v 2`
Expected: FAIL because the summary reader still consumes only legacy raw keys.

**Step 3: Write minimal implementation**

Teach the summary helper to read normalized keys first and fall back to legacy payload keys.

**Step 4: Run test to verify it passes**

Run: `SECRET_KEY=test DEBUG=1 python twocomms/manage.py test management.test_invoices.InvoiceSummaryTests -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add twocomms/management/test_invoices.py twocomms/management/shop_views.py
git commit -m "feat: use normalized invoice rows in shop summaries"
```

### Task 4: Wire the UI for manual price and extra description

**Files:**
- Modify: `twocomms/management/templates/management/invoices.html`

**Step 1: Write the failing test**

Use the backend API tests as the protection layer; there is no current frontend test harness in this area.

**Step 2: Run test to verify it fails**

Run: `SECRET_KEY=test DEBUG=1 python twocomms/manage.py test management.test_invoices -v 2`
Expected: Existing backend tests pass, manual browser verification still pending.

**Step 3: Write minimal implementation**

Update the order form to support:
- auto vs manual pricing toggle
- editable manual price input
- extra description field
- order item cards that display pricing mode and the appended title

**Step 4: Run test to verify it passes**

Run: `SECRET_KEY=test DEBUG=1 python twocomms/manage.py test management.test_invoices -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add twocomms/management/templates/management/invoices.html
git commit -m "feat: add manual invoice pricing controls"
```

### Task 5: Verify, commit, push, and deploy

**Files:**
- Modify: `twocomms/management/views.py`
- Modify: `twocomms/management/shop_views.py`
- Modify: `twocomms/management/templates/management/invoices.html`
- Modify: `twocomms/management/test_invoices.py`
- Create: `twocomms/management/invoice_service.py`

**Step 1: Run the full focused verification**

Run: `SECRET_KEY=test DEBUG=1 python twocomms/manage.py test management.test_invoices -v 2`
Expected: PASS

**Step 2: Inspect git diff**

Run: `git diff -- twocomms/management/invoice_service.py twocomms/management/views.py twocomms/management/shop_views.py twocomms/management/templates/management/invoices.html twocomms/management/test_invoices.py docs/plans/2026-03-10-management-invoice-overrides.md`
Expected: Only intended invoice-related changes

**Step 3: Commit**

```bash
git add docs/plans/2026-03-10-management-invoice-overrides.md twocomms/management/invoice_service.py twocomms/management/views.py twocomms/management/shop_views.py twocomms/management/templates/management/invoices.html twocomms/management/test_invoices.py
git commit -m "feat: add manual pricing for management invoices"
```

**Step 4: Push**

```bash
git push origin HEAD
```

**Step 5: Deploy**

```bash
sshpass -p 'trs5m4t1' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && git pull'"
```
