# Instagram Follow Intelligence Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add authoritative, demand-driven Instagram follow-state intelligence, context-aware follow CTAs, a compact manager indicator, and exact-once delivery of manager-verified UGC promo rewards.

**Architecture:** A deterministic fail-closed policy owns eligibility, concurrency, cooldown, final authorization, and delivery outcome. Meta observations are cached in dedicated InnoDB projections and refreshed only at eligible decision points; Gemini can author or veto one optional sentence but can never override policy. Mandatory lifecycle and UGC messages use existing receipt-backed workers and never wait for optional follow work.

**Tech Stack:** Django 5, Python 3.14, MariaDB/InnoDB production, Django test runner, Meta Instagram Login Graph API v25.0, Gemini structured JSON, vanilla JavaScript/CSS manager UI, Playwright/browser QA.

---

## Context Recovery Rules

- [ ] Work only in `/Users/zainllw0w/.config/superpowers/worktrees/site/ig-follow-intelligence` until final integration.
- [ ] Preserve the dirty prerequisite worktree `/Users/zainllw0w/.config/superpowers/worktrees/site/codex-ig-follow-lifecycle-truth`.
- [ ] Do not edit `docs/instagram_bot_audit/14_IMPLEMENT2.md` until final rebase/reconciliation because another agent owns it.
- [ ] Never use the dirty primary checkout to build or stage this feature.
- [ ] Treat production MariaDB and server runtime as truth; local SQLite is not concurrency proof.
- [ ] Do not send synthetic Instagram messages or Meta advertising events during verification.
- [ ] If `origin/main` adds a migration after `0156`, renumber the new migration during final rebase.

### Task 1: Commit Design and Plan Baseline

**Files:**
- Create: `docs/plans/2026-08-14-instagram-follow-intelligence-design.md`
- Create: `docs/plans/2026-08-14-instagram-follow-intelligence.md`

- [ ] Run `git diff --check` and expect exit 0.
- [ ] Run `git status --short` and confirm only the two plan files are new.
- [ ] Commit with `git add docs/plans/2026-08-14-instagram-follow-intelligence-design.md docs/plans/2026-08-14-instagram-follow-intelligence.md && git commit -m "docs(ig): design follow intelligence"`.

### Task 2: Add Durable Follow Models

**Files:**
- Modify: `twocomms/management/ig_bot_models.py`
- Create: `twocomms/management/migrations/0157_ig_follow_intelligence.py`
- Create: `twocomms/management/tests_ig_follow_models.py`

**Model contract:**

```python
class IgFollowCapabilityState(models.Model): ...
class IgFollowState(models.Model): ...
class IgFollowObservation(models.Model): ...
class IgFollowRefreshJob(models.Model): ...
class IgFollowCtaDecision(models.Model): ...
```

- [ ] RED: write model tests for defaults, unique client projection/job, append-only observations, immutable decision identity, unique episode slot, and safe state transitions.
- [ ] Run `python manage.py test management.tests_ig_follow_models --settings=twocomms.test_settings_no_network -v 2` from `twocomms/`.
- [ ] Confirm RED because the models do not exist.
- [ ] Implement enums, fields, constraints, indexes, append-only guards, and `__all__` exports.
- [ ] Generate the migration with normal project settings, then inspect it manually.
- [ ] Ensure every new table is converted to InnoDB using the repository's non-atomic MariaDB-safe migration pattern.
- [ ] Use `db_constraint=False` for references that cross the legacy engine boundary.
- [ ] GREEN: rerun `management.tests_ig_follow_models` and expect all tests to pass.
- [ ] Run `python manage.py makemigrations --check --dry-run` and expect `No changes detected`.
- [ ] Commit with `git commit -am "feat(ig): add follow intelligence state"` plus the new files.

### Task 3: Implement Follow Observation Contract

**Files:**
- Create: `twocomms/management/services/ig_follow_state.py`
- Create: `twocomms/management/tests_ig_follow_state.py`
- Modify: `twocomms/management/services/instagram_bot.py` only to reuse/expose existing provider helpers if required.

**Public service API:**

```python
def effective_follow_state(client, *, now=None) -> FollowStateView: ...
def request_follow_refresh(client, *, trigger, now=None) -> IgFollowRefreshJob: ...
def run_follow_refresh_job(job_id, *, now=None) -> str: ...
def refresh_follow_state_if_due(client, *, trigger, now=None) -> str: ...
```

