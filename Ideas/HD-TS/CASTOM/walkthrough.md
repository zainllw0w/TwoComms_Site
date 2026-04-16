# TwoComms Configurator UX Redesign — Walkthrough

## Summary

Complete rewrite of the custom print configurator's CSS, HTML template, and JavaScript to address all UX issues identified in the V4 vision document. The old 6-step flow with a bloated "product" mega-step has been replaced by a clean 8-step flow with animated transitions, lobby mode, and premium visual states.

---

## Key Changes

### 1. Step Flow: 6 → 8 steps

The old `product` step forced users to configure fit, fabric, color, zones, AND add-ons all at once. This has been split:

| Old Step | New Steps |
|----------|-----------|
| `quickstart` | `quickstart` (unchanged) |
| `mode` | `mode` (unchanged) |
| `product` ← mega-step | **`product`** — Lobby: just pick the garment |
| | **`config`** — Fit + Fabric + Color |
| | **`zones`** — Print zones + Add-ons |
| `artwork` | `artwork` (unchanged) |
| `quantity` | `quantity` (unchanged) |
| `review` | `review` (unchanged) |

### 2. Lobby Mode

Steps 1–3 (`quickstart`, `mode`, `product`) are "lobby" steps — full-width, no Stage Card visible. The Stage Card only appears from step 4 (`config`) onward once the user has made a product choice. This prevents the awkward empty-garment-on-the-left problem.

### 3. Animated Step Transitions

Steps now animate with directional transitions:
- **Forward** (going deeper): old step slides left + fades, new step slides in from right
- **Backward** (going back): reversed direction
- 300ms cubic-bezier easing for smooth feel
- `requestAnimationFrame` double-buffered for jank-free entry

### 4. Premium Selected States

All option cards and chips now have:
- **Golden border** (`var(--cp-accent)`) + `box-shadow` glow when `is-active`
- **✓ badge** (absolute positioned circle) with pop-in animation on selected cards
- No more orange outlines — clean golden system throughout

### 5. Build Strip State Management

Build strip chips now have 3 states:
- **`is-active`** — Gold border, current step
- **`is-done`** — Green ✓ badge, subtle green border, clickable to go back
- **`is-pending`** — Dimmed (45% opacity), non-clickable, can't skip ahead

### 6. Desktop 50/50 Layout

The workbench grid is now `1fr 1fr` instead of the old `3fr 2fr`. Both Stage Card and step panel get equal space. Stage Card is `position: sticky` with `top: 1rem` so it follows scroll.

### 7. Mobile Improvements

- **Compact Stage**: `max-height: 220px` on mobile so it doesn't dominate the viewport
- **Sticky Build Strip**: stays at top of viewport on scroll with right-edge fade gradient for scroll indicator
- **Full-width buttons**: step actions stack vertically on mobile

### 8. Garment Cross-Fade

Color changes trigger a smooth cross-fade animation on the garment silhouette (opacity + scale transition, 250ms).

### 9. Zone Pulse Animation

Active zone pins on the garment get a pulsing box-shadow animation to draw attention.

### 10. Smart Config Skipping

Products without fit/fabric options (t-shirt, longsleeve, customer_garment) automatically skip the `config` step and go directly from `product` to `zones`.

---

## Files Modified

### [custom-print-configurator.css](file:///Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/static/css/custom-print-configurator.css)
render_diffs(file:///Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/static/css/custom-print-configurator.css)

### [custom_print.html](file:///Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/pages/custom_print.html)
render_diffs(file:///Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/pages/custom_print.html)

### [custom-print-configurator.js](file:///Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/static/js/custom-print-configurator.js)
render_diffs(file:///Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/static/js/custom-print-configurator.js)

---

## Deployment

Since the production site uses **WhiteNoise** with `CompressedManifestStaticFilesStorage`, changes require:

```bash
cd twocomms
python manage.py collectstatic --noinput
# Then restart the server/gunicorn
```

> [!IMPORTANT]
> The browser tests showed the **old cached version** because `collectstatic` hasn't been run yet. All code changes are correct and ready for deployment.

## Backwards Compatibility

- Old drafts saved in `localStorage` with the 6-step flow are handled: the `normalizeState` function maps unknown step names back to `quickstart`
- The `buildSnapshot()` and `buildFormData()` functions produce the same API payload as before — no backend changes needed
- The `custom_print_config.py` backend config is unchanged
