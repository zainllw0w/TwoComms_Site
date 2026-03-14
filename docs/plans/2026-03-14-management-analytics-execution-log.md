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

## Verification Evidence

- Baseline Django tests from production SHA: `11` tests passed in `management.tests`.
- Current implementation verification: `44` Django tests passed across `management.tests`, `tests_phase1`, `tests_phase2_dedupe`, `tests_phase3_services`, `tests_phase3_snapshots`, and `tests_phase6_foundation`.
- `python manage.py makemigrations management --check --dry-run` reports no pending model changes.

## Implemented Slice

- Extended `ManagementStatsConfig` and added `ComponentReadiness`, `CommandRunLog`, `ManagerDayStatus`, `NightlyScoreSnapshot`, `ScoreAppeal`, and `DuplicateReview`.
- Added dedupe identity fields to `Client` and `ManagementLead`, plus weighted duplicate resolution with review creation.
- Added services for score, churn, payroll, dedupe, and snapshots; added commands `seed_management_defaults`, `compute_nightly_scores`, `process_telephony_webhooks`, `reconcile_call_records`, and `refresh_dtf_bridge_snapshot`.
- Added telephony/DTF foundation models: `OwnershipChangeLog`, `TelephonyWebhookLog`, `CallRecord`, `TelephonyHealthSnapshot`, `CallQAReview`, `SupervisorActionLog`, and `DtfBridgeSnapshot`.
- Surfaced shadow score data in stats payload and UI; added score appeal create/resolve APIs.

## Next Slice

1. Extend manager/admin UX around appeals, admin economics, and compare views on top of the new `shadow_score` payload.
2. Implement follow-up overload redistribution, quiet hours/digesting, and backlog grace as a dedicated safe subsystem.
3. Add validation-gate plumbing and preview/server deployment verification for the feature branch.
