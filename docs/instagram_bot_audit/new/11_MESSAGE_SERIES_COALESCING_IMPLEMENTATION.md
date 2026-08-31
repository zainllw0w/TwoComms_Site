# 11 — Смысловая сборка серий сообщений и отмена устаревшего ответа

> **Статус на 2026-08-31:** implementation plan готов; код по этому документу
> **не реализован**. Канонический пункт общего roadmap — `Э2.2B` в
> `04_IMPLEMENTATION.md`.
>
> **Production baseline:** `main`/server SHA
> `40b9eb211e2efeee0c199d22a8427015fe897cf9`; MariaDB — источник истины для
> таймингов, блокировок и фактических диалогов. Локальная SQLite остаётся только
> быстрым структурным тестовым слоем.
>
> **Назначение документа:** дать следующему агенту исполнимый план, который
> устраняет преждевременный ответ на один фрагмент пользовательской мысли, не
> заставляя всех клиентов ждать десятки секунд и не создавая второй независимый
> debounce-механизм.
>
> **Ревизия 2026-08-31 (audit pass поверх исходного плана).** Проверены код,
> миграции и пересечения с остальными этапами `04`. Исходная архитектура
> подтверждена: раздельные часы, typed wait policy, revision + CAS, ACK без
> коммерческого смысла и отказ от LLM на горячем пути — правильные решения, их
> менять не нужно. Добавлено то, чего не хватало для исполнимости:
> §4.2 (границы владения с ЭА/Э0.4/Э3.6/Э4 и обязательный порядок относительно
> ЭА.21), правило пересчёта `hard_deadline` при смене класса внутри хода (§8.2),
> второй due-предикат по истёкшему continuation TTL (§11.5), канонический порядок
> блокировок `client → turn` (§12–13), трактовка нарушения unique-ключа ACK как
> штатного `already_acked` (§11.3), ограничение `mark_seen` (§8.4),
> переиспользование префикса промпта при bounded restart (§13.1) и
> revision-binding узлов воронки (§20.2). Уточнена формулировка дефекта
> `ig_turn_budget.py` (§4.1): расхождение реально, но правка — это связь с
> фактической policy, а не замена одного числа другим.

---

## 1. Решение в одном абзаце

Нельзя выбрать одно «идеальное число секунд». В production медиана следующего
сообщения после отдельного приветствия или фото близка к 19 секундам: ждать
столько перед **каждым** ответом медленно, а отвечать всем через фиксированные
6 секунд — часто рано. Поэтому существующий `IgCustomerTurn` расширяется до
durable revision-aware хода: входящие сообщения сначала объединяются дешёвым
детерминированным классификатором; самостоятельный текст получает короткое
sliding quiet-window, а приветствие, фото, чек и фраза «сейчас объясню» —
ограниченное ожидание или безопасный ACK без коммерческого смысла. Каждый запуск
Gemini работает по неизменяемому snapshot всего хода. Новое inbound до
`send_state="sending"` увеличивает `turn.revision`, аннулирует старый draft и
запрещает его отправку через атомарный compare-and-swap. После начала Meta Send
API сообщение уже нельзя безопасно «отозвать»: позднее продолжение становится
связанным corrective turn без blind retry и без повторного коммерческого
действия.

Это не «ещё один AI-агент перед AI-агентом». На горячем пути не нужен второй
LLM-вызов: признаки приветствия, незавершённой фразы, вложения, reply-to,
postback, opt-out, ожидания фото/чека и последнего вопроса бота вычисляются за
миллисекунды. Историческая манера клиента используется лишь как слабая,
ограниченная поправка к времени и никогда не становится постоянным режимом.

---

## 2. Scope и запреты

### 2.1. В scope

- объединение 2–N быстрых текстовых сообщений в один смысловой ход;
- фото → приветствие → объяснение, текст → фото, фото → фото;
- чек/скрин оплаты → пояснение о частичной оплате;
- отдельные приветствия и фразы ожидания;
- новое inbound во время quiet-window, Gemini, typing-паузы и pre-send;
- позднее inbound после начала Meta Send API;
- adaptive cadence без ручного списка «таких клиентов»;
- один bundle-level multimodal snapshot со всеми исходными message IDs;
- единый lineage `turn → revision → request → draft → receipt`;
- manager visibility, shadow evaluation, canary и rollback;
- производительность, квоты, токены, дедупликация и crash recovery.

### 2.2. Не в scope

- исправление самого `HTTP 400 INVALID_ARGUMENT`, обнаруженного во втором
  запросе production-кейса: это отдельный structured-output/provider defect;
- изменение бизнес-правил сертификатов, скидок, оплаты или заказа;
- попытка получить недокументированный статус online/typing клиента;
- blind polling Meta conversation перед каждым ответом;
- гарантированное удаление/отзыв уже отправленного Instagram-сообщения;
- автоматическое включение нативного reply-to обычного DM без подтверждённой
  capability текущего endpoint;
- новый daemon или отдельная очередь только ради debounce;
- удаление или физическое склеивание raw `InstagramBotMessage`.

### 2.3. Жёсткие запреты

1. Не ждать минуту перед обычным ответом.
2. Не отвечать generic sales-вопросом на `GREETING_ONLY`, если продолжение ещё
   вероятно.
3. Не считать `typing_on`, отправленный ботом, доказательством того, что печатает
   пользователь.
4. Не запускать LLM-классификатор только для выбора окна ожидания.
5. Не выполнять необратимые payment/order/commerce side effects на устаревшей
   revision.
6. Не повторять Meta send после неоднозначного timeout.
7. Не смешивать provider timestamp и local ingestion clock в одном дедлайне.
8. Не считать feature-флаг полноценным rollback, если уже начался внешний send.
9. Не использовать signed media URL как identity вложения.
10. Не прятать raw evidence после объединения сообщений.

---

## 3. Production evidence: кейс, который должен стать replay fixture

### 3.1. Фактическая последовательность

В документации сохраняется только необходимый минимум: production client `#336`
и строки сообщений, без IGSID, access token, provider MID и private media URL.

| Событие | Provider event time (UTC) | Local DB / execution time (UTC) | Что произошло |
|---|---:|---:|---|
| Фото сертификата, source `2811` | 15:57:42.294 | 15:57:45.251 | webhook lag ≈ 2.957 с |
| `Вітаю`, source `2812` | 15:57:44.460 | 15:57:46.382 | присоединено к turn `8` |
| deadline turn `8` | — | 15:57:48.294 | **6 с от provider time первого фото** |
| claim turn `8` | — | 15:57:49.794 | обрабатывается `2812`, фото `2811` поглощено |
| Gemini request | — | 15:57:52.229–15:57:54.601 | draft generic greeting готов |
| `Отримав сертифікат )`, source `2813` | 15:57:55.040 | 15:57:56.245 | отправлено клиентом до send, но локально пришло позже |
| `send_state="sending"` для `2812` | — | 15:57:55.233 | Meta boundary пересечён через ≈ 0.193 с после provider event |
| generic reply подтверждён | — | 15:57:57.106 | устаревший смысл уже нельзя безопасно отозвать |
| claim нового turn `9` | — | 15:58:01.834 | продолжение обрабатывается отдельно |
| второй Gemini | — | 15:58:03.662–15:58:04.517 | `HTTP 400 INVALID_ARGUMENT` |
| manager fallback подтверждён | — | 15:58:19.228 | отдельное следствие provider failure |

### 3.2. Что доказывает таймлайн

Это не один дефект «окно маловато»:

1. **Смешаны часы.** `window_deadline` строится от provider event time, а worker
   живёт по local wall clock. В первом сообщении почти три секунды шестисекундного
   окна исчезли ещё до записи в MariaDB.
2. **Окно фиксировано от первого фрагмента.** Greeting присоединился к turn, но
   не продлил quiet-period.
3. **После `OPEN → CLAIMED` turn закрыт для новых входящих.** Смысловое
   продолжение автоматически стало новым turn.
4. **Нет revision gate перед send.** Генерация и typing-пауза не знают, что
   появился более свежий inbound.
5. **Физическая отмена имеет предел.** Локальный webhook пришёл уже после
   `send_state="sending"`; никакая локальная проверка не может увидеть ещё не
   доставленное событие.
6. **Queue-level merge не равен model-level merge.** Worker выбрал текстовую
   строку `2812`; media recovery строится вокруг выбранной строки, поэтому фото
   из поглощённой `2811` не гарантированно становится изображением в Gemini.
7. **Второй fallback — отдельный failure class.** Coalescing не должен скрывать
   или переименовывать `invalid_payload`.

### 3.3. Production агрегаты для выбора стратегии

Это exploratory calibration, а не финальная product-метрика: классификация
greeting/media выполнена простыми правилами, а исторические сообщения ещё не
имели канонического semantic bundle.

| Срез | Выборка | Наблюдение |
|---|---:|---|
| Последовательные user→user пары, 180 дней | 381 | p50 gap = 10.256 с |
| Те же пары ≤ 6 с | 138 / 381 | 36.2% |
| Те же пары ≤ 20 с | 257 / 381 | 67.5% |
| Greeting → следующее user, 180 дней | 23 | p50 = 18.86 с |
| Media → следующее user, 180 дней | 38 | p50 = 19.0 с |
| Webhook ingress lag, 30 дней | 182 | p50 = 1.368 с; p95 = 4.977 с; p99 = 24.352 с |
| `IgCustomerTurn` после миграции `0173` | 14 | 12×1 сообщение; 2×2 сообщения — мало для настройки |
| Автоматически исполненные turns | 7 | все остались `CLAIMED` при терминальных source rows |

Следствия:

- увеличить глобальное окно до 19–20 секунд — плохой UX;
- оставить 6 секунд — систематический false split;
- sub-second debounce из внешних примеров не учитывает фактический webhook lag;
- нужен гибрид `short wait + stable ACK/continuation expectation + revision`;
- timing должен считаться по local ingestion clock, а пользовательская latency —
  отдельно по provider event time;
- до canary нужно исправить lifecycle `CLAIMED → PROCESSED` и собирать больше
  turn-level данных.

---

