# Evidence Log

## Discovery Snapshot
- Current branch: `codex/dtf-p0p1-fixes-2026-02`
- URL stack:
  - `ROOT_URLCONF = twocomms.urls` (`twocomms/twocomms/settings.py`)
  - Root routes include `path("", include("storefront.urls"))` (`twocomms/twocomms/urls.py`)
  - `robots.txt` routed to `storefront_views.robots_txt`
  - `sitemap.xml` routed to `storefront_views.static_sitemap`
- Missing/404 routes (before fixes): `/quality/`, `/price/`, `/prices/`, `/order/`
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
- Production infra changes for docroot-level `robots.txt` and `sitemap.xml` are documented in `DEPLOY.md` and blocked pending SSH access.

## Implemented P0 Changes
- Added routes in `twocomms/storefront/urls.py`:
  - `/quality/` (`quality`)
  - `/price/` (`price`)
  - `/prices/` (301 redirect to `/price/`)
- Added new template:
  - `twocomms/twocomms_django_theme/templates/pages/quality.html`
- Updated static views:
  - `robots_txt` now writes sitemap using current request host/scheme.
  - `static_sitemap` now generates XML directly with current host and includes `/price/`.
- Updated exports/imports:
  - `twocomms/storefront/views/__init__.py` exports `quality` and `price`.
- Updated sitemap static entries:
  - `twocomms/storefront/sitemaps.py` static items include `price`.

## Test Results
- `python3 twocomms/manage.py test storefront.tests.test_dtf_p0 --settings=test_settings` -> **OK (5/5)**
- `python3 twocomms/manage.py test storefront.tests.test_upload_security --settings=test_settings` -> **OK (4/4)**
- `python3 twocomms/manage.py test storefront.tests.test_dtf_p0 storefront.tests.test_upload_security --settings=test_settings` -> **OK (9/9)**
- `python3 twocomms/manage.py check --settings=test_settings` -> **System check identified no issues**
- `python3 twocomms/manage.py test dtf --settings=test_settings` -> **fails** because `dtf` is an incomplete namespace package in this repo (no source test module / `__file__`).

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
