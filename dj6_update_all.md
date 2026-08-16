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

- Git baseline: `37ced3a4553d4068c6cb1ad93f38e641e3ba41a0` (`origin/main` на момент старта аудита).
- Runtime: Python 3.14.6, Django 6.1, Django REST Framework 3.18.0.
- DB runtime: локальный `mysqlclient`/`MySQLdb` 2.2.8; production read-only probe подтвердил MariaDB `11.4.12-MariaDB`. В production non-DTF schema насчитывается 305 model tables: 127 InnoDB и 178 MyISAM. Runtime и базы исключенного субдомена в этом аудите не проверяются.
- После перехода выполнены lock verification, `pip check`, `manage.py check`, `migrate --check`, `collectstatic`, `compress` и Passenger reload marker.
- Live smoke после перехода: public `/healthz/`, `/`, `/cart/` и management `/bot/health/` вернули HTTP 200.
- Полный репозиторный suite не считать доказательством зеленого состояния: ранее обнаружены несвязанные baseline-сбои окружения/кастомного print. Их не исправлять в рамках этого inventory; DTF исключен.
- Production-цифры ниже получены 2026-08-16 через утвержденный read-only SSH-путь с caller-provided credential; пароль и его значение в документ не записываются. Probe не выполнял миграций, записей, очистки кэша, внешних provider-вызовов или DTF-действий. Перед любым release mutation нужны отдельные post-deploy checks.

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
  no-network system check, реальный migration drift check, warning gate,
  `138/138` management command parsers, static/compressor/WhiteNoise pipeline и
  sanitized non-DTF inventory.
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
- Stage 1 начат подготовительными explicit SHA-1, `MAILERS` и `load_module()`
  изменениями, но соответствующие пункты остаются открытыми до полных
  acceptance matrices.

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
| Async, Celery, cron, Redis, фоновые задачи и параллелизация | delegated async/server audit | проверено; worker/Redis production заблокированы |
| HTTP, middleware, templates, forms, admin, DRF, security | primary repository sweep | проверено локально; browser/live gaps отмечены |
| Приложения и субдомены, кроме DTF | primary repository sweep | проверено локально |
| Production MariaDB, Passenger, права, observability | server audit + Stage 0 release | read-only inventory проверен; `storefront.0096` применена; post-deploy matrix зеленая |

## Начальные находки после перехода

### DJ6-BASE-001 - Не включены новые model field fetch modes

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: ORM всего storefront/management/accounts/reviews/finance; DTF исключить.
- Доказательство: compatibility upgrade намеренно оставил `fetch_mode`/`FETCH_PEERS` выключенными; static inventory нашел 126 вызовов `only()`/`defer()` в non-DTF Python-коде. На динамической SQLite-модели Django 6.1 `FETCH_PEERS` загрузил поле для двух peer-инстансов одним дополнительным запросом, а `FETCH_RAISE` корректно выбросил `FieldFetchBlocked`.
- Что может дать: меньше round-trip при чтении deferred-полей, предсказуемее загрузка peer-полей, меньше N+1 и лишних payload в тяжелых списках.
- Риск: изменение числа SQL-запросов и памяти, async-код не может лениво догружать deferred fields, возможна несовместимость с `select_related`, сериализаторами и шаблонами.
- Следующая проверка: выбрать 2-3 узких read-only projections, снять query-count/latency на representative flows и внедрять `FETCH_PEERS` только там, где parity доказана.

### DJ6-BASE-002 - Не исследованы database-level `on_delete` actions

- Статус: `отложено`; предварительный приоритет: `P2`.
- Область: все модели с ForeignKey/OneToOne/мягким удалением; DTF исключить.
- Доказательство: в non-DTF inventory 566 relation fields (552 FK/OneToOne и 14 ManyToMany): для прямых связей `CASCADE` 222, `SET_NULL` 195, `DO_NOTHING` 78, `PROTECT` 57; `db_constraint=False` у 179 прямых relation fields. Live MariaDB probe подтвердил 178 MyISAM/127 InnoDB, только 39 фактических FK и `DELETE_RULE=RESTRICT` у них. Поэтому DB-level action остается отдельным schema этапом, а не включается автоматически.
- Что может дать: часть целостности и каскадных действий может выполняться на уровне MariaDB, меньше Python-side work и race windows.
- Риск: существующие MyISAM-таблицы, исторические данные, разные семантики `PROTECT`/`RESTRICT`/`SET_NULL`, миграции и irreversible cascade.
- Следующая проверка: инвентаризация engine/constraints/удалений и read-only dry-run на копии схемы; production mutation не выполнять.

### DJ6-BASE-003 - Не исследован новый `MAILERS` API

- Статус: `подтверждено`; предварительный приоритет: `P3`.
- Область: email notifications, password reset, checkout/management mail paths.
- Доказательство: `rg` нашел проектные `EmailMessage`/`EmailMultiAlternatives`/`send_mail` call sites и deprecated `EMAIL_*` settings; документация Django 6.1 подтверждает `MAILERS` и `using=` как replacement. Все вызовы остаются sync и не дают очередь сами по себе.
- Что может дать: явное разделение backend/политик отправки, изоляция ошибок и более управляемые тестовые/production mail routes.
- Риск: shared-hosting SMTP credentials, `fail_silently`, шаблоны, retry/idempotency и наблюдаемость доставки.
- Следующая проверка: найти все `send_mail`/`EmailMessage`/`EmailMultiAlternatives`, измерить фактические backend и delivery failure semantics.

### DJ6-BASE-004 - MariaDB system-check warnings требуют отдельного решения

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: `reviews.ReviewVote`, `storefront.ProductFitOption`, `storefront.WebPushDeviceSubscription.endpoint`.
- Доказательство: live Django 6.1/MariaDB probe подтвердил, что conditional unique constraints не созданы в `reviews_reviewvote` и `storefront_productfitoption`; также остается warning для unique `CharField` с `max_length > 255`. Read-only duplicate scan по этим двум контрактам вернул нули, но отсутствие дублей не заменяет реальное ограничение.
- Что может дать: восстановление реально гарантируемой уникальности и отсутствие ложного ощущения, что ограничения действуют.
- Риск: существующие дубли, миграции на больших таблицах, изменение API ошибок и конкурирующие записи.
- Следующая проверка: read-only duplicate scan, сравнение фактических `SHOW CREATE TABLE` с моделями, затем отдельная миграционная стратегия.

### DJ6-BASE-005 - Celery/Redis capability не доказана production runtime

- Статус: `заблокировано правами/окружением`; предварительный приоритет: `P1` для архитектурного решения, не для немедленного включения.
- Область: фоновые задачи, cron, management commands, Redis broker, Passenger workers; DTF исключить.
- Доказательство: live production probe получил `gaierror` для настроенного Redis hostname; `redis-cli`, пакет `celery`, `supervisorctl` и systemd-команды на сервере недоступны, а `TASKS.default` равен `django.tasks.backends.immediate.ImmediateBackend`. Celery/worker capability нельзя считать рабочей только по наличию зависимостей в lock.
- Что может дать: очереди, retries, параллелизация тяжелых задач и уменьшение request-path latency, если broker/worker реально разрешены хостингом.
- Риск: shared hosting permissions, отсутствие daemon/supervisor, дубли cron и Passenger, потеря задач, PII в broker, стоимость Redis и отсутствие graceful shutdown.
- Следующая проверка: read-only DNS/TCP/auth/ACL probe для Redis, инвентаризация cron/Passenger/process limits, затем маленький no-send canary в отдельной очереди.