## 4. Что уже есть и должно быть переиспользовано

| Контракт | Текущий узел | Что сохраняем |
|---|---|---|
| Raw inbound | `InstagramBotMessage` | append-only evidence, `mid`, synthetic key, provider/local timestamps |
| Логический ход | `IgCustomerTurn` | один owner вместо второй очереди |
| Membership | `IgTurnMessage` | все source IDs и ordinal |
| Inbound dedupe | `message_dedupe_key()` | native MID → provider object ID → synthetic key |
| Claim | `_claim_exact_row()` + `claim_turn()` | conditional update и per-client ownership |
| Client lease | `automation_lease_token/until` | один worker на клиента |
| Permission | `reply_execution_boundary()` / `customer_send_boundary()` | pause/takeover/opt-out epoch |
| Delivery | `send_state`, provider receipts | `UNKNOWN` без blind retry |
| Reset boundary | `current_message_floor()` | не смешивать эпизоды |
| Gemini lineage | `GeminiRequest` / attempts | request ID, model, candidate graph |
| Recovery | `IgAiReplyRecoveryJob` | durable retry/receipt правила |
| Budget | `ig_turn_budget.py` | единый бюджет, а не новая независимая константа |
| Bot UX | `mark_seen`, `typing_on/off` | только outbound sender actions |

### 4.1. Prerequisite defects, которые нельзя «обойти» новым кодом

1. `mark_turn_processed()` не вызывается после обычного успешного/терминального
   исполнения. Production rows остаются `CLAIMED`.
2. `_turn_debounce_seconds()` в `ig_turn_budget.py` объявляет
   `MAX_TURN_WAIT = 20 с`, тогда как фактическое `window_deadline` всегда равно
   `TURN_DEBOUNCE = 6 с`: `min(now + 6 с, now + 20 с)` и отсутствие продления
   дедлайна при attach делают `MAX_TURN_WAIT` мёртвой константой.
   **Важно про направление правки.** Расхождение сейчас безопасно по эффекту
   (объявленный бюджет больше реального, watchdog менее чувствителен), поэтому
   нельзя просто «заменить 20 на 6» и через одну фазу вернуть назад. Требование
   формулируется как связь, а не как число: `turn_phases()` обязан выводить фазу
   ожидания из **фактической** wait policy — сегодня это `TURN_DEBOUNCE`, после
   Phase 3 это `max(silent hard cap)` по включённым классам, ограниченный
   глобальным потолком. Тест согласованности должен падать, когда объявленное
   значение перестаёт совпадать с максимумом, который реально может подождать
   scheduler.
3. `resolve_logical_turn_key()` всё ещё строит row-anchor вместо ID
   `IgCustomerTurn`.
4. `_build_history()` читает общую историю, но нет неизменяемого bundle snapshot.
5. `_recover_current_message_media(row)` ориентируется на одну выбранную строку,
   а не на все `IgTurnMessage`.
6. Commerce/classifier/follow-up writes могут начаться до финальной проверки
   актуальности revision.

Эти пункты — **Phase 0/1**, а не «когда-нибудь потом».

### 4.2. Границы владения с другими этапами `04`

Этот workstream пересекается с уже запланированными пунктами, и без явного
владельца получатся два конкурирующих механизма в одном send-path. Правило: **не
создавать второй экземпляр того, что уже имеет владельца.**

| Механизм | Владелец | Что делает Э2.2B |
|---|---|---|
| Идемпотентность Meta send и `UNKNOWN` без повторной отправки | **ЭА.21** | не создаёт вторую таблицу outbound-интентов; расширяет ключ ЭА.21 полем `revision` и `kind` |
| Единый notification/outbound outbox и атомарный лимит | **ЭА.16** | stable ACK проходит через тот же outbox и тот же лимит; ACK не получает обходной путь |
| Один технический текст / одно извинение на логический ход | **ЭА.6, ЭА.8** | stable ACK **считается** в этом бюджете; ACK + holding в одном ходе запрещены |
| Бюджет логического хода и отмена по дедлайну | **ЭА.13** (и Э2.10) | wait policy отдаёт фазу ожидания в бюджет; собственного watchdog-окна не вводит |
| Единый объект решения об исходящем сообщении | **Э0.4** | `IgTurnReplyCandidate` — durable persistence решения Э0.4, а не второй тип решения |
| Provenance ответа (prompt hash, revision IDs, request_id) | **Э3.6** | `revision` и `snapshot digest` становятся полями provenance, отдельного журнала нет |
| Голодание очереди и справедливость | **Э2.8** | fairness остаётся у Э2.8; scheduler Э2.2B только добавляет due-предикат |
| Реестр узлов воронки | **Э4.1–Э4.2** | когда Э4 разблокируется, создание узла обязано быть revision-bound: superseded revision не оставляет открытый узел |

#### Обязательный порядок относительно ЭА

Э2.2B **нельзя** начинать с Phase 5 (atomic send gate) до того, как закрыт
**ЭА.21**. Причина механическая, а не организационная: ЭА.21 определяет
идемпотентный outbound-интент и семантику `UNKNOWN` для того же перехода
`→ SENDING`, в который Э2.2B встраивает revision-CAS. Если сделать наоборот,
финальный CAS придётся переписывать второй раз, и в промежутке будут два
источника истины о том, отправлено ли сообщение.

Практический вывод по последовательности:

1. **Сейчас:** Phase 0/1 Э2.2B (prerequisite-ремонты) — это исправление уже
   задеплоенного кода, оно не зависит ни от чего и снимает живой дефект
   телеметрии (`record_completed_customer_turn()` не вызывается ни для одного
   реального хода, потому что `mark_turn_processed()` стоит только на
   деградационной ветке `_claim_next()`).
2. **Затем:** ЭА.13, ЭА.21 (и ЭА.9/ЭА.10, потому что они дешевле и уже
   разблокированы закрытым Э3.7).
3. **Затем:** Phase 2–4 Э2.2B (schema, shadow policy, bundle snapshot) — они не
   меняют send-path и могут идти параллельно остальному ЭА.
4. **Только после ЭА.21:** Phase 5–7 (supersession, atomic send gate, ACK,
   canary).

#### Взаимодействие с активным инцидентом провайдера

Отдельный сценарий, которого нет в исходной постановке: активный
`IgProviderIncident` и semantic turn одновременно хотят отправить клиенту
единственное сообщение. Правило:

- при открытом инциденте semantic turn продолжает **собирать** ход и повышать
  revision, но **не запускает** substantive generation вне бюджета ЭА.13;
- клиентское сообщение при открытом инциденте принадлежит эпизоду деградации
  (ЭА.3): holding — единственный customer-visible текст;
- stable ACK при открытом инциденте **не отправляется**, иначе клиент получит
  и `фото отримано`, и holding — то есть ровно тот двойной технический текст,
  который снимает ЭА.8;
- после закрытия инцидента recovery (ЭА.7) отвечает по **последней** revision
  хода, а не по той, что была на момент сбоя.

---

## 5. Ограничения Meta/Instagram, которые определяют архитектуру

### 5.1. Что подтверждено

- Instagram Messaging webhook даёт независимые `messages` events с `mid`,
  sender/recipient и timestamp; raw events нужно сохранять и дедуплицировать.
- `messaging_seen` говорит, что клиент прочитал сообщение бизнеса. Это не online
  status и не typing.
- `typing_on`, `typing_off`, `mark_seen` — **sender actions бизнеса**, а не
  входящий сигнал о клиенте.
- обычный Send API возвращает `recipient_id` и `message_id`.
- официальный body обычного text DM содержит recipient + text; универсальное
  поле reply-to произвольного DM в подтверждённом контракте не найдено.
- private reply по `comment_id` и `reply_to.story` — другие механизмы; их нельзя
  выдавать за reply-to обычного Direct message.

### 5.2. Что считать недоступным до отдельного доказательства

- «пользователь сейчас печатает»;
- online/offline или active presence собеседника;
- строгий HTTP arrival order соседних webhook requests;
- автоматическую идемпотентность Meta Send API по одинаковому body;
- надёжный отзыв сообщения после начала send;
- нативный reply-to обычного DM.

Следовательно, закрытый профиль не создаёт отдельную ветку: этих сигналов нет и
для открытого профиля. Correctness опирается на durable events, timestamps,
revision и CAS, а не на presence.

Если Meta позже официально добавит inbound typing/presence, сигнал можно
использовать только как advisory modifier внутри уже существующего hard cap. Он
не заменяет revision/CAS и не превращается в обязательную зависимость.

---

## 6. Термины

| Термин | Определение |
|---|---|
| Raw message | одна неизменяемая `InstagramBotMessage` от webhook/poll |
| Technical turn | текущий `IgCustomerTurn`, который группирует raw rows |
| Semantic bundle | версия turn, содержащая все фрагменты одной пользовательской мысли |
| Quiet window | локальный период без новых inbound перед snapshot/generation |
| Hard deadline | верхняя граница silent collection от первого local ingress |
| Continuation expectation | состояние после safe ACK/hold, когда поздний фрагмент ещё связан с тем же смыслом, но worker не блокируется |
| Revision | монотонный номер состава bundle; растёт только от нового уникального inbound/control event |
| Input snapshot | неизменяемая ссылка на source IDs/media IDs/state fingerprint для одной revision |
| Reply candidate | draft, сгенерированный для точной revision |
| Stable ACK | ответ, который остаётся истинным при любом разумном продолжении: greeting/receipt only, без продукта, цены, оплаты и обещаний |
| Substantive reply | ответ по сути, который имеет право уйти только для актуальной revision |
| Superseded | draft/generation, потерявший право на отправку из-за новой revision или manager takeover |
| Provider boundary | момент записи `send_state="sending"` непосредственно перед Meta I/O |
| Corrective turn | связанное продолжение после provider boundary, когда старое сообщение уже нельзя отозвать |

---

## 7. Целевой pipeline

