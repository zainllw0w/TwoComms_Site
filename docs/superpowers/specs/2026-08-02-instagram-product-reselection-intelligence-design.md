# Instagram Product Reselection and Catalog Intelligence

**Date:** 2026-08-02
**Status:** Approved direction; written specification awaiting review
**Surface:** Instagram Direct sales conversation and assisted checkout proposal creation

## 1. Outcome

The Instagram bot must let a customer browse, ask product questions, replace a
rejected selection, configure another garment, and return to checkout at any
point without being trapped by an earlier product or payment intent.

The system must understand natural Russian, Ukrainian, and English sales
language, but it must never let a language model invent a sellable SKU,
availability, product construction, print placement, price, or payment link.
Natural-language understanding proposes structured constraints; deterministic
catalog, warehouse, and checkout services decide what can be offered and paid.

When several verified products satisfy the known request constraints, the bot
shows at most three configurable candidates and asks the customer to choose.
It describes exact availability only after size, color, fit, and quantity can be
allocated. It automatically selects a product only when the customer supplies a
trusted exact product URL or the catalog resolver finds one unique match.

## 2. Incident Contract

The production incident for `zainllw0w` defines the minimum regression path:

1. a pink Reality Bends T-shirt is rejected as unavailable;
2. the customer asks for a standard black classic T-shirt;
3. the old product must stop participating in every subsequent decision;
4. asking for the oversize size guide must answer the information request and
   must not retry checkout;
5. saying `not Reality Bends`, `without a back print`, or sending the canonical
   `classic-tshirt` URL must replace the old product context;
6. a trusted URL must resolve to its published product regardless of stale CRM
   `intent=payment` or `current_product_id`;
7. no identical unavailable response may be sent repeatedly;
8. a proposal URL may be created only after the new product configuration and
   authoritative availability are complete.

No implementation or production verification may send a test message to this
real customer. Tests use fixtures, mocks, or a dedicated non-customer account.

## 3. Design Principles

- **Current turn before historical intent.** The latest customer action is more
  important than a persistent `payment` intent left by an earlier turn.
- **Conversation is reversible.** Product, garment type, fit, color, size, and
  quantity can be changed independently without restarting the whole dialog.
- **Exact evidence before inference.** A trusted URL outranks text matching;
  structured catalog data outranks generated descriptions.
- **AI interprets, code authorizes.** Gemini may extract constraints and explain
  choices, but it never returns the authoritative product ID or availability.
- **Unknown is not unavailable.** Missing catalog-to-warehouse evidence opens a
  manager-review path rather than producing a false out-of-stock claim.
- **One useful next step.** Every blocked state offers a verified alternative,
  asks one discriminating question, or escalates once to a manager.
- **Idempotent effects.** Reprocessed inbound messages cannot create duplicate
  replies, proposals, reservations, or escalation work.

## 4. Source-of-Truth Boundaries

### 4.1 Authoritative commerce data

The following data may authorize a candidate or proposal:

- published `storefront.Product` identity, category, price, media, and canonical
  slug;
- active `ProductFitOption`, size-grid rules, and Fable option compatibility;
- `ProductColorVariant` identity and color, but not raw stock for warehouse-
  backed garments;
- verified semantic sales profiles described in section 5;
- `VariantBlankLink` and `warehouse.StockItem` for blank garment availability;
- active Instagram checkout reservations and committed paid allocations;
- immutable checkout proposal snapshots and verified payment state.

### 4.2 Non-authoritative evidence

Free text such as product descriptions, SEO keywords, `metadata.bot_vision`, and
Gemini output may help recall or rank candidates. It cannot independently prove
that a garment has no back print, has a front logo, uses an elastic hem, is in
stock, or is payable.

`ProductColorVariant.stock` remains valid only for catalog variants explicitly
configured to use catalog-variant stock. It must not be treated as the retail
stock source for a variant linked to warehouse blanks.

## 5. Catalog Knowledge Graph

