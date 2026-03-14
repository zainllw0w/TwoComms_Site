# Management Analytics Execution Log

## Context

- Branch: `codex/management-canonical-analytics-full`
- Worktree base: production/server `main` SHA `cfda108f52340e00403d6e8c3aade34e3117ff8f`
- Scope: full phases `1-9`
- Runtime owner: `twocomms/management/`

## Phase Board

- [x] Bootstrap: clean worktree from server `main`
- [x] Phase 1: data foundation
- [x] Phase 2: dedupe, follow-up, ownership safety
- [x] Phase 3: shadow score engine and snapshots
- [x] Phase 4: manager/admin explainability UI foundation
- [x] Phase 5: payroll-safe logic and appeals foundation
- [x] Phase 6-7: telephony readiness and soft launch foundation
- [ ] Phase 8: validation and activation plumbing
- [x] Phase 9: DTF read-only bridge foundation
- [ ] Verification, review, commit, push, preview deploy

## Decisions

- Base branch/worktree is cut from the live server `main`, not the dirty local branch.
- Preview verification must use a separate server checkout/worktree.
- Legacy KPD remains live during rollout; MOSAIC starts in shadow mode.
- Redis/Celery remain optional; DB + cron is the required baseline.
- DTF bridge stays read-only and must not affect management score or payroll.
- Phase 2 dedupe is unified through `management.services.dedupe` and now covers manual lead create, lead-to-client conversion, and parser moderation.
- Phase 3 snapshots are built from existing `stats_service` day ranges; new shadow formulas persist alongside legacy KPD instead of replacing it.
- Shadow score is surfaced in the main stats hero as a secondary analytic layer with explicit `SHADOW/STALE/LOW CONFIDENCE` signaling.
- Telephony and DTF are implemented as persistence + command foundations first, in degraded-safe mode, so later live integrations do not need schema redesign.
- Canonical config/version registries are now centralized in `management.services.config_versions` instead of drifting across commands/services.
- Reminder logic is upgraded to digest/overload semantics via `management.services.followups` and the new `send_management_reminders` / `check_duplicate_queue` commands.
- Shadow payload now carries gate, trust, dampener, incident, portfolio, rescue, simulator, and forecast context so UI and admin logic read from one canonical contract.
- Range-based shadow views now aggregate canonical daily snapshots instead of falling back to a latest-snapshot-only read.
- Manager/admin UI was refactored into component includes under `templates/management/components/` for radar, timeline, DTF/admin control center, decomposition drawer, and appeal drawer.
- Shadow UI now exposes previous-period comparison, pace state, evidence-first decomposition, in-page appeal submission, and a unified client communication timeline.
- Admin analytics now expose queue presets, forecast confidence/bands, cohort retention proxy, and at-risk manager ranking.
- A second-pass audit against the March 13 master file and March 12 supporting synthesis confirmed a real gap in the manual home client flow and weak-outcome reason capture.
- Manual home create/update now uses the same shared dedupe contract as leads and parser moderation, with inline duplicate review surfacing instead of silent fallback.
- Weak/negative client outcomes now use structured reason capture (`reason_code`, `reason_note`, contextual extras) and those signals now feed `DataQuality` and bounded shadow trust.
- Stats/admin localization is preserved in Ukrainian, including partial-range state labels and roster visibility for excluded former managers.

## Verification Evidence

- Baseline Django tests from production SHA: `11` tests passed in `management.tests`.
- Current implementation verification: `59` Django tests passed across `management.tests`, `tests_phase1`, `tests_phase2_dedupe`, `tests_phase3_services`, `tests_phase3_snapshots`, `tests_phase4_analytics`, `tests_phase5_completion`, and `tests_phase6_foundation`.
- `SECRET_KEY=test-secret-key-for-testing-only-do-not-use-in-production DB_ENGINE=sqlite python3 manage.py makemigrations management --check --dry-run` reports no pending model changes.
- `python3 -m compileall management` completed successfully.
- `SECRET_KEY=test-secret-key-for-testing-only-do-not-use-in-production python3 manage.py check --settings=test_settings` completed successfully.
- `git diff --check` reports no whitespace or patch-shape problems.
- Local second-pass regression after the gap closure:
  - `DEBUG=1 SECRET_KEY=test-secret python3 manage.py test management.tests_phase2_dedupe management.tests_phase3_snapshots --settings=test_settings -v 2`
  - `DEBUG=1 SECRET_KEY=test-secret python3 manage.py test management.tests_phase4_analytics management.tests_phase5_completion --settings=test_settings -v 2`
  - `DEBUG=1 SECRET_KEY=test-secret python3 manage.py makemigrations --check --dry-run management`
  - `DEBUG=1 SECRET_KEY=test-secret python3 manage.py check --settings=test_settings`
