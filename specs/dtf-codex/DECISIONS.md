# Decision Log

## 2026-02-05

### D-001: Execute against real repository topology
- Decision: Implement prompt goals against actual code layout, not assumed `urls_dtf.py` + `dtf.urls` sources.
- Why: Discovery showed `twocomms/twocomms/urls_dtf.py` source is absent (only stale `.pyc`), and `/quality`, `/price`, `/prices` are currently unresolved in active `ROOT_URLCONF`.
- Evidence: `resolve('/quality/')`, `resolve('/price/')`, `resolve('/prices/')` -> 404 under `test_settings`.

### D-002: Keep changes minimal and local to storefront static routes/tests first
- Decision: Add minimal endpoints and tests in `storefront` modules used by current URL stack.
- Why: Lowest risk path to close P0 without introducing new app/router architecture.
- Evidence: `twocomms/twocomms/urls.py` includes `storefront.urls`; static pages already centralized in `storefront/views/static_pages.py`.

### D-003: Host-aware SEO output over hardcoded domain
- Decision: Build `robots.txt` and `sitemap.xml` using request host/scheme.
- Why: Current sitemap classes set `domain = 'twocomms.shop'`, which is incorrect for DTF host isolation.
- Evidence: `twocomms/storefront/sitemaps.py` contains hardcoded domain.

### D-004: Upload security baseline without new binary dependencies
- Decision: Use Django/Pillow/native checks (size, extension allowlist, MIME/content sniff via image decode) before considering `python-magic`.
- Why: No confirmed hosting support for extra system libs in this iteration.
- Risk: Non-image file validation may remain best-effort where only extension/MIME is available.

### D-005: Build sitemap XML manually for strict host isolation
- Decision: Generate `sitemap.xml` directly in `static_sitemap` using `request.get_host()`.
- Why: Django sitemap + Site framework returned `example.com` in tests, which violates DTF host isolation requirement.
- Evidence: failing test before fix showed `<loc>https://example.com/...`.

### D-006: Apply contrast fix via dedicated override stylesheet
- Decision: Add `static/css/dtf-fixes.css` with token `--c-molten-onlight` and targeted overrides instead of rewriting the large generated stylesheet.
- Why: Minimal-risk patch with clear rollback path and no purge/minify rebuild dependency.

### D-007: Fix Google Merchant feed by loading legacy handler directly
- Decision: Replace recursive `from storefront import views` call with explicit loader from `storefront/views.py.backup` and guarded fallback XML response.
- Why: Current implementation recursively calls itself via package export and causes production `500` on `/google_merchant_feed.xml`.
- Evidence: production traceback showed `RecursionError` in `storefront/views/static_pages.py` before fix.

### D-008: Restore `/checkout/` as compatibility route
- Decision: Re-enable `/checkout/` route and bind it to `checkout_view` (redirect to cart).
- Why: Regression guard includes `/checkout/`; current production returned 404. Redirect preserves current cart-integrated checkout flow with minimal risk.
- Evidence: added smoke test `test_checkout_redirects_to_cart` and production check `302 -> /cart/`.
