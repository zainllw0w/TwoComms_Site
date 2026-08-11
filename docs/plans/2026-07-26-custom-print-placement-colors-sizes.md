# Custom Print Placement, Colors and Size Guides Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ambiguous Custom Print placement rules with typed zones, honest render fallbacks, a complete design-service card, and independent classic/oversize T-shirt size guides.

**Architecture:** Django emits the canonical placement, format, palette, render-fallback, artwork-service and size-guide contracts. The vanilla JavaScript configurator normalizes drafts against those contracts and expands enabled options into stable placement specs consumed by preview, uploads, validation, summaries and submission. The server repeats normalization before persistence and notification so malformed or legacy client state cannot produce impossible placements.

**Tech Stack:** Django/Python, Django templates, vanilla JavaScript, CSS, Node test runner, Python unittest/Django TestCase, Playwright, AVIF/WebP render assets.

**Approved design:** `docs/plans/2026-07-26-custom-print-zones-colors-sizes-design.md`

---

## File map

- `twocomms/storefront/custom_print_config.py`: canonical formats, placement schemas, colors, preview fallback, snapshot normalization and placement expansion.
- `twocomms/twocomms_django_theme/templates/pages/custom_print.html`: specialized zone editors, preview fallback notice, artwork layout and size-guide dialog markup.
- `twocomms/twocomms_django_theme/static/js/custom-print-configurator.js`: state transitions, zone controls, upload slots, stage side switching, summaries and payload.
- `twocomms/twocomms_django_theme/static/js/custom-print-preview.js`: pure preview asset/fallback and placement geometry helpers.
- `twocomms/twocomms_django_theme/static/css/custom-print-guided-studio.css`: responsive specialized controls, stage markers, design service and size-guide dialog.
- `twocomms/storefront/custom_print_notifications.py`: manager-facing placement, color fallback and artwork package rendering.
- `twocomms/storefront/views/static_pages.py`: expose canonical T-shirt guide data and preserve structured snapshot fields.
- `tests/test_custom_print_config_contract.py`: server config and normalization contracts.
- `tests/custom-print-preview.test.cjs`: pure preview/fallback/geometry tests.
- `tests/test_custom_print_guided_studio_source.py`: template/JS/CSS integration contracts.
- `tests/test_custom_print_notifications_unit.py`: Telegram summary contracts.
- `twocomms/storefront/tests/test_custom_print.py`: Django page and submission integration.

## Shared verification commands

Run from `/Users/zainllw0w/TwoComms/site` unless a command contains an explicit `cd`.

```bash
.venv/bin/python -m unittest \
  tests.test_custom_print_config_contract \
  tests.test_custom_print_guided_studio_source \
  tests.test_custom_print_notifications_unit
node --test tests/custom-print-preview.test.cjs tests/custom-print-mobile-shell.test.cjs tests/custom-print-submission-policy.test.cjs
node --check twocomms/twocomms_django_theme/static/js/custom-print-configurator.js
cd twocomms && SECRET_KEY=test_local_secret ../.venv/bin/python manage.py test storefront.tests.test_custom_print --keepdb
cd twocomms && SECRET_KEY=test_local_secret ../.venv/bin/python manage.py check
git diff --check
```

Expected: all selected tests pass, JavaScript syntax check is silent, Django reports no issues, and `git diff --check` is silent. Existing unrelated failures must be recorded with exact evidence and must not be hidden by broad retries.

## Production checkpoint protocol

Every task marked **ship checkpoint** ends with this exact sequence:

1. Re-run the task's focused tests plus all shared checks affected by the diff.
2. Confirm `git status --short`, `git diff --cached --name-only`, and `git diff --cached --check`; stage only listed task files.
3. Commit and push `main`. Never store the SSH credential in a file, command transcript, plan, commit message or environment persisted beyond the current process.
4. On production, use an ephemeral credential to run `git pull --ff-only`, `collectstatic --no-input`, `compress --force`, `manage.py check`, and touch `tmp/restart.txt`.
5. Verify deployed SHA equals the pushed SHA.
6. Verify `/custom-print/`, `/ru/custom-print/`, `/en/custom-print/` return 200.
7. Use Playwright at 1440x1000, 390x844 and 320x740. Check the changed path, `scrollWidth <= clientWidth`, no blocking console errors, no duplicate dialogs/handlers, and correct focus restoration.
8. Only then mark the task complete and start the next task.

---

