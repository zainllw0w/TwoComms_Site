# 03 - Дополнительные находки: сильные бусты агента и новые code-path риски

Дата: 2026-08-26.

Этот документ продолжает `01_FINDINGS.md` и `02_ANALYSIS.md`, но намеренно не
повторяет их реестр памяти, подворонок, catalog revision, lifecycle policy,
Gemini candidate ledger или generic prompt tuning. Здесь находятся только:

1. новые source-to-sink defects, не описанные в первых двух файлах;
2. отдельные security/privacy candidates с честным proof gap;
3. архитектурные и sales-agent возможности, которые делают ответы точнее,
   безопаснее и полезнее без манипуляций и выдуманных обещаний;
4. external practices, переведённые в конкретные, измеримые contracts проекта.

## Базовая линия и метод

- Кодовая база: локальный `main == origin/main == cb4d6463b3f3adcccb0402e2adb32870ed6e5636`.
- `01_FINDINGS.md` был пересмотрен другим агентом: в нём появились
  классификация, слияния с `02`, новые wave tables и честная фиксация версионного
  расхождения. В этом запуске это расхождение снято: скидочные follow-up на
  `cb4d6463` требуют manager approval через migration `0169`, authenticated
  Telegram callback и revalidation перед send. `01` обновлён соответственно.
- Production не менялся. Свежий SSH read-only probe невозможен в этом запуске:
  `TWOCOMMS_DEPLOY_PASSWORD` не был передан окружением, а ключевая SSH
  аутентификация отклонена. Любой пункт, требующий частоты/engine/runtime
  факта, помечен `CALIBRATE`.
- Внешние источники проверялись только как design evidence. Они не заменяют
  Meta contract, серверные данные или собственные regression tests.

### Свежая локальная проверка baseline

На `cb4d6463` с project Python 3.14.6/Django 6.1 прошли `manage.py check` и
140 focused tests из `management.tests_ig_discount_approval`,
`management.tests_ig_daemon`, `management.tests_ig_bot_resilience`,
`management.tests_ig_webhook_extract` и
`management.tests_ig_data_deletion_safety`. Это подтверждает текущие approval,
daemon, webhook/media и deletion contracts, но не является доказательством, что
новые code-path findings отсутствуют: для каждого из них ниже указан отдельный
RED/acceptance case.

### Статусы

| Статус | Что именно доказано |
|---|---|
| **SOURCE-CONFIRMED** | Найден полный code path от reachable input/condition до конкретного нежелательного эффекта. |
| **SECURITY-CANDIDATE** | Source и sink существуют, но реальная attacker control или deployment constraint требует отдельной валидации. Не объявлять incident без неё. |
| **EXTERNAL-BOOST** | Идея опирается на первоисточник, но отсутствует как продуктовая capability. Нужен baseline и controlled rollout. |
| **CALIBRATE** | Направление обосновано, однако приоритет зависит от production rate/p95/p99 или provider policy. |

### Что уже не переоткрывается

Этот файл не предлагает снова сделать typed memory, request-level Gemini ledger,
one funnel node registry, manager-approved discounts, Meta policy object, stale
analysis marking, line-scoped commerce или post-sale lifecycle funnel. Это уже
корректно описано в `01/02`. Новые пункты используют эти будущие contracts как
dependencies, а не создают параллельные версии.

## A. Новые source-confirmed defects

### ADD-CODE-001 - Успешно отправленный ответ может молча потерять конец текста

- **Статус:** SOURCE-CONFIRMED.
- **Приоритет:** P1. Это потеря смысла уже после правильной генерации, а не
  косметический лимит длины.
- **Trace:** `ig_response_control.py` допускает `reply_text` до 4 000
  символов. `instagram_bot._split_for_send()` делит ответ максимум на четыре
  чанка по 950 UTF-8 байт и возвращает созданные chunks, не возвращая остаток.
  `send_text()` считает все созданные chunks complete delivery.
- **Нежелательный эффект:** сложный ответ с украинскими символами, emoji, list
  или длинным custom-print explanation может быть принят Meta полностью для
  первых четырёх chunks, но заключение, safety caveat, price clarification или
  CTA в конце исчезнет. Receipt остаётся зелёным: это не существующий
  `partial_delivery` case.
- **Правильное решение:** before provider I/O create a `delivery_plan` with
  exact byte accounting and one of двух явных outcomes: `complete` или
  `intentionally_summarized`. Нельзя silently truncate. Для semantic long reply
  лучше deterministic compacting policy до send: сохранить factual ядро,
  удалить повторение, перенести необязательное в next turn только при новом
  customer input. Если compressed form не проходит, route to manager или
  structured card, а не отправлять полфразы.
- **RED/acceptance:** reply with final sentinel after 3 800+ UTF-8 bytes либо
  доставляется целиком с четырьмя+ разрешёнными chunks, либо source row хранит
  `truncated_before_send` + exact reason and customer receives a grammatical
  short form. No outcome may report `sent` if source tail disappeared.
- **Метрика:** `reply_truncated_before_send`, p95 byte length, loss-of-tail
  count and manager corrections attributable to incomplete replies.

### ADD-CODE-002 - Глобальная permission lock сериализует Meta I/O всех клиентов

