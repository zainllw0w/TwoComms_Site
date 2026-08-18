# DJ6-MIG-001: migration squash gate

Дата evidence: 2026-08-18

Исходный commit: `5000def6f2c1dda7754af7c757717a5ab38f84f4`

Runtime: CPython 3.14.6, Django 6.1
Область: только реальный non-DTF graph. DTF не открывался и не изменялся.

## Итоговое решение

**Решение: `NO-GO`. Squash и удаление historical migrations запрещены.**

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

| Проверка | Результат |
|---|---|
| Graph fingerprint одинаков до/после install и после restore | PASS: `95ef0304cc909e83f31d80b8a739d41627863db0a007abcbe48f2d2756ca55db` |
| Non-DTF graph nodes / leaves | `441 / 16` |
| Clean install на disposable SQLite | PASS, `pending=0`, 1836 schema objects |
| Restore (`sqlite.Connection.backup`) | PASS, integrity check и schema совпали |
| Applied migration history после restore | PASS, `pending=0`, hash совпал |
| Model migration drift | PASS (`makemigrations --check --dry-run`) |
| Реальный DTF app / migrations / tables | PASS: не загружены, real modules `[]`, tables `[]` |
| Production MariaDB mutation | НЕ выполнялась |
| Historical migration deletion / squash | НЕ выполнялись |

Hashes disposable rehearsal:

- schema: `9382be71731a9707632c86e2e1d15d5206ac6f9f76b4a441579f03a6448d753b`;
- applied non-DTF history: `b0b486b4e98769432343047a56afc678cbd3e3b539406d3f3b0a56ff063ecbc5`;
- applied migration count после clean install: `450`.

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

## Почему SQLite не закрывает production decision

SQLite подтверждает только то, что текущий Django 6.1 graph можно применить с
чистого состояния и восстановить без потери migration recorder/schema в
локальном disposable файле. Он не моделирует MariaDB engine differences,
legacy MyISAM/InnoDB constraints, MySQL-specific SQL, collation или реальные
production applied rows. Поэтому этот evidence полезен как быстрый regression
gate, но не заменяет MariaDB rehearsal и applied-history inventory.

## Следующий разрешённый шаг

Не менять migration-файлы. Сначала получить read-only applied-history inventory
из утверждённой non-DTF MariaDB-копии, затем поднять отдельную disposable
MariaDB той же версии и повторить clean-install/restore. Только после review
конкретных ranges можно сформировать отдельные `replaces` migrations; старые
файлы удалять лишь в последующем релизе после deploy/restore proof.
