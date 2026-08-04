# 11_FINAL_VALIDATION_REPORT — production validation checkpoint through 2026-08-05

## Scope

This checkpoint validates the durable funnel analytics, bounded
superseded-invoice recovery and variant-specific prompt price/size parity
slices. It also reconciles the follow-up worktree backlog into
`07_IMPLEMENTATION_PLAN.md` as the self-contained handoff. It does not claim
that the remaining implementation backlog is complete.

## Local evidence

- Current runtime baseline: `0ad694bc` (variant-specific prompt price/size parity on top of typed graph/ranker and commercial episode recovery).
- Unrelated Custom Print and asset WIP remains unstaged and uncommitted.
- Required audit artifacts `00`–`12` are present.
- `07_IMPLEMENTATION_PLAN.md` is the task-status authority and contains
  individual checkbox matrices for all **175 `F-*` findings** and all **50
  `IMPR-*` improvements**. Finding status is **130 checked / 39 open / 6
  partial**; improvement status is **14 checked / 36 unfinished**.
- Implementation status is **103 `IMP-*`: 76 checked, 23 open, 4 partial**.
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
- Identifier reconciliation: 175/175 findings and 50/50 improvements match
  their canonical registers; no missing/extra IDs across refs, worktrees or
  stashes.
- Production MySQL migration state through `0133`: applied.
- Production MySQL migration `0134_ig_deal_invoice_lifecycle`: applied; bounded
  superseded-invoice check-only returned zero candidates and the lifecycle table
  is empty because the dataset has no historical superseded IDs.

## Production evidence

Historical IMP-058 deployment evidence: commits `274c2c61`, `79882368`,
`92d46c5a` were deployed after push; server HEAD at that checkpoint was
`92d46c5ac68bf7b936c7ee6aaa4e5d82695b550f`. Its production
`status_snapshot()` reported `is_enabled=True`, `state='running'`, `alive=True`,
`running=True`, transport `instagram_login`, database and daemon heartbeat ages
of `0.0` seconds, and empty `last_error`. The exact pull, Django
check/migration-drift, and restart history is recorded in
`09_DEPLOYMENT_LOG.md`.

IMP-089 implementation commit `280c07e8` and final deployed checkpoint
`6883ac2c` are in `origin/main` and production.
MariaDB migration `0134` is applied; bounded check-only reported zero current,
superseded, projection and order candidates, and the lifecycle table has zero
rows because this dataset contains no historical superseded invoice IDs. The
daemon recovered from the restart's transient worker error and reports
`running=True`, `last_error=''`.

## F-PAY-015 / IMP-081 checkpoint (2026-08-05)

Daemon collision fix `93ae8684` passed 134 local commercial/payment tests,
check, migration drift and compileall. Production MySQL reconcile in three
passes returned zero remaining sources; after restart the daemon is
running/alive on `instagram_login` with empty error and zero active queues.
Client `59` retains separate canonical and superseded timelines with no current
terminal pointer.

The `IMP-081` semantic/inventory foundation is also confirmed in production:
`storefront.0088` and `fable5.0008` are applied, all three tables use InnoDB,
there are 77 explicit policies (`29 warehouse`, `48 untracked`), and revision
UPDATE/DELETE triggers exist. It remains PARTIAL because runtime/admin consumers
and a disposable MariaDB test gate are still missing.

## IMP-082/083 checkpoint (2026-08-05, deployed PARTIAL)

Commits `7b5d5cc7` and `1c4d6d48` established the typed graph/ranker.
`e44d1440` and `0ad694bc` then fixed F-CAT-007 by binding prompt sizes to exact
variant+fit and separating authoritative empty size contracts from missing
variant-specific sources. Current evidence: 188 focused tests, complete
2675-test management suite (3 skipped), Django check, migration drift,
compileall and diff check.

Production product 110 prompt proof: `variant_id=81`, thermo green, exact
1450 грн, oversize XS/M; false `XS/S/M/L/XL/XXL` product-wide sizes are absent.
One daemon is running on `0ad694bc` with `running=True`, `alive=True`, heartbeat
0.1 s, `instagram_login`, empty error and reply/notification queues. F-CAT-007
is FIXED/VERIFIED. IMP-082/083 remain PARTIAL because graph/ranker are not yet
the durable runtime commerce-session source and lack stale binding, relaxed
alternatives and full print/blank/media topology.

## IMP-094 checkpoint (2026-08-04, deployed; MariaDB gate still open)

The reliability slice passes the full `management` suite twice:
**2619 tests, 3 skipped, `OK`** from the worktree root and from `twocomms`.
The focused gate passes **136 tests**, and detached-worker/recovery regressions
pass **6 tests**. The changes also pass `git diff --check`.

This is SQLite evidence only. Commit `15147ded` is in `main` and production;
`manage.py check` and migration-drift passed, then the standard `--ensure`
command restored the restarted daemon to `running=True`, `alive=True` with
empty `last_error`. A separately provisioned disposable MariaDB instance is
still required for the DB-contract gate; production MySQL was not used for
tests. Until that run, `IMP-094` and `F-TEST-002` remain unchecked.

## Acceptance decision

The IMP-058, IMP-089, IMP-077, F-PAY-015, F-CAT-007 and IMP-082/083 foundation
slices are verified and deployed. Product/data blockers, partial W9 reselection,
remaining W8/W9/W10 work, `IMP-098` and W12 `IMP-102/103` remain explicitly
open. The next implementation must start from this file set; no status may be
inferred from an old branch or historical progress paragraph without updating
the checkbox and evidence matrix.

## IMP-077 completion (2026-08-04)

`221cf37d` closes F-OPS-009 after the original flow-control slice: terminal
UNKNOWN/DEAD_LETTER outcomes receive a bounded redacted summary rather than an
unsafe resend; lifecycle window/delivery alerts have separate keys; a failed
paylink produces exactly one actionable manager alert. 75 focused tests passed
after rebase. Production fast-forward, `manage.py check`, daemon ensure and
`status_snapshot()` are recorded in `09`: bot running/alive on
`instagram_login`, no last error and zero terminal outbox rows.
