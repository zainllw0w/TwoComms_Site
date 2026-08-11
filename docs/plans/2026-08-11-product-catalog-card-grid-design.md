# Product Catalog Card Grid Design

## Objective

Restore the useful visual-card model of the custom catalog admin while keeping the current canonical Product Catalog backend, compact actions, indexing state, taxonomy hierarchy, and drag-and-drop contracts. The result is a dark desktop operations workspace aligned with the management UI: dense enough for hundreds of products, visually calm, and immediately scannable.

This is a presentation and interaction refinement. It does not replace the renamed editor, change product/category URLs, reintroduce any Fable 5 runtime identity, or alter persistence semantics.

## Visual Direction

Use one dark operational surface with graphite panels, restrained violet and amber accents, thin borders, and shallow elevation. Avoid light-theme fallbacks, oversized decorative cards, saturated gradients, and long text buttons. Motion communicates state: hover lift is subtle, drag lift is stronger, drop targets pulse once, and save/index transitions do not resize controls.

Typography follows the management workspace: compact labels, readable product names, tabular metric values, and zero negative letter spacing. Cards use a maximum 8px radius.

## Product Grid

At a 1440px desktop viewport the product list uses four equal columns. At narrower desktop widths it may reduce to three or two columns so content never overlaps; mobile-specific redesign is out of scope.

Each product card contains only decision-relevant information:

- a stable portrait image area with a small order badge and drag handle overlay;
- product name, garment category, price, and publication state;
- four compact icon metrics for colors, photos, total views, and unique visitors;
- optional featured/points indicators only when present;
- a compact status selector;
- small IndexNow and Google controls with idle, pending, accepted, and error states;
- icon-only edit and delete actions with labels, titles, and keyboard focus.

The image is the primary visual anchor. Names clamp to two lines; metric labels are exposed through tooltips and accessible labels rather than long visible text. The action footer has fixed-height controls so long status text cannot squeeze edit/delete buttons.

The existing products-grid, product-card, data-product-id, data-order-position, data-drag-handle, reorder endpoint, keyboard arrows, and save-state behavior remain canonical.

## Drag And Drop

Dragging starts only from the dedicated handle. The lifted card keeps its original dimensions; a same-size placeholder preserves the four-column grid. Nearby cards animate into their new cells using the existing FLIP behavior. The target receives a restrained amber outline, and the card settles without a layout jump.

Keyboard reordering remains available from the handle. Pointer and keyboard paths call the same order persistence logic. Search filtering must not silently reorder hidden products.

## Garment Categories

Garment categories use three equal columns at desktop width. Each card shows its icon or cover, name, URL slug, product count, order, indexing controls, and icon-only edit/delete actions. Cards remain visually related to product cards but use a wider landscape composition and less height.

The category block stays distinct from merchandising taxonomy. T-shirts, hoodies, longsleeves, and future garment types are not parents of military, streetwear, or brigades.

## Merchandising Taxonomy

The taxonomy manager remains above garment categories, but becomes a compact hierarchy board rather than one long undifferentiated list. Root nodes use three desktop columns where space permits. Each root panel contains its immediate children as compact nested rows, so 225 and 127 are visibly inside brigades.

Every node retains icon/cover preview, localized name, path, product/child counts, SEO readiness, reorder, edit, archive/restore, arbitrary depth, and keyboard focus. 225 and 127 derive brigades; military remains fully manual and is never inferred.

## Editor Main Tab

The Основне tab uses a balanced twelve-column desktop composition. Назва та адреса and Комерція та публікація receive equal visual weight. Аудиторія and Теми та підкатегорії align as equal-height working panels when content permits. The Storage artwork picker forms a regular grid below them.

This layout preserves the current active-first-tab behavior, audience/taxonomy contracts, canonical Storage print imagery, autosave/dirty state, and all existing form field identifiers.

## Scale And Loading

The initial product surface renders in batches of up to 48 cards. Search and filters operate on the authoritative catalog set; further batches load without shifting existing cards. Long-distance reordering may use a compact move action in addition to drag-and-drop, but the current release keeps the existing order endpoint and DnD behavior intact unless scale testing proves a backend change is required.

## Accessibility And States

All icon-only controls have aria-label and title. Focus rings are visible on the dark surface. Accepted indexing uses a check, pending uses a non-layout-shifting spinner, and error uses an alert mark. Empty, filtered-empty, saving, drag, failed-save, and reduced-motion states remain explicit.

## Verification

Release requires:

- template contract tests for four-column products, three-column categories, icon metrics, accessible actions, and preserved DnD hooks;
- JavaScript tests for reorder behavior and state transitions;
- focused Django tests for catalog context, taxonomy, audience, editor, and cross-category collection visibility;
- browser QA at 1280x900 and 1440x1000 with no horizontal overflow, overlap, clipped controls, or light surfaces;
- visual review against the management workspace;
- final variant-image live-preview and progress verification after the main catalog/editor UI is stable;
- production MariaDB schema-adoption, migration, backup, engine, and data-backfill gates before deployment.

