# PDP Mobile Gallery Swipe Design

## Goal

Make the existing top product-image carousel respond to light, smooth horizontal swipes on iPhone and other touch devices without opening a separate viewer or changing the page layout.

## Confirmed Scope

- Keep the routed `product_detail.html` gallery, main image, thumbnails, dots, arrows, keyboard navigation, color-driven image changes, and optional zoom action.
- Swipe directly inside the current `.tc-media-stage`.
- Preserve normal vertical page scrolling and pinch zoom.
- Do not add a modal-first flow, a full-screen requirement, a CDN dependency, or a second carousel implementation.

## Root Cause

Two independent input paths made the gallery unreliable on iPhone-class devices:

1. The custom drag waited too long before recognizing horizontal intent and required either a relatively large distance or high release velocity. A real CDP touch trace (`dx=15`, `dy=2`) was already recognized as horizontal and rendered an adjacent preview, but its sampled velocity was only `0.12 px/ms`; the release logic rejected it and snapped back.
2. The shared mobile optimizer was initialized from both `main.js` and `product-media.js`. It installed two non-passive document-level `touchend` listeners and called `preventDefault()` even when `cancelable=false`, producing two console errors per gesture and adding avoidable main-thread touch handling.

The swipe settle also kept the gallery locked through an unnecessary image-decode/timer chain, while every drag transform was written directly during `pointermove`.

## Design

Keep the custom in-place carousel and make its lifecycle deterministic:

1. Declare vertical page scrolling and pinch zoom through `touch-action`; horizontal dragging stays with the carousel.
2. Capture the primary touch pointer at `pointerdown`, while retaining the real `pointercancel` path for browser-owned vertical scrolling.
3. Warm adjacent images, create the adjacent preview as soon as horizontal intent is clear, and coalesce drag transforms to animation frames.
4. Recognize horizontal intent after `8 px` at up to a `45 degree` angle. Allow a `12 px` light commit only when the final gesture is strongly horizontal, while retaining distance and velocity fallbacks for ordinary swipes.
5. Commit on `transitionend` with a bounded fallback, shorten settle/fade timing, and release the settling lock promptly.
6. Never map `lostpointercapture` to cancellation because an intentional `releasePointerCapture()` emits it during a valid swipe.
7. Make the global touch optimizer idempotent and passive. Suppress a ghost click on the later capture-phase `click` event instead of cancelling `touchend`.

## Acceptance

- Fast, slow, short, and repeated left/right swipes change one image inside the existing stage.
- Vertical and predominantly vertical diagonal gestures scroll the page without changing the image.
- Edge drags have bounded resistance and return cleanly.
- Swiping never opens the lightbox; only the explicit zoom control does.
- No stuck drag/settling classes, preview nodes, horizontal page overflow, duplicate handlers, or console errors.
- Thumbnails, dots, arrows, color changes, zoom button, and keyboard navigation remain operational.
- Browser coverage includes Chromium CDP touch at 390/430 px, WebKit pointer lifecycle, products with 3/4/5/6/12 images, and a single-image product.
