# Django 6.1 Stage 2: отчёт о завершении

Дата: 2026-08-17. Область: non-DTF ORM, публичный API, корзина,
административная аналитика, Django admin и операционная пагинация.

## Результат

| ID | До | После | Parity / ограничение |
| --- | --- | --- | --- |
| `DJ6-ORM-001` | 11 запросов на 10 payment snapshots | 1 запрос | discount/payable payload совпадает |
| `DJ6-ORM-002` | 11 запросов на 10 reseller rows | 1 запрос | `Decimal('246.80')` |
| `DJ6-ORM-003` | 11 запросов на 10 company rows | 1 запрос | `Decimal('246.80')`, exception policy не менялась |
| `DJ6-ORM-004` | 21 запрос на 10 UserAdmin rows | 1 запрос | profile/points могут отсутствовать |
| `DJ6-ORM-005` | 12 запросов на 10 Category API rows | 2 запроса | published/draft/empty counts совпадают |
| `DJ6-ORM-006` | Product detail с 3 variants: 6 запросов | 3 запроса | Product list остаётся 2 запроса без variant prefetch |
| `DJ6-ORM-007` | До 25 отдельных product lookups | 1 bulk lookup | порядок, duplicate/null/deleted IDs сохранены |
| `DJ6-ORM-008` | 5 order `exists()` запросов | 1 correlated query | user/anonymous semantics, rate `40.0%` |
| `DJ6-ORM-009` | 1 запрос с полными Product models | 1 запрос только `id/price` | money rules не изменены |
| `DJ6-ORM-010` | 1 запрос с полными Variant models | 1 запрос только `id/product_id` | cart cleanup и Monobank reset сохранены |
| `DJ6-ORM-011` | 8 querysets: `totally_ordered=False` | 8 querysets: `True` | tie-boundary pages без пропусков/дублей |
| `DJ6-ORM-012` | Нет fail-fast contract для узких projections | 7 `FETCH_RAISE` contracts | production default остаётся `FETCH_ONE` |
| `DJ6-ADMIN-001` | Actions только в changelist, без permission contract | change list + change form, `change` permission | 10 admin rows читаются одним запросом |

## Fetch mode decision

- [x] Глобальный `FETCH_PEERS` не включён.
- [x] Глобальный `FETCH_RAISE` не включён.
- [x] Production queryset default подтверждён как `FETCH_ONE`.
- [x] Для фактических N+1 сначала применены explicit projection,
  `select_related`, filtered annotation, `Prefetch` и `in_bulk()`.
- [x] `FETCH_RAISE` используется только внутри test context manager и превращает
  будущую скрытую lazy fetch в `FieldFetchBlocked`.

Локальный smoke для `DJ6-ORM-001..003` показал: exact projection выполняет
один запрос, а `FETCH_PEERS` потребовал бы два. Поэтому новый режим не выдаётся
за универсальную оптимизацию.

## Admin permission review

Первый quality review обнаружил, что mutating restock actions были доступны
staff с одним `view_restocksubscription`. Исправление добавило
`permissions=['change']` для retry/close/reopen actions.

Повторный review потребовал отдельный forged changelist POST contract. Итоговые
тесты покрывают обе action locations, change-form и changelist POST, отсутствие
изменений `status`, `next_attempt_at`, `notification_attempts` и отсутствие
постановки доставки в очередь.

## Verification

- [x] Единый SQLite/no-network Stage 2 gate: `29/29`.
- [x] Disposable MariaDB gate: `11.4.12-MariaDB`, тот же acceptance-набор,
  реальный migration graph, статус `passed`.
- [x] MariaDB database check: `passed`, только 4 ранее allowlisted
  `DJ6-BASE-004` warnings.
- [x] Temporary MariaDB database/user cleanup: `verified`.
- [x] `check --database=default --settings=test_settings_no_network_non_dtf`:
  без ошибок.
- [x] `makemigrations --check --dry-run --noinput` через
  `test_settings_migrations_non_dtf`: `No changes detected`.
- [x] CPython `3.14.6`, Django `6.1`.
- [x] 24 Python-файла diff `ORM-004..012`/`ADMIN-001` скомпилированы;
  вместе с ранее выпущенными `ORM-001..003` Stage 2 охватывает 28 уникальных
  Python-файлов.
- [x] `git diff --check origin/main...HEAD`: clean.
- [x] Изменённых DTF paths: `0`.
- [x] Production fetch-mode overrides: `0`.

Во время SQLite tests остаётся только известный warning об отсутствующем
worktree-каталоге `staticfiles/`; он не относится к runtime-коду Stage 2.

## MariaDB evidence

- Category query использует `idx_category_active_order`; product relation
  читается по FK index.
- Product detail имеет `const` lookups; variant prefetch использует
  `ref + eq_ref`.
- UserAdmin reverse OneToOne joins используют `eq_ref`.
- Restock admin product relation использует `eq_ref`.
- Reseller consignment old/new projection использует `type=ref`,
  `idx_cons_item_res_cons`, estimate `10`, `Using where`.
- Company consignment old/new projection использует `type=ref`, company FK
  index, estimate `11`, `Using where`.
- Survey outer scan оценивается в 8 rows; correlated order lookup использует
  `orders_order_user_id_e9b59eb1` (`ref`, estimate 7), а `created` остаётся
  residual predicate.
- Для paginator tie-breakers ухудшения plans не найдено.
- Новый индекс или другой Stage 2 DDL не требуется.

## Release state

Code release SHA: `505458e919064205113aeb9b88e2e471ac2488ef`.
Он опубликован в GitHub `main` и получен production checkout через
разрешённый `git pull --ff-only origin main`.

Production release evidence:

- server checkout: branch `main`, tracked clean, SHA и `origin/main` совпадают
  с `505458e919064205113aeb9b88e2e471ac2488ef`;
- runtime: CPython `3.14.6`, Django `6.1`, Django REST Framework `3.18.0`,
  mysqlclient `2.2.8`, MariaDB `11.4.12`; pending non-DTF migrations: `0`;
- server database check: `passed`; известны только четыре ранее allowlisted
  MariaDB capability warnings `DJ6-BASE-004`; новых Stage 2 warnings нет;
- local HTTP matrix и server post-deploy matrix: все 10 non-DTF probes
  прошли (storefront, management, finance, storage; ожидаемые login
  redirects имеют `302`); DTF scope `excluded`;
- до restart были зафиксированы шесть старых `lswsgi` PID, после `touch
  tmp/restart.txt` и HTTP-запросов Passenger работает на новых PID;
- `run_instagram_bot --ensure` завершён успешно, daemon `run_instagram_bot
  --forever` работает;
- migrations, `collectstatic` и `compress` не запускались: code diff не
  содержит migrations, static, templates или assets.

Таким образом, Stage 2 code и live proof закрыты; этот файл входит в отдельный
документационный commit после code release.
