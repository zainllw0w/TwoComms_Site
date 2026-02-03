# 03 — HOME (Draft)

## Hero: Printhead Scan (L2 baseline)
- H1 uses double layer: outline + fill.
- Fill is revealed via `clip-path` animation (900ms).
- Scan line is a thin vertical line animated once.
- Reduced motion: `scan-static` shows partial fill, no animation.
- Tier selection via `DTF_FEATURE_FLAGS` (`enable_printhead_scan`, `tier_mode=auto/force0..4`).

## Quick Estimate Bar
- Inline calculator sits right after hero.
- Uses `length_m` input + hidden `copies=1`.
- Server-side calc via HTMX (`hx-get` → `/estimate/`) updates `#estimate-result`.
- Outputs: `#calc-price` and `#calc-meters` (tabular nums).
- Action submits to order page with prefilled meters; secondary CTA allows skipping calc.

## Files
- `twocomms/dtf/templates/dtf/index.html`
- `twocomms/dtf/static/dtf/css/dtf.css`
- `twocomms/dtf/static/dtf/js/dtf.js`

## Notes
- Effect is CSS-only and runs once on load.
- CTA remains visible throughout.
- Reduced motion hides scan line.
- Hero media uses CLS-safe `asset-slot` placeholder (aspect-ratio 16:9).
- `#pricing-data` remains on home for progressive fallback (JS calc if HTMX fails).

## Proof Block (Gallery Preview)
- Works section now includes chip metadata overlays (width/turnaround/type).
- CTA leads to `#works` anchor (gallery page to be added in Phase 5).
- Added compare cards (2) + lens card (1) as placeholder proof interactions.
- Compare/lens gated by `enable_compare` / `enable_lens` feature flags.
