# 02 — Global Layout (Draft)

## Scope
- Header/nav/footer baseline
- Global background and layout grid
- Safe-area and viewport behavior

## Implemented
- Dark Control Deck palette applied via legacy tokens in `tokens.css`.
- `body` uses dark gradient background; `color-scheme: dark`.
- `dtf-shell` uses `min-height: 100svh` to mitigate mobile viewport jumps.
- Header uses dark glass surface with `backdrop-filter` and fallback.
- Safe-area inset applied to header top padding.
- Mobile CTA bottom offset includes `env(safe-area-inset-bottom)`.
- Mobile bottom dock nav (Order/Price/Status/Help) added.
- Mobile drawer nav (hamburger) added with focus trap.
- Background noise layer hooked to `noise-tiling-1.png`.
- `theme-color` meta set to dark.
- Active state styling for desktop nav and mobile dock via `aria-current`.
- DTF-specific 404/500 handlers + templates added.
