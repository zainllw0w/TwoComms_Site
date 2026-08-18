# Django 6.1 Stage 5: checklist evidence audit

Дата аудита: 2026-08-18
Проверенная текущая ревизия `origin/main`: `55f7082ae`.
Stage 5 code tip: `e3a89c83e`, построен поверх `b633b5567` и отстаёт от
текущей цели на один непересекающийся parser-commit. Rebase/push/deploy
отложены до явного SAFE-сигнала владельца production-инцидента.
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
перенесённых в Stage 5 code tip `e3a89c83e`. Сам publish-кандидат ещё не
заявляется как опубликованный в `main` или развернутый на production.

## Матрица

| ID | Evidence и что реально проверено | Решение сейчас | Что нельзя утверждать / следующий обязательный gate |
| --- | --- | --- | --- |
| `DJ6-SRV-003` | `docs/qa/django61-stage5-innodb-roadmap.md`, sanitized inventory-tool `scripts/build_innodb_stage5_inventory.py` и programmatic-only disposable gate `scripts/run_stage5_innodb_canary.py`. Gate fail-closed проверяет local/default MariaDB, создаёт случайную schema, верифицирует shadow backup, измеряет conversion и rollback, затем доказывает cleanup. В tracked historical aggregate есть `332` таблицы (`142` InnoDB, `190` MyISAM, `25` triggers), но отдельный per-table live dump отсутствует. | **NO-GO** для production migration; reusable inventory/canary tooling готово, live выполнение отсутствует. | Нельзя считать aggregate актуальным point-in-time фактом, утверждать готовый `model -> engine -> order` список, безопасный production canary или zero-downtime conversion. Нужны свежие sanitized `information_schema` rows и утверждённый запуск gate на production-compatible disposable MariaDB с backup/rollback evidence. |
| `DJ6-SRV-004` | `docs/qa/django61-stage5-connection-budget.md` (candidate `a34d7589c`/`566102c86`) и connection gate в `scripts/run_django61_live_matrix.py` (candidate `bc4d0edc1`). Read-only baseline: MariaDB `11.4.12`, `max_connections=150`, `max_user_connections=20`, `wait_timeout=60`, effective `CONN_MAX_AGE=0`, `CONN_HEALTH_CHECKS=True`; gate также проверяет usage counters и запрещает DTF alias. | **READ-ONLY/REHEARSAL CLOSED** для текущего connection-policy guard; **NO-GO** для расширения worker/pool capacity. | Нельзя утверждать, что любой новый async/worker backend безопасен или что есть unlimited connection headroom. Для каждого нового процесса нужны bounded capacity/load evidence, peak attribution и сохранение budget `20/150`; нельзя повышать `CONN_MAX_AGE` по одному green snapshot. |
| `DJ6-SRV-006` | Тот же connection/charset evidence document и live-matrix gate: client/session/schema/table values проверяются как `utf8mb4`, session `default_storage_engine=InnoDB`, global server default наблюдается как `latin1`/`latin1_swedish_ci` и намеренно не изменяется. | **READ-ONLY/REHEARSAL CLOSED** для fail-closed compatibility gate; **NO-GO** для global charset change. | Нельзя утверждать, что server default уже исправлен, что raw SQL/manual table creation автоматически безопасны или что существующие таблицы преобразованы. Любой `ALTER DATABASE`, `SET GLOBAL` или charset migration требует host-owner review, отдельного backup/rollback и проверки соседних приложений. |
| `DJ6-BASE-002` | `docs/qa/django61-stage5-db-actions.md`, static inventory `554` non-DTF FK/OneToOne relations, DTF app/table prefix fail-closed, engine/FK/`DELETE_RULE`/orphan/signal/soft-delete/rollback fields. Reusable `companion_action_design` теперь описывает E050-safe sibling conversion: для `storefront.PageView` сначала `user -> DB_SET_NULL`, затем `session -> DB_CASCADE`, с обратным rollback order. | **READ-ONLY/REHEARSAL CLOSED** для static inventory/design; **NO-GO** для изменения `on_delete` в production. | Нельзя утверждать, что static graph равен live schema, что реальные FK/orphans готовы или что delete signals сохранятся. Нужны свежий production read-only FK/orphan inventory, review design и отдельная обратимая migration. |
| `DJ6-DB-001` | В том же DB-actions evidence пройден disposable MariaDB `11.4.12`: `2000` parent sessions × `10` child events, batch `100`; Python delete `0.070519 s`, DB cascade `0.068915 s` (`1.023x`), orphans `0/0`, остаток `0/0`, реальные rules `RESTRICT`/`CASCADE`, transaction rollback и reverse DDL восстановили исходное состояние. | **READ-ONLY/REHEARSAL CLOSED** для synthetic benchmark/rollback; **NO-GO** для production adoption. | Нельзя переносить synthetic timing на production, считать production engines/FK подтверждёнными или считать обязательные `pre_delete`/`post_delete` side effects сохранёнными. До rollout нужны live schema evidence, signal review, lock/size budget и approved migration/rollback. |
| `DJ6-ORM-013` | `docs/qa/django61-stage5-generated-field.md` (candidate `f87674bc6`) и disposable harness: MariaDB `11.4.12`, `29/29` parity строк, discounts `0/1/33/100` и `NULL`, insert/update/refresh/deferred behavior, index range/order plans. Первый `CASE ... FLOOR` rejected MariaDB `ERROR 1901`; рабочая `DIV`-формула расходится со старой catalog `CAST` (например `1091/33`: `731` против canonical `730`). | **READ-ONLY/REHEARSAL CLOSED** для experiment; **NO-GO** для `GeneratedField` в `storefront.Product`. | Нельзя утверждать, что production formula уже едина, что existing catalog sorting parity сохранена или что DDL можно добавлять сейчас. Сначала исправить и доказать всех consumers, проверить `discount_percent > 100`, затем повторить disposable matrix/`EXPLAIN` и подготовить маленькую обратимую DDL migration. |
| `DJ6-MIG-001` | `docs/qa/django61-stage5-migration-squash.md` и fail-closed harness: Django `6.1`, non-DTF graph `441/16`, clean-install/restore на disposable SQLite, `pending=0`, graph/schema/history hashes совпали. Новые validators требуют authoritative read-only history, фактическую MariaDB version, production-compatible clean-install/replay и backup/restore/rollback evidence; одни boolean claims не дают `GO`. | **READ-ONLY/REHEARSAL CLOSED** для local graph/restore и evidence contract; **NO-GO** для squash и удаления historical migrations. | Нельзя утверждать production applied-history parity, MariaDB compatibility, готовые `replaces` ranges или право удалять старые migration files. Сначала получить sanitized authoritative evidence, повторить clean-install/restore на production-compatible MariaDB и согласовать ranges; до этого migration graph не менять. |

