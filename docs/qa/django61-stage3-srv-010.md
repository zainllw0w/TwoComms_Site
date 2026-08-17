# Django 6.1 Stage 3: DJ6-SRV-010

Дата production acceptance: 2026-08-17. DTF scope исключён.

## Что изменено

- `run_instagram_bot --ensure` больше не считает daemon здоровым только по
  удерживаемому OS lock и текущему release marker: требуется свежий heartbeat.
- Stale heartbeat направляет watchdog в существующий bounded drain/spawn path:
  если старый процесс освобождает lock, запускается новый; если зависший
  процесс удерживает lock, команда завершается ошибкой и не запускает второй
  daemon. Принудительного kill зависшего процесса этот guard не выполняет.
  Второй daemon по-прежнему блокируется внутренними spawn/daemon `flock`.
- Добавлен idempotent installer managed cron block. Он заменяет точную legacy
  строку, сохраняет unrelated crontab entries и запрещает duplicate owners.
- Первичный production acceptance выполнял watchdog каждую минуту через
  внешний non-blocking `flock` и `timeout 50s`. Единый cron contract затем
  поднял deadline до `75s` с `--kill-after=15s`, потому что bounded drain и
  повторное получение singleton lock могут суммарно занимать до 60 секунд.

## Локальные gates

- [x] RED: stale-heartbeat test на исходном коде не различал свежий heartbeat.
- [x] GREEN: 22 `DaemonPathTests` прошли, включая follow-up contract
  fail-closed поведения зависшего worker.
- [x] Stale worker, удерживающий lock, проверен fail-closed тестом: новый
  процесс не запускается, команда возвращает bounded `CommandError`.
- [x] 5 installer contracts прошли: legacy replacement, idempotency,
  preservation, malformed/duplicate rejection, unsafe path и marker boundary.
- [x] `bash -n`, changed-file `py_compile` и `git diff --check`: clean.

## Production evidence

- Release SHA: `4af27a19b4b660b79bcd6bb0fd11cc09b691e0ec`.
- `HEAD == origin/main`.
- Installer `--install` и повторный `--check`: `OK`.
- Watchdog command lines: `1`; managed BEGIN markers: `1`; END markers: `1`.
- Managed line содержит `/usr/bin/flock -n` и
  `/usr/bin/timeout --signal=TERM 50s`.
- `run_instagram_bot --ensure`: `daemon alive - ok`.
- Daemon singleton lock удерживается; runtime snapshot:
  `daemon_online=True`, `running=True`, `alive=True`, cron task health healthy.

## Follow-up acceptance единого cron contract

- Releases `5d4e358cb` и `c56123c0d` перевели текущую строку на
  `/usr/bin/flock -n -E 75` и
  `/usr/bin/timeout --signal=TERM --kill-after=15s 75s`.
- Release `254bdb3e6d877daa35cb60f619b231d0d94d4094` добавил fail-closed
  распознавание любого loose/duplicate watchdog owner, сохранив миграцию
  поддерживаемой legacy-строки.
- Production: ровно один `run_instagram_bot --ensure`, installer `--check=OK`,
  watchdog heartbeat healthy, `/bot/health/` вернул `status=ok` и
  `bot_state=running`; DTF scope не открывался.

## Граница закрытия

Этот пункт закрывает singleton/overlap поведение `DJ6-SRV-010`. Общий contract
шести production jobs закрыт отдельно как `DJ6-SRV-005`; он не заменяет
durable provider state и ambiguous-delivery recovery.
