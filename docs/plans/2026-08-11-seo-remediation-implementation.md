# TwoComms SEO/GEO Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** ship the production-backed SEO/GEO remediation from the 2026-08-10 audit in dependency order, with every completed slice proven after deploy.

**Architecture:** Establish URL ownership first, then route all metadata, schema, feeds, sitemaps and internal links through shared eligibility/locale/fact resolvers. Keep UI-only facets and selectors usable while allowing only evidence-backed clean landings and variant URLs into the indexable graph.

**Tech Stack:** Django 5 storefront, Python 3.14 production virtualenv, Django templates, JSON-LD/schema.org, XML sitemaps/merchant feeds, existing test suite and Playwright/crawl scripts.

**Baseline:** Focused category SEO tests on `c6d82593` run 2026-08-11: 21 tests, 3 pre-existing failures in synthetic top-menu expectations (`test_phase10b_seo_layout.py`), 18 passing. These failures are recorded and must not be silently attributed to SEO remediation.

**Per-task release protocol:**

1. Write a failing regression test and run it (RED).
2. Implement the smallest scoped fix and run focused plus regression tests (GREEN).
3. Run `manage.py check`, `git diff --check`, and the task's static/browser/crawl gate.
4. Commit the code/test slice with the task still marked `[ ]` for deployment.
5. Push the exact commit to `origin/main`; deploy production with the repository release gate; prove deployed SHA and live behavior.
6. Mark the task `[x]` with commit/SHA/evidence links, commit that checklist update, push and deploy the documentation checkpoint, then continue.

## Priority and dependency checklist

### Task 1: Eliminate linked 404 destinations without touching Custom Print behavior

- [ ] **1.1** Verify the 24 numeric IDs and `/catalog/custom-print/` against the current production DB and backlink/history data; classify each as exact published successor, stale removable row, or unresolved (unresolved stays open). Confirm `/custom-print/`, `/ru/custom-print/` and `/en/custom-print/` owners before changing links.
- [ ] **1.2** Add failing service/template tests proving published `extra.product_id` rows render a locale-aware current slug URL and authoritative live price, missing/draft references render no link, and `/catalog/custom-print/` normalizes to the matching-locale custom-print owner.
- [ ] **1.3** Implement URL and price resolution in `twocomms/storefront/services/category_seo_blocks.py` plus the category SEO partial; do not change the Custom Print configurator view/template/state or create blanket numeric redirects.
- [ ] **1.4** Run `storefront.tests.test_phase10_category_seo_blocks`, `storefront.tests.test_phase10b_seo_layout`, and a rendered category-link assertion for UK/RU/EN.
- [ ] **1.5** Commit, push, deploy and live-crawl. Record the deployed SHA, 0 linked 404, `/custom-print/` 200 self-canonical, and no change to the configurator browser smoke.
- [ ] **1.6** Commit/push/deploy this checklist evidence and only then mark **Task 1 complete**.

**Files:** `twocomms/storefront/services/category_seo_blocks.py`; `twocomms/storefront/tests/test_phase10_category_seo_blocks.py`; add a focused regression module only if the existing test boundary cannot express URL normalization. No data migration until DB mapping proves it is required.

### Task 2: Establish and enforce the approved variant URL allowlist

- [ ] **2.1** Produce a versioned inventory of 210 variant URLs with product, color, fit, size, stock, media, locale, demand placeholder and proposed owner.
- [ ] **2.2** Add failing tests for approved versus UI-only combinations, stable segment order, invalid/empty combinations and no Cartesian-product sitemap emission.
- [ ] **2.3** Implement one shared resolver used by `views/product.py`, `services/variant_meta.py`, variant sitemap and internal-link helpers. Preserve Custom Print and existing checkout selection behavior.
- [ ] **2.4** Define redirect/canonical behavior for removed variants only after owner mapping; do not mass-301 to a category or base product.
- [ ] **2.5** Run sitemap, canonical, hreflang and Playwright preselection checks for representative color-only, fit-only, color×fit and size URLs.
- [ ] **2.6** Commit, push, deploy, live-verify and then mark Task 2 `[x]` in a docs checkpoint commit.