- [ ] RED: exact request uses `INSTAGRAM_GRAPH`, `GRAPH_VERSION`, requested IGSID, and only `fields=is_user_follow_business`.
- [ ] RED: legacy transport, missing consent evidence, missing field, `null`, string booleans, malformed JSON, ID mismatch, timeout, HTTP 4xx/5xx, and provider errors all publish `unknown`/error rather than `not_following`.
- [ ] RED: HTTP 200 with exact booleans publishes known state and increments revision.
- [ ] RED: first observed `true` sets `first_observed_following_at` once.
- [ ] RED: configuration fingerprint change makes prior evidence ineffective.
- [ ] RED: stale worker lease/generation cannot overwrite newer state.
- [ ] RED: duplicate refresh requests coalesce to one job.
- [ ] RED: token/permission/rate-limit failures open the provider-wide circuit; per-client transport/5xx failures back off without scanning other clients.
- [ ] Run the focused test and confirm expected failures.
- [ ] Implement typed result classification, TTL, exponential backoff, circuit breaker, lease claim/publication, and safe observations.
- [ ] Reuse `_provider_url()`, `_provider_http()`, `provider_transport()`, `get_page_token()`, `GRAPH_VERSION`, and `INSTAGRAM_LOGIN_TRANSPORT`; do not extend `refresh_profiles_batch()`.
- [ ] Keep Graph I/O outside transactions and revalidate lease/configuration before publication.
- [ ] GREEN: rerun the focused test.
- [ ] Commit with `git commit -am "feat(ig): observe follow state on demand"`.

### Task 4: Implement Deterministic CTA Policy and Reservation

**Files:**
- Create: `twocomms/management/services/ig_follow_cta.py`
- Create: `twocomms/management/tests_ig_follow_cta.py`
- Modify: `twocomms/management/services/ig_commercial_episodes.py` only if a reusable InnoDB client lock helper is needed.

**Public service API:**

```python
def evaluate_follow_opportunity(*, client, opportunity, episode, source_message=None,
                                order=None, lifecycle_event=None, base_text="",
                                now=None) -> FollowOpportunity: ...
def prepare_follow_decision(opportunity, *, candidate_text, model_meta=None) -> IgFollowCtaDecision: ...
def authorize_follow_cta(decision_id, *, current_base_text, now=None) -> AuthorizedFollowCta | None: ...
def finalize_follow_delivery(decision_id, *, outcome, provider_message_ids=(), now=None) -> None: ...
```

- [ ] RED: fresh `not_following` is required; unknown/stale/error suppresses.
- [ ] RED: hidden, blocked, spam, opt-out, pause, takeover, closed window, stale episode, new inbound, complaint, return, exchange, refund, reversal, cancellation, paylink/payment recovery, and another CTA suppress.
- [ ] RED: payment opportunity is permitted when otherwise safe.
- [ ] RED: hesitation requires current-turn soft hesitation plus current fresh qualified/high-intent analysis and sufficient confidence; persistent `primary_objection` alone is insufficient.
- [ ] RED: delivered-review/UGC request wins over follow CTA.
- [ ] RED: validator rejects URL, markdown, multiple sentences/questions, percentages, discount/stacking claims, urgency, guilt, surveillance wording, excess emoji, wrong language, control tokens, and high similarity.
- [ ] RED: combined text must remain one `_split_for_send` chunk.
- [ ] RED: one episode slot is atomic and global 90-day/two-per-year limits serialize on an InnoDB follow-state row.
- [ ] RED: pre-provider cancellation releases without cooldown; receipt-confirmed and ambiguous provider I/O consume cooldown.
- [ ] Run focused tests and confirm RED.
- [ ] Implement policy reason codes, context fingerprint, immutable snapshots, atomic reservation, final revalidation, and outcome transitions.
- [ ] GREEN: rerun focused tests.
- [ ] Add a MariaDB-only transaction test harness for concurrent episode and cross-episode reservation; keep it skippable when MariaDB env is absent.
- [ ] Commit with `git commit -am "feat(ig): add contextual follow policy"`.

### Task 5: Extend Structured Gemini Response Safely

**Files:**
- Modify: `twocomms/management/services/ig_response_control.py`
- Modify: `twocomms/management/services/instagram_bot.py`
- Modify: `twocomms/management/services/call_ai_analysis.py`
- Modify: `twocomms/management/models.py`
- Modify: `twocomms/management/management/commands/seed_ig_bot_sales_playbooks.py`
- Modify: `twocomms/management/tests_ig_agentic_dialog.py`
- Create: `twocomms/management/tests_ig_follow_ai.py`

- [ ] RED: missing `follow_cta` remains backward compatible.
- [ ] RED: valid optional object is parsed into an immutable candidate separate from controls.
- [ ] RED: malformed/unknown optional content is discarded while a valid base reply and controls survive.
- [ ] RED: model cannot smuggle discounts, URLs, control tags, or surveillance claims through `follow_cta`.
- [ ] RED: prompt exposes only safe follow opportunity facts and explicitly allows omission.
- [ ] RED: no follow context is added when local policy says it is irrelevant.
- [ ] RED: `reasoning_policy("follow_cta_copy")` is bounded and valid for background preparation.
- [ ] Run focused tests and confirm RED.
- [ ] Extend `ValidatedResponse` with immutable optional follow candidate.
- [ ] Update the system prompt and seeded playbook protocol without duplicating the schema text.
- [ ] Add `follow_cta_copy` reasoning policy with a short deadline and no hidden reasoning persistence.
- [ ] GREEN: run `management.tests_ig_agentic_dialog management.tests_ig_follow_ai management.tests_ig_playbook`.
- [ ] Commit with `git commit -am "feat(ig): add bounded follow copy contract"`.

