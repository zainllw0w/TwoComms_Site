# Instagram Assisted Checkout Acceptance Checklist

This is the authoritative completion checklist. An item may be checked only
when code, tests, and where applicable production evidence exist. Planning or a
successful command alone is not production proof. `[x]` means closed for the
current logic slice; visual/browser polish and production rollout remain
explicitly deferred until the next pass.

## A. Integration and scope safety

- [x] Reconcile every clause of the re-pasted original brief against the
  implementation plan's Original brief reconciliation table before coding.
- [x] Fetch current `origin/main` immediately before implementation.
- [x] Inspect `/private/tmp/twocomms-ig-verify.dIoXh3` and identify whether its
  Instagram Login changes were committed/merged.
- [x] Obtain the parallel Instagram agent's final commit SHA or explicit
  no-merge decision before editing overlapping files or allocating migrations.
- [x] Rebase the feature branch onto the final integration SHA.
- [x] Preserve all unrelated dirty Custom Print and other worktrees.
- [x] Resolve overlapping bot/model/URL files manually; do not copy stale files.
- [x] Allocate management and orders migration numbers from the rebased graph.
- [x] Record final dependencies on the latest merged management/orders migrations.
- [x] Verify production table engines for all new enforced relationships.
- [x] Resolve the two pre-existing `PostPaymentEventsDeferralTests` failures.
- [x] Run and record a clean focused baseline before feature code.
- [x] Keep legacy direct `IGDEAL-*` invoices payable and webhook-compatible.
- [x] Prohibit all new direct Monobank URLs from the Instagram bot path.

## B. Proposal domain model

- [x] Add `IgCheckoutProposal` with client/deal/episode ownership.
- [x] Persist the exact `ensure_episode_for_deal()` episode on every proposal.
- [x] Add explicit ready/viewed/details/invoice/paid/expired/revoked/superseded states.
- [x] Add 25-minute expiry and server-side state helpers.
- [x] Add monotonic revision and current item digest.
- [x] Add locale and currency.
- [x] Add catalog total, negotiated discount, quoted total, payment type, and
  requested payment amount.
- [x] Add explicit `allow_promo`; default false when negotiated discount exists.
- [x] Add optional PaymentAttempt link and supersession link.
- [x] Use protected historical proposal relations plus exactly one
  `IgDeal.active_checkout_proposal` pointer serialized under a deal row lock.
- [x] Add indexed state/expiry/client timestamps for management queries.
- [x] Add `IgCheckoutProposalItem` snapshots with product/variant links.
- [x] Snapshot title, SKU, image, color, fit, size, options, quantity, and prices.
- [x] Preserve price source and conversation evidence message IDs.
- [x] Add append-only `IgCheckoutRevision` audit records.
- [x] Prevent update/delete of historical revisions through service/API paths.
- [x] Add `IgCheckoutAccessToken` with SHA-256 digest, kind, expiry, revocation,
  use count, and last use.
- [x] Never persist raw token in the token table.
- [x] Add invoice-lifetime inventory reservation state with consume/release
  semantics; do not reserve during the whole unopened proposal lifetime.
- [x] Add `IgLifecycleEvent` with unique event key, lease, delivery status,
  provider message ID, and classified errors.
- [x] Persist exact `IgOrderAttribution` on every order-bound lifecycle event.
- [x] Add model constraints for valid totals, revision, expiry, and payment state.
- [x] Add migrations with production-compatible InnoDB/FK boundaries.
- [x] Add admin or management observability without exposing secrets/PII.

## C. Strict product configuration

- [x] Normalize single and multi-item controls through one validator.
- [x] Require a published catalog product for every automated proposal item.
- [x] Require quantity and enforce configured line/unit caps.
- [x] Require a valid size when the product exposes sizes.
- [x] Require classic/oversize fit for applicable T-shirts.
- [x] Require any other active ProductFitOption when applicable.
- [x] Reject inactive or product-mismatched fit options.
- [x] Require color when multiple sellable variants exist.
- [x] Reject a color variant belonging to another product.
- [x] Reject out-of-stock/non-sellable variant combinations.
- [x] Validate generic option values and labels.
- [x] Use `variant_allows_purchase()` and `effective_cart_unit_price()`.
- [x] Revalidate the full configuration before invoice creation.
- [x] Keep the frozen proposal quote unchanged until expiry; catalog drift must
  block and require a new Direct revision, never silently reprice submit.