This design uses a typed in-process knowledge graph built from the existing
relational catalog. A separate graph database is unnecessary at the current
catalog size and would create a second source of truth.

### 5.1 Graph nodes

- product;
- category or garment type;
- color variant;
- fit;
- size;
- semantic trait;
- print and print placement;
- warehouse blank family and concrete `StockItem`;
- canonical product URL and customer-visible media.

### 5.2 Graph edges

Examples include:

- product `IS_A` garment type;
- product `SUPPORTS` fit and size;
- product `HAS_VARIANT` color;
- product `HAS_TRAIT` verified semantic value;
- product `USES_PRINT` print at chest, back, sleeve, or another placement;
- variant plus fit `USES_BLANK_FAMILY` through `VariantBlankLink`;
- blank family plus size and color `ALLOCATES_FROM` a `StockItem`;
- product `HAS_CANONICAL_URL` and `HAS_MEDIA`.

### 5.3 Verified semantic profiles

Add a stable `ProductSalesSemanticProfile` identity for a product and
append-only `ProductSalesSemanticProfileRevision` records. A revision stores a
versioned and validated schema rather than arbitrary prompt text:

- localized aliases for Ukrainian, Russian, and English;
- design family, such as `plain_logo` or a named collection;
- front decoration: `none`, `logo`, or `print`;
- back decoration: `none`, `logo`, or `print`;
- construction traits such as standard hem or elastic hem;
- other controlled merchandising traits needed by the candidate engine;
- status: `draft`, `verified`, or `revoked`;
- verification source, verifier, verification time, and schema version.

The admin editor validates controlled codes and aliases and creates a new
revision instead of mutating verified history. Existing structured print links
may seed decoration evidence. Descriptions and `bot_vision` may seed an
unverified review suggestion, but an automated backfill must never mark them
verified. Transitions and proposals store the exact verified revision IDs and
normalized trait values used, not only a mutable profile pointer or graph
digest.

The profile is intentionally limited to semantic facts not already represented
by product, fit, color, size, print, or warehouse models.

Add an explicit `ProductInventoryPolicy` with `warehouse`, `catalog_variant`,
or `untracked` source. The policy is required for checkout stock truth. A
missing `VariantBlankLink` under a warehouse policy means `unknown`; it never
silently falls back to catalog-variant stock.

### 5.4 Graph construction and caching

`CatalogKnowledgeGraphBuilder` creates an immutable snapshot with a digest. It
prefetches the small published catalog and its structured relations in bounded
queries. Semantic topology may be cached briefly and invalidated after catalog
or profile changes. Live availability is never served from that cache; stock
and reservation counts are queried at decision time.

The snapshot digest and resolver reasons are stored with conversation
transitions so a production decision can be reconstructed.

## 6. Turn Understanding

### 6.1 Trusted URL resolver

Before Gemini, `TrustedProductReferenceResolver` parses URLs with
`urllib.parse`, accepts only configured TwoComms storefront hosts, supports an
optional locale prefix, removes query and fragment data, and resolves the exact
published product slug.

Only `https` URLs with an exact allowlisted hostname, no userinfo, and no
unexpected port qualify as trusted. Lookalike subdomains and host suffixes are
rejected. If a message contains an unknown URL plus useful product text, the URL
cannot authorize checkout, but the text constraints may still produce normal
verified candidates.

- A known trusted URL emits an exact product reference with highest priority.
- An unknown TwoComms slug is reported as unresolved and cannot create a
  proposal.
- External URLs are treated as conversational evidence, not catalog identity.
- Model-generated control tags cannot override a trusted customer URL.

### 6.2 Structured turn request

Gemini receives a bounded catalog vocabulary and returns a validated
`CommerceTurnRequest`, not a product ID. The request is orthogonal rather than
one mutually exclusive intent:

- exact reference, when present;
- corrections and rejected values;
- field updates;
- information topics;
- `checkout_requested`, `reset_requested`, and `support_requested` flags;
- positive and negative constraints;
- garment type, fit, color, size, quantity, and payment preference when stated;
- semantic constraints such as `back_decoration=none`;
- information topic such as `size_guide`;
- confidence and one proposed clarification when genuinely ambiguous.

