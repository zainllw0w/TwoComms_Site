# Instagram Follow Intelligence Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add authoritative, demand-driven Instagram follow-state intelligence, context-aware follow CTAs, a compact manager indicator, and exact-once delivery of manager-verified UGC promo rewards.

**Architecture:** A deterministic fail-closed policy owns eligibility, concurrency, cooldown, final authorization, and delivery outcome. Meta observations are cached in dedicated InnoDB projections and refreshed only at eligible decision points; Gemini can author or veto one optional sentence but can never override policy. Mandatory lifecycle and UGC messages use existing receipt-backed workers and never wait for optional follow work.

**Tech Stack:** Django 5, Python 3.14, MariaDB/InnoDB production, Django test runner, Meta Instagram Login Graph API v25.0, Gemini structured JSON, vanilla JavaScript/CSS manager UI, Playwright/browser QA.

## Progress Snapshot

This is the authoritative implementation checklist for this branch. A box is
checked only after the corresponding code exists and a focused verification has
passed. The snapshot is refreshed after each implementation slice.

- Implementation checked: **170 / 277 (61.4%)**
- Design ledger checked: **7 / 8 (87.5%)**
- Combined checked: **177 / 285 (62.1%)**
- Remaining implementation boxes: **107**
- Last verified slices (2026-08-15): durable follow observation/CTA/UI, immediate payment lifecycle plus optional preparation, provider-native UGC provenance/assessment retry, lifetime reward snapshots, guest promo ledger rollback/retry, normal Instagram proposal `allow_promo`, compact accessible follow UI, and environment-backed UGC auto-award mode. Fresh expanded gate: **925 passed, 3 MariaDB-only skipped, 0 failures**. MariaDB race proof, browser/live production proof, migration drift, main integration/deploy, and unresolved policy hardening stay explicitly open.
- Grouped evidence (2026-08-15): follow/core/UI **231 passed + 3 skips**; UGC + promo + Instagram checkout **138 passed**; UGC external + assessment + lifecycle timing **69 passed**. Earlier recorded slices **155 / 585 / 17** remain historical breakdowns; the 925-test expanded gate is authoritative for this worktree.
- Working documents: this file and `docs/plans/2026-08-14-instagram-follow-intelligence-design.md`.
- Out of scope for this branch: `docs/instagram_bot_audit/14_IMPLEMENT2.md`.

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

- [x] RED: write model tests for defaults, unique client projection/job, append-only observations, immutable decision identity, unique episode slot, and safe state transitions. Evidence: `management.tests_ig_follow_models` in the 2026-08-15 follow gate.
- [x] Run `python manage.py test management.tests_ig_follow_models --settings=test_settings_no_network -v 2` from `twocomms/`. Evidence: passed in the 231-test follow/core/UI run.
- [ ] Confirm RED because the models do not exist.
- [x] Implement enums, fields, constraints, indexes, append-only guards, and `__all__` exports. Evidence: durable follow models and model contract tests are present.
- [x] Generate the migration with normal project settings, then inspect it manually. Evidence: migration graph replay through management `0165` passes on the disposable SQLite test layer; live MariaDB DDL remains Task 15.
- [x] Ensure every new table is converted to InnoDB using the repository's non-atomic MariaDB-safe migration pattern. Evidence: migrations `0157`, `0158`, `0164`, and storefront `0095` are non-atomic and each runs an explicit MySQL/MariaDB `information_schema.TABLES` engine guard after creating its tables; full migration replay through `0165`/`0095` succeeds on disposable SQLite (`MIGRATE_ALL_SQLITE_OK`). Live MariaDB engine proof remains Task 15.
- [x] Use `db_constraint=False` for references that cross the legacy engine boundary. Evidence: AST/static inspection of all new FK/O2O fields in `0157`–`0165` and storefront `0095` found the legacy-boundary references explicitly disabled; the migration graph loads without unresolved dependencies. Live MariaDB constraint proof remains Task 15.
- [x] GREEN: rerun `management.tests_ig_follow_models` and expect all tests to pass. Evidence: included in the 231-test follow/core/UI run (2026-08-15).
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

- [x] RED: exact request uses `INSTAGRAM_GRAPH`, `GRAPH_VERSION`, requested IGSID, and only `fields=is_user_follow_business`. Evidence: `management.tests_ig_follow_state` request contract.
- [x] RED: legacy transport, missing consent evidence, missing field, `null`, string booleans, malformed JSON, ID mismatch, timeout, HTTP 4xx/5xx, and provider errors all publish `unknown`/error rather than `not_following`. Evidence: fail-closed state tests in the 231-test follow/core/UI run.
- [x] RED: HTTP 200 with exact booleans publishes known state and increments revision. Evidence: follow-state service tests.
- [x] RED: first observed `true` sets `first_observed_following_at` once. Evidence: follow-state service tests.
- [x] RED: configuration fingerprint change makes prior evidence ineffective. Evidence: follow-state configuration-rotation test.
- [x] RED: stale worker lease/generation cannot overwrite newer state. Evidence: lease/generation publication tests.
- [x] RED: duplicate refresh requests coalesce to one job. Evidence: model/service coalescing tests.
- [x] RED: token/permission/rate-limit failures open the provider-wide circuit; per-client transport/5xx failures back off without scanning other clients. Evidence: capability-circuit and retry tests.
- [ ] Run the focused test and confirm expected failures.
- [x] Implement typed result classification, TTL, exponential backoff, circuit breaker, lease claim/publication, and safe observations. Evidence: `ig_follow_state.py` plus the 231-test follow/core/UI gate.
- [x] Reuse `_provider_url()`, `_provider_http()`, `provider_transport()`, `get_page_token()`, `GRAPH_VERSION`, and `INSTAGRAM_LOGIN_TRANSPORT`; do not extend `refresh_profiles_batch()`. Evidence: provider contract/static tests.
- [x] Keep Graph I/O outside transactions and revalidate lease/configuration before publication. Evidence: stale lease/configuration tests.
- [x] GREEN: rerun the focused test. Evidence: `management.tests_ig_follow_state` passed in the 231-test follow/core/UI run (2026-08-15).
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

