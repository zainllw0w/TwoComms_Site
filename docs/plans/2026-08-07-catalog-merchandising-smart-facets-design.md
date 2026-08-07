# Catalog Merchandising Smart Facets Design

**Status:** Approved design contract, ready for implementation planning

**Scope:** The concrete category pages `/catalog/tshirts/`, `/catalog/hoodie/`, and `/catalog/long-sleeve/`, indexable merchandising collection pages such as `/merch/225/`, and the compact merchandising context in the upper decision zone of every affected product detail page (PDP). The root catalog and search pages remain on their current rendering path until a separate decision is made.

## Product Goal

Turn the Variant 3 Smart Selector into the primary conversion surface for paid and organic category traffic. A visitor must see real product media immediately, understand the current category and available cuts, narrow the catalog without losing context, and reach a product page in one or two taps on a phone. The same information architecture must remain compact and legible on tablet and desktop.

The page is not a visual SEO essay. Product discovery owns the first viewport; contextual editorial content appears after the product list and is useful to both people and crawlers.

## Decisions

### Experience model

Use a hybrid of Variant 3 Smart Selector and curated collection landing pages:

- category tabs stay at the top and use real crawlable URLs;
- a compact first-viewport command shelf exposes result count, applied chips, sort, and the mobile filter trigger;
- high-frequency themes are visible as a single horizontally scrollable row on mobile and a compact row on desktop;
- every other facet lives in a mobile bottom sheet or a sticky desktop rail;
- collection and brigade pages reuse the same product grid and filters but add a small collection identity block;
- audience and collection assignments made in Fable 5 continue into both the catalog card and the upper PDP decision zone from the same normalized source;
- category, collection, and product URLs remain real links and work without JavaScript;
- the server renders the initial product set and pagination fallback; JavaScript adds progressive loading and visual transitions only.

### Filter semantics

The selected category is always an AND constraint. Between facet groups, constraints are also AND constraints.

Audience is an explicit strict AND group, per the product decision:

- selecting `unisex` and `women` returns products carrying both audience tags;
- a product can carry any combination of `unisex`, `women`, and `men`;
- selecting no audience means no audience restriction;
- existing T-shirts are backfilled with `unisex`; hoodies and long sleeves are left unchanged until staff assigns them.

For choice facets that describe alternatives rather than product identity, the UI will show the behavior explicitly: selected sizes and colors represent acceptable purchasable options, while availability, fit, theme, brigade, and audience remain required constraints. The implementation must expose this distinction in tests and copy rather than rely on an undocumented assumption.

Canonical query encoding uses repeated keys in stable order, for example:

```text
/catalog/tshirts/?audience=unisex&audience=women&fit=oversize&size=M&size=XL&availability=in_stock
```

Unknown values are ignored server-side. The resulting state is deterministic and safe to cache.

### Fable 5 product data

Add a product-level audience taxonomy to Fable 5 rather than storing comma-separated text in `Product.target_audience`:

- `AudienceTag`: stable code (`unisex`, `women`, `men`), translated labels, sort order, active flag;
- `ProductAudience`: unique product/tag assignment with an optional editorial note for staff;
- an editor fieldset with three large check controls, current selection summary, and validation that at least one tag is selected for published apparel;
- an idempotent data migration/backfill that assigns `unisex` to all published and draft T-shirts without overwriting existing explicit assignments;
- the legacy `target_audience` text remains available for explanatory copy and is not used as a filter source.

Add a normalized collection taxonomy for future growth:

- `MerchCollection`: slug, kind (`theme`, `city`, `brigade`, `collab`), parent, localized name/title/description, SEO title/description, cover image, accent token, indexable flag, order, and active flag;
- `ProductMerchCollection`: product-to-collection assignment with ordering and optional display label;
- `MerchCollection` may be nested without hard-coded template branches. In the first catalog tree, `military`, `brigades`, `streetwear`, and `kharkiv` are sibling themes under the T-shirt category, while `225` and `127` are brigade children of `brigades`;
- thermochromic remains authoritative on `ProductColorVariant.is_thermo`/Fable 5 color details and is never duplicated in free text.