A deterministic phrase layer covers high-risk corrections and common synonyms
even when Gemini is unavailable. For example, `classic`, `класична`, and
`классическая` map to a fit constraint unless an exact product title or URL
proves otherwise. `без принта` is retained as an underspecified decoration
constraint until the bot establishes whether the customer means the front,
back, or both.

### 6.3 Action priority

The resolver applies this precedence:

1. trusted exact product reference;
2. explicit correction, rejection, or product/garment switch;
3. information request, including a size guide;
4. configuration change;
5. explicit checkout request;
6. historical CRM intent only as a final hint.

The reducer applies reference and corrections first, then explicit field
updates, answers information topics, validates the resulting selection, and
only then considers checkout. A guide topic such as `show the oversize size
guide` never changes the payable fit by itself. Fit changes only when the same
message contains explicit selection language such as `I choose oversize`.

One turn may therefore answer information and update configuration. It must not
create a proposal unless the same turn contains an unambiguous checkout request
and all gates pass.

## 7. Explainable Candidate Engine

`CatalogCandidateEngine` applies hard constraints, then ranks remaining
candidates with explainable soft evidence.

### 7.1 Hard constraints

Hard constraints eliminate candidates that contradict:

- trusted exact product identity;
- published state;
- garment type;
- explicit color, fit, or size;
- verified positive or negative semantic traits;
- Fable option compatibility.

Constraints are classified before ranking:

- mandatory identity and safety constraints, including an exact URL, garment
  type, explicit negative print placement, and incompatible fit/size, are never
  relaxed silently;
- preferences may be relaxed one at a time only in a separately labelled
  `closest alternatives` result with the exact difference explained.

Availability has two levels. `Configurable` means that at least one verified
catalog configuration exists but does not promise the customer's still-missing
size or color. `Allocatable` means the exact product, variant, fit, size, and
quantity have a concrete live stock allocation. Customer-visible candidate
lists may show configurable products with honest `choose size/color` wording;
only allocatable candidates may be described as available for the exact
configuration or proceed to checkout. An `unknown` allocation is separated
into manager verification.

An unverified trait cannot satisfy a hard semantic constraint. It may only
produce a clarification or manager review.

### 7.2 Ranking

The stable ranking order is:

1. exact trusted URL;
2. exact verified alias or full title;
3. complete verified hard-constraint match;
4. match with the fewest explicitly explained relaxed preferences;
5. catalog priority and current customer preference evidence;
6. stable product ID tie-breaker.

The language model may normalize customer language and produce an explanation,
but it cannot reorder candidates after deterministic scoring. Ranking only
sorts a multi-candidate result; it never grants permission to silently select
the top candidate.

### 7.3 Ambiguity behavior

- An exact trusted URL, one exact unique verified alias, or one sole candidate
  remaining after all mandatory filters: select it automatically.
- Any remaining set of two or more candidates: show at most three choices
  with real image when the existing outbound media transport supports it, plus
  product name, fit/color summary, price, and canonical link.
- More than three candidates: choose the three most discriminating choices and
  ask one question that will reduce the remaining set.
- No exact candidate but verified near matches exist: relax one constraint at a
  time and explain the difference, such as another design or available size.
- A relaxed candidate is never selected automatically. A changed print, fit,
  color, size, or garment type requires explicit customer acceptance before it
  can become the active payable selection.
- No verified candidate: escalate once and keep the conversation open.

## 8. Durable Commerce Session State Machine

Add `IgCommerceSelectionSession`, one active row per client, with optimistic
revisioning. The row stores:

- the current commercial episode or session generation;
- state;
- ordered editable basket lines and the active line index;
- product, color variant, fit, size, quantity, and payment type per line;
- current positive and negative constraints;
- candidate IDs and candidate-set digest;
- rejected selection and rejection reason;
- pending field or pending clarification;
- last validation error;
- last outbound decision fingerprint;
- manager escalation fingerprint;
- source message watermark;
- catalog graph digest and revision.

