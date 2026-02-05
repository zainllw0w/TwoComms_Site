# Evidence Log

## Discovery Snapshot
- Current branch: `codex/dtf-p0p1-fixes-2026-02`
- URL stack:
  - `ROOT_URLCONF = twocomms.urls` (`twocomms/twocomms/settings.py`)
  - Root routes include `path("", include("storefront.urls"))` (`twocomms/twocomms/urls.py`)
  - `robots.txt` routed to `storefront_views.robots_txt`
  - `sitemap.xml` routed to `storefront_views.static_sitemap`
- Missing/404 routes (before fixes): `/quality/`, `/price/`, `/prices/`, `/checkout/`, `/order/`
- Existing `.pyc` indicates historical `urls_dtf.py` existed but source file is absent:
  - `twocomms/twocomms/__pycache__/urls_dtf.cpython-313.pyc`
  - Disassembly shows include of `dtf.urls`, but no source in repo.

## Commands Run
- `python3 twocomms/manage.py shell --settings=test_settings -c "...resolve(...)"` confirmed:
  - `/quality/ -> 404`
  - `/price/ -> 404`
  - `/prices/ -> 404`
  - `/robots.txt -> robots_txt`
  - `/sitemap.xml -> django.contrib.sitemaps.views.sitemap` (route name)

## Notes
- Production infra changes for docroot-level `robots.txt` and `sitemap.xml` are completed and documented in `DEPLOY.md`.
- Branch pushed: `origin/codex/dtf-p0p1-fixes-2026-02`
- Suggested PR URL: `https://github.com/zainllw0w/TwoComms_Site/pull/new/codex/dtf-p0p1-fixes-2026-02`
- `gh` CLI is unavailable in this environment, so PR was not opened automatically.

## Implemented P0 Changes
- Added routes in `twocomms/storefront/urls.py`:
  - `/quality/` (`quality`)
  - `/price/` (`price`)
  - `/prices/` (301 redirect to `/price/`)
  - `/checkout/` (302 redirect to `/cart/` via `checkout_view`)
- Added new template:
  - `twocomms/twocomms_django_theme/templates/pages/quality.html`
- Updated static views:
  - `robots_txt` now writes sitemap using current request host/scheme.
  - `static_sitemap` now generates XML directly with current host and includes `/price/`.
  - `google_merchant_feed` now loads legacy handler from `views.py.backup` safely (no recursive self-call).
- Updated exports/imports:
  - `twocomms/storefront/views/__init__.py` exports `quality` and `price`.
- Updated sitemap static entries:
  - `twocomms/storefront/sitemaps.py` static items include `price`.
- Updated production host allowlist:
  - `twocomms/twocomms/production_settings.py` now always includes `dtf.twocomms.shop` in `ALLOWED_HOSTS` and CSRF trusted origins.

## Test Results
- `python3 twocomms/manage.py test storefront.tests.test_dtf_p0 --settings=test_settings` -> **OK (6/6)**
- `python3 twocomms/manage.py test storefront.tests.test_upload_security --settings=test_settings` -> **OK (4/4)**
- `python3 twocomms/manage.py test storefront.tests.test_feed_endpoints --settings=test_settings` -> **OK (2/2)**
- `python3 twocomms/manage.py test storefront.tests.test_dtf_p0 storefront.tests.test_upload_security storefront.tests.test_feed_endpoints --settings=test_settings` -> **OK (12/12)**
- `python3 twocomms/manage.py check --settings=test_settings` -> **System check identified no issues**
- `python3 twocomms/manage.py test dtf --settings=test_settings` -> **fails** because `dtf` is an incomplete namespace package in this repo (no source test module / `__file__`).

## Production Verification
- Docroot override files no longer present:
  - `/home/qlknpodo/public_html/robots.txt` -> absent
  - `/home/qlknpodo/public_html/sitemap.xml` -> absent
  - backups exist in `/home/qlknpodo/public_html/_backup/20260206-012836/`
- Final smoke (`twocomms.shop` and `dtf.twocomms.shop`):
  - `/`, `/catalog/`, `/product/clasic-tshort/`, `/quality/`, `/price/`, `/cart/` -> **200**
  - `/prices/` -> **301** to `/price/`
  - `/checkout/` -> **302** to `/cart/`
  - `/robots.txt`, `/sitemap.xml`, `/google_merchant_feed.xml`, `/prom-feed.xml` -> **200**
- Admin route smoke (unauthenticated):
  - `/admin-panel/`, `/admin-panel/product/new/`, `/admin-panel/product/1/edit/` -> **302** to login (no `404/500`)
- Host isolation checks:
  - `robots.txt` sitemap line is host-specific for each domain.
  - `sitemap.xml` `<loc>` values use the requested host (`twocomms.shop` vs `dtf.twocomms.shop`).
- Reduced-motion guard:
  - `prefers-reduced-motion` media queries still present in active CSS (`styles.css`, `styles.min.css`, `styles.direct.css`).

## P1 Implementation Evidence
- Performance:
  - `twocomms/twocomms_django_theme/templates/pages/index.html`
    - hero logo switched to `decoding="async"` and explicit `sizes`
    - featured image switched to `loading='lazy'` and `fetchpriority='low'` with `sizes`
- Accessibility + Sticky:
  - `twocomms/twocomms_django_theme/static/css/dtf-fixes.css`
    - token `--c-molten-onlight`
    - high-contrast overrides for accent text on light surfaces
    - mobile sticky overrides for cart/order summary blocks
  - `twocomms/twocomms_django_theme/templates/base.html`
    - direct include of `css/dtf-fixes.css`
- Upload security:
  - `twocomms/storefront/upload_security.py`
  - Integrated into:
    - `twocomms/storefront/forms.py`
    - `twocomms/storefront/views/auth.py`
    - `twocomms/orders/forms.py`

## Commits
- `d5dffae` docs(dtf): initialize execution checklist and evidence log
- `b2df90e` fix(dtf): add quality/price routes and host-aware seo endpoints
- `00622c2` security: validate and normalize uploaded image files
- `c6ecf91` perf(a11y): optimize above-fold media and fix accent/sticky issues
- `8c37e2a` docs(dtf): record test results, branch push, and commit evidence
- `dbc136f` Allow dtf subdomain in production hosts and CSRF origins
- `b52ff31` fix(feed): stop google merchant recursion and add feed smoke tests
- `941891a` fix(routing): restore checkout alias and cover with smoke test
