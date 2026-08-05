# Instagram Legacy Order Resolution Design

## Context

The management Orders workspace currently exposes a manager payment decision for
Instagram payment reviews. The ordinary `full_payment` and `prepayment` paths
must know the negotiated order total before they can authorize any order
execution or order linking. Legacy reviews created from old conversations can
contain a receipt amount while lacking a saved deal or negotiated total. The UI
currently offers the ordinary action anyway, producing the fail-closed error:
`Повна вартість замовлення не визначена; підтвердження не може авторизувати виконання.`

Production currently has four canonical pending orderless reviews, one already
confirmed review, and twenty-three superseded duplicates. Two pending reviews
have recoverable amounts (`1760` and `1550`); two do not have a trustworthy
numeric amount. The business instruction is to record all four as old completed
sales, without inventing local orders or financial totals.

## Goals

1. Keep ordinary payment confirmation fail-closed and make the missing-total
   requirement visible and actionable.
2. Add an explicit, auditable legacy-completion operation for a sale that was
   already paid and received before the Instagram bot workflow existed.
3. Preserve separate facts for negotiated total, paid amount, provider truth,
   order linkage, and fulfillment outcome.
4. Make the Orders workspace progress blocks and action variants truthful for
   pending, normal confirmed, linked, reconciled, and historical-completed
   states.
5. Reconcile the current production backlog through a bounded, explicit-ID,
   dry-run-first command.

## Non-goals

- Do not remove the normal full-payment/prepayment amount checks.
- Do not fabricate an `orders.Order` for a historical sale.
- Do not mutate Monobank/provider projections from a manager decision.
- Do not emit a new Purchase, Meta event, customer message, or new-order
  Telegram notification for historical completion.
- Do not treat an unknown historical amount as zero, an estimate, or revenue.

## Decision Model

### Normal confirmation

The manager form will show two money inputs:

- `order_total_amount`: the full negotiated order value;
- `confirmed_amount`: the amount actually verified in the evidence.

The total is prefilled from the review/deal/evidence when available. The server
stores both values in the append-only decision and preserves the existing rules:

- full payment requires a positive total and an equal confirmed amount;
- prepayment requires a positive total and a smaller confirmed amount;
- provider conflicts still enter reconciliation and block order actions.

### Historical completion

The action `historical_paid_fulfilled` is available only for a visible,
orderless, legacy-compatible review. It requires:

- a staff management actor;
- one fulfillment outcome: `already_received`, `already_delivered`, or
  `completed_unknown`;
- an operator reason;
- either a positive verified amount or an explicit declaration that the amount
  cannot be recovered.

The action appends a manager decision with verification scope
`historical_fulfilled`, marks the review as confirmed, archives it using the
existing `historical_paid_archived` resolution, closes the commercial episode
as fulfilled, resolves its manager notification, and records the selected
outcome. A missing amount remains missing in all financial projections and
analytics. For the new UI flow the client is moved to the completed stage; the
existing internal archive service keeps its backwards-compatible default for
older callers.

The operation is rejected for hidden clients, linked orders, active checkout
proposals, cancelled/reversed provider truth, and replay attempts with a
different decision. A replay of the same completed resolution is idempotent.

## API and Service Boundaries

- Extend `IgPaymentReviewDecision.VerificationScope` with
  `historical_fulfilled`.
- Add nullable decision fields for the separately audited order total and its
  source.
- Add a typed review resolution outcome field.
- Extend `record_review_decision()` with `order_total_amount` and the historical
  scope branch; normal callers continue through `resolve_review_payment_amount`.
- Extend the existing archive service with an explicit outcome and an opt-in
  completed-stage transition; preserve its current default behavior.
- Extend `bot_payment_review_action_api` with the new action and structured
  validation error codes. No raw status update or direct SQL bulk mutation is
  allowed.
- Add a bounded management command that accepts explicit review IDs, actor,
  outcome, reason, optional per-review paid amounts, and `--apply`. Default is
  dry-run; every row reports `eligible`, `skipped`, or `applied` with a reason.

Derived conversation-analysis scheduling will be moved behind an
`transaction.on_commit()` boundary so a worker/queue failure cannot roll back
an already recorded operator decision.

## Orders Workspace UX

- Normal reviews show separate total and paid fields and focus the missing
  field when validation fails.
- Legacy-compatible reviews show a distinct historical-completion panel with
  outcome, optional known amount, explicit unknown-amount choice, and required
  reason. The normal action remains available only when its prerequisites are
  satisfied.
- Historical-completed cards get a named green state, display the outcome and
  resolution note, show all progress steps complete, and say that a local order
  is not required. They never render a create/link CTA.
- `amount_clarification`, `payment_reconciliation`, and linked-order states keep
  their existing blocking copy and actions.
- Proposal filter headings and counts become mutually consistent so the upper
  Orders blocks do not describe one state while showing another.

## Side-Effect Contract

Normal manager confirmation may update manager truth, client stage, episode
payment state, and analysis scheduling. Historical completion additionally
closes the episode and alert, but must not create or mutate an Order, Purchase,
provider projection, Meta event, customer message, or new-order notification.

## Verification Strategy

Tests will cover:

1. ordinary unknown-total confirmation still fails;
2. ordinary confirmation succeeds when the manager supplies a total and the
   amount matches its scope;
3. historical completion succeeds with a known amount;
4. historical completion succeeds with an explicitly unknown amount while
   preserving empty financial amount fields;
5. hidden, linked, active-checkout, provider-conflict, non-staff, invalid,
   mismatched, and replay cases are rejected or idempotent as specified;
6. no Order/Purchase/Meta/customer/Telegram side effect is created by the
   historical path;
7. dry-run/apply bulk command behavior and repeat safety;
8. API payloads, inline JavaScript contracts, responsive action reachability,
   focus/error placement, and truthful progress states.

Local checks will include targeted management tests, related payment/order tests,
Python compilation, JavaScript syntax, Django check, migration drift, and
`git diff --check`. Production verification will prove the deployed SHA,
migrations, daemon/heartbeat, review counts/resolution states, and absence of
unexpected outbound events before and after the bounded reconciliation.
