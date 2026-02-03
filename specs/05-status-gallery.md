# 05 — STATUS + GALLERY (Draft)

## Status (Control Deck)
- Header with order number, copy/share link.
- Pipeline timeline (Intake → Preflight → Print → Powder → Cure → Pack → Ship).
- QC report block with real data derived from order fields (file, meters, copies, review flag).
- Delivery block with TTN and NP tracking link.
- Share mode: `?share=1&order=...` hides QC + internal blocks (reorder/help).
- Alias route: `/status/<code>/` opens share-safe view.
- Dynamic favicon gated by `enable_dynamic_favicon` (progress ring).
- Stage change flash (120ms scan‑flash) via `status-board.is-flash`.

## Gallery (Proof-first)
- Filters for Macro/Process/Final.
- Grid cards with chips + expandable passport (details/summary).
- Compare sliders (3) + Lens (1) placeholders, gated by feature flags.
- Lens on mobile opens zoom modal (tap → modal).
- CTA "Зробити як тут" → `/order?ref=<id>`.

## Files
- `twocomms/dtf/templates/dtf/status.html`
- `twocomms/dtf/templates/dtf/gallery.html`
- `twocomms/dtf/static/dtf/css/dtf.css`
- `twocomms/dtf/static/dtf/js/dtf.js`
- `twocomms/dtf/views.py`
- `twocomms/dtf/urls.py`
