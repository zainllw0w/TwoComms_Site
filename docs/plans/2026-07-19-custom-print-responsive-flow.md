# Custom Print Responsive Flow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the homepage hero, localization prompt, and Custom Print configurator stable and understandable across desktop/mobile, with corrected pricing, validation, contacts, and Telegram handoff.

**Architecture:** Keep the existing Django template + config-driven JavaScript flow. Put business rules (print size ranges, garment deltas, fabric copy) in `custom_print_config.py`, keep rendering and navigation in the existing configurator modules, and use CSS media queries/safe-area variables for responsive layout. Preserve the current server endpoints and snapshot schema while improving the user-facing payload and idempotent submit state.

**Tech Stack:** Django templates/i18n, Python config/helpers, vanilla JavaScript modules, CSS, pytest/Django tests, Playwright.

---

### Task 1: Establish regression coverage for pricing, locale, and validation

**Files:**
- Modify: `twocomms/storefront/tests/test_custom_print_config_contract.py`
- Modify: `tests/test_custom_print_guided_studio_source.py`
- Create: `twocomms/storefront/tests/test_custom_print_pricing_rules.py`

**Steps:** Add failing assertions for A6/A4/A3/A2 price deltas and labels, tshirt oversize +200, premium/thermo copy, Ukrainian default language prompt behavior, contact icon markup, visible breadcrumbs, and step validation targeting the missing section. Run the focused tests and record the failures.

### Task 2: Correct config-driven product pricing and size guidance

**Files:**
- Modify: `twocomms/storefront/custom_print_config.py`
- Modify: `twocomms/twocomms_django_theme/static/js/custom-print-configurator.js`

**Steps:** Add explicit ISO size ranges and per-print price deltas, expose them in the serialized config, update tshirt oversize/premium/thermo rules, compute the same deltas in client and normalized server snapshots, clamp quantity/size breakdown controls, and keep legacy keys compatible.

### Task 3: Fix responsive hero, breadcrumbs, appbar, and studio navigation

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/css/home.css`
- Modify: `twocomms/twocomms_django_theme/static/css/custom-print-guided-studio.css`
- Modify: `twocomms/twocomms_django_theme/templates/pages/custom_print.html`
- Modify: `twocomms/twocomms_django_theme/static/js/custom-print-mobile-shell.js`
- Modify: `twocomms/twocomms_django_theme/static/js/custom-print-configurator.js`

**Steps:** Add safe-area/header offsets, stable hero min/max heights, no scene overflow, breadcrumb placement below the header, a real back button in the appbar, deterministic restart/exit, and responsive stage/lacing rules. Keep tap targets stable at 390px and 1440px widths.

### Task 4: Improve guided-step UX and contact controls

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/pages/custom_print.html`
- Modify: `twocomms/twocomms_django_theme/static/css/custom-print-guided-studio.css`
- Modify: `twocomms/twocomms_django_theme/static/js/custom-print-configurator.js`

**Steps:** Replace alert-like validation with inline status/error regions and scroll/focus to the first invalid step, render fleece as one segmented toggle, show contact channels as icon-first equal-width controls, clarify gift skip/continue wording, and make manager CTA reliably open with a fresh greeting and no stale draft dependency.

### Task 5: Make manager and cart handoff readable and immediate

**Files:**
- Modify: `twocomms/storefront/custom_print_notifications.py`
- Modify: `twocomms/twocomms_django_theme/static/js/custom-print-submit-flow.js`
- Modify: `twocomms/twocomms_django_theme/templates/pages/custom_print.html`
- Modify: `twocomms/storefront/tests/test_custom_print.py`

**Steps:** Structure the Telegram brief into compact labeled sections, include print sizes/ranges, garment/fabric/fit, quantity, gift, contact, and named uploaded files; use immediate pending/success/error state and dedupe-safe submission; update the cart dialog copy to explain manager confirmation before payment.

### Task 6: Verify at source and browser level

**Files:**
- Modify: none unless tests expose regressions.

**Steps:** Run focused pytest plus the full custom print source contract suite, run Django checks, start the local server, capture Playwright screenshots at 1440x812, 390x844, and 360x800, inspect overflow/overlap and language behavior, then run a final git diff/status audit before commit/push/deploy.
