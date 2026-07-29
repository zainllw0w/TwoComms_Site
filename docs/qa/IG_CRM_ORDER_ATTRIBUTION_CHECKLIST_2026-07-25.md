# Instagram CRM order attribution checklist

Scope: payment-review alerts, conversation-derived order drafts, product/fit/size
evidence, manager confirmation, existing-order linking, and production MariaDB
behavior.

## Master plan status

- [x] **Task 1 — Payment decision truth and rejection lifecycle.** Shipped in
  `18bc49bf`; manager/provider truth remains separate and auditable.
- [x] **Task 2 — Order attribution, existing-order linking, and item
  provenance.** Shipped in `7a319f4f`; production migration `0104`, InnoDB
  tables and append-only triggers verified.
- [x] **Task 3 — Nova Poshta validation and fulfillment gates.** Shipped in
  `e805ec7f`; text-only delivery fails closed, signed-directory Refs survive to
  `Order`, and production migration `0105` is verified on MariaDB.
- [x] **Task 4 — Client workspace API contract.** Shipped in `fcea1668`; the
  bounded client/orders contract, explicit order resolution, permissions and
  production MariaDB/runtime behavior are verified.
- [x] **Task 5 — Responsive workspace, client drawer, and `Замовлення` UX.**
  Shipped in `bed00422`; product approvals no longer live in the general
  overview and the dedicated section/client drawer use one verified contract.
- [x] **Task 6 — Repeat-order commercial episodes and fulfillment-aware history.**
  Implemented locally in the current release slice. One Instagram client may
  have many immutable order/funnel episodes; payment confirmation never creates
  a duplicate order. Release commit/deploy evidence is tracked below.
- [ ] **Task 7 — Pattern episodes and honest analytics.** Raw duplicate signal
  counters must become evidence-bound episodes/outcomes.
- [ ] **Task 8 — Telegram action/media audit and final release verification.**

## Existing-order and repeat-order acceptance

- [x] Confirming payment changes only payment-review truth; it does not create or preselect an order.
- [x] A confirmed review without an order remains in `Потрібна дія` as `needs_order_resolution`.
- [x] The manager explicitly chooses `Прив'язати існуюче` by exact order number or `Створити нове` through the editable form.
- [x] An order already created manually can be linked to the review/deal/client without creating a duplicate.
- [x] The persistence model permits one Instagram client to own many distinct attributed orders; one canonical order has at most one active Instagram attribution.
- [x] The custom admin shows Instagram origin plus client display name when available and retains a durable IG UID reference/digest.
- [x] The client workspace shows every linked order number, date, amount, payment, shipment/TTN and creation mode, with a new-tab custom-admin link.
- [x] Every linked order belongs to one distinct auditable commercial episode; review count and order count remain separate and physical orders are counted by distinct `order_id`.
- [x] A repeat purchase starts a new episode-scoped funnel while every completed stage timeline, product/price fact, payment decision, order and evidence snapshot remains unchanged.
- [x] Explicit repeat intent is classified separately from a first purchase and is available to analytics/statistics.
- [x] Order-status replies resolve an exact order number or TTN across deal-linked and attribution-only orders and use Order/Nova Poshta truth; ambiguous multi-order references create one clarification task instead of guessing.
- [x] Exact existing-order linking blocks cancelled orders and requires a structured manager override for fulfilled/shipped or payment-incompatible orders.
- [x] Automatic provider-verified payment creates one idempotent attributed order only after validated products, negotiated totals and canonical delivery data are complete; otherwise it creates manager work without a duplicate.
- [x] Negotiated line prices, agreed order total, requested payment amount and actually paid provider/manager amount remain separate and scoped to the exact client episode; no runtime fixture amount or previous-client value is reused, and arbitrary valid prepayments are not coerced to `200 грн`.
- [x] Automatic, manager-created and linked-existing orders expose distinct creation modes while sharing the same client/order history contract.

## Task 5 UX acceptance

