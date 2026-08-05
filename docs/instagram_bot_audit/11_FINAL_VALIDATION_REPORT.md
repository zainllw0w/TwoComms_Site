# 11_FINAL_VALIDATION_REPORT — production validation checkpoint through 2026-08-05

## Scope

This checkpoint validates the durable funnel analytics, bounded
superseded-invoice recovery, authoritative configuration pricing, exact availability foundation, event-driven
follow-up continuation, provider-evidenced delivery FSM and sender-action
observability. It reconciles the current implementation backlog into
`07_IMPLEMENTATION_PLAN.md`; remaining W5/W8/W9/W10/W11 work is still open.

## Local evidence

- Current runtime baseline: `17f5b672` (event continuation, configuration pricing, sender observability, durable escalation and exact availability foundation on top of the prior delivery/prompt/payment foundations).
- Unrelated Custom Print and asset WIP remains unstaged and uncommitted.
- Required audit artifacts `00`–`12` are present.
- `07_IMPLEMENTATION_PLAN.md` is the task-status authority and contains
  individual checkbox matrices for all **179 `F-*` findings** and all **51
  `IMPR-*` improvements**. Finding status is **134 checked / 39 open / 6
  partial**; improvement status is **17 checked / 34 unfinished**.
- Implementation status is **104 `IMP-*`: 79 checked, 20 open, 5 partial**.
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
- IMP-102 gates: 23/23 focused and 160/160 expanded. The full management run
  executed 2696 tests with 1 failure and 7 errors: four were missing
  `FIELD_ENCRYPTION_KEY`; the remaining objection cases reproduce the known
  SQLite append-only trigger/flush isolation issue outside the delivery path.
- Production MariaDB: migration `0133` applied; canonical backfill created 5
  events, deterministic silence scan created 96 drop-offs; raw-event/API
  reconciliation reported 197 events and 17 event types.
- Identifier reconciliation: 179/179 findings and 51/51 improvements match
  their current canonical registers and checkbox matrices; F-FUP-013 is present
  in both.
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

## IMP-084 checkpoint (2026-08-05, deployed PARTIAL)

`17f5b672` integrates the exact availability foundation from the preserved
`e9d982df` source without importing its old branch base. `resolve_allocation`
honors the explicit `ProductInventoryPolicy`, returns exact warehouse
`StockItem` or catalog-variant facts, aggregates repeated allocation identities
in a basket, and fails closed on missing or ambiguous warehouse mappings.
Availability coverage is 5/5 tests; the combined availability/checkout/
follow-up/live-visual/restock gate is 277 tests. Production fast-forward,
`manage.py check`, migration drift and daemon ensure passed; server SHA is
`17f5b672fc03f405b63cc173cb866043d7a377a2`.

`IMP-084` remains PARTIAL: readiness/proposal/hosted-checkout wiring must carry
all allocation identities, and reservation/write-off/reversal lifecycle plus
disposable MariaDB proof remain `IMP-086`/`IMP-088`.

## IMP-102 / F-FUP-013 checkpoint (2026-08-05, deployed)

`0d4d38c0`, `0e9e9ba5`, `4cb86743` and `414e639e` implement explicit
`PROCESSING/SENT/AMBIGUOUS/COMPLETED`, receipt-first crash recovery without
resend, audited manager resolution and lock-safe preservation of a concurrently
finalized `SENT`. The delivery boundary passed 23/23 focused and 160/160
expanded tests plus Django check, migration drift, compileall and diff check.

Production HEAD is `414e639eced30a01ff2c5553b08605099465478c` with
`management.0141` applied. Exactly one daemon is `running/alive` on
`instagram_login`, `last_error=''`; processing, ambiguous,
sent-without-message and delivery-review queues are empty. IMP-102,
IMPR-FUP-014 and F-FUP-013 are closed. Exact event payload/time, absolute
policy timeline and pre-send invoice/restock recheck remain IMP-103.

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

## IMP-103 / IMP-104 current acceptance

`IMP-103` is closed and deployed through `35d3bd93`: event continuation stores
immutable event facts, derives an absolute policy timeline, rechecks invoice and
restock truth immediately before send, and keeps continuation auditable. The
focused event/FSM/checkout/restock gate is 255 tests.

`IMP-104` is closed and deployed through `1f8cead2`: selected configuration
prices are authoritative across speech, readiness, proposal, deal and hosted
checkout. Ambiguous exact claims and invalid option contexts fail closed; the
checkout renders selected option facts and line totals. The authoritative-price
gate is 12 tests.

The runtime code baseline is `434428ad`; production code SHA is
`434428ad1ff0c6892b0f2c56456e01555d082f48`. Migration `0143` is applied and production
has one healthy `instagram_login` daemon with empty pending reply/notification
queues.

## Acceptance decision

The IMP-058, IMP-089, IMP-077, F-PAY-015, F-CAT-007, IMP-084 foundation, IMP-102/F-FUP-013,
IMP-103/IMPR-FUP-015 and IMP-104/F-CAT-008/009/010 foundation slices are verified
and deployed. Product/data blockers, partial W9 reselection, remaining
W5/W8/W9/W10/W11 work and `IMP-098` remain explicitly open. The next
implementation must start from this file set;
no status may be inferred from an old branch or historical progress paragraph
without updating the checkbox and evidence matrix.

## IMP-077 completion (2026-08-04)

`221cf37d` closes F-OPS-009 after the original flow-control slice: terminal
UNKNOWN/DEAD_LETTER outcomes receive a bounded redacted summary rather than an
unsafe resend; lifecycle window/delivery alerts have separate keys; a failed
paylink produces exactly one actionable manager alert. 75 focused tests passed
after rebase. Production fast-forward, `manage.py check`, daemon ensure and
`status_snapshot()` are recorded in `09`: bot running/alive on
`instagram_login`, no last error and zero terminal outbox rows.