### Task 6: Integrate Follow CTA into Live Replies

**Files:**
- Modify: `twocomms/management/services/instagram_bot.py`
- Modify: `twocomms/management/services/ig_follow_cta.py`
- Create: `twocomms/management/tests_ig_follow_live_reply.py`

- [ ] RED: eligible live reply sends one combined message and records exact final snapshot/receipt.
- [ ] RED: new inbound during Gemini removes CTA but still sends the base answer.
- [ ] RED: follow revision changes to `following` before provider I/O removes CTA.
- [ ] RED: opt-out/takeover/complaint/episode change before provider I/O removes CTA.
- [ ] RED: invalid model candidate sends base answer.
- [ ] RED: provider timeout before request does not consume cooldown; timeout after provider request marks CTA ambiguous and disables replay.
- [ ] RED: a hesitation reply never contains two questions or a follow CTA alongside paylink/order controls.
- [ ] Confirm RED.
- [ ] Build opportunity before the existing Gemini call and pass it into the prompt only when relevant.
- [ ] Parse and validate candidate after generation.
- [ ] Reserve/final-authorize inside the existing customer-send boundary without adding another Meta or Gemini round trip.
- [ ] Persist the exact combined delivery evidence and finalize decision from the existing receipt result.
- [ ] GREEN: run focused tests plus `management.tests_ig_agentic_dialog management.tests_ig_ai_reply_recovery`.
- [ ] Commit with `git commit -am "feat(ig): attach follow CTA to safe live replies"`.

### Task 7: Integrate Payment Lifecycle without Blocking Core Delivery

**Files:**
- Modify: `twocomms/management/services/ig_lifecycle.py`
- Modify: `twocomms/management/services/ig_checkout_payment.py`
- Modify: `twocomms/management/services/ig_follow_cta.py`
- Create: `twocomms/management/tests_ig_follow_lifecycle.py`

- [ ] RED: payment lifecycle uses prepared CTA when ready and current.
- [ ] RED: no prepared CTA sends the original payment message immediately.
- [ ] RED: slow/failed Meta lookup or Gemini preparation never delays lifecycle delivery beyond the strict local budget.
- [ ] RED: immutable lifecycle payload is unchanged.
- [ ] RED: the exact same final text is stored in the lifecycle outbox and passed to provider I/O.
- [ ] RED: TTN, payment recovery, delivered-review, exchange, return, and refund messages never attach follow CTA.
- [ ] RED: final boundary suppresses CTA on assignment/order/payment/follow/conversation changes but still sends core text.
- [ ] Confirm RED.
- [ ] Schedule/coalesce follow preparation immediately after verified payment commit.
- [ ] At dispatch, use only an already prepared and current decision; never synchronously wait on network I/O.
- [ ] Add a `final_text` snapshot path that preserves lifecycle outbox identity without mutating event payload.
- [ ] GREEN: run `management.tests_ig_follow_lifecycle management.tests_ig_lifecycle management.tests_ig_payment_delivery` or the current equivalent suites.
- [ ] Commit with `git commit -am "feat(ig): add nonblocking payment follow opportunity"`.

### Task 8: Add Multimodal UGC Assessment and Lifetime Eligibility

**Files:**
- Modify: `twocomms/management/ig_bot_models.py`
- Modify: `twocomms/management/migrations/0157_ig_follow_intelligence.py`
- Create: `twocomms/management/services/ig_ugc_assessment.py`
- Modify: `twocomms/management/services/instagram_bot.py`
- Modify: `twocomms/management/services/bot_vision.py`
- Modify: `twocomms/management/services/ig_response_control.py`
- Create: `twocomms/management/tests_ig_ugc_assessment.py`
- Modify: `twocomms/management/tests_ig_message_media.py`

