# Instagram Follow Intelligence Design

**Date:** 2026-08-14

**Status:** Approved for implementation by the user's instruction to produce the plan and continue autonomously.

**Scope:** Management Instagram Direct bot, authoritative follow-state observation, contextual follow outreach, manager UX, and verified UGC promo delivery.

## 1. Problem

TwoComms needs to know whether an Instagram Direct customer currently follows `@twocomms`, expose that fact to the selling agent and manager, and occasionally ask a commercially qualified non-follower to subscribe. The request must feel like part of the current human conversation, not a campaign message or a fixed template.

The same work also closes an existing post-purchase gap: manager verification currently creates a 10% UGC promo but deliberately does not deliver it, and the created account-scoped promo cannot be redeemed by the anonymous Instagram checkout that generated the order.

This feature sits on high-risk boundaries:

- Meta follow truth is external, rate-limited, and permission-sensitive.
- The bot already has mandatory payment, tracking, delivery, payment-link, and manager-handoff messages.
- The production database is MariaDB with legacy MyISAM tables and newer InnoDB durable tables.
- A provider request can succeed while its local result is ambiguous.
- Commercial state can change while Gemini or Meta is in flight.

The design therefore treats follow outreach as an optional, fail-closed fragment attached to an already useful response. It never becomes a standalone automatic message and never owns the mandatory delivery path.

## 2. Goals

- Observe `is_user_follow_business` through the active Instagram Login transport only.
- Cache authoritative observations with revision, TTL, provenance, retry, and configuration fingerprint.
- Refresh only at eligible decision points; never scan all clients for follow state.
- Let deterministic server policy decide whether outreach is permitted.
- Let Gemini write or veto one short contextual sentence inside that permission envelope.
- Atomically enforce one ask per commercial episode, 90-day cooldown, and two asks per rolling 365 days.
- Treat uncertainty, stale evidence, permission errors, and races as `omit CTA`.
- Keep mandatory payment, TTN, delivered-review, and promo messages independent and prompt.
- Surface a compact accessible follow indicator next to the conversation identity.
- Issue a usable one-use 10% UGC promo only after manager-verified evidence and deliver it through the existing receipt-backed durable outbox.
- Recognize qualifying story mentions/reposts even when the purchase came from the public site, a physical shop, a friend, or another unlinked channel.
- Automatically award only high-confidence provider-owned UGC; route uncertain evidence to a manager and reject spam/ads/unrelated content without a discount.
- Enforce one lifetime 10% UGC reward per Instagram identity, regardless of how many orders or mentions exist.
- Preserve exact delivery evidence and never blindly retry an ambiguous send.
- Provide tests and production verification that do not send synthetic customer messages.

## 3. Non-goals

- No global cron that polls every Instagram customer.
- No follower-count collection.
- No inferred or historical “follow date”; only `first_observed_following_at`.
- No next-day reminder because a customer said they would follow.
- No follow request during complaints, returns, exchanges, refunds, payment recovery, or TTN delivery.
- No standalone follow-only automatic message.
- No invented promotions, discount stacking, urgency, guilt, or surveillance wording.
- No Graph API version bump isolated to this feature.
- No causal claim that a later follow was caused by the CTA; metrics remain observational.

## 4. Considered Approaches

### A. Put follow state and CTA choice entirely in Gemini

This would be flexible but unsafe. A model cannot authoritatively enforce cooldown, concurrent reservations, delivery truth, Meta permissions, or stale-state races. It could also turn unknown provider state into a false “not following” claim.

**Rejected.**

### B. Use fixed server templates and periodic follow polling

This would be deterministic but would create repetitive copy, load Meta and the server unnecessarily, and ignore the conversational nuance requested by the business.

**Rejected.**

### C. Hybrid deterministic policy plus bounded model authorship

The server owns evidence, eligibility, reservations, final authorization, and delivery outcome. Gemini receives only safe facts and may return one optional sentence or an explicit omission. Follow lookup is demand-driven and coalesced.

**Selected.** This preserves intelligence in wording and timing while keeping safety and exact-once behavior in code and the database.

## 5. Core Invariants