- [x] Never infer a default fit, size, color, price, or discount from style/language.
- [x] Ask the customer only for the missing choice.
- [x] Show/send the relevant size guide before completing apparel configuration.
- [x] Do not ask a redundant final confirmation after all required choices exist.
- [x] Exclude unresolved custom-print requests from automated checkout.
- [x] Test one shirt, one hoodie, two products, repeated lines, and 12-line limit.
- [x] Atomically synchronize each proposal revision into `IgDeal` amounts,
  payment type/evidence, and `IgDealItem` snapshots used by episode/attribution.
- [x] Prove proposal/deal/items/episode digests cannot diverge on rollback or
  concurrent revision.

## D. Pricing, negotiated totals, and promos

- [x] Calculate catalog gross from authoritative current product services.
- [x] Accept negotiated total only with current-episode message evidence.
- [x] Represent multi-item negotiated pricing as an order-level discount.
- [x] Never invent per-line allocation for an aggregate negotiated total.
- [x] Keep requested prepayment separate from full order total.
- [x] Extend PaymentAttempt with evidence-bound generic prepayment.
- [x] Ensure full payment and prepayment both create one Purchase.
- [x] Use full discounted order value as `Purchase.value`.
- [x] Preserve actual provider money as `paid_value`/`paid_amount`.
- [x] Never emit a Lead for verified prepayment.
- [x] Permit promo entry for catalog pricing.
- [x] Reject invalid, expired, exhausted, or user-ineligible promo codes.
- [x] Define explicit anonymous-payer promo eligibility; never downgrade an
  account-scoped `can_be_used_by_user()` failure to unrestricted use.
- [x] Do not stack promo and negotiated discount unless `allow_promo=True`.
- [x] Recompute and lock promo discount under the invoice transaction.
- [x] Reserve limited promo usage atomically; consume after verified Order and
  release only after confirmed cancellation/expiry/failure.
- [x] Prove two concurrent invoices cannot consume one remaining promo use.
- [x] Show base total, discount source, final total, and charge-now amount clearly.
- [x] Include valid basket lines/discount in Monobank merchant payment info.

## E. Token, session, and forwarding security

- [x] Generate access tokens from at least 256 bits of randomness.
- [x] Compare token digests in constant-time-safe framework primitives.
- [x] Reject expired, revoked, wrong-proposal, and malformed tokens.
- [x] Token entry route contains no PII and performs no analytics.
- [x] Establish a signed, proposal-scoped browser grant.
- [x] Give each clean-page grant a random `grant_id` for per-browser analytics.
- [x] Redirect to a token-free clean URL before loading analytics.
- [x] Set `Cache-Control: no-store, private`.
- [x] Set `X-Robots-Tag: noindex, nofollow`.
- [x] Set `Referrer-Policy: no-referrer`.
- [x] Ensure CSP does not leak or block the page.
- [x] Make copy/share issue a separate CSRF-protected token.
- [x] Make a forwarded link work in a clean independent browser session.
- [x] Keep Instagram username/chat content off the public page.
- [x] Store recipient PII only after valid submit in PaymentAttempt.
- [x] First successful submit locks recipient data.
- [x] Later viewers see only masked delivery/email/phone facts.
- [x] Later viewers can continue the same invoice but cannot change recipient.
- [x] Rate-limit token validation, share issuance, promo checks, and invoice submit.
- [x] Prevent bearer token in analytics, logs, exception text, DOM, and source URL.
- [ ] Verify proxy/access logs omit or normalize the bearer-token path.

## F. Public mobile checkout UI

- [x] Render official TwoComms identity and proposal reference on first viewport.
- [x] Display proposal expiry/countdown and honest expired state.
- [x] Display real selected product imagery, not generic atmosphere.
- [x] Reserve 4:5 image dimensions before load.
- [x] Display title, color swatch+label, fit, size, quantity, unit/line price.
- [x] Keep multiple products scan-friendly and stable for arbitrary line counts.
- [x] Keep the page useful when product image fails.
- [x] Provide recipient full-name field.
- [x] Provide Ukrainian phone input with normalization.
- [x] Keep receipt email optional, explain that a receipt/confirmation is sent
  there only when supplied, normalize blank values, and validate any non-empty
  value before provider I/O.
- [x] Render one shared maintainable HTML checkout template from proposal rows;
  never generate or deploy a physical page file per customer.
- [x] Substitute frozen existing catalog/variant images and facts directly so
  proposal creation remains fast and deterministic.