- [x] The dedicated `Замовлення` tab is placed after statistics, shows the action count and supports `Потрібна дія`, `Підтверджені`, and `Усі` selections without mounting approval cards in the general overview.
- [x] A review card keeps product screenshots, receipt screenshots, custom-print references and unknown images in separate labelled groups; negotiated conversation prices are visually primary over catalog prices.
- [x] The manager sees one explicit route: `Перевірка оплати` -> `Прив’язка замовлення` -> `Виконання`; after payment confirmation, the same selected card stays open and clearly activates the order-resolution step.
- [x] `Прив’язати існуюче` is visually primary for an order already created in custom admin; `Створити нове` remains a separate deliberate action and payment confirmation alone never opens or creates another order.
- [x] The client drawer shows the same pending action and chronological order history, but counts only rows with a real canonical `order.id`.
- [x] Every linked order row shows number, date, negotiated/order amount, payment truth, order status, shipment/TTN status, creation mode and a new-tab custom-admin link.
- [x] Username/display name is shown first when available; stable Instagram UID remains visible as fallback and navigation identity.
- [x] Desktop and mobile browser acceptance covers 1440, 1280, 768, 390 and 320 px, keyboard/focus, Escape, reduced motion, long Ukrainian text, no horizontal overflow, no nested scroll trap and no console errors.

Task 5 browser evidence: fresh authenticated local browser runs confirmed the
direct `review` deep-link, the full-payment mutation into
`needs_order_resolution`, retained `review:3` selection, focused exact-order
input within the first mobile viewport, separate create-new link, client drawer
focus trap/Escape restoration, grouped media, linked-order history, zero
horizontal overflow at all five target widths, 320 px single-page scrolling,
reduced-motion suppression and zero console errors/warnings.

## Task 6 durable episode acceptance

- [x] Add an immutable commercial episode owned by one Instagram client and connected to its deal, payment review/decision, intended order, attribution, stage events, product/price evidence and outcome.
- [x] A client may have zero, one or many episodes and orders; one order cannot silently belong to two different episodes, while replay inside the same episode remains idempotent.
- [x] Starting a repeat purchase creates a new current episode and restarts only that funnel. Completed episodes remain visible as dated cards with order number, amount, outcome and source.
- [x] Repeat intent such as `хочу ще`, reorder, gift or another recipient is evidence-bound, versioned and available to analytics without inference from language, profile style or perceived wealth.
- [x] The AI status resolver can use attribution-only orders without `IgDeal`, selects by exact order number/TTN, and asks a clarifying question when several orders fit.
- [x] Shipment notifications, `shipped_notified_at`, payment decisions and next actions are scoped to the exact episode/order and cannot update another order of the same client.
- [x] The custom admin order card displays Instagram source, automatic/manual/linked creation mode, client display name when known and durable UID-backed navigation to the management client.
- [x] The client workspace keeps only two primary panes (clients + conversation); commercial context/settings open in an explicit right drawer.
- [x] The conversation has one compact, single-row funnel above the transcript; manager/bot/customer colors remain distinct and action-required cards pulse without duplicating facts.
- [x] The chat header restores the evidence-bound client-potential indicator (band, probability, confidence and clear label), including cold/lost/opted-out/spam states; verified payment and physical order state are shown separately and never derived from potential.
- [x] Existing-order linking offers compact searchable order cards with date, client, items, amount, payment/shipment state and source; selecting a card binds the exact order to this client/episode and keeps exact-number input as an audited fallback.
- [x] The payment/client drawer has one viewport-bounded scroll surface: all product images, receipt screenshots, evidence/history and bottom actions are reachable at 1440/1280/768/390/320 px, with no nested scroll trap or sticky-action overlap.
- [x] Strict duplicate payment reviews for one client, receipt/payment evidence, currency, total, items and delivery converge on one canonical review/order; a changed receipt or commercial fingerprint remains a separate purchase episode.
- [x] Legacy duplicate reviews preserve audit history as `superseded`, point to the canonical review/order, disappear from the action queue and replay idempotently without creating a second order or attribution.
- [x] Exchange and return are separate post-sale cases attached to the existing client/order/episode; they never rewind payment truth or create another purchase/order.
- [x] Explicit customer exchange/return messages take priority over the generic paid-waiting category, create one evidence-bound case and merge later details into that active case idempotently.
- [x] A post-sale case auto-selects an order only when exactly one durable Instagram attribution exists; multiple orders require manager selection and orders attributed to another client are rejected.
- [x] The conversation shows a compact action-required exchange/return state above the transcript; the right drawer exposes order, original fit/size, desired size, evidence, manager note and lifecycle controls without adding a third permanent pane.

