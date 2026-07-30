# Instagram Assisted Checkout Design

**Status:** Approved for implementation planning
**Date:** 2026-07-30
**Primary surface:** `twocomms.shop` mobile checkout opened from Instagram Direct

## 1. Product outcome

When an Instagram customer is ready to buy, the bot must stop sending a direct
Monobank provider URL. It must create a branded, personal TwoComms proposal with
the agreed products already configured. The customer verifies the immutable
selection, enters delivery and email data, and continues to Monobank from the
site. A verified payment creates one real order and completes the Instagram
commercial chain through payment, TTN, delivery, and review request.

The routine path is fully automated. Manager involvement is an exception for
ambiguous evidence, provider rejection, expired Meta permissions, or inventory
conflict. The system must never claim that a message or payment succeeded when
the provider did not confirm it.

## 2. Experience principles

1. **First-party trust.** The customer lands on the official TwoComms domain,
   sees the exact products and a clear protected-payment transition.
2. **No duplicate cart.** Products are a server-owned commercial snapshot, not
   mutable browser cart state.
3. **No surprise edits.** The payer can edit only recipient/delivery data,
   email, and an allowed promo code.
4. **Direct owns product changes.** Product, fit, size, color, quantity, and
   negotiated price changes are requested in Direct and validated by the bot.
5. **Provider truth.** Payment, TTN, and delivery are driven by committed
   provider/order events, not AI text and not Telegram output.
6. **Shareable without leaking PII.** Another person may pay, but cannot replace
   locked recipient data or see full sensitive values after submit.
7. **Mobile first.** The 320-430 px experience is primary; desktop remains
   clear and restrained.

## 3. System architecture

```text
Instagram inbound message
  -> classifier and Gemini response
  -> strict checkout control contract
  -> IgDeal + IgCheckoutProposal revision
  -> proposal access token
  -> bot sends twocomms.shop URL

Proposal GET
  -> validate token, expiry, state
  -> establish secure proposal grant
  -> redirect before analytics to clean URL
  -> render locked products and delivery form

Proposal POST
  -> lock proposal row
  -> validate revision, expiry, stock, prices, promo, signed NP tokens, PII
  -> create/reuse one standard PaymentAttempt
  -> create one Monobank invoice
  -> redirect to provider

Verified webhook/return
  -> materialize one Order
  -> bind IgDeal, IgClient, episode, attribution, payment projection
  -> create payment_verified lifecycle event

Order domain events
  -> tracking number created -> ttn_created lifecycle event
  -> NP StatusCode delivered -> delivered_review lifecycle event
  -> lifecycle worker -> Direct or policy fallback
```

### Ownership boundaries

- `management`: Instagram client/deal/proposal/revision/token/outbox models,
  strict bot contract, proposal service, commercial linkage, lifecycle worker.
- `orders`: canonical `PaymentAttempt`, `Order`, TTN transition, Nova Poshta
  delivery transition, email/Telegram payment behavior.
- `storefront`: public proposal views/routes, form boundary, page templates,
  static assets, analytics/browser success state.
- `fable5`, `productcolors`, and storefront product services: sellable product,
  fit, size, option, color, stock, and effective catalog price validation.

## 4. Data model

### IgCheckoutProposal

One active commercial proposal tied to an Instagram deal.

Key fields:

- `client`, protected `deal`, `commercial_episode`
- `public_id` UUID for non-secret clean routing
- `status`
- `revision`
- `locale`
- `currency`
- `catalog_total`
- `negotiated_discount`
- `quoted_total`
- `requested_payment_amount`
- `pay_type`
- `allow_promo`
- `items_digest`
- `expires_at`, `viewed_at`, `details_locked_at`, `paid_at`
- `payment_attempt`
- `superseded_by`
- created/updated timestamps

`IgDeal.active_checkout_proposal` is the nullable current pointer. The deal can
retain multiple historical/replacement proposals, but proposal creation locks
the deal and updates that pointer atomically. This avoids relying on unsupported
MariaDB partial unique constraints while preserving audit history.