- [x] Reuse signed Nova Poshta city autocomplete.
- [x] Provide branch/post-locker segmented selection.
- [x] Reuse signed warehouse autocomplete and server validation.
- [x] Hide promo under a compact optional disclosure.
- [x] Provide one dominant `Continue to payment - amount` action.
- [x] Provide copy/share action with accessible name and confirmation.
- [x] Provide a Direct correction action without allowing item edits on page.
- [x] Provide server-rendered validation summaries and field errors.
- [x] Provide stable loading state that cannot resize/shift the button.
- [x] Provide truthful pending-payment polling state.
- [x] Provide verified-only success page with order/delivery summary.
- [x] Provide cancelled, failed, expired, unavailable, and superseded states.
- [x] Provide a cancellation-ambiguous review state with every invalid payment
  or replacement action suppressed.
- [x] Preserve checkout state on browser back/visibility changes.
- [x] Refresh current proposal revision on `visibilitychange`.
- [x] Use UA/RU/EN based on client locale with safe language switching.
- [x] Add legal/privacy/payment-support links without fake trust badges.

## G. Visual design and motion

- [x] Use the approved C3 Brand Night system: deep charcoal frame and form
  surfaces, warm orange primary action, and green only for verified/valid states.
- [x] Avoid purple/blue gradient dominance and one-note palette.
- [x] Avoid giant hero copy, floating section cards, nested cards, particles,
  or decorative orbs.
- [x] Keep product imagery calm and consistent; editorial asymmetry is optional
  under the approved C3 Brand Night specification.
- [x] Keep facts and form fields aligned predictably.
- [x] Use 8 px or smaller card radii unless existing design requires otherwise.
- [ ] Use Lucide/existing icon library for copy/share/status actions.
- [x] Add tooltip/accessible name for unfamiliar icon actions.
- [x] Use short one-time entrance motion plus one bounded CTA readiness sheen;
  never use autonomous or infinite motion.
- [x] Animate only opacity/transform for entrance.
- [ ] Add short stable loading and verified-success transitions.
- [x] Ensure no animated/transformed ancestor changes the containing block of
  the fixed mobile payment rail.
- [x] Disable nonessential movement under `prefers-reduced-motion`.
- [x] No infinite shimmer, glow, rotating gradient, or layout-shifting animation.
- [ ] Verify text never overlaps or overflows at all target viewports.
- [x] Verify visible keyboard focus and minimum 44 px controls.
- [x] Use `env(safe-area-inset-bottom)` plus terminal scroll padding and verify
  the sticky CTA never covers focused fields, errors, or the final item row.

## H. PaymentAttempt and Monobank integration

- [x] Create no invoice on GET, preview, crawler, or invalid form.
- [x] Lock proposal/client identity before checking for an existing attempt.
- [x] Fingerprint by proposal+revision, not browser session.
- [x] Create/reuse exactly one active PaymentAttempt.
- [x] Claim invoice creation with a durable unguessable owner lease before the
  provider network call.
- [x] Persist `invoice_creation_ambiguous` on timeout/crash/malformed response
  and prohibit blind automatic create retry.
- [x] Heal ambiguous creation only from trusted provider reference truth or an
  audited manager resolution.
- [x] Copy only validated recipient and signed Nova Poshta refs.
- [x] Freeze product/cart snapshot and pricing into the attempt.
- [x] Capture payer browser attribution server-side.
- [x] Include customer email in provider payload where supported.
- [x] Prove assisted full-payment email reaches PaymentAttempt and Order, sends
  exactly one receipt after verified materialization, and recovers idempotently
  after receipt failure, including a forwarded payer.
- [x] Limit invoice validity to remaining proposal lifetime, maximum 25 minutes.
- [x] Reuse one existing invoice for duplicate clicks/browsers.
- [x] Reconcile provider amount against `payment_amount`.
- [x] Require matching invoice/reference, UAH/980 currency, exact minor amount,
  and provider-verified final success; under/overpayment remains review.
- [x] Treat `hold` as pending unless an explicit two-stage capture contract is
  configured and proven final.
- [x] Trust only signed/pull-verified provider success.
- [x] Materialize exactly one Order under webhook/return concurrency.
- [x] Preserve secure success-page ownership for the paying browser.
- [x] Do not show paid success before provider verification.
- [x] Handle failed/cancelled/expired attempts without creating an Order.
- [x] Reserve inventory for the payable invoice lifetime; consume on Order and
  release on confirmed cancellation/expiry/failure.
