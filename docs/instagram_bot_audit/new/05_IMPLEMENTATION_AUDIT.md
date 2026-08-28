# 05 - Аудит implementation-плана Instagram-бота TwoComms

Дата аудита: 2026-08-27.

Проверяемый документ: `04_IMPLEMENTATION.md`.

Источники: `01_FINDINGS.md`, `02_ANALYSIS.md`, `03_ADDITIONAL_FINDINGS.md`,
текущий локальный `HEAD` `cb4d6463b3f3adcccb0402e2adb32870ed6e5636`, исходники
Instagram-бота и актуальная документация Meta, проверенная 2026-08-27.

## 0. Как читать этот аудит

Это независимый engineering review плана, а не новый канонический план и не
решение владельца продукта. Цель - дать следующему агенту материал для
осознанной коррекции: что уже хорошо сформулировано, где есть доказанная
неточность, где есть только гипотеза, а где сначала нужно получить policy или
production evidence.

Я не изменял `04_IMPLEMENTATION.md`, код или миграции. Этот файл намеренно
содержит альтернативы и вопросы. Формулировка «исправить» означает
«рассмотреть как обязательную коррекцию перед реализацией», а не
автоматическое указание вне продуктового решения.

### Ограничения доказательств

- В рабочем дереве есть многочисленные чужие незакоммиченные изменения и
  неотслеживаемые артефакты. Они не являются частью этого review и не должны
  быть откатаны.
- Свежий production SSH/MariaDB probe в этом продолжении не выполнялся:
  `TWOCOMMS_DEPLOY_PASSWORD` отсутствует в окружении. Исторические цифры из
  `01/02/03` поэтому обозначаются как historical или требуют повторной
  read-only проверки.
- `manage.py check` с проектным `.venv` (CPython 3.14.6, Django 6.1) прошёл.
  Четыре набора focused-тестов не дошли до тестовых методов на чистой SQLite
  БД: миграция `0158_ig_ugc_intelligence` требует
  `IG_UGC_IDENTITY_HMAC_KEYRING` и active key id. Это отдельный environment
  precondition, а не доказательство отсутствия или наличия бизнес-регрессии.
- Я не использовал live Meta/Telegram/customer sends. Документация Meta и
  чистые serialization/policy проверки не заменяют проверку конкретного
  приложения, токена, Graph API version и scopes проекта.

## 1. Краткий вывод

План очень силён как карта рисков: он сохраняет append-only evidence, не делает
модель источником цены или наличия, отделяет post-sale от `IgClient.stage`,
требует receipt-first и не предлагает бездумный автоперманентный бан за
prompt-injection. Это хорошие архитектурные границы.

Однако до начала реализации нужно исправить несколько блокирующих логических
мест. Самые опасные ошибки находятся не в отдельных названиях карточек, а на
стыках policy, transaction, delivery и authoritative data:

| Приоритет | Место плана | Вердикт | Почему это блокирует реализацию |
|---|---|---|---|
| P0 | `04:398-489`, Э1.0-Э1.1 | **Перепроверить и, вероятно, переписать** | План строит вне-24-hour Instagram delivery на `notification_messages`/One-Time Notification. В актуальной Meta-документации One-Time Notifications прямо указаны как недоступные для Instagram Messaging API. Нельзя создавать модель токена и обещать доставку до подтверждения точного IG-контракта. |
| P0 | `04:1285-1325`, Э2.7 | **Исправить** | Запрещать `ensure_lifecycle_event()` внутри транзакции неправильно: durable lifecycle row должен быть атомарен с изменением заказа/оплаты. В транзакцию нельзя помещать только HTTP dispatch. |
| P0 | `04:704-747`, `883-917`, Э1.6/Э1.10 | **Исправить** | `payment_truth_snapshot` не является источником ещё не оплаченной котировки. Для карточки нужны поля текущего `IgCheckoutProposal`; prepayment и full payment должны быть явно разделены. |
| P0 | `04:726-729`, Э1.6 | **Исправить** | Нажатие `web_url` не даёт webhook-события. `PAYLINK_VIEWED` можно доказать на защищённом first-party checkout GET, а не на самом клике Instagram. |
| P0 | `04:583-647`, Э1.4 | **Расширить** | Текущая нормализация действительно выбрасывает postback, но для исправления недостаточно «добавить роутер»: нужна новая нормализованная event-схема, потому что у postback может не быть обычного `mid`. |
| P0 | `04:491-532`, Э1.2 | **Расширить** | Единый `send_template()` должен покрыть text/media/card durable outbox и provider receipt. Текущий `send_catalog_media()` считает HTTP 200 успехом даже без message ID и не имеет тех же гарантий, что text sender. |
| P0 | `04:649-700`, Э1.5 | **Переставить dependency** | Карусель требует variant/fit/size-aware media resolver, а текущий `select_catalog_media()` принимает только product IDs. Нельзя выкатывать визуальное обещание до resolver-а. |
| P1 | `04:994-998`, карта этапов | **Переставить** | Э2 содержит P0-поломки доставки, но стоит после десяти customer-visible card slices. Карточки частично уменьшают текстовый шум, но не исправляют silent tail loss, окно Meta, lock и ambiguous receipt. |
| P1 | `04:29-43`, общий DoD | **Сделать классовым** | RED->GREEN, baseline metric и deploy разумны для дефектов, но не подходят одинаково для MEASURE, POLICY, docs-only и тестовой инфраструктуры. Нельзя требовать deployment для pure read-only measurement и RED-теста, который не меняет runtime. |
| P1 | `04:45-59`, commit/deploy | **Уточнить** | Feature flag не откатывает миграцию, уже отправленный внешний message или изменённую схему event identity. Нужны expand/contract, dual-read, backfill и явный ambiguous state. |
| P1 | `04:103-108`, deferred list | **Дополнить** | `NEW-PROMPT-001`, `NEW-LINK-002`, `NEW-LINK-006`, `NEW-SUBFUNNEL-004/008/009` отсутствуют как самостоятельные решения; `NEW-PROMPT-002` фактически только упомянут в shadow rule. Это мешает доказать полноту handoff. |

### Главная рекомендация

Сначала сделать короткий Wave 0 из factual gates и durable delivery contracts,
затем ограниченный card slice только внутри подтверждённого Meta окна. Не
делать всю Э1 customer-visible до того, как sender, receipt, event identity,
proposal pricing и variant media имеют один источник истины.

## 2. Доказательная база по текущему коду

### 2.1 Webhook и postback

В `twocomms/management/services/instagram_bot.py:11485-11542` `_iter_events()`
создаёт пустой `message` для события с `postback`, хотя referral из postback
забирается. В `:11946-12005` `handle_webhook_payload()` сразу делает
`if not msg: continue`. `_quick_reply_payload()` в `:11703-11707` читает только
`message.quick_reply`, а не `event.postback`. Следовательно, Э1.4 правильно
называет текущий дефект, но её acceptance должен проверять всю нормализованную
event boundary, а не только условие `if not msg`.

Нужно различать как минимум:

```text
interaction_type       message | quick_reply | postback | reaction | control
provider_event_id      стабильный ID события, если Meta его даёт
provider_message_id    обычный message ID, если он существует
payload                 непустой payload кнопки/quick reply
reply_to_provider_id   ID исходной карточки, если он пришёл
source_card_revision   наша версия карточки/сессии
provider_timestamp     время Meta, отдельно от local ingest time
```

`provider_message_id` нельзя заранее назначать универсальным idempotency key для
postback. Повторное событие может иметь другой envelope или вообще не иметь
обычного message ID. Сервер должен проверять подписанный/opaque card token,
current session, episode, line, revision и nonce.

### 2.2 Card/media transport

`twocomms/management/services/ig_catalog_media.py:142-220` показывает, что
`select_catalog_media(product_ids)` перебирает все `stock__gt=0` variants и
возвращает `product_id`, но не exact `variant_id`, `fit`, `size` или option
revision. `send_catalog_media()` в `:263-368` делает HTTP-запрос картинки,
регистрирует outgoing ID только если он вернулся, и при HTTP 200 может вернуть
`SENT` без provider message ID. Это расходится с receipt-first контрактом
`InstagramBotMessage`/`IgCommerceTurnDecision`.

Нельзя просто добавить ещё один `send_template()` рядом. Нужна одна логическая
delivery abstraction с типами payload:

```text
text | image | generic_template | carousel | quick_replies
```

У неё должны быть общие состояния `planned -> preflight -> sending -> sent /
unknown / failed / cancelled`, provider IDs по каждому физическому сообщению,
одна logical delivery ID и fallback только до начала неоднозначного provider
I/O. После timeout нельзя автоматически отправлять fallback: Meta могла принять
первый запрос.

### 2.3 Payment proposal и payment truth

`IgCheckoutProposal` в `twocomms/management/ig_bot_models.py:2209-2305`
содержит `catalog_total`, `negotiated_discount`, `quoted_total`,
`requested_payment_amount`, `pay_type`, `revision`, `expires_at` и status
`READY/VIEWED/.../PAID`. Это frozen offer.

`payment_truth_snapshot()` и payment projection описывают provider-confirmed
payment state. Для новой карточки до оплаты источник должен быть таким:

```text
current deal -> active IgCheckoutProposal -> quote/revision/pay_type/access token
```

После оплаты источник факта оплаты остаётся payment projection/provider evidence.
Подмена этих двух понятий создаёт опасный сценарий: клиент видит сумму
предоплаты, принимает её за полную стоимость или получает старую сумму из
исторической памяти.

### 2.4 Lifecycle transaction boundary

`IgLifecycleEvent` в `twocomms/management/ig_bot_models.py:2814-2924` имеет
обязательные связи с client, deal, proposal, order, commercial episode и
attribution. `clean()` требует order, exact attribution и proposal с
`payment_attempt`.

Отсюда следует важное исправление Э2.7 и Э6.1:

1. Изменение заказа/оплаты и создание durable lifecycle/outbox row должны быть
   в одной транзакции.
2. После commit можно зарегистрировать wake-up для dispatcher.
3. Provider HTTP должен выполняться вне транзакции и под отдельным lease.
4. Если Meta результат неизвестен, row остаётся `UNKNOWN`/reconciliation, а не
   слепо повторяется.

Перенос самой записи lifecycle в `on_commit()` теряет событие при падении
процесса между commit бизнес-изменения и callback. `on_commit()` подходит для
пробуждения уже созданной durable задачи, не для единственного места её
создания.

### 2.5 Commerce state и through-связи

`IgCommerceSelectionSession` уже является durable state с generation, lines,
constraints и revision (`ig_bot_models.py:5083-5181`).
`IgCommerceSelectionTransition` и `IgCommerceTurnDecision` используют
`OneToOneField(source_message)` (`:5192-5235`, `:5268-5373`). Поэтому новый
`CustomerTurn`, объединяющий несколько inbound, должен иметь:

- `Turn` с episode/client, debounce interval и claim state;
- through-таблицу `TurnMessage` для всех source messages;
- один primary source message для старых OneToOne-контрактов;
- append-only provenance для всех остальных сообщений.

Простое добавление `consumed_by_turn_id` без решения для существующих
OneToOne-связей создаст невозможную схему: один decision всё ещё требует одну
строку, а turn содержит несколько.

### 2.6 SQLite migration baseline

`twocomms/storefront/migrations/0097_mariadb_generated_uniqueness.py:181-232`
использует `SeparateDatabaseAndState`: generated column добавляется в state для
всех backend, а database operation реально выполняется только на MariaDB
(`:30-37`, `:133-155`). Это подтверждает `NEW-TEST-001`.

Но план должен явно считать environment key precondition частью test setup:
`0158_ig_ugc_intelligence` останавливает создание чистой test DB без
`IG_UGC_IDENTITY_HMAC_KEYRING` и active key id. Иначе агент будет путать две
разные проблемы: schema divergence и секреты миграционного preflight.

### 2.7 Storage-engine inventory

Команда `audit_ig_table_engines.py` читает `IG_RUNTIME_TABLES` из
`twocomms/management/services/ig_engine_health.py:1-37`. Список уже шире, чем
простые client/follow-up таблицы, и это хорошо. Но перед тем как считать его
полным, нужно сверить его с новыми commerce/post-sale моделями: в текущем списке
не видно как минимум `IgPostSaleCase`, `IgOrderShipment`,
`IgCommerceSelectionSession`, `IgCommerceSelectionTransition`,
`IgCommerceTurnDecision` и manager-review таблиц. Команда является хорошим
инструментом, но не доказательством полноты inventory сама по себе.

## 3. Поправки к общим правилам плана

### 3.1 Definition of Done должен зависеть от класса находки

Текущий универсальный DoD (`04:29-43`) полезен как контроль качества, но его
нужно разложить:

| Класс | Минимальный DoD | Что нельзя требовать автоматически |
|---|---|---|
| DEFECT | RED reproducer, GREEN fix, forbidden side effects, focused suite, source trace, rollback/compatibility | production metric до накопления достаточной выборки |
| MEASURE | read-only query/command, scope, timestamp, redaction, reproducible output | RED->GREEN и deployment, если runtime не менялся |
| POLICY | documented owner decision, exact provider/app/version/scope evidence, no-send test | модель/миграция «на всякий случай» |
| GAP | product owner acceptance, falsifiable baseline, narrow slice and safety case | широкая новая FSM без подтверждённой нужности |
| DOC/TEST INFRA | deterministic fixture and environment contract | customer-visible deployment, если код поведения не менялся |

Для карточек и delivery добавляется provider-contract acceptance. Для миграций
добавляется expand/contract and backfill plan. Для аналитики добавляется
denominator, time window, cohort and censoring rule.

### 3.2 «Метрика» должна быть фальсифицируемой и определённой

Фразы вроде «должна упасть», «должно стать 0» полезны как направление, но
недостаточны. Для каждой метрики записать:

- numerator/denominator;
- период и timezone;
- cohort и исключения;
- source rows и event timestamp;
- минимальный sample size;
- guardrail metrics (ошибочные claims, возвраты, opt-out, unknown delivery);
- условие остановки, если основной показатель растёт за счёт вреда.

Например, CTR карточки не доказывает корректность: высокий CTR при неверном
variant photo хуже низкого CTR. `PAYLINK_VIEWED` должен иметь отдельные
знаменатели для `button_rendered`, `checkout_page_viewed` и `payment_created`.

### 3.3 Rollback нельзя сводить к feature flag

Флаг помогает переключить чтение/отправку, но не возвращает уже отправленное
сообщение, не удаляет provider side effect и не откатывает `GeneratedField` или
новый event identity. Для миграционных шагов нужны:

1. expand schema;
2. dual-read/dual-write или backfill;
3. consistency report;
4. переключение флага;
5. contract verification;
6. только затем contract/cleanup migration.

Для ambiguous provider result rollback означает `UNKNOWN + reconciliation`, а
не повторный send и не удаление row.

### 3.4 Production deployment rule

План правильно запрещает `git add .` и сохраняет SSH-процедуру. Дополнить:

- docs-only audit не требует production deployment;
- migration deploy должен включать backup/restore readiness, migrate/check,
  точечную runtime-проверку и deployed SHA;
