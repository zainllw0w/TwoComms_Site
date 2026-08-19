# DJ6-MIG-001: migration squash gate

Дата evidence: 2026-08-19

Исходный commit lifecycle: `0dcf2e8e40bf616687e598907da947df25924e76`

Runtime: CPython 3.14.6, Django 6.1
Область: только реальный non-DTF graph. DTF не открывался и не изменялся.

## Итоговое решение

**Решение: `NO-GO`. Squash и удаление historical migrations запрещены.**

Полный clean-install/dump/restore/replay текущего non-DTF graph на disposable
MariaDB `11.4.12` завершён. Это закрывает safety rehearsal самого
`DJ6-MIG-001`, но не разрешает запускать `squashmigrations`: production history
snapshot относится к предыдущему graph, а свежая identity-set сверка и
утверждённые ranges отсутствуют. Поэтому migration graph и historical files
остаются неизменными.

Gate доказывает воспроизводимость текущего graph на disposable SQLite, но это
не является разрешением менять production history. Разрешение появится только
после всех трёх независимых доказательств:

1. authoritative applied-history production/non-DTF базы сверена с выбранными
   диапазонами;
2. полный clean-install и restore rehearsal повторены на disposable MariaDB
   production-compatible версии;
3. владелец базы утвердил точные ranges и порядок публикации.

Пока любое из условий отсутствует, historical migration-файлы сохраняются, а
`squashmigrations` не запускается.

## Что проверено

Команда:

```bash
TWC_PYTHON="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.venv/bin/python"
"$TWC_PYTHON" scripts/run_django61_migration_squash_gate.py \
  --allow-local-sqlite-rehearsal \
  --evidence /tmp/django61-migration-squash-evidence.json
```

Gate сам создаёт изолированный temporary directory, очищает чувствительное
окружение, принудительно выбирает `test_settings_migrations_non_dtf` и один
SQLite alias. Он отказывается работать при явном `DJANGO_ENV=production` или
`.env.production`, не принимает путь базы вне своего temporary directory и
требует явного флага локальной rehearsal.

### Внешние доказательства для будущего GO

Локальный runner дополнительно предоставляет переиспользуемые валидаторы
`validate_authoritative_applied_history`, `validate_mariadb_rehearsal_evidence`
и `validate_restore_drill_evidence`. Они принимают только обезличенный JSON с
фактами и fail-closed отклоняют неполные или неподходящие артефакты:

- authoritative history должна быть `read_only=true`, `authoritative=true`,
  `database_vendor=mysql|mariadb`, alias `default`, область `non_dtf_only=true`,
  `pending=0`, непустой источник/временная отметка и SHA-256 graph/history;
- MariaDB rehearsal должна быть `disposable=true`, с явной
  `production_compatible=true`, версией сервера с маркером `MariaDB`,
  `clean_install.pending=0` и
  отдельным `replay.pending=0`;
- restore drill должна содержать backup artifact + SHA-256, integrity check,
  parity schema/history и подтверждённый rollback.

Даже если вызывающий код передаст все boolean-флаги как `true`,
`build_decision()` оставляет `NO-GO` без этих трёх внешних evidence-объектов.
SQLite никогда не проходит authoritative/MariaDB валидатор. Такой JSON не
содержит credentials и должен создаваться только владельцем утверждённой
копии базы; production подключение или миграция из этого runner не выполняются.

| Проверка | Результат |
|---|---|
| Graph fingerprint одинаков до/после install и после restore | PASS: `3318190d6963dd4f12770f86713b9d5822627a8cea3399a8a51ec0f36ad9bbcf` |
| Non-DTF graph nodes / leaves | `442 / 17` |
| Clean install на disposable SQLite | PASS, `pending=0`, 1836 schema objects |
| Restore (`sqlite.Connection.backup`) | PASS, integrity check и schema совпали |
| Applied migration history после restore | PASS, `pending=0`, hash совпал |
| Replay после restore (`migrate --check`) | PASS, `pending=0`, history hash совпал |
| Authoritative production applied history (read-only) | PASS: MariaDB `11.4.12`, `461` non-DTF rows, `pending=0`; sanitized artifact: `django61-stage5-mig001-production-history.json` |
| MariaDB disposable clean install/replay | PASS: полный non-DTF graph на MariaDB `11.4.12`, clean/restore `pending=0`, `451` applied migrations |
| MariaDB backup/restore/rollback for migration rehearsal | PASS: `mariadb-dump`, SHA-256 `06882ce0160414ee33695811ceea9b9aaec8464b6500d728d4c67efab7e73fa4`, schema/history/count parity, cleanup verified |
| Model migration drift | PASS (`makemigrations --check --dry-run`) |
| Реальный DTF app / migrations / tables | PASS: не загружены, real modules `[]`, tables `[]` |
| Production MariaDB mutation | НЕ выполнялась |
| Historical migration deletion / squash | НЕ выполнялись |

Hashes disposable rehearsal:

- schema: `9382be71731a9707632c86e2e1d15d5206ac6f9f76b4a441579f03a6448d753b`;
- applied non-DTF history: `b0b486b4e98769432343047a56afc678cbd3e3b539406d3f3b0a56ff063ecbc5`;
- applied migration count после clean install: `450` (SQLite-only rehearsal).

## Production history evidence (read-only)

Проверка выполнена через CloudLinux-bound Python 3.14.6 на production checkout
с явным `twocomms.production_settings`. Она проверила только alias `default`:
`connection.vendor=mysql`, `SELECT VERSION()`, migration recorder,
`MigrationLoader` graph и pending plan. Не выполнялись `migrate`, `makemigrations`,
DDL, запись данных, `collectstatic`, restart или `git pull`.