- [x] Cancel old invoice before post-invoice proposal replacement.
- [x] Confirm provider cancellation before permitting a second invoice.
- [x] Let verified payment win a correction/payment race.
- [x] Keep legacy direct IG invoice webhook behavior unchanged.

## I. Instagram binding adapter

- [x] Detect assisted-checkout source from trusted PaymentAttempt metadata.
- [x] Run adapter only after Order/payment commit.
- [x] Keep Order/payment successful if adapter needs reconciliation.
- [x] Write append-only provider-attempt payment evidence.
- [x] Update `IgPaymentProjection` from trusted PaymentAttempt scope without a
  second analytics Purchase.
- [x] Bind IgDeal.order.
- [x] Create exactly one IgOrderAttribution with `provider_attempt` source.
- [x] Bind the current commercial episode.
- [x] Finish at proposal=`paid`, deal/client=`order_created`, then synchronize
  episode payment and bind the Order using current service signatures.
- [x] Create one `payment_verified` lifecycle event.
- [x] Add bounded reconciliation for converted attempts missing linkage.
- [x] Test crash after Order commit and before every adapter sub-step.
- [x] Test adapter replay to a fully linked state.
- [x] Preserve reversal/refund behavior and automatic fulfillment blocks.
- [x] Propagate post-materialization reversal/refund through PaymentAttempt,
  Order, proposal/deal/projection, fulfillment block, and one manager review.

## J. Bot prompts, playbooks, and link delivery

- [x] Change injected payment protocol from direct invoice to proposal page.
- [x] Update editable seeded playbooks without overwriting admin customizations.
- [x] Keep `[PAYLINK]` compatibility while changing server behavior.
- [x] Add strict complete-item controls for all item counts.
- [x] Detect `How can I pay?` from current commercial context.
- [x] Ask missing fit/size/color/quantity rather than generating an invalid link.
- [x] Generate the proposal immediately when complete.
- [x] Send clear two-minute checkout copy and correction instructions.
- [x] Mention 25-minute validity and shareability accurately.
- [x] Never let Gemini type or invent Monobank/provider URLs.
- [x] Treat own-domain proposal URL as critical payment delivery.
- [x] Never degrade a payment proposal to text that claims a link was sent.
- [x] Resolve Meta 508/window fallback from assisted proposal delivery records,
  not only `IgDeal.invoice_url`/Monobank URL regex.
- [x] Persist classified Meta 508/2534122 delivery failure honestly.
- [x] Retry only provider-confirmed retryable failures within policy bounds.
- [x] Prevent automated HUMAN_AGENT use.
- [x] Keep client stage at checkout until invoice, then payment_pending.
- [x] Keep already-paid clients from receiving duplicate current-episode proposal.
- [x] Update default prompt, `PAYMENT_PROTOCOL_NOTE`, seeded Product/SKU context,
  and exact persisted legacy prompt fragments in one idempotent migration.
- [x] Keep `[ORDER]` runtime only for legacy direct-invoice delivery collection.

## K. Product discovery media

- [x] Add a bounded structured control for catalog media recommendations.
- [x] Select only published catalog products/variants.
- [x] Prefer three or four real product images.
- [x] Use selected variant imagery when color is known.
- [x] Validate media host, scheme, MIME, size, and count.
- [x] Use native multi-image/carousel format only when supported by active transport.
- [x] Provide deterministic bounded image sequence fallback.
- [x] Follow media with one compact product-name/caption message.
- [x] Avoid product URLs unless requested/useful.
- [x] Avoid untrusted Gemini-provided media URLs.
- [x] Record outbound media delivery status and partial/ambiguous sends.
- [x] Test transport payload without live customer sends.

## L. Lifecycle triggers and Direct messages

- [x] Add durable lifecycle event emission independent of Telegram success.
- [x] Create `payment_verified` from verified adapter only.
- [x] Detect first committed non-empty tracking number.
- [x] Create `ttn_created` even if order status changes in a separate save.
- [x] Key TTN idempotency by order and normalized tracking digest.
- [x] Use official Nova Poshta tracking URL.
- [x] Detect delivery from canonical Nova Poshta status code, not localized text.
- [x] Create `delivered_review_requested` only after committed `done` transition.
- [x] Key delivery idempotency by order and provider status code.
- [x] Bind every event to exact Order, attribution, deal, episode, and IgClient.
- [x] Localize payment, TTN, and review messages.
- [x] Ask whether everything arrived correctly and whether the customer liked
  the order before politely requesting a review or `@twocomms` story tag.