State values:

```text
ready
  -> viewed
  -> details_locked
  -> invoice_created
  -> paid

ready/viewed -> expired
ready/viewed -> superseded
invoice_created -> cancelled (provider-confirmed cancellation only)
any non-paid state -> revoked
```

`IgDeal.Status.QUOTED` means the proposal exists but no invoice exists.
`IgDeal.Status.AWAITING_PAYMENT` begins only after invoice creation.

### IgCheckoutProposalItem

An immutable current-revision display and payment snapshot:

- `proposal`, `product`, `color_variant`
- product/SKU/title/image snapshots
- color code/label snapshot
- size
- fit code/label
- generic option values/labels
- quantity
- catalog unit price and line total
- quoted unit price and line total where evidence supports it
- price source and evidence message IDs
- stable ordering index

Products remain relationally linked for final stock validation, while display
fields are snapshotted so the commercial proposal does not silently change when
catalog copy or imagery changes.

### IgCheckoutRevision

Append-only audit record created for every product/price change:

- proposal, revision number, digest
- PII-free item/pricing snapshot
- source (`bot_create`, `bot_update`, `system_supersede`)
- evidence message IDs and source message watermark
- created timestamp

The buyer-facing item table represents only the current revision. Historical
revisions are never mutable.

### IgCheckoutAccessToken

- proposal
- SHA-256 digest of a 256-bit random bearer token
- kind (`bot`, `share`, `replacement`)
- expiry/revocation timestamps
- use count and last-used timestamp

The raw token is not stored in this table. It can exist in the persisted Direct
message because the customer must receive it. The token entrance route validates
it, stores a signed proposal grant in the browser session, and redirects to a
clean public-ID URL before Pixel, TikTok, or GA load.

Each signed grant contains an independent random `grant_id` used only for
per-browser analytics occurrence IDs. It is not the bearer token or session key.

### IgCheckoutInventoryReservation and PromoCodeReservation

Inventory is reserved only when one worker owns invoice creation, for no longer
than the payable invoice lifetime. Reservations are consumed by verified Order
materialization and released only after confirmed cancellation, expiry, or
failure. Limited promo usage is reserved under a PromoCode row lock, consumed
once after verified payment, and released only after provider truth confirms the
attempt cannot pay.

### IgLifecycleEvent

Durable source of truth for post-payment Direct actions:

- event key (unique)
- kind (`payment_verified`, `ttn_created`, `delivered_review_requested`)
- client, deal, proposal, order, commercial episode, order attribution
- PII-minimal payload and locale
- state (`pending`, `processing`, `sent`, `waiting_window`, `manager_review`,
  `ambiguous`, `failed`, `cancelled`)
- due time, attempts, lease token/expiry
- provider message ID
- last error and completion timestamps

Unique event keys:

```text
payment:<payment_attempt_id>:verified
ttn:<order_id>:<sha256(normalized_tracking_number)>
delivered:<order_id>:<nova_poshta_status_code>
```

Lease ownership is revalidated immediately before the final state write so a
stale worker cannot mark a reclaimed event as sent.

## 5. Proposal token and forwarding design

1. The bot issues an access URL valid until the proposal expiry.
2. The access route accepts no PII and sends `no-store`, `noindex`, and
   `Referrer-Policy: no-referrer` headers.
3. It validates the token digest and proposal state, stores a scoped signed
   session grant, and redirects to a clean URL.
4. The clean page loads analytics only after the bearer token is absent.
5. The copy/share action requests a separate share token from a CSRF-protected
   endpoint. The UI copies a fresh access URL, not the clean session URL.
6. A forwarded payer receives an independent session grant.
7. The first valid delivery submit locks recipient data and creates the single
   invoice. Later viewers see masked recipient information and can continue the
   same invoice but cannot replace recipient data.