### DJ6-BASE-006 - Deferred/async access boundaries не проверены по всему сайту

- Статус: `неактуально для текущего runtime`; предварительный приоритет: `P1`.
- Область: async views, DRF, serializers, background commands и любые `defer()`/`only()`.
- Доказательство: static search по всем non-DTF Python-файлам не нашел `async def`, `sync_to_async`, `database_sync_to_async` или async ORM methods. Deferred fields используются только в sync-коде; async boundary для текущего runtime не существует.
- Что может дать: устранение runtime `SynchronousOnlyOperation`, предсказуемые async query plans и безопасная подготовка к fetch modes.
- Риск: скрытый доступ к полю в serializer/template/property, разные DB aliases и MyISAM/InnoDB поведение.
- Следующая проверка: повторить static gate при появлении первого async view/worker; до этого не добавлять async-only mitigation и не считать `only()` сам по себе async-багом.

## Findings log

Новые записи добавлять ниже по мере получения отчетов агентов и production evidence. Дубли объединять по ID, сохраняя все доказательства.

## Матрица релизных изменений 5.2 -> 6.0 -> 6.1

Ниже собраны функции релизов, которые пересекаются с активным non-DTF кодом, тестами, конфигурацией или серверным runtime. Это не разрешение на автоматическое внедрение: `не используется` означает, что поиск не нашел применимого контракта, а `отложено` - что для функции нужен отдельный schema/worker/UX этап.

| Версия | Функция | Проверка в проекте | Итоговый ID/статус |
| --- | --- | --- | --- |
| 5.2 | `CompositePrimaryKey` | Composite PK в non-DTF моделях не найден; текущие связи и admin рассчитаны на обычный `pk`. | Не используется; отдельной миграции не нужно. |
| 5.2 | Новые ORM/model API и compatibility checks | Весь model graph построен под Django 6.1; фактический DB constraint/engine parity вынесен в отдельные проверки. | `DJ6-SITE-001`, `DJ6-DB-002` - подтверждено. |
| 6.0 | Django Tasks contract (`@task`, `.enqueue()`) | API доступен, но production backend - `ImmediateBackend`, worker/scheduler отсутствует. | `DJ6-TASK-001`, `DJ6-TASK-002` - подтверждено как архитектурный разрыв. |
| 6.0 | Database-level `on_delete` (`DB_CASCADE` и аналоги) | Нужны InnoDB и реальные FK; production содержит 178 MyISAM и только 39 FK. | `DJ6-BASE-002`, `DJ6-DB-001`, `DJ6-SRV-003` - отложено. |
| 6.0 | Template partials (`partialdef`/`partial`) | 265 шаблонов распарсились; повторяющиеся full/fragment пары не переведены. | `DJ6-TPL-001` - подтвержденная opportunity. |
| 6.0 | `{% querystring %}` | Найдены ручные `request.GET.urlencode` и pagination links. | `DJ6-TPL-002` - подтверждено. |
| 6.0 | HTTPS default для `URLField` | Runtime `URLField().assume_scheme == "https"`; найдено 16 model URLFields и 1 explicit form field. | `DJ6-FORM-001` - подтверждено. |
| 6.0 | Forkserver/parallel test runner | Изолированный `--parallel 2` проходит, полный suite еще не green. | `DJ6-TEST-001` - отложено. |
| 6.0 | Keyword-only mail API и новые email deprecations | Старые `fail_silently`/email kwargs используются во множестве call sites. | `DJ6-EMAIL-002` - подтверждено. |
| 6.0 | PBKDF2 iteration increase до 1,200,000 | Пароли используют стандартный hasher; CPU/rehash behavior требует измерения. | `DJ6-AUTH-001` - подтверждено. |
| 6.0 | Встроенная CSP middleware/policy base | Проект формирует CSP вручную; inline/eval policy не переведена. | `DJ6-CSP-001` - подтверждено. |
| 6.1 | Model field fetch modes (`FETCH_PEERS`, `FETCH_RAISE`) | 126 `only()`/`defer()` вызовов; локальный динамический smoke подтвердил оба режима. | `DJ6-BASE-001`, `DJ6-ORM-001..012` - подтверждено, внедрение отложено до query parity. |
| 6.1 | Named `MAILERS` и `using=` | Настройки и call sites используют deprecated `EMAIL_*`/старую mail policy. | `DJ6-EMAIL-001` - подтверждено. |
| 6.1 | CSP nonce attribute и `security.W027` | Базовая CSP есть вручную, nonce/report-only contract отсутствует. | `DJ6-CSP-001` - подтверждено. |
| 6.1 | Signed-cookie salt derivation | `SIGNED_COOKIE_LEGACY_SALT_FALLBACK=False`; custom salts отдельно инвентаризированы. | `DJ6-COOKIE-001` - подтверждено. |
| 6.1 | PBKDF2 iteration increase до 1,500,000 | Следующий login может rehash старый пароль; нагрузка не измерена. | `DJ6-AUTH-001` - подтверждено. |
| 6.1 | `UUID4`/`UUID7` database functions | MariaDB `11.4.12` ниже официального порога availability `11.7`. | `DJ6-ORM-014` - заблокировано версией БД. |
| 6.1 | Admin `list_select_related` behavior/deprecation | 124 non-DTF admin зарегистрированы; deprecated project `True` не найден, vendor warning есть. | `DJ6-ADMIN-001`, `DJ6-COMPAT-002` - подтверждено. |
| 6.1 | Strict Base64 parsing | В credential/provider paths есть permissive `b64decode`; strict table-driven smoke пройден. | `DJ6-SEC-002` - подтверждено. |
| 6.1 | Cache-key/signed-cookie compatibility changes | File cache и краткоживущие cookies требуют controlled deploy miss/rollout. | `DJ6-CACHE-001`, `DJ6-COOKIE-001` - подтверждено. |
| 6.1 | `salted_hmac()` explicit algorithm requirement | IG payment digest не передает `algorithm`; текущий default SHA-1 меняется в Django 7. | `DJ6-SEC-001`, `DJ6-WARN-001` - подтверждено. |
| 6.1 | QuerySet `values().in_bulk()` и `totally_ordered` | Найдены два узких mapping path и несколько недетерминированных paginator ordering. | `DJ6-ORM-009..011` - подтверждено. |
| 6.1 | Strict model/parser validation и текущие checks | `manage.py check`, import/parser/template/static smoke пройдены; baseline video test и migration drift остаются отдельно. | `DJ6-SITE-001`, `DJ6-MIG-002`, `DJ6-TEST-003` - подтверждено как coverage/baseline debt. |

Матрица закрывает найденные пересечения релизов с сайтом. Функции, не имеющие model/HTTP/template/worker/DB применения в non-DTF коде, не превращаются в искусственные backlog-пункты.

### DJ6-EMAIL-001 - Перейти с deprecated `EMAIL_*`/`EMAIL_BACKEND` на Django 6.1 `MAILERS`