```text
Meta webhook
  → verify signature
  → persist raw event + provider/local timestamps
  → dedupe identity
  → attach to canonical IgCustomerTurn
  → increment revision / cancel stale candidate
  → HTTP 200

Indexed due-turn scheduler (existing daemon, no per-client threads)
  → deterministic wait class
  → quiet/hard deadline decision
  → immutable bundle snapshot (all text + all media references)
  → pure/read-only routing and draft planning
  → Gemini at most once for stable revision (bounded restart if superseded)
  → persist reply candidate
  → revision + permission + lease + episode CAS
  → prepare revision-bound side effects
  → final CAS + unique outbound intent
  → send_state="sending"
  → Meta Send API outside transaction
  → receipt / UNKNOWN
  → commit delivered side effects
  → PROCESSED
```

### 7.1. Почему не нужен новый daemon

- ingress уже durable и отделён от generation;
- daemon просыпается раз в 1.5 секунды, что задаёт естественную гранулярность;
- due query должен читать индекс `(state, collect_until)`;
- один новый daemon увеличит DB connections, ownership и restart surface;
- отдельный LLM-анализатор добавит quota/latency failure до настоящего ответа.

Если позже 1.5-секундный scheduler станет доказанным bottleneck, это отдельная
оптимизация с замером. В этом workstream запрещён busy-loop 100–250 мс.

---

## 8. Три времени вместо одной константы

### 8.1. Раздельные часы

| Часы | Источник | Использование |
|---|---|---|
| `provider_event_at` | Meta timestamp | chronology и user-perceived latency |
| `ingested_at` | локальный `created_at` | quiet/hard scheduling; только это система реально наблюдает |
| monotonic execution | процесс worker | provider/generation/typing duration |

`collect_until` считается от **последнего local ingress**, `hard_deadline` — от
**первого local ingress**. Provider timestamp не сокращает локальное окно, но
сохраняется в snapshot и метриках. При out-of-order arrival порядок presentation
строится по `(provider_event_at, ingested_at, id)`, а arrival ordinal остаётся
append-only evidence.

### 8.2. Provisional timing policy v0

Эти числа — старт для shadow/canary, а не вечная истина. Фактическое выполнение
квантуется текущим daemon tick до +1.5 с. Менять одновременно несколько строк
таблицы запрещено.

**Правило пересчёта `hard_deadline` при смене класса внутри хода.** Класс хода
определяется не первым сообщением, а всем составом bundle: `Вітаю`
(`GREETING_ONLY`, cap 4 с) плюс пришедшее следом фото (`MEDIA_UNSOLICITED`,
cap 8 с) — это один ход с потолком 8 с, а не 4 с. Наивная реализация
`hard_deadline = first_ingest + cap(первого класса)` молча урезала бы окно
именно в том сценарии, из-за которого написан этот документ. Поэтому:

- `effective_wait_class` = класс с **наибольшим** silent hard cap среди частей
  текущей revision, кроме `IMMEDIATE_CONTROL`;
- `hard_deadline = first_ingested_at + cap(effective_wait_class)`, но не более
  `first_ingested_at + GLOBAL_HARD_CAP` (20 с);
- `hard_deadline` **монотонно не убывает** в пределах одного хода: класс может
  только повысить потолок, никогда не понизить его задним числом;
- `IMMEDIATE_CONTROL` — единственное исключение: любой control/bypass part
  немедленно ставит `collect_until = hard_deadline = now` и снимает ожидание для
  всего хода;
- `collect_until = min(last_ingested_at + sliding_quiet(class текущей части),
  hard_deadline)`; при новом ходе `hard_deadline` вычисляется **до** первого
  `collect_until`, иначе `min()` получит `NULL`.

| Wait class | Пример | Sliding quiet | Silent hard cap | После cap | Continuation TTL |
|---|---|---:|---:|---|---:|
| `IMMEDIATE_CONTROL` | opt-out, manager request, postback/quick reply | 0 | 0 | deterministic action | 0 |
| `COMPLETE_TEXT` | полный вопрос/заказ одним сообщением | 0.75 с | 3 с | substantive path | 0 |
| `SHORT_FRAGMENT` | `чорне`, `розмір L`, незаконченная фраза | 1.5 с | 6 с | combine или clarify | 15 с |
| `YES_NO_CORRECTION` | `да`, `нет`, `не это` | 0.5 с | 3 с | resolve latest explicit expectation | 0 |
| `GREETING_ONLY` | `Вітаю`, `Здравствуйте` | 2.5 с | 4 с | stable greeting ACK, **без** generic sales CTA | 60 с |
| `HOLD_PHRASE` | `зараз поясню`, `одну секунду` | 0 | 0 | no text reply; wait state only | 90 с |
| `MEDIA_EXPECTED` | фото после просьбы прислать пример | 2 с | 6 с | treat media as answer | 20 с |
| `MEDIA_UNSOLICITED` | фото/скрин без объяснения | 3 с | 8 с | stable receipt ACK или один clarify | 60 с |
| `MEDIA_WITH_OPENER` | фото + greeting, но без сути | 3 с | 6 с | stable `greeting + received` ACK | 60 с |
| `MULTI_MEDIA` | несколько вариантов | 2.5 с после каждого | 10 с от первого | one media-set analysis | 30 с |
| `PAYMENT_EVIDENCE` | чек/скрин оплаты | 4 с | 8 с | safe verification ACK; no payment conclusion | 90 с |
| `URGENT_COMPLETE` | самостоятельная жалоба/ошибка | 0.5 с | 2 с | substantive/support path | 0 |

### 8.3. Почему greeting/media не ждут медианные 19 секунд молча

После 2.5–8 секунд система может сделать **stable ACK**, но не закрывает
continuation expectation. ACK не вызывает Gemini и не задаёт вопрос «что вам
предложить?». Если смысл приходит на 19-й секунде, выполняется ровно один
substantive model execution по полному bundle. Так пользователь быстро видит,
что сообщение принято, а бот не делает преждевременный коммерческий вывод.

### 8.4. `mark_seen` и typing

- `mark_seen` можно отправить после durable ingress: это не содержательный ответ.
  Но он ограничен: максимум один `mark_seen` на `(turn_id, revision-batch)`, он
  проходит через тот же outbound outbox (ЭА.16) и учитывается в rate-бюджете
  Meta. Отправлять `mark_seen` на каждый fragment длинного burst-а запрещено —
  это превращает экономию provider calls в её противоположность.
- `typing_on` включается только когда реально началась подготовка ответа, а не на
  всё continuation TTL.
- ACK не обязан имитировать долгий typing.
- `typing_off` обязателен при supersession, permission change, failure и success.
- отсутствие inbound typing не влияет ни на одну ветку алгоритма.

### 8.5. Provisional UX SLO

Пока нет чистого matched baseline, используются одновременно абсолютные и
относительные guardrails:

- ordinary `COMPLETE_TEXT`: local ingress → generation eligibility p50 ≤ 2.5 с,
  p95 ≤ 4.5 с с учётом daemon tick;
- greeting stable ACK: local ingress → ACK receipt p95 ≤ 8 с;
- coalescing не добавляет после **последнего** fragment больше quiet-window
  текущего класса + одного scheduler tick;
- substantive final-fragment → receipt p95 не ухудшается более чем на 10% против
  matched control без provider incident;
- p50 ordinary reply должен стать быстрее legacy fixed 6-second path;
- ни один class не создаёт 60–90 секунд **молчаливого ожидания**: длинный TTL —
  только неблокирующая связь после ACK/no-reply hold phrase;
- payment/order safety имеет приоритет над latency SLO.

После 7–14 дней shadow/control эти числа заменяются baseline-derived gates с
указанием sample size и policy version.

---

## 9. Детерминированный wait-classifier

### 9.1. Сильные признаки в порядке приоритета

1. **Control/bypass:** quick-reply payload, postback, opt-out, manager/support.
2. **Permission/ownership:** pause, takeover, hidden/erasure, response window.
3. **Explicit linkage:** `reply_to_provider_message_id`, активный card/proposal
   revision, последнее обязательство/вопрос бота.
4. **Media context:** attachment type, provider object ID, число media, был ли
   предыдущий запрос «пришлите фото/чек/пример».
5. **Financial/commerce risk:** чек, сумма, invoice/order/certificate markers.
6. **Text form:** greeting-only, hold phrase, короткий fragment, correction,
   законченный вопрос/утверждение, conjunction/trailing punctuation.
7. **Current episode/floor:** никогда не объединять через reset, opt-out, manager
   substantive message или новый verified order event.
8. **Cadence profile:** только слабая поправка после текущих признаков.

### 9.2. Что classifier не решает

- не определяет stage/intent/payment truth;
- не читает изображение через vision;
- не создаёт заказ, proposal, invoice или follow-up;
- не решает, прав клиент или нет;
- не запоминает человека как «всегда медленного»;
- не пишет customer-facing текст, кроме выбора approved stable ACK template.

### 9.3. Failure behavior

Любая ошибка classifier-а даёт `COMPLETE_TEXT` для самостоятельного текста или
`MEDIA_UNSOLICITED` для вложения. Ingress не блокируется. Неизвестный класс и
причина записываются в PII-safe telemetry.

---

## 10. State machine

### 10.1. Состояния

| State | Можно присоединить inbound | Можно вызвать Gemini | Можно начать Meta send |
|---|---|---|---|
| `COLLECTING` | да | нет | нет |
| `ACKED_WAITING` | да, до TTL/semantic boundary | нет, пока нет сути | stable ACK имеет отдельный candidate send-state |
| `READY` | да; revision снова делает `COLLECTING` | после snapshot | нет |
| `GENERATING` | да; повышает revision и supersede candidate | один active candidate | нет |
| `DRAFT_READY` | да; draft superseded | нет | только после CAS |
| `SEND_RESERVED` | только control event; обычный inbound пытается сорвать CAS | нет | ещё нет provider I/O |
| `SENDING` | нет; новое inbound идёт в corrective turn | нет | substantive/corrective Meta send уже начат |
| `SENT` | нет | нет | substantive/corrective reply завершён |
| `PROCESSED` | нет | нет | завершён |
| `SUPERSEDED` | нет | нет | запрещён |
| `AMBIGUOUS` | нет | нет | retry запрещён до reconciliation |
| `FAILED` | нет | по typed recovery policy | по typed recovery policy |

