# Catalog Visual Cleanup Design

## Goal

Restore product-first clarity to Variant 3 without removing the structured merchandising capabilities added to Product Catalog, catalog filtering, PDP, SEO, analytics, or URLs.

This iteration is a focused refinement of the approved Variant 3, not a replacement design. The selector keeps its composition, information architecture, site header/footer, product imagery and card proportions. Only weak or noisy surfaces adopt the restrained, warm, high-trust language of the Instagram hosted checkout: dark neutral surfaces, soft warm borders, orange/gold actions, compact typography and deliberate motion.

## Visible hierarchy

The category tabs remain first. The heading and product count remain compact. The permanent quick-facet row is removed. Mobile shows one filter command and sorting; desktop shows the existing left rail. Applied chips exist only after a selection. Product cards return to image, availability badge, title, price, and color swatches.

## Card rules

The catalog card does not print theme, audience, fit, or availability facts. Those values remain available to filters and machine-readable contexts. Swatches need no visible `Колір` label. A thermochromic flame is nested inside the 22px swatch circle and never rendered as a sibling floating at the edge of the 44px touch target.

## Filter rules

The mobile filter remains a real bottom sheet with a drag handle, 22px top radii, sticky header/footer, safe-area padding and an ease-out entrance. Selected options use a checkmark with the Instagram checkout gold/action colors; unselected controls stay neutral. Purple is removed from the catalog selector stylesheet. The desktop rail uses the same controls at lower visual intensity.

The filter trigger, sort field, rail sections and sheet actions may be redesigned within their existing semantic structure. Avoid generic boxed rows: use calm surface hierarchy, readable spacing and subtle warm feedback. Keep animations limited to disclosure, sheet entrance, selected-state transition and product appearance; support reduced motion.

## Quality bar

The first mobile viewport must show category context, the compact command row and actual product imagery without a dense introductory panel. Every visible label must help a purchase decision. Decorative effects cannot compete with product photos or increase layout shift. Desktop should retain the successful Variant 3 composition while making the rail feel integrated rather than bolted on.

## Non-goals

No taxonomy, filtering semantics, Product Catalog schema, SEO copy, product assignment, sorting, pagination, infinite loading, analytics event names or URL behavior changes.

## Verification

Focused Django render contracts will assert the removed card metadata and quick row do not render, the thermo icon is nested inside the swatch dot, active filters still render, and filter controls remain present. JavaScript syntax, Django checks and existing focused tests must pass. Mobile and desktop screenshots must confirm product-first hierarchy, no overflow and a functional bottom sheet.
