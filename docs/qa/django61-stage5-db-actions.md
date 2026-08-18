# Django 6.1 Stage 5: database actions

Дата evidence: 2026-08-18
Scope: только non-DTF; production MariaDB, DTF alias и storefront/parser
incident-файлы не изменялись.

## Итог

| Пункт | Результат | Решение |
| --- | --- | --- |
| `DJ6-BASE-002` | Добавлен воспроизводимый static/live inventory relations, который собирает engine, фактический FK, `DELETE_RULE`, orphan count, delete receivers, soft-delete поля и rollback evidence. Static graph содержит 554 non-DTF FK/OneToOne relations. | Inventory-артефакт готов. Финальный live факт именно production-схемы должен запускаться отдельно read-only; до него rollout не разрешён. |
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
`NO-GO`; companion relation пришлось бы отдельно проектировать как
`DB_SET_NULL`, что выходит за этот безопасный experiment.

Soft-delete полей у `PageView` и `SiteSession` не обнаружено, `delete()` override
нет, обязательных delete receivers нет. Это не отменяет E050 и требования
проверить реальную схему.

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

Disposable experiment принимает только Unix socket или loopback host; remote
host, hostname production и отсутствие endpoint завершаются ошибкой. Пароль
если нужен, передаётся только через `TWC_DJ61_DISPOSABLE_DB_PASSWORD`, а не
через аргумент командной строки.

## Rollback contract

До любого будущего изменения требуется:

1. backup и сохранённый `SHOW CREATE TABLE` child table;
2. подтверждённые InnoDB engines, реальный FK и `orphan_count=0`;
3. companion `on_delete` actions без `models.E050` и отсутствие обязательных
   delete side effects;
4. обратимая `AlterField` (`DB_CASCADE` -> исходный Python action) и проверка
   фактического FK rule после reverse.

Ни один из этих шагов не выполнялся на production в рамках данного commit.
До свежего live inventory и отдельного approved migration design статус
production rollout остаётся **NO-GO**.
