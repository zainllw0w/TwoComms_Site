# Django 6.1: единый backlog аудита и улучшений TwoComms

> Статус документа: живой inventory. Stage 0 завершен; остальные находки не
> считаются внедренными без checkbox и отдельного release evidence.
> Каждая новая находка добавляется отдельной записью с доказательством и следующим шагом проверки.

## Цель и границы

Цель - пройти весь сайт и серверный runtime после перехода на Django 6.1 и собрать полный, пригодный для следующего агента список:

- возможностей Django 6.1 и совместимых библиотек, которые можно безопасно применить;
- ошибок, предупреждений, deprecated API, скрытых несовместимостей и технического долга;
- мест, где можно уменьшить задержки, запросы, память, фоновые работы и операционную нагрузку;
- возможностей распараллеливания и фонового выполнения с учетом реальных ограничений хостинга;
- серверных улучшений, которые зависят от прав, Passenger, cron, Redis, MariaDB или cPanel.

DTF-субдомен и его код, страницы, задачи, миграции, статика, серверные процессы и база данных полностью исключены из этого аудита. Не добавлять DTF-находки даже как «небольшие» улучшения.

## Подтвержденный baseline

- Исторический baseline старта аудита: `37ced3a4553d4068c6cb1ad93f38e641e3ba41a0`.
  Проверенная цель интеграции Stage 5: `origin/main` `55f7082ae`;
  release-кандидат перебазирован на эту цель и содержит code commits через
  `54f36a1b7`; provenance history начинается с `2d55c5089` и дополнена этим
  release-документом. Safety gate disposable helpers закрыт этими commits;
  перед push/deploy выполняется один свежий scoped verification.
- Runtime: Python 3.14.6, Django 6.1, Django REST Framework 3.18.0.
- DB runtime: локальный `mysqlclient`/`MySQLdb` 2.2.8; production read-only probe подтвердил MariaDB `11.4.12-MariaDB`. В production non-DTF schema насчитывается 305 model tables: 127 InnoDB и 178 MyISAM. Runtime и базы исключенного субдомена в этом аудите не проверяются.
- После перехода выполнены lock verification, `pip check`, `manage.py check`, `migrate --check`, `collectstatic`, `compress` и Passenger reload marker.
- Live smoke после перехода: public `/healthz/`, `/`, `/cart/` и management `/bot/health/` вернули HTTP 200.
- Полный репозиторный suite не считать доказательством зеленого состояния: ранее обнаружены несвязанные baseline-сбои окружения/кастомного print. Их не исправлять в рамках этого inventory; DTF исключен.
- Исходные production baseline figures в inventory получены 2026-08-16 через утвержденный read-only SSH-путь с caller-provided credential; пароль и его значение в документ не записываются. Тот probe не выполнял миграций, записей, очистки кэша, внешних provider-вызовов или DTF-действий. Отдельное Stage 2 post-deploy evidence от 2026-08-17 приведено выше; такие проверки нужно повторять перед будущими release.

## Статус реализации Stage 0 на 2026-08-16

- Полный explicit non-DTF A/B выполнен один раз на одинаковом source SHA:
  Django 5.2.11 и Django 6.1 дали одинаковые `6080` тестов, `71 failures`,
  `30 errors`, `10 skipped`; typed delta равен `0`.
- Machine-readable schema v2 artifact хранит source SHA, sanitized scope и
  command, hashes обоих логов, все `101` outcome occurrence и `31`
  детерминированный triage cluster. Непроверенные причины помечены
  `diagnosis: null`, поэтому старый test debt не выдается за регрессию Django.
- CI валидирует tracked artifacts и сравнивает fresh Django 6.1 full smoke с
  сохраненной candidate-стороной; новое падение или исчезнувший baseline
  outcome не может пройти только из-за `continue-on-error` у самого smoke.
- Отдельный schema v2 MariaDB A/B artifact фиксирует 14/14 против 14/14 на
  MariaDB 11.4 с delta `0`.
- Локальный Stage 0 release gate прошел `86/86` focused tests, exact runtime,
  no-network system check, реальный migration drift check, warning gate и
  исторический `138/138` management-command baseline. После добавления двух
  новых non-DTF команд текущий exact-count smoke обновлен до `140/140`;
  static/compressor/WhiteNoise pipeline и sanitized inventory также проходят.
- Локальный MariaDB snapshot default alias совпал с production table+engine
  hash. Исторический MariaDB A/B дал `14/14` на обеих версиях и delta `0`; DTF
  test identifiers отсутствуют, но setup этих старых logs применял DTF
  migration dependency. Строгий DTF-zero setup для исторического MariaDB
  artifact не заявляется. Полный 6080-test A/B DTF не загружал.
- Stage 0 закрыт release SHA
  `df5a99d09b4135bdc7d70baba7956e89e3610ca9`: GitHub Django run
  `31967237986` и MariaDB run `31967237927` завершились `success`, migration
  `storefront.0096` применена, server и HTTP post-deploy matrices вернули
  `status=ok`.
- Обычные pull requests и push в `main` выполняют fast required gates без
  6080-test smoke. Fresh полный smoke остается явным release proof через
  manual `workflow_dispatch`; Markdown-only push с
  implementation/report docs не запускает его повторно.
- Stage 1 закрыт: explicit SHA-1, named `MAILERS`, URLField contracts,
  signed-cookie policy, strict Base64 boundaries, social-auth compatibility,
  active legacy loader и Python 3.15 import contract прошли единый gate
  `61/61`; итоговый отчёт находится в
  `docs/qa/django61-stage1-completion-report.md`.
- Stage 2 закрыт code и live proof: release SHA
  `505458e919064205113aeb9b88e2e471ac2488ef` опубликован в GitHub `main` и
  получен production через разрешённый `git pull --ff-only`; SQLite и
  disposable MariaDB 11.4 gates прошли `29/29`, production runtime
  CPython 3.14.6/Django 6.1/MariaDB 11.4.12 подтверждён, 10 non-DTF HTTP
  probes зелёные, Passenger перезапущен через `tmp/restart.txt`, DTF scope
  остаётся `excluded`. Полный отчёт: `docs/qa/django61-stage2-completion-report.md`.

## Статус проверки Stage 5 на 2026-08-19

Stage 5 пока не означает применение новых DDL-решений в production. В этом
срезе завершены безопасные non-DTF audits и disposable experiments, а опасные
кандидаты получили явное решение `NO-GO` до снятия перечисленных блокеров.
Production schema, модели и historical migrations не менялись; DTF не
открывался и не затрагивался.

В implementation plan отмечены `[x]` только bounded evidence/rehearsal пункты
`DJ6-SRV-004`, `DJ6-SRV-006`, `DJ6-DB-001` и `DJ6-ORM-013`. Эти отметки
фиксируют завершение безопасных проверок, а не production adoption: все DDL,
migration и Stage 5 exit-gate остаются открытыми.

### Выполненные audits и experiments

- `DJ6-SRV-004` и `DJ6-SRV-006`: read-only production baseline подтвердил
  MariaDB `11.4.12`, `max_connections=150`, `max_user_connections=20`,
  `wait_timeout=60`, эффективные `CONN_MAX_AGE=0` и
  `CONN_HEALTH_CHECKS=True`. Django client/session, schema и проверенные tables
  используют `utf8mb4`; session default равен `INNODB`. Глобальный server
  default остаётся `latin1` и намеренно не менялся. Полный fail-closed контракт:
  `docs/qa/django61-stage5-connection-budget.md`.
- `DJ6-SRV-003`: sanitized per-table matrix, ranking tooling и disposable
  MariaDB 11.4.12 rehearsal зафиксированы. Canary runner теперь требует
  проверенный backup SHA/размер, полные index/FULLTEXT, zero-writer и
  zero-orphan audits, измеренные conversion/rollback timings и write-loss-safe
  rollback proof **до открытия MariaDB-соединения или выполнения любого SQL**.
  Production targets остаются на HOLD: production `ALTER TABLE` не выполнялся.
  Подробности: `docs/qa/django61-stage5-innodb-roadmap.md` и
  `docs/qa/django61-stage5-srv003.md`.
- `DJ6-ORM-013`: на disposable MariaDB `11.4.12` доказана работоспособность
  persisted `GeneratedField`: canonical parity `29/29`, корректные
  INSERT/UPDATE/refresh/deferred fetch и индексные range/order plans на `4126`
  строках. Temporary schema, user и datadir удалены; production модель и schema
  не менялись. Evidence: `docs/qa/django61-stage5-generated-field.md`.
- `DJ6-BASE-002` и `DJ6-DB-001`: static inventory охватил `554` non-DTF
  `ForeignKey`/`OneToOneField` relations. Synthetic MariaDB benchmark использовал
  `2000` parents и по `10` children: Python delete занял `0.070519 s`,
  database cascade — `0.068915 s`; orphan/remaining counts равны нулю, rollback
  восстановил counts `(1, 1)`, обратный DDL вернул `RESTRICT`. Evidence:
  `docs/qa/django61-stage5-db-actions.md`.
- `DJ6-MIG-001`: safety gate закрыт полным disposable MariaDB lifecycle для
  non-DTF graph: MariaDB `11.4.12`, graph `442/17`, clean install и restore
  прошли с `pending=0`, `321` schema objects и одинаковыми schema/history
  hashes. `migrate --check`, `makemigrations --check`, logical dump с SHA-256,
  restore/replay и fail-closed cleanup прошли; DTF scope исключён. Evidence:
  `docs/qa/django61-stage5-mig001-mariadb-lifecycle.json` и
  `docs/qa/django61-stage5-migration-squash.md`. Фактический squash, создание
  `replaces` и удаление historical migrations не выполнялись; decision остаётся
  `NO-GO` до свежей production identity-set сверки и утверждённых ranges.

### Stage 5 safety hardening release candidate (2026-08-19)

Интеграционные коммиты `b7f84b964`, `d1e834b3f` и `67859d912` добавляют
fail-closed gates
для pre-DDL InnoDB canary и migration-squash readiness. Свежий focused gate
под CPython `3.14.6`/Django `6.1` прошёл `26/26` тестов; `git diff --check`
чистый. Эти коммиты не выполняют production DDL, `migrate`,
`squashmigrations`, удаление historical migrations или любые изменения DTF.
Inventory теперь требует завершённый domain review и блокирует таблицы с
существующим managed-engine migration contract; `PromoCodeGroup` исключён из
canary, потому что его таблица уже управляется migration `0087` и активно
используется транзакционным `select_for_update()` кодом.
Чекбокс `DJ6-MIG-001` закрыт полным disposable MariaDB lifecycle. Чекбокс
`DJ6-SRV-003` и первые два Stage 5 exit gates остаются открытыми до approved
production canary с backup, writer/orphan/domain proof, timing и rollback.

### Решения NO-GO для production adoption

- `GeneratedField` для итоговой цены сейчас не внедрять. Старая catalog
  аннотация с `CAST` округляет иначе, чем canonical truncation и проверенный
  GeneratedField. Доказаны четыре расхождения: `1/1` даёт `1` вместо `0`,
  `1/33` — `1` вместо `0`, `1091/33` — `731` вместо `730`,
  `2147483647/1` (max-int/1) — `2126008811` вместо `2126008810`. Сначала нужно
  унифицировать формулу во всех consumers и повторить matrix/`EXPLAIN`.
- `DB_CASCADE` не внедрять в project models только по результату synthetic
  benchmark. Первый retention candidate `storefront.PageView.session` имеет
  соседний `user:SET_NULL`; смешивание database-level и Python-level actions в
  одной модели блокируется Django check `models.E050`.
- Migration squash и удаление historical migrations запрещены. MariaDB
  rehearsal доказал воспроизводимость текущего graph, но production snapshot
  устарел относительно graph `442/17`; до свежей identity-set сверки и
  утверждённых ranges нельзя создавать `replaces` или удалять историю.
- MyISAM -> InnoDB conversion не начинать по planning artifact. Ни одна таблица
  не получила production acceptance, а backup-only rollback не считается
  безопасным при продолжающихся записях.

### Остающиеся блокеры Stage 5

- `DJ6-SRV-003`: снять свежий sanitized production per-table
  `information_schema` inventory с engines, sizes, rows, indexes, triggers, FK,
  orphan и writer dependencies; затем выполнить approved backup/restore
  rehearsal и один low-risk canary с проверенным rollback. Production inventory
  и canary на 2026-08-18 **не завершены**.
- `DJ6-BASE-002`/`DJ6-DB-001`: нужен отдельный read-only live inventory
  фактических engines/FK/`DELETE_RULE`/orphans и approved design, который
  устраняет `models.E050`, учитывает delete signals и имеет обратимую migration.
- `DJ6-ORM-013`: заменить catalog `CAST` на единую MariaDB-safe integer
  semantics, проверить все price consumers и значения `discount_percent > 100`,
  затем повторить disposable parity/index gate и подготовить отдельный
  lock/rollback план DDL.
- `DJ6-MIG-001`: safety rehearsal закрыт, но остаются два blocker-а для
  фактического squash: `fresh_authoritative_identity_set_review_missing` и
  `approved_squash_ranges_missing`. До их снятия `squashmigrations` не
  запускать и historical files не удалять.
- `DJ6-SRV-004`: текущий connection budget подтверждён, но любой новый
  worker/daemon/pool требует отдельного bounded capacity test с peak usage и
  connection errors; наличие свободных соединений в одном snapshot не является
  разрешением на расширение concurrency.

## Правила записи находок

Каждая запись должна содержать:

1. Уникальный ID вида `DJ6-<AREA>-NNN`.
2. Статус: `кандидат`, `подтверждено`, `заблокировано правами`, `отложено`, `неактуально`.
3. Приоритет только предварительный: `P0`, `P1`, `P2`, `P3`; финальная приоритизация будет отдельным этапом.
4. Точную область: приложение, субдомен, серверный компонент и файл/символ/маршрут.
5. Доказательство: ссылка на файл и строки, команда/вывод, production-факт или ссылка на официальную документацию.
6. Что дает изменение: измеримый эффект для корректности, скорости, надежности, стоимости или поддержки.
7. Риск и ограничения: миграции, MariaDB, права хостинга, Passenger, Redis, cron, Celery, обратная совместимость и rollback.
8. Следующую проверку: тест, benchmark, read-only production probe или отдельный implementation task.

Гипотезы не выдавать за ошибки. Если runtime или права не позволяют проверить пункт, фиксировать блокер явно, а не делать вывод «работает».

## Сводка областей

| Область | Агент/источник | Статус |
| --- | --- | --- |
| Django 5.2 -> 6.0 -> 6.1 release notes и API | primary + Context7 | проверено локально |
| ORM, модели, `fetch_mode`, deferred fields, `on_delete`, QuerySet | primary + delegated ORM audit | проверено локально; DB-level часть отложена |
| Async, Celery, cron, Redis, фоновые задачи и параллелизация | delegated async/server audit + Stage 6 activation | Redis/Celery/daemon NO-GO; MariaDB durable cron active только для allowlisted no-send scope |
| HTTP, middleware, templates, forms, admin, DRF, security | primary repository sweep | проверено локально; browser/live gaps отмечены |
| Приложения и субдомены, кроме DTF | primary repository sweep | проверено локально |
| Production MariaDB, Passenger, права, observability | server audit + Stage 0 release | read-only inventory проверен; `storefront.0096` применена; post-deploy matrix зеленая |

## Начальные находки после перехода