- **Статус:** SOURCE-CONFIRMED.
- **Приоритет:** P1 before scaling traffic.
- **Trace:** every live reply, commerce reply, follow-up and lifecycle send
  supplies `customer_send_boundary()` to `send_text()`. That boundary holds one
  global file lock through the context `yield`; `send_text()` performs the
  provider request inside it. Meta request timeout is bounded but non-trivial,
  and a multi-chunk reply repeats the boundary.
- **Нежелательный эффект:** a slow provider call for client A can delay a
  legitimate response to every other client. The current global lock protects
  pause/takeover correctness, but converts one network tail into global queue
  latency and amplifies `ADD-CODE-003/007`.
- **Не делать:** нельзя просто убрать lock или switch to threads: then a
  permission epoch/takeover may change after preflight and before provider I/O.
- **Правильное направление:** preserve short global epoch capture + durable
  `sending` marker, then use a per-client fenced send lease for the actual
  request. Final permission recheck must be atomic with marker creation; an
  epoch change afterwards yields an auditable ambiguous boundary, not blind
  retry. Record lock wait separately from provider latency.
- **RED/acceptance:** mocked 12-second send for A must not block a clean
  send for B beyond a bounded global preflight budget; a concurrent manager
  takeover for A still prevents A's provider call if it wins before marker.
  No duplicate send and no cross-client receipt mix-up.
- **Метрика:** global boundary wait p50/p95/p99, per-client send time,
  `permission_abort_before_io`, provider latency and queue age by client.

### ADD-CODE-003 - Нормально работающий long turn может выглядеть watchdog-у мёртвым

- **Статус:** SOURCE-CONFIRMED.
- **Приоритет:** P1; concrete refinement of `02: NEW-OPS-003`, not a duplicate
  uptime dashboard request.
- **Trace:** daemon heartbeat is renewed only after `_run_work_cycle()` returns.
  `HB_ALIVE_WINDOW` is 45 seconds. A complex live Gemini task is allowed a
  45-second deadline before typing/send/post-processing, while
  `process_pending(max_items=15)` is synchronous. `--ensure` treats held lock +
  stale heartbeat as a stale daemon and waits/reports a reload failure.
- **Нежелательный эффект:** no crash is required. One slow but valid response
  can miss the heartbeat window, make cron report failure, trigger alert debt or
  contribute to restart churn. This explains why "fresh watchdog" is not a
  sufficient user-outcome health signal.
- **Правильное решение:** heartbeat must represent two dimensions: process
  liveness and active work lease. Renew liveness independently on a safe timer;
  expose `active_work_started_at`, kind, bounded deadline and progression. A
  watchdog should only consider a work lease stale after its own maximum plus a
  buffer, not because an ordinary permitted call occupies the loop.
- **RED/acceptance:** deterministic blocking `process_pending` longer than 45
  seconds but shorter than its declared work deadline never causes a restart/
  `CommandError`; truly wedged work beyond the declared deadline does. The
  daemon still exits correctly on maintenance/restart sentinel.
- **Метрика:** false-stale count, daemon generation/restart rate, longest work
  lease, live reply p95 and true stale recovery success.

### ADD-CODE-004 - Полный Gemini cooldown превращает inbox в молчаливую очередь

- **Статус:** SOURCE-CONFIRMED.
- **Приоритет:** P1.
- **Trace:** when every chat key is in cooldown,
  `_defer_for_gemini_cooldown()` returns current row to `PENDING` and sets a
  global `ig_bot_gemini_backoff` cache key. It runs before
  `build_ai_failure_fallback()`. While the key exists, `process_pending()` exits
  before claiming any row.
- **Нежелательный эффект:** support, order and general customer input receive
  no holding response, no safe fallback and no deterministic manager handoff
  until the earliest cooldown. The code protects quota, but not the user's
  expectation of acknowledgement. This is distinct from `NEW-AI-001/002`, which
  concern quality/model routing rather than whole-queue silence.
- **Правильное решение:** a cooldown state must choose one of explicitly
  policy-valid behaviours per intent: deterministic acknowledgement, durable
  manager case, or delayed retry with visible ETA only if truthful. It must not
  use the model, create an unbounded retry storm or advertise unavailable human
  response. Queue admission can stay closed for expensive AI while a small
  no-AI lane drains safe customer acknowledgements.
- **RED/acceptance:** all chat keys forced to cooldown; each inbound reaches a
  terminal customer/state outcome once, without Gemini call or duplicate send.
  Payment/order claims remain fail-closed. After cooldown, original row is not
  reprocessed into a second customer reply.
- **Метрика:** cooldown silent-age, fallback/handoff outcome, queue size/age,
  reply receipt rate and duplicate reply rate after recovery.

### ADD-CODE-005 - Mid-less webhook dedupe can fail when CDN signature changes

- **Статус:** SOURCE-CONFIRMED.
- **Приоритет:** P1 for webhook reliability.
- **Trace:** missing-`mid` events derive a synthetic key from sender, timestamp,
  text and attachment URL. The code itself documents provider signed media URLs
  as disposable. A retry of the same attachment with a new signature therefore
  hashes differently and can create a second pending row/reply.
