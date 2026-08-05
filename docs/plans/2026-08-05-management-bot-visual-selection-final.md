# Финальный план отбора визуальных улучшений management Instagram bot

**Дата:** 2026-08-05
**Статус:** канонический shortlist для последующих релизов; кодовые изменения
выпускаются отдельными срезами
**База:** `main` / `1849441d`
**Область:** management Instagram bot, список клиентов, переписка, коммерческий
контекст, обзор и статистика.

## Цель

Сделать рабочее место менеджера быстрее для сканирования и безопаснее для
решений: новый inbound должен быть заметен без перезагрузки, коммерческое
состояние должно объясняться фактом, статистика должна читаться одним взглядом,
а адаптивность и анимации должны помогать работе, а не добавлять шум.

Typing/seen уже выделен в отдельный и доставленный срез. Этот план не меняет его
поведение и не дублирует уже выпущенные изменения: зеленое verified paid,
фиолетовое shipped, янтарное attention, сворачиваемый context drawer,
компактные primary/advanced filters, симметричная панель действий и обновлённая
Overview-сетка считаются базой.

## Как принималось решение

Каждая рекомендация из 100 оценена по одной шкале и по одному набору запретов:

| Критерий | Вес | Что считается достаточным |
|---|---:|---|
| Скорость решения менеджера | 25% | элемент подсказывает, что делать дальше, а не только украшает экран |
| Скорость визуального понимания | 20% | смысл считывается без чтения длинного абзаца |
| Правдивость данных | 20% | состояние строится на существующем server/API fact, а не на догадке |
| Визуальный эффект | 15% | появляется ясная и спокойная иерархия, а не декоративная анимация |
| Интерактивность | 10% | действие сокращает путь или сохраняет контекст работы |
| Responsive-устойчивость | 5% | работает на 320/375/768/1440 px без overflow |
| Стоимость поддержки | 5% | можно покрыть контрактом, browser QA и rollback |

В реализацию попадают решения с итогом не ниже 75/100 и без провала по
правдивости. Цвет без короткого текстового маркера, звук без явной операторской
необходимости, постоянные пульсации, fake countdown, выдуманный shipment status,
автопереключение открытого диалога и скрытая бизнес-логика во frontend запрещены.

## Приоритеты и порядок релизов

Каждый релиз ниже является самостоятельным срезом: RED-контракт, минимальная
реализация, focused tests, browser QA, отдельный commit, push feature-ветки,
fast-forward в локальный `main`, push `origin/main`, серверный deploy и
проверка SHA/heartbeat. Следующий срез начинается только после подтверждения
предыдущего.

### Release 1 — Live inbox и пространственная память

**Ценность:** менеджер видит новый inbound сразу, понимает, какая карточка
изменилась, и не теряет открытый диалог.

1. Poll existing clients API только при видимой вкладке Bot; `AbortController`
   отменяет устаревший search/filter/list request.
2. Снимок сравнивается по `client_id + last_message_at`; серверная сортировка
   `-last_message_at, -id` остаётся единственным источником порядка.
3. DOM-строки получают стабильный `data-client-id`; существующие элементы
   обновляются in-place, новые входят сверху, ушедшие из фильтра выходят мягко.
4. FLIP-анимация двигает только изменившиеся строки, длительность 160–200 ms;
   rail/chip получают короткий highlight, вся карточка не вспыхивает.
5. `prefers-reduced-motion` отключает движение и оставляет маркер, aria-live и
   корректный порядок.
6. Открытый менеджером клиент никогда не заменяется другим автоматически.
   Если он не выбран, новый клиент может появиться сверху, но selection не
   меняется принудительно.
7. В header списка появляется компактное `Оновлено ...` и stale/reconnect
   состояние после двух пропущенных циклов; retry использует backoff и jitter.
8. Частые изменения coalesce-ятся в один render frame; повторное событие не
   создаёт дубликат строки или маркера.

**Не делаем в этом релизе:** SSE, звук, виртуализацию списка, принудительный
auto-open чужого диалога и искусственное изменение `last_message_at`.

**Acceptance:** visible-tab polling, abort, stale/reconnect, idempotent
reconcile, FLIP, reduced-motion и selected-client preservation покрыты
контрактами; browser QA проверяет 320/375/768/1440 px и отсутствие overflow.

### Release 2 — Новые сообщения и управление перепиской

**Ценность:** менеджер видит границу новых сообщений и возвращается к актуальной
точке без ручной прокрутки длинной истории.

1. Использовать существующий `after_id` conversation API; новые сообщения
   добавляются без пересоздания transcript.
2. Добавить разделитель `Нові повідомлення` только для сообщений, пришедших
   после открытия/последнего явного просмотра текущей сессии. Не выдавать его за
   серверный unread marker, пока такой факт не хранится backend.
3. Кнопка `До останнього` появляется только при отрыве от низа; переход сохраняет
   anchor и не дёргает layout.