- [x] RED: fresh `not_following` is required; unknown/stale/error suppresses. Evidence: CTA policy tests.
- [x] RED: hidden, blocked, spam, opt-out, pause, takeover, closed window, stale episode, new inbound, complaint, return, exchange, refund, reversal, cancellation, paylink/payment recovery, and another CTA suppress. Evidence: suppression matrix in `management.tests_ig_follow_cta`.
- [x] RED: payment opportunity is permitted when otherwise safe. Evidence: CTA policy tests.
- [x] RED: hesitation requires current-turn soft hesitation plus current fresh qualified/high-intent analysis and sufficient confidence; persistent `primary_objection` alone is insufficient. Evidence: current-turn analysis tests.
- [x] RED: delivered-review/UGC request wins over follow CTA. Evidence: CTA/UGC suppression tests.
- [x] RED: validator rejects URL, markdown, multiple sentences/questions, percentages, discount/stacking claims, urgency, guilt, surveillance wording, excess emoji, wrong language, control tokens, and high similarity. Evidence: candidate validator tests.
- [x] RED: combined text must remain one `_split_for_send` chunk. Evidence: CTA/live-reply tests.
- [x] RED: one episode slot is atomic and global 90-day/two-per-year limits serialize on an InnoDB follow-state row. Evidence: reservation/cooldown tests; real MariaDB lock proof remains Task 15.
- [x] RED: pre-provider cancellation releases without cooldown; receipt-confirmed and ambiguous provider I/O consume cooldown. Evidence: CTA outcome tests.
- [ ] Run focused tests and confirm RED.
- [x] Implement policy reason codes, context fingerprint, immutable snapshots, atomic reservation, final revalidation, and outcome transitions. Evidence: `ig_follow_cta.py` and 231-test follow/core/UI gate.
- [x] GREEN: rerun focused tests. Evidence: `management.tests_ig_follow_cta` passed in the 231-test follow/core/UI run (2026-08-15).
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

- [x] RED: missing `follow_cta` remains backward compatible. Evidence: agentic response parser tests.
- [x] RED: valid optional object is parsed into an immutable candidate separate from controls. Evidence: agentic response parser tests.
- [x] RED: malformed/unknown optional content is discarded while a valid base reply and controls survive. Evidence: agentic response parser tests.
- [x] RED: model cannot smuggle discounts, URLs, control tags, or surveillance claims through `follow_cta`. Evidence: follow-copy validator tests.
- [x] RED: prompt exposes only safe follow opportunity facts and explicitly allows omission. Evidence: `management.tests_ig_follow_ai`.
- [x] RED: no follow context is added when local policy says it is irrelevant. Evidence: follow-AI prompt tests.
- [x] RED: `reasoning_policy("follow_cta_copy")` is bounded and valid for background preparation. Evidence: follow-AI reasoning policy test.
- [ ] Run focused tests and confirm RED.
- [x] Extend `ValidatedResponse` with immutable optional follow candidate. Evidence: response-control model and parser tests.
- [x] Update the system prompt and seeded playbook protocol without duplicating the schema text. Evidence: agentic/playbook contract tests.
- [x] Add `follow_cta_copy` reasoning policy with a short deadline and no hidden reasoning persistence. Evidence: follow-AI policy test.
- [x] GREEN: run `management.tests_ig_agentic_dialog management.tests_ig_follow_ai management.tests_ig_playbook`. Evidence: included in the fresh 925-test expanded gate (2026-08-15).
- [ ] Commit with `git commit -am "feat(ig): add bounded follow copy contract"`.

### Task 6: Integrate Follow CTA into Live Replies

**Files:**
- Modify: `twocomms/management/services/instagram_bot.py`
- Modify: `twocomms/management/services/ig_follow_cta.py`
- Create: `twocomms/management/tests_ig_follow_live_reply.py`

