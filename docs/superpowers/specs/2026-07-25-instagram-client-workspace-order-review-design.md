# Instagram Client Workspace and Order Review

**Status:** approved by owner direction on 2026-07-25.

## Goal

Give managers one evidence-bound Instagram client workspace where conversation ownership, interpretation, payment truth, fulfillment, products, and linked orders are visible as separate facts. A manager can verify a manual payment claim, reject it with a durable reason, create a reviewed order draft, or link an existing order without losing product, price, media, attribution, or Nova Poshta provenance.

## Non-negotiable truth boundaries

- `IgPaymentProjection` remains provider-only. It records Monobank/provider observations and never changes because a screenshot or model says paid.
- A manager decision is a separate source-qualified payment truth: `manager_verified`, `manager_rejected`, or `evidence_accepted_provider_unverified`.
- Only `provider_verified` or explicit `manager_verified` can authorize fulfillment. A receipt without a manager decision cannot.
- Customer intent and preferences come from customer evidence. Manager text can establish negotiated commercial facts or an operator observation, but never customer intent or provider truth.
- Hidden clients are excluded from operational analysis and actions. Paused or manager-led clients remain observable and analyzable.
- Nova Poshta free text is a suggestion until canonical settlement/warehouse refs are validated by the existing directory contract.

## UX architecture

The client view becomes a desktop three-pane workspace: client list, role-labelled conversation timeline, and a sticky commercial context rail. The first viewport shows client identity, automation owner, funnel stage, payment truth, fulfillment/order state, and one next action.

The context rail order is:

1. `Потрібна дія`: pending payment review with a restrained pulse and a one-click drawer entry.
2. `Чернетка замовлення`: product cards with catalog links, fit, color, size, quantity, negotiated line/total price, evidence, and uncertainty.
3. `Пов’язані замовлення`: order number, items, order value, paid value, payment source, creation origin, shipment state, and TTN.
4. `Аналіз`: one category, probability/confidence, model/rules version, evidence disclosure, and uncertainties.
5. `Патерни`: episode summaries with occurrence count, resolution state, evidence, and outcome. Raw signal counts are never the primary label.

On narrow screens, the list, chat, and context become separate screens with a segmented control; the payment review opens as a full-screen sheet and its primary action remains sticky. No nested scroll trap is permitted. The review dialog supports Escape, focus return, keyboard actions, reduced-motion, and long Ukrainian labels.

## Payment review workflow

`Pending -> manager_verified` or `Pending -> manager_rejected` is one atomic, idempotent decision. Rejection requires a reason code and optional comment. The decision stores actor, timestamp, evidence watermark, verification scope, and previous/current state. Confirming or rejecting schedules truth reanalysis and a stage event; it does not mutate provider ledger data.

The Telegram alert uses one callback action bound to the exact delivered review message and authorized staff actor. It independently delivers product and receipt media with captions and catalog links. Media delivery failure never rolls back the decision and remains retryable.

## Order and attribution model

The first implementation introduces management-owned projections rather than widening the broad retail `Order` contract:

- `IgPaymentReviewDecision`: append-only decision history with source, reason, actor, and evidence watermark.
- `IgOrderAttribution`: one order can have one active Instagram attribution projection, preserving client/deal/review IDs, IGSID/username snapshot, channel, creation mode, payment verification source, and evidence version.
- `IgClientOrderLink`: append-only link/unlink history for one client to many orders; fuzzy candidates remain review-only.

`IgDealItem` gains fit/option and price provenance snapshots so classic/oversize, color, quantity, negotiated prices, and source messages survive materialization. `IgDeal` gains validated Nova Poshta refs and a validation state. Automatic fulfillment refuses text-only destinations and unresolved price/product allocation.

## Pattern model

Existing `IgConversationSignal` rows remain immutable observations. New pattern occurrences, episodes, and transitions project them into operator-friendly facts:

- occurrence: semantic key, actor/origin, message evidence, confidence, and rules/model version;
- episode: one size/price/payment/custom-print issue with open/resolved/unresolved/superseded status;
- transition: actor, reason, evidence, and outcome.

Statistics distinguish unique users, occurrences, episodes, resolved episodes, verified payments, orders, order value, paid value, refunds, and shipments. Every metric exposes denominator, exclusions, timezone `Europe/Kiev`, date semantics, and sample size.

## Language

Explanatory copy is Ukrainian. Exact technical/product names remain English: `live`, `ENV`, `API Key`, `API`, `Conversions API`, `Meta Test Event Code`, `Checkout started`, and catalog names. Raw internal enum values are never rendered without a localized label.

## Delivery slices

1. Payment decision model, review API/detail payload, and TDD for manager verification/rejection.
2. Existing-order linking and Instagram attribution with idempotent services.
3. Nova Poshta canonical refs, fit/price provenance, and fulfillment gates.
4. Client workspace and responsive payment drawer.
5. Pattern episodes and honest aggregate statistics.
6. Telegram callback/media audit hardening and end-to-end/browser/production verification.

Every slice uses RED -> GREEN -> REFACTOR, focused Django tests, related Instagram/Gemini/chat suites, `manage.py check`, migration drift, compile/diff checks, then commit, push, production migration/static/restart/daemon verification, and deployed-SHA proof.