Task 6 local verification (2026-07-26): the final repeat/payment/order/shipment/UI
acceptance suite passed **555 tests** with 2 expected skips. `manage.py check`,
`makemigrations --check --dry-run`, scoped `compileall`, inline JavaScript syntax
validation and `git diff --check` passed. The MariaDB lock-order regression test
`test_all_order_resolution_paths_lock_review_before_projection` passed, proving
automatic materialization and manual create/link acquire review before projection.
Migration-window regressions prove that several reviews in one connected component
converge to one episode, a review written by an old worker after initial backfill is
promoted safely after restart, and the mandatory daemon reconciliation reports zero
unmaterialized deals, reviews and attributions. Independent code-quality re-review
returned `APPROVED`.
The broad `management` suite ran 1471 tests with 14 failures and 3 errors; a
clean detached base SHA ran 1379 tests with 15 failures and 3 errors, and every
remaining failure is a pre-existing unrelated baseline contract. No new Task 6
failure remains.

Task 6 amount/linking follow-up verification (2026-07-26): legacy manager
confirmation without an exact amount now enters `amount_clarification` in the
action queue. The append-only clarification links only to conversation messages
containing the exact amount and never falls back to a receipt or watermark.
Ambiguous multi-item totals stay unallocated until a manager enters positive
line prices; no automatic equal split is invented. Authenticated browser QA at
1440, 390 and 320 px confirmed the transition from clarification to the compact
existing-order selector and separate create-new action, complete receipt/history
reachability and zero page-level horizontal overflow. The preview scenario linked
the already shipped `TWC24072026N01` through a structured historical override;
the database retained exactly one order and connected review, client and
attribution to it. The related suite passed **254 tests** with 2 expected skips;
`manage.py check`, migration drift, scoped compilation, strict inline JavaScript
syntax and `git diff --check` also passed.

Task 6 production release proof (2026-07-26, commit `02e577ab`): production
MariaDB `11.4.12` was backed up to a validated `0600` gzip archive before deploy;
the server is on the deployed SHA with migrations through `0108`, `manage.py
check`, collectstatic/compress, Passenger restart, playbook seed, daemon ensure,
and bounded payment polling completed. Review `2` for client `59` was clarified
append-only with `2100.00` UAH and amount evidence `[237]`; receipt message `238`
and watermark `242` are not amount evidence. Existing order `296`,
`TWC24072026N01`, was linked with `historical_fulfilled_order`; its two lines are
`1050 + 1050`, attribution mode is `linked_existing`, the client/episode/order
references are consistent, and the physical order count remained exactly `51`.
Production staff API returned `200` with one physical order, the exact order URL,
separate receipt/product media groups, and the same evidence IDs. `/healthz/`
returned `200`; daemon heartbeat was fresh and pending notification/analysis
queues were zero. The focused local regression set passed **187 tests** with 2
expected skips.

Task 6 duplicate/post-sale follow-up local proof (2026-07-26): strict payment-review
fingerprints canonicalize the historical double-review case without weakening
real repeat-order isolation. The post-sale model/API/UI keeps exchange and return
on the existing order and exposes one manager action in the client queue and
drawer. The connected payment-review/order-link/commercial-episode/client-UI/
taxonomy/post-sale suite passed **207 tests**. `manage.py check`, migration drift,
scoped compilation and `git diff --check` passed. Production proof is recorded
only after the MariaDB backup, migrations `0109`/`0110`, deploy and live API/DB
reconciliation complete.

Task 6 final production proof (2026-07-26, commits `edef71bd` and `762b7816`):

- [x] MariaDB backup completed before each deploy; the final archive
  `/home/qlknpodo/db_backups/daily/qlknpodo_MySQL_DB-20260726.sql.gz` is gzip-valid,
  mode `0600`, and was published at `2026-07-26T16:05:36+03:00`.
- [x] Production is on `762b7816`; migrations `0109` and `0110` are applied,
  `manage.py check`, collectstatic/compress, Passenger restart, playbook seed,
  commercial-episode reconciliation and daemon ensure all completed.
- [x] Client `59` has exactly one physical order (`296`,
  `TWC24072026N01`) and one append-only attribution (`id=2`,
  `creation_mode=linked_existing`). Review `2` is canonical and review `1` is
  `superseded_by=2`; no second order or attribution was created.