### DJ6-BASE-001 - Новые model field fetch modes внедрены как локальная стратегия

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P2`.
- Область: ORM всего storefront/management/accounts/reviews/finance; DTF исключить.
- Доказательство: Stage 2 устранил подтвержденные N+1 через exact projection,
  annotation, `select_related`, `Prefetch` и bulk mappings. Локальный smoke для
  `DJ6-ORM-001..003` дал `1` запрос с exact fields против `2` с `FETCH_PEERS`.
  Семь `FETCH_RAISE` contracts защищают узкие projections, default
  `FETCH_ONE` подтвержден, production override отсутствует. Evidence:
  `docs/qa/django61-stage2-completion-report.md`.
- Что дало: скрытая lazy fetch теперь падает в целевых tests, но production не
  получает глобального изменения query count, памяти или async behavior.
- Риск и ограничения: новый `FETCH_PEERS` может быть полезен на других
  queryset batches, но только после измерения; глобальное включение по-прежнему запрещено.
- Следующая проверка: для новых доказанных deferred N+1 сравнивать exact fields,
  prefetch и локальный `FETCH_PEERS`, затем выбирать минимальный measured вариант.

### DJ6-BASE-002 - Не исследованы database-level `on_delete` actions

- Статус: `отложено`; предварительный приоритет: `P2`.
- Область: все модели с ForeignKey/OneToOne/мягким удалением; DTF исключить.
- Доказательство: в non-DTF inventory 566 relation fields (552 FK/OneToOne и 14 ManyToMany): для прямых связей `CASCADE` 222, `SET_NULL` 195, `DO_NOTHING` 78, `PROTECT` 57; `db_constraint=False` у 179 прямых relation fields. Live MariaDB probe подтвердил 178 MyISAM/127 InnoDB, только 39 фактических FK и `DELETE_RULE=RESTRICT` у них. Поэтому DB-level action остается отдельным schema этапом, а не включается автоматически.
- Что может дать: часть целостности и каскадных действий может выполняться на уровне MariaDB, меньше Python-side work и race windows.
- Риск: существующие MyISAM-таблицы, исторические данные, разные семантики `PROTECT`/`RESTRICT`/`SET_NULL`, миграции и irreversible cascade.
- Следующая проверка: инвентаризация engine/constraints/удалений и read-only dry-run на копии схемы; production mutation не выполнять.

### DJ6-BASE-003 - Закрыть новый `MAILERS` API полным call graph

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P1` как umbrella для email migration.
- Область: email notifications, password reset, checkout/management mail paths.
- Доказательство: `docs/qa/django61-stage1-email-call-graph.md` фиксирует все восемь non-DTF отправок, их aliases и exception policy. Настроены `default`, `transactional` и `reports`; contract запрещает неявный mailer и покрывает no-network/production-equivalent backend construction.
- Что может дать: явное разделение backend/политик отправки, изоляция ошибок и более управляемые тестовые/production mail routes.
- Риск: named mailers не являются очередью; retry/idempotency и наблюдаемость доставки остаются отдельной задачей background/durable delivery.
- Следующая проверка: сохранять AST inventory и no-send mail checks в CI; реальную SMTP-доставку проверять только отдельным контролируемым operational smoke.

### DJ6-BASE-004 - MariaDB system-check warnings требуют отдельного решения

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: `reviews.ReviewVote`, `storefront.ProductFitOption`, `storefront.WebPushDeviceSubscription.endpoint`.
- Доказательство: live Django 6.1/MariaDB probe подтвердил, что conditional unique constraints не созданы в `reviews_reviewvote` и `storefront_productfitoption`; также остается warning для unique `CharField` с `max_length > 255`. Read-only duplicate scan по этим двум контрактам вернул нули, но отсутствие дублей не заменяет реальное ограничение.
- Что может дать: восстановление реально гарантируемой уникальности и отсутствие ложного ощущения, что ограничения действуют.
- Риск: существующие дубли, миграции на больших таблицах, изменение API ошибок и конкурирующие записи.
- Следующая проверка: read-only duplicate scan, сравнение фактических `SHOW CREATE TABLE` с моделями, затем отдельная миграционная стратегия.

### DJ6-BASE-005 - Redis capability повторно проверена; выбран cron alternative

- Статус: `реализовано 2026-08-19: Redis NO-GO, MariaDB/cron GREEN`; приоритет: `P1` как зафиксированное архитектурное решение.
- Область: фоновые задачи, cron, management commands, Redis broker, Passenger workers; DTF исключить.
- Доказательство: CloudLinux-bound production probe повторно получил `gaierror` для настроенного Redis hostname; `redis-cli`, пакет `celery`, `supervisorctl` и systemd-команды недоступны, а `TASKS.default` равен `django.tasks.backends.immediate.ImmediateBackend`. Redis/Celery не объявлены рабочими и не менялись. Вместо этого MariaDB durable adapter с bounded cron прошел applied migration, no-send reclaim canary, ownership и budget gates.
- Что дало: отказ от ложного ожидания Redis/daemon на shared hosting и подтвержденный production путь для ограниченного no-send task scope без нового сервиса.
- Риск и ограничения: это не разрешение переносить произвольные provider side effects в adapter; Redis DNS/TLS/ACL и long-lived worker остаются отдельным будущим вопросом. Один active cron owner и leases обязательны.
- Следующая проверка: для новой domain task отдельно добавить allowlist, idempotency/lease contract, capacity gate и production evidence. Источник: `docs/qa/django61-stage6-production-activation.md`.

### DJ6-BASE-006 - Deferred/async access boundaries не проверены по всему сайту

- Статус: `неактуально для текущего runtime`; предварительный приоритет: `P1`.
- Область: async views, DRF, serializers, background commands и любые `defer()`/`only()`.
- Доказательство: static search по всем non-DTF Python-файлам не нашел `async def`, `sync_to_async`, `database_sync_to_async` или async ORM methods. Deferred fields используются только в sync-коде; async boundary для текущего runtime не существует.
- Что может дать: устранение runtime `SynchronousOnlyOperation`, предсказуемые async query plans и безопасная подготовка к fetch modes.
- Риск: скрытый доступ к полю в serializer/template/property, разные DB aliases и MyISAM/InnoDB поведение.
- Следующая проверка: повторить static gate при появлении первого async view/worker; до этого не добавлять async-only mitigation и не считать `only()` сам по себе async-багом.

## Findings log

Новые записи добавлять ниже по мере получения отчетов агентов и production evidence. Дубли объединять по ID, сохраняя все доказательства.

### DJ6-DOC-001/002 - Актуализировать current-facing runtime и deployment docs

- Статус: `реализовано в release candidate`; приоритет: `P2`.
- Область: `ARCHITECTURE_SUMMARY.md`, `README_ARCHITECTURE.md`,
  `DEPLOYMENT_INSTRUCTIONS.md`.
- Доказательство: документы теперь указывают CPython `3.14.6`, Django `6.1`,
  DRF `3.18.0`, MariaDB `11.4.12`, `mysqlclient 2.2.8`, общий `.venv` и
  fast-forward SSH pull через `main`; старый Django 5.2, PyMySQL, старый IP,
  feature-ветка, `pip install`, SCP/release wrappers и автоматические
  migrations/collectstatic удалены из current-facing пути. QA:
  `docs/qa/django61-stage7-docs-runtime.md`.
- Что дает: новые агенты и разработчики видят тот же runtime/deploy contract,
  поэтому диагностика не уходит в другой Python/Django и не запускает опасный
  альтернативный deploy.
- Риск и ограничения: исторические audit/incident docs намеренно не
  переписаны; документация не заменяет live production proof.
- Следующая проверка: после push/deploy подтвердить SHA, runtime и чистоту
  tracked-файлов read-only SSH probe.

### DJ6-SRV-007 - Destructive Stage 5 helpers должны fail-closed по endpoint и identity

- Статус: `исправлено в release commits 8ece82452 и 54f36a1b7`; приоритет: `P1`.
- Область: `scripts/audit_django61_db_actions.py::run_disposable_experiment`,
  `scripts/run_stage5_innodb_canary.py::run_disposable_innodb_canary`.
- Доказательство: review выявил, что programmatic helper мог получить
  production-backed `connection_factory` после проверки только loopback/`allow_disposable`;
  вызов создавал и удалял schema. Исправление требует точный interlock,
  именованный временный socket, disposable-only DB user, dedicated non-3306
  host port (or named socket) и live-проверку `VERSION()`, `@@hostname`,
  `@@port`, `CURRENT_USER()` и пустого `DATABASE()` до любого DDL.
- Что дает: случайный production socket/credential больше не проходит до
  `CREATE DATABASE`; неправильный identity завершается до открытия schema.
- Риск и ограничения: это только safety gate для disposable harness, не
  разрешение на production DDL и не доказательство production engine state.
- Проверка: regression tests должны доказать отсутствие вызова factory при
  неполном interlock, отказ от production socket и отказ при identity mismatch;
  затем один scoped Stage 5 gate.

## Матрица релизных изменений 5.2 -> 6.0 -> 6.1

Ниже собраны функции релизов, которые пересекаются с активным non-DTF кодом, тестами, конфигурацией или серверным runtime. Это не разрешение на автоматическое внедрение: `не используется` означает, что поиск не нашел применимого контракта, а `отложено` - что для функции нужен отдельный schema/worker/UX этап.

| Версия | Функция | Проверка в проекте | Итоговый ID/статус |
| --- | --- | --- | --- |
| 5.2 | `CompositePrimaryKey` | Composite PK в non-DTF моделях не найден; текущие связи и admin рассчитаны на обычный `pk`. | Не используется; отдельной миграции не нужно. |
| 5.2 | Новые ORM/model API и compatibility checks | Весь model graph построен под Django 6.1; фактический DB constraint/engine parity вынесен в отдельные проверки. | `DJ6-SITE-001`, `DJ6-DB-002` - подтверждено. |
| 6.0 | Django Tasks contract (`@task`, `.enqueue()`) | `TASKS.default` остается `ImmediateBackend`, но для allowlisted no-send scope production-active MariaDB durable adapter с одним bounded cron owner прошел migration/reclaim/budget gates. Redis/Celery остается NO-GO. | `DJ6-TASK-001` - реализовано в ограниченном scope; `DJ6-TASK-002` guard сохраняет запрет тяжелого inline enqueue. |
| 6.0 | Database-level `on_delete` (`DB_CASCADE` и аналоги) | Нужны InnoDB и реальные FK; production содержит 178 MyISAM и только 39 FK. | `DJ6-BASE-002`, `DJ6-DB-001`, `DJ6-SRV-003` - отложено. |
| 6.0 | Template partials (`partialdef`/`partial`) | 265 шаблонов распарсились; повторяющиеся full/fragment пары не переведены. | `DJ6-TPL-001` - подтвержденная opportunity. |
| 6.0 | `{% querystring %}` | Найдены ручные `request.GET.urlencode` и pagination links. | `DJ6-TPL-002` - подтверждено. |
| 6.0 | HTTPS default для `URLField` | Все 16 non-DTF model URLFields инвентаризированы; project-owned формы и legacy HTTP behavior закреплены regression tests. | `DJ6-FORM-001` - реализовано. |
| 6.0 | Forkserver/parallel test runner | Изолированный `--parallel 2` проходит, полный suite еще не green. | `DJ6-TEST-001` - отложено. |
| 6.0 | Keyword-only mail API и новые email deprecations | Deprecated kwargs удалены из полного non-DTF call graph; raise/retry policy закреплена HTTP/cron/recovery tests. | `DJ6-EMAIL-002` - реализовано. |
| 6.0 | PBKDF2 iteration increase до 1,200,000 | Пароли используют стандартный hasher; CPU/rehash behavior требует измерения. | `DJ6-AUTH-001` - подтверждено. |
| 6.0 | Встроенная CSP middleware/policy base | Проект формирует CSP вручную; inline/eval policy не переведена. | `DJ6-CSP-001` - подтверждено. |
| 6.1 | Model field fetch modes (`FETCH_PEERS`, `FETCH_RAISE`) | В tracked non-DTF Python найдено 129 call sites: 127 production (`125` `only()` + `2` `defer()`) и 2 test-only `only()`; подтвержденные Stage 2 N+1 устранены точными ORM-стратегиями, семь projections защищены test-only `FETCH_RAISE`. | `DJ6-BASE-001`, `DJ6-ORM-001..012` - реализовано. |
| 6.1 | Named `MAILERS` и `using=` | Настроены `default`, `transactional`, `reports`; восемь non-DTF call sites используют явный alias и проходят `mail.E001`. | `DJ6-EMAIL-001`, `DJ6-BASE-003` - реализовано. |
| 6.1 | CSP nonce attribute и `security.W027` | Базовая CSP есть вручную, nonce/report-only contract отсутствует. | `DJ6-CSP-001` - подтверждено. |
| 6.1 | Signed-cookie salt derivation | Project override отсутствует; runtime использует Django default `False`, custom salts инвентаризированы. | `DJ6-COOKIE-001` - реализовано. |
| 6.1 | PBKDF2 iteration increase до 1,500,000 | Следующий login может rehash старый пароль; нагрузка не измерена. | `DJ6-AUTH-001` - подтверждено. |
| 6.1 | `UUID4`/`UUID7` database functions | MariaDB `11.4.12` ниже официального порога availability `11.7`. | `DJ6-ORM-014` - заблокировано версией БД. |
| 6.1 | Admin `list_select_related` behavior/deprecation | Runtime registry содержит 125 non-DTF admin; social-auth admin переведён на explicit related fields, restock actions проверены на query count и permissions. | `DJ6-ADMIN-001`, `DJ6-COMPAT-002` - реализовано. |
| 6.1 | Strict Base64 parsing | Credential, PII, Meta, Telegram legacy и Monobank paths используют общий strict decoder и regression matrix. | `DJ6-SEC-002` - реализовано. |
| 6.1 | Cache-key/signed-cookie compatibility changes | File cache и краткоживущие cookies требуют controlled deploy miss/rollout. | `DJ6-CACHE-001`, `DJ6-COOKIE-001` - подтверждено. |
| 6.1 | `salted_hmac()` explicit algorithm requirement | IG payment evidence явно закрепляет SHA-1; frozen vector и historical signature acceptance предотвращают скрытую смену формата. | `DJ6-SEC-001`, `DJ6-WARN-001` - реализовано. |
| 6.1 | QuerySet `values().in_bulk()` и `totally_ordered` | Два cart mapping path используют узкие dict mappings; восемь paginator querysets получили unique tie-breaker. | `DJ6-ORM-009..011` - реализовано. |
| 6.1 | Strict model/parser validation и текущие checks | `manage.py check`, import/parser/template/static smoke, реальный migration graph и исправленный Product Video contract входят в Stage 0 gates. | `DJ6-SITE-001`, `DJ6-MIG-002`, `DJ6-TEST-003` - реализовано. |

Матрица закрывает найденные пересечения релизов с сайтом. Функции, не имеющие model/HTTP/template/worker/DB применения в non-DTF коде, не превращаются в искусственные backlog-пункты.

### DJ6-EMAIL-001 - Перейти с deprecated `EMAIL_*`/`EMAIL_BACKEND` на Django 6.1 `MAILERS`

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P1` как обязательная подготовка к Django 7.0.
- Область: общая конфигурация email и все не-DTF пути отправки: `twocomms/twocomms/settings.py:961-980`, `twocomms/orders/email_receipt.py:369-378`, `twocomms/storefront/services/restock.py:361`, `twocomms/storefront/management/commands/send_utm_report.py:140-155`, `twocomms/management/views.py:6597-6605`, `6901-6910`, `7273-7281`, `8224-8226`.
- Доказательство: Django 6.1 `MAILERS` внедрен с aliases `default`, `transactional`, `reports`; существующие hosting environment names сохранены. Все восемь non-DTF call sites передают `using=`, а no-network и production-equivalent SMTP contracts проходят `mail.E001` без реальной отправки. Полная карта: `docs/qa/django61-stage1-email-call-graph.md`. Источник API: <https://docs.djangoproject.com/en/6.1/releases/6.1/#mailers> и <https://docs.djangoproject.com/en/6.1/howto/mailers-migration/>.
- Что даст: уберет накопление deprecation debt, подготовит проект к Django 7.0, позволит развести транзакционные письма, отчеты и потенциальные маркетинговые отправки по разным backend/credentials/timeout-политикам и тестировать их независимо.
- Риск и ограничения: нельзя механически переносить SMTP-параметры без проверки cPanel SSL/TLS, `DEFAULT_FROM_EMAIL`, поведения console backend в `DEBUG`, маскирования секретов и фактической доставки. Именованные mailers не являются очередью и сами по себе не дают retry/idempotency.
- Следующая проверка: контролировать aliases через AST contract и отдельно проектировать durable retry/outbox; реальный SMTP smoke не смешивать с automated tests.

### DJ6-EMAIL-002 - Удалить deprecated `fail_silently` и проверить новые ошибки email API

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P1`.
- Область: `EmailMessage.send()`/`EmailMultiAlternatives.send()` и `send_mail()` во всех не-DTF приложениях; конкретные вызовы перечислены в `DJ6-EMAIL-001`, дополнительно `twocomms/orders/management/commands/recover_checkouts.py:105-110`.
- Доказательство: удалены семь `fail_silently=False`; default raise semantics сохранены. SMTP exception tests подтверждают существующую политику для management HTTP, UTM cron, restock/receipt и checkout recovery paths; deprecated project-owned kwargs больше не остаются. Источник: <https://docs.djangoproject.com/en/6.1/releases/6.1/#email> и <https://docs.djangoproject.com/en/6.1/releases/6.0/#positional-arguments-in-django-core-mail-apis>.
- Что даст: явную политику обработки SMTP-сбоев вместо скрытого флага, одинаковые исключения для HTTP, cron и будущих background workers, готовность к Django 7.0.
- Риск и ограничения: простое удаление `fail_silently=False` может изменить ожидаемую обработку исключений в recovery-командах и административных формах; для каждого пути нужно решить `raise`, логирование, retry или durable outbox.
- Следующая проверка: retry/idempotency реализовывать отдельно через durable delivery contract; текущие sync paths намеренно продолжают поднимать SMTP exception.

