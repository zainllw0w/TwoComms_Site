# Evidence Log (DTF Re-baseline)

## Git / branch
- Branch: `codex/dtf-p0p1-fixes-2026-02`
- Local commits pushed:
  - `74f84f8` (`fix(dtf): complete p1 hero optimization and contrast token`)
  - `2c05731` (`fix(dtf): enable touch lens modal on home page`)
  - `864ec13` (`fix(dtf): restore mobile order autolayout and remove overlay conflicts`)
  - `64d947f` (`fix(dtf): bust template asset cache for mobile layout updates`)
- Server HEAD after deploy: `64d947f`

## Local validation
- `SECRET_KEY=test-secret-key-123 python3 twocomms/manage.py check` -> `System check identified no issues (0 silenced).`
- `python3 twocomms/manage.py test dtf --settings=test_settings` -> `Ran 16 tests ... OK`

## What is covered by tests
- DTF P0 routes (`/quality/`, `/price/`, `/prices/` redirect)
- DTF `robots.txt`/`sitemap.xml` host correctness
- DTF upload security (size/ext/mime/magic + safe naming)
- DTF vs main host isolation for robots/sitemap
- DTF landing renders DTF template markers/assets
- DTF hero uses responsive AVIF/WebP sources with preload/fetchpriority
- DTF home touch-lens fallback modal exists and opens on tap
- DTF `/order/` mobile layout no longer uses fixed overlay summary and hides FAB on order page
- DTF base template adds asset version query params to avoid stale client-side cache

## Production deploy output summary
- `git pull` updated `be59420..74f84f8`, `74f84f8..2c05731`, `a77c67c..864ec13`, `864ec13..64d947f`
- `python manage.py check` -> no issues
- `python manage.py migrate --noinput` -> no migrations to apply
- `python manage.py collectstatic --noinput` -> completed
- Passenger restart trigger: `tmp/restart.txt`

## Production smoke (2026-02-06)
### Status codes
- `https://dtf.twocomms.shop/` -> 200
- `https://dtf.twocomms.shop/quality/` -> 200
- `https://dtf.twocomms.shop/price/` -> 200
- `https://dtf.twocomms.shop/prices/` -> 301 (`Location: /price/`)
- `https://dtf.twocomms.shop/robots.txt` -> 200
- `https://dtf.twocomms.shop/sitemap.xml` -> 200
- `https://twocomms.shop/` -> 200
- `https://twocomms.shop/robots.txt` -> 200
- `https://twocomms.shop/sitemap.xml` -> 200

### Host/template isolation assertions
- `dtf_home_has_dtf_css=yes`
- `dtf_home_has_logo_mark=yes`
- `main_home_has_dtf_css=no`
- `main_home_has_logo_mark=no`
- `dtf_home_has_lens_modal=yes`
- `dtf_home_has_hero_avif_sources=yes`
- `dtf_order_uses_versioned_css_js=yes`

### Robots assertions
- DTF: `Sitemap: https://dtf.twocomms.shop/sitemap.xml`
- Main: `Sitemap: https://twocomms.shop/sitemap.xml`

### Sitemap assertions
- DTF sitemap contains DTF host URLs and no main host URLs
- Main sitemap contains main host URLs and no DTF host URLs

### Feed endpoints guard
- Main: `/google_merchant_feed.xml` -> 200, `/prom-feed.xml` -> 200
- DTF: `/google_merchant_feed.xml` -> 404, `/prom-feed.xml` -> 404 (expected for isolated DTF urlconf)