1. Deterministic policy is the only authority that may permit follow outreach.
2. Gemini may author or veto copy but may never override a prohibition.
3. Any uncertainty yields no CTA.
4. A follow CTA is never a standalone automatic message.
5. A mandatory lifecycle message is sent without waiting for optional follow work.
6. One outgoing message contains at most one growth/engagement CTA.
7. One commercial episode receives at most one automatic follow touch.
8. One client receives no more than one follow touch per 90 days and two per rolling 365 days.
9. Provider I/O ambiguity consumes the reservation and prohibits automatic replay.
10. A fresh authoritative `following=true` suppresses outreach immediately.
11. A stale positive observation may suppress; a stale negative observation may never authorize.
12. Final authorization runs immediately before provider I/O against the latest client, episode, order, conversation, and follow revisions.
13. Follow work never delays payment, TTN, delivery review, UGC reward, or promo delivery.
14. UGC reward creation and its durable delivery event commit in one transaction.
15. A one-use promo is identity-independent for the anonymous assisted checkout and cannot stack because checkout supports one promo reservation.

## 6. Data Model

New tables are created as InnoDB. Foreign keys to legacy production tables use `db_constraint=False` where required by the current MariaDB engine boundary.

### 6.1 `IgFollowCapabilityState`

Singleton/provider-wide circuit breaker.

- `transport`, `graph_version`, `ig_user_id`, `config_fingerprint`
- `status`: `unknown`, `available`, `degraded`, `blocked`
- `checked_at`, `next_probe_at`, `blocked_until`
- typed `last_error_kind`, safe `last_error_code`
- `consecutive_failures`, `updated_at`

Invalid token, permission, and provider-wide rate-limit failures must not be rediscovered once per customer after a daemon restart.

### 6.2 `IgFollowState`

One-to-one projection for a client.

- `state`: `unknown`, `following`, `not_following`
- monotonic `revision`
- `source`, `graph_version`, `config_fingerprint`
- `observed_at`, `expires_at`
- `first_observed_following_at`
- `last_check_at`, `last_result`, typed error and retry fields
- refresh lease token/expiry and requested generation
- delivery/cooldown serialization row for the client

Only HTTP 200 with an exact JSON boolean for `is_user_follow_business` creates a known observation. Errors preserve the last display observation but make the effective policy state unknown after expiry or configuration change.

### 6.3 `IgFollowObservation`

Append-only provider evidence.

- client and state revision
- trigger/opportunity
- request configuration fingerprint
- HTTP and safe Graph error codes
- field presence/type and normalized boolean
- timing and result classification

No raw token, response body, transcript, or personal metadata beyond the already known IGSID is stored.

### 6.4 `IgFollowRefreshJob`

One coalescing job per client.

- requested and claimed generation
- bounded trigger list
- pending/processing/done/failed state
- lease token/expiry, attempts, retry/backoff
- expected configuration fingerprint

The Graph request happens outside a database transaction. Publication locks the job and state again and rejects stale lease, generation, or configuration results.

### 6.5 `IgFollowCtaDecision`

Durable decision, generation, reservation, and outcome record.

- unique `trigger_key`
- client, commercial episode, optional order/lifecycle/source message
- opportunity: `payment`, `hesitation`, `post_delivery`
- policy version and reason codes
- follow revision and observation evidence
- conversation watermark and context fingerprint
- immutable base text, generated clause, and final outgoing snapshot
- Gemini model/key/prompt metadata without hidden reasoning text
- state: `suppressed`, `waiting_follow`, `preparing`, `prepared`, `reserved`, `sent`, `ambiguous`, `cancelled`, `failed`
- unique nullable `episode_slot_key`
- provider receipt IDs and delivery evidence
- observed follow-after-touch timestamp for non-causal reporting

Reservation and final authorization are separate. A prepared decision does not consume cooldown until the provider boundary starts.

### 6.6 `IgUgcEvidenceAssessment`

Durable, lease-backed multimodal assessment for one inbound story mention/repost or manager-supplied evidence.