### DJ6-CSP-001 - Заменить самописную CSP-строку на встроенный Django CSP с report-only и nonce

- Статус: `подтверждено`; предварительный приоритет: `P1`.
- Область: все не-DTF HTTP-субдомены; `twocomms/twocomms/middleware.py:271-289`, `twocomms/twocomms/settings.py:1271-1325` и продолжение `CONTENT_SECURITY_POLICY`, базовые шаблоны и inline-скрипты.
- Доказательство: проект вручную формирует один строковый `Content-Security-Policy` и выставляет его через `SecurityHeadersMiddleware`; policy содержит `'unsafe-inline'` и `'unsafe-eval'`. Django 6.0 добавил `ContentSecurityPolicyMiddleware`, `SECURE_CSP`, `SECURE_CSP_REPORT_ONLY`, контекстный процессор и per-view decorators; Django 6.1 добавил `csp_nonce_attr` и check `security.W027`. Источники: <https://docs.djangoproject.com/en/6.1/howto/csp/> и <https://docs.djangoproject.com/en/6.1/releases/6.1/#csp>.
- Что даст: структурированную и проверяемую policy, безопасное постепенное ужесточение через report-only, nonce для собственных inline assets, системные проверки и меньше риска ошибочно собрать заголовок строковой конкатенацией.
- Риск и ограничения: на сайте много analytics/pixel/GTM/Clarity/TikTok и inline-кода; немедленное удаление `'unsafe-inline'`/`'unsafe-eval'` может сломать checkout и аналитику. Нужна отдельная инвентаризация реально загружаемых origins и CSP reports по каждому субдомену; DTF не проверять.
- Следующая проверка: снять текущие headers и browser console violations для storefront/management/warehouse/finance, развернуть эквивалентную `SECURE_CSP_REPORT_ONLY`, добавить nonce context processor и только затем планировать enforce policy.

### DJ6-TASK-001 - Production backend Django Tasks выбран и активирован в ограниченном scope

- Статус: `реализовано 2026-08-19`; приоритет: `P1`.
- Область: `task_runtime`, `twocomms/twocomms/settings.py`, bounded cron и no-send canary; DTF исключить.
- Доказательство: Django 6.1 предоставляет task contract, но не worker. В production `TASKS.default` намеренно остается `ImmediateBackend`, а opt-in MariaDB durable alias допускает только allowlisted `no_send_canary`. Scoped `task_runtime.0001_initial` применена к MariaDB/InnoDB; отдельный process lease был reclaimed после expiry без duplicate completion (`done`, `attempts=2`, один idempotency key, `external_io=false`). Один durable cron owner, installer `--check`, periodic-owner `status=ok` и budget `1/20` DB connections, `34/1024` FDs, `7/512874` processes подтверждены на SHA `ba032bbd2030421d2340e9314a921eddabe2f582`.
- Что дало: реальный durable backend и restart/reclaim путь для безопасного no-send scope без Redis/Celery daemon, без переключения существующего request path.
- Риск и ограничения: `ImmediateBackend` не стал очередью; произвольная task/provider call/user write продолжает fail-closed. Нельзя добавлять второго owner, Redis/Celery или image worker без отдельного решения и gates.
- Следующая проверка: каждая новая domain task требует собственного allowlist, payload/idempotency/lease contract, capacity gate и production evidence. Источник: `docs/qa/django61-stage6-production-activation.md`.

### DJ6-TPL-001 - Использовать Django template partials для повторно рендеримых фрагментов

- Статус: `подтверждено`; предварительный приоритет: `P3`.
- Область: storefront/management/finance/warehouse templates с большим числом `{% include %}` и AJAX/HTMX-подобных fragment responses; DTF исключить.
- Доказательство: Django 6.0 добавил `{% partialdef %}`, `{% partial %}` и синтаксис `template.html#partial_name`; в проекте новый API не используется, а 265 non-DTF template files успешно распарсились. `{% include %}` остается распространенным, поэтому это подтвержденная low-risk opportunity, а не ошибка.
- Что даст: компонент и его standalone fragment останутся в одном файле, уменьшится рассинхронизация full-page и AJAX-разметки, тестам будет проще рендерить конкретный фрагмент.
- Риск и ограничения: не каждый `include` стоит переносить; общие межстраничные компоненты по-прежнему лучше держать отдельными файлами. Нужно учитывать cached template loader и django-compressor.
- Следующая проверка: найти пары «одинаковая разметка в full response и fragment endpoint», оценить дублирование и выбрать 2-3 low-risk кандидата для отдельного benchmark/implementation этапа.

### DJ6-COOKIE-001 - Проверить совместимость старых подписанных cookies после смены salt derivation в 6.1

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P1`.
- Область: общие session/messages cookies и custom signed payloads в `twocomms/twocomms/middleware.py:108-154`, `orders/nova_poshta_checkout.py:49-86`, `orders/telegram_status_links.py:25-43`, `storefront/views/ig_checkout.py:462-495`, `storefront/views/qr.py:122-245`, `management/views.py:270-272`, `8155-8183`.
- Доказательство: project setting намеренно отсутствует,
  runtime default Django 6.1 равен `False`. AST inventory фиксирует
  20 non-DTF signing call sites и отсутствие project-owned HTTP
  signed-cookie API. Executable matrix доказывает v2 rejection/acceptance,
  `cached_db` sessions, message cookies и девять custom formats; `23/23`
  focused/consumer tests прошли. Карта: `docs/qa/django61-stage1-signed-cookie-matrix.md`.
- Что даст: предотвращение неожиданных logout/потери messages/невалидных долгоживущих ссылок или QR-context после обновления и явная дата окончания legacy acceptance.
- Риск и ограничения: fallback не включён; будущий project-owned
  `set_signed_cookie()`/`get_signed_cookie()` потребует отдельный lifetime/rotation
  contract, а не глобальную миграцию custom salts.
- Следующая проверка: сохранять AST inventory в CI и обновлять matrix
  при каждом новом signing call site.

### DJ6-ADMIN-001 - Проверить новую 6.1 семантику `list_select_related` и admin actions

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P2`.
- Область: все кастомные `ModelAdmin` не-DTF приложений и административные change list/change form страницы.
- Доказательство: runtime inventory 125 non-DTF `ModelAdmin` сохранён. Restock actions
  перенесены в `CHANGE_LIST + CHANGE_FORM`, получили отдельные singular/plural
  descriptions и `permissions=['change']`. View-only staff не видит actions и
  не может выполнить forged POST; 10 строк changelist читаются одним запросом.
- Что дало: единый action UX без N+1 и закрытая privilege boundary для mutating actions.
- Риск и ограничения: auto select-related не покрывает computed/deep relations
  новых admin classes; каждый новый тяжёлый `list_display` всё ещё измерять отдельно.
- Следующая проверка: сохранять permission regression и query-count test при
  добавлении новых admin actions или computed columns.

### DJ6-SRV-001 - Redis endpoint остается NO-GO; официально выбран другой backend

- Статус: `реализовано через альтернативу 2026-08-19`; приоритет: `P1`.
- Область: production `REDIS_URL`/`REDIS_DSN`, `twocomms/twocomms/settings.py`, `twocomms/twocomms/production_settings.py`, MariaDB durable adapter и bounded cron; DTF исключить.
- Доказательство: read-only production probe получил `gaierror` для Redis Cloud hostname; DNS/TCP/TLS/PING/ACL не доказаны. Endpoint, credentials, firewall и тариф не менялись. Формально выбран MariaDB-backed durable adapter с bounded cron; его scoped schema activation, reclaim canary, single owner и resource budget green.
- Что дало: production backend не зависит от неподтвержденного Redis и не требует Celery/supervisor на shared hosting, сохраняя контролируемый cron rollback path.
- Риск и ограничения: Redis не следует считать пригодным для cache, lock или tasks до отдельного green DNS/TCP/TLS/auth/ACL probe и новой capacity/migration оценки. `ImmediateBackend` не используется для тяжелой работы.
- Следующая проверка: Redis owner может отдельно предоставить валидный endpoint/TLS/ACL contract; это будет новая архитектурная задача, а не prerequisite текущего MariaDB/cron backend.

### DJ6-SRV-002 - Текущий production cache file-based: крупное файловое хранилище и неготовый distributed lock

- Статус: `подтверждено`; предварительный приоритет: `P1` для reliability фоновых задач, `P2` для производительности.
- Область: `twocomms/twocomms/production_settings.py:376-575`, cache-dependent rate limits, cron locks и task deduplication.
- Доказательство: production `CACHE_BACKEND=file`; `default` содержит 5 565 файлов / 110.7 MB, `fragments` 10 909 / 35.0 MB, `ratelimit` 17 486 / 0.59 MB; каталоги имеют mode `0755`. В то же время live snapshot обнаружил 4 `lswsgi` процесса и отдельный постоянный `run_instagram_bot`, а большой набор вызовов `cache.add()`/`cache.incr()` используется как lock/rate limit.
- Что даст: явный план по inode/IO/eviction observability и предотвращение ошибочного предположения, что file cache обеспечивает надежный межпроцессный queue/lease contract. После восстановления Redis или выбора другой БД можно отдельно внедрять distributed locks и cache herd protection.
- Риск и ограничения: FileBasedCache - осознанный fallback shared hosting; немедленный перенос может ухудшить uptime, а чистка cache вручную разрушит rate limit/lock семантику. Не считать `cache.add()` достаточной заменой durable job lease без конкурентного теста.
- Следующая проверка: измерить p95 cache filesystem latency, inode limits, lifecycle/TTL файлов и конкуренцию `cache.add` между Passenger+cron; затем выбрать cache backend отдельно от backend очереди.

### DJ6-SRV-003 - MyISAM остается главным барьером для транзакций, constraints и DB-level `on_delete`

- Статус: `подтверждено`; предварительный приоритет: `P1` для целостности данных, `P2` для постепенной миграции.
- Область: production MariaDB `default`, в том числе accounts, finance, storefront, warehouse, reviews, auth и legacy части management/orders; DTF не включен в подсчет.
- Доказательство: read-only inventory non-DTF моделей: 178 MyISAM таблиц (~43.90 MB) и 127 InnoDB (~549.56 MB). Полностью MyISAM остаются `accounts` (6), `finance` (28), `productcolors` (3), `reviews` (3), `warehouse` (11), а `storefront` смешан (37 MyISAM/14 InnoDB), как и `management`/`orders`. На schema есть лишь 39 фактических FK, и все их `DELETE_RULE=RESTRICT`.
- Что даст: перевод выбранных write-critical таблиц на InnoDB открывает реальные `transaction.atomic()`, row locking, FK/unique constraints, безопасные background workers и применимость Django 6.1 `DB_CASCADE`/`DB_SET_NULL`/`DB_SET_DEFAULT`.
- Риск и ограничения: `ALTER TABLE ... ENGINE=InnoDB` требует размера/lock/rollback плана, возможны старые orphan rows и различия full-text/index behavior. Нельзя мигрировать все 178 таблиц одной операцией или предполагать, что DB-level cascade сохранит `pre_delete`/`post_delete` signals.
- Следующая проверка: составить таблицу «модель -> engine -> write volume -> FK graph -> signals -> кандидат», начать с одной маленькой InnoDB-compatible copy/rehearsal, а не с production-wide migration.

### DJ6-SRV-004 - Сохранить `CONN_MAX_AGE=0`: лимит MariaDB 20 user connections не допускает бездумной async/worker экспансии

- Статус: `подтверждено`; предварительный приоритет: `P1` как architectural guardrail.
- Область: `twocomms/twocomms/production_settings.py:240-265`, Passenger, cron и будущие Django Tasks/ASGI workers.
- Доказательство: production MariaDB сообщает `max_user_connections=20`, `max_connections=150`, `wait_timeout=60`; live snapshot обнаружил 4 Passenger `lswsgi` процесса. Settings сознательно выставляет `CONN_MAX_AGE=0` и `CONN_HEALTH_CHECKS=True` из-за предыдущих stale socket/connection exhaustion инцидентов. Django async docs отдельно рекомендуют отключать persistent DB connections в async mode.
- Что даст: не допустить возврата случайных 5xx/`server has gone away` при включении worker, async endpoint или расширении Passenger; формирует capacity budget до новой параллелизации.
- Риск и ограничения: повышение `DB_CONN_MAX_AGE`, увеличение Passenger или добавление постоянных worker без расчета верхней границы соединений может снова занять все 20 слотов. При этом `CONN_MAX_AGE=0` добавляет connect overhead, который нужно измерять, а не угадывать.
- Следующая проверка: снять peak `Threads_connected` и connection attribution по Passenger/cron/daemon, задать бюджет на каждый новый процесс и нагрузочно проверить candidate worker с DB connection close discipline.

### DJ6-SRV-005 - Cron является текущим единственным допустимым scheduler: проверить overlap, lease и idempotency каждой периодики

- Статус: `реализовано и production-проверено 2026-08-17`; приоритет: `P1`, закрыт.
- Область: production cron и команды `run_instagram_bot` (каждую минуту), `reconcile_order_telegram_notifications`, `reconcile_ig_checkout`, `reconcile_ig_order_fulfillment` (каждые 2 минуты), `poll_ig_deal_payments` (каждые 4 минуты), `update_tracking_statuses` (каждые 5 минут); DTF исключен.
- Доказательство: releases `5d4e358cb`, `c56123c0d` и review-hardening `254bdb3e6` создали три managed blocks и idempotent installers. Последний hardening закрыл неизвестные loose variants watchdog/Nova Poshta и malformed marker boundaries без записи повреждённого crontab. На production найден ровно один owner каждой из шести команд, всего шесть matching scheduled lines; loose duplicates отсутствуют. Каждая строка содержит `/usr/bin/flock -n -E 75` и `/usr/bin/timeout --signal=TERM --kill-after=15s`; deadlines составляют 75 секунд для watchdog, 90 секунд для трёх двухминутных reconciliation jobs, 180 секунд для payment polling и 240 секунд для Nova Poshta. Встроенные limits/state machines ограничивают batch, leases и retry/backoff; `task_heartbeat` и hourly-deduplicated alerting наблюдают failed/stale owners.
- Что даст: один проверяемый scheduler boundary для текущего shared hosting, отсутствие overlap двух владельцев, ограниченное время/число элементов одного прогона и единая operational telemetry. Этот contract можно сохранить при будущем переходе на durable Django Tasks backend без изменения бизнес-idempotency.
- Риск и ограничения: cron по-прежнему не даёт exactly-once. Exit `75` означает намеренный overlap skip, а принудительный `KILL` после grace period останавливает зависший процесс, но не доказывает исход уже начатого внешнего запроса; поэтому provider receipt/ambiguous state остаются authoritative. Добавлять новый scheduler или второй owner без отдельного ownership migration запрещено.
- Проверка закрытия: production `HEAD == origin/main == 254bdb3e6`; все три installer `--install`/`--check` вернули `OK`; шесть task heartbeat были healthy с возрастом 15-17 секунд, dangerous backlog `0`; MariaDB `11.4.12`, pending non-DTF migrations `0`, server matrix `status=ok`, все 10 non-DTF HTTP probes прошли. Полный evidence: `docs/qa/django61-stage3-srv-005.md`.

### DJ6-SRV-006 - Server default charset `latin1` расходится с `utf8mb4` таблицами и требует явной миграционной защиты

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: production MariaDB server/schema defaults и любые будущие migration/manual SQL; DTF исключен.
- Доказательство: `@@character_set_server=latin1`, `@@collation_server=latin1_swedish_ci`, хотя все 305 таблиц, соответствующих non-DTF Django моделям, имеют `utf8mb4_unicode_ci`; Django default connection устанавливает `charset='utf8mb4'` и `default_storage_engine=INNODB` в `production_settings.py:210-219`.
- Что даст: предотвращение mojibake или случайного MyISAM/latin1 при создании таблицы/индекса вне Django, а также предсказуемую репетицию DB-level migrations.
- Риск и ограничения: смена глобального server default может затронуть другие приложения cPanel и не входит в безопасную Django migration. Для существующих таблиц она ничего не исправляет автоматически.
- Следующая проверка: проверить права на `ALTER DATABASE` и влияние на соседние приложения, затем выбрать минимальную политику: Django-only migrations с явными defaults либо отдельное согласованное изменение schema default.