The page never exposes unmasked Instagram username, chat excerpts, phone,
email, or delivery address to a forwarded viewer.

## 6. Revision and correction rules

### Before invoice creation

- The customer requests a change in Direct.
- The bot identifies the active proposal and validates the new complete item
  configuration against current catalog and conversation evidence.
- A row lock serializes the update.
- The old revision is preserved append-only.
- Current items and pricing are replaced atomically.
- Revision and digest increase.
- Existing unexpired access tokens continue to resolve to the latest revision.
- A page already open checks revision on `visibilitychange` and shows a small
  `Proposal updated` transition without WebSockets.

### After invoice creation

- The proposal is immutable while an invoice may still accept money.
- The service requests provider cancellation and verifies the terminal result.
- Only a confirmed non-payable old invoice permits a replacement proposal.
- The old proposal becomes `superseded`; a new proposal and token are issued.
- The old page shows a clear replacement state and links through a fresh access
  grant.
- If provider cancellation is ambiguous, no second invoice is created. A
  manager review is opened because two simultaneously payable totals are worse
  than a delayed correction.
- A verified payment always wins over a concurrent correction.

### After verified payment

The order is immutable through this flow. Additional products or corrections
create a separate commercial episode and proposal; they never rewrite the paid
order.

## 7. Product and price contract

The internal `[PAYLINK]` tag remains temporarily for compatibility but changes
meaning: it requests a TwoComms proposal, never a Monobank URL.

Preferred explicit control contract:

```text
[PAYLINK:full]
[ITEM:<product_id>|<qty>|<size>|<fit>|<color_variant_id>]
```

For evidence-bound prepayment:

```text
[PAYLINK:prepay]
[PAYMENT:<exact_amount>]
```

Rules:

- Always normalize one item into the same list path as many items.
- Never default fit, size, or color when the catalog exposes a choice.
- Ask only the missing option and, for size, send the applicable size guide.
- Validate published state, stock, product/variant ownership, size, fit,
  generic options, quantity, and effective price twice.
- Treat the proposal quote as frozen until expiry. Catalog/availability drift
  blocks submit and requires a new Direct revision; it never silently reprices
  an already issued proposal.
- Catalog pricing is authoritative unless the exact negotiated total is tied to
  current-episode message evidence.
- For a multi-item negotiated total, represent the difference as an order-level
  negotiated discount. Do not invent per-line price allocation.
- Promo codes may apply to catalog pricing. They do not stack with a negotiated
  Instagram discount unless `allow_promo=True` is explicitly stored on the
  proposal.
- Custom Print is excluded from this automated slice unless it already has an
  approved, fixed, sellable catalog/lead snapshot compatible with
  `PaymentAttempt`.

## 8. Public page information architecture

### Mobile layout (primary)

```text
TwoComms logo                         share icon
Personal proposal              expires in 11:42

Selected products
[4:5 real image] Product title
                 color swatch + label
                 Classic / Oversize
                 Size L | quantity 1
                 line price

Recipient
Full name
Phone
Email  "Receipt and confirmation arrive here"

Delivery
Nova Poshta city autocomplete
Branch / post-locker segmented choice
Signed warehouse autocomplete

Promo disclosure
Price summary

[sticky total] [Continue to payment - amount]
```

### Desktop layout

- Maximum content width approximately 1040 px.
- Products and price context occupy the left 42%.
- Delivery form occupies the right 58%.
- No floating hero, no marketing split-card composition, no nested cards.
- The mobile sticky action becomes an inline terminal action.

### Product presentation

- Real product or selected color-variant image.
- Reserved 4:5 aspect ratio to prevent layout shift.
- `object-fit: contain` on a neutral inspection surface; no dark or blurred
  atmospheric crop.
- Stable compact rows for multiple products.
- One product may receive a larger image, but information order stays identical.
- Color is represented by a swatch and text label.
- Fit and size are plain, high-contrast facts, not decorative pills.