- [x] RED: eligible live reply sends one combined message and records exact final snapshot/receipt. Evidence: live-reply receipt tests.
- [x] RED: new inbound during Gemini removes CTA but still sends the base answer. Evidence: live-reply boundary tests.
- [x] RED: follow revision changes to `following` before provider I/O removes CTA. Evidence: live-reply boundary tests.
- [x] RED: opt-out/takeover/complaint/episode change before provider I/O removes CTA. Evidence: live-reply boundary tests.
- [x] RED: invalid model candidate sends base answer. Evidence: live-reply candidate tests.
- [x] RED: provider timeout before request does not consume cooldown; timeout after provider request marks CTA ambiguous and disables replay. Evidence: live-reply outcome tests.
- [x] RED: a hesitation reply never contains two questions or a follow CTA alongside paylink/order controls. Evidence: CTA/live-reply arbitration tests.
- [ ] Confirm RED.
- [x] Build opportunity before the existing Gemini call and pass it into the prompt only when relevant. Evidence: live worker wiring and prompt tests.
- [x] Parse and validate candidate after generation. Evidence: response-control/CTA tests.
- [x] Reserve/final-authorize inside the existing customer-send boundary without adding another Meta or Gemini round trip. Evidence: provider-boundary live-reply tests.
- [x] Persist the exact combined delivery evidence and finalize decision from the existing receipt result. Evidence: receipt snapshot tests.
- [x] GREEN: run focused tests plus `management.tests_ig_agentic_dialog management.tests_ig_ai_reply_recovery`. Evidence: fresh 925-test expanded gate (2026-08-15).
- [ ] Commit with `git commit -am "feat(ig): attach follow CTA to safe live replies"`.

### Task 7: Integrate Payment Lifecycle without Blocking Core Delivery

**Files:**
- Modify: `twocomms/management/services/ig_lifecycle.py`
- Modify: `twocomms/management/services/ig_checkout_payment.py`
- Modify: `twocomms/management/services/ig_follow_cta.py`
- Create: `twocomms/management/tests_ig_follow_lifecycle.py`

- [x] RED: payment lifecycle uses prepared CTA when ready and current. Evidence: `management.tests_ig_lifecycle.test_payment_dispatch_uses_prepared_follow_snapshot_and_finalizes_decision`.
- [x] RED: no prepared CTA sends the original payment message immediately. Evidence: lifecycle original-text/failure tests.
- [x] RED: slow/failed Meta lookup or Gemini preparation never delays lifecycle delivery beyond the strict local budget. Evidence: `InstagramLifecycleTests.test_verified_payment_dispatches_immediately_and_queues_follow_preparation_without_network_io` proves `PAYMENT_VERIFIED.due_at` remains immediate while the optional preparation keeps its separate deadline.
- [x] RED: immutable lifecycle payload is unchanged. Evidence: lifecycle snapshot tests.
- [x] RED: the exact same final text is stored in the lifecycle outbox and passed to provider I/O. Evidence: lifecycle final-text/receipt tests.
- [x] RED: TTN, payment recovery, delivered-review, exchange, return, and refund messages never attach follow CTA. Evidence: lifecycle kind suppression tests.
- [x] RED: final boundary suppresses CTA on assignment/order/payment/follow/conversation changes but still sends core text. Evidence: lifecycle boundary tests.
- [ ] Confirm RED.
- [x] Schedule/coalesce follow preparation immediately after verified payment commit. Evidence: `bind_verified_payment()` queues `IgPaymentFollowPreparation`; dispatch remains `transaction.on_commit`.
- [x] At dispatch, use only an already prepared and current decision; never synchronously wait on network I/O. Evidence: immediate-payment and reconciler tests.
- [x] Add a `final_text` snapshot path that preserves lifecycle outbox identity without mutating event payload. Evidence: lifecycle snapshot tests.
- [x] GREEN: run `management.tests_ig_follow_lifecycle management.tests_ig_lifecycle management.tests_ig_payment_delivery` or the current equivalent suites. Evidence: fresh 925-test expanded gate; payment/lifecycle slices passed on 2026-08-15.
- [ ] Commit with `git commit -am "feat(ig): add nonblocking payment follow opportunity"`.

#### Follow CTA policy gates from adversarial commercial/psychology review

- [x] Persist an explicit follow-specific refusal/suppression state. A customer who declines the follow request must never receive another automatic follow CTA, while ordinary service messages remain allowed. Evidence: durable refusal test in the 231-test follow/core/UI run.
- [x] A `post_delivery` opportunity requires authoritative carrier collection plus a positive inbound created after that delivery timestamp. Generic `дякую`/`спасибо`, a paid/order-created stage, or gratitude before collection is insufficient. Evidence: post-delivery truth tests.
- [x] Current-turn complaint, defect, support, return, exchange, refund, cancellation, or mixed positive-plus-negative language always outranks hesitation or post-delivery positivity. Evidence: CTA suppression matrix.
- [x] Arbitrate the complete final reply: no follow CTA beside a paylink/order action, another growth CTA, manager handoff, or an existing question; the combined text may contain at most one clear customer action. Evidence: CTA/live-reply arbitration tests.
- [x] Validate copy against the current-turn language, reject imperative/commanding follow wording, and compare against earlier sent/ambiguous CTA snapshots rather than only the current base reply. Evidence: language/prior-snapshot validator tests.
- [x] Distinguish reactive in-conversation sends from background lifecycle preparation in quiet hours. Optional growth text never creates a standalone or out-of-hours automatic message. Evidence: lifecycle preparation and response-window tests.
- [x] Revalidate the reserved follow decision inside `send_text(..., provider_request_boundary_factory=...)` immediately before every provider request. A changed follow revision, refusal, inbound watermark, complaint, permission, episode, or order state removes the CTA before Meta I/O. Evidence: provider-boundary live-reply tests.
- [ ] Add a real production caller that prepares verified-payment opportunities after commit under a strict local budget; lifecycle dispatch must remain independent and use only an already prepared current decision.

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

