# Instagram Payment Review Deduplication Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task.

**Goal:** Keep one actionable payment-review task for one customer payment claim in one Instagram commercial episode, without rerunning costly media analysis or creating duplicate manager work.

**Architecture:** A review receives a stable, evidence-derived claim anchor before any vision/catalog work. Its `dedupe_key` becomes the database-enforced `(client, episode, claim-anchor)` identity, while later conversation context refreshes the same pending review. Only the live customer-message classifier may intake a review; durable AI analysis and reconciliation remain consumers of that state and never create payment-review side effects. Historical strict duplicates are superseded in a resumable management command, retaining audit history and closing redundant episodes.

**Tech Stack:** Django, MariaDB/InnoDB, Django transaction locks, Django tests, existing Instagram commercial episodes and notification outbox.

---

### Task 1: Characterize the duplicate boundary

**Files:**
- Modify: `twocomms/management/tests_ig_payment_review.py`
- Modify: `twocomms/management/tests_ig_sales_automation.py`
- Modify: `twocomms/management/tests_ig_inbox_refresh.py`

**Step 1: Write failing regression tests**

Cover these user-visible invariants:

```python
# Same customer receipt, then new manager price/delivery/product context.
assert second_review.pk == first_review.pk
assert IgPaymentConfirmationReview.objects.filter(client=client).count() == 1

# A different receipt in a subsequent repeat commercial episode is distinct.
assert first_review.pk != second_review.pk

# Reconciliation/history projection creates no review, notification, or vision call.
assert create_payment_review.call_count == 0
assert notify_manager.call_count == 0
```

**Step 2: Run the focused tests to verify RED**

Run:

```bash
SECRET_KEY=test_local_secret .venv/bin/python twocomms/manage.py test management.tests_ig_payment_review management.tests_ig_sales_automation management.tests_ig_inbox_refresh -v 2
```

Expected: failures proving that a mutable conversation fingerprint creates a second review and that reconciliation retains operational effects.

### Task 2: Make payment-review intake idempotent before vision

**Files:**
- Modify: `twocomms/management/services/ig_payment_review.py`
- Modify: `twocomms/management/services/ig_commercial_episodes.py`
- Modify: `twocomms/management/ig_bot_models.py` only if an existing unique key cannot express the invariant
- Create: `twocomms/management/migrations/0141_*.py` only if schema metadata changes are required

**Step 1: Introduce a stable claim anchor**

Build an immutable digest from the user-originated payment evidence only: source message IDs, normalized payment-statement text, and receipt identity. Exclude watermarks, manager text, order draft, catalog candidates, delivery details, and model classifications.

**Step 2: Claim the review before expensive enrichment**

Within the existing client/episode locking pattern, resolve or create one review using a stable key such as:

```python
dedupe_key = f"ig-payment-review:v2:{client.pk}:{episode.pk}:{claim_anchor}"
review, created = IgPaymentConfirmationReview.objects.get_or_create(
    dedupe_key=dedupe_key,
    defaults=base_evidence,
)
```

Only the caller that creates the row performs media persistence, image-role classification, and catalog matching. A later call with the same anchor refreshes safe contextual evidence on the pending record and reuses its notification outbox key.

**Step 3: Preserve genuine repeat purchases**

Use the current commercial episode in the identity. A new explicit repeat episode or a resolved prior episode permits a new review; two copies of the same claim within one active episode do not.

**Step 4: Run focused tests to verify GREEN**

Run the Task 1 command and verify every new invariant passes.

### Task 3: Establish one side-effect owner

**Files:**
- Modify: `twocomms/management/services/bot_sales_classifier.py`
- Modify: `twocomms/management/services/bot_conversation_analysis.py`
- Modify: `twocomms/management/tests_ig_sales_automation.py`
- Modify: `twocomms/management/tests_ig_conversation_analysis_jobs.py`

**Step 1: Keep review intake at the live customer-evidence boundary**

The synchronous deterministic classifier may intake a review only for a live customer message with payment evidence. Remove the post-Gemini review creation path so Gemini completion cannot create a second review or duplicate manager notification.

**Step 2: Make reconciliation read/project only**

Pass `operational_effects=False` for every historical/reconciliation `ensure_rule_classification()` call. Confirm no payment review, Telegram outbox write, vision request, or order mutation is possible there.

**Step 3: Run the focused tests to verify GREEN**

Run the Task 1 command plus:

```bash
SECRET_KEY=test_local_secret .venv/bin/python twocomms/manage.py test management.tests_ig_conversation_analysis_jobs -v 2
```

### Task 4: Safely reconcile historic duplicate tasks

**Files:**
- Modify: `twocomms/management/services/ig_payment_review.py`
- Create: `twocomms/management/management/commands/reconcile_ig_payment_reviews.py`
- Modify: `twocomms/management/tests_ig_payment_review.py`
- Create: `twocomms/management/tests_ig_payment_review_reconciliation.py`
- Modify: `twocomms/management/bot_views.py`
- Modify: `twocomms/management/tests_ig_clients_ui.py`

**Step 1: Write failing reconciliation tests**

Create a group of unlinked pending reviews with the same strict legacy evidence fingerprint. Verify exactly one canonical review remains actionable; every other row becomes `superseded`, retains its evidence, references the canonical row, and closes only its redundant episode. Verify a different receipt fingerprint remains untouched.

**Step 2: Add a dry-run-first management command**

The command must support `--dry-run`, bounded `--limit`, optional `--client-id`, deterministic selection, JSON summary counts, and idempotent reruns. It must not contact Meta, Gemini, Telegram, Monobank, or create orders.

**Step 3: Exclude superseded rows from all order-workspace counts and cards**

The UI must expose a compact history signal only in a selected review context, not present duplicate active cards. Action, confirmed, and all counts must be canonical physical work counts.

**Step 4: Run focused tests to verify GREEN**

Run the Task 1 command plus the new reconciliation and UI tests.

### Task 5: Verify release behavior and remediate production records

**Files:**
- Modify: `docs/IG_CRM_RECONCILIATION_2026-07-30.md` only if it remains the canonical operational record

**Step 1: Run integrity checks**

```bash
SECRET_KEY=test_local_secret .venv/bin/python twocomms/manage.py check
SECRET_KEY=test_local_secret .venv/bin/python twocomms/manage.py makemigrations --check --dry-run
python3 -m compileall -q twocomms/management
git diff --check
```

**Step 2: Independently review specification and code quality**

Review exact tests, diff, query behavior, race handling, and no-network reconciliation before commit.

**Step 3: Commit, integrate current `origin/main`, push `main`, and deploy**

On the server: fast-forward `main`, migrate if needed, run `check`, collect static assets if UI changes require it, restart Passenger, ensure the bot daemon, then run the reconciliation command in dry-run mode followed by bounded live mode.

**Step 4: Prove production outcome**

Verify equal local/origin/server SHA; query MariaDB for zero active duplicate payment-review fingerprints, no new duplicate notification keys, current daemon heartbeat, and analysis token/job totals with historical backfill disabled. Verify the management orders API returns one actionable card per canonical claim.
