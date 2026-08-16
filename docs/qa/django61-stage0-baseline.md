# Django 6.1 Stage 0 baseline и evidence

Этот файл хранит sanitized baseline для сравнения после каждого release slice.
Он не заменяет CI artifacts и не разрешает отмечать implementation checkbox.

## Scope

- В scope: storefront, management, finance, storage/warehouse, accounts,
  orders, reviews, product catalog и общая non-DTF инфраструктура.
- Вне scope: DTF URLconf, модели, migrations, commands, static files, processes,
  database и hostname.
- Production MariaDB не используется как disposable test fixture.

## Runtime baseline

| Поле | Значение |
| --- | --- |
| Python | CPython 3.14.6 |
| Django | 6.1 |
| DRF | 3.18.0 |
| mysqlclient | 2.2.8 |
| MariaDB | 11.4.12 production runtime; exact live value проверяется matrix |
| A/B source baseline SHA | `f57f8cfb47ffa726815081365499ce7ccee7ec2c` |
| Stage 0 release SHA | `df5a99d09b4135bdc7d70baba7956e89e3610ca9` |

Exact runtime должен подтверждаться `scripts/verify_project_runtime.py`, а не
версией, напечатанной bare `python` из PATH.

## Статус release evidence

Stage 0 завершен 2026-08-16. Release SHA находится в GitHub `main` и
production; state-only migration `storefront.0096` применена. Django gate
[`31967237986`](https://github.com/TwoComms-shop/TwoComms_Site/actions/runs/31967237986)
и MariaDB gate
[`31967237927`](https://github.com/TwoComms-shop/TwoComms_Site/actions/runs/31967237927)
завершились `success`. Server и HTTP post-deploy matrices вернули `status=ok`.

## Non-DTF inventory

Sanitized inventory command на baseline SHA дал:

| Объект | Count |
| --- | ---: |
| Django models | 305 |
| URL patterns | 1204 |
| HTML templates | 267 |
| Python files | 1493 |
| JavaScript files | 94 |
| Management commands | 138 |

Evidence fields: `dtf_scope=excluded`, `dtf_app_loaded=false`, без путей,
секретов и environment values. Генератор: `scripts/build_non_dtf_inventory.py`.
Отдельный command smoke подтверждает 138/138 import + parser; `handle()` не
вызывается.

## Full-suite A/B classification

Финальный одинаковый explicit non-DTF scope собрал 6080 тестов на каждой
версии Django. Machine-readable artifact:
`docs/qa/django61-full-ab-baseline.json` (schema v2).

| Matrix | Result |
| --- | --- |
| Django 5.2.11 baseline | 6080 tests, 71 failures, 30 errors, 10 skipped |
| Django 6.1 candidate | 6080 tests, 71 failures, 30 errors, 10 skipped |
| Typed outcome delta | 0 baseline-only и 0 Django 6.1-only occurrences |
| Triage coverage | 101/101 outcome occurrences в 31 deterministic clusters |
| MariaDB-only subset на Django 6.1 | 14/14 passed |
| MariaDB-only subset на Django 5.2.11 | 14/14 passed |
| MariaDB compatibility delta | 0 test-status IDs |

Граница DTF у двух artifacts различается и не скрывается. Полный 6080-test A/B
имеет `dtf_scope=excluded` и `dtf_migration_setup=not-loaded`. Исторические
14-test MariaDB logs не содержат DTF test identifiers, но их setup применял DTF
migration dependency; artifact явно хранит
`dtf_scope=test-identifiers-excluded` и
`dtf_migration_setup=included-in-historical-logs`. Поэтому строгий DTF-zero
setup для этого исторического MariaDB снимка не заявляется.

Старые числа `65 failures + 47 errors`, `67/47`, `66/47` и targeted subset
остаются только историческими снимками. Для `DJ6-TEST-002` используется schema
v2 artifact с source SHA, sanitized command/scope, log hashes и полными
нормализованными outcome occurrences.

Классификация Stage 0 считается завершенной, потому что:

- каждый failure/error occurrence входит ровно в один детерминированный
  module-prefix cluster;
- каждый cluster повторен на Django 5.2.11 и 6.1 в одинаковом code/fixture
  scope;
- 14 MariaDB-only IDs имеют A/B evidence: 14/14 на обеих версиях, delta 0;
- stable shards перечислены в CI и отделены от baseline test debt.

Поле `diagnosis` намеренно равно `null`, пока отдельная работа не докажет root
cause. Для compatibility release достаточно доказанного нулевого Django 6.1
delta; старый test debt не маскируется и не объявляется исправленным.

## Production MariaDB parity target

Текущий target inventory для локального snapshot:

| Объект | Count |
| --- | ---: |
| Base tables | 332 |
| InnoDB tables | 142 |
| MyISAM tables | 190 |
| Triggers | 25 |
| Routines | 0 |
| Events | 0 |

`--single-transaction --quick --skip-lock-tables` дает согласованный снимок
InnoDB, но не полную point-in-time согласованность MyISAM. Полную гарантию
можно заявлять только после maintenance lock или перевода MyISAM в InnoDB.

Локальный snapshot rehearsal завершен: 332 base tables, 142 InnoDB, 190
MyISAM, 25 triggers, 0 routines и 0 events. Hash сверки table+engine на
локальном и production snapshot совпал:
`3166bd1ad8ef8f55680731422ca257e7ee09b0b92064e5ba39d9f1baa316ba70`.
Артефакт находится вне Git с private mode; DTF database в snapshot отсутствует.

Acceptance для `FOUNDATION-DB-001`:

- dump получен только по approved SSH path и только для alias `default`;
- restore сделан в явно именованную local database с prefix `twc_snapshot_`;
- table/engine/trigger/routine/event counts сверены с этим inventory;
- DTF database отсутствует;
- dump, rollback и local env находятся вне Git и имеют private mode.

Это закрывает parity/rehearsal evidence для `FOUNDATION-DB-001`; после
интеграции в `main`, зеленых CI artifacts и release proof пункт отмечен
выполненным.

## Свежие локальные Stage 0 contracts

- Migration drift contract имеет оба ожидаемых исхода: synthetic model drift
  дает RED, а чистый non-DTF graph проходит GREEN.
- Static gate выполняет `collectstatic` и `compress --force`, рендерит
  `base.html`, проверяет hashed static URLs и manifest-backed `/static/CACHE/`
  assets.
- `storefront.0096` прошел MariaDB rehearsal; `sqlmigrate` показывает no-op для
  `body_html`, `h2` и `queries_json`.
- Финальный агрегированный gate прошел `86/86` tests за 17.576 сек.; отдельно
  прошли `check --database=default`, реальный migration drift check, exact
  runtime, warning gate без blocked warnings, `138/138` command parsers,
  sanitized inventory и production-like static gate.
- Оба tracked A/B artifacts проходят строгую schema v2 validation. Повторное
  сравнение сохраненного полного Django 6.1 log с tracked candidate подтвердило
  `6080/71/30/10` и пустые `fresh_only`/`tracked_candidate_only` delta.
- Read-only production preflight подтвердил baseline SHA
  `f57f8cfb47ffa726815081365499ce7ccee7ec2c`, чистые tracked-файлы, CPython
  3.14.6, Django 6.1, MariaDB 11.4.12 и отсутствие примененной
  `storefront.0096` до release.
- GitHub Django gate `31967237986` повторил fresh 6080-test Django 6.1 smoke за
  422.297 сек. и получил `6080/71/30/10`; comparison artifact имеет
  `status=matched`, `fresh_only=[]`, `tracked_candidate_only=[]`.
- GitHub MariaDB gate `31967237927` прошел lifecycle, checkout concurrency и
  follow/UGC concurrency suites на disposable MariaDB 11.4.12; каждый run
  подтвердил `check --database=default`, schema proof и cleanup.
- Production post-deploy matrix на SHA
  `df5a99d09b4135bdc7d70baba7956e89e3610ca9` подтвердил branch `main`, чистые
  tracked-файлы, совпадение `HEAD/origin/main`, exact runtime, MariaDB 11.4.12,
  `pending migrations=0`, database check и три `lswsgi` processes.
- Финальный read-only inventory production alias `default` подтвердил 332 base
  tables: 142 InnoDB, 190 MyISAM, 25 triggers, 0 routines и 0 events.
- HTTP post-deploy matrix проверил 10 non-DTF endpoints: storefront,
  management, finance и storage вернули ожидаемые `200/302`, общий
  `status=ok`.

## CI evidence artifacts

Release run `31967237986` сохранил artifact `django61-stage0-evidence`, а run
`31967237927` - `mariadb-gate-evidence`. General workflow сохраняет:

- `command-smoke.json` - 138 non-DTF command imports/parsers;
- `warning-gate.json` - blocked and allowlisted warning counts with owner/expiry;
- `static-gate.json` - temporary WhiteNoise/compressor manifest counts;
- `non-dtf-inventory.json` - counts and explicit DTF exclusion.
- `full-non-dtf-comparison.json` - fresh Django 6.1 smoke против tracked
  candidate; любая новая summary/outcome delta блокирует CI.
- `django61-targeted-ab-baseline.json` - MariaDB 11.4 A/B, 14/14 против 14/14.

Artifacts не должны содержать body, headers, cookies, env, DSN, passwords,
tokens, user names, raw exceptions или executable paths. CI retention сейчас
14 дней; для долговременного baseline в этот документ заносится только
sanitized summary и source SHA.

Обычный pull request и push в `main` выполняют fast Stage 0 checks, но не
повторяют 6080-test smoke. Fresh полный smoke и сравнение с tracked candidate
остаются явным release proof через manual `workflow_dispatch`. Push, меняющий только
implementation/report Markdown (`docs/operations/**`, `docs/plans/**`,
`docs/qa/*.md`, `dj6_update_all.md`), не запускает повторный полный suite.

## Closure evidence

| Gate | Evidence | Итог |
| --- | --- | --- |
| Runtime release verification | `df5a99d09b4135bdc7d70baba7956e89e3610ca9` | `HEAD == origin/main` на момент release proof |
| Django CI | Run `31967237986`, artifact `django61-stage0-evidence` | `success` |
| MariaDB CI | Run `31967237927`, artifact `mariadb-gate-evidence` | `success` |
| Migration | Production `storefront.0096` | `[X]`, pending non-DTF migrations `0` |
| Server matrix | exact SHA/runtime/default MariaDB/check/Passenger | `status=ok` |
| HTTP matrix | 10 non-DTF storefront/management/finance/storage probes | `status=ok` |
| DTF boundary | Full A/B setup excluded; historical MariaDB setup limitation recorded | production DTF не затронут; DTF test IDs не запускались |

Stage 0 checkboxes в implementation plan отмечены выполненными. Подготовительные
изменения Stage 1 в этом release не считаются завершенными без их отдельных
acceptance matrices.
