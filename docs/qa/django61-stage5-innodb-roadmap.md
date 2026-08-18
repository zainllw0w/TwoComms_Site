# Django 6.1 Stage 5: non-DTF MyISAM to InnoDB roadmap (DJ6-SRV-003)

Дата: 2026-08-18
Статус: planning/read-only; production acceptance не заявляется. Tooling и
disposable rehearsal contract добавлены, но production inventory/canary ещё не
подтверждены.

## Scope and evidence boundary

Цель DJ6-SRV-003 - подготовить управляемую поэтапную замену legacy MyISAM в
production MariaDB для non-DTF части проекта. Этот документ не выполняет
`ALTER TABLE`, не применяет migrations и не является разрешением на изменение
production.

В checkout нет свежего per-table `information_schema` dump: поэтому размер,
точный текущий engine, строки, индексы, orphan count и FK graph для отдельных
таблиц ниже помечены `unknown`, если их нельзя подтвердить tracked evidence.
Единственный текущий sanitized aggregate из Stage 0:

| Scope | Tables | InnoDB | MyISAM | Triggers | Routines/events |
| --- | ---: | ---: | ---: | ---: | ---: |
| Production alias `default`, base tables, DTF excluded | 332 | 142 | 190 | 25 | 0 / 0 |

Источник aggregate: `docs/qa/django61-stage0-baseline.md` (Stage 0 snapshot
rehearsal). Этот snapshot не является point-in-time доказательством для MyISAM:
`--single-transaction` согласует InnoDB, но MyISAM требует maintenance lock либо
перевода в InnoDB. Поэтому ни одна строка ниже не считается live acceptance.

## Read-only inventory and migration candidates

`Historical evidence` означает только то, что таблица/связь так описывалась в
tracked reports; перед любой миграцией engine нужно заново снять
`information_schema.tables`, `table_constraints`, `key_column_usage`, размеры,
row counts и orphan queries на production read-only preflight.

| Model / table | Engine (current) | Size / criticality | Orphan / FK risk | Migration order | Canary / rollback prerequisites |
| --- | --- | --- | --- | --- | --- |
| `orders.Order` / `orders_order` | **unknown**; historical F-102 evidence was MyISAM, later report says checkout set converted | Very high; orders and payment state; size **unknown** | High: payment, attribution, user/session references; MyISAM cannot enforce transactional rollback | derived from live FK/writer graph | Full backup + restore rehearsal; row/checksum baseline; write freeze or online-DDL plan; dual read-only order/payment canary; rollback requires write-loss-safe sync, never backup restore alone |
| `storefront.UTMSession` / `storefront_utmsession` | **unknown**; historical F-102 evidence was MyISAM, later report says checkout set converted | High; attribution and conversion joins; size **unknown** | High: `UserAction`, order attribution and session keys; orphan scan required | derived from live FK/writer graph | Snapshot counts and representative attribution joins; verify no open writers; restore plan and post-cutover reconciliation |
| `storefront.Product` / `storefront_product` | **unknown**; tracked catalog plans identify it as legacy MyISAM-backed | High; catalog read path and product identity; size **unknown** | High: logical links from newer InnoDB catalog tables intentionally use `db_constraint=False`; FK creation must remain disabled until parent is InnoDB | derived from live FK/writer graph | Catalog read/price/stock canary; index/charset/collation comparison; backup and reversible cutover; no FK addition in same change |
| `productcolors_*` legacy color tables | **unknown**; tracked catalog plans identify legacy MyISAM links | High; variant/color selection and pricing; size **unknown** | High: product catalog links are logical, not enforced FKs; orphan variant IDs and duplicate natural keys must be measured | derived from live FK/writer graph | Per-family row/index/price reconciliation; selected-variant checkout canary; restore tested before next family |
| `auth.User` / `auth_user` | **unknown**; historical incident report described MyISAM | Critical shared identity table; size **unknown** | Critical: admin, orders, management and audit references; incompatible FK targets can fail DDL | derived from live FK/writer graph; hold if unresolved | Confirm all referencing columns/types/collations; no FK changes in engine slice; login/admin/order read canaries; tested restore and maintenance window |
| `management.IgClient` / `management_igclient` | **unknown**; historical plan listed MyISAM before a later 12-table conversion | High; CRM identity and conversation ownership; size **unknown** | High: many durable IG tables use logical `db_constraint=False`; orphan client IDs must be reported | derived from live FK/writer graph | Bot read-only conversation lookup; no outbound transport; snapshot + orphan report; rollback by restore/switchover |
| `management.InstagramBotMessage` / `management_instagrambotmessage` | **unknown**; historical plan listed MyISAM before later conversion | Critical append/read message history; size **unknown** | High: follow-up/deal/analysis references and provider IDs; duplicate/idempotency checks required | derived from live FK/writer graph | No-network replay/read canary; provider IDs and counts reconcile; backup, trigger inventory, restore drill |
| `management.IgFollowUpTask`, `management.IgDeal` / corresponding tables | **unknown**; historical plan listed MyISAM before later conversion | High; manager workflow and sales state; size **unknown** | High: references to client/message; orphan and uniqueness checks required | derived from live FK/writer graph | Queue/CRM read-only canary, no sends; verify leases/status counts; restore/switchover rollback |
| `warehouse.*`, `finance.*`, remaining non-DTF legacy tables | **unknown**; no local per-table engine evidence | Criticality and size **unknown**; classify from live usage before scheduling | Unknown; inspect constraints, triggers, Django `db_table`, raw SQL and cron writers | derived from live FK/writer graph; unknown nodes block | Domain-specific read-only canaries, trigger/foreign-key inventory, backup/restore and load/lock budget; do not batch unknown critical tables |