- [ ] RED: only provider-owned inbound story mention/repost/message evidence can schedule automatic assessment; no global media scan is introduced.
- [ ] RED: ingress preserves structured Meta attachment provenance (`story_mention` target, provider `media_id`, media type, sender and webhook/message identity) before URL normalization; URL-only or model-supplied media cannot become owned evidence.
- [ ] RED: `potential_ugc` is detected before classifier/commerce reduction and suppresses product pinning, paylink, generic product discovery, and follow CTA for that turn even when assessment is still pending.
- [ ] RED: duplicate webhook/message/media fingerprint coalesces to one assessment.
- [ ] RED: assessment records exact brand-tag provenance, owned media IDs, stable catalog product candidates, confidence, policy version, and safe reason codes without raw model reasoning.
- [ ] RED: vision qualification requires high policy thresholds and catalog coverage above 60% for each claimed garment; two visible shirts may produce two candidates without changing single-identity reward ownership.
- [ ] RED: clear story mention with verified `@twocomms` tag, visible apparel, strong catalog match, and no abuse flags becomes `qualified_auto`.
- [ ] RED: automatic qualification is limited to a live provider-native story mention/repost with an owned attachment, exact configured `@twocomms` tag, personal worn apparel, and conservative high-confidence catalog evidence. A DM URL, OCR-only tag, official catalog/ad screenshot, share without provider mention, or expired/historical URL is never auto-qualified.
- [ ] RED: medium confidence, obscured/multiple ambiguous products, manager URL, or incomplete provider metadata becomes `needs_manager_review`.
- [ ] RED: ad/referral-only content, catalog screenshot, unrelated repost, no brand tag, no apparel, spam, duplicate/stolen evidence, and malformed model output becomes `rejected`.
- [ ] RED: two people/two shirts may produce multiple product candidates but reward ownership remains the posting Instagram client.
- [ ] RED: no face matching, identity inference, or reward transfer is attempted for the second person. A second reward requires that person's independent qualifying provider event.
- [ ] RED: recognized UGC changes reply intent: natural acknowledgment is allowed; product discovery, “розповісти про продукт”, paylink, and follow CTA are prohibited in the same turn.
- [ ] RED: assessment lease/generation and new inbound/manager decisions are revalidated before publication.
- [ ] RED: provider-object/media-id reuse is a hard reject, while a byte-similar or cross-posted image from a different legitimate post/story is `needs_manager_review` unless ownership and provenance independently pass; never collapse those cases into one duplicate rule.
- [ ] RED: automatic assessment is restricted to provider-owned inbound evidence and cannot be triggered by a global media scan, ad creative, or an image URL supplied by the model.
- [ ] RED: manager review UI/API is part of this task (`bot_views.py`, `bot.html`, endpoint tests); review decisions are authenticated, audited, generation-bound, and cannot override lifetime identity or evidence provenance.
- [ ] Confirm RED.
- [ ] Implement `IgUgcEvidenceAssessment` as an InnoDB, lease-backed, generation-safe model.
- [ ] Reuse locally owned media and catalog-grounded vision; do not store raw provider bodies or image copies beyond existing owned media.
- [ ] Store only owned-media references or stable privacy-safe hashes with retention/cleanup behavior; use `PROTECT`/explicit cleanup semantics so an assessment cannot silently lose the evidence required for an already-issued reward.
- [ ] Add a bounded structured `ugc_evidence_assessment` reasoning contract. The model recommends evidence facts; deterministic policy chooses auto/review/reject.
- [ ] Persist provider-owned media/object identifiers and a privacy-safe perceptual fingerprint separately. Exact provider-object reuse is a hard block; perceptual similarity is only a review signal when provider provenance differs.
- [ ] Feed assessment state into the existing Gemini call so the reply acknowledges UGC and does not restart sales discovery.
- [ ] GREEN: run `management.tests_ig_ugc_assessment management.tests_ig_message_media management.tests_ig_agentic_dialog`.
- [ ] Commit with `git commit -am "feat(ig): assess branded UGC intelligently"`.

### Task 9: Generalize UGC Reward and Enforce One Lifetime Reward

**Files:**
- Modify: `twocomms/management/ig_bot_models.py`
- Modify: `twocomms/management/migrations/0157_ig_follow_intelligence.py`
- Modify: `twocomms/management/services/ig_ugc_rewards.py`
- Modify: `twocomms/management/services/ig_order_fulfillment.py`
- Modify: `twocomms/management/bot_views.py`
- Modify: `twocomms/management/tests_ig_w4_ugc_reward.py`
- Modify: `twocomms/management/tests_ig_order_fulfillment.py`
- Create: `twocomms/management/tests_ig_ugc_external_reward.py`