### Visual language

- Near-black frame, white/light form surface, warm orange primary action.
- Green appears only for provider-verified success/valid fields.
- Neutral gray supports secondary metadata.
- No purple gradient, decorative orbs, particles, bokeh, or card grid.
- Page-specific CSS and JavaScript remain isolated from the existing cart.

### Motion

- 300-400 ms one-time stagger on product/form entrance using only opacity and
  transform.
- 150-200 ms field validation transitions.
- Payment button changes to a stable loading state without resizing.
- Verified success uses a short check-draw transition.
- No infinite shimmer or autonomous motion.
- `prefers-reduced-motion: reduce` removes all nonessential animation.
- The mobile sticky action includes `env(safe-area-inset-bottom)` and terminal
  scroll padding so the CTA never covers a focused field, its error text, or the
  last product row when the software keyboard is open.

### Accessibility and resilience

- Real labels, autocomplete attributes, input modes, and error associations.
- Keyboard-operable Nova Poshta results and share action.
- Minimum 44 px interactive targets.
- Visible focus states.
- No horizontal overflow at 320 px.
- Server-rendered error fallback when JavaScript fails.
- Stable loading dimensions and responsive images.

## 9. Form and invoice behavior

Editable fields:

- full recipient name;
- Ukrainian phone;
- required email;
- Nova Poshta city;
- branch or post-locker;
- optional promo code.

Server validation:

- normalizes phone and email;
- resolves signed city and warehouse tokens using existing Nova Poshta services;
- rejects free-text delivery refs;
- checks proposal grant, state, revision, expiry, current inventory, price, and
  promo eligibility under a row lock;
- creates one fingerprint from proposal ID and revision, independent of browser
  session, so forwarded browsers reuse the same attempt;
- sends email in Monobank `customerEmails` where supported;
- sets invoice validity to the remaining proposal lifetime, maximum 12 hours;
- sets session ownership needed for the secure success page.
- claims invoice creation with a durable lease before the provider call;
- persists `invoice_creation_ambiguous` for timeout/crash boundaries and never
  blindly repeats provider create;
- reserves inventory and limited promo capacity for the invoice lifetime.

The payment button reads `Continue to payment - <amount>`. Invoice creation is
never performed on GET, page preload, or crawler access.

## 10. Payment and Instagram binding

`PaymentAttempt` remains the only new-payment truth. On verified materialization:

1. Create the `Order` exactly once.
2. Persist the attempt/order provider evidence.
3. Schedule the Instagram adapter after commit.
4. Adapter locks the proposal/deal and creates an append-only
   `IgPaymentEvent` sourced from the verified attempt.
5. Update `IgPaymentProjection` without sending a second Purchase event.
6. Bind `IgDeal.order`.
7. Create `IgOrderAttribution(payment_source="provider_attempt")`.
8. Bind the commercial episode and synchronize payment state.
9. Move proposal to `paid`, deal to `order_created`, and client stage to
   `order_created`; then synchronize episode payment and bind the Order.
10. Create the unique `payment_verified` lifecycle event.

Every proposal revision atomically updates the matching `IgDeal` payment fields
and `IgDealItem` snapshots before `ensure_episode_for_deal()` is called. The
proposal stores that exact episode so payment truth, attribution provenance, and
order materialization cannot read a stale or empty deal snapshot.

A reconciliation command scans converted Instagram attempts missing any of
these bindings and repairs them idempotently.

Post-payment external channels are tracked independently: Telegram, receipt
email, Meta Purchase, TikTok Purchase, and Instagram lifecycle emission each
have their own pending/confirmed/skipped/failed marker and lease. Success in one
channel never clears another. A bounded reconciler replays only missing channels
after process loss.

## 11. Analytics design