### DJ6-ORM-001 - Устранить deferred N+1 в снимках оплаты заказов

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P1`.
- Область: `twocomms/storefront/views/admin.py:795-804`, `twocomms/orders/nova_poshta_documents.py:244-247`.
- Доказательство: regression batch из 10 заказов воспроизводит RED `11 != 1`
  с десятью отдельными SELECT `discount_amount`; explicit projection даёт GREEN
  `1` запрос и сохраняет 10 snapshot rows, discount/payable totals. Production
  MariaDB old/new `EXPLAIN` идентичен на 10 последних заказах. Карта:
  `docs/qa/django61-stage2-orm-001-003.md`.
- Что даст: устранит до одного дополнительного SQL-запроса на каждый заказ в пакетном admin endpoint и снизит задержку обновления платежных карточек.
- Риск и ограничения: глобальный `FETCH_PEERS` не включён; точная projection
  доказана дешевле локального peer fetch (`1` против `2` запросов).
- Следующая проверка: сохранять query-count test при изменении payment snapshot.

### DJ6-ORM-002 - Устранить deferred N+1 в расчете замороженной суммы одного реселлера

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P2`.
- Область: `twocomms/finance/services/consignment.py:389-396`, `twocomms/finance/models_consignment.py:214-223`.
- Доказательство: batch из 10 consignment items воспроизводит RED `11 != 1`;
  включение `is_consignment` в `.only()` даёт GREEN `1` и точный
  `Decimal('246.80')`. На disposable MariaDB 11.4 fixture из 10 целевых,
  1 non-consignment и 500 rows другой компании old/new `EXPLAIN` идентичен:
  `type=ref`, key `idx_cons_item_res_cons`, estimate `10`, `Using where`.
- Что даст: один SQL вместо схемы `1 + N` при расчете замороженных средств магазина; уменьшит задержку finance dashboard.
- Риск и ограничения: production таблица пуста, поэтому data-bearing evidence
  получено только на disposable MariaDB, а не на live данных.
- Следующая проверка: повторить read-only `EXPLAIN` на production после появления реальных consignment rows.

### DJ6-ORM-003 - Устранить тот же deferred N+1 в общей замороженной сумме компании

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P2`.
- Область: `twocomms/finance/services/consignment.py:417-431`, `twocomms/finance/models_consignment.py:214-223`.
- Доказательство: тот же controlled batch фиксирует `11 -> 1` и точный
  `Decimal('246.80')`; broad `except Exception` не изменён. Disposable MariaDB
  old/new `EXPLAIN` идентичен: `type=ref`, company FK key, estimate `11`,
  `Using where`. Spec и quality review commit `c8e6b13bd` прошли без замечаний.
- Что даст: особенно заметное снижение числа запросов на общем dashboard и более предсказуемая диагностика ошибочного расчета.
- Риск и ограничения: изменение exception policy является отдельным поведением; в первом проходе достаточно устранить deferred access и измерить запросы.
- Следующая проверка: отдельно аудировать broad exception policy; live
  `EXPLAIN` повторять после появления production consignment rows.

### DJ6-ORM-004 - Убрать до двух N+1-запросов на строку в Django admin пользователей

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P2`.
- Область: `twocomms/accounts/admin.py:52-77`, связи `UserProfile.user` и `UserPoints.user` в `twocomms/accounts/models.py:22-24`, `112-115`.
- Доказательство: explicit `select_related("userprofile", "points")` сократил
  10 строк `21 -> 1`; отсутствующие profile/points возвращают `—`. SQLite и
  disposable MariaDB 11.4 contracts прошли.
- Что дало: убраны два reverse OneToOne lazy fetch на строку UserAdmin.
- Риск и ограничения: в queryset не добавлялись inline/M2M relations.
- Следующая проверка: сохранять test при расширении `UserAdmin.list_display`.

### DJ6-ORM-005 - Заменить N+1 подсчет товаров в Category API на аннотацию

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P2`.
- Область: `twocomms/storefront/viewsets.py:39-52`, `twocomms/storefront/serializers.py:24-33`.
- Доказательство: filtered `Count` сократил 10 категорий `12 -> 2`; published,
  draft-only и empty values совпадают на SQLite/MariaDB.
- Что дало: публичный Category API больше не выполняет count на каждую строку.
- Риск и ограничения: при добавлении новых joins повторно проверить необходимость `distinct`.
- Следующая проверка: query plan повторно измерять при изменении Category queryset.

### DJ6-ORM-006 - Предзагрузить цвет и варианты только для Product detail API

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P2`.
- Область: `twocomms/storefront/viewsets.py:71-91`, `twocomms/storefront/serializers.py:36-49`, `108-110`, `twocomms/productcolors/models.py:28-34`.
- Доказательство: detail с тремя variants сократился `6 -> 3`; list остался
  `2` и SQL не обращается к variant table.
- Что дало: bounded detail queries без дополнительного list payload.
- Риск и ограничения: prefetch намеренно привязан только к action `retrieve`.
- Следующая проверка: сохранять отдельные detail/list query-count tests.

### DJ6-ORM-007 - Использовать один `in_bulk()` вместо 25 запросов в analytics widget товаров

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P2`.
- Область: `twocomms/storefront/services/admin_analytics.py:1328-1358`.
- Доказательство: до 25 lookups заменены одним `in_bulk()`; исходный rows
  order, duplicate IDs, null skip и deleted product fallback сохранены.
- Что дало: product lookup cluster административной аналитики ограничен одним SQL.
- Риск и ограничения: aggregate queries вокруг widget не менялись.
- Следующая проверка: сохранять fallback/query-count contract при изменении widget.

### DJ6-ORM-008 - Заменить N+1 `exists()` в survey analytics на `Exists/OuterRef`

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P2`.
- Область: `twocomms/storefront/services/admin_analytics.py:1522-1526`.
- Доказательство: пять order lookups сведены к одному correlated query; rate
  `40.0%`, user/anonymous/null semantics сохранены. Production `EXPLAIN`
  использует user index (`ref`, estimate 7), `created` остаётся residual predicate.
- Что дало: bounded SQL и отсутствие materialization всех completed sessions.
- Риск и ограничения: составной `(user_id, created)` пока не оправдан текущим объёмом.
- Следующая проверка: вернуться к индексу при росте survey/order rows и slow-query evidence.

### DJ6-ORM-009 - Применить новый Django 6.1 `values().in_bulk()` в расчете subtotal корзины

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P3`.
- Область: `twocomms/storefront/views/cart.py:95-113`.
- Доказательство: запрос остался `1 -> 1`, но выбирает только `id/price`;
  `Decimal('600')`, missing product, zero price, discount и invalid quantity
  закреплены backend-neutral SQLite/MariaDB assertions.
- Что дало: меньше выбранных колонок и без создания Product instances.
- Риск и ограничения: выигрыш по latency зависит от размера корзины/строки.
- Следующая проверка: benchmark крупных корзин только при performance incident.

### DJ6-ORM-010 - Применить `values().in_bulk()` при проверке принадлежности варианта товара

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P3`.
- Область: `twocomms/storefront/views/utils.py:261-273`, `294-313`.
- Доказательство: запрос остался `1 -> 1`, выбирает только `id/product_id`;
  dict/model mappings, wrong/missing/duplicate variants и pending Monobank reset сохранены.
- Что дало: уже bulk path стал уже по payload и model allocation.
- Риск и ограничения: helper намеренно поддерживает старые model mappings для callers/tests.
- Следующая проверка: сохранять session cleanup contract при изменении cart schema.

### DJ6-ORM-011 - Использовать `QuerySet.totally_ordered` как gate для стабильной пагинации

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P1` для операционных списков, `P2` для остальных.
- Область: `twocomms/management/views.py:2099-2108`, `management/shop_views.py:281-293`, `management/network_views.py:56-87`, `management/checker_views.py:150-188`, `management/parsing_views.py:114-138`, `warehouse/views/history.py:17-42`, `orders/dropshipper_views.py:329-355`, `439-451`.
- Доказательство: восемь querysets получили `-id`; `totally_ordered` стал
  `False -> True`, 8 tie-boundary tests исключают пропуски/дубли. MariaDB plans
  не ухудшились, новый DDL не нужен.
- Что дало: стабильная пагинация management, dropshipper и warehouse lists.
- Риск и ограничения: существующие production `print()` в dropshipper view не
  менялись и остаются отдельной observability находкой.
- Следующая проверка: использовать `totally_ordered` как regression gate для новых paginator paths.

### DJ6-ORM-012 - Включать `FETCH_RAISE` в тестах для намеренно узких projections

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P2`.
- Область: `twocomms/storefront/services/catalog_facets.py:40-47`, `storefront/seo_utils.py:167-199`, `management/bot_views.py:2418-2429`, `storefront/sitemaps.py:114-130`, `239-250`, `307-320`.
- Доказательство: шесть storefront contracts и один management lifecycle
  contract проходят под test-only `FETCH_RAISE`; контрольный omitted field
  выбрасывает `FieldFetchBlocked`, default остаётся `FETCH_ONE`.
- Что дало: SEO/sitemap/facets/lifecycle projections теперь fail-fast при будущем N+1.
- Риск и ограничения: monkeypatch ограничен test context; production не изменён.
- Следующая проверка: добавлять такой contract к новым намеренно узким `.only()` paths.

### DJ6-ORM-013 - Исследовать `GeneratedField` для единой итоговой цены Product

- Статус: `отложено`; предварительный приоритет: `P3`, только schema experiment.
- Область: формула `Product.final_price` в `twocomms/storefront/models.py:1016-1025`, дублирование в `storefront/views/catalog.py:730-750` и `storefront/serializers.py:241-247`.
- Доказательство: одна и та же discount formula вычисляется Python property, SQL annotation и serializer fallback. Django 6.0 улучшил `GeneratedField`, но на MariaDB после save такое поле будет deferred из-за отсутствия `RETURNING`. Источник: <https://docs.djangoproject.com/en/6.1/ref/models/fields/#generatedfield>.
- Что даст: один DB-maintained источник итоговой цены, возможность единообразно сортировать/индексировать и убрать расхождение округления.
- Риск и ограничения: это DDL legacy Product table; нужны точная integer/Decimal семантика, проверка MariaDB generated columns, engine, lock time и deferred refresh. Не считать готовым изменением.
- Следующая проверка: disposable MariaDB schema, parity matrix для скидок 0/1/33/100 и `EXPLAIN` сортировки до плана миграции.

### DJ6-DB-001 - Рассмотреть `DB_CASCADE` только для retention-графа аналитики

- Статус: `отложено`; предварительный приоритет: `P2`.
- Область: `SiteSession -> PageView` в `twocomms/storefront/models.py:2242-2245`, cleanup `twocomms/storefront/management/commands/trim_analytics.py:39-48`.
- Доказательство: удаление старых SiteSession проходит через Python collector и каскадирует PageView. Django 6.1 добавил `DB_CASCADE`, который не загружает связанные строки и не отправляет delete signals. Источник: <https://docs.djangoproject.com/en/6.1/ref/models/fields/#django.db.models.ForeignKey.on_delete>.
- Что даст: ускорить массовое retention-удаление технической аналитики и уменьшить память/время Python процесса.
- Риск и ограничения: только после подтверждения InnoDB и реального FK через `SHOW CREATE TABLE`; проверить отсутствие delete signals/audit hooks. Для Product, Order и финансовых данных этот вывод не переносить.
- Следующая проверка: signal graph, engine/FK inventory и disposable MariaDB migration с замером batch delete.

### DJ6-DB-002 - Сделать реальные MariaDB constraints обязательным compatibility gate

- Статус: `подтверждено`; предварительный приоритет: `P1`.
- Область: `twocomms/reviews/models.py:256-273`, конкурентный vote upsert `reviews/views.py:203-226`; `storefront/models.py:1432-1446`, запись fit options `product_catalog/views.py:798-817`.
- Доказательство: production Django 6.1 checks и live `SHOW CREATE TABLE` подтверждают, что MariaDB не создает conditional unique constraints для `reviews_reviewvote` и `storefront_productfitoption`; read-only duplicate scans вернули нули, но приложение при этом выполняет конкурентные create/update paths. Django 6.0 добавил `Constraint.check()` в системный check framework. Источник: <https://docs.djangoproject.com/en/6.1/releases/6.0/#models>.
- Что даст: перестать считать декларацию модели фактической гарантией БД и ловить backend gap до deploy; снизить риск дублей при гонке запросов.
- Риск и ограничения: check сам не заменяет constraint. Нужны duplicate inventory и MariaDB-compatible стратегия, возможно другая schema/locking/idempotency.
- Следующая проверка: read-only duplicate scan, `SHOW CREATE TABLE`, concurrency tests на локальной копии и отдельный migration design.

### DJ6-BG-001 - Заменить request-owned post-payment daemon на durable task/outbox

- Статус: `подтверждено`; предварительный приоритет: `P1`.
- Область: `twocomms/storefront/views/utils.py:743-749`, `972-1001`, `1116-1346`; recovery `orders/management/commands/reconcile_order_telegram_notifications.py:22+`.
- Доказательство: после `transaction.on_commit()` создается daemon thread, который синхронно выполняет Telegram, Meta CAPI, TikTok и SMTP. Поток может исчезнуть при reload/restart Passenger, хотя channel markers, leases и reconciliation уже существуют.
- Что даст: доставка внешних side effects после рестарта, контролируемая конкуренция, retries/backoff и наблюдаемый статус без удержания request worker.
- Риск и ограничения: передавать в очередь только `order_pk`, предыдущий статус и pay type; не сериализовать ORM instance. Recovery cron оставить до доказательства worker health. Не менять семантику Purchase/Lead и idempotency markers.
- Следующая проверка: выбрать одну no-send canary-задачу, проверить durable outbox/lease и replay на копии БД, затем сравнить с существующим reconciliation.

### DJ6-BG-002 - Оставить создание Monobank invoice синхронным, а CAPI/Telegram вынести из checkout

- Статус: `подтверждено`; предварительный приоритет: `P1`.
- Область: `twocomms/storefront/views/monobank.py:112-154`, `871-959`.
- Доказательство: invoice URL нужен в HTTP-ответе, поэтому `_monobank_api_request()` должен остаться синхронным. После сохранения PaymentAttempt тот же request выполняет AddPaymentInfo CAPI и побочные уведомления; retry уже запускается daemon thread и может потеряться.
- Что даст: сократит checkout latency и исключит блокировку пользователя из-за внешнего CAPI/Telegram; повтор станет durable и idempotent.
- Риск и ограничения: очередь получает только PaymentAttempt PK/event ID; invoice creation, lease и ambiguous outcome нельзя превращать в fire-and-forget. Нужны provider idempotency keys и существующий payment truth contract.
- Следующая проверка: измерить долю/время CAPI на checkout, добавить outbox canary без отправки и подтвердить replay после процесса.

### DJ6-BG-003 - Убрать пятиминутный request-owned polling анализа Binotel

- Статус: `подтверждено`; предварительный приоритет: `P1`.
- Область: `twocomms/management/services/call_ai_analysis.py:1521-1584`, durable command `twocomms/management/management/commands/run_call_ai_analyses.py:43+`.
- Доказательство: `schedule_call_analysis()` запускает daemon, который до пяти минут спит, опрашивает Binotel, читает ORM и вызывает Gemini. Уже есть management command с DB-lock, stale recovery, attempt/daily caps.
- Что даст: освобождение Passenger/request, единый retry/lease contract и возможность ограниченной параллельной обработки звонков.
- Риск и ограничения: не запускать без проверки прав cron/worker и DB connection budget; сохранять caps и передавать идентификатор записи, а не ORM объект.
- Следующая проверка: сравнить command runtime с cron cadence, добавить bounded batch и no-network/mock provider test.

### DJ6-BG-004 - Перенести готовые image optimization jobs из ThreadPoolExecutor в внешний worker

- Статус: `отложено`; предварительный приоритет: `P1`.
- Область: `twocomms/product_catalog/image_jobs.py:123-380`, recovery `product_catalog/management/commands/reconcile_image_optimization_jobs.py:15+`.
- Доказательство: DB-job уже содержит supersede, lease token, conditional updates и reconciliation, но ускорение выполняется per-process `ThreadPoolExecutor`.
- Уточнение после Stage 6 activation: общий MariaDB durable backend не включал
  image worker. В production manifest `product_catalog_image_jobs` имеет
  `active:false`; cron block и owner отсутствуют. Это не live rollout.
