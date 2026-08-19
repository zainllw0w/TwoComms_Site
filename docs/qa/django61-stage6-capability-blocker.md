# Django 6.1 Stage 6: production capability decision and Redis blocker

Исходная read-only проверка: 2026-08-18 23:13-23:16 Europe/Kiev.
Production activation evidence: 2026-08-19.

Scope: `DJ6-BASE-005`, `DJ6-SRV-001`, `DJ6-TASK-001`

Исходный probe был только read-only SSH: DTF, schema, данные и runtime тогда
не изменялись. Последующая activation была строго ограничена
`task_runtime.0001_initial`, no-send canary и managed cron; ее факты приведены
ниже и в `docs/qa/django61-stage6-production-activation.md`.

## Решение, обновлено 2026-08-19

Redis/Celery имеет статус **NO-GO**: Redis DNS не работает, а долгоживущий
supervisor/daemon worker не является доказанной capability. Redis endpoint,
credentials, TLS/ACL policy и тариф не изменялись.

Это не блокирует текущий Stage 6 scope. Официально выбран и активирован
MariaDB-backed durable Django Tasks adapter с одним bounded cron owner. Он
прошел scoped migration, no-send restart/reclaim canary, owner validation и
resource budget. `ImmediateBackend` по-прежнему нельзя использовать для
тяжелых Django Tasks и он остается только default request-path backend.

Таким образом, закрытие трех scope-пунктов означает подтвержденное решение
через альтернативный backend, а не ложное утверждение, что Redis стал рабочим.

## Исторический read-only evidence

Проверка выполнена через CloudLinux-bound Python Selector runtime:

- CPython `3.14.6`, Django `6.1`, production database engine
  `django.db.backends.mysql`;
- Redis endpoint и пароль присутствуют в process environment, но DNS lookup
  настроенного Redis Cloud hostname завершается `gaierror`;
- из-за DNS failure TCP, TLS, `PING`, `ACL WHOAMI` и `INFO` не достигаются;
  `redis-py 5.2.1` установлен, поэтому это не import-only failure;
- endpoint объявлен со схемой `redis`, а не `rediss`; TLS capability не
  доказана и не должна выводиться из наличия credentials;
- Celery не установлен; `redis-cli`, `supervisorctl` и доступный `systemctl`
  отсутствуют;
- Django `TASKS.default` разрешается в
  `django.tasks.backends.immediate.ImmediateBackend`;
- в видимой account process table есть один долгоживущий Python process;
  доказательства отдельного task worker, supervisor restart policy или
  graceful shutdown нет;
- user crontab содержит восемь bounded entries с cadence от одной минуты до
  одного часа. Они используют `flock`/`timeout` и остаются текущим ownership
  path; параллельный scheduler добавлять нельзя;
- MariaDB `11.4.12`: `CONN_MAX_AGE=0`, `CONN_HEALTH_CHECKS=True`,
  `max_user_connections=20`, `max_connections=150`,
  `Threads_connected=15`, `Threads_running=1`,
  `Max_used_connections=77`, `wait_timeout=60`;
- `Threads_connected` и `Max_used_connections` являются global counters MariaDB;
  они не показывают текущее число соединений именно account user. Поэтому
  фактический per-user headroom не доказан этим snapshot;
- account file-descriptor limit равен `1024`.

Секреты и значения credentials не выводились. Probe не выполнял Redis writes,
MariaDB writes/DDL, migrations, cache cleanup, process start/restart или
изменение cron.

## Checklist decision

| Пункт | Статус | Решение и доказательство |
| --- | --- | --- |
| `DJ6-BASE-005` | ЗАКРЫТО: Redis NO-GO, cron alternative green | Capability review завершен: Redis недоступен, daemon/supervisor не доказан; MariaDB durable adapter с bounded cron прошел отдельный owner/reclaim/budget gate. |
| `DJ6-SRV-001` | ЗАКРЫТО через альтернативу | Рабочий Redis endpoint не получен и не менялся. Формально выбран MariaDB-backed durable adapter с bounded cron; Redis не добавлен как production dependency. |
| `DJ6-TASK-001` | ЗАКРЫТО: production active, scope limited | `task_runtime.0001_initial` применена к MariaDB/InnoDB; no-send canary доказал restart/reclaim без duplicate completion; один active cron owner и resource budget green. `ImmediateBackend` таким backend не является. |

## Реализованный и активированный альтернативный backend

При текущих ограничениях реализован и активирован MariaDB-backed durable Django
Tasks adapter и bounded cron worker, без Redis/Celery daemon:

1. Adapter сохраняет только allowlisted task name, JSON-safe scalar IDs,
   idempotency key, status, attempts, `available_at`, lease token/expiry и
   последнее bounded error; ORM instances и credentials не сериализуются.
2. Один management command по cron использует существующие `flock`/`timeout`,
   забирает малый batch через atomic claim/lease и всегда закрывает DB
   connection между jobs.
3. Первый canary не вызывает provider, не пишет пользовательские данные и
   только переводит durable row через `PENDING -> RUNNING -> DONE`.
4. Production canary доказал reclaim expired lease после остановки отдельного
   process: одна row завершилась `done`, `attempts=2`, с одним idempotency key
   и `external_io=false`, без duplicate completion.
5. Свежий CloudLinux-bound gate сохранил `CONN_MAX_AGE=0` и подтвердил
   `1/20` account MariaDB connections, `34/1024` FDs, `7/512874` processes;
   post-worker headroom составил `18/958/512864`.

Initial adapter intentionally allows only the registered no-send canary.
Ordinary Django enqueue creates a fresh dispatch; business deduplication must
be supplied through the explicit durable-row contract rather than inferred
from task arguments. Production schema activation была строго scoped к
`task_runtime.0001_initial`; generic migrations, provider side effects и DTF
не затрагивались. Full evidence:
`docs/qa/django61-stage6-production-activation.md`.

## Redis остается отдельным будущим вариантом

Host/Redis owner может предоставить исправленный endpoint и обязательный
TLS/ACL contract. После этого read-only DNS/TCP/TLS/auth/ACL probe повторяется
из того же CloudLinux-bound runtime. Redis backend рассматривается только как
отдельная будущая архитектурная замена после green probe, отдельного
process/connection budget и migration plan; он не нужен для текущего
активированного MariaDB/cron backend.