- Gap audit document written to `docs/plans/2026-03-15-management-analytics-gap-audit.md`.

## Implemented Slice

- Extended `ManagementStatsConfig` and added `ComponentReadiness`, `CommandRunLog`, `ManagerDayStatus`, `NightlyScoreSnapshot`, `ScoreAppeal`, and `DuplicateReview`.
- Added dedupe identity fields to `Client` and `ManagementLead`, plus weighted duplicate resolution with review creation.
- Added services for score, churn, payroll, dedupe, and snapshots; added commands `seed_management_defaults`, `compute_nightly_scores`, `process_telephony_webhooks`, `reconcile_call_records`, and `refresh_dtf_bridge_snapshot`.
- Added telephony/DTF foundation models: `OwnershipChangeLog`, `TelephonyWebhookLog`, `CallRecord`, `TelephonyHealthSnapshot`, `CallQAReview`, `SupervisorActionLog`, and `DtfBridgeSnapshot`.
- Added canonical service modules: `config_versions`, `trust`, `followups`, `forecast`, `advice`, `appeals`, and `telephony`.
- Extended phase-5/phase-2 models with follow-up ladder fields, payout evidence/freeze fields, and richer score appeal metadata.
- Surfaced shadow score data in stats/admin payload and UI with `Why changed today`, `Must do today`, `Best opportunities`, `Rescue top-5`, `Salary simulator`, admin readiness/incidents, and forecast widgets.
- Added radar preview, decomposition drawer, appeal drawer, pace-state rail, unified client communication timeline, and richer admin control center cards while preserving existing routes and live KPD.
- Added reminder digesting/overload accounting and new management commands: `send_management_reminders` and `check_duplicate_queue`.
- Added structured client outcome capture through `management.services.outcomes` and migration `0024_client_call_result_reason_fields.py`.
- Upgraded manager home modals with dynamic reason taxonomy, contextual fields for weak outcomes, and an inline duplicate review surface.
- Wired `reason_quality` into stats summary, snapshot payloads, `DataQuality`, and bounded production trust, while keeping legacy KPD/payroll truth unchanged.

## Next Slice

1. Commit, push, and deploy the second-pass gap closure to the MySQL hosting environment.
2. Run post-deploy verification for manual client save/edit, lead conversion, stats/admin/payouts, and excluded-manager visibility on the live management subdomain.
3. Finish phase-8 validation plumbing and explicit activation controls in UI/admin workflows.

## 2026-03-15 Hotfix Pass: Home JS + Historical MOSAIC Visibility

- Reproduced the live `home` regression in the authenticated browser and isolated two separate client-side failures:
  - a stray broken JavaScript tail in `management/templates/management/base.html` that prevented all later page scripts from executing;
  - invalid JSON embedding for `data-outcome-reason-schema` in `management/templates/management/home.html`, which caused `JSON.parse()` to fail before modal handlers and countdown bootstrapped.
- Fixed the home page boot path by removing the broken base-template fragment and switching the embedded outcome schema from JS-escaped text to HTML-escaped JSON so the client modal can initialize safely again.
- Audited the historical shadow-score path and found a logic bug: old snapshots were permanently marked `STALE` because `freshness_seconds` was computed from `now - day_end`, which punishes any historical day forever.
- Corrected snapshot freshness semantics in `management/services/snapshots.py` so historical daily snapshots are treated as fresh once persisted, while current-day snapshots still retain freshness timing.
- Added on-demand shadow snapshot repair in `management/stats_service.py` for management subjects with meaningful history, including excluded managers and long-lived users with `>= 20` processed clients.
- Updated `compute_nightly_scores` to use the management roster service so excluded managers with real management history keep receiving future nightly snapshots instead of silently dropping out of MOSAIC coverage.
- Shifted the manager-facing copy so MOSAIC is presented as the primary rating surface and `КПД` is explicitly labeled `Legacy КПД` in the shadow showcase/decomposition surfaces.
- Cleaned the most visible remaining English strings in manager/admin shadow surfaces (`Інциденти`, `Довіра`, rescue urgency labels, timeline badges, action-stack labels) so live stats/admin screens stay meaningfully Ukrainian after the hotfix.

### Verification Evidence For This Hotfix Pass