- Статус: `подтверждено`; предварительный приоритет: `P1` как обязательная подготовка к Django 7.0.
- Область: общая конфигурация email и все не-DTF пути отправки: `twocomms/twocomms/settings.py:961-980`, `twocomms/orders/email_receipt.py:369-378`, `twocomms/storefront/services/restock.py:361`, `twocomms/storefront/management/commands/send_utm_report.py:140-155`, `twocomms/management/views.py:6597-6605`, `6901-6910`, `7273-7281`, `8224-8226`.
- Доказательство: Django 6.1 официально пометил `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_SSL`, `EMAIL_USE_TLS`, `EMAIL_TIMEOUT` и связанные настройки deprecated; текущий проект использует именно их. `MAILERS` позволяет именованные backend-конфигурации и аргумент `using=`. Источник: <https://docs.djangoproject.com/en/6.1/releases/6.1/#mailers> и <https://docs.djangoproject.com/en/6.1/howto/mailers-migration/>.
- Что даст: уберет накопление deprecation debt, подготовит проект к Django 7.0, позволит развести транзакционные письма, отчеты и потенциальные маркетинговые отправки по разным backend/credentials/timeout-политикам и тестировать их независимо.
- Риск и ограничения: нельзя механически переносить SMTP-параметры без проверки cPanel SSL/TLS, `DEFAULT_FROM_EMAIL`, поведения console backend в `DEBUG`, маскирования секретов и фактической доставки. Именованные mailers не являются очередью и сами по себе не дают retry/idempotency.
- Следующая проверка: построить полный call graph email, определить алиасы (`default`, `transactional`, `reports`), проверить новый `mail.E001` deployment check и сделать no-send тестовые backend-проверки до переключения production SMTP.

### DJ6-EMAIL-002 - Удалить deprecated `fail_silently` и проверить новые ошибки email API

- Статус: `подтверждено`; предварительный приоритет: `P1`.
- Область: `EmailMessage.send()`/`EmailMultiAlternatives.send()` и `send_mail()` во всех не-DTF приложениях; конкретные вызовы перечислены в `DJ6-EMAIL-001`, дополнительно `twocomms/orders/management/commands/recover_checkouts.py:105-110`.
- Доказательство: в коде есть многочисленные `msg.send(fail_silently=False)` и `send_mail(..., fail_silently=False)`. Django 6.1 deprecated `fail_silently`, `connection`, `auth_user`, `auth_password` и `get_connection()`; сочетание явного `connection` с частью старых аргументов уже может давать `TypeError`. Django 6.0 также требует keyword-аргументы для необязательных параметров. Источник: <https://docs.djangoproject.com/en/6.1/releases/6.1/#email> и <https://docs.djangoproject.com/en/6.1/releases/6.0/#positional-arguments-in-django-core-mail-apis>.
- Что даст: явную политику обработки SMTP-сбоев вместо скрытого флага, одинаковые исключения для HTTP, cron и будущих background workers, готовность к Django 7.0.
- Риск и ограничения: простое удаление `fail_silently=False` может изменить ожидаемую обработку исключений в recovery-командах и административных формах; для каждого пути нужно решить `raise`, логирование, retry или durable outbox.
- Следующая проверка: для каждого вызова зафиксировать владельца retry/idempotency, добавить тесты SMTP exception path и проверить, нет ли кастомных email backend/subclass, принимающих лишние `**kwargs`.

### DJ6-CSP-001 - Заменить самописную CSP-строку на встроенный Django CSP с report-only и nonce

- Статус: `подтверждено`; предварительный приоритет: `P1`.
- Область: все не-DTF HTTP-субдомены; `twocomms/twocomms/middleware.py:271-289`, `twocomms/twocomms/settings.py:1271-1325` и продолжение `CONTENT_SECURITY_POLICY`, базовые шаблоны и inline-скрипты.
- Доказательство: проект вручную формирует один строковый `Content-Security-Policy` и выставляет его через `SecurityHeadersMiddleware`; policy содержит `'unsafe-inline'` и `'unsafe-eval'`. Django 6.0 добавил `ContentSecurityPolicyMiddleware`, `SECURE_CSP`, `SECURE_CSP_REPORT_ONLY`, контекстный процессор и per-view decorators; Django 6.1 добавил `csp_nonce_attr` и check `security.W027`. Источники: <https://docs.djangoproject.com/en/6.1/howto/csp/> и <https://docs.djangoproject.com/en/6.1/releases/6.1/#csp>.
- Что даст: структурированную и проверяемую policy, безопасное постепенное ужесточение через report-only, nonce для собственных inline assets, системные проверки и меньше риска ошибочно собрать заголовок строковой конкатенацией.
- Риск и ограничения: на сайте много analytics/pixel/GTM/Clarity/TikTok и inline-кода; немедленное удаление `'unsafe-inline'`/`'unsafe-eval'` может сломать checkout и аналитику. Нужна отдельная инвентаризация реально загружаемых origins и CSP reports по каждому субдомену; DTF не проверять.
- Следующая проверка: снять текущие headers и browser console violations для storefront/management/warehouse/finance, развернуть эквивалентную `SECURE_CSP_REPORT_ONLY`, добавить nonce context processor и только затем планировать enforce policy.

### DJ6-TASK-001 - Выбрать реальный backend для Django Tasks вместо ложного ощущения работающей очереди

- Статус: `подтверждено как архитектурный разрыв`; предварительный приоритет: `P1`.
- Область: `twocomms/twocomms/settings.py:1085-1102`, legacy `storefront/tasks.py`, `orders/tasks.py`, `management/tasks.py`, `warehouse/tasks.py`, cron-команды и тяжелые внешние вызовы; DTF исключить.
- Доказательство: настройки прямо называют Celery-конфигурацию мертвой и запрещают добавлять туда задачи; `TASKS` в проекте не настроен. Django 6.0 добавил стандартный task contract (`@task`, `.enqueue()`, validation/result API), но встроенные backend предназначены для разработки/тестов и Django не предоставляет worker. Источник: <https://docs.djangoproject.com/en/6.1/topics/tasks/>.
- Что даст: единый интерфейс постановки фоновых работ, возможность постепенно отвязать бизнес-код от Celery shim и выбрать подходящий внешний worker/backend после проверки прав хостинга. Снижает request latency только вместе с реально работающим durable worker.
- Риск и ограничения: `ImmediateBackend` в production не распараллеливает работу, `DummyBackend` ее не выполняет; без daemon/supervisor задачи будут теряться. Нельзя параллельно оставить cron/Celery/Django Tasks владельцами одной периодики без idempotency и lease.
- Следующая проверка: read-only capability matrix хостинга (Redis DNS/TCP/ACL, долгоживущий процесс, cron granularity, Passenger lifecycle), затем выбрать backend и одну безопасную canary-задачу без пользовательских side effects.

### DJ6-TPL-001 - Использовать Django template partials для повторно рендеримых фрагментов

