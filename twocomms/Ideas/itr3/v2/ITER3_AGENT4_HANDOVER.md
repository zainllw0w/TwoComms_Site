# ITER3 Agent4 Handover

## Purpose
This handover documents the UI micro-pack assets and integration contracts used by Agent3/Agent5 during Iter3 reconciliation.

## Delivered asset groups

### SVG icons (`twocomms/dtf/static/dtf/svg/`)
- `icon-file.svg`
- `icon-scan.svg`
- `icon-check.svg`
- `icon-info.svg`
- `icon-warning.svg`
- `icon-fix.svg`
- `icon-bulb.svg`
- `icon-truck.svg`
- `icon-sheet60.svg`
- `icon-palette.svg`
- `icon-telegram.svg`
- `icon-upload.svg`
- `icon-clock.svg`
- `icon-shield.svg`
- `icon-calculator.svg`

### Component CSS (`twocomms/dtf/static/dtf/css/components/`)
- `icons.css`
- `animations.css`
- `effect.compare.css`
- `effect.tooltip-card.css`
- `effect.text-generate.css`
- `multi-step-loader.css`
- `floating-dock.css`
- `effects-bundle.css` (runtime bundle)

### Component JS (`twocomms/dtf/static/dtf/js/components/`)
- `effect.compare.js`
- `effect.tooltip-card.js`
- `effect.text-generate.js`
- `multi-step-loader.js`
- `floating-dock.js`
- `effects-bundle.js` (runtime bundle)

## Runtime wiring contract

### Base includes
- `twocomms/dtf/templates/dtf/base.html` loads:
  - `dtf.css`
  - `icons.css`
  - `animations.css`
  - `effects-bundle.css`
  - `dtf.js`
  - `effects-bundle.js`

### Effect registration contract
- All effect modules register through `DTF.registerEffect(...)`.
- Runtime selectors are based on `data-effect` and/or explicit attributes (e.g. `data-floating-dock`, `data-upload-flow`).

### File check naming contract (UI)
- UI terminology uses `filecheck`/`check` instead of `preflight`/`qc` for new selectors/classes:
  - `data-filecheck-url`
  - `data-filecheck-loader`
  - `.constructor-filecheck-card`
  - `dtf:filecheck-ready`
  - `.filecheck-*`
  - `.check-*`

## Integration points by template
- `twocomms/dtf/templates/dtf/index.html`:
  - Homepage process/FAQ icon embeds, compare cards, bulb in why-us block.
- `twocomms/dtf/templates/dtf/order.html`:
  - `data-upload-flow` + `data-filecheck-url` + filecheck status blocks.
- `twocomms/dtf/templates/dtf/constructor_app.html`:
  - constructor filecheck card + floating dock integration.
- `twocomms/dtf/templates/dtf/status.html`:
  - status timeline classes use `check-*` naming.
- `twocomms/dtf/templates/dtf/faq.html`:
  - canonical FAQ structure (`faq-item`, `faq-q`, `faq-a`).

## JS behavior assumptions
- FAQ accordion uses `.faq-item` with `.faq-q` button + `.faq-a` answer.
- Icon animations are one-shot and triggered by viewport/interaction (`.dtf-icon-animate` toggled by JS).
- Compare autoplay uses eased ping-pong motion and synchronized handle/clip.

## Build/minify step
After source edits to `dtf.css`, `dtf.js`, or `effects-bundle.js` run:
- `python manage.py minify_dtf_assets`

This regenerates:
- `twocomms/dtf/static/dtf/css/dtf.min.css`
- `twocomms/dtf/static/dtf/js/dtf.min.js`
- `twocomms/dtf/static/dtf/js/components/effects-bundle.min.js`

## Validation checklist
- No stale `data-preflight-*` selectors in active runtime JS/CSS bundles.
- No `.qc-*` classes in status UI.
- FAQ accordion works on `/` and `/faq/` with `aria-expanded` updates.
- Topbar rotator cycles multiple localized phrases.
