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
