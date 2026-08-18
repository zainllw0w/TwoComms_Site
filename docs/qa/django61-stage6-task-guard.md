# Django 6.1 Stage 6: heavy-task backend guard

Дата: 2026-08-18
Scope: `DJ6-TASK-002`
Release candidate: `187a8e51d`

## Что сделано

В `twocomms/task_boundaries.py` добавлен fail-closed boundary для тяжёлых
Django Tasks:

- `ImmediateBackend` и `DummyBackend` всегда блокируются;
- неизвестный backend блокируется, пока явно не выставит
  `supports_durable_enqueue = True` после отдельной capability-проверки;
- sync и async enqueue проходят один и тот же guard до вызова задачи;
- ошибка backend resolution также блокирует enqueue.

Существующий Celery/cron runtime и production settings не менялись. Это
защищает будущие call sites и не объявляет worker доступным автоматически.

## Доказательства

- `management.tests_django61_task_backend_guard`: `6/6 OK`;
- `manage.py check --settings=test_settings_no_network_non_dtf
  --database=default`: `System check identified no issues`;
- runtime: CPython `3.14.6`, Django `6.1`;
- `git diff --check`: OK.

## Ограничения

`DJ6-TASK-001`, `DJ6-BASE-005`, `DJ6-SRV-001` и Stage 6 exit gate остаются
открытыми: production Redis/worker, restart persistence, connection budget и
no-send canary ещё не подтверждены. До этого существующие cron остаются
rollback/ownership path, а новые тяжёлые enqueue должны использовать guard.