- Статус: `подтверждено`; предварительный приоритет: `P3`.
- Область: storefront/management/finance/warehouse templates с большим числом `{% include %}` и AJAX/HTMX-подобных fragment responses; DTF исключить.
- Доказательство: Django 6.0 добавил `{% partialdef %}`, `{% partial %}` и синтаксис `template.html#partial_name`; в проекте новый API не используется, а 265 non-DTF template files успешно распарсились. `{% include %}` остается распространенным, поэтому это подтвержденная low-risk opportunity, а не ошибка.
- Что даст: компонент и его standalone fragment останутся в одном файле, уменьшится рассинхронизация full-page и AJAX-разметки, тестам будет проще рендерить конкретный фрагмент.
- Риск и ограничения: не каждый `include` стоит переносить; общие межстраничные компоненты по-прежнему лучше держать отдельными файлами. Нужно учитывать cached template loader и django-compressor.
- Следующая проверка: найти пары «одинаковая разметка в full response и fragment endpoint», оценить дублирование и выбрать 2-3 low-risk кандидата для отдельного benchmark/implementation этапа.

### DJ6-COOKIE-001 - Проверить совместимость старых подписанных cookies после смены salt derivation в 6.1

- Статус: `подтверждено`; предварительный приоритет: `P1` для бесшовного перехода пользователей.
- Область: общие session/messages cookies и custom signed payloads в `twocomms/twocomms/middleware.py:108-154`, `orders/nova_poshta_checkout.py:49-86`, `orders/telegram_status_links.py:25-43`, `storefront/views/ig_checkout.py:462-495`, `storefront/views/qr.py:122-245`, `management/views.py:270-272`, `8155-8183`.
- Доказательство: Django 6.1 изменил derivation salt для signed cookies и по умолчанию выключил `SIGNED_COOKIE_LEGACY_SALT_FALLBACK`; runtime подтвердил `SESSION_ENGINE=django.contrib.sessions.backends.cached_db` и fallback `False`. Custom `signing.dumps()` tokens используют собственные salts и не меняются автоматически; legacy message-cookie остается ограниченным краткоживущим UI-риском. Источник: <https://docs.djangoproject.com/en/6.1/releases/6.1/#security>.
- Что даст: предотвращение неожиданных logout/потери messages/невалидных долгоживущих ссылок или QR-context после обновления и явная дата окончания legacy acceptance.
- Риск и ограничения: изменение относится не ко всем `django.core.signing` токенам одинаково; нельзя включать fallback бессрочно без подтверждения конкретного affected cookie path. Это compatibility-аудит, а не доказанная поломка.
- Следующая проверка: на canary-окне проверить реальный legacy message cookie и задать срок окончания fallback; сессионные и custom salted tokens не мигрировать без отдельного parity-теста.

### DJ6-ADMIN-001 - Проверить новую 6.1 семантику `list_select_related` и admin actions

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: все кастомные `ModelAdmin` не-DTF приложений и административные change list/change form страницы.
- Доказательство: в runtime зарегистрировано 124 non-DTF `ModelAdmin`; 122 используют `False`/`None`, один project admin tuple, а единственный `list_select_related=True` принадлежит vendor `social_django`. Django 6.1 автоматически берет FK из `list_display`; project code не использует deprecated True. Источник: <https://docs.djangoproject.com/en/6.1/releases/6.1/#django-contrib-admin>.
- Что даст: меньше лишних JOIN в admin, возможность действия с change form и корректные singular/plural подписи; одновременно предотвращает скрытый N+1 в вычисляемых `list_display`.
- Риск и ограничения: автоматическое улучшение Django не покрывает свойства, методы и deep relations в `list_display`; изменение query plan надо измерять по каждой тяжелой админке, а action API проверить на кастомные overrides.
- Следующая проверка: собрать карту `ModelAdmin`/`list_display`/`get_queryset`, запустить query-count на списках с реальными объемами и отдельно проверить сигнатуры `get_actions`/`get_action_choices`.

### DJ6-SRV-001 - Redis endpoint недоступен с production, поэтому не является доступной основой для очереди

- Статус: `подтверждено`; предварительный приоритет: `P1` как блокер задач/распределенного cache, не как немедленный перенос.
- Область: production `REDIS_URL`/`REDIS_DSN`, `twocomms/twocomms/settings.py:992-1102`, `twocomms/twocomms/production_settings.py:376-498`.
- Доказательство: read-only probe 2026-08-16 из production Python 3.14/Django 6.1 получил `gaierror` для настроенного Redis Cloud hostname. На сервере нет `redis-cli` и пакета `celery`; `TASKS.default` сейчас `django.tasks.backends.immediate.ImmediateBackend`. Это подтверждает historical comment в settings, а не только повторяет его.
- Что даст: исключает ложное решение «достаточно включить Celery/Django Tasks» и направляет усилия на сначала DNS/ACL/TLS/Redis-план или другой внешний backend.
- Риск и ограничения: DNS-сбой не доказывает, что провайдер Redis удален или что нельзя восстановить доступ; не менять endpoint, пароль, firewall или оплачиваемый тариф без отдельного согласования. `ImmediateBackend` в production выполнять тяжелые задачи синхронно.
- Следующая проверка: получить у Redis/cPanel владельца допустимый hostname/port/TLS/ACL, сделать отдельный read-only `PING` через production runtime и только затем рассматривать Redis для cache, lock или Django Tasks backend.

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

- Статус: `подтверждено`; предварительный приоритет: `P1`.
- Область: production cron и команды `run_instagram_bot` (каждую минуту), `reconcile_order_telegram_notifications`, `reconcile_ig_checkout`, `reconcile_ig_order_fulfillment` (каждые 2 минуты), `poll_ig_deal_payments` (каждые 4 минуты), `update_tracking_statuses` (каждые 5 минут); DTF исключен.
- Доказательство: на production нет `supervisorctl`, `systemctl` и `celery`, но есть `crontab`, `nohup`, `flock`; обнаружены 6 активных cron lines и один running `run_instagram_bot`. Django Tasks не предоставляет worker/scheduler сам по себе.
- Что даст: стабильный переходный путь для выноса тяжелых request-path действий без предположения о несуществующей очереди: durable row/job, `flock`/DB lease, bounded batch, retry/backoff, наблюдаемое завершение.
- Риск и ограничения: cron cadence не гарантирует exactly-once; запуск новой задачи без overlap protection способен дублировать Telegram, платежные или внешние API side effects. Нельзя переводить уже работающую IG-periodику на новый scheduler до сравнения ownership.
- Следующая проверка: для шести существующих команд проверить `flock`/lease/timeout/exit-code/alerting и описать единый job contract, который позже можно использовать Django Tasks backend-ом.

### DJ6-SRV-006 - Server default charset `latin1` расходится с `utf8mb4` таблицами и требует явной миграционной защиты

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: production MariaDB server/schema defaults и любые будущие migration/manual SQL; DTF исключен.
- Доказательство: `@@character_set_server=latin1`, `@@collation_server=latin1_swedish_ci`, хотя все 305 таблиц, соответствующих non-DTF Django моделям, имеют `utf8mb4_unicode_ci`; Django default connection устанавливает `charset='utf8mb4'` и `default_storage_engine=INNODB` в `production_settings.py:210-219`.
- Что даст: предотвращение mojibake или случайного MyISAM/latin1 при создании таблицы/индекса вне Django, а также предсказуемую репетицию DB-level migrations.
- Риск и ограничения: смена глобального server default может затронуть другие приложения cPanel и не входит в безопасную Django migration. Для существующих таблиц она ничего не исправляет автоматически.
- Следующая проверка: проверить права на `ALTER DATABASE` и влияние на соседние приложения, затем выбрать минимальную политику: Django-only migrations с явными defaults либо отдельное согласованное изменение schema default.