- [x] The client-detail API now reports `orders.count=1` and
  `orders.attribution_count=1`, and two repeated staff requests both return one
  order card `(order_id=296, review_id=2)`.
- [x] `/healthz/` returned `200`; daemon heartbeat age was about 4 seconds and
  pending notification/analysis queues were `0/0`.
- [x] Exchange/return remains evidence-bound: production history had no stored
  customer exchange message, so no guessed post-sale case or size was created.

The backend card deduplication fix was added after live verification found that
the frontend hid duplicate review cards while the API still returned both. The
regression suite was rerun after that fix: **209 tests passed**, with no failures;
`manage.py check`, migration drift, scoped compilation and `git diff --check`
also passed.

Task 6 Yana visibility follow-up (2026-07-26, production release `cd24e6fd`):

- [x] Root cause was reproduced from production truth without mutating business
  data: client `59` has raw stage `paid`, one real physical order `296`
  (`TWC24072026N01`), one canonical confirmed review `2`, and one durable
  `linked_existing` attribution. Reopening confirmation or detaching the order
  would be incorrect and could create another duplicate.
- [x] Manager-confirmed order truth now keeps the client visibly paid even when
  provider truth is independently `unverified`; the UI labels those two sources
  separately instead of showing the contradictory `Потребує звірки оплати`.
- [x] The main chat keeps a persistent compact linked-order strip after the
  action review closes, including manager confirmation, order number, amount,
  fulfillment status, TTN, creation mode and the custom-admin order link.
- [x] Orders workspace badges exclude superseded audit reviews and count distinct
  canonical physical orders consistently with rendered cards.
- [x] Conversation-level exchange detection now covers colloquial
  `поміняти` / `поменять` wording through a red-green regression test.
- [x] Connected client/payment/order/commercial-episode/post-sale suite passed
  **191 tests** with no failures.
- [x] Authenticated production browser QA confirms the Yana card exposes the
  manager-confirmed label, separate provider/manager truth, one persistent
  linked-order strip for `TWC24072026N01`, and the exact custom-admin link to
  order `296`; desktop and 390/320 px mobile widths had no horizontal overflow
  and browser console/page errors were empty.
- [x] Production MariaDB was backed up before release; server SHA is `5c82465d`,
  migrations are current, `/healthz/` returns HTTP 200, daemon is running, and
  notification/analysis queues are empty. The temporary browser-QA staff user
  was deleted and the Yana business rows remained unchanged.
- [ ] Production exchange case remains intentionally absent until the actual
  customer message is stored. Current production evidence has no new message or
  raw event after message `242`; manually inventing a case would violate the
  evidence-bound post-sale contract.
- [ ] Restore `IG_APP_SECRET` in the runtime environment and resolve Graph
  polling failures (`conversations HTTP 500`, `poll_messages http_-1`), then
  verify a fresh signed inbound message creates the exchange case on the sole
  attributed order `296` without duplicating the order.

Task 6 active-conversation regression follow-up (2026-07-26):

- [x] Reproduced the disappearance with a RED API test: once a client gained a
  manager-confirmed linked order, the default `active` filter excluded the
  client even though the conversation and messages remained stored.
- [x] The default client workspace now keeps all non-hidden, non-spam and
  non-cold conversations available after payment; `Оплачені` remains an
  additional focused view rather than the only place to find a paid client.
- [x] The regression test confirms a manager-confirmed `linked_existing`
  order stays visible in the default conversation list without a deep-link
  `client_id` override.
- [x] Focused regression and the connected client/payment/post-sale suite pass
  (88 tests), along with Django system check, migration drift and diff checks.

## Completed in this slice

