# Django 6.1 Stage 3: DJ6-BG-005 и DJ6-BG-006

Дата production acceptance: 2026-08-17. DTF scope исключён.

## Что изменено

- Nova Poshta tracking middleware удалён из active request stack.
- Legacy middleware-классы оставлены import-compatible, но являются чистым
  pass-through и не запускают cache, ORM, provider API или thread.
- `NOVA_POSHTA_FALLBACK_ENABLED` принудительно выключен; единственный owner
  tracking batch - managed cron `update_tracking_statuses`.
- `kick_order_fulfillment()` больше не запускает daemon thread из Passenger.
  Durable `IgOrderCustomerEvent` state machine и её cron reconciliation не
  менялись.

## Локальные gates

- [x] RED: legacy Nova flag запускал `threading.Thread`, middleware находился в
  active stack, fulfillment wake создавал daemon thread.
- [x] GREEN: 40 focused тестов прошли:
  `orders.tests.test_background_ownership`,
  `storefront.tests.test_nova_poshta_tracking_command`,
  `management.tests_ig_order_fulfillment`.
- [x] `manage.py check --settings=test_settings_no_network_non_dtf` прошёл.
- [x] Changed-file `py_compile` и `git diff --check` прошли.

## Production evidence

- Code release SHA:
  `83652c134d3d35398b3098337751ba90813dc8c6`.
- Preflight: CPython `3.14.6`, Django `6.1`, MariaDB `11.4.12`, pending
  non-DTF migrations `0`, tracked checkout clean.
- До release: Nova Poshta managed cron block совпадал с repository installer;
  tracking due backlog `0`, fulfillment due backlog `0`.
- После release: `HEAD == origin/main`, server matrix `status=ok`, middleware
  отсутствует в runtime settings, legacy flag `False`, fulfillment kick
  возвращает `None` без thread.
- Passenger был перезапущен через `tmp/restart.txt`; первый внешний HTTP gate
  попал в короткое окно restart и вернул `http_status_invalid`. Немедленная
  status matrix показала ожидаемые ответы, повторный официальный gate прошёл
  все 10 non-DTF probes.

## Граница закрытия

Закрыты только `DJ6-BG-005` и `DJ6-BG-006`. Общая унификация timeout,
exit-code и alerting cron jobs остаётся в `DJ6-SRV-005`; остальные Stage 3
side effects не считаются завершёнными.