- [x] RED: only provider-owned inbound story mention/repost/message evidence can schedule automatic assessment; no global media scan is introduced. Evidence: webhook ingress/assessment tests in the 167-test UGC/agentic run.
- [x] RED: ingress preserves structured Meta attachment provenance (`story_mention` target, provider `media_id`, media type, sender and webhook/message identity) before URL normalization; URL-only or model-supplied media cannot become owned evidence. Evidence: `management.tests_ig_webhook_extract` — 26/26, including forged normalized-key regression.
- [x] RED: `potential_ugc` is detected before classifier/commerce reduction and suppresses product pinning, paylink, generic product discovery, and follow CTA for that turn even when assessment is still pending.
- [x] RED: duplicate webhook/message/media fingerprint coalesces to one assessment.
- [x] RED: assessment records exact brand-tag provenance, owned media IDs, stable catalog product candidates, confidence, policy version, and safe reason codes without raw model reasoning.
- [x] RED: vision qualification requires high policy thresholds and one independently grounded, unique catalog match for every claimed garment; duplicate product IDs cannot satisfy two-shirt coverage.
- [x] RED: clear story mention with verified `@twocomms` tag, visible apparel, independently grounded catalog matches, and no abuse flags becomes `qualified_auto` only when the rollout mode permits auto-award. Evidence: assessment policy/reward suites in the 285-test UGC/provenance/agentic run.
- [x] RED: automatic qualification is limited to a live provider-native story mention/repost with an owned attachment, exact configured `@twocomms` tag, personal worn apparel, and conservative high-confidence catalog evidence. A DM URL, OCR-only tag, official catalog/ad screenshot, share without provider mention, or expired/historical URL is never auto-qualified. Evidence: provenance regression + 80-test UGC run.
- [x] RED: medium confidence, obscured/multiple ambiguous products, manager URL, or incomplete provider metadata becomes `needs_manager_review`. Evidence: `tests_ig_ugc_assessment` and external-reward review cases.
- [x] RED: ad/referral-only content, catalog screenshot, unrelated repost, no brand tag, no apparel, spam, duplicate/stolen evidence, and malformed model output becomes `rejected`. Evidence: assessment/webhook negative cases.
- [x] RED: two people/two shirts may produce multiple product candidates but reward ownership remains the posting Instagram client.
- [ ] RED: no face matching, identity inference, or reward transfer is attempted for the second person. A second reward requires that person's independent qualifying provider event. The two-person owner invariant is tested; explicit biometric/identity-inference audit remains policy hardening.
- [x] RED: recognized UGC changes reply intent: natural acknowledgment is allowed; product discovery, “розповісти про продукт”, paylink, and follow CTA are prohibited in the same turn.
- [x] RED: assessment lease/generation and new inbound/manager decisions are revalidated before publication. Evidence: capture lease/retry worker, generation-bound manager API, and stale reward snapshot tests in the 285-test UGC/provenance/agentic run.
- [x] RED: provider-object/media-id reuse is a hard reject, while a byte-similar or cross-posted image from a different legitimate post/story is `needs_manager_review` unless ownership and provenance independently pass; never collapse those cases into one duplicate rule.
- [x] RED: automatic assessment is restricted to provider-owned inbound evidence and cannot be triggered by a global media scan, ad creative, or an image URL supplied by the model. Evidence: 26/26 webhook extraction plus 80/80 assessment/reward tests.
- [x] RED: manager review UI/API is part of this task (`bot_views.py`, `bot.html`, endpoint tests); review decisions are authenticated, audited, generation-bound, and cannot override lifetime identity or evidence provenance. Evidence: 65 UGC tests green, including terminal approve/reject/replay and rollback.
- [ ] Confirm RED.
- [x] Implement `IgUgcEvidenceAssessment` as an InnoDB, lease-backed, generation-safe model and enforce lease/generation ownership in assessment publication, not only in fields. Evidence: migrations `0158`/`0160`/`0163`, capture lease publication, and 285-test UGC/provenance/agentic run; MariaDB engine proof remains Task 15.
- [x] Reuse locally owned media and catalog-grounded vision; do not store raw provider bodies or image copies beyond existing owned media.
- [ ] Store only owned-media references or stable privacy-safe hashes with retention/cleanup behavior; use `PROTECT`/explicit cleanup semantics so an assessment cannot silently lose the evidence required for an already-issued reward. Core references and deletion cleanup are present; retention/production proof remains open.
- [x] Add a bounded structured `ugc_evidence_assessment` reasoning contract. The model recommends evidence facts; deterministic policy chooses auto/review/reject.
- [x] Persist provider-owned media/object identifiers and a privacy-safe perceptual fingerprint separately. Exact provider-object reuse is a hard block; perceptual similarity is only a review signal when provider provenance differs.
- [x] Feed assessment state into the existing Gemini call so the reply acknowledges UGC and does not restart sales discovery. Evidence: 167-test assessment/media/agentic run.
- [x] Make acknowledgement tier-aware: qualified UGC may praise the verified worn items; pending/review uses a neutral receipt without reward promise; rejected/spam/unrelated content must not claim the person wears TwoComms. Evidence: 167-test assessment/media/agentic run.
- [x] GREEN: run `management.tests_ig_ugc_assessment management.tests_ig_message_media management.tests_ig_agentic_dialog`. Evidence: 167 tests passed on 2026-08-15.
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