### 10.2. Главный инвариант

```text
Meta send разрешён ⇔
  turn.state == SEND_RESERVED
  AND candidate.turn_revision == turn.revision
  AND candidate.snapshot_revision == turn.revision
  AND permission_epoch неизменен
  AND client lease принадлежит worker
  AND episode/floor неизменны
  AND unique outbound intent ещё не пересёк provider boundary
```

Проверка выполняется одной транзакционной conditional update непосредственно при
переходе `SEND_RESERVED → SENDING`. Проверка «за несколько строк до send» не
закрывает TOCTOU.

### 10.3. ACK не закрывает ход

Stable ACK имеет отдельный `outbound_kind="ack"`, собственный candidate
send-state и idempotency key. ACK-вызов **не переводит весь turn в substantive
`SENDING`**: continuation, пришедшее во время Meta I/O ACK, всё равно
присоединяется и повышает revision. После receipt turn становится
`ACKED_WAITING`, а не `SENT`. Только substantive reply или истечение
continuation TTL закрывает смысловой ход.

---

## 11. Рекомендуемая схема данных

### 11.1. Расширение `IgCustomerTurn`

Добавить expand-only migration после актуального migration leaf; номер не
фиксировать заранее, потому что параллельные workstreams могут добавить миграцию.

```text
lifecycle_state
revision                   unsigned; 0 before first membership, then 1..
first_ingested_at
last_ingested_at
last_provider_event_at
collect_until
hard_deadline
continuation_expected_until
wait_class
wait_policy_version
claimed_revision
active_candidate_revision
substantive_sent_revision
ack_sent_at
ack_message_id
lease_token / lease_until   либо явное переиспользование client lease
terminal_reason
superseded_reason
```

Существующий `primary_source_message` остаётся для legacy OneToOne compatibility.
Новые consumers используют `turn_id + revision`; новые side effects нельзя
привязывать только к primary/latest row.

### 11.2. Новый `IgTurnInputSnapshot`

```text
turn FK
revision
ordered_message_ids JSON
message_ids_digest
attachment_object_ids JSON
attachment_state_digest
provider_time_min/max
local_time_min/max
message_floor
episode_id
settings_permission_epoch
client_permission_epoch
client_state_fingerprint
created_at
invalidated_at / invalidated_reason
UNIQUE(turn, revision)
```

Полный customer text и private signed URLs **не дублировать** в snapshot: raw
rows уже являются evidence. Snapshot хранит IDs и digest; ordered parts строятся
из append-only rows. Owned media references должны быть стабильными и
retention-aware.

### 11.3. Новый `IgTurnReplyCandidate`

```text
turn FK
revision
snapshot FK
kind                 ack | substantive | corrective | deterministic
status               prepared | generating | ready | superseded |
                     send_reserved | sending | sent | ambiguous | failed
request_id
draft_digest
routing_decision_id / policy version
superseded_by_revision
superseded_reason
reply_message FK nullable
provider_message_ids JSON
idempotency_key UNIQUE
created/started/ready/send/completed timestamps
UNIQUE(turn, revision, kind)
```

Сохранять raw draft до send только там, где это уже требуется recovery-контрактом;
иначе достаточно digest + final persisted reply. Это уменьшает дублирование PII.

`idempotency_key` строится детерминированно: ACK —
`turn:{id}:ack:{ack_policy_version}` (не зависит от последующих revisions),
substantive/corrective — `turn:{id}:revision:{n}:{kind}`. Поэтому продолжение
после ACK не может породить второй ACK, а retry одной substantive revision не
создаёт второй outbound intent.

Отсюда следует конкретное требование к коду, которое легко упустить: ACK-строка
создаётся с `revision` момента ACK, но уникальность ей даёт **не**
`UNIQUE(turn, revision, kind)`, а `idempotency_key`. Значит вторая попытка ACK на
более поздней revision получит нарушение unique-ограничения. Это **штатный
исход** `already_acked`, а не ошибка: он ловится и превращается в «ACK уже
отправлен, продолжать сбор», без исключения в лог и без второй отправки. То же
правило для `(turn, revision, kind)` substantive: `IntegrityError` означает
`intent_already_claimed`, и worker обязан прочитать существующую строку, а не
создавать новую.

### 11.4. `IgClientCadenceProfile` — optional read model

```text
client OneToOne
eligible_turns
burst_turns
ewma_gap_ms
p90_bucket
greeting_continuation_count
media_continuation_count
single_message_count
last_observed_at
profile_version
```

Профиль обновляется асинхронно после terminal turn, не на webhook critical path.
Можно начать без новой таблицы: shadow-политику считать агрегатным запросом, а
materialize только после доказанной пользы.

### 11.5. Индексы и ограничения

- `(lifecycle_state, collect_until)` для due scheduler;
- `(lifecycle_state, continuation_expected_until)` для закрытия истёкших
  `ACKED_WAITING` и `HOLD_PHRASE`: без второго due-предиката ход после ACK
  закрывать нечем, и `continuation_expected_until` останется декларацией —
  scheduler обязан иметь **два** источника due-работы, `collect_until` и
  истёкший continuation TTL (последний ведёт к терминальному
  `PROCESSED/no_substantive_needed`, а не к генерации);
- `(client_id, lifecycle_state, -id)` для active turn;
- unique membership message→turn сохраняется;
- unique `(turn, revision)` snapshot;
- unique `(turn, revision, kind)` outbound intent;
- `send_revision <= revision` DB/check constraint там, где MariaDB поддерживает
  и реально применяет его;
- никакого partial unique, который MariaDB не гарантирует; использовать nullable
  active key по существующему recovery-паттерну.

---

## 12. Ingress transaction

```python
def attach_inbound(raw_message):
    persist_or_get_deduped_raw_message(raw_message)

    with transaction.atomic():
        # Канонический порядок блокировок: client → turn. Он обязателен и для
        # worker-а тоже (см. §13): ingress берёт client, потом turn, а worker
        # берёт turn — при обратном порядке в одном из путей MariaDB даст
        # взаимную блокировку под burst-ом.
        client = lock_client(raw_message.client_id)
        apply_permission_control_first(client, raw_message)

        turn = select_attachable_turn(client, raw_message)  # SELECT ... FOR UPDATE
        if not turn:
            turn = create_turn(
                first_ingested_at=raw_message.created_at,
                revision=0,
                # hard_deadline вычисляется здесь, ДО первого collect_until.
                hard_deadline=raw_message.created_at + capped_hard_cap(
                    classify_wait_policy(None, raw_message)
                ),
            )

        if message_identity_already_present(turn, raw_message):
            return existing_membership  # revision НЕ растёт

        append_membership(turn, raw_message)
        turn.revision += 1
        turn.last_ingested_at = raw_message.created_at
        turn.last_provider_event_at = max_event_time(...)

        wait = classify_wait_policy(turn, raw_message)
        if wait.is_immediate_control:
            turn.collect_until = raw_message.created_at
            turn.hard_deadline = raw_message.created_at
        else:
            # Потолок может только вырасти (см. §8.2), и не выше глобального.
            turn.hard_deadline = min(
                max(turn.hard_deadline, turn.first_ingested_at + wait.hard_cap),
                turn.first_ingested_at + GLOBAL_HARD_CAP,
            )
            turn.collect_until = min(
                raw_message.created_at + wait.sliding_quiet,
                turn.hard_deadline,
            )
        turn.wait_class = wait.name
        turn.effective_wait_class = max_cap_class(turn, wait)

        if turn.state in {GENERATING, DRAFT_READY, SEND_RESERVED}:
            supersede_candidate_if_provider_boundary_not_crossed(turn)
            turn.state = COLLECTING

        save_with_revision_increment(turn)
```

### 12.1. Attachability rules

Присоединять к текущему turn можно, если одновременно:

- тот же client/account;
- сообщение после `current_message_floor()`;
- тот же commercial/service episode либо безопасная нейтральная граница;
- нет substantive manager/model reply после turn start, кроме stable ACK;
- нет provider boundary для substantive candidate;
- continuation TTL не истёк;
- нет конфликтующего authoritative order/payment identity;
- raw message уникален.

При сомнении financial/order branch создаёт новый связанный turn и один
clarification, а не смешивает разные сделки.

---

## 13. Worker и CAS-протокол

Порядок блокировок в worker-е тот же, что в ingress: **client → turn**. Если
worker уже держит client lease как строку `IgClient`, повторный `lock_turn()`
безопасен; брать `lock_turn()` до client-строки запрещено.

```python
turn = claim_due_turn_with_lease()
restart_count = 0

while restart_count <= 1:
    snapshot = build_snapshot(turn.id, turn.revision)
    candidate = reserve_candidate(turn.id, snapshot.revision)

    draft = generate_or_deterministic(snapshot)

    with transaction.atomic():
        locked = lock_turn(turn.id)
        if locked.revision != snapshot.revision:
            mark_candidate_superseded(candidate, locked.revision)
            if locked.provider_boundary_crossed:
                create_linked_corrective_turn()
                return
            restart_count += 1
            continue
        persist_candidate_ready(candidate, draft)

    prepare_revision_bound_side_effects_without_provider_io(candidate)

    with transaction.atomic():
        locked = lock_turn(turn.id)
        assert_permission_lease_episode_floor(locked, snapshot)
        updated = conditional_update(
            id=turn.id,
            revision=snapshot.revision,
            state=DRAFT_READY,
            set_state=SEND_RESERVED,
        )
        if updated != 1:
            supersede_and_restart_or_stop()

    stop_typing_advisory()

    with transaction.atomic():
        # Последний CAS непосредственно перед внешним I/O.
        updated = conditional_update(
            id=turn.id,
            revision=snapshot.revision,
            state=SEND_RESERVED,
            set_state=SENDING,
            send_revision=snapshot.revision,
        )
        claim_unique_outbound_intent(turn.id, snapshot.revision, candidate.kind)
        if updated != 1:
            cancel_prepared_side_effects()
            return

    receipt = meta_send_outside_transaction(draft)
    persist_receipt_or_ambiguous(receipt)
    finalize_delivered_side_effects()
    mark_turn_processed()
    return

pause_until_hard_deadline_and_generate_latest_once()
```

