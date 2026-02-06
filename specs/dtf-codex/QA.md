# QA Checklist (DTF backlog re-run)

## Automated checks
- [x] `DJANGO_SETTINGS_MODULE=test_settings python3 manage.py check`
- [x] `DJANGO_SETTINGS_MODULE=test_settings python3 manage.py test dtf.tests --keepdb`
- [x] `DJANGO_SETTINGS_MODULE=test_settings python3 manage.py compilemessages -l uk -l ru -l en`

## Regression test map (`dtf.tests`)
- [x] `/quality/` returns 200
- [x] `/price/` returns 200
- [x] `/prices/` redirects 301 to `/price/`
- [x] `/robots.txt` points to DTF sitemap and excludes main host sitemap
- [x] `/sitemap.xml` returns DTF-host URLs and includes `/price/`
- [x] DTF legal pages (`/privacy/`, `/terms/`, `/returns/`, `/requisites/`) return 200
- [x] Upload security rejects invalid payloads and renames valid uploads safely
- [x] DTF/main host isolation checks for robots and sitemap
- [x] Home hero responsive assets/preload/fetchpriority are present
- [x] EN language switch works and sets `dtf_lang=en`
- [x] Hot Peel old spinner asset is absent (`hot-peel.gif` not rendered)

## Manual checks performed (pre-deploy baseline)
- [x] `curl -I https://dtf.twocomms.shop/quality/` => 200
- [x] `curl -I https://dtf.twocomms.shop/price/` => 200
- [x] `curl -I https://dtf.twocomms.shop/prices/` => 301 + `Location: /price/`
- [x] `curl -i https://dtf.twocomms.shop/robots.txt` => DTF sitemap line
- [x] `curl -i https://dtf.twocomms.shop/sitemap.xml` => 200 + DTF host `<loc>` values

## Post-deploy checklist (must pass)
- [ ] `https://dtf.twocomms.shop/` renders new assets (`dtf.css?v=20260206e`, `dtf.js?v=20260206e`)
- [ ] Mobile drawer opens/closes cleanly and does not leave background interactive
- [ ] Manager modal is visually solid (not over-transparent) and FAB does not overlap when modal is open
- [ ] Before/after slider supports direct drag and range movement
- [ ] EN language switch visible and functional
- [ ] `https://dtf.twocomms.shop/sitemap.xml` includes legal URLs
