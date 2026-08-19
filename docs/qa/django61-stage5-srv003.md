# Django 6.1 Stage 5: MyISAM -> InnoDB roadmap evidence (DJ6-SRV-003)

Date: 2026-08-19

Status: the historical read-only roadmap and disposable rehearsal remain the
baseline for the 176 remaining MyISAM targets. A single approved production
exception, `reviews_reviewvote`, was subsequently converted and is recorded in
`django61-stage5-production-canary-2026-08-19.{md,json}`. This document must
not be read as permission for any other production engine conversion.

## Scope and safety boundary

This evidence excludes DTF. The original inventory below was queried read-only
through the normal SSH environment and did not authorize DDL. The later
`reviews_reviewvote` production canary and its backup/write-freeze proof are
documented separately; no other table in this roadmap was changed.

The captured production default alias reported MariaDB `11.4.12`, 320 non-DTF
base tables, 143 InnoDB tables, 177 MyISAM tables, 39 physical foreign-key
edges, and 13 tables with triggers. MariaDB `TABLE_ROWS` is an estimate, so the
matrix does not represent it as an exact count.

## Read-only matrix and preflight order

[`django61-stage5-srv003-matrix.json`](django61-stage5-srv003-matrix.json)
contains every current non-DTF MyISAM target with:

- Django model or an explicit unmapped/through-table blocker;
- current engine, estimated row count, data and index size;
- criticality, physical FK degree, trigger and FULLTEXT facts;
- explicit risk and a deterministic preflight sequence;
- a separate `writer_audit_complete` and `orphan_scan_complete` state.

The historical snapshot marked all 177 MyISAM rows
`blocked_pending_writer_orphan_and_domain_preflight`. That snapshot predates
the separately approved `reviews_reviewvote` canary; the remaining 176 targets
retain that HOLD. The sequence is the order for *read-only preflight*, not
permission to run DDL:
low-risk/small families are reviewed first, then medium, high, critical, and
unmapped tables. A table can leave HOLD only after a domain-specific writer,
orphan, index/FULLTEXT, trigger, and rollback review.

## Disposable MariaDB canary

One local MariaDB `11.4.12` rehearsal ran through the existing fail-closed
`run_disposable_innodb_canary()` contract. It used a fresh temporary datadir,
loopback port, temporary user named `twc_dj61_disposable_stage5`, random
database, and automatic cleanup. The synthetic 250-row MyISAM table was backed
up to a shadow table, converted to InnoDB, then restored to MyISAM and checked
by engine, row count, and SHA-256 digest.

| Check | Result |
| --- | --- |
| Shadow backup verification | passed in 0.018076 s |
| MyISAM -> InnoDB conversion | passed in 0.047288 s |
| Rollback verification | passed in 0.049011 s |
| Temporary schema cleanup | verified |

The runner now requires a versioned offline `preflight` proof before it opens
even the disposable MariaDB connection. The proof is rejected unless all of
the following agree:

- the selected non-DTF table has exact row evidence, complete index inventory,
  matching index SHA-256, and a `MyISAM -> InnoDB` engine contract;
- FULLTEXT inventory is complete and contains zero indexes;
- writer and orphan audits are complete and both counts are zero;
- a real, absolute, non-symlink backup artifact exists and its non-zero size
  and computed SHA-256 match the declared backup evidence;
- backup row/index evidence matches the selected candidate;
- conversion and rollback rehearsal timings are positive and do not exceed one
  declared approved limit;
- rollback was rehearsed and verified, restores the row/index/backup contract,
  and is write-loss-safe through either a verified maintenance write freeze or
  verified reverse synchronization for an approved online strategy.

Missing, malformed, stale, or contradictory evidence fails before
`connection_factory(None)`, `CREATE DATABASE`, or any other SQL. The validated
report exposes only sanitized counts, digests, timings, and strategy; it does
not expose the local backup path.

The shadow-table rollback is valid evidence only for a no-write disposable
schema. It is not a production rollback strategy: any production conversion
still requires an approved backup/restore drill plus either a maintenance write
freeze, dual-write/reverse synchronization, or a reconciled replica/snapshot
switchover.

## Regression gate

The focused inventory and canary contracts pass with the shared CPython
3.14.6/Django 6.1 runtime. The inventory fails closed when writer or orphan
evidence is absent, and the canary runner independently blocks all connection
and DDL work until the complete preflight proof above is validated.

```bash
TWC_PYTHON="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.venv/bin/python"
"$TWC_PYTHON" -m unittest tests.test_django61_stage5_innodb_tooling tests.test_django61_stage5_innodb_canary -v
```

## Explicit non-goals

- No remaining bulk MyISAM target was converted. The sole exception is the
  separately evidenced `reviews_reviewvote` canary.
- No database-level cascade or generated column was introduced by this slice.
- `DJ6-MIG-001` migration squashing remains independent and open.