- [ ] RED: Direct evidence older than `tracking_terminal_at` is rejected.
- [ ] RED: stale assignment/version is rejected under lock.
- [ ] RED: order-linked eligibility still requires current assignment, authoritative TTN collection, no cancellation/refund/return, and evidence after collection.
- [ ] RED: `external_ugc` eligibility requires a current `qualified_auto` or manager-approved assessment but requires no fabricated order/assignment/TTN.
- [ ] RED: one Instagram client cannot receive a second UGC 10% reward through another order, another assessment, another evidence type, or a concurrent worker.
- [ ] RED: another person visible in the photo receives no reward unless their own Instagram identity supplies independent qualifying evidence.
- [ ] RED: manager review can approve/reject but cannot override duplicate evidence, lifetime reward, client ownership, or malformed media provenance.
- [ ] RED: `auto` and `manager` issuance have explicit decision sources; automatic qualification leaves `reviewed_by` nullable and must never create a synthetic manager identity. Database checks enforce the source/reviewer XOR.
- [ ] RED: order-linked reward evidence is compared with `nova_poshta_delivery_confirmed_at()` (provider event timestamp, terminal timestamp only as fallback), not merely the time our delayed polling marked the order terminal.
- [ ] RED: reward and `ugc_reward_issued` event are created atomically; forced event failure rolls back promo/reward.
- [ ] RED: API returns `reward_eligible` and returns the same reward/event on idempotent replay.
- [ ] RED: worker sends the exact existing code, records receipt, and never creates another code.
- [ ] RED: concurrent delivered-order and `external_ugc` attempts for one Instagram identity serialize on the same lifetime slot and yield exactly one reward/promo/event.
- [ ] RED: ambiguous promo delivery is not retried automatically.
- [ ] RED: an ambiguous or failed provider send recovers the same grant/code and never burns a second lifetime slot; it must not silently mint a replacement reward.
- [ ] RED: validity is anchored to grant issuance and the 90-day expiry is shown explicitly; delivery is queued only inside a valid response window or the same grant is delivered through a later authorized channel without re-issuance.
- [ ] RED: canonical lifecycle handoff does not cancel UGC reward events.
- [ ] RED: order-linked matcher cancels when assignment, delivered truth, reward, or promo validity is stale; external matcher uses assessment generation/client/lifetime slot without requiring an order.
- [ ] Confirm RED.
- [ ] Make reward order/assignment optional only for `external_ugc`; add eligibility path, assessment link, and database-enforced lifetime client slot.
- [ ] Enforce lifetime identity uniqueness with a secret-bound `identity_digest` (HMAC/pepper, never a raw IGSID) so the database constraint is durable without expanding sensitive identifiers.
- [ ] Add a separate receipt-backed external UGC outbox/event shape, or make order/assignment nullable only for `UGC_REWARD_ISSUED` with database XOR checks and an audit of every consumer; do not send an external reward through an event path that dereferences mandatory order/assignment FKs.
- [ ] Preflight production for duplicate reward clients before applying the unique lifetime constraint; stop migration on unresolved duplicates rather than choosing silently.
- [ ] Add `UGC_REWARD_ISSUED` kind and localized immutable promo message snapshot that states 10%, one use, and exact 90-day expiry.
- [ ] Add a database-enforced lifetime slot keyed by Instagram client identity, while keeping order/assignment optional only for `external_ugc` and requiring path-specific XOR checks.
- [ ] Link-order evidence time must use `nova_poshta_delivery_confirmed_at()` (provider event timestamp, with terminal timestamp only as fallback), so late polling cannot reject a genuine post-delivery mention.
- [ ] Define post-issuance policy: full refund/return revokes an unused linked-order code; exchange pauses and revalidates; a redeemed code remains consumed on partial refund. External UGC has no fabricated order to revoke.
- [ ] Create reward and event in the same transaction, then let the existing reconciler send after commit.
- [ ] Ensure external rewards use a dedicated reward receipt-backed outbox or an event shape whose nullable order/assignment fields are protected by database XOR constraints; every consumer must handle the external path without dereferencing missing FKs.
- [ ] Extend current-fulfillment checks and cancellation rules only for the new kind.
- [ ] GREEN: run `management.tests_ig_w4_ugc_reward management.tests_ig_ugc_external_reward management.tests_ig_order_fulfillment`.
- [ ] Inspect production for unused existing UGC reward promos before deciding whether a targeted data migration/backfill is justified; do not rewrite used/expired codes.
- [ ] Commit with `git commit -am "feat(ig): reward qualifying UGC across channels"`.

#### Required scenario: cross-channel two-person branded story

- [ ] Add an end-to-end fixture for a provider-native story mention in which the
  posting Instagram identity shares one owned photo containing two people wearing
  two different TwoComms shirts. Vision must return two independently grounded
  catalog candidates, but the reward owner remains only the posting `IgClient`.
- [ ] Verify the same scenario when neither person has an Instagram order, an
  assigned chat order, or a known phone number. A missing order/TTN is valid for
  `external_ugc`; the implementation must not invent an order, require a TTN, or
  route the user into product discovery merely because purchase provenance is
  unavailable. A public-site, physical-store, friend-assisted, or other-channel
  purchase is intentionally accepted through the evidence path.
- [ ] Verify that automatic issuance requires the live provider story-mention
  target and locally captured media plus the high apparel/brand/catalog gates. A
  manager URL, OCR-only `@twocomms`, generic share, ad, catalog screenshot,
  unrelated image, or expired URL-only event routes to review/rejection and never
  mints a code automatically.
- [ ] Verify the live reply is a short natural acknowledgment of the worn items;
  it must not ask to explain the products, start catalog discovery, attach a
  paylink, or append a follow CTA in the same turn. If review is pending, it may
  thank the customer without promising a discount; once authorized, the durable
  reward event sends the exact private code separately.
- [ ] Verify lifetime uniqueness across all channels and races: an Instagram
  identity that already received the 10% UGC grant through a delivered order,
  external evidence, another assessment, or a prior provider event cannot receive
  a second grant. A second person in the photo receives nothing unless their own
  identity later supplies an independent qualifying event.
- [ ] Verify the code is a one-use private bearer promo with `max_uses=1`, no
  stacking, `one_time_per_user=False`, and an exact 90-day expiry date in the
  receipt. Guest COD, online checkout, and Instagram-assisted checkout consume
  one shared capacity atomically; duplicate/concurrent redemption and ambiguous
  delivery reuse the original grant and never create a replacement code.

### Task 10: Make the Private UGC Promo Guest-redeemable and Exact-once

