# Decision Log — DTF POLISH ONLY (2026-02-06)

## D-001 Keep DTF Isolation Strict
- Decision: Apply changes only in DTF app/templates/static/locales and DTF spec docs.
- Why: User requirement to avoid impact on `twocomms.shop` main storefront.
- Evidence: `twocomms/twocomms/middleware.py`, `twocomms/twocomms/urls_dtf.py`

## D-002 Treat Lighthouse As Baseline Contract, Not Vanity Metric
- Decision: Capture baseline for `/`, `/order/`, `/price/` on mobile+desktop before additional polish.
- Why: Prevent visual refinements from silently regressing CWV.
- Evidence: `specs/dtf-codex/perf/*.report.json`, `specs/dtf-codex/perf/lighthouse-metrics-2026-02-06.txt`

## D-003 Fix Language Quality In Catalogs, Not Template Forks
- Decision: Correct RU/EN phrasing in locale catalogs instead of adding per-language template branches.
- Why: Keep template structure stable and avoid divergence.
- Evidence: `twocomms/dtf/locale/ru/LC_MESSAGES/django.po`, `twocomms/dtf/locale/en/LC_MESSAGES/django.po`

## D-004 Localize Runtime JS Notifications By Active Locale
- Decision: Add locale-aware runtime message map in JS (`uk/ru/en`) and route alerts/toasts through it.
- Why: Previous JS strings were always Ukrainian, causing mixed-language UX.
- Evidence: `twocomms/dtf/static/dtf/js/dtf.js`

## D-005 Ship JS Cache-Bust With Runtime Text Changes
- Decision: Bump JS static version query parameter.
- Why: Ensure fresh client bundle after localization/polish changes.
- Evidence: `twocomms/dtf/templates/dtf/base.html`

## D-006 Patch Security Dependencies Immediately
- Decision: Update `Django` and `social-auth-app-django` to non-vulnerable versions from `pip-audit` guidance.
- Why: Audit showed known vulnerabilities affecting current pinned versions.
- Evidence: `twocomms/requirements.txt`, `specs/dtf-codex/perf/pip-audit.json`, `specs/dtf-codex/perf/pip-audit-postfix.json`

## D-007 Preserve Existing HTMX Lifecycle Pattern
- Decision: Keep `initOnce/initAll` + `htmx.onLoad` architecture intact; no refactor to new framework.
- Why: It already ensures idempotent re-init after swaps and aligns with repository pattern.
- Evidence: `twocomms/dtf/static/dtf/js/dtf.js`

## D-008 No Dead-Code Cleanup In This Pass
- Decision: Skip deletions without strict proof of zero usage across subdomains.
- Why: Phase priority is polish/stability, and cleanup risk is higher than value here.
- Evidence: `specs/dtf-codex/CHECKLIST.md`
