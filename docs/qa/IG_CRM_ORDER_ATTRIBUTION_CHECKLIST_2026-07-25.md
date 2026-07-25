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
- [ ] **Task 5 — Responsive workspace, client drawer, and `Замовлення` UX.**
  Product approvals must not live in the general overview; they are available
  in the dedicated section, client workspace, and Telegram deep-link.
- [ ] **Task 6 — Repeat-order commercial episodes and fulfillment-aware history.**
  One Instagram client may have many immutable order/funnel episodes; payment
  confirmation must never create a duplicate order.
- [ ] **Task 7 — Pattern episodes and honest analytics.** Raw duplicate signal
  counters must become evidence-bound episodes/outcomes.
- [ ] **Task 8 — Telegram action/media audit and final release verification.**

## Existing-order and repeat-order acceptance

- [x] Confirming payment changes only payment-review truth; it does not create or preselect an order.
- [x] A confirmed review without an order remains in `Потрібна дія` as `needs_order_resolution`.
- [x] The manager explicitly chooses `Прив'язати існуюче` by exact order number or `Створити нове` through the editable form.
- [x] An order already created manually can be linked to the review/deal/client without creating a duplicate.
- [x] The persistence model permits one Instagram client to own many distinct attributed orders; one canonical order has at most one active Instagram attribution.
- [ ] The custom admin shows Instagram origin plus client display name when available and retains a durable IG UID reference/digest.
- [x] The client workspace shows every linked order number, date, amount, payment, shipment/TTN and creation mode, with a new-tab custom-admin link.
- [ ] Every linked order belongs to one distinct auditable commercial episode; review count and order count remain separate and physical orders are counted by distinct `order_id`.
- [ ] A repeat purchase starts a new episode-scoped funnel while every completed stage timeline, product/price fact, payment decision, order and evidence snapshot remains unchanged.
- [ ] Explicit repeat intent is classified separately from a first purchase and is available to analytics/statistics.
- [ ] Order-status replies resolve an exact order number or TTN across deal-linked and attribution-only orders and use Order/Nova Poshta truth; ambiguous multi-order references create one clarification task instead of guessing.
- [ ] Exact existing-order linking blocks cancelled orders and requires a structured manager override for fulfilled/shipped or payment-incompatible orders.
- [ ] Automatic provider-verified payment creates one idempotent attributed order only after validated products, negotiated totals and canonical delivery data are complete; otherwise it creates manager work without a duplicate.
- [ ] Automatic, manager-created and linked-existing orders expose distinct creation modes while sharing the same client/order history contract.

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

- [ ] Add an immutable commercial episode owned by one Instagram client and connected to its deal, payment review/decision, intended order, attribution, stage events, product/price evidence and outcome.
- [ ] A client may have zero, one or many episodes and orders; one order cannot silently belong to two different episodes, while replay inside the same episode remains idempotent.
- [ ] Starting a repeat purchase creates a new current episode and restarts only that funnel. Completed episodes remain visible as dated cards with order number, amount, outcome and source.
- [ ] Repeat intent such as `хочу ще`, reorder, gift or another recipient is evidence-bound, versioned and available to analytics without inference from language, profile style or perceived wealth.
- [ ] The AI status resolver can use attribution-only orders without `IgDeal`, selects by exact order number/TTN, and asks a clarifying question when several orders fit.
- [ ] Shipment notifications, `shipped_notified_at`, payment decisions and next actions are scoped to the exact episode/order and cannot update another order of the same client.
- [ ] The custom admin order card displays Instagram source, automatic/manual/linked creation mode, client display name when known and durable UID-backed navigation to the management client.

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
- [x] Production client `1735898131060065` remains duplicate-safe: two reviews exist, one confirmed review is `needs_order_resolution`, and zero `IgOrderAttribution` links exist until the manager explicitly selects the already-created order or chooses create-new.

## Required follow-up before broad analytics rollout

- [ ] Make the full `0104` schema/backfill migration resumable after an interrupted MariaDB DDL step, not only its trigger phase.
- [ ] Define and implement retention/scrubbing for order-linked attribution and link-event rows when a customer requests DIRECT_BOT deletion.
- [ ] Add a production MariaDB smoke that inspects `SHOW TRIGGERS`, migration state, and a transaction-level append-only rejection without mutating real business rows.
- [ ] Add browser coverage for the Telegram-to-management confirmation flow, absolute existing-order navigation, and post-mutation refresh failure handling.
- [ ] Continue product-image classification and catalog matching audit with stored evidence thumbnails and explicit custom-print/interest versus purchase intent states.
- [ ] Add funnel/signal aggregates with Ukrainian labels, resolution state, evidence IDs, manager involvement, and no duplicate counting across deal episodes.
