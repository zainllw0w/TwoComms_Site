# Custom Ref Garment Stage Design

## Goal

Replace the procedural Custom Print 3D garment with the supplied `CUSTOM_REF` garment renders while preserving the existing configurator state, print-zone selection, and submission payloads.

## Asset Model

The stage uses a normalized lookup keyed by garment family, fit, color, and side:

`{type, fit, color, side} -> {avif, webp}`

The source PNGs are converted once into AVIF and WebP assets. The browser receives AVIF first with WebP fallback through `<picture>`. The lookup includes explicit aliases for the current configurator values (`tshirt`, `hoodie`, `longsleeve`, `classic`, `regular`, `oversize`) and falls back to the closest black render when a requested color or side is not available.

## Stage Behavior

- The existing `stage_view` state remains the source of truth for front/back.
- Selecting a print zone continues to update the zone overlays and stage receipt.
- The garment layer is a regular image inside a fixed aspect-ratio stage frame, centered with `object-fit: contain` and `object-position: center`.
- The old Three.js viewer is not initialized. No pointer-driven rotation, geometry rebuild, or material recoloring remains on this path.
- A subtle crossfade is used only when the resolved asset changes; reduced-motion users receive an instant swap.
- Existing stage controls, labels, safe-zone overlays, and mobile preview sheet remain untouched except where they need to reference the new image layer.

## Compatibility And Quality

- WebP is the broad fallback; AVIF is preferred where supported.
- Transparent pixels are preserved during conversion.
- The asset manifest is generated deterministically from `CUSTOM_REF` and checked into the static tree so deploys do not depend on image tooling.
- The lookup is defensive: invalid state, missing side, or unknown color resolves to a valid black front/back asset instead of leaving an empty stage.

## Verification

- Contract tests cover every supported garment/fit/color/side mapping and fallback behavior.
- JavaScript syntax checks cover the stage module and configurator.
- Django checks and focused Custom Print tests run before commit.
- Playwright/browser verification covers front/back, each zone, fit/color changes, mobile preview, no horizontal overflow, and stable centered rendering.
