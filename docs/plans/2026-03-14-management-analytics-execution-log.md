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
