# CHANGELOG CODEX

## 2026-02-07 02:05 UTC
- Scope: Part 3 execution protocol hardening and QA/evidence updates for `dtf.twocomms.shop`.
- Summary:
  - Added operational runbook artifacts and refreshed QA evidence (tests, pip-audit, curl matrix, lighthouse).
  - Synced checklist/docs to Part 3 definition-of-done flow.
  - Kept isolation: DTF-only workflows and verification; main-domain behavior unchanged.
- Files:
  - `specs/dtf-codex/CHECKLIST.md`
  - `specs/dtf-codex/QA.md`
  - `specs/dtf-codex/DEPLOY.md`
  - `specs/dtf-codex/EVIDENCE.md`
  - `DTF_CHECKLIST.md`
  - `MCP_TODO.md`
  - `EVIDENCE.md`
  - `DEPLOY.md`
- Rollback note:
  - Docs-only rollback: checkout previous commit and restore docs.
  - If deployed and any regression appears: checkout last good commit on server, run `collectstatic`, then `touch tmp/restart.txt`.
- Deploy status:
  - Branch `codex/codex-refactor-v1` pushed and deployed.
  - Server applied `dtf.0003_knowledgepost` migration and restarted app.

## 2026-02-07 01:05 UTC
- Scope: Part 4 feature wave for DTF subdomain (`WOW visuals + sample + constructor + products + cabinet`).
- Summary:
  - Added Free Sample end-to-end flow (`/sample/`, `DtfSampleLead`, admin, anti-spam/rate-limit).
  - Implemented component effect pack and wired global `DTF.init()` + `initEffects()` + HTMX re-init pattern.
  - Added Constructor MVP (`/constructor/`, `/constructor/app/`, `/constructor/submit/`) with preflight report and Pillow preview rendering.
  - Added `/products/`, `/about/` and cabinet MVP pages (`/cabinet/*`) with loyalty summary and saved sessions.
  - Applied data-ui anchors and microcopy updates on home/order/gallery/requirements/status/templates.
- Files:
  - `twocomms/dtf/models.py`
  - `twocomms/dtf/forms.py`
  - `twocomms/dtf/views.py`
  - `twocomms/dtf/urls.py`
  - `twocomms/dtf/admin.py`
  - `twocomms/dtf/tests.py`
  - `twocomms/dtf/utils.py`
  - `twocomms/dtf/migrations/0004_dtfsamplelead_alter_dtforder_length_source_and_more.py`
  - `twocomms/dtf/templates/dtf/*` (base + part4 pages/updates)
  - `twocomms/dtf/static/dtf/js/components/*`
  - `twocomms/dtf/static/dtf/css/components/*`
  - `twocomms/dtf/static/dtf/js/dtf.js`
  - `twocomms/dtf/static/dtf/css/dtf.css`
- Validation:
  - `python3 -m compileall -q twocomms/dtf` -> OK
  - `python3 twocomms/manage.py test dtf --settings=test_settings` -> `33 tests OK`
- Rollback note:
  - Revert to previous commit, run `collectstatic --noinput`, then `touch tmp/restart.txt`.

## 2026-02-07 01:25 UTC
- Scope: Post-Part4 deploy hardening for QA matrix compatibility.
- Summary:
  - Added HEAD support on form pages (`/order/`, `/status/`, `/sample/`, `/constructor/app/`, `/preflight/`) so `curl -I` checks align with runbook.
  - Re-deployed branch and verified key endpoints now return `HTTP 200` for HEAD requests.
- Files:
  - `twocomms/dtf/views.py`
- Commit:
  - `40986e7`
