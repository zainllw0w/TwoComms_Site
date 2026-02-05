# DTF Codex Checklist

## Execution
- [x] `P0` `CODEX` Create spec folder and baseline docs (`specs/dtf-codex/*`) | Evidence: created files in repo
- [x] `P0` `CODEX` Fix `/quality/` route and template rendering (`GET /quality/ -> 200`) | Evidence: Django test `test_quality_page_returns_200`
- [x] `P0` `CODEX` Add `/price/` route and fix `/prices/` to 301 redirect | Evidence: Django tests `test_price_page_returns_200`, `test_prices_redirects_to_price`
- [x] `P0` `CODEX` Make `robots.txt` DTF-safe (sitemap host from request, no hardcoded main domain) | Evidence: Django test `test_robots_points_to_current_host_sitemap`
- [x] `P0` `CODEX` Make `sitemap.xml` host-aware and include `/price/` | Evidence: Django test `test_sitemap_uses_request_host_and_contains_price`
- [x] `P1` `CODEX` Improve hero/LCP image delivery (preload/fetchpriority/srcset/sizes where missing) | Evidence: `templates/pages/index.html` updates for hero + featured image loading policy
- [x] `P1` `CODEX` Accessibility fix for accent-on-light contrast (AA target) | Evidence: `static/css/dtf-fixes.css` token `--c-molten-onlight` + usage overrides
- [x] `P1` `CODEX` Fix sticky overlap on order/cart flow for narrow screens | Evidence: `static/css/dtf-fixes.css` mobile sticky overrides
- [x] `P1` `CODEX` Add server-side upload validation (size/ext/mime/magic + safe naming policy where applicable) | Evidence: `storefront/upload_security.py` + `test_upload_security.py`
- [ ] `P2` `CODEX` Cleanup only proven dead code | Evidence: grep/test proof
- [ ] `P0` `CODEX` Deploy + verify URLs on production | Evidence: deploy log/commands in `DEPLOY.md`

## Regression Guard
- [ ] Do not break `/`, `/catalog/`, `/product/<slug>/`, `/cart/`, `/checkout/`
- [ ] Do not break admin add/edit product flows
- [ ] Do not break Google feed endpoints (`/google_merchant_feed.xml`, `/prom-feed.xml`)
- [ ] Keep reduced-motion behavior intact

## Open Questions (Blockers Only)
- [ ] Production SSH access details and credentials are not available in this session, so live infra move of docroot `robots.txt`/`sitemap.xml` is blocked.
