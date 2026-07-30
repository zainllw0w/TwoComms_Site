# Instagram Assisted Checkout Acceptance Checklist

This is the authoritative completion checklist. An item may be checked only
when code, tests, and where applicable production evidence exist. Planning or a
successful command alone is not production proof.

## A. Integration and scope safety

- [ ] Fetch current `origin/main` immediately before implementation.
- [ ] Inspect `/private/tmp/twocomms-ig-verify.dIoXh3` and identify whether its
  Instagram Login changes were committed/merged.
- [ ] Obtain the parallel Instagram agent's final commit SHA or explicit
  no-merge decision before editing overlapping files or allocating migrations.
- [ ] Rebase the feature branch onto the final integration SHA.
- [ ] Preserve all unrelated dirty Custom Print and other worktrees.
- [ ] Resolve overlapping bot/model/URL files manually; do not copy stale files.
- [ ] Allocate management and orders migration numbers from the rebased graph.
- [ ] Record final dependencies on the latest merged management/orders migrations.
- [ ] Verify production table engines for all new enforced relationships.
- [ ] Resolve the two pre-existing `PostPaymentEventsDeferralTests` failures.
- [ ] Run and record a clean focused baseline before feature code.
- [ ] Keep legacy direct `IGDEAL-*` invoices payable and webhook-compatible.
- [ ] Prohibit all new direct Monobank URLs from the Instagram bot path.

## B. Proposal domain model

- [ ] Add `IgCheckoutProposal` with client/deal/episode ownership.
- [ ] Persist the exact `ensure_episode_for_deal()` episode on every proposal.
- [ ] Add explicit ready/viewed/details/invoice/paid/expired/revoked/superseded states.
- [ ] Add 12-hour expiry and server-side state helpers.
- [ ] Add monotonic revision and current item digest.
- [ ] Add locale and currency.
- [ ] Add catalog total, negotiated discount, quoted total, payment type, and
  requested payment amount.
- [ ] Add explicit `allow_promo`; default false when negotiated discount exists.
- [ ] Add optional PaymentAttempt link and supersession link.
- [ ] Use protected historical proposal relations plus exactly one
  `IgDeal.active_checkout_proposal` pointer serialized under a deal row lock.
- [ ] Add indexed state/expiry/client timestamps for management queries.
- [ ] Add `IgCheckoutProposalItem` snapshots with product/variant links.
- [ ] Snapshot title, SKU, image, color, fit, size, options, quantity, and prices.
- [ ] Preserve price source and conversation evidence message IDs.
- [ ] Add append-only `IgCheckoutRevision` audit records.
- [ ] Prevent update/delete of historical revisions through service/API paths.
- [ ] Add `IgCheckoutAccessToken` with SHA-256 digest, kind, expiry, revocation,
  use count, and last use.
- [ ] Never persist raw token in the token table.
- [ ] Add invoice-lifetime inventory reservation state with consume/release
  semantics; do not reserve during the whole unopened proposal lifetime.
- [ ] Add `IgLifecycleEvent` with unique event key, lease, delivery status,
  provider message ID, and classified errors.
- [ ] Persist exact `IgOrderAttribution` on every order-bound lifecycle event.
- [ ] Add model constraints for valid totals, revision, expiry, and payment state.
- [ ] Add migrations with production-compatible InnoDB/FK boundaries.
- [ ] Add admin or management observability without exposing secrets/PII.

## C. Strict product configuration

- [ ] Normalize single and multi-item controls through one validator.
- [ ] Require a published catalog product for every automated proposal item.
- [ ] Require quantity and enforce configured line/unit caps.
- [ ] Require a valid size when the product exposes sizes.
- [ ] Require classic/oversize fit for applicable T-shirts.
- [ ] Require any other active ProductFitOption when applicable.
- [ ] Reject inactive or product-mismatched fit options.
- [ ] Require color when multiple sellable variants exist.
- [ ] Reject a color variant belonging to another product.
- [ ] Reject out-of-stock/non-sellable variant combinations.
- [ ] Validate generic option values and labels.
- [ ] Use `variant_allows_purchase()` and `effective_cart_unit_price()`.
- [ ] Revalidate the full configuration before invoice creation.
- [ ] Keep the frozen proposal quote unchanged until expiry; catalog drift must
  block and require a new Direct revision, never silently reprice submit.
