# DTF i18n Inventory (2026-02-06)

## Scope
- Subdomain only: `dtf.twocomms.shop`
- Templates audited: `/`, `/order/`, `/price/`, `/quality/`, `/status/`, legal pages
- Runtime locale sources: `lang` query param + `dtf_lang` cookie (`uk`, `ru`, `en`)

## Findings And Fixes
- `order` flow had low-quality RU wording and mixed terminology in key labels.
  - Fixed in `twocomms/dtf/locale/ru/LC_MESSAGES/django.po` and recompiled `django.mo`.
- `quality` page had multiple non-professional RU/EN phrases.
  - Fixed in `twocomms/dtf/locale/ru/LC_MESSAGES/django.po` and `twocomms/dtf/locale/en/LC_MESSAGES/django.po`.
- JS toasts/alerts were hardcoded in Ukrainian for all locales.
  - Added locale-aware runtime message map in `twocomms/dtf/static/dtf/js/dtf.js`.
- Asset cache invalidation required for JS language polish rollout.
  - Bumped JS asset version in `twocomms/dtf/templates/dtf/base.html`.

## Terms Consistency
- Kept as product terms: `DTF`, `Hot Peel`, `Preflight`, `QC`, `Nova Poshta`.
- Unified wording around:
  - gang sheet / gang-list,
  - registration control,
  - white underbase,
  - lead times / cutoff.

## Validation
- `DJANGO_SETTINGS_MODULE=test_settings python3 manage.py compilemessages -l uk -l ru -l en`
- `DJANGO_SETTINGS_MODULE=test_settings python3 manage.py test dtf.tests --keepdb`

## Notes
- Legal pages intentionally use `TEMP:` placeholders per phase contract; no lorem/garbage text introduced.
