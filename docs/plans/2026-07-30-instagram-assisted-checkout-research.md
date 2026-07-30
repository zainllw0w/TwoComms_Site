# Instagram Assisted Checkout Research

**Date:** 2026-07-30
**Branch:** `codex/instagram-assisted-checkout`
**Research base:** initial audit at `e4cfb80b`; implementation baseline rebased to
`origin/main` at `7fe26280`
**Scope:** Management Instagram bot, first-party checkout proposal, standard
`PaymentAttempt`, Monobank, Nova Poshta, analytics, and post-sale Direct
notifications.

## 1. Executive conclusion

The new flow must not create a second payment implementation. The bot should
create a first-party, time-limited commercial proposal on `twocomms.shop` and
send that URL in Direct. The buyer reviews a locked product configuration,
enters validated delivery and email data, and only then creates a standard
`orders.PaymentAttempt`. A verified Monobank provider result materializes the
real `Order` and links it back to the Instagram client, deal, and commercial
episode.

The reliable domain event chain is:

```text
Instagram purchase intent
  -> validated IgDeal and proposal revision
  -> first-party proposal URL (12 hours)
  -> signed Nova Poshta selection and email
  -> one PaymentAttempt and one Monobank invoice
  -> provider-verified payment
  -> one Order and Instagram attribution
  -> payment_verified lifecycle event
  -> tracking_number_created lifecycle event
  -> nova_poshta_delivered lifecycle event
  -> review request lifecycle event
```

Telegram alerts are consumers of order events, not the trigger or source of
truth. Instagram messages must be generated from the same committed domain
events through a durable, idempotent outbox.

## 2. Repository and production baseline

- The original local `main` is 18 commits behind `origin/main` and contains
  unrelated Custom Print work. It must not be used for implementation.
- This planning worktree started from `e4cfb80b` and was rebased onto the final
  Instagram Login integration commit `7fe26280` before runtime changes.
- The former verification worktree is clean on branch
  `codex/instagram-login-runtime`; its runtime changes are already represented
  by `origin/main` at `7fe26280`.
- Production was verified at `e4cfb80b` during the initial research pass. It
  must be checked again against the final feature SHA during Task 20; no claim
  is made here that production already runs `7fe26280`.
- Production tables `IgClient`, `IgDeal`, `PaymentAttempt`, `Order`, and the
  relevant attribution tables use InnoDB.
- Production has applied management migrations through `0114` and orders
  migrations through `0052`.
- A separate worktree, `/private/tmp/twocomms-ig-verify.dIoXh3`, has uncommitted
  Instagram runtime changes which overlap `ig_bot_models.py`,
  `instagram_bot.py`, `bot_sales_classifier.py`, `bot_views.py`, URLs, tests,
  and a proposed management migration `0115`. It is not touched by this branch.
- Before runtime implementation, fetch the integration SHA, inspect that
  worktree's final status, rebase this branch, and allocate migration numbers
  from the resulting graph. Do not assume `0115` is available.

### Baseline verification

Command:

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py check
```

Result: pass, zero system-check issues.

Focused baseline command:

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_paylink_fix \
  management.tests_ig_shipment \
  orders.tests.test_payment_attempts \
  storefront.tests.test_monobank_webhook --verbosity 1
```

Initial result after the integration rebase: 74 tests, 72 pass, 2 failures:

- `PostPaymentEventsDeferralTests.test_external_sends_deferred_until_commit`
- `PostPaymentEventsDeferralTests.test_retail_status_helper_uses_shared_dispatcher_after_commit_once`

Both expected one `transaction.on_commit` callback and observed two. The second
callback came from `management.services.ig_order_truth`: it scheduled Instagram
truth reconciliation for every storefront order payment/status change, even
when no `IgDeal`, `IgOrderAttribution`, `IgCommercialEpisode`, or
`IgOrderLinkEvent` owned the order.

Task 0 now gates that signal on a persisted Instagram link. Ordinary storefront
orders retain one post-payment callback, while existing attribution-only tests
continue to prove that Instagram-linked orders schedule truth reconciliation.
Verification after the fix:

- `manage.py check`: zero issues;
- `PostPaymentEventsDeferralTests`: 7/7 pass;
- `management.tests_ig_paylink_fix management.tests_ig_shipment
  orders.tests.test_payment_attempts storefront.tests.test_monobank_webhook`:
  74/74 pass.

## 3. Existing Instagram purchase flow

### Ingress and reply generation

- `management/bot_webhook.py` verifies webhook signatures, persists raw events,
  and queues the durable customer-message path.
- `management/management/commands/run_instagram_bot.py` runs the reply worker.
- `management/services/instagram_bot.py` builds the Gemini prompt from the
  default prompt, editable settings, routed `BotInstruction` playbooks, catalog
  context, commercial memory, and the injected payment protocol.
- `_extract_control()` parses hidden control tags and removes them from visible
  customer text.
- `_process_one_inside_reply_boundary()` applies the tags and sends the reply.

### Purchase intent and current direct invoice

- `bot_sales_classifier.py` recognizes payment-related language and moves the
  client toward `checkout`.
