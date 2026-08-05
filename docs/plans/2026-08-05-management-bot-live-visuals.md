# Instagram Bot Live Visuals Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore a perceptible, human-like Instagram typing/seen state and add live, animated inbox reordering without page reloads, then ship separately verified order/lifecycle and statistics visual slices.

**Architecture:** Keep Meta delivery and CRM truth unchanged. The worker gets an observable, provider-aware sender-action helper plus a bounded typing window before the existing idempotent Send API boundary. The manager UI reconciles the existing `last_message_at`-ordered clients endpoint while preserving the selected conversation and animating only rows whose server timestamp changed.

**Tech Stack:** Django/Python, Instagram Graph API, server-rendered HTML, vanilla JavaScript/CSS, Django TestCase/SimpleTestCase, Playwright/browser QA.

---

### Task 1: Make sender actions observable and testable

**Files:**
- Modify: `twocomms/management/services/instagram_bot.py:4421-4439`
- Test: `twocomms/management/tests_ig_live_visuals.py`

**Step 1: Write the failing tests**

- Verify `send_sender_action` builds the active provider URL, returns a typed success result for HTTP 200, and returns a typed failure result for provider/transport errors.
- Verify raw provider response bodies and customer identifiers are not written to the action diagnostic log.

**Step 2: Run the focused test to verify it fails**

Run: `DEBUG=1 SECRET_KEY=codex-local-test-only python manage.py test management.tests_ig_live_visuals.SenderActionTests -v 2`

Expected: FAIL because the helper currently returns `None` and discards the provider result.

**Step 3: Implement the minimal helper contract**

- Add a small immutable result value with `ok`, `http_status`, `kind`, and a bounded `action` field.
- Keep the existing provider host/transport selection and timeout policy.
- Log only a redacted action outcome when an action fails; do not log sender id, token, body, or provider payload.
- Preserve best-effort semantics: an action failure must never block a normal reply.

**Step 4: Run the focused test to verify it passes**

Run: `DEBUG=1 SECRET_KEY=codex-local-test-only python manage.py test management.tests_ig_live_visuals.SenderActionTests -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add twocomms/management/services/instagram_bot.py twocomms/management/tests_ig_live_visuals.py
git commit -m "fix(ig): observe sender action delivery"
```

After verification: push the feature branch, integrate this commit into local `main`, push `origin/main`, deploy, and verify server SHA/daemon health without sending customer text.

### Task 2: Restore a perceptible human typing window

**Files:**
- Modify: `twocomms/management/services/instagram_bot.py:7495-7500, 7820-7840`
- Test: `twocomms/management/tests_ig_live_visuals.py`

**Step 1: Write the failing tests**

- Verify reply-length calculation produces a small bounded target window.
- Verify a fast generation waits only for the remaining target window after `typing_on`.
- Verify a slow generation does not add unnecessary delay.
- Verify a cancelled/stale automation lease does not send or sleep before the final boundary.

**Step 2: Run the focused test to verify it fails**

Run: `DEBUG=1 SECRET_KEY=codex-local-test-only python manage.py test management.tests_ig_live_visuals.TypingWindowTests -v 2`

Expected: FAIL because no typing-window helper or delay exists.

**Step 3: Implement the minimal timing behavior**

- Capture the monotonic start time immediately after successful `typing_on`.
- Use a deterministic, bounded delay derived from visible reply length; keep the cap low enough for queue throughput and skip it when generation already exceeded the target.
- Do not sleep while holding a DB transaction or customer send lock.
- Send `typing_off` (best effort) immediately before the final Send API call; retain existing receipt/idempotency and lease checks.
- If the action failed, do not manufacture a delay that suggests the customer is typing; let the normal reply path continue.

**Step 4: Run focused and related tests**

Run: `DEBUG=1 SECRET_KEY=codex-local-test-only python manage.py test management.tests_ig_live_visuals management.tests_ig_live_reply_priority -v 1`

Expected: PASS with no changes to provider send receipts.

**Step 5: Commit and ship**

```bash
git add twocomms/management/services/instagram_bot.py twocomms/management/tests_ig_live_visuals.py
git commit -m "feat(ig): keep typing indicator perceptible"
```

Push, integrate into `main`, deploy, and verify the deployed action outcome counters, daemon heartbeat, and one real manager-observed conversation. Do not send a synthetic customer message.

