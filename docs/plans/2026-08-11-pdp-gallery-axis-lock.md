# PDP Gallery Axis Lock Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Lock a PDP gallery touch to its initially selected axis so slow horizontal swipes cannot be stolen by later vertical drift on iPhone.

**Architecture:** Keep the existing Pointer Events carousel. Add a pure sticky-axis resolver and a stage-scoped non-passive Touch Events guard that prevents native scrolling only after horizontal intent wins; harden `pointercancel` to finish a horizontally owned gesture from saved coordinates.

**Tech Stack:** Vanilla JavaScript, Pointer Events, Touch Events, CSS `touch-action`, Node test runner, Django template tests, Playwright/CDP and WebKit.

---

### Task 1: Sticky Axis Contract

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/js/product-detail.test.js`
- Modify: `twocomms/twocomms_django_theme/static/js/product-detail.js`

1. Add a test proving `pending` resolves after a radial 5 px with Swiper's 45-degree boundary and that `horizontal` or `vertical` never changes after later cross-axis movement.
2. Run the Node test and confirm it fails because the resolver does not exist.
3. Add and export the minimal pure resolver.
4. Run the Node test and confirm it passes.

### Task 2: Stage-Scoped Scroll Guard

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/js/product-detail.js`

1. Track the active touch identifier and initial coordinates on `touchstart`.
2. Resolve the touch axis once and keep it until `touchend` or `touchcancel`.
3. Add a `{ passive: false }` stage `touchmove` listener.
4. Prevent default only for a single-touch gesture whose locked axis is horizontal.
5. Leave vertical-first and multi-touch gestures native.

### Task 3: Cancellation Fallback And Asset Release

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/js/product-detail.js`
- Modify: `twocomms/twocomms_django_theme/templates/pages/product_detail.html`
- Modify focused Django asset-key tests.

1. Reuse saved pointer coordinates when a horizontally owned gesture receives `pointercancel`.
2. Keep pointer-axis ownership independent from Touch Events cleanup so either cancel-event order settles identically.
3. Prevent a multi-touch/pinch cancellation from committing an image change.
4. Keep the existing vertical handoff cancellation path.
5. Bump only the PDP JavaScript cache key to `20260811-gallery-v6`.
6. Run Node tests, syntax checks, focused Django tests, Django check, and `git diff --check`.

### Task 4: Mobile Verification And Release

1. Run current-code and fixed-code traces for slow horizontal movement followed by vertical drift.
2. Verify vertical-first scrolling, multi-image and single-image products, edge resistance, controls, zoom, cleanup, overflow, and console state.
3. Commit only the axis-lock files and plans.
4. Push to `main`, deploy with fast-forward pull, collectstatic, compress, Django check, and Passenger restart.
5. Repeat production Chromium 390/430 and WebKit 390 verification without asset interception and prove SHA alignment.
