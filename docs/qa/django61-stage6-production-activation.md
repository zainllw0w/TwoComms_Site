# Django 6.1 Stage 6: production activation evidence

Дата: 2026-08-19. Scope: non-DTF `DJ6-BASE-005`, `DJ6-SRV-001`,
`DJ6-TASK-001`, `DJ6-TASK-002`, `DJ6-BG-004`, `DJ6-BG-008` и
`DJ6-BG-010`. Production activation относится только к первым трём пунктам;
остальные строки документа фиксируют deployed code/policy state и явно не
выдают inactive image cron за активированный worker.

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

## Матрица закрытия implementation checkbox

| Пункт | Code evidence | Focused contract | Production evidence и граница | Итог |
| --- | --- | --- | --- | --- |
| `DJ6-BASE-005` | `docs/qa/django61-stage6-capability-blocker.md`; budget и owner validators | `tests.test_django61_stage6_task_budget_gate`, `tests.test_django61_stage6_periodic_owners` | CloudLinux-bound capability review подтвердил Redis DNS NO-GO и допустимый bounded cron/MariaDB budget | закрыт как capability decision, не как рабочий Redis |
| `DJ6-SRV-001` | `twocomms/twocomms/settings.py`, `twocomms/task_runtime/runtime.py`, `scripts/install_django61_durable_tasks_cron.sh` | durable runtime, cron installer, budget и owner contracts | официально выбран и активирован MariaDB-backed durable alias; Redis endpoint/credentials не менялись | закрыт через доказанную альтернативу |
| `DJ6-TASK-001` | `twocomms/task_runtime/models.py`, `runtime.py`, `tasks.py`, `run_durable_tasks.py`, migration `0001_initial` | `management.tests_django61_task_runtime` плюс cron/budget/owner contracts | InnoDB table, restart/reclaim no-send canary, один cron owner и green budget на SHA `ba032bbd2030421d2340e9314a921eddabe2f582` | закрыт для allowlisted no-send scope |
| `DJ6-TASK-002` | `twocomms/twocomms/task_boundaries.py` | `management.tests_django61_task_backend_guard` | project-level heavy-task boundary отклоняет `ImmediateBackend`, `DummyBackend` и backend без capability; текущих production heavy-task callers вне boundary нет. Это не глобальный перехват произвольного `Task.enqueue()` | закрыт как boundary contract |
| `DJ6-BG-004` | `twocomms/product_catalog/image_jobs.py`, reconcile command, `image_optimizer.py`, image cron installer | `product_catalog.tests.test_editor`, `storefront.tests.test_image_optimization`, `tests.test_install_product_catalog_image_jobs_cron` | request-owned executor удалён, durable image rows и bounded command реализованы; production cron marker/owner намеренно отсутствует, поэтому live worker execution не заявляется | code complete, rollout planned/inactive |
| `DJ6-BG-008` | `twocomms/storefront/views/qr.py` | `storefront.tests.test_qr_thanks` | deployed source не создаёт QR worker: сохранены promo/cookie/PageView, request-owned alert удалён; отдельный live QR smoke не заявлен | закрыт как решение удалить alert |
| `DJ6-BG-010` | `twocomms/twocomms/image_middleware.py` | `twocomms.tests_image_middleware_guard` и adjacent middleware suite | `MiddlewareNotUsed` fail-closed входит в deployed source; activation не включает image middleware | закрыт как запрет включения без proof |

## Матрица exit gate

| Exit gate | Доказательство | Итог |
| --- | --- | --- |
| Один owner каждой активной периодики | full active non-DTF owner validator `status=ok`; durable marker/owner `1`; inactive image marker/owner `0` | закрыт |
| Restart/reclaim без потери или дубля | отдельный lease-owner завершился до finish; reclaim worker завершил одну canary row как `done`, `attempts=2`, `external_io=false` | закрыт |
| Connection/FD/process budget | `1/20` DB connections, `34/1024` FDs, `7/512874` processes; headroom `18/958/512864`; gate `status=ok` | закрыт |
| Cron как execution/rollback path | точный durable managed block, installer `--check`, owner validator и фактический idle cron log green | закрыт |

## Что остаётся вне Stage 6 completion

- `product_catalog_image_jobs` остаётся `active:false`; image cron, live media
  volume и asset verification требуют отдельного rollout gate. Закрытый
  `DJ6-BG-004` означает завершённый перенос кода, а не активную периодику.
- `ImageOptimizationMiddleware` остаётся fail-closed и не включается флагом.
- Durable allowlist содержит только no-send canary. Provider/domain tasks,
  Redis/Celery и новый scheduler не разрешены этой activation.
- DTF полностью исключён.