- client and unique provider/source evidence fingerprint
- source message, owned media IDs, provider story/repost/mention metadata
- assessment generation, conversation watermark, lease and retry fields
- `brand_tag_verified`, `brand_apparel_visible`, `customer_content`, `suspected_abuse`
- catalog product candidates with stable IDs, confidence, and bounded evidence labels
- normalized decision: `qualified_auto`, `needs_manager_review`, `rejected`
- typed reason codes and safe model/prompt/version metadata
- optional manager decision/audit fields

The assessment stores no raw image bytes or hidden model reasoning. It references locally owned message media and safe structured evidence. A model recommendation never creates a promo by itself; the deterministic reward policy consumes only a validated assessment.

### 6.7 Generalized `IgUgcReward`

The existing reward is extended from an order-only record to two eligibility paths:

- `delivered_order`: current assignment and authoritative TTN collection remain mandatory.
- `external_ugc`: no linked order is required, but provider-owned mention evidence and a high-confidence apparel assessment are mandatory.

The reward keeps an optional order/assignment, requires one assessment or reviewed evidence, and adds a database-enforced lifetime identity slot so one `IgClient` cannot receive the 10% UGC reward twice. Existing production rows must be checked for duplicate clients before the constraint is applied.

## 7. Demand-driven Follow Observation

### 7.1 Allowed lookup triggers

- Verified payment lifecycle opportunity.
- Current-turn qualified hesitation opportunity.
- Explicitly positive post-delivery reply when no UGC/review CTA competes.
- Manager opening a conversation may request a low-priority refresh only when state is absent/stale and capability is healthy; it must not block page rendering.

### 7.2 Forbidden lookup triggers

- Sidebar/list rendering.
- Generic inbound questions.
- TTN creation or payment-recovery messages.
- Complaints, exchanges, returns, refunds, reversals, cancellations.
- Historical client scans and the existing profile refresh batch.

### 7.3 Meta contract

Use the active Instagram Login provider URL:

`GET https://graph.instagram.com/v25.0/<IGSID>?fields=is_user_follow_business`

The feature stays on the repository-wide Graph version. A future version upgrade must migrate and verify the whole Instagram Login contract.

Known state requires all of:

- active transport is `instagram_login`;
- local evidence that the customer has initiated messaging/consent;
- HTTP 200;
- returned object identity matches the requested IGSID when present;
- field exists;
- field value is JSON `true` or `false`, not a string, number, or null.

## 8. Opportunity Policy

### 8.1 Global suppressions

- Effective follow state is not fresh `not_following`.
- Client is hidden, blocked, spam, opted out, paused, or under manager takeover.
- Meta response window is closed.
- No current commercial episode or episode mismatch.
- New inbound exists after the decision watermark.
- Assignment/order/lifecycle generation is stale.
- Open complaint, support escalation, exchange, return, refund, reversal, or cancellation.
- Another growth CTA appears in the same message.
- Episode already has a reservation, confirmed touch, or ambiguous touch.
- 90-day cooldown or rolling-year cap is active.
- Customer explicitly declined follow outreach.
- Analysis evidence is absent, stale, low-confidence, or outside the current episode where analysis is required.

### 8.2 Payment opportunity

Primary opportunity. The customer has completed a high-trust action, and the request can be appended to the payment confirmation only when follow evidence is already ready within a very short local preparation budget. The mandatory payment confirmation is never delayed for a network call or a separate Gemini call.

### 8.3 Hesitation opportunity

Allowed only in the current useful closing response when all are true:

- current inbound explicitly expresses soft hesitation;
- current episode and turn are still current;
- evidence-bound analysis says qualified/high intent/checkout with sufficient confidence;
- no explicit no-buy, support, complaint, or post-sale risk;
- the reply does not already contain a second question or payment CTA.

The follow sentence replaces, rather than stacks with, another closing CTA.

### 8.4 Post-delivery opportunity

The automatic delivered-review/UGC message already contains the primary CTA, so no follow request is appended there. A later explicitly positive customer reply may create a follow opportunity only if no UGC/review request is present in that outgoing response.

## 9. AI Copy Contract

The structured live response gains an optional `follow_cta` object generated in the same Gemini call:

```json
{
  "reply_text": "...",
  "controls": [],
  "follow_cta": {
    "include": true,
    "text": "..."
  }
}
```