- [x] Explicit `PRODUCT`/`ITEM` IDs are authoritative; missing or unpublished IDs fail closed.
- [x] Malformed or conflicting control tags reject the complete PAYLINK payload.
- [x] Multi-item payloads validate quantity, item count, duplicate identity, fit, size, variant ownership, stock, and effective Fable5 price.
- [x] Negotiated prices require seller/customer acceptance evidence and message IDs; ambiguous multi-item allocation fails closed.
- [x] Deal line totals are persisted and order materialization verifies that line totals equal the declared deal total.
- [x] Manager-only receipt confirmation creates an unpaid preparation order and never a provider Purchase event.
- [x] Provider payment truth remains separate from manager evidence truth.
- [x] Existing-order linking is exact-number, idempotent, client-safe, commercial-fingerprint checked, and override-reason coded.
- [x] Existing-order links use the absolute storefront custom-admin URL; new orders use the manual-order form.
- [x] Attribution and link events are append-only at ORM and database-trigger layers; direct Instagram identity snapshots are replaced with an HMAC digest.
- [x] MariaDB/MySQL paylink creation is serialized per Instagram client with `GET_LOCK`/`RELEASE_LOCK`; non-MariaDB fallback locks are weakly held.
- [x] Migration `0104` trigger creation is resumable for the trigger phase and does not remove `0103` payment-decision guards on rollback.
- [x] Focused order/payment/manual-order tests, migration-enabled payment-review tests, Django checks, migration drift checks, compilation, and diff checks pass.
- [x] Client workspace and `Замовлення` APIs share one bounded card contract for reviews, attributed orders, grouped media, negotiated draft lines, payment sources, fulfillment, decisions, direct storefront-admin links, and Telegram/workspace deep-links.
- [x] Hidden clients and Meta-reviewer-only accounts cannot read commercial workspace data; staff/admin access is enforced.
- [x] Active action-required reviews are selected independently from the bounded 20-row history, so older pending/order-resolution work is never hidden by newer terminal reviews.
- [x] Untrusted JSON evidence is whitelisted and bounded by type, field, string length, ID-list length, item count, media count, and trusted URL policy.
- [x] Task 4 verification passed: 35 focused UI/API tests, 104 related client/payment/order-link/review tests, Django check, migration drift, compilation, diff check, and independent code-quality re-review (`APPROVED`).
- [x] Task 4 production proof: server SHA `fcea1668`, MariaDB `11.4.12`, no pending migrations, one live daemon with approximately six-second heartbeat, empty notification outbox and analysis queue, `/healthz/` `200`, management/API anonymous boundaries `302`, and read-only staff orders API `200` with counts `action=2`, `confirmed=1`, `all=2`.
- [x] Task 5 local proof: 86 focused UI/payment tests and 260 related client/payment/order/manual-order tests passed (2 expected skips), plus Django check, migration drift, scoped compilation, inline JavaScript syntax and diff checks; independent spec/code-quality reviews returned `APPROVED` and the visual reviewer returned `PASS` after a fresh-server 320 px recheck.
- [x] Task 5 production proof: `bed00422` is on `origin/main` and production `main`; MariaDB reports `11.4.12-MariaDB`, migrations through `0105` are applied, collectstatic/compress/Passenger restart and playbook seeding succeeded, the single daemon is online with approximately 1.1-second DB/cache heartbeat, pending queue/notification outbox/analysis jobs are all zero, `/healthz/` is `200`, and public bot/orders boundaries are `302`.
- [x] Production client `1735898131060065` remains explicit-resolution-only after the UX deploy: two confirmed reviews, zero order attributions, and staff Orders API `200` with counts `action=2`, `confirmed=2`, `all=2`; no order was auto-created or auto-linked by payment confirmation.

## Required follow-up before broad analytics rollout

- [ ] Make the full `0104` schema/backfill migration resumable after an interrupted MariaDB DDL step, not only its trigger phase.
- [ ] Define and implement retention/scrubbing for order-linked attribution and link-event rows when a customer requests DIRECT_BOT deletion.
- [ ] Add a production MariaDB smoke that inspects `SHOW TRIGGERS`, migration state, and a transaction-level append-only rejection without mutating real business rows.
- [ ] Add browser coverage for the Telegram-to-management confirmation flow, absolute existing-order navigation, and post-mutation refresh failure handling.
- [ ] Continue product-image classification and catalog matching audit with stored evidence thumbnails and explicit custom-print/interest versus purchase intent states.
- [ ] Add funnel/signal aggregates with Ukrainian labels, resolution state, evidence IDs, manager involvement, and no duplicate counting across deal episodes.

## Task 6 active-chat ingress and live-funnel follow-up (2026-07-26)

- [x] Added a visible `Усі` conversation view that includes every non-hidden
  conversation, including paid, cold, spam and completed histories; `Активні`
  remains the bounded work queue and no longer hides completed paid clients.