**Files:** `twocomms/storefront/views/product.py`; `twocomms/storefront/services/variant_meta.py`; sitemap modules; product templates/tests; production inventory evidence under `output/seo-audit-2026-08-10/`.

### Task 3: Make RU/EN publication and structured data genuinely localized

- [ ] **3.1** Add a rendered locale matrix test that fails on Ukrainian fallback in RU/EN visible H1/body/meta/alt/aria/JSON-LD, except approved proper nouns.
- [ ] **3.2** Fix locale-aware URL builders and fallback policy for categories, color landings, PDPs, pro-brand OfferCatalog and FAQ.
- [ ] **3.3** Remove query/noindex alternates from noindex facet pages while preserving full reciprocal self-inclusive hreflang on indexable owners.
- [ ] **3.4** Verify translated fields for the six products with missing RU/EN data; keep them consolidated or non-indexable until editorial data exists.
- [ ] **3.5** Run locale HTML/schema/sitemap checks and browser language-switch checks, then commit/push/deploy and record evidence before checking Task 3.

**Files:** locale helpers/base template; `catalog.html`, color landing and product templates; `seo_utils.py`; localized tests and sitemap tests.

### Task 4: Replace contradictory PDP boilerplate with one fact-owned editorial block

- [ ] **4.1** Add failing tests for exactly one rendered PDP SEO editorial block, deduplicated FAQ questions, and no service-only keyword sentence in visible content.
- [ ] **4.2** Create a versioned fact registry contract (owner, source field/URL, locale, effective date) for material, weight, print method, wash durability, fit, care, delivery threshold, founding date, donation and location.
- [ ] **4.3** Remove/merge the second generated block; keep product-specific facts and preserve Custom Print links/flow unchanged.
- [ ] **4.4** Deduplicate FAQ at the data/render/schema boundary; retain global policy answers once and product-specific answers only when materially different.
- [ ] **4.5** Run fact-lint across PDP HTML, JSON-LD, feeds, llms and checkout copy; commit/push/deploy and mark Task 4 only after live parity proof.

**Files:** `twocomms/storefront/views/product.py`; `seo_utils.py`; `services/product_seo_landing.py`; PDP templates; FAQ models/services/tests; fact-registry docs/tests.

### Task 5: Normalize facets and pagination by route family

- [ ] **5.1** Add failing tests for `page=1` one-hop redirects on home/category/locale routes, page>=2 self-canonical, and invalid/empty combinations returning 404. Correct the crawler fixture/utility to resolve relative hrefs against the source final URL before trusting route-level inlink counts.
- [ ] **5.2** Remove SEO hreflang from noindex facets and stop editorial rails from linking to noindex query states.
- [ ] **5.3** Make grey/olive filter exceptions intentional: either approved clean landing owners or UI-only noindex/follow; do not leave index/follow plus non-self canonical.
- [ ] **5.4** Ensure page>=2 does not render the full page-1 SEO boilerplate; preserve distinct product lists and pagination discoverability.
- [ ] **5.4a** Measure anonymous cache-key cardinality and catalog query timing for clean, valid facet, invalid facet and page>=2 requests; reject the release if UX selectors regress or invalid 200 aliases still populate cache.
- [ ] **5.5** Run parameter crawl and Search Console sampling, commit/push/deploy, and check Task 5 after live evidence.

**Files:** catalog views/templates, pagination/canonical helpers, `general_catalog_seo.py`, `color_seo_copy.py`, robots/hreflang helpers and tests.

### Task 6: Link only approved clean landings in matching locale

- [ ] **6.1** Add failing tests for same-locale category → color/fit landing links and absence of editorial links to UI-only query facets.
- [ ] **6.2** Implement locale-aware landing URL builders and an allowlist-backed internal-link helper; keep Smart Selector/query state operational.
- [ ] **6.3** Verify every approved landing has inventory, unique copy, media, schema/feed support and at least one same-locale category link before sitemap inclusion.
- [ ] **6.4** Commit/push/deploy and mark Task 6 after crawl/browser proof.