- не выполнять broad crawler smoke на shared host;
- после каждого customer-visible card slice проверять только малый
  последовательный endpoint set, provider response через mocks/approved test
  account и persisted outbox state;
- не считать `daemon spawned` доказательством liveness.

## 4. Аудит последовательности этапов

### 4.1 Э0 - фундамент проверяемости

**Что хорошо:** план начинает с test honesty, engine inventory, lifecycle
reachability, policy object, action corpus, turn identity и customer SLO. Это
лучше, чем сразу добавлять десятки prompt-флагов.

**Главная неточность:** утверждение `04:129-135`, что Э0 не меняет клиентское
поведение и все его шаги независимы, неверно. Э0.4, Э0.6 и часть Э0.7 после
переключения меняют routing/delay/observability. Их нужно пометить как
`no-customer-behaviour only until flag is enabled`, а зависимости описать
точнее.

#### Э0.1 - SQLite commerce schema

- **Нравится:** план не предлагает переписать шесть `invalid_options` ожиданий
  вслепую; сначала отделяет schema failure от domain contract.
- **Проблема:** «выбрать generated column или test matrix» слишком грубо. Нужно
  отдельно решить Django model state, SQLite capabilities, MariaDB physical
  schema и тестовый routing. Model field не должен объявляться существующим на
  backend, где migration намеренно его не создаёт.
- **Доработка:** добавить test setup с локальным HMAC key fixture; проверить
  `makemigrations --check`, migrate from zero и migrate forward/backward на
  SQLite и disposable MariaDB; после schema fix классифицировать 26 schema
  errors и 6 `invalid_options` независимо.
- **Acceptance:** `ProductFitOption` создаётся на чистой SQLite; MariaDB
  generated expression/index проверены; ни один тест не пропускается только
  потому, что backend неудобен.

#### Э0.2 - Storage engine

- **Нравится:** read-only production inventory и запрет побочной конверсии -
  правильная осторожность.
- **Проблема:** текущая команда проверяет только перечисленный constant. Если
  новый commerce/post-sale table отсутствует в `IG_RUNTIME_TABLES`, отчёт
  формально зелёный и неполный.
- **Доработка:** сначала сгенерировать candidate table set из Django model
  metadata и вручную сверить его с lock/lease writers; для каждой строки указать
  `engine`, `used_by`, `lock contract`, `missing/unknown`.
- **Acceptance:** InnoDB inventory всех реально блокируемых таблиц; disposable
  MariaDB race test отдельно доказывает exact lease/CAS contract.

#### Э0.3 - Lifecycle reason funnel

- **Нравится:** требование измерить `window closed`, отсутствие event и COD до
  изменения логики - сильное.
- **Проблема:** `IgLifecycleEvent` хранит текущее состояние, attempts, lease,
  provider ID и last error, но не append-only history всех переходов. Из одной
  строки нельзя честно восстановить полную цепочку `created -> claimed -> send
  attempt -> receipt`.
- **Доработка:** либо назвать результат `terminal disposition projection`, либо
  добавить append-only transition audit. Assignment не доказывает lifecycle
  eligibility: один Order может иметь несколько shipment/episode/assignment.
- **Acceptance:** запрос возвращает scope, denominator, current state, terminal
  reason и age; отсутствие исторического transition не выдаётся за доказанное
  время остановки.

#### Э0.4 - Outbound policy decision

- **Нравится:** чистая функция без I/O, reason code и `allow` != send.
- **Проблема:** условие «внутри окна ИЛИ token ИЛИ service response human» нельзя
  считать общей Meta policy. Human-authored text не отменяет platform window.
- **Доработка:** вход должен содержать `platform_contract_version`, event kind,
  message purpose, channel/app type, token scope, latest user provider timestamp,
  frequency and case state. Решение должно возвращать `policy_basis`, а при
  неизвестной capability - `block/defer`, не `allow`.
- **Acceptance:** policy tests не делают provider calls; для неизвестного IG
  notification capability нет customer send.

#### Э0.5 - Action evaluation corpus

- **Нравится:** forbidden actions и replay без внешних событий - один из лучших
  пунктов плана.
- **Проблема:** RED->GREEN для первого корпуса не всегда существует: новый
  evaluation infrastructure может быть чистым GAP. Требование 100% safety
  должно иметь versioned corpus, иначе агент начнёт подгонять expected output.
- **Доработка:** зафиксировать provider boundary mocks, model/prompt version,
  deterministic seeds, state snapshot и запрет реальных network calls. Разделить
  hard safety failures и мягкую текстовую rubric.
- **Acceptance:** любой forbidden side effect fail-ит сценарий, даже при
  красивом тексте; expected action не генерируется моделью.

#### Э0.6 - CustomerTurn

- **Нравится:** единая identity для burst, dedupe и provenance.
- **Проблема:** нельзя сделать сущность только с `source_message_ids` и
  `consumed_by_turn_id`: существующие transition/decision OneToOne требуют один
  primary source. Также «окно взять из messages-per-turn» - circular: метрика
  описывает текущий режим, но не доказывает оптимальный debounce.
- **Доработка:** through-table, primary message, event ordering, late arrival,
  duplicate webhook, explicit postback/quick-reply bypass и bounded max wait.
  Подобрать debounce через controlled metric, а не объявлять metric источником
  константы.
- **Acceptance:** три burst inbound дают один turn/один execution, raw rows
  сохраняются, postback не ждёт debounce, late message после deadline создаёт
  новый turn.

#### Э0.7 - Customer SLO

- **Нравится:** terminal correctness отделена от heartbeat, p50 от p95/p99.
- **Проблема:** `unknown` receipt - terminal observation, но не корректный
  customer outcome. Также «единственная метрика успеха» в `04:4499-4507`
  слишком агрегирована и легко скроет cohort failure.
- **Доработка:** определить `correct_final_outcome` отдельно от
  `terminal_disposition`; показывать cohort safety, policy blocks и unknown.
  Admin panel не должна блокировать каждую маленькую docs/test slice.
- **Acceptance:** одинаковые numerator/denominator в UI, report и rollout
  decision; critical cohort regression блокирует policy rollout.

### 4.2 Э1 - Meta Opt-In и интерактивные карточки

**Общая оценка:** приоритет владельца понятен, а правило «payload, URL, сумма и
номер ТТН не генерирует модель» обязательно нужно сохранить. Но формулировка
«Э1 первым» технически опасна: часть Э1 зависит от ещё не подтверждённого
канала вне окна, а часть требует P0 delivery contracts из Э2 и variant resolver
из Э3. Без перестановки карточки могут сделать уже существующую ошибку более
убедительной для клиента.

#### Э1.0 - Проверка доступности consent/notification protocol

- **Нравится:** наличие отдельного policy gate до миграции - правильный подход.
- **Критическая поправка:** в актуальной документации Meta для Send API
  (`https://developers.facebook.com/docs/messenger-platform/send-messages/`)
  раздел Instagram говорит, что стандартное окно составляет 24 часа; там же
  прямо указано, что One-Time Notifications и Sponsored Messages недоступны
  для Instagram Messaging API. Документ `messaging_optins` описывает
  `notification_messages` в Messenger-контексте, поэтому нельзя считать его
  доказательством Instagram token flow.
- **Что это меняет:** пока не проверены фактический тип IG приложения (linked
  Page или Instagram Login), Graph API version, endpoint, scope и доступный
  message type, Э1.1 нельзя считать реализуемой. «Если недоступно - перейти к
  Э1.2» недостаточно: нужно также пометить все post-24h карточки и proactive
  sends как blocked/deferred, оставив карточки внутри стандартного окна.
- **Acceptance:** письменная таблица `app_type -> endpoint -> scope -> message
  type -> window -> review requirement`, со ссылкой на Meta docs и датой.
  Никаких customer sends для capability, которую документация на IG запрещает.

#### Э1.1 - Opt-in model/token

- **Нравится:** секретность token, topic scoping, revocation и idempotency
  предусмотрены правильно.
- **Проблема:** поля `token`, `token_expires_at`, `topic` и условие
  `inside_window OR token OR human service response` предполагают конкретную
  Meta функцию, которой для Instagram может не быть. Человеческий ответ не
  является универсальным обходом platform policy.
- **Доработка:** до policy decision описать нейтральный `OutboundConsent`
  registry только для доказанных каналов. Для IG, где нет допустимого token
  flow, оставить `inside_window` и deterministic next-contact handling. Не
  создавать токен из клика по нашей карточке, если Meta не присылает
  authoritative opt-in webhook.
- **Доработка:** «дослать при следующем контакте» применимо не ко всем событиям.
  Review/UGC/marketing message через месяц может быть неуместным и незаконным;
  для каждого event kind нужны TTL, purpose и policy basis.
- **Acceptance:** revoke блокирует pending task до provider I/O; отсутствие
  доказанного consent не превращается в `allow`; неавторизованный event имеет
  видимую terminal reason, а не бесконечный retry.

#### Э1.2 - Template/card transport

- **Нравится:** fallback prepared before send, CRM projection и отображение
  кнопок в истории модели - сильные требования.
- **Критическая поправка:** `send_template()` нельзя проектировать как
  самостоятельный sender. Он должен использовать тот же durable outbox,
  permission fence, receipt-first и ambiguous result semantics, что text,
  image и commerce delivery. `send_catalog_media()` сейчас возвращает SENT при
  HTTP 200 без обязательного provider ID (`ig_catalog_media.py:263-368`).
- **Важный fallback нюанс:** fallback на текст допустим для deterministic
  preflight rejection (например, локальный лимит или недоступный asset до
  provider I/O). После timeout/connection reset нельзя автоматически отправлять
  текст: карточка могла быть принята Meta. Это должно стать `UNKNOWN` + manager
  reconciliation, иначе «fallback» породит дубль.
- **Доработка:** добавить logical delivery ID, payload revision, physical
  message IDs, `SENT/PARTIAL/UNKNOWN/FAILED/CANCELLED`, safe retry policy и
  provider error classification. Сохранение JSON payload и text projection
  должно быть immutable после начала отправки.
- **Acceptance:** provider 200 без message ID не считается SENT; partial media
  не вызывает второй полный fallback; duplicate task не создаёт второй logical
  delivery; CRM видит фактический payload/projection.

#### Э1.3 - Meta limits and degradation

- **Нравится:** приоритет полей вместо тупой обрезки - правильная идея.
- **Проверенный контракт:** generic template documentation для Instagram
  указывает title 80 characters, subtitle 80, максимум 3 buttons per element и
  максимум 10 elements; quick replies documentation указывает максимум 13
  кнопок и 20 characters на title. Эти лимиты нужно версионировать по API
  surface, а не смешивать с текстовым `950 UTF-8 bytes`.
- **Проблемы формулировки:** документация говорит о characters, а текущий
  text sender режет по UTF-8 bytes; для JSON body, URL, emoji и combining
  marks нужно проверять и semantic character limit, и фактический serialized
  request. Нельзя считать, что один лимит подходит для title, subtitle, button
  title, quick reply и image metadata.
- **Доработка:** для каждого card type объявить field budget, locale, Unicode
  normalization, URL validation, MIME/size and fallback. `display_short` не
  должен быть неуправляемым runtime auto-truncation; лучше curated/validated
  display name с revision.
- **Acceptance:** longest real product, longest branch/TTN, mixed-language,
  emoji, URL without spaces и missing image проходят preflight без provider
  call; critical field никогда не теряется молча.

#### Э1.4 - Postback as deterministic FSM action

- **Нравится:** обход LLM, signed/generation-aware payload, мягкая обработка
  stale click и no-debounce - всё верно по направлению.
- **Недоработка:** текущий `_iter_events()`/`handle_webhook_payload()` не дают
  payload в queue. Нужна нормализованная event schema из раздела 2.1, а не
  просто расширение `_quick_reply_payload()`.
- **Idempotency поправка:** ключ `payload + provider_message_id` недостаточен,
  если postback не имеет message ID или повторный envelope получает другой ID.
  Нужна canonical provider event identity, card instance/revision, signed
  action nonce и уникальное ограничение на logical action. Один и тот же
  payload на двух разных карточках не должен считаться одной операцией.
- **Security/commerce:** до изменения состояния сервер проверяет current
  client, episode, session, line, product, variant, fit, option values,
  generation/revision, expiry и permission. Postback не должен обходить
  `can_issue_link`, payment approval, inventory truth или manager takeover.
- **Acceptance:** generic button (`postback`) и quick reply (`message.quick_reply`)
  имеют разные event types; повтор webhook идемпотентен; stale action не
  изменяет state; обычный LLM path получает уже committed state только при
  необходимости.

#### Э1.5 - Catalog carousel and size card

- **Нравится:** максимум 3 product elements как UX policy, запрет показывать
  три размера из шести и exact variant media - хорошие решения. Нельзя
  заставлять клиента угадывать скрытые размеры.
- **Критический dependency:** текущий `select_catalog_media()` не может дать
  exact variant photo. Э1.5 должен зависеть от нового resolver-а, а не просто
  вызывать существующую функцию. Product carousel и size card должны иметь
  разные selection contracts: для первого нужна candidate digest, для второго
  current line/variant/fit/size revision.
- **Payload поправка:** `size:<gen>:set:<S>` не содержит достаточно контекста.
  Без server-side current selection устаревший L в другом цвете/фасоне может
  закрыть неверную line. Использовать opaque signed card token, связанный с
  session/line/revision; raw DB IDs не считать защитой сами по себе.
- **`_disabled_sizes()` не authority:** кнопки должны строиться тем же
  `variant_allows_purchase`/effective option resolver, который позже принимает
  checkout. Disabled rule может быть только одним входом.
- **Carousel count:** «3» - продуктовая политика choice overload, а не Meta
  limit. Кнопка `Показати ще` должна создавать новую candidate revision и не
  обещать, что отсутствующие в первой карусели товары отсутствуют в каталоге.

#### Матрица размеров для реализации

| Доступные размеры после resolver-а | Рекомендуемый UI | Закрытие узла |
|---|---|---|
| 0 | Текст о недоступности/неопределённости, возможные альтернативы или manager case; кнопка размера не показывается | Не закрывать автоматически; сохранить reason `unavailable/unknown` |
| 1 | Одна явная кнопка `Підтвердити S` или текст + явное подтверждение; не молча выбирать | Закрыть только после явного customer action |
| 2 | Две generic-template postback buttons | Одна кнопка = одна signed action для текущей line |
| 3 | Три postback buttons | Все доступные, без скрытого четвёртого варианта |
| 4-13 | Quick replies, только если подтверждён Instagram API contract; иначе size-grid/текстовая таблица с выбором | Quick reply создаёт message event и обрабатывается как отдельный typed event |
| Более 13 | Пагинация/first-party size page/текстовый выбор; не обрезать до 13 без сообщения о продолжении | Каждая страница имеет собственную revision и expiry |

Для каждого варианта нужны тесты: `available`, `disabled`, `unknown`, quantity,
fit, color variant, option values, stale revision, повторный click и смена
товара между render и click. При одном доступном размере нельзя молча отправить
счёт: explicit confirmation всё равно нужна, если размер является коммерчески
значимым выбором.

#### Э1.6 - Checkout/payment card