Fits, size grids, price, and stock continue to use the existing `ProductFitOption`, `variant_public_context()`, Fable 5 size-grid services, and inventory rules. The selector must never infer sellability from a size guide row alone.

The hierarchy is editorial, not duplicate product data. Staff may assign the most specific fact such as `225`; the public resolver derives membership in the `brigades` parent for counts and filtering. A parent with children is a disclosure group with an explicit "all brigades" choice, while `225` and `127` remain independently selectable child values. Selecting several brigade children applies strict AND. Selecting a parent together with one of its children is canonicalized to the child because the parent is already implied. Catalog cards and the compact PDP rail show the most specific assigned label and do not repeat `Бригади / 225 ОШП` as two badges.

### PDP merchandising continuity

Fable 5 assignments are not complete until they are visible and truthful on the public product page. A single server-side resolver accepts the product, active language, selected color variant, and selected fit, then returns a presentation-safe context for both initial HTML and variant JavaScript. It combines only authoritative sources:

- audience labels from active `ProductAudience` assignments;
- theme, city, brigade, and collaboration markers from active `ProductMerchCollection` assignments in their stored order;
- public links only for collections with a real active curated route; unpublished or non-indexable assignments may be shown as plain facts when appropriate but never as dead links;
- thermochromic state, material story, and price delta from the selected `ProductColorVariant` through `variant_public_context()`, never from a product title, collection tag, or free-text description;
- fit, price, availability, and size truth from the existing variant/stock services rather than from merchandising labels.

The upper PDP hierarchy remains purchase-first: gallery, product title, category, price, and primary selection/purchase action keep their current prominence. Merchandising appears as one compact context rail adjacent to the title/meta region, not as a hero or a wall of badges. The rail uses the most specific normalized assignment, so a `225` product shows `225 ОШП` rather than a redundant `Бригади` plus `225 ОШП` pair. Collection and brigade labels are meaningful links; audience is rendered as a labelled product fact. On narrow screens the rail is a single stable horizontal row with 44px link hit areas and no multi-line growth; secondary assignments remain reachable through horizontal scrolling or a compact `+N` disclosure. It must not move the first price or buy action below the expected first interaction area.

Static product assignments stay stable while a shopper changes color or fit. Variant-dependent markers update in place from the already-delivered variant payload: selecting a thermochromic color reveals the flame, material explanation, and truthful price delta; selecting an ordinary color removes them without reloading or moving surrounding layout. The server-rendered state, URL-selected state, and hydrated JavaScript state must agree.

PDP schema and analytics consume the same normalized codes, with lossless truth taking priority over additional fields. Product schema must remove the current universal `Стріт & Мілітарі` style assertion and emit collection/style properties only for real assignments. A single unambiguous audience may map to `suggestedGender`; multiple audience tags remain visible as audience values and must not be collapsed into a false single gender. Existing `view_item` and variant-selection events may be enriched with normalized audience/collection codes after the current consent and deduplication path is traced; no second page-view event and no PII are introduced.

### Routes and landing pages

The first collection route is `/merch/225/`, localized by the existing language routing convention. The `127` node is present in the taxonomy but remains non-indexable until it has assigned products and reviewed localized editorial content. The `225` route is a `CollectionPage` with:

- one descriptive H1 such as `Мерч для 225 ОШП — TwoComms`;
- a short collection identity line, not a large hero;
- the same smart product grid and filter controls;
- a curated internal-link cluster to the parent category, size guide, delivery, and custom print;
- an editorial FAQ written specifically for the brigade/collection.

The collection resolver must return `404` for inactive or non-indexable collections and must avoid generating thousands of indexable combinations from arbitrary facet URLs.

### SEO, AEO, and GEO

