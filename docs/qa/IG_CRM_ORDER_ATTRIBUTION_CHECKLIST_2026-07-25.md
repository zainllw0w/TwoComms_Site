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
- [ ] The custom admin shows Instagram origin plus client display name when available and retains a durable IG UID reference/digest.
- [ ] The client workspace shows every linked order number, date, amount, payment, shipment/TTN and creation mode, with a new-tab custom-admin link.
- [ ] One Instagram client can own many orders; every order belongs to a distinct auditable commercial episode.
- [ ] A repeat purchase starts a new funnel episode while completed funnel/history/evidence remains unchanged.
- [ ] Explicit repeat intent is classified separately from a first purchase and is available to analytics/statistics.
- [ ] Order-status replies resolve the correct linked order and use Order/Nova Poshta truth; ambiguous multi-order references escalate for clarification.

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