- **Нравится:** pay button first, `can_issue_link`, no model-generated URL и
  отдельные Edit/Help actions.
- **Критическая поправка к сумме:** использовать `IgCheckoutProposal` с
  `catalog_total`, `quoted_total`, `requested_payment_amount`, `pay_type`,
  `revision`, `expires_at`, а не `payment_truth_snapshot` для ещё не
  оплаченного offer. Payment truth нужен для уже подтверждённой оплаты.
- **Prepayment:** карточка обязана явно показывать `передоплата X` и
  `повна вартість Y`, если обе величины релевантны. Сумма предоплаты не должна
  выглядеть как полный order total. Сохраняется проектное правило: prepayment
  и full payment остаются одной Purchase с полной discounted order value и
  отдельным paid value, не вторым заказом.
- **Discount:** `negotiated_discount` в proposal - денежная сумма, а
  `IgClient.discount_offered_percent` - mutable CRM. Процент разрешено
  отображать только при authoritative approval evidence и совпадении с текущим
  revision; иначе показывать только валидную итоговую сумму или не показывать
  discount label.
- **`PAYLINK_VIEWED`:** клик web URL внутри Instagram не является нашим
  webhook. События нужно разделить: `button_rendered`, `button_clicked` если
  Meta действительно присылает событие, и `checkout_page_viewed` на
  authenticated/opaque first-party GET. Прямой Monobank URL не позволяет
  честно записать `PAYLINK_VIEWED`.
- **Acceptance:** card привязана к конкретному proposal/access-token revision;
  expired/superseded/paid proposal не выдаёт новый link; repeated click не
  создаёт proposal/invoice; first-party view transition идемпотентен; сумма и
  pay type проходят final revalidation перед send.

#### Э1.7 - Delivery/status cards

- **Нравится:** не обещать unknown storage date и не начинать жалобу с
  бюрократической карточки.
- **Проблема:** `Order.tracking_number` - scalar; проект уже имеет append-only
  `IgOrderShipment` с несколькими направлениями, заменами и возвратами
  (`ig_bot_models.py:3541-3642`). Карточка должна читать exact shipment,
  purpose/direction и current status, иначе replacement TTN может быть показан
  как initial shipment.
- **Проблема с текстом:** «1-3 робочі дні» - promise. Нужен подтверждённый
  ETA source; при отсутствии - только факт отправки/TTN. Номер отделения и
  storage deadline нельзя заполнить предположением.
- **Code 7:** добавить arrival event можно только после Gate 1/2/3 из плана;
  event key должен включать shipment identity/purpose, а не только order.
  Перед send нужна final recheck: parcel мог быть забран между tracking update
  и provider I/O.
- **Proactive care:** карточка ухода вместе с TTN тоже является outgoing send.
  Она требует eligibility/opt-in по доказанному Meta contract; «полезная тема»
  не даёт обход окна. Локализованные инструкции должны быть versioned facts,
  а не только текстом на баннере.

#### Э1.8 - Follow-gate

- **Нравится:** явный customer action экономит фоновые Graph calls и корректно
  разделяет confirmed/not confirmed/unknown.
- **Нюанс:** quick reply/postback должен быть связан с конкретной card revision;
  `refresh_follow_state_if_due()` может вернуть cached stale/unknown, а
  «одна проверка» не должна запрещать bounded retry после transient API error.
- **Нюанс:** follow status не доказывает identity другого аккаунта клиента,
  loyalty или purchase intent. Не использовать его для коммерческой истины.
- **Acceptance:** API failure/circuit open не сообщается как «не подписался»;
  state change и card response идемпотентны; Graph request count измеряется с
  denominator и cache age.

#### Э1.9 - Service/custom cards

- **Нравится:** кастом ведёт в текстовый brief, обмен начинается с эмпатии,
  а не с формы.
- **Проблема:** proactive care card снова зависит от Meta policy; если
  post-window channel недоступен, её нужно показывать только в допустимом
  окне или по следующему inbound.
- **Custom:** пример работ должен быть allowlisted first-party URL; вложения
  brief должны проходить attachment ownership/retention/SSRF policy. Card
  `has_artwork/describe` - только начало, не заменяет typed brief.
- **Exchange/return:** кнопки должны создавать/reuse один `IgPostSaleCase`,
  не новый order; stale card не должна открыть уже закрытый case.
- **UGC:** не выдавать discount автоматически за положительный отзыв или
  публикацию. Оставить manager review/legal gate из `NEW-UGC-001`.

#### Э1.10 - Cards are not model-generated

- **Нравится:** это правильное сквозное ограничение.
- **Доработка:** typed model output всё равно является untrusted proposal:
  schema validation, enum allowlist, maximum lengths, current state lookup,
  authoritative reconstruction и forbidden-action test обязательны.
- **Совместимость:** новая card decision должна сосуществовать с текущими
  control tags `[PAYLINK]`, `[PRODUCT]`, `[ITEM]`, `[FIT]`, `[PRICE]`;
  free-text tag не должен стать authoritative только потому, что рядом есть
  typed JSON.
- **Acceptance:** adversarial output с чужим URL, суммой, payload/domain,
  превышенным limit и несуществующим variant блокируется до provider I/O.

#### Э1.11 - Card rhythm

- **Нравится:** один card per logical turn, greeting/emotion guard и обязательный
  сопроводительный текст защищают разговор от «каталога».
- **Проблема:** порог «выше примерно 50%» не является универсальным KPI. В
  `browse` и `size-choice` высокий card rate нормален, в `service` - нет. Метрику
  считать per intent/cohort, а не одним глобальным числом.
- **Доработка:** явно определить card chain state, что происходит при
  repeated click, abandoned card, stale card и customer text after card.
  `one card per turn` должен считать carousel одним logical delivery, а не
  несколько physical media rows.
- **Acceptance:** greeting/complaint first response stays text; card after
  click may follow; no automatic card cascade when customer did not interact.

#### Э1.12 - Assets

- **Нравится:** HTTPS, ratio, size, minimal text, versioning и visual QA.
- **Недоработка:** «семь типов» не определяет locale, alt, ownership, cache
  invalidation, expiry и fallback. Нужен asset manifest с `asset_key`, locale,
  revision, MIME, dimensions, max bytes, public URL and replacement policy.
- **Доработка:** product exact media не дублировать статическим баннером;
  asset replacement не должен менять уже отправленный immutable payload.
  Проверка в реальном Instagram client полезна, но до неё обязательны
  serialization/API contract tests и approved test account.

### 4.3 Э2 - Критические поломки доставки

**Общая оценка:** это самый недооценённый порядок в исходном плане. Э2
исправляет случаи, когда правильное решение не доходит, доходит частично,
дублируется или создаёт неизвестный provider outcome. Большинство этих пунктов
должно быть до широкого customer-visible rollout Э1, даже если владелец хочет
карточки первыми. Карточка не заменяет durable delivery.

#### Э2.1 - Потеря хвоста ответа

- **Нравится:** точный RED sentinel, byte accounting, запрет silent `sent`,
  защита URL и deterministic compression.
- **Проблема:** `04:1007-1015` правильно описывает `_split_for_send()`, но
  арифметику «4 x 950 байт примерно 1900 кириллических символов» нельзя
  использовать как универсальный limit: emoji, combining marks, ASCII URL и
  JSON overhead дают другой результат.
- **Доработка:** `delivery_plan` должен хранить исходный logical text,
  planned physical parts, exact encoded size, semantic retention and outcome.
  `intentionally_summarized` допустим только при сохранении фактов/ссылок и
  явном audit reason. Если ссылка длиннее одного chunk, не разрывать её и не
  скрывать потерю.
- **Acceptance:** suffix sentinel/CTA/URL либо доставлен, либо клиент получает
  короткую грамматичную deterministic форму; `SENT` без полного или явно
  summarized outcome невозможен; partial send становится reconciliation case.

#### Э2.2 - Burst клиента

- **Нравится:** связывание с `CustomerTurn`, bypass для opt-out/takeover/postback,
  верхняя граница окна и сохранение raw evidence.
- **Проблема:** план считает, что три быстрых сообщения всегда должны давать
  один ответ. Это не всегда верно: «стоп» или исправление после первой фразы
  может быть отдельным turn. Нужны правила смысловой границы, а не только
  elapsed seconds.
- **Доработка:** turn reducer должен принимать source IDs, provider time,
  episode/revision, postback/quick reply type и cancellation markers. Debounce
  должен иметь max wait, per-client single-flight и explicit flush on high-risk
  message. Не брать размер окна только из observed `messages-per-turn`.
- **Acceptance:** duplicate delivery одного event не создаёт второй row;
  burst с совместимой темой даёт один execution; correction/opt-out/manager
  request немедленно прерывает batch; сообщение после deadline создаёт новый
  turn.

#### Э2.3 - Cache failure -> quota -> silent inbox

- **Нравится:** правильно разделены «не наказывать клиента за cache outage» и
  «не разрешать бесконечный расход», а no-AI lane поставлена раньше полного
  cooldown recovery.
- **Критическая поправка:** in-process counter из `04:1127-1163` не защищает
  несколько Passenger/web/daemon процессов и после restart обнуляется. Он может
  быть дополнительным аварийным ограничителем, но основной budget должен быть
  shared/durable и иметь fail-closed semantics.
- **Доработка:** определить, что происходит, если shared cache недоступен:
  bounded DB/admission fallback, статический per-process cap или безопасный
  no-AI acknowledgement. Не использовать тот же cache для admission и для
  единственной durable truth. Любой no-AI ответ всё равно должен пройти
  permission/policy и receipt boundary.
- **Acceptance:** cache outage не превращает guard в unlimited; full Gemini
  cooldown выдаёт ровно один typed terminal outcome на inbound; no-AI path не
  создаёт retry storm и не обещает человека без durable case.

#### Э2.4 - Manager text as model speech

- **Нравится:** структурная роль `not_customer_fact/not_bot_commitment` и
  отделение approved proposal от обычной заметки.
- **Проблема:** тест «дай 30% -> бот предлагает 30%» должен доказывать не
  только prompt wording, но и отсутствие `send`, proposal mutation или
  approval bypass. Иначе можно пройти текстовый тест и всё ещё испортить цену.
- **Доработка:** хранить manager note с author/time/episode and evidence; из
  `0169` брать только свежий authenticated approved offer с expiry/revision.
  Auto-release takeover не должен автоматически активировать незакрытое
  обещание.
- **Acceptance:** обычная manager note видна оператору, но не меняет customer
  facts/discount; approved offer может быть процитирован только в пределах
  своего proposal/policy window; forbidden action corpus зелёный.

#### Э2.5 - Manager ownership protocol

- **Нравится:** явная state machine вместо простого 12-hour timer.
- **Недоработка:** не определены owner identity, lease expiry, acknowledgement
  semantics, SLA breach и поведение при owner unavailable. `claimed` без
  durable owner не доказывает, что человек действительно увидел кейс.
- **Доработка:** добавить unique active case per client/episode, explicit
  `claimed_by`, `acknowledged_at`, `released_at`, escalation on SLA breach и
  idempotent owner actions. Return to bot должен проверять active commitments,
  not only customer re-entry.
- **Acceptance:** бот не обещает «менеджер ответит» без assigned/acknowledged
  case; stale owner не теряет case; resume проходит role/provenance checks.

#### Э2.6 - Meta window from wrong field

- **Нравится:** отдельное `last_user_message_at`, сохранение `last_message_at`
  для UI sorting и backfill.
- **Проблема:** простого фильтра `role=USER` мало. Для Meta window важен
  provider-created timestamp, а polling/backfill/late webhook может иметь
  старое время и новый local insert ID. Нужна clock-skew политика.
- **Доработка:** хранить `last_user_provider_message_at` и, при необходимости,
  source/provider owner; обновлять монотонно по provider timestamp только для
  валидного live inbound. Отдельно документировать, учитываются ли quick
  replies, postbacks, comments и private replies как открывающие окно.
- **Acceptance:** bot echo/manager/backfill не продлевает окно; старый
  backfill не откатывает новый timestamp; сортировка списка не меняется;
  boundary uses current provider contract.

#### Э2.7 - HTTP inside transaction

- **Нравится:** запрет HTTP под DB lock и желание проверить все call sites.
- **Критическая ошибка плана:** пункт `04:1306-1310` предлагает «ensure
  lifecycle только через on_commit или вне транзакции». Это ломает атомарность
  бизнес-изменения и durable event. Если процесс упадёт после commit до
  callback, event будет потерян.
- **Правильная схема:** `ensure_lifecycle_event()`/outbox row создаётся или
  обновляется внутри той же транзакции, что order/payment/assignment state;
  `transaction.on_commit()` только будит dispatcher. `dispatch_lifecycle_event`
  с Meta HTTP запускается после commit, вне DB transaction. Проверка
  `in_atomic_block` должна стоять в dispatcher/send boundary, а не запрещать
  создание row.
- **Acceptance:** rollback бизнес-изменения откатывает его event; commit
  оставляет durable pending row даже если worker умер; provider HTTP не
  выполняется под открытой transaction; lifecycle row не создаётся дважды.

#### Э2.8 - Fresh-first starvation

- **Нравится:** age ceiling, single-flight и измерение p95/p99 до изменения.
- **Проблема:** добавление приоритета по стадии при равном возрасте может
  систематически голодать service/urgent cases или дать новый скрытый score
  без объяснения.
- **Доработка:** объявить lexicographic policy: safety/opt-out/takeover,
  maximum age, urgency, then freshness/stage. Доказать, что per-client lease
  не допускает два ответа. Не связывать «продвинутую стадию» с revenue/value
  без policy approval.
- **Acceptance:** synthetic continuous fresh stream не превышает age ceiling;
  support case не теряет приоритет; одна client active send максимум.

#### Э2.9 - Global send lock

- **Нравится:** план не предлагает просто убрать lock и признаёт, что он
  защищает permission epoch.
- **Недоработка:** «короткий global capture + per-client fenced lease» требует
  формальной state machine. Epoch change после marker creation означает
  ambiguous send, а не гарантированную отмену.
- **Доработка:** переиспользовать `IgCommerceTurnDecision` delivery state,
  добавить logical delivery ID and provider request boundary. Global lock
  удерживать только для короткого CAS; provider call - per-client lease.
  Reconciliation должен быть явным для crash/timeout после request start.
- **Acceptance:** A slow send не блокирует B; takeover до marker blocks A;
  takeover после marker создаёт `UNKNOWN`/audit, но не blind resend; receipt
  IDs не смешиваются между клиентами.

#### Э2.10 - Watchdog and long turn budget

- **Нравится:** separate process liveness and active work lease, declared
  deadline and consistency test.
- **Нюанс:** арифметику `45 + 3 + 4*12 = 96` из `04:1433-1437` нужно
  перепроверить на реальном path: number of HTTP calls, typing behavior,
  fallback/retry and lock wait may differ. Heartbeat derived from budget should
  include cleanup/reconciliation slack, not only nominal phases.
- **Доработка:** worker heartbeat timer must be safe on process shutdown and
  never renew a dead/stalled lease indefinitely. Watchdog needs generation,
  PID, work lease, deadline, last progress and restart reason.
