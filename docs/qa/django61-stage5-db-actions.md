# Django 6.1 Stage 5: database actions

Дата evidence: 2026-08-18
Scope: только non-DTF; production MariaDB, DTF alias и storefront/parser
incident-файлы не изменялись.

## Итог

| Пункт | Результат | Решение |
| --- | --- | --- |
| `DJ6-BASE-002` | Production read-only inventory проверил engine, фактический FK, `DELETE_RULE`, orphan count, delete receivers, soft-delete поля и rollback evidence для 554 non-DTF FK/OneToOne relations. | Инвентаризация закрыта; retention-кандидат получил `NO-GO`. Production `DB_CASCADE` и любое DDL по-прежнему запрещены. |
| `DJ6-DB-001` | Disposable MariaDB benchmark и rollback rehearsal пройдены. | Эксперимент доказан; изменение project models не выполнялось. |

Команда не меняет модели, миграции, таблицы или данные. `DB_CASCADE` не считается
внедрённым только потому, что synthetic experiment зелёный.

## Static inventory

Инструмент: `scripts/audit_django61_db_actions.py`.

- Все concrete `ForeignKey`/`OneToOneField` non-DTF relations собираются через
  Django app registry; relation, у которой child или parent имеет app label
  `dtf` либо table prefix `dtf_`, отбрасывается fail-closed.
- Для каждого relation фиксируются исходный `on_delete`, `db_constraint`,
  engine/FK placeholders, soft-delete поля обеих моделей, `delete()` override,
  `pre_delete`/`post_delete` receivers, orphan count и hash `SHOW CREATE TABLE`.
  В каждой строке также есть `companion_action_design`: read-only план
  перехода sibling-полей на `DB_CASCADE`/`DB_SET_NULL`/`DB_SET_DEFAULT`,
  проверка `null`/default prerequisites, явные `models.E050` blockers и
  обратимый порядок `AlterField` с восстановлением захваченных FK.
- Два wildcard receiver-а проекта не считаются обязательными для аналитических
  моделей, потому что их собственные guarded maps не содержат `PageView`:
  `storefront.signals.cancel_deleted_image_optimization` и
  `warehouse.signals.warehouse_delete_print_images`. Любой новый receiver
  автоматически становится blocker до явного review.

### Retention candidate

Кандидат: `storefront.PageView.session` (`storefront_pageview.session_id` ->
`storefront_sitesession.id`, source `on_delete=CASCADE`). У `PageView` есть
соседний relation `user:SET_NULL`. Django 6.1 запрещает смешивать
database-level и Python-level actions в одной модели (`models.E050`). Поэтому
перевод только `session` на `DB_CASCADE` сейчас получает однозначный
`NO-GO`. Inventory теперь фиксирует companion design: `user` должен стать
`DB_SET_NULL` (поле nullable), затем `session` — `DB_CASCADE`; rollback идёт в
обратном порядке по захваченным FK/`SHOW CREATE TABLE`. Этот design только
показывает, как устранить E050, и не является одобрением миграции.

Для sibling с `PROTECT`, `RESTRICT`, `DO_NOTHING` или неизвестным действием
design остаётся `blocked`, потому что в Django 6.1 нет соответствующего
database-level action для автоматического сохранения Python semantics.
Ненулевое поле для `DB_SET_NULL` и поле без default для `DB_SET_DEFAULT` также
fail-closed блокируют план. Ни одна из этих проверок не выполняет DDL или не
меняет данные.

Soft-delete полей у `PageView` и `SiteSession` не обнаружено, `delete()` override
нет, обязательных delete receivers нет. Это не отменяет E050 и требования
проверить реальную схему.

## Production read-only inventory

Evidence снят 2026-08-18 через CloudLinux-bound Python на production SHA
`f8c0656d03710d53679b02d48b59f344056fd7cc`. Runtime: CPython `3.14.6`,
Django `6.1`, MariaDB `11.4.12-MariaDB-cll-lve`; default storage engine
`InnoDB`, SQL mode содержит `STRICT_TRANS_TABLES` и `NO_ENGINE_SUBSTITUTION`.
Использовался только alias `default`; DTF relations в отчёте: `0`.

Команда выполнила только `SELECT` по `information_schema`, orphan-count и
`SHOW CREATE TABLE`. На production не выполнялись `CREATE`, `DROP`, `ALTER`,
`DELETE`, migration либо запись report-файла.

| Факт | Значение |
| --- | ---: |
| Проверено non-DTF relations | `554` |
| Relations без engine facts | `0` |
| Relations без orphan scan | `0` |
| Relations без `SHOW CREATE` hash | `0` |
| Реальные FK с `DELETE_RULE=RESTRICT` | `39` |
| Relations без реального FK/delete rule | `515` |
| Engine pair `MyISAM -> MyISAM` | `249` |
| Engine pair `MyISAM -> InnoDB` | `23` |
| Engine pair `InnoDB -> MyISAM` | `91` |
| Engine pair `InnoDB -> InnoDB` | `191` |
| Orphans во всём relation graph | `1` |

