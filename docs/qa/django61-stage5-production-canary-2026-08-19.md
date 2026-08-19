# Django 6.1 Stage 5: production canary evidence

Дата: 2026-08-19. Scope: только non-DTF production MariaDB; DTF намеренно не
затрагивался. Полная машиночитаемая запись находится в
`django61-stage5-production-canary-2026-08-19.json`.

## Итог

Первый production InnoDB canary выполнен на `reviews_reviewvote`. Таблица
переведена в InnoDB после backup, disposable MariaDB rehearsal и короткого
write-freeze. После миграции сохранены `0` строк, оба generated unique index,
check constraint и отсутствие FK/trigger/FULLTEXT. Marker снят только после
after-proof; обычное состояние сейчас `marker_missing`.

Отдельно завершён pending migration `storefront.0097_mariadb_generated_uniqueness`.
До него ORM уже падал на `Unknown column default_product_identity`; после него
ORM read проходит. Физическая web-push схема не менялась: `varchar(1000)` и
`UNIQUE endpoint USING HASH` сохранены.

## Production facts

| Объект | Факт после rollout |
| --- | --- |
| Runtime | CPython 3.14.6, Django 6.1, MariaDB 11.4.12 |
| Deploy SHA | `3de4c6a7d499aa3d701409ef14950747b0f36c82` |
| `reviews_reviewvote` | InnoDB, 0 rows |
| `storefront_productfitoption` | MyISAM, 70 rows, 34 default rows |
| `storefront_webpushdevicesubscription` | MyISAM, 1 row, max endpoint 188 chars |
| Migration state | `reviews.0003` и `storefront.0097` applied |
| Django gates | `migrate --check` и `check --fail-level WARNING` passed |

Approved matrix row for `reviews.ReviewVote`: medium criticality, migration
order `11`, post-rollout `DATA_LENGTH=16384` and `INDEX_LENGTH=81920`, with
zero FK, trigger and FULLTEXT objects. The host account cannot read
`PROCESS`/`performance_schema.metadata_locks`; therefore the lock evidence is
bounded to the controlled write-freeze and an empty `SHOW OPEN TABLES` result,
not an unrestricted metadata-lock census.

ReviewVote backup: `/home/qlknpodo/db_backups/stage5-reviewvote/`
`reviews_reviewvote-20260819T152619Z.sql.gz`, mode `0600`, SHA-256
`edbb7b11069a447d875505f9e89471dfd18975efcb5debbf8cbe412f3eb243b2`.

Свежий full backup для storefront rollout: `/home/qlknpodo/db_backups/`
`stage5-storefront-0097/daily/qlknpodo_MySQL_DB-20260819.sql.gz`, mode `0600`,
23,335,186 bytes, SHA-256
`a7d46ff57316bafd7795669acba0be82d4295d785854862353e087ae7db3f1d9`.
Он восстановлен в отдельную локальную MariaDB 11.4.12; engines и row counts
совпали, временная схема удалена.

## Граница закрытия

Эта запись закрывает только первый одобренный canary и связанные Stage 5 exit
gates. Остальные MyISAM таблицы не переводились: массовый `ALTER TABLE`,
изменение global charset, DB-level cascade и squash historical migrations по-
прежнему требуют отдельных evidence/owner/rollback gates. SQLite не является
acceptance-базой для generated MariaDB fields.
