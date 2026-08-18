# Django 6.1: приоритетный план реализации

> **Для агента-исполнителя:** обязательный следующий навык - \`superpowers:executing-plans\`. Реализовывать план небольшими изолированными блоками, с TDD, review и отдельной production-проверкой каждого завершенного блока.

**Цель:** превратить подтвержденные находки из \`dj6_update_all.md\` в безопасную последовательность изменений, которая сначала защищает платежи, данные и deploy, затем дает быстрый выигрыш в запросах и latency, и только после этого меняет фоновые процессы, MariaDB и инфраструктуру.

**Архитектура:** изменения выполняются от \`origin/main\` в отдельном worktree. Сначала создается надежный test/release baseline, затем внедряются узкие совместимые исправления. Глобальные ORM-режимы, фоновые worker и DDL не включаются до измерений и завершения их prerequisites.

**Стек:** CPython 3.14.6, Django 6.1, Django REST Framework 3.18, MariaDB 11.4.12, Passenger, cron, file-based Django cache, mysqlclient 2.2.8.

---

## Источник и границы

- Источник находок: \`dj6_update_all.md\`, 83 уникальных \`DJ6-*\` ID.
- План охватывает storefront, management, finance, storage/warehouse, accounts, orders, reviews, product catalog и общую инфраструктуру.
- DTF-субдомен, DTF URLconf, модели, миграции, команды, статика, процессы и база данных полностью исключены.
- Production MariaDB является источником истины, но не используется как тестовая или disposable база.
- Для schema/query/performance работ нужна локальная изолированная MariaDB-копия production non-DTF базы.
- Redis сейчас недоступен по DNS; Celery, Supervisor и systemd недоступны. До доказательства обратного нельзя проектировать обязательную зависимость от worker.
- Локальный checkout \`main\` может быть грязным и отставать от \`origin/main\`; реализация начинается только в новом worktree от проверенного \`origin/main\`.

## Как отмечать выполнение

Чекбокс конкретного \`DJ6-*\` пункта отмечается только после одновременного выполнения всех условий:

- [ ] есть failing regression test или измеримый baseline до изменения;
- [ ] минимальная реализация завершена без несвязанных refactor;
- [ ] focused tests проходят;
- [ ] no-network check, Django check, migration drift check и \`git diff --check\` проходят;
- [ ] для ORM/DB изменений есть query-count, parity или MariaDB evidence;
- [ ] изменение интегрировано в GitHub \`main\`;
- [ ] при наличии production-эффекта выполнены разрешенный deploy и post-deploy proof;
- [ ] DTF не затронут ни кодом, ни тестами, ни серверными командами.

Checkbox нельзя отмечать по факту написания кода или локального зеленого теста. Для production-задач обязательны deployed SHA и live evidence.

## Модель приоритета

Приоритет определяется не исходной меткой P1/P2 отдельно, а сочетанием факторов:

| Фактор | Вес | Что считается высоким значением |
| --- | ---: | --- |
| Целостность денег и данных | 5 | платежи, заказы, подписи, constraints, повторные side effects |
| Доступность и reliability | 5 | request-owned daemon, cron overlap, connection exhaustion |
| Пользовательская скорость | 4 | N+1, тяжелый middleware, лишние внешние вызовы |
| Security и будущая совместимость | 4 | deprecated API, CSP, CSRF, строгая валидация |
| Ширина эффекта | 3 | общий runtime/CI важнее одного редкого экрана |
| Доказанность | 2 | подтвержденный кодом/query/runtime факт выше гипотезы |
| Стоимость реализации | -3 | маленький точечный фикс выше большого redesign при равном эффекте |
| Риск rollout | -5 | DDL, MyISAM, worker и provider-side effects сдвигаются позже |

Зависимости имеют больший вес, чем итоговый балл. Например, CI/no-network baseline выполняется раньше ORM-ускорений, а InnoDB rehearsal раньше DB-level \`on_delete\`.

## Очередность этапов

| Этап | Смысл | Ожидаемый результат |
| --- | --- | --- |
| 0 | Сделать тесты и release доказательными | следующие изменения нельзя случайно проверить под Django 5.2 или с внешней сетью |
| 1 | Закрыть риски корректности и совместимости | стабильные подписи, cookies, email и parsing перед performance-работами |
| 2 | Быстрые ORM-выигрыши | меньше N+1 и SQL round-trip без изменения архитектуры |
| 3 | Убрать опасную работу из request path | меньше latency и потерь side effects на существующем cron/DB contract |
| 4 | Security, cache и server observability | контролируемый CSP/CSRF rollout и измеримая серверная нагрузка |
| 5 | MariaDB foundation | безопасная подготовка InnoDB, constraints и будущих DB actions |
| 6 | Реальный task backend | worker только после capability proof и connection budget |
| 7 | Низкорисковые Django 6.x улучшения | templates, docs и test throughput после основных рисков |
| 8 | Явно заблокированные/неактуальные функции | не тратить ресурсы до изменения runtime или MariaDB |

## Первые четыре implementation-блока

Именно в таком порядке следует начинать реализацию:

1. **Release truth:** ENV/CI/WARN/NET/CMD/CHECK/STATIC/MIG/TEST baseline.
2. **Малые correctness fixes:** explicit \`salted_hmac\`, stale video-schema test, strict Base64 и cookie compatibility.
3. **ORM quick wins:** payment snapshot, finance totals, public API, analytics, cart mappings и stable pagination.
4. **Durable request-path work:** post-payment outbox, Nova Poshta middleware, Binotel polling и cron overlap.

Нельзя начинать с Celery, глобального \`FETCH_PEERS\`, массового InnoDB или CSP enforcement.

---

## Этап 0. Доказательный runtime, CI и локальная MariaDB

**Почему первый:** без этого любой следующий зеленый тест может быть ложным, а provider/network side effects могут попасть в production.

**Статус: завершен 2026-08-16.** Release SHA
`df5a99d09b4135bdc7d70baba7956e89e3610ca9` находится в GitHub `main` и
production. Django gate
[`31967237986`](https://github.com/TwoComms-shop/TwoComms_Site/actions/runs/31967237986)
и MariaDB gate
[`31967237927`](https://github.com/TwoComms-shop/TwoComms_Site/actions/runs/31967237927)
завершились `success`; server и HTTP post-deploy matrices имеют `status=ok`.

### Foundation

- [x] **FOUNDATION-DB-001 - Подготовить защищенную локальную копию production non-DTF MariaDB.**
  - Проверить существующие commits/ветку guarded MariaDB sync, не дублировать уже готовую реализацию.
  - Dump получать только утвержденным SSH-путем, с \`--single-transaction --quick --routines --triggers --no-tablespaces\`.
  - Архивы и local env должны быть untracked, mode \`0600\`, без production host/user/password в repository.
  - Restore выполнять только в явно названные disposable local databases; запретить любую команду с production host.
  - Acceptance: schema/table counts совпадают с sanitized production inventory; restore drill воспроизводим; DTF database отсутствует.

### Audit IDs

- [x] **DJ6-ENV-001 - Запретить silent downgrade dependency lock.**
  - Files: \`twocomms/requirements.in\`, \`twocomms/requirements.lock\`, \`tests/test_requirements_contract.py\`, release wheelhouse scripts.
  - Acceptance: clean install доказывает exact Django 6.1/mysqlclient 2.2.8 и падает на старом lock.

- [x] **DJ6-ENV-002 - Сделать project Python единственным допустимым runtime.**
  - Добавить tracked Python 3.14.6 pin и reusable preflight.
  - Acceptance: bare Python 3.13/Django 5.2 не может пройти project gate; worktree/subagent используют exact interpreter.

- [x] **DJ6-CI-001 - Проверять exact CPython 3.14.6 и Django 6.1 во всех relevant jobs.**
  - Acceptance: каждый Django job печатает и asserts versions после hash-locked install.

- [x] **DJ6-CI-002 - Создать честный migration-drift gate с включенными migration modules.**
  - Files: \`twocomms/test_settings_no_network.py\`, новый isolated settings profile, \`scripts/run_ig_baseline.py\`.
  - Acceptance: intentional model drift делает gate красным.

- [x] **DJ6-CI-003 - Добавить \`check --database=default\` в disposable MariaDB gate.**
  - Acceptance: MariaDB backend warnings видны и имеют явный временный allowlist.

- [x] **DJ6-CI-004 - Добавить общий Django 6.1 gate для обычных pull requests.**
  - Минимум: exact versions, no-network check, migration drift, command import/parser, stable focused suites.
  - Acceptance: изменение обычного view/model/form не может обойти Django gate.

- [x] **DJ6-WARN-001 - Добавить отдельный \`-Wa\` deprecation-warning gate.**
  - Project-owned warnings запрещены; vendor warnings имеют owner и срок удаления.
  - Acceptance: новый \`RemovedInDjango70Warning\` делает job красным.

- [x] **DJ6-NET-001 - Реально запретить сеть внутри test subprocess.**
  - Не использовать отдельный завершившийся monkeypatch process как доказательство.
  - Acceptance: synthetic DNS/direct socket/provider call блокируется внутри тестового процесса; local disposable MariaDB разрешается явно.

- [x] **DJ6-CMD-001 - Закрепить import/parser smoke non-DTF management commands.**
  - Не вызывать \`handle()\`.
  - Acceptance: удаленный import или сломанный \`add_arguments()\` ловится без DB/network side effects.

- [x] **DJ6-CHECK-001 - Явно ограничить database checks alias \`default\`.**
  - Acceptance: check не открывает DTF alias и не вызывает внешнюю сеть.

- [x] **DJ6-STATIC-001 - Воспроизвести production static/compressor pipeline в изоляции.**
  - Temporary static root, WhiteNoise manifest, offline compressor.
  - Acceptance: representative non-DTF templates рендерят manifest-backed assets после \`collectstatic\` и \`compress\`.

- [x] **DJ6-COMPAT-001 - Зафиксировать compatibility matrix активных интеграций.**
  - Compressor, WhiteNoise, DRF Spectacular, ratelimit, Redis client и social-auth тестируются по отдельным contracts.

- [x] **DJ6-MIG-002 - Закрыть baseline drift \`CatalogColorSeoOverride\`.**
  - Сначала доказать metadata-only operations на local MariaDB copy.
  - Acceptance: \`makemigrations --check --dry-run\` чистый на реальном migration graph.

- [x] **DJ6-TEST-002 - Классифицировать полный non-DTF suite.**
  - Каждый failure/error occurrence поместить в один детерминированный triage
    cluster и сравнить этот cluster на Django 5.2.11 и Django 6.1.
  - Stage 0 не обязан исправлять старый одинаковый test debt или угадывать его
    root cause; неподтвержденный диагноз должен оставаться `null`.
  - Acceptance: compatibility delta отделена от старого test debt, все
    occurrences учтены ровно один раз, стабильные shards выделены в CI.

- [x] **DJ6-TEST-003 - Исправить stale Product Video Schema test.**
  - Files: \`twocomms/storefront/tests/test_product_video.py\`, \`twocomms/storefront/seo_utils.py\`.
  - Проверять \`subjectOf -> VideoObject\`, \`embedUrl\`, \`contentUrl\`, не возвращать невалидный \`Product.video\`.

- [x] **DJ6-SITE-001 - Превратить полный non-DTF coverage smoke в CI artifact.**
  - Сохранять counts моделей, URL, templates, Python/JS и commands с явным DTF exclusion.

- [x] **DJ6-LIVE-001 - Сделать sanitized read-only preflight/post-deploy matrix обязательной.**
  - Проверять deployed SHA, Python/Django/DRF, MariaDB, migrations/check, Passenger и non-DTF health routes.

### Exit gate этапа 0

- [x] Чистая CPython 3.14.6 среда устанавливается только из текущего lock.
- [x] Fast required CI зеленый и не ходит во внешнюю сеть.
- [x] Migration drift и production-like static pipeline доказательны.
- [x] Локальная MariaDB-копия доступна для следующих query/schema тестов.
- [x] Полный suite имеет классифицированный baseline, а не безымянные 112 проблем.

### Локальные доказательства до main/deploy

Эти отметки сохраняют локальную часть release evidence. Основные `DJ6-*`,
foundation и exit-gate чекбоксы выше закрыты после публикации tracked schema v2
A/B artifacts, свежего Django 6.1 CI comparison, disposable MariaDB CI,
интеграции в GitHub `main`, deployment и post-deploy proof. Повторный полный
Django 5.2.11 A/B для документационного закрытия не выполнялся.

- [x] Exact runtime подтвержден: CPython 3.14.6, Django 6.1, DRF 3.18.0 и
  mysqlclient 2.2.8; verifier отклоняет любое несовпадение версии.
- [x] Warning-gate RED/GREEN contracts прошли `7/7`; запрещены
  `RemovedInDjango70Warning`, `DeprecationWarning` и
  `PendingDeprecationWarning`, vendor allowlist имеет owner и expiry
  `2026-10-01`.
- [x] Management-command contracts прошли `3/3`: исторический Stage 0 baseline
  был `138/138`; текущий inventory после двух новых non-DTF команд составляет
  `140/140`. Все команды импортируются и строят parser без вызова `handle()`,
  DB и внешней сети.
- [x] Django 6.1 compatibility contracts прошли `17/17`: кроме import checks,
  отдельно доказаны non-DTF schema generation (`44` operations), POST rate
  limit (`10` разрешенных запросов и `429` на следующем), lazy django-redis и
  social-auth begin/callback без обращения к provider.
- [x] Полный explicit non-DTF Django 5.2.11/6.1 A/B artifact совпал: на обеих
  версиях `6080` тестов, `71 failures`, `30 errors`, `10 skipped`; typed delta
  равен `0`. Все `101` outcome occurrence входят в `31` детерминированный
  triage cluster; непроверенные root cause не выданы за доказанный диагноз.
- [x] Production-like static rehearsal прошел: isolated `collectstatic`,
  `compress --force`, WhiteNoise manifest, compressor manifest и render
  manifest-backed assets.
- [x] Migration rehearsal прошел: synthetic drift дает RED, реальный non-DTF
  migration graph дает GREEN; `storefront.0096` подтверждена на локальной
  MariaDB как metadata/state-only migration без физического DDL для трех полей.
- [x] Production-default MariaDB snapshot восстановлен локально вне Git с mode
  `0600`: 332 base tables, 142 InnoDB, 190 MyISAM, 25 triggers, 0 routines и
  0 events; local/production table+engine hash совпал:
  `3166bd1ad8ef8f55680731422ca257e7ee09b0b92064e5ba39d9f1baa316ba70`;
  DTF database отсутствует.
- [x] Финальный короткий локальный release gate прошел: `86/86` Stage 0 tests,
  `check --database=default`, реальный `makemigrations --check`, warning gate,
  текущие `140/140` command parsers, production-like static gate и sanitized
  inventory. Исторический artifact Stage 0 сохраняет `138/138`.
- [x] Schema v2 validation прошла для полного non-DTF и MariaDB A/B artifacts;
  сохраненный Django 6.1 full log повторно совпал с tracked candidate без
  summary/outcome delta. CI выполняет такое же сравнение после fresh smoke.
- [x] Ограничение исторического MariaDB A/B записано явно: DTF test identifiers
  исключены, но setup старых 14-test logs применял DTF migration dependency.
  Полный 6080-test A/B имеет `dtf_migration_setup=not-loaded`; строгий
  DTF-zero setup для исторического MariaDB artifact не заявляется.

---

## Этап 1. Корректность, security и совместимость до Django 7

**Почему сейчас:** это небольшие или средние изменения с высоким риском будущей поломки платежных/почтовых/security контрактов.

Stage 1 завершён поверх release Stage 0. Ниже сохранены закрытые acceptance
contracts для explicit SHA-1, `MAILERS`, URLField, signed cookies, strict Base64,
social-auth admin, active legacy loader и Python 3.15 import compatibility.

- [x] **DJ6-SEC-001 - Явно закрепить algorithm для IG payment \`salted_hmac\`.**
  - Сначала parity test текущих SHA-1 signatures; не менять digest format скрыто.
  - Acceptance: старые события валидируются, новые детерминированы, Django 7 warning отсутствует.
  - Evidence: frozen vector
    `dbd20b4d534cef919aa46493f69b143ee815c3c4` закрепляет SHA-1 при
    контролируемом `SECRET_KEY`; отдельный model test создает старое событие
    через независимую reference HMAC-функцию и подтверждает его прием. Оба
    теста RED при `sha256`, GREEN при explicit `sha1`; warning отсутствует.

- [x] **DJ6-COOKIE-001 - Проверить и ограничить legacy signed-cookie compatibility.**
  - Не включать global fallback бессрочно.
  - Acceptance: session/messages/custom salted token matrix документирует affected и unaffected paths.
  - Выполнено: project setting намеренно отсутствует, runtime
    использует Django 6.1 default `False`. AST inventory фиксирует
    20 non-DTF signing call sites; cached DB sessions, cookie messages и
    девять custom salted formats доказаны unaffected. Focused matrix: `23/23`.

- [x] **DJ6-FORM-001 - Проверить HTTPS default для всех URLField contracts.**
  - Acceptance: stored legacy HTTP/provider URLs, forms и validation errors сохраняют ожидаемое поведение.
  - Выполнено: inventory закрепляет все 16 non-DTF model \`URLField\`; три
    project-owned формы явно используют HTTPS, а explicit HTTP/HTTPS и stored
    legacy HTTP значения сохраняются без скрытой нормализации модели.

- [x] **DJ6-SEC-002 - Включить строгую Base64-валидацию на credential/PII/provider paths.**
  - Acceptance: мусор отклоняется предсказуемо; валидные padded/unpadded payloads имеют тесты; секреты не логируются.
  - Выполнено: общий strict decoder закрывает Google credentials,
    Meta `signed_request`, legacy Telegram start wrapper, три Monobank paths
    и active `views.py.backup`; BinaryField/PII contract и безопасное
    логирование закреплены. Strict matrix: `21/21`, с consumers: `28/28`.

- [x] **DJ6-EMAIL-001 - Перейти на Django 6.1 \`MAILERS\`.**
  - Алиасы: минимум \`default\`, \`transactional\`, \`reports\`, если call graph докажет их необходимость.
  - Acceptance: no-send backends и production SMTP configuration проходят \`mail.E001\`; delivery policy не меняется скрыто.
  - Выполнено: настроены три именованных mailer alias с сохранением текущих
    environment variables; no-network и production-equivalent SMTP contracts
    создают все backend и проходят \`mail.E001\` без отправки писем.

- [x] **DJ6-EMAIL-002 - Удалить deprecated email kwargs и определить exception policy.**
  - Для каждого call site выбрать raise/log/retry/outbox.
  - Acceptance: SMTP exception tests есть для HTTP, cron и recovery paths.
  - Выполнено: восемь non-DTF call sites используют явный \`using=\`, семь
    \`fail_silently=False\` удалены без изменения raise-policy; SMTP failures
    закреплены тестами для HTTP, cron и recovery paths.

- [x] **DJ6-BASE-003 - Закрыть umbrella-пункт MAILERS полным call graph.**
  - Отмечается только вместе с \`DJ6-EMAIL-001\` и \`DJ6-EMAIL-002\`.
  - Выполнено: полный non-DTF call graph и назначение aliases сохранены в
    \`docs/qa/django61-stage1-email-call-graph.md\`; DTF и delivery policy не
    изменялись.

- [x] **DJ6-COMPAT-002 - Устранить social-auth Django 7 warning.**
  - Сначала проверить upstream release; local subclass только при отсутствии безопасного обновления.
  - Выполнено: latest upstream 6.0.1 сохраняет deprecated \`True\` и добавляет
    unrelated login changes, поэтому текущий proven pin оставлен; локальный
    admin использует explicit \`("user",)\`, а vendor allowlist теперь пуст.

- [x] **DJ6-LEGACY-001 - Убрать no-argument \`select_related()\` из активного legacy loader.**
  - Обязательный route test \`/pricelist_opt.xlsx\`; \`views.py.backup\` не считать мертвым.
  - Выполнено: удалены девять no-argument вызовов без изменения explicit
    joins или query shape; XLSX output и wholesale page закреплены route tests.

- [x] **DJ6-PY-001 - Заменить \`SourceFileLoader.load_module()\` до Python 3.15.**
  - Acceptance: forced fallback test проверяет module identity и нормальное распространение import error.
  - Выполнено: fallback использует
    `spec_from_file_location()`/`module_from_spec()`/`exec_module()`, сохраняет
    identity `sys.modules["image_optimizer"]`, очищает модуль при ошибке
    `exec_module()` и не скрывает транзитивный `ModuleNotFoundError`.

### Exit gate этапа 1

- [x] Warning gate не содержит project-owned Django 7/Python 3.15 warnings.
  - Evidence: `blocked_warning_count=0`, `allowed_vendor_warning_count=0`,
    allowlist пуст, все три subprocess завершились с code `0`.
- [x] Payment signature, cookies, URL parsing, Base64 и email имеют regression matrix.
  - Evidence: единый non-DTF Stage 1 gate прошел `61/61`.
- [x] Ни один тест не отправляет реальное письмо или provider event.
  - Evidence: mailer aliases используют `locmem`, socket-level network
    guard включен, SMTP/provider boundaries заменены mocks.

Production acceptance от 2026-08-17:

- code SHA `cdb8f78b13d7b642b12c395afe04eee5d8cb0552` опубликован в GitHub
  `main` и получен production checkout через `git pull --ff-only`;
- production runtime: CPython `3.14.6`, Django `6.1`, MariaDB
  `11.4.12-MariaDB-cll-lve`, cookie fallback `False`;
- storefront, management, storage и finance probes завершились HTTP `200`
  после ожидаемых login redirects;
- production database check выдал только четыре уже вынесенных
  в `DJ6-BASE-004` MariaDB capability warnings; новых Stage 1 warnings нет.

---

## Этап 2. Быстрые ORM-выигрыши с минимальным риском

**Почему раньше фоновых worker и DDL:** это подтвержденные N+1/overfetch проблемы, которые можно исправлять точечно и измерять query-count тестами.

- [x] **DJ6-BASE-001 - Внедрить fetch modes только как локальную стратегию.**
  - Запрещено глобально включать \`FETCH_PEERS\`.
  - Default: сначала исправить projection/prefetch; \`FETCH_PEERS\` применять только при доказанном выигрыше.
  - Выполнено: production default остался \`FETCH_ONE\`; глобальные
    \`FETCH_PEERS\`/\`FETCH_RAISE\` не добавлены. В \`DJ6-ORM-001..010\`
    использованы точные projection, annotation, prefetch и bulk mappings, а
    \`FETCH_RAISE\` включён только в семи test contracts \`DJ6-ORM-012\`.

- [x] **DJ6-ORM-001 - Устранить deferred N+1 в payment snapshots.**
  - Files: \`storefront/views/admin.py\`, \`orders/nova_poshta_documents.py\`.
  - Acceptance: batch из 10 заказов не создает по запросу на \`discount_amount\`.
  - Выполнено: explicit \`discount_amount\` projection сократила endpoint
    с \`11\` до \`1\` business query; 10 payload rows и точные discount/payable
    значения закреплены regression test.

- [x] **DJ6-ORM-002 - Устранить deferred N+1 в frozen value одного reseller.**
  - Acceptance: точная Decimal-сумма и bounded query count.
  - Выполнено: \`is_consignment\` включён в projection; batch из 10 строк
    сократился с \`11\` до \`1\` запроса при точном \`Decimal('246.80')\`.

- [x] **DJ6-ORM-003 - Устранить deferred N+1 в company frozen total.**
  - Не менять broad exception policy в том же change без отдельного теста.
  - Выполнено: company projection также загружает \`is_consignment\` и даёт
    \`11 -> 1\` при точном \`Decimal('246.80')\`; broad exception policy не менялась.

Evidence блока: \`docs/qa/django61-stage2-orm-001-003.md\`.

- [x] **DJ6-ORM-004 - Добавить \`select_related\` для reverse OneToOne в UserAdmin.**
  - Acceptance: пользователи без profile/points корректны; changelist query count стабилен.
  - Выполнено: explicit \`select_related("userprofile", "points")\` сократил
    чтение 10 пользователей с \`21\` до \`1\` запроса; отсутствие любой из
    reverse OneToOne связей сохраняет fallback \`—\`.

- [x] **DJ6-ORM-005 - Заменить Category API N+1 count на annotation.**
  - Acceptance: published/draft/empty category response parity на MariaDB.
  - Выполнено: filtered \`Count\` сократил список десяти категорий с \`12\`
    до \`2\` запросов; published/draft/empty counts совпадают на SQLite и
    disposable MariaDB 11.4.

- [x] **DJ6-ORM-006 - Добавить detail-only Prefetch color variants + color.**
  - List endpoint не должен получить лишний prefetch/payload.
  - Выполнено: detail с тремя вариантами сократился с \`6\` до \`3\`
    запросов; list остался на \`2\` и не читает таблицу вариантов.

- [x] **DJ6-ORM-007 - Заменить до 25 product lookups одним \`in_bulk()\`.**
  - Сохранить порядок analytics rows и fallback удаленных ID.
  - Выполнено: до 25 отдельных product lookups заменены одним
    \`select_related("category").in_bulk()\`; порядок, duplicate/null ID и
    fallback удалённых товаров сохранены.

- [x] **DJ6-ORM-008 - Перенести survey purchase \`exists()\` в \`Exists/OuterRef\`.**
  - Acceptance: parity count и приемлемый MariaDB \`EXPLAIN\`.
  - Выполнено: пять per-session order lookups сведены к одному correlated
    \`Exists\`; user/anonymous semantics и rate \`40.0%\` сохранены. Production
    MariaDB использует индекс \`orders_order_user_id_e9b59eb1\`.

- [x] **DJ6-ORM-009 - Использовать \`values().in_bulk()\` в subtotal корзины.**
  - Acceptance: Decimal, missing product, zero price, discount и invalid quantity parity.
  - Выполнено: один запрос остался одним, но загружает только \`id/price\`
    без model instances; Decimal, missing/zero/discount/invalid quantity parity
    закреплена backend-neutral SQL assertions.

- [x] **DJ6-ORM-010 - Использовать \`values().in_bulk()\` для variant ownership.**
  - Acceptance: wrong/missing/duplicate variant и pending checkout reset не меняются.
  - Выполнено: один запрос загружает только \`id/product_id\`; helper сохраняет
    совместимость с dict/model mappings, очистку wrong/missing/duplicate rows и
    reset pending Monobank state.

- [x] **DJ6-ORM-011 - Сделать paginator querysets totally ordered.**
  - Добавлять unique tie-breaker только после \`EXPLAIN\`; тестировать ties на границе страниц.
  - Выполнено: восемь management/orders/warehouse paginator querysets получили
    unique \`-id\` tie-breaker; \`totally_ordered\` изменился \`False -> True\`,
    boundary tests не допускают пропуски/дубли, MariaDB plans не ухудшились.

- [x] **DJ6-ORM-012 - Добавить \`FETCH_RAISE\` в тесты узких projections.**
  - Production behavior не менять глобально.
  - Выполнено: семь contracts защищают catalog facets, homepage price, sitemap
    и management lifecycle projections; default \`FETCH_ONE\` подтверждён,
    production queryset behavior не изменён.

- [x] **DJ6-ADMIN-001 - Проверить admin query plans и Django 6.1 action API.**
  - Отдельно измерить computed/deep \`list_display\`, которые auto select-related не покрывает.
  - Выполнено: restock actions доступны в change list/change form, имеют
    singular/plural descriptions и требуют \`change\` permission. View-only
    forged POST не меняет записи; changelist из 10 строк выполняет один запрос.

Evidence блока: \`docs/qa/django61-stage2-completion-report.md\`.

### Exit gate этапа 2

- [x] Для каждого ORM-пункта сохранены before/after query counts либо явно
  зафиксировано отсутствие изменения числа запросов для projection/test-only пунктов.
- [x] API/HTML/денежная parity доказана 29 focused contracts.
- [x] Disposable MariaDB \`11.4.12\` gate прошёл с реальными миграциями и
  representative fixtures; production read-only \`EXPLAIN\` не требует нового DDL.
- [x] Ни один глобальный fetch mode не добавлен.

Production acceptance от 2026-08-17:

- code SHA \`505458e919064205113aeb9b88e2e471ac2488ef\` опубликован в GitHub
  \`main\` и получен production checkout через \`git pull --ff-only origin main\`;
- production runtime: CPython \`3.14.6\`, Django \`6.1\`, DRF \`3.18.0\`,
  mysqlclient \`2.2.8\`, MariaDB \`11.4.12\`; pending non-DTF migrations: \`0\`;
- server preflight и post-deploy matrix имеют \`status=ok\`, tracked checkout
  чистый, SHA и \`origin/main\` совпадают с release SHA;
- local и production HTTP matrices прошли все 10 non-DTF probes; ожидаемые
  login redirects остаются \`302\`, DTF scope \`excluded\`;
- \`tmp/restart.txt\` обновлён, после HTTP-запросов Passenger получил новые
  \`lswsgi\` workers; \`run_instagram_bot --ensure\` запустил daemon;
- code diff не содержит migrations/static/templates/assets, поэтому
  \`migrate\`, \`collectstatic\` и \`compress\` для этого release не требовались.

---

## Этап 3. Durable side effects и удаление тяжелой работы из request path

**Архитектурное решение:** до появления реального worker использовать durable DB rows/outbox, idempotency, leases и существующий cron. Не создавать вторых owners одной периодики.

- [x] **DJ6-SRV-005 - Ввести единый cron job contract.**
  - Releases `5d4e358cb`, `c56123c0d` и review-hardening `254bdb3e6`
    добавили три idempotent installer-а для watchdog, четырёх Instagram
    periodic jobs и Nova Poshta tracking; позднее managed contract расширен
    guarded default-OFF owner для автоанализа звонков.
  - На production каждый из семи owners существует ровно в одном managed
    block. Все строки используют `flock -n -E 75` и
    `timeout --signal=TERM --kill-after=15s` с deadline `75/90/180/240s` по
    типу задачи; cadence и batch limits зафиксированы в repository contract.
  - Durable state/leases/provider receipts и retry/backoff остаются внутри
    соответствующих command/service state machines. `task_heartbeat` пишет
    success/failure, а daemon supervision сообщает о failed/stale cron jobs;
    Nova Poshta включена в тот же health contract.
  - Финальный production snapshot: `HEAD == origin/main == 718c41268`, все три
    installer `--check` прошли, семь owner lines и шесть активных heartbeat
    entries healthy; guarded call-analysis выключен, dangerous backlog `0`,
    non-DTF HTTP matrix зелёная. Подробности:
    `docs/qa/django61-stage3-srv-005.md`.

- [x] **DJ6-SRV-010 - Добавить overlap guard для \`run_instagram_bot --ensure\`.**
  - \`--ensure\` теперь считает удерживаемый daemon lock здоровым только при
    свежем heartbeat; stale worker проходит bounded drain/spawn path, а при
    неосвобождённом lock команда завершается ошибкой без второго daemon.
  - Production cron переведён в один managed block с внешним \`flock\`;
    первоначальный release использовал \`timeout 50s\`, а единый contract
    `DJ6-SRV-005` поднял текущий deadline до `75s` с `--kill-after=15s`.
  - Release \`4af27a19b\`: один watchdog line, один managed block, daemon lock
    удерживается, daemon/task heartbeat healthy. Подробности:
    \`docs/qa/django61-stage3-srv-010.md\`.

- [x] **DJ6-BG-001 - Заменить post-payment request daemon на durable outbox/job.**
  - В transaction сохранять только durable intent; внешняя отправка после commit.
  - Acceptance: rollback, crash-before-send, crash-after-send и replay не дают дублей.

- [x] **DJ6-BG-002 - Оставить Monobank invoice sync, вынести CAPI/Telegram.**
  - Не менять Purchase/Lead semantics и сумму события.
  - Acceptance: checkout latency before/after, durable replay и provider mock.

- [x] **DJ6-BG-003 - Убрать пятиминутный Binotel polling из request-owned daemon.**
  - Использовать существующую command state machine, caps и leases.

- [x] **DJ6-BG-005 - Убрать полный Nova Poshta tracking batch из middleware.**
  - Middleware удалён из active request stack; legacy-классы оставлены только
    как pass-through compatibility и не содержат DB/provider/thread работы.
  - Production cron остаётся единственным owner, managed block прошёл
    `--check`; перед release due backlog был `0`.

- [x] **DJ6-BG-006 - Заменить fulfillment wake-up thread, сохранив event semantics.**
  - `kick_order_fulfillment()` больше не создаёт daemon thread; durable
    `IgOrderCustomerEvent` reconciliation остаётся у существующего cron owner.
  - Локальный focused gate прошёл 40 тестов; production due backlog был `0`,
    post-deploy server/HTTP matrices зелёные. Подробности:
    `docs/qa/django61-stage3-bg-005-006.md`.

- [x] **DJ6-BG-007 - Сделать registration notification commit-safe и durable.**
  - Передавать PK/идентификатор, не ORM instance и не PII/password.

- [x] **DJ6-BG-009 - Зафиксировать Telegram logging как отдельный аварийный канал.**
  - Не переносить его в обычную task queue; добавить bounded timeout/fallback и защиту от recursive logging.

- [x] **DJ6-BG-011 - Сохранить sync transaction boundaries.**
  - Любой future async/task adapter получает ID и открывает свою sync transaction.

- [x] **DJ6-LIVE-002 - Разобрать 18 failed Instagram analysis jobs через dry-run.**
  - Сначала report по ID/reason/attempts; адресный retry только с quota budget и без массовой мутации.

### Exit gate этапа 3

- [x] Request завершение не владеет долгоживущим daemon/thread для критичных side effects.
- [x] Все внешние side effects имеют durable state и idempotency marker.
- [x] Повторный command/cron run дает нулевую или детерминированную работу.
- [x] Connection budget остается ниже production лимита \`max_user_connections=20\`.

---

## Этап 4. Security, cache и server observability

- [x] **DJ6-CSP-001 - Перейти на встроенный Django CSP через report-only.**
  - Этап A: эквивалентная policy и сбор violations.
  - Этап B: nonce для собственных inline scripts.
  - Enforce и удаление \`unsafe-inline\`/\`unsafe-eval\` только после browser matrix checkout/analytics.

- [x] **DJ6-SEC-003 - Провести contract-аудит 26 \`csrf_exempt\` endpoints.**
  - Для каждого: auth/signature, replay, rate limit, origin/host, idempotency и negative tests.
  - Массово снимать exemption запрещено.

- [x] **DJ6-BASE-004 - Закрыть MariaDB system-check warnings отдельными contracts.**
  - Сначала duplicate scan и \`SHOW CREATE TABLE\`; затем app-level/concurrency protection или DDL plan.

- [x] **DJ6-DB-002 - Сделать реальные MariaDB constraints частью compatibility gate.**
  - Gate должен отличать unsupported conditional constraint от реально созданного DB constraint.

- [x] **DJ6-SRV-002 - Измерить file cache и запретить считать его durable distributed lock.**
  - Метрики: p50/p95 IO, inode count, cleanup/TTL, concurrent \`cache.add\` semantics.
  - Evidence: \`docs/qa/django61-stage4-observability.md\`; p50 0.143 ms, p95 0.407 ms, 3265 inodes, TTL 300, \`distributed_lock_safe=false\`.

- [x] **DJ6-SRV-007 - Исследовать disk temporary tables по query shapes.**
  - Не менять global MariaDB variables без rights/neighbor impact review.
  - Evidence: \`docs/qa/django61-stage4-observability.md\`; temporary tables delta 1, disk temporary tables delta 0, без \`SET GLOBAL\`.

- [x] **DJ6-SRV-008 - Атрибутировать aborted connections/clients.**
  - Снять дельту, а не только cumulative counter; сопоставить Passenger/cron/daemon lifecycle.
  - Evidence: \`docs/qa/django61-stage4-observability.md\`; aborted clients/connects delta 0/0.

- [x] **DJ6-SRV-009 - Добавить file-descriptor budget в concurrency design.**
  - Измерить open FDs под peak и зафиксировать caps.
  - Evidence: \`docs/qa/django61-stage4-observability.md\`; 5/1024 FDs, utilization 0.488%.

- [x] **DJ6-CACHE-001 - Учесть Django 6.1 cache-key cold start.**
  - Добавить warm-up/observability, не смешивать old/new custom cache keys.
  - Evidence: \`docs/qa/django61-stage4-observability.md\`; cold miss -> warm hit, old-key reads 0.

- [x] **DJ6-AUTH-001 - Измерить PBKDF2 1,500,000 CPU и rehash rate.**
  - Не ослаблять password hasher без отдельного security решения.
  - Evidence: \`docs/qa/django61-stage4-observability.md\`; encode 536.72 ms, verify 688.658 ms, current rehash false, legacy rehash true.

### Exit gate этапа 4

- [x] CSP report-only не ломает GTM/Meta/TikTok/Clarity/checkout на desktop/mobile.
  - Production SHA `4f18e625563f57fb2d1d887a5405294a4798c6a9` подтверждён
    после `git pull`, `collectstatic` и Passenger restart.
  - Desktop и mobile browser evidence закрывает PDP, analytics, `cart/add`,
    mini-cart и открытие cart/checkout page; заказ и платёж не отправлялись.
  - Mobile web-push prompt больше не перекрывает sticky CTA (live CSS asset,
    bottom `90px`, CTA top `760px`, overlap `false`, hit-test в CTA).
  - Read-only `/cart/items/` после deploy вернул `200`; retry ограничен
    безопасными GET/HEAD disconnect-кодами. Детали:
    `docs/qa/django61-stage4-acceptance.md`.
- [x] Каждый \`csrf_exempt\` endpoint имеет записанный security contract.
- [x] Cache, temp tables, DB connections и FDs имеют измеримые dashboards/reports.
  - Evidence: \`docs/qa/django61-stage4-observability.md\`.
- [x] MariaDB warnings больше не воспринимаются как работающие constraints.
  - Evidence: \`docs/qa/django61-stage4-base004-db002.md\`; warnings и conditional constraints разделены fail-closed gate.

---

## Этап 5. MariaDB foundation: InnoDB, constraints и DB actions

**Правило:** один небольшой table family за один change. Никакого массового \`ALTER\` 178 MyISAM таблиц.

- [ ] **DJ6-SRV-003 - Составить и выполнить поэтапный MyISAM -> InnoDB roadmap.**
  - Ранжировать по write criticality, size, orphan risk, index/fulltext behavior и FK graph.
  - Первый canary только на маленькой таблице с rollback/rehearsal.

- [x] **DJ6-SRV-004 - Сохранить connection budget и \`CONN_MAX_AGE=0\`.**
  - Любой новый worker/connection pool проходит capacity test до production.
  - Закрыт только bounded read-only evidence/rehearsal для текущего guardrail;
    production rollout нового worker/pool не выполнен и не разрешён.

- [x] **DJ6-SRV-006 - Защититься от server default latin1.**
  - Предпочесть явные Django/schema defaults; global server change только с host-owner review.
  - Закрыт только fail-closed compatibility evidence; production change global
    charset/default не выполнялся и не разрешён.

- [ ] **DJ6-BASE-002 - Инвентаризировать database-level \`on_delete\` кандидатов.**
  - Проверить engine, real FK, signals, soft delete, orphan data и rollback.

- [x] **DJ6-DB-001 - Испытать \`DB_CASCADE\` только на retention-графе аналитики.**
  - Disposable MariaDB, batch delete benchmark и доказательство отсутствия обязательных delete signals.
  - Закрыт только disposable benchmark/rollback evidence; production adoption
    DB-level cascade не выполнен и остаётся запрещённым до отдельного rollout gate.

- [x] **DJ6-ORM-013 - Испытать \`GeneratedField\` для итоговой цены только в disposable schema.**
  - Decimal/integer parity, discounts 0/1/33/100, MariaDB refresh/deferred behavior и index plan.
  - Закрыт только disposable experiment evidence; production `GeneratedField`
    и DDL rollout не выполнены и остаются запрещёнными до устранения formula drift.

- [ ] **DJ6-MIG-001 - Squash migrations только после стабильного graph и restore drill.**
  - Не удалять historical migrations до applied-history и clean-install proof.

### Exit gate этапа 5

- [ ] Есть одобренная таблица \`model -> engine -> size -> risk -> migration order\`.
- [ ] Первый InnoDB canary имеет backup, rehearsal timing и rollback.
- [ ] DB-level cascade/generated column не внедрены без disposable MariaDB proof.

---

## Этап 6. Реальный task backend и worker capability

**Стартовать только после этапов 0, 3 и server capability review.**

- [ ] **DJ6-BASE-005 - Повторно проверить Redis/worker capability через host owner.**
  - DNS, TCP, TLS, auth, ACL, process lifetime, cron cadence и DB connection budget.

- [ ] **DJ6-SRV-001 - Получить рабочий Redis endpoint или официально выбрать другой backend.**
  - Не менять endpoint/тариф/credentials без согласования.

- [ ] **DJ6-TASK-001 - Выбрать production backend для Django Tasks.**
  - Built-in \`ImmediateBackend\` не считать очередью.
  - Начать с no-send canary с durable DB state.

- [x] **DJ6-TASK-002 - Добавить fail-fast guard против \`ImmediateBackend\` для тяжелых tasks.**
  - Production enqueue тяжелой задачи должен быть невозможен без worker proof.
  - Evidence: `twocomms/task_boundaries.py`,
    `twocomms/management/tests_django61_task_backend_guard.py`,
    `docs/qa/django61-stage6-task-guard.md`; `ImmediateBackend`, `DummyBackend`
    и неизвестные backends блокируются до enqueue.

- [ ] **DJ6-BG-004 - Перенести image optimization jobs во внешний worker.**
  - Только после shared media atomic-write benchmark и lease/recovery tests.

- [ ] **DJ6-BG-008 - Решить судьбу durable QR alert.**
  - Сначала измерить volume/value; не строить queue для малополезного сигнала.

- [ ] **DJ6-BG-010 - Оставить ImageOptimizationMiddleware выключенным до pre-generation proof.**
  - Включение возможно только после worker, atomic media и browser asset verification.

### Exit gate этапа 6

- [ ] Есть один owner каждой периодики.
- [ ] Worker переживает restart и не теряет/не дублирует canary task.
- [ ] Redis/backend и worker не превышают MariaDB connection/FD/process limits.
- [ ] Cron остается rollback path до доказанного production health.

---

## Этап 7. Низкорисковые Django 6.x улучшения и поддерживаемость

- [ ] **DJ6-TPL-001 - Перенести только доказанные full/fragment пары на template partials.**
  - Не заменять общие includes без пользы; начать с 2-3 representative components.

- [ ] **DJ6-TPL-002 - Использовать \`{% querystring %}\` в pagination templates.**
  - Тесты: empty query, repeated params, page replacement, escaped values.

- [x] **DJ6-DOC-001 - Обновить current architecture docs на Python 3.14.6/Django 6.1.**
  - Исторические incident/plans не переписывать.

- [x] **DJ6-DOC-002 - Удалить current-facing инструкции с bare Python/Django 5.2.**
  - Acceptance: README/runbook ведет к exact project runtime и supported deploy path.

- [ ] **DJ6-TEST-001 - Включать forkserver/parallel tests только для stable shards.**
  - Full parallel suite только после устранения shared cache/media/SQLite race.

### Exit gate этапа 7

- [ ] Template changes имеют response parity и browser smoke.
- [x] Current docs не предлагают старый runtime или unsupported deploy scripts.
  - Evidence: `docs/qa/django61-stage7-docs-runtime.md`; current-facing architecture/deploy docs reviewed after integration.
- [ ] Parallelization ускоряет CI без flaky/race роста.

---

## Этап 8. Явно заблокированные или неактуальные функции

Эти чекбоксы не означают «сделать сейчас». Они отмечаются после выполнения условия разблокировки или документированного окончательного отказа.

- [ ] **DJ6-ORM-014 - Не использовать DB \`UUID4/UUID7\` до MariaDB >= 11.7.**
  - После upgrade отдельно классифицировать public/secret/ordered UUID use cases.

- [ ] **DJ6-BASE-006 - Не добавлять async-specific mitigation, пока async runtime отсутствует.**
  - Повторить аудит при первом \`async def\`, async ORM или external async worker.

---

## Обязательный TDD/release шаблон для каждого implementation-пункта

1. Создать отдельный worktree/branch от актуального \`origin/main\`.
2. Снять before baseline: тест, query count, latency, schema или live read-only факт.
3. Написать failing regression test.
4. Запустить тест и зафиксировать ожидаемую причину падения.
5. Реализовать минимальное изменение.
6. Запустить focused tests.
7. Запустить exact-version/no-network Django gate.
8. Для DB/ORM: local MariaDB parity, query count и \`EXPLAIN\`.
9. Запустить migration drift, production-like static gate и \`git diff --check\` по риску изменения.
10. Провести code review отдельным агентом/ревьюером.
11. Commit только scoped files; push и интеграция в \`main\`.
12. При разрешенном production rollout использовать только deploy-путь из \`AGENTS.md\`.
13. Подтвердить deployed SHA, migrations/check, Passenger и scoped live behavior.
14. Только после доказательства отметить соответствующий checkbox.

## Нельзя объединять в один change

- CI baseline и массовые business fixes.
- Email \`MAILERS\` и worker/outbox migration.
- ORM N+1 fixes и MariaDB engine conversion.
- CSP report-only и CSP enforcement.
- MyISAM -> InnoDB нескольких крупных app families.
- Redis/backend setup и перенос всех cron jobs.
- Test expectation fix и изменение production Schema.org semantics.
- Django 6.1 compatibility fixes и unrelated feature redesign.

## Контроль покрытия аудита

- [ ] Все 83 \`DJ6-*\` ID присутствуют в этом плане ровно один раз как implementation checkbox.
- [ ] Ни один DTF finding не добавлен.
- [ ] Заблокированные пункты имеют условие разблокировки.
- [ ] Для каждого этапа определен exit gate.
- [ ] Приоритет сначала защищает release/деньги/данные, затем дает performance boost, затем меняет архитектуру.

## Ожидаемый эффект по завершении

- Deploy и CI всегда используют CPython 3.14.6/Django 6.1 и не вызывают внешние side effects.
- Критичные платежные, email, cookie и security contracts готовы к Django 7.
- Подтвержденные N+1 устранены с измеримым снижением SQL round-trip.
- Критичные внешние side effects становятся durable и replay-safe.
- Server limits, cache и MariaDB bottlenecks измеряются, а не предполагаются.
- InnoDB/constraints/task backend внедряются постепенно с rollback и production evidence.
- Новые возможности Django 6.0/6.1 используются там, где дают реальный выигрыш, а не ради самого факта обновления.