### DJ6-ORM-001 - Устранить deferred N+1 в снимках оплаты заказов

- Статус: `подтверждено`; предварительный приоритет: `P1`.
- Область: `twocomms/storefront/views/admin.py:795-804`, `twocomms/orders/nova_poshta_documents.py:244-247`.
- Доказательство: endpoint загружает заказы через `.only("id", "payment_status", "pay_type", "total_sum", "payment_payload")`, а `build_order_payment_snapshot()` затем читает невыбранный `discount_amount`. Для каждого заказа Django делает отдельную ленивую догрузку. Django 6.1 позволяет управлять этим через `FETCH_PEERS`, но здесь дешевле сначала расширить явную projection. Источник: <https://docs.djangoproject.com/en/6.1/topics/db/fetch-modes/>.
- Что даст: устранит до одного дополнительного SQL-запроса на каждый заказ в пакетном admin endpoint и снизит задержку обновления платежных карточек.
- Риск и ограничения: глобально включать `FETCH_PEERS` нельзя; это может увеличить размер batch-запроса и память. Добавление одного денежного поля в `.only()` является более узким первым вариантом.
- Следующая проверка: query-count test на 3-10 заказах со скидкой и без нее, затем сравнение явного поля с локальным `FETCH_PEERS`.

### DJ6-ORM-002 - Устранить deferred N+1 в расчете замороженной суммы одного реселлера

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: `twocomms/finance/services/consignment.py:389-396`, `twocomms/finance/models_consignment.py:214-223`.
- Доказательство: queryset выбирает только `qty`, `sold_qty`, `unit_cost`, но property `frozen_value` дополнительно читает `is_consignment`. Несмотря на фильтр `is_consignment=True`, поле модели остается deferred и догружается на каждом объекте.
- Что даст: один SQL вместо схемы `1 + N` при расчете замороженных средств магазина; уменьшит задержку finance dashboard.
- Риск и ограничения: `FETCH_PEERS` можно рассматривать только локально. Самый дешевый фикс - добавить boolean в `.only()` или заменить Python-цикл DB aggregate после проверки Decimal-семантики.
- Следующая проверка: query-count и точная сумма для набора с проданными, частично проданными и неконсигнационными позициями.

### DJ6-ORM-003 - Устранить тот же deferred N+1 в общей замороженной сумме компании

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: `twocomms/finance/services/consignment.py:417-431`, `twocomms/finance/models_consignment.py:214-223`.
- Доказательство: company-wide расчет повторяет projection без `is_consignment`, после чего property читает это поле для каждой строки. Широкий `except Exception` дополнительно способен скрыть ошибку или timeout и вернуть ложный ноль.
- Что даст: особенно заметное снижение числа запросов на общем dashboard и более предсказуемая диагностика ошибочного расчета.
- Риск и ограничения: изменение exception policy является отдельным поведением; в первом проходе достаточно устранить deferred access и измерить запросы.
- Следующая проверка: query-count на реальном объеме копии MariaDB, regression test точной суммы и отдельный аудит причины широкого exception.

### DJ6-ORM-004 - Убрать до двух N+1-запросов на строку в Django admin пользователей

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: `twocomms/accounts/admin.py:52-77`, связи `UserProfile.user` и `UserPoints.user` в `twocomms/accounts/models.py:22-24`, `112-115`.
- Доказательство: `UserAdmin.list_display` вызывает `obj.userprofile.phone` и `obj.points.points`, но `get_queryset()` не переопределен. Новая admin-оптимизация Django 6.1 охватывает ForeignKey из `list_display`, но не эти вычисляемые reverse OneToOne методы. Источник: <https://docs.djangoproject.com/en/6.1/ref/contrib/admin/#django.contrib.admin.ModelAdmin.get_queryset>.
- Что даст: заменить до двух запросов на каждого пользователя одним `LEFT JOIN` через явный `select_related("userprofile", "points")`.
- Риск и ограничения: проверить пользователей без одной или обеих связей и не раздувать queryset тяжелыми inline relations.
- Следующая проверка: query-count changelist на 25-100 пользователей, включая отсутствующие profile/points.

### DJ6-ORM-005 - Заменить N+1 подсчет товаров в Category API на аннотацию

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: `twocomms/storefront/viewsets.py:39-52`, `twocomms/storefront/serializers.py:24-33`.
- Доказательство: `CategorySerializer.get_products_count()` выполняет `.count()` отдельно для каждой категории. Queryset viewset не добавляет агрегат.
- Что даст: один grouped SQL с `Count(..., filter=...)` вместо `1 + N` запросов к публичному API.
- Риск и ограничения: на MariaDB нужно проверить `GROUP BY`, distinct при возможных join и сохранение нулевого значения для пустых категорий.
- Следующая проверка: API response parity и query-count для нескольких активных категорий с published/draft товарами.

### DJ6-ORM-006 - Предзагрузить цвет и варианты только для Product detail API

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: `twocomms/storefront/viewsets.py:71-91`, `twocomms/storefront/serializers.py:36-49`, `108-110`, `twocomms/productcolors/models.py:28-34`.
- Доказательство: detail serializer читает `color_variants` и вложенный `color` через `depth=1`, но queryset загружает только category. Это создает запрос к вариантам и затем запросы к color по каждой строке.
- Что даст: bounded набор запросов через `Prefetch("color_variants", queryset=...select_related("color"))`, без увеличения payload list API.
- Риск и ограничения: prefetch должен включаться только для action `retrieve`; глобальный prefetch раздует список товаров.
- Следующая проверка: detail с 3+ вариантами, query-count и отдельная проверка неизменного list endpoint.

### DJ6-ORM-007 - Использовать один `in_bulk()` вместо 25 запросов в analytics widget товаров

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: `twocomms/storefront/services/admin_analytics.py:1328-1358`.
- Доказательство: цикл по `view_rows[:25]` делает `Product.objects.filter(...).select_related("category").first()` для каждой строки.
- Что даст: один запрос `select_related("category").in_bulk(ids)` вместо до 25 отдельных запросов, быстрее административная аналитика.
- Риск и ограничения: сохранить текущие fallback для удаленных/null product IDs и порядок исходных analytics rows.
- Следующая проверка: query-count с существующими, удаленными и пустыми product IDs.

### DJ6-ORM-008 - Заменить N+1 `exists()` в survey analytics на `Exists/OuterRef`

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: `twocomms/storefront/services/admin_analytics.py:1522-1526`.
- Доказательство: все completed sessions материализуются, после чего для каждой выполняется отдельный `Order.objects.filter(...).exists()`.
- Что даст: вычислить downstream purchase одним correlated `Exists` запросом, уменьшить SQL round-trip и Python memory.
- Риск и ограничения: до внедрения нужен `EXPLAIN` на MariaDB; составной индекс для условия `user + created` должен быть подтвержден, а anonymous session semantics сохранены.
- Следующая проверка: parity downstream count, query-count и `EXPLAIN` на локальной копии production MariaDB.