**Files:** `services/color_seo_copy.py`, `services/general_catalog_seo.py`, Smart Selector helpers, category/color landing templates/tests.

### Task 7: Complete variant media, alt text and fit data

- [ ] **7.1** Add data-quality tests that fail when an indexable variant lacks matching media, localized alt, sellable rows or measurements.
- [ ] **7.2** Backfill only verified production assets/measurements; do not invent classic/oversize photos or claim a color image that does not exist.
- [ ] **7.3** Hide or consolidate unsupported fit states while retaining the working selector for valid UI states.
- [ ] **7.4** Run representative mobile/desktop browser checks and schema/media audits; commit/push/deploy and check Task 7.

**Files:** variant/media models and assignment services; PDP gallery/alt helpers/templates; focused data-quality tests and reviewed admin/backfill command.

### Task 8: Align ProductGroup, MemberProgram, Offer counts and merchant feeds

- [ ] **8.1** Add failing tests that compare homepage `offerCount`, sitemap, feed and eligible public products from one queryset/snapshot.
- [ ] **8.2** Implement the shared public eligibility predicate and variant resolver in schema, feeds and llms generation.
- [ ] **8.3** Replace unsupported `MemberProgramTierBenefit` with documented truthful enumeration plus `membershipPointsEarned`, or remove MemberProgram until the business rule is verified.
- [ ] **8.4** Make selected variant schema/feed URLs, images, price and availability agree with the rendered page and canonical policy.
- [ ] **8.5** Run Rich Results/Schema Validator checks and feed parsers, then commit/push/deploy and mark Task 8.

**Files:** `twocomms/storefront/seo_utils.py`; ProductGroup/Offer schema builders; merchant feed modules; llms generator; tests and validator evidence.

### Task 9: Correct mobile filter state and performance bottlenecks

- [ ] **9.1** Add failing browser/JS tests for a clean URL showing filter badge `0` and for back/forward state transitions.
- [ ] **9.2** Fix state derivation without changing catalog availability or analytics contracts; preserve Custom Print.
- [ ] **9.3** Run three sequential mobile Lighthouse traces per representative catalog/PDP URL and record median/p75; do not call lab opportunities a field ranking penalty.
- [ ] **9.4** Obtain dated CrUX/GSC/RUM evidence where available, then commit/push/deploy and mark Task 9.

**Files:** catalog filter JS/templates/styles; Lighthouse runner and browser tests; no real ad/purchase test events.

### Task 10: GEO/AI factuality and monitoring contract

- [ ] **10.1** Add a fact/entity registry test covering founding date, delivery threshold, address/hours, donation and price range across visible text, schema, feeds and llms.
- [ ] **10.2** Remove unverified ClothingStore coordinates/hours and conflicting founding/entity claims unless the business owner supplies current evidence.
- [ ] **10.3** Replace request-time `dateModified=now()` with source `updated_at` and localize pro-brand OfferCatalog URLs.
- [ ] **10.4** Create a monthly UK/RU/EN query/citation ledger with date, country, device, model/search engine, cited URL and factuality result; no promise of citation boost.
- [ ] **10.5** Commit/push/deploy and mark Task 10 only after the monitoring baseline is reproducible.

**Files:** entity/schema helpers, pro-brand template, llms/robots generators, governance docs, monitoring script/tests.

## Final release gate

- [ ] Full sitemap + one-hop crawl has 0 linked 404 and no unintended SEO redirect chains.
- [ ] All sitemap URLs are approved owners with 200, indexability and self-canonical.
- [ ] RU/EN visible content and JSON-LD are locale-correct; hreflang is reciprocal and self-inclusive.
- [ ] Variant selected state, media, metadata, schema and feed agree.
- [ ] Facts are single-source and no duplicate/contradictory PDP blocks remain.
- [ ] Mobile purchase path, cart, analytics and Custom Print browser smoke pass.
- [ ] GSC/CrUX/RUM limitations and residual risks are recorded; no ranking-growth claim is made without measurement.
