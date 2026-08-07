# Catalog Merchandising Smart Facets Design

**Status:** Approved design contract, ready for implementation planning

**Scope:** The concrete category pages `/catalog/tshirts/`, `/catalog/hoodie/`, and `/catalog/long-sleeve/`, plus indexable merchandising collection pages such as `/merch/225/`. The root catalog and search pages remain on their current rendering path until a separate decision is made.

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
- `MerchCollection` may be nested, so `military -> brigades -> 225` is represented without hard-coded template branches;
- thermochromic remains authoritative on `ProductColorVariant.is_thermo`/Fable 5 color details and is never duplicated in free text.

Fits, size grids, price, and stock continue to use the existing `ProductFitOption`, `variant_public_context()`, Fable 5 size-grid services, and inventory rules. The selector must never infer sellability from a size guide row alone.

### Routes and landing pages

The first collection route is `/merch/225/`, localized by the existing language routing convention. It is a `CollectionPage` with:

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
- Replacing the existing product card, checkout, or payment flow.
- Assigning invented audience/size/stock values where production data is missing.
- Creating indexable pages for every arbitrary filter combination.

## Acceptance

The slice is accepted when the focused Django/JavaScript tests pass, the Fable 5 editor can save and reload multi-select audience tags, all three category routes and `/merch/225/` work in Ukrainian/Russian/English, mobile and desktop browser checks pass at 320/375/430/768/1024/1440 widths, LCP/CLS and accessibility budgets are measured, and live SEO output contains only truthful canonical/schema/indexation states.
