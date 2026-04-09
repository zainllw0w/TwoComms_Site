# Parsing Moderation Density Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rework the parsing moderation table so it remains compact and readable across desktop screen widths while keeping moderation actions prominent and stable.

**Architecture:** Keep the existing moderation table and API payloads, but rebuild the row composition around primary vs secondary information. The change stays in the parsing dashboard template plus regression tests, with browser validation on representative desktop widths.

**Tech Stack:** Django templates, inline CSS/JS in `management/parsing.html`, Django tests, local browser validation, targeted production template deploy.

---

### Task 1: Lock the target structure with regression tests

**Files:**
- Modify: `twocomms/management/tests_template_regressions.py`

**Step 1: Write the failing test**

Add assertions for the compact moderation row hooks:
- action rail wrapper
- primary review button wrapper
- compact metadata wrappers for shop/site/keyword cells

**Step 2: Run test to verify it fails**

Run: `python twocomms/manage.py test management.tests_template_regressions.ManagementTemplateRegressionTests.test_parsing_dashboard_exposes_compact_moderation_row_layout --settings=test_settings`

Expected: FAIL because the new hooks are not yet present in the template.

**Step 3: Keep the existing quick-action regression**

Retain coverage for quick approve/reject icon buttons so the redesign does not regress the new compact actions.

### Task 2: Rebuild the moderation row layout

**Files:**
- Modify: `twocomms/management/templates/management/parsing.html`

**Step 1: Adjust table sizing**

Update the moderation `colgroup`, column width rules, and desktop breakpoints to prioritize `Магазин`, `Сайт`, and `Дія`.

**Step 2: Introduce compact cell structure**

Split row rendering into primary and secondary wrappers for shop/site/keyword/phone content without changing the underlying payload.

**Step 3: Stabilize the action rail**

Keep `Оглянути` readable with a minimum comfortable size and keep the icon stack fixed-width so it does not push outside the table shell.

**Step 4: Refine desktop breakpoints**

Hide or compress secondary metadata first, then allow scroll only as the last fallback on narrower desktop widths.

### Task 3: Verify locally

**Files:**
- Modify if needed: `twocomms/management/tests.py`

**Step 1: Run targeted regression tests**

Run: `python twocomms/manage.py test management.tests_template_regressions.ManagementTemplateRegressionTests management.tests.ParserApiTests --settings=test_settings`

Expected: PASS.

**Step 2: Validate in a browser**

Start the local app, load the parsing dashboard with representative moderation rows, and inspect widths such as `1366px`, `1280px`, and `1600px`.

Expected: action rail stays visible, `Оглянути` remains readable, and cells do not bleed outside the table shell.

### Task 4: Deploy safely and smoke-check production

**Files:**
- Runtime only: production `management/templates/management/parsing.html`

**Step 1: Backup the current production template**

Copy the runtime file to a timestamped `.bak_codex_*` backup.

**Step 2: Upload the updated template**

Replace only the runtime template because production checkout is dirty.

**Step 3: Run production checks**

Run: `python manage.py check`

Expected: no system check issues.

**Step 4: Restart and smoke-check**

Touch Passenger restart file, then verify:
- login page returns `200`
- parsing page redirects to login when unauthenticated
- runtime template contains the new compact row hooks