Backward-compatible parsing accepts missing `follow_cta`. Unknown keys, malformed types, or invalid text fail closed by discarding only the optional CTA while preserving a valid base reply.

For background lifecycle composition, use a bounded dedicated `follow_cta_copy` reasoning task only during preparation, never on the mandatory dispatch path.

Server validation requires:

- one sentence, approximately 40-220 characters;
- same customer language;
- at most one calm emoji;
- no URL or markdown;
- no percentage, promo, stacking, frequent-sale, scarcity, urgency, guilt, or surveillance claim;
- no “ми помітили, що ви не підписані” wording;
- no second question;
- no control tokens;
- low similarity to earlier CTA text;
- combined message remains one Meta chunk.

Invalid copy is omitted; there is no risky fixed-text fallback.

## 10. Live Reply Integration

1. Before Gemini, policy builds a read-only follow opportunity envelope from fresh local state.
2. The envelope is included in the existing model call only when potentially eligible.
3. The parser returns base reply, existing controls, and optional CTA candidate.
4. The server validates the candidate and creates/prepares a decision.
5. Immediately before Meta I/O, the send boundary locks the follow state/decision and rechecks every policy invariant, conversation watermark, and chunk count.
6. If valid, it reserves the episode/cooldown slot and sends one combined snapshot.
7. If invalid, it sends the original base reply.
8. Confirmed receipt marks the decision sent; ambiguous provider outcome marks it ambiguous; definite pre-request cancellation does not start cooldown.

## 11. Lifecycle Integration

Payment lifecycle dispatch currently follows the transaction quickly. Optional preparation therefore starts as soon as verified payment materializes but operates under a strict deadline. Dispatch uses a prepared CTA only if it is already available and still authorized. Otherwise `_message(event)` is sent unchanged.

The immutable `IgLifecycleEvent.payload` is not modified. `IgFollowCtaDecision` stores the optional clause and exact final snapshot. The same final text is persisted in the lifecycle outbox and passed to `send_text()` before provider I/O so local and provider identities cannot diverge.

TTN, payment recovery, exchange shipment, delivered-review, and UGC promo delivery never wait for or require follow preparation.

## 12. Intelligent UGC Reward and Promo Delivery

### 12.1 Two valid purchase paths

The order-linked rule remains strict. If the evidence is evaluated against an Instagram-assigned order, the order must still be current, not cancelled/refunded/returned, and authoritatively collected through its TTN. Direct evidence must belong to the client and occur at or after `tracking_terminal_at`.

An unlinked purchase is also valid. Customers may have bought through the public site, a physical shop, a friend, or an earlier channel that cannot be joined safely to the Instagram identity. For this path, no order or TTN is fabricated. Eligibility comes from the inbound Meta evidence itself.

### 12.2 Multimodal evidence policy

Candidate creation is event-driven from provider-owned inbound data, never from a global media scan. The assessment combines:

- authoritative Meta story mention/repost/message ownership;
- an explicit tag/mention of the configured `@twocomms` account;
- locally owned image media attached to that inbound event;
- multimodal classification that apparel is genuinely visible;
- catalog-grounded product candidates with stable IDs and confidence;
- conversation context proving the user is sharing/marking content rather than sending an ad, catalog screenshot, meme, or unrelated spam;
- evidence-fingerprint and lifetime-reward dedupe.

Examples with two people or two TwoComms shirts may list multiple product candidates. The reward belongs only to the Instagram identity that sent the qualifying mention. The second person must independently provide a qualifying mention to receive their own lifetime reward.

### 12.3 Decision tiers

`qualified_auto` requires all deterministic gates plus high multimodal confidence. It is reserved for provider-authentic story mentions/reposts with owned media, a verified brand tag, visible apparel, at least one strong catalog match, no abuse flags, and no prior lifetime reward.

`needs_manager_review` covers plausible brand apparel with incomplete metadata, medium confidence, partially obscured garments, multiple ambiguous products, an expiring story that needs a screenshot, or a manager-supplied URL. The manager sees the exact reason codes, media, candidate products, and confidence.

