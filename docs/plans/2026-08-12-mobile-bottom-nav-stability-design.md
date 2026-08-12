# Mobile Bottom Navigation Stability Design

## Goal

Make the storefront mobile bottom navigation stable during short scrolls and swipes: icons, labels, and avatars keep their exact size while the dock transitions cleanly between fully visible and fully hidden states across iOS, Android, and narrow tablets.

## Design

- Keep the dock height fixed and reserve `safe-area-inset-bottom` in its padding; do not use dynamic viewport units for the dock geometry.
- Use one composited dock transition (`translate3d` plus opacity) with no scale or layout animation on descendants.
- Use a dock-owned rAF-throttled scroll listener with direction accumulators, a hide threshold, a larger reveal threshold, and hard overrides at the top and footer.
- Keep deliberate dock swipes, focus hiding, reduced-motion behavior, and desktop media-query teardown intact.
- While the dock is transitioning, interaction is disabled only in the hidden state; the visible dock remains keyboard and screen-reader reachable.

## Verification

- Add source-contract assertions for fixed geometry, safe-area padding, no scale transition, hysteresis thresholds, and reduced-motion handling.
- Run focused Django storefront tests and JavaScript syntax checks.
- Run Playwright at 320, 375, 390, 430, and 768 CSS px; exercise short and full vertical swipes, top-of-page reveal, dock bounds, child dimensions, reduced motion, and zero horizontal overflow.
