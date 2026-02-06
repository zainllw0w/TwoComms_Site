# Evidence Log — DTF POLISH ONLY (2026-02-06)

## Branch / Scope
- Branch: `codex/dtf-p2-polish-only-2026-02`
- Scope: DTF-only codepaths and docs.
- Isolation intent: no changes to main-domain routing behavior.

## P2-0 Discovery Snapshot

### DTF project map
- DTF app root: `twocomms/dtf/`
- Templates: `twocomms/dtf/templates/dtf/`
- Tokens: `twocomms/dtf/static/dtf/css/tokens.css`
- Main DTF JS lifecycle: `twocomms/dtf/static/dtf/js/dtf.js`
  - idempotent init gate: `initOnce(...)`
  - global bootstrapping: `initAll(...)`
  - HTMX hook: `window.htmx.onLoad((content) => initAll(content))`
- Subdomain routing: `twocomms/twocomms/middleware.py` (`SubdomainURLRoutingMiddleware`) -> `twocomms/twocomms/urls_dtf.py`

### Production curl snapshot (GET headers)
- Artifact: `specs/dtf-codex/perf/discovery-curl-2026-02-06.txt`
- Routes covered:
  - `https://dtf.twocomms.shop/`
  - `https://dtf.twocomms.shop/order/`
  - `https://dtf.twocomms.shop/price/`
  - `https://dtf.twocomms.shop/prices/`
  - `https://dtf.twocomms.shop/quality/`
  - `https://dtf.twocomms.shop/robots.txt`
  - `https://dtf.twocomms.shop/sitemap.xml`

### Robots/Sitemap body checks
- Artifact: `specs/dtf-codex/perf/robots-sitemap-2026-02-06.txt`
- Observed:
  - DTF `robots.txt` points to `https://dtf.twocomms.shop/sitemap.xml`
  - DTF `sitemap.xml` contains DTF host URLs
  - Main domain robots/sitemap remain main-domain specific

## P2-1 Lighthouse Baseline

### Artifacts
- Mobile JSON/HTML:
  - `specs/dtf-codex/perf/home-mobile-baseline.report.json`
  - `specs/dtf-codex/perf/order-mobile-baseline.report.json`
  - `specs/dtf-codex/perf/price-mobile-baseline.report.json`
  - `specs/dtf-codex/perf/home-mobile-baseline.report.html`
  - `specs/dtf-codex/perf/order-mobile-baseline.report.html`
  - `specs/dtf-codex/perf/price-mobile-baseline.report.html`
- Desktop JSON/HTML:
  - `specs/dtf-codex/perf/home-desktop-baseline.report.json`
  - `specs/dtf-codex/perf/order-desktop-baseline.report.json`
  - `specs/dtf-codex/perf/price-desktop-baseline.report.json`
  - `specs/dtf-codex/perf/home-desktop-baseline.report.html`
  - `specs/dtf-codex/perf/order-desktop-baseline.report.html`
  - `specs/dtf-codex/perf/price-desktop-baseline.report.html`
- Metrics summary: `specs/dtf-codex/perf/lighthouse-metrics-2026-02-06.txt`

### Baseline metrics (from summary)
- Home mobile: perf `60`, LCP `7.29s`, CLS `0.000`
- Order mobile: perf `88`, LCP `3.02s`, CLS `0.017`
- Price mobile: perf `73`, LCP `4.75s`, CLS `0.051`
- Home desktop: perf `57`, LCP `5.58s`, CLS `0.017`
- Order desktop: perf `83`, LCP `2.08s`, CLS `0.014`
- Price desktop: perf `84`, LCP `1.80s`, CLS `0.037`

## P2-2 i18n Inventory + Fixes
- Inventory document: `specs/dtf-codex/I18N_INVENTORY.md`
- RU/EN catalog improvements:
  - `twocomms/dtf/locale/ru/LC_MESSAGES/django.po`
  - `twocomms/dtf/locale/en/LC_MESSAGES/django.po`
- Compiled message catalogs:
  - `twocomms/dtf/locale/ru/LC_MESSAGES/django.mo`
  - `twocomms/dtf/locale/en/LC_MESSAGES/django.mo`
- Localized JS runtime alerts/toasts by locale:
  - `twocomms/dtf/static/dtf/js/dtf.js`
- Cache-bust for JS rollout:
  - `twocomms/dtf/templates/dtf/base.html` (`dtf.js?v=20260206p`)