- Red tests first:
  - `SECRET_KEY=test-secret python3 manage.py test management.tests_phase3_snapshots.ComputeNightlyScoresCommandTests management.tests_phase5_completion.HomePageScriptRegressionTests management.tests_phase5_completion.SnapshotAggregationExplainabilityTests.test_excluded_manager_with_real_history_gets_historical_shadow_backfill --settings=test_settings`
  - initial failures confirmed:
    - invalid embedded JSON on `home`;
    - excluded managers omitted from nightly snapshots;
    - no historical shadow backfill for excluded managers.
- Green after implementation:
  - same focused command above passed with `4` tests green.
  - `SECRET_KEY=test-secret python3 manage.py test management.tests_phase3_snapshots management.tests_phase4_analytics management.tests_phase5_completion --settings=test_settings` passed with `28` tests green.
  - `SECRET_KEY=test-secret python3 manage.py check --settings=test_settings` passed.
  - `SECRET_KEY=test-secret python3 manage.py makemigrations --check --dry-run --settings=test_settings` reported no changes.
  - `python3 -m py_compile management/stats_service.py management/services/snapshots.py management/management/commands/compute_nightly_scores.py` passed.
  - `git diff --check` passed.

## 2026-03-15 Localization And Historical Snapshot Readability Pass

- Reproduced the remaining live mixed-language issue specifically on Polina's long-range admin stats page after the home/modal hotfix was already green.
- Root cause split into two layers:
  - fresh UI copy still had a few English carryovers (`Legacy КПД`, mixed helper text);
  - historical snapshot payloads preserved old human-facing values (`LOW`, `MEDIUM`, `REMINDER_STORM`, `82d overdue`, `82d stale`, `logistic`) that were being rendered verbatim on aggregated ranges.
- Fixed the problem without touching formulas or payroll semantics:
  - added read-time normalization in `management/services/ui_labels.py` and `management/stats_service.py` for confidence labels, incident labels, rescue urgency, churn basis labels, and legacy English advisory phrases;
  - updated `management/services/advice.py` to render translated incident/confidence values and switched the visible KPD label to `Перехідний КПД`;
  - updated the shadow showcase/decomposition templates so the manager-facing label no longer mixes English into the primary cards;
  - localized remaining static wording such as the stale shop advice text in `stats_service.py`;
  - bumped the `get_stats_payload()` cache namespace to `mgmt:stats:v6` so production would stop serving pre-fix mixed-language payloads after deploy;
  - kept MOSAIC/KPD formulas, trust bands, snapshot selection, and rescue ranking logic unchanged.
- Canonical source check for this pass:
  - re-read the March 13 authority set around `03_SCORE_MOSAIC_EWR_CONFIDENCE.md`, `07_MANAGER_ADMIN_UX_EXPLAINABILITY.md`, `08_ADMIN_ECONOMICS_FORECAST_DECISION_SAFETY.md`, `10_GOVERNANCE_DATA_MODEL_JOBS_ROLLOUT.md`, and `18_IMPLEMENTATION_MASTER_FILE.md`;
  - confirmed this pass is presentation/readability-only and remains aligned with the canonical requirements that:
    - KPD coexists with shadow MOSAIC during transition;
    - confidence/freshness stay explicit;
    - rescue cards stay evidence-first and snapshot-driven;
    - historical ranges come from daily snapshots rather than ad hoc recomputation.

### Verification Evidence For This Localization Pass

- `SECRET_KEY=test-secret python3 manage.py test management.tests_phase3_snapshots management.tests_phase4_analytics management.tests_phase5_completion --settings=test_settings` passed with `28` tests green.
- `SECRET_KEY=test-secret python3 manage.py test management.tests_phase5_completion.SnapshotAggregationExplainabilityTests.test_shadow_payload_auto_heals_missing_daily_snapshot_gaps_for_stats_ranges management.tests_phase5_completion.HomePageScriptRegressionTests.test_home_page_has_parseable_reason_schema_and_valid_inline_scripts management.tests_phase5_completion.SnapshotAggregationExplainabilityTests.test_excluded_manager_with_real_history_gets_historical_shadow_backfill management.tests_phase3_snapshots.ComputeNightlyScoresCommandTests.test_command_includes_excluded_manager_with_management_history --settings=test_settings` passed.
- `SECRET_KEY=test-secret python3 manage.py check --settings=test_settings` passed.
- `SECRET_KEY=test-secret python3 manage.py makemigrations --check --dry-run --settings=test_settings` reported no changes.
- `python3 -m py_compile management/services/ui_labels.py management/services/advice.py management/services/snapshots.py management/stats_service.py management/stats_views.py` passed.
- `git diff --check` passed.