### DJ6-ORM-009 - Применить новый Django 6.1 `values().in_bulk()` в расчете subtotal корзины

- Статус: `подтверждено`; предварительный приоритет: `P3`.
- Область: `twocomms/storefront/views/cart.py:95-113`.
- Доказательство: `_calculate_original_subtotal()` materializes полные Product через `Product.objects.in_bulk(ids)`, хотя использует только `id` и `price`. Django 6.1 разрешил `in_bulk()` после `values()`/`values_list()`. Источник: <https://docs.djangoproject.com/en/6.1/releases/6.1/#models>.
- Что даст: уменьшить ширину строк, создание model instances и память на каждом расчете корзины.
- Риск и ограничения: новый mapping shape нужно проверить отдельно; dynamic-model smoke уже вернул `{pk: dict}` mapping с ожидаемыми ключами, но Decimal и отсутствующие товары не должны изменить итог.
- Следующая проверка: benchmark корзин разного размера и тесты missing product, zero price, скидка и невалидное quantity.

### DJ6-ORM-010 - Применить `values().in_bulk()` при проверке принадлежности варианта товара

- Статус: `подтверждено`; предварительный приоритет: `P3`.
- Область: `twocomms/storefront/views/utils.py:261-273`, `294-313`.
- Доказательство: проверке нужны только `variant.id` и `variant.product_id`, но `ProductColorVariant.objects.in_bulk()` загружает всю модель.
- Что даст: меньше данных и model-object overhead на каждом чтении корзины с цветовыми вариантами.
- Риск и ограничения: сохранить интерфейс `filter_cart_variant_ownership()` либо явно адаптировать его к dict; API smoke подтвердил саму возможность `values().in_bulk()`, а session mutation и Monobank reset требуют regression tests.
- Следующая проверка: wrong product, missing variant, duplicate session rows и неизменность очистки pending checkout.

### DJ6-ORM-011 - Использовать `QuerySet.totally_ordered` как gate для стабильной пагинации

- Статус: `подтверждено`; предварительный приоритет: `P1` для операционных списков, `P2` для остальных.
- Область: `twocomms/management/views.py:2099-2108`, `management/shop_views.py:281-293`, `management/network_views.py:56-87`, `management/checker_views.py:150-188`, `management/parsing_views.py:114-138`, `warehouse/views/history.py:17-42`, `orders/dropshipper_views.py:329-355`, `439-451`.
- Доказательство: paginator querysets сортируются по timestamp/score/count без уникального tie-breaker. Django 6.1 добавил `QuerySet.totally_ordered`, который позволяет формально обнаруживать недетерминированный порядок. Источник: <https://docs.djangoproject.com/en/6.1/ref/models/querysets/#django.db.models.query.QuerySet.totally_ordered>.
- Что даст: исключить пропуски и дубли между страницами при одинаковых timestamp/score; добавить тестируемый guardrail для новых paginator endpoints.
- Риск и ограничения: добавление `id` меняет SQL plan и может потребовать составные индексы; сначала `EXPLAIN`, затем tie-boundary tests. Отдельно в dropshipper view обнаружен production `print()` и повторная итерация queryset, это вынести в отдельную находку.
- Следующая проверка: создать ties на границе страниц, добавить уникальный `id/pk` в ordering и проверить `totally_ordered is True` для каждого пути.

### DJ6-ORM-012 - Включать `FETCH_RAISE` в тестах для намеренно узких projections

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: `twocomms/storefront/services/catalog_facets.py:40-47`, `storefront/seo_utils.py:167-199`, `management/bot_views.py:2418-2429`, `storefront/sitemaps.py:114-130`, `239-250`, `307-320`.
- Доказательство: эти пути сознательно используют `.only()` и сейчас читают выбранные поля. `FETCH_RAISE` позволяет превратить будущую скрытую ленивую догрузку в `FieldFetchBlocked` во время теста. Источник: <https://docs.djangoproject.com/en/6.1/topics/db/fetch-modes/>.
- Что даст: защитит SEO, sitemap, catalog facets и bot observability от незаметного появления N+1 после следующего изменения property/template.
- Риск и ограничения: не включать режим глобально в production; сначала локальные tests/query-count. Любой intentionally deferred access придется сделать явным.
- Следующая проверка: targeted tests с `FETCH_RAISE`, где доступ к omitted field намеренно падает, а штатный результат остается прежним.

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
- Что даст: общую очередь между Passenger-процессами, устойчивость к reload и контролируемую CPU/IO concurrency; пользовательский upload перестанет зависеть от локального executor.
- Риск и ограничения: worker и Passenger должны видеть один `MEDIA_ROOT`; нельзя потерять lease/supersede или создать две оптимизированные версии. Бенчмарк Pillow и лимиты памяти обязательны.
- Следующая проверка: dry-run job на копии media, конкурентный lease test и сравнение с текущей reconciliation-командой.

### DJ6-BG-005 - Убрать полный tracking batch из middleware Nova Poshta

- Статус: `подтверждено`; предварительный приоритет: `P1`.
- Область: `twocomms/orders/nova_poshta_middleware.py:57-154`, `180-232`; batch `NovaPoshtaService.update_all_tracking_statuses`.
- Доказательство: каждый web request проверяет heartbeat/lock и может запускать полный tracking batch в daemon, а simple режим выполняет его прямо в request. Batch уже ограничен и использует row locks.
- Что даст: стабильное время ответа storefront/management и одно плановое место для rate-limited внешнего API.
- Риск и ограничения: middleware отключать только после подтвержденного cron/task scheduler, `flock`/DB lease, timeout и alerting. Нельзя оставлять две competing owners периодики.
- Следующая проверка: измерить batch duration и overlap, затем canary cron с выключенным request trigger и reconciliation proof.

### DJ6-BG-006 - Заменить поток wake-up fulfillment, сохранив durable event semantics

- Статус: `отложено`; предварительный приоритет: `P2`.
- Область: `twocomms/management/services/ig_order_fulfillment.py:860-877`, event/lease graph `285-423`, `718-857`.
- Доказательство: `kick_order_fulfillment()` только ускоряет уже durable event queue с event keys, leases, receipt checkpoint и stale-to-ambiguous переходом.
- Что даст: task wake-up или чистый cron снизит количество локальных потоков без потери бизнес-состояния и упростит recovery.
- Риск и ограничения: неизвестный Meta outcome должен остаться `manager review`; нельзя заменять queue семантику простым повтором API.
- Следующая проверка: сравнить latency bot/cron, проверить idempotent replay и убрать thread только после proof.

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

### DJ6-TASK-002 - Зафиксировать отсутствие production worker для `ImmediateBackend`

- Статус: `подтверждено`; предварительный приоритет: `P1`.
- Область: `twocomms/twocomms/settings.py:1085-1102`, `twocomms/twocomms/__init__.py:1-10`.
- Доказательство: в production оставлен только legacy `CELERY_*` конфиг, Celery worker/beat отсутствуют; Django Tasks фактически использует `ImmediateBackend`. `ImmediateBackend` исполняет задачу inline и не является очередью.
- Что даст: устранит ложную предпосылку при планировании распараллеливания; архитектурный backlog будет разделять enqueue API, внешний worker, scheduler и recovery.
- Риск и ограничения: нельзя просто заменить backend на Redis, пока DNS/ACL/права и connection budget не подтверждены. Не удалять cron ownership без canary и rollback.
- Следующая проверка: capability matrix хостинга и безопасный no-send task contract.

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

