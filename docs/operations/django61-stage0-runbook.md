# Django 6.1 Stage 0: операционный runbook

Документ описывает только безопасную проверку и разрешенный deployment path для
non-DTF части TwoComms. Он не является разрешением менять production database,
cron или серверные настройки.

## Границы

- Целевой runtime: CPython 3.14.6, Django 6.1, Django REST Framework 3.18.0,
  mysqlclient 2.2.8.
- Production Passenger должен запускать `twocomms.production_settings`.
- Production MariaDB parity snapshot Stage 0: 332 base tables, 142 InnoDB,
  190 MyISAM, 25 triggers, 0 routines, 0 events.
- Dump с `--single-transaction` дает InnoDB-consistent snapshot; таблицы MyISAM
  остаются best-effort и не дают полной point-in-time гарантии.
- DTF полностью исключен: не проверять DTF URL, DTF database alias, DTF models,
  DTF migrations, DTF commands или DTF hostname.

## Перед любым deploy

Рабочее дерево должно быть чистым, а release SHA должен быть известен. Пароль
берется только из локального файла deploy environment и никогда не печатается.

```bash
source /Users/zainllw0w/.config/twocomms/deploy-env.zsh
test -n "${TWOCOMMS_DEPLOY_PASSWORD:-}" || {
  echo "TWOCOMMS_DEPLOY_PASSWORD не загружен" >&2
  exit 1
}
```

Локальный runtime проверяется только через общий project interpreter:

```bash
TWC_PYTHON="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.venv/bin/python"
test -x "$TWC_PYTHON"
"$TWC_PYTHON" -c 'import django, sys; assert sys.version_info[:3] == (3, 14, 6); assert django.get_version() == "6.1"; print(sys.executable, django.get_version())'
"$TWC_PYTHON" scripts/verify_project_runtime.py
```

Не использовать bare `python`, `python3`, старый lock, SCP, source build,
`deploy.sh`, `scripts/deploy_release.py` или другой release wrapper.

## Server preflight

Выполняется read-only командой в production checkout до pull. Это единственный
поддержанный SSH-шаблон проекта; `bash -lc` и активация server virtualenv
обязательны. На первом release этого Stage 0 сам matrix script еще отсутствует
на старом SHA, поэтому сначала выполняется bootstrap-проверка ниже. После
первого pull полноценный server matrix становится обязательной частью каждого
следующего preflight.

Bootstrap preflight (только runtime, ветка и MariaDB default; без DTF):

```bash
SSHPASS="$TWOCOMMS_DEPLOY_PASSWORD" sshpass -e ssh \
  -o StrictHostKeyChecking=no qlknpodo@195.191.25.63 \
  "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && test \"\$(git branch --show-current)\" = main && test -z \"\$(git status --porcelain=v1 --untracked-files=no)\" && git rev-parse HEAD && python --version && python -m django --version && python -c \"import sys,django; assert sys.version_info[:3] == (3,14,6); assert django.VERSION[:2] == (6,1)\" && python manage.py check --database=default --settings=twocomms.production_settings'"
```

После того как script уже есть на сервере, использовать:

```bash
SSHPASS="$TWOCOMMS_DEPLOY_PASSWORD" sshpass -e ssh \
  -o StrictHostKeyChecking=no qlknpodo@195.191.25.63 \
  "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && python scripts/run_django61_live_matrix.py server --phase preflight'"
```

Ожидается JSON со статусом `ok`, веткой `main`, чистыми tracked-файлами,
CPython 3.14.6/Django 6.1/DRF 3.18.0/mysqlclient 2.2.8, MariaDB на alias
`default`, отсутствием pending non-DTF migrations и работающим `lswsgi`.

HTTP preflight выполняется отдельно, чтобы не смешивать server shell proof и
публичный HTTP proof:

```bash
"$TWC_PYTHON" scripts/run_django61_live_matrix.py http --phase preflight
```

## Разрешенный deploy

1. Зафиксировать `EXPECTED_SHA` после commit и push в GitHub `main`.
2. Повторить bootstrap preflight для первого release или `server --phase preflight`
   для уже установленного matrix script.
3. Выполнить только fast-forward pull:

```bash
SSHPASS="$TWOCOMMS_DEPLOY_PASSWORD" sshpass -e ssh \
  -o StrictHostKeyChecking=no qlknpodo@195.191.25.63 \
  "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && git pull --ff-only origin main'"
```

