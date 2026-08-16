# OPS — боевой сервер TwoComms

> W0-5 (CB-043/CB-044/CB-012). Зафиксировано по инвентаризации 05-07.07.2026.
> Обновляйте этот файл при ЛЮБОМ изменении crontab или деплой-процесса.

## Боевой settings-модуль

- Продакшен Passenger: `twocomms.production_settings` (env-переменные из
  `.env.production`, выбранного `manage.py`/WSGI на сервере).
- Локальные быстрые тесты: `test_settings` (SQLite); non-DTF release checks
  используют `test_settings_no_network_non_dtf` и отдельные migration/static
  profiles. Не подменять production settings локальным bare runtime.
- Тесты в песочнице/CI: `test_settings` (sqlite in-memory) / `preview_settings`.
- Ключевые env-инварианты: `MONOBANK_TOKEN`, `MONOBANK_WEBHOOK_SECRET`, `TELEGRAM_BOT_TOKEN`, `FACEBOOK_CAPI_TOKEN`, `TIKTOK_EVENTS_TOKEN` — все берутся из env, НЕ из кода (после W0-2-ротации).

## Exact runtime contract

Для локальных команд и linked worktrees использовать только общий project
interpreter. Bare `python`/`python3` может указывать на другой Django.

```bash
TWC_PYTHON="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.venv/bin/python"
test -x "$TWC_PYTHON"
"$TWC_PYTHON" -c 'import django, sys; assert sys.version_info[:3] == (3, 14, 6); assert django.get_version() == "6.1"; print(sys.executable, django.get_version())'
"$TWC_PYTHON" scripts/verify_project_runtime.py
```

На production этот же contract выполняется после активации virtualenv
`.../3.14/bin/activate`; Passenger должен загрузить
`twocomms.production_settings` и только alias `default` для non-DTF proof.

## Crontab (live snapshot 17.07.2026: 6 задач)

> Production acceptance на HEAD `5ee9a974` подтвердила шесть scheduled jobs,
> ровно одну строку запуска `scripts/backup_mysql.sh` и сохранность всех
> посторонних строк. Таблица ниже документирует три известные записи; остальные
> три F-090 не инвентаризировал, поэтому их команды здесь намеренно не придуманы.

| # | Расписание | Команда | Лог | Назначение / риск |
|---|---|---|---|---|
| 1 | `45 3 * * *` | `TWC_DB_NAMES="$(/usr/bin/paste -sd, "$HOME/.twocomms_backup_dbs")" /bin/bash /home/qlknpodo/TWC/TwoComms_Site/scripts/backup_mysql.sh` | `/home/qlknpodo/db_backups/backup.log` | F-090: приватный список БД, полный валидируемый batch и один guarded daily run |
| 2 | `10 4 * * *` | `scripts/rotate_twocomms_logs.sh` | `$HOME/log_archives/twocomms/rotate_twocomms_logs.log` | ротация/retention persistent logs |
| 3 | `17 4 * * *` | `manage.py reconcile_purchase_actions --apply` | `logs/reconcile_purchase_actions.log` | F-083: идемпотентно лечит доказуемые пропуски внутренних purchase |

### Другие scheduler-задачи

F-090 проверял только backup entry и сохранность остальных строк. Наличие или
отсутствие Merchant feed, IndexNow/sitemap ping, survey inactivity, analytics
retention и задач из snapshot 05.07.2026 этим прогоном не переоценивалось;
они остаются отдельными audit scopes.

### Решение: Celery НЕ возвращаем (W3-1 / TD-015)

Прод-хостинг (shared, Passenger) не запускает Celery-воркер и beat; Redis-брокер
с сервера не резолвится. Все `@shared_task` работают через синхронный шим
(`storefront/tasks.py`), фоновость для Telegram-уведомлений — daemon-поток
(`orders/tasks.py`). `CELERY_BEAT_SCHEDULE` в settings.py — мёртвый конфиг,
периодика выполняется ТОЛЬКО через crontab (см. отдельные scopes выше). Новую
фоновую работу оформлять как management-команду + cron, НЕ как Celery-таск.

### Инварианты

- Все три документированные cron-команды имеют entry points в репо; итоговый crontab содержит шесть scheduled jobs.
- НИКОГДА не добавляйте cron-задачу без записи в эту таблицу.
- Новые задачи логируйте в закрытый служебный каталог; backup log находится вне web-root, а `reconcile_purchase_actions` пишет одну короткую итоговую строку в сутки.

### MySQL backup runbook (F-090)

Repository entry point:
`/home/qlknpodo/TWC/TwoComms_Site/scripts/backup_mysql.sh`.

- The script requires every database name explicitly as positional arguments;
  it has no implicit production database fallback.
- Credentials are read only from
  `TWC_MYSQL_DEFAULTS_FILE` (default `$HOME/.my.cnf`, mode `0600` or `0400`).
- `$HOME/db_backups`, `daily/` and `weekly/` are outside the project/web root and
  remain mode `0700`; archives and `last_success` remain mode `0600`.
- A non-blocking `flock` prevents cron/manual overlap. Exit 75 means another
  backup already owns the lock.
- Every configured database is first dumped to a process-scoped temporary
  archive. Size and `gzip -t` must pass for the complete batch before any final
  archive is replaced.
- Daily retention is 14 days; Sunday copies remain 35 days. Successful runs
  atomically update `$HOME/db_backups/last_success` with timestamp and database
  count only.

Live cron reads the database names from a private mode-`0600` configuration file;
the names and credentials are not stored in crontab or this document:

```cron
# TWOCOMMS_DB_BACKUP
45 3 * * * TWC_DB_NAMES="$(/usr/bin/paste -sd, "$HOME/.twocomms_backup_dbs")" /bin/bash /home/qlknpodo/TWC/TwoComms_Site/scripts/backup_mysql.sh >> /home/qlknpodo/db_backups/backup.log 2>&1
```

**Live acceptance (17.07.2026, runtime commit `5ee9a974`):** local behavioral
tests passed 11 with one Linux-only skip; server tests passed 11/11. Private
defaults/list files are mode `0600`. The manual production run published exactly
two valid archives; backup root and daily directories are mode `0700`, archive
files are mode `0600`, and temporary leftovers are zero.

Both archives restored into isolated temporary databases with exact all-table
row-count parity (265 and 21 tables); trigger/routine inventories matched and
the Django check passed. The temporary restore databases were deleted. The final
crontab retained all unrelated lines (six scheduled jobs total, exactly one backup
script line). A temporary one-minute scheduled canary ran successfully and was
removed; its temporary baseline file was also removed.

### Log rotation / PII (W3-6)

REPO-часть:

- `twocomms.log_handlers.PIIRedactionFilter` подключён ко всем logging handlers и маскирует email, украинские телефоны и длинные числовые последовательности до записи в persistent logs.
- `scripts/rotate_twocomms_logs.sh` ротирует большие `*.log` под проектом, gzip-архивы складывает в `$HOME/log_archives/twocomms`, права 700/600, retention 30 дней.

SERVER-часть:

```cron
10 4 * * * /bin/bash /home/qlknpodo/TWC/TwoComms_Site/scripts/rotate_twocomms_logs.sh >> /home/qlknpodo/log_archives/twocomms/rotate_twocomms_logs.log 2>&1
17 4 * * * cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python manage.py reconcile_purchase_actions --apply >> /home/qlknpodo/TWC/TwoComms_Site/twocomms/logs/reconcile_purchase_actions.log 2>&1
```

## Git-состояние сервера (CB-043, снято 05.07.2026)

- Ветка `main`, tracked-файлы чистые → `git pull` безопасен.
- **10 git-stash** на сервере — судьба каждого решается с владельцем `[OWNER]`; до решения `git stash drop` НЕ выполнять.
- Untracked диаг-скрипты на бою — инвентаризировать перед удалением.

## Смок-тесты перед деплоем (W0-4 / CB-024)

Прогонять локально перед каждым деплоем:

```bash
TWC_PYTHON="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.venv/bin/python"
"$TWC_PYTHON" manage.py test \
  storefront.tests.test_checkout \
  storefront.tests.test_monobank_webhook \
  storefront.tests.test_cart_sync \
  storefront.tests.test_utm_attribution \
  --settings=test_settings
```

Покрытие «денежного» контура:
- COD-заказ (гость и авторизованный), double-submit, промокоды — `test_checkout`
- Подпись ECDSA, pull-verify, недоплата, **идемпотентность повторного вебхука** — `test_monobank_webhook`
- Слияние корзины при логине, мультидевайс — `test_cart_sync`
- UTM-привязка заказа (fallback-цепочка) — `test_utm_attribution`

## Деплой

- Изменили статику (`static/js/*`, CSS) → bump cache-buster в base.html + `collectstatic`.
- Изменили модели → `makemigrations` + `migrate` (бэкап БД перед migrate — см. W0-3).
- После деплоя: смок-прогон руками — главная, карточка товара, добавление в корзину, шаг чекаута.

### Единственный разрешенный deploy path

После commit и push в GitHub `main` production обновляется только fast-forward
pull по утвержденному SSH-шаблону. Пароль приходит из локального
`deploy-env.zsh`, не хранится в OPS и не печатается:

```bash
source /Users/zainllw0w/.config/twocomms/deploy-env.zsh
test -n "${TWOCOMMS_DEPLOY_PASSWORD:-}"
SSHPASS="$TWOCOMMS_DEPLOY_PASSWORD" sshpass -e ssh \
  -o StrictHostKeyChecking=no qlknpodo@195.191.25.63 \
  "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && git pull --ff-only origin main'"
unset TWOCOMMS_DEPLOY_PASSWORD
```

Не использовать `deploy.sh`, `scripts/deploy_release.py`, SCP/package install,
source build или произвольный remote checkout mutation как замену этому пути.
До pull и после pull запускать sanitized live matrix:

```bash
# На сервере, в активированном virtualenv:
python scripts/run_django61_live_matrix.py server --phase preflight
python scripts/run_django61_live_matrix.py server --phase post-deploy --expected-sha "$EXPECTED_SHA"

# Локально, через exact interpreter:
"$TWC_PYTHON" scripts/run_django61_live_matrix.py http --phase preflight
"$TWC_PYTHON" scripts/run_django61_live_matrix.py http --phase post-deploy
```

Server matrix проверяет `main`/SHA, CPython 3.14.6, Django 6.1, DRF,
mysqlclient, MariaDB alias `default`, migration/check state, Passenger и только
non-DTF health routes. HTTP matrix не следует redirect автоматически и не
выводит body, headers, cookies или credentials. Failed pre/post proof блокирует
закрытие release checklist.

### MariaDB parity note

Stage 0 target inventory: 332 base tables, 142 InnoDB, 190 MyISAM, 25 triggers,
0 routines, 0 events. `--single-transaction` является InnoDB-consistent;
MyISAM остаётся best-effort. Snapshot/restore выполняется только в local
`twc_snapshot_*` database и не включает DTF.