## P2-3 Visual QA Baseline (Breakpoints)
- Captured screenshots for `320/375/768/1024/1440` on:
  - `/`
  - `/order/`
  - `/price/`
  - `/quality/`
  - `/gallery/`
  - `/privacy/`
- Artifact index: `specs/dtf-codex/perf/screens/index-2026-02-06.txt`
- Screenshot folder: `specs/dtf-codex/perf/screens/`

## P2-4 HTMX Lifecycle Regression Check
- JS confirms idempotent + re-init lifecycle pattern remains intact.
- Evidence file: `twocomms/dtf/static/dtf/js/dtf.js`

## P2-5 Security / Headers / Dependencies

### Headers sanity
- Source: `specs/dtf-codex/perf/discovery-curl-2026-02-06.txt`
- Confirmed headers on DTF routes include:
  - `Strict-Transport-Security`
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy`
  - `X-Frame-Options`
  - CSP present

### Dependency audit
- Initial audit: `specs/dtf-codex/perf/pip-audit.json`
  - Found vulnerabilities in `Django==5.2.6` and `social-auth-app-django==5.4.1`.
- Remediation:
  - `twocomms/requirements.txt` -> `Django==5.2.11`
  - `twocomms/requirements.txt` -> `social-auth-app-django==5.6.0`
- Post-fix audit: `specs/dtf-codex/perf/pip-audit-postfix.json`
  - Result: `No known vulnerabilities found`.

## Local Validation Commands
```bash
cd /Users/zainllw0w/PycharmProjects/TwoComms/twocomms
DJANGO_SETTINGS_MODULE=test_settings python3 manage.py compilemessages -l uk -l ru -l en
DJANGO_SETTINGS_MODULE=test_settings python3 manage.py check
DJANGO_SETTINGS_MODULE=test_settings python3 manage.py test dtf.tests --keepdb
python3 -m pip_audit -r /Users/zainllw0w/PycharmProjects/TwoComms/twocomms/requirements.txt -f json -o /Users/zainllw0w/PycharmProjects/TwoComms/specs/dtf-codex/perf/pip-audit-postfix.json
```

## Local Validation Results
- `compilemessages`: RU/EN catalogs rebuilt, UK unchanged.
- `manage.py check`: `System check identified no issues (0 silenced).`
- `manage.py test dtf.tests --keepdb`: `Ran 19 tests ... OK`.
- `pip-audit` after dependency update: no known vulnerabilities.

## Files Changed In This Polish Run
- `twocomms/dtf/static/dtf/js/dtf.js`
- `twocomms/dtf/templates/dtf/base.html`
- `twocomms/dtf/locale/ru/LC_MESSAGES/django.po`
- `twocomms/dtf/locale/ru/LC_MESSAGES/django.mo`
- `twocomms/dtf/locale/en/LC_MESSAGES/django.po`
- `twocomms/dtf/locale/en/LC_MESSAGES/django.mo`
- `twocomms/requirements.txt`
- `specs/dtf-codex/I18N_INVENTORY.md`
- `specs/dtf-codex/CHECKLIST.md`
- `specs/dtf-codex/DECISIONS.md`
- `specs/dtf-codex/QA.md`
- `specs/dtf-codex/DEPLOY.md`
- `specs/dtf-codex/EVIDENCE.md`
- `specs/dtf-codex/perf/*`

## Deployment Status
- Deployed to server branch: `codex/dtf-p2-polish-only-2026-02`
- Deployed commit: `0d4c9a4`
- Server actions executed:
  - `git fetch --all --prune`
  - `git checkout codex/dtf-p2-polish-only-2026-02`
  - `git pull --ff-only`
  - `python manage.py check`
  - `python manage.py migrate --noinput`
  - `python manage.py collectstatic --noinput`
  - `touch tmp/restart.txt`
- Server output summary:
  - `System check identified no issues`
  - `No migrations to apply`
  - `1 static file copied, 321 unmodified`

## Post-Deploy Verification
- Artifact: `specs/dtf-codex/perf/postdeploy-curl-2026-02-06.txt`
- Confirmed:
  - DTF routes `/, /order/, /price/, /quality/` return `HTTP/2 200`
  - `/prices/` returns `HTTP/2 301` -> `/price/`
  - DTF `robots.txt` points to DTF sitemap only
  - DTF `sitemap.xml` contains DTF host URLs
  - Main domain `robots/sitemap` remained main-domain scoped
  - JS asset version on live page: `dtf/js/dtf.js?v=20260206p`
  - RU/EN live smoke strings reflect updated translations
