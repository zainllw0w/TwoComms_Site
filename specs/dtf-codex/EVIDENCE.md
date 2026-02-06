# Evidence Log (DTF Re-baseline)

## Git / branch
- Branch: `codex/dtf-p0p1-fixes-2026-02`
- Local commit pushed: `21ef640` (`fix(dtf): rebaseline dtf-only p0/p1 and verify isolation`)
- Server HEAD after deploy: `21ef640`

## Local validation
- `python3 manage.py check --settings=test_settings` -> `System check identified no issues (0 silenced).`
- `python3 manage.py test dtf --settings=test_settings` -> `Ran 15 tests ... OK`

## What is covered by tests
- DTF P0 routes (`/quality/`, `/price/`, `/prices/` redirect)
- DTF `robots.txt`/`sitemap.xml` host correctness
- DTF upload security (size/ext/mime/magic + safe naming)
- DTF vs main host isolation for robots/sitemap
- DTF landing renders DTF template markers/assets

## Production deploy output summary
- `git pull` updated `90aed2b..21ef640`
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

### Robots assertions
- DTF: `Sitemap: https://dtf.twocomms.shop/sitemap.xml`
- Main: `Sitemap: https://twocomms.shop/sitemap.xml`

### Sitemap assertions
- DTF sitemap contains DTF host URLs and no main host URLs
- Main sitemap contains main host URLs and no DTF host URLs

### Feed endpoints guard
- Main: `/google_merchant_feed.xml` -> 200, `/prom-feed.xml` -> 200
- DTF: `/google_merchant_feed.xml` -> 404, `/prom-feed.xml` -> 404 (expected for isolated DTF urlconf)
