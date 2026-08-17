# Django 6.1 Stage 3: DJ6-SRV-005

Дата production acceptance: 2026-08-17. DTF scope исключён.

## Что изменено

- Добавлен единый repository contract для исходных шести application cron jobs.
  Позднее тот же managed contract был расширен седьмым, guarded owner для
  автоанализа звонков. Watchdog, четыре Instagram periodic jobs, Nova Poshta
  tracking и guarded call-analysis находятся в трёх idempotent managed blocks;
  installer сохраняет unrelated entries и fail closed при duplicate, malformed
  или неизвестном loose owner.
- Каждая scheduled line использует non-blocking `flock -n -E 75` и
  `timeout --signal=TERM --kill-after=15s` с deadline короче либо согласованным
  с cadence задачи.
- Batch limits, durable leases/idempotency markers, provider receipt и
  retry/backoff остаются в command/service state machines. Cron отвечает за
  ownership и запуск, но не объявляется exactly-once системой.
- Шесть активных supervised jobs публикуют durable task heartbeat; failed/stale
  state получает hourly-deduplicated manager alert. Седьмой call-analysis owner
  защищён default-OFF marker и при выключенном флаге не запускает Django, поэтому
  отдельный heartbeat от него не ожидается. Nova Poshta добавлена в supervision.

## Локальные gates

- [x] 20 installer tests прошли для watchdog, periodic block и Nova Poshta,
  включая fail-closed unknown loose owners и malformed marker boundaries.
- [x] 37 focused Django tests прошли для daemon/task-health/Nova contracts.
- [x] `bash -n`, changed-file `py_compile`,
  `manage.py check --settings=test_settings_no_network_non_dtf` и
  `git diff --check` прошли.
- [x] Code releases: `5d4e358cb`, `c56123c0d` и review-hardening
  `254bdb3e6`.

## Production rollout

- `git pull --ff-only origin main` обновил production с `3012b0426` через
  основной contract `c56123c0d` до review-hardening
  `254bdb3e6d877daa35cb60f619b231d0d94d4094`.
- Runtime: CPython `3.14.6`, Django `6.1`, DRF `3.18.0`, mysqlclient `2.2.8`.
- Три installer `--install` и последующие три `--check` вернули `OK`.
- На исходном rollout найдено ровно шесть matching scheduled lines: по одному
  owner для watchdog, order Telegram reconciliation, IG checkout, IG fulfillment,
  IG payments и Nova Poshta. Все шесть содержали ожидаемые `flock` и
  TERM-to-KILL timeout; каждый из трёх managed BEGIN markers существовал один раз.
- Cron самостоятельно выполнил все шесть jobs после установки: task heartbeat
  snapshot показал `healthy=true`, `unhealthy_count=0`, возраст success 15-17
  секунд и пустой `last_error_kind` для каждой задачи. Отдельный ручной
  provider-run не потребовался и не создавал второго owner.
- Long-lived Instagram daemon подтвердил `daemon_alive=True`,
  `daemon_code_current=True`; его supervision видит общий task health как
  healthy.
- Queue snapshot: `dangerous_backlog=0`, inbound/reply/notification/analysis
  pending и recovery unresolved равны `0`. Исторические 18 failed analysis jobs
  не мутировались и остаются отдельным `DJ6-LIVE-002`.

## Release gates

- Server matrix: `status=ok`, `HEAD == origin/main == 254bdb3e6`, tracked tree
  clean, MariaDB `11.4.12`, только alias `default`, pending non-DTF migrations
  `0`, Passenger `lswsgi` processes `6`.
- HTTP matrix: все 10 non-DTF probes прошли с ожидаемыми status codes: storefront
  health/home/catalog/cart, management login/bot health, finance login/health и
  storage login/home.
- Migrations, collectstatic и compress для этого release не требовались.

## Финальный Stage 3 snapshot

- Подтверждённый текущий production/main SHA:
  `718c412682b3eb455068660ebfee75860c92cf7d`.
- Подтверждённый Stage 3 ancestor:
  `6f340cd409c37c25ab8b9084db873e4a0f8a1f94`.
- Production runtime: CPython `3.14.6`, Django `6.1`, MySQL/MariaDB `11.4.12`;
  pending migrations: `0`.
- Все три installer-файла существуют в production checkout, tracked текущим
  `HEAD`, и каждый `--check` завершился с exit code `0` и результатом `OK`.
- Текущий crontab содержит ровно семь owner lines в трёх managed blocks. Шесть
  активных heartbeat entries имеют `healthy=true`, `unhealthy_count=0`; guarded
  call-analysis owner выключен и не должен запускать Python/Django.
- Queue snapshot: `dangerous_backlog=0`; соединения MariaDB: `11/20`.
- Read-only `reconcile_ig_analysis_jobs --dry-run --report-failed --limit 500`
  завершился с exit code `0`: найдено 18 исторических failures, `retry_ids=[]`,
  persisted state не изменялся.
- Storefront, catalog, PDP, management и storage вернули HTTP `200`; DTF не
  входил в scope проверки.

## Граница закрытия

`DJ6-SRV-005` закрывает scheduler ownership, overlap, deadline, batch и
operational health текущих owners. Он не заменяет durable business state и
не закрывает остальные Stage 3 side effects. Новый worker/backend нельзя
включать вторым owner: требуется отдельная ownership migration с теми же
idempotency и ambiguous-delivery правилами.
