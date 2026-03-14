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

## Verification Evidence

- Baseline Django tests from production SHA: `11` tests passed in `management.tests`.
- Current implementation verification: `50` Django tests passed across `management.tests`, `tests_phase1`, `tests_phase2_dedupe`, `tests_phase3_services`, `tests_phase3_snapshots`, `tests_phase4_analytics`, and `tests_phase6_foundation`.
- `python manage.py makemigrations management --check --dry-run` reports no pending model changes.
- Pending migration generated: `management/migrations/0023_clientfollowup_escalation_level_and_more.py`.

## Implemented Slice

- Extended `ManagementStatsConfig` and added `ComponentReadiness`, `CommandRunLog`, `ManagerDayStatus`, `NightlyScoreSnapshot`, `ScoreAppeal`, and `DuplicateReview`.
- Added dedupe identity fields to `Client` and `ManagementLead`, plus weighted duplicate resolution with review creation.
- Added services for score, churn, payroll, dedupe, and snapshots; added commands `seed_management_defaults`, `compute_nightly_scores`, `process_telephony_webhooks`, `reconcile_call_records`, and `refresh_dtf_bridge_snapshot`.
- Added telephony/DTF foundation models: `OwnershipChangeLog`, `TelephonyWebhookLog`, `CallRecord`, `TelephonyHealthSnapshot`, `CallQAReview`, `SupervisorActionLog`, and `DtfBridgeSnapshot`.
- Added canonical service modules: `config_versions`, `trust`, `followups`, `forecast`, `advice`, `appeals`, and `telephony`.
- Extended phase-5/phase-2 models with follow-up ladder fields, payout evidence/freeze fields, and richer score appeal metadata.
- Surfaced shadow score data in stats/admin payload and UI with `Why changed today`, `Must do today`, `Best opportunities`, `Rescue top-5`, `Salary simulator`, admin readiness/incidents, and forecast widgets.
- Added reminder digesting/overload accounting and new management commands: `send_management_reminders` and `check_duplicate_queue`.

## Next Slice

1. Finish phase-8 validation plumbing and explicit activation controls in UI/admin workflows.
2. Decide the safest server exposure path: separate Passenger preview checkout if publicly routable, otherwise controlled branch deploy on the live management checkout with rollback-ready git state.
3. After deploy, run smoke verification for management stats/admin/payouts/parsing plus non-regression checks on the main site and DTF subdomain.