4. Добавить date separators только при смене календарной даты; подряд идущие
   сообщения одной роли сгруппировать, но оставить доступный timestamp.
5. В conversation header явно показывать active takeover: `Менеджер веде
   діалог`; обычные transport errors остаются отдельным operational warning.
6. Для TTN и provider message id добавить copy action с text fallback и
   коротким подтверждением вместо постоянного текста.
7. Sticky action rail в длинном context drawer разрешён только для одной
   primary action; secondary facts не превращаются в постоянно плавающие кнопки.

**Acceptance:** сохранение scroll position, корректная работа `after_id`,
keyboard/focus contract, mobile one-column flow и browser проверки длинного
диалога.

### Release 3 — Коммерческое доказательство и доставка

**Ценность:** цвет не требует догадки: менеджер видит, на каком факте основан
paid/shipped/attention и что делать дальше.

1. Сохранить backend precedence: active shipment с подтверждённым tracking
   отображается как shipped; confirmed paid без active shipment — paid;
   pending action — attention; остальное нейтрально.
2. Добавить компактный evidence popover по клику/фокусу: источник факта, сумма,
   order id, TTN, `tracking_checked_at`, verifier и время. Токены, raw webhook и
   лишние PII никогда не показывать.
3. В карточке заказа показать truthful lifecycle только из canonical Nova
   Poshta fields: `Не відправлено`, `Відправлено`, `У дорозі`, `У відділенні`,
   `Отримано`, либо `Статус не підтверджено`. TTN сам по себе не является
   доказательством движения.
4. В detail показать одну компактную progression line, а историю переходов
   открыть по клику; пустые этапы и пустые секции не рендерить.
5. Для `attention` показывать короткий next action (`Перевірити оплату`,
   `Прив'язати замовлення`, `Запросити TTN`) только если API реально сообщает
   такую возможность.
6. Таймер оплаты делать только при настоящем server `expires_at`; без него
   никакого countdown, псевдо-SLA или вычисления от момента открытия страницы.
7. Тонкая rail/chip transition при изменении факта, без полной заливки карточки;
   reduced-motion оставляет цвет, текст и aria announcement.

**Acceptance:** presentation matrix paid/shipped/done/pending/error, order and
Nova Poshta serializer tests, no inferred delivery, detail popover keyboard path,
responsive 320 px.

### Release 4 — Статистика, которую можно понять одним взглядом

**Ценность:** вместо стены таблиц менеджер видит объём, качество и узкое место
воронки за выбранный период, затем открывает подробности.

#### Backend data contract

Расширить текущий stats API без изменения его существующих полей:

- `generated_at` и `schema_version` для честного времени свежести;
- `totals.messages`, `totals.inbound_messages`, `totals.bot_replies`,
  `totals.manager_messages`, `totals.unique_conversations`;
- `totals.qualified`, `totals.paid`, `totals.lost_or_refused`, где paid берётся
  только из verified payment truth;
- сохранить `interactions`, `stages`, `funnel`, `ads`, `products`, objections и
  `funnel_meta` как источники диаграмм;
- при отсутствии данных отдавать `0`/пустой массив, а не выдуманную динамику.

#### UI composition

1. Верхний ряд — четыре KPI: `Сообщения`, `Діалоги`, `Підтверджені оплати`,
   `Відмови / втрати`; у каждого короткий definition tooltip и `дані ... тому`.
2. Второй ряд — proportional funnel: `написали → кваліфіковані → товар →
   checkout → verified paid`; ширина полосы нормируется на первый этап, нули не
   создают пустых декоративных карточек.
3. Третий ряд — две компактные горизонтальные диаграммы: категории диалогов и
   товары; подписи короткие, точное значение показывается рядом/по focus.
4. Реклама — ranked bars `chats / paid / revenue`, топ-5 в первом экране,
   остальные в раскрытии; не смешивать revenue с количеством диалогов.
5. Подробные cohort/drop-off/time-on-step таблицы остаются в disclosure, не
   исчезают и не занимают первый viewport.
6. Переключатель `Метрики / Інциденти` показывает actionable health отдельно;
   нули и неактуальные warning rows скрываются, но badge количества сохраняется.
7. Значение KPI crossfade-анимируется только при изменении и только 120 ms;
   initial load показывает skeleton не дольше 800 ms, затем честный unavailable.

**Не делаем:** тяжёлую chart library, декоративные pie charts, time-series без
server series, проценты без denominator, conversion из неподтверждённой оплаты.

**Acceptance:** stats API contract tests, distinct counts, zero/empty states,
period/timezone tests, chart-label overflow matrix и screenshot QA.

### Release 5 — Фильтры, context и micro-interactions

**Ценность:** уменьшить число кликов и случайных действий после того, как live
и stats уже дают правильные данные.

