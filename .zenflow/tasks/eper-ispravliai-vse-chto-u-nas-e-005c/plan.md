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

### [ ] Step 3: PDP — wrap Product into `ProductGroup` with `productGroupID`, `variesBy`, full `hasVariant`
- Extend `generate_product_schema` to emit `ProductGroup` when variants exist (color/fit/size).
- Each variant a full `Product` with `sku`, `color`, `size`, `image`, `url`, `offers`.

### [ ] Step 4: Offer — add `deliveryLeadTime` (3-5 days) for `MadeToOrder`
- Append `deliveryLeadTime` `QuantitativeValue` to `Offer` payload to clarify lead time alongside `MadeToOrder` availability.

### [ ] Step 5: variant_meta.py — index 2-segment color+fit URLs (self-canonical)
- When `segments_count == 2` and both `color_slug` + `fit_code` present (no `size_code`), set `is_self_canonical = True` and `canonical_path = current_path`.
- Generate richer title/description for the color+fit combination.

### [ ] Step 6: PDP titles for low-CTR "бентежне" products
- For products whose slug starts with `bentejne-`, prefer a clearer commercial title pattern in `pages/product_detail.html` SEO fallback / `seo_title` helper — emphasize «Принт «Бентежне» — {category} | TwoComms» so SERP recovery is possible (audit §13.13 Recovery math: +13 clicks/28d).

### [ ] Step 7: Extend llms.txt with commerce-intent facts
- Add pricing range, shipping window, founding info, mission, signature line, custom-print lead time, and reviews/AggregateRating policy. Pulled from audit §5.6.

### [ ] Step 8: Django check + commit + push + deploy
- Run `python manage.py check` to ensure no syntax/runtime errors.
- Commit, push to origin, then SSH deploy `git pull` on prod.
