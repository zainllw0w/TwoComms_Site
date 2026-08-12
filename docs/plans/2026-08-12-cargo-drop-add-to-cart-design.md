# Cargo Drop Add-to-Cart Animation Design

**Date:** 2026-08-12

**Goal:** Add the approved cargo-drop animation to every product add-to-cart trigger while preserving existing button styling and opening the mini-cart only after successful completion.

## Current behavior

The product detail page has a primary `.tc-add-btn[data-add-to-cart]` and a mobile `[data-pdp-sticky-add]` proxy that invokes the primary button. The shared `main.js` delegated handler currently opens the mini-cart before the `/cart/add/` request resolves, then refreshes it after success. Header cart controls already have separate desktop and mobile DOM nodes and a shared badge-update path.

## Proposed behavior

1. Every add-to-cart trigger gets the same internal cargo scene, while its existing visual shell (gradient, border, typography, dimensions, and responsive layout) remains unchanged.
2. Clicking either trigger resolves to the actual clicked button, marks only that button busy, and prevents duplicate submissions.
3. The existing request payload, variant/size/fit/option resolution, CSRF retry, analytics, and cart refresh remain unchanged. The mini-cart is not opened before request success.
4. After a successful response, the clicked button runs the reference sequence: belt/parcel entry, scan, fold/seal, ship to cart, and confirmation.
5. At the parcel-to-cart beat, both desktop and mobile header cart triggers receive a short, restartable attention pulse. The pulse uses transform/box-shadow only, has no layout shift, and is removed on completion.
6. The mini-cart content is refreshed before the panel opens. The panel opens only after the cargo confirmation lands, so users see the persisted item rather than a loading shell.
7. Failed requests never show a false success or open the panel; the clicked button receives the existing danger state and returns to idle.
8. `prefers-reduced-motion` skips the long scene, announces success accessibly, performs the cart refresh, pulses the header without motion, and opens the mini-cart after the same success gate.
9. If a second trigger is clicked while another animation is active, it is independently guarded; the first request/animation remains authoritative and no duplicate request is sent from the same button.

## Implementation surfaces

- `twocomms/twocomms_django_theme/templates/pages/product_detail.html`: add semantic scene markup to the primary and sticky triggers, preserving existing labels/icons.
- `twocomms/twocomms_django_theme/static/css/product-detail.css`: add namespaced cargo-scene styles, phase animations, compact sticky adaptations, reduced-motion rules, and button state rules without replacing the current shell.
- `twocomms/twocomms_django_theme/static/js/main.js`: extract reusable scene lifecycle helpers, delay mini-cart opening until success/animation completion, and coordinate header attention pulses.
- `twocomms/twocomms_django_theme/templates/base.html`: add stable data hooks to desktop/mobile cart toggles if the current markup does not expose both hooks.
- `twocomms/twocomms_django_theme/static/js/product-detail.test.js` or a focused adjacent Node test: assert the source-level contracts for trigger markup, delayed `openMiniCart`, and reduced-motion/attention-pulse helpers.

## Accessibility and resilience

- Scene decorations are `aria-hidden`; the button keeps an accessible label and uses `aria-busy` while adding.
- Live status text announces “Added to cart” once; reduced-motion users do not receive a forced multi-second animation.
- Focus remains on the clicked button until the panel opens; no timer can reopen a stale panel after a later failure or newer operation.
- All timers are scoped to the button and cancelled during reset. CSS animations use compositor-friendly opacity/transform and `will-change` only during active phases.

## Verification

- Node/source-contract tests for phase hooks, trigger coverage, open timing, and reduced-motion branch.
- Django/template checks and focused storefront tests for the existing add/cart contract.
- Browser QA on desktop and mobile: click primary and sticky buttons, capture the cargo phases, verify both header cart triggers pulse, verify no early panel, verify refreshed item is visible on open, test failure and reduced-motion paths, and confirm no console errors.
