# Category Smart Selector Design

## Decision

Implement the approved Variant 3 Smart Selector only on the three concrete product category routes: `/catalog/tshirts/`, `/catalog/hoodie/`, and `/catalog/long-sleeve/`. Keep `/catalog/` and search on their current templates and interactions.

The production page uses the existing Django catalog data and the existing storefront shell. It keeps one semantic H1, real product/detail URLs, the existing SEO editorial blocks, and crawlable pagination. The visual hierarchy is compact at the top so the first mobile viewport reaches the product grid quickly, while desktop receives the approved four-column grid and left filter rail.

## Experience

- A compact category switcher links to real category URLs and exposes the active category in the URL.
- The command shelf contains the active result summary, sort, and a 44px mobile filter trigger. Desktop expands this into the left rail.
- T-shirts and hoodies expose Classic/Oversize only when the product data supports those fits; long sleeves expose Standard only.
- Theme, fit, color, audience, availability, and price controls preserve URL state. Color continues to use the existing canonical color filter service. Theme matching reuses the existing thematic keyword contract; fit and stock use the existing fit/variant inventory relations.
- Product cards keep the existing preferred image, price, color variants, favorite/cart behavior, and real product links. The Smart Selector wrapper adds semantic item metadata without duplicating card logic.
- Mobile filters open as an internally scrolling bottom sheet with page lock, Escape/backdrop close, focus return, and a sticky result action. Desktop filters remain visible and compact.
- Progressive loading fetches the next normal category pagination URL when the sentinel enters view. The server-rendered pagination remains in the DOM as an accessible and crawlable fallback.

## Visual system

Use the production header and footer partials and the approved prototype's restrained dark/purple treatment: thin borders, dense grid rhythm, no decorative gradients or oversized hero copy, and stable card/image dimensions. Scoped `smart-selector-*` selectors prevent the design from changing the general catalog or search pages.

## Data and SEO boundaries

No new database fields or migrations are required. The view computes a small Smart Selector context from existing category, product, color, fit, and SEO services. Unsupported facets are rendered disabled or omitted rather than implying inventory. Query parameters are validated against known values; invalid values fall back to the category page. Canonical/meta/JSON-LD/pagination blocks remain the current category contracts.

## Verification

The feature is accepted only when focused Django tests, the full storefront catalog regression set, JavaScript syntax checks, and browser checks at 320, 375, 430, 768, and 1440px pass. The browser checks must cover category links, filters, sheet close/reset, sorting, progressive loading, product/card URLs, SEO fallback markup, no horizontal overflow, and no console/request/image errors.
