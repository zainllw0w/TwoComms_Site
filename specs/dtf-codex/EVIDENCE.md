# Evidence Log (DTF backlog re-run, 2026-02-06)

## Branch / scope
- Branch: `codex/dtf-p0p1-fixes-2026-02`
- Scope: DTF-only code paths + DTF docs in `/specs/dtf-codex/`

## Local validation commands
```bash
cd /Users/zainllw0w/PycharmProjects/TwoComms/twocomms
DJANGO_SETTINGS_MODULE=test_settings python3 manage.py check
DJANGO_SETTINGS_MODULE=test_settings python3 manage.py test dtf.tests --keepdb
DJANGO_SETTINGS_MODULE=test_settings python3 manage.py compilemessages -l uk -l ru -l en
```

## Local validation result
- `manage.py check`: `System check identified no issues (0 silenced).`
- `manage.py test dtf.tests --keepdb`: `Ran 19 tests ... OK`
- `compilemessages`: updated `ru` + `en` catalogs, `uk` up-to-date

## Pre-deploy production probes
```bash
curl -I https://dtf.twocomms.shop/quality/
curl -I https://dtf.twocomms.shop/price/
curl -I https://dtf.twocomms.shop/prices/
curl -i https://dtf.twocomms.shop/robots.txt
curl -i https://dtf.twocomms.shop/sitemap.xml
```

### Observed status (pre-deploy)
- `/quality/` => `HTTP/2 200`
- `/price/` => `HTTP/2 200`
- `/prices/` => `HTTP/2 301` with `Location: /price/`
- `/robots.txt` => contains `Sitemap: https://dtf.twocomms.shop/sitemap.xml`
- `/sitemap.xml` => `HTTP/2 200`, content-type `application/xml`, DTF host URLs

## Code artifacts touched in this run
- `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/static/dtf/css/dtf.css`
- `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/static/dtf/js/dtf.js`
- `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/templates/dtf/base.html`
- `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/templates/dtf/index.html`
- `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/templates/dtf/price.html`
- `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/templates/dtf/legal/privacy.html`
- `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/templates/dtf/legal/terms.html`
- `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/templates/dtf/legal/returns.html`
- `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/templates/dtf/legal/requisites.html`
- `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/views.py`
- `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/urls.py`
- `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/utils.py`
- `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/tests.py`
- `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/locale/en/LC_MESSAGES/django.po`
- `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/locale/en/LC_MESSAGES/django.mo`
- `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/locale/ru/LC_MESSAGES/django.po`
- `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/locale/ru/LC_MESSAGES/django.mo`
- `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/locale/uk/LC_MESSAGES/django.po`
- `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/locale/uk/LC_MESSAGES/django.mo`

## Post-deploy evidence (to append after deploy)
- [ ] Server pull/restart commands and resulting commit hash
- [ ] Post-deploy curl checks for DTF pages + robots/sitemap
- [ ] Browser checks for mobile menu, manager modal, compare slider, EN switch