### Task 1: Canonical typed placement contracts

**Ship checkpoint:** yes

**Files:**
- Modify: `twocomms/storefront/custom_print_config.py`
- Modify: `tests/test_custom_print_config_contract.py`
- Modify: `twocomms/storefront/tests/test_custom_print.py`

- [ ] **Step 1: Write failing tests for formats and typed placement expansion**

Add assertions equivalent to:

```python
self.assertEqual([item["value"] for item in config["back_size_presets"]], ["A4", "A3", "A3+"])
self.assertEqual(config["special_placements"]["shoulder"]["formats"], ["A6"])
self.assertEqual(config["special_placements"]["hem"]["modes"], ["text", "A6", "A6+"])

specs = build_placement_specs({
    "product": {"type": "tshirt", "fit": "regular"},
    "print": {
        "zones": ["front", "shoulder", "hem"],
        "zone_options": {
            "front": {"size_preset": "A4"},
            "shoulder": {"left_enabled": True, "right_enabled": True},
            "hem": {"enabled": True, "side": "back", "mode": "A6+"},
        },
    },
})
self.assertEqual([item["placement_key"] for item in specs], ["front", "shoulder_left", "shoulder_right", "hem_back"])
self.assertTrue(specs[-1]["requires_artwork_file"])
```

Also test `hem` text mode produces `requires_artwork_file=False`, preserves text, and rejects an empty side.

- [ ] **Step 2: Run focused tests and confirm failure**

```bash
.venv/bin/python -m unittest tests.test_custom_print_config_contract
cd twocomms && SECRET_KEY=test_local_secret ../.venv/bin/python manage.py test storefront.tests.test_custom_print.CustomPrintPageTests.test_custom_print_config_exposes_progress_steps_tshirt_rules_and_zone_presets --keepdb
```

Expected: failures reference missing `A3+` and `special_placements`.

- [ ] **Step 3: Define canonical formats and placement schemas**

In `custom_print_config.py`:

```python
FORMAT_DIMENSIONS["A3+"] = {"width_mm": 350, "height_mm": 500}
FORMAT_DIMENSIONS["A6+"] = {"width_mm": 210, "height_mm": 105}

BACK_SIZE_PRESETS = [
    {"value": "A4", ...},
    {"value": "A3", ...},
    {"value": "A3+", "label": "A3+", "stage_scale": 0.86, "price_delta": 100, "range_label": _("більше A3, менше A2")},
]

SPECIAL_PLACEMENTS = {
    "shoulder": {"formats": ["A6"], "sides": ["left", "right"]},
    "hem": {"modes": ["text", "A6", "A6+"], "sides": ["front", "back"]},
}
```

Expose deep copies through `build_custom_print_config`. Add `shoulder`, `shoulder_left`, `shoulder_right`, `hem`, `hem_front`, and `hem_back` to `ZONE_LABELS`. Do not add shoulder or hem to products that cannot physically support them; start with T-shirts and reconcile hoodie/longsleeve availability against existing profile anchors.

- [ ] **Step 4: Normalize legacy and invalid states server-side**

Implement these explicit rules in `normalize_custom_print_snapshot`:

```python
if back_options.get("size_preset") == "A2":
    back_options["size_preset"] = "A3+"

shoulder["left_enabled"] = bool(shoulder.get("left_enabled"))
shoulder["right_enabled"] = bool(shoulder.get("right_enabled"))

hem["side"] = hem.get("side") if hem.get("side") in {"front", "back"} else ""
hem["mode"] = hem.get("mode") if hem.get("mode") in {"text", "A6", "A6+"} else "A6"
hem["text"] = str(hem.get("text") or "")[:120] if hem["mode"] == "text" else ""
```

Remove legacy `custom.size_preset` from newly normalized state. Preserve `custom.location/note` only as free placement description. Expand specialized placements in `build_placement_specs` with stable keys and file requirements.

- [ ] **Step 5: Run focused and related tests**

Run Task 1 tests plus `tests.test_custom_print_form_logic` and the full Django Custom Print test module. Expected: PASS; legacy A2 expectations must be deliberately updated to A3+.

- [ ] **Step 6: Commit, push, deploy and live-check config contract**

Commit message: `feat: define typed custom print placements`. Follow the production checkpoint protocol. Live-check that the existing UI still loads and old local draft opens without an exception before UI controls are introduced.

---

### Task 2: Specialized zone UI, uploads and synchronized preview