1. Показывать counts в advanced filter disclosure и компактные active-condition
   chips; текущие `Усі/Активні/Оплачені` остаются первичными.
2. Добавить сортировку `Останні / Потрібна дія / Оплата / Доставка`, сохранив
   `Останні` по умолчанию и server-authoritative semantics.
3. Deep-link сохраняет filter, search, page и client id через безопасные numeric
   ids; auth/backend остаются обязательными.
4. Секции context раскрываются по потребности, состояние хранится как UI
   preference; payment/order evidence всегда имеет видимый entry point.
5. Keyboard-only: roving tabindex для tablists/rows, Arrow/Home/End, Escape и
   возврат фокуса после drawer; один page `main` и labelled list/conversation/
   context regions.
6. Disabled controls получают короткую причину через `aria-describedby`; POST
   кнопки имеют bounded busy state, сохранённую ширину и recoverable error.
7. Ошибки live-потоков изолируются: stale/reconnect marker, retry, не ломая
   transcript; aria-live разделяет polite counters и assertive errors.
8. Единый reduced-motion policy и touch-target минимум 44 px; zoom 200% и
   контраст коммерческих tokens входят в CI/browser QA.

### Release 6 — Измерение и финальная модернизация

До новых крупных эффектов записать baseline и проверить:

- время от открытия вкладки до первого понятного решения;
- время от `Потрібна увага` до завершённого action;
- использование advanced filters и deep links;
- stale/overflow/reconnect без PII;
- visual snapshots 320/375/768/1440 с маскированием времени и счётчиков.

После этого можно включать только подтверждённые улучшения плотности, saved
presets, manager presence и UI telemetry. Каждое крупное изменение получает
feature flag с expiry date и rollback path. Ежеквартально удалять controls,
которыми никто не пользуется.

## Полный ledger по 100 рекомендациям

Ledger нужен, чтобы ни один пункт не исчез в процессе и чтобы «не делать» было
осознанным решением.

### Реализовать в этом цикле (55)

`2, 3, 4, 8, 12, 14, 15, 16, 17, 20, 22, 23, 25, 27, 30, 32, 33, 37, 38,
39, 42, 45, 47, 48, 50, 53, 54, 56, 57, 59, 61, 62, 63, 65, 66, 68, 70, 71,
72, 73, 74, 75, 76, 77, 79, 80, 83, 85, 86, 87, 89, 90, 96, 97, 98`.

Это live inbox, evidence/order UI, stats restructuring, actionable freshness,
keyboard/reduced-motion и release-quality safeguards. Они дают прямой прирост
понимания или предотвращают ошибочное действие.

### Реализовать после baseline-измерений (40)

`1, 5, 6, 7, 9, 10, 11, 19, 21, 24, 26, 28, 29, 31, 34, 35, 36, 41, 43,
44, 46, 49, 52, 55, 58, 60, 64, 67, 69, 78, 81, 84, 88, 91, 92, 93, 94, 95,
99, 100`.

Эти решения полезны, но могут добавить плотность, storage/telemetry или
поддерживаемую поверхность. Их включать только после проверки, что базовые
релизы не решают ту же проблему проще.

### Отложить до доказанной потребности (4)

`18` (density profiles), `40` (context density profiles), `51` (SSE), `82`
(virtualization). Polling и disclosure покрывают текущий масштаб; переходить к
этим решениям можно только после измерения нагрузки и реального использования.

### Отклонить (1)

`13` (global command palette): она скрывает действия, которые сейчас должны быть
видимыми, и не даёт достаточного выигрыша для этого операционного экрана.

Дополнительно отклонены, хотя их не было отдельными номерами: звуковые сигналы,
автопереключение на любого нового клиента, фальшивые countdown, decorative
particles/gradients, постоянные pulse-анимации, full-screen modal для каждого
факта и любые статусы доставки, выведенные только из TTN или текста.

## Definition of done для всего цикла

1. Каждый release имеет focused RED/GREEN tests, JavaScript syntax check,
   `manage.py check`, migration drift check и `git diff --check`.
2. Browser matrix: 320, 375, 768, 1440 px; проверяются overflow, focus,
   reduced-motion, open chat, filter state, drawer и stats empty states.
3. После каждого release: commit в feature, force-safe push, fast-forward local
   `main`, push `origin/main`, server `git pull --ff-only`, migrations/check,
   static/compress, Passenger restart, daemon ensure и SHA/heartbeat verification.
4. Никаких synthetic Meta/customer messages, ad test events или production test
   fixtures; коммерческие состояния проверяются локальными fixtures и
   serializer/API tests.
5. После финального release документируется фактический deployed SHA, остаточные
   риски и список пунктов, которые сознательно отложены/отклонены.

## Следующий шаг

После утверждения этого draft начать только с Release 1. Не смешивать live
reorder со статистикой или заказной lifecycle в одном commit/deploy.