- Что даст: общую очередь между Passenger-процессами, устойчивость к reload и контролируемую CPU/IO concurrency; пользовательский upload перестанет зависеть от локального executor.
- Риск и ограничения: worker и Passenger должны видеть один `MEDIA_ROOT`; нельзя потерять lease/supersede или создать две оптимизированные версии. Бенчмарк Pillow и лимиты памяти обязательны.
- Следующая проверка: dry-run job на копии media, конкурентный lease test и сравнение с текущей reconciliation-командой.

### DJ6-BG-005 - Убрать полный tracking batch из middleware Nova Poshta

- Статус: `реализовано`; приоритет: `P1`; release `83652c134d3d35398b3098337751ba90813dc8c6`.
- Область: `twocomms/orders/nova_poshta_middleware.py`, `twocomms/twocomms/settings.py`; batch `NovaPoshtaService.update_all_tracking_statuses`.
- Доказательство: middleware удалён из active `MIDDLEWARE`; legacy-классы стали pass-through без cache/ORM/provider/thread работы. Production managed cron block `update_tracking_statuses` прошёл `--check`, request flag принудительно `False`, due backlog перед release был `0`.
- Что даст: стабильное время ответа storefront/management и одно плановое место для rate-limited внешнего API.
- Риск и ограничения: timeout/alerting всей cron-периодики закрываются общим `DJ6-SRV-005`; возвращать request fallback нельзя.
- Проверка закрытия: 40 focused тестов, Django system check, production preflight/post-deploy и 10-route non-DTF HTTP matrix прошли; детали в `docs/qa/django61-stage3-bg-005-006.md`.

### DJ6-BG-006 - Заменить поток wake-up fulfillment, сохранив durable event semantics

- Статус: `реализовано`; приоритет: `P2`; release `83652c134d3d35398b3098337751ba90813dc8c6`.
- Область: `twocomms/management/services/ig_order_fulfillment.py:860-877`, event/lease graph `285-423`, `718-857`.
- Доказательство: `kick_order_fulfillment()` теперь compatibility no-op и не создаёт request-owned thread. Существующий `reconcile_ig_order_fulfillment --limit 100` cron остаётся owner durable event queue с event keys, leases, receipt checkpoint и stale-to-ambiguous переходом; production due backlog перед release был `0`.
- Что даст: task wake-up или чистый cron снизит количество локальных потоков без потери бизнес-состояния и упростит recovery.
- Риск и ограничения: доставка теперь имеет cron cadence до двух минут; неизвестный Meta outcome остаётся `manager_review`, queue семантика и provider receipt не изменялись.
- Проверка закрытия: 40 focused тестов, production post-deploy matrix и все 10 non-DTF HTTP probes прошли; детали в `docs/qa/django61-stage3-bg-005-006.md`.

### DJ6-BG-007 - Сделать уведомление о новой регистрации durable и commit-safe

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: `twocomms/accounts/signals.py:44-78`.
- Доказательство: `post_save` сразу создает daemon, ждет пять секунд и отправляет Telegram без `transaction.on_commit` и durable marker. При rollback или reload уведомление может уйти/потеряться несогласованно.
- Что даст: сообщение отправляется только после commit, имеет idempotency key и повторяется через общий worker/reconciliation contract.
- Риск и ограничения: определить, обязательно ли уведомление для каждого пользователя; не отправлять пароль/PII в payload. При использовании `on_commit` сохранять PK, не объект.
- Следующая проверка: transaction rollback/commit test, duplicate delivery test и no-send provider mock.

### DJ6-BG-008 - Оценить необходимость durable QR-алерта вместо session-only daemon

- Статус: `отложено`; предварительный приоритет: `P3`.
- Область: `twocomms/storefront/views/qr.py:205-230`.
- Доказательство: один Telegram alert запускается daemon-потоком только по session flag; reload процесса теряет работу, а две вкладки/устройства не дают единой event ledger.
- Что даст: если каждый scan является бизнес-событием, durable запись даст аудит и повтор; если это best-effort сигнал, можно убрать поток и оставить дешевый metric.
- Риск и ограничения: не превращать малозначимый scan в дорогую очередь и не дублировать уведомления. Требуется решение о бизнес-ценности.
- Следующая проверка: измерить volume и полезность алертов, затем выбрать metric либо outbox.

### DJ6-BG-009 - Не переносить Telegram logging handler в Django Tasks

- Статус: `подтверждено как граница`; предварительный приоритет: `P3`.
- Область: `twocomms/twocomms/log_handlers.py:52-103`.
- Доказательство: handler уже best-effort и защищен от исключений/recursion, отправляет через daemon без DB. Привязка к приложенческой очереди создаст циклическую зависимость именно во время отказа backend.
- Что даст: сохранит аварийную независимость логирования; улучшение искать во внешнем observability sink и bounded transport, а не в ORM task.
- Риск и ограничения: не считать этот поток кандидатом на обычный durable worker без отдельного внешнего канала.
- Следующая проверка: проверить лимит/доставку stderr/external sink и отсутствие recursive logging.

### DJ6-BG-010 - Оставить ImageOptimizationMiddleware выключенным до durable pre-generation

- Статус: `заблокировано правами/архитектурой`; предварительный приоритет: `P2`.
- Область: `twocomms/twocomms/image_middleware.py:20-38`, `66-99`, `157-178`; flags `twocomms/twocomms/settings.py:982-984`.
- Доказательство: каждый WSGI-процесс создает собственный `ThreadPoolExecutor` и локальный `_pending_paths`; restart теряет job, несколько Passenger процессов могут повторить conversion. В production оба флага выключены.
- Что даст: не допустить CPU burst и непредсказуемой работы в request path; вместо этого использовать уже существующие durable image jobs/CDN/pre-generation.
- Риск и ограничения: включение без общей очереди и media lock ухудшит uptime и может породить поврежденные/дублированные файлы.
- Следующая проверка: benchmark pre-generation worker и atomic file write на общей media, затем отдельное разрешение на canary.

### DJ6-BG-011 - Сохранить sync-границы транзакций при подготовке async/tasks

- Статус: `подтверждено как ограничение`; предварительный приоритет: `P1`.
- Область: payment/lease блоки с `transaction.atomic()` и `select_for_update()`, будущие task wrappers; настройки `twocomms/twocomms/settings.py:277` (WSGI-only).
- Доказательство: Django 6.1 не поддерживает транзакции непосредственно в async mode; проверенные production пути не содержат `async def`, но имеют блокирующий ORM и внешние вызовы.
- Что даст: предотвращает `SynchronousOnlyOperation`, broken transaction semantics и утечку соединений при ошибочном переводе sync бизнес-логики в async.
- Риск и ограничения: если нужен async endpoint, оборачивать цельную sync-функцию через `sync_to_async(thread_sensitive=True)`, закрывать connections и передавать PK. Не использовать async как замену durable worker.
- Следующая проверка: targeted async boundary tests с intentional deferred access и connection accounting.

### DJ6-TASK-002 - Сохранить fail-fast guard для `ImmediateBackend`

- Статус: `guard реализован и сохраняется`; приоритет: `P1`.
- Область: `twocomms/twocomms/task_boundaries.py`,
  `twocomms/management/tests_django61_task_backend_guard.py`, а также
  `twocomms/twocomms/settings.py:1085-1102`.
- Доказательство: Redis/Celery worker/beat по-прежнему отсутствуют, а `TASKS.default` остается `ImmediateBackend`. Отдельно production-active MariaDB durable adapter работает только для allowlisted no-send scope через один bounded cron owner. `ImmediateBackend` исполняет задачу inline и не является очередью.
- Что сделано: sync/async heavy enqueue теперь fail-closed для `ImmediateBackend`, `DummyBackend` и любого backend без явного `supports_durable_enqueue=True`; focused contract `6/6`.
- Что даст: устраняет ложную предпосылку при планировании распараллеливания и не позволяет случайно выполнить тяжёлую работу inline вне явного durable contract.
- Риск и ограничения: нельзя просто заменить backend на Redis, пока DNS/ACL/права и connection budget не подтверждены. Не добавлять произвольные task/provider side effects к active no-send scope и не дублировать cron owner.
- Следующая проверка: новая domain task может быть добавлена только через allowlist, idempotency/lease, capacity и production evidence; `DJ6-BASE-005`, `DJ6-SRV-001`, `DJ6-TASK-001` уже закрыты для текущего ограниченного backend scope.

### DJ6-TPL-002 - Использовать `{% querystring %}` для безопасной pagination

- Статус: `реализовано 2026-08-18`; приоритет: `P2`.
- Область: `twocomms/warehouse/templates/warehouse/history.html`.
- Что сделано: ручная конкатенация `page` и фильтров заменена на стандартный
  Django 6.1 template tag `{% querystring page=... %}`.
- Доказательство: `warehouse.tests.test_django61_querystring_pagination` и
  `warehouse.tests.test_django61_pagination_ordering` проходят `5/5`; покрыты
  пустой query, повторяющиеся параметры, замена page и escaping.
- Что дает: меньше шаблонного кода, корректное сохранение фильтров и единое
  URL-кодирование без дублирования `page`.
- Ограничения: внедрен только один изолированный non-DTF pagination surface;
  остальные шаблоны требуют отдельной parity-проверки.

### DJ6-CACHE-001 - Учесть одноразовый cache miss после смены Django 6.1 cache keys

- Статус: `подтверждено`; предварительный приоритет: `P2` на deploy-процедуру.
- Область: template fragment cache в `twocomms/twocomms_django_theme/templates/partials/header.html:15`, `partials/catalog_smart_selector.html:321`, `pages/catalog.html:546-550`, `pages/index.html:155`, `410`, `581`, `625`, `pages/product_detail.html:786`; также `storefront/views/utils.py:53+`.
- Доказательство: Django 6.1 изменил ключи кэшированных страниц/фрагментов, зависящих от дополнительных vary-аргументов. Первый запрос после обновления закономерно получает miss. Источник: <https://docs.djangoproject.com/en/6.1/releases/6.1/#miscellaneous>.
- Что даст: правильный deploy warm-up и отсутствие ложной тревоги по росту latency/DB load после reload; можно заранее прогреть тяжелые fragment paths.
- Риск и ограничения: не удалять cache вручную во время checkout/ratelimit activity и не считать miss постоянной неисправностью. FileBasedCache может усилить stampede.
- Следующая проверка: измерить hit/miss и SQL до/после warm-up на storefront, catalog и management; проверить, что custom `cache_page_for_anon` не смешивает старые ключи.

### DJ6-SEC-001 - Зафиксировать алгоритм `salted_hmac` для стабильного IG payment digest

- Статус: `выполнено 2026-08-16`; приоритет реализации: `P2`.
- Область: `twocomms/management/ig_bot_models.py`, функция
  `provider_evidence_signature`; provider poll/webhook, terminal cancellation,
  verified payment и проверка cancellation evidence.
- Реализация: `salted_hmac()` получает explicit `algorithm="sha1"`, поэтому
  Django 7 не изменит существующий 40-символьный digest скрыто.
- Доказательство: frozen vector с `SECRET_KEY="signature-contract-secret"`
  равен `dbd20b4d534cef919aa46493f69b143ee815c3c4`; отдельный model test создает
  legacy event с подписью от независимой SHA-1 reference-функции и подтверждает
  `has_provider_confirmed_cancellation() is True`. При временной мутации на
  `sha256` оба acceptance-теста падают, после восстановления SHA-1 проходят;
  `RemovedInDjango70Warning` не возникает.
- Что дает: сохраненные payment evidence остаются валидными после Django 7,
  новые подписи детерминированы и сохраняют прежний формат.
- Остаточный риск: изменение `SECRET_KEY` по-прежнему инвалидирует подписи и
  требует отдельной key-rotation стратегии; алгоритм без нового формата
  менять нельзя.

### DJ6-CHECK-001 - Явно ограничить database checks основным alias

- Статус: `подтверждено как operational guardrail`; предварительный приоритет: `P1` для CI/deploy.
- Область: все вызовы `manage.py check`, custom system checks и `scripts/fin_test.sh:8`.
- Доказательство: без `--database` команда `check` передает `databases=None`; поэтому часть database-tagged checks может быть пропущена, а custom checks должны корректно обрабатывать отсутствие списка либо явно переданные aliases. Django 6.1 отдельно требует готовности callers к database access. Источник: <https://docs.djangoproject.com/en/6.1/releases/6.1/#system-checks> и <https://docs.djangoproject.com/en/6.1/ref/django-admin/#cmdoption-check-database>.
- Что даст: предсказуемую read-only проверку основной базы там, где она нужна, и отсутствие ложного «green» от пропущенных database checks.
- Риск и ограничения: не использовать `--database default` как замену отдельной compatibility-проверки всех допустимых production aliases; список проверяемых баз должен быть явным и согласованным.
- Следующая проверка: inventory custom checks, заменить deploy-команды на `check --database default` там, где нужен DB check, и отдельно проверить `--tag models` без сетевых side effects.

### DJ6-MIG-001 - Подтвердить безопасную процедуру squash исторических миграций

- Статус: `подтверждено как safety gate; фактический squash отложен`; предварительный приоритет: `P3`.
- Область: non-DTF migration graph: 435 nodes (`management` 168, `storefront` 90, `orders` 52, `accounts` 30, `finance` 21 и системные/vendor chains).
- Доказательство: Django 6.0 разрешил повторно squash уже squashed migrations до перехода в normal state. Текущий graph под Django 6.1 прошёл полный disposable MariaDB clean/dump/restore/replay lifecycle с parity и cleanup; sanitized evidence: `docs/qa/django61-stage5-mig001-mariadb-lifecycle.json`. Источник: <https://docs.djangoproject.com/en/6.0/releases/6.0/#migrations>.
- Что даст: меньше времени на создание test DB/проверку migration plan и меньше файлов для сопровождения новых окружений.
- Риск и ограничения: production уже применил длинные цепочки; неправильное удаление старых migration files ломает deploy/restore и внешние базы. Не смешивать с изменением схемы или DTF.
- Следующая проверка: получить свежую read-only identity-set сверку applied migration history на production-compatible MariaDB, согласовать конкретные ranges и rollback; удаление файлов не делать до отдельного deploy/restore proof.

### DJ6-AUTH-001 - Измерить CPU-эффект нового PBKDF2 cost и постепенный rehash

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: login/password-change paths, в частности `twocomms/storefront/views/profile.py:670-671`; явный `PASSWORD_HASHERS` в проекте не задан.
- Доказательство: Django 6.0 поднял PBKDF2 iteration count до 1,200,000, Django 6.1 - до 1,500,000. Старые пароли обычно перехешируются при успешном входе. Источники: <https://docs.djangoproject.com/en/6.0/releases/6.0/#django-contrib-auth> и <https://docs.djangoproject.com/en/6.1/releases/6.1/#django-contrib-auth>.
- Что даст: прогнозируемое время входа и план capacity для Passenger вместо неожиданного CPU spike при массовых логинах.
- Риск и ограничения: понижать cost ради скорости нельзя без отдельного security-решения; Argon2/кастомный hasher потребуют совместимости с существующими hashes.
- Следующая проверка: benchmark login/hash upgrade на production-подобном CPU, измерить долю старых hash prefixes и определить rate-limited rollout.