### DJ6-MIG-001 - Составить план безопасного squash исторических миграций

- Статус: `отложено`; предварительный приоритет: `P3`.
- Область: non-DTF migration graph: 435 nodes (`management` 168, `storefront` 90, `orders` 52, `accounts` 30, `finance` 21 и системные/vendor chains).
- Доказательство: Django 6.0 разрешил повторно squash уже squashed migrations до перехода в normal state. Текущий real graph под Django 6.1 успешно строится, но его длина и production history делают squash отдельным high-risk этапом. Источник: <https://docs.djangoproject.com/en/6.0/releases/6.0/#migrations>.
- Что даст: меньше времени на создание test DB/проверку migration plan и меньше файлов для сопровождения новых окружений.
- Риск и ограничения: production уже применил длинные цепочки; неправильное удаление старых migration files ломает deploy/restore и внешние базы. Не смешивать с изменением схемы или DTF.
- Следующая проверка: построить dependency graph по каждому приложению, проверить applied migration history и rehearsal на чистой MariaDB-копии; удаление файлов не делать в этой фазе.

### DJ6-AUTH-001 - Измерить CPU-эффект нового PBKDF2 cost и постепенный rehash

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: login/password-change paths, в частности `twocomms/storefront/views/profile.py:670-671`; явный `PASSWORD_HASHERS` в проекте не задан.
- Доказательство: Django 6.0 поднял PBKDF2 iteration count до 1,200,000, Django 6.1 - до 1,500,000. Старые пароли обычно перехешируются при успешном входе. Источники: <https://docs.djangoproject.com/en/6.0/releases/6.0/#django-contrib-auth> и <https://docs.djangoproject.com/en/6.1/releases/6.1/#django-contrib-auth>.
- Что даст: прогнозируемое время входа и план capacity для Passenger вместо неожиданного CPU spike при массовых логинах.
- Риск и ограничения: понижать cost ради скорости нельзя без отдельного security-решения; Argon2/кастомный hasher потребуют совместимости с существующими hashes.
- Следующая проверка: benchmark login/hash upgrade на production-подобном CPU, измерить долю старых hash prefixes и определить rate-limited rollout.

### DJ6-FORM-001 - Проверить изменение default scheme `URLField` на HTTPS

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: `twocomms/orders/forms.py:30-34` и все ModelForm для URLField в `accounts`, `finance`, `orders`, `product_catalog`, `storefront`, `management`.
- Доказательство: Django 6.0 удалил transitional `FORMS_URLFIELD_ASSUME_HTTPS` и сделал default scheme `https`; runtime подтвердил `forms.URLField().assume_scheme == "https"`, а inventory содержит 16 non-DTF model URLFields и один explicit form URLField. Сохраненные старые значения и внешние интеграции нужно проверить. Источник: <https://docs.djangoproject.com/en/6.0/releases/6.0/#features-removed-in-6-0>.
- Что даст: единообразные безопасные ссылки и меньше mixed-content/redirect surprises.
- Риск и ограничения: нельзя автоматически переписывать пользовательские URL или webhook endpoints; часть legacy HTTP-сервисов может быть намеренной.
- Следующая проверка: form validation matrix (`example.com`, `http://`, `https://`, localhost/provider endpoints) и read-only inventory stored schemes.

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

- Статус: `подтверждено как configuration gap`; предварительный приоритет: `P1`.
- Область: production `crontab`: `* * * * * ... manage.py run_instagram_bot --ensure` без `flock`; рядом уже работает отдельный `run_instagram_bot --forever`.
- Доказательство: остальные пять периодик используют `/usr/bin/flock`, но Instagram line lock не содержит. При задержке/гонке cron может породить второй starter или неясное ownership между `--ensure` и `--forever`.
- Что даст: единственный владелец bot process, отсутствие duplicate polling/API side effects и понятный exit/health contract.
- Риск и ограничения: не менять cron вслепую; сначала понять semantics `--ensure`, running marker и restart recovery. `flock` path должен быть writable и иметь stale-safe lifecycle.
- Следующая проверка: read-only проверить command state machine, затем тест overlap на staging/copy и добавить lock/timeout/alerting.

### DJ6-TEST-001 - Оценить forkserver/parallel test runner после стабилизации suite

- Статус: `отложено`; предварительный приоритет: `P3`.
- Область: 435-node non-DTF migration graph и связанные test chains; стандартного CI runner с `--parallel` в репозитории не найдено.
- Доказательство: Django 6.0 добавил поддержку `DiscoverRunner` для parallel tests на forkserver; isolated non-DTF `storefront.tests.test_cache_hygiene --parallel 2` прошел 6/6. Полный suite upgrade baseline все еще содержит 65 failures и 47 errors, поэтому общую параллелизацию отложить. Источник: <https://docs.djangoproject.com/en/6.0/releases/6.0/#tests>.
- Что даст: сократит время большой regression suite и позволит чаще прогонять matrix Python 3.14/MariaDB.
- Риск и ограничения: текущие tests используют общую файловую cache/media, внешние mocks и возможные SQLite/MariaDB locks; параллелизация до baseline green может маскировать race.
- Следующая проверка: выбрать изолированный no-network subset, запустить `manage.py test --parallel 2` с отдельными temp dirs и сравнить flake/query contention.

### DJ6-SEC-002 - Проверить строгую Base64-валидацию на PII/credential import paths

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: `twocomms/management/models.py:3419-3439` (BinaryField encrypted PII), `management/parser_usage.py:97-104`, Monobank signature decoders `storefront/views/utils.py:1406-1408`, `storefront/views/monobank.py:504-511`.
- Доказательство: Django 6.1 теперь строго отклоняет invalid Base64 в `BinaryField`, multipart parser и DatabaseCache. Проект принимает Base64 из Google credential/env и provider signatures с permissive `b64decode`; table-driven smoke подтвердил, что Python `base64.b64decode()` без `validate=True` принимает мусор, тогда как strict validation его отклоняет. PII BinaryField должен оставаться bytes, а не silently coerced text. Источник: <https://docs.djangoproject.com/en/6.1/releases/6.1/#models> и <https://docs.djangoproject.com/en/6.1/releases/6.1/#miscellaneous>.
- Что даст: явные ошибки конфигурации/подписи вместо тихого обрезания или пустого значения, меньше неоднозначности при импорте/валидации.
- Риск и ограничения: менять декодирование webhook можно только с сохранением provider-compatible padding/URL-safe rules; не логировать секретные payloads.
- Следующая проверка: table-driven tests valid/invalid/padded/base64url inputs и форма/serializer round-trip для BinaryField без production mutation.

### DJ6-ENV-001 - Не допустить silent downgrade из старого dependency lock

