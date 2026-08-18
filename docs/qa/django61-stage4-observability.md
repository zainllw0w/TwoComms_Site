# Django 6.1 Stage 4: единый baseline observability

Команда `measure_stage4_baseline` формирует один JSON snapshot для
`DJ6-SRV-002`, `DJ6-SRV-007`, `DJ6-SRV-008`, `DJ6-SRV-009`,
`DJ6-CACHE-001` и `DJ6-AUTH-001`. DTF не входит в scope.

Команда не меняет MariaDB и не выполняет `SET GLOBAL`: два последовательных
`SHOW GLOBAL STATUS` дают baseline/delta для temporary tables и aborted
connections. File-cache IO, `cache.add` и cache-key cold/warm проверяются
только в удаляемых временных каталогах. Configured cache не изменяется.
Пароли пользователей не читаются: PBKDF2 проверяется на синтетическом
значении с текущими 1 500 000 iterations.

Один production snapshot после deploy:

```bash
TWC_RELEASE_SHA="$(git rev-parse HEAD)" python manage.py \
  measure_stage4_baseline --samples 9 > /tmp/django61-stage4.json
```

Acceptance: exit `0`; `schema=twocomms.django61.stage4.v1`; MariaDB
`available=true`; `concurrent_add.distributed_lock_safe=false` независимо от
наблюдаемого числа winners; `old_key_reads=0`; PBKDF2 iterations `1500000`,
verify `true`, current rehash `false`, legacy rehash `true`; FD utilization
ниже 70%. Snapshot фиксирует фактические p50/p95, inventory, TTL, temp-table
и aborted-connection delta. Рост оценивается повторным snapshot под
контролируемой нагрузкой без изменения global variables.

## Evidence matrix (2026-08-18)

Снимок был сформирован на runtime `CPython 3.14.6 / Django 6.1` командой
ниже; `TWC_RELEASE_SHA` намеренно берётся из `git rev-parse`, а не вводится
вручную. В acceptance-артефакте зафиксирован release SHA `5f9af836f`;
перед повторным использованием его нужно сверить с фактическим deployed
`HEAD`.

```sh
TWC_PYTHON="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.venv/bin/python"
cd twocomms
TWC_RELEASE_SHA="$(git rev-parse HEAD)" "$TWC_PYTHON" manage.py \
  measure_stage4_baseline --samples 9 > /tmp/django61-stage4.json
```

| Пункт | Машинно проверяемое поле | Допустимый вывод |
| --- | --- | --- |
| `DJ6-SRV-002` | `cache.io`, `cache.inventory`, `cache.configured_ttl_seconds`, `cache.concurrent_add.distributed_lock_safe` | Bounded file-cache IO/inventory; `cache.add` не считается durable distributed lock. |
| `DJ6-SRV-007` | `database.temporary_tables.baseline/delta` | Дельта `Created_tmp_tables`/`Created_tmp_disk_tables` за окно probe; `SET GLOBAL` не выполняется. Это не attribution к отдельным query shapes. |
| `DJ6-SRV-008` | `database.aborted_connections.baseline/delta` | Дельта `Aborted_connects`/`Aborted_clients` за окно probe; нулевая дельта не доказывает причинную привязку к отдельному lifecycle. |
| `DJ6-SRV-009` | `file_descriptors.open`, `soft_limit`, `soft_utilization_pct` | Snapshot FD budget (acceptance `5/1024`, `0.488%`); это моментальный baseline, **не peak-concurrency measurement**. |
| `DJ6-CACHE-001` | `cache_keys.cold_hit`, `warm_hit_after`, `old_key_reads` | Изолированный cold -> warm contract и отсутствие legacy-key reads; production hit-rate не заявляется. |
| `DJ6-AUTH-001` | `password_hasher.iterations`, timings, `verify_ok`, `*_needs_rehash` | Синтетический PBKDF2 contract; aggregate user rehash rate и auth-peak CPU не измеряются. |

Focused local contract: `storefront.tests.test_django61_stage4_observability`
(`3/3`, CPython 3.14.6/Django 6.1). DTF, production cache flush, `SET GLOBAL`,
DDL и изменение пользовательских паролей в evidence не входят.
