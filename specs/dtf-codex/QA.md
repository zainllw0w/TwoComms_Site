# QA Checklist (DTF Re-run)

## Automated
- [x] `python3 manage.py check --settings=test_settings`
- [x] `python3 manage.py test dtf --settings=test_settings`

## Coverage map (DTF tests)
- [x] `/quality/` returns 200
- [x] `/price/` returns 200
- [x] `/prices/` redirects 301 to `/price/`
- [x] `/robots.txt` points to `https://dtf.twocomms.shop/sitemap.xml`
- [x] `/sitemap.xml` uses DTF host and includes `/price/`
- [x] DTF upload security blocks invalid files and renames accepted uploads
- [x] Host isolation check: main and dtf robots/sitemap stay separated
- [x] DTF landing uses DTF template assets

## Manual production smoke (must-do per deploy)
- [ ] `https://dtf.twocomms.shop/` => DTF template visible
- [ ] `https://dtf.twocomms.shop/quality/` => 200
- [ ] `https://dtf.twocomms.shop/price/` => 200
- [ ] `https://dtf.twocomms.shop/prices/` => 301 to `/price/`
- [ ] `https://dtf.twocomms.shop/robots.txt` => DTF sitemap line
- [ ] `https://dtf.twocomms.shop/sitemap.xml` => DTF-only locs
- [ ] `https://twocomms.shop/` => NOT DTF template
- [ ] `https://twocomms.shop/robots.txt` => main sitemap line
- [ ] `https://twocomms.shop/sitemap.xml` => main host locs