- Production SHA на момент capture: `c64dc224b171295eed1d98da451e88ef1f70f76d`.
- MariaDB: `11.4.12-MariaDB-cll-lve`.
- Non-DTF graph: `441` nodes, `16` leaves; fingerprint совпадает с локальным
  rehearsal: `95ef0304cc909e83f31d80b8a739d41627863db0a007abcbe48f2d2756ca55db`.
- Applied non-DTF history: `461` rows, hash
  `d0b6dbdb164353c467886c79f8f5430173b7b6fe5d4a4069d21e05362bd954dd`.
- Pending non-DTF migrations: `0`.

Обезличенный JSON с теми же фактами находится в
`docs/qa/django61-stage5-mig001-production-history.json`.

## MariaDB rehearsal status

Runner создал две случайно именованные disposable базы и отдельного
пользователя на loopback MariaDB `11.4.12`, применил полный non-DTF graph,
выполнил `migrate --check`, `makemigrations --check`, `mariadb-dump`, restore во
вторую базу и повторный `migrate --check`. Результат: schema hash
`1ef54e1ca1333b1887251dae2440b1886691c3828e47200c8738c1bb4569288d`, history
hash `e9ee23a5d7922b77c580d54bd1270c47e30d5e3edce4f7bd00adc2df62d18a02`,
`451` applied migrations и `321` таблица совпали после restore. Обе базы,
пользователь, временный dump и локальный server удалены.

MariaDB меняет имена двух автоматически созданных JSON CHECK constraints после
logical restore (`*_new` -> финальное имя колонки). Gate сравнивает такие CHECK
по таблице и нормализованному `CHECK_CLAUSE`, сохраняя строгие имена для
PRIMARY/UNIQUE/FK. Regression-тест фиксирует этот контракт.

Sanitized evidence: `docs/qa/django61-stage5-mig001-mariadb-lifecycle.json`.
Production доступ, schema и данные не затрагивались.

## Inventory кандидатов

Inventory является advisory: он показывает, где вообще может быть польза от
будущего squash, но намеренно не предлагает ranges автоматически. Для
кандидата используется порог `20` migration-файлов; `high` означает наличие
data/SQL операций, `atomic=False` или необратимых операций.

| App | Migrations | Risk | Eligibility | Наблюдаемые ограничения |
|---|---:|---|---|---|
| `accounts` | 30 | high | blocked | cross-app/data history |
| `finance` | 21 | high | blocked | cross-app/data history |
| `management` | 170 | high | blocked | 52 data/SQL, 18 `atomic=False`, 66 cross-app |
| `orders` | 54 | high | blocked | cross-app/data history |
| `product_catalog` | 15 | high | not_candidate | 13 data/SQL, 4 `atomic=False` |
| `productcolors` | 7 | high | not_candidate | data migrations present |
| `reviews` | 1 | low | not_candidate | no data/SQL operations |
| `storefront` | 91 | high | blocked | 27 data/SQL, 6 `atomic=False` |
| `warehouse` | 13 | high | not_candidate | 4 data/SQL, 1 `atomic=False`, legacy DTF edge shadowed |

Для всех пяти candidate apps gate добавляет одинаковые блокеры:
`authoritative_applied_history_missing`, `mariadb_clean_install_missing` и
`approved_squash_ranges_missing`. Это предотвращает ложное закрытие пункта по
одному SQLite-проходу.

## Metadata-only readiness artifact

В runner добавлен `build_squash_artifact_manifest()`. Он допускает создание
только обезличенного metadata-manifest, когда одновременно доказаны:

- один и тот же graph fingerprint в текущем graph, authoritative production
  history и disposable MariaDB rehearsal;
- clean-install и replay на production-compatible MariaDB с `pending=0` и
  applied-history hash, совпадающей между собой и с authoritative history;
- отдельный backup/restore/rollback artifact с проверенной целостностью;
- явно утверждённые non-DTF ranges с reviewer и timestamp.

Manifest содержит SHA-256 каждого evidence-объекта, включая утверждение
ranges, чтобы последующая генерация не могла незаметно использовать другой
набор доказательств.

Manifest не запускает `squashmigrations`, не создаёт migration-файл и не
удаляет historical migrations. `build_decision()` намеренно разделяет право
сформировать replacement migration (`squash_may_run`) и последующее удаление
старой истории: `historical_migrations_may_be_deleted` всегда `false`, а
`post_squash_requirements` содержит `follow_up_release_required`. Удаление
history возможно только в отдельном релизе после deploy/restore proof.

MariaDB full clean-install/replay теперь доказан, но текущий production snapshot
снят на graph `441/16`, тогда как rehearsal использует `442/17`. Прямое
равенство history hash между clean install и старым production snapshot не
является корректным критерием. До свежего read-only identity-set review и
утверждённых ranges metadata-manifest не создаётся, решение остаётся `NO-GO`.

## Почему SQLite не закрывает production decision

SQLite подтверждает только то, что текущий Django 6.1 graph можно применить с
чистого состояния и восстановить без потери migration recorder/schema в
локальном disposable файле. Он не моделирует MariaDB engine differences,
legacy MyISAM/InnoDB constraints, MySQL-specific SQL, collation или реальные
production applied rows. Поэтому этот evidence полезен как быстрый regression
gate, но не заменяет MariaDB rehearsal и applied-history inventory.

## Следующий разрешённый шаг

Не менять migration-файлы. Получить свежую read-only identity-set сверку
production applied history с graph `442/17`, включая replacements и pending,
после чего владелец должен утвердить конкретные ranges. Только тогда можно
сформировать отдельные `replaces` migrations; старые файлы удалять лишь в
последующем релизе после deploy/restore proof.
