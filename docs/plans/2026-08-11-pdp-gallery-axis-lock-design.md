# PDP Gallery Axis Lock Design

## Goal

Keep the existing top PDP gallery easy to drag slowly on iPhone: a vertical-first gesture scrolls the page, while a horizontal-first gesture stays owned by the carousel until the finger is released, even when the finger later drifts several pixels vertically.

## Root Cause

The gallery already keeps its JavaScript `horizontalIntent` flag after it is set, but the browser is still allowed to arbitrate native vertical scrolling because the stage uses `touch-action: pan-y pinch-zoom` and every gallery move listener is passive. On WebKit, a slow horizontal drag can therefore be cancelled when later movement contains enough vertical drift. The resulting `pointercancel` path always returns the preview, which is the visible jerk and reset reported on iPhone.

Swiper and Embla use the same two-stage contract:

1. Decide scroll versus drag once from the initial movement angle.
2. If horizontal wins, call `preventDefault()` from a non-passive move listener for the remainder of that touch.

## Design

- Add a small pure axis resolver with three states: `pending`, `horizontal`, and `vertical`; resolve at a radial 5 px like Swiper while retaining the existing 8 px visual drag threshold.
- Keep the state unchanged after either axis wins.
- Preserve `touch-action: pan-y pinch-zoom` so a vertical-first gesture and pinch zoom remain native.
- Track the active touch identifier on the gallery stage.
- Register only the gallery stage's `touchmove` listener as `{ passive: false }`.
- Call `preventDefault()` only after the axis resolves to `horizontal`; never block a vertical-first or multi-touch gesture.
- Keep Pointer Events for rendering, pointer capture, velocity, and settling.
- If `pointercancel` arrives after horizontal ownership, finish from the last stored coordinates. If the distance is insufficient, return cleanly; otherwise settle to the adjacent image.
- Keep Pointer and Touch axis state independent: WebKit may emit `touchcancel` before `pointercancel`, and touch cleanup must not erase the pointer's horizontal ownership.
- Record multi-touch separately so a pinch-triggered cancellation returns the drag instead of switching the image.
- Do not add a modal-first flow, a new carousel library, or global touch blocking.

## Acceptance

- A slow horizontal drag followed by vertical jitter does not scroll the page, cancel, or snap back unexpectedly.
- A vertical-first drag scrolls the page and never changes the image.
- Axis ownership cannot switch during one touch.
- Pinch zoom remains available.
- `pointercancel -> touchcancel` and `touchcancel -> pointercancel` produce the same horizontal result, while a cancellation after a second finger never changes the image.
- Fast, short, repeated, edge, thumbnail, arrow, keyboard, and explicit zoom flows remain unchanged.
- No stuck preview nodes/classes, horizontal overflow, swipe-opened lightbox, or console errors.
