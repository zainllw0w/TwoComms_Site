# Django 6.1 Stage 5: non-DTF MyISAM to InnoDB roadmap (DJ6-SRV-003)

Дата: 2026-08-18
Статус: planning/read-only; production acceptance не заявляется.

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
| `orders.Order` / `orders_order` | **unknown**; historical F-102 evidence was MyISAM, later report says checkout set converted | Very high; orders and payment state; size **unknown** | High: payment, attribution, user/session references; MyISAM cannot enforce transactional rollback | 3, after independent reference tables and before dependent audit/event tables | Full backup + restore rehearsal; row/checksum baseline; write freeze or online-DDL plan; dual read-only order/payment canary; rollback is restore/switchover, never reverse `ALTER` blindly |
| `storefront.UTMSession` / `storefront_utmsession` | **unknown**; historical F-102 evidence was MyISAM, later report says checkout set converted | High; attribution and conversion joins; size **unknown** | High: `UserAction`, order attribution and session keys; orphan scan required | 2, with other attribution/session tables | Snapshot counts and representative attribution joins; verify no open writers; restore plan and post-cutover reconciliation |
| `storefront.Product` / `storefront_product` | **unknown**; tracked catalog plans identify it as legacy MyISAM-backed | High; catalog read path and product identity; size **unknown** | High: logical links from newer InnoDB catalog tables intentionally use `db_constraint=False`; FK creation must remain disabled until parent is InnoDB | 4, after order/session canary and after catalog dependents are mapped | Catalog read/price/stock canary; index/charset/collation comparison; backup and reversible cutover; no FK addition in same change |
| `productcolors_*` legacy color tables | **unknown**; tracked catalog plans identify legacy MyISAM links | High; variant/color selection and pricing; size **unknown** | High: product catalog links are logical, not enforced FKs; orphan variant IDs and duplicate natural keys must be measured | 5, one table family at a time after `storefront_product` | Per-family row/index/price reconciliation; selected-variant checkout canary; restore tested before next family |
| `auth.User` / `auth_user` | **unknown**; historical incident report described MyISAM | Critical shared identity table; size **unknown** | Critical: admin, orders, management and audit references; incompatible FK targets can fail DDL | 1 (only after a standalone compatibility proof); otherwise hold and use logical references | Confirm all referencing columns/types/collations; no FK changes in engine slice; login/admin/order read canaries; tested restore and maintenance window |
| `management.IgClient` / `management_igclient` | **unknown**; historical plan listed MyISAM before a later 12-table conversion | High; CRM identity and conversation ownership; size **unknown** | High: many durable IG tables use logical `db_constraint=False`; orphan client IDs must be reported | 6, after shared identity and catalog dependencies | Bot read-only conversation lookup; no outbound transport; snapshot + orphan report; rollback by restore/switchover |
| `management.InstagramBotMessage` / `management_instagrambotmessage` | **unknown**; historical plan listed MyISAM before later conversion | Critical append/read message history; size **unknown** | High: follow-up/deal/analysis references and provider IDs; duplicate/idempotency checks required | 7, after `IgClient` and before dependent append-only tables | No-network replay/read canary; provider IDs and counts reconcile; backup, trigger inventory, restore drill |
| `management.IgFollowUpTask`, `management.IgDeal` / corresponding tables | **unknown**; historical plan listed MyISAM before later conversion | High; manager workflow and sales state; size **unknown** | High: references to client/message; orphan and uniqueness checks required | 8, dependency order after client/message | Queue/CRM read-only canary, no sends; verify leases/status counts; restore/switchover rollback |
| `warehouse.*`, `finance.*`, remaining non-DTF legacy tables | **unknown**; no local per-table engine evidence | Criticality and size **unknown**; classify from live usage before scheduling | Unknown; inspect constraints, triggers, Django `db_table`, raw SQL and cron writers | 9+, risk-ranked batches only after full inventory | Domain-specific read-only canaries, trigger/foreign-key inventory, backup/restore and load/lock budget; do not batch unknown critical tables |

The historical IG rows must not be interpreted as a current defect: tracked
planning evidence also records a later 12-table conversion and a 12/12 engine
health check. The current engine for every IG table remains `unknown` until a
new read-only `information_schema` result is attached to the release evidence.

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
5. **Batch rollout:** migrate only one dependency layer at a time in the order
   above. Capture before/after counts, checksums where practical, engine,
   indexes, triggers, and error/lock metrics. Stop on any mismatch.
6. **Rollback gate:** rollback means restoring the verified backup or switching
   to a prepared replica/snapshot according to the approved runbook. Do not
   assume `ALTER TABLE ... ENGINE=MyISAM` is a safe rollback: it can lose
   transactional guarantees and may not preserve concurrent writes.
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