## Exit-gate Stage 5

По этой сверке безопасно закрыты только evidence/rehearsal подэтапы. Полный
Stage 5 exit gate **не закрыт**, потому что одновременно отсутствуют:

1. утверждённая live таблица `model -> engine -> size -> risk -> migration
   order`;
2. production-compatible InnoDB canary с backup, rehearsal timing и rollback;
3. approved design и live proof для DB-level cascade/generated column;
4. applied-history и MariaDB restore proof для migration squash.

До выполнения этих условий нельзя закрывать `DJ6-SRV-003`, `DJ6-BASE-002`,
`DJ6-MIG-001` или любой пункт Stage 5 exit gate; production
DDL/migrate/`squashmigrations` запускать нельзя. Отметки четырёх bounded
evidence-пунктов выше не снимают этот запрет.

## Provenance

- Current integration target: `origin/main` `55f7082ae`; code-tip parent:
  `b633b5567`; Stage 5 code tip: `e3a89c83e` (rebase/push/deploy на hold).
- Latest fail-closed Stage 5 gates: `e3a89c83e`.
- Connection/charset evidence: `85c9d90fa`, `90debf557`, `5735f4727`.
- InnoDB roadmap/tooling evidence: `578ecd3d1`, `e5b6aba4c`.
- DB actions evidence: `6c2197af3`.
- GeneratedField evidence: `5911e7053`.
- Migration squash evidence: `babdab194`.
