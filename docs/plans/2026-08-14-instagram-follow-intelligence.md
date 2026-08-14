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

### Task 8: Make UGC Promo Usable and Create Durable Delivery

**Files:**
- Modify: `twocomms/management/ig_bot_models.py`
- Modify: `twocomms/management/migrations/0157_ig_follow_intelligence.py`
- Modify: `twocomms/management/services/ig_ugc_rewards.py`
- Modify: `twocomms/management/services/ig_order_fulfillment.py`
- Modify: `twocomms/management/bot_views.py`
- Modify: `twocomms/management/tests_ig_w4_ugc_reward.py`
- Modify: `twocomms/management/tests_ig_order_fulfillment.py`
- Modify: `twocomms/storefront/tests/test_ig_checkout_view.py`

- [ ] RED: Direct evidence older than `tracking_terminal_at` is rejected.
- [ ] RED: stale assignment/version is rejected under lock.
- [ ] RED: reward promo is 10%, 90 days, `max_uses=1`, `one_time_per_user=False`, and has no account-scoped group.
- [ ] RED: anonymous assisted checkout can reserve the promo exactly once.
- [ ] RED: reward and `ugc_reward_issued` event are created atomically; forced event failure rolls back promo/reward.
- [ ] RED: API returns `reward_eligible` and returns the same reward/event on idempotent replay.
- [ ] RED: worker sends the exact existing code, records receipt, and never creates another code.
- [ ] RED: ambiguous promo delivery is not retried automatically.
- [ ] RED: canonical lifecycle handoff does not cancel UGC reward events.
- [ ] RED: fulfillment matcher cancels when assignment, delivered truth, reward, or promo validity is stale.
- [ ] Confirm RED.
- [ ] Add `UGC_REWARD_ISSUED` kind and localized immutable promo message snapshot.
- [ ] Create reward and event in the same transaction, then let the existing reconciler send after commit.
- [ ] Extend current-fulfillment checks and cancellation rules only for the new kind.
- [ ] GREEN: run all three focused suites.
- [ ] Inspect production for unused existing UGC reward promos before deciding whether a targeted data migration/backfill is justified; do not rewrite used/expired codes.
- [ ] Commit with `git commit -am "fix(ig): deliver usable verified UGC rewards"`.

### Task 9: Add Follow State to Manager API without N+1

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

### Task 10: Build Compact Accessible Follow Indicator

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

### Task 11: Privacy, Reset, and Operational Reconciliation

**Files:**
- Modify: `twocomms/management/services/ig_data_deletion.py`
- Modify: `twocomms/management/services/ig_funnel_reset.py`
- Modify: `twocomms/management/management/commands/run_instagram_bot.py`
- Create: `twocomms/management/management/commands/reconcile_ig_follow_intelligence.py`
- Create: `twocomms/management/tests_ig_follow_operations.py`

- [ ] RED: data deletion removes/anonymizes follow state, observations, refresh jobs, and CTA decisions according to current retention behavior.
- [ ] RED: funnel reset cancels prepared/unreserved current-episode decisions and cannot revive prior episode slots.
- [ ] RED: reconciliation only processes pending/due jobs and decisions; it never scans clients to create follow checks.
- [ ] RED: daemon work is bounded, lease-aware, and safe when reply processing is disabled where appropriate.
- [ ] Confirm RED.
- [ ] Implement cleanup/reset/reconcile behavior and safe counters.
- [ ] Add bounded daemon reconciliation hooks without a global client polling cron.
- [ ] GREEN: run focused operations tests plus existing data-deletion/reset suites.
- [ ] Commit with `git commit -am "feat(ig): reconcile follow intelligence safely"`.

### Task 12: Focused and Adjacent Verification

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
  management.tests_ig_w4_ugc_reward \
  storefront.tests.test_ig_checkout_view \
  --settings=twocomms.test_settings_no_network -v 2
