# Django 6.1 Stage 5: connection budget и charset gate

Дата фиксации baseline: 2026-08-18. Scope: non-DTF Django runtime и
production MariaDB read-only checks. Этот документ фиксирует evidence для
`DJ6-SRV-004` и `DJ6-SRV-006`; он не отмечает пункты implementation plan
выполненными.

## Подтвержденный read-only baseline

| Область | Факт |
| --- | --- |
| MariaDB | `11.4.12` |
| Global connection ceiling | `max_connections=150` |
| Per-user connection ceiling | `max_user_connections=20` |
| Idle timeout | `wait_timeout=60` секунд |
| Django connection lifetime | эффективный `CONN_MAX_AGE=0` |
| Django health check | `CONN_HEALTH_CHECKS=True` |
| Client/session encoding | `utf8mb4` |
| Schema и table encoding | `utf8mb4` |
| Session storage engine default | `default_storage_engine=INNODB` |
| Global server encoding | `latin1`; значение только наблюдается и не изменяется |

Значения connection budget читаются через `SHOW VARIABLES`/`SHOW STATUS` и
не выводятся из локального SQLite. Charset проверяется отдельно на уровне
schema/table и текущей DB session; совпадение только одного из этих уровней
не считается доказательством.

## DJ6-SRV-004: connection budget

Gate считается пройденным только при одновременном выполнении всех условий:

1. Для каждого non-DTF MySQL/MariaDB alias эффективные настройки Django
   содержат `CONN_MAX_AGE=0` и `CONN_HEALTH_CHECKS=True`. Значение
   `DB_CONN_MAX_AGE` не должно незаметно переопределять lifetime на ненулевой.
2. Read-only snapshot production показывает ровно `150/20/60` для
   `max_connections`, `max_user_connections` и `wait_timeout`.
3. Любые новые worker, daemon или connection pool проходят отдельный
   bounded capacity test до production rollout. Один локальный green test или
   наличие свободных слотов в момент снимка такой тест не заменяет.
4. Snapshot и capacity evidence содержат effective limits, peak usage и
   ошибки подключения; неуспешный или неполный probe не публикуется как
   acceptance.

### Fail-closed условия

Проверка останавливается и остается незакрытой, если отсутствует хотя бы
одно значение baseline, любое значение отличается от `150/20/60`, effective
`CONN_MAX_AGE` не равен нулю, не доказана граница нового pool/worker либо
probe вернул ошибку/неполный результат. Нельзя объявлять пункт безопасным по
одному `Threads_connected` без проверки hard limits и effective Django config.

## DJ6-SRV-006: защита от global `latin1`

Gate считается пройденным только при одновременном выполнении всех условий:

1. Конфигурация DB client явно задает `charset=utf8mb4`; это проверяется по
   effective Django settings, а не только по исходнику.
2. Read-only session probe подтверждает `utf8mb4` для текущих connection
   charset values; schema и проверенный table inventory также имеют
   `utf8mb4` defaults/collations.
3. Effective session default для новых Django-created tables равен
   `default_storage_engine=INNODB`.
4. Наблюдаемый global server default `latin1` сохраняется. Для этой задачи
   он является host-level compatibility fact, а не целью исправления.

### Fail-closed условия

Проверка останавливается, если client/session/schema/table encoding не
подтвержден как `utf8mb4`, session engine default неизвестен, global value
нельзя прочитать или предлагается изменить global `latin1`. Нельзя считать
явный client charset доказательством корректности уже существующих таблиц.

## Запрещенные действия в рамках gate

Все проверки этого документа read-only. Запрещены production DDL,
migrations и любые data mutations, включая `CREATE`, `ALTER`, `DROP`,
`TRUNCATE`, `INSERT`, `UPDATE`, `DELETE`, запуск `migrate`/`makemigrations`,
а также `SET GLOBAL`/`SET PERSIST` и изменение server defaults. Не создаются
заказы, платежи или иные тестовые записи. Разрешены только `SHOW`/`SELECT`,
`information_schema` inventory и чтение effective application settings.

Любой будущий InnoDB conversion или charset migration требует отдельного
change с backup, rehearsal, rollback и host-owner review; он не является
частью этого acceptance документа.
