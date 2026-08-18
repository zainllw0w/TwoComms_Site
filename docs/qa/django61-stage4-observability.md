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