| Event | Trigger | Browser | Server | Event ID |
| --- | --- | --- | --- | --- |
| `ViewContent` | meaningful clean proposal render | Pixel | optional CAPI beacon | proposal/revision/grant HMAC |
| `InitiateCheckout` | first valid Continue-to-payment submit per grant | Pixel | CAPI beacon | proposal/revision/grant HMAC |
| `AddPaymentInfo` | valid invoice creation | Pixel before redirect | CAPI | PaymentAttempt ID |
| `Purchase` | verified success only | verified success page | CAPI after materialization | Order ID |

Additional rules:

- Pixel and CAPI share the same deterministic event ID only for the same event
  occurrence. Separate forwarded grants get separate ViewContent/Initiate IDs.
- Render, focus, typing, validation failure, preload, and crawler access emit no
  `InitiateCheckout`. Repeated valid submits reuse the same grant event ID.
- Browser tracking never receives the bearer token or unmasked Instagram data.
- `utm_source=instagram`, `utm_medium=direct`, and a stable assisted-checkout
  campaign are stored server-side.
- Original Instagram client/deal attribution is preserved when another browser
  pays.
- `Purchase.value` is the full discounted order value; `paid_value` is actual
  provider-verified money.
- A pending return renders `Payment is being verified` and polls a bounded
  status endpoint. It does not render success or emit Purchase.
- Live advertising test events are prohibited without explicit authorization.

## 12. Bot conversation and catalog media

### Purchase flow

The prompt and playbooks must instruct the bot to:

1. Detect concrete purchase intent such as `How can I pay?`.
2. Resolve the exact product(s) from current commercial context.
3. Ask only missing color, fit, size, or quantity.
4. For T-shirts, ask fit first, then send the exact product-and-fit-specific size
   grid before asking size. Never use another product's grid or create a proposal
   while fit/size remains unresolved.
5. Emit strict controls only after all required choices are sellable.
6. Create the proposal immediately without a redundant confirmation question.
7. Send concise customer copy:

```text
I prepared your TwoComms proposal. Check the products, enter Nova Poshta
delivery details and the email for your receipt, then continue to protected
payment. It takes up to two minutes. If you want to change an item, write here
and I will update the proposal.
```

8. Never invent or type a Monobank URL.

### Product discovery media

- Bot playbooks and prompt authorities own this behavior, not only the transport
  parser: general UA/RU/EN requests to show products emit media controls, while
  an explicit request for a link may emit a catalog URL.
- Prefer three or four real catalog/variant images when the customer asks to
  see available products.
- Use a native supported Instagram media/carousel format when the active
  Instagram Login transport supports it.
- If the API does not support a multi-image album, send a bounded sequence of
  image messages followed by one compact caption; do not emulate an album with
  a page of links.
- Use catalog links only when explicitly useful or requested.
- Product media messages are deterministic from catalog IDs; Gemini selects
  candidates but cannot supply arbitrary external image URLs.
- Add rate, count, host, MIME type, and size validation.

## 13. Lifecycle messages

### Payment verified

Triggered from the verified PaymentAttempt adapter, not browser return:

```text
Thank you, payment received. Order <number> is being prepared for <recipient>,
phone <phone>, Nova Poshta <city/branch>. I will send the TTN here as soon as it
is created.
```

### TTN created

Triggered by the first committed non-empty tracking number:

```text
Your order <number> has been prepared for shipment.
TTN: <tracking number>
Track it: <official Nova Poshta tracking URL>
```

### Delivered review request

Triggered by canonical Nova Poshta delivery status:

```text
Thank you for choosing TwoComms. Did everything arrive correctly, and did you
like the order? If you have a minute, tag @twocomms in a story or send a short
review - honest customer feedback helps us grow.
```

Messages are localized to UA/RU/EN, deterministic, and idempotent. AI may adapt
tone only within a bounded template; it must never alter order, payment, TTN, or
delivery facts.

Full recipient facts are sent only to the exact original bound Instagram
conversation after verified payment. Forwardable browser pages and management
lists remain masked.

### Meta policy routing

