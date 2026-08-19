# Stage 5 ReviewVote InnoDB canary runbook

Дата: 2026-08-19

Статус: код и disposable physical rehearsal готовы; production canary не
выполнялся, а чекбоксы `DJ6-SRV-003` и два связанных exit gate остаются
открытыми до live after-proof.

## Scope

Кандидат только один: non-DTF `reviews_reviewvote`. По переданной
read-only production evidence таблица была `MyISAM`, `0` строк, `2048` байт,
без physical FK, trigger и FULLTEXT. Перед rollout эти факты нужно повторить
с production MariaDB: snapshot от 2026-08-18 не является свежим разрешением на
DDL.

Migration `reviews.0003_reviewvote_innodb_canary` depends on
`reviews.0002_mariadb_vote_uniqueness` and:

- `atomic = False` и меняет engine той же таблицы через `ALTER TABLE ... ENGINE`;
- не добавляет поля, generated columns или constraints; до DDL подтверждает
  post-`0002` stored generated `anon_identity` и real unique indexes
  `rev_vote_unique_user`/`rev_vote_unique_anon`;
- на SQLite делает no-op;
- на уже `InnoDB` оставляет fresh-install schema без изменений;
- на production `MyISAM` останавливается до DDL, если marker, индексы,
  row-count, duplicate, FK, trigger или FULLTEXT proof не совпадают;
- reverse переводит ту же таблицу обратно в `MyISAM` и проверяет сохранение
  строк и индексов.

## Disposable proof

Общий `scripts/run_mariadb_gate.py` остаётся warning/constraint gate и не
подменяет физический engine-canary; отдельного `stage5-reviewvote-canary`
suite в нём нет. Не запускайте несуществующий suite и не считайте обычный
`lifecycle` доказательством этой миграции. Физический disposable lifecycle
был выполнен отдельным fail-closed harness на loopback MariaDB 11.4.12:

- `0002` применился без ошибок, затем FK staging перевёл synthetic table в
  MyISAM;
- `0003` forward перевёл её в InnoDB, reverse вернул MyISAM, empty reapply
  снова прошёл, а одна запись сохранилась через forward/reverse;
- временные database/user и write-freeze marker удалены; production checkout и
  production DB не использовались.

Tracked unit contract остаётся `reviews.tests.test_stage5_innodb_canary`; он
проверяет fail-closed interlocks и тот же migration validator. Для нового
production кандидата сначала создайте отдельный reviewed harness/evidence,
а не расширяйте этот документ утверждением, что disposable proof равен live
rollout.

## Production activation checklist (не запускать автоматически)

1. Снять свежий read-only snapshot `SHOW CREATE TABLE`, `information_schema`
   engine/index/FK/trigger/FULLTEXT, exact row count и duplicate scans.
2. Сверить snapshot с matrix и получить письменный domain-owner approval.
3. Проверить backup artifact: абсолютный путь вне Git, размер, SHA-256,
   restore в disposable MariaDB 11.4.12, row/index/engine parity. Backup-only
   rollback не считается write-loss-safe.
4. В отдельном maintenance window создать marker с owner-only правами:

   ```bash
   install -d -m 700 /home/qlknpodo/TWC/TwoComms_Site/twocomms/tmp
   printf 'review-write-freeze-v1\n' > /home/qlknpodo/TWC/TwoComms_Site/twocomms/tmp/review_writes.frozen
   chmod 600 /home/qlknpodo/TWC/TwoComms_Site/twocomms/tmp/review_writes.frozen
   ```

   Verify public review submit/vote return `503` with `Retry-After: 60`, and
   staff Review/ReviewVote add/change/delete/actions are disabled. Do not
   continue if any writer remains active.
5. Run `migrate reviews 0003_reviewvote_innodb_canary` through the supported
   deploy procedure, then verify engine, exact row count, index signatures,
   no new FK/trigger/FULLTEXT, and read-only PDP/admin behavior.
6. Keep the marker until after post-migration evidence is captured. Remove it
   only after a coordinated decision to reopen review writes; verify marker
   removal and a successful controlled write separately.
7. For rollback, use the same marker and a tested write-freeze or reverse-sync
   strategy, then run `migrate reviews 0002_mariadb_vote_uniqueness` so only
   the `0003` engine canary is reversed, and repeat the full after-proof. Never
   restore an old backup over live writes.

## Evidence placeholders required before checkboxes

- `production_snapshot_sha256`: `TODO`
- `backup_artifact_sha256_and_restore_id`: `TODO`
- `freeze_marker_verified_at`: `TODO`
- `writer_count_and_window`: `TODO`
- `forward_migration_started_finished`: `TODO`
- `post_forward_engine_rows_indexes`: `TODO`
- `rollback_strategy_and_rehearsal`: `TODO`
- `production_deployed_sha`: `TODO`

Until every placeholder is populated from the live non-DTF canary, do not mark
the Stage 5 implementation or its exit gates complete.