- **Acceptance:** work inside declared deadline does not restart; work beyond
  deadline is marked stale exactly once; restart during provider ambiguity leaves
  `UNKNOWN`, not automatic duplicate send.

#### Э2.11 - Mid-less webhook dedupe

- **Нравится:** preference for provider object ID, rejection of blind query
  stripping and observation-only fallback.
- **Проблема:** URL signature normalization needs a provider contract. A URL
  digest alone can merge distinct media or fail to merge the same media. Event
  identity should be separated from downloaded asset identity.
- **Доработка:** store `provider_media_object_id` when available, URL digest
  only as secondary evidence, event timestamp/text/attachment ordinal as
  bounded composite, and confidence. Different attachments must remain
  distinct even if URLs share path.
- **Acceptance:** same media object with two signatures -> one observed inbound/
  turn; different object -> two; no arbitrary URL query removal; no duplicate
  provider AI/media call.

### 4.4 Э3 - Истина данных и контекста

#### Э3.1 - Untrusted memory in `system_instruction`

- **Нравится:** immediate low-cost containment before typed envelope and removal
  of phone/branch from free summary.
- **Проблема:** merely prefixing a free-text summary with «not instructions» is
  not a complete injection boundary: models can still follow imperative text
  inside quoted data. Temporary exclusion is safer until typed projection.
- **Доработка:** split deterministic facts from narrative, taint narrative,
  enforce allowlisted render fields and never use summary as policy/evidence.
  Keep PII out of generic summary; explicit PII policy may use references, not
  raw phone/address in every prompt.
- **Acceptance:** adversarial summary cannot alter role, price, stock, manager
  approval or tool action; no PII field is requested by `SUMMARY_INSTRUCTION`;
  next reply has safe behavior.

#### Э3.2 - Stage and audit event atomicity

- **Нравится:** RED injected failure, direct-writer inventory and preservation
  of `MODEL_HARD_STAGES`/`FACT_ONLY_STAGES`.
- **Нюанс:** atomicity requires both involved tables transactional. After fixing
  engine, do not wrap unrelated provider calls or swallow event failures.
- **Доработка:** one transaction for stage plus append-only event; failed event
  rolls back stage or writes explicit durable failed transition. Static ban on
  direct writers only after setup/migration/test writers are enumerated.
- **Acceptance:** no stage without exactly one evidence event; payment/
  fulfillment stages still require verified facts; direct bypass detected by
  structural test without blocking legitimate fixtures.

#### Э3.3 - Language and reset floor

- **Нравится:** one current-episode queryset for history/language/style/memory.
- **Проблема:** reset floor by message ID can interact with late provider
  messages and polling backfill; a new message with older provider time may be
  valid evidence but should not revive old language. Explicit language request
  has different scope from detected language.
- **Доработка:** define floor by episode/revision plus provider-time policy;
  distinguish `explicit_language_request` and `detected_language`; include
  media-only/empty text behavior.
- **Acceptance:** old RU/EN below reset cannot steer new neutral turn; explicit
  UK/EN request in current episode wins; backfill does not silently change live
  language.

#### Э3.4 - Stale analysis snapshot

- **Нравится:** one freshness selector for card/list/count/filter and historical
  timeline retention.
- **Доработка:** compare snapshot watermark to latest relevant user turn, current
  episode and state fingerprint. `stale` and `unknown` must be typed states,
  not blank values that accidentally pass filters.
- **Нюанс:** manager messages may legitimately trigger internal analysis but
  cannot advance customer-facing freshness; selector needs role coverage.
- **Acceptance:** card/list/count/follow-up all agree on current/stale; stale
  payment/intent labels cannot route customer action; historical snapshot remains
  inspectable with date and scope.

#### Э3.5 - Manager-only evidence

- **Нравится:** source-role coverage and forced `MANAGER_OBSERVATION`.
- **Доработка:** snapshot claims need per-claim user message IDs, not only a
  transcript-level `source_role`. Mixed transcript must split claims; a manager
  quote about a customer does not become customer intent without corroborating
  user evidence.
- **Acceptance:** manager-only note cannot create product interest/payment
  pending/collaboration customer state; CRM may show observation separately;
  follow-up ignores manager-only customer claims.

#### Э3.6 - Reply provenance

- **Нравится:** redacted envelope with prompt hash, revision IDs, deploy SHA,
  catalog revision and request correlation.
- **Недоработка:** hashing a canonical prompt «without client text» is useful for
  instructions, but not enough to reproduce context selection. Store separate
  hashes/IDs for policy, catalog, current state, selected evidence and prompt
  template; never store raw provider body/keys/PII.
- **Доработка:** generate request ID before first candidate, propagate through
  all attempts, record skipped/not-attempted candidates and link reply/outbox
  once. Do not use a mutable global last-model field as reply truth.
- **Acceptance:** one reply opens a stable redacted chain; retry/review is
  read-only; selected model/key alias and attempt graph match the actual
  request, including CustomerTurn with multiple source IDs.

#### Э3.7 - Variant/availability/media resolver

- **Нравится:** one authoritative resolver, `unknown` fail-closed, model never
  declares stock, and exact media dependency for cards.
- **Критическая поправка:** resolver must reuse checkout's effective pricing/
  availability semantics, not invent a parallel `in_stock/made_to_order` rule.
  `ProductColorVariant.stock` is not enough in this project; generic options,
  fit, size, quantity and variant rules all matter.
- **Доработка:** return immutable `selection_revision`, exact variant/fit/size/
  options, availability state, price source, media evidence and fallback reason.
  Media selection must accept this resolved selection; generic media only with
  explicit reason.
- **Acceptance:** prompt/catalog/checkout agree on same fixture; stale revision
  cannot send media/card; exact variant photo and price correspond to current
  line; unknown blocks checkout claim.

#### Э3.8 - Catalog cache error vs empty result

- **Нравится:** distinguish empty catalog from provider/cache failure and use
  revision invalidation with emergency TTL.
- **Нюанс:** cross-process invalidation needs durable monotonic revision and
  reconciliation; a cache hit from an older revision must be labeled stale, not
  silently treated as empty.
- **Acceptance:** error is never cached as valid empty prompt block; invalidation
  failure produces bounded alert; catalog answer degrades to truthful unknown.

#### Э3.9 - Follow-up cancellation and episode

- **Нравится:** second check immediately before provider I/O, watermark and
  episode/revision binding.
- **Проблема:** after provider request starts, new inbound cannot guarantee
  cancellation. It must become `sent/unknown` with a reason, not be described as
  cancelled after the fact.
- **Доработка:** store claim watermark, episode, line/deal revision and
  cancellation checkpoint. Repeat/reset should supersede old tasks with an
  append-only reason. Current deal must be selected from active episode, not
  latest global non-cancelled deal.
- **Acceptance:** inbound after claim but before I/O prevents call; inbound
  after I/O records ambiguous/sent outcome; old episode task never sends in new
  episode; replay is idempotent.

#### Э3.10 - Commerce line/episode/repeat

- **Нравится:** line/recipient binding, synchronous repeat detection and no
  transfer of verified payment.
- **Критическая недоработка:** existing `IgCommerceSelectionTransition` and
  `IgCommerceTurnDecision` use `OneToOne(source_message)`. A multi-message
  CustomerTurn needs primary source + through relation, otherwise provenance
  cannot represent one turn correctly.
- **Доработка:** line revision must cover product, variant, fit, size, options,
  recipient, candidate digest and proposal allocation. `_has_explicit_repeat_evidence()`
  should be called before Gemini only after deterministic current episode/line
  checks, not on a single ambiguous phrase.
- **Acceptance:** two recipients remain isolated; old stock gap is not in new
  episode; «ще одну» creates new revision before model/send; old payment never
  migrates.

#### Э3.11 - Atomic `sales_context`

- **Нравится:** immediate small fix followed by append-only decomposition.
- **Проблема:** `JSON_SET` expressions differ between MariaDB and SQLite and
  nested missing paths have edge cases. A generic «Django 6.1 can express it» is
  not sufficient without backend contract tests.
- **Доработка:** define per-key ownership, JSON schema/version, merge semantics,
  conflict policy and max size. On MariaDB use row lock/JSON_SET as appropriate;
  on SQLite test the chosen compatibility path. Do not claim p95 prompt latency
  independence until long-client fixtures exist.
- **Acceptance:** two concurrent writes preserve both keys on disposable
  MariaDB; SQLite test layer has equivalent semantic result; append-only fields
  have owner/episode indexes and bounded projection.

#### Э3.12 - Memory by watermark

- **Нравится:** content-triggered typed projection, retry/outbox and non-blocking
  live reply.
- **Нюанс:** «inbound without reply gets memory job» can create unbounded jobs
  during webhook burst. Coalesce by client/episode/watermark and preserve latest
  durable watermark.
- **Acceptance:** meaningful size/address/objection change schedules one job;
  failure retries with visible telemetry; reset does not create an eight-message
  blind window; routine «ок» does not invoke expensive summarizer.

#### Э3.13 - Content boundary

- **Нравится:** output gate, fail-closed high-risk behavior and false-positive
  tests.
- **Проблема:** a deterministic classifier cannot reliably infer all off-topic
  language; it must not become a second opaque LLM truth engine. Safe handoff
  itself needs a delivery/policy contract.
- **Доработка:** keep scope classification bounded and reason-coded; allow
  ordinary product/size/support questions; rate-limit repeated technical-secret
  requests without banning customer. Store decision metadata, not raw text.
- **Acceptance:** prompt/key/DB-secret requests never disclose; normal multilingual
  sales/support passes; repeated off-topic reaches bounded terminal handling.

#### Э3.14 - Injection risk signal

- **Нравится:** signal + safe response + human review instead of auto-ban.
- **Нюанс:** pattern detector is a signal, not a security boundary; adversarial
  text can avoid patterns, and harmless quotation can match them. `low/medium/
  high` needs calibrated examples and review feedback.
- **Доработка:** keep injection strikes separate, add episode/time decay and
  redacted pattern codes; rate budget must not starve a real buyer. Manager
  notification must be deduplicated and itself not expose attack text.
- **Acceptance:** explicit attack gets safe bounded reply and alert; quoted
  harmless example has no customer consequence; no auto spam/ban transition.

#### Э3.15 - Gemini ledger and downgrade

- **Нравится:** ledger before planner, request-level correlation and explicit
  `not_attempted_reason`.
- **Критическая tension:** «try every distinct 3.7 candidate» conflicts with
  the 35/45-second live SLA if calls are sequential. The plan correctly says not
  to raise sequential limit to six, but must define staged/hedged budget rather
  than leaving it implicit.
- **Доработка:** ledger states `planned/lease_busy/skipped/attempted/unknown/
  cancelled/succeeded`, project identity confidence and policy version. 403
  excludes only proven credential/project; 404 circuit needs independent
  evidence. Cancelled late calls are observable, and no second reply is allowed.
- **Acceptance:** API1/2 timeout + healthy distinct API3 yields 3.7 when budget
  allows; candidates not attempted have explicit reason; all attempts join one
  request; full trace fits deadline or ends in truthful fallback.

#### Э3.16 - SSRF/media URL policy

- **Нравится:** honest status as policy candidate, mock-only tests and no live
  exploit probing.
- **Нюанс:** current `_trusted_media_item()` first-party host/suffix/mime/size
  check is for outgoing catalog assets; it does not prove inbound downloader
  safety. DNS rebinding and redirect behavior must be enforced by the actual
  fetcher/proxy, not only URL parser.
- **Acceptance:** unit mocks cover localhost/loopback/RFC1918/link-local,
  rebinding and redirect; provider object ID preferred; no production SSRF test.

#### Э3.17 - Raw webhook batch erasure

- **Нравится:** recognizing legal/privacy severity and rejecting substring JSON
  surgery.
- **Critical detail:** `record_raw_event()` stores up to 20,000 characters of
  the whole payload and indexes the first sender (`instagram_bot.py:11632-11679`).
  Adding more sender IDs to the same row is still insufficient for selective
  erasure if the JSON is truncated or contains shared participants.
- **Доработка:** parse event-per-participant before raw persistence, or retain a
  bounded full batch with complete participant index and a transactionally
  verified redaction/deletion process. Explicit opt-out/erasure must suppress
  future persistence according to policy; retention purge cannot be the only
  mechanism.
- **Acceptance:** deleting A removes A's raw evidence while retaining B's
  unrelated row; deleting B also works; no malformed truncated JSON is silently
  treated as erased.

#### Э3.18 - Hidden client and `hidden_at`

- **Нравится:** policy gate before changing established test contract and clear
  separation of observation from automation.
- **Нюанс:** `hidden_at` may mean UI hidden, automation paused, or erasure. The
  plan correctly asks for production calibration, but «dedupe/lock/persistence
  before hidden check» is valid only for non-erasure meanings.
- **Доработка:** introduce explicit states (`ui_hidden`, `automation_suppressed`,
  `erasure_pending/completed`) instead of overloading one timestamp. Persist
  non-erasure inbound as observation-only; never create new raw/message data
  after an authoritative erasure boundary.
- **Acceptance:** non-erasure hidden inbound is visible in CRM and no automation
  runs; opt-out/erasure suppresses storage according to policy; hide race yields
  one idempotent outcome with reason and no permission epoch mutation.

### 4.5 Э4 - Реестр узлов воронки и UI

**Общая оценка:** идея сначала перенести существующий `checkout_readiness`, а
потом добавлять новые узлы - одна из самых здоровых частей плана. Нельзя
одновременно создавать новый registry, менять обязательность, fast-track и
визуальный граф: иначе будет невозможно понять, что именно изменило
конверсию. Также важно не смешать definition registry и персональное state.

#### Э4.1 - Каноническое определение node

- **Нравится:** отказ от двух расходящихся физических registry, явные policy
  fields, graph validation и сохранение `checkout_readiness` как payment
  authority.
- **Нюанс:** «одно каноническое определение» не означает одну таблицу для
  definition и всех client states. Definition (versioned catalog of node
  semantics) и state/projection (episode/line-specific evidence) должны быть
  разделены, иначе обновление политики изменит прошлую историю.
- **Доработка:** `applicable_when`, dependencies и `blocking_for` нельзя
  полностью выразить четырьмя типами рёбер. Сложная availability/quantity/
  option logic остаётся в authoritative resolver; graph описывает порядок и
  invalidation, но не заменяет domain code.
- **Acceptance:** первоначально mapped только product/fit/size/color/options/
  quantity/city/branch/phone/recipient/pay type/paylink; старое поведение
  совпадает; definition version immutable; state scoped by episode/line.

#### Э4.2 - `invalidated`/`superseded`

- **Нравится:** требование причины и различение «передумал», «стало
  недопустимо» и «устарело».
- **Проблема:** план одновременно предлагает `closed_superseded` и
  `superseded`; не следует без необходимости раздувать enum. Нужен единый
  status плюс typed reason/previous value/causing node.
- **Доработка:** invalidation event append-only, previous value immutable,
  current projection rebuilt. `customer changed value` не должен порождать
  лишний вопрос; `availability invalidated` обязан объяснить причину и задать
  только необходимый вопрос.
