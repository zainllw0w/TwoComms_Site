# Отчет о завершении Django 6.1 Stage 0

Дата закрытия: 2026-08-16.

Stage 0 завершен. Его задача была не исправить весь старый test debt, а создать
доказательный runtime и release-контур, в котором следующие изменения можно
сравнивать без silent downgrade, внешней сети, DTF и подмены MariaDB локальным
SQLite.

## Release evidence

| Проверка | Доказательство | Результат |
| --- | --- | --- |
| Runtime release SHA | `df5a99d09b4135bdc7d70baba7956e89e3610ca9` | `HEAD == origin/main`, branch `main`, на момент release proof |
| Django CI | [Run 31967237986](https://github.com/TwoComms-shop/TwoComms_Site/actions/runs/31967237986) | `success` |
| MariaDB CI | [Run 31967237927](https://github.com/TwoComms-shop/TwoComms_Site/actions/runs/31967237927) | `success` |
| Django artifact | `django61-stage0-evidence` | uploaded, retention 14 days |
| MariaDB artifact | `mariadb-gate-evidence` | uploaded, retention 14 days |
| Production migration | `storefront.0096` | applied, pending non-DTF migrations `0` |
| Server matrix | SHA/runtime/MariaDB/check/Passenger | `status=ok` |
| HTTP matrix | 10 non-DTF probes | `status=ok` |

## Что закрыто

- Exact runtime: CPython 3.14.6, Django 6.1, DRF 3.18.0, mysqlclient 2.2.8.
- Hash-locked dependency install и запрет silent downgrade.
- Реальный migration-drift gate с RED/GREEN contract.
- No-network policy внутри test subprocess.
- `check --database=default` на disposable MariaDB 11.4.
- Import/parser smoke для 138 non-DTF management commands.
- Production-like `collectstatic`/WhiteNoise/compressor gate.
- Compatibility contracts текущих active dependency pins.
- Local production-default MariaDB snapshot и restore/parity rehearsal вне Git.
- Production alias `default`: 332 base tables, 142 InnoDB, 190 MyISAM,
  25 triggers, 0 routines и 0 events.
- Sanitized server/HTTP preflight и post-deploy matrices.

## A/B и старый test debt

Полный одинаковый non-DTF scope на Django 5.2.11 и 6.1 содержит по 6080
тестов. Обе версии дали `71 failures`, `30 errors`, `10 skipped`; typed delta
равен `0`. Все 101 failure/error occurrences входят в 31 детерминированный
cluster. Неподтвержденные причины остаются `diagnosis=null`.

Release CI повторил Django 6.1 smoke за 422.297 сек. и подтвердил:

```text
status=matched
tests=6080
failures=71
errors=30
skipped=10
fresh_only=[]
tracked_candidate_only=[]
```

Это доказывает отсутствие нового Django 6.1 delta, но не объявляет старые 101
outcome исправленными.

## Граница DTF

DTF routes, database alias, production data, host и test identifiers не
использовались. Полный A/B имеет `dtf_scope=excluded` и
`dtf_migration_setup=not-loaded`.

Исторический 14-test MariaDB A/B имеет более узкое доказательство: DTF test
identifiers исключены, но setup старых logs применял DTF migration dependency.
Это записано в artifact как:

```text
dtf_scope=test-identifiers-excluded
dtf_migration_setup=included-in-historical-logs
```

Строгий DTF-zero setup для этого исторического MariaDB artifact не заявляется.

## CI после закрытия

Обычный pull request и push в `main` выполняют fast required checks и не
повторяют 6080-test smoke. Fresh полный smoke остается явным release proof
через manual `workflow_dispatch`. Push, меняющий только
implementation/report Markdown, не запускает длинный suite повторно.

## Передача в Stage 1

Stage 1 открыт. В release уже вошли подготовительные explicit SHA-1,
`MAILERS` и `load_module()` изменения, но их checklist items не отмечены:
необходимо продолжить с текущего кода и закрыть полный payment/email/import
call graph, regression matrix и exception policy без повторной реализации.
