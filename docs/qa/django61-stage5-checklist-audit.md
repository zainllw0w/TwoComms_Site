# Django 6.1 Stage 5: checklist evidence audit

Дата аудита: 2026-08-18 (матрица захвачена `2026-08-18T23:48:07+03:00`).
Это audit tracked evidence для Stage 5, а не заявление о публикации или
production rollout. Актуальная sanitized matrix и disposable rehearsal
зафиксированы в этом release candidate; origin/main проверяется отдельно
при интеграции и здесь намеренно не подменяется старым SHA.
Scope: только non-DTF MariaDB/Django evidence. Production schema, данные,
migrations, storefront и parser в рамках этого документа не изменялись.

## Как читать решения

`READ-ONLY/REHEARSAL CLOSED` означает, что соответствующий безопасный
инвентаризационный или disposable gate имеет tracked evidence. Для четырёх
пунктов, чья формулировка ограничена именно такой проверкой (`DJ6-SRV-004`,
`DJ6-SRV-006`, `DJ6-DB-001`, `DJ6-ORM-013`), это отражено отметкой `[x]` в
плане. Эта отметка не означает, что production DDL, migration или rollout
разрешены либо что закрыт Stage 5 exit gate.

`NO-GO` означает, что обязательное production-доказательство, согласованный
DDL-дизайн или обратимый rollout отсутствует либо есть блокирующее
несоответствие. Для таких пунктов чекбокс плана оставляется пустым.

Указанные ниже commit SHA являются provenance исходных evidence-срезов,
перенесённых в Stage 5 release candidate. Кандидат до отдельного safety gate
не заявляется как опубликованный в `main` или развернутый на production.

## Матрица

| ID | Evidence и что реально проверено | Решение сейчас | Что нельзя утверждать / следующий обязательный gate |
| --- | --- | --- | --- |
| `DJ6-SRV-003` | `docs/qa/django61-stage5-srv003-matrix.json` содержит свежую sanitized read-only матрицу: `320` non-DTF base tables, `143` InnoDB, `177` MyISAM targets, `39` physical FK edges и `13` tables with triggers. Все `177` строк заблокированы до writer/orphan/domain preflight; `167` имеют риск `blocked_unmeasured_writer_and_orphan_risk`, `10` являются unmapped/through-table blockers, `0` production DDL targets и `0` canary candidates approved. `scripts/run_stage5_innodb_canary.py` отдельно прошёл disposable MariaDB 11.4.12 rehearsal с backup, conversion, rollback и cleanup. | **READ-ONLY/REHEARSAL CLOSED**, но **NO-GO** для production migration. | Нельзя считать матрицу разрешением на DDL или production canary. Для снятия HOLD нужны подтверждённые writer/orphan/domain facts, approved table order и отдельный production-compatible canary с backup/rollback evidence. |
| `DJ6-SRV-004` | `docs/qa/django61-stage5-connection-budget.md` (candidate `a34d7589c`/`566102c86`) и connection gate в `scripts/run_django61_live_matrix.py` (candidate `bc4d0edc1`). Read-only baseline: MariaDB `11.4.12`, `max_connections=150`, `max_user_connections=20`, `wait_timeout=60`, effective `CONN_MAX_AGE=0`, `CONN_HEALTH_CHECKS=True`; gate также проверяет usage counters и запрещает DTF alias. | **READ-ONLY/REHEARSAL CLOSED** для текущего connection-policy guard; **NO-GO** для расширения worker/pool capacity. | Нельзя утверждать, что любой новый async/worker backend безопасен или что есть unlimited connection headroom. Для каждого нового процесса нужны bounded capacity/load evidence, peak attribution и сохранение budget `20/150`; нельзя повышать `CONN_MAX_AGE` по одному green snapshot. |
| `DJ6-SRV-006` | Тот же connection/charset evidence document и live-matrix gate: client/session/schema/table values проверяются как `utf8mb4`, session `default_storage_engine=InnoDB`, global server default наблюдается как `latin1`/`latin1_swedish_ci` и намеренно не изменяется. | **READ-ONLY/REHEARSAL CLOSED** для fail-closed compatibility gate; **NO-GO** для global charset change. | Нельзя утверждать, что server default уже исправлен, что raw SQL/manual table creation автоматически безопасны или что существующие таблицы преобразованы. Любой `ALTER DATABASE`, `SET GLOBAL` или charset migration требует host-owner review, отдельного backup/rollback и проверки соседних приложений. |
| `DJ6-BASE-002` | `docs/qa/django61-stage5-db-actions.md`, static inventory `554` non-DTF FK/OneToOne relations, DTF app/table prefix fail-closed, engine/FK/`DELETE_RULE`/orphan/signal/soft-delete/rollback fields. Reusable `companion_action_design` теперь описывает E050-safe sibling conversion: для `storefront.PageView` сначала `user -> DB_SET_NULL`, затем `session -> DB_CASCADE`, с обратным rollback order. | **READ-ONLY/REHEARSAL CLOSED** для static inventory/design; **NO-GO** для изменения `on_delete` в production. | Нельзя утверждать, что static graph равен live schema, что реальные FK/orphans готовы или что delete signals сохранятся. Нужны свежий production read-only FK/orphan inventory, review design и отдельная обратимая migration. |
| `DJ6-DB-001` | В том же DB-actions evidence пройден disposable MariaDB `11.4.12`: `2000` parent sessions × `10` child events, batch `100`; Python delete `0.070519 s`, DB cascade `0.068915 s` (`1.023x`), orphans `0/0`, остаток `0/0`, реальные rules `RESTRICT`/`CASCADE`, transaction rollback и reverse DDL восстановили исходное состояние. | **READ-ONLY/REHEARSAL CLOSED** для synthetic benchmark/rollback; **NO-GO** для production adoption. | Нельзя переносить synthetic timing на production, считать production engines/FK подтверждёнными или считать обязательные `pre_delete`/`post_delete` side effects сохранёнными. До rollout нужны live schema evidence, signal review, lock/size budget и approved migration/rollback. |
| `DJ6-ORM-013` | `docs/qa/django61-stage5-generated-field.md` (candidate `f87674bc6`) и disposable harness: MariaDB `11.4.12`, `29/29` parity строк, discounts `0/1/33/100` и `NULL`, insert/update/refresh/deferred behavior, index range/order plans. Первый `CASE ... FLOOR` rejected MariaDB `ERROR 1901`; рабочая `DIV`-формула расходится со старой catalog `CAST` (например `1091/33`: `731` против canonical `730`). | **READ-ONLY/REHEARSAL CLOSED** для experiment; **NO-GO** для `GeneratedField` в `storefront.Product`. | Нельзя утверждать, что production formula уже едина, что existing catalog sorting parity сохранена или что DDL можно добавлять сейчас. Сначала исправить и доказать всех consumers, проверить `discount_percent > 100`, затем повторить disposable matrix/`EXPLAIN` и подготовить маленькую обратимую DDL migration. |
| `DJ6-MIG-001` | `docs/qa/django61-stage5-migration-squash.md` и fail-closed harness: Django `6.1`, non-DTF graph `441/16`, clean-install/restore на disposable SQLite, `pending=0`, graph/schema/history hashes совпали. Новые validators требуют authoritative read-only history, фактическую MariaDB version, production-compatible clean-install/replay и backup/restore/rollback evidence; одни boolean claims не дают `GO`. | **READ-ONLY/REHEARSAL CLOSED** для local graph/restore и evidence contract; **NO-GO** для squash и удаления historical migrations. | Нельзя утверждать production applied-history parity, MariaDB compatibility, готовые `replaces` ranges или право удалять старые migration files. Сначала получить sanitized authoritative evidence, повторить clean-install/restore на production-compatible MariaDB и согласовать ranges; до этого migration graph не менять. |

