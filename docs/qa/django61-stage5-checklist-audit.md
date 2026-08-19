# Django 6.1 Stage 5: checklist evidence audit

Дата аудита: 2026-08-18; production addendum: 2026-08-19.
Историческая matrix захвачена `2026-08-18T23:48:07+03:00`. Актуальный
production canary и storefront migration записаны в
`django61-stage5-production-canary-2026-08-19.{md,json}` и имеют SHA
`3de4c6a7d499aa3d701409ef14950747b0f36c82`.
Scope: только non-DTF MariaDB/Django evidence. DTF и parser не затрагивались;
production изменения ограничены отдельно одобренными `reviews_reviewvote`
canary и `storefront.0097`.

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
| `DJ6-SRV-003` | Историческая matrix содержит `320` non-DTF base tables и `177` MyISAM targets; отдельный production artifact закрывает approved `reviews.ReviewVote` (backup, controlled write freeze, duplicate/schema preflight, InnoDB after-proof, disposable reverse) и сохраняет HOLD для остальных `176` targets. `storefront.0097` также применена после duplicate/schema preflight. | **PRODUCTION CANARY CLOSED / BULK PROGRAM HOLD**. | Нельзя считать один canary разрешением на массовый `ALTER TABLE`; для каждой следующей таблицы нужны собственные writer/orphan/domain/rollback facts. Lock census ограничен правами production account и явно записан в artifact. |
| `DJ6-SRV-004` | `docs/qa/django61-stage5-connection-budget.md` (candidate `a34d7589c`/`566102c86`) и connection gate в `scripts/run_django61_live_matrix.py` (candidate `bc4d0edc1`). Read-only baseline: MariaDB `11.4.12`, `max_connections=150`, `max_user_connections=20`, `wait_timeout=60`, effective `CONN_MAX_AGE=0`, `CONN_HEALTH_CHECKS=True`; gate также проверяет usage counters и запрещает DTF alias. | **READ-ONLY/REHEARSAL CLOSED** для текущего connection-policy guard; **NO-GO** для расширения worker/pool capacity. | Нельзя утверждать, что любой новый async/worker backend безопасен или что есть unlimited connection headroom. Для каждого нового процесса нужны bounded capacity/load evidence, peak attribution и сохранение budget `20/150`; нельзя повышать `CONN_MAX_AGE` по одному green snapshot. |
| `DJ6-SRV-006` | Тот же connection/charset evidence document и live-matrix gate: client/session/schema/table values проверяются как `utf8mb4`, session `default_storage_engine=InnoDB`, global server default наблюдается как `latin1`/`latin1_swedish_ci` и намеренно не изменяется. | **READ-ONLY/REHEARSAL CLOSED** для fail-closed compatibility gate; **NO-GO** для global charset change. | Нельзя утверждать, что server default уже исправлен, что raw SQL/manual table creation автоматически безопасны или что существующие таблицы преобразованы. Любой `ALTER DATABASE`, `SET GLOBAL` или charset migration требует host-owner review, отдельного backup/rollback и проверки соседних приложений. |
| `DJ6-BASE-002` | `docs/qa/django61-stage5-db-actions.md`, static inventory `554` non-DTF FK/OneToOne relations, DTF app/table prefix fail-closed, engine/FK/`DELETE_RULE`/orphan/signal/soft-delete/rollback fields. Reusable `companion_action_design` теперь описывает E050-safe sibling conversion: для `storefront.PageView` сначала `user -> DB_SET_NULL`, затем `session -> DB_CASCADE`, с обратным rollback order. | **READ-ONLY/REHEARSAL CLOSED** для static inventory/design; **NO-GO** для изменения `on_delete` в production. | Нельзя утверждать, что static graph равен live schema, что реальные FK/orphans готовы или что delete signals сохранятся. Нужны свежий production read-only FK/orphan inventory, review design и отдельная обратимая migration. |
| `DJ6-DB-001` | В том же DB-actions evidence пройден disposable MariaDB `11.4.12`: `2000` parent sessions × `10` child events, batch `100`; Python delete `0.070519 s`, DB cascade `0.068915 s` (`1.023x`), orphans `0/0`, остаток `0/0`, реальные rules `RESTRICT`/`CASCADE`, transaction rollback и reverse DDL восстановили исходное состояние. | **READ-ONLY/REHEARSAL CLOSED** для synthetic benchmark/rollback; **NO-GO** для production adoption. | Нельзя переносить synthetic timing на production, считать production engines/FK подтверждёнными или считать обязательные `pre_delete`/`post_delete` side effects сохранёнными. До rollout нужны live schema evidence, signal review, lock/size budget и approved migration/rollback. |
| `DJ6-ORM-013` | `docs/qa/django61-stage5-generated-field.md` (candidate `f87674bc6`) и disposable harness: MariaDB `11.4.12`, `29/29` parity строк, discounts `0/1/33/100` и `NULL`, insert/update/refresh/deferred behavior, index range/order plans. Первый `CASE ... FLOOR` rejected MariaDB `ERROR 1901`; рабочая `DIV`-формула расходится со старой catalog `CAST` (например `1091/33`: `731` против canonical `730`). | **READ-ONLY/REHEARSAL CLOSED** для experiment; **NO-GO** для `GeneratedField` в `storefront.Product`. | Нельзя утверждать, что production formula уже едина, что existing catalog sorting parity сохранена или что DDL можно добавлять сейчас. Сначала исправить и доказать всех consumers, проверить `discount_percent > 100`, затем повторить disposable matrix/`EXPLAIN` и подготовить маленькую обратимую DDL migration. |
| `DJ6-MIG-001` | `docs/qa/django61-stage5-migration-squash.md` и fail-closed harness: Django `6.1`, non-DTF graph `441/16`, clean-install/restore на disposable SQLite, `pending=0`, graph/schema/history hashes совпали. Новые validators требуют authoritative read-only history, фактическую MariaDB version, production-compatible clean-install/replay и backup/restore/rollback evidence; одни boolean claims не дают `GO`. | **READ-ONLY/REHEARSAL CLOSED** для local graph/restore и evidence contract; **NO-GO** для squash и удаления historical migrations. | Нельзя утверждать production applied-history parity, MariaDB compatibility, готовые `replaces` ranges или право удалять старые migration files. Сначала получить sanitized authoritative evidence, повторить clean-install/restore на production-compatible MariaDB и согласовать ranges; до этого migration graph не менять. |