- **Нежелательный эффект:** one customer media turn becomes two automation
  turns. This is especially damaging when image analysis consumes quota or when
  the first reply has already created a commerce action.
- **Правильное решение:** use provider-native attachment object ID whenever it
  exists; otherwise normalize a URL to a verified stable identity only under a
  documented Meta contract. If neither exists, choose a conservative
  observation-only/dedupe-window path rather than pretending a volatile signed
  URL is identity.
- **RED/acceptance:** same sender/timestamp/text and same provider media object
  with two URL signatures produces exactly one CRM row, one analysis schedule
  and at most one reply. Distinct attachments remain distinct. Never canonicalize
  arbitrary customer URLs by dropping all query data blindly.
- **Метрика:** no-`mid` duplicate rate, synthetic-key collision rate, duplicate
  media AI calls and duplicate customer sends.

### ADD-CODE-006 - Cache outage fail-opens cost and flood-control guards

- **Статус:** SOURCE-CONFIRMED.
- **Приоритет:** P1.
- **Trace:** cache exceptions make `_rate_exceeded()` return false,
  `_repeated_question()` return zero and `_match_allowed()` return true. These
  guards sit before Gemini and vision work.
- **Нежелательный effect:** a cache outage, exactly when the system is already
  degraded, permits repeated questions/photos to consume the most expensive
  provider path. It can deepen quota exhaustion and then trigger
  `ADD-CODE-004` queue silence.
- **Правильное решение:** distinguish customer safety from economic admission.
  Never auto-block a customer because cache is unhealthy, but use a small
  durable/local bounded circuit for provider-heavy work: one limited attempt,
  deterministic acknowledgement, and manager/scheduled recovery as needed.
- **RED/acceptance:** cache get/add/incr failures plus burst text/photos do not
  create unbounded Gemini/vision calls. A normal client still gets one safe
  outcome and no false spam state.
- **Метрика:** provider calls during cache error, cache-error fallback rate,
  per-sender cost cap and queue age.

### ADD-SEC-001 - Media downloader has a plausible SSRF boundary, not yet a proven exploit

- **Статус:** SECURITY-CANDIDATE, confidence medium.
- **Приоритет:** P1 validation gate; do not label it an incident or test it
  against production infrastructure.
- **Source/sink:** webhook attachment parsing accepts `http(s)` payload URLs
  for several media/link types. Live media capture later forwards stored URL to
  `urllib.request.urlopen()` with redirects enabled and no explicit hostname,
  DNS/IP-range or redirect target policy.
- **Why it matters:** if a legitimate signed webhook can carry a customer-
  controlled link attachment rather than only a Meta CDN URL, the application
  can be induced to fetch an internal/private or slow endpoint from production
  network context. The signed webhook verifies Meta delivery, not necessarily
  the safety of every user-originated URL inside its payload.
- **Counterevidence/proof gap:** repository fixtures often use CDN-like URLs;
  no source proof yet establishes that the production Meta payload contract
  exposes arbitrary user-controlled URL for a live capture-eligible attachment.
  Historical media is metadata-only. Therefore this is not a P0 reportable
  finding until the exact provider contract and a local no-network test settle
  reachability.
- **Required validation:** unit-test URL policy only, using mocks: reject
  localhost, loopback, RFC1918, link-local, IPv6 local ranges, DNS rebinding
  results and redirect-to-private before connection; permit only documented
  Meta CDN host patterns or a separately reviewed fetch proxy. Do not make live
  SSRF requests.
- **Safe design:** validate scheme, canonical host allowlist, resolved public IP
  on every redirect and size/content type before streaming. Prefer provider
  object IDs or owned media bytes over arbitrary URLs.

### ADD-DATA-001 - Raw webhook batch and deletion isolation use incompatible ownership models

- **Статус:** SOURCE-CONFIRMED.
- **Приоритет:** P1 privacy/correctness.
- **Trace:** `record_raw_event()` stores up to 20k of the entire webhook batch,
  but stores only the first discovered `sender_id` as its index. Data deletion
  removes raw rows by that one `sender_id`.
- **Нежелательный эффект:** a batch containing A and B can leave B's personal
  payload inside row indexed as A after B deletion, or delete the evidence of B
  when A is deleted. Existing structured-message deletion does not solve this
  representation mismatch.
- **Правильное решение:** make raw evidence per logical event/participant, or
  store an encrypted/redacted batch with a complete bounded participant index
  and a transactionally safe redaction-on-erasure procedure. Do not rewrite
  arbitrary JSON using substring replacement.
- **RED/acceptance:** a two-client payload then deletion for A and for B leaves
  neither client's personal content retrievable through raw events while never
  deleting the other client's unrelated durable records. Retention cleanup
  still works idempotently.

### ADD-CODE-007 - Freshest-first inbox priority can starve older ready customers

- **Статус:** SOURCE-CONFIRMED; real magnitude requires CALIBRATE.
- **Приоритет:** P1 for customer SLA.
- **Trace:** `_claim_next()` intentionally orders conversations by most recent
  `client.last_message_at`; `process_pending()` serially handles a bounded
  batch. A continuous arrival of new messages can keep older pending rows below
  the head indefinitely.