- Inside the conservative response window: ordinary automatic response.
- Outside the window: one prepared manager task and one deduplicated Telegram
  operational alert.
- `HUMAN_AGENT`: only explicitly human-authored support, never this worker.
- Mark sent only on confirmed provider delivery.
- Capture the provider message ID in a structured receipt and execute sends
  inside the existing reply/customer boundaries to close opt-out/takeover races.
- Unknown/ambiguous provider response is not automatically retried.

## 14. Management workspace

Extend the existing Orders workspace with `Awaiting payment` visibility:

- proposal/client/order reference;
- current revision;
- product count and amount;
- ready/viewed/details/invoice/paid/expired state;
- expiry countdown;
- delivery form completed flag without raw PII;
- invoice/provider state;
- link delivery state and last classified error;
- actions: open safe preview, issue copy token, resend through bot, revoke,
  inspect audit/revision history;
- revoke/supersede is blocked while an invoice remains payable or ambiguous and
  requires provider-confirmed non-payable state;
- no routine manual step required.

Existing action/confirmed/all views remain intact.

## 15. Error and recovery matrix

| Failure | Customer state | Durable action |
| --- | --- | --- |
| Missing fit/size/color | no proposal | bot asks only missing option |
| Product unpublished/out of stock | no invoice | proposal blocked, bot proposes correction |
| Expired token | expired page | repeated payment intent creates a fresh proposal/token automatically; never revive the old token |
| Stale open revision | refresh transition | render latest revision |
| Duplicate submit | same invoice | reuse locked PaymentAttempt |
| Two payer browsers | first details win | second sees masked locked state |
| Monobank create failure | retryable page | attempt/error stored, no Order |
| Webhook/return race | one Order | row-lock/idempotent materialization |
| Adapter crash | payment remains valid | reconciler binds Instagram state |
| TTN signal crash | Telegram independent | lifecycle reconciler recreates event |
| Meta window closed | no false sent marker | manager task plus alert |
| Meta 508 link restriction | proposal persists | classified link-delivery review; never strip payment URL silently |
| Provider timeout during invoice create | ambiguous | reference lookup/reconcile; no blind second invoice |
| Provider timeout after message send | ambiguous | no blind replay, manager review |
| Payment reversal/refund | fulfillment blocked | existing reversal truth and review path |
| Cancelled/failed attempt | terminal payment state | suppress payment CTA; show the correct Direct/retry path |
| Product unavailable | unavailable proposal | suppress payment CTA; return to Direct for a corrected configuration |
| Cancellation ambiguous | review state | suppress replacement/payment actions until provider truth resolves |

## 16. Security and privacy controls

- 256-bit random access tokens; digest only in token table.
- CSRF for every mutation and share-token endpoint.
- Scoped signed browser grant after token handshake.
- Rate limits by IP, proposal, token digest, and client.
- No bearer token in analytics URL, logs, referrer, DOM data attributes, or
  error reporting.
- `Cache-Control: no-store, private`, `X-Robots-Tag: noindex, nofollow`, and
  `Referrer-Policy: no-referrer`.
- Existing CSP respected; no inline script without established nonce/hash.
- Signed Nova Poshta directory selections only.
- No chat PII on the forwardable page.
- Full delivery data stored only in PaymentAttempt/Order.
- Masked post-submit page and management summaries.
- Append-only revision/payment/lifecycle evidence.
- Provider success body alone is never trusted without current pull/signature
  and amount reconciliation.

## 17. Explicit non-goals

- Replacing the ordinary storefront cart.
- Rebuilding Monobank webhook verification.
- Creating Orders before verified payment.
- Automatic catalog checkout for unresolved Custom Print requests.
- Reserving inventory before invoice ownership; proposal viewing alone never
  blocks stock.
- Sending prohibited automated `HUMAN_AGENT` messages.
- Live Meta/TikTok test purchases or events.
- Refactoring unrelated management dashboard or Custom Print code.
