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
- Production watchdog выполняется каждую минуту через внешний non-blocking
  `flock` и `timeout 50s`, то есть один starter не переживает следующий cadence.

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

## Граница закрытия

Этот пункт закрывает только `DJ6-SRV-010`. Единый contract всех production
cron jobs (`DJ6-SRV-005`) остаётся открытым до унификации owner/cadence/timeout,
bounded batch, retry/backoff, exit code и alerting для остальных команд.
