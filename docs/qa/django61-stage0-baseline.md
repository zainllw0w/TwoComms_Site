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
| Baseline repository SHA | `f57f8cfb47ffa726815081365499ce7ccee7ec2c` |

Exact runtime должен подтверждаться `scripts/verify_project_runtime.py`, а не
версией, напечатанной bare `python` из PATH.

## Статус release evidence

Локальные Stage 0 contracts, полный A/B baseline и MariaDB rehearsal обновлены
и имеют свежий evidence. Перед release завершен read-only production preflight;
интеграция в GitHub `main`, фактический CI artifact и post-deploy proof будут
зафиксированы в секции release evidence после deployment. До этого основные
implementation-plan checkboxes остаются открытыми.

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

Это закрывает локальный parity/rehearsal evidence для `FOUNDATION-DB-001`;
чекбокс плана остается открытым до интеграции в `main`, CI artifact и release
proof.

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

## CI evidence artifacts

`.github/workflows/django61-gate.yml` должен сохранять sanitized artifacts:

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

## Current open gates

- `DJ6-CI-002`: локальный RED->GREEN drift contract готов; нужен GitHub `main`
  и CI artifact с этим доказательством.
- `DJ6-STATIC-001`: локальный render/hashed/CACHE contract готов; нужен CI
  artifact и release evidence на `main`.
- `DJ6-COMPAT-001`: named behavioral integration contracts готовы, включая
  schema/request/cache/OAuth evidence; нужен CI artifact на `main`.
- `FOUNDATION-DB-001`: локальный snapshot parity и hash сверка готовы; нужны
  интеграция в `main` и сохраненный CI/release proof.
- `DJ6-TEST-002`: полный non-DTF A/B и MariaDB A/B закрыты локально с delta 0;
  остается опубликовать machine-readable evidence в CI.
- `DJ6-MIG-002`: `storefront.0096` rehearsal прошел локально; нужен CI/main
  migration-drift proof перед отметкой плана.
- `DJ6-LIVE-001`: выполнить server preflight и post-deploy matrix с expected
  SHA.

Ни один checkbox Stage 0 не отмечается до commit/push в `main`; для
production-effect дополнительно нужны approved SSH deploy и post-deploy proof.
