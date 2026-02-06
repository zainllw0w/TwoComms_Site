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
- [x] Server pull/restart commands and resulting commit hash
- [x] Post-deploy curl checks for DTF pages + robots/sitemap
- [x] Browser checks for mobile menu, manager modal, compare slider, EN switch

### Server deploy log (latest)
```bash
sshpass -p '***' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "\
bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate && \
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && \
git pull --ff-only && \
python manage.py check && \
python manage.py collectstatic --noinput && \
touch tmp/restart.txt && \
git log -1 --oneline'"
```

Observed:
- Production branch: `codex/dtf-p0p1-fixes-2026-02`
- Deployed commit: `dc7ab38 fix(dtf-ui): correct mobile drawer layering above page content`
- `python manage.py check` on server: `System check identified no issues`
- `collectstatic`: completed (1 static file copied, rest unchanged)

### Post-deploy production probes
```bash
curl -I https://dtf.twocomms.shop/quality/
curl -I https://dtf.twocomms.shop/price/
curl -I https://dtf.twocomms.shop/prices/
curl https://dtf.twocomms.shop/robots.txt
curl https://dtf.twocomms.shop/sitemap.xml
curl https://twocomms.shop/robots.txt
curl https://twocomms.shop/sitemap.xml
```

Observed:
- `https://dtf.twocomms.shop/quality/` => `HTTP/2 200`
- `https://dtf.twocomms.shop/price/` => `HTTP/2 200`
- `https://dtf.twocomms.shop/prices/` => `HTTP/2 301` with `Location: /price/`
- DTF `robots.txt` contains only DTF sitemap:
  - `Sitemap: https://dtf.twocomms.shop/sitemap.xml`
- DTF `sitemap.xml` => `200` and contains DTF-only URLs including:
  - `/price/`, `/privacy/`, `/terms/`, `/returns/`, `/requisites/`
- Main domain isolation preserved:
  - `https://twocomms.shop/robots.txt` points to `https://twocomms.shop/sitemap.xml`
  - `https://twocomms.shop/sitemap.xml` contains main-domain catalog/product URLs

### Browser/manual verification (mobile)
- Mobile drawer layering fixed and now fully overlays content.
  - Screenshot: `/Users/zainllw0w/PycharmProjects/TwoComms/artifacts/postdeploy-mobile-menu-live-dc7ab38.png`
- Manager modal visual opacity/contrast now solid and aligned with theme.
  - Screenshot: `/Users/zainllw0w/PycharmProjects/TwoComms/artifacts/postdeploy-mobile-modal-live-dc7ab38.png`
- Before/after slider drag works (JS runtime check):
  - `--compare` changed from `55%` to `80%`, range value changed to `80`
- EN switch visible in header and active in language links.
