# Catalog Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the public catalog landing view with a dark TwoComms streetwear scene closely matching the supplied reference while keeping category/product links, SEO metadata, and stable layout.

**Architecture:** Keep the change presentation-first: Django view adds a small static showcase-card payload from existing categories; the template renders the hero, CTA panel, category showcase, filters, and existing product grid. New generated raster assets live under theme static files as optimized WebP, and a page-specific CSS file owns the visual system to avoid bloating global CSS.

**Tech Stack:** Django templates/views, static WebP assets, page-specific CSS, existing Inter font and static/compress/collectstatic pipeline.

---

### Task 1: Assets

**Files:**
- Create: `twocomms/twocomms_django_theme/static/img/catalog/catalog-hero.webp`
- Create: `twocomms/twocomms_django_theme/static/img/catalog/catalog-longsleeves.webp`
- Create: `twocomms/twocomms_django_theme/static/img/catalog/catalog-tshirts.webp`
- Create: `twocomms/twocomms_django_theme/static/img/catalog/catalog-hoodies.webp`

- [x] Generate dark catalog hero and three category product-card images with TwoComms branding.
- [x] Copy selected outputs into the project.
- [x] Convert to WebP and remove large copied PNG sources.

### Task 2: View Payload

**Files:**
- Modify: `twocomms/storefront/views/catalog.py`

- [ ] Add a private `CATALOG_SHOWCASE_CARD_CONFIG` constant for the three visual cards.
- [ ] Add a helper that matches existing production categories by slug/name tokens and builds safe fallback links.
- [ ] Count published products for matched categories without changing models or database state.
- [ ] Pass `catalog_showcase_cards` only on the root catalog view.

### Task 3: Template

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/pages/catalog.html`

- [ ] Keep title/description/canonical/pagination/JSON-LD blocks intact.
- [ ] Replace the root catalog visual section with a full-bleed dark hero, custom breadcrumb, CTA panel, filter rail, and three showcase cards.
- [ ] Keep category links visible for SEO/discoverability and keep product-grid rendering on category/search pages.
- [ ] Use code-native text for headings, buttons, links, and structured content.

### Task 4: CSS

**Files:**
- Create: `twocomms/twocomms_django_theme/static/css/catalog-redesign.css`

- [ ] Implement stable dimensions, aspect ratios, responsive breakpoints, and reduced-motion behavior.
- [ ] Add smoke/haze animation that degrades under `prefers-reduced-motion` and existing `effects-lite/perf-lite` modes.
- [ ] Keep text readable and prevent mobile overflow/CLS.

### Task 5: Verification, Commit, Deploy

**Files:**
- Verify only; no code file ownership.

- [ ] Run targeted Django checks/tests.
- [ ] Run static lookup/collectstatic dry run.
- [ ] Run browser visual checks on desktop and mobile.
- [ ] Commit focused changes.
- [ ] Deploy through existing project deploy flow and run post-deploy catalog smoke checks.