- [ ] Never infer a default fit, size, color, price, or discount from style/language.
- [ ] Ask the customer only for the missing choice.
- [ ] Show/send the relevant size guide before completing apparel configuration.
- [ ] Do not ask a redundant final confirmation after all required choices exist.
- [ ] Exclude unresolved custom-print requests from automated checkout.
- [ ] Test one shirt, one hoodie, two products, repeated lines, and 12-line limit.
- [ ] Atomically synchronize each proposal revision into `IgDeal` amounts,
  payment type/evidence, and `IgDealItem` snapshots used by episode/attribution.
- [ ] Prove proposal/deal/items/episode digests cannot diverge on rollback or
  concurrent revision.

## D. Pricing, negotiated totals, and promos

- [ ] Calculate catalog gross from authoritative current product services.
- [ ] Accept negotiated total only with current-episode message evidence.
- [ ] Represent multi-item negotiated pricing as an order-level discount.
- [ ] Never invent per-line allocation for an aggregate negotiated total.
- [ ] Keep requested prepayment separate from full order total.
- [ ] Extend PaymentAttempt with evidence-bound generic prepayment.
- [ ] Ensure full payment and prepayment both create one Purchase.
- [ ] Use full discounted order value as `Purchase.value`.
- [ ] Preserve actual provider money as `paid_value`/`paid_amount`.
- [ ] Never emit a Lead for verified prepayment.
- [ ] Permit promo entry for catalog pricing.
- [ ] Reject invalid, expired, exhausted, or user-ineligible promo codes.
- [ ] Define explicit anonymous-payer promo eligibility; never downgrade an
  account-scoped `can_be_used_by_user()` failure to unrestricted use.
- [ ] Do not stack promo and negotiated discount unless `allow_promo=True`.
- [ ] Recompute and lock promo discount under the invoice transaction.
- [ ] Reserve limited promo usage atomically; consume after verified Order and
  release only after confirmed cancellation/expiry/failure.
- [ ] Prove two concurrent invoices cannot consume one remaining promo use.
- [ ] Show base total, discount source, final total, and charge-now amount clearly.
- [ ] Include valid basket lines/discount in Monobank merchant payment info.

## E. Token, session, and forwarding security

- [ ] Generate access tokens from at least 256 bits of randomness.
- [ ] Compare token digests in constant-time-safe framework primitives.
- [ ] Reject expired, revoked, wrong-proposal, and malformed tokens.
- [ ] Token entry route contains no PII and performs no analytics.
- [ ] Establish a signed, proposal-scoped browser grant.
- [ ] Give each clean-page grant a random `grant_id` for per-browser analytics.
- [ ] Redirect to a token-free clean URL before loading analytics.
- [ ] Set `Cache-Control: no-store, private`.
- [ ] Set `X-Robots-Tag: noindex, nofollow`.
- [ ] Set `Referrer-Policy: no-referrer`.
- [ ] Ensure CSP does not leak or block the page.
- [ ] Make copy/share issue a separate CSRF-protected token.
- [ ] Make a forwarded link work in a clean independent browser session.
- [ ] Keep Instagram username/chat content off the public page.
- [ ] Store recipient PII only after valid submit in PaymentAttempt.
- [ ] First successful submit locks recipient data.
- [ ] Later viewers see only masked delivery/email/phone facts.
- [ ] Later viewers can continue the same invoice but cannot change recipient.
- [ ] Rate-limit token validation, share issuance, promo checks, and invoice submit.
- [ ] Prevent bearer token in analytics, logs, exception text, DOM, and source URL.
- [ ] Verify proxy/access logs omit or normalize the bearer-token path.

## F. Public mobile checkout UI