- [x] Incremental chat polling now returns the operational stage and funnel
  projection, and the browser applies those values to the open header/funnel
  without discarding the transcript. A linked `ship` order therefore projects
  `Замовлення створено`, while raw analysis stage remains available as `stage_raw`.
- [x] The daemon now persists `last_poll_at` for a successful poll cycle and
  records provider/refresh failures as `polling:*`; status separates daemon
  heartbeat from inbound availability and exposes `ingress_degraded`.
- [x] The production shipment-payment smoke exposed a missing `timezone` import
  in the attribution-only manager-review path; the import is restored and a
  regression test now proves an outside-window episode creates one skipped
  manager task without attempting an automated send.
- [x] Focused verification passed **205 tests** for clients/UI, daemon,
  webhook security, polling, commercial episodes and shipment, plus **171
  related payment/order/post-sale tests** (2 expected skips). `manage.py check`,
  migration drift, scoped compilation, inline JavaScript syntax and
  `git diff --check` passed.
- [x] Reproduced the stale-cache false-positive with RED tests: a failed later
  conversation-discovery page and an incomplete message page preserved safe
  data/cursors but emitted no durable degradation signal, so a later successful
  read of old cached conversation IDs could incorrectly restore `running`.
- [x] Conversation refresh and message polling now publish independent,
  page-scoped, bounded-TTL degradation evidence with a redacted reason and
  timestamp. A complete fresh conversation snapshot clears only refresh
  degradation; a complete error-free message cycle clears only polling
  degradation. A budget-limited round-robin cycle cannot clear prior evidence.
- [x] `ingress_status()` now gives fresh degradation evidence precedence over a
  fresh `last_poll_at`; daemon liveness therefore remains visible without
  claiming inbound availability or allowing the top-level state to become
  `running`.
- [x] Independent review reproduced a malformed shared-cache timestamp crashing
  the status path. Cache timestamps are now normalized fail-safe while retaining
  the degradation signal, with a RED/GREEN regression proving the management
  status remains available.
- [x] Ingress telemetry verification passed **155 focused tests**, the expanded
  client/UI, daemon, webhook, polling, commercial-episode and shipment set
  passed **210 tests**, and the related payment/order/link/post-sale set passed
  **177 tests** with 2 expected skips. `manage.py check`, migration drift,
  scoped compilation and `git diff --check` passed.
- [ ] Production inbound delivery is not yet restored by code alone: the
  runtime still needs the real `IG_APP_SECRET`, and Meta polling currently
  reports Graph `conversations HTTP 500` / `poll_messages http_-1`. Keep the
  webhook fail-closed; after credentials/provider recovery, verify a fresh
  signed Yana message reaches `InstagramBotMessage`, updates analysis and
  creates an evidence-bound exchange case without a duplicate order.

## Task 7A webhook-first ingress and analysis contract (2026-07-26)

- [x] Architectural decision recorded in
  `docs/plans/2026-07-26-instagram-webhook-first-ingress-design.md`; the detailed
  TDD/release sequence is in
  `docs/plans/2026-07-26-instagram-webhook-first-ingress.md`.
- [x] Chosen architecture is signed-webhook primary plus bounded adaptive
  recovery polling. Webhook-only and permanent short Graph polling are rejected
  for recoverability and quota/permission reasons respectively.
- [x] Context7 MCP availability was checked and is absent in this runtime. The
  official Meta rate-limit and Messaging documentation URLs, confirmed facts
  and the boundary between provider fact and our operational policy are recorded
  in the design instead of inventing Context7 results.
- [x] Recovery fallback parameter slice verified locally: conversation
  discovery uses `limit=10`, message reads allow the production-evidenced
  12-second timeout, and no customer-specific values are embedded. Fresh clean
  runs passed 22 polling tests, 264 expanded ingress/UI/daemon/webhook/analysis/
  shipment tests, and 123 payment/order/post-sale tests with 2 expected skips.
  `manage.py check`, migration drift, scoped compile and `git diff --check`
  passed. Production deploy evidence is recorded after backup/release below.
