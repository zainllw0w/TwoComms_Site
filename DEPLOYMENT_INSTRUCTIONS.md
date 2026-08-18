# TwoComms: текущий deployment contract

Этот файл заменяет старые audit-инструкции. Единственный поддерживаемый
production-путь для текущего Django 6.1 runtime: commit scoped changes, push в
GitHub `main`, затем fast-forward pull на сервере через CloudLinux-bound
virtualenv. Старые feature-ветки, адреса, release wrappers, SCP/source-build и
ручная установка зависимостей больше не являются deployment contract.

## Runtime

- CPython `3.14.6` (`.python-version`)
- Django `6.1`
- Django REST Framework `3.18.0`
- MariaDB `11.4.12` на production alias `default`
- `mysqlclient` `2.2.8`

Локальные команды Django выполняются только через общий project interpreter,
а не через `python`/`python3` из `PATH`:

```bash
TWC_PYTHON="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.venv/bin/python"
test -x "$TWC_PYTHON"
"$TWC_PYTHON" -c 'import django, sys; assert sys.version_info[:3] == (3, 14, 6); assert django.get_version() == "6.1"; print(sys.executable, django.get_version())'
```

Не выполняйте bare `pip`. Для проверки зависимостей используйте `uv pip ...
--python "$TWC_PYTHON"`.

## Перед push

1. Работайте в отдельном worktree от актуального `origin/main`.
2. Запустите focused tests для измененного блока, `manage.py check`,
   migration-drift check и `git diff --check`.
3. Убедитесь, что DTF-код, DTF-модели, DTF-миграции и DTF-серверные команды не
   затронуты.
4. Зафиксируйте только scoped files и отправьте commit в `main` обычным
   non-force push:

```bash
git push origin HEAD:main
```

## Разрешенный server pull

Пароль никогда не записывается в команду, вывод или документацию. Загрузите
его из локального private environment:

```bash
source /Users/zainllw0w/.config/twocomms/deploy-env.zsh

test -n "${TWOCOMMS_DEPLOY_PASSWORD:-}" || {
  echo "TWOCOMMS_DEPLOY_PASSWORD не загружен" >&2
  exit 1
}

SSHPASS="$TWOCOMMS_DEPLOY_PASSWORD" sshpass -e ssh \
  -o StrictHostKeyChecking=no qlknpodo@195.191.25.63 \
  "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && git pull --ff-only origin main'"

unset TWOCOMMS_DEPLOY_PASSWORD
```

Стандартный pull не выполняет `migrate`, `collectstatic`, очистку release
артефактов, переключение venv или изменение `LD_PRELOAD`. Любая migration,
static/runtime mutation или database operation требует отдельного одобренного
runbook и production evidence; не добавляйте её автоматически к pull.

## Post-deploy read-only proof

Подставьте SHA, который был отправлен в `main`, и выполните только
неизменяющие проверки:

```bash
EXPECTED_SHA="$(git rev-parse HEAD)"

source /Users/zainllw0w/.config/twocomms/deploy-env.zsh
test -n "${TWOCOMMS_DEPLOY_PASSWORD:-}" || exit 1

SSHPASS="$TWOCOMMS_DEPLOY_PASSWORD" sshpass -e ssh \
  -o StrictHostKeyChecking=no qlknpodo@195.191.25.63 \
  "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && test \"\$(git rev-parse HEAD)\" = \"$EXPECTED_SHA\" && test \"\$(git branch --show-current)\" = main && test \"\$(python --version)\" = \"Python 3.14.6\" && test \"\$(python -m django --version)\" = \"6.1\" && git status --porcelain=v1 --untracked-files=no'"

unset TWOCOMMS_DEPLOY_PASSWORD
```

Для release с production-эффектом дополнительно используйте
`docs/operations/django61-stage0-runbook.md` и соответствующий sanitized
post-deploy matrix. При любой ошибке остановите release и сохраните только
sanitized evidence без credentials, DSN, cookies или raw exception.

## Что не является стандартным deployment path

- `deploy.sh`, `scripts/deploy_release.py` и произвольные release wrappers;
- `pip install`/source builds на production;
- pull из feature-ветки или non-fast-forward reset;
- автоматические `migrate`, `collectstatic`, cache clear и restart;
- удаление или пересоздание production MariaDB/venv/release paths.

Для истории старых audit-изменений используйте документы в `docs/qa/` и
`docs/operations/`; они не переопределяют этот current-facing contract.
