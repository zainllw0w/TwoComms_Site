# Variant 3 Catalog Restoration Design

## Decision

Restore the approved Variant 3 as the visual base of the complete category catalog instead of iterating on the heavier production treatment. The original HTML prototype and supplied screenshots are the reference for the mobile first viewport, selector sheets, desktop rail, compact command shelf, product grid, card proportions, favorite-button weight and overall visual density.

The work is a presentation and interaction correction, not a new design. Existing Product Catalog taxonomy, AND multi-select URL semantics, audience, availability, size, thermochromic, brigade children, analytics, pagination, SEO and product pricing remain authoritative and are fitted into the Variant 3 composition.

## Product-first hierarchy

- Mobile shows the compact command row with `Фільтри`, result count and sort, followed by the three Variant 3 selectors: `Тема`, `Крій`, `Колір`.
- Each quick selector opens a focused bottom sheet with the Variant 3 handle, compact heading and full-width option rows. The general filter button opens all advanced facets.
- Sort uses the same focused sheet language on mobile rather than a visually unrelated native select.
- The catalog heading remains compact on mobile; long category SEO copy stays in the lower editorial area.

## Desktop rail

The left rail returns to the Variant 3 composition: an unframed sticky column, a quiet right divider, compact groups and clear reset action. It must stay sticky while the product grid scrolls. The catalog root cannot create an overflow ancestor that disables sticky positioning.

New groups are retained but visually subordinated:

- Theme, including expandable brigade children.
- Fit.
- Color swatches.
- Availability.
- Audience.
- Size.
- Thermochromic technology.

## Cards

Cards return to open catalog tiles. The product photo carries the visual boundary; the whole card has no panel background, external border, inset padding or dashboard shadow. A thin lower divider and grid spacing separate products. The fit marker sits quietly beside the price so color swatches remain attached to the product information.

The favorite control keeps a 44px touch target but presents only the heart glyph with a subtle shadow. It does not render a large circular fill over the product image.

## Interaction model

One existing filter overlay is reused for focused and advanced modes. A trigger identifies its mode (`theme`, `fit`, `color`, `sort`, or `all`); JavaScript updates the sheet title, exposes only the relevant section for focused modes, preserves focus trapping and browser-back close behavior, and keeps analytics source data.

Filter selection continues to navigate through canonical server URLs. Repeatable facets remain AND filters. The sort sheet writes the existing validated `sort` query parameter.

## Acceptance

- At 320px and 390px, the compact controls and the top of the first product row are visible without horizontal overflow.
- Theme, fit, color and sort open dedicated Variant 3-style sheets; general filters expose all enhanced facets.
- At 1024px and 1440px, the left rail remains sticky during page scroll and has no enclosing card surface.
- Product photos regain the Variant 3 width; the favorite glyph has no visible circular container.
- Django tests, JavaScript syntax, Django checks and browser console checks pass.
