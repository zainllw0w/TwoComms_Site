# Django 6.1 Stage 6: periodic ownership and rollback evidence contract

Дата подготовки: 2026-08-19. Scope: только non-DTF периодические jobs.

## Что добавлено

`docs/qa/django61-stage6-periodic-owners.json` является машинным inventory
контрактом. В нём перечислены десять non-DTF owners, включая bounded durable
task canary, guarded auto-analysis и image optimization. Для каждого owner зафиксированы cadence,
команда, managed marker, lock path, `flock` и bounded timeout. Это не меняет
crontab и не утверждает, что live production snapshot уже соответствует
контракту.

Для будущего durable owner зафиксированы тот же CloudLinux production settings
context, что проверяет preflight (`DJANGO_ENV=production` и
`DJANGO_SETTINGS_MODULE=twocomms.production_settings`), и `exec flock`: shell
cron заменяется launcher-ом, поэтому budget из трёх процессов не занижен.

`scripts/verify_django61_stage6_periodic_owners.py` принимает manifest и
санитизированный crontab snapshot (`--crontab PATH` или `--stdin`) и завершает
работу с ошибкой при любом из условий:

- объявлен DTF scope или DTF встречается в evidence;
- встречается неизвестный `# BEGIN TWOCOMMS ...` managed block;
- отсутствует или дублируется managed block/owner;
- owner находится вне своего managed block;
- owner installer отсутствует в repository;
- cadence, lock, `flock` или bounded timeout не совпадают;
- отсутствует явный repository rollback path и rollback owner/action.

Validator только читает файлы: он не устанавливает cron, не запускает Django,
не выполняет SSH, migration, DDL, cleanup или worker.

## Как закрываются чекбоксы

`DJ6-SRV-005` и Stage 6 exit gate «one owner» можно отмечать только после
передачи свежего production `crontab -l` snapshot в этот validator с
результатом `status=ok`, сохранённого вместе с release SHA и датой. Наличие
manifest или green synthetic test недостаточно.

Exit gate «cron remains rollback path» можно отмечать только когда тот же
snapshot, manifest и rollback runbook принадлежат одному release SHA; operator
должен быть явно указан, а rollback script/path доступен в checkout. Этот
commit намеренно оставляет оба production gate открытыми.

## Проверка

Один focused unittest gate:

```text
.venv/bin/python -m unittest tests.test_django61_stage6_periodic_owners -v
```

Дополнительно требуется `py_compile` validator-а и `git diff --check` перед
commit. Production database, cron и DTF не затрагиваются.
