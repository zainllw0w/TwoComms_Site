# Instagram Legacy Order Resolution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let managers accurately resolve historical Instagram sales already paid and fulfilled, while preserving the fail-closed normal payment/order workflow.

**Architecture:** Extend the append-only payment decision with separately audited total data and a non-fulfillment-authoritative historical scope. A transactional domain service performs historical closure; the protected API, Orders workspace, and explicit-ID command use that service rather than changing rows directly.

**Tech Stack:** Django 5.2, MariaDB-compatible migrations, Python unit/API tests, server-rendered template with inline JavaScript, Django management commands.

---

### Task 1: Establish a clean targeted baseline

**Files:**
- Test: `twocomms/management/tests_ig_payment_review.py`
- Test: `twocomms/management/tests_ig_payment_review_truth.py`
- Test: `twocomms/management/tests_ig_clients_ui.py`

**Step 1: Run the existing focused baseline suite**

```bash
DEBUG=1 SECRET_KEY=codex-local-test-only python twocomms/manage.py test \
  management.tests_ig_payment_review \
  management.tests_ig_payment_review_truth \
  management.tests_ig_clients_ui
```

Expected: exit code 0 before feature work. Record an existing failure instead of attributing it to this feature.

**Step 2: Run static baseline checks**

```bash
cd twocomms
DEBUG=1 SECRET_KEY=codex-local-test-only python manage.py check
DEBUG=1 SECRET_KEY=codex-local-test-only python manage.py makemigrations --check --dry-run
cd .. && git diff --check
```

### Task 2: Add the append-only legacy resolution contract

**Files:**
- Modify: `twocomms/management/ig_bot_models.py:849-1070`
- Create: `twocomms/management/migrations/0142_ig_payment_review_legacy_resolution.py`
- Test: `twocomms/management/tests_ig_payment_review_truth.py`

**Step 1: Write failing model-contract tests**

Add a test that persists a `historical_fulfilled` decision with null paid and total amount, and asserts a typed `resolution_outcome` on its review.

```python
decision = IgPaymentReviewDecision.objects.create(
    review=review, client=review.client, decision="manager_verified",
    verification_scope="historical_fulfilled", confirmed_amount=None,
    order_total_amount=None, actor=staff, actor_source="management_user",
    actor_external_id=str(staff.pk),
)
self.assertIsNone(decision.confirmed_amount)
```

**Step 2: Run the test to verify red**

```bash
DEBUG=1 SECRET_KEY=codex-local-test-only python twocomms/manage.py test \
  management.tests_ig_payment_review_truth.PaymentReviewTruthTests.test_historical_resolution_keeps_unknown_amount_null
```

Expected: fail because the scope/fields do not exist.

**Step 3: Implement the smallest schema change**

In `IgPaymentConfirmationReview`, add outcomes `already_received`, `already_delivered`, and `completed_unknown`. In `IgPaymentReviewDecision`, add the `historical_fulfilled` scope plus nullable `order_total_amount` and `order_total_source` fields. Generate the migration from `0141_igfollowuptask_delivery_fsm`.

**Step 4: Verify green**

Run the focused test, then `makemigrations --check --dry-run` and confirm no migration drift.

**Step 5: Commit**

```bash
git add twocomms/management/ig_bot_models.py twocomms/management/migrations/0142_ig_payment_review_legacy_resolution.py twocomms/management/tests_ig_payment_review_truth.py
git commit -m "feat(ig): add legacy payment resolution audit fields"
```

### Task 3: Preserve total/paid separation in normal manager decisions

**Files:**
- Modify: `twocomms/management/services/ig_payment_review.py:2086-2444`
- Modify: `twocomms/management/services/ig_commercial_episodes.py:81-320`
- Modify: `twocomms/management/bot_views.py:936-1060`
- Test: `twocomms/management/tests_ig_payment_review_truth.py`
- Test: `twocomms/management/tests_ig_commercial_episodes.py`

**Step 1: Write failing normal-path tests**

```python
record_review_decision(
    review, actor=staff, decision="manager_verified",
    verification_scope="full_payment", order_total_amount="1550.00",
    confirmed_amount="1550.00",
)
decision = review.decisions.get()
self.assertEqual(decision.order_total_amount, Decimal("1550.00"))
self.assertEqual(decision.confirmed_amount, Decimal("1550.00"))
```