- [ ] Render official TwoComms identity and proposal reference on first viewport.
- [ ] Display proposal expiry/countdown and honest expired state.
- [ ] Display real selected product imagery, not generic atmosphere.
- [ ] Reserve 4:5 image dimensions before load.
- [ ] Display title, color swatch+label, fit, size, quantity, unit/line price.
- [ ] Keep multiple products scan-friendly and stable for arbitrary line counts.
- [ ] Keep the page useful when product image fails.
- [ ] Provide recipient full-name field.
- [ ] Provide Ukrainian phone input with normalization.
- [ ] Require email and explain that receipt/confirmation is sent there.
- [ ] Reuse signed Nova Poshta city autocomplete.
- [ ] Provide branch/post-locker segmented selection.
- [ ] Reuse signed warehouse autocomplete and server validation.
- [ ] Hide promo under a compact optional disclosure.
- [ ] Provide one dominant `Continue to payment - amount` action.
- [ ] Provide copy/share action with accessible name and confirmation.
- [ ] Provide a Direct correction action without allowing item edits on page.
- [ ] Provide server-rendered validation summaries and field errors.
- [ ] Provide stable loading state that cannot resize/shift the button.
- [ ] Provide truthful pending-payment polling state.
- [ ] Provide verified-only success page with order/delivery summary.
- [ ] Provide cancelled, failed, expired, unavailable, and superseded states.
- [ ] Preserve checkout state on browser back/visibility changes.
- [ ] Refresh current proposal revision on `visibilitychange`.
- [ ] Use UA/RU/EN based on client locale with safe language switching.
- [ ] Add legal/privacy/payment-support links without fake trust badges.

## G. Visual design and motion

- [ ] Use a near-black frame, light form surface, orange primary action, and
  green only for verified/valid states.
- [ ] Avoid purple/blue gradient dominance and one-note palette.
- [ ] Avoid giant hero copy, floating section cards, nested cards, particles,
  or decorative orbs.
- [ ] Use restrained editorial asymmetry only in product imagery.
- [ ] Keep facts and form fields aligned predictably.
- [ ] Use 8 px or smaller card radii unless existing design requires otherwise.
- [ ] Use Lucide/existing icon library for copy/share/status actions.
- [ ] Add tooltip/accessible name for unfamiliar icon actions.
- [ ] Use 300-400 ms one-time entrance animation only.
- [ ] Animate only opacity/transform for entrance.
- [ ] Add short stable loading and verified-success transitions.
- [ ] Disable nonessential movement under `prefers-reduced-motion`.
- [ ] No infinite shimmer, glow, rotating gradient, or layout-shifting animation.
- [ ] Verify text never overlaps or overflows at all target viewports.
- [ ] Verify visible keyboard focus and minimum 44 px controls.

## H. PaymentAttempt and Monobank integration

- [ ] Create no invoice on GET, preview, crawler, or invalid form.
- [ ] Lock proposal/client identity before checking for an existing attempt.
- [ ] Fingerprint by proposal+revision, not browser session.
- [ ] Create/reuse exactly one active PaymentAttempt.
- [ ] Claim invoice creation with a durable unguessable owner lease before the
  provider network call.
- [ ] Persist `invoice_creation_ambiguous` on timeout/crash/malformed response
  and prohibit blind automatic create retry.
- [ ] Heal ambiguous creation only from trusted provider reference truth or an
  audited manager resolution.
- [ ] Copy only validated recipient and signed Nova Poshta refs.
- [ ] Freeze product/cart snapshot and pricing into the attempt.
- [ ] Capture payer browser attribution server-side.
- [ ] Include customer email in provider payload where supported.
- [ ] Limit invoice validity to remaining proposal lifetime, maximum 12 hours.
- [ ] Reuse one existing invoice for duplicate clicks/browsers.
- [ ] Reconcile provider amount against `payment_amount`.
- [ ] Require matching invoice/reference, UAH/980 currency, exact minor amount,
  and provider-verified final success; under/overpayment remains review.
- [ ] Treat `hold` as pending unless an explicit two-stage capture contract is
  configured and proven final.
- [ ] Trust only signed/pull-verified provider success.
- [ ] Materialize exactly one Order under webhook/return concurrency.
- [ ] Preserve secure success-page ownership for the paying browser.
- [ ] Do not show paid success before provider verification.
- [ ] Handle failed/cancelled/expired attempts without creating an Order.
- [ ] Reserve inventory for the payable invoice lifetime; consume on Order and
  release on confirmed cancellation/expiry/failure.
- [ ] Cancel old invoice before post-invoice proposal replacement.
- [ ] Confirm provider cancellation before permitting a second invoice.
- [ ] Let verified payment win a correction/payment race.
- [ ] Keep legacy direct IG invoice webhook behavior unchanged.

## I. Instagram binding adapter

