# Django 6.1 Stage 4: MariaDB warning/constraint gate

Дата: 2026-08-18. Scope: только non-DTF disposable MariaDB gate; production DDL
и production data не изменялись.

## Закрытые пункты

- [x] `DJ6-BASE-004`: набор четырёх ожидаемых MariaDB system-check warnings
  теперь является точным контрактом. Неизвестный, лишний, пропавший либо
  просроченный warning останавливает gate.
- [x] `DJ6-BASE-004`: gate выполняет duplicate scans для двух вариантов
  `ReviewVote`, default `ProductFitOption` и уникального web-push endpoint.
  Любой найденный дубль останавливает gate до публикации артефакта.
- [x] `DJ6-DB-002`: `information_schema.STATISTICS` и `SHOW CREATE TABLE`
  доказывают фактические unique/check constraints. Conditional constraints,
  которые MariaDB не создаёт, явно фиксируются как
  `unsupported+duplicate_free`, а реально созданные constraints как
  `verified`; смешение этих состояний является ошибкой gate.

## Проверка

```text
$ TWC_PYTHON=.../.venv/bin/python
$ $TWC_PYTHON -m unittest tests.test_mariadb_gate_runner
Ran 43 tests in 0.010s
OK
```

RED перед реализацией: 5 ожидаемых failures/errors из-за отсутствующих
`missing` warning contract, schema proof и duplicate/constraint checks. После
минимальной реализации тот же focused-модуль прошёл 43/43. Полный suite не
повторялся в соответствии с ограниченным Stage 4 scope.

## Ограничения

Gate является fail-closed защитой compatibility/release workflow, а не новым
production constraint. Для unsupported conditional uniqueness production DDL
не добавлялся; конкурентные расхождения обнаруживаются duplicate scan в
disposable MariaDB после выполнения focused concurrency/lifecycle suite. DTF
не подключается и не проверяется этим изменением.
