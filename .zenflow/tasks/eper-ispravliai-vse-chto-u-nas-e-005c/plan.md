# SEO improvements — VILNI_AUDIT_DEEP_REVIEW_2026-05-19 implementation

## Context
Implement all reasonable SEO fixes from `SEO/analysis/VILNI_AUDIT_DEEP_REVIEW_2026-05-19.md`.
Skip items the codebase already covers (verified by exploration):
- `dateModified` / `releaseDate` on Product schema — present (`seo_utils.py:853`).
- `OfferShippingDetails` on Offer — present (`seo_utils.py:849`).
- `hasMerchantReturnPolicy` on Offer — present (`seo_utils.py:837`).
- `hasVariant` array on base Product — present (`seo_utils.py:1066`).
- Preconnect to GTM / FB / TikTok — present (`base.html:223-225`).
- `og_locale_for_lang` returns `uk_UA`/`ru_RU`/`en_US`, `hreflang` already `xx-UA` reciprocal.
- `_homepage_price_range_text()` helper exists and used on `/`.

Focus on what's truly missing or wrong.

### [x] Step 1: /contacts/ ClothingStore — remove `₴₴`, drop fake store addresses, unify sameAs
- Replace `"priceRange": "₴₴"` with dynamic helper output passed from `contacts` view.
- Remove placeholder store cards (Хрещатик 22 Київ / Соборний 15 Львів) — Vilni-missed conflicting NAP signal.
- Replace hardcoded `sameAs` list with full curated list from `_organization_same_as()`.

### [x] Step 2: Organization schema — `hasMerchantReturnPolicy` + `hasMemberProgram` at Organization level
- Add Organization-level `MerchantReturnPolicy` (Google Merchant docs).
- Add `MemberProgram` describing TWOCOMMS Бали (Google loyalty schema).

### [x] Step 3: PDP — emit `ProductGroup` alongside base `Product` in @graph
- Added `generate_product_group_schema()` in `seo_utils.py` with `productGroupID`, `variesBy`, `hasVariant` refs by stable `@id`.
- `product_graph` template tag now emits the ProductGroup node next to the base Product on canonical PDP (no variant URL).

### [x] Step 4: Offer — add `deliveryLeadTime` (3-5 days) for `MadeToOrder`
- `deliveryLeadTime` QuantitativeValue (3-5 DAY) added to Offer in `generate_product_schema`.

### [x] Step 5: variant_meta.py — index 2-segment color+fit URLs (self-canonical)
- `is_color_fit_combo` branch sets self-canonical for `/product/<slug>/<color>/<fit>/`.
- Dedicated title/description for the combo page.
- `ProductVariantSitemap` now emits the 2-segment combos for discovery.

### [x] Step 6: PDP titles for low-CTR "бентежне" products
- `SEOKeywordGenerator.generate_meta_title` returns «Принт «Бентежне» — {category} | TwoComms» for `bentejne-*` slugs (only when `seo_title` is empty).

### [x] Step 7: Extend llms.txt with commerce-intent facts
- Added Commerce facts (currency, price range, payment methods, shipping window, lead time, return policy, loyalty), Brand mission/signature line, and Reviews policy.

### [x] Step 8: Django check + commit + push + deploy
- `python manage.py check` — System check identified no issues.
- Commit `c0b1c813` pushed to `origin/main`.
- SSH deploy executed: `git pull` fast-forwarded prod from `f1ed2849` to `c0b1c813`.