The historical IG rows must not be interpreted as a current defect: tracked
planning evidence also records a later 12-table conversion and a 12/12 engine
health check. The current engine for every IG table remains `unknown` until a
new read-only `information_schema` result is attached to the release evidence.

### Canary decision

The only small-table candidate available for a disposable rehearsal is
`storefront_promocodegroup`: tracked code identifies this legacy table as
MyISAM-compatible, and the local SQLite production-like copy contains one row.
That is sufficient to exercise the ranking/tooling contract only; SQLite does
not prove the current MariaDB engine, lock behavior, triggers, or writers.
Therefore the production canary remains **blocked** until the sanitized
per-table inventory reports current `MyISAM`, row/size limits, zero writers,
zero triggers, and no FK links. The candidate is never migrated by this change.

Run the read-only tool with a sanitized export:

```bash
python scripts/build_innodb_stage5_inventory.py inventory.json \
  --output stage5-inventory-report.json
```

## Recommended execution gates

1. **Inventory gate (read-only):** on the approved production SSH path, export
   only sanitized rows for `information_schema.tables` (table name, engine,
   `data_length`, `index_length`, `table_rows`), constraints, triggers, and
   database/table allowlist. Exclude DTF databases and credentials. Record the
   query timestamp and server/database identity.
2. **Dependency gate:** map Django model `db_table`, raw SQL, scheduled writers,
   triggers, and all logical `db_constraint=False` links. Run orphan and
   duplicate-key queries before choosing a batch. Any unknown dependency blocks
   that table.
3. **Backup/restore gate:** take an approved backup, restore it into an
   explicitly named disposable local MariaDB database, and compare table
   counts, engines, indexes, triggers, and representative business totals.
   Keep artifacts outside Git with restrictive permissions.
4. **Canary gate:** select one low-volume table family, schedule a maintenance
   or lock budget, measure metadata lock time and write latency, then run
   read-only order/catalog/CRM reconciliation. No live ad, payment, Telegram,
   Meta, or DTF activity is part of this gate.
5. **Batch rollout:** migrate only one dependency layer at a time in the
   tooling-generated `dependency_order`. Capture before/after counts, checksums where practical, engine,
   indexes, triggers, and error/lock metrics. Stop on any mismatch.
6. **Rollback gate:** backup restore alone is not rollback-safe because writes
   after the backup can be lost. Use one of: (a) a maintenance window with an
   explicit write freeze and verification before/after DDL; (b) dual-write plus
   reverse synchronization of the changed table; or (c) replica/snapshot
   switchover with binlog/GTID reconciliation. The tooling rejects backup-only
   plans and reverse `ALTER TABLE ... ENGINE=MyISAM` is never assumed safe.
7. **Acceptance gate:** DJ6-SRV-003 is complete only when production evidence
   shows the intended engines, zero unexplained orphans, preserved triggers and
   indexes, successful canaries, and a tested rollback path. This document alone
   cannot mark that checkbox complete.

## Explicit non-goals

- No DDL, `ALTER TABLE`, migration application, backup, or production SSH was
  performed for this document.
- No table size, per-table engine, row count, orphan count, or FK status is
  inferred from model declarations or local SQLite.
- No production acceptance, zero-downtime claim, or rollback success is claimed.
- No fixed migration order is authoritative: the order must be generated from
  the sanitized FK graph and writer dependencies; unresolved nodes block.