- Статус: `подтверждено`; предварительный приоритет: `P1`.
- Область: основной локальный checkout `main`, `twocomms/requirements.in`, `twocomms/requirements.lock`, общая `.venv`, CI и будущая интеграция upgrade-ветки.
- Доказательство: на момент проверки `/Users/zainllw0w/TwoComms/site/.venv` содержит CPython `3.14.6`, Django `6.1`, DRF `3.18.0` и `mysqlclient 2.2.8`, но current `main` закрепляет `Django==5.2.11`, `djangorestframework==3.15.2` и `PyMySQL==1.1.2`. Верифицированная ветка `codex/django-61-upgrade` содержит согласованный набор Django `6.1`, DRF `3.18.0`, `mysqlclient 2.2.8` и compatibility-правки. Повторный install из lock основного checkout вернет старый runtime; запуск старого кода на новой `.venv` выявил несовместимый `CheckConstraint(check=...)`.
- Что даст: один воспроизводимый источник истины для локальных тестов, CI, release wheelhouse и production; устранит ложные результаты, когда код тестируется не под той парой Python/Django.
- Риск и ограничения: нельзя копировать только два requirements-файла: переход одновременно меняет DB driver и код моделей/settings. Не выполнять `pip install -r` из старого lock поверх Django 6.1 venv и не использовать несовместимое состояние как доказательство production readiness.
- Следующая проверка: сравнить полный diff verified upgrade-ветки с целевым `main`, интегрировать его атомарно в отдельной задаче, затем проверить hash-locked install на чистой CPython 3.14.6 venv и exact SHA на server.

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

- Статус: `подтверждено`; предварительный приоритет: `P1` до Django 7.0.
- Область: установленный `social-auth-app-django==5.6.0`, `social_django.admin.UserSocialAuthOption`, OAuth admin/login integration.
- Доказательство: fresh `PYTHONWARNINGS=default manage.py check --settings=test_settings --database default` под CPython `3.14.6`/Django `6.1` выдал `RemovedInDjango70Warning` из `site-packages/social_django/admin.py:13`: пакет задает `ModelAdmin.list_select_related = True`, что deprecated в Django 6.1.
- Что даст: раннее решение vendor compatibility до Django 7.0 без потери social-auth admin и OAuth flow.
- Риск и ограничения: не monkey-patch vendor class без тестов; обновление social-auth может изменить callback, pipeline, storage и token semantics.
- Следующая проверка: проверить свежий upstream release/changelog, воспроизвести warning в isolated matrix и выбрать upgrade либо минимальный локальный admin subclass с OAuth/admin regression tests.

### DJ6-LEGACY-001 - Активный `views.py.backup` содержит удаляемый `select_related()` без полей

- Статус: `подтверждено`; предварительный приоритет: `P1` до Django 7.0.
- Область: `twocomms/storefront/views/__init__.py:318-347`, `twocomms/storefront/views.py.backup:299,1584,3369,5605,5614,5833,5842,5890,5899`, route `twocomms/storefront/urls.py:625` (`/pricelist_opt.xlsx`).
- Доказательство: legacy loader реально подгружает `views.py.backup`, а public pricelist route берет из него `wholesale_prices_xlsx`; модуль содержит вызовы `select_related()` без имен полей. Django 6.1 deprecated no-argument form и требует перечислить relation fields либо рассмотреть `FETCH_PEERS`. Источник: <https://docs.djangoproject.com/en/6.1/releases/6.1/#miscellaneous>.
- Что даст: сохранит доступность прайс-листа и legacy management paths после следующего major upgrade, а также устранит неявные joins.
- Риск и ограничения: backup фактически active runtime, поэтому его нельзя удалять или mass-refactor как мертвый файл; для каждого call site нужно определить реальные relation names и query count.
- Следующая проверка: route-level test `/pricelist_opt.xlsx`, static inventory всех no-argument calls и маленькие query-count tests перед точечной заменой или переносом функции в поддерживаемый module.

### DJ6-PY-001 - Заменить deprecated `SourceFileLoader.load_module()` до Python 3.15

- Статус: `подтверждено`; предварительный приоритет: `P2`.
- Область: fallback import в `twocomms/storefront/tasks.py:62-68`.
- Доказательство: при `ModuleNotFoundError` код вызывает `SourceFileLoader(...).load_module()`. API deprecated в Python importlib и удаляется в Python 3.15; проект уже использует CPython 3.14.6. Источник: <https://docs.python.org/3/library/importlib.html#importlib.machinery.SourceFileLoader.load_module>.
- Что даст: исключит будущий hard failure при следующем обновлении Python и сделает fallback import согласованным с уже используемым `spec_from_loader` pattern в legacy loader.
- Риск и ограничения: fallback срабатывает только при поврежденном import path; нельзя считать обычный import failure поводом тихо загрузить другой module и скрыть packaging defect.
- Следующая проверка: отдельный test с forced fallback, заменить на `spec_from_file_location`/`module_from_spec`/`exec_module`, затем проверить module identity и error propagation.

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

### DJ6-CMD-001 - Нет import/parser smoke для 138 custom management commands

- Статус: `подтверждено как coverage gap`; предварительный приоритет: `P2`.
- Область: management commands всех не-DTF приложений; строго исключенный bridge command в подсчет не включен.
- Доказательство: inventory насчитывает 138 command modules после исключения DTF-named/DTF paths (139 файлов, если считать `refresh_dtf_bridge_snapshot.py`, который намеренно исключен). Read-only import/parser smoke импортировал все 138 `Command` classes, построил argparse parser, не вызвал `handle()` и не увидел failures при заблокированной сети. `manage.py check` сам по себе этот contract не проверяет.
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
- Доказательство: runtime/lock audit подтверждает CPython 3.14.6/Django 6.1 на проверенной ветке, тогда как active architecture README и часть WSGI-комментариев остаются на старых версиях; основной checkout `main` все еще закрепляет Django 5.2.11, поэтому менять исторические документы до интеграции upgrade нельзя.
- Что даст: после атомарной интеграции уменьшит повторный запуск проверок под старым runtime и риск silent downgrade.
- Риск и ограничения: исторические incident reports и планы не переписывать; обновлять только current-facing docs после merge/deploy.
- Следующая проверка: после интеграции lock в `main` обновить README/runbook, добавить exact-version preflight и проверить ссылки на production Python 3.14 virtualenv.


## Сводка статусов после полной read-only проверки

- Всего записей: 83 уникальных ID; дублей нет.
- Подтверждено или подтверждено с уточненным типом сигнала/границы: 71 запись.
- Отложено до отдельного implementation/schema/worker этапа: 8 записей.
- Заблокировано правами, архитектурой или версией MariaDB: 3 записи.
- Неактуально для текущего runtime: 1 запись (`DJ6-BASE-006`, async-кода нет).
- Статус `кандидат` после этой проверки не оставлен: каждая исходная гипотеза переведена в доказанный backlog, отложенный пункт, блокер или неактуальный пункт.
- Это не означает, что улучшения уже внедрены: файл фиксирует доказательства и порядок следующего этапа, а не разрешение менять production.

## Отдельный список блокеров и неизвестных

- Повторный live SSH probe перед следующим release обязателен; текущий read-only снимок уже подтвержден (`DJ6-LIVE-001`), но он не заменяет post-deploy проверку.
- Redis DNS/ACL и worker/supervisor capability остаются неподтвержденными: hostname не разрешается, `redis-cli`/Celery/Supervisor/systemd недоступны (`DJ6-BASE-005`, `DJ6-SRV-001`, `DJ6-TASK-002`).
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