- `_wants_paylink()` recognizes `[PAYLINK:full|prepay]` or a link promise.
- `payment_link_allowed()` requires a concrete product and purchase evidence.
- `finalize_paylink()` calls `bot_orders.create_deal_and_link()`.
- `bot_orders.create_deal_and_link()` creates/reuses `IgDeal` and
  `IgDealItem`, binds the current commercial episode, and immediately calls
  `bot_payments.create_payment_link()`.
- `bot_payments.create_payment_link()` creates a Monobank invoice and returns
  the provider URL directly to Instagram.

That final step is the replacement boundary. Existing direct `IGDEAL-*`
invoices remain readable and payable for backward compatibility, but new bot
purchases must never call this path.

## 4. Product-configuration findings

The multi-item path is already substantially safer than the single-item path:

- It caps line and unit counts.
- Size is required and checked against `resolve_product_sizes()`.
- Active product fit options are required and validated.
- A color variant, when provided, must belong to the product and have stock.
- `variant_allows_purchase()` validates the sellable combination.
- Duplicate identical lines and unreasonable totals are rejected.

The single-item path has a critical gap:

- Size and fit are validated only when present, not required.
- Color variant is not carried through the single-item shortcut.
- `IgClient` stores size, color, and quantity, but has no evidence-bound current
  fit field.

The new flow must use one strict item-list validator for both one and many
products. For every product:

- quantity is required;
- size is required when the product exposes sizes;
- fit is required when active fit options exist;
- `classic` versus `oversize` must be explicit for applicable T-shirts;
- color is required when more than one sellable variant is possible;
- product, variant, fit, size, option combination, published state, and price
  are revalidated before proposal creation and again before invoice creation.

The bot asks only for missing data. Once all required choices and purchase
intent are present, it creates the proposal without an extra confirmation
question.

## 5. Existing standard PaymentAttempt path

`orders.PaymentAttempt` already provides the correct payment lifecycle:

- a unique fingerprint and provider reference;
- an immutable cart snapshot before `Order` exists;
- signed Nova Poshta refs and recipient data;
- promo-code linkage;
- gross, discount, payable, payment, and paid amounts;
- one Monobank invoice;
- provider amount reconciliation;
- atomic, idempotent `Order` materialization;
- Telegram recovery markers;
- email and post-payment dispatch;
- browser/CAPI event identifiers;
- a secure success-page ownership session.

The proposal should create this object only after form validation. It should not
create an unpaid `Order`, hydrate a browser cart, or reuse the legacy direct
`IgDeal` invoice mechanism.

### Required PaymentAttempt extension

The model currently distinguishes `online_full` and legacy `prepay_200`. The
Instagram deal supports evidence-bound arbitrary prepayment. Add a generic
`prepayment` choice and preserve this semantic contract:

- `gross_amount`: full catalog/negotiated order value before discount;
- `discount_amount`: evidence-bound negotiated and allowed promo discount;
- `payable_amount`: full order value after discount;
- `payment_amount`: amount charged now;
- `paid_amount`: provider-verified money received.

Both full payment and prepayment are one `Purchase` with the full discounted
order value. `paid_value` is separate. A prepayment must not create a `Lead`.

## 6. Instagram linkage gap after PaymentAttempt

A standard `PaymentAttempt` creates the `Order`, but it does not currently know
how to bind Instagram commercial state. Without an adapter:

- `IgDeal.order` remains empty;
- `IgPaymentProjection` does not reflect provider truth;
- the current commercial episode is not bound to the order;
- `IgOrderAttribution` is not created;
- shipment and post-sale jobs may not find the Instagram client;
- the old direct-invoice flow remains a conflicting second truth source.

The adapter must run after successful materialization, be idempotent, and have a
bounded reconciler for a crash between `Order` commit and Instagram linkage.
Payment and order creation must remain successful even if the adapter needs
later repair.

## 7. Delivery and post-sale findings

### Tracking number creation

`orders/signals.py` already detects the first transition from an empty tracking
number to a populated tracking number. It currently queues only a Telegram
notification. The Instagram lifecycle emitter must be attached to the same
committed transition, not to Telegram delivery and not to a UI action.

The current `notify_shipped_deals()` job additionally requires `Order.status ==
"ship"`. This can miss a newly created TTN when the tracking number and status
are saved in separate operations. The new `tracking_number_created` event must
be based on the first non-empty canonical tracking number and the Instagram
order attribution, regardless of notification ordering.

### Nova Poshta delivery

`orders/nova_poshta_service.py` already treats canonical Nova Poshta delivered
status as a domain transition. `StatusCode=9` (plus the existing compatibility
codes) moves the order to `done`, records the provider status anchor, and emits
current admin/customer notifications.

After that transaction commits, the Instagram integration must create one
`nova_poshta_delivered` lifecycle event keyed by order and provider status. It
must never infer delivery only from localized text.

### Missing lifecycle outbox

There is no durable, unified outbox for:

- payment confirmation in Direct;
- immediate TTN duplication in Direct;
- delivered-order review request;
- provider message ID and delivery certainty;
- crash reconciliation across those events.

The new outbox is therefore a required component, not an optional notification
helper.

