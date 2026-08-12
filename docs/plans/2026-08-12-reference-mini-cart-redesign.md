# Reference Mini-Cart Redesign

## Scope

- Preserve the existing `/cart/mini/` endpoint, AJAX refresh, removal callbacks, cart totals, and checkout route.
- Rebuild the partial markup around the supplied mobile bottom-sheet reference.
- Add responsive mobile bottom-sheet and desktop top/right drawer presentation with safe-area and reduced-motion handling.
- Add a visual free-shipping progress block using the canonical 3000 UAH threshold and the rendered combined total.
- Render color variants as circular swatches with accessible labels, without visible color text.

## Verification

- Focused template/CSS contract tests.
- Django checks and template test suite.
- Browser screenshots at phone, tablet, and desktop widths with empty, partial, and threshold-reaching cart states where available.
