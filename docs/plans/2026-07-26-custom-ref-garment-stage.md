# Custom Ref Garment Stage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the procedural Custom Print 3D garment with the supplied `CUSTOM_REF` AVIF/WebP renders while preserving the configurator behavior and making the stage stable across browsers and viewports.

**Architecture:** Convert the reference PNGs into AVIF/WebP static assets, expose a small manifest/lookup module for deterministic resolution, and render the resolved image in the existing stage container. The configurator keeps ownership of state, zones, side, and color; the stage module only resolves and displays the correct asset with safe fallbacks.

**Tech Stack:** Django templates, vanilla ES modules, static assets, Node syntax tests, Python/Django tests, Playwright.

---

### Task 1: Prepare static reference assets

**Files:**
- Create: `twocomms/twocomms_django_theme/static/img/configurator/custom-ref/*.avif`
- Create: `twocomms/twocomms_django_theme/static/img/configurator/custom-ref/*.webp`

**Steps:**
1. Confirm the source PNG dimensions and transparency.
2. Convert each source once with quality-preserving settings.
3. Verify every output can be decoded and has non-zero dimensions.

### Task 2: Add deterministic asset manifest and stage renderer

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/js/custom-print-3d-viewer.js`
- Create: `twocomms/twocomms_django_theme/static/js/custom-print-garment-stage.js`
- Modify: `twocomms/twocomms_django_theme/templates/pages/custom_print.html`

**Steps:**
1. Define normalized aliases and explicit asset records for all supplied references.
2. Implement front/back and color fallback resolution.
3. Render a `<picture>` with AVIF and WebP sources inside the existing stage frame.
4. Preserve the public `create({ getState })` API so the configurator integration remains narrow.
5. Remove the procedural viewer initialization from the page path.

### Task 3: Make stage layout stable and accessible

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/css/custom-print-configurator.css`
- Modify: `twocomms/twocomms_django_theme/static/js/custom-print-configurator.js`

**Steps:**
1. Add a fixed responsive aspect-ratio image layer with centered containment.
2. Keep overlays and receipt positioning anchored to the stage frame.
3. Add reduced-motion handling and accessible alt text reflecting garment, color, and side.
4. Ensure a state change swaps the image without layout shift.

### Task 4: Add focused contract tests

**Files:**
- Create: `tests/test_custom_print_ref_stage_contract.py`

**Steps:**
1. Assert all supported source mappings and expected output paths.
2. Assert invalid/missing colors and sides resolve to black fallbacks.
3. Assert the template loads the stage renderer and no longer initializes the procedural viewer.

### Task 5: Verify and ship

**Steps:**
1. Run focused Node/Python/Django checks.
2. Run browser checks for zones, front/back, colors, mobile and desktop layout.
3. Review the diff and stage only task-scoped files.
4. Commit, push, pull on the production server with the supplied SSH command, collect deployed-SHA and HTTP evidence.
