# Google Merchant Auto-Tagging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Accept Google Merchant auto-tagged landings without 404 and retain accurate free-listing attribution through product and order analytics.

**Architecture:** A shared attribution-query contract feeds catalog validation, first-touch capture, durable UTM storage, order context, admin reporting, and SEO noise handling. Merchant and canonical URLs remain clean; inbound tokens are captured without becoming content identity.

**Tech Stack:** Django 5.2, Django ORM/migrations, Django TestCase, XML Merchant feeds, custom admin analytics.

---

### Task 1: Lock The Routing And Attribution Contract

**Files:**
- Modify: `twocomms/storefront/tests/test_prod002_catalog_color_canonicalization.py`
- Modify: `twocomms/storefront/tests/test_utm_normalization.py`

1. Add failing catalog tests for `srsltid` and redirect preservation.
2. Add failing tests for `google / organic` inference and durable storage.
3. Run both modules with `DJANGO_SETTINGS_MODULE=test_settings`.
4. Confirm failures are caused by the missing allowlist entry and model field.

### Task 2: Centralize Google And Platform Identifiers

**Files:**
- Modify: `twocomms/storefront/utm_utils.py`
- Modify: `twocomms/storefront/tracking.py`
- Modify: `twocomms/storefront/utm_middleware.py`
- Modify: `twocomms/storefront/views/catalog.py`

1. Define shared UTM, click-ID, and tracking-query constants.
2. Include `srsltid`, `gbraid`, and `wbraid` in first-touch capture.
3. Infer `srsltid` as `google / organic` and paid Google IDs as
   `google / cpc` without overriding explicit UTM attribution.
4. Strictly validate catalog-owned keys while accepting opaque external keys;
   exclude all external keys from cache and SEO identity.
5. Run the RED tests and confirm they move to the persistence failure only.

### Task 3: Persist And Expose Durable Attribution

**Files:**
- Modify: `twocomms/storefront/models.py`
- Create: `twocomms/storefront/migrations/0093_utm_click_ids.py`
- Modify: `twocomms/storefront/utm_middleware.py`
- Modify: `twocomms/storefront/utm_tracking.py`
- Modify: `twocomms/storefront/views/admin_analytics_extras.py`
- Modify: `twocomms/storefront/utm_api_views.py`
- Modify: `twocomms/storefront/services/admin_analytics.py`

1. Add bounded, indexed Google identifier fields to `UTMSession`.
2. Store them on create and fill missing first-touch values on later linking.
3. Restore them when rebuilding attribution during checkout.
4. Include them in order tracking context without changing Meta behavior.
5. Expose identifiers and `google_free_listings` classification in custom
   admin session/acquisition data.
6. Run attribution and admin analytics tests.

### Task 4: Protect Canonical And Merchant Identities

**Files:**
- Modify: `twocomms/storefront/views/static_pages.py`
- Modify: `twocomms/storefront/tests/test_seo_regressions.py`
- Modify: `twocomms/storefront/tests/test_marketplace_feeds.py`

1. Add `srsltid`, `gbraid`, and `wbraid` query-noise patterns to robots.
2. Assert canonical output excludes inbound tracking parameters.
3. Assert V3 `g:link` values are query-free canonical variant URLs.
4. Keep tracking parameters on legitimate product variant redirects.

### Task 5: Verify, Publish, And Deploy

**Files:**
- Verify only; stage only files from Tasks 1-4 and these plan documents.

1. Run focused routing, UTM, analytics, SEO, and feed tests.
2. Run Django system checks and migration checks.
3. Generate Google V3 locally and validate IDs and links.
4. Commit the scoped change to `main` and push `origin/main`.
5. Deploy with the supplied SSH command and run migrations/feed regeneration
   when required by the deployed change.
6. Verify the deployed SHA, three localized `srsltid` catalog URLs, canonical
   output, feed aliases, item counts, and every unique V3 product link.
