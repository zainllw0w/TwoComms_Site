# Stage 5 ReviewVote InnoDB canary runbook

Дата: 2026-08-19

Статус: production canary выполнен 2026-08-19. Код, disposable physical
rehearsal, backup, write-freeze и live after-proof закрыты. Полная актуальная
сводка: `django61-stage5-production-canary-2026-08-19.{md,json}`.

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

## Production activation checklist (исторический runbook)

Ниже сохранён воспроизводимый порядок, использованный для закрытого canary.
Повторно запускать его на `reviews_reviewvote` не нужно; для следующей
таблицы требуется новый owner approval и новый evidence artifact.

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

## Closed production evidence

- `production_snapshot`: `reviews_reviewvote` MyISAM, `0` rows, no FK,
  trigger or FULLTEXT; duplicate scan `0`.
- `backup_artifact`: `/home/qlknpodo/db_backups/stage5-reviewvote/`
  `reviews_reviewvote-20260819T152619Z.sql.gz`, mode `0600`, 914 bytes,
  SHA-256 `edbb7b11069a447d875505f9e89471dfd18975efcb5debbf8cbe412f3eb243b2`;
  gzip and disposable MariaDB 11.4.12 restore passed.
- `freeze_marker`: verified during the window; after-proof state is
  `marker_missing`; a valid write canary returned `503 temporarily_unavailable`
  and inserted no row.
- `forward`: `reviews.0002` applied at `15:32:22.397622`,
  `reviews.0003` at `15:32:23.172999`.
- `post_forward`: `reviews_reviewvote` is InnoDB with `0` rows,
  `rev_vote_unique_user`, `rev_vote_unique_anon`, and
  `rev_vote_user_or_anon_required`; no FK/trigger/FULLTEXT was introduced.
- `rollback_rehearsal`: empty forward/reverse, write-preservation reverse and
  cleanup passed on disposable MariaDB 11.4.12. Production reverse was not
  run because no rollback was needed.
- `production_deployed_sha`: `3de4c6a7d499aa3d701409ef14950747b0f36c82`.

These facts close the Stage 5 implementation checkbox and its first-canary
exit gate. They do not authorize conversion of the remaining MyISAM tables.