- [x] Webhook POST persists/deduplicates and schedules work before returning
  `200`, with no classifier, Gemini, Graph, media download or notification
  transport on the HTTP path. The signed endpoint regression covers duplicate
  delivery, durable message/job creation and all forbidden I/O boundaries.
  If durable scheduling fails, customer and manager persistence rolls back and
  the endpoint returns `503` so Meta can retry; a repeated manager `mid` is a
  complete no-op for the message, job, notification and takeover epoch.
- [x] Removed the per-request background thread. Durable daemon workers, not an
  unbounded Passenger thread per webhook, own reply and analysis processing.
- [x] Rule classification is deferred to the daemon: active customer messages
  classify before Gemini, while bounded reconciliation classifies manager,
  paused and reply-disabled bursts before high-reasoning analysis.
- [ ] Customer, manager and bot messages all advance one durable per-client
  analysis watermark. A 30-second debounce coalesces a burst; manager/model
  roles never generate a customer reply.
- [x] Local transcript recovery now persists validated historical user and
  page-side messages without reply/classifier side effects, retains fetched
  pages when a bounded recovery cycle is incomplete, and advances polling
  cursors only after a complete traversal.
- [x] Client detail exposes `before_id` cursor metadata and a compact
  "Завантажити старішу історію" control; the initial 300-message window can
  be walked backwards without any Graph request from the UI.
- [x] Profile enrichment is batch/cooldown based: the daemon refreshes bounded
  name/username/profile-picture batches and stores local avatar copies; a
  manual `refresh_ig_profiles` command is available for controlled backfill.
- [x] Manager takeover and explicit opt-out stay immediate local routing
  barriers. Manager evidence is higher-priority operational evidence but is not
  rewritten as customer intent.

Task 7B polling recovery, provenance and profile enrichment (2026-07-29):

- [x] A validated customer message found during an incomplete recovery traversal
  enters the normal idempotent queue exactly once; the next complete traversal
  cannot lose it through the unique Meta `mid`, and the cursor still advances
  only after complete persistence.
- [x] Historical customer messages remain observed-only, while page-side history
  is stored as `MANAGER` evidence. A new page-side message uses the same atomic
  takeover/pause barrier as webhook echoes; known bot echoes remain `MODEL`.
- [x] Meta `created_time` is stored separately as `provider_created_at`; the chat
  API renders provider time with a local-ingest fallback, preserving chronology.
  Webhook and polling sender/message IDs fail closed at MariaDB column limits.
- [x] Profile refresh is bounded, independent of the reply-enabled gate, and
  persists exponential per-client backoff plus explicit `no_token` and
  `permission_denied` batch states. Manual `--force` can override client backoff.
- [x] Evidence links now auto-page up to 20 local history requests, report a
  deterministic not-found state, and prepend older rows in provider order.
- [x] Local Task 7B gate passed: polling 30, profiles 10, client/UI 87, daemon
  47, webhook-shape 15, webhook-security 9, intelligence 28, post-sale 10,
  payment 25 and shipment 10 tests; `manage.py check`, migration drift,
  compile and diff checks passed.
- [x] Production secret configuration is corrected (2026-07-29): the App ID
  `2120980214971807` and App Secret shown in the Meta Basic settings screenshot
  were verified as a pair; the Graph app probe now returns HTTP 200. The value
  is stored in the selected `.env.production` (0600) and CloudLinux app env,
  Passenger and the daemon were restarted, and both runtime fingerprints match.
- [ ] Production signed webhook acceptance remains open: before the correction,
  Meta POSTs from `facebookexternalua` reached `/bot/webhook/` with HTTP 403
  `bad_signature`. No genuine post-correction non-role inbound has appeared in
  the access log yet. Verify one real event through signed webhook -> queue ->
  analysis -> reply without a synthetic event, then close this gate.
- [x] Production deploy evidence (2026-07-29): `main` is at `b470cd06`,
  migration `0111_instagrambotmessage_provider_created_at` is applied,
  `manage.py check --deploy` is clean, `/healthz/` returns HTTP 200, the
  Instagram daemon has one `--forever` worker with a fresh heartbeat, and
  pending/processing queues are both zero. MariaDB backup
  `qlknpodo_MySQL_DB-20260729.sql.gz` was created before the migration.