### DJ6-FORM-001 - Проверить изменение default scheme `URLField` на HTTPS

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P2`.
- Область: `twocomms/orders/forms.py:30-34` и все ModelForm для URLField в `accounts`, `finance`, `orders`, `product_catalog`, `storefront`, `management`.
- Доказательство: contract inventory фиксирует все 16 non-DTF model URLFields. `CompanyProfileForm`, `BlogPostForm` и `PrintProposalForm` явно задают `assume_scheme="https"`; scheme-less ввод становится HTTPS, explicit HTTP/HTTPS сохраняются, invalid URL возвращает стабильный код `invalid`, а DB round-trip не переписывает stored legacy HTTP. Источник: <https://docs.djangoproject.com/en/6.0/releases/6.0/#features-removed-in-6-0>.
- Что даст: единообразные безопасные ссылки и меньше mixed-content/redirect surprises.
- Риск и ограничения: stored HTTP намеренно не мигрируется; его допустимость остается предметом конкретного provider/content contract, а не глобальной перезаписи.
- Следующая проверка: сохранять 16-field inventory и forced framework-default regression; новые project-owned ModelForm с URLField должны явно выбирать scheme policy.

### DJ6-TPL-002 - Заменить ручное сохранение query string на `{% querystring %}`

- Статус: `подтверждено`; предварительный приоритет: `P3`.
- Область: `twocomms/finance/templates/finance/partials/report_header.html:23`, `finance/templates/finance/payments.html:27-28`, длинные pagination links в `twocomms/twocomms_django_theme/templates/partials/admin_orders_section.html:986-992` и `admin_payment_attempts_section.html:37`.
- Доказательство: шаблоны вручную конкатенируют `request.GET.urlencode` и отдельные параметры. Django 6.0 обновил `{% querystring %}`: стабильно добавляет `?` и принимает несколько mappings. Источник: <https://docs.djangoproject.com/en/6.0/releases/6.0/#templates>.
- Что даст: сохранять фильтры без двойных `?`/`&`, уменьшить дублирование и упростить добавление/замену page parameter.
- Риск и ограничения: проверить allowlist параметров, чтобы не протащить служебные/PII query keys в экспортные ссылки.
- Следующая проверка: template tests для пустого и непустого query string, повторных параметров и page navigation.

### DJ6-ORM-014 - Не использовать DB-функции `UUID4/UUID7` на текущей MariaDB 11.4

- Статус: `заблокировано версией БД`; предварительный приоритет: `P3`.
- Область: UUID-поля с `uuid.uuid4` в `management`, `warehouse`, `storefront` и возможные будущие `db_default`.
- Доказательство: Django 6.1 добавил `UUID4`/`UUID7`, но официальная availability для MariaDB начинается с 11.7; live production probe подтвердил MariaDB `11.4.12-MariaDB`. Источник: <https://docs.djangoproject.com/en/6.1/ref/models/database-functions/#uuid-functions>.
- Что даст: не допустить migration/runtime SQL error при попытке использовать новую DB function; UUID7 для индексируемых operation IDs можно рассматривать позже на Python-уровне или после upgrade MariaDB.
- Риск и ограничения: UUID7 раскрывает временную компоненту и не подходит для secret/public tokens без threat-model; upgrade MariaDB не выполняется из Django user account.
- Следующая проверка: классифицировать UUID поля на secret/public/ordering, затем отдельно решить Python UUID7 versus host-managed MariaDB upgrade.

### DJ6-SRV-007 - Разобрать disk temporary tables и включить безопасную диагностику запросов

- Статус: `подтверждено как измеренный сигнал`; предварительный приоритет: `P1`.
- Область: production MariaDB `default`, аналитика, сортировки и агрегаты.
- Доказательство: read-only snapshot 2026-08-16: `Created_tmp_tables=79,544,882`, `Created_tmp_disk_tables=10,095,663` (около 12.7% temporary tables на диске), `tmp_table_size=max_heap_table_size=16 MiB`, `slow_query_log=OFF`, `performance_schema=OFF`.
- Что даст: индексы/query-shape tuning и безопасная диагностика самых дорогих Django ORM запросов; потенциально меньше disk IO и latency.
- Риск и ограничения: нельзя бездумно поднять per-connection tmp limits при user cap 20; slow log/performance_schema могут иметь hosting cost/permission limits и требуют retention/redaction.
- Следующая проверка: получить top query shapes через host-approved observability, сопоставить с `EXPLAIN`, оценить memory budget перед изменением variables.

### DJ6-SRV-008 - Исследовать высокий счетчик aborted connections/clients

- Статус: `подтверждено как сигнал`; предварительный приоритет: `P1`.
- Область: Passenger/cron/Django DB connection lifecycle.
- Доказательство: на том же snapshot `Threads_connected=17`, `Threads_running=3`, `Max_used_connections=71`, `Aborted_connects=11,118`, `Aborted_clients=11,339`; причина счетчиков пока не доказана. Значения являются счетчиками на момент probe, а не атрибуцией конкретному process.
- Что даст: выявление stale sockets, failed health checks, process restarts или invalid credentials до того, как они съедят лимит 20 user connections.
- Риск и ограничения: counters глобальны и не являются доказательством конкретного виновника; не менять timeout/connection policy без time-series и логов.
- Следующая проверка: снять дельту за 15-60 минут, сопоставить с Passenger/cron lifecycle и проверить `close_old_connections` в daemon paths.

### DJ6-SRV-009 - Учитывать `ulimit -n=1024` при file cache и worker design

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: 4 Passenger `lswsgi`, Instagram process, file-based cache и будущие worker/thread pools.
- Доказательство: production `ulimit -n` равен 1024; live snapshot обнаружил 4 `lswsgi` процесса и отдельный Instagram daemon. `ulimit -u` и disk/inode capacity не являются текущим ограничением (`512874`, inode use 6%).
- Что даст: предотвращение `EMFILE` при одновременных cache files, media uploads, sockets и threads; более реалистичный concurrency budget.
- Риск и ограничения: повышение лимита требует хостинг-права; нельзя компенсировать его бесконтрольным числом процессов.
- Следующая проверка: измерить open FDs по каждому process (`/proc/<pid>/fd` или разрешенный equivalent) под peak load и задать worker/thread cap.

### DJ6-SRV-010 - Добавить overlap guard для cron Instagram bot

- Статус: `реализовано и production-проверено 2026-08-17`; приоритет: `P1`, закрыт.
- Область: production `crontab`: `* * * * * ... manage.py run_instagram_bot --ensure` без `flock`; рядом уже работает отдельный `run_instagram_bot --forever`.
- Доказательство: release `4af27a19b` исправил ложный healthy при удерживаемом lock и stale heartbeat; `scripts/install_instagram_bot_watchdog_cron.sh` заменил legacy line на один managed block с `/usr/bin/flock -n` и `/usr/bin/timeout --signal=TERM 50s`. При stale heartbeat watchdog ждёт bounded release старого lock: если lock не освобождён, завершается ошибкой без второго daemon; принудительный kill зависшего процесса не выполняется. Production check вернул один watchdog line, один BEGIN/END block, held daemon lock, `daemon_online=True`, `running=True`, `alive=True`, healthy task heartbeat.
- Что даст: единственный владелец bot process, отсутствие duplicate polling/API side effects и понятный exit/health contract.
- Риск и ограничения: внешний lock сериализует starters, а внутренние spawn/daemon locks остаются authoritative singleton boundary; timeout короче минутного cadence. Stale process, который не освобождает lock, требует отдельной operator/host recovery; этот пункт не обещает принудительный restart. Общий contract остальных cron jobs остаётся отдельным `DJ6-SRV-005`.
- Проверка: 22 watchdog contracts, 5 installer contracts, shell syntax/compile/diff gates и production installer `--check`; полный evidence: `docs/qa/django61-stage3-srv-010.md`.

### DJ6-TEST-001 - Оценить forkserver/parallel test runner после стабилизации suite

- Статус: `отложено`; предварительный приоритет: `P3`.
- Область: 435-node non-DTF migration graph и связанные test chains; стандартного CI runner с `--parallel` в репозитории не найдено.
- Доказательство: Django 6.0 добавил поддержку `DiscoverRunner` для parallel tests на forkserver; isolated non-DTF `storefront.tests.test_cache_hygiene --parallel 2` прошел 6/6. Полный suite upgrade baseline все еще содержит 65 failures и 47 errors, поэтому общую параллелизацию отложить. Источник: <https://docs.djangoproject.com/en/6.0/releases/6.0/#tests>.
- Что даст: сократит время большой regression suite и позволит чаще прогонять matrix Python 3.14/MariaDB.
- Риск и ограничения: текущие tests используют общую файловую cache/media, внешние mocks и возможные SQLite/MariaDB locks; параллелизация до baseline green может маскировать race.
- Следующая проверка: выбрать изолированный no-network subset, запустить `manage.py test --parallel 2` с отдельными temp dirs и сравнить flake/query contention.

### DJ6-SEC-002 - Проверить строгую Base64-валидацию на PII/credential import paths

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P2`.
- Область: Google credential env, Meta `signed_request`, legacy Telegram
  manager start wrapper, modular/legacy Monobank signatures и public keys,
  active `views.py.backup`, encrypted PII `BinaryField`.
- Доказательство: `strict_b64decode()` принимает standard/URL-safe
  padded и unpadded Base64, но отклоняет whitespace, не-ASCII,
  partial padding, impossible length и trailing garbage. Все provider paths
  декодируются до crypto/parser processing; logs не содержат
  credential, key, signature или PII material. Matrix: `21/21`, с active
  consumers: `28/28`. Карта: `docs/qa/django61-stage1-sec002-base64.md`.
- Что даст: явные ошибки конфигурации/подписи вместо тихого обрезания или пустого значения, меньше неоднозначности при импорте/валидации.
- Риск и ограничения: менять декодирование webhook можно только с сохранением provider-compatible padding/URL-safe rules; не логировать секретные payloads.
- Следующая проверка: сохранять static inventory всех non-DTF
  decoder call sites и добавлять provider-specific valid vectors при новых форматах.

### DJ6-ENV-001 - Не допустить silent downgrade из старого dependency lock

- Статус: `реализовано`; приоритет реализации: `P1`.
- Область: основной локальный checkout `main`, `twocomms/requirements.in`, `twocomms/requirements.lock`, общая `.venv`, CI и production release gates.
- Доказательство: current `main`, hash-locked requirements, CI и project `.venv` закрепляют CPython `3.14.6`, Django `6.1`, DRF `3.18.0` и `mysqlclient 2.2.8`; exact-version preflight отклоняет несовпадение, чистая установка lock и production runtime подтверждены Stage 0 release evidence.
- Что даст: один воспроизводимый источник истины для локальных тестов, CI, release wheelhouse и production; устранит ложные результаты, когда код тестируется не под той парой Python/Django.
- Риск и ограничения: нельзя частично откатывать requirements или запускать bare Python; dependency changes должны проходить lock compilation, clean install, CI и production preflight как единый контракт.
- Следующая проверка: сохранять exact-version assertions и hash-locked clean-install gate при каждом dependency update.

### DJ6-ENV-002 - Bare `python` и `python3` не являются runtime проекта

- Статус: `подтверждено`; предварительный приоритет: `P1` для тестовой дисциплины.
- Область: локальные shell-команды, linked Git worktrees, инструкции агентам и ad-hoc проверки.
- Доказательство: в основном checkout bare `python` разрешается в CPython `3.13.6` с Django `5.2.11`, а `python3` - в другой CPython `3.14.3`; только `.venv/bin/python` дает CPython `3.14.6`/Django `6.1`. Локальный `.python-version` содержит `3.14.6`, но игнорируется `.gitignore`, поэтому не распространяется в worktree. `AGENTS.md` дополнен командой `TWC_PYTHON` через `git rev-parse --git-common-dir` как немедленный guardrail.
- Что даст: test/management commands и subagents будут падать сразу при неправильном runtime, а не создавать ложноположительные результаты под старым Django.
- Риск и ограничения: нельзя менять global `PATH`, `UV_PROJECT_ENVIRONMENT` или активировать venv глобально: это смешает разные проекты и worktree. Bare shell не станет правильным сам по себе даже после `uv` pin.
- Следующая проверка: в upgrade-ветке сделать `.python-version` tracked, добавить маленький wrapper для Python-команд, закрепить exact runtime в CI и запускать preflight assertion перед каждой matrix/job.

### DJ6-CI-001 - CI не доказывает exact CPython 3.14.6/Django 6.1 во всех gates

- Статус: `подтверждено`; предварительный приоритет: `P1`.
- Область: `.github/workflows/instagram-bot-mariadb-gate.yml:62-72`, `tests/test_django61_compatibility.py:17-27` и release workflows.
- Доказательство: MariaDB workflow запрашивает только `python-version: "3.14"`, а не `3.14.6`, и после установки не asserts версию interpreter или Django. Compatibility-test запускает subprocess через текущий `sys.executable`, но не проверяет `sys.version_info`/`django.get_version()`. Immutable wheelhouse workflow уже показывает нужный строгий pattern для CPython `3.14.6`.
- Что даст: CI станет доказательством именно целевой версии, а не случайной минорной версии Python или старого Django из cache/lock.
- Риск и ограничения: exact pin нужно обновлять осознанно при security patch Python; не превращать это в ложную гарантию production cPanel ABI, который требует отдельный Linux wheelhouse/runtime gate.
- Следующая проверка: добавить preflight assertion CPython `3.14.6` + Django `6.1` после hash-locked install во все relevant jobs, затем искусственно запустить test под Django 5.2 и убедиться, что gate красный.

### DJ6-CI-002 - Migration-drift gate отключает сам graph миграций

- Статус: `подтверждено`; предварительный приоритет: `P1`.
- Область: `scripts/run_ig_baseline.py:56-64`, `twocomms/test_settings_no_network.py:9`, `twocomms/test_settings.py:53-64`.
- Доказательство: baseline запускает `makemigrations --check --dry-run` с `test_settings_no_network`; профиль наследует test settings, где `MIGRATION_MODULES` отключает migrations. Поэтому проход gate не доказывает соответствие моделей реальной migration graph.
- Что даст: раннее обнаружение drift до deploy и защита от несогласованных migration files при Django 6.1.
- Риск и ограничения: нельзя гонять реальные migrations по production DB ради этой проверки; изоляция network и внешних side effects должна сохраниться.
- Следующая проверка: добавить отдельный no-network settings profile с нормальными migration modules, выполнить `makemigrations --check --dry-run` на disposable SQLite/MariaDB и включить это как независимый CI gate.

### DJ6-CI-003 - Disposable MariaDB gate не запускает `check --database=default`

- Статус: `подтверждено`; предварительный приоритет: `P1`.
- Область: `.github/workflows/instagram-bot-mariadb-gate.yml:68-108`, `scripts/run_mariadb_gate.py`.
- Доказательство: workflow запускает unit contracts и lifecycle/concurrency suites, но ни одна команда не выполняет Django `check --database=default`; ручные schema assertions не являются заменой всех database-tagged Django checks.
- Что даст: предупреждения backend, constraints и модели попадут в disposable MariaDB gate до production.
- Риск и ограничения: список приемлемых warnings должен быть явным и временным; не скрывать новый warning через глобальное silencing.
- Следующая проверка: добавить `manage.py check --settings=<disposable-mariadb-settings> --database=default` после подготовки схемы, сохранить sanitized evidence и сделать test runner contract на этот вызов.

### DJ6-STATIC-001 - Static/compressor tests не воспроизводят production путь

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: `twocomms/test_settings.py:91-125`, `twocomms/twocomms/production_settings.py:631-665`, collectstatic/compress release path.
- Доказательство: test settings отключают `COMPRESS_ENABLED`/`COMPRESS_OFFLINE` и используют plain `StaticFilesStorage`, тогда как production использует WhiteNoise manifest storage и offline compression. Прохождение unit suite не подтверждает manifest URLs или `{% compress %}` после Django 6.1.
- Что даст: ловит ошибки stale manifest, WhiteNoise/compressor integration и release static root до Passenger restart.
- Риск и ограничения: production static root нельзя использовать как test fixture; test должен иметь отдельный temporary root и не ходить в external storage.
- Следующая проверка: отдельный isolated test/job с production-equivalent storages, `collectstatic --no-input`, `compress --force`, render representative non-DTF pages и assert на manifest-backed URLs.

### DJ6-COMPAT-001 - Нет явной Django 6.1/Python 3.14 compatibility matrix для активных интеграций

- Статус: `подтверждено`; предварительный приоритет: `P1`.
- Область: `django-compressor==4.6.0`, `whitenoise==6.7.0`, `drf-spectacular==0.27.2`, `django-ratelimit==4.1.0`, `django-redis==5.4.0`, `social-auth-app-django==5.6.0` в `twocomms/requirements.in:24-36`.
- Доказательство: свежий isolated smoke под CPython 3.14.6/Django 6.1 импортировал compressor, WhiteNoise, DRF Spectacular, django-ratelimit, django-redis и social-auth; OpenAPI собрала 44 paths, template/static pipeline и rate-limit imports прошли. Vendor support/changelog matrix все еще нужна отдельно, но текущий runtime contract проверен.
- Что даст: управляемый upgrade сторонних библиотек вместо случайных runtime failures в schema generation, cache, login callback, rate limit или static pipeline.
- Риск и ограничения: не обновлять все версии «до последней» одним коммитом; у каждой библиотеки собственные backward-compatibility и hosting constraints.
- Следующая проверка: зафиксировать эти версии/результаты в CI и отдельно проверить upstream support/changelog перед будущим upgrade; не обновлять vendors массово в рамках compatibility-release.

