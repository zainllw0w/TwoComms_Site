# Evidence Log (DTF Re-baseline)

## Local branch and scope
- Branch: `codex/dtf-p0p1-fixes-2026-02`
- Current change scope (before deploy):
  - `twocomms/dtf/forms.py`
  - `twocomms/dtf/utils.py`
  - `twocomms/dtf/views.py`
  - `twocomms/dtf/urls.py`
  - `twocomms/dtf/tests.py`
  - `twocomms/dtf/static/dtf/css/tokens.css`
  - `twocomms/dtf/static/dtf/css/dtf.css`
  - `twocomms/dtf/templates/dtf/index.html`
  - `specs/dtf-codex/*`

## Local validation
- `python3 manage.py check --settings=test_settings` -> `System check identified no issues (0 silenced).`
- `python3 manage.py test dtf --settings=test_settings` -> `Ran 15 tests ... OK`

## What is verified by tests now
- P0 routes and SEO behavior (`quality/price/prices/robots/sitemap`) for DTF host.
- Host isolation between `twocomms.shop` and `dtf.twocomms.shop` for `robots.txt` and `sitemap.xml`.
- DTF upload security: extension, MIME, magic bytes, size and safe filename policy.

## Pending evidence
- Production smoke after latest commit/deploy (to be appended after server update).
