# QA Matrix — DTF POLISH ONLY (2026-02-06)

## Automated Checks (Local)
- [x] `DJANGO_SETTINGS_MODULE=test_settings python3 manage.py check`
- [x] `DJANGO_SETTINGS_MODULE=test_settings python3 manage.py test dtf.tests --keepdb`
- [x] `DJANGO_SETTINGS_MODULE=test_settings python3 manage.py compilemessages -l uk -l ru -l en`
- [x] `python3 -m pip_audit -r twocomms/requirements.txt -f json -o specs/dtf-codex/perf/pip-audit-postfix.json`

## Regression Coverage (`dtf.tests`)
- [x] DTF routes are stable (`/quality/`, `/price/`, `/prices/` redirect).
- [x] Robots/sitemap are host-isolated for DTF vs main domain.
- [x] DTF legal pages return `200`.
- [x] Upload security blocks invalid files and renames valid uploads safely.
- [x] Hero responsive asset hints remain intact.
- [x] EN switch wiring remains functional.

## Performance Baseline (Lighthouse)
- [x] Mobile + desktop baseline reports generated for `/`, `/order/`, `/price/`.
- [x] Metrics summary generated.
- Artifacts:
  - `specs/dtf-codex/perf/home-mobile-baseline.report.json`
  - `specs/dtf-codex/perf/order-mobile-baseline.report.json`
  - `specs/dtf-codex/perf/price-mobile-baseline.report.json`
  - `specs/dtf-codex/perf/home-desktop-baseline.report.json`
  - `specs/dtf-codex/perf/order-desktop-baseline.report.json`
  - `specs/dtf-codex/perf/price-desktop-baseline.report.json`
  - `specs/dtf-codex/perf/lighthouse-metrics-2026-02-06.txt`

## Guardrails (Mandatory For Any Next Visual Change)
- Re-run Lighthouse on `/` and `/order/` before and after change.
- `CLS` must stay `<= 0.10`.
- `LCP` must not degrade by more than `10%` versus baseline on same profile (mobile vs mobile, desktop vs desktop).
- If guardrail fails, rollback or optimize before deploy.

## Breakpoints QA (Production Visual Baseline)
- [x] Captured screenshots for `320/375/768/1024/1440` for:
  - `/`
  - `/order/`
  - `/price/`
  - `/quality/`
  - `/gallery/`
  - `/privacy/`
- Artifacts: `specs/dtf-codex/perf/screens/`, `specs/dtf-codex/perf/screens/index-2026-02-06.txt`

## Headers And SEO Sanity (Production)
- [x] `curl` snapshot includes status and security headers for DTF pages.
- [x] `robots.txt` and `sitemap.xml` confirmed for DTF host.
- [x] Main domain robots/sitemap unchanged.
- Artifacts:
  - `specs/dtf-codex/perf/discovery-curl-2026-02-06.txt`
  - `specs/dtf-codex/perf/robots-sitemap-2026-02-06.txt`

## Post-Deploy Minimum (Must Re-Run After Server Pull)
1. `curl -i https://dtf.twocomms.shop/`
2. `curl -i https://dtf.twocomms.shop/order/`
3. `curl -i https://dtf.twocomms.shop/price/`
4. `curl -i https://dtf.twocomms.shop/prices/`
5. `curl -i https://dtf.twocomms.shop/quality/`
6. `curl -i https://dtf.twocomms.shop/robots.txt`
7. `curl -i https://dtf.twocomms.shop/sitemap.xml`
8. Visual smoke on mobile `/order/` (drawer + modal + summary overlap).
9. Quick Lighthouse compare for `/` and `/order/` mobile profile against baseline.