- **Нежелательный effect:** responsiveness for fresh chats improves while a
  ready buyer who wrote earlier may never receive an answer. Average latency can
  look healthy, hiding severe p95/p99 and lost conversions.
- **Правильное решение:** maintain priority lanes: urgent response within a
  freshness budget, then ageing promotion based on waiting time. Each client
  remains single-flight through existing lease; fairness must not create two
  concurrent replies to one conversation.
- **RED/acceptance:** synthetic continuous fresh influx cannot postpone an older
  eligible row beyond a declared age ceiling. One client never has more than
  one active send; priority does not bypass takeover/opt-out/Meta boundary.
- **Метрика:** queue-age p50/p95/p99, maximum age, starvation count, replies by
  lead stage and conversion versus wait time.

### ADD-CODE-008 - Conversation identity is not namespace-scoped by provider owner

- **Статус:** SOURCE-CONFIRMED design defect; priority is CALIBRATE/P2 now and
  P1 before account/transport migration.
- **Trace:** inbox refresh stores `provider_owner_id`, while `IgClient` is
  global by `igsid` and inbound message identity is global. Webhook-created
  client/message state does not persist a canonical ingress owner/transport.
- **Нежелательный effect:** when an Instagram account, app transport or owner
  changes, the same remote ID can theoretically inherit old memory, opt-out,
  takeover, order binding or dedupe state without a provable cutover rule.
- **Правильное решение:** persist immutable owner/transport namespace at ingress
  and define explicit cutover/migration policy. Do not silently scope current
  unique keys by adding a column without resolving existing records.
- **Acceptance:** two owner namespaces with equal sender/message IDs cannot
  share customer state; intended migration has an audited mapping and rollback.

### ADD-CODE-009 - Retention cleanup is performed inside webhook acknowledgement path

- **Статус:** SOURCE-CONFIRMED.
- **Приоритет:** P2, P1 under high ingress.
- **Trace:** webhook handler invokes `record_raw_event()` before returning
  acknowledgement. At retention threshold that function performs count/order/
  list/delete work. Operational log cleanup uses a similar request-path cleanup
  pattern.
- **Нежелательный effect:** housekeeping latency raises webhook ACK tail and
  therefore duplicate provider delivery risk precisely under load.
- **Правильное решение:** keep raw event persistence bounded and fast; move
  purge to an idempotent bounded worker/command with a watermarked cursor.
  Retention job failure must not reject or slow a valid webhook.
- **Acceptance:** a forced retention threshold does not materially change p95
  webhook ACK; cleanup can resume after crash without deleting newest events or
  increasing duplicate ingress.

### ADD-DIALOG-001 - One customer burst can produce several replies to the same combined context

- **Статус:** SOURCE-CONFIRMED.
- **Приоритет:** P1 for perceived intelligence and send correctness.
- **Trace:** `enqueue_inbound()` stores each valid user message as a separate
  `PENDING` row. `_build_history()` includes all rows for the sender, including
  later pending messages. `process_pending()` claims and processes up to 15
  rows sequentially, but does not coalesce/supersede sibling user messages after
  one reply is sent.
- **Нежелательный эффект:** client writes three natural fragments - "хочу
  худи", "чёрное", "размер L". The first processed row sees the whole history
  and can answer correctly; then each later pending row can cause another reply
  against an almost identical context. This is not merely token waste: duplicate
  answers can repeat questions, send multiple options or create conflicting
  commerce actions.
- **Правильное решение:** model a customer *turn* as a bounded burst, not one
  webhook row. Use a short quiet/debounce window only for adjacent user rows in
  the same episode, record all source message IDs, claim a turn atomically, and
  mark consumed sibling rows with `consumed_by_turn_id`. Urgent explicit
  opt-out/manager/takeover events bypass debounce.
- **Не делать:** do not delete/merge raw messages, and do not delay an explicit
  customer question indefinitely waiting for a perfect burst. The response SLA
  in `ADD-AGENT-013` is the upper bound.
- **RED/acceptance:** three quick inbound rows yield one model/send execution,
  one provenance record with all message IDs and one visible reply. A later
  message outside the window produces a new turn. Duplicate webhook delivery
  remains idempotent.
- **Метрика:** messages-per-turn, replies-per-turn, duplicate-reply rate,
  correction rate after burst and p95 time-to-first-response.

### ADD-DIALOG-002 - Manager text is replayed to Gemini as prior model speech

- **Статус:** SOURCE-CONFIRMED.
- **Приоритет:** P1 after manager handoff semantics are clarified.
- **Trace:** `_build_history()` maps `InstagramBotMessage.Role.MANAGER` to
  Gemini `role="model"` with prefix `"Менеджер: "`. Manager takeover normally
  pauses automation, but stale takeover can auto-release after 12 hours and a
  later bot turn reuses the history.
- **Нежелательный effect:** a manual promise, price exception, personal
  wording or provisional statement appears to the model as something the bot
  itself said. On resume it can be repeated as a commitment without an
  authoritative fact, or a manager instruction can silently steer customer
  reply style/state.