- [x] RED: Direct evidence older than `tracking_terminal_at` is rejected. Evidence: delivered-order reward evidence tests using `nova_poshta_delivery_confirmed_at()`.
- [x] RED: stale assignment/version is rejected under lock. Evidence: order-linked fulfillment/reward tests.
- [x] RED: order-linked eligibility still requires current assignment, authoritative TTN collection, no cancellation/refund/return, and evidence after collection. Evidence: delivered-order reward/fulfillment tests.
- [x] RED: `external_ugc` eligibility requires a current `qualified_auto` or manager-approved assessment but requires no fabricated order/assignment/TTN.
- [x] RED: one Instagram client cannot receive a second UGC 10% reward through another order, another assessment, another evidence type, or a concurrent worker. Evidence: lifetime replay/cross-path/expiry tests; real MariaDB race proof remains Task 15.
- [x] RED: another person visible in the photo receives no reward unless their own Instagram identity supplies independent qualifying evidence.
- [x] RED: manager review can approve/reject but cannot override duplicate evidence, lifetime reward, client ownership, or malformed media provenance. Evidence: `tests_ig_ugc_external_reward` manager API/authentication, generation-bound terminal approve/reject, provenance revalidation, lifetime idempotency, and rollback tests (65 UGC tests green).
- [x] RED: `auto` and `manager` issuance have explicit decision sources; automatic qualification leaves `reviewed_by` nullable and must never create a synthetic manager identity. Database checks enforce the source/reviewer XOR.
- [x] RED: order-linked reward evidence is compared with `nova_poshta_delivery_confirmed_at()` (provider event timestamp, terminal timestamp only as fallback), not merely the time our delayed polling marked the order terminal. Evidence: `award_ugc_reward()` and delivered-order evidence tests.
- [x] RED: reward, lifetime slot, and immutable delivery outbox are created through one locked transaction; forced delivery failures roll back the grant. Evidence: `test_delivery_outbox_failure_rolls_back_reward_promo_and_lifetime`.
- [x] RED: API returns `reward_eligible` and returns the same reward/event on idempotent replay. Evidence: terminal manager API and external replay tests.
- [x] RED: worker sends the exact existing code, records receipt, and never creates another code. Evidence: external reward delivery/replay tests.
- [ ] RED: concurrent delivered-order and `external_ugc` attempts for one Instagram identity serialize on the same lifetime slot and yield exactly one reward/promo/event.
- [x] RED: ambiguous promo delivery is not retried automatically.
- [x] RED: an ambiguous or failed provider send recovers the same grant/code and never burns a second lifetime slot; it must not silently mint a replacement reward. Evidence: ambiguous-delivery/replay tests.
- [x] RED: validity is anchored to grant issuance and the 90-day expiry is shown explicitly; delivery is queued only inside a valid response window or the same grant is delivered through a later authorized channel without re-issuance. Evidence: expiry/window tests.
- [x] RED: canonical lifecycle handoff does not cancel UGC reward events. Evidence: dedicated `IgUgcRewardDelivery` outbox and order-linked/external reward tests.
- [x] RED: order-linked matcher cancels when assignment, delivered truth, reward, or promo validity is stale; external matcher uses assessment generation/client/lifetime slot without requiring an order. Evidence: fulfillment/reward reconciliation tests.
- [ ] Confirm RED.
- [x] Make reward order/assignment optional only for `external_ugc`; add eligibility path, assessment link, and database-enforced lifetime client slot.
- [x] Enforce lifetime identity uniqueness with a versioned, rotation-safe `identity_digest` keyring (HMAC/pepper, never a raw IGSID) so secret rotation cannot reopen a lifetime grant. Evidence: keyring/rotation/recreated-client tests in `management.tests_ig_ugc_external_reward`.
- [x] Add a separate receipt-backed external UGC outbox/event shape, or make order/assignment nullable only for `UGC_REWARD_ISSUED` with database XOR checks and an audit of every consumer; do not send an external reward through an event path that dereferences mandatory order/assignment FKs.
- [ ] Preflight production for duplicate reward clients before applying the unique lifetime constraint; stop migration on unresolved duplicates rather than choosing silently. Production/MariaDB evidence remains Task 15/20.
- [x] Use the dedicated `IgUgcRewardDelivery` receipt-backed outbox with a localized immutable promo message snapshot that states 10%, one use, and exact 90-day expiry; no mandatory order-event FK is dereferenced on `external_ugc`. Evidence: delivered/external reward delivery tests.
- [x] Add a database-enforced lifetime slot keyed by Instagram client identity, while keeping order/assignment optional only for `external_ugc` and requiring path-specific XOR checks. Evidence: `IgUgcRewardLifetime` constraints and cross-path tests; MariaDB race proof remains Task 15.
- [x] Link-order evidence time must use `nova_poshta_delivery_confirmed_at()` (provider event timestamp, with terminal timestamp only as fallback), so late polling cannot reject a genuine post-delivery mention. Evidence: delivered-order reward implementation/tests.
- [ ] Define post-issuance policy: full refund/return revokes an unused linked-order code; exchange pauses and revalidates; a redeemed code remains consumed on partial refund. External UGC has no fabricated order to revoke.
- [x] Create reward, lifetime grant, and immutable delivery outbox atomically in one transaction, then let the reconciler send only after the transaction commits. Evidence: rollback/idempotent outbox tests in the 285-test UGC/provenance/agentic gate.
- [x] Ensure external rewards use a dedicated reward receipt-backed outbox or an event shape whose nullable order/assignment fields are protected by database XOR constraints; every consumer must handle the external path without dereferencing missing FKs.
- [ ] Extend current-fulfillment checks and cancellation rules only for the new kind.
- [x] GREEN: run `management.tests_ig_w4_ugc_reward management.tests_ig_ugc_external_reward management.tests_ig_order_fulfillment`. Evidence: fresh 925-test expanded gate (2026-08-15); MariaDB-only concurrency remains Task 15.
- [ ] Inspect production for unused existing UGC reward promos before deciding whether a targeted data migration/backfill is justified; do not rewrite used/expired codes.
- [ ] Commit with `git commit -am "feat(ig): reward qualifying UGC across channels"`.