## 8. Meta delivery constraints

The business event and the Instagram permission window are separate facts. A
Monobank webhook, TTN signal, or Nova Poshta status update does not reopen the
Instagram response window. The current code uses a conservative 23-hour window
and rejects automated `HUMAN_AGENT` use unless `human_authored=True`.

The lifecycle worker must therefore:

1. Create the event regardless of Meta availability.
2. Send immediately through ordinary response messaging when eligible.
3. Mark `sent` only after a confirmed provider response and persist the provider
   message ID when available.
4. Treat timeouts/5xx as ambiguous and avoid blind duplicate replay.
5. Outside the response window, create one deduplicated manager task with the
   prepared text and one operational Telegram alert.
6. Never use automated `HUMAN_AGENT` for payment, shipment, or review requests.

The 12-hour proposal lifetime makes payment confirmation normally eligible.
TTN and delivery events commonly occur outside the response window, so their
event and prepared message are guaranteed; immediate Direct delivery cannot be
claimed unless Meta accepts it.

## 9. Analytics findings and required semantics

- `ViewContent`: first meaningful proposal render with real product IDs.
- `InitiateCheckout`: first valid Continue-to-payment submit, once per clean
  browser grant; render, focus, typing, validation failure, preload, and crawler
  access emit none.
- `AddPaymentInfo`: valid form submission and invoice creation, using the
  `PaymentAttempt` event ID in browser Pixel and CAPI.
- `Purchase`: only after provider-verified success, using the deterministic
  order event ID in browser Pixel and CAPI.

Never emit `Purchase` on page view, button click, redirect, unverified webhook
body, or pending return. Do not send live Meta test events during verification.
Use mocked/no-network serialization tests.

The server retains original Instagram attribution even when a different person
opens and pays the forwarded link. Browser attribution belongs to the actual
payer's browser and is captured in `PaymentAttempt.tracking_payload`.

## 10. UX and trust findings

The page should be a first-party commercial proposal, not a second cart and not
a marketing landing page. It needs:

- official `twocomms.shop` domain and TwoComms identity;
- exact products and real imagery in the first viewport;
- clear fit, size, color, quantity, unit price, and total;
- immutable products with a Direct-based correction path;
- validated recipient, phone, email, city, branch/post-locker selection;
- a clear note that the email receives receipt/confirmation;
- optional promo disclosure;
- 12-hour expiry and share/copy action;
- a single dominant payment action;
- truthful pending, paid, expired, superseded, and unavailable states;
- no unmasked Instagram handle or private chat data on a forwardable page;
- no full PII after details are locked;
- `noindex`, `no-store`, and `Referrer-Policy: no-referrer`.

The best implementation is server-rendered Django HTML with small isolated CSS
and JavaScript, using existing Nova Poshta signed selectors and analytics
loader. No new frontend framework is justified.

## 11. Approaches rejected

### Hydrate the normal cart from the link

Rejected because it is session-dependent, mutable, unsafe to forward, and can
diverge from the negotiated deal.

### Add a form directly on IgDeal and keep its Monobank integration

Rejected because it duplicates PaymentAttempt idempotency, promo validation,
tracking, email, Telegram, webhook, and success-page behavior.

### Create an unpaid Order when the bot sends the proposal

Rejected because it pollutes order truth, weakens verified-payment semantics,
and creates cleanup/reconciliation problems for expired links.

## 12. Implementation gate

Before Task 1 code changes:

- re-fetch `origin/main`;
- inspect the final Instagram Login worktree/branch and its migration;
- rebase and resolve overlapping runtime files deliberately;
- rerun the focused baseline;
- resolve the two pre-existing callback-count failures;
- confirm the final migration dependencies;
- verify production table engines read-only;
- do not copy or overwrite another agent's uncommitted files.

## 13. Second source-brief reconciliation

A fresh line-by-line pass against the re-pasted original request added ten
acceptance details that were previously implicit or too weakly assigned:

1. Product discovery intent is owned by seeded prompt/playbook authorities, not
   only a media transport parser; general UA/RU/EN requests show 3-4 catalog
   images and one caption, while explicit link requests may return a product URL.
2. T-shirt conversation order is fit first, exact product/fit size grid second,
   size choice third; no proposal exists before resolution.
3. The automated happy path proves zero manager task/alert and zero provider
   call before valid website submit.
4. Repeated payment intent after expiry issues a fresh proposal/token and never
   revives an expired bearer token.
5. Assisted full-payment receipt email is covered through PaymentAttempt, Order,
   verified delivery, forwarded payer, and crash recovery.
6. The delivered message first asks whether everything arrived correctly and
   whether the customer liked the order, then asks for a review/story tag.
7. Telegram delivered alerts and Instagram review lifecycle are independent
   channels with independent success/failure evidence.
8. Mobile sticky CTA behavior includes safe-area padding and focused-field
   occlusion checks at the smallest target viewports.
9. Cancelled, failed, unavailable, and cancellation-ambiguous states have
   explicit render and Playwright contracts with invalid actions suppressed.
10. `InitiateCheckout` occurs on the first valid payment submit, matching the
    requested funnel boundary, rather than on initial form interaction.
