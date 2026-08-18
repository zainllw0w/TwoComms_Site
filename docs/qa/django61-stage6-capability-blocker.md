# Django 6.1 Stage 6: production capability blocker

Дата проверки: 2026-08-18 23:13-23:16 Europe/Kiev

Scope: `DJ6-BASE-005`, `DJ6-SRV-001`, `DJ6-TASK-001`

Режим: только read-only SSH; DTF, schema, данные и runtime не изменялись.

## Решение

Переход на production worker/backend пока имеет статус **NO-GO**. Текущие
cron-команды остаются единственным подтвержденным owner/rollback path, а
`ImmediateBackend` нельзя использовать для тяжелых Django Tasks.

Причина не в Django 6.1: инфраструктурные prerequisites на production не
выполнены. Ни один из трех scope-пунктов нельзя закрыть предположением или
локальным импортом зависимости.

## Live evidence

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

## Что блокирует чекбоксы

| Пункт | Статус | Недостающее доказательство |
| --- | --- | --- |
| `DJ6-BASE-005` | OPEN / BLOCKED | Host owner должен подтвердить допустимый endpoint, DNS route, TLS policy, auth/ACL и способ долговременного process supervision. Нужен отдельный bounded capacity test нового процесса при лимите 20 DB connections. |
| `DJ6-SRV-001` | OPEN / BLOCKED | Нужен рабочий endpoint с успешными DNS, TCP, TLS, authenticated `PING`, ACL identity и read-only server metadata probes либо формально согласованный другой backend. |
| `DJ6-TASK-001` | OPEN / BLOCKED | Нужен выбранный внешний Django Tasks adapter, durable no-send canary, restart/reclaim/duplicate proof и явный перевод ownership только одной периодики. `ImmediateBackend` таким backend не является. |

## Следующий implementable candidate

При текущих ограничениях ближайший проверяемый вариант - MariaDB-backed
durable Django Tasks adapter и bounded cron worker, без Redis/Celery daemon:

1. Adapter сохраняет только allowlisted task name, JSON-safe scalar IDs,
   idempotency key, status, attempts, `available_at`, lease token/expiry и
   последнее bounded error; ORM instances и credentials не сериализуются.
2. Один management command по cron использует существующие `flock`/`timeout`,
   забирает малый batch через atomic claim/lease и всегда закрывает DB
   connection между jobs.
3. Первый canary не вызывает provider, не пишет пользовательские данные и
   только переводит durable row через `PENDING -> RUNNING -> DONE`.
4. Crash/restart tests обязаны доказать reclaim expired lease, fencing stale
   owner, отсутствие duplicate completion и сохранение cron rollback path.
5. Connection test должен сохранить `CONN_MAX_AGE=0` и доказать, что bounded
   worker не превышает лимит `max_user_connections=20` при текущих Passenger,
   daemon и cron owners.

Это только кандидат, не выбранный backend. `DJ6-SRV-001` и `DJ6-TASK-001`
остаются открыты до реализации adapter, disposable tests и production restart
canary. Production schema/cron в рамках этой проверки не изменяются.

## Альтернативный следующий шаг для Redis

Host/Redis owner может предоставить исправленный endpoint и обязательный
TLS/ACL contract. После этого read-only DNS/TCP/TLS/auth/ACL probe повторяется
из того же CloudLinux-bound runtime. Redis backend рассматривается только после
green probe и отдельного process/connection budget; существующий cron остается
rollback path до production health evidence.