Keep the existing test that an ordinary full/prepayment action without a total fails.

**Step 2: Run the focused tests to verify red**

Expected: the supplied-total case fails for an unsupported parameter; the old fail-closed case remains green.

**Step 3: Implement minimally**

Pass `order_total_amount` through `resolve_review_payment_amount()` and `record_review_decision()`. Persist it separately and let it win only over missing deal/draft totals. Teach `payment_truth_snapshot()` and decision payloads to expose it while keeping `historical_fulfilled` non-authoritative for new fulfillment. Move truth-analysis scheduling to `transaction.on_commit()` with logging so a derived-job failure cannot roll back the decision.

**Step 4: Verify green**

Run focused payment-truth and commercial-episode tests. Provider truth must remain unverified; missing normal total must still fail.

**Step 5: Commit**

```bash
git add twocomms/management/services/ig_payment_review.py twocomms/management/services/ig_commercial_episodes.py twocomms/management/bot_views.py twocomms/management/tests_ig_payment_review_truth.py twocomms/management/tests_ig_commercial_episodes.py
git commit -m "fix(ig): persist manager supplied order totals"
```

### Task 4: Implement the atomic historical-completion service

**Files:**
- Modify: `twocomms/management/services/ig_payment_review.py:2270-2590`
- Test: `twocomms/management/tests_ig_payment_review.py`
- Test: `twocomms/management/tests_ig_payment_review_truth.py`

**Step 1: Write failing service tests**

Cover known and explicitly unknown amounts. Both must append one decision, archive the review, close the episode, resolve its existing alert, and create no `Order`, provider event, Purchase, Meta event, customer message, or new-order notification. Add rejection tests for hidden client, linked order, active checkout, provider reversal, missing reason, invalid outcome, non-staff, and conflicting replay.

```python
archived = resolve_historical_paid_review(
    review, actor=staff, outcome="already_received",
    reason="Historical sale confirmed by owner",
    confirmed_amount=None, amount_unrecoverable=True,
)
self.assertEqual(archived.resolution_kind, "historical_paid_archived")
self.assertEqual(archived.resolution_outcome, "already_received")
```

**Step 2: Run to verify red**

Expected: failure because the domain service does not exist.

**Step 3: Implement the transactional service**

`resolve_historical_paid_review()` locks review/client, validates its manager actor and preconditions, appends one `historical_fulfilled` decision, writes the existing historical archive outcome, resolves the alert, and transitions the new flow to `done`. Refactor `archive_historical_paid_review()` only enough to share closure logic while preserving its old full-payment default behavior. An identical replay returns the existing resolution; a different replay is rejected.

**Step 4: Verify green**

Run service-focused cases and `management.tests_ig_order_links` to protect existing exact-link overrides.

**Step 5: Commit**

```bash
git add twocomms/management/services/ig_payment_review.py twocomms/management/tests_ig_payment_review.py twocomms/management/tests_ig_payment_review_truth.py
git commit -m "feat(ig): resolve completed historical sales safely"
```

### Task 5: Expose the protected API and explicit-ID batch command

**Files:**
- Modify: `twocomms/management/bot_views.py:2788-2965`
- Create: `twocomms/management/management/commands/resolve_historical_ig_sales.py`
- Create: `twocomms/management/tests_ig_historical_resolution_command.py`
- Test: `twocomms/management/tests_ig_payment_review_truth.py`

**Step 1: Write failing API and command tests**

Test staff `action=historical_paid_fulfilled`, non-staff denial, no create/link URL, command default dry-run, explicit-ID apply, omitted amounts, skips, and second-apply idempotency.

**Step 2: Run to verify red**

Expected: unknown action/unknown command.

**Step 3: Implement the endpoints**

The API calls only the domain service and returns field errors for total, paid amount, reason, and outcome. The command accepts repeatable `--review-id`, `--actor-id`, `--outcome`, `--reason`, `--paid-amount REVIEW_ID=AMOUNT`, `--amount-unrecoverable REVIEW_ID`, and `--apply`; it refuses an empty ID list, defaults to dry-run, makes no network calls, and reports every row.