### DJ6-COMPAT-002 - `social-auth-app-django` уже выдает Django 7 deprecation warning

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P1` до Django 7.0.
- Область: установленный `social-auth-app-django==5.6.0`, `social_django.admin.UserSocialAuthOption`, OAuth admin/login integration.
- Доказательство: upstream `6.0.1` все еще задает deprecated `list_select_related=True`, а major 6.0 одновременно меняет login на POST-only. Поэтому proven pin сохранен, а `TwoCommsAdminConfig` точечно заменяет vendor registration на `UserSocialAuthCompatAdmin` с `list_select_related=("user",)`. Runtime contract подтверждает отсутствие warning; warning gate имеет blocked `0`, allowed `0`, vendor allowlist `{}`.
- Что даст: раннее решение vendor compatibility до Django 7.0 без потери social-auth admin и OAuth flow.
- Риск и ограничения: локальный shim ограничен admin registration и не меняет OAuth pipeline/login semantics; будущий vendor upgrade должен отдельно доказать callback и POST-login parity.
- Следующая проверка: сохранять registry/warning/OAuth contracts; удалить shim только после безопасного upstream release и отдельного upgrade slice.

### DJ6-LEGACY-001 - Активный `views.py.backup` содержит удаляемый `select_related()` без полей

- Статус: `реализовано 2026-08-17`; приоритет реализации: `P1` до Django 7.0.
- Область: `twocomms/storefront/views/__init__.py:318-347`, `twocomms/storefront/views.py.backup:299,1584,3369,5605,5614,5833,5842,5890,5899`, route `twocomms/storefront/urls.py:625` (`/pricelist_opt.xlsx`).
- Доказательство: legacy loader реально подгружает `views.py.backup`; static AST contract теперь подтверждает ноль no-argument вызовов после удаления девяти мест. Существующие explicit `select_related("category")` и per-product variant queries сохранены. `/pricelist_opt.xlsx` проверяет content type, filename и workbook values без Django 7 warning; существующий `/wholesale/` regression также проходит. Источник: <https://docs.djangoproject.com/en/6.1/releases/6.1/#miscellaneous>.
- Что даст: сохранит доступность прайс-листа и legacy management paths после следующего major upgrade, а также устранит неявные joins.
- Риск и ограничения: backup остается active runtime и не должен массово рефакториться как мертвый файл; этот slice намеренно не меняет query counts или XLSX semantics.
- Следующая проверка: держать AST/route contracts до отдельного переноса legacy функций в поддерживаемые modules; ORM-оптимизации выполнять отдельными measured slices.

### DJ6-PY-001 - Заменить deprecated `SourceFileLoader.load_module()` до Python 3.15

- Статус: `реализовано`; предварительный приоритет был `P2`.
- Область: fallback import в `twocomms/storefront/tasks.py`.
- Доказательство: deprecated `load_module()` заменен на `spec_from_file_location()`/`module_from_spec()`/`exec_module()`. Forced fallback test подтверждает identity `sys.modules["image_optimizer"]`; отдельный test подтверждает cleanup и распространение ошибки `exec_module()`. Regression test доказал RED старого широкого `except ModuleNotFoundError` и GREEN после ограничения fallback только прямым отсутствием `image_optimizer`; транзитивная import error больше не скрывается. Источник API: <https://docs.python.org/3/library/importlib.html#importlib.machinery.SourceFileLoader.load_module>.
- Что даст: исключит будущий hard failure при следующем обновлении Python и сделает fallback import согласованным с уже используемым `spec_from_loader` pattern в legacy loader.
- Риск и ограничения: fallback разрешен только когда отсутствует сам top-level `image_optimizer`; ошибки его транзитивных зависимостей намеренно пробрасываются.
- Следующая проверка: сохранять четыре import compatibility tests в Python 3.14/3.15 compatibility gate.

### DJ6-DOC-001 - Обновить активную архитектурную документацию после интеграции

- Статус: `подтверждено`; предварительный приоритет: `P3`.
- Область: `README_ARCHITECTURE.md:7,281-282`.
- Доказательство: active architecture README по-прежнему заявляет Django `5.2.6` и Python `3.x`, хотя target runtime audit - CPython `3.14.6`/Django `6.1`. Исторические планы и incident reports не надо переписывать: они являются датированными evidence, а не current runbook.
- Что даст: снизит риск, что новый разработчик или агент построит environment по устаревшей версии.
- Риск и ограничения: не менять исторические документы так, чтобы потерять контекст инцидентов/решений; текущую версию указывать только после атомарной интеграции upgrade в `main`.
- Следующая проверка: после merge/deploy обновить только current-facing README/runbook, проверить ссылки на requirements и Python runtime.

### DJ6-WARN-001 - Добавить обязательный deprecation-warning gate с `-Wa`

- Статус: `подтверждено`; предварительный приоритет: `P1`.
- Область: локальные upgrade tests, CI, release baseline и все не-DTF Django-приложения.
- Доказательство: официальный upgrade guide требует включать warnings через `python -Wa manage.py test`; текущие release/CI commands этого не делают. Fresh warning-enabled check уже показывает `RemovedInDjango70Warning` для `EMAIL_*` и `social_django`, а targeted tests также обнаруживают `salted_hmac()` без явного algorithm; Python предупреждает о `SourceFileLoader.load_module()`. Источник: <https://docs.djangoproject.com/en/6.1/howto/upgrade-version/#resolving-deprecation-warnings>.
- Что даст: будущие Django 7/Python 3.15 поломки станут видимы до upgrade, а не после удаления API.
- Риск и ограничения: нельзя просто включить `-Werror` на весь шум сторонних библиотек и OS; нужен небольшой documented allowlist с владельцем и сроком удаления каждого исключения.
- Следующая проверка: отдельный no-network test shard с `-Wa`, machine-readable сбор предупреждений по module/category, затем последовательно убрать project-owned warnings и завести upstream/upgrade tasks для vendor warnings.

### DJ6-CI-004 - Обычные pull requests не имеют общего Django 6.1 gate

- Статус: `подтверждено`; предварительный приоритет: `P1`.
- Область: `.github/workflows/immutable-release-wheelhouse.yml:3-12`, `.github/workflows/instagram-bot-mariadb-gate.yml:3-35`, весь не-DTF codebase.
- Доказательство: wheelhouse workflow запускается только на push в `main` и только при изменении узкого набора lock/build files; MariaDB workflow имеет path filters вокруг Instagram/models/gate files. Изменение обычного view, model, form, template helper или management command может пройти PR без любого Django test/check под 6.1.
- Что даст: единый минимальный regression signal на каждом PR независимо от затронутого приложения.
- Риск и ограничения: полный suite сейчас не зеленый и слишком тяжел для немедленного required gate; нельзя сделать постоянно красный workflow обязательным.
- Следующая проверка: сначала добавить быстрый exact-version no-network smoke (`check`, warning shard, import contracts, migration drift), затем расширять test shards по стабильным приложениям и отдельно оставить MariaDB concurrency gate.

### DJ6-MIG-002 - Зафиксировать baseline drift трех полей `CatalogColorSeoOverride`

- Статус: `подтверждено как baseline debt, не регрессия Django 6.1`; предварительный приоритет: `P2`.
- Область: `twocomms/storefront/models.py:3122-3150`, migration `0056_phase19h_seo_admin_overrides.py:56-79`.
- Доказательство: real-graph `makemigrations --check --dry-run` под Django 6.1 предлагает `0096_alter_catalogcolorseooverride_body_html_and_more.py` для `h2`, `body_html`, `queries_json`; обычный test profile ложно отвечает `No changes detected`, потому что migrations отключены. Независимый сравнительный запуск на исходном Django 5.2.11 дает тот же diff, то есть upgrade его не создал.
- Что даст: чистый model/migration contract и честный migration gate; изменения help text/state больше не будут скрывать будущий реальный schema drift.
- Риск и ограничения: перед созданием migration проверить, что diff только metadata/state и не вызывает тяжелый ALTER на MariaDB; не смешивать с Django 6.1 compatibility commit без отдельного решения.
- Следующая проверка: `makemigrations --dry-run --verbosity 3` на обеих версиях, inspect generated operations/SQL на disposable MariaDB, затем отдельная migration с review.

### DJ6-NET-001 - Release baseline не запрещает сеть в тестовом subprocess

- Статус: `подтверждено`; предварительный приоритет: `P1`.
- Область: `scripts/deploy_release.py:610-639`, release preparation tests/checks.
- Доказательство: script запускает отдельный Python `-c`, monkey-patches `socket.getaddrinfo` и сразу завершает этот process; следующий `manage.py test` запускается новым process и не наследует monkeypatch. Label `no-network baseline` поэтому не доказывает отсутствие внешних запросов.
- Что даст: предотвращение случайных Telegram/Meta/Google/SMTP/Nova Poshta side effects и flaky release validation.
- Риск и ограничения: блокировать только test/release-preparation process; production smoke после switch намеренно требует network. Простая замена DNS может не закрыть direct-IP sockets/subprocess clients.
- Следующая проверка: внедрить reusable no-network settings/test guard внутри целевого process, добавить regression test с попыткой loopback/external socket и allowlist только для disposable local MariaDB при соответствующем gate.

### DJ6-CMD-001 - Нет import/parser smoke для non-DTF custom management commands

- Статус: `подтверждено как coverage gap`; предварительный приоритет: `P2`.
- Область: management commands всех не-DTF приложений; строго исключенный bridge command в подсчет не включен.
- Доказательство: Stage 0 inventory насчитывал 138 command modules после исключения DTF-named/DTF paths. После добавления `measure_stage4_baseline.py` и `check_ig_gemini_metadata_health.py` текущий inventory насчитывает 140 non-DTF modules; exact-count smoke импортирует все `140/140` `Command` classes, строит argparse parser, не вызывает `handle()` и не видит failures при заблокированной сети. `manage.py check` сам по себе этот contract не проверяет.
- Что даст: дешево ловит удаленные Django/Python imports, syntax/import-time side effects и сломанные `add_arguments()` до cron/deploy.
- Риск и ограничения: импорт command module может сам иметь опасный import-time side effect; smoke должен сначала обнаруживать и запрещать такой pattern, не вызывать `handle()` и не обращаться к production DB/network.
- Следующая проверка: вынести этот allowlist/import-parser smoke в отдельный no-network CI gate, а DTF bridge оставить отдельной исключенной проверкой.

### DJ6-TEST-002 - Полный suite еще не является зеленым upgrade gate

- Статус: `подтверждено`; предварительный приоритет: `P1` как блокер строгого CI, не как утверждение о Django-регрессии.
- Область: полный non-DTF regression suite и test infrastructure.
- Доказательство: read-only прогон upgrade-ветки собрал 6060 tests, из них 65 failures и 47 errors. Targeted dependency/compatibility subset (29 tests), Django check и GitHub Actions на audited SHA прошли; причины полного suite еще не классифицированы относительно Django 5.2 baseline.
- Что даст: разделение реальных Django 6.1 regressions, старого baseline debt, test-environment gaps и случайных external assumptions; позволит поэтапно сделать общий PR gate обязательным.
- Риск и ограничения: нельзя считать все 112 проблем последствиями upgrade или исправлять их одним массовым change; нужен одинаковый shard/fixture на 5.2 и 6.1.
- Следующая проверка: кластеризовать failures/errors по root cause и app, повторить каждый cluster на зафиксированном Django 5.2 baseline, занести только delta в compatibility-fix queue, а существующий baseline debt - в отдельный backlog.

### DJ6-SITE-001 - Полное non-DTF покрытие импортов, URL, шаблонов и статических файлов

- Статус: `подтверждено`; предварительный приоритет: `P1` как coverage baseline.
- Область: 24 non-DTF installed apps/интеграции, storefront, management, finance, warehouse, orders, accounts, reviews и product_catalog; DTF URLconf, модели, команды и статика исключены.
- Доказательство: под CPython 3.14.6/Django 6.1 `manage.py check --settings=test_settings` и `check --deploy` на production-like settings прошли без ошибок; четыре non-DTF URLconf резолвятся без resolver errors (1276/1031/950/897 leaf patterns); OpenAPI schema собрала 44 paths/44 operations; 265 non-DTF templates распарсились; 1472 Python-файла прошли `compile()`; 94 JavaScript-файла прошли `node --check`; 138 non-DTF management commands прошли import + `create_parser()` с заблокированной сетью; `async def`, `sync_to_async`, `database_sync_to_async` и async ORM-вызовы не найдены.
- Что дает: это воспроизводимая граница, которая показывает, что compatibility-аудит охватил весь активный Django surface, а не только storefront; любой будущий failure можно сравнить с этим baseline.
- Риск и ограничения: статический/import smoke не заменяет browser flows, real MariaDB, внешние webhook/provider calls, email delivery, cron overlap и production cache; DTF bridge `refresh_dtf_bridge_snapshot.py` намеренно не входит в 138 команд.
- Следующая проверка: превратить counts и исключения в no-network CI artifact, затем отдельно выполнить browser/live-MariaDB matrix для non-DTF субдоменов.

### DJ6-SEC-003 - CSRF-exempt non-DTF endpoints требуют отдельного contract-аудита

- Статус: `подтверждено как coverage gap`; предварительный приоритет: `P1`.
- Область: 26 non-DTF мест с `csrf_exempt` в Telegram/Monobank/Binotel/push/webhook, RUM/analytics и внешних integration endpoints (`accounts`, `finance`, `management`, `orders`, `storefront`, `warehouse`).
- Доказательство: статический inventory насчитал 26 decorators/wrappers; часть endpoints явно подписывает provider payload, часть принимает browser beacon или service-worker событие. Django 6.1 сам по себе не делает такие views безопаснее и не может определить, где CSRF действительно заменен подписью/rate-limit/origin check.
- Что даст: исключит случайный public write endpoint без аутентификации, replay protection или лимита и даст проверяемую карту причин каждого exemption.
- Риск и ограничения: нельзя массово убрать exemption: Monobank/Telegram/provider callbacks и `sendBeacon` могут перестать работать. Проверка должна быть read-only, с synthetic requests и без отправки внешних событий.
- Следующая проверка: для каждого endpoint зафиксировать authentication/signature/idempotency/rate-limit contract, добавить negative tests (missing/invalid signature, replay, wrong host) и browser beacon smoke для разрешенных случаев.

### DJ6-LIVE-001 - Production truth для MariaDB, Redis, cron и non-DTF routes подтверждена read-only

- Статус: `подтверждено`; предварительный приоритет: `P0` для release sign-off и отдельной post-deploy проверки.
- Область: production SSH, default MariaDB, cache/Redis, Passenger processes, cron, non-DTF management/finance/storage routes; DTF не трогать.
- Доказательство: read-only probe 2026-08-16 через утвержденный `sshpass -e` путь подтвердил Python `3.14.6`, Django `6.1`, DRF `3.18.0`, MariaDB `11.4.12-MariaDB`, non-DTF schema `127` InnoDB/`178` MyISAM, `max_user_connections=20`, `max_connections=150`, `wait_timeout=60`, file-based cache, 4 `lswsgi` процесса, отдельный Instagram daemon и 6 активных cron lines. Redis hostname получил `gaierror`; `redis-cli`, Celery, Supervisor и systemd-команды недоступны. Public smoke вернул ожидаемые ответы для `/`, `/healthz/`, `/cart/`, `/catalog/`, `/robots.txt`, `/sitemap.xml`, `/sitemap-products.xml`, `management.../bot/health/`, `fin.../health/` и `storage.../`; `/api/schema/` вернул ожидаемый staff-only `404`. DTF не проверялся.
- Что дает: live evidence теперь отделено от локального SQLite и historical notes; можно принимать решения о Django 6.1 backend, MariaDB constraints, connection budget, cache и cron на реальных данных.
- Риск и ограничения: probe не выполнял миграций, записей, очистки кэша, внешних provider-вызовов или server configuration changes. Read-only подтверждение не является доказательством успешного будущего deploy/restart; Redis/worker и database-engine debt остаются отдельными находками.
- Следующая проверка: перед каждым release повторять sanitized read-only preflight, а после разрешенного deploy отдельно подтвердить SHA, migrations/check, Passenger health и non-DTF browser/API matrix.

### DJ6-LIVE-002 - В production остаются 18 terminal `failed` Instagram analysis jobs

- Статус: `подтверждено`; предварительный приоритет: `P1` для reliability/CRM, не как регрессия Django 6.1.
- Область: `management.IgConversationAnalysisJob`, `/bot/health/`, `run_instagram_bot`, `reconcile_ig_analysis_jobs`; DTF исключен.
- Доказательство: read-only production query 2026-08-16: всего 298 jobs, из них `done=107`, `failed=18`, `skipped=173`, без `pending/processing`; `/bot/health/` сообщает `analysis_failed=18` при `analysis_pending=0` и working daemon. 17 failed jobs (IDs `3,5,6,8,52,114,115,117,121,125,126,127,128,140,151,152,153`) созданы в диапазоне `2026-07-23`--`2026-07-30` UTC и содержат `CallAIAnalysisError`/Gemini quota/HTTP 429 exhaustion; один job (ID `292`) создан `2026-08-06 14:48 UTC` и завершился `stale_lease_retry_exhausted`. Последняя дата `failed` — `2026-08-06 14:51:59 UTC`; это исторические terminal rows, а не активный backlog.
- Что дает: reconciliation/recovery для этих строк позволит отделить реально потерянный анализ от ожидаемо terminal failure, убрать постоянный degraded-сигнал health и сделать quota/lease failure observable для будущего worker/task backend.
- Риск и ограничения: нельзя массово повторять Gemini-вызовы или менять статусы в production без правил idempotency, quota budget и manager approval; старые failed rows могут намеренно сохраняться для аудита. `reconcile_ig_analysis_jobs` по умолчанию изменяет durable queue, поэтому сначала нужен dry-run или disposable copy.
- Следующая проверка: добавить read-only report/dry-run по ID, причине, attempts и last_error; затем на копии проверить bounded retry/backoff и только после review выполнить адресную reconciliation с доказательством новых snapshots и отсутствия дублей внешних side effects.

### DJ6-TEST-003 - Product video schema test расходится с текущим canonical Schema.org contract

- Статус: `подтверждено как baseline debt, не регрессия Django 6.1`; предварительный приоритет: `P1` для regression gate.
- Область: `twocomms/storefront/tests/test_product_video.py:98-110`, `twocomms/storefront/seo_utils.py:1209-1240`, Product JSON-LD.
- Доказательство: `ProductVideoSchemaTests.test_schema_embeds_video_object` ожидает `schema["video"]`, но текущий генератор намеренно кладет `VideoObject` в `schema["subjectOf"]`, потому что `video` не является валидным свойством `Product`. Один и тот же failure воспроизводится в serial и `--parallel 2` запуске под CPython 3.14.6/Django 6.1; ошибка возникает на assertion ключа, а не в ORM/тестовом runner. При failure фактический payload содержит `subjectOf.@type == "VideoObject"`, `embedUrl` и `contentUrl`.
- Что дает: синхронизация теста с SEO-контрактом не даст ложный красный upgrade gate и одновременно сохранит проверку валидной Schema.org связи; отдельная Google/Schema.org validation подтвердит rich-result semantics.
- Риск и ограничения: нельзя просто заменить ключ, если внешние consumers ожидают старый JSON-LD; сначала проверить production HTML/structured-data snapshots и search-console contract. Не возвращать невалидное `Product.video` ради зеленого теста.
- Следующая проверка: обновить assertion на `subjectOf`, добавить проверку вложенного `VideoObject` и schema validation fixture, затем повторить serial/parallel targeted tests.

### DJ6-DOC-002 - Current-facing документация и инструкции еще расходятся с Django 6.1

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: `README_ARCHITECTURE.md`, `twocomms/wsgi.py`, старые runbooks и инструкции, которые называют Django 5.2.6/Python 3.x или используют bare `python`.
- Доказательство: current `main`, CI, локальная `.venv` и production уже используют CPython 3.14.6/Django 6.1, тогда как active architecture README и часть WSGI-комментариев всё ещё называют старые версии.
- Что даст: синхронизация current-facing документации уменьшит повторный запуск проверок под старым runtime и риск silent downgrade.
- Риск и ограничения: исторические incident reports и планы не переписывать; обновлять только current-facing docs после merge/deploy.
- Следующая проверка: обновить README/runbook и проверить ссылки на production Python 3.14 virtualenv; исторические incident reports не переписывать.


## Live-аудит production-логов 2026-08-19

Ниже зафиксированы только сигналы, подтвержденные свежей read-only сверкой с
MariaDB/HTTP/process state. Старые cumulative-логи не считаются текущим
инцидентом без нового воспроизведения.

- [x] **Schema drift `storefront_productfitoption.default_product_identity` — закрыто на сервере.**
  В старом `stderr.log` были 1054 на `/`, каталогах и PDP. Read-only probe
  подтвердил физическую generated-колонку, `uniq_default_fit_product` и
  migration `storefront.0097_mariadb_generated_uniqueness`; `SHOW CREATE TABLE`
  соответствует модели. В access archive и `stderr.log` подтверждены ровно
  `45` пользовательских HTTP 500 в окне `18:31:48-18:48:24 EEST`
  (одна и та же причина, `1054 Unknown column`, а не 45 разных дефектов).
  Последняя запись migration была применена в `18:48:34 EEST`; после этого
  повторный smoke home/catalog/tshirts/PDP вернул `200`, новых application
  500 в delta-логе не появилось. В рамках этого аудита `ALTER TABLE` и
  ручной `migrate` не выполнялись.

- [x] **Schema drift `product_catalog_imageoptimizationjob.lease_token` —
  исторический, не текущий.** Production MariaDB содержит `lease_token`
  (`varchar(32) NOT NULL`), InnoDB и индексы; migrations `0013`, `0014`,
  `0015` применены. Нового 500-воспроизведения нет.

- [x] **`IgClient` `UnboundLocalError` — исправление реализовано.** Повторный
  локальный импорт внутри `_process_one_inside_reply_boundary` создавал
  локальную binding и ломал commerce projection. Удален только внутренний
  импорт, добавлен regression assertion; focused commerce suite зеленый.
  Коммит: `eabcec27b` (patch-id совпадает с `fb9ee1eaa`, повторно cherry-pick
  не требуется).

- [x] **SQLite fallback Instagram daemon — предотвращен fail-closed guard.**
  При `DEBUG=False` и SQLite `run_instagram_bot --once/--ensure/--forever`
  теперь завершается до polling/spawn с понятным `CommandError`; локальный
  `DEBUG=True` SQLite режим сохранен. Regression suite `24/24`. Коммит:
  `b3a1964da` (patch-id совпадает с исходным scoped commit `1565a12a2`).

- [x] **GeoIP2 warning — исправление реализовано.** При отсутствующем или
  пустом `GEOIP_PATH` конструктор GeoIP2 не вызывается, внешний API не
  запускается, запрос остается fail-soft. Для валидной `.mmdb` базы путь
  передается явно. Regression suite покрывает missing/valid/empty cases.
  Коммиты: `97dc7bab7` + `368f395bf` + `1ac8fb266`; первый patch-id совпадает
  с агентским `565825ae3`, два последних уточняют проверку имен баз.

- [x] **Compressor stale-manifest — текущего дефекта нет.** На production
  `CACHE/manifest.json` существует, новее всех watched sources, assets
  отдаются `200`, свежий import production settings с `-W error::RuntimeWarning`
  проходит без warning, HTML не содержит неразрешенных compressor tags.
  На границе reload кратко записался stale-manifest warning, но после
  `collectstatic` -> `compress --force` manifest был создан (`701` байт,
  mtime `23:35:43 EEST`) и runtime gate снова включил offline mode. Это
  подтверждает корректность fail-open guard, а не новый 500; код менять не
  нужно. В release runbook сохраняется порядок `collectstatic` -> `compress`
  -> Passenger reload.

- [x] **`DisallowedHost` для `mail.*` — внешний шум, не misconfiguration.**
  Не добавлять эти hostnames в `ALLOWED_HOSTS`; DTF и host policy не менять.

- [x] **`Too many connections` и Passenger SIGKILL/SIGTERM — исторические
  записи.** Свежий runtime использует MariaDB, `CONN_MAX_AGE=0`, connection
  budget в пределах лимита; новые GET не воспроизводят эти ошибки. После
  marker `tmp/restart.txt` (`23:35:44 EEST`) новый LSAPI master продолжил
  обслуживать запросы, а пачка `SIGKILL` относится к его child recycle/idle
  reap; host memory свободна, LVE/dmesg недоступны, поэтому OOM не доказан.
  Новых worker/process или повышения connection limits не внедрять без
  измерения.

- [x] **Telegram error alerts и periodic jobs — сверены.** В rotated/app
  `stderr.log` найдены исторические алерты на 500 (1054 schema drift),
  GeoIP2, SQLite fallback и `IgClient`, а также старые transport timeout,
  `invalid_parse_entities` и `OSError`; это не новые события текущего
  runtime. Сегодня дополнительно зафиксированы `32` bounded Telegram
  transport fallback (`timeout`), но ни одного нового `sendMessage`/cron
  failure: handler намеренно ограничен 2 секундами и пишет fallback в
  `stderr`, не превращая транспортный таймаут в application 500. В свежем
  срезе `order_telegram_reconcile`, IG checkout/fulfillment и durable cron
  показывают `failed=0`/`errors=0`; Telegram-alert handler не отключался и не
  маскировал ошибки.

- [x] **Client-side error inventory — классифицирован.** `client_errors.log`
  содержит браузерные/сторонние сигналы (`window.webkit.messageHandlers`,
  `M_ID`, `Script error`, `readonly property`) без server traceback. Они не
  доказывают Django/MariaDB дефект. Единственный owned deterministic signal —
  `isStatsTab` ReferenceError в странице промокодов — исправлен DOM-guard,
  добавлен regression test; commit `80ced7a04`.

- [ ] **Runtime minor-version drift.** Read-only production wrapper сейчас
  сообщает CPython `3.14.7`, тогда как project contract фиксирует `3.14.6`.
  Это не вызвало текущих 500, поэтому runtime не переключался; требуется
  отдельное согласование wheel/CloudLinux binding перед изменением версии.

- [x] **Единственный post-restart `503 /csp-report/` — upstream, не Django.**
  Access log содержит одну строку `23:42:10 EEST`, размер ответа `3678` байт;
  `csp_report()` и rate-limit middleware имеют только `204`/`429` ветки,
  traceback в `django.log`/`stderr.log` отсутствует, а соседние CSP POST
  получили `204` и каталог `200`. Запрос не дошел до `django.request`, поэтому
  TelegramAlertHandler его не отправлял; код менять не нужно.

- [x] **Сегодняшние provider errors классифицированы без ложных фиксов.**
  Gemini `HTTP 400 INVALID_ARGUMENT` и Clarity `429` являются ответами
  провайдеров с существующим bounded/stale fallback; Nova Poshta timeout-строки
  оказались историческими (`2026-07-15`), а хвост `2026-08-19` не содержит
  timeout/error. Ни один класс не дал нового owned traceback или пользовательского
  500, поэтому внешние API не дергались и код не менялся.

- [x] **Sentry/Telegram error stream за 2026-08-20 сверена.** В production
  checkout и доступной домашней области нет Sentry/Seder event-файлов или
  отдельного SDK; фактический канал серверных алертов —
  `TelegramAlertHandler` (`django.request`) с bounded direct Bot API request.
  Накопленный `stderr.log` содержит `32` fallback timeout, `134` incident lines
  и старые 500/503 без timestamp, поэтому эти числа нельзя считать сегодняшним
  incident count без access-log correlation. В access-log окне `00:00-00:15`
  EEST подтвержден ровно один `503 GET /bot/api/clients/?view=all&page=1`
  в `00:04:06`, при `0` новых `500/502/504`; upstream-ответ был `3678` байт,
  traceback/Django view отсутствуют, соседние запросы успешны. Это warm-up/
  upstream сигнал, а не доказанная application ошибка. `sendMessage` и
  cron failure не подтверждены. SQLite `no such table` в `ig_bot.log` и три
  `IgClient` ULE-записи в MariaDB имеют исторические даты до deployed fixes;
  текущий daemon стартует через CloudLinux Python wrapper и MariaDB, последние
  события — `gemini_ok`/`reply_sent`/`daemon_start`. Код Telegram-alert handler
  без доказанного свежего application failure не менялся.

- [x] **Nova Poshta city lookup для Latin/цифровых запросов — исправлено.**
  `/cart/delivery/cities/` отправлял `boulder`, `new york`, `coral gables` и
  цифровые значения в legacy API, который отвечал `CityName has invalid
  characters`; storefront превращал это в HTTP `502`. Сервис теперь до
  provider call принимает только кириллические буквы, сохраняет aliases
  `Kyiv/Kiev -> Київ`, а неподдерживаемый ввод возвращает пустой список (200
  с `items=[]`). Добавлены regression cases, внешние запросы для фикса не
  выполнялись; свежий Nova cron показывает успешные `No orders with tracking
  numbers`, а все `ReadTimeout` относятся к историческому запуску 2026-07-15.

- [x] **Cron environment explicitness — реализовано.** Watchdog и все managed
  Instagram periodic commands теперь явно задают `DJANGO_ENV=production` и
  `DJANGO_SETTINGS_MODULE=twocomms.production_settings` до `flock`/Python;
  старые unprefixed loose owner-строки остаются распознаваемыми для безопасной
  миграции installer. Focused cron suite `26/26`, commit `e0fe8733c`; DTF не
  затронут.

- [x] **Объединенный локальный gate.** На CPython `3.14.6` / Django `6.1`
  прошли `127/127` focused Django tests (commerce, daemon, templates, GeoIP,
  UTM) и `26/26` cron installer tests; `bash -n`, `py_compile` и оба
  `git diff --check` завершились без ошибок.

- [x] **Release gate для этого log-аудита.** Production, локальный `main` и
  `origin/main` подтверждены на `30c261306898c666d92cd8bfb098875aa6b344f4`.
  SSH proof подтвердил Django `6.1`, MariaDB `11.4.12`, `ENGINE=mysql`, strict
  mode/InnoDB, колонку `default_product_identity`, migration `0097`, manifest
  и `-W error::RuntimeWarning`; post-restart access delta содержит `0`
  application 500. Этот чекбокс отражает уже выполненный deploy/reload, а не
  обещание будущего rollout.

## Историческая сводка после полной read-only проверки

- Всего записей: 83 уникальных ID; дублей нет.
- Реализовано или подтверждено с уточненным типом сигнала/границы: 72 записи.
- Отложено до отдельного implementation/schema/worker этапа: 7 записей.
- Заблокировано правами, архитектурой или версией MariaDB: 3 записи.
- Неактуально для текущего runtime: 1 запись (`DJ6-BASE-006`, async-кода нет).
- Статус `кандидат` после этой проверки не оставлен: каждая исходная гипотеза переведена в доказанный backlog, отложенный пункт, блокер или неактуальный пункт.
- Не все 83 улучшения внедрены: реализованные Stage 0-2 отмечены выше, остальные остаются подтвержденным backlog, отложенными, заблокированными или неактуальными пунктами.
- Эта числовая сводка относится к исходному audit snapshot. После нее Stage 6
  закрыл `DJ6-BASE-005`, `DJ6-SRV-001` и `DJ6-TASK-001` через ограниченный
  MariaDB/cron backend; актуальная evidence указана в
  `docs/qa/django61-stage6-production-activation.md`.

## Отдельный список блокеров и неизвестных

- Повторный live SSH probe перед следующим release обязателен; текущий read-only снимок уже подтвержден (`DJ6-LIVE-001`), но он не заменяет post-deploy проверку.
- Redis DNS/ACL и worker/supervisor capability остаются NO-GO: hostname не
  разрешается, `redis-cli`/Celery/Supervisor/systemd недоступны. Это больше не
  блокирует текущий MariaDB durable cron backend, но остается отдельным
  вопросом для будущего Redis/Celery rollout; `ImmediateBackend` guard
  сохраняется (`DJ6-TASK-002`).
- Какие модели и таблицы безопасно перевести на InnoDB и где допустимы DB-level actions; MyISAM нельзя считать транзакционно безопасным (`DJ6-SRV-003`, `DJ6-BASE-002`, `DJ6-DB-001`).
- Production engine/version/FK graph и connection budget подтверждены текущим read-only снимком; любые schema/engine изменения требуют отдельной репетиции на копии, локальный SQLite остается только быстрым тестовым слоем.
- Browser-поверхность платежей, checkout, webhooks, CSP violations, email delivery и внешние provider calls требует отдельной staging/live matrix; текущий import/static/schema smoke не заменяет эти сценарии.
- Async runtime сейчас отсутствует; повторный аудит нужен только при появлении async view/worker (`DJ6-BASE-006`).
- 18 исторических failed Instagram analysis jobs требуют отдельной dry-run/reconciliation процедуры; production rows не менять в рамках этого inventory (`DJ6-LIVE-002`).

## Источники и дата аудита

- Старт аудита: 2026-08-16, Europe/Kiev.
- Repository: `/Users/zainllw0w/TwoComms/site`.
- Audit worktree: `/Users/zainllw0w/.config/superpowers/worktrees/site/dj6-update-all-audit`.
- Основная документация: официальные Django release notes/database/queryset/async docs через Context7; использованы `/django/django` snippets для fetch modes, MAILERS, Tasks, CSP, partials/querystring, admin, cache-cookie changes и deprecations; точные URL добавлены к каждой находке.