- [ ] Detect assisted-checkout source from trusted PaymentAttempt metadata.
- [ ] Run adapter only after Order/payment commit.
- [ ] Keep Order/payment successful if adapter needs reconciliation.
- [ ] Write append-only provider-attempt payment evidence.
- [ ] Update `IgPaymentProjection` from trusted PaymentAttempt scope without a
  second analytics Purchase.
- [ ] Bind IgDeal.order.
- [ ] Create exactly one IgOrderAttribution with `provider_attempt` source.
- [ ] Bind the current commercial episode.
- [ ] Finish at proposal=`paid`, deal/client=`order_created`, then synchronize
  episode payment and bind the Order using current service signatures.
- [ ] Create one `payment_verified` lifecycle event.
- [ ] Add bounded reconciliation for converted attempts missing linkage.
- [ ] Test crash after Order commit and before every adapter sub-step.
- [ ] Test adapter replay to a fully linked state.
- [ ] Preserve reversal/refund behavior and automatic fulfillment blocks.
- [ ] Propagate post-materialization reversal/refund through PaymentAttempt,
  Order, proposal/deal/projection, fulfillment block, and one manager review.

## J. Bot prompts, playbooks, and link delivery

- [ ] Change injected payment protocol from direct invoice to proposal page.
- [ ] Update editable seeded playbooks without overwriting admin customizations.
- [ ] Keep `[PAYLINK]` compatibility while changing server behavior.
- [ ] Add strict complete-item controls for all item counts.
- [ ] Detect `How can I pay?` from current commercial context.
- [ ] Ask missing fit/size/color/quantity rather than generating an invalid link.
- [ ] Generate the proposal immediately when complete.
- [ ] Send clear two-minute checkout copy and correction instructions.
- [ ] Mention 12-hour validity and shareability accurately.
- [ ] Never let Gemini type or invent Monobank/provider URLs.
- [ ] Treat own-domain proposal URL as critical payment delivery.
- [ ] Never degrade a payment proposal to text that claims a link was sent.
- [ ] Resolve Meta 508/window fallback from assisted proposal delivery records,
  not only `IgDeal.invoice_url`/Monobank URL regex.
- [ ] Persist classified Meta 508/2534122 delivery failure honestly.
- [ ] Retry only provider-confirmed retryable failures within policy bounds.
- [ ] Prevent automated HUMAN_AGENT use.
- [ ] Keep client stage at checkout until invoice, then payment_pending.
- [ ] Keep already-paid clients from receiving duplicate current-episode proposal.
- [ ] Update default prompt, `PAYMENT_PROTOCOL_NOTE`, seeded Product/SKU context,
  and exact persisted legacy prompt fragments in one idempotent migration.
- [ ] Keep `[ORDER]` runtime only for legacy direct-invoice delivery collection.

## K. Product discovery media

- [ ] Add a bounded structured control for catalog media recommendations.
- [ ] Select only published catalog products/variants.
- [ ] Prefer three or four real product images.
- [ ] Use selected variant imagery when color is known.
- [ ] Validate media host, scheme, MIME, size, and count.
- [ ] Use native multi-image/carousel format only when supported by active transport.
- [ ] Provide deterministic bounded image sequence fallback.
- [ ] Follow media with one compact product-name/caption message.
- [ ] Avoid product URLs unless requested/useful.
- [ ] Avoid untrusted Gemini-provided media URLs.
- [ ] Record outbound media delivery status and partial/ambiguous sends.
- [ ] Test transport payload without live customer sends.

## L. Lifecycle triggers and Direct messages

- [ ] Add durable lifecycle event emission independent of Telegram success.
- [ ] Create `payment_verified` from verified adapter only.
- [ ] Detect first committed non-empty tracking number.
- [ ] Create `ttn_created` even if order status changes in a separate save.
- [ ] Key TTN idempotency by order and normalized tracking digest.
- [ ] Use official Nova Poshta tracking URL.
- [ ] Detect delivery from canonical Nova Poshta status code, not localized text.
- [ ] Create `delivered_review_requested` only after committed `done` transition.
- [ ] Key delivery idempotency by order and provider status code.
- [ ] Bind every event to exact Order, attribution, deal, episode, and IgClient.
- [ ] Localize payment, TTN, and review messages.
- [ ] Keep order/payment/TTN facts deterministic and AI-proof.
- [ ] Send full confirmed recipient name, phone, and Nova Poshta destination only
  to the exact original bound Instagram conversation; keep forwarded web and
  management list surfaces masked.