- **Правильное решение:** manager content needs a separate context class:
  quoted operational note with author/time/evidence and explicit policy
  `not_customer_fact`, `not_bot_commitment` unless manager explicitly records a
  structured approved commitment. Bot resumption needs a reconciliation step:
  unresolved manual promise is either closed/confirmed by owner or shown as a
  safe clarification, never replayed as model authority.
- **Relation to old register:** `NEW-ANALYSIS-002` guards analysis snapshot
  subjectivity. This finding is distinct: it reaches the *live reply history*
  even when no analysis job runs.
- **RED/acceptance:** a manager note "give 30%" cannot make a later resumed bot
  offer 30%; a structured manager-approved offer can be referenced with its
  expiry/evidence. Plain manager text remains visible to operator but not as
  assistant speech.

### ADD-CODE-010 - Discount control is gated, but visible copy still describes an obsolete approval model

- **Статус:** SOURCE-CONFIRMED.
- **Приоритет:** P2; repair with `NEW-PROMPT-004`, not as isolated copywork.
- **Trace:** current scheduler requires approval for every nonzero
  `discount_percent`. Existing `price_d1` text tells the customer that 5% is
  the maximum "without separate approval".
- **Нежелательный effect:** no unauthorised discount is sent, but the customer
  receives a misleading explanation of the business rule. It weakens trust and
  makes any future analysis of approval/value framing ambiguous.
- **Correct change:** once a manager has approved the task, tell the truth in
  customer language: it is an individual approved offer with exact terms and
  expiry from authoritative facts. Never reveal internal approval workflow or
  imply automatic entitlement.
- **Acceptance:** copy is generated/selected from task approval state, has no
  false automatic threshold, and the test covers 5%, 10%, rejected and stale
  task states.

### ADD-PERF-001 - Seven background threads have no shared admission or connection budget

- **Статус:** SOURCE-CONFIRMED architecture risk; production severity is
  CALIBRATE.
- **Приоритет:** P1 before further background capability is added.
- **Trace:** one `run_instagram_bot --forever` process starts independent
  conversation refresh, analysis, recovery, permission transition, inbox
  refresh, lifecycle and follow-intelligence threads, plus the primary loop.
  Each correctly calls `close_old_connections()`, but no common connection/token
  budget, per-lane concurrency cap or global work admission controller is
  declared.
- **Нежелательный effect:** independently "bounded" workers can collectively
  exceed shared MariaDB/LSAPI/provider capacity. Adding an async function or
  Django 6.1 task blindly would increase parallelism, not throughput.
- **Django 6.1 implication:** the project already contains an opt-in durable
  Django Tasks adapter and intentionally rejects `ImmediateBackend` for heavy
  work. Reuse that explicit durable boundary only after the MariaDB engine and
  worker ownership gates in `02` are passed; do not replace the daemon with
  `asyncio` or enqueue work on the default immediate backend.
- **Correct design:** introduce an observable admission controller: global DB
  connection budget, per-lane provider budget, reserved live-reply capacity and
  age-aware background quotas. Worker state reports `admitted`, `deferred`,
  `blocked_by_budget` rather than silently competing.
- **Acceptance:** simulated slow analysis/lifecycle/refresh cannot consume the
  reserved live-reply slot; p95 DB connection count stays within configured
  budget; deferred work remains durable and fair.

## B. Agent capabilities that genuinely increase quality and conversion

The following are **EXTERNAL-BOOST** items. They are not "add another prompt".
Each creates a constrained feedback loop, a safer tool boundary or a clearer
customer decision. They should be shadowed and measured before any automatic
customer-facing rollout.

### ADD-AGENT-001 - Commitment ledger: model "yes/no" must resolve against one explicit offer

- **Problem:** natural customer confirmations are short: "так", "давай", "а
  якщо інший колір?". A long transcript may contain price, size, delivery,
  discount and manager statements. An LLM can infer intent, but it should not
  decide silently which business commitment is being accepted.
- **Capability:** create an episode-scoped `CustomerCommitment` projection for
  each customer-visible actionable offer: proposed product configuration,
  pay-link proposal, approved discount, manager handoff, requested proof or
  custom brief. Fields: type, immutable payload digest, source reply ID,
  expires/invalidates at, allowed confirmation phrases, owner and terminal
  status.
- **How agent uses it:** prompt sees at most one concise "active commitment"
  plus its safe next actions. Deterministic resolver can accept unambiguous
  confirmation; ambiguous "yes" after two live commitments triggers one
  clarification, not a guessed payment/discount action.
- **Why it is new:** `IgCheckoutProposal` handles a subset of checkout. This
  contract spans every high-consequence promise and does not replace funnel
  nodes, payment truth or manager approval.
- **Guardrails:** commitment never grants price/stock/payment truth; mutation
  requires typed authoritative state and idempotency key. An expired commitment
  cannot be resurrected by a later "yes".
- **Measurement:** ambiguous-confirmation rate, wrong-action correction rate,
  time from confirmation to valid action, cancelled stale commitments.

### ADD-AGENT-002 - Customer correction should execute a repair plan, not just overwrite a field

- **Problem:** "не L, а M", "не себе, а брату", "не этот товар" changes the
  validity of a proposal, queued follow-up, size advice and any already drafted
  customer message. A field update alone leaves hidden stale actions.