```

- [ ] Run `python manage.py check` with normal settings.
- [ ] Run `python manage.py makemigrations --check --dry-run` with normal settings.
- [ ] Run `python -m compileall management storefront orders` from `twocomms/`.
- [ ] Run `git diff --check`.
- [ ] Parse the inline JavaScript using the repository's existing Node/template extraction check or an equivalent `node --check` temporary extraction.
- [ ] Record exact counts and failures in this plan before moving on.

### Task 13: Disposable MariaDB Migration and Race Gates

- [ ] Load the configured MariaDB test credentials without printing secrets.
- [ ] Create a disposable database with an explicit task-specific name.
- [ ] Run migrations from zero through the new migration.
- [ ] Confirm all new tables use InnoDB and expected unique indexes exist.
- [ ] Run concurrent reservation tests: payment versus hesitation on one episode yields one slot.
- [ ] Run concurrent reservation tests: two episodes for one client still enforce global cooldown.
- [ ] Run stale lease/publication tests against real row locks.
- [ ] Drop only the validated disposable database after recording results.

### Task 14: Browser and Accessibility QA

- [ ] Start the local development server on an unused port.
- [ ] Use a manager fixture or authenticated test session with following, non-following, unknown, and stale/error conversations.
- [ ] Capture and inspect `1440x900`, `1280x800`, `1024x768`, `820x1180`, `390x844`, `375x812`, and `320x568`.
- [ ] Verify 200% zoom, keyboard focus, tooltip access, reduced motion, forced colors, no console errors, and no horizontal overflow.
- [ ] Confirm long display names do not overlap follow indicator, stage, or action buttons.
- [ ] Confirm incremental polling changes indicator state without layout shift.
- [ ] Store only temporary QA screenshots outside tracked product paths unless an audit artifact explicitly needs one.

### Task 15: Independent Review

- [ ] Request a read-only code review covering the full feature diff against base `51db3058a`.
- [ ] Ask specifically for policy bypasses, race conditions, ambiguous delivery, PII retention, query growth, prompt injection, and UI accessibility.
- [ ] Reproduce every Critical/Important finding against current code before changing it.
- [ ] Add a failing regression test for each validated finding.
- [ ] Fix and rerun focused/adjacent verification.
- [ ] Record rejected findings with evidence.

### Task 16: Rebase, Audit Reconciliation, and Main Integration

- [ ] Fetch `origin/main` and inspect all commits added since `f81195895`.
- [ ] Rebase `codex/ig-follow-intelligence` onto current `origin/main` while preserving prerequisite `51db3058a` behavior.
- [ ] Resolve migration number conflicts and rerun migration/tests.
- [ ] Reconcile current `docs/instagram_bot_audit/00_PROGRESS.md`, `08_COMPLETION_LOG.md`, `09_DEPLOYMENT_LOG.md`, `14_IMPLEMENT2.md`, and `15_IMPLEMENT2_EMERGENT_FINDINGS.md` only after reading the parallel agent's final state.
- [ ] Mark only evidence-backed checklist items complete.
- [ ] Commit audit reconciliation separately.
- [ ] Integrate the verified branch into `main` without touching unrelated dirty primary-checkout files; use a clean integration worktree if required.
- [ ] Verify `git rev-list --left-right --count main...origin/main` before push.
- [ ] Push `main` and record the exact remote SHA.

### Task 17: Production Deploy

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

### Task 18: Production Verification

- [ ] Confirm server `HEAD` equals pushed `origin/main` SHA.
- [ ] Confirm the new migration is applied.
- [ ] Confirm new tables are InnoDB and unique indexes/constraints exist.
- [ ] Confirm daemon heartbeat and reply transport remain healthy with `provider_transport='instagram_login'` and polling disabled unless intentionally configured.
- [ ] Confirm follow capability state, job counts, state distribution, decision distribution, and duplicate episode slot count through read-only queries.
- [ ] Confirm UGC reward event queue has no duplicate reward/order keys and no blind retry of ambiguous sends.
- [ ] Run one read-only Graph follow contract probe for an existing consented production client; verify HTTP 200 and exact boolean without persisting raw response or sending a message.
- [ ] Verify `/`, `/healthz/`, manager login redirect/auth boundary, and the bot page static bundle.
- [ ] Confirm no synthetic customer messages or ad events were created during deployment verification.
- [ ] Update deployment log with exact SHA, migration, commands, counts, and read-only proof.

## Completion Gate

The task is complete only when every applicable checkbox above is evidence-backed, focused and adjacent suites are green, MariaDB races are proven, browser QA passes, independent review findings are resolved, `main` is pushed, the server runs the same SHA, migrations and daemon are healthy, and no verification step has sent a synthetic customer message.