- [ ] Persist independent post-payment channel states for Telegram, receipt,
  Meta Purchase, TikTok Purchase, and Instagram lifecycle emission.
- [ ] Never let one successful channel clear another channel's pending state.
- [ ] Lease lifecycle work and revalidate ownership before final save.
- [ ] Send ordinary RESPONSE only inside conservative Meta window.
- [ ] Mark sent only after confirmed Meta response/provider ID.
- [ ] Return/persist a structured provider delivery receipt while preserving
  tuple compatibility for legacy send callers.
- [ ] Execute lifecycle sends inside existing reply/customer send boundaries to
  close opt-out/takeover races before the provider call.
- [ ] Treat timeout/5xx as ambiguous and avoid blind replay.
- [ ] Outside window, create one prepared manager task and one deduped alert.
- [ ] Never set legacy `shipped_notified_at` on failed/ambiguous delivery.
- [ ] Reconcile missing payment, TTN, and delivery events after crash.
- [ ] Reconcile verified orders with missing receipt/CAPI/Telegram/lifecycle
  channel markers regardless of Telegram success.
- [ ] Test repeated signals, cron runs, daemon restarts, and concurrent workers.

## M. Management Orders workspace

- [ ] Add `Awaiting payment` filter/count without breaking existing filters.
- [ ] Show ready/viewed/details/invoice/paid/expired state.
- [ ] Show client, revision, item count, total, expiry, and classified delivery state.
- [ ] Do not expose bearer token or raw PII in list/API payload.
- [ ] Add safe proposal preview.
- [ ] Add issue-copy-token action.
- [ ] Add bot resend action through the durable delivery path.
- [ ] Add revoke action with audit event.
- [ ] Gate revoke/supersede on trusted provider-confirmed non-payable state;
  payable or ambiguous invoice remains immutable and opens review.
- [ ] Add revision and lifecycle history.
- [ ] Make the normal flow observable but not manager-dependent.
- [ ] Verify mobile management layout and keyboard interaction.

## N. Analytics and attribution

- [ ] Fire ViewContent only after clean proposal render.
- [ ] Fire ViewContent/InitiateCheckout per eligible clean grant, not once for
  the whole proposal.
- [ ] Use HMAC event IDs derived from event/proposal/revision/grant ID.
- [ ] Keep original and forwarded payer InitiateCheckout IDs distinct while
  deduplicating Pixel/CAPI for the same grant.
- [ ] Fire AddPaymentInfo only after valid invoice creation.
- [ ] Share AddPaymentInfo event ID between browser and CAPI.
- [ ] Fire Purchase only after verified provider success.
- [ ] Share Purchase event ID between success page and CAPI.
- [ ] Ensure CAPI Purchase works when payer never returns.
- [ ] Ensure pending/failed return never emits Purchase.
- [ ] Preserve fbp/fbc/IP/UA server authority.
- [ ] Freeze the winning payer browser attribution on first valid submit and
  prevent later viewers from overwriting it.
- [ ] Respect existing consent gating for browser events and approved privacy/
  exclusion policy for server events.
- [ ] Preserve original Instagram deal/client/episode attribution.
- [ ] Attribute browser events to actual forwarding/paying browser.
- [ ] Store full discounted value and separate paid value.
- [ ] Emit no extra Lead for prepayment.
- [ ] Test deduplication and payload serialization with network mocked.
- [ ] Send no live Meta/TikTok test events without explicit authorization.

## O. Automated tests

- [ ] Proposal model/state/constraint tests.
- [ ] Token handshake/share/revocation/expiry tests.
- [ ] Strict one/multi-item validation tests.
- [ ] Negotiated total and promo-stacking tests.
- [ ] Signed Nova Poshta form tests.
- [ ] PII masking and cache/referrer/robots header tests.
- [ ] Forwarded-browser and first-submit-wins tests.
- [ ] Duplicate POST and simultaneous payer TransactionTestCase.
- [ ] PaymentAttempt generic prepayment lifecycle tests.
- [ ] Monobank create/return/webhook amount and race tests.
- [ ] Instagram adapter and reconciliation tests.
- [ ] Legacy direct invoice regression tests.
- [ ] Bot intent/control/missing-option/proposal-copy tests.
- [ ] Product-media transport payload tests.
- [ ] Payment/TTN/delivered lifecycle idempotency tests.
- [ ] Meta window, HUMAN_AGENT rejection, ambiguous send tests.
- [ ] Orders workspace API/template tests.
- [ ] Pixel/CAPI event timing/dedup/value tests.
- [ ] Email/Telegram persistence and recovery tests.
- [ ] Migration forward and migration-drift tests.

