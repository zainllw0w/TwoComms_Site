# OpenGraph Image Refresh Design

## Goal

Replace the generic TwoComms social preview with the user-provided artwork while preserving entity-specific previews for products, categories, and blog articles.

## Asset contract

- The source is `open_graph/scr.jpg` from the primary checkout.
- The published fallback is a new cache-busting static path, `img/social-preview-2026-08.jpg`.
- The published file is a progressive sRGB JPEG at exactly 1200x630.
- The source is center-cropped from 4642x2580 to the 1.9048:1 OpenGraph ratio before downscaling. It is never stretched and no generative editing is applied.
- Metadata is stripped and compression is tuned for a small social-crawler download without visible text or edge degradation.

## Resolution rules

The image chosen for a page remains entity-aware:

1. A self-canonical product/color URL uses that product or color variant's image.
2. A catalog/category page uses the category cover when it has one.
3. A blog article uses its optimized WebP cover.
4. Pages without an owned preview, plus entity pages without an image, use the new fallback.

The new fallback is shared across UA, RU, and EN because the approved artwork itself is the canonical brand card. Old locale-specific rendered cards are no longer selected.

## Metadata integrity

- `og:image` and `twitter:image` always resolve to the same selected asset.
- The fallback declares `image/jpeg`, 1200x630, and a descriptive localized alt.
- Blog covers retain their known `image/webp`, 1600x1000 metadata.
- Dynamic product/category images keep their entity URL and alt, but must not inherit the fallback's JPEG MIME type or 1200x630 dimensions when those facts are not guaranteed.
- Schema.org organization/storefront/homepage/contact fallbacks use the same versioned static path. Blog and product structured data keep their own images.

This follows the Open Graph structured-property rule that type, dimensions, and alt describe the immediately preceding image instead of a different fallback asset.

## Deployment and verification

- Run focused Django regression tests under CPython 3.14.6 / Django 6.1.
- Validate the JPEG dimensions, color mode, progressive encoding, and file size.
- Run `collectstatic --noinput` locally against an isolated static root to prove the manifest contains the versioned asset.
- Push the scoped commits directly to `main`.
- On production, pull `main`, run `collectstatic --noinput`, restart Passenger, then verify HTML metadata and the image response for representative fallback, product, category, and blog URLs.