**Files:**
- Modify: `twocomms/storefront/models.py`
- Create: `twocomms/storefront/migrations/0095_promocode_guest_redeemable.py` or the next migration after final rebase
- Modify: `twocomms/storefront/views/cart.py`
- Modify: `twocomms/storefront/views/checkout.py`
- Modify: `twocomms/storefront/views/ig_checkout.py`
- Modify: `twocomms/orders/promo_reservations.py`
- Modify: `twocomms/storefront/tests/test_checkout.py`
- Modify: `twocomms/storefront/tests/test_ig_checkout_view.py`
- Create: `twocomms/storefront/tests/test_ugc_guest_promo.py`

- [ ] RED: ordinary promos remain unavailable anonymously.
- [ ] RED: only explicit `guest_redeemable=True`, non-account-scoped, active, one-use UGC promo can be applied by an anonymous cart/assisted checkout.
- [ ] RED: reward promo is 10%, 90 days, `max_uses=1`, `one_time_per_user=False`, no account-scoped group, and cryptographically random.
- [ ] RED: public cart and assisted checkout reserve the same code atomically; concurrent attempts yield one reservation/invoice.
- [ ] RED: a promo cannot stack with another session/order promo.
- [ ] RED: expired, consumed, leaked second use, grouped, account-scoped, or non-UGC guest promo fails closed.
- [ ] Confirm RED.
- [ ] Add the explicit capability field; do not infer guest safety from `one_time_per_user=False` alone.
- [ ] Extend the anonymous checkout ledger because current `PromoCodeUsage` requires a non-null user; guest reservation and consumption must be atomic for both COD and online checkout and must not weaken authenticated promo rules.
- [ ] Route all redemptions through `reserve_promo_for_checkout()` so `max_uses=1` is serialized.
- [ ] Keep the private code tied to the `IgUgcReward.client` audit record while truthfully treating checkout redemption as bearer-based, not identity verification.
- [ ] Treat the guest code as a bearer capability: enforce origin, one-use atomic reservation/consumption, no stacking, and audit metadata, but do not claim recipient identity verification.
- [ ] GREEN: run storefront promo/checkout focused suites.
- [ ] Commit with `git commit -am "fix(promo): redeem private UGC rewards as guest"`.

#### UGC policy gates from adversarial review

- [ ] Add a shadow/feature flag rollout for automatic qualification. Do not enable auto-award from uncalibrated Gemini probabilities; record calibrated deterministic gate outcomes first.
- [ ] Keep the hard thresholds named and versioned (exact provider mention, live owned media, worn personal apparel, configured brand tag, catalog match, no risk/duplicate/lifetime/open service case). Any ambiguity or mid-confidence result routes to manager review.
- [ ] Capture story bytes at webhook ingress. A live owned attachment plus original provider event may survive URL expiry; URL-only or failed capture can never become bot-proven auto evidence.
- [ ] Treat OCR/text inside an image as untrusted input. Prompt-injection text, official ads, catalog screenshots, logo-only media, referral-only shares, missing Meta provenance, and no visible garment must fail closed.
- [ ] Make `provider_object_key`, source-message identity, and evidence fingerprint dedupe fields explicit and unique where appropriate; exact object reuse is non-overridable, while same/near-similar bytes across distinct provider objects go to review for legitimate group cross-posts.
- [ ] Lock the client row and InnoDB lifetime slot during issuance so delivered-order and external UGC paths cannot race into two rewards. A duplicate-client preflight must abort the migration rather than silently selecting a winner.
- [ ] Ensure every UGC/outbox table is InnoDB and every legacy FK boundary is `db_constraint=False`; add engine and constraint checks to the disposable MariaDB gate.
- [ ] Never fabricate a service manager for automatic issuance. Store an immutable assessment generation/policy snapshot, `decision_source`, and nullable reviewer; manager approval requires an authenticated actor and reason.
- [ ] Keep the 90-day expiry visible as an exact Kyiv calendar date in the immutable message snapshot. The lifetime slot is consumed at issuance even after expiry; ambiguous or failed delivery recovers the same grant/code/event and never mints a second one.
- [ ] Pre-provider retry may reuse the same event lease. Once provider I/O is ambiguous, require manual reconciliation and prohibit blind automatic resend.
- [ ] Apply source-order lifecycle rules: hold while exchange/return/support is open; deactivate an unused linked-order grant on full cancellation/refund/return; partial refund after redemption does not restore the code; an unrelated order return never revokes an external UGC grant.
- [ ] Route product-sale price plus UGC promo through the existing one-promo reservation semantics; no code+code stacking, and no marketing copy that promises stacking or a discount on shipping/custom charges unless explicitly configured.
- [ ] Add RED tests for ingress provenance, story expiry owned-vs-URL-only, OCR prompt injection, official ad/catalog/no-garment rejection, two people/two shirts with one reward owner, exact object duplicate vs cross-post review, stale assessment/assignment/refund races, transaction rollback, MariaDB engine/unique constraints, guest COD/online/Instagram checkout, concurrent reservation, 90-day boundary, no stacking, and ambiguous delivery recovery.

### Task 11: Add Follow State to Manager API without N+1

**Files:**
- Modify: `twocomms/management/bot_views.py`
- Modify: `twocomms/management/tests_ig_clients_ui.py`
- Modify: `twocomms/management/tests_ig_follow_state.py`

