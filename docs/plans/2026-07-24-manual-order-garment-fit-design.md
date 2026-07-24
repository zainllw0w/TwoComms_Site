# Manual Order Garment Fit Design

## Goal

Make manual order creation and editing preserve the selected garment fit, show thermochromic variants clearly, and preselect the correct warehouse blank for each order line.

## Production Findings

- `OrderItem` already stores `fit_option_code` and `fit_option_label`.
- Manual-order backend already resolves a product default fit, but both admin UIs omit fit data from their payloads. Editing therefore recreates the line and loses its original fit.
- Production has 31 non-archived T-shirt products. Normal products expose `classic` and `oversize`; product 110 is thermo and allows only `oversize`.
- Production warehouse T-shirt families are:
  - `crc-classic-101` for current classic blanks;
  - `oversize-erc` for current oversize blanks;
  - `termo` for thermochromic blanks.
- `VariantBlankLink` is the existing authoritative color+fit to warehouse-family mapping, but production currently has zero links.
- Nova Poshta already builds the shipment description from the sum of `OrderItem.qty`; two garments become `у кількості 2 шт.`.

## Data Model

Do not add a second garment-type field. Fit remains `classic` or `oversize` on `OrderItem`. Thermo remains a property of the selected color through `ColorProfile.is_thermo`, because it is a material/color characteristic rather than a fit.

Use `VariantBlankLink` as the warehouse routing table:

- normal color + `classic` -> `crc-classic-101`;
- normal color + `oversize` -> `oversize-erc`;
- thermo color + allowed fit -> `termo`.

The backfill must preserve existing explicit links, support dry-run, and be idempotent.

## Manual Order UI

Each catalog line receives a compact `Посадка` selector. The product payload includes active fits, default fit, fit-specific sizes, variant-specific allowed fit codes, thermo metadata, and authoritative color+fit prices.

Changing the color normalizes the selected fit to an allowed value. A thermo color shows a `Термотканина` marker and automatically selects its sole allowed fit. Changing color or fit refreshes the suggested catalog price and valid sizes; managers can still override the price afterward.

The same behavior is implemented in both the full manual-create page and the existing order edit drawer. Existing orders round-trip their stored fit instead of defaulting back to classic.

## Server Validation

The server validates that the selected fit belongs to the product and is allowed for the selected color. Missing fit keeps backward compatibility by selecting the first valid default. Invalid posted color+fit combinations return a human-readable 422 response.

## Warehouse Write-Off

The matcher first follows `VariantBlankLink` and then applies size/color matching within that blank family. The write-off page continues showing the full warehouse list for manual correction. Candidate ranking must not leave a wrong family selected when an exact linked family exists.

## Safety

- No Telegram source changes.
- No live TTN creation or live stock write-off during verification.
- Existing explicit warehouse links are never overwritten by the backfill command.
- No schema change is required for order fit storage.

## Verification

- Create two same-size lines for one product, one classic and one oversize, and assert both remain distinct.
- Edit an existing order and assert fit round-trips.
- Reject a thermo variant with classic fit and auto-select oversize in the UI payload.
- Assert warehouse matching resolves classic, oversize, and thermo to their linked subcategories.
- Assert the backfill is dry-run safe, idempotent, and preserves explicit links.
- Assert Nova Poshta description reports a total quantity of two.