`rejected` covers missing brand tag, no TwoComms apparel, product-only advertising, unrelated reposts, duplicate/stolen evidence, repeated webhook, spam, unsafe content, or a client that already received the lifetime reward.

No fixed threshold may be changed silently. Thresholds and prompt versions are named, tested policy constants and exposed in safe telemetry.

### 12.4 Conversation behavior

Recognized UGC changes the conversational intent. The bot acknowledges the photo/story and the visible TwoComms items naturally; it must not restart discovery with “розповісти про продукт”, ask what the customer wants to buy, or treat worn products as an unknown catalog inquiry.

While evidence is under review, the bot may thank the customer and say the mark is being checked, without promising that a code already exists. A qualified reward is delivered by the durable promo event, not improvised inside a normal Gemini reply.

### 12.5 Lifetime reward and guest-safe promo

- One Instagram client may receive this 10% UGC reward once for life.
- Promo is a cryptographically random private bearer code tied to the client in `IgUgcReward`.
- Promo is 10%, `max_uses=1`, valid for 90 days, non-stackable, and not account-scoped.
- Add an explicit `guest_redeemable` promo capability. Anonymous cart/assisted checkout may accept only this bounded non-account-scoped class; ordinary promos remain login-protected.
- Checkout reserves capacity atomically, so a leaked/reused code can be consumed only once.
- The bot never claims the code is identity-verified at checkout; ownership is represented by private delivery and the reward audit link.

### 12.6 Exact-once issuance and delivery

- Revalidate the assessment, client lifetime slot, current order truth when applicable, and promo policy under locks.
- Create `IgUgcReward`, the promo, and `IgOrderCustomerEvent(kind=ugc_reward_issued)` in one transaction.
- Do not send inside the assessment/manager transaction.
- For order-linked rewards, fulfillment matching checks current assignment, delivered truth, reward, and active unused promo.
- For external UGC rewards, matching checks the same client, assessment generation, lifetime slot, and active unused promo without inventing an order.
- Exclude UGC reward events from canonical lifecycle cancellation.
- Use existing lease, response-window, receipt, and ambiguous-delivery behavior.
- Replay reuses the same reward, promo, and event. It never creates a second code.

## 13. Manager UX

The conversation header displays a fixed-size status indicator immediately after the customer name:

- green filled check/dot: fresh observed follower;
- amber hollow dot: fresh observed non-follower;
- neutral gray question mark: unknown;
- dimmed/dashed symbol: stale or last check failed.

The indicator is omitted from the dense conversation sidebar in this iteration.

Accessibility and layout:

- `role="img"`, complete localized `aria-label`, keyboard focus;
- hover/focus tooltip with effective state, observed time, source, and retry state;
- fixed dimensions to avoid layout shift;
- forced-colors and reduced-motion support;
- long names wrap without overlapping stage/actions;
- incremental detail polling updates the indicator without rerendering the whole page.

## 14. Privacy and Deletion

Follow state is operational account-interaction data. Client deletion must remove or anonymize all new follow observations, jobs, and decisions consistently with existing transcript and order-retention rules. No raw Meta payloads, tokens, hidden model reasoning, or unnecessary follower metadata are persisted.

## 15. Observability

Safe counters and reason codes:

- lookup requested/coalesced/skipped/succeeded/failed;
- capability circuit state;
- effective follow-state distribution;
- CTA suppression reasons;
- prepared/reserved/sent/ambiguous decisions;
- `follow_observed_after_cta` without causal conversion language;
- UGC reward outbox pending/sent/ambiguous/manager-review.

Production verification uses read-only queries and one read-only Graph contract probe. It sends no synthetic customer message and no advertising test event.

## 16. Rollout

1. Ship schema and dormant services.
2. Verify migration engines/indexes and read-only Meta contract.
3. Enable UI projection and demand-driven refresh.
4. Enable policy preparation with sends still omitted; inspect suppression/state distributions.
5. Enable live/lifecycle attachment once production evidence is healthy.
6. Enable durable UGC promo delivery after guest-safe promo tests pass.
7. Keep capability circuit and feature behavior fail-closed on any provider regression.