- [x] Keep order/payment/TTN facts deterministic and AI-proof.
- [x] Send full confirmed recipient name, phone, and Nova Poshta destination only
  to the exact original bound Instagram conversation; keep forwarded web and
  management list surfaces masked.
- [x] Persist independent post-payment channel states for Telegram, receipt,
  Meta Purchase, TikTok Purchase, and Instagram lifecycle emission.
- [x] Never let one successful channel clear another channel's pending state.
- [x] Prove delivered-status Telegram and Instagram outcomes are independent in
  both success and failure directions.
- [x] Lease lifecycle work and revalidate ownership before final save.
- [x] Send ordinary RESPONSE only inside conservative Meta window.
- [x] Mark sent only after confirmed Meta response/provider ID.
- [x] Return/persist a structured provider delivery receipt while preserving
  tuple compatibility for legacy send callers.
- [x] Execute lifecycle sends inside existing reply/customer send boundaries to
  close opt-out/takeover races before the provider call.
- [x] Treat timeout/5xx as ambiguous and avoid blind replay.
- [x] Outside window, create one prepared manager task and one deduped alert.
- [x] Never set legacy `shipped_notified_at` on failed/ambiguous delivery.
- [x] Reconcile missing payment, TTN, and delivery events after crash.
- [x] Reconcile verified orders with missing receipt/CAPI/Telegram/lifecycle
  channel markers regardless of Telegram success.
- [x] Test repeated signals, cron runs, daemon restarts, and concurrent workers.

## M. Management Orders workspace

- [x] Add `Awaiting payment` filter/count without breaking existing filters.
- [x] Show ready/viewed/details/invoice/paid/expired state.
- [x] Show client, revision, item count, total, expiry, and classified delivery state.
- [x] Do not expose bearer token or raw PII in list/API payload.
- [x] Add safe proposal preview.
- [x] Add issue-copy-token action.
- [x] Add bot resend action through the durable delivery path.
- [x] Add revoke action with audit event.
- [x] Gate revoke/supersede on trusted provider-confirmed non-payable state;
  payable or ambiguous invoice remains immutable and opens review.
- [x] Add revision and lifecycle history.
- [x] Make the normal flow observable but not manager-dependent.
- [ ] Verify mobile management layout and keyboard interaction.

## N. Analytics and attribution

- [x] Fire ViewContent only after clean proposal render.
- [x] Fire ViewContent/InitiateCheckout per eligible clean grant, not once for
  the whole proposal.
- [x] Fire InitiateCheckout only after the first valid Continue-to-payment
  submit; render, focus, typing, validation failure, preload, and crawler emit none.
- [x] Use HMAC event IDs derived from event/proposal/revision/grant ID.
- [x] Keep original and forwarded payer InitiateCheckout IDs distinct while
  deduplicating Pixel/CAPI for the same grant.
- [x] Fire AddPaymentInfo only after valid invoice creation.
- [x] Share AddPaymentInfo event ID between browser and CAPI.
- [x] Fire Purchase only after verified provider success.
- [x] Share Purchase event ID between success page and CAPI.
- [x] Ensure CAPI Purchase works when payer never returns.
- [x] Ensure pending/failed return never emits Purchase.
- [x] Preserve fbp/fbc/IP/UA server authority.
- [x] Freeze the winning payer browser attribution on first valid submit and
  prevent later viewers from overwriting it.
- [x] Respect existing consent gating for browser events and approved privacy/
  exclusion policy for server events.
- [x] Preserve original Instagram deal/client/episode attribution.
- [x] Attribute browser events to actual forwarding/paying browser.
- [x] Store full discounted value and separate paid value.
- [x] Emit no extra Lead for prepayment.
- [x] Test deduplication and payload serialization with network mocked.
- [x] Send no live Meta/TikTok test events without explicit authorization.

## O. Automated tests

