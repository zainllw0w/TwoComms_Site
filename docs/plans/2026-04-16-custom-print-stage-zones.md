# Custom Print Stage/Zones Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the lobby first step full-width, add richer front/back/sleeve sizing controls with correct stage rendering, extend T-shirt fit/fabric rules, and keep the `custom-print` payload backward-compatible.

**Architecture:** Keep the current Django template + config JSON + plain JS architecture, but normalize zone-specific options into one richer `zone_options` contract. Render the new UX from config instead of hardcoding scattered conditionals so pricing, stage layout, and payload serialization stay aligned.

**Tech Stack:** Django templates, Python config builder, vanilla JavaScript configurator, CSS, Django/unittest tests

---

### Task 1: Document the approved design

**Files:**
- Create: `docs/plans/2026-04-16-custom-print-stage-zones-design.md`
- Create: `docs/plans/2026-04-16-custom-print-stage-zones.md`

**Step 1: Verify both docs exist**

Run: `ls docs/plans/2026-04-16-custom-print-stage-zones-design.md docs/plans/2026-04-16-custom-print-stage-zones.md`
Expected: both files printed

**Step 2: Commit the docs**

Run:
```bash
git add docs/plans/2026-04-16-custom-print-stage-zones-design.md docs/plans/2026-04-16-custom-print-stage-zones.md
git commit -m "docs: capture custom print stage and zones plan"
```

### Task 2: Extend config contract

**Files:**
- Modify: `twocomms/storefront/custom_print_config.py`
- Test: `tests/test_custom_print_config_contract.py`

**Step 1: Write/extend failing contract tests**

Cover:
- T-shirt fits now include `regular` and `oversize`
- T-shirt fabrics now include `premium` and `thermo`
- `thermo` carries `+500`
- back size presets include `A4/A3/A2`
- sleeve side options normalize correctly

**Step 2: Run the contract suite and confirm failure**

Run: `PYTHONPATH=twocomms ./.venv/bin/python -m unittest tests.test_custom_print_config_contract`
Expected: failing assertions for the new config contract

**Step 3: Implement the minimal config changes**

Add:
- richer preset constants
- T-shirt fit/fabric pricing
- sleeve-side normalization
- updated placement-spec serialization support

**Step 4: Run the contract suite again**

Run: `PYTHONPATH=twocomms ./.venv/bin/python -m unittest tests.test_custom_print_config_contract`
Expected: `OK`

### Task 3: Update template structure

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/pages/custom_print.html`

**Step 1: Add the missing UI hooks**

Add markup for:
- full-width lobby mode container treatment
- back-size controls
- sleeve-left/sleeve-right controls
- sleeve text inputs

**Step 2: Keep server-rendered page backward-compatible**

Preserve existing `data-*` hooks that other JS paths still expect.

### Task 4: Rework client state and stage rendering

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/js/custom-print-configurator.js`

**Step 1: Write/adjust JS-facing server tests first where possible**

Use Python tests for snapshot/build payload expectations before changing JS serialization logic.

**Step 2: Implement state normalization**

Add support for:
- `back.size_preset`
- `sleeve_left` and `sleeve_right`
- sleeve mode `a6` vs `full_text`
- sleeve text payload

**Step 3: Implement stage overlay changes**

Render:
- full-width mode after lobby
- vertical back plate
- left/right sleeve plates
- scene badges for back and sleeve settings

**Step 4: Implement pricing + summary changes**

Ensure:
- second sleeve counts as another zone
- T-shirt thermo delta is included
- fabric chips show visible price modifiers

**Step 5: Re-run JS syntax check**

Run: `node --check twocomms/twocomms_django_theme/static/js/custom-print-configurator.js`
Expected: exit code `0`

### Task 5: Adjust CSS for lobby and new controls

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/css/custom-print-configurator.css`

**Step 1: Make lobby step full-width**

Ensure `cp-step--mode` spans the full waterfall width in lobby mode.

**Step 2: Style new controls**

Add styles for:
- back-size row
- sleeve-side cards
- inline price badges on fabrics
- sleeve text fields
- vertical stage plates

### Task 6: Update Django tests

**Files:**
- Modify: `twocomms/storefront/tests/test_custom_print.py`
- Modify: `tests/test_custom_print_config_contract.py`

**Step 1: Extend page/config assertions**

Verify new JSON keys and page strings are present.

**Step 2: Extend normalization/placement tests**

Verify:
- back sizes persist
- sleeve side options persist
- legacy drafts still normalize safely

### Task 7: Run verification

**Files:**
- No code changes

**Step 1: Check migrations**

Run: `DEBUG=1 ./.venv/bin/python twocomms/manage.py makemigrations --check --dry-run`
Expected: `No changes detected`

**Step 2: Run contract tests**

Run: `PYTHONPATH=twocomms ./.venv/bin/python -m unittest tests.test_custom_print_config_contract`
Expected: `OK`

**Step 3: Run targeted Django test if possible**

Run: `DEBUG=1 ./.venv/bin/python twocomms/manage.py test storefront.tests.test_custom_print`
Expected: either pass or known unrelated project-level failure recorded honestly

**Step 4: Run browser validation**

Verify:
- first step is full-width
- back presets appear only on zones step
- sleeve left/right controls work
- thermo pricing appears for T-shirt
- stage overlays are vertical and aligned

### Task 8: Finish branch and deploy

**Files:**
- No code changes unless fixups are needed

**Step 1: Commit implementation**

Run:
```bash
git add docs/plans/2026-04-16-custom-print-stage-zones-design.md docs/plans/2026-04-16-custom-print-stage-zones.md twocomms/storefront/custom_print_config.py twocomms/storefront/tests/test_custom_print.py twocomms/twocomms_django_theme/templates/pages/custom_print.html twocomms/twocomms_django_theme/static/js/custom-print-configurator.js twocomms/twocomms_django_theme/static/css/custom-print-configurator.css tests/test_custom_print_config_contract.py
git commit -m "feat: expand custom print stage and zone controls"
```

**Step 2: Merge into `main`**

Run:
```bash
git switch main
git pull --ff-only origin main
git merge --no-ff codex/custom-print-stage-zones-recovery -m "Merge branch 'codex/custom-print-stage-zones-recovery'"
git push origin main
```

**Step 3: Deploy via SSH**

Run the production rollout:
- `git pull --ff-only origin main`
- `python manage.py migrate --noinput`
- `python manage.py collectstatic --noinput`
- `python manage.py compress --force`
- `touch tmp/restart.txt`

**Step 4: Post-deploy verify**

Verify:
- `https://twocomms.shop/custom-print/` returns `200`
- new HTML contains full-width lobby copy and updated config payload
- page visually reflects the new lobby and zones behavior