#### Required scenario: cross-channel two-person branded story

- [x] Add an end-to-end fixture for a provider-native story mention in which the
  posting Instagram identity shares one owned photo containing two people wearing
  two different TwoComms shirts. Vision must return two independently grounded
  catalog candidates, but the reward owner remains only the posting `IgClient`. Evidence: `UGCIngressAssessmentTests.test_two_people_two_shirts_auto_qualifies_but_one_owner`.
- [x] Verify the same scenario when neither person has an Instagram order, an
  assigned chat order, or a known phone number. A missing order/TTN is valid for
  `external_ugc`; the implementation must not invent an order, require a TTN, or
  route the user into product discovery merely because purchase provenance is
  unavailable. A public-site, physical-store, friend-assisted, or other-channel
  purchase is intentionally accepted through the evidence path. Evidence: external reward path tests prove no order/assignment/TTN is fabricated.
- [x] Verify that automatic issuance requires the live provider story-mention
  target and locally captured media plus the high apparel/brand/catalog gates. A
  manager URL, OCR-only `@twocomms`, generic share, ad, catalog screenshot,
  unrelated image, or expired URL-only event routes to review/rejection and never
  mints a code automatically. Evidence: provenance/assessment negative cases.
- [x] Verify the live reply is a short natural acknowledgment of the worn items;
  it must not ask to explain the products, start catalog discovery, attach a
  paylink, or append a follow CTA in the same turn. If review is pending, it may
  thank the customer without promising a discount; once authorized, the durable
  reward event sends the exact private code separately. Evidence: tier-aware acknowledgement and durable delivery tests.
- [x] Verify lifetime uniqueness across all channels and races: an Instagram
  identity that already received the 10% UGC grant through a delivered order,
  external evidence, another assessment, or a prior provider event cannot receive
  a second grant. A second person in the photo receives nothing unless their own
  identity later supplies an independent qualifying event. Evidence: cross-path/lifetime replay tests; real MariaDB race remains Task 15.
- [x] Verify the code is a one-use private bearer promo with `max_uses=1`, no
  stacking, `one_time_per_user=False`, and an exact 90-day expiry date in the
  receipt. Guest COD, online checkout, and Instagram-assisted checkout consume
  one shared capacity atomically; duplicate/concurrent redemption and ambiguous
  delivery reuse the original grant and never create a replacement code. Evidence: reward delivery, guest checkout, rollback, and ambiguous-send tests.

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

