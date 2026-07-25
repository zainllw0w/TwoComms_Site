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
- [ ] **Task 4 — Client workspace API contract.** Next: one bounded contract
  for client context plus the separate `Замовлення` queue/count and actions.
- [ ] **Task 5 — Responsive workspace, client drawer, and `Замовлення` UX.**
  Product approvals must not live in the general overview; they are available
  in the dedicated section, client workspace, and Telegram deep-link.
- [ ] **Task 6 — Pattern episodes and honest analytics.** Raw duplicate signal
  counters must become evidence-bound episodes/outcomes.
- [ ] **Task 7 — Telegram action/media audit and final release verification.**

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

## Required follow-up before broad analytics rollout

- [ ] Make the full `0104` schema/backfill migration resumable after an interrupted MariaDB DDL step, not only its trigger phase.
- [ ] Define and implement retention/scrubbing for order-linked attribution and link-event rows when a customer requests DIRECT_BOT deletion.
- [ ] Add a production MariaDB smoke that inspects `SHOW TRIGGERS`, migration state, and a transaction-level append-only rejection without mutating real business rows.
- [ ] Add browser coverage for the Telegram-to-management confirmation flow, absolute existing-order navigation, and post-mutation refresh failure handling.
- [ ] Continue product-image classification and catalog matching audit with stored evidence thumbnails and explicit custom-print/interest versus purchase intent states.
- [ ] Add funnel/signal aggregates with Ukrainian labels, resolution state, evidence IDs, manager involvement, and no duplicate counting across deal episodes.
