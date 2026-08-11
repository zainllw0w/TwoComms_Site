# Product Catalog integration design

## Goal

Install the supplied Product Catalog Django application as a staff-only product editor while preserving the existing product editor and public storefront behavior.

## Scope

- Add the `product_catalog` app, its initial migration, templates, JavaScript, CSS, template tags, admin registrations, and service helpers.
- Register the app in `INSTALLED_APPS` and mount its unprefixed staff routes.
- Keep the old editor, public product templates, feed generators, Storage integration, and Telegram integration unchanged. Those remain Phase 2.
- Correct only defects demonstrated during integration review, with regression coverage.

## Data and deployment

Product Catalog owns new `product_catalog_*` tables and references existing product and color tables through foreign keys. Production MySQL is the source of truth, so schema changes are applied only after the commit reaches `origin/main`. Deployment uses a fast-forward pull, migration, Django check, static collection, offline compression, Passenger restart, and authenticated server-side route checks.

## Safety and verification

All editor and JSON endpoints remain staff-only and CSRF-protected. JSON embedded into the editor page must use Django's safe JSON-script mechanism. Tests cover anonymous access, staff rendering with hostile text, migration consistency, and core create/update behavior. Existing unrelated working-tree changes and the unpacked archive are excluded from staging.