Единственный orphan найден у retention-кандидата
`storefront.PageView.session`. Его live schema facts:

- child `storefront_pageview`: `MyISAM`;
- parent `storefront_sitesession`: `InnoDB`;
- реальный FK и `DELETE_RULE`: отсутствуют;
- `orphan_count=1`;
- `SHOW CREATE TABLE` SHA-256:
  `7d653eba52f34641ac18960ec0e00e35348713918a36ec9344e77e098d764adb`;
- обязательных delete signals, soft-delete contract и `delete()` override нет;
- соседний `user:SET_NULL` требует отдельного `DB_SET_NULL` design из-за
  `models.E050`.

Итог retention decision: **NO-GO**. Блокеры:
`child_engine_not_innodb`, `real_fk_missing`, `orphan_rows_present`,
`mixed_on_delete_models.E050`, `rollback_evidence_missing`. Инвентаризация
закрывает `DJ6-BASE-002`, но не разрешает исправлять orphan, менять engine,
создавать FK или внедрять database-level action без отдельного rollout.

## Disposable MariaDB evidence

Запускался только локальный временный MariaDB datadir/socket. Production
endpoint `195.191.25.63`, его credentials и DTF DB не использовались.

Параметры:

- MariaDB `11.4.12-MariaDB`;
- сгенерированная база с prefix `twc_dj61_db_actions_`, удалена и проверена
  после завершения;
- `2000` parent retention sessions, `10` child events на каждую, batch `100`;
- Python graph: FK `ON DELETE RESTRICT`, перед удалением child очищается явно;
- database graph: FK `ON DELETE CASCADE`, удаляется только parent.

Результаты одного запуска:

| Проверка | Значение |
| --- | ---: |
| Python-side batch delete | `0.070519 s` |
| DB cascade batch delete | `0.068915 s` |
| Отношение времени Python/DB | `1.023x` |
| Orphans до удаления (оба графа) | `0 / 0` |
| Остаток parent+child после удаления | `0 / 0` |
| Реальный FK rule Python graph | `RESTRICT` |
| Реальный FK rule DB graph | `CASCADE` |
| `django.db.models.DB_CASCADE.operation` | `CASCADE` |
| Transactional delete до rollback | `(0, 0)` |
| Counts после rollback | `(1, 1)` |
| DDL reverse FK rule | `RESTRICT` |
| Cleanup generated database | подтверждён |

Эксперимент подтверждает два независимых свойства: MariaDB действительно
удаляет child без Python collector, а InnoDB transaction rollback возвращает
каскадно удалённые строки. Он также проверяет обратный DDL-путь на synthetic
FK. Delete signals для database cascade не исполняются; проектный signal
contract отдельно проверяется static inventory.

## Использование

Локальный static report (без подключения к БД):

```bash
TWC_PYTHON="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.venv/bin/python"
DEBUG=1 SECRET_KEY=... DJANGO_SETTINGS_MODULE=twocomms.settings \
  PYTHONPATH=twocomms "$TWC_PYTHON" \
  scripts/audit_django61_db_actions.py inventory \
  --output /tmp/django61-db-actions-inventory.json
```

Live read-only inventory разрешён только с явно настроенным non-DTF MariaDB
alias и после отдельной координации:

```bash
... scripts/audit_django61_db_actions.py inventory --live --database-alias default
```

Disposable experiment намеренно не доступен через CLI. Его запускает только
gate-owned programmatic harness с переданной фабрикой соединений к временной
локальной MariaDB и двумя обязательными interlock-ами: точным
`DJ6-DISPOSABLE-MARIADB-LOCAL-ONLY-v1` и identity proof с окружением
`disposable`, ролью `temporary`, именованным временным socket/loopback endpoint
и пользователем с prefix `twc_dj61_disposable_`. Перед первым `CREATE DATABASE`
скрипт сверяет фактические `VERSION()`, `@@hostname`, `@@port` и
`CURRENT_USER()` с этим proof. Операторские `host`/`socket`/`user`/password
параметры скрипт не принимает; CLI инструмента предоставляет только
`inventory`.

## Rollback contract

До любого будущего изменения требуется:

1. backup и сохранённый `SHOW CREATE TABLE` child table;
2. подтверждённые InnoDB engines, реальный FK и `orphan_count=0`;
3. companion `on_delete` actions без `models.E050` и отсутствие обязательных
   delete side effects;
4. обратимая `AlterField` (`DB_CASCADE` -> исходный Python action) и проверка
   фактического FK rule после reverse.

Ни один из этих шагов не выполнялся на production в рамках данного commit.
Свежий live inventory доказал существующие блокеры; до их устранения и
отдельного approved migration design production rollout остаётся **NO-GO**.
