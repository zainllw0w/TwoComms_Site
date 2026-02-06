# DTF Codex Checklist — POLISH ONLY (2026-02-06)

## Scope
- Branch: `codex/dtf-p2-polish-only-2026-02`
- Target host: `dtf.twocomms.shop`
- Isolation rule: DTF-only codepaths and docs, no main-domain routing changes.

## P2-0 Discovery Snapshot
- [x] Project map for DTF app/templates/tokens/JS init + subdomain routing captured.
  - Evidence: `specs/dtf-codex/EVIDENCE.md`, `twocomms/dtf/`, `twocomms/twocomms/middleware.py`, `twocomms/twocomms/urls_dtf.py`
- [x] Production curl snapshot captured for `/`, `/order/`, `/price/`, `/prices/`, `/quality/`, `/robots.txt`, `/sitemap.xml`.
  - Evidence: `specs/dtf-codex/perf/discovery-curl-2026-02-06.txt`

## P2-1 Performance Baseline + Guardrails
- [x] Lighthouse baseline (mobile + desktop) collected for `/`, `/order/`, `/price/`.
  - Evidence: `specs/dtf-codex/perf/*.report.html`, `specs/dtf-codex/perf/*.report.json`, `specs/dtf-codex/perf/lighthouse-metrics-2026-02-06.txt`
- [x] QA guardrails documented (visual change requires re-run on `/` and `/order/`; LCP/CLS thresholds defined).
  - Evidence: `specs/dtf-codex/QA.md`

## P2-2 i18n + Language Quality
- [x] Language inventory documented.
  - Evidence: `specs/dtf-codex/I18N_INVENTORY.md`
- [x] RU/EN translation quality fixes applied for order/price/quality/status key copy.
  - Evidence: `twocomms/dtf/locale/ru/LC_MESSAGES/django.po`, `twocomms/dtf/locale/en/LC_MESSAGES/django.po`
- [x] JS runtime notifications localized by current page locale.
  - Evidence: `twocomms/dtf/static/dtf/js/dtf.js`
- [x] Locale catalogs rebuilt.
  - Evidence: `twocomms/dtf/locale/ru/LC_MESSAGES/django.mo`, `twocomms/dtf/locale/en/LC_MESSAGES/django.mo`

## P2-3 Visual Polish / UX Consistency
- [x] Breakpoint visual baseline captured for key pages at `320/375/768/1024/1440`.
  - Evidence: `specs/dtf-codex/perf/screens/`, `specs/dtf-codex/perf/screens/index-2026-02-06.txt`
- [x] Asset cache-bust updated for polished JS behavior.
  - Evidence: `twocomms/dtf/templates/dtf/base.html`

## P2-4 HTMX Lifecycle / Dead HTML Regression
- [x] Idempotent init strategy confirmed (`initOnce` + `initAll` + `htmx` hooks).
  - Evidence: `twocomms/dtf/static/dtf/js/dtf.js`
- [x] Automated regression suite still green.
  - Evidence: `DJANGO_SETTINGS_MODULE=test_settings python3 manage.py test dtf.tests --keepdb`

## P2-5 Security / Headers / Dependencies
- [x] Security header sanity snapshot captured from production.
  - Evidence: `specs/dtf-codex/perf/discovery-curl-2026-02-06.txt`
- [x] Dependency audit executed and remediated.
  - Evidence: `specs/dtf-codex/perf/pip-audit.json`, `specs/dtf-codex/perf/pip-audit-postfix.json`, `twocomms/requirements.txt`
- [x] Upload security regression remains covered by tests.
  - Evidence: `twocomms/dtf/tests.py` (`DtfUploadSecurityTests`)

## P2-6 QA Contour
- [x] QA matrix updated with baseline, guardrails, automated checks, post-deploy minimum.
  - Evidence: `specs/dtf-codex/QA.md`

## P2-7 Cleanup
- [ ] Dead-code cleanup intentionally skipped in this pass (no proven-unused candidates with zero-risk guarantee).

## Regression Guard
- [x] Main domain robots/sitemap isolation preserved in checks and docs.
  - Evidence: `specs/dtf-codex/perf/robots-sitemap-2026-02-06.txt`, `twocomms/dtf/tests.py`

## Blockers
- [x] None.
