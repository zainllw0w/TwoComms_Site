# Product Catalog Taxonomy Priority Design

## Objective

Finish the product-editor redesign around the two workflows that matter most:

1. selecting audience and merchandising hierarchy in the `Основне` tab;
2. managing that hierarchy compactly above the garment categories in the custom admin catalog.

The existing renamed editor remains the implementation base. This is a focused refinement, not another editor rewrite. Previously discovered rename, migration, MySQL, print-preview, indexing, and image-job defects remain release blockers and must be closed before deployment.

## Taxonomy Contract

Garment categories and merchandising taxonomy remain separate concepts:

- Garment category: T-shirt, hoodie, longsleeve, and future product types.
- Top-level merchandising nodes: `military`, `streetwear`, `brigades`, and future peers.
- Brigade children: `225`, `127`, and future brigade-specific nodes.

Selecting `225` or `127` automatically exposes and checks `brigades` as a derived parent. The parent is not stored redundantly when a child is stored. Public filtering and editor bootstrap resolve the effective chain from the selected leaf.

`military` is always manual. Selecting `225`, `127`, or `brigades` must never select `military`. A product may independently belong to `military`, `streetwear`, both, or neither.

## Audience Contract

`unisex` is the canonical persisted assignment. In catalog filtering it effectively matches `unisex`, `men`, and `women`. In the editor, choosing `unisex` visibly checks and locks the derived `men` and `women` states without persisting redundant assignments.

An explicit `women` or `men` assignment remains untouched unless an administrator changes it. Production backfill adds `unisex` only to products that currently have no audience assignment.

## Editor Layout

The `Основне` tab keeps a dense desktop layout:

- Garment category remains near product identity because it defines the product type.
- Audience uses three compact selectable tiles. Derived states are visually distinct and explain why they are active.
- Merchandising taxonomy uses grouped rows rather than one undifferentiated list: top-level themes are immediately scannable, and children are shown directly under their parent.
- Selected leaf assignments are summarized compactly. Derived parents are visible but cannot be removed while their child remains selected.
- The hierarchy must remain usable with future children without hard-coding only `225` and `127`.

The existing print picker stays in `Основне`, but it is not part of this priority refinement beyond preserving its canonical Storage artwork behavior.

## Custom Admin Layout

The taxonomy manager sits above the garment-category and product lists. It is a compact tree, not a grid of oversized cards.

Each row shows an icon/PNG preview, localized name, hierarchy path, child/product counts, SEO readiness, and small icon actions for reorder, edit, and archive. Add/edit opens one focused dialog with parent selection, localized content, icon/cover upload, SEO fields, indexability, and active state.

The manager supports arbitrary parent-child depth, blocks cycles, and prevents archiving a node with active children. Garment categories remain a separate block below it.

## Production Data

The production MariaDB snapshot currently has 74 non-archived products: 31 already assigned `unisex`, 43 without audience assignments, and no current `women-only` assignment. The backfill must still preserve any explicit `women` or `men` rows to remain correct if production changes before deployment.

The two current `225` products are `225-tshirt` and `225-hoodie`. They receive the `225` leaf assignment. `brigades` is derived through the taxonomy; `military` is not modified.

All backfill operations are dry-run by default, idempotent, row-counted, and applied only after the product-catalog schema adoption has completed on MariaDB.

## Deferred Image Workflow

Variant-color image upload remains required but is the last implementation priority. It must show the uploaded image immediately without a page reload and then display upload, WebP, AVIF, responsive derivative, save, verification, retry, cancel, and terminal error states on the image itself.

## Release Gates

Deployment is blocked until:

- the former editor identity is absent from runtime routes, templates, static assets, and visible labels;
- schema adoption preserves all 35 populated legacy editor tables and metadata on MariaDB;
- external MyISAM relations remain `db_constraint=False`;
- audience and taxonomy contracts pass focused tests;
- production backfill dry-run exactly matches the reviewed rows;
- desktop browser QA passes for `Основне`, taxonomy admin, product cards, indexing controls, drag-and-drop, and finally variant image upload;
- previously found upload-job, polling, recovery, and migration defects remain covered and passing.
