# 11_FINAL_VALIDATION_REPORT — IMP-058/089 production validation checkpoint 2026-08-03

## Scope

This checkpoint validates the durable funnel analytics and bounded
superseded-invoice recovery slices and keeps
`07_IMPLEMENTATION_PLAN.md` as the self-contained handoff. It does not claim
that the remaining implementation backlog is complete.

## Local evidence

- Current runtime baseline: `280c07e8` (IMP-089 superseded-invoice recovery).
- Unrelated Custom Print and asset WIP remains unstaged and uncommitted.
- Required audit artifacts `00`–`12` are present.
- `07_IMPLEMENTATION_PLAN.md` is the task-status authority and contains
  individual checkbox matrices for all **170 `F-*` findings** and all **48
  `IMPR-*` improvements**. Finding status is **120 checked / 46 open / 4
  partial**; improvement status is **14 checked / 34 unfinished**.
- Implementation status is **99 `IMP-*`: 72 checked, 25 open, 2 partial**.
- `02` remains the 120-item audit coverage authority; `03` and `05` remain the
  detailed finding/improvement evidence registers.

## Verification evidence

- 45/45 `management.tests_ig_audit_fixes`.
- 53 funnel/follow-up, 161 analysis/inbox/intelligence, and 103
  commercial/funnel regression tests.
- `python manage.py check`: no issues.
- `python manage.py makemigrations --check --dry-run`: no changes detected.
- `python -m compileall -q` for changed IG service/tests: exit 0.
- `git diff --check`: exit 0 before code commit.
- Production MariaDB: migration `0133` applied; canonical backfill created 5
  events, deterministic silence scan created 96 drop-offs; raw-event/API
  reconciliation reported 197 events and 17 event types.
- Identifier reconciliation: 170/170 findings and 48/48 improvements match
  their canonical registers; no missing/extra IDs across refs, worktrees or
  stashes.
- Production MySQL migration state through `0133`: applied.
- Production MySQL migration `0134_ig_deal_invoice_lifecycle`: applied; bounded
  superseded-invoice check-only returned zero candidates and the lifecycle table
  is empty because the dataset has no historical superseded IDs.

## Production evidence

The IMP-058 code commits `274c2c61`, `79882368`, `92d46c5a` are deployed after
push; server HEAD is `92d46c5ac68bf7b936c7ee6aaa4e5d82695b550f`. The current production
`status_snapshot()` reports `is_enabled=True`, `state='running'`, `alive=True`,
`running=True`, transport `instagram_login`, database and daemon heartbeat ages
of `0.0` seconds, and empty `last_error`. The exact pull, Django
check/migration-drift, and restart history is recorded in
`09_DEPLOYMENT_LOG.md`.

IMP-089 implementation commit `280c07e8` is in `origin/main` and production.
MariaDB migration `0134` is applied; bounded check-only reported zero current,
superseded, projection and order candidates, and the lifecycle table has zero
rows because this dataset contains no historical superseded invoice IDs. The
daemon recovered from the restart's transient worker error and reports
`running=True`, `last_error=''`.

## Acceptance decision

The IMP-058 and IMP-089 slices are verified and deployed. Product/data pricing
blockers, branch-only reselection, W8/W9/W10 work and `IMP-098` remain explicitly
open. The next implementation must start from this file set; no status may be
inferred from an old branch or historical progress paragraph without updating
the checkbox and evidence matrix.