This session is the authoritative pre-proposal commerce state. Existing
`IgClient.current_*`, `intent`, and `sales_context` fields become a compatibility
projection written in the same transaction after a successful state
transition. Once a session exists, checkout logic must not fall back to stale
legacy values. Legacy readers are migrated or routed through the projection
adapter before rollout.

Information-only `query_constraints` are separate from persisted
`selection_constraints`. Mentioning oversize inside a guide question affects
only the query. A new commercial episode creates a new session generation; a
closed or paid generation cannot leak product state into a repeat purchase.

Add append-only `IgCommerceSelectionTransition` rows containing the source
message, action, previous snapshot, next snapshot, resolver reasons, and graph
digest. MariaDB constraints and append-only protection preserve forensic
evidence. Migrations start from the actual current management leaf at
implementation time; no historical migration is rewritten.

Add `IgCommerceManagerReview` with a unique idempotency key, client, session,
reason code, safe selection snapshot, status, due time, owner/claim fields,
resolution, and timestamps. It is visible in the existing management workflow
and has an explicit SLA. A reply may promise manager verification only after
this row is durably created.

Add `IgCommerceTurnDecision` with database uniqueness on the source
`InstagramBotMessage` identity. It records the accepted transition, outbound
reply receipt, proposal, reservation, and escalation result. Replaying the same
inbound event returns this stored result even if the session revision has since
advanced.

### 8.1 States

- `browsing`;
- `awaiting_candidate_choice`;
- `configuring`;
- `awaiting_field`;
- `awaiting_alternative`;
- `ready_for_checkout`;
- `manager_review`;
- `proposal_created`.

### 8.2 Critical transitions

**Product or garment switch**

- replace the active product;
- clear old product, variant, fit, size, quantity, price, availability error,
  and proposal intent;
- apply only constraints explicitly stated in the switching turn;
- preserve conversation language and non-product customer context.

**Information request**

- answer from structured product/size-guide data;
- do not call proposal creation;
- do not change a valid selection unless the customer explicitly changes a
  field in the same message.

**Unavailable selection**

- record the rejected dimension and exact reason;
- apply the exact invalidation matrix: size failure clears size and allocation;
  color failure clears color variant and allocation; fit failure clears fit,
  size, and allocation; invalid product clears the complete active line;
  product switch replaces the complete active line; unknown warehouse mapping
  preserves the requested configuration but blocks checkout for manager review;
- move to `awaiting_alternative`;
- offer verified alternatives or create one manager-review request;
- never retry checkout only because historical intent is `payment`.

**Candidate selection**

- accept a numbered choice, exact title, exact URL, or unique candidate alias;
- accept a numbered choice only when it refers to the current candidate-set
  digest and session revision; a stale number causes the choices to be shown
  again;
- pin that product atomically and clear the candidate set;
- continue from the first genuinely missing configuration field.

**Checkout**

- require exact product, fit when applicable, color when applicable, size when
  applicable, explicit positive quantity, payment type, and authoritative
  allocation;
- compute a canonical payable-selection digest from commercial episode, deal,
  ordered configured lines, prices, payment type, and allocation identities;
- enforce one active proposal per payable-selection digest at the database
  boundary; a new evidence message or transition revision returns the existing
  active URL instead of creating a second proposal or reservation;
- freeze the resolved product, configuration, graph digest, availability
  allocation, price, and evidence in the proposal snapshot.

**Change after proposal creation**

- a ready or viewed proposal without an invoice is revoked transactionally and
  its temporary allocation is released before reselection continues;
- an unpaid proposal with an already created invoice enters provider
  cancellation and cannot produce a replacement proposal until cancellation is
  provider-confirmed;
- the customer's requested replacement remains in the session as pending, so
  the conversation does not return to the rejected old product;
