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

## Закрытие временных warnings (2026-08-19)

Временный allowlist удалён. `ReviewVote` использует обычный unique key для
зарегистрированных пользователей и nullable stored generated identity для
гостей. `ProductFitOption` использует nullable generated product identity для
default-строки. Для web-push Django state больше не объявляет unsupported
длинный unique field, но `SeparateDatabaseAndState` не меняет production
column/index: существующий `varchar(1000)` и `UNIQUE endpoint USING HASH`
сохраняются. State-only `UniqueConstraint(endpoint)` сохраняет ORM validation,
а digest-колонка не создаётся.

Каждая data migration сначала выполняет fail-closed duplicate scan и не
исправляет данные автоматически. MyISAM DDL выполняется с
`Migration.atomic = False`, `IF NOT EXISTS`, exact schema verification после
каждого шага и повторяемым `DROP ... IF EXISTS` reverse. Disposable MariaDB
gate требует ноль warnings и доказывает три MyISAM engines, две generated
columns, три новых unique indexes, сохранённый endpoint HASH index,
существующий `(product_id, code)` key и `SHOW CREATE TABLE`. DTF не
подключается.

Финальная проверка на disposable MariaDB `11.4.12`:

```text
model/migration contracts: focused gate OK
MariaDB gate runner: focused gate OK
database check: allowed_warnings=0
physical proof: engines=3_myisam generated_columns=2_verified
unique_indexes=3_new+1_preserved endpoint_unique=hash_preserved
cleanup=verified
makemigrations --check: No changes detected
```