### 13.1. Bounded regeneration

- одновременно максимум одна generation на клиента;
- максимум один automatic restart после supersession;
- при втором новом inbound worker не запускает третью модель немедленно, а ждёт
  latest quiet/hard deadline и генерирует один раз по последней revision;
- физическая cancellation provider request — оптимизация стоимости, не safety;
- stale result всегда сохраняет attempt telemetry, но никогда не получает право
  send.

**Дешёвая оптимизация restart-а, которой нет в исходной постановке.** Между
revision `n` и `n+1` меняется только хвост bundle: system instruction, память,
каталожные факты и prior history идентичны. Значит restart не обязан платить
полную цену prompt-а — устойчивый префикс (`system_instruction` + prior history +
профиль) выносится в стабильный блок и переиспользуется механизмом кэширования
контекста Gemini, а изменяемым остаётся только `[CURRENT CUSTOMER TURN]`. Это
снимает главное возражение против bounded restart («второй вызов дорог») и
делает `generation_superseded_total` дешёвой метрикой вместо болезненной. Условие:
порядок блоков промпта фиксируется по policy version, иначе префикс перестанет
совпадать и кэш не даст выигрыша. Отдельная задача: подтвердить, что текущий
routing (`09`) не пересобирает префикс при смене ключа/проекта — при смене
проекта кэш префикса теряется, и это нормально, но должно быть видно в метрике.

---

## 14. Единый bundle snapshot для Gemini

### 14.1. Prompt shape

Предыдущая история заканчивается перед текущим semantic bundle. Текущий bundle
передаётся один раз, сохраняя границы:

```text
[CURRENT CUSTOMER TURN, revision=3]
part 1: image attachment #A, source_message_id=2811
part 2: text "Вітаю", source_message_id=2812
part 3: text "Отримав сертифікат )", source_message_id=2813
Instruction: interpret all parts as one ordered customer turn. Do not answer
each part separately. Do not infer payment/certificate validity from image alone.
```

В production prompt запрещено раскрывать DB IDs клиенту; IDs нужны внутреннему
structured envelope и lineage.

### 14.2. Media

- собрать owned media всех `IgTurnMessage`, а не только latest row;
- сохранять порядок и source binding;
- одинаковое provider object ID не добавлять повторно;
- разные фотографии не схлопывать по похожему URL;
- partial media capture не удаляет текстовые parts;
- если обязательное изображение недоступно, safe fallback/manager branch остаётся
  отдельным typed outcome;
- один bundle вызывает максимум один vision-capable generation для стабильной
  revision.

### 14.3. History

- не дублировать текущие user fragments одновременно в prior history и current
  bundle;
- manager text остаётся operational note, а не model speech;
- reset floor, opt-out, hidden/erasure и episode boundary применяются до snapshot;
- позднее manager message инвалидирует snapshot.

---

## 15. Новое сообщение на каждой фазе

| Когда пришло | Действие |
|---|---|
| Quiet collection | attach, revision++, sliding deadline |
| Snapshot ещё не создан | attach, snapshot строится один раз позже |
| Gemini ещё не вызван | attach, старый reservation отменить |
| Gemini выполняется | revision++, candidate superseded; best-effort cancel; bounded restart |
| Draft готов / typing wait | revision++, draft запрещён; пересобрать |
| `SEND_RESERVED`, но `SENDING` ещё нет | ingress и send соревнуются через один DB CAS; выигрывает только одна revision |
| substantive `SENDING` | не отзывать; создать linked corrective turn |
| substantive `SENT` | новый/corrective turn; предыдущий receipt неизменен |
| `UNKNOWN` | не resend; reconciliation + новый inbound обрабатывается без повторения старого intent |

Если в этот момент `SENDING` относится только к extension-stable ACK, inbound
остаётся в том же semantic turn: ACK не является границей мысли клиента.

### 15.1. Material vs non-material inbound

Для safety **любое уникальное user inbound до send повышает revision**. Решение
«это всего лишь спасибо, draft не меняется» допускается только после того, как
candidate потерял право send и deterministic reducer доказал, что отдельного
substantive ответа не нужно. LLM не имеет права сам объявить свой draft
неизменившимся и обойти revision.

### 15.2. После provider boundary

Correction не повторяет весь предыдущий ответ. Она должна:

- явно учитывать новое уточнение;
- не извиняться автоматически, если прежний ответ был корректен на свой момент;
- исправить только изменившийся смысл;
- не создавать второй invoice/proposal/order;
- ссылаться на прежний turn/receipt в audit lineage;
- при финансовом конфликте передать менеджеру.

---

## 16. Stable ACK policy

### 16.1. Разрешённые свойства

Stable ACK может только:

- поздороваться;
- подтвердить получение текста/фото/чека;
- сказать, что сообщение рассматривается;
- нейтрально попросить продолжить, если пользователь сам обозначил продолжение.

ACK не может:

- предлагать товар;
- называть цену/наличие/скидку;
- подтверждать сертификат или оплату;
- обещать manager action, которого нет;
- менять funnel/stage;
- создавать follow-up, order, proposal или invoice;
- использовать Gemini.

### 16.2. Approved intents, не жёсткие тексты

Тексты локализуются через существующий template слой. В плане фиксируется смысл:

- greeting ACK: `приветствие + я здесь`, без «что вам предложить?»;
- media ACK: `фото получено`, без догадки, что изображено;
- payment evidence ACK: `подтверждение получения на проверку`, без `оплачено`;
- hold phrase: по умолчанию **нет текстового ACK**, чтобы не перебивать клиента.

### 16.3. Idempotency

Один ACK на `(turn_id, ack_policy_version)`. Новые fragments не дают второй ACK.
Receipt/UNKNOWN подчиняется тем же правилам Meta delivery, что и любой outbound.

---

## 17. Reply-to конкретного сообщения

### 17.1. Решение по текущему контракту

По умолчанию bundle получает **одно общее сообщение**, потому что ответ относится
ко всему набору. Нативный reply-to обычного DM остаётся выключенным.

### 17.2. Addressing modes

1. `TURN_GENERAL` — default: цельный ответ на весь bundle.
2. `EXPLICIT_REFERENT` — человеческая формулировка `По фото…`, `Щодо
   сертифіката…`, когда нужно снять неоднозначность.
3. `NATIVE_REPLY` — только после capability probe текущего Instagram Login
   endpoint, schema test, receipt test и отдельного флага default-off.

Inbound `reply_to_provider_message_id` уже полезен, чтобы понять, на какой вопрос
или карточку отвечает **клиент**. Это не доказательство, что бот может отправить
такой же reply-to.

### 17.3. Capability gate

- официальная документация/актуальная версия подтверждает поле;
- staging/live test с собственным аккаунтом возвращает provider MID;
- unsupported/permission/schema error даёт обычный text fallback;
- никакого автоматического retry с неизвестным body;
- feature flag `IG_DM_NATIVE_REPLY_ENABLED=false` по умолчанию.

---

## 18. Сценарные подалгоритмы

### 18.1. Greeting → смысл

```text
"Вітаю"
  → short silent window
  → если смысл пришёл: один substantive execution
  → если не пришёл: один stable greeting ACK, state=ACKED_WAITING
  → смысл в TTL: attach + один substantive execution
  → TTL истёк: close no-substantive-needed
```

Запрещён ранний generic CTA, потому что он конкурирует со следующим сообщением
клиента и создаёт впечатление, что бот не прочитал продолжение.

### 18.2. Фото → описание

- если бот сам просил фото, media может быть завершённым ответом;
- unsolicited media получает longer quiet + safe ACK/clarify;
- текст в TTL присоединяется к media bundle;
- все изображения передаются одним ordered media-set;
- новое фото в окне — ещё один вариант, а не новый ответ;
- отсутствие текста не позволяет выдумывать цель изображения.

### 18.3. Чек → `остальные 200 завтра`

- user-uploaded receipt — evidence, не payment truth;
- ждать bounded continuation;
- одна stable verification ACK допустима;
- сумма чека, сумма заказа и план клиента — разные typed facts;
- конфликт/частичная оплата не создаёт автоматически `paid`, новый invoice или
  order;
- authoritative provider payment webhook обрабатывается отдельно и немедленно;
- перед любым действием перечитать `IgPaymentProjection`/order truth;
- после позднего пояснения повторно валидировать permission, episode и сумму.

### 18.4. `Сейчас объясню` / `одну секунду`

- no-model/no-substantive reply;
- continuation expectation до 90 с без занятого worker/DB lock;
- `mark_seen` допустим;
- если продолжения нет, никаких автоматических напоминаний;
- новый смысл после TTL — новый turn, но prior phrase остаётся history evidence.

### 18.5. `Да` / `нет`

- сначала `reply_to_provider_message_id`, card revision, commitment ledger и
  последнее однозначное предложение;
- при одном актуальном вопросе — immediate deterministic binding;
- при двух актуальных вопросах — один clarify, не угадывание;
- yes/no не присоединяется к unrelated media/payment bundle только по времени.

### 18.6. Два независимых intent в одном burst

- сохранить границы raw parts;
- один ответ может кратко покрыть оба, если нет конфликтующих действий;
- два order/payment identities разрывают bundle или требуют clarify;
- irreversible action только после явного выбора;
- не создавать две параллельные model sends.

### 18.7. Очень длинный burst

- raw rows сохраняются все;
- configurable cap на prompt parts/media/bytes, согласованный с существующим
  token/media budget;
- duplicate identities не расходуют cap;
- overflow получает typed outcome `bundle_input_capped`, manager visibility и
  один безопасный clarify/summary request;
- никакой silent truncation и никакой generation на каждый fragment.

### 18.8. Edit, delete, reaction, audio и unsupported media

- edit до substantive provider boundary сохраняется отдельным raw event/tombstone,
  повышает revision и заменяет смысл только в новом snapshot; исходный evidence
  не переписывается задним числом;