- a paid proposal is immutable: a new purchase starts a new commercial episode,
  while a change to the paid item follows the existing exchange workflow.

Leaving `manager_review` for a new explicit product, fit, size, or color cancels
only the obsolete pending review and returns the active line to configuring. A
resolved review applies its result only when its session generation and
selection digest still match; stale manager results are retained as audit
evidence but cannot overwrite a newer customer choice.

## 9. Availability and Reservation

Introduce `CommerceAvailabilityService` with a typed result:

- `available` with a concrete allocation;
- `unavailable` with a verified limiting dimension;
- `unknown` when authoritative mapping is incomplete.

### 9.1 Warehouse-backed garments

For a color variant and fit linked through `VariantBlankLink`, the allocation is
the exact `StockItem` matching blank family, normalized size, and color. Sellable
quantity equals physical quantity minus active temporary reservations and paid
commitments not yet physically written off.

For warehouse inventory, legacy numeric `ProductColorVariant.stock` and
`VariantSizeRule.stock` values do not participate in availability. The service
still respects `VariantSizeRule.is_enabled`, fit rules, size grids, and option
compatibility. This distinction prevents legacy zero counters from blocking a
real warehouse-backed garment.

The matcher must not fall back from exact size or color to a broad category when
authorizing checkout. Existing graceful warehouse matching remains useful for
manager assistance, not customer-facing stock truth.

### 9.2 Catalog-variant stock

Products explicitly configured for catalog-variant inventory may continue to
use `ProductColorVariant.stock`. The source is explicit in the availability
result; there is no silent fallback between stock systems.

### 9.3 Reservation lifecycle

Extend checkout reservations to reference the concrete allocation source.

- Persist `allocation_source`, exact `stock_item`, order, write-off request,
  stock movement, paid-commitment time, and fulfillment time as applicable.
- Enforce one allocation per proposal item and validate that product, variant,
  fit, size, quantity, order, and stock target agree.
- Use explicit states `active`, `paid_committed`, `fulfilled`, `released`, and
  `overbooked_review` with guarded transitions.
- Proposal creation locks the allocation row and creates a 25-minute `active`
  reservation atomically.
- Expiry or provider-confirmed terminal failure changes `active` to `released`.
- Verified payment changes warehouse allocation to `paid_committed`; it no
  longer expires and does not yet decrement physical `StockItem.quantity`.
- Warehouse write-off locks the exact fresh `StockItem`, decrements it, records
  the matching `StockMovement`, and changes the same order/item/allocation from
  `paid_committed` to `fulfilled` in one transaction.
- A controlled manager substitution of a warehouse allocation is a separate,
  audited operation; a generic manual choice cannot silently fulfill a
  different reserved size, color, quantity, or order.
- Reversing a write-off atomically restores physical quantity and moves the
  exact fulfilled commitment back to `paid_committed`. A confirmed payment
  cancellation or return uses an explicit terminal release path instead.
- Legacy catalog-variant allocation retains its existing guarded consumption
  behavior.

Availability queries subtract active and paid-unfulfilled allocations. They do
not treat a released or fulfilled reservation as unavailable stock.

Every negative `StockItem` adjustment locks the fresh row and refuses to reduce
physical quantity below other active plus paid-unfulfilled commitments. This
guard applies to checkout, manual write-off, bulk adjustment, and any service
calling `adjust_stock_item`.

If a late provider success arrives after a temporary reservation was released,
the exact allocation is checked again under lock. When stock is still available
it becomes `paid_committed`; when it is not, the paid order remains payment truth
and a durable `overbooked_review` is created instead of silently decrementing or
discarding the payment.

## 10. Reply Policy and Sales Recovery

The response generator receives a deterministic decision object. It may make
the wording natural, but it cannot change products, availability, price, or the
next allowed action.

For a verified unavailable size, the bot should say that the exact size is not
currently available, promise manager verification only when a durable
manager-review task was actually created, and offer another verified size or
product in the same response.

