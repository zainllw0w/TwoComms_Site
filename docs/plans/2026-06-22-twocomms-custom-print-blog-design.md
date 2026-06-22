# TwoComms Custom Print Blog Design

## Goal

Publish ten Ukrainian/Russian custom-print blog articles as conversion-oriented post-landings on the main TwoComms storefront blog, with reusable editor blocks, indexable routes, FAQ schema, and internal linking to `/custom-print/`, catalog categories, cooperation, size, and care pages.

## Current State

- The main site blog is implemented in `storefront`, not `dtf`.
- Production currently has one published blog article and several mostly empty categories.
- Empty blog categories render `noindex, follow` and are excluded from the blog sitemap until they contain published posts.
- Blog posts already support `django-modeltranslation` fields for UA/RU/EN copy and SEO fields.
- `BlogPostBlock` already supports localized rich text, CTA groups, metric cards, tables, images, galleries, videos, callouts, source lists, product CTA, promo blocks, and FAQ.

## Chosen Approach

Use the existing block system instead of adding a new page model or storing every article as a single HTML blob.

Add a small reusable publication layer:

- an idempotent management command that creates/updates the ten articles and their blocks;
- deterministic slugs, categories, SEO fields, internal links, and FAQ blocks;
- lightweight CSS classes for post-landing sections that can also be reused from the editor;
- tests that verify publication, rendering, indexing signals, localization, CTA links, and schema.

## Content Architecture

All articles follow the same strategic structure, but each article keeps its own intent, title, headings, FAQ, table/checklist, and internal links:

1. Hero copy through post title, excerpt, cover alt/caption, and an opening `rich_text` block.
2. Two early CTA buttons: ready file and idea-only path.
3. Fear-removal cards through `metric_cards`.
4. Usage scenarios through `rich_text` card grids.
5. Ordering process through `metric_cards` or `rich_text` steps.
6. Topic-specific SEO/AIO section with H2/H3, definitions, table or checklist.
7. "Як це робить TwoComms" proof block.
8. FAQ block with `FAQPage` schema.
9. Internal link CTA/source list block for related articles and commercial pages.
10. Final CTA back to the custom-print flow or cooperation page.

## Category Plan

Create or reuse a blog category for custom-print guides under the existing guide knowledge area:

- `guides` remains the parent informational category.
- `custom-print-guides` becomes the child category for the ten new articles.

This keeps commercial print content separate from brand news and product reviews while still letting the parent guide category become indexable.

## Visual Design

The articles should feel like compact landing pages, not classic SEO walls:

- high-contrast dark editorial style consistent with the existing blog;
- orange/blue accents already present in blog CTA and metric blocks;
- card grids for fears, scenarios, ideas, and steps;
- dense but readable tables for technical topics;
- sticky mobile-safe CTA behavior via existing CTA blocks;
- no decorative blobs or unrelated abstract hero art.

Generated cover images can be added after the content publish command. The command should work without generated images so production publication is not blocked by image generation.

## SEO And Indexing

- Each post is published with `is_published=True` and `published_at <= now`.
- The blog post route emits `index, follow` through the default `base.html` robots block.
- Category pages become indexable automatically once posts exist.
- Blog sitemap already includes published posts and non-empty categories with i18n alternates.
- FAQ schema comes from visible FAQ blocks only.
- H1 is the post title; rich text sanitizer removes any accidental H1 in content blocks.

## Safety

- Do not touch `dtf`.
- Do not store deploy secrets.
- Keep staff-only view counters unchanged.
- The management command must be safe to rerun and should update the same slugs rather than creating duplicates.
- Keep schema changes out unless there is a clear need; the existing block payload JSON is enough.

