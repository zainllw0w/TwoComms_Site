# Management Bot Visual Refinement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve the management Instagram bot workspace through compact,
evidence-based visual status cues and responsive operational controls.

**Architecture:** The server exposes a small semantic presentation field derived
from durable payment and linked-order truth. The template consumes that field
for CSS classes and progressively discloses lower-frequency controls without
changing the existing API contracts or business actions.

**Tech Stack:** Django, Django TestCase, inline HTML/CSS/vanilla JavaScript,
Playwright CLI.

---

### Task 1: Define commercial visual truth

**Files:**
- Modify: `twocomms/management/tests_ig_clients_ui.py`
- Modify: `twocomms/management/bot_views.py`
- Modify: `twocomms/management/templates/management/bot.html`

**Step 1: Write the failing test**

Add regression cases that assert a manager-verified or provider-verified sale
serializes as `paid`, and that an active linked order with a real shipment
status (`ship`) serializes as `shipped`; a delivered `done` order stays
`paid`. Assert that an incidental Direct delivery error alone cannot yield
`shipped`.

**Step 2: Run test to verify it fails**

Run: `SECRET_KEY=test_local_secret /Users/zainllw0w/TwoComms/site/.venv/bin/python twocomms/manage.py test management.tests_ig_clients_ui --verbosity 1`

Expected: the new `commercial_visual_state` assertion fails because the API has
not exposed the presentation field.

**Step 3: Implement the smallest payload extension**

Annotate the client list query with the latest active Instagram order's
operational status and tracking number. Derive `commercial_visual_state` in
`_client_card` from that durable order truth first, then confirmed payment.
Keep `delivery_status` reserved for Direct transport errors.

**Step 4: Render the compact visual treatment**

Add a state class and a concise state chip to client rows. Use a 3px rail,
border, subtle background, and a matching badge: green for paid, violet for
shipped, amber only for actionable pending payment. Preserve the existing
post-sale and action warnings as higher-priority risk indicators.

**Step 5: Run target checks**

Run the test from step 2, `node --check` against the extracted inline script if
applicable, and `git diff --check`.

**Step 6: Commit**

Commit the design/plan with the implementation using a scoped message such as
`feat(ig): clarify paid and shipped client states`.

### Task 2: Make the context panel controllable

**Files:**
- Modify: `twocomms/management/tests_ig_clients_ui.py`
- Modify: `twocomms/management/templates/management/bot.html`

**Step 1: Write a failing template/interaction contract test**

Cover the gear's toggle semantics, `aria-expanded`, preference persistence,
and the desktop class that collapses the third pane without changing mobile
drawer accessibility.

**Step 2: Verify red, implement, then verify green**

Use the focused Django suite before and after the smallest CSS/JS change.

**Step 3: Browser-check responsive reflow**

At desktop, verify context closes and both list and conversation widen. At
mobile, verify the gear still opens/closes the modal context panel.

**Step 4: Commit and release**

Integrate the completed slice into `main`, push, deploy, and prove the server
SHA before beginning Task 3.

### Task 3: Compress filters and normalise dialogue actions

**Files:**
- Modify: `twocomms/management/tests_ig_clients_ui.py`
- Modify: `twocomms/management/templates/management/bot.html`

**Steps:** Write red contracts for primary filters, advanced-filter disclosure,
and stable action-grid classes. Keep query values/API semantics unchanged.
Implement, test keyboard interactions and desktop/mobile geometry, commit,
integrate, deploy, and verify SHA.

### Task 4: Recompose the overview

**Files:**
- Modify: `twocomms/management/tests_ig_clients_ui.py`
- Modify: `twocomms/management/templates/management/bot.html`

**Steps:** Write a red template contract for removal of `Як працює` and a
non-overflowing operational metric layout. Implement compact metrics and
runtime-status blocks. Test at 320px, 768px, and desktop; then commit,
integrate, deploy, and verify SHA.

### Task 5: Produce the audited improvement shortlist

**Files:**
- Create: `docs/audits/2026-08-05-management-bot-visual-improvements.md`

**Steps:** Audit the completed live UI and current source. Rank exactly 100
non-duplicated visual, interaction, accessibility, responsiveness, and
real-time UX proposals with rationale, expected benefit, implementation cost,
risk, and recommended priority. Commit the document separately after review;
do not silently implement speculative ideas.

### Release Procedure for Every Implemented UI Slice

1. Rebase/merge the focused branch into current `main` without carrying
   unrelated worktree changes.
2. Push `origin/main`.
3. On the production server: `git pull --ff-only origin main`, `python manage.py migrate`, `python manage.py check`, `python manage.py collectstatic --noinput`, `python manage.py compress --force`, `touch tmp/restart.txt`, and `python manage.py run_instagram_bot --ensure`.
4. Confirm the branch, `origin/main`, and remote server SHA are identical;
   inspect the bot heartbeat and relevant read-only client/order state.
