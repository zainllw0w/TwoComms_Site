# Instagram Commerce Durable Reply Delivery Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Send a narrow set of deterministic Instagram commerce replies through the already-persisted `IgCommerceTurnDecision` outbox, treating a provider message ID as the only delivery receipt and never falling through to a second generic reply.

**Architecture:** Keep reduction and delivery separate. A pure reply builder runs inside `apply_turn()` after the locked reduction and before immutable decision creation, so its text becomes immutable outbox data. The worker can send only that payload through `resume_turn_delivery()`; any ambiguous, partial, or failed provider outcome becomes durable manager review instead of a blind resend.

**Tech Stack:** Django transactions and row locks, existing `IgCommerceTurnDecision`/`IgCommerceManagerReview`, Instagram Login `send_text(..., return_receipt=True)`, Django `TestCase` and `TransactionTestCase`.

---

## Scope and Safety Boundary

This slice handles only deterministic, text-only commerce outcomes that make no price, availability, payment, or manager-action promise: accepted trusted product reference, explicit clarification, and a stale numeric candidate reply rejection. Each payload is one short text chunk. Candidate ranking, media, relaxed alternatives, checkout proposals, burst coalescing, manual review UI, and provider read-back reconciliation remain separate W9 work and must not be marked complete.

All non-successful transport outcomes are conservatively `UNKNOWN` in this first slice. This deliberately gives up a possible retry rather than risk a duplicate customer message when the provider boundary is uncertain.

### Task 1: Create a Pure Durable Commerce Reply Builder

**Files:**

- Create: `twocomms/management/services/ig_commerce_replies.py`
- Modify: `twocomms/management/services/ig_commerce_state.py:322-549`
- Test: `twocomms/management/tests_ig_commerce_delivery.py`

**Step 1: Write failing tests.** Cover that an exact trusted product selection, a supported clarification, and `candidate_prompt_mismatch` receive exactly one short text payload before the decision is persisted. Cover that an ordinary commerce field update receives no durable reply and continues through the legacy conversation path. Assert no builder output includes a price, stock claim, payment URL, or manager promise.

**Step 2: Run RED.**

```bash
cd twocomms
python manage.py test --settings=test_settings management.tests_ig_commerce_delivery
```

Expected: the tests fail because no pure builder or locked builder hook exists.

**Step 3: Implement the smallest pure API.** Add a reply builder that accepts the bounded `CommerceTurnRequest`, reducer action/reasons, and locked before/after snapshots, and returns either `{"text": [single_short_message]}` or `{}`. Extend `apply_turn()` with an optional pure callback invoked only after it has computed the immutable result and before `_create_decision()`. Do not call the provider, query price, or create side effects in this callback. Replays must return the stored decision before invoking the callback.

**Step 4: Run GREEN.** Re-run the focused test and the existing state suite.

```bash
cd twocomms
python manage.py test --settings=test_settings management.tests_ig_commerce_delivery management.tests_ig_commerce_state
```

### Task 2: Bridge Worker Delivery to the Persisted Outbox

**Files:**

- Modify: `twocomms/management/services/instagram_bot.py:6278-6287,7891-8775`
- Modify: `twocomms/management/services/ig_commerce_state.py:552-698`
- Test: `twocomms/management/tests_ig_commerce_delivery.py`

**Step 1: Write failing worker tests.** Mock `send_text` to return an explicit `ProviderDeliveryReceipt`. Assert a handled commerce turn: creates one immutable decision with the exact persisted payload, sends it once with `return_receipt=True`, stores the provider message ID, writes one local `MODEL` history row, and never calls Gemini. Replaying the inbound row must not send again.

Add a second test where the receipt is missing/unknown or the transport throws: the decision becomes `UNKNOWN`, an idempotent `delivery_unknown` review is created, the inbound row is terminally marked unknown, and replay makes zero provider calls.

**Step 2: Run RED.**

```bash
cd twocomms
python manage.py test --settings=test_settings management.tests_ig_commerce_delivery
```

Expected: worker still runs the generic reply path and does not persist receipts.

**Step 3: Implement the bridge.** Make `_persist_commerce_turn()` pass the pure builder into `apply_turn()`. After normal permission, opt-out, lease, and inbound claim checks, a decision with `delivery_required=True` is handled before classifier/Gemini. Its transport calls `send_text(..., return_receipt=True)` under the existing customer-send boundary, then converts the typed receipt to the outbox format. A message ID is required for `SENT`; every non-success is mapped to `UNKNOWN`, gets one durable review, and does not retry automatically.

On confirmed delivery, update the inbound row to `DONE`, write exactly one local `MODEL` row with the receipt ID, and update only the ordinary reply counters and last-reply timestamp. Do not run paylink, price-quote, funnel, memory, or follow-up side effects for this safe informational slice. Returning from this branch must prevent the generic Gemini send path from running.

**Step 4: Run GREEN.**

```bash
cd twocomms
python manage.py test --settings=test_settings management.tests_ig_commerce_delivery management.tests_ig_commerce_state management.tests_ig_agentic_dialog
```

### Task 3: Structural Verification, Audit Evidence, and Release

**Files:**

- Modify: `docs/instagram_bot_audit/00_PROGRESS.md`
- Modify: `docs/instagram_bot_audit/03_FINDINGS_REGISTER.md` only if a new validated defect appears
- Modify: `docs/instagram_bot_audit/07_IMPLEMENTATION_PLAN.md`
- Modify: `docs/instagram_bot_audit/09_DEPLOYMENT_LOG.md`

**Step 1: Verify code and schema.**

```bash
cd twocomms
python manage.py check
python manage.py makemigrations --check --dry-run
python -m compileall management
git diff --check
```

**Step 2: Commit the focused source, tests, and audit evidence.** Use a single commit only after all focused tests are green. Fast-forward it into `main`, push `origin/main`, and verify `HEAD...origin/main` is `0 0`.

**Step 3: Deploy.** On production, fast-forward `main`, run migrate/check, restart Passenger and `run_instagram_bot --ensure`, then verify deployed SHA, empty pending queue, daemon liveness, and no customer-send test data. Do not use production MariaDB as a fixture database.

**Step 4: Update status precisely.** Record the receipt-backed delivery bridge as partial evidence under `IMP-087`; retain its checkbox unchecked until candidate ranking, burst reduction, reconciliation consumer, manager UI, and MariaDB proof are separately completed.