- [x] Proposal model/state/constraint tests.
- [x] Token handshake/share/revocation/expiry tests.
- [x] Strict one/multi-item validation tests.
- [x] Negotiated total and promo-stacking tests.
- [x] Signed Nova Poshta form tests.
- [x] PII masking and cache/referrer/robots header tests.
- [x] Forwarded-browser and first-submit-wins tests.
- [x] Duplicate POST and simultaneous payer TransactionTestCase.
- [x] PaymentAttempt generic prepayment lifecycle tests.
- [x] Monobank create/return/webhook amount and race tests.
- [x] Instagram adapter and reconciliation tests.
- [x] Legacy direct invoice regression tests.
- [x] Bot intent/control/missing-option/proposal-copy tests.
- [x] Product/fit-specific size-grid conversation tests: fit first, exact grid,
  then size, with no proposal before all choices are resolved.
- [x] No-manager happy-path test: one proposal and own-domain URL, zero provider
  call before web submit, and zero manager task/alert.
- [x] Expired-link renewal test creates a fresh proposal/token automatically and
  never revives the expired bearer token.
- [x] Product-media transport payload tests.
- [x] UA/RU/EN discovery intent tests prove general requests emit 3-4 catalog
  images plus one caption and no URL; explicit link requests may emit a URL.
- [x] Payment/TTN/delivered lifecycle idempotency tests.
- [x] Meta window, HUMAN_AGENT rejection, ambiguous send tests.
- [x] Orders workspace API/template tests.
- [x] Pixel/CAPI event timing/dedup/value tests.
- [x] Email/Telegram persistence and recovery tests.
- [x] Migration forward and migration-drift tests.

## P. Browser and visual verification

- [x] Run checkout with real local catalog imagery and mocked provider create.
- [x] Capture and inspect 320x568 screenshot.
- [x] Capture and inspect 375x812 screenshot.
- [x] Capture and inspect 430x932 screenshot.
- [x] Capture and inspect 768x1024 screenshot.
- [x] Capture and inspect 1440x900 screenshot.
- [ ] Verify 1, 2, 4, and long product lists.
- [ ] Verify keyboard-only form and Nova Poshta selector.
- [x] At 320x568 and 430x932, focus every delivery/promo field and prove the
  sticky CTA does not occlude the field, error, or terminal content.
- [ ] Verify cancelled, failed, unavailable, and cancellation-ambiguous states
  suppress invalid actions and expose the correct Direct/retry/review route.
- [ ] Verify mocked Nova Poshta city/warehouse APIs, branch/locker switching,
  signed hidden tokens, stale token, and wrong-city rejection through the real
  `nova-poshta-form-bridge.js` path.
- [ ] Verify error, loading, pending, paid, expired, and superseded states.
- [x] Verify reduced-motion screenshot/state.
- [x] Verify no overlap, horizontal overflow, clipped text, or layout shift.
- [x] Verify product images render and are inspectable.
- [ ] Verify page-specific animation runs once and remains smooth.
- [x] Verify token is absent from analytics/network source URLs.
- [x] Verify CSP console has no new violations.
- [ ] Verify authenticated management mobile/desktop filter, preview,
  copy/resend/revoke/history, permissions, focus order, and overflow.

## Q. Full verification before commit

- [x] Run focused new checkout tests.
- [x] Run all listed IG bot/payment/order linkage suites.
- [x] Run `orders.tests.test_payment_attempts`.
- [x] Run `storefront.tests.test_monobank_webhook`.
- [x] Run Nova Poshta selector/tracking tests.
- [x] Run analytics loader/Meta Pixel/TikTok tests.
- [x] Run `python manage.py check`.
- [x] Run `python manage.py makemigrations --check --dry-run`.
- [x] Run JavaScript tests/lint relevant to the new page.
- [x] Run `git diff --check`.
- [x] Run independent read-only review of security/payment/lifecycle boundaries.
- [x] Reconcile every checklist mark against test or code evidence.

## R. Commit, push, deploy, and production proof

- [x] Re-fetch and rebase/merge current `main` without scope drift.
- [x] Confirm staged paths contain only this feature and its plan docs.
- [x] Commit in small reviewed checkpoints.
- [x] Push the intended feature/main branch as agreed at execution time.
- [x] Confirm remote SHA.
- [x] On server, pull with `--ff-only`.
- [x] Run production migration.
- [x] Run production `manage.py check`.
- [x] Run collectstatic and compressor.
- [x] Seed/update bot playbooks safely.
- [x] Restart Passenger.
- [x] Ensure Instagram bot daemon and bounded reconcilers are running.
- [x] Install non-overlapping `flock` schedules for checkout and post-payment
  reconcilers while preserving unrelated cron entries.