`git pull` не выполняет миграции автоматически. Если release содержит
одобренную миграцию, сначала должен существовать local MariaDB rehearsal и
backup proof. Для state-only `storefront.0096` отдельный контролируемый шаг
выглядит так:

```bash
SSHPASS="$TWOCOMMS_DEPLOY_PASSWORD" sshpass -e ssh \
  -o StrictHostKeyChecking=no qlknpodo@195.191.25.63 \
  "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && python manage.py migrate storefront 0096 --database=default --settings=twocomms.production_settings --noinput'"
```

Этот шаг нельзя выполнять вслепую, откатывать вручную или распространять на
DTF. Если migration plan не был заранее согласован, deploy останавливается
после pull и передается владельцу production database.

## Post-deploy proof

`EXPECTED_SHA` должен быть ровно SHA, который был отправлен в `main`.

```bash
EXPECTED_SHA="$(git rev-parse HEAD)"

SSHPASS="$TWOCOMMS_DEPLOY_PASSWORD" sshpass -e ssh \
  -o StrictHostKeyChecking=no qlknpodo@195.191.25.63 \
  "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && python scripts/run_django61_live_matrix.py server --phase post-deploy --expected-sha $EXPECTED_SHA'"

"$TWC_PYTHON" scripts/run_django61_live_matrix.py http --phase post-deploy
```

Post-deploy JSON должен подтвердить совпадение `HEAD`, `origin/main` и
`EXPECTED_SHA`, runtime, MariaDB/check/migration state, Passenger и все
разрешенные non-DTF HTTP routes. В артефакты не должны попадать body, headers,
cookies, env, credentials, DSN, user или raw exception.

После завершения:

```bash
unset TWOCOMMS_DEPLOY_PASSWORD
```

Любой failed check означает остановку release и сохранение sanitized JSON для
разбора. Не повторять deploy циклически без новой причины и нового evidence.

## Server to local MariaDB snapshot

Синхронизируется только production Django alias `default`. Имя базы передается
явно через private environment, local target обязан начинаться с
`twc_snapshot_`, а local MariaDB host должен быть loopback.

Dry-run не подключается к серверу и не создает базу:

```bash
export TWOCOMMS_REMOTE_DB_NAMES="replace-with-production-default-db-name"
export TWOCOMMS_LOCAL_HOST="127.0.0.1"
export TWOCOMMS_LOCAL_PORT="3306"
export TWOCOMMS_LOCAL_DB_PREFIX="twc_snapshot_"
export TWOCOMMS_LOCAL_MYSQL_DEFAULTS_FILE="$HOME/.config/twocomms/local-mariadb.cnf"
export TWOCOMMS_SYNC_ROOT="$HOME/.twocomms-db-sync"
bash scripts/sync_production_mysql.sh --dry-run
```

Apply разрешается только после проверки private defaults file mode `0600` или
`0400`, локального MariaDB, production password environment и отдельного
подтверждения:

```bash
bash scripts/sync_production_mysql.sh --apply --confirm-production-snapshot
```

До закрытия `FOUNDATION-DB-001` дополнительно требуется code review guardrails:
remote host/user/project/venv должны задаваться private environment, remote
shell должен соответствовать approved `bash -lc` path, а несовместимые флаги
`--dry-run` и `--apply` должны быть отвергнуты в любом порядке. Наличие safety
tests без реального dump/restore не является parity proof.

Архивы, rollback и temporary databases находятся вне Git и имеют mode `0600`.
После restore сверяются table/engine/trigger/routine/event counts и отсутствие
DTF database. Полную идентичность данных MyISAM нельзя заявлять без maintenance
lock или перевода таблиц в InnoDB.

## Чекбоксы и доказательства

Stage 0 checkbox не отмечается по наличию файла или локальному зеленому тесту.
Нужны baseline, focused tests, no-network/check/migration proof, GitHub `main`,
а для production effect - deployed SHA и post-deploy evidence. DTF должен быть
исключен из кода, тестов и server commands.

General Django 6.1 CI дополнительно валидирует оба tracked schema v2 A/B
artifact и после full smoke сравнивает свежий Django 6.1 log с tracked
candidate. Сам smoke может завершиться с известным ненулевым unittest status,
но новая summary/failure/error delta делает comparison step красным.