**Step 4: Verify green**

Run API/command tests and confirm there is no raw `QuerySet.update()` status or decision mutation.

**Step 5: Commit**

```bash
git add twocomms/management/bot_views.py twocomms/management/management/commands/resolve_historical_ig_sales.py twocomms/management/tests_ig_historical_resolution_command.py twocomms/management/tests_ig_payment_review_truth.py
git commit -m "feat(ig): add audited historical sales resolution actions"
```

### Task 6: Make the Orders workspace truthful and actionable

**Files:**
- Modify: `twocomms/management/bot_views.py:1759-1908`
- Modify: `twocomms/management/templates/management/bot.html:329-487,824-860,1894-2079`
- Test: `twocomms/management/tests_ig_clients_ui.py`

**Step 1: Write failing workspace contracts**

Cover separate normal total/paid inputs, historical outcome/unknown amount/reason inputs, a green named archive state, completed progress with local-order exemption, absent create/link actions, total-field focus on validation error, and proposal headings matching their selected filter.

**Step 2: Run to verify red**

Expected: existing template lacks these contracts.

**Step 3: Implement smallest UI/API payload change**

Expose legacy eligibility/recommendation only for eligible reviews. Render a separate historical form instead of loosening the normal form. Update optimistic state, labels, CSS, progress copy, focus/error placement, and proposal heading/count consistency.

**Step 4: Verify green**

Run `management.tests_ig_clients_ui` and syntax-check the extracted inline JavaScript with `node --check`.

**Step 5: Commit**

```bash
git add twocomms/management/bot_views.py twocomms/management/templates/management/bot.html twocomms/management/tests_ig_clients_ui.py
git commit -m "feat(management): manage completed legacy Instagram sales"
```

### Task 7: Integration, browser, deployment, and backlog reconciliation

**Files:**
- Test: `twocomms/management/tests_ig_payment_review.py`
- Test: `twocomms/management/tests_ig_payment_review_truth.py`
- Test: `twocomms/management/tests_ig_clients_ui.py`
- Test: `twocomms/management/tests_ig_order_links.py`
- Test: `twocomms/management/tests_ig_commercial_episodes.py`

**Step 1: Run the complete related gate**

```bash
DEBUG=1 SECRET_KEY=codex-local-test-only python twocomms/manage.py test \
  management.tests_ig_payment_review \
  management.tests_ig_payment_review_truth \
  management.tests_ig_clients_ui \
  management.tests_ig_order_links \
  management.tests_ig_commercial_episodes
```

Then run Django check, migration drift, `compileall management`, JavaScript syntax, and `git diff --check`.

**Step 2: Run browser coverage**

Use the `playwright` skill in an authenticated local test session. Capture normal missing-total and historical known/unknown-amount forms at desktop, 880px, 560px, 390px, and 320px. Verify no overlap, reachable sticky actions, and focus restoration.

**Step 3: Review and integrate**

Use `superpowers:requesting-code-review`, fix all findings, fetch current `origin/main`, integrate only this branch, re-run the gate, push `main`, and keep unrelated primary-worktree commits out of the push.

**Step 4: Deploy and prove production state**

On the server run:

```bash
git pull --ff-only origin main
python manage.py migrate
python manage.py check
python manage.py collectstatic --noinput
python manage.py compress --force
python manage.py seed_ig_bot_sales_playbooks
touch tmp/restart.txt
python manage.py run_instagram_bot --ensure
```

Verify deployed SHA, migration `0142`, daemon/heartbeat, and baseline counts. Then run dry-run first and only then apply exactly:

```bash
python manage.py resolve_historical_ig_sales \
  --review-id 3 --review-id 5 --review-id 17 --review-id 20 \
  --actor-id <verified-staff-id> --outcome already_received \
  --reason "Historical completed sale confirmed by owner" \
  --paid-amount 5=1760 --paid-amount 20=1550 \
  --amount-unrecoverable 3 --amount-unrecoverable 17
```

Repeat with `--apply`, then re-run dry-run. Prove all four canonical reviews are archived, their financial gaps remain null, no local Orders/Purchases/provider mutations or outbound customer/Telegram/Meta events were created, and repeated apply produces no duplicate audit record.
