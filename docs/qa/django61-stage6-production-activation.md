# Django 6.1 Stage 6: production activation evidence

Дата: 2026-08-19. Scope: только non-DTF `DJ6-BASE-005`, `DJ6-SRV-001` и
`DJ6-TASK-001`.

## Итоговое решение

Production backend для разрешенного Stage 6 scope - opt-in MariaDB-backed
durable adapter с одним bounded cron owner. Redis/Celery не включались и не
являются частью этого решения: настроенный Redis hostname по-прежнему не
разрешается, поэтому DNS/TCP/TLS/auth/ACL для Redis не доказаны. Endpoint,
credentials и тариф Redis не менялись.

Подтвержденный production SHA:
`ba032bbd2030421d2340e9314a921eddabe2f582`.

## Production runtime и schema

- CloudLinux-bound Python: CPython `3.14.6`, Django `6.1`;
- authoritative database: MariaDB через `django.db.backends.mysql`,
  `CONN_MAX_AGE=0`;
- scoped migration `task_runtime.0001_initial` применена;
- `task_runtime_durabletask` использует `InnoDB`;
- `TASKS["default"]` остается `ImmediateBackend`. Durable alias opt-in и
  допускает только зарегистрированный `no_send_canary`; provider calls,
  пользовательские записи и произвольные Django Tasks fail-closed.

## No-send restart/reclaim canary

Отдельный process получил durable lease и завершился до финализации. Следующий
bounded worker reclaimed запись после истечения lease. Одна durable row дошла
до `done` с `attempts=2`, одним idempotency key и result
`external_io=false`; duplicate completion не произошло.

Первый ручной низкоуровневый probe с неверной формой payload был безопасно
отклонен как `missing marker`, а его diagnostic row удалена. Успешный canary
использовал Django Tasks payload:

```json
{"args": [], "kwargs": {"marker": "<idempotency-key>"}}
```

## Cron ownership и capacity

- durable cron установлен и здоров: ровно один managed marker/owner;
- installer `--check` прошел; полный periodic-owner validator вернул
  `status=ok`;
- production cron log: `claimed=0 completed=0 failed=0 lost=0`;
- `product_catalog_image_jobs` остается inventory-only с `active:false`:
  его managed block и owner отсутствуют. Это не rollout image worker;
- свежий budget gate: `1/20` account MariaDB connections, `34/1024` FDs и
  `7/512874` processes; после bounded worker остается headroom `18` DB
  connections, `958` FDs и `512864` processes.

## Граница решения

Cron остается единственным managed execution и rollback path для этого
production backend. Эта activation не дает разрешения на Redis rollout,
Celery/supervisor, image-optimization cron, provider side effects, generic
migrations, DTF actions или изменение данных за пределами scoped no-send
canary. Новая domain task требует отдельного allowlist, idempotency/lease
contract и собственных production gates.