For ambiguous `black classic`, the bot treats black as color and classic as fit.
It shows verified candidates instead of assuming a named design.

For `without print`, the bot asks whether the customer means no print on the
back, no print anywhere, or only the front logo when the message does not make
that distinction. Once the customer states `logo in front, no print on back`,
the graph filters only on verified traits.

For an exact product URL, the bot acknowledges the selected product and asks
only for missing configuration. It must not repeat an error associated with the
previous product.

## 11. Deduplication and Escalation

Idempotency uses separate keys for separate guarantees:

- `inbound_effect_key` is the unique provider/source message identity and
  prevents duplicate processing regardless of later session revision;
- `semantic_block_key` is commercial episode plus canonical rejected selection
  and reason and suppresses repeated unavailable wording across new messages;
- `payable_selection_digest` identifies the immutable configured basket and
  prevents duplicate active proposals when evidence messages change.

- Reprocessing the same inbound message produces no second outbound message.
- Reaching the same unavailable state from a new message does not resend the
  same paragraph; it asks for the pending alternative or reports the already
  created manager review.
- Manager escalation is unique by the semantic block key, not by a volatile
  transition revision.
- A materially new product, fit, size, color, or semantic constraint changes the
  semantic key and permits a new relevant decision. An unrelated message or
  revision increment does not.

The bot must never claim `I will ask a manager` without a persisted manager
review task visible in management operations.

## 12. Failure Handling

- Gemini unavailable or malformed: use deterministic URL and phrase parsing;
  ask one narrow clarification rather than guessing.
- Catalog graph build failure: do not create a proposal; persist a safe
  diagnostic code and route once to manager review.
- Unknown warehouse mapping: describe the need to verify availability, not an
  out-of-stock statement.
- Concurrent selection messages: optimistic revision check retries the latest
  state once; stale transition output is discarded.
- Concurrent proposal requests: unique revision/evidence idempotency returns the
  existing proposal.
- Reservation race: row locks decide the winner; the losing request receives
  freshly calculated alternatives.
- Unknown or external product URL: explain that the exact item was not found and
  ask for its name/photo or a TwoComms product link.

## 13. Observability and Operations

Structured logs and CRM diagnostics expose:

- action selected for the current turn;
- trusted URL resolution result;
- hard constraints, candidate count, and deterministic score reasons;
- graph digest;
- availability source and safe error code;
- state transition revision;
- reply, proposal, reservation, and escalation idempotency results.

Logs must not include full customer transcripts, tokens, payment URLs, phone,
email, or delivery data. The management interface shows current selection,
pending question, rejected choice, candidate reasons, and manager-review state
without requiring raw JSON inspection.

Metrics cover ambiguous-match rate, unavailable rate by source, unknown stock
mapping rate, repeated-error suppression, manager escalation rate, proposal
conversion, and product-switch recovery.

## 14. Performance

- Build the semantic graph with bounded prefetches and cache only immutable
  topology.
- Query availability only for the shortlisted candidates, in stable batches.
- Resolve exact URLs without sending the whole catalog to Gemini.
- Cap customer-visible candidates at three and model vocabulary to controlled
  codes.
- Time-bound model calls and retain the deterministic fallback.

The target is no additional model call for an exact trusted URL and no
catalog-sized loop of database queries.

## 15. Migration and Backfill

Implementation adds new migrations after the actual current leaves in the
affected apps. Existing migrations, especially checkout history, remain frozen.
At this specification review, the observed leaves are `management.0127`,
`fable5.0007`, `warehouse.0011`, and `storefront.0087`; implementation must
re-read the unified graph immediately before naming new migrations and declare
all required cross-app dependencies. Historical `management.0116` is immutable.

Provide idempotent commands with dry-run modes to:

1. create conservative semantic-profile suggestions from structured aliases,
   product titles, fit options, and print links;