**Payload shape:**

```json
{
  "follow": {
    "state": "following|not_following|unknown",
    "fresh": true,
    "stale": false,
    "revision": 3,
    "observed_at": "...",
    "source": "instagram_login",
    "next_retry_at": "...",
    "aria_label": "..."
  }
}
```

- [ ] RED: `_client_card()` returns safe effective state and never labels stale/error as non-follower.
- [ ] RED: full detail and `after_id` incremental detail payloads both include current follow revision.
- [ ] RED: list/detail serialization has bounded query count with `select_related`/prefetch and no per-client lookup loop.
- [ ] RED: opening a UI list does not perform Meta I/O.
- [ ] Confirm RED.
- [ ] Add serializer helper and annotate/select the one-to-one state in list/detail querysets.
- [ ] Return `reward_eligible` in the order/UGC payload.
- [ ] GREEN: run `management.tests_ig_clients_ui management.tests_ig_follow_state`.
- [ ] Commit with `git commit -am "feat(ig): expose follow state to managers"`.

### Task 12: Build Compact Accessible Follow Indicator

**Files:**
- Modify: `twocomms/management/templates/management/bot.html`
- Modify: `twocomms/management/tests_ig_clients_ui.py`
- Create: `twocomms/management/tests_ig_follow_ui_contract.py`

- [ ] RED: template contract contains a focusable `role="img"` indicator, tooltip relationship, and all four visual states.
- [ ] RED: incremental polling updates the existing indicator when revision changes.
- [ ] RED: indicator is absent from dense sidebar rows.
- [ ] Confirm RED.
- [ ] Add fixed-size indicator immediately after the conversation name in `renderConversation()`.
- [ ] Use restrained green/amber/neutral colors already compatible with the management palette; add forced-colors fallback and no decorative animation.
- [ ] Tooltip must show state, first/last observation wording, source, and retry/error state without implying an exact follow date.
- [ ] Make the title row a stable flex/grid layout so long names wrap without colliding with stage/actions.
- [ ] GREEN: run UI contract and clients UI tests.
- [ ] Commit with `git commit -am "feat(ig): show compact follow status"`.

### Task 13: Privacy, Reset, and Operational Reconciliation

**Files:**
- Modify: `twocomms/management/services/ig_data_deletion.py`
- Modify: `twocomms/management/services/ig_funnel_reset.py`
- Modify: `twocomms/management/management/commands/run_instagram_bot.py`
- Create: `twocomms/management/management/commands/reconcile_ig_follow_intelligence.py`
- Create: `twocomms/management/tests_ig_follow_operations.py`

- [ ] RED: data deletion removes/anonymizes follow state, observations, refresh jobs, CTA decisions, UGC assessments, and private reward delivery metadata according to current retention behavior.
- [ ] RED: funnel reset cancels prepared/unreserved current-episode decisions and cannot revive prior episode slots.
- [ ] RED: reconciliation only processes pending/due jobs and decisions; it never scans clients to create follow checks.
- [ ] RED: daemon work is bounded, lease-aware, and safe when reply processing is disabled where appropriate.
- [ ] Confirm RED.
- [ ] Implement cleanup/reset/reconcile behavior and safe counters.
- [ ] Add bounded daemon reconciliation hooks without a global client polling cron.
- [ ] GREEN: run focused operations tests plus existing data-deletion/reset suites.
- [ ] Commit with `git commit -am "feat(ig): reconcile follow intelligence safely"`.

### Task 14: Focused and Adjacent Verification

- [ ] Run all new focused suites with `--settings=twocomms.test_settings_no_network`.
- [ ] Run adjacent suites:

```bash
python manage.py test \
  management.tests_ig_agentic_dialog \
  management.tests_ig_ai_reply_recovery \
  management.tests_ig_clients_ui \
  management.tests_ig_commercial_episodes \
  management.tests_ig_lifecycle \
  management.tests_ig_order_fulfillment \
  management.tests_ig_ugc_assessment \
  management.tests_ig_ugc_external_reward \
  management.tests_ig_w4_ugc_reward \
  storefront.tests.test_ugc_guest_promo \
  storefront.tests.test_ig_checkout_view \
  --settings=twocomms.test_settings_no_network -v 2
```

- [ ] Run `python manage.py check` with normal settings.
- [ ] Run `python manage.py makemigrations --check --dry-run` with normal settings.
- [ ] Run `python -m compileall management storefront orders` from `twocomms/`.
- [ ] Run `git diff --check`.
- [ ] Parse the inline JavaScript using the repository's existing Node/template extraction check or an equivalent `node --check` temporary extraction.
- [ ] Record exact counts and failures in this plan before moving on.

### Task 15: Disposable MariaDB Migration and Race Gates

