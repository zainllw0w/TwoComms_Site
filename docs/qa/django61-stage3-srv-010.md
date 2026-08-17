# Django 6.1 Stage 3: DJ6-SRV-010

Дата production acceptance: 2026-08-17. DTF scope исключён.

## Что изменено

- `run_instagram_bot --ensure` больше не считает daemon здоровым только по
  удерживаемому OS lock и текущему release marker: требуется свежий heartbeat.
- Stale heartbeat направляет watchdog в существующий bounded restart path;
  второй daemon по-прежнему блокируется внутренними spawn/daemon `flock`.
- Добавлен idempotent installer managed cron block. Он заменяет точную legacy
  строку, сохраняет unrelated crontab entries и запрещает duplicate owners.
- Production watchdog выполняется каждую минуту через внешний non-blocking
  `flock` и `timeout 50s`, то есть один starter не переживает следующий cadence.

## Локальные gates

- [x] RED: stale-heartbeat test на исходном коде не увидел restart path.
- [x] GREEN: 21 `DaemonPathTests` прошли.
- [x] 3 installer contracts прошли: legacy replacement, idempotency,
  preservation и malformed/duplicate rejection.
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
