# Catalog Assets And Product Cards

## Goal

Refresh the catalog showcase images from the user-provided PNG sources and make product listing cards in catalog/category/search pages reuse the same visual component as the homepage product grid.

## Scope

- Convert `newCatalog/*.png` into the existing tracked WebP assets in `twocomms/twocomms_django_theme/static/img/catalog/`.
- Keep the user source PNG files untracked.
- Load the homepage product card styles on catalog pages and render catalog products with `home_card=True`.
- Preserve existing SEO metadata, structured data, pagination, and fragment caching behavior.

## Verification

- Add a regression test for catalog category product-card markup.
- Run targeted Django tests and checks.
- Run `collectstatic --dry-run`.
- Inspect local and production pages with browser screenshots after deployment.
