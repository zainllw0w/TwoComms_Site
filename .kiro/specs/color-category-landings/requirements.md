# Color-Category Landing Pages — Requirements

**Date:** 2026-05-15  
**Site:** https://twocomms.shop  
**Owner:** SEO + content team  
**Spec status:** draft

## Why

The TwoComms catalogue currently exposes one landing page per top-level category (`/catalog/tshirts/`, `/catalog/hoodie/`, `/catalog/long-sleeve/`). Real Ukrainian search demand differentiates by colour:

| Query | Monthly volume (estimate) | Current ranking |
|-------|---------------------------|-----------------|
| «чорні футболки» | ~3,500 | not ranked (no dedicated page) |
| «чорне худі streetwear» | ~900 | not ranked |
| «біла футболка з принтом» | ~1,200 | not ranked |
| «худі хакі чоловіче» | ~600 | not ranked |

Competitors (AAC.com.ua, Modna, Hood.ua) capture these queries by serving indexable URLs at `/category/colour/` with editorial copy, structured data, and sub-product grids. TwoComms currently throws a 404 for any URL of that shape.

## What

Create indexable landing pages of the form **`/catalog/<cat_slug>/<color_slug>/`** for a curated set of colour × category combinations (top 5–7 anchor colours per category, ~15–21 pages total at launch).

Each landing page must carry:

1. Unique editorial copy (≥200 words, written by content team — **not** auto-generated).
2. Unique `<title>`, `<h1>`, `meta description`, structured-data graph.
3. A product grid filtered to the matching `(category, colour)` slice.
4. Colour-specific FAQ (4–6 entries) addressing pairing, occasion, care.
5. Internal linking to the parent category, sibling colours of the same category, and the same colour in other categories.
6. Sitemap inclusion via a dedicated `sitemap-color-categories.xml` sub-sitemap.
7. IndexNow notification on publish/unpublish.

## User stories

### US-1 — Visitor (organic)
*As a Ukrainian shopper searching for «чорні футболки з принтом»,*  
I want to land on a TwoComms page that explains the brand's range of black tees, shows me the matching products, and gives me confidence to buy,  
**so that** I do not bounce back to a generic catalogue.

**Acceptance:**
- Page returns HTTP 200 with `<title>` containing both the colour and the category name.
- Editorial paragraph reads as human-written prose, not a templated mash-up.
- At least three product cards visible above the fold (mobile / desktop).
- Breadcrumbs: `Головна › Каталог › <Category> › <Colour>` are clickable.

### US-2 — Visitor (returning)
*As a returning customer,*  
I want the colour chips on the parent category page to take me to the dedicated colour landing when one exists,  
**so that** I can deep-link / bookmark / share without losing context.

**Acceptance:**
- On `/catalog/tshirts/` the colour chip "чорний" links to `/catalog/tshirts/black/` (when a landing is published).
- When no landing exists for that colour, the chip falls back to `/catalog/tshirts/?color=black` (current behaviour).

### US-3 — Content manager
*As a content manager,*  
I want to draft and publish landing pages from the Django admin without touching code,  
**so that** I can iterate on copy and ship new colour landings without a deploy.

**Acceptance:**
- `CategoryColorLanding` is exposed in the admin.
- The form includes: category dropdown, colour dropdown, editorial body (rich-text optional, but plain HTML is acceptable v1), SEO fields, FAQ JSON.
- A landing with `is_published=False` returns 404 to anonymous traffic and is excluded from the sitemap.
- A landing with editorial copy below the anti-thin threshold cannot be published from the form (validation error).

### US-4 — Search engine
*As Googlebot,*  
I want the landing pages to be discoverable, canonicalised, and machine-readable,  
**so that** I can rank them for narrow long-tail intents.

**Acceptance:**
- The page emits `rel="canonical"` to itself.
- The page is listed in the XML sitemap (under a section named `sitemap-color-categories.xml`).
- Structured data: `BreadcrumbList`, `CollectionPage`, optional `FAQPage` — all in a single `@graph` block.
- An IndexNow ping fires when `is_published` flips from `False` to `True`.

## Edge cases

| Case | Expected behaviour |
|------|--------------------|
| Landing unpublished | 404 (not 301 / not soft-fallback) |
| Landing published but zero matching products | 404 (matching products are required to avoid empty grids in the SERP) |
| `color_slug` invalid (no Colour with that English slug) | 404 |
| Colour name has multiple components (e.g. «чорний + білий») | Slug derived from `english_slug_for_color_name` joining tokens with `-` (existing behaviour) |
| RU/EN locale | The page renders but emits `noindex, follow` (consistent with the rest of the storefront's i18n policy) |
| `?color=other` in query while on a landing | Ignore the query parameter; the URL slug wins. Canonical still points to landing's clean URL. |
| Product goes out of stock | The card stays visible (matches `/catalog/`'s OOS policy) |

## Anti-thin-content guards

1. `editorial_html` must be ≥800 characters (~200 words); otherwise the model raises a `ValidationError` on save when `is_published=True` is requested.
2. The landing is excluded from the sitemap when published-but-thin — defensive belt-and-braces.
3. The sitemap entry is also excluded when there are zero matching live products at the moment the sitemap is rendered.

## Out of scope (for v1)

- Auto-generation of editorial copy.
- Cross-language `hreflang` for RU/EN colour landings (RU/EN copy isn't translated yet for the rest of the site).
- Sub-colour facets like `/catalog/tshirts/black/oversize/` (would create combinatorial explosion; revisit later).
- Size-specific landings (no organic demand).

## Success metrics (90 days post-launch)

- ≥5 colour landings ranking in Google top 50 for their primary keyword (Search Console).
- 0 broken-page warnings in Search Console for the new URL pattern.
- 0 thin-content warnings.
- Average bounce rate on landings within 10% of `/catalog/tshirts/` baseline.