## Exit-gate Stage 5

По этой сверке закрыты bounded read-only/evidence, disposable rehearsal и
первый production canary. Оставшиеся ограничения Stage 5 не расширяют его
на массовую конверсию:

1. утверждённая live таблица `model -> engine -> size -> risk -> migration
   order` для `reviews.ReviewVote` — **закрыто** в новом artifact;
2. production-compatible InnoDB canary с backup, rehearsal timing и rollback
   — **закрыто** в новом artifact;
3. production adoption proof для DB-level cascade/generated column (оба
   disposable эксперимента сами по себе production rollout не разрешают);
4. applied-history и MariaDB restore proof для migration squash.

Условия 1 и 2 закрыты только для одного кандидата; `DJ6-SRV-003` и два
соответствующих exit-gate чекбокса отмечены в canonical plan с этой границей.
`DJ6-BASE-002` и disposable `DJ6-DB-001`/`DJ6-ORM-013` отражают только
заявленный bounded evidence.
Migration squash остаётся NO-GO до authoritative applied-history and restore
proof for its own ranges. Production DDL, `migrate` and `squashmigrations`
запускать нельзя без отдельного scoped gate.

## Provenance

Safety hardening commits `b7f84b964` (pre-DDL InnoDB preflight),
`d1e834b3f` (migration-squash readiness) and `67859d912` (canary inventory
domain/managed-engine guard) add fail-closed validation without
performing production DDL, migrations, squash, historical-file deletion or
DTF access. The combined focused Stage 5 gate passed `25/25` under CPython
`3.14.6`/Django `6.1` before the final guard; the final integrated gate passed
`26/26`. These results close the tooling/evidence substep only,
not the `NO-GO` production decisions above.

- Matrix snapshot: `docs/qa/django61-stage5-srv003-matrix.json`, captured
  `2026-08-18T23:48:07+03:00`; server vendor/version `MariaDB 11.4.12`.
- Current production evidence: `docs/qa/django61-stage5-production-canary-2026-08-19.{md,json}`.
- Latest fail-closed Stage 5 tooling is referenced by the scoped roadmap and
  focused tests; production DDL is limited to the two separately evidenced
  migrations above.
- Connection/charset evidence: `85c9d90fa`, `90debf557`, `5735f4727`.
- InnoDB roadmap/tooling evidence: `578ecd3d1`, `e5b6aba4c`.
- DB actions evidence: `6c2197af3`.
- GeneratedField evidence: `5911e7053`.
- Migration squash evidence: `babdab194`.
