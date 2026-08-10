# PDP Mobile Gallery Swipe Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the existing top PDP image carousel easy and smooth to swipe on iPhone and other touch devices without changing its visible workflow.

**Architecture:** Retain the current single-stage custom gallery and harden its Pointer Events lifecycle. Warm neighboring images, recognize horizontal intent earlier, render drag transforms on animation frames, shorten the settle lock, and remove duplicate non-passive global touch handling while preserving vertical browser scrolling.

**Tech Stack:** Vanilla JavaScript, CSS Pointer Events/touch-action, Node test runner, Django templates/tests, Playwright/CDP mobile emulation.

---

### Task 1: Gesture Contracts

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/js/product-detail.test.js`
- Modify: `twocomms/twocomms_django_theme/static/js/product-detail.js`

1. Add failing tests for early unambiguous horizontal intent and a light short flick.
2. Reproduce the measured low-velocity `15 px` flick and protect a similarly short diagonal gesture from switching.
3. Run the focused Node test and confirm the intended assertions fail.
4. Change only the gesture thresholds/helpers required to pass.
5. Run the focused Node test again.

### Task 2: Pointer And Rendering Lifecycle

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/js/product-detail.js`
- Modify: `twocomms/twocomms_django_theme/static/css/product-detail.css`

1. Capture the primary touch pointer on start and release it on vertical handoff or finish.
2. Warm adjacent images and create the directional preview before its first animation-frame render.
3. Coalesce transform writes with `requestAnimationFrame` and make pointermove passive.
4. Finish the settle on transition completion with a bounded timeout fallback.
5. Keep `pointercancel` handling but do not add `lostpointercapture` cancellation.

### Task 3: Asset Version And Regression Checks

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/pages/product_detail.html`
- Modify relevant focused Django template tests only if their asset-version expectation changes.

1. Bump only the PDP JS/CSS cache key.
2. Run Node tests, syntax check, focused Django PDP tests, Django check, and `git diff --check`.

### Task 4: Shared Mobile Touch Arbitration

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/js/modules/optimizers.js`

1. Reproduce the duplicate `touchend cancelable=false` console error in real CDP touch input.
2. Make touch optimization idempotent across `main.js` and `product-media.js` initialization.
3. Keep touch listeners passive and move ghost-click suppression to capture-phase `click`.
4. Repeat the browser scenario and require zero console errors and no swipe-triggered lightbox.

### Task 5: Mobile Browser And Production Verification

1. Verify 390 px and 430 px touch flows for fast, slow, short, diagonal, vertical, edge, and repeated gestures.
2. Verify Chromium touch and WebKit lifecycle behavior across products with 3, 4, 5, 6, and 12 images plus a single-image product.
3. Verify thumbnails, arrows, dots, variant changes, zoom control, console, and horizontal overflow.
4. Commit only scoped files, push `main`, deploy with fast-forward pull, collectstatic, compress, Django check, and Passenger restart.
5. Repeat live touch checks and prove local, origin, and server SHAs match.