- **Capability:** emit a typed `CorrectionEvent` with customer message ID,
  resolved target, confidence, invalidated dependency IDs, cancelled action IDs
  and one repair-next-action. The reply first reflects the correction in natural
  language, then asks only the highest-value remaining question.
- **Why it boosts sales:** customers feel heard and stop repeating themselves;
  the system cannot continue selling an obsolete configuration. It turns error
  recovery into a trust-building moment rather than a branch failure.
- **Guardrails:** manager text/inference is not a customer correction; uncertain
  target is a clarification. Irreversible checkout changes require exact
  current proposal/line evidence.
- **Measurement:** stale action after correction, correction-to-repair latency,
  repeat correction, follow-up cancelled before provider I/O and conversion
  after repaired turns.

### ADD-AGENT-003 - Inter-reply contradiction firewall for bot commitments

- **Problem:** existing truth gates cover important individual claims, but a
  reply can still contradict a recent bot promise about size availability,
  delivery expectation, price exception or discount without any single claim
  looking invalid in isolation.
- **Capability:** extract only bounded operational claims from the candidate
  reply, compare them to current typed facts plus active commitments, then
  select `allow`, `rewrite_from_fact`, `clarify` or `manager_case`. Store a
  redacted conflict code, not free model reasoning.
- **Guardrails:** no regex/LLM inference becomes truth. Hard block only applies
  to authoritative fact conflicts; low-confidence semantic difference yields a
  safe clarification so false positives do not paralyse conversation.
- **Measurement:** contradicted bot commitments per 1,000 replies, true/false
  positive conflict rate, manager correction rate and factual refund/return
  correlation.

### ADD-AGENT-004 - Route the *decision mode*, not only the topic

- **Problem:** "покажи всё", "что лучше между этими", "беру, как оформить",
  "не подошло" can mention the same product but require opposite interaction
  styles. One sales prompt may be either pushy to a browser or passive to a
  ready buyer.
- **Capability:** derive a non-sensitive turn mode: `browse`, `compare`,
  `decide`, `reassure`, `service`. It controls evidence packet and reply
  structure, not commercial truth. Browse returns a transparent catalog path;
  compare gives a small differentiated shortlist with trade-offs; decide
  verifies configuration; service suppresses selling.
- **External basis:** routing is valuable when categories require specialised
  downstream workflows, but should be deterministic where possible rather than
  an opaque autonomous agent.
- **Guardrails:** client can always request full catalog; no universal "three
  choices" dogma, fake scarcity or suppression of inventory. Mode is reset on
  explicit customer correction.
- **Measurement:** turns-to-product link by mode, full-catalog requests after
  shortlist, change-of-mind, cancellation/return and manager takeover rate.

### ADD-AGENT-005 - Every uncertainty needs a resolver, evidence source and terminal state

- **Problem:** a polished answer that says "уточню" may create an unowned
  promise. Analysis already stores uncertainties, but a string alone does not
  tell system or manager how the uncertainty will end.
- **Capability:** `uncertainty_code -> authorised resolver -> expected
  evidence -> due/terminal state`. Examples: stock unknown -> authoritative
  availability read; special price -> manager decision; media ambiguity -> ask
  one customer question or manager case. Missing resolver immediately creates a
  visible handoff, not a repeated model loop.
- **Guardrails:** never state an ETA, stock, price or approval before evidence;
  resolver must be read-only or explicit manager action. A failed resolver
  degrades to a truthful customer status, not another AI guess.
- **Measurement:** uncertainty resolution rate/age, factual error after
  uncertainty, abandoned case rate and repeat-question rate.

### ADD-AGENT-006 - Human handoff needs an ownership protocol, not a 12-hour pause

- **Problem:** the current auto-release of stale manager takeover prevents a
  permanently silent bot, but it can also return automation while a human case
  still has an unresolved promise. External messaging policy makes a real human
  path operationally important, not merely a `manager_takeover=True` flag.
- **Capability:** explicit state machine: `requested -> claimed(owner,
  acknowledged_at) -> human_active -> return_pending -> bot_active`. A return
  is explicit owner release or a narrow new customer-entry rule with no active
  commitment, not only an idle timer.
- **Guardrails:** bot must not claim that a human will answer unless a durable
  owner/SLA case exists. Human text does not automatically become bot fact;
  `ADD-DIALOG-002` applies on resume.
- **Measurement:** p90 time-to-claim, unclaimed handoffs, auto-release while
  case remained open, customer re-entry, resolution and policy-invalid sends.

### ADD-AGENT-007 - Trace-first evaluation corpus must validate actions, not only elegant text

- **Problem:** golden dialogues alone can prove wording quality but miss a wrong
  pay-link, wrong manager handoff, stale action, duplicate send or policy bypass.
  A response that sounds excellent but mutates the wrong state is a failure.
- **Capability:** an anonymized replay scenario contains inbound turn, pre-state,
  admissible evidence/tools, expected action class, forbidden actions, expected
  final state, reply rubric and latency/cost budget. It replays code and mocks
  provider boundary; it never sends Meta/Telegram/customer events.
- **Why it differs from `01/02`:** this is not a prompt-only golden set. It
  checks trace, tool/action selection, idempotency and terminal state in one
  deterministic artifact.