- **Acceptance:** change color -> unavailable size gives reason and one
  re-question; changed preference does not re-ask already explicit value;
  history remains visible to operator.

#### Э4.3 - API projection

- **Нравится:** API/read model до frontend и отделение aggregate cohort from
  per-client card.
- **Недоработка:** API status `required` alongside `complete/partial/...` is
  ambiguous: required is applicability/policy, not a lifecycle state. Лучше
  separate `applicable`, `blocking`, `status`, `reason`, `freshness`.
- **Доработка:** projection must be rebuildable from event/evidence, versioned,
  bounded and scoped by client/episode/line. UI cannot infer current state from
  raw JSON or ordering.
- **Acceptance:** evidence IDs, confidence, generated_at and schema version are
  present; reset/repeat creates new branch; aggregate endpoint cannot be used as
  current customer state.

#### Э4.4 - Purchase occasion typed fact

- **Нравится:** recipient/occasion/deadline as typed evidence and separation of
  recipient size from buyer `current_size`.
- **Проблема:** `readiness += 10` is a scoring heuristic, not proof of purchase
  intent. It may remain for compatibility but cannot authorize paylink or
  priority by itself until calibrated.
- **Доработка:** store source message IDs, scope, confidence and validity. Regex
  `подар` must distinguish «подарочная упаковка» from gift recipient. Date
  extraction must not invent a deadline from «на день рождения».
- **Acceptance:** reset preserves client-level occasion only when policy says so;
  line recipient facts stay line-scoped; evidence non-empty; low-confidence
  occasion does not force urgency.

#### Э4.5 - Next-best-action and decision mode

- **Нравится:** orthogonal mode (`browse/compare/decide/reassure/service`)
  versus node skip; no second FSM; grouped semantic questions and explicit
  price acknowledgement.
- **Проблема:** «high share of HARD nodes -> skip SOFT» is unsafe without
  objective evidence and current proposal. A hot lead can still be uncertain,
  and skipping a QUALITY node may raise returns.
- **Доработка:** mode is a typed, explainable classification with fallback;
  skip reason and policy version are recorded; `price_acknowledged` must be
  tied to the current offer/revision, not merely a word in chat.
- **Acceptance:** fully configured customer reaches link with at most one
  evidence question; greeting/price question does not enter fast-track; mode
  can move backwards after correction or doubt.

#### Э4.6 - Follow-up reads open node

- **Нравится:** one parameterized policy and one highest-value question instead
  of a policy per missing field.
- **Нюанс:** follow-up needs current proposal/episode and outbound policy; an
  open node alone cannot authorize a post-window send. `PAYLINK_VIEWED` must
  distinguish rendered/clicked/checkout-page-viewed as discussed above.
- **Доработка:** closing a node invalidates queued tasks with a durable reason;
  multiple missing nodes use priority and evidence, not arbitrary list order.
- **Acceptance:** one message asks one actionable missing fact; no reminder
  survives explicit customer closure; eligibility is rechecked at claim and
  immediately before provider I/O.

#### Э4.7 - Expandable UI/journal

- **Нравится:** compact first layer, evidence on demand, `not_applicable` vs
  `unknown`, accessible list before graph, and static history.
- **Проблема:** «восемь стадий» and «three layers» can become a new rigid UI
  contract even when current funnel definitions change. The UI should consume
  versioned API labels, not hardcode count.
- **Доработка:** never expose customer PII, raw prompts, tokens or unredacted
  manager notes in the operator list. Show `hard blocker`, current line,
  service case and freshness with stable severity.
- **Acceptance:** operator can identify blocker without click; evidence/transition
  history is scoped and paginated; aggregate metrics cannot overwrite per-client
  card; keyboard/screen-reader path remains usable.

#### Э4.8 - Closure method/provenance

- **Нравится:** closure method, confidence, evidence IDs and confirmation of
  history-derived values before irreversible action.
- **Проблема:** `answered` and `volunteered` are not automatically trustworthy:
  «maybe L» or a quoted size can be ambiguous. `inferred` should never close a
  blocking node without explicit confirmation.
- **Доработка:** map closure method to evidence quality; postback is strong only
  after current card/session validation. Confirmation summary must list the
  exact product/variant/fit/size/payment terms and allow correction.
- **Acceptance:** history/inference cannot create paylink/TTN without current
  confirmation; explicit customer value is preserved; closure source visible in
  UI and audit.

#### Э4.9 - Carry size when product changes

- **Нравится:** preserve human context as a suggestion while resetting price,
  payment and variant-specific data; keep price-leak regression green.
- **Critical nuance:** size and fit are not purely person-level. A person may
  wear oversize L but classic L is not necessarily equivalent. `line_id` is
  also the identity of a product line; keeping it across a new product can
  corrupt history and recipient binding.
- **Доработка:** carry only as `suggested_from_line_id`, validate new product/
  fit/variant compatibility, ask confirmation, and create a new line identity
  or explicit lineage. Never reuse price/proposal/allocation. Recipient can be
  preserved only when the customer explicitly keeps the same recipient.
- **Acceptance:** compatible size is offered once for confirmation; incompatible
  fit reopens node; old price/payment/proposal never carries; UI shows lineage.

### 4.6 Э5 - Память, адресность и profile projection

#### Э5.1 - Typed memory envelope

- **Нравится:** typed facts with scope, source, TTL, sensitivity, supersession
  and prohibition on duplicating payment/stock/order truth.
- **Доработка:** add encryption/access policy for PII, retention owner and
  deletion propagation. `subject_scope=client` is not sufficient for a phone or
  address that can change by order/recipient.
- **Acceptance:** prompt renderer allowlists fields; narrative remains tainted
  quoted data; reset supersedes episode facts without deleting evidence; erasure
  removes or redacts all permitted projections.

#### Э5.2 - Memory index and addressable loading

- **Нравится:** compact index plus deterministic L0-L3 loading, no second tool
  call by default, and authority blocks never discarded.
- **Проблема:** L0 currently includes potentially sensitive «number of
  purchases/current money truth». The model may not need raw values to know that
  a reference exists. Index content should be minimal and purpose-limited.
- **Доработка:** each block needs authority/freshness/token cost and scope;
  fallback must not claim absence when index says data exists. Tool-call loading
  is a later optimization, not a prerequisite for correctness.
- **Acceptance:** greeting does not load friction/history; gift/return/size
  intents load only relevant typed facts; no block omission causes false
  denial of known authoritative data.

#### Э5.3 - Memory as analysis projection

- **Нравится:** removes duplicate Gemini summarizer and preserves a cheap
  synchronous projection while analysis is asynchronous.
- **Критическая граница:** analysis output is still model-generated and needs
  validation, role/evidence/watermark checks before entering memory. «Analysis is
  single producer» must not make its free JSON authoritative.
- **Доработка:** deterministic columns (language, size, stage, authoritative
  totals) update synchronously; interpretive facts update only from reviewed
  typed analysis; stale analysis never overwrites a newer projection.
- **Acceptance:** one model call for shared analysis; memory/CRM agree or mark
  stale; analysis outage leaves deterministic context available.

#### Э5.4 - Intent-aware prompt sections

- **Нравится:** deterministic planner, authority precedence and golden matrix.
- **Нюанс:** intent itself may be uncertain or multi-intent. Planner must support
  a bounded set and a safe union/fallback, not force one mode from one keyword.
- **Доработка:** payment/order/policy blocks stay mandatory for relevant open
  state; catalog subset must retain safe lookup; prompt hash/provenance records
  exactly what was included and omitted.
- **Acceptance:** greeting, size, delivery, support, collaboration and payment
  have explicit required/forbidden sections; p95 token/latency measured per
  cohort; no model-generated retrieval query becomes truth.

#### Э5.5 - Profile and catalog facts

- **Нравится:** one revisioned profile projection and structured catalog facts,
  not a JSON writer in every path.
- **Проблема:** keeping «aggregate such as purchases, size» after raw retention
  purge can still be personal data. Legal retention classification must precede
  archive design.
- **Доработка:** use one owner job, source IDs, episode/revision/freshness and
  conflict policy. For `NEW-CAT-004`, facts like fleece/composition must be
  catalog-authored and versioned; `planned` must never imply ETA.
- **Acceptance:** inbound without reply still projects after durable analysis;
  one-fit product does not cause a question; hoodie/zip/thermo properties come
  from product facts; stale catalog is labeled.

#### Э5.6 - Custom-print brief

- **Нравится:** collect rather than confirm, explicit missing fields, structured
  manager handoff and no-price/no-deadline promise.
- **Недоработка:** `contact_preference`, `deadline_date`, attached files and
  reference URLs have privacy/retention/SSRF implications. A Telegram card is
  another outbound delivery and must use durable/idempotent notification, not a
  direct side effect.
- **Доработка:** define field sensitivity and evidence source, validate file
  ownership/content type, dedupe by client/episode/brief revision, and record
  manager acknowledgement/SLA without promising it to the customer.
- **Acceptance:** repeat request updates/reuses one brief; unknown fields are
  explicit; no price/color/deadline claim is sent; manager receives exactly one
  durable structured case.

### 4.7 Э6 - Post-purchase, delivery and LTV

**Общая оценка:** Э6 правильно запрещает строить LTV на неподтверждённой
доставке и отделяет post-sale projection от `IgClient.stage`. Но его вступление
(`04:3139-3147`) всё ещё считает opt-in достаточным для post-window delivery;
после Meta verification result это нужно переписать как «только после доказанного
channel policy, либо next-contact/on-window mode».

#### Э6.1 - Post-delivery context/payment guards

- **Нравится:** разделение payment truth и delivery fact, COD calibration,
  строгость денежных событий и TTL для late binding.
- **Критическая проблема:** текущий `IgLifecycleEvent.clean()` требует
  proposal с payment attempt и exact attribution. Нельзя просто «ослабить
  `_context_for_order`» и оставить ту же модель: `IgOrderAssignment` alone не
  удовлетворит обязательные FK/clean invariants.
- **Доработка:** выбрать один безопасный вариант: отдельный delivery/post-sale
  event model с nullable payment context; расширить существующую модель с
  новой проверенной kind-specific schema; либо материализовать только
  assignment-scoped projection, не называя её `IgLifecycleEvent`. Не
  подделывать proposal/payment attribution для COD/manual order.
- **Acceptance:** delivered COD с валидным IG assignment получает отдельный
  post-sale fact/event; `PAYMENT_VERIFIED` остаётся payment-gated; order без
  trustworthy client binding не отправляет ничего; late assignment догоняется
  только в TTL.

#### Э6.2 - Parcel arrived/storage reminder

- **Нравится:** три gate, event code 7, no fixed storage date, terminal recheck,
  idempotency and no live test sends.
- **Проблема:** storage policy зависит от shipment type/branch/provider and
  может отличаться для initial/return/replacement. Один `order_id` не является
  достаточным event identity.
- **Доработка:** `PARCEL_ARRIVED`/`STORAGE_EXPIRING` должны ссылаться на
  `IgOrderShipment`, tracking, direction, purpose, arrived_at and policy
  version. Текст без подтверждённого сроку хранит только факт прибытия.
- **Acceptance:** code 7 event durable once per exact shipment; terminal pickup
  before send cancels with no provider call; reminder cadence/frequency/quiet
  hours and Meta eligibility are revalidated; no post-window promise without
  approved channel.

#### Э6.3 - Feedback timing

- **Нравится:** separate delivered fact from feedback request, configurable
  delay, one question, negative response service branch, no silent sentiment.
- **Доработка:** `delivered` event should not be overloaded with customer-facing
  message fields; feedback task needs its own logical event/revision and source
  shipment/order. One per order may be wrong for multi-line orders; decide
  whether one response covers all lines or each line has a bounded survey.
- **Acceptance:** late-evening delivery respects quiet hours; delivery evidence
  persists even if feedback send is blocked; no answer does not create neutral
  score; negative answer suppresses UGC/discount and opens service case.

#### Э6.4 - Satisfaction model

- **Нравится:** user-only evidence, typed aspects, no impact on payment truth and
  no record for silence.
- **Нюанс:** one `order_id + episode_id` row cannot represent repeated corrections,
  multiple items or an updated answer without a revision/append-only response
  model. Sentiment extraction is not automatically deterministic just because
  it is typed.
- **Доработка:** define unique survey/response identity, line/aspect scope,
  correction policy, source message IDs and quote retention. Keep raw customer
  text subject to erasure/retention.
- **Acceptance:** positive/negative/mixed responses have distinct typed records;
  fit/print/delivery aspects aggregate by exact product/variant; manager text
  cannot create satisfaction; silence remains no data.

#### Э6.5 - Post-sale projection

- **Нравится:** separate projection tied to order/episode and no expansion of
  `IgClient.stage`.
- **Проблема:** the proposed node list mixes facts (`parcel_arrived`), actions
  (`storage_reminded`), responses (`feedback_received`) and predictions
  (`repeat_ready`). A single status field will recreate the same ambiguity.
- **Доработка:** model event ledger plus derived per-order engagement state;
  allow independent branches (feedback, follow, UGC, repeat, service), with
  policy/consent metadata and immutable history.
- **Acceptance:** delivered/no-feedback, delivered/negative, verified UGC and
  repeat are distinguishable; exchange does not reset first order history; new
  purchase creates a new commercial episode.

#### Э6.6 - Exchange/return case FSM

- **Нравится:** case beside main line, shipment evidence, verified refund as the
  only legitimate financial regression.
- **Нюанс:** current `IgPostSaleCase.Status` already contains
  `NEEDS_DETAILS/OPEN/APPROVED/IN_TRANSIT/RECEIVED/COMPLETED/REJECTED/CANCELLED`.
  The proposed `requested/accepted/return_in_transit/...` must be mapped to
  existing statuses or justified as a separate event layer, not create a second
  incompatible FSM.
- **Доработка:** add append-only transition audit, idempotent case actions,
  shipment direction/purpose and replacement lineage. One case may have return
  and replacement concurrently; a linear FSM may be insufficient.
- **Acceptance:** API/UI distinguish request vs approved vs inbound received
  vs replacement shipped; closing case does not move main sales stage; refund
  regression requires verified provider evidence.

### 4.8 Э7 - Контракты агента

**Общая оценка:** эти пункты действительно могут повысить качество диалога,
но они не должны опережать durable delivery, source-of-truth и policy gates.
Их acceptance должен проверять действия и запрещённые side effects, а не только
естественность текста.

#### Э7.1 - Commitment ledger

- **Нравится:** явная связь «да/нет» с одним предложением, expiry и запрет
  превращать commitment в цену/stock/payment truth.
- **Доработка:** интегрировать ledger с существующим immutable
  `IgCommerceTurnDecision`, `IgCheckoutProposal` и manager-approval, а не
  создавать независимый mutable JSON. Commitment должен ссылаться на
  proposal/line revision и сохранять source message ID.
- **Нюанс:** «да» после нескольких карточек или в burst может быть
  неоднозначным. При отсутствии единственного active offer нужен clarification,
  а не выбор последнего по времени.
- **Acceptance:** expired commitment не оживает поздним «да»; один explicit
  offer -> один action; duplicate callback idempotent; commitment не разрешает
  необоснованную цену, stock, скидку или отправку.

