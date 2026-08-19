# Django 6.1 Stage 6: durable task runtime activation

Дата: 2026-08-19

Scope: `DJ6-TASK-001`, только non-DTF Django 6.1 code и подтвержденная
production activation. Исторический локальный implementation slice сохранен
ниже как часть доказательств, но больше не является текущим status.

## Что реализовано

- `task_runtime.DurableTask` хранит allowlisted task name, JSON payload,
  explicit idempotency key, schedule, lease token/expiry, attempts, result и
  bounded error.
- Alias `TASKS["durable"]` является opt-in. `TASKS["default"]` остаётся
  `ImmediateBackend`, поэтому существующий request path не переключается.
- `run_durable_tasks` выполняет один bounded batch, восстанавливает истёкшие
  leases и закрывает старые database connections до и после работы.
- Обычный `Task.enqueue()` всегда получает новый dispatch key. Явная
  idempotency доступна только низкоуровневому API, которому caller передаёт
  бизнес-ключ самостоятельно.
- Fencing проверяет status, observed lease token и expiry. Потерявший lease
  worker записывает `lost` и продолжает batch, не выполняя второй stale finish.
- `takes_context` отклоняется до enqueue. Пока lease renewal и domain
  side-effect contract не доказаны, runtime разрешает только зарегистрированный
  `no_send_canary`; provider calls и пользовательские записи fail-closed.

## Предварительная локальная проверка

```text
management.tests_django61_task_runtime: 6/6 OK
django check: OK
py_compile: OK
git diff --check: OK
```

Runtime: CPython `3.14.6`, Django `6.1`.

## Production activation 2026-08-19

- Production SHA: `ba032bbd2030421d2340e9314a921eddabe2f582`.
- CloudLinux-bound runtime подтвердил CPython `3.14.6`, Django `6.1`, MariaDB
  через `django.db.backends.mysql` и `CONN_MAX_AGE=0`.
- Scoped migration `task_runtime.0001_initial` применена; таблица
  `task_runtime_durabletask` использует `InnoDB`.
- Separate process получил lease и завершился до финализации. После expiry
  bounded worker reclaimed ту же запись: один idempotency key завершился
  `done`, `attempts=2`, `external_io=false`, без duplicate completion.
- Durable cron имеет ровно один managed marker/owner; installer `--check` и
  полный periodic-owner validator вернули green/status `ok`. Реальный cron log:
  `claimed=0 completed=0 failed=0 lost=0`.
- Fresh budget gate: `1/20` account MariaDB connections, `34/1024` FDs и
  `7/512874` processes; post-worker headroom: `18` DB connections, `958` FDs
  и `512864` processes.

Успешный canary использовал Django Tasks payload
`{"args": [], "kwargs": {"marker": "<idempotency-key>"}}`. Ранний
низкоуровневый probe с другой формой payload был корректно отклонен как
`missing marker`; его diagnostic row удалена и не считается failed canary.

## Что намеренно не включено

- Redis остается DNS NO-GO; endpoint, credentials, TLS/ACL policy и тариф не
  менялись. Celery/supervisor daemon не добавлялись.
- `TASKS["default"]` остается `ImmediateBackend`. Durable alias разрешает
  только allowlisted `no_send_canary`; business/provider side effects и
  произвольные enqueue fail-closed.
- `product_catalog_image_jobs` остается inventory-only (`active:false`) без
  cron owner/block. Это не production rollout image worker.
- DTF, generic migrations и изменения данных вне scoped no-send canary не
  выполнялись.

## Статус и следующий scope

`DJ6-TASK-001` закрыт вместе с `DJ6-BASE-005`, `DJ6-SRV-001` и Stage 6
exit gates: MariaDB durable adapter плюс bounded cron является утвержденным
production backend для этого ограниченного scope. Cron остается единственным
managed execution/rollback path.

Следующая domain task требует отдельного allowlist, idempotency/lease contract,
capacity gate и production evidence. Redis или image-worker rollout являются
отдельными решениями и не следуют автоматически из этой activation.

Полная production evidence: `docs/qa/django61-stage6-production-activation.md`.
