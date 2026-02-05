# QA Checklist

## Automated
- [x] `python manage.py test storefront.tests.test_dtf_p0 --settings=test_settings`
- [x] `python manage.py test storefront.tests.test_upload_security --settings=test_settings`
- [x] `python manage.py test storefront.tests.test_feed_endpoints --settings=test_settings`
- [ ] `python manage.py test storefront --settings=test_settings`
- [x] `python manage.py check --settings=test_settings`
- [ ] `npm run build:css` (if CSS source changed)

## Manual Smoke
- [x] `GET /quality/` returns 200 and renders template correctly
- [x] `GET /price/` returns 200
- [x] `GET /prices/` returns 301 -> `/price/`
- [x] `GET /robots.txt` points to current host sitemap and has no wrong main-domain sitemap link
- [x] `GET /sitemap.xml` contains only current host URLs and includes `/price/`
- [ ] Mobile 320px: sticky summary does not cover form fields/buttons
- [ ] Home first viewport: no obvious image CLS jump
- [ ] Reduced-motion still disables animations

## Evidence Capture
- [x] Save command outputs and key assertions in `EVIDENCE.md`
- [x] Record production verification URLs/HTTP codes in `DEPLOY.md`
