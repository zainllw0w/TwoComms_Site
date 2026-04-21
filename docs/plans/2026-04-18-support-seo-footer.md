# Support SEO Footer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a premium SEO-oriented footer, new informational support pages, sitemap coverage, and mobile navigation fixes for the main `twocomms.shop` storefront.

**Architecture:** Build a reusable support-page rendering layer in `storefront.views.static_pages`, expose new named routes in `storefront.urls`, surface them through a redesigned footer, and add minimal targeted JS/CSS changes for mobile pagination and bottom navigation. Keep DTF subdomain code untouched.

**Tech Stack:** Django 5.2, Django templates, existing `twocomms_django_theme`, targeted JS module updates, static CSS.

---

### Task 1: Lock the expected behavior with tests

**Files:**
- Modify: `twocomms/storefront/tests/test_static_support_pages.py`

**Step 1: Keep support/navigation tests isolated from broken project migrations**

Use `SimpleTestCase`, `Client`, `RequestFactory`, and patch product/category sitemap querysets.

**Step 2: Verify tests fail for the intended reasons**

Run: `DEBUG=1 SECRET_KEY=test /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test storefront.tests.test_static_support_pages -v 2 --settings=twocomms.settings`

Expected: missing route names, missing footer links, missing sitemap entries, mobile profile toggle still present.

### Task 2: Add reusable support-page data and views

**Files:**
- Modify: `twocomms/storefront/views/static_pages.py`
- Modify: `twocomms/storefront/views/__init__.py`

**Step 1: Add reusable support page configuration**

Create a shared content map for `dopomoga`, `faq`, `rozmirna-sitka`, `doglyad-za-odyagom`, `vidstezhennya-zamovlennya`, `mapa-saytu`, `news`, `returns`, `privacy_policy`, `terms_of_service`.

**Step 2: Add a generic renderer helper**

Return a consistent template context with SEO meta, feature stats, sections, quick links, FAQ data, and CTA blocks.

**Step 3: Expand `static_sitemap` support coverage**

Include all new informational routes alongside existing static routes before dynamic product/category entries.

### Task 3: Expose new routes

**Files:**
- Modify: `twocomms/storefront/urls.py`

**Step 1: Register named routes for every new support page**

Add new paths for help, FAQ, size guide, care, tracking, site map, news, returns, privacy, and terms.

### Task 4: Build the shared support template system

**Files:**
- Create: `twocomms/twocomms_django_theme/templates/pages/support_page.html`
- Create: `twocomms/twocomms_django_theme/templates/pages/legal_page.html`
- Create: `twocomms/twocomms_django_theme/static/css/support-hub.css`
- Modify: `twocomms/twocomms_django_theme/templates/base.html`

**Step 1: Create a premium reusable support page layout**

Add poster-like hero, section rails, internal-link chips, FAQ blocks, CTA band, and legal prose support.

**Step 2: Load the new CSS globally**

Include `support-hub.css` in the base stylesheet bundle so footer and support pages share the same styling system.

### Task 5: Redesign the footer and mobile navigation

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/partials/footer.html`
- Modify: `twocomms/twocomms_django_theme/templates/partials/header.html`
- Modify: `twocomms/twocomms_django_theme/static/css/styles.css`

**Step 1: Replace the old footer with a multi-zone SEO footer**

Add brand block, icon-based social links, quick actions, featured FAQ/internal links, and a compact sitemap cluster.

**Step 2: Remove the mobile avatar entry**

Replace the profile item in the mobile bottom nav with a support/help action.

### Task 6: Fix homepage mobile pagination

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/pages/index.html`
- Modify: `twocomms/twocomms_django_theme/static/js/modules/homepage.js`

**Step 1: Make pagination rail safe on narrow screens**

Use start-aligned horizontal scrolling, safe-area paddings, snap behavior, and smaller nav widths on mobile.

**Step 2: Keep the active page visible after updates**

Scroll the active pagination item into view after initialization and after “load more”.

### Task 7: Verify locally, then finalize and deploy

**Files:**
- Verify only

**Step 1: Run targeted tests**

Run the support-page test module again and confirm green.

**Step 2: Run a local browser check**

Open the homepage and support pages, verify footer, mobile bottom nav, and pagination at phone widths.

**Step 3: Commit, push, deploy, and post-deploy verify**

Only after tests and UI checks pass.