### Task 3: Live client inbox reconciliation and FLIP reorder

**Files:**
- Modify: `twocomms/management/templates/management/bot.html`
- Test: `twocomms/management/tests_ig_live_visuals.py`

**Step 1: Write failing UI contract tests**

- Assert the bot template has a visible-tab-only client list poll, stale-request cancellation, client-id reconciliation, selected-client preservation, and a reduced-motion branch.
- Assert the CSS has a stable row geometry and a short `is-live-updated` state without animating commercial colors.

**Step 2: Run tests to verify they fail**

Run: `DEBUG=1 SECRET_KEY=codex-local-test-only python manage.py test management.tests_ig_live_visuals.InboxLiveContractTests management.tests_ig_clients_ui -v 1`

Expected: FAIL because the clients list currently refreshes only on manual load/tab activation.

**Step 3: Implement the minimal live reconciliation**

- Poll the existing clients endpoint while the Bot tab is visible, with adaptive visible/hidden intervals and an `AbortController` for stale requests.
- Compare `id` + `last_message_at`, preserve current search/filter/page and selected client, and update rows by stable `data-client-id`.
- Use FLIP (`getBoundingClientRect` before/after) to move only changed rows to the server-authoritative position. Add one short highlight/new marker and remove it after the transition.
- If a selected client changes, keep it open and let the existing `after_id` conversation poll append messages. Never auto-open a different client and interrupt the manager.
- Remove rows that leave the active filter with a short exit state; insert newly matching rows at the top.
- Respect `prefers-reduced-motion` and maintain touch targets/keyboard focus.

**Step 4: Run focused tests and browser QA**

Run: `DEBUG=1 SECRET_KEY=codex-local-test-only python manage.py test management.tests_ig_live_visuals management.tests_ig_clients_ui management.tests_ig_category_ui -v 1`

Run browser checks at 320, 375, 768, and 1440 px for live row movement, search/filter preservation, no horizontal overflow, and an open conversation receiving a new message.

**Step 5: Commit and ship**

```bash
git add twocomms/management/templates/management/bot.html twocomms/management/tests_ig_live_visuals.py
git commit -m "feat(management): live reorder Instagram conversations"
```

Push, integrate into `main`, deploy, and verify the live manager page against the deployed SHA.

### Task 4: Truthful order and Nova Poshta lifecycle visual

**Files:**
- Modify: `twocomms/management/bot_views.py`, `twocomms/management/templates/management/bot.html`
- Test: `twocomms/management/tests_ig_live_visuals.py`, relevant order/assignment tests

Expose existing `tracking_status_code`, `shipment_status`, `tracking_checked_at`, `tracking_next_check_at`, and the tracking URL in the compact linked-order card. Map only canonical provider codes to the visual progress state. Hide empty sections and never infer delivery from a TTN or free-form text. Add focused serializer/template tests and ship this as its own commit/deploy.

### Task 5: Compact visual statistics

**Files:**
- Modify: `twocomms/management/templates/management/bot.html`
- Test: `twocomms/management/tests_ig_live_visuals.py`, statistics API/UI tests

Keep the existing statistics API truth. Replace the long first-view table wall with four KPI tiles, a proportional event funnel, and compact ranked bars for ads/products/categories. Keep details behind existing disclosure behavior, hide empty sections, and do not invent time-series data or deltas absent from the API. Ship separately after browser QA.

### Task 6: Re-audit all 100 visual recommendations

**Files:**
- Modify: `docs/audits/2026-08-05-management-bot-visual-improvements.md`
- Create: `docs/audits/2026-08-05-management-bot-visual-decisions.md`

Re-score every recommendation against visual impact, comprehension speed, operator utility, text reduction, truthfulness, overload risk, responsive risk, and implementation cost. Mark only evidence-backed items as implemented now; classify the rest as later or reject. Include the typing/reorder decisions and explicit rejection of decorative sound, generic countdowns, invented lifecycle history, and color-only accessibility features. This is documentation-only and is not a substitute for code verification.

### Task 7: Final visual QA and release reconciliation

Run the full focused management-bot suite, Django checks, migration drift check, JavaScript syntax checks, `git diff --check`, and browser visual matrix. Confirm local feature branch, local `main`, `origin/main`, and server SHA are intentionally aligned, then record residual risks and deployed evidence.
