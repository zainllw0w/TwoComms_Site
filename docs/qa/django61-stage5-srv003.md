# Django 6.1 Stage 5: MyISAM -> InnoDB roadmap evidence (DJ6-SRV-003)

Date: 2026-08-18

Status: complete for the roadmap, read-only production inventory, and
disposable canary gates. This is not a production engine-conversion release.

## Scope and safety boundary

This evidence excludes DTF. Production MariaDB was queried read-only through
the normal SSH environment. No production `ALTER TABLE`, migration, backup,
restore, write-freeze, or schema/data mutation was performed.

The captured production default alias reported MariaDB `11.4.12`, 320 non-DTF
base tables, 143 InnoDB tables, 177 MyISAM tables, 39 physical foreign-key
edges, and 13 tables with triggers. MariaDB `TABLE_ROWS` is an estimate, so the
matrix does not represent it as an exact count.

## Approved matrix and order

[`django61-stage5-srv003-matrix.json`](django61-stage5-srv003-matrix.json)
contains every current non-DTF MyISAM target with:

- Django model or an explicit unmapped/through-table blocker;
- current engine, estimated row count, data and index size;
- criticality, physical FK degree, trigger and FULLTEXT facts;
- explicit risk and a deterministic preflight sequence;
- a separate `writer_audit_complete` and `orphan_scan_complete` state.

All 177 MyISAM rows are deliberately marked
`blocked_pending_writer_orphan_and_domain_preflight`. None has a false
zero-writer or zero-orphan claim; consequently the matrix approves zero
production DDL targets and zero production canary candidates. The sequence is
the approved order for *read-only preflight*, not permission to run DDL:
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

The shadow-table rollback is valid evidence only for a no-write disposable
schema. It is not a production rollback strategy: any production conversion
still requires an approved backup/restore drill plus either a maintenance write
freeze, dual-write/reverse synchronization, or a reconciled replica/snapshot
switchover.

## Regression gate

The focused inventory and canary contracts pass with the shared CPython
3.14.6/Django 6.1 runtime. The inventory now fails closed when writer or orphan
evidence is absent, preventing an incomplete snapshot from selecting a canary.

```bash
TWC_PYTHON="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.venv/bin/python"
"$TWC_PYTHON" -m unittest tests.test_django61_stage5_innodb_tooling tests.test_django61_stage5_innodb_canary -v
```

## Explicit non-goals

- No production MyISAM table was converted.
- No database-level cascade or generated column was introduced by this slice.
- `DJ6-MIG-001` migration squashing remains independent and open.