The document head and body use the existing multilingual SEO services and add only truthful structured data:

- `BreadcrumbList` for category and collection hierarchy;
- `ItemList` for the server-rendered visible products, with canonical product URLs and positions;
- `CollectionPage` for curated collection routes;
- `FAQPage` only when the questions and answers are visible in the HTML;
- existing organization/product schema remains the source of brand and offer facts.

Arbitrary filtered combinations use a canonical to the nearest curated category/collection and `noindex,follow` when they have no editorial landing contract. Curated collection routes are indexable and receive unique localized title, description, H1, intro, and FAQ content. Do not place `noindex` on the base category pages.

The lower module is a context-aware editorial surface:

- `At a glance`: fit, fabric, size availability, thermochromic note, and delivery;
- `Explore this collection`: links to military, streetwear, Kharkiv, and brigade pages that actually exist;
- `How to choose`: a compact size/fit explainer linking to the full guide;
- `FAQ`: 3-5 concise accordions, localized and visible to crawlers;
- `Create your print`: a restrained final CTA for visitors who did not find a ready-made design.

Each section has a stable heading and semantic landmarks, but the visual treatment is a refined editorial panel matching the current checkout/main-site shell: thin borders, restrained accent color, compact rows, and no keyword stuffing.

### Visual and interaction contract

Mobile is the source layout. At 375px:

- the first product image starts within 280 CSS pixels of the top of the content;
- the category switcher fits one horizontal scroll row without wrapping;
- the command shelf remains sticky only after the header has scrolled away, avoiding a double-sticky stack;
- applied filters are removable chips with 44px hit areas;
- the filter sheet uses a fixed header, internally scrollable body, and fixed action footer;
- filter groups are accordion sections with counts, active state, and a short affordance label;
- thermochromic swatches show a small flame badge and a text label for assistive technology;
- cards reserve media space with fixed aspect ratio and show title, truthful price range, fit, availability, audience, and color cues without text collisions.
- fixed mobile bottom navigation reserves its own safe-area space; no card title, price, CTA, pagination, or SEO content may sit underneath it.

At 768px the sheet remains available as a drawer. At 1024px and above the rail is sticky, compact, and keyboard navigable; the product grid uses stable 3/4-column tracks based on available width.

Animations are limited to opacity/transform and do not change layout:

- 180ms backdrop fade;
- 220ms sheet translate with an ease-out curve;
- 160ms accordion height/opacity transition with a reduced-motion fallback;
- 220ms product reveal stagger capped at four items;
- no animation is used for the first LCP image or for URL navigation.

The mobile shell exposes a measured `--mobile-nav-reserved` value. Main content, the progressive-loading sentinel, and the editorial footer receive bottom padding derived from that value plus `env(safe-area-inset-bottom)`. When the filter dialog is open, its action footer sits above the safe area and the mobile navigation cannot capture pointer events.

### Accessibility and mobile reliability

The filter surface is a real dialog pattern:

- `aria-expanded` and `aria-controls` remain synchronized;
- background content becomes inert while the sheet is open;
- focus moves into the sheet, is trapped, and returns to the trigger;
- Escape and backdrop close work; browser back closes an open sheet before navigating;
- all groups use `fieldset`/`legend` semantics or equivalent labelled sections;
- keyboard and touch activation use the same delegated handler;
- static asset versioning is bumped whenever selector JavaScript changes so stale cached assets cannot reintroduce the mobile bug.

### Analytics contract

Use the existing analytics/dataLayer adapters after tracing their current naming and deduplication conventions. Events are emitted only after the UI state changes:

- `view_item_list`: category/collection, visible product IDs, language;
- `catalog_filter_apply`: facet, selected values, result count, source (`quick_row`, `sheet`, `rail`);
- `catalog_filter_clear`;
- `catalog_filter_sheet_open` and `catalog_filter_sheet_close`;
- `select_item` and `quick_view_open`;
- `view_merch_collection` with collection/brigade slug;
- the existing PDP `view_item` and variant-selection payloads may carry normalized collection/audience codes from the same server context, without duplicating the event;
- `catalog_progressive_load`;
- `custom_print_click`.