- [x] Verify server HEAD equals intended SHA.
- [x] Verify new tables, indexes, engines, and migration state.
- [x] Verify proposal route headers and staff-safe preview.
- [x] Verify Orders workspace pending section.
- [x] Verify outbox/queue/daemon health.
- [x] Verify legacy direct-invoice polling through a no-side-effect dry-run or
  check-only command; do not call the mutating poller as a smoke test.
- [x] Verify live analytics configuration, token-free URLs, consent bridge,
  deterministic IDs, and persisted markers without emitting a live ad event.
- [x] Verify persisted idempotency markers for a non-live test fixture or approved test.
- [x] Verify no real customer/Meta/Monobank event was sent during smoke tests.
- [x] Document any production-only limitation honestly.
- [x] If production evidence is committed afterward, push/pull that docs commit
  and re-prove local/origin/server SHA equality.

## Current Evidence (2026-08-01)

- Focused checkout, proposal, workspace, bot, lifecycle, attribution, payment,
  email and webhook run after final backend changes: `374 tests, 1 skip, 0 failures`.
- Catalog-drift regression: proposal revision is revalidated before recipient
  lock/invoice creation; changed catalog state returns `catalog_changed` and
  makes zero provider calls.
- Promo and payment-state regressions: account-scoped promos require an
  authenticated eligible account and fail closed after prior use or an active
  reservation from another code in the same `one_per_account` group; anonymous
  payers may use only explicitly non-account-scoped promos. Inactive promo
  groups fail closed before provider I/O. Provider ambiguity is exposed as
  `cancellation_ambiguous` and suppresses payment/replace actions.
- Product discovery regression: `[SHOW_PRODUCTS]` resolves only published
  catalog records, caps transport to four trusted first-party HTTPS images,
  validates stored MIME and byte size, prefers stocked variant imagery, and
  persists partial/ambiguous delivery states without replaying already delivered
  images. UA/RU/EN pipeline tests keep product URLs out unless explicitly asked.
- Receipt regression: assisted checkout accepts missing/blank email without
  provider `customerEmails`, persists an empty value through PaymentAttempt ->
  Order, records receipt delivery as `skipped / no_valid_email`, and continues
  payment and Instagram lifecycle normally. A supplied non-empty address is
  validated before provider I/O and uses the same
  `orders.email_receipt.send_order_receipt_email()` and
  `orders/emails/order_receipt.html` path as normal cart checkout.
- Independent-channel regression: Telegram failure does not clear Meta, TikTok,
  receipt, or Instagram lifecycle state; delivered-status lifecycle failure does
  not block operational delivery notifications, and the reverse failure direction
  is also covered.
- Fresh focused checkout/media/lifecycle/email/Nova Poshta/analytics run after
  these changes: `115 tests, 0 failures`.
- Final C3 verification on 2026-08-01: current checkout modules `95 tests,
  1 skip, 0 failures`; catalog/lifecycle/paylink/receipt/promo/tracking/analytics
  modules `95 tests, 0 failures`; PaymentAttempt plus Monobank webhook boundary
  modules `37 tests, 0 failures`; checkout UI contract `5 tests, 0 failures`.
- Static checks: `manage.py check`, `makemigrations --check --dry-run`,
  `compileall`, Node syntax check for `instagram-checkout.js`, and `git diff
  --check` pass.
- Final release slice after locale/header and operational safety changes:
  checkout/payment/lifecycle modules `252 tests, 1 documented skip, 0 failures`;
  UI contracts `12 tests, 0 failures`. `poll_ig_deal_payments --check-only`
  performs bounded ORM counts with zero provider calls, writes, or sends.
- Final recovery regression after independent audit: `49 tests, 0 failures`
  across checkout reconciliation, canonical lifecycle/order fulfillment, shared
  post-payment recovery, and Telegram reconciliation. The worker now repairs
  missing payment, TTN, and delivered-review events from committed Order truth,
  while fully terminal orders no longer consume the bounded recovery limit.
- Production deploy proof: MariaDB `11.4.12-MariaDB-cll-lve`; management
  migrations `0116` through `0119`, orders `0053`, and storefront `0087` are
  applied. `storefront_promocodegroup`, PaymentAttempt, checkout, lifecycle,
  assignment, and customer-event tables are `InnoDB`; all nine append-only
  checkout/assignment triggers are installed and the inspected tables expose
  their expected indexes.