2. report unverified semantic traits without promoting free text to truth;
3. audit `VariantBlankLink` coverage for published garments;
4. report exact size/color stock allocations and ambiguous warehouse mappings;
5. backfill an initial clean selection session from current CRM state only when
   it is internally consistent; otherwise start in `browsing` and preserve the
   old values as transition evidence.

No production backfill invents product construction or stock. Unverified rows
remain visible for manager review.

## 16. Test Matrix

### 16.1 Turn and state behavior

- old pink unavailable selection to a black classic replacement;
- exact trusted `classic-tshirt` URL switches the product;
- unknown TwoComms slug and external URL do not create a proposal;
- size-guide question during checkout leaves proposal creation untouched;
- T-shirt to hoodie or long sleeve clears stale product configuration;
- `black classic` is color plus fit, not a guessed design title;
- `no back print, front logo` uses verified semantic constraints;
- underspecified `without print` asks one placement clarification;
- numbered, named, and URL candidate selection;
- persistent payment intent cannot outrank current browsing action;
- a completed replacement can return to checkout normally.

### 16.2 Candidate and availability behavior

- one unique candidate auto-selects;
- multiple matches return at most three stable verified choices;
- unavailable exact size returns verified alternatives;
- missing warehouse mapping returns `unknown`, not `unavailable`;
- warehouse-backed T-shirt availability ignores raw zero variant stock;
- exact size/color/fit allocation is required;
- active and paid-unfulfilled reservations reduce sellable quantity;
- expiry releases temporary stock;
- payment commitment plus later write-off does not double-decrement stock;
- reversing that write-off restores the same allocation consistently;
- late payment after release either re-commits exact stock or creates one
  overbooked review without losing payment truth;
- legacy zero `VariantSizeRule.stock` does not block a warehouse-backed size;
- concurrent last-item reservations produce one winner.

### 16.3 Side effects and checkout

- repeated inbound processing creates one reply;
- replay after the session revision advanced returns the stored turn decision;
- repeated unavailable state is not spammed;
- manager review is created once and is operationally visible;
- incomplete configuration never creates a proposal;
- complete configuration creates exactly one proposal URL;
- immutable snapshot contains product, fit, size, color, quantity, graph digest,
  allocation source, price, and evidence messages;
- changing selection after a proposal requires the existing safe replacement or
  cancellation lifecycle rather than mutating the frozen proposal.
- multiple basket lines preserve independent configuration and immutable
  ordered proposal snapshots.

### 16.4 Integration verification

- focused Django suites under the repository test settings;
- migration executor tests for MariaDB-specific constraints or triggers;
- production-like MariaDB integration for stock locks and reservation races;
- `makemigrations --check --dry-run`, Django checks, compile checks, and diff
  checks;
- sanitized read-only replay of the `zainllw0w` chronology against the decision
  engine, with all outbound transports disabled;
- production smoke using a dedicated test fixture/account, never a real
  customer.

## 17. Acceptance Criteria

The work is complete only when:

1. every incident-contract step passes as an automated regression;
2. a customer can change product or garment type from any pre-payment state;
3. informational questions never accidentally resume payment;
4. candidate choices are verified, explainable, and capped at three;
5. exact product URLs deterministically replace stale selection;
6. warehouse-backed garments use real MariaDB stock and reservations;
7. unknown stock is handled honestly and escalated once;
8. duplicate unavailable replies and proposals are suppressed;
9. manual stock adjustments and write-off/reversal cannot steal, double-debit,
   or orphan an active or paid stock allocation;
10. the final migration graph, focused tests, MariaDB checks, and read-only replay
   pass on the unified commit;
11. the scoped result is integrated into `main`, deployed, and verified by
    matching local, origin, and server commit SHAs.

## 18. Explicit Non-Goals

- A separate graph database or vector database.
- Automatically trusting visual AI, SEO text, or generated descriptions as
  payable product facts.
- Sending experimental messages to existing customers.
- Rewriting the already approved assisted-checkout page design.
- Changing verified payment, order, TTN, or post-sale lifecycle semantics except
  where inventory allocation must integrate atomically with existing write-off.