- delete до send инвалидирует part в snapshot, но не удаляет audit row; если
  содержательных parts не осталось, substantive candidate закрывается без send;
- edit/delete после `SENDING` не «отзывает» ответ и создаёт corrective/manual
  branch по тем же правилам late continuation;
- reaction-only не присоединяется как новый текстовый fragment и не запускает
  Gemini, но сохраняется как отдельное событие;
- voice/audio/file получает typed media class; transcription, если она есть,
  становится новым evidence part той же revision, а failure транскрипции не
  скрывает исходное вложение;
- unsupported media даёт один safe outcome/manager visibility, не бесконечный
  retry и не generic товарный ответ.

---

## 19. Адаптация к манере клиента

### 19.1. Не «тип человека навсегда»

Профиль — rolling статистика с decay, а не enum `writes_in_bursts=True`.
Пользователь может сегодня написать один полный вопрос, а завтра отправить три
фото и пояснение.

### 19.2. Минимальная доказательность

- профиль начинает влиять после минимум 8 eligible turns;
- EWMA/бакеты затухают с half-life около 30 дней;
- текущий message class сильнее истории;
- episode/reset не стирает статистику cadence, но cadence не переносит business
  facts между эпизодами;
- hidden/private profile не отключает алгоритм.

### 19.3. Ограниченная поправка

- `COMPLETE_TEXT`: максимум `-0.25…+0.75 с` к quiet;
- continuation-prone classes: максимум `0…+2 с` к silent hard cap;
- hard global cap 20 с автоматически не повышается;
- control/bypass, payment safety и manager takeover не меняются профилем;
- профиль не может сам разрешить commerce action.

### 19.4. Почему не Gemini 3.6

Токены могут быть доступны, но запросы имеют latency, RPM/RPD, failure и
project-capacity. Выбор между 0.75 и 2.5 секунды по очевидным признакам не требует
генеративной модели. Durable Analysis V2 может позже оценивать качество решения
в shadow, но не становится обязательным gate живого ответа.

---

## 20. Side effects и транзакционные границы

### 20.1. Read → decide → write

Для snapshot revision сначала вычисляется **план** без необратимых эффектов.
Перед отправкой все reservations привязываются к `(turn_id, revision)` и могут
быть отменены. Финальные side effects выполняются после receipt либо по уже
существующему authoritative provider event.

### 20.2. Что обязано быть revision-bound

- commerce turn decision;
- checkout proposal/paylink;
- follow CTA/reservation;
- manager handoff task;
- funnel/stage projection (и, когда Э4 разблокируется, создание/закрытие узла
  воронки: superseded revision не имеет права оставить открытый узел, иначе
  реестр узлов начнёт накапливать призрачные ожидания от отменённых draft-ов);
- memory/analysis scheduling;
- recovery/holding intent;
- catalog media selection;
- outbound text/media plan.

### 20.3. Payment truth остаётся живой

Даже неизменяемый input snapshot не кэширует provider payment truth на весь ход.
Непосредственно перед payment/order action перечитывается authoritative state,
как уже требует `ig_turn_snapshot.py`.

### 20.4. Supersession

Подготовленный side effect обязан иметь `cancelled_before_io`/`superseded`
terminal outcome. Нельзя просто потерять Python object: после restart reservation
должна быть видна и reconciled.

---

## 21. Recovery и crash safety

### 21.1. Turn lease

`CLAIMED/GENERATING` без бессрочной lease недопустим. После expiry:

| Evidence | Reconciliation |
|---|---|
| provider boundary не пересечён, candidate stale | `READY` на latest revision |
| terminal source row, confirmed reply receipt | `PROCESSED` |
| `SENDING/UNKNOWN` без receipt | `AMBIGUOUS`, no auto retry |
| permission/takeover изменён | `SUPERSEDED`/`CANCELLED` |
| no-send terminal outcome | `PROCESSED` с reason |

### 21.2. Текущие stuck turns

Перед canary отдельная команда инвентаризации классифицирует 7 production rows.
Команда по умолчанию read-only/dry-run. Apply mode требует точной категории;
массовый `CLAIMED → PROCESSED` запрещён.

### 21.3. `IgAiReplyRecoveryJob`

Добавить связь с `turn_id + revision + source_message_ids`, сохранив текущие
message-floor, permission, response-window и UNKNOWN guards.

- новая revision до provider boundary отменяет recovery draft;
- после `SENDING` новый inbound не разрешает повтор old draft;
- holding ACK и substantive reply — разные outbound kinds;
- recovery не создаёт второй ACK/извинение.

---

## 22. Производительность и нагрузка

### 22.1. Hot-path budget

На один уникальный inbound:

- одна raw upsert/dedupe;
- один lock active turn/client;
- одна membership insert;
- один revision update;
- без Gemini, vision, provider conversation read и profile aggregation.

### 22.2. Scheduler

- indexed batch due query;
- текущий daemon tick 1.5 с сохраняется в первой версии;
- fairness: разные clients, затем oldest due within priority class;
- один client lease, без параллельных generations;
- no per-client timers/threads;
- no broad polling loop.

### 22.3. Экономия provider calls

Целевой эффект — один call на стабильную revision вместо call на каждый fragment.
Метрики обязаны считать не только tokens, но `provider_calls_started`, потому что
RPD/RPM ограничивают даже короткие prompts.

### 22.4. Backpressure

- per-sender message/media caps;
- global due queue depth;
- bounded max active generations;
- typed deferral при provider incident;
- не позволять одному long burst морить другие conversations голодом;
- load test только локально/staging, не широким production crawler.

---

## 23. Observability и management UI

### 23.1. Обязательная трасса

```text
hashed client / client_id
→ turn_id
→ source message IDs + provider/local timestamps
→ wait class/policy version
→ revision history
→ snapshot digest
→ Gemini request/attempt graph
→ candidate status/supersession
→ outbound intent
→ Meta receipt/UNKNOWN
→ terminal side effects
```

### 23.2. Метрики

| Метрика | Зачем |
|---|---|
| `messages_per_semantic_turn` | реальная склейка |
| `substantive_replies_per_turn` | главный anti-spam показатель |
| `acks_per_turn` | ACK не стал новым спамом |
| `quiet_wait_ms` по class | калибровка времени |
| provider→local ingress lag p50/p95/p99 | физический предел cancellation |
| final-fragment→reply receipt latency | UX после завершения мысли |
| `generation_superseded_total` | поздние inbound во время AI |
| `stale_send_blocked_total` | польза revision gate |
| `late_after_send_total` | неизбежные corrective turns |
| `false_merge` / `false_split` | качество bundle policy |
| correction within 60/120 s | proxy преждевременного ответа |
| manager takeover after bot reply | вред неверного automation |
| duplicate/UNKNOWN outbound | delivery safety |
| provider calls per user fragment | quota/performance |
| conflicting commerce effects | zero-tolerance safety |

### 23.3. UI

В карточке диалога показать компактно:

- `Собирает продолжение · 2 сообщения · до 4 с`;
- `Генерация revision 3`;
- `Draft r2 отменён новым сообщением`;
- `Ответ отправлен по 3 сообщениям`;
- `Позднее продолжение после send`;
- `UNKNOWN — нужна reconciliation`.

Raw тексты остаются в чате; отдельная панель не должна дублировать PII. Для
аудита менеджер может отметить `ошибочно объединил`, `ответил слишком рано`,
`ожидание лишнее`. Эти labels — данные для shadow tuning, не автоматическая
истина без review.

---

## 24. Feature flags и config ownership

```text
IG_SEMANTIC_TURNS_MODE = off | shadow | canary | on
IG_TURN_REVISION_SEND_GUARD = true/false
IG_TURN_STABLE_ACKS = true/false
IG_TURN_CADENCE_MODIFIER = true/false
IG_DM_NATIVE_REPLY_ENABLED = false
```

- timing policy version хранится в БД/typed config, не разбросана по regex;
- `IG_TURN_DEBOUNCE` legacy остаётся rollback path на время миграции;
- `revision send guard` можно включить раньше adaptive timing после тестов;
- native reply не включается общим semantic-turn flag;
- изменение флага не отменяет уже начатый Meta request.

---

## 25. План реализации по фазам

### Phase 0 — Заморозить baseline и RED replay

- [ ] Зафиксировать anonymized production replay `2811–2815` с двумя clocks.
- [ ] Добавить агрегатор provider→local lag и user→user gap.
- [ ] RED: media+greeting+continuation даёт stale generic reply в текущем path.
- [ ] RED: media первой строки отсутствует в latest-row multimodal input.
- [ ] RED: успешный turn остаётся `CLAIMED`.
- [ ] RED: новое inbound между draft-ready и send marker не блокирует send.
- [ ] Зафиксировать baseline p50/p95 latency, calls/turn, duplicate/correction.

**Файлы:** новый replay/test module; `tests_ig_burst_single_reply.py`,
`tests_ig_turn_budget.py`, production-safe aggregate command.

### Phase 1 — Один канонический turn и исправный lifecycle

- [x] После каждого terminal path переводить turn в `PROCESSED` с reason.
- [x] Добавить lease/reconciliation для stale `CLAIMED`.
- [x] Перевести `resolve_logical_turn_key()` на членство в `IgCustomerTurn`.
      **Поправка к исходной формулировке:** ключом стал не `turn:{id}`, а
      `logical_turn_key(client, первое сообщение хода)`. Формат `t{client}:{msg}`
      уже записан в живых `IgClientDegradationEpisode.logical_turn_id`; смена
      формата посреди открытого инцидента разорвала бы coalescing holding-ов и
      дала бы клиенту второй holding в том же ходе. Новый якорь даёт ту же строку
      в типовом случае и исправляет эвристику там, где она расходилась — когда
      между сообщениями клиента встрял исходящий ряд, не закрывающий смысл хода.
- [x] Legacy fallback оставить только для historical row без membership.
- [ ] `turn_phases()` выводит фазу ожидания из фактической wait policy
      (сегодня `TURN_DEBOUNCE`), а тест согласованности падает при расхождении
      объявленного и реального максимума ожидания.