**Ship checkpoint:** yes

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/pages/custom_print.html`
- Modify: `twocomms/twocomms_django_theme/static/js/custom-print-configurator.js`
- Modify: `twocomms/twocomms_django_theme/static/js/custom-print-preview.js`
- Modify: `twocomms/twocomms_django_theme/static/css/custom-print-guided-studio.css`
- Modify: `tests/custom-print-preview.test.cjs`
- Modify: `tests/test_custom_print_guided_studio_source.py`

- [ ] **Step 1: Write failing pure JS tests**

Export/test helpers that resolve view and geometry:

```javascript
assert.equal(viewForPlacement({ placement_key: "hem_back" }), "back");
assert.equal(viewForPlacement({ placement_key: "shoulder_left" }), "front");
assert.deepEqual(requirementsForPlacement({ zone: "hem", mode: "text" }), { requiresFile: false });
assert.ok(boxForFormat("A3+").scale > boxForFormat("A3").scale);
assert.ok(boxForFormat("A3+").scale < 0.92);
```

Add source-contract tests for independent shoulder buttons, hem side/mode controls, a hem text field, and removal of generic custom size buttons.

- [ ] **Step 2: Run tests and confirm failure**

```bash
node --test tests/custom-print-preview.test.cjs
.venv/bin/python -m unittest tests.test_custom_print_guided_studio_source
```

- [ ] **Step 3: Add specialized markup and state normalization**

Add dedicated containers in the placement step:

```html
<section data-shoulder-options hidden>...</section>
<section data-hem-options hidden>...</section>
<section data-custom-zone-options hidden>...</section>
```

Use buttons with `aria-pressed` for shoulder sides, a segmented control for hem front/back, and mode buttons for Text/A6/A6+. Keep arbitrary `custom` as an on/off block with one note field.

In JS add `ensureShoulderOptions()`, `ensureHemOptions()`, `renderShoulderControls()`, and `renderHemControls()`. Reuse the proven sleeve pattern for independent sides, but keep shoulder mode fixed to A6.

- [ ] **Step 4: Expand upload slots and clean disabled state**

Update `getExpandedPlacements()` and client `buildPlacementSpecs()` so keys exactly match the server. When a placement is disabled or changes to text mode, call `deletePlacementFiles(key)` before rendering and clear validation messages for that key.

- [ ] **Step 5: Synchronize preview side and markers**

Set `STATE.ui.stage_view` from the selected placement before calling the render cycle. Add side-edge shoulder markers with leader lines and lower-edge hem markers. Do not draw a precise box for arbitrary `custom`. Keep desktop stage and mobile dialog bound to the same state.

- [ ] **Step 6: Style responsive controls**

Use two-column shoulder toggles on desktop and narrow mobile where labels fit, stable min-heights, and one-column editors below 480px. Ensure marker dimensions use percentages within the existing stable canvas, never viewport-based font scaling.

- [ ] **Step 7: Run JS, source, syntax and Django tests**

Run all shared verification commands. Expected: placement count, upload requirements and preview side pass for front/back/shoulder/hem/custom.

- [ ] **Step 8: Commit, push, deploy and browser-test zones**

Commit message: `feat: add precise custom print zone controls`. In Playwright verify both shoulders, hem front/back and each hem mode; open/close the mobile eye dialog at least five times and confirm one dialog, one handler effect, restored focus and no overflow.

---

### Task 3: Color palettes and honest render fallback

**Ship checkpoint:** yes

**Files:**
- Modify: `twocomms/storefront/custom_print_config.py`
- Modify: `twocomms/twocomms_django_theme/templates/pages/custom_print.html`
- Modify: `twocomms/twocomms_django_theme/static/js/custom-print-preview.js`
- Modify: `twocomms/twocomms_django_theme/static/js/custom-print-configurator.js`
- Modify: `twocomms/twocomms_django_theme/static/css/custom-print-guided-studio.css`
- Modify: `twocomms/storefront/custom_print_notifications.py`
- Modify: `tests/test_custom_print_config_contract.py`
- Modify: `tests/custom-print-preview.test.cjs`
- Modify: `tests/test_custom_print_notifications_unit.py`

- [ ] **Step 1: Write failing palette and fallback tests**

Assert regular T-shirt canonical values are exactly `black`, `milk`, `coyote`, `khaki`, `pink`; oversize remains its current palette. Assert hoodie regular includes black, light canonical value, khaki and pink without duplicate slugs.

Add JS cases:

```javascript
assert.deepEqual(resolveGarmentRender(assets, "tshirt:regular", "khaki"), {
  selectedColor: "khaki",
  previewColor: "white",
  fallbackUsed: true,
  sources: assets["tshirt:regular"].white,
});
```

Also test selected state remains khaki after resolving fallback.

- [ ] **Step 2: Run tests and confirm failure**

Run config, preview and notification unit tests.

- [ ] **Step 3: Define palettes and render metadata**

Add canonical hex values after checking existing product/color slugs. Add white regular T-shirt render mapping if the prepared asset exists; otherwise create a declared neutral fallback chain that reports its actual base rather than claiming white. Never recolor the PNG/AVIF with CSS filters.

- [ ] **Step 4: Render fallback notice without mutating product color**

Store preview metadata under `STATE.ui.preview_render`, not `STATE.product.color`. Render one compact live region near the stage and one line in the final receipt only when `fallback_used` is true.

- [ ] **Step 5: Persist and notify manager**

Include preview metadata in the normalized snapshot. Add manager rows for selected order color and displayed preview base. Preserve these fields in safe-exit, add-to-cart and direct lead flows.

- [ ] **Step 6: Run focused and integration tests**

Run all shared commands plus submission form logic. Expected: selected and preview colors remain separate through client snapshot, server normalization and Telegram formatting.

- [ ] **Step 7: Commit, push, deploy and live-check fallback**

Commit message: `feat: show honest custom print color fallbacks`. Browser-test every available regular/oversize T-shirt and hoodie color. Network-check AVIF primary and WebP fallback return 200.

---

### Task 4: Complete artwork development package

**Ship checkpoint:** yes

**Files:**
- Modify: `twocomms/storefront/custom_print_config.py`
- Modify: `twocomms/twocomms_django_theme/static/js/custom-print-configurator.js`
- Modify: `twocomms/twocomms_django_theme/static/css/custom-print-guided-studio.css`
- Modify: `twocomms/storefront/custom_print_notifications.py`
- Modify: `tests/test_custom_print_config_contract.py`
- Modify: `tests/test_custom_print_guided_studio_source.py`
- Modify: `tests/test_custom_print_notifications_unit.py`

- [ ] **Step 1: Write failing structured-service tests**

Assert the `design` service exposes these stable feature keys:

```python
["full_design", "idea_development", "two_revisions", "approval_mockup"]
```

Assert Telegram includes all four localized labels when design is selected and excludes them for ready/adjust.

- [ ] **Step 2: Run focused tests and confirm failure**

- [ ] **Step 3: Add structured service data and UI**

Extend only the `design` config item with `features`. Render first two service cards in the two-column grid and apply `grid-column: 1 / -1` to design. Use a compact feature list with check icons; do not nest another card.

- [ ] **Step 4: Persist package features**

Snapshot selected service value plus a server-resolved list of feature keys. Do not trust arbitrary client feature labels. Format the manager summary from canonical config.

- [ ] **Step 5: Run tests and visual checks**

Verify 1440px has two normal cards plus one full-width card, and 390/320px has a single column with no text clipping.

- [ ] **Step 6: Commit, push, deploy and live-check**

Commit message: `feat: explain full custom print design service`. Follow the production checkpoint protocol.

---

### Task 5: Independent classic and oversize T-shirt size guides

**Ship checkpoint:** yes

**Files:**
- Modify: `twocomms/storefront/views/static_pages.py`
- Modify: `twocomms/twocomms_django_theme/templates/pages/custom_print.html`
- Modify: `twocomms/twocomms_django_theme/static/js/custom-print-configurator.js`
- Modify: `twocomms/twocomms_django_theme/static/js/custom-print-mobile-shell.js` if shared dialog focus helpers require extension
- Modify: `twocomms/twocomms_django_theme/static/css/custom-print-guided-studio.css`
- Modify: `twocomms/storefront/tests/test_custom_print.py`
- Modify: `tests/test_custom_print_guided_studio_source.py`
- Modify: `tests/custom-print-mobile-shell.test.cjs`

- [ ] **Step 1: Write failing context and independence tests**

Assert the Custom Print page exposes classic and oversize guide blocks with canonical image URL, `guide_data` rows and localized labels. Add a JS test proving changing `guide_view_fit` does not modify `STATE.product.fit`, size breakdown or price.

- [ ] **Step 2: Run tests and confirm failure**

- [ ] **Step 3: Reuse canonical guide service**

In `static_pages.py`, use the existing ProductCatalog size-guide service to resolve the two canonical T-shirt profiles. Do not query or assign per-product grids and do not copy media. Expose a minimal serializable payload containing fit, title, image URL, alt and structured rows.

- [ ] **Step 4: Replace manager size mode for T-shirts**

Keep actual order size modes `single` and `mixed`. For T-shirts replace the manager card with a `Розмірна сітка` command button. Hoodie, longsleeve and customer-garment behavior remains unchanged unless their current flow already excludes that mode.

- [ ] **Step 5: Implement accessible guide dialog**

Add a native dialog or existing project dialog component with tab semantics, image, HTML table and close button. On open, set `guide_view_fit` to current T-shirt fit. Tab selection only changes dialog view. On close, restore focus and remove scroll lock.

- [ ] **Step 6: Style for compact responsive reading**

Use an unframed dialog section, restrained tab control, responsive image aspect ratio, semantic table and an internal scroll container only where needed. Page `scrollWidth` must remain unchanged.

- [ ] **Step 7: Run full size-guide and Custom Print regression**

Run shared checks plus existing ProductCatalog size-guide tests. Expected: guide switching is independent from purchasable fit in both PDP and Custom Print.

- [ ] **Step 8: Commit, push, deploy and browser-test guides**

Commit message: `feat: add custom print tshirt size guides`. Verify classic-first and oversize-first flows, switching both tabs, Escape/close/focus, image 200, table content, and no order-state mutation.

---

### Task 6: Draft normalization, final regression and production hardening

**Ship checkpoint:** yes

**Files:**
- Modify as justified by failing evidence only: files changed in Tasks 1–5
- Modify: `tests/test_custom_print_config_contract.py`
- Modify: `tests/custom-print-preview.test.cjs`
- Modify: `twocomms/storefront/tests/test_custom_print.py`
- Modify: `docs/plans/2026-07-26-custom-print-placement-colors-sizes.md` to mark verified checklist items

- [ ] **Step 1: Add regression fixtures for old drafts**

Cover legacy A2 back, custom shoulder/hem locations, stale upload entries, missing fit/fabric after restore, and unknown colors. Expected normalization: A2 becomes A3+, recognizable custom shoulder/hem becomes specialized state where unambiguous, arbitrary custom remains described, and invalid file requirements are removed.

- [ ] **Step 2: Reproduce and fix saved-draft visual/state mismatch**

Use a localStorage fixture where regular fit is visible but required fields are incomplete. Assert normalized state and rendered active controls agree before allowing navigation. Make the smallest state-normalization fix supported by the failing test.

- [ ] **Step 3: Audit analytics 400 without expanding scope**

Capture the failing `/api/track-event/` request seen during read-only production inspection. If the Custom Print payload violates the current endpoint contract, add a focused test and correct it. If the 400 is caused by unrelated environment/session policy, document evidence and keep it outside this feature rather than masking it.

- [ ] **Step 4: Run the full verification matrix**

Run all shared commands, related ProductCatalog guide tests, form logic, pricing source, ref-stage contract and notification transport tests. Run `makemigrations --check --dry-run`; expected: no migrations.

- [ ] **Step 5: Perform local browser acceptance**

Start the local server on an unused port. Exercise UA/RU/EN at desktop, tablet, 390px and 320px. Cover every product/fit/color, front/back/A3+, both shoulders, hem modes/sides, arbitrary zone, artwork packages, upload removal, size guides, draft reload, back navigation, safe exit and preview dialog repetition. Do not submit a production lead.

- [ ] **Step 6: Run final code review and resolve findings**

Review the entire diff for state divergence, unsupported server combinations, stale files, inaccessible controls, untranslated copy, duplicate canonical color slugs, asset 404s and unrelated changes. Fix only evidenced findings and rerun the affected tests.

- [ ] **Step 7: Final commit, push, deploy and live acceptance**

Commit message: `test: harden custom print placement flow`. Deploy and verify exact SHA. Repeat the local acceptance subset on production without creating a lead. Confirm routes and render assets return 200, no horizontal overflow, no blocking console errors, and all earlier production checkpoints remain functional.

- [ ] **Step 8: Close the plan**

Mark each verified checkbox, record commit SHAs and production SHA without credentials, and report any genuinely residual limitation. Do not mark completion until every required task is deployed and live-verified.
