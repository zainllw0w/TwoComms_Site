# DJ6-ORM-013: GeneratedField для итоговой цены

Дата эксперимента: 2026-08-18

Исходный commit: `5000def6f`
Область: только disposable schema; модель `storefront.Product`, миграции,
production MariaDB, DTF и runtime не изменялись.

## Команда и безопасность

Эксперимент запускается из
`scripts/run_generated_price_experiment.py`:

```text
TWC_PYTHON scripts/run_generated_price_experiment.py \
  --mariadb-bin-dir /opt/homebrew/opt/mariadb@11.4/bin
```

Harness:

- поднимает отдельный MariaDB `11.4.12` на loopback и случайном порту;
- создаёт случайные schema/user с префиксом `test_twocomms_gprice_`;
- не читает и не передаёт `DB_*`, `DB_*_DTF`, provider credentials или другие
  application secrets;
- не принимает удалённый host и не открывает DTF alias;
- создаёт только одну временную таблицу `dj6_generated_price_probe` через
  `schema_editor`, после чего удаляет таблицу, user, schema и datadir;
- при любой ошибке завершается fail-closed и не печатает credentials.

## Результат native gate

Среда: CPython `3.14.6`, Django `6.1`, MariaDB `11.4.12-MariaDB`.

| Проверка | Результат |
|---|---|
| GeneratedField persisted DDL | `InnoDB`, persisted/stored generated column, expression с `COALESCE` и MariaDB `DIV` |
| Canonical parity | `29/29` строк: `Product.final_price` = Decimal = serializer fallback = GeneratedField |
| Скидки | `0`, `1`, `33`, `100`; дополнительно `NULL` |
| INSERT generated value | MariaDB/Django вернули значение сразу (`insert_returning=true`) |
| UPDATE generated value | Django 6.1 вернул новое значение сразу (`update_returned_immediately=true`) |
| `refresh_from_db(fields=...)` | новое значение подтверждено |
| `only()`/deferred | generated field был deferred; доступ загрузил его ровно одним SELECT |
| Индексный range plan | `type=range`, key `dj6_gprice_final_idx`, `Using index` |
| Индексный order/limit plan | `type=index`, key `dj6_gprice_final_idx`, без filesort |
| Масштаб index probe | `4126` строк |
| Cleanup | `schema+user+datadir removed` |

## Найденный блокер и точная причина

Первый кандидат с обычным выражением `CASE ... FLOOR(...)` был проверен на
том же disposable MariaDB и отклонён сервером с `ERROR 1901`: MariaDB не
разрешает это выражение в `GENERATED ALWAYS AS`. Варианты с `IF`, `CASE`,
`CAST` и `DIV` внутри условной ветки дали тот же запрет.

Рабочий MariaDB-совместимый кандидат — без условной ветки:

```sql
(price * (100 - COALESCE(discount_percent, 0))) DIV 100
```

Для допустимого диапазона скидки `0..100` он точно соответствует текущему
целочисленному контракту `Product.final_price` и не использует округление
`CAST`.

Однако существующая catalog-аннотация в
`twocomms/storefront/views/catalog.py` использует `Cast(decimal, IntegerField)`.
На MariaDB это округляет отдельные значения, поэтому единый GeneratedField
сейчас нельзя внедрять без исправления всех потребителей формулы.

Обнаруженные расхождения в contract matrix:

| `price` | `discount` | catalog `CAST` | canonical/GeneratedField |
|---:|---:|---:|---:|
| 1 | 1 | 1 | 0 |
| 1 | 33 | 1 | 0 |
| 1091 | 33 | 731 | 730 |
| 2147483647 | 1 | 2126008811 | 2126008810 |

`Product.final_price`, Decimal, serializer fallback и GeneratedField между
собой совпали во всех `29/29` строках. Поэтому это не сбой самого кандидата,
а доказанная несовместимость старой SQL-аннотации с canonical truncation.

## Решение

**NO-GO для production adoption сейчас.** Не добавлять GeneratedField в
`storefront.Product`, не создавать миграцию и не менять production schema.

Следующий отдельный change перед возможным внедрением должен:

1. заменить catalog `CAST` на ту же MariaDB-safe integer semantics и доказать
   response/order/serializer parity;
2. повторить disposable matrix и `EXPLAIN` после изменения всех потребителей;
3. отдельно проверить данные `discount_percent > 100`, поскольку unsigned
   generated output не должен получать отрицательное значение;
4. только после этого подготовить маленькую DDL-миграцию с lock/rollback
   планом. Production/DTF к этому эксперименту не относятся.

## Артефакты

- `scripts/run_generated_price_experiment.py` — fail-closed native harness.
- `tests/test_generated_price_experiment.py` — 7 focused unit contracts.