- [ ] Load the configured MariaDB test credentials without printing secrets.
- [ ] Create a disposable database with an explicit task-specific name.
- [ ] Run migrations from zero through the new migration.
- [ ] Confirm all new tables use InnoDB and expected unique indexes exist.
- [ ] Run concurrent reservation tests: payment versus hesitation on one episode yields one slot.
- [ ] Run concurrent reservation tests: two episodes for one client still enforce global cooldown.
- [ ] Run stale lease/publication tests against real row locks.
- [ ] Run concurrent external/order-linked UGC issuance for one client and prove one lifetime reward/promo/event.
- [ ] Run concurrent guest promo reservations and prove exactly one capacity consumer.
- [ ] Drop only the validated disposable database after recording results.

### Task 16: Browser and Accessibility QA

- [ ] Start the local development server on an unused port.
- [ ] Use a manager fixture or authenticated test session with following, non-following, unknown, and stale/error conversations.
- [ ] Capture and inspect `1440x900`, `1280x800`, `1024x768`, `820x1180`, `390x844`, `375x812`, and `320x568`.
- [ ] Verify 200% zoom, keyboard focus, tooltip access, reduced motion, forced colors, no console errors, and no horizontal overflow.
- [ ] Confirm long display names do not overlap follow indicator, stage, or action buttons.
- [ ] Confirm incremental polling changes indicator state without layout shift.
- [ ] Store only temporary QA screenshots outside tracked product paths unless an audit artifact explicitly needs one.

### Task 17: Independent Review

- [ ] Request a read-only code review covering the full feature diff against base `51db3058a`.
- [ ] Ask specifically for policy bypasses, UGC fraud/reused media, cross-channel eligibility, lifetime reward races, guest promo leakage, ambiguous delivery, PII retention, query growth, prompt injection, and UI accessibility.
- [ ] Reproduce every Critical/Important finding against current code before changing it.
- [ ] Add a failing regression test for each validated finding.
- [ ] Fix and rerun focused/adjacent verification.
- [ ] Record rejected findings with evidence.

### Task 18: Rebase, Audit Reconciliation, and Main Integration

- [ ] Fetch `origin/main` and inspect all commits added since `f81195895`.
- [ ] Rebase `codex/ig-follow-intelligence` onto current `origin/main` while preserving prerequisite `51db3058a` behavior.
- [ ] Resolve migration number conflicts and rerun migration/tests.
- [ ] Reconcile current `docs/instagram_bot_audit/00_PROGRESS.md`, `08_COMPLETION_LOG.md`, `09_DEPLOYMENT_LOG.md`, `14_IMPLEMENT2.md`, and `15_IMPLEMENT2_EMERGENT_FINDINGS.md` only after reading the parallel agent's final state.
- [ ] Mark only evidence-backed checklist items complete.
- [ ] Commit audit reconciliation separately.
- [ ] Integrate the verified branch into `main` without touching unrelated dirty primary-checkout files; use a clean integration worktree if required.
- [ ] Verify `git rev-list --left-right --count main...origin/main` before push.
- [ ] Push `main` and record the exact remote SHA.

### Task 19: Production Deploy

- [ ] Preflight SSH and server Git status without printing the password/token.
- [ ] Refuse to pull over unexpected server modifications; inspect and preserve them.
- [ ] Run on the server:

```bash
source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
git pull --ff-only origin main
python manage.py migrate
python manage.py check
python manage.py collectstatic --noinput
python manage.py compress --force
python manage.py seed_ig_bot_sales_playbooks
touch tmp/restart.txt
python manage.py run_instagram_bot --ensure
python manage.py poll_ig_deal_payments --limit 5
python manage.py reconcile_ig_follow_intelligence --limit 50 --dry-run
```

- [ ] Never paste the SSH password into a tracked file, process listing, or final response.

### Task 20: Production Verification

- [ ] Confirm server `HEAD` equals pushed `origin/main` SHA.
- [ ] Confirm the new migration is applied.
- [ ] Confirm new tables are InnoDB and unique indexes/constraints exist.
- [ ] Confirm daemon heartbeat and reply transport remain healthy with `provider_transport='instagram_login'` and polling disabled unless intentionally configured.
- [ ] Confirm follow capability state, job counts, state distribution, decision distribution, and duplicate episode slot count through read-only queries.
- [ ] Confirm UGC reward event queue has no duplicate reward/order keys and no blind retry of ambiguous sends.
- [ ] Confirm lifetime reward uniqueness per Instagram client, assessment decision distribution, and zero duplicate evidence fingerprints.
- [ ] Confirm guest-redeemable promo rows are only the intended private UGC class and all are `max_uses=1`.
- [ ] Run one read-only Graph follow contract probe for an existing consented production client; verify HTTP 200 and exact boolean without persisting raw response or sending a message.
- [ ] Verify `/`, `/healthz/`, manager login redirect/auth boundary, and the bot page static bundle.
- [ ] Confirm no synthetic customer messages or ad events were created during deployment verification.
- [ ] Update deployment log with exact SHA, migration, commands, counts, and read-only proof.

## Completion Gate

The task is complete only when every applicable checkbox above is evidence-backed, focused and adjacent suites are green, MariaDB races are proven, browser QA passes, independent review findings are resolved, `main` is pushed, the server runs the same SHA, migrations and daemon are healthy, and no verification step has sent a synthetic customer message.
