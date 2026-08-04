# 05_DATA_AND_EVENT_CATALOG — данные и события

## Канонические сущности

| Сущность | Роль | Источник истины | Примечание |
|---|---|---|---|
| `IgClient` | Instagram customer card | CRM + arbiter projection | stage is mutable; history is not inferred from it |
| `InstagramBotMessage` | inbound/outbound durable message | message row + send state | provider receipt/unknown boundary |
| `IgCommercialEpisode` | repeat-order episode | episode lifecycle | статистика должна считать episode, не client snapshot |
| `IgDeal` / `IgDealItem` | proposal and selected items | deal/payment contract | selected variant price is immutable per item |
| `IgPaymentProjection` | provider payment truth | verified webhook/backstop | refund/reversal is terminal negative truth |
| `IgFollowUpTask` | scheduled touch/manager task | event key + claim token | current claim layer; provider-evidenced delivery FSM is IMP-102 |
| `IgObjection` / `IgObjectionAttempt` | objection lifecycle | verified attempt evidence | `[OBJHANDLE]` fingerprint is validated |
| `IgLifecycleEvent` | event-driven post-payment state | lifecycle event row | event consumers must be idempotent |
| `IgOrderAssignment` | IG ↔ existing order link | append-only assignment audit | manager-owned/manual contract |
| `IgOrderShipment` | shipment history | append-only shipment journal | avoids overwriting exchange history |
| `ProductColorVariant` | color/material/variant identity | catalog variant | price/stock must be variant-aware |
| `VariantSizeRule` / `SizeGrid` | fit and size availability | fit/size rule | white variant data remains absent in production |
| `ProductSalesSemanticProfileRevision` | verified aliases/traits revision | append-only manager authority | generic aliases and unauthoritative revocation are rejected |
| `ProductInventoryPolicy` | source of stock truth per product | explicit warehouse/untracked policy | 77 production rows: 29 warehouse, 48 untracked |

## Current and planned event vocabulary

| Event family | Examples | Current status |
|---|---|---|
| inbound | `message_received`, `echo_received`, `reaction_only` | durable/current |
| reply | `reply_generated`, `reply_sent`, `reply_unknown`, `reply_blocked` | durable/current |
| funnel | stage transition, product switch, checkout/readiness | journal/FSM current; analytics `IMP-058` |
| payment | `checkout_started`, `payment_confirmed`, `payment_reversed`, `invoice_expired` | payment truth and event-time analytics current |
| follow-up | policy step, claim, provider receipt, ambiguous delivery, manager review, cancelled | claim layer current; delivery FSM/event materialization IMP-102/103 |
| fulfillment | payment → delivery request, TTN, exchange shipment, delivered | current in W4/W4B/W6 slices |
| objection | opened, handled, reopened, resolved/abandoned | `IMP-057` current |
| drop-off | silence, explicit refusal, opt-out, unreachable, spam, superseded | model/statistics `IMP-058` |

## Data invariants

- A confirmed payment is one purchase; a refund/reversal does not create a second
  order and a partial refund does not erase the purchase.
- A payment link is generated only from the selected product/variant/fit/size
  decision. The conversation price and checkout price must come from one read model.
- No outbound customer message is sent after a manager/permission epoch change.
- Ambiguous provider outcomes are never replayed automatically.
- Superseded payment-review links retained for audit are not ownership edges and
  cannot merge their terminal episode with the canonical fulfilled episode.
- Local SQLite does not prove MySQL foreign-key, length, engine or lock behavior.

## Missing or partial data

`F-DATA-015` imported-role provenance and `F-DATA-016` white product variant
remain explicitly open. `F-STAT-001…004` event analytics and `F-PAY-014`
superseded invoice polling are closed by `IMP-058`/`IMP-089` with production
evidence. No backfill is inferred from text where authoritative evidence is
absent.

`IMP-081` is partial rather than open: its semantic revision and inventory
policy tables are deployed on InnoDB with append-only triggers, but the full
catalog graph/admin/runtime consumer and disposable MariaDB test gate remain.

`IMP-082/083` have a deployed immutable graph/ranker foundation, and
`e44d1440`/`0ad694bc` close F-CAT-007 by making the prompt price/size contract
variant-specific. Product 110 is now `variant_id=81`, thermo green, 1450 грн,
oversize XS/M. The graph is still not the durable runtime commerce-session
source; stale binding, relaxed alternatives and full topology remain.

Follow-up scheduling currently has event keys and claim tokens but not the
complete delivery truth required after an ambiguous provider boundary.
`IMP-102` adds `PROCESSING/SENT/AMBIGUOUS/COMPLETED`, lease recovery, provider
receipt and manual resolution without blind retry. `IMP-103` materializes exact
`event_key`/payload and an absolute policy timeline, then rechecks invoice or
restock truth immediately before send so stale scheduled facts cannot escape.