- **External basis:** production agents benefit from traces, evaluations and
  feedback tied to system events, rather than a single subjective text score.
- **Guardrails:** raw transcript minimization, fixed redacted corpus, explicit
  versioning, no model-written expected outputs, and 100% pass for hard safety
  cohorts before a rollout.
- **Measurement:** factual/action/policy pass rate by cohort, regression delta
  by commit/prompt/model, p95 latency/cost and unsafe-action prevention rate.

### ADD-AGENT-008 - Manager correction should become trace-linked quality data

- **Problem:** a human often knows why a reply was wrong, but that correction
  may stay in chat/notification and never reach the evaluation loop.
- **Capability:** minimal `IgReplyQualityReview` linked to reply trace with
  labels `wrong_fact`, `wrong_recommendation`, `missed_question`, `too_pushy`,
  `wrong_language`, `handoff_needed`, plus corrected fact/action and evidence.
- **Why it boosts the agent:** improvements target recurring failure clusters
  from real management work instead of a team guessing which prompt tweak
  converted. It also creates a safe source for new evaluation cases.
- **Guardrails:** review never changes prompt/model automatically; label needs
  a reason/evidence; feedback is not training data export and retains no extra
  raw PII. Measure reviewer agreement before trusting a category.
- **Measurement:** review coverage for risk-sampled replies, label agreement,
  recurrence by cluster and post-fix reduction without worsening other cohorts.

### ADD-AGENT-009 - New sales policies need shadow decision and controlled rollout

- **Problem:** a higher conversion headline can hide more complaints, refunds,
  customer corrections, opt-outs or manual recovery. A fully automatic policy
  launch cannot establish causality.
- **Capability:** first calculate new next-best-action/offer policy in shadow
  mode without sending. Manager compares it with baseline. Then versioned small
  cohort rollout with holdout, explicit stop conditions and a kill switch. Every
  decision trace stores policy version.
- **Guardrails:** never experiment on verified payment, discount, inventory
  reservation, Meta-window eligibility or personally sensitive decisions without
  separate approval. Never create synthetic customer events to get a metric.
- **Measurement:** conversion *and* refunds/returns, correction, takeover,
  complaint/opt-out, p95 reply time, confidence interval and policy-version
  error budget.

### ADD-AGENT-010 - Context should earn its token budget through ablation, not intuition

- **Problem:** `NEW-MEM-005/008` correctly require retrieval, but a system can
  still keep adding "relevant" blocks until context becomes slow/noisy again.
- **Capability:** every per-intent context section carries authority, freshness,
  selection reason and token cost. Offline ablation removes one section at a
  time and evaluates fact recall, action correctness, hallucination/conflict and
  latency. Sections that do not improve a cohort lose default priority.
- **External basis:** agent context should be minimal, high-signal and loaded
  just-in-time; complicated context is not an automatic quality improvement.
- **Guardrails:** policy, payment/order and current authoritative facts are not
  eligible for token-only removal. Free narrative never wins priority only
  because it is long or recent.
- **Measurement:** prompt tokens, relevant-fact recall, conflict rate, p95
  model latency, cost per resolved turn and quality delta per ablation.

### ADD-AGENT-011 - Split read, decision and write tools behind a narrow orchestration boundary

- **Problem:** `instagram_bot.py` coordinates context, model, catalog, receipt,
  policy, follow-up and state changes. Broad helpers make it hard for a model or
  future developer to know which call is harmless and which one has side effect.
- **Capability:** adapter interfaces with explicit contracts:
  `read_authoritative_context`, `evaluate_readiness`, `propose_action`,
  `authorize_send`, `record_customer_fact`, `commit_effect`. Each write requires
  evidence, idempotency key, owner and policy/permission check.
- **External basis:** specialised, non-overlapping tools are easier for agents
  and people to use correctly than a large ambiguous toolbox.
- **Guardrails:** no big-bang rewrite. Start around the risky edge
  `candidate reply -> authorization -> send receipt`; preserve existing
  functions behind adapters and use contract tests.
- **Measurement:** duplicate side effects, hidden writes per turn, test
  isolation, tool selection failures, query count and latency.

### ADD-AGENT-012 - Customer-journey SLO must replace daemon-only health as the primary success signal

- **Problem:** heartbeat, a green key health card or one `daemon spawned` line
  cannot prove that a customer got a correct final outcome.
- **Capability:** define traces and SLOs for at least three journeys:
  sales reply, urgent support/handoff and lifecycle/customer event. A trace ends
  in `inbound persisted -> decision -> allowed send/policy block/human case ->
  provider receipt/unknown`, not merely in a background loop tick.
- **Guardrails:** a fast incorrect reply is not success. Error budget pauses new
  automated policy rollout, not existing customer support. Split p50 from p95/
  p99 and count terminal correctness separately.
- **Measurement:** durable ingress ratio, p95/p99 time-to-terminal, unknown
  delivery rate, handoff acknowledgement, policy blocks by reason and error
  budget burn by root cause.

### ADD-AGENT-013 - Operational cohort testing prevents average-quality blindness

- **Problem:** a global conversion or average response score can hide failures
  for media-only turns, language switch, long-idle re-entry, repeat buyer,
  manager-returned conversation, special product and complex checkout.
