# DTF Codex Checklist

## Execution
- [x] `P0` `CODEX` Create spec folder and baseline docs (`specs/dtf-codex/*`) | Evidence: created files in repo
- [x] `P0` `CODEX` Fix `/quality/` route and template rendering (`GET /quality/ -> 200`) | Evidence: Django test `test_quality_page_returns_200`
- [x] `P0` `CODEX` Add `/price/` route and fix `/prices/` to 301 redirect | Evidence: Django tests `test_price_page_returns_200`, `test_prices_redirects_to_price`
- [x] `P0` `CODEX` Make `robots.txt` DTF-safe (sitemap host from request, no hardcoded main domain) | Evidence: Django test `test_robots_points_to_current_host_sitemap`
- [x] `P0` `CODEX` Make `sitemap.xml` host-aware and include `/price/` | Evidence: Django test `test_sitemap_uses_request_host_and_contains_price`
- [x] `P0` `CODEX` Fix `google_merchant_feed.xml` recursion 500 | Evidence: Django test `test_google_merchant_feed_is_not_server_error`; prod URL check `200`
- [x] `P1` `CODEX` Improve hero/LCP image delivery (preload/fetchpriority/srcset/sizes where missing) | Evidence: `templates/pages/index.html` updates for hero + featured image loading policy
- [x] `P1` `CODEX` Accessibility fix for accent-on-light contrast (AA target) | Evidence: `static/css/dtf-fixes.css` token `--c-molten-onlight` + usage overrides
- [x] `P1` `CODEX` Fix sticky overlap on order/cart flow for narrow screens | Evidence: `static/css/dtf-fixes.css` mobile sticky overrides
- [x] `P1` `CODEX` Add server-side upload validation (size/ext/mime/magic + safe naming policy where applicable) | Evidence: `storefront/upload_security.py` + `test_upload_security.py`
- [x] `P0` `CODEX` Restore `/checkout/` compatibility route (to cart) | Evidence: Django test `test_checkout_redirects_to_cart`; prod URL check `302 -> /cart/`
- [ ] `P2` `CODEX` Cleanup only proven dead code | Evidence: grep/test proof
- [x] `P0` `CODEX` Deploy + verify URLs on production | Evidence: `DEPLOY.md` + prod smoke outputs in `EVIDENCE.md`

## Regression Guard
- [x] Do not break `/`, `/catalog/`, `/product/<slug>/`, `/cart/`, `/checkout/` | Evidence: prod smoke `200/302` for both hosts
- [ ] Do not break admin add/edit product flows
- [x] Do not break Google feed endpoints (`/google_merchant_feed.xml`, `/prom-feed.xml`) | Evidence: prod smoke `200` for both hosts
- [ ] Keep reduced-motion behavior intact

## Open Questions (Blockers Only)
- [x] Production SSH access/credentials obtained; docroot `robots.txt` + `sitemap.xml` moved to backup and verified.
