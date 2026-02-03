# 04 — ORDER (Draft)

## Layout
- Two-column structure: left (Upload/Preview/Preflight), right (Params/Delivery + Sticky Summary).
- Tabs remain for Ready vs Help flows.

## Upload
- Dropzone with caution-tape micro stripe background and dragover glow.
- Visible CTA for Clipboard paste (Safari requirement).
- File name feedback and upload step chips.
- Global paste hint prompts user to use the clipboard button.

## Preflight Terminal
- Advisory checks with OK/WARN/RISK labels.
- WARN never blocks order; optional risk acknowledgment checkbox.

## Underbase Preview
- Toggle simulates view on dark fabric (visual class only, conservative).

## Live Pricing
- HTMX server calc via `/estimate/?context=order` with debounce (300ms) on length/copies.
- Fallback JS calc via `#pricing-data` when HTMX unavailable.

## Sticky Summary
- Desktop: sticky right panel.
- Mobile: fixed bottom bar; hidden when `body.keyboard-open`.
- Visual Viewport API toggles `keyboard-open`.

## Submit Guard
- Submit button disables on submit and shows spinner.

## Draft сохранение
- Order формы сохраняют черновик в `localStorage` и восстанавливают поля при возврате.

## Files
- `twocomms/dtf/templates/dtf/order.html`
- `twocomms/dtf/templates/dtf/partials/order_calc.html`
- `twocomms/dtf/static/dtf/css/dtf.css`
- `twocomms/dtf/static/dtf/js/dtf.js`
- `twocomms/dtf/views.py`