- [ ] Profile enrichment and all-recipient live messaging remain externally
  blocked: a real page-token request for client `1735898131060065` returned
  Meta `403 (#200) App does not have Advanced Access to
  instagram_manage_messages...`; the profile batch therefore reports
  `permission_denied`. Grant the approved current permission to the actual
  app/token (or complete the Instagram Login migration), refresh the page token,
  then rerun the profile batch and one consenting non-role end-to-end message.
- [ ] Recovery discovery uses the page-scoped endpoint, small pages, cursors,
  request/time budgets, adaptive backoff, jitter, Meta error classes and usage
  headers. Permission/configuration failures must not be retried every few
  seconds.
- [x] Production token-path smoke (2026-07-29): the configured system-user
  token is valid and `/me/accounts` returns the configured Page plus its Page
  Access Token; `/{page_id}/subscribed_apps` returns HTTP 200 with `messages`.
  A bounded refresh found 2 conversation IDs and `poll_ingest` checked both
  conversations in 2 requests with `degraded=False` and `enqueued=0`. Directly
  using the system-user token on a Page endpoint correctly fails with Graph
  `(#190)`, so the Page-token exchange must remain the only polling path.
- [ ] Chat UI reads MariaDB-backed incremental APIs only, pauses/backs off in a
  hidden tab, and never causes a Meta Graph request.
- [ ] List card, chat header, one-row funnel, review drawer and incremental chat
  use the same operational projection. Receipt claim, pending/approved/rejected
  manager review, provider truth, linked order and fulfillment remain visibly
  distinct; diagnostic `stage_raw` cannot falsely label pending evidence paid.
- [ ] Production acceptance requires a fresh signed inbound event. Until the
  real app secret and Advanced Access exist, show `ingress_degraded`; never use
  faster polling to conceal the external blocker.

### Task 7A release evidence (2026-07-26)

- [x] Recovery parameter slice shipped in `efef6b444dc9083e3dfe38c13078cfe1458b9fcc`.
- [x] A fresh MariaDB backup was created before deploy: archive
  `qlknpodo_MySQL_DB-20260726.sql.gz`, 19,931,867 bytes, gzip validation passed,
  mode `0600`.
- [x] Production deploy completed with migrations clean, `manage.py check`
  clean, static/compress complete, Passenger restarted and the singleton bot
  daemon ensured.
- [x] Live verification: deployed SHA matches, `/healthz/` returned `200`,
  daemon was online, ingress status was `available`, pending inbound messages,
  analysis jobs and notification outbox were all `0`, and effective Gemini
  model was `gemini-3.6-flash`.
- [x] Production source confirms `CONV_PAGE_LIMIT = 10` and
  `POLL_MESSAGE_TIMEOUT = 12`; no customer-specific value is embedded.
- [ ] A fresh signed inbound event has not yet been used as acceptance proof;
  do not mark webhook-first delivery fully complete until one real event is
  stored, analyzed and reflected in the local chat/funnel.

Task 7A persistence-only webhook local verification (2026-07-26): a single
focused gate covering signed endpoint/security/extraction, conversation
analysis and intelligence, daemon, notification outbox, client API, takeover
and manager-echo regressions passed **252/252**.
`manage.py check`, migration drift, scoped compilation and `git diff --check`
passed. Three stale rules-v4 assertions in `tests_ig_intelligence` were updated
to the already-shipped rules-v5 taxonomy (`checkout`, collaboration, B2B,
support and community); no production classifier behavior was weakened.

Task 7A persistence-only webhook production evidence (2026-07-26): commit
`1aad45461092159201d527f4e5a7eca56cabd245` was deployed after a fresh verified
MariaDB archive (`qlknpodo_MySQL_DB-20260726.sql.gz`, 19,934,306 bytes, gzip
valid, mode `0600`). Migrations pending were `0`; `manage.py check`,
collectstatic, compressor and Passenger restart completed; exactly one daemon
was online with a 4.4-second heartbeat. `/healthz/` returned `200`; inbound,
analysis and notification queues were all empty; the effective model was
`gemini-3.6-flash`. An unsigned webhook POST returned `403` and changed no
message rows. Client `59` remained visible and linked only to order `296`
(`TWC24072026N01`, 2100.00, paid, shipped). Production still has no
`IG_APP_SECRET`, so signed webhook acceptance remains open and ingress is
currently available through bounded recovery polling; this external/config
blocker is not represented as a completed signed-event proof.