- [x] RED: ordinary promos remain unavailable anonymously. Evidence: `UGCGuestPromoTests.test_ordinary_anonymous_promo_is_rejected` and anonymous view tests.
- [x] RED: only explicit `guest_redeemable=True`, non-account-scoped, active, one-use UGC promo can be applied by an anonymous cart/assisted checkout.
- [x] RED: both external and delivered-order reward promos are 10%, 90 days, `max_uses=1`, `one_time_per_user=False`, no account-scoped group, guest-capable, and cryptographically random. Evidence: external/delivered reward and guest-promo suites.
- [ ] RED: public cart and assisted checkout reserve the same code atomically; concurrent attempts yield one reservation/invoice. Exact guest reservation-generation matching and fail-closed stale callbacks are covered by `orders.tests.test_promo_atomicity.PromoAtomicityTests.test_late_success_after_guest_reservation_release_cannot_consume_reissued_capacity` and `storefront.tests.test_ig_checkout_view.InstagramCheckoutViewTests.test_guest_ugc_promo_ig_checkout_late_success_cannot_steal_reissued_capacity`; real concurrent capacity proof remains Task 15.
- [x] RED: a promo cannot stack with another session/order promo. Evidence: guest promo and negotiated-discount regression (102 promo/UGC tests).
- [x] RED: expired, consumed, leaked second use, grouped, account-scoped, or non-UGC guest promo fails closed. Evidence: guest capability/expiry/replay cases.
- [ ] Confirm RED.
- [x] Add the explicit capability field; do not infer guest safety from `one_time_per_user=False` alone. Evidence: `guest_redeemable` model/validation tests.
- [x] Extend the anonymous checkout ledger because current `PromoCodeUsage` requires a non-null user; guest reservation and consumption must be atomic for public online and Instagram-assisted checkout. COD remains globally disabled and must not consume capability. Evidence: guest checkout suite.
- [x] Route all redemptions through `reserve_promo_for_checkout()` so `max_uses=1` is serialized. Evidence: public guest reservation test.
- [x] Keep the private code tied to the `IgUgcReward.client` audit record while truthfully treating checkout redemption as bearer-based, not identity verification. Evidence: external reward/guest checkout tests.
- [x] Treat the guest code as a bearer capability: enforce origin, one-use atomic reservation/consumption, no stacking, and audit metadata, but do not claim recipient identity verification. Evidence: 102 promo/UGC tests.
- [x] Use one locked reward/promo/outbox factory for both `delivered_order` and `external_ugc`; idempotent replay must return the same promo and delivery row on either path. Evidence: shared `_create_locked_ugc_grant()` plus delivered/external replay tests.
- [x] Enable promo entry on normal bot-created Instagram checkout proposals and route it through the same reservation ledger as public online checkout. Evidence: `FinalizePaylinkTests.test_normal_bot_checkout_enables_promo_entry`, `test_allow_promo_policy_is_part_of_proposal_digest`, and `ig_checkout_payment.py` reservation path.
- [x] Define stacking precisely: one UGC promo may apply to the already discounted merchandise subtotal, but code+code, group+code, negotiated manual discount+code, shipping, and custom-charge stacking stay fail-closed unless explicitly configured. Evidence: negotiated-discount regression and guest no-stacking tests.
- [x] Freeze assessment generation, policy version, provider digest, evidence fingerprint, and catalog mapping on the issued reward so later manager edits cannot rewrite issuance evidence. Evidence: reward issuance snapshot tests.
- [x] GREEN: run storefront promo/checkout focused suites. Evidence: fresh UGC + promo + Instagram checkout group **138 passed**; the final 925-test expanded gate had 0 failures.
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

- [x] RED: `_client_card()` returns safe effective state and never labels stale/error as non-follower. Evidence: `management.tests_ig_clients_ui.ClientsApiTests.test_follow_state_is_exposed_in_list_and_detail_without_labeling_stale_as_negative`.
- [x] RED: full detail and `after_id` incremental detail payloads both include current follow revision. Evidence: the same clients API contract test (fresh run 2026-08-15).
- [x] RED: list/detail serialization has bounded query count with `select_related`/prefetch and no per-client lookup loop. Evidence: `ClientsApiTests.test_clients_list_prefetches_follow_projection_without_meta_io` (follow projection query count <= 1).
- [x] RED: opening a UI list does not perform Meta I/O. Evidence: `ClientsApiTests.test_clients_list_prefetches_follow_projection_without_meta_io` with `_provider_http.assert_not_called()`.
- [ ] Confirm RED.
- [x] Add serializer helper and annotate/select the one-to-one state in list/detail querysets. Evidence: `_client_follow_payload()` plus `select_related("follow_state_projection")` in `bot_views.py`.
- [x] Return `reward_eligible` in the order/UGC payload. Evidence: client detail order assignment and `ugc_rewards` payloads expose the computed eligibility/reason; `management.tests_ig_w4_ugc_reward` and `management.tests_ig_ugc_external_reward` cover delivered, pending, duplicate, and replay states.
- [x] GREEN: run `management.tests_ig_clients_ui management.tests_ig_follow_state`. Evidence: 171 tests passed on 2026-08-15; follow UI contract additions bring the combined run to 174 passed.
- [ ] Commit with `git commit -am "feat(ig): expose follow state to managers"`.

### Task 12: Build Compact Accessible Follow Indicator

**Files:**
- Modify: `twocomms/management/templates/management/bot.html`
- Modify: `twocomms/management/tests_ig_clients_ui.py`
- Create: `twocomms/management/tests_ig_follow_ui_contract.py`

