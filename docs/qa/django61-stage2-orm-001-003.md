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
- [x] Historical ORM-001..003 release SHA:
  `c8e6b13bd2d7cd72301a5031513e60adfb1fb639`.
- [x] Historical production runtime: CPython `3.14.6`, Django `6.1`.
- [x] Historical production check: только четыре ранее известные
  `DJ6-BASE-004` warnings.
- [x] Historical storefront, management, storage и finance probes: HTTP `200`.
- [x] Current combined Stage 2 release SHA:
  `505458e919064205113aeb9b88e2e471ac2488ef`; current post-deploy matrix
  прошла 10 non-DTF probes: 8 ожидаемых `200` и 2 ожидаемых `302` login redirects.

## MariaDB evidence и ограничение

На 10 production заказах old/new payment projection имеют одинаковый
`EXPLAIN`; меняется только выбранная колонка, access plan не ухудшен.

На исходном production read-only probe от 2026-08-16 `finance_consignmentitem`
содержала `0` строк, поэтому live old/new `EXPLAIN` сообщал `Impossible WHERE
noticed after reading const tables`. Это historical baseline, а не disposable
fixture и не новый release proof.
Data-bearing proof выполнен отдельно на disposable MariaDB `11.4.12` после
полного migration graph и `ANALYZE TABLE`: 10 целевых consignment rows,
1 non-consignment row и 500 rows другой компании.

- `reseller_frozen()`: old/new `type=ref`, key `idx_cons_item_res_cons`,
  estimate `10`, `Using where`.
- `consignment_frozen_total()`: old/new `type=ref`, company FK key,
  estimate `11`, `Using where`.
- В обеих парах SQL отличается только добавленной колонкой `is_consignment`;
  filters, params, ordering и планы совпадают. Old/new totals равны
  `Decimal('246.80')`, query count `11 -> 1`.
- Временные schema/user и native MariaDB process удалены; cleanup проверен.

Live `EXPLAIN` следует повторить после появления production consignment rows,
но data-bearing exit gate Stage 2 закрыт без использования production как fixture.
Current release/runtime proof находится в `docs/qa/django61-stage2-completion-report.md`.
