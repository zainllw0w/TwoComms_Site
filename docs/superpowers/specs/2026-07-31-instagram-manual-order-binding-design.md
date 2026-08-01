# Instagram Manual Order Binding Design
**Status:** Approved by the user's instruction to decide autonomously and finish end to end
**Date:** 2026-07-31
**Primary surface:** desktop management Instagram inbox

## 1. Outcome

A manager can open any active Instagram conversation, search a website order by
its exact order number, bind that order to the Instagram client, and undo an
incorrect binding with an explicit reason. Automatic Monobank/assisted-checkout
materialization uses the same current-binding service, so the UI shows one
consistent owner and a truthful origin regardless of how the link was created.

The feature also exposes the canonical Nova Poshta operation for the bound
order. When a tracking number is present, the customer-facing shipment and
delivered-review events are localized from the client's stored language and are
processed idempotently.

## 2. Non-negotiable invariants

1. `IgOrderAttribution` remains append-only commercial/payment provenance. It
   is never edited or deleted to implement an operational correction.
2. `IgOrderAssignment` is the authoritative current client-to-order edge.
   One order has at most one current assignment row.
3. A link to an order assigned to another client returns HTTP 409. The manager
   must unlink first; no silent reassignment is allowed.
4. Every mutation locks the `Order` and assignment, checks `expected_version`,
   and writes an append-only `IgOrderAssignmentEvent` with actor, source,
   before/after client, reason, version, and a PII-minimal snapshot.
5. Automatic attribution may create or confirm an assignment, but it never
   overwrites a different active owner.
6. Manual binding never changes order payment fields, client paid truth, deal
   payment truth, or analytics Purchase state.
7. Unlinking changes current operational ownership only. Historical payment
   attribution and audit records remain visible.
8. Hidden clients and cancelled orders cannot receive new manual assignments.
9. Customer messages are generated from stored locale (`uk`, `ru`, `en`),
   honor send-policy boundaries, and use durable dedupe keys.
10. The management UI never calls Nova Poshta directly. It opens the existing
    staff-only action which mints the canonical signed operation URL.

## 3. Data model

### IgOrderAssignment

- `order`: one-to-one canonical `orders.Order`
- `client`: nullable current `IgClient`; null means deliberately detached
- `source`: `provider_auto`, `checkout_auto`, `manager_payment_review`,
  `manager_manual`, `manager_created`, or `legacy_attribution`
- `assigned_by`: nullable management user
- `assigned_at`, `unassigned_at`
- `version`: monotonically increasing optimistic-concurrency token
- `last_reason_code`, `last_reason`
- timestamps

The row is mutable only through `management.services.ig_order_assignments`.

### IgOrderAssignmentEvent

Append-only event fields:

- unique `operation_id`
- assignment, order
- `kind`: `linked`, `unlinked`, `auto_confirmed`
- from/to clients
- actor and actor source
- assignment source, reason code/text, resulting version
- bounded JSON snapshot and timestamp

ORM update/delete is rejected. A migration backfills assignments from existing
`IgOrderAttribution` rows without changing attribution.

### IgOrderCustomerEvent

A durable customer notification for directly or automatically assigned orders:

- unique `event_key`
- assignment/version, order, client
- `kind`: `ttn_assigned` or `delivered_review`
- locale and immutable rendered text/tracking snapshot
- state, due time, attempts, lease token/expiry
- provider message id, last error, completion timestamps

The producer reconciles current assignment plus order truth. The worker claims
before provider I/O, revalidates assignment/version and send permission, then
marks sent, waiting/manual-review, ambiguous, cancelled, or failed.

## 4. Service and API contract

`link_order_to_client(...)`:

1. Resolve an exact `order_number`; partial identifiers are selector-only.
2. Lock order, assignment, and relevant immutable attribution.
3. Reject cancelled orders, hidden clients, stale versions, and another active
   owner.
4. Return the existing result for a repeated `operation_id` or exact same link.
5. Persist assignment and audit event without changing payment semantics.
6. Enqueue a localized TTN event when the order already has a tracking number.

`unlink_order_from_client(...)`:

1. Lock and verify assignment, client, and expected version.
2. Require a structured reason and explanatory note.
3. Set current client to null, increment version, append event, and cancel any
   unsent customer events tied to the old version.

Endpoints:

- `POST /bot/api/clients/<client_id>/order-assignments/`
- `POST /bot/api/clients/<client_id>/order-assignments/<id>/unlink/`
- existing candidate GET is extended to assignment-first ownership

Stale version and ownership conflicts return 409 with a stable error code.
Validation returns 400; missing records return 404; authentication/role checks
continue using `_require_admin_json`.

## 5. Desktop UI

The conversation header receives a compact 36px package-link icon before the
advanced-profile control. It is always available for an active client and has a
tooltip, `aria-label`, visible focus state, and a numeric/current-state marker.

The existing client drawer becomes the order-management surface:

- current bound orders with number, items, total, payment/order status;
- quiet origin line: automatic source or manager name and timestamp;
- TTN state with tracking link and canonical create/delete action;
- secondary unlink action requiring reason and confirmation;
- exact-number search with keyboard-focusable unavailable results and a
  human-readable server reason;
- `Create new order` link carrying client context to the existing staff manual
  order form.

The compact green order strip above the conversation remains, now reflecting
current assignment instead of immutable attribution alone. No animation is
used for stable states and the layout is optimized for 1440x900 and 1920x1080.

## 6. Notification copy

TTN assigned:

- UK: `Ваше замовлення відправлено. ТТН Нової пошти: {ttn}. Відстеження: {url}`
- RU: `Ваш заказ отправлен. ТТН Новой почты: {ttn}. Отслеживание: {url}`
- EN: `Your order has been shipped. Nova Poshta tracking number: {ttn}. Track it here: {url}`

Delivered review:

- UK/RU/EN concise thanks plus a request for an honest review or an Instagram
  story mention with the product. The copy does not promise compensation and
  does not pressure the customer.

Unknown language falls back to Ukrainian. Messages snapshot locale and content
at enqueue time so a retry cannot silently change wording.

## 7. Failure and concurrency behavior

- Two managers linking one free order: one succeeds, the other receives 409.
- Stale drawer after another mutation: version mismatch, reload required.
- Repeat POST with the same operation ID: returns the original result.
- Link to the same client without operation ID reuse: idempotent, no duplicate
  audit event.
- Unlink with pending notification: event is cancelled before send.
- Provider timeout with unknown delivery: event becomes ambiguous/manual review
  and is not replayed automatically.
- Outside response window or paused/taken-over client: create one manager task,
  do not mark the customer message as sent.
- Manual TTN without Nova Poshta document ref opens order edit; API-created TTN
  opens the canonical delete flow.

## 8. Verification

- model/service/API tests for manual, automatic, idempotent, stale-version,
  conflict, unlink, re-link, and immutable-audit behavior;
- localized event producer/worker tests for UK/RU/EN and policy boundaries;
- current-reader regressions for client detail, orders workspace, post-sale,
  shipment, and automatic attribution;
- migration drift, Django check, focused and related management/order suites;
- Playwright keyboard and visual flows at 1440x900 and 1920x1080;
- production MySQL migration, deployed SHA, assignment/event counts, daemon and
  command smoke, and a no-send reconciliation dry check.