- **Capability:** report quality/safety per operational cohort only - no
  demographic profiling. Each cohort stores sample size and confidence; a
  material regression in a critical cohort blocks rollout even if average rises.
- **Guardrails:** no inference of sensitive attributes, no tiny-sample ranking,
  no individual customer performance score.
- **Measurement:** per-cohort factual failure, policy block, correction,
  p95 latency, handoff delay and completion/drop-off.

### ADD-AGENT-014 - Automation disclosure and re-entry expectation need a policy-tested customer contract

- **Status:** EXTERNAL-BOOST + policy calibration.
- **Problem:** current source does not expose a clear, versioned first-contact/
  handoff/resume disclosure contract. Meta's published policy recommends making
  automation clear; applicable law can require disclosure in some jurisdictions.
- **Capability:** a minimal locale-aware disclosure state: first automated
  interaction, long-idle re-entry and handoff from human to bot. It must be
  concise, not a marketing banner, and never claim human availability that the
  system cannot meet.
- **Guardrails:** policy/legal owner decides exact scope after checking active
  IG/Messenger app type and jurisdictions. Do not add repeated disclosure to
  every reply or use it as a substitute for a functional manager path.
- **Measurement:** disclosure delivery, confusion/"human?" rate, handoff
  acknowledgement and policy complaints.

## C. Integration order: what is safe to implement first

### Wave A0 - No customer-visible behaviour change, but removes blind spots

1. `ADD-CODE-003`: heartbeat work-lease model and watchdog regression.
2. `ADD-CODE-009`: move retention cleanup out of webhook ACK path.
3. `ADD-AGENT-007`: trace-first evaluation fixture format.
4. `ADD-AGENT-012/013`: customer journey SLO and cohort dashboards.
5. `ADD-SEC-001`: validation only, not a production probe.

### Wave A1 - Protect live customer correctness and latency

1. `ADD-CODE-001`: no silent tail loss.
2. `ADD-CODE-004`: deterministic cooldown acknowledgement/handoff path.
3. `ADD-DIALOG-001`: turn batching with explicit response SLA.
4. `ADD-CODE-007`: ageing/fairness queue policy after baseline metric.
5. `ADD-CODE-002`: global send lock redesign only with race tests and receipt
   proof.

### Wave A2 - Strengthen sales intelligence without risky persuasion

1. `ADD-AGENT-001/002/003`: commitment, correction and contradiction contracts.
2. `ADD-AGENT-004/005`: decision mode and uncertainty resolver.
3. `ADD-DIALOG-002` and `ADD-AGENT-006`: manager ownership/resumption.
4. `ADD-AGENT-008/009/010/011`: feedback, experiments, ablation and tool
   boundary.

### Wave A3 - Infrastructure and namespace hardening

1. `ADD-CODE-005/006`: robust mid-less identity and cache outage admission.
2. `ADD-DATA-001`: batch-safe erasure representation.
3. `ADD-CODE-008`: provider owner namespace/cutover design.
4. `ADD-PERF-001`: worker/connection budget after MariaDB engine validation.

## External sources and how they were used

1. [Meta Messaging Platform Policy](https://developers.facebook.com/documentation/business-messaging/messenger-platform/policy), checked 2026-08-26. It confirms the standard 24-hour response window, warns that some outside-window mechanisms are platform-specific, recommends communicating automation and requires timely response for applicable automated bots. It supports `ADD-AGENT-006/014`, not any claim that a human can bypass every Instagram constraint.
2. [Anthropic, Building Effective AI Agents](https://www.anthropic.com/engineering/building-effective-agents). It distinguishes predictable workflows from open agents, recommends simplest composable patterns and narrow well-documented tools. It supports `ADD-AGENT-004/011`, not a proposal to add an autonomous general agent.
3. [Google Cloud Agent Platform: Scale your agents](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale), checked 2026-08-26. It connects sessions/memory revisions, trace/feedback and continuous evaluation. It supports `ADD-AGENT-007/008/010/012` as engineering patterns, not a dependency on Google infrastructure.
4. [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework). It supports measuring trustworthiness throughout design, use and evaluation; it motivates `ADD-AGENT-009/013`.
5. Chernev, Böckenholt, Goodman, [Choice overload meta-analysis](https://doi.org/10.1016/j.jcps.2014.08.002). It supports testing choice-mode behaviour rather than imposing a universal number of products in `ADD-AGENT-004`.

## Handoff acceptance checklist

- [ ] Every selected finding has a current-`main` source trace, not an old
  checkout line number.
- [ ] Source-confirmed defects get one minimal RED regression before change.
- [ ] Security candidate gets local policy validation and provider-contract
  review, not a live attack attempt.
- [ ] No rollout sends synthetic customer/Meta/Telegram events.
- [ ] Any customer-facing sales policy passes shadow comparison, cohort safety
  check and explicit stop condition.
- [ ] Any Django 6.1 task/async change proves durable queue ownership; default
  `ImmediateBackend` is not treated as background execution.
- [ ] Production proof records server SHA, time window, metric definition and
  redaction; local SQLite does not stand in for MariaDB concurrency or provider
  delivery.
