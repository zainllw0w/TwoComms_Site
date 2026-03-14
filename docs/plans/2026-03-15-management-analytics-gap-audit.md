# Management Analytics Gap Audit

## Audit Scope

- Authority file checked first:
  - `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/18_IMPLEMENTATION_MASTER_FILE.md`
- Supporting March 13 files checked against runtime code:
  - `02_SYSTEM_ARCHITECTURE_AND_INVARIANTS.md`
  - `03_SCORE_MOSAIC_EWR_CONFIDENCE.md`
  - `04_PAYROLL_KPI_PORTFOLIO_EARNED_DAY.md`
  - `05_IDENTITY_DEDUPE_FOLLOWUP_ANTI_ABUSE.md`
  - `07_MANAGER_ADMIN_UX_EXPLAINABILITY.md`
  - `13_IMPLEMENTATION_BLUEPRINT_AND_DEPENDENCY_ORDER.md`
  - `16_DECISION_LOG_REJECTED_IDEAS_AND_BACKLOG.md`
- Previous final synthesis checked for omitted context:
  - `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_12/01_MASTER_SYNTHESIS.md`
  - `02_MOSAIC_SCORE_SYSTEM.md`
  - `06_UI_UX_AND_MANAGER_CONSOLE.md`
  - `07_IMPLEMENTATION_ROADMAP.md`
  - `15_ADMIN_ECONOMICS_AND_EARNED_DAY.md`
- Additional note:
  - no older `final_codex_synthesis_*` folders exist in the repository beyond `2026_03_12` and `2026_03_13`.

## Confirmed Gaps Found

### 1. Manual home flow diverged from shared dedupe policy

Master file section `Phase 2` requires shared dedupe decisions across:

- manager home client create/update
- lead create/process
- parser moderation

Actual gap before this pass:

- `management/views.py::home()` could still create/update clients without the shared `evaluate_duplicate_zone()` contract.
- front-end fallback on save error could re-submit the form and bypass the review-first dedupe response.

Resolution in this pass:

- manual client create/update now goes through `management.services.dedupe`.
- AJAX save no longer falls back to a blind submit after a conflict.
- duplicate review details now surface directly inside the modal.

### 2. Weak/negative outcomes lacked structured mandatory reasons

Canonical MOSAIC docs explicitly require:

- mandatory reasons for weak outcomes;
- `missing reason after negative outcome` as a `DataQuality` red flag;
- `reason_quality` to influence trust in a bounded way.

Actual gap before this pass:

- result reasons were stored only as freeform text in `call_result_details`;
- manual home flow and lead conversion flow had no structured reason fields;
- stats/snapshots could not measure reason completeness reliably.

Resolution in this pass:

- added structured client fields:
  - `call_result_reason_code`
  - `call_result_reason_note`
  - `call_result_context`
- added shared normalization/validation in `management.services.outcomes`.
- added dynamic UI for:
  - `Не цікавить`
  - `Дорого`
  - `Не відповідає`
  - `Номер недоступний`
  - `Інше`

### 3. Reason completeness was not affecting shadow quality/trust

Actual gap before this pass:

- `DataQuality` only considered follow-up plan gaps and missing reports;
- `compute_production_trust()` used a placeholder `reason_quality` heuristic unrelated to actual CRM completeness.

Resolution in this pass:

- `stats_service` now computes:
  - `negative_outcomes_total`
  - `required_reason_missing`
  - `reason_detail_missing`
  - `reason_quality`
  - `reason_breakdown`
- `services/snapshots.py` now feeds `reason_quality` into:
  - `DataQuality` axis
  - production trust multiplier
- impact stays bounded and shadow-safe; legacy KPD/payroll truth remains untouched.

## Safe Defers Kept Explicit

- No change was made to legacy KPD points mapping for reason completeness.
  - This is intentional and matches the master file warning that legacy points must not be remapped into MOSAIC without a separately designed transition.
- No new payroll penalties were introduced from reason completeness.
  - The effect is limited to shadow analytics and explainability.
- No parser-only result-reason workflow was added.
  - Parser moderation still governs lead quality; structured outcome reasons are attached at the moment a lead becomes a real processed client.

## Runtime Files Touched By This Gap Closure

- `twocomms/management/views.py`
- `twocomms/management/lead_views.py`
- `twocomms/management/models.py`
- `twocomms/management/stats_service.py`
- `twocomms/management/services/outcomes.py`
- `twocomms/management/services/snapshots.py`
- `twocomms/management/services/trust.py`
- `twocomms/management/templates/management/home.html`
- `twocomms/twocomms_django_theme/static/css/management.css`
- `twocomms/management/migrations/0024_client_call_result_reason_fields.py`

## Verification Notes

- Local regression used project `test_settings.py` because the repository has an unrelated global migration issue outside this feature slice.
- Production-safe verification still must happen on the real MySQL hosting environment after deploy.
