# Mobile Catalog Shell Stability Design

## Decision

Refine the approved mobile catalog and global shell without replacing their visual language. The interface stays black and graphite with an orange action accent, condensed display typography, compact garment cards, and the existing fixed header and dock. The work addresses five concrete problems together: Safari document height, non-functional root filters, uneven mini-cart geometry, header brand spacing, and homepage hero-logo LCP.

The root catalog remains category-first when no filters are selected. Opening filters changes it into an aggregate product-results route backed by the server, so a shopper can filter T-shirts, hoodies, and long sleeves together instead of being forced into one category first.

## Approaches Considered

### 1. Server-rendered aggregate filters (selected)

The root `/catalog/` accepts repeated category and inventory facet parameters, applies them to the complete published-product queryset, and renders the normal product-card grid with pagination. This keeps URLs shareable, avoids loading the whole assortment into JavaScript, and reuses the canonical inventory facet service.

### 2. Redirect into one category selector

The root filter could first ask for a garment and then redirect to the existing category Smart Selector. This is simpler but cannot show multiple garment types in one result set, which conflicts with the requested all-catalog behavior.

### 3. Client-side filtering

The root could preload product cards and hide non-matches in the browser. This would increase HTML and image work, break pagination truth, and make filtered links non-shareable. It is rejected.

## Catalog Height And Safari

The page background must be continuous through the full document, not only through the fixed-height mobile composition. The route-level `html`, `body`, `main`, root shell, and mobile reference use the same black background. Minimum height uses `100svh` as the stable baseline and `100dvh` where supported, plus the fixed dock and safe-area inset. The reference wrapper no longer relies on `overflow: clip` for page-level geometry.

This directly addresses the supplied iPhone screenshot where the black catalog surface ends and the base graphite page background continues for a large empty area.

## Mobile Filter Drawer

The root filter control opens a bottom sheet with four concise groups:

- garment: T-shirts, hoodies, long sleeves;
- color: current public color variants from the database;
- size: the canonical sellable size order;
- availability and sort: in stock, recommended, newest, price ascending, price descending.

Selections are native form controls with large labels and real GET parameters. Apply submits the form; reset returns to the unfiltered root. The sheet has a fixed header and action footer, a scrollable middle, focus restoration, Escape/backdrop close, body-scroll locking, active-count synchronization, and safe-area padding. On category pages, the same global filter buttons continue to delegate to the existing Smart Selector sheet.

When root filters are active, category hero cards are replaced by the standard product grid containing every matching published product across the selected garment categories. Empty results remain a normal server-rendered empty state.

## Mini-Cart Refinement

The mobile mini-cart keeps its current content and checkout actions. Its panel becomes a stable grid between the fixed mobile header and dock: compact header, independently scrollable cart content, and the existing delivery/info rows below. It uses the same black/off-white/orange palette as the catalog.

Each item row uses explicit grid tracks for media, flexible copy, and price/remove actions. Copy tracks use `min-width: 0`; titles clamp to two lines; metadata wraps naturally; prices use tabular numbers and never share the title track. At short viewport heights, secondary delivery copy is reduced before the checkout action becomes cramped.

## Header And Homepage LCP

The mobile wordmark group moves two pixels left and increases the mark-to-name gap to 10px. The desktop brand receives a dedicated class with an explicit logo/name gap, so Bootstrap utilities do not own the alignment contract.

The homepage preloads the existing `logo.svg`, changes the hero image to asynchronous decode, and removes redundant `filter` and `will-change` work from the hero image itself. Dimensions and visual output stay unchanged.

## Custom Print Motion

The four low-contrast logo marks remain behind the garment and away from copy. Each mark follows a distinct slow transform path with small horizontal drift, vertical lift, and rotation. Motion is continuous and visibly alive but low-amplitude; delays prevent synchronized movement. `prefers-reduced-motion: reduce` freezes the marks.

## Acceptance

- No graphite/gray document tail appears after the catalog on iPhone-like tall viewports.
- Root filter buttons open a real accessible filter sheet.
- Multiple garment types can appear in one filtered result set.
- Filter values are derived from public catalog data or canonical facet constants.
- Mini-cart titles, prices, remove controls, and actions do not collide at 320px.
- Header logo and wordmark align at 320, 390, 430, and desktop widths.
- Custom-print marks visibly animate without crossing the copy or CTA.
- Homepage hero logo is preloaded and no longer performs redundant image filtering.
- Desktop catalog composition is unchanged.