## P. Browser and visual verification

- [ ] Run checkout with real local catalog imagery and mocked provider create.
- [ ] Capture and inspect 320x568 screenshot.
- [ ] Capture and inspect 375x812 screenshot.
- [ ] Capture and inspect 430x932 screenshot.
- [ ] Capture and inspect 768x1024 screenshot.
- [ ] Capture and inspect 1440x900 screenshot.
- [ ] Verify 1, 2, 4, and long product lists.
- [ ] Verify keyboard-only form and Nova Poshta selector.
- [ ] Verify mocked Nova Poshta city/warehouse APIs, branch/locker switching,
  signed hidden tokens, stale token, and wrong-city rejection through the real
  `nova-poshta-form-bridge.js` path.
- [ ] Verify error, loading, pending, paid, expired, and superseded states.
- [ ] Verify reduced-motion screenshot/state.
- [ ] Verify no overlap, horizontal overflow, clipped text, or layout shift.
- [ ] Verify product images render and are inspectable.
- [ ] Verify page-specific animation runs once and remains smooth.
- [ ] Verify token is absent from analytics/network source URLs.
- [ ] Verify CSP console has no new violations.
- [ ] Verify authenticated management mobile/desktop filter, preview,
  copy/resend/revoke/history, permissions, focus order, and overflow.

## Q. Full verification before commit

- [ ] Run focused new checkout tests.
- [ ] Run all listed IG bot/payment/order linkage suites.
- [ ] Run `orders.tests.test_payment_attempts`.
- [ ] Run `storefront.tests.test_monobank_webhook`.
- [ ] Run Nova Poshta selector/tracking tests.
- [ ] Run analytics loader/Meta Pixel/TikTok tests.
- [ ] Run `python manage.py check`.
- [ ] Run `python manage.py makemigrations --check --dry-run`.
- [ ] Run JavaScript tests/lint relevant to the new page.
- [ ] Run `git diff --check`.
- [ ] Run independent read-only review of security/payment/lifecycle boundaries.
- [ ] Reconcile every checklist mark against test or code evidence.

## R. Commit, push, deploy, and production proof

- [ ] Re-fetch and rebase/merge current `main` without scope drift.
- [ ] Confirm staged paths contain only this feature and its plan docs.
- [ ] Commit in small reviewed checkpoints.
- [ ] Push the intended feature/main branch as agreed at execution time.
- [ ] Confirm remote SHA.
- [ ] On server, pull with `--ff-only`.
- [ ] Run production migration.
- [ ] Run production `manage.py check`.
- [ ] Run collectstatic and compressor.
- [ ] Seed/update bot playbooks safely.
- [ ] Restart Passenger.
- [ ] Ensure Instagram bot daemon and bounded reconcilers are running.
- [ ] Install non-overlapping `flock` schedules for checkout and post-payment
  reconcilers while preserving unrelated cron entries.
- [ ] Verify server HEAD equals intended SHA.
- [ ] Verify new tables, indexes, engines, and migration state.
- [ ] Verify proposal route headers and staff-safe preview.
- [ ] Verify Orders workspace pending section.
- [ ] Verify outbox/queue/daemon health.
- [ ] Verify legacy direct-invoice polling through a no-side-effect dry-run or
  check-only command; do not call the mutating poller as a smoke test.
- [ ] Verify live analytics configuration, token-free URLs, consent bridge,
  deterministic IDs, and persisted markers without emitting a live ad event.
- [ ] Verify persisted idempotency markers for a non-live test fixture or approved test.
- [ ] Verify no real customer/Meta/Monobank event was sent during smoke tests.
- [ ] Document any production-only limitation honestly.
- [ ] If production evidence is committed afterward, push/pull that docs commit
  and re-prove local/origin/server SHA equality.