- [x] RED: template contract contains a focusable `role="img"` indicator, tooltip relationship, and all four visual states. Evidence: `management.tests_ig_follow_ui_contract.FollowIndicatorTemplateContractTests.test_header_indicator_has_accessible_state_and_provenance_contract`.
- [x] RED: incremental polling updates the existing indicator when revision changes and is a no-op for an unchanged snapshot. Evidence: signature guard in `updateFollowIndicator()` and `test_incremental_poll_is_a_noop_for_an_unchanged_follow_snapshot`.
- [x] RED: indicator is absent from dense sidebar rows. Evidence: `test_all_visual_states_remain_distinct_and_sidebar_stays_dense` and existing clients UI contract.
- [ ] Confirm RED.
- [x] Add fixed-size indicator immediately after the conversation name in `renderConversation()`. Evidence: `renderConversation()` appends `renderFollowIndicator()` to `.bot-conversation-title-row`.
- [x] Use restrained green/amber/neutral colors already compatible with the management palette; add forced-colors fallback and no decorative animation. Evidence: `.bot-follow-indicator` state classes and forced-colors/reduced-motion CSS.
- [x] Tooltip must show state, first/last observation wording, source, and retry/error state without implying an exact follow date. Evidence: `followTooltipText()` and `test_header_indicator_has_accessible_state_and_provenance_contract`.
- [x] Make the title row a stable flex/grid layout so long names wrap without colliding with stage/actions. Evidence: `.bot-conversation-title-row`, `.bot-conversation-title`, and responsive conversation-head rules.
- [x] GREEN: run UI contract and clients UI tests. Evidence: `management.tests_ig_follow_ui_contract management.tests_ig_clients_ui management.tests_ig_follow_state` — 174 tests passed on 2026-08-15.
- [ ] Commit with `git commit -am "feat(ig): show compact follow status"`.

### Task 13: Privacy, Reset, and Operational Reconciliation

**Files:**
- Modify: `twocomms/management/services/ig_data_deletion.py`
- Modify: `twocomms/management/services/ig_funnel_reset.py`
- Modify: `twocomms/management/management/commands/run_instagram_bot.py`
- Create: `twocomms/management/management/commands/reconcile_ig_follow_intelligence.py`
- Create: `twocomms/management/tests_ig_follow_operations.py`

- [x] RED: data deletion removes/anonymizes follow state, observations, refresh jobs, CTA decisions, UGC assessments, private reward delivery metadata, and payment-follow preparation orphans according to current retention behavior. Evidence: `management.tests_ig_data_deletion_safety` plus new orphan regression.
- [x] RED: funnel reset cancels prepared/unreserved current-episode decisions and cannot revive prior episode slots. Evidence: `BuyerTruthTests.test_funnel_reset_cancels_unreserved_follow_decisions_but_keeps_sent_history` and existing reset boundary tests.
- [x] RED: reconciliation only processes pending/due jobs and decisions; it never scans clients to create follow checks. Evidence: `management.tests_ig_follow_operations`.
- [x] RED: daemon work is bounded, lease-aware, and safe when reply processing is disabled where appropriate. Evidence: operations/lifecycle suite.
- [ ] Confirm RED.
- [x] Implement cleanup/reset/reconcile behavior and safe counters. Evidence: `ig_funnel_reset.reset_funnel`, `ig_follow_reconcile.reconcile_follow_intelligence_once`, deletion orphan cleanup, and bounded counter assertions in operations/lifecycle tests.
- [x] Add bounded daemon reconciliation hooks without a global client polling cron. Evidence: `_follow_intelligence_worker` invokes the bounded reconciler independently of reply enablement; `management.tests_ig_follow_operations` verifies the hook and no-client-scan behavior.
- [x] GREEN: run focused operations tests plus existing data-deletion/reset suites. Evidence: 102 operations/deletion/lifecycle tests passed.
- [ ] Commit with `git commit -am "feat(ig): reconcile follow intelligence safely"`.

### Task 14: Focused and Adjacent Verification

- [x] Run all new focused suites with `--settings=test_settings_no_network`. Evidence: expanded feature gate below — 925 tests passed, 3 MariaDB-only skips.
- [x] Run adjacent suites:

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
  --settings=test_settings_no_network -v 2
```

- [x] Run `python manage.py check` with normal settings. Evidence: `SECRET_KEY=ig-follow-doc-check-only DEBUG=1 python manage.py check` — `System check identified no issues (0 silenced)` on 2026-08-15.
- [ ] Run `python manage.py makemigrations --check --dry-run` with normal settings.
- [x] Run `python -m compileall management storefront orders` from `twocomms/`. Evidence: exit 0 on 2026-08-15.
- [x] Run `git diff --check`. Evidence: clean on 2026-08-15.
- [x] Parse the inline JavaScript using the repository's existing Node/template extraction check or an equivalent `node --check` temporary extraction. Evidence: `ClientsPageRenderTests.test_bot_page_inline_scripts_have_valid_javascript_syntax` passed on 2026-08-15.
- [x] Record exact counts and failures in this plan before moving on. Evidence: 925 passed, 3 MariaDB-only skipped; no failures. Standard test profile emits only the known offline-compression/staticfiles warnings.

Normal-settings note: `check` is clean with the ephemeral task secret shown above; `makemigrations --check --dry-run` remains intentionally open because it reports the pre-existing unrelated storefront drift (`0096 CatalogColorSeoOverride`). That baseline migration is outside this feature and must be reconciled before claiming a globally clean migration graph.

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