#### Э7.2 - Customer correction repair plan

- **Нравится:** correction event, invalidation of dependent actions, one next
  repair question and cancellation before provider I/O.
- **Проблема:** correction может приходить после provider send; тогда
  «отменить действие» невозможно, и нужно честно записать sent/unknown plus
  remediation. Нельзя обещать полную отмену уже ушедшего сообщения.
- **Доработка:** typed correction target must include line/recipient/episode,
  confidence and exact invalidated IDs. Updating a field alone is forbidden;
  proposal/payment/TTN changes need their own authorized transition.
- **Acceptance:** correction before send cancels stale follow-up/card; correction
  after send creates visible repair case; uncertain target asks clarification;
  no old action executes after repair.

#### Э7.3 - Resolver for uncertainty

- **Нравится:** every uncertainty has resolver, evidence and terminal state;
  absence of resolver creates visible handoff instead of repeated model loop.
- **Недоработка:** «ожидаемый срок» должен означать SLA/owner deadline, а не
  customer-facing ETA. Не обещать клиенту дату, если resolver only queues
  manager work.
- **Доработка:** registry should define resolver type (`read_only`, `manager`,
  customer_clarification`), evidence schema, due_at, escalation, terminal
  reason and policy version.
- **Acceptance:** unknown stock/price/media never becomes an AI guess; failed
  resolver yields truthful status; stale resolver does not leave a silent
  unowned promise.

#### Э7.4 - Contradiction firewall

- **Нравится:** bounded operational claims, authoritative facts plus active
  commitments, four explicit outcomes and low-confidence clarification.
- **Проблема:** extracting claims with another LLM can create a second
  untrusted decision engine. It must not be allowed to mark a conflict as fact
  or override application evidence.
- **Доработка:** hard conflicts only against typed authoritative values; model
  extraction is advisory and schema-validated. Include current proposal/line,
  shipment and policy revision in comparison. Store redacted conflict code,
  not reasoning/transcript.
- **Acceptance:** stale promise/price/availability conflict is caught; normal
  paraphrase is not blocked; no firewall result sends a message without the
  same permission/receipt boundary.

#### Э7.5 - Shadow/holdout rule

- **Нравится:** treating experimentation as an acceptance rule, not a feature,
  and prohibiting experiments on payment, discount, inventory, eligibility and
  sensitive decisions.
- **Недоработка:** plan does not define how holdout interacts with a small
  Instagram population, consent, repeated customer exposure and emergency
  support. Randomizing customer-facing policy can itself be a product/policy
  decision.
- **Доработка:** deterministic cohort assignment, policy version, exposure
  ledger, sample-size/stop condition, guardrail metrics and kill switch. Shadow
  must never call external send or mutate payment/inventory.
- **Acceptance:** rollout can be disabled without losing existing support;
  critical safety cohort failure blocks rollout; no synthetic Meta/Telegram
  events are generated.

#### Э7.6 - Manager quality reviews

- **Нравится:** trace-linked labels, corrected fact/action, evidence and no
  automatic prompt/model mutation.
- **Нюанс:** review text is itself sensitive and can contain customer PII or
  manager secrets. «Без дополнительных raw PII» needs field-level enforcement,
  not only reviewer instructions.
- **Доработка:** review schema should reference reply/trace, store bounded
  labels and redacted correction, carry retention/deletion linkage and measure
  inter-reviewer agreement before using labels as metrics.
- **Acceptance:** review is immutable/auditable, erasure propagates, it can
  generate a future evaluation case without silently becoming training data.

#### Э7.7 - Context ablation and cohorts

- **Нравится:** token cost, authority/freshness metadata, operational cohorts
  and protection against average-quality blindness.
- **Проблема:** ablation can accidentally remove required policy/payment facts;
  «section does not improve cohort» is not enough to remove a safety block.
- **Доработка:** hard non-ablated set, deterministic replay corpus, model/prompt
  version and confidence intervals. Cohort assignment must use operational
  state only, not inferred sensitive demographics.
- **Acceptance:** per-intent token/latency/factual/action/policy metrics;
  critical cohort regression stops rollout even if global average increases.

#### Э7.8 - Read/decision/write adapters

- **Нравится:** narrow boundary, explicit evidence/idempotency/owner/policy and
  no big-bang rewrite.
- **Недоработка:** adapters introduced before delivery/transaction contracts
  stabilize may just hide the existing ambiguity behind more names. The first
  boundary should be a real risky edge with one owner, not a full architecture
  rewrite.
- **Доработка:** start with `candidate reply -> authorize -> durable outbox ->
  receipt`; preserve old functions behind contract adapters, add forbidden
  action tests and query/latency baseline.
- **Acceptance:** one adapter boundary has explicit read/write effects;
  old behavior is preserved by replay corpus; no hidden ORM write or duplicate
  provider call occurs.

### 4.9 Э8 - Operations, performance and analytics

#### Э8.1 - Connection budget

- **Нравится:** reserved live-response capacity, age-aware background work and
  rejection of Django `ImmediateBackend` as heavy background execution.
- **Проблема:** admission controller cannot infer exact DB connection count from
  thread count alone; `CONN_MAX_AGE=0`, Passenger workers, management command
  processes and provider threads need a measured budget.
- **Доработка:** inventory process/thread counts, DB max_user_connections,
  query duration and provider concurrency. Use shared admission state or a
  bounded queue; no in-process-only guarantee across workers.
- **Acceptance:** background work cannot consume live reserve; deferred work is
  durable; p95/p99 connections remain below documented budget; overload has a
  truthful terminal reason.

#### Э8.2 - Analysis queue telemetry/concurrency

- **Нравится:** measure first, small pool 2-3, different clients only, watermark
  guard and `close_old_connections()`.
- **Нюанс:** per-client lease is not enough; Gemini key/project lease, DB
  connection admission, transaction scope and cancellation semantics also need
  enforcement. Threads that finish after deadline must not commit stale snapshot.
- **Доработка:** separate current inbound from historical backfill, add queue
  age/lease age/attempts, terminal reason and bounded retry. Concurrency only
  after production evidence and disposable MariaDB race test.
- **Acceptance:** same client never has concurrent analysis; two different
  clients can proceed within budgets; failed worker returns one durable job and
  no duplicate current snapshot.

#### Э8.3 - Readable operational alerts

- **Нравится:** business impact, severity, human age formatting, runbook hint,
  dedupe and `unobserved` handling.
- **Проблема:** `unobserved` may mean missing cron configuration, not incident;
  hardcoding critical/warning severity without inspecting current structured
  alert bodies recreates noise. `instruction_code` may already exist upstream.
- **Доработка:** first inspect production/current alert payloads, then add
  localized mapping and severity per task. Alert on one state transition or
  deduped window, not each health poll.
- **Acceptance:** critical alert says what business path is broken and first
  action; diagnostic stale is distinguishable; unconfigured task does not spam.

#### Э8.4 - Daemon generation/uptime

- **Нравится:** PID/start/uptime/restart count/window/last useful work and no
  restart as part of probe.
- **Нюанс:** generation must survive process replacement and distinguish
  intentional maintenance from crash churn. A fresh heartbeat alone remains
  insufficient.
- **Acceptance:** churn and staleness separate; restart reason is durable;
  health endpoint is read-only and cannot trigger a process restart.

#### Э8.5 - One context snapshot

- **Нравится:** production measurement first, prefetch/only/values, preserved
  per-section error isolation and `assertNumQueries`.
- **Critical transaction nuance:** «one transaction» must end before Gemini/HTTP
  call. Holding a DB transaction while assembling or generating a response
  would recreate Э2.7. Snapshot transaction should read consistent data, close,
  then pass immutable values to prompt sections.
- **Доработка:** query budget must be backend-specific; `assertNumQueries` on
  SQLite is not proof of MariaDB latency. Cache brand/playbook separately with
  revision.
- **Acceptance:** measured query count and prompt-build latency improve;
  missing one optional source does not abort other sections; no open DB
  transaction crosses provider I/O.

#### Э8.6 - Out-of-catalog and inquiry categories

- **Нравится:** truthful absence, optional manager signal, aggregated demand,
  no promise of future product and separate job/B2B/casual routing.
- **Нюанс:** «обязательно предложить посмотреть, что есть» can be wrong in a
  complaint/service context; decision mode must suppress sales when customer is
  asking for support. Aggregating rare categories needs privacy and sample-size
  rules.
- **Доработка:** category resolver first, mode/policy second, response/action
  third. `job_inquiry` and B2B need structured case with owner/SLA, not just
  notification. Outside-window follow-up remains blocked without proof.
- **Acceptance:** out-of-catalog gets no false refusal or promise; demand
  aggregate is deduped and non-PII; support/casual do not receive sales push;
  job inquiry reaches the correct manager queue.

#### Э8.7 - Score, attribution and hedging

- **Нравится:** deterministic step score separate from interpretation,
  episode-level attribution and strict conditions for hedged Gemini.
- **Проблема:** deterministic «closed nodes» still depend on source quality and
  may over-score a customer who clicked but did not understand the offer. It
  must not silently become an automatic discount/priority authority.
- **Attribution:** first/last touch and repeat origin must be append-only and
  tied to episode/order without duplicating revenue. Clearly version the model
  and handle missing attribution.
- **Hedging:** ThreadPoolExecutor does not cancel an already-running HTTP call;
  late winner/loser results, key leases and quota charges must be recorded. Two
  successful generations still produce one authorized reply. Do not introduce
  hedging merely to improve benchmark latency.
- **Acceptance:** score is calibrated against historical outcomes; revenue is
  counted once; hedged attempts have `winner/loser/cancelled/unknown` states;
  no second provider send or payment action.

### 4.10 Э9 - Остаточные улучшения

#### Э9.1 - Priority minor fixes

- **Нравится:** removing PII from summary, replacing `except: pass` with safe
  telemetry and centralizing quiet hours.
- **Correction:** `NEW-MINOR-003` and `NEW-MINOR-001` partly duplicate Э3.1/
  Э3.12; implement once and cross-reference, otherwise two agents may add two
  logging/projection paths. Quiet-hours unification is more than a text cleanup:
  every outbound policy and emergency exception must use the same versioned
  source.
- **Acceptance:** no duplicate writer/log path, error kind is redacted and
  observable, all senders use one policy source.

#### Э9.2 - Constants and limits

- **Нравится:** expiry for spam strikes, one history budget and removal of
  scattered transcript/language limits.
- **Нюанс:** API limits should not be made a freely editable business setting
  without provider-version validation. A stale configured value can either
  reject valid payloads or send invalid ones.
- **Доработка:** define one versioned budget object per surface (text/template/
  quick reply/analysis), with tests for byte/character and API version. Strike
  expiry needs policy owner and audit of old decisions.
- **Acceptance:** changing one budget updates all dependent tests; old strikes
  expire according to documented policy; no limit is silently lower/higher than
  current provider contract.

#### Э9.3 - Retention, identity, observability

- **Нравится:** namespace warning before account migration, retention worker
  instead of webhook ACK cleanup and backup alert path.
- **Priority correction:** `ADD-CODE-008`, `ADD-CODE-009` and `NEW-TECH-004`
  are not harmless leftovers. Namespace and ACK-path cleanup belong in an early
  infrastructure/privacy wave; failure notification independent of DB write is
  an operational P1. Hiding them in E9 delays safeguards required by E1/E2.
- **Privacy nuance:** retaining aggregates (purchase count, total, size) after
  deleting messages may still be personal data. A legal retention class and
  erasure propagation are required before archive design.
- **Identity:** namespace must participate in unique keys/foreign-key lookup,
  backfill and all cache/dedupe keys; merely adding a field without changing
  lookup leaves cross-owner contamination possible.
- **Acceptance:** purge never runs in webhook ACK; bounded worker is idempotent;
  DB failure still emits a redacted alert; provider-owner change cannot reuse
  old client memory/opt-out/order binding.

#### Э9.4 - Discount copy and other text

- **Нравится:** recognizing that visible copy can contradict an otherwise working
  approval gate and inviting negotiation against margin.
- **Priority correction:** factual copy correction for `ADD-CODE-010` should be
  an immediate P0/P1 content fix, not wait for E9. The separate `NEW-PROMPT-004`
  value-framing experiment can stay behind shadow/holdout.
- **Other items:** `_POSITIVE_POST_DELIVERY` regex is an acceptable temporary
  fail-closed guard, but it must be replaced or superseded once structured
  satisfaction exists; `TYPING_SECONDS...` needs measured budget; `JOURNAL_LIMIT`
  and intent enum divergence need schema ownership, not only comments.
- **Acceptance:** discount explanation matches actual migration/approval rule;
  no customer is invited to bargain by a misleading maximum; minor changes have
  no hidden policy side effect.

#### Э9.5 - Deferred items

- **Нравится:** LTV/reactivation, UGC incentive, personal notes, post-payment
  enrichment and seasonal context are correctly treated as policy-sensitive.
- **Missing crosswalk:** deferred list must also explicitly classify
  `NEW-PROMPT-001`, `NEW-LINK-002`, `NEW-LINK-006`,
  `NEW-SUBFUNNEL-004/008/009` and the under-scoped `NEW-PROMPT-002`. Absence
  from the plan is not the same as intentional deferral.
- **UGC:** do not exchange discount for positive review or make «Готово» issue
  a reward automatically. Existing `IgUgcReward` manager review and legal
  policy remain required.
- **Acceptance:** every deferred ID has owner, reason, re-entry condition and
  no hidden customer-visible implementation; no silence is interpreted as
  consent or positive sentiment.

## 5. Сквозной контракт карточек

Этот раздел нужен отдельно, потому что карточка одновременно является UI,
командой FSM, provider payload и частью CRM evidence. Ошибка в одном измерении
может выглядеть успешной в другом.

### 5.1 Разделение сущностей

| Слой | Что является источником истины | Что ему запрещено |
|---|---|---|
| Model/LLM decision | intent, decision mode, candidate card type, natural-language wrapper | URL, amount, stock, TTN, approval, payload command |
| Commerce resolver | product/variant/fit/size/options/quantity availability and price source | customer send, payment confirmation |
| `IgCheckoutProposal` | frozen quote, `quoted_total`, `requested_payment_amount`, `pay_type`, revision, expiry | claim that provider payment is already confirmed |
| Payment projection/provider evidence | paid amount/status and provider identity | rewriting current offer silently |
| Card builder | deterministic title/subtitle/buttons/image from typed inputs | accepting arbitrary model JSON |
| Delivery outbox | logical delivery, physical parts, provider IDs, status and retry boundary | retry after ambiguous provider I/O without reconciliation |
| Webhook/postback normalizer | event type, payload, provider identity, timestamp and source card | direct payment/order mutation without current-state validation |
| Admin UI | versioned read model/projection | becoming a second source of funnel truth |

### 5.2 Card lifecycle

```text
decision planned
  -> authoritative data snapshot
  -> schema/limit/permission preflight
  -> durable logical outbox row
  -> short CAS permission marker
  -> provider I/O outside DB transaction
  -> provider receipt with message ID
       -> SENT / PARTIAL / UNKNOWN / FAILED
```

Fallback is allowed only before provider I/O or after a deterministic provider
rejection that proves no message was accepted. A timeout, connection reset or
missing receipt is `UNKNOWN`; it must not trigger an automatic second payload.

### 5.3 Size-card command contract

The user-visible label can be `S`, `M`, `L`, but the server-side action must be
bound to an opaque signed card instance containing or resolving to:

```text
client_id, commercial_episode_id, session_id, line_id,
product_id, color_variant_id, fit_code, option_values,
candidate/selection revision, offered value, expiry, nonce
```

On click, reload the current state and compare all dimensions. A matching size
string alone is not proof that the customer selected the same product or fit.
The action is applied only once. Every rejected action gets a reason code
(`stale_card`, `wrong_line`, `unavailable_now`, `permission_changed`,
`already_applied`) and a soft customer response.

### 5.4 Generic template vs quick reply

These are different APIs and different inbound shapes:

- generic-template buttons: maximum 3 buttons per element, `postback` or
  `web_url`; carousel maximum 10 elements, title/subtitle maximum 80 characters
  according to the checked Instagram generic-template documentation;
- quick replies: maximum 13, title up to 20 characters; a tap yields a
  `message` event with `quick_reply.payload` and button text, not necessarily a
  standalone postback event.

The plan should not call both «postback» or assume the Messenger event shape for
Instagram. Each surface needs its own serializer, parser, limit tests and
provider-version reference.

## 6. Crosswalk находок: что пропущено, слито или закрыто

Отсутствие ID в отдельном заголовке плана не должно оставаться не объяснённым.
Следующая таблица - минимальная коррекция handoff.

| ID | Статус в каноне | Что сделано в `04` | Что нужно добавить/уточнить |
|---|---|---|---|
| `NEW-TECH-002` | CLOSED/REJECTED, idempotent retry | Не должен стать задачей | Явно записать `CLOSED`, сохранить regression reference и не «чинить» двойной вызов |
| `NEW-SUBFUNNEL-002-OLD` | Intentionally rejected | Используется новая одна definition в Э4.1 | Добавить cross-reference на rejected design; не создавать два registry |
| `NEW-PROMPT-001` | Confirmed/P1 в каноне | Не имеет собственного пункта | Либо добавить в E9/P1 как curated locale lifecycle copy с factual core, либо явно deferred с owner/metric |
| `NEW-PROMPT-002` | Reframed: playbooks уже существуют | Только упомянут в E7.5 applicability | Добавить задачу на evidence/outcome evaluation, не переписывать существующий routing |
| `NEW-LINK-002` | P2, friction tone/escalation | Только `_REASON_LABELS` и UI journal в Э4.7 | Добавить episode-scoped follow-up suppression + manager task после подтверждённого friction |
| `NEW-LINK-006` | P2, ad product prefill | Не покрыт | Добавить prefilled-with-confirmation node/source; не закрывать product автоматически |
| `NEW-SUBFUNNEL-004` | P2, preferences persistence | Не покрыт | Добавить typed client/episode preference projection with TTL and evidence |
| `NEW-SUBFUNNEL-008` | P2, adaptive post-purchase question | Частично E6.3 generic feedback | Отдельно указать product/occasion/history adapter and one-question policy |
| `NEW-SUBFUNNEL-009` | P2/P1 thermo, product-specific understanding | Не покрыт | Добавить QUALITY node `product_specifics_communicated` only for products with authoritative attributes |
| `NEW-LINK-003` | P3, follow tone | Deferred list есть | Сохранить deferred reason; не выводить loyalty из follow state |
| `NEW-LINK-005` | P3, UGC/satisfaction relation | Deferred list есть | Require both user-evidenced satisfaction and UGC facts; no automatic reward |
| `NEW-TECH-004` | Confirmed operational notification gap | Спрятан в E9.3 | Поднять в early ops/privacy wave; DB failure must not suppress alert |
| `ADD-CODE-008` | P1 namespace | Спрятан в E9.3 | Сделать precondition before any account/provider migration and cache/dedupe change |
| `ADD-CODE-009` | P1 webhook ACK retention | Спрятан в E9.3 | Перенести до customer-visible feature; move purge to bounded worker |
| `ADD-CODE-003` | P1 watchdog | Э2.10, но поздно | Put heartbeat/work-lease baseline in Wave 0/1 before card rollout |
| `ADD-PERF-001` | P1 connection admission | Э8.1 | At minimum measure shared-host budget before adding threads/card media |

## 7. Исправленная последовательность реализации

Это не обязательная замена плана, а более безопасный вариант, учитывающий
найденные зависимости.

### Wave 0 - factual and policy gates, no customer behavior

1. Current source/dirty-worktree inventory and exact `origin/main` SHA.
2. Meta app type, account linkage, Graph API version, scopes and exact
   Instagram message capabilities. Mark One-Time Notification as unavailable
   unless a current IG-specific contract proves otherwise.
3. SQLite migration/environment preflight, including test HMAC fixture; then
   separate schema and `invalid_options` failures.
4. Complete storage-engine inventory from model metadata + lock writers; include
   all commerce/post-sale tables, not only current `IG_RUNTIME_TABLES`.
5. Read-only lifecycle terminal-disposition report with explicit denominator;
   do not add or send customer events.
6. Card/quick-reply provider contract matrix and size-count matrix.

### Wave 1 - durable correctness before broad cards

1. Webhook normalized event schema and hidden/opt-out/erasure semantics.
2. Durable outbox/receipt contract shared by text, media, template and
   lifecycle; provider HTTP outside DB transaction.
3. Fix silent tail loss and ambiguous fallback.
4. Fix provider-timestamp response window.
5. Add request-level provenance and no-send action corpus.
6. Add CustomerTurn through relation/primary source and idempotent claim.
7. Move retention cleanup out of webhook ACK and namespace identity into all
   lookup/dedupe keys.
8. Heartbeat active-work lease and generation baseline.

### Wave 2 - one constrained in-window card slice

1. Deterministic card builder/serializer and card rhythm guard.
2. One catalog/size card behind a feature flag, only for current response window.
3. Use existing `IgCommerceSelectionSession`; no parallel card state.
4. Require current variant/fit/option resolver and exact media or truthful
   text fallback.
5. Render all available sizes according to the matrix in section 5; never show
   three of six without a continuation affordance.
6. Verify outbound receipt and CRM projection with provider mocks/approved test
   account before any larger rollout.

### Wave 3 - authoritative commerce and payment card

1. Proposal-based payment summary with explicit full/prepayment values.
2. First-party checkout view event for `PAYLINK_VIEWED`; do not infer it from
   an Instagram web URL click.
3. Final revalidation of proposal revision, access token, expiry, payment state,
   inventory and permission.
4. Product carousel/size choices only after exact media resolver and stale-card
   tests.

### Wave 4 - conversation correctness

1. Manager role/protocol, correction repair and follow-up watermark/episode.
2. Cache outage no-AI lane and age-aware queue fairness.
3. Analysis ledger/downgrade policy and bounded Gemini capacity.
4. Memory typed projection and context planner.

### Wave 5 - funnel, UI and product intelligence

1. Existing readiness nodes into versioned projection.
2. Invalidation/closure provenance and recipient/occasion facts.
3. API/UI journal and open-node follow-up.
4. Ad prefill, preferences, thermo/product-specific understanding and custom
   brief as independently measured slices.

### Wave 6 - post-sale only after policy and delivery proof

1. Kind-specific delivery/post-sale event model compatible with COD/manual
   orders; do not weaken payment FK invariants accidentally.
2. Shipment-scoped code 7/arrival and storage reminders only when channel
   eligibility is proven.
3. Delayed feedback and typed satisfaction; no UGC/discount incentive without
   legal/manager decision.
4. Separate post-sale projection and exchange/return case transitions.

### Wave 7 - agent experiments and operations

1. Commitment/correction/uncertainty/contradiction contracts.
2. Shadow/holdout, review labels, ablation and cohorts.
3. Read/decision/write adapters around the proven delivery boundary.
4. Connection budgets, bounded analysis concurrency, readable alerts and
   attribution/hedging only after measured need.

## 8. Минимальный acceptance checklist для следующего агента

Перед изменением `04_IMPLEMENTATION.md` или кодом проверить:

- [ ] Каждая из 90 секций имеет один owner, одну бизнес-инварианту и один
      source-of-truth.
- [ ] Для каждого ID есть статус `DO/REFRAME/CALIBRATE/KEEP/CLOSE/DEFER`.
- [ ] P0/P1 source-confirmed defects не отложены за customer-visible cards без
      письменной причины владельца.
- [ ] Meta capability matrix подтверждает именно Instagram, а не только
      Messenger.
- [ ] `ensure_lifecycle_event` создаёт durable row атомарно с бизнес-изменением;
      только dispatcher/HTTP вынесены после commit.
- [ ] Text/media/card sender имеют одинаковые receipt/unknown/idempotency
      semantics.
- [ ] Payment card использует proposal quote; payment truth используется только
      для подтверждённой оплаты.
- [ ] `PAYLINK_VIEWED` разделён на rendered/clicked/first-party viewed.
- [ ] Postback и quick reply имеют разные нормализованные event types и
      provider identity.
- [ ] Size card проверяет product/variant/fit/options/episode/line/revision,
      а не только размерную строку.
- [ ] Поведение 0/1/2/3/4-13/>13 размеров покрыто тестами и описано в UI.
- [ ] `IgOrderShipment` используется для shipment status; scalar
      `Order.tracking_number` не объявлен полной историей.
- [ ] SQLite migration test environment имеет безопасный non-production HMAC
      fixture; MariaDB concurrency/generated-column tests запускаются на
      disposable database.
- [ ] Любая customer-visible policy имеет shadow/holdout или письменное
      исключение для чистого correctness fix.
- [ ] Метрика имеет numerator, denominator, period, cohort, baseline и stop
      condition.
- [ ] Rollback для schema/provider side effects описан как compatibility/
      reconciliation plan, а не только feature flag.
- [ ] Production proof после реализации будет содержать SHA, migration state,
      targeted runtime checks, persisted IDs and redacted logs; broad crawl не
      используется.

## 9. Итоговый вердикт

`04_IMPLEMENTATION.md` можно сохранить как основу, но перед передачей агенту,
который будет писать код, обязательно исправить четыре вещи:

1. убрать предположение, что Instagram One-Time Notification/`notification_messages`
   автоматически открывает post-24h delivery;
2. исправить Э2.7 на «durable row внутри transaction, HTTP после commit»;
3. заменить `payment_truth_snapshot` в pre-payment card на frozen proposal quote
   и разделить prepayment/full payment;
4. сделать card/postback/media contracts зависимыми от normalized event schema,
   current variant resolver и receipt-first outbox.

Остальные замечания в основном уменьшают риск переусложнения: не делать второй
FSM вместо существующего state, не превращать UI или модель в source of truth,
не скрывать пропущенные находки и не считать aggregate metric доказательством
корректности конкретного customer journey. После этих коррекций план станет
пригодным для поэтапной реализации и проверки, сохраняя свободу другого агента
отвергнуть отдельную рекомендацию при наличии более сильного evidence.

## Приложение A - Exhaustive ID crosswalk

В этой таблице каждый идентификатор из `01_FINDINGS.md` и `03_ADDITIONAL_FINDINGS.md`
назван явно. Группировка означает общий verdict и область аудита; она не
означает, что все элементы группы нужно реализовывать одним коммитом.

### Core findings

| ID | Verdict | Где проверять в аудите | Обязательная оговорка |
|---|---|---|---|
| `NEW-DB-001` | CALIBRATE/GATE | Э0.2, Э3.2, Э3.11, Э8.1 | Проверить полный table set и реальные engines; MyISAM блокирует lock claims |
| `NEW-LIFECYCLE-001` | CALIBRATE/GATE | Э0.3, Э6.1 | Текущий row хранит disposition, не полную transition history |
| `NEW-POLICY-001` | DO/GATE | Э0.4, Wave 0/1 | Все outbound producers должны мигрировать на policy object; one-stream adoption недостаточна |
| `NEW-OPTIN-001` | POLICY/GATE | Э1.0-Э1.1 | Instagram One-Time Notification capability is not assumed; verify app type and IG-specific docs |
| `NEW-PROVENANCE-001` | DO | Э3.6, Wave 1 | Reply-level chain must include request ID, prompt/context revisions and selected attempts |
| `REOPEN-CORE-001` | DO/POLICY | Э3.18, Wave 1 | Define hidden UI vs automation suppression vs erasure before persistence change |

| ID | Verdict | Где проверять в аудите | Обязательная оговорка |
|---|---|---|---|
| `NEW-MEM-001`, `NEW-MEM-002`, `NEW-MEM-003` | DO/REFRAME | Э3.1, Э3.12, Э5.1, Э5.5 | Typed projection и watermark; free summary не authoritative |
| `NEW-LANG-001`, `NEW-STAGE-001` | DO | Э3.2, Э3.3 | Reset/role scope и transaction engine должны быть доказаны |
| `NEW-UX-001`, `NEW-UX-002`, `NEW-UX-003`, `NEW-UX-004` | DO/REFRAME | Э4.3, Э4.7 | API/read model first; список предпочтительнее обязательного графа |
| `NEW-COMMERCE-001`, `NEW-COMMERCE-002`, `NEW-COMMERCE-003` | DO | Э3.10 | Line/recipient/episode/repeat, без смешения payment truth |
| `NEW-AI-001`, `NEW-AI-002` | DO/REFRAME | Э3.15 | Ledger before downgrade; SLA vs full 3.7 exhaustion |
| `NEW-CAT-001`, `NEW-CAT-002`, `NEW-CAT-003` | DO | Э3.7, Э3.8, Э5.5 | Exact variant resolver/media and revision cache |
| `NEW-CAT-004` | DO/DEFER | Э5.5 | Только authoritative catalog facts; не обещать план/срок |
| `NEW-CAT-005` | DEFER | Э9.5 | Сезонность - context, не hard rule |
| `REOPEN-AI-001`, `RECONFIRM-CTX-001` | DO/REFRAME | Э3.8, Э5.4 | Cache error != empty; intent planner deterministic and auditable |
| `NEW-FUP-001`, `NEW-FUP-002` | DO | Э3.9 | Recheck before I/O; after I/O outcome is sent/unknown, not cancelled |
| `NEW-ANALYSIS-001`, `NEW-ANALYSIS-002`, `NEW-ANALYSIS-003` | DO/CALIBRATE | Э3.4, Э3.5, Э8.2 | Freshness and role evidence; concurrency only after queue metrics |
| `NEW-SEC-001`, `NEW-SEC-002` | DO/REFRAME | Э3.13, Э3.14 | Boundary/risk signal, no injection autoban |
| `NEW-FUNNEL-001`, `NEW-FUNNEL-002`, `NEW-FUNNEL-003`, `NEW-FUNNEL-004`, `NEW-FUNNEL-005` | DO/REFRAME | Э4.1, Э4.5, Э4.9, Э6.5, Э6.6 | Separate post-sale projection; no stage encyclopedia |
| `NEW-MEM-004`, `NEW-MEM-005`, `NEW-MEM-006`, `NEW-MEM-007`, `NEW-MEM-008`, `NEW-MEM-009` | DO/DEFER | Э3.11, Э4.4, Э5.1-Э5.3, Э9.5 | Occasion/recipient scope; personal notes policy; one owner per projection |
| `NEW-DELIVERY-001`, `NEW-DELIVERY-002` | CALIBRATE/DO | Э6.2, Э6.3 | Provider policy, shipment identity and cadence must precede sends |
| `NEW-LTV-001` | DO | Э6.4 | User-evidenced satisfaction, no score from silence |
| `NEW-LTV-002` | DEFER | Э9.5 | Consent, Meta policy, holdout and frequency cap required |
| `NEW-UGC-001` | DEFER | Э1.9, Э6.3, Э9.5 | Never make discount conditional on positive review |
| `NEW-FOLLOW-001` | CALIBRATE | Э1.8 | Explicit CTA can replace polling only after API/quota evidence |
| `NEW-PROMPT-001` | UNDER-SCOPED DO | Э1.7, Э6.3, Э9.4 | Curated locale copy with factual core; no free model mutation of TTN/price |
| `NEW-PROMPT-002` | REFRAME | Э7.5, Э9.5 | Playbooks already exist; add outcome/evidence evaluation, not duplicate routing |
| `NEW-PROMPT-003` | DO | Э5.6, Э1.9 | Structured brief, attachments and manager handoff |
| `NEW-PROMPT-004` | SPLIT | Э1.6, Э9.4 | Approval gate is present; immediate copy correction separate from value-framing experiment |
| `NEW-PERF-001`, `NEW-PERF-002`, `NEW-PERF-003` | CALIBRATE/DO | Э8.1, Э8.2, Э8.5 | Measure provider/DB budgets first; no unbounded async/hedging |
| `NEW-ATTR-001` | DO | Э8.7 | Episode/multi-touch attribution, no duplicate revenue |
| `NEW-SCORE-001` | DO/REFRAME | Э8.7 | Deterministic progress separate from model interpretation |
| `NEW-CRIT-001`, `NEW-CRIT-002`, `NEW-CRIT-004` | CALIBRATE/DO | Э0.3, Э2.6, Э6.1 | Window, COD and late binding require live evidence |
| `NEW-CRIT-003` | KEEP/CLOSE | Э6.6 verification note only | Canonical file rejects the defect hypothesis; retain only a timing regression test, no new implementation |
| `NEW-BRANCH-001`, `NEW-BRANCH-002` | DO | Э7.3, Э8.6 | Resolver/owner before customer promise; category-specific handoff |
| `NEW-OPS-001`, `NEW-OPS-002`, `NEW-OPS-003` | DO/CALIBRATE | Э8.3, Э8.4 | Inspect current alert bodies; historical daemon churn is not current proof |
| `NEW-LINK-001`, `NEW-LINK-002`, `NEW-LINK-003`, `NEW-LINK-004`, `NEW-LINK-005`, `NEW-LINK-006` | DO/DEFER | Э4.6, Э4.7, Э3.10, Э9.5 | Missing-node follow-up; friction/ad prefill; follow state never equals loyalty |
| `NEW-SUBFUNNEL-001`, `NEW-SUBFUNNEL-002`, `NEW-SUBFUNNEL-003`, `NEW-SUBFUNNEL-004`, `NEW-SUBFUNNEL-005`, `NEW-SUBFUNNEL-006` | DO/REFRAME | Э4.1-Э4.5, Э4.8, Э9.5 | One definition, explicit policy fields, no second FSM |
| `NEW-SUBFUNNEL-007`, `NEW-SUBFUNNEL-008`, `NEW-SUBFUNNEL-009`, `NEW-SUBFUNNEL-010`, `NEW-SUBFUNNEL-011`, `NEW-SUBFUNNEL-012` | DO/DEFER | Э4.1, Э4.5, Э4.8, Э6.3, Э9.5 | Payment != consent; product-specific understanding and one-question cadence |
| `NEW-TECH-001`, `NEW-TECH-003`, `NEW-TECH-004`, `NEW-TECH-005` | DO | Э2.7, Э6.1, Э8.3, Э3.12 | Correct transaction boundary, late assignment, alert fallback and watermark |
| `NEW-TECH-002` | KEEP/CLOSE | Э6.2 note | Double dispatcher call is intentionally idempotent retry; do not reopen as bug |
| `NEW-TEST-001` | DO | Э0.1 | SQLite state/schema and HMAC migration environment are separate blockers |
| `NEW-TMPL-001`, `NEW-TMPL-002`, `NEW-TMPL-003`, `NEW-TMPL-004`, `NEW-TMPL-005`, `NEW-TMPL-006`, `NEW-TMPL-007`, `NEW-TMPL-008`, `NEW-TMPL-009`, `NEW-TMPL-010` | DO/REFRAME | Э1.2-Э1.12 | Generic/quick-reply contracts, durable sender, card rhythm and no model payload |
| `NEW-SUBFUNNEL-002-OLD` | KEEP/CLOSE | Э4.1 note | Historical rejected two-registry design; do not implement |

### Additional delivery and agent findings

| ID | Verdict | Где проверять | Обязательная оговорка |
|---|---|---|---|
| `ADD-CODE-001`, `ADD-CODE-002`, `ADD-CODE-003`, `ADD-CODE-004`, `ADD-CODE-005`, `ADD-CODE-006`, `ADD-CODE-007` | DO/REFRAME | Э2.1-Э2.3, Э2.8-Э2.11 | Durable delivery, turn identity, cache-safe budget and age fairness before broad cards |
| `ADD-CODE-008`, `ADD-CODE-009`, `ADD-CODE-010` | DO/REFRAME | Э9.3, Э9.4, Wave 1 | Namespace/ACK cleanup early; discount copy immediate; approval gate already exists |
| `ADD-DATA-001` | DO | Э3.17 | Event-per-participant or complete participant index; no substring JSON rewrite |
| `ADD-DIALOG-001`, `ADD-DIALOG-002` | DO | Э2.2, Э2.4 | Burst turn and manager role are separate but coupled contracts |
| `ADD-EXTRA-001`, `ADD-EXTRA-002`, `ADD-EXTRA-003`, `ADD-EXTRA-004` | DO/REFRAME | Э2.3, Э2.9, Э2.10, Э0.6 | Break failure chains; one turn identity; explicit end-to-end budget |
| `ADD-PERF-001` | CALIBRATE/DO | Э8.1 | Shared-host connection/provider budget before adding workers |
| `ADD-SEC-001` | CALIBRATE | Э3.16 | SSRF candidate only; mock policy tests, no live exploit probe |
| `ADD-AGENT-001`, `ADD-AGENT-002`, `ADD-AGENT-003`, `ADD-AGENT-004`, `ADD-AGENT-005`, `ADD-AGENT-006` | DO/REFRAME | Э7.1-Э7.4, Э2.5 | Typed commitments/corrections/resolvers, not free model authority |
| `ADD-AGENT-007`, `ADD-AGENT-008`, `ADD-AGENT-009`, `ADD-AGENT-010`, `ADD-AGENT-011`, `ADD-AGENT-012`, `ADD-AGENT-013` | DO/REFRAME | Э0.5, Э0.7, Э7.5-Э7.8 | Trace-first actions, reviews, shadow/holdout, ablation and cohort safety |
| `ADD-AGENT-014` | DEFER/CALIBRATE | Э9.5 | Automation disclosure scope depends on current app type and jurisdiction |

### Explicit minor crosswalk

`NEW-MINOR-001`, `NEW-MINOR-002`, `NEW-MINOR-003`, `NEW-MINOR-004`,
`NEW-MINOR-005`, `NEW-MINOR-006`, `NEW-MINOR-007`, `NEW-MINOR-008`,
`NEW-MINOR-009`, `NEW-MINOR-010`, `NEW-MINOR-011`, `NEW-MINOR-012`,
`NEW-MINOR-013`, `NEW-MINOR-014`, `NEW-MINOR-015` all belong to Э9, but not
all should wait until the end:

- `NEW-MINOR-001`, `NEW-MINOR-003`, `NEW-MINOR-009` are partly covered by
  Э3.1/Э3.12 and should be implemented once, not twice;
- `NEW-MINOR-002`, `NEW-MINOR-007` require retention/legal classification;
- `NEW-MINOR-004`, `NEW-MINOR-005`, `NEW-MINOR-010`, `NEW-MINOR-011`,
  `NEW-MINOR-014` are budget/constant consistency tasks and depend on the
  delivery/context budget;
- `NEW-MINOR-006` needs strike-aging policy;
- `NEW-MINOR-008` is a temporary fail-closed sentiment guard;
- `NEW-MINOR-012` is superseded only after append-only journal migration;
- `NEW-MINOR-013` is already source-checked and should be marked verified/no-op,
  not left as an unqualified implementation checkbox;
- `NEW-MINOR-015` needs one documented owner for `IgClient.Intent` versus
  analysis `interaction_type`, but is not itself a runtime bug.

## Приложение B - Evidence commands used

The following read-only checks were used for this audit:

```text
rg -n '^## Э[0-9]|^### ' docs/instagram_bot_audit/new/04_IMPLEMENTATION.md
rg -n '^### (NEW|REOPEN|RECONFIRM|ADD)-' docs/instagram_bot_audit/new/01_FINDINGS.md
TWC_PYTHON=.venv/bin/python manage.py check
```

`manage.py check` passed with CPython 3.14.6/Django 6.1. Focused test commands
created SQLite test databases but stopped in migration `0158` because the
required local HMAC keyring/active key id was not provided. No claim of focused
test pass is made here. A future agent should provide an ephemeral local test
key through the test environment and then rerun the suite; production keys must
never enter this document or repository.

## Приложение C - Дополнительные точечные расхождения

Эти пункты не меняют главный verdict, но их стоит внести в `04` при следующей
редакции, чтобы реализация не оставила мелкие логические дыры.

1. **`NEW-POLICY-001` coverage.** Э0.4 (`04:244-276`) принимает только один
   поток до Definition of Done. Добавить inventory всех outbound producers,
   dual-run/coverage metric и no-send default для немигрированных потоков.
   Иначе новый E1/E6 путь может обойти policy object.
2. **`NEW-CRIT-001` activation gate.** Владелец может приоритизировать cards,
   но activation post-window delivery нельзя разрешать до Э0.3 terminal
   disposition и доказанного channel policy. Opt-in не исправляет события,
   которые вообще не были созданы.
3. **`NEW-TECH-001` transaction wording.** В `04:1306-1310` заменить blanket
   «ensure только on_commit/вне transaction» на «create/update durable row
   атомарно; HTTP dispatch after commit». Это принципиально разные операции.
4. **`ADD-CODE-004/006` shared budget.** In-process counter из Э2.3 не
   является глобальным guard при нескольких process. Нужен shared durable
   counter/admission или явная доказанная single-process deployment model.
5. **`ADD-PERF-001` early reserve.** Connection/provider reserve из Э8.1
   должен быть safety gate до customer-visible cards и post-purchase, даже
   если полный worker budget останется в Э8.
6. **Action taxonomy for `blocking_for`.** Э4.1 ограничивает blocking node
   только paylink. Определить все irreversible actions: issue invoice,
   reserve inventory, create TTN, verified payment transition, manager-side
   mutation. Маркетинговый context не должен блокировать, но write action
   должен иметь explicit guard.
7. **Единый vocabulary funnel state.** Не смешивать `required` с lifecycle
   status и не добавлять одновременно `closed_superseded`/`superseded`/
   `stale_confirm` без typed reason. Рекомендуется: `applicable`, `status`,
   `freshness`, `confirmation_required`, `reason` как отдельные поля.
8. **`NEW-SUBFUNNEL-012` closure enum.** В `04:2764-2771` отсутствуют
   `postback` и `system_authoritative`, хотя postback назван самым надёжным.
   Без этих values card actions не попадают корректно в provenance/UI.
9. **`NEW-FUNNEL-004` mode naming.** В Э4.5 используется `normal`, которого
   нет в canonical five modes. Либо использовать `browse`, либо ввести
   отдельный orthogonal `pace`. Исправить также ссылку Э2.2, где указан Э4.6,
   хотя mode slice находится в Э4.5.
10. **`NEW-FOLLOW-001` is partial, not closed.** E1.8 covers explicit CTA
    verification only; unknown Graph result still schedules recheck and
    `NEW-LINK-003` follow-tone remains deferred. Do not mark the finding solved.
11. **UGC contradiction.** E1.7 (`04:777-781`) предлагает UGC card after
    positive feedback, но E9.5 (`04:4304-4309`) правильно defers UGC/legal.
    Удалить раннюю активацию или поставить hard policy/legal/opt-in/receipt
    gate; follow-gate and UGC offer are separate slices.
12. **`NEW-SUBFUNNEL-008`.** E6.3's adjective «адаптированный» не заменяет
    resolver по `garment_type`, occasion, repeat history and locale. Добавить
    immutable factual order core, curated wrapper and safe fallback.
13. **`NEW-LINK-002`.** `FrictionSummary.escalate` in E4.7 is only a UI flag;
    it does not pause follow-ups/create manager case. Add episode-scoped,
    idempotent friction gate and false-positive test.
14. **`NEW-LINK-006`.** Ad prompt hint in E8.7 is not state. Add
    `prefilled_pending_confirmation`, trusted campaign evidence, change-product
    path and UI provenance; never auto-complete product node.
15. **`NEW-SUBFUNNEL-004`.** Add durable explicit preferences and separate
    `unmet_preference`, TTL/source IDs and a sorting hint. Do not infer a stable
    taste from one unavailable variant.
16. **`NEW-SUBFUNNEL-009`.** Add `product_specifics_communicated` only where
    catalog facts require it (thermo/fleece/DTF/fit). Closure is a fact that was
    communicated, not a model guess that customer understood; thermo may be
    blocking for express checkout.
17. **E4.9 carry-over.** Add recipient identity, freshness/TTL and lineage to
    carried size/fit; a gift recipient's size must never leak into buyer line.
18. **E5.2 L0.** «Денежная правда» and service presence in the index must be
    references/revisioned pointers, not a second authoritative payment claim.
    All action gates reread source rows.
19. **E5.6 customer copy.** «С ним свяжутся» is a promise. Require durable
    owner/ack/SLA or use truthful «заявка передана менеджеру» without ETA.
20. **E6.1 assignment relaxation.** If delivery context uses only
    `IgOrderAssignment`, check assignment freshness, recipient scope,
    hidden/opt-out/permission and revalidate immediately before send.
21. **E8.5 snapshot.** Explicitly close the snapshot transaction and release
    connection before Gemini/provider I/O; otherwise the optimization revives
    `NEW-TECH-001` under another name.
22. **`NEW-MINOR-013`.** It is described as verified/no fix in `04:4288-4290`
    but remains an unchecked implementation item. Mark it verification-only or
    `[-]`, not a phantom commit/deploy task.
23. **Canonical index exception.** `01_FINDINGS.md` calls its final index the
    main priority source (`01:7763+`), but active owner-priority
    `NEW-OPTIN-001` and `NEW-TMPL-001..010` are outside that table. Add an
    explicit owner-priority annex/exception in `01`, otherwise a coverage tool
    will report them as missing or closed.
