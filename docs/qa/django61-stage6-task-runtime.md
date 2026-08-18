# Django 6.1 Stage 6: durable task runtime candidate

Дата: 2026-08-19

Scope: `DJ6-TASK-001`, только non-DTF Django 6.1 code. Этот документ
фиксирует локальный implementation slice, а не production activation.

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

## Локальная проверка

```text
management.tests_django61_task_runtime: 6/6 OK
django check: OK
py_compile: OK
git diff --check: OK
```

Runtime: CPython `3.14.6`, Django `6.1`.

## Что намеренно не сделано

- `task_runtime.0001_initial` не применялась к production MariaDB.
- Production crontab, Redis, Celery, supervisor, venv, database schema/data
  и DTF не изменялись.
- `DJ6-TASK-001`, `DJ6-BASE-005`, `DJ6-SRV-001` и все Stage 6 exit gates
  остаются открытыми.

## Единственный следующий production gate

После отдельного согласования schema mutation: применить только
`task_runtime.0001_initial`, выполнить CloudLinux-bound no-send canary,
доказать restart/reclaim без duplicate completion и измерить дополнительный
MariaDB/FD/process budget. До этого cron остаётся rollback path.