No raw form data or PII is sent. Existing Meta/GTM naming and browser/server deduplication rules take precedence over inventing a second event vocabulary.

### Performance contract

- Server-render the first page and all semantic headings/content.
- Reserve image dimensions and card heights to keep CLS below the agreed Core Web Vitals threshold.
- Preload only the first visible product media; lazy-load the rest with `loading="lazy"` and `decoding="async"`.
- Keep progressive loading as an enhancement; pagination links remain visible to crawlers and no-JS users.
- Avoid `content-visibility` or deferred hydration on the H1, first row, structured data, or SEO headings.
- Measure LCP, CLS, INP, TTFB, console errors, request failures, image failures, and horizontal overflow at all target viewports.

## Non-goals

- Redesigning the root `/catalog/` or search page in this slice.
- Replacing the entire PDP, checkout, or payment flow. This slice does recompose the catalog card meta zone and add a compact merchandising context to the existing upper PDP decision zone.
- Assigning invented audience/size/stock values where production data is missing.
- Creating indexable pages for every arbitrary filter combination.

## Molecular UX quality matrix

Every visible surface has one job and one measurable reason to exist:

| Surface | Required behavior | Why it stays | What is deliberately excluded |
| --- | --- | --- | --- |
| Shared header | Same logo, navigation, search, cart, account, language controls as the home/checkout shell | Preserves trust and lets ad traffic recognize the brand immediately | A second catalog-only header |
| Category switcher | Three real links, active state, horizontal scroll on narrow screens, keyboard-visible focus | Makes the landing category obvious and supports direct ad destinations | A carousel that hides category names |
| H1/result row | One H1, concise intent copy, count aligned to the edge | Gives users and crawlers immediate context | A large hero or slogan before products |
| Theme quick row | At most one compact row, counts, active state, scroll affordance; `Бригади` discloses `225` and `127` without leaving the product grid | Lets high-intent military/brigade/Kharkiv/streetwear traffic branch in one tap | A wall of chips, duplicated parent/child badges, or hidden child categories |
| Command shelf | Filter trigger, applied-count, sort, and removable chips; sticky only after header exit | Keeps the action path visible without covering products | A permanent bottom commerce bar |
| Mobile filter sheet | Full-height dialog with sticky header/footer, accordion groups, Apply/Reset, focus trap | Allows deep filtering without shrinking product cards | A nested modal inside the sheet |
| Desktop rail | Sticky, compact, grouped by intent, counts and disabled states | Makes comparison efficient on large screens | Oversized card-like panels around every group |
| Product card | Stable image, truthful price range, fit, audience, availability, thermo marker, favorite, real detail link | Answers purchase questions before the PDP | Invented badges, fake scarcity, or price inferred from legacy text |
| PDP merchandising rail | Same normalized audience/collection assignments as Fable 5 and catalog; selected-variant thermo state; real curated links | Preserves context from campaign/category to product without delaying purchase decisions | A badge wall, dead links, free-text inference, or a second hero |
| Empty state | Explain which constraints conflict, offer one-tap chip removal and a category reset | Recovers conversion instead of ending the session | A dead-end “nothing found” message |
| Progressive status | Quiet status text and stable sentinel; pagination stays available | Gives feedback without page-jump or crawler loss | Skeletons that replace server-rendered cards |
| Collection identity | Small collection mark, one-line context, optional cover, then products | Makes a brigade/collab landing page feel specific without a hero takeover | Military imagery or claims not supplied by content owners |
| Editorial SEO module | Facts, links, FAQ, custom-print CTA in semantic sections/`details` | Serves intent, AEO/GEO extraction, and internal linking after discovery | Keyword-heavy paragraphs above the grid |
| Mobile bottom navigation | Reserves measured safe-area space and never overlaps content; disabled while dialog is open | Preserves the existing shell and prevents occlusion | A second sticky row that competes with the command shelf |