- `storefront.0087` initially exposed a real MariaDB deployment defect because
  engine DDL was inside an atomic migration. Commit `89c04239` adds
  `Migration.atomic = False` with a RED/GREEN contract; the retry applied cleanly
  and converted `storefront_promocodegroup` from MyISAM to InnoDB.
- Runtime deploy proof: feature/main/server were fast-forwarded through
  `2e2bddcb`; production `manage.py check`, collectstatic, compressor, and
  playbook seed completed. Passenger workers restarted after `tmp/restart.txt`;
  the Instagram daemon restarted as PID `2162931` with a fresh heartbeat and no
  maintenance lease. Separate two-minute `flock` schedules now run checkout and
  order-fulfillment reconciliation while preserving the existing watchdog and
  Telegram reconciler.
- Production no-send proof: checkout dry-run reported zero errors/missing
  payment, TTN, or delivery events; lifecycle dry-run reported zero due; payment
  `--check-only` reported `external_calls=0 writes=0` and one legacy provider
  invoice candidate. Authenticated Awaiting Payment workspace returned HTTP 200;
  the invalid token entry returned 410 with `no-store/private`, `noindex`, and
  `no-referrer` headers. No live Monobank, Meta, TikTok, email, Telegram, or
  Instagram smoke event was generated by these checks.
- Queue health after deploy: no pending bot messages, manager notifications,
  analysis jobs, or assisted lifecycle events. One order-customer event was
  correctly held in `waiting_window`; existing payment-review cases remain
  manager work rather than an automated-send backlog.
- Live analytics configuration has Meta Pixel, CAPI, and TikTok identifiers;
  three existing Purchase markers prove persisted production dedupe. Assisted
  checkout analytics/event IDs/consent and token-free source URL behavior are
  covered by the focused tests and clean-page browser network inspection without
  emitting an ad event.
- The obsolete `order_success_old.html` is intentionally absent; its regression
  now asserts that current contract instead of trying to read a deleted file.
- Earlier C3 browser QA used a real local catalog fixture with mocked provider
  create at mobile `375x812` and desktop `1440x900`. Those captures document the
  earlier visual iteration, while the final C3 HEAD is evidenced separately
  below. The
  mobile run proved no horizontal overflow, a stable 48px CTA, empty-submit
  focus on `full_name`, non-overlapping validation summary and fixed payment
  rail, promo disclosure rail handoff, exit-dialog focus restoration, and a
  terminal disabled expired state. Reduced-motion removed nonessential
  transitions and the browser console stayed error-free. Screenshots are kept
  as QA evidence outside Git at `/tmp/ig-checkout-mobile-clean.png`,
  `/tmp/ig-checkout-mobile-validation.png`,
  `/tmp/ig-checkout-mobile-promo.png`,
  `/tmp/ig-checkout-mobile-expired.png`, and
  `/tmp/ig-checkout-desktop-full.png`.
- Narrow-screen release smoke at `320x568` proved all three language icons
  visible (including the branded RU icon), `scrollWidth == innerWidth == 320`,
  the C3 payment rail fixed and visible, and no browser console warnings/errors.
- Final C3 browser QA on current HEAD captured `320x568`, `430x932`, and
  `768x1024`. At every viewport all UK/RU/EN flags and real product images were
  visible, `scrollWidth == innerWidth`, the fixed payment rail remained topmost,
  and console/page/CSP/network failures were zero. At 320 and 430 every visible
  recipient, email, delivery, and promo field received focus with at least
  `197px` clearance from the rail; no checkout POST, Nova Poshta call, or provider
  call was made. Artifacts are ignored under `output/playwright/ig-checkout-final/`.
- Production limitation: the shared-host access-log format could not be proven
  to normalize a future valid bearer-token entry path. Tokens remain random,
  short-lived, revocable, and redirect to a clean token-free URL before page
  assets/analytics load. A valid production proposal/preview was intentionally
  not fabricated; the authenticated empty Awaiting Payment workspace and preview
  authorization/payload contract tests are the no-customer substitute until the
  first real proposal is created.

## Deferred Next Pass

The following remain intentionally open for the next design/browser pass and
are not production release blockers: arbitrary product-list lengths;
keyboard-only Nova Poshta selector interaction; terminal-state matrix beyond
the tested expired fixture; authenticated management mobile browser QA; a
verified-success micro-transition; one-time animation smoothness; Lucide sprite
provenance; and all-viewport typography polish. Proxy/access-log normalization
also remains open until effective hosting configuration can be proven or the
entry transport is redesigned. These are not marked complete by unit contracts.
