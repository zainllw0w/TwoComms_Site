# Implementation Plan: Color-Category Landing Pages — Tasks

**Spec:** color-category-landings
**Status:** code-complete; awaiting content team to draft and publish landings
**Last updated:** 2026-05-15

## Overview

Implementation of indexable colour×category SEO landing pages
(`/catalog/<cat_slug>/<color_slug>/`). All code, routing, sitemap, IndexNow
signals and tests are merged. Until the content team manually publishes
a `CategoryColorLanding` row, every URL of this shape returns 404 — so
the deploy is content-gated and zero-risk.

## Tasks

### Phase 0: Spec
- [x] T0.1 Create `requirements.md`
- [x] T0.2 Create `design.md`
- [x] T0.3 Create `tasks.md`

### Phase 1: Data model + admin
- [x] T1.1 Add `CategoryColorLanding` to `storefront/models.py`
- [x] T1.2 Migration `0061_categorycolorlanding`
- [x] T1.3 Anti-thin `clean()` validator (≥800 chars when published)
- [x] T1.4 Auto-derive `color_slug` in `save()` and `full_clean()`
- [x] T1.5 Admin registration with character counter
- [x] T1.6 Tests: `test_color_category_landing_model.py` (9 cases)

### Phase 2: View + routing
- [x] T2.1 Add `category_color_landing` view to `storefront/views/catalog.py`
- [x] T2.2 Wire URL pattern `catalog_by_cat_color` in `storefront/urls.py`
- [x] T2.3 404 guards (unpublished, zero products, inactive category)
- [x] T2.4 Canonical, hreflang, OG fields, `@graph` schema
- [x] T2.5 Tests: `test_color_category_landing_view.py` (11 cases)

### Phase 3: Template
- [x] T3.1 Create `pages/category_color_landing.html`
- [x] T3.2 Breadcrumbs, H1, editorial copy, product grid, FAQ, internal links
- [x] T3.3 `@graph` structured data: `BreadcrumbList`, `CollectionPage`, `FAQPage`
- [x] T3.4 Reuse `partials/product_card.html`
- [x] T3.5 Mobile-responsive inline styles

### Phase 4: Sitemap + IndexNow
- [x] T4.1 Add `CategoryColorLandingSitemap` to `storefront/sitemaps.py`
- [x] T4.2 Add `sitemap_section_color_categories` view
- [x] T4.3 Register `/sitemap-color-categories.xml` in sitemap-index
- [x] T4.4 IndexNow signal on `is_published=True` (+ delete + slug change)
- [x] T4.5 Tests: `test_color_category_landing_sitemap.py` (3 cases)

### Phase 5: Internal linking
- [x] T5.1 Update `build_available_colors` to swap `?color=` URLs for
  landing URLs when a published landing exists for `(category, slug)`.
- [ ] T5.2 Footer category links: surface 1-2 top colour landings per
  category (deferred — depends on what content team publishes)
- [x] T5.3 Existing `test_phase9_color_filter` regression suite green

### Phase 6: Seed content (CONTENT TEAM)
- [ ] T6.1 Draft editorial copy for 9 launches (≥250 words each + 4 FAQ)
- [ ] T6.2 Manual entry via Django admin (instead of data migration)
- [ ] T6.3 Manual review checklist for content team

### Phase 7: Deploy
- [x] T7.1 Run targeted test suite (60 spec + 28 regression — all green)
- [x] T7.2 Commit + push
- [x] T7.3 Deploy to server (git pull, migrate, cache clear, restart)
- [ ] T7.4 Verify 404 on unpublished landings (post-deploy smoke check)
- [ ] T7.5 Verify sitemap-index references the new section
- [ ] T7.6 Content team publishes 1-2 landings → verify production
  rendering, structured-data validator, IndexNow ping

### Phase 8: Post-launch
- [ ] T8.1 Monitor Search Console for new URL pattern: 0 thin / 0 broken warnings
- [ ] T8.2 Track impressions / clicks at 30 / 60 / 90 days post-launch
- [ ] T8.3 If a landing fails to attract impressions: review copy, internal
  linking, or unpublish

## Notes

- Seed content was deliberately deferred from automation to manual admin
  entry per user direction. The data migration approach would have
  baked editorial copy into git history; admin entry keeps copy editable
  by non-developers.
- Phase 5.2 (footer cross-links) is best implemented after at least 3
  landings ship, so the footer can highlight the top performers.
- All anti-thin guards remain active: a published landing without ≥800
  chars of editorial copy will fail `full_clean()` in admin.

## Task Dependency Graph

```
Phase 0 (spec)
  └── Phase 1 (model + admin + migration)
        └── Phase 2 (view + routing)
        │     └── Phase 3 (template)
        │           └── Phase 4 (sitemap + IndexNow)
        │                 └── Phase 5 (internal linking)
        │                       └── Phase 7 (deploy)
        │                             └── Phase 6 (content team publishes)
        │                                   └── Phase 8 (post-launch monitoring)
```
