# Cargo Drop Add-to-Cart Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Preserve the live product buttons' current shells while adding the reference cargo-drop sequence, synchronized header-cart attention, and success-gated mini-cart opening to both primary and sticky triggers.

**Architecture:** A reusable Django partial supplies a purely decorative cargo scene inside each live trigger. Shared helpers in `main.js` coordinate button-local phase classes, the cart-header pulse, request success, mini-cart refresh, and final panel opening; the existing request payload and analytics path remain intact. Namespaced CSS renders the scene responsively within the existing button dimensions and collapses the sequence for reduced-motion users.

**Tech Stack:** Django templates/i18n, vanilla ES module JavaScript, CSS animations, Node `node:test`, Django test runner, Playwright CLI.

---

### Task 1: Lock the behavior contract

**Files:**
- Create: `twocomms/twocomms_django_theme/static/js/add-to-cart-animation.test.js`

**Step 1:** Assert both live PDP triggers expose idle/scene/done hooks while preserving `.tc-add-btn` and `.tc-sticky-add-btn`.

**Step 2:** Assert the success handler invokes `runCargoDropAnimation`, refreshes mini-cart content, and only then opens the panel.

**Step 3:** Assert both header triggers expose `data-cart-attention` and shared pulse logic targets the hook.

**Step 4:** Assert reduced-motion detection has a dedicated branch.

**Step 5:** Run `node --test twocomms/twocomms_django_theme/static/js/add-to-cart-animation.test.js`; expect four failures because the feature is absent.

### Task 2: Add reusable button scene markup

**Files:**
- Create: `twocomms/twocomms_django_theme/templates/partials/add_to_cart_cargo_scene.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/product_detail.html`
- Modify: `twocomms/twocomms_django_theme/templates/partials/header.html`

**Step 1:** Add decorative belt, scanner, box, cart, and confirmation markup with `aria-hidden="true"`.

**Step 2:** Wrap the current primary label/icon in `data-cargo-idle` and include the partial without changing the button shell classes.

**Step 3:** Give the sticky trigger the same product metadata and `data-add-to-cart` contract, wrap its current label in `data-cargo-idle`, and include the same partial.

**Step 4:** Add `data-cart-attention` to both desktop and mobile header cart buttons.

**Step 5:** Update the product asset version query strings to avoid stale production CSS/JS.

### Task 3: Render cargo phases inside existing shells

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/css/product-detail.css`
- Modify: `twocomms/twocomms_django_theme/static/css/mobile-shell.css`

**Step 1:** Add idle/scene/done layering without replacing current backgrounds, borders, radii, dimensions, typography, or shadows.

**Step 2:** Port the reference phase animations under `tc-cargo-*` names with percentage/`clamp()` geometry that works in both buttons.

**Step 3:** Add a compact sticky layout and ensure long localized labels remain hidden only during the active sequence.

**Step 4:** Add restartable `.is-cart-attention` pulse styling for both header implementations with no layout shift.

**Step 5:** Add reduced-motion overrides and active-only `will-change` behavior.

### Task 4: Coordinate request, animation, and mini-cart

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/js/main.js`
- Modify: `twocomms/twocomms_django_theme/static/js/product-detail.js`

**Step 1:** Add timer-safe helpers to reset and run scene phases on the clicked button.

**Step 2:** Add `pulseHeaderCartAttention()` targeting both header hooks and cleaning the class before replay.

**Step 3:** Stop opening mini-cart before `/cart/add/` resolves and stop opening it on failures.

**Step 4:** On success, update the badge immediately, refresh mini-cart concurrently, run the button animation, pulse the header at the ship beat, await both animation and refresh, then open the panel.

**Step 5:** Keep button busy/disabled through the full cycle and restore it in `finally`; preserve cart events and analytics.

**Step 6:** Remove the sticky proxy click because the sticky button now owns the same add contract directly.

### Task 5: Verify contracts and regressions

**Files:**
- Test: `twocomms/twocomms_django_theme/static/js/add-to-cart-animation.test.js`
- Test: `twocomms/twocomms_django_theme/static/js/product-detail.test.js`

**Step 1:** Run the focused contract test; expect all four tests to pass.

**Step 2:** Run `node --test twocomms/twocomms_django_theme/static/js/product-detail.test.js`; expect no regression.

**Step 3:** Run `python manage.py check` and focused storefront product/cart/template tests using the repository virtualenv.

**Step 4:** Inspect `git diff --check` and verify no unrelated files entered the branch.

### Task 6: Browser QA and production shipment

**Files:**
- Artifacts: `output/playwright/` (ignored/local only)

**Step 1:** Start the local Django server and open a real available product at desktop width.

**Step 2:** Click the primary CTA, verify the mini-cart stays closed during the scene, verify the header pulse at the ship beat, and verify the refreshed panel opens after confirmation.

**Step 3:** Repeat at mobile width using the sticky trigger and inspect console/network errors.

**Step 4:** Emulate reduced motion and verify the short success path.

**Step 5:** Commit the implementation, integrate to local `main` without touching the original worktree WIP, push `main`, deploy with the supplied SSH command, and verify server SHA plus live desktop/mobile flow.