## Exit-gate Stage 5

По этой сверке закрыты только bounded read-only/evidence и disposable
rehearsal подэтапы. Полный Stage 5 exit gate **не закрыт**, потому что
production acceptance всё ещё отсутствует:

1. утверждённая live таблица `model -> engine -> size -> risk -> migration
   order`;
2. production-compatible InnoDB canary с backup, rehearsal timing и rollback;
3. production adoption proof для DB-level cascade/generated column (оба
   disposable эксперимента сами по себе production rollout не разрешают);
4. applied-history и MariaDB restore proof для migration squash.

До выполнения условий 1 и 2 нельзя закрывать `DJ6-SRV-003` или два
соответствующих exit-gate чекбокса; `DJ6-BASE-002` и disposable
`DJ6-DB-001`/`DJ6-ORM-013` отражают только заявленный bounded evidence.
`DJ6-MIG-001` остаётся открытым до authoritative applied-history и restore
proof. Production DDL, `migrate` и `squashmigrations` запускать нельзя.

## Provenance

- Matrix snapshot: `docs/qa/django61-stage5-srv003-matrix.json`, captured
  `2026-08-18T23:48:07+03:00`; server vendor/version `MariaDB 11.4.12`.
- This evidence is tracked in the Stage 5 release candidate; integration SHA
  and production SHA must be recorded only after the parent integration gate.
- Latest fail-closed Stage 5 tooling is referenced by the scoped roadmap and
  focused tests; no production DDL or migration was run for this audit.
- Connection/charset evidence: `85c9d90fa`, `90debf557`, `5735f4727`.
- InnoDB roadmap/tooling evidence: `578ecd3d1`, `e5b6aba4c`.
- DB actions evidence: `6c2197af3`.
- GeneratedField evidence: `5911e7053`.
- Migration squash evidence: `babdab194`.
