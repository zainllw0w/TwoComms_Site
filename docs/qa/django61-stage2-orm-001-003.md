# Django 6.1 Stage 2: DJ6-ORM-001..003

Дата: 2026-08-17. Область: payment snapshots и finance consignment, без DTF.

## Результат

| ID | До | После | Parity |
| --- | --- | --- | --- |
| `DJ6-ORM-001` | 11 запросов для 10 заказов | 1 запрос | 10 snapshot rows; точные discount/payable values |
| `DJ6-ORM-002` | 11 запросов для 10 позиций | 1 запрос | `Decimal('246.80')` |
| `DJ6-ORM-003` | 11 запросов для 10 позиций | 1 запрос | `Decimal('246.80')`; exception policy неизменна |

RED воспроизведён на base SHA `f50348cc0`: каждый тест упал с `11 != 1` и
показал один основной SELECT плюс десять deferred SELECT. GREEN подтверждён на
commit `c8e6b13bd2d7cd72301a5031513e60adfb1fb639`.

## Fetch mode decision

- Глобальный fetch mode не добавлен.
- Локальный smoke показал для этих projection paths: explicit fields - `1`
  запрос, `FETCH_PEERS` - `2`.
- Context7 `/django/django` подтвердил семантику `FETCH_ONE`, `FETCH_PEERS` и
  raise-mode. Так как Context7 source следует Django `main`, точное имя для
  установленного Django 6.1 дополнительно проверено runtime source:
  `FETCH_RAISE` (не будущий/смешанный `RAISE`).

## Verification

- [x] Новые query-count tests: `3/3`.
- [x] Полные затронутые модули: `61/61`.
- [x] Spec review: approved.
- [x] Code quality review: approved.
- [x] `manage.py check`: clean локально.
- [x] Migration drift: `No changes detected` через
  `test_settings_migrations_non_dtf`.
- [x] Changed-file compilation и `git diff --check`: clean.
- [x] Production SHA: `c8e6b13bd2d7cd72301a5031513e60adfb1fb639`.
- [x] Production CPython `3.14.6`, Django `6.1`.
- [x] Production check: только четыре ранее известные `DJ6-BASE-004` warnings.
- [x] Storefront, management, storage и finance probes: HTTP `200`.

## MariaDB evidence и ограничение

На 10 production заказах old/new payment projection имеют одинаковый
`EXPLAIN`; меняется только выбранная колонка, access plan не ухудшен.

Production `finance_consignmentitem` сейчас содержит `0` строк. Old/new
company/reseller `EXPLAIN` также совпадает, но MariaDB сообщает
`Impossible WHERE noticed after reading const tables`. Это не выдаётся за
data-bearing benchmark: representative consignment `EXPLAIN` остаётся открытой
частью общего exit gate Stage 2 и будет выполнен на локальном production mirror.