The implementation review must mark each row as verified or explain the residual risk. A surface that cannot be tied to a user decision, a crawl contract, or a performance/accessibility requirement is removed from the slice.

### Product card relationship audit

The card must read as one product decision, not as an image, a price block, and a detached color control:

1. **Media layer:** image, availability badge, favorite button, and optional quick-view affordance share one stable media box.
2. **Identity layer:** title is followed by the truthful visible price/range. A thermo price delta is marked beside the price with the flame icon and a short reason, never as a second unexplained price.
3. **Decision meta layer:** fit, audience, and availability are compact labelled facts in one aligned row/grid. Empty facts are omitted rather than leaving blank gaps.
4. **Color layer:** a labelled `Колір` row sits directly under the decision meta, inside the same card body and border rhythm. Swatches use 44px hit areas with 20-24px visual dots, contrast rings for white/light colors, and a flame badge for thermochromic variants. A `+N` affordance appears only when there are more variants than the compact row can show.
5. **Action boundary:** the card's bottom border separates cards, not price from color. There is no orphan dot below a horizontal rule and no swatch whose meaning depends on an adjacent card.

The card contract is invariant on mobile and desktop; only the number of columns and the amount of meta wrapping changes. Tests must assert the DOM order `title -> price -> decision meta -> color`, and visual QA must check that long translated labels do not push the color row outside the card.

### Measured baseline defects to remove

The August 8 live audit at 390x844 and 1440x1000 establishes a concrete before-state:

- on mobile the first product media starts around 322 CSS pixels, but the long H1 is visibly clipped and competes with the quick selectors;
- the current card renders a divider after price/fit and then an unlabelled color dot, so the swatch reads as detached from the product;
- the fixed mobile navigation overlaps the following product media and must reserve real safe-area space in the document;
- the theme/fit/color selector row compresses labels instead of preserving a deliberate one-row hierarchy;
- the desktop rail presents `Бригади` as a flat peer with no visible path to `225` or `127`.

These are acceptance defects, not optional polish. The final screenshot matrix must include the first viewport, a card boundary with its complete color row, an open brigade disclosure, the mobile filter sheet, and the upper PDP merchandising rail.

### Decision psychology guardrails

- Recognition precedes choice: category, H1, first image, and price appear before deep filters.
- Choice is progressive: theme quick row first, then filter sheet groups ordered by campaign intent (collection/audience, availability, fit, size, color, thermo).
- Feedback is immediate: counts, applied chips, and result status update with the URL state.
- Commitment is postponed: the catalog offers product links and a subtle custom-print route, not a forced quick-view funnel.
- Trust beats novelty: motion highlights state changes but never delays the first product image or disguises stock/price truth.

### Cross-device invariants

The following must remain true at every supported width and language:

- no horizontal overflow and no clipped translated label;
- every interactive target is at least 44 CSS pixels in its active axis;
- no fixed element overlaps a card control or semantic heading;
- the same URL state produces the same selected facets on reload and back/forward;
- JS disabled still exposes category, collection, product, pagination, FAQ, and custom-print links;
- reduced motion preserves all state changes without transition-dependent content;
- focus order follows visual order and never moves behind an overlay.

## Acceptance

The slice is accepted when the focused Django/JavaScript tests pass, the Fable 5 editor can save and reload multi-select audience and collection assignments, those assignments appear consistently on catalog cards and the upper PDP context, selected-color thermo state remains synchronized, all three category routes and `/merch/225/` work in Ukrainian/Russian/English, mobile and desktop browser checks pass at 320/375/430/768/1024/1440 widths, LCP/CLS and accessibility budgets are measured, and live SEO output contains only truthful canonical/schema/indexation states.