- [ ] Dry-run inventory текущих stuck turns; apply только после классификации.
- [ ] Зафиксировать канонический порядок блокировок `client → turn` в ingress и
      worker (§12–13) и покрыть его тестом на MariaDB.

**Файлы:** `ig_customer_turns.py`, `ig_turn_lineage.py`, `instagram_bot.py`,
`ig_turn_budget.py`, management command, focused tests.

### Phase 2 — Expand schema и invariants, поведение ещё off

- [ ] Расширить `IgCustomerTurn` revision/deadline/state полями.
- [ ] Добавить snapshot и reply-candidate models.
- [ ] Добавить индексы/unique constraints с MariaDB-compatible контрактом,
      включая `(lifecycle_state, continuation_expected_until)`.
- [ ] Миграция expand-only, без data deletion/contract.
- [ ] Backfill existing turns как terminal historical state, не переигрывать их.
- [ ] Проверить InnoDB для новых таблиц.

**Файлы:** `ig_bot_models.py`, `models.py` export, migrations, schema tests.

### Phase 3 — Deterministic policy в shadow

- [ ] Реализовать typed `WaitDecision`, без LLM.
- [ ] Развести provider/local clocks.
- [ ] Рассчитать hypothetical `collect_until`, ACK, merge/split, revision.
- [ ] Не менять current claim/send path.
- [ ] Вывести PII-safe shadow metrics и manager labels.
- [ ] Снимать минимум одну policy version за раз.

**Нельзя:** shadow customer sends; второй live Gemini на каждый turn.

### Phase 4 — Bundle snapshot и media aggregation

- [ ] Snapshot включает все ordered source IDs и все owned media bindings.
- [ ] Prior history исключает current bundle duplicates.
- [ ] Commerce/prompt получает bundle text/parts, а не только latest row.
- [ ] Current floor/episode/permission fingerprint фиксируется.
- [ ] New inbound инвалидирует snapshot revision.
- [ ] Query budget не создаёт N+1 на каждый fragment.

**Файлы:** новый `ig_semantic_turns.py` или расширение
`ig_customer_turns.py`, `instagram_bot.py`, `ig_turn_snapshot.py` (не смешивать
runtime cache с durable input snapshot), media tests.

### Phase 5 — Supersession и atomic send gate

- [ ] Candidate создаётся для точной revision.
- [ ] Inbound во время generation делает candidate superseded.
- [ ] Один bounded restart; затем wait-latest-once.
- [ ] CAS revision/permission/lease/episode прямо перед `SENDING`.
- [ ] Unique outbound intent на `(turn, revision, kind)` — **расширением**
      идемпотентного intent-а ЭА.21, без второй таблицы outbound-состояния.
- [ ] Нарушение unique-ключа обрабатывается как `intent_already_claimed`
      (штатный исход), а не как исключение.
- [ ] Side-effect reservations revision-bound и cancellable.
- [ ] `UNKNOWN` не ретраится.
- [ ] Recovery связан с turn/revision.

### Phase 6 — Stable ACK и continuation expectation

- [ ] Approved ACK intents через template layer.
- [ ] ACK не закрывает semantic turn.
- [ ] Один ACK максимум.
- [ ] ACK проходит через outbound outbox ЭА.16 и считается в бюджете «один
      технический текст на ход» (ЭА.6/ЭА.8).
- [ ] При открытом `IgProviderIncident` ACK не отправляется: единственный
      customer-visible текст принадлежит эпизоду деградации (ЭА.3).
- [ ] Hold phrase по умолчанию без текста.
- [ ] Late continuation в TTL получает один substantive execution.
- [ ] Native reply остаётся off до отдельного capability proof.

### Phase 7 — Canary, production calibration и rollout

- [ ] Shadow report reviewed.
- [ ] Internal/test allowlist.
- [ ] Low-risk text canary.
- [ ] Greeting/media canary.
- [ ] Payment/certificate остаются no-side-effect до отдельного sign-off.
- [ ] Малый последовательный production test; никаких широких crawls.
- [ ] Истёкший continuation TTL закрывает ход в `PROCESSED` с reason, и в
      production нет `ACKED_WAITING` старше TTL + одного tick.
- [ ] Записать deployed SHA, migrations, daemon PID/heartbeat, DB states,
      request→receipt lineage и метрики.

---

## 26. QA-матрица

### 26.1. Время и текст

- [ ] Полный вопрос одним сообщением.
- [ ] Три слова с интервалами 0.1/0.5/1.5 с.
- [ ] Пять fragments за 6 с.
- [ ] Greeting → смысл через 0.2/1/6/10.58/19/61 с.
- [ ] Greeting без продолжения.
- [ ] Hold phrase → продолжение через 5/20/89/91 с.
- [ ] `да` при одном вопросе.
- [ ] `да` при двух незакрытых вопросах.
- [ ] Correction `не чорне, біле` во время generation.
- [ ] Два независимых intent в одном burst.

### 26.2. Media

- [ ] Фото → текст.
- [ ] Текст → фото.
- [ ] Фото → greeting → описание (production replay).
- [ ] Фото после явной просьбы бота.
- [ ] Unsolicited фото без текста.
- [ ] Два/пять фото как варианты.
- [ ] Два одинаковых provider object IDs с разными signed URLs.
- [ ] Два разных media с похожими URLs.
- [ ] Partial media capture failure.
- [ ] Story reply/mention не спутан с обычным фото.
- [ ] Voice/audio → transcription continuation и transcription failure.
- [ ] Unsupported file даёт один safe outcome.

### 26.3. Payment/commerce

- [ ] Чек 800 → `остальные 200 завтра`.
- [ ] Чек без пояснения.
- [ ] Пояснение → чек.
- [ ] Два разных order IDs в одном burst.
- [ ] Provider payment webhook во время Gemini.
- [ ] Verified paid не получает второй invoice.
- [ ] Certificate image не считается валидированным только моделью.
- [ ] Superseded revision не создаёт proposal/paylink/order/follow-up.

### 26.4. Concurrency

- [ ] Inbound до snapshot.
- [ ] Inbound сразу после provider generation start.
- [ ] Inbound на последней миллисекунде generation.
- [ ] Inbound во время typing wait.
- [ ] Inbound между pre-check и send CAS.
- [ ] Inbound после `SENDING`, до receipt.
- [ ] Два workers claim один turn.
- [ ] Duplicate webhook не повышает revision.
- [ ] Out-of-order webhook меняет presentation order, но не теряет evidence.
- [ ] Edit/delete до send повышает revision и инвалидирует snapshot.
- [ ] Edit/delete после send не создаёт blind resend.
- [ ] Reaction-only не становится текстовым fragment.
- [ ] Manager takeover в collection/generation/send-reserved.
- [ ] Opt-out внутри burst.
- [ ] Quick reply внутри burst.

### 26.5. Failure/restart

- [ ] Crash после membership insert, до revision save.
- [ ] Crash после snapshot, до Gemini.
- [ ] Crash во время Gemini.
- [ ] Crash после draft, до send marker.
- [ ] Crash после `SENDING`, до provider response.
- [ ] Meta accepted, local timeout → `UNKNOWN`, no retry.
- [ ] Echo приходит после restart.
- [ ] Lease expires в каждом non-terminal state.
- [ ] Provider 400/403/429/5xx/ReadTimeout классифицируются отдельно.
- [ ] Context7/внешняя документация недоступна — runtime не зависит от неё.

### 26.6. Performance/privacy

- [ ] 100 клиентов с короткими bursts в local/staging load test.
- [ ] Один клиент с >50 fragments не блокирует остальных.
- [ ] Due query использует индекс.
- [ ] Prompt query budget bounded, нет N+1 по message count.
- [ ] Нет второго classifier LLM call.
- [ ] Логи не содержат IGSID, token, private media URL или полный чек.
- [ ] Raw retention и deletion workflow сохраняют privacy contract.
- [ ] MariaDB concurrency tests отдельно от SQLite unit tests.

---

## 27. Shadow и canary

### 27.1. Shadow mode

Текущий outbound path не меняется. Новый policy engine записывает:

- hypothetical bundle membership;
- wait class/timers;
- merge/split decision;
- был бы draft superseded;
- сколько model calls/answers избежали бы;
- какой ACK был бы выбран;
- какой latency delta получился бы.

Shadow Gemini допускается только на малом sampling rate и не отправляет ответ.
Для первых метрик достаточно безмодельного replay текущих событий.

### 27.2. Canary ladder

1. `0%`: shadow only.
2. internal/test accounts allowlist.
3. `1–5%`: low-risk informational text.
4. `10%`: greeting/short-fragment.
5. `25%`: expected media.
6. `50%`: unsolicited media после manual review.
7. `100%`: только после owner sign-off.

Payment, certificate redemption и irreversible order actions не включаются
процентом общего canary: для них отдельный explicit gate.

### 27.3. Hard stop gates

Расширение запрещено при любом из условий:

- один confirmed false merge с неверным payment/order effect;
- stale substantive send при **уже локально сохранённом** более новом inbound;
- missed manager takeover/opt-out;
- duplicate outbound выше baseline;
- `UNKNOWN` без reconciliation;
- raw event loss;
- отсутствует `turn → revision → request → receipt`;
- p95 final-fragment→reply заметно хуже baseline без согласованной причины;
- растут DB lock contention, queue depth или Meta/provider errors;
- ACK превращается в дополнительный spam.

Порог `заметно хуже` до canary заменяется числом по 7–14-дневному baseline.
Придумывать процент без baseline запрещено. Для commerce safety допустимый порог
всегда ноль подтверждённых ошибок.

---

## 28. Rollback и reconciliation

### 28.1. Rollback

- `IG_SEMANTIC_TURNS_MODE=off` для новых turns;
- остановить новые candidates, не прерывая `SENDING`;
- drain/cancel только pre-provider reservations;
- legacy one-row path остаётся доступен;
- schema/raw/snapshot/attempt evidence не удаляется;
- native reply flag независим и остаётся off.

### 28.2. После rollback

Классифицировать все:

- `COLLECTING/ACKED_WAITING` → legacy pending latest row;
- `GENERATING/DRAFT_READY/SEND_RESERVED` → superseded/cancelled before I/O;
- `SENDING/AMBIGUOUS` → receipt/echo reconciliation;
- `SENT`, но side effects не завершены → idempotent finalize;
- conflicting payment/order markers → manual queue.

Rollback останавливает новые решения, но не притворяется, что удаляет уже
доставленное Instagram-сообщение.

---

## 29. Definition of Done

Workstream нельзя закрыть только потому, что unit tests зелёные.

### 29.1. Code/schema

- [ ] Один canonical `IgCustomerTurn`; legacy lineage только для истории.
- [ ] Turn lifecycle не остаётся бессрочно `CLAIMED`.
- [ ] Revision растёт только на уникальный inbound/control event.
- [ ] Все media/text parts попадают в bundle snapshot.
- [ ] Candidate не отправляется при revision mismatch.
- [ ] Side effects revision-bound.
- [ ] `UNKNOWN` не ретраится.
- [ ] Stable ACK отдельный от substantive reply.
- [ ] One substantive reply per stable semantic turn.

### 29.2. Tests

- [ ] Production replay зелёный.
- [ ] Полная QA-матрица critical branches зелёная.
- [ ] SQLite structural suite зелёная.
- [ ] MariaDB lock/concurrency suite зелёная.
- [ ] Django `check`, migration drift, compile и diff checks зелёные.
- [ ] Fault injection до/после provider boundary зелёный.

### 29.3. Production

- [ ] Deployed SHA совпадает с `origin/main` и server HEAD.
- [ ] Новые migrations применены; новые tables InnoDB.
- [ ] Daemon перезапущен на новом коде; PID/heartbeat/main progress свежие.
- [ ] Нет stale `CLAIMED` без классифицированной причины.
- [ ] Test account replay даёт один substantive reply.
- [ ] Source IDs, revision, request ID и provider receipt связываются одним
      запросом.
- [ ] Нет duplicate/commerce regression.
- [ ] Shadow/canary метрики записаны с baseline и owner sign-off.

---

## 30. Отвергнутые решения

| Идея | Почему не выбрана |
|---|---|
| Всегда ждать 20–60 с | медленно для большинства; greeting/media median не означает, что всем нужно молчать |
| Оставить fixed 6 с | production ловит лишь часть continuation; не защищает generation/send race |
| Отвечать на каждую строку | spam, конфликтующие предложения и side effects |
| Сначала ответить, потом «исправить» | correction полезна только после необратимой границы, не как основной алгоритм |
| Смотреть user typing/online | официальный server API не даёт надёжный сигнал |
| Перед каждым send читать Meta conversation | дополнительный I/O/rate/latency, eventual consistency, новый failure dependency |
| LLM решает, ждать ли ещё | медленнее и дороже самого debounce, имеет собственные ошибки/квоты |
| Client flag `writes_in_bursts` | стиль меняется; постоянный флаг создаёт неправильную задержку |
| Cancel provider request = safety | cancellation может опоздать; безопасность даёт revision CAS |
| Reply-to любого DM | capability не подтверждена текущим официальным contract |
| Удалить поглощённые rows | теряется evidence, dedupe, replay и manager context |
| Retrying Meta timeout | может удвоить уже принятое сообщение |

---

## 31. Вопросы для дополнительного аудита

Это не блокеры проектирования, а параметры, которые следующий аудит должен
подтвердить данными:

1. Нужен ли greeting ACK после 2.5–4 с или достаточно `mark_seen` в текущем UI
   Instagram?
2. Какой baseline final-fragment→reply у ordinary/complex turns без provider
   incident?
3. Какая доля 19-секундных greeting/media pairs действительно один intent, а не
   новая мысль?
4. Может ли текущий Instagram Login endpoint документированно отправлять native
   reply-to DM?
5. Какие commerce writes можно перевести в prepare/finalize без изменения
   существующих authoritative reducers?
6. Какой bounded prompt/media cap соответствует текущему Gemini routing budget?
7. Нужна ли materialized cadence table после shadow или достаточно агрегатов?
8. Достаточен ли daemon tick 1.5 с после сокращения ordinary quiet-window?

Все ответы фиксируются новой policy version; нельзя тихо менять секунды в коде.

---

## 32. Карта файлов для implementer

### 32.1. Основные production-файлы

| Путь | Планируемая ответственность |
|---|---|
| `twocomms/management/bot_webhook.py` | сохранить быстрый persistence-only ingress; не запускать coalescing/Gemini внутри HTTP request |
| `twocomms/management/services/instagram_bot.py` | заменить latest-row execution на bundle snapshot; вставить revision CAS, ACK/corrective delivery и terminal lifecycle hooks |
| `twocomms/management/services/ig_customer_turns.py` | canonical attachability, local clocks, wait decision, revision, due claim, terminal transitions и reconciliation helpers |
| `twocomms/management/services/ig_turn_lineage.py` | canonical `IgCustomerTurn` ID; legacy fallback только для historical rows |
| `twocomms/management/services/ig_turn_budget.py` | фактические per-policy wait phases, heartbeat/notice consistency |
| `twocomms/management/services/ig_ai_reply_recovery.py` | turn/revision-aware cancellation, UNKNOWN и corrective boundary |
| `twocomms/management/services/ig_turn_snapshot.py` | сохранить runtime/prompt cache; не превращать его молча в durable input snapshot |
| `twocomms/management/services/ig_reply_boundary.py` | permission/takeover epoch остаётся обязательным CAS input |
| `twocomms/management/services/ig_commerce_turns.py` и reducers | prepare/finalize или revision-bound side effects без второго business lifecycle |
| `twocomms/management/services/ig_commerce_state.py` | reply-to/card expectation для `да/нет`, но не outbound native reply capability |
| `twocomms/management/services/ig_private_media.py` / `bot_vision.py` | собрать owned media всех parts и сохранить retention/ownership |
| `twocomms/management/ig_bot_models.py` | turn/snapshot/candidate/cadence schema |
| `twocomms/management/models.py` | exports и `InstagramBotMessage` compatibility fields только при необходимости |
| `twocomms/management/management/commands/run_instagram_bot.py` | reuse 1.5-second scheduler, recovery/reconciliation ownership; без нового daemon |
| `twocomms/twocomms/settings.py` | typed feature flags и policy version defaults |
| `twocomms/management/templates/management/bot.html` / API projection | compact turn state, supersession и manager labels после backend truth |

Новый cohesive service допустим как
`twocomms/management/services/ig_semantic_turns.py`, если
`ig_customer_turns.py` иначе станет смешивать persistence, policy и delivery.
Нельзя оставлять два владельца attachability: один public facade должен быть
каноническим.

### 32.2. Focused tests, которые расширяются

| Тест | Что добавить |
|---|---|
| `tests_ig_customer_turns.py` | local clocks, sliding/hard deadlines, revision и terminal states |
| `tests_ig_burst_single_reply.py` | production replay, ACK vs substantive, 3–5 fragments |
| `tests_ig_inbound_dedupe.py` | duplicate не повышает revision; rotated signed URL |
| `tests_ig_media_identity.py` / `tests_ig_media_workflow.py` | all-part media snapshot, multi-photo order, partial capture |
| `tests_ig_turn_budget.py` | policy-aware wait, daemon/notice budget consistency |
| `tests_ig_live_reply_priority.py` | new inbound during generation/typing/pre-send, manager takeover |
| `tests_ig_reply_delivery_evidence.py` | unique outbound intent, receipt/UNKNOWN by revision |
| `tests_ig_ai_reply_recovery.py` | superseded recovery, post-boundary continuation, no blind retry |
| `tests_ig_turn_snapshot.py` | durable snapshot не ломает runtime cache/query budget |
| `tests_ig_commerce_turns.py` / `tests_ig_commerce_state.py` | no stale proposal/invoice/order, yes/no binding |
| `tests_ig_conversation_analysis_jobs.py` | один analysis schedule на terminal bundle revision |
| новый state-machine test module | exhaustive transition table и crash points |
| новый MariaDB integration module | conditional claim/CAS/lease concurrency; SQLite не является доказательством |

### 32.3. Документы, которые обновляются при реализации

- `04_IMPLEMENTATION.md`: статус/checkbox/SHA/production evidence;
- этот файл: policy version, реальные тайминги и отклонения от плана;
- `08_IMPLEMENTATION_FINDINGS_LOG.md`: обнаруженные во время кода расхождения;
- `06_SUMMARY.md`: новые state/concurrency/payment/media сценарии
  (отдельного `06_TEST_MATRIX.md` в репозитории нет — не создавать новый
  индекс, расширять существующий свод);
- runbook деградации/rollback, если меняются operator actions.

---

## 33. Источники и граница исследования

Context7 был вызван 2026-08-31 для Meta Instagram Messaging API, но сервер вернул
`Monthly quota reached`. Это не было выдано за успешную проверку. Ограничения API
сверены по первичным/официальным материалам:

- [Meta Instagram API / Send API](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api)
- [Meta Instagram webhook subscriptions](https://www.postman.com/meta/instagram/request/23987686-0223707a-7035-46a2-8015-1fdf7249278f)
- [Meta Messenger/Instagram webhook fields](https://www.postman.com/meta/messenger-platform-api/folder/22794852-b5d97624-14d8-4e67-a2e4-529add49ca58)
- [Meta sender actions](https://www.postman.com/meta/messenger-platform-api/folder/7plilu6/sender-actions)
- [AWS: high-performance AI assistant messaging](https://aws.amazon.com/blogs/messaging-and-targeting/best-practices-for-building-high-performance-whatsapp-ai-assistant-using-aws/)
- [AWS Well-Architected: resilient messaging layer](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentrel01-bp01.html)
- [AWS Well-Architected: idempotent task execution](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentrel06-bp04.html)

Внешние источники подтверждают durable ingestion, sender actions,
idempotency/traceability и отсутствие документированного user typing в списке
Instagram webhook subscriptions. Конкретные timing values этого документа —
TwoComms policy proposal, выведенный из production evidence и подлежащий shadow
калибровке, а не универсальный стандарт Meta/AWS.
