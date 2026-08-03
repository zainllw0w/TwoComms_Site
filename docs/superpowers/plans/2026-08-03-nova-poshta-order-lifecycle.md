# Nova Poshta Order Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore bounded, idempotent Nova Poshta tracking and repair the linked waybill, variant, Telegram, and Meta regressions.

**Architecture:** Keep legacy tracking as the current production source of truth, batch up to 100 TTNs, persist the next eligible poll and terminal state, and run the command through an idempotent managed cron block. Use one best-effort immediate lookup after TTN attachment. Keep payment side effects in the existing durable JSON ledger and align browser Pixel/CAPI with the deterministic order Purchase ID.

**Tech Stack:** Django management commands and ORM, requests, MariaDB-compatible migrations, Django TestCase/SimpleTestCase, shell cron installer, existing Playwright/browser smoke flow.

---

### Task 1: Tracking contract and persistence

**Files:**
- Modify: `twocomms/orders/models.py` (`Order` tracking fields)
- Create: `twocomms/orders/migrations/0054_order_tracking_lifecycle.py`
- Modify: `twocomms/orders/nova_poshta_service.py`
- Modify: `twocomms/orders/management/commands/update_tracking_statuses.py`
- Test: `twocomms/storefront/tests/test_nova_poshta_tracking_dedup.py`
- Test: `twocomms/storefront/tests/test_nova_poshta_tracking_command.py`

- [ ] Write tests for a 101-order queryset becoming two provider requests (100 + 1), response matching by TTN rather than position, codes 9/10/11 completing exactly once, and terminal rows being excluded on the next queryset.
- [ ] Run the focused tests and confirm RED because the service currently performs one request per order and only recognizes code 9.
- [ ] Add nullable/indexed tracking fields and the migration: `tracking_status_code`, `tracking_checked_at`, `tracking_provider_event_at`, `tracking_next_check_at`, `tracking_failure_count`, and `tracking_terminal_at`.
- [ ] Implement `get_tracking_info_batch()` with a reusable session, normalized TTN keys, a hard chunk size of 100, and explicit API/partial-response errors.
- [ ] Refactor `update_all_tracking_statuses()` to select eligible active/recent orders, batch provider calls, apply each result atomically, and report batch/row errors without publishing a heartbeat on failure.
- [ ] Make delivery success `{9, 10, 11}` and terminal failures explicit sets. Never infer completion from localized status text.
- [ ] Set next checks to five minutes for active movement and fifteen minutes for waiting/storage states; stop polling terminal rows and orders older than 90 days without a result.
- [ ] Run the focused tests and confirm GREEN, then run `manage.py makemigrations --check` and `manage.py check`.

### Task 2: Durable cron installation and immediate TTN lookup

**Files:**
- Create: `scripts/install_nova_poshta_tracking_cron.sh`
- Test: `tests/test_install_nova_poshta_tracking_cron.py`
- Modify: `twocomms/storefront/views/order_actions.py`
- Test: `twocomms/storefront/tests/test_telegram_order_status_actions.py`

- [ ] Add failing installer tests for preserving unrelated crontab lines, replacing one stale managed block, rejecting malformed/duplicate markers, idempotent `--install`, and `--check` drift detection.
- [ ] Run the installer tests and confirm RED for the missing entry point.
- [ ] Add an executable installer with a managed BEGIN/END block, `flock`, `nice`, explicit project paths, and no full-crontab replacement outside the managed block.
- [ ] Add a best-effort post-commit lookup for a newly attached TTN; catch and log provider failures after the local transaction has committed.
- [ ] Run installer and action tests GREEN, including a failure case proving the TTN remains persisted.

### Task 3: Waybill description retry, variants, and UI placement

**Files:**
- Modify: `twocomms/orders/nova_poshta_documents.py`
- Modify: `twocomms/orders/models.py`
- Modify: `twocomms/storefront/views/order_actions.py`
- Modify: `twocomms/twocomms_django_theme/templates/pages/telegram_order_nova_poshta_action.html`
- Test: `twocomms/storefront/tests/test_telegram_order_status_actions.py`
- Test: `twocomms/storefront/tests/test_phase7_variants.py`

- [ ] Write RED tests for exact `Description is not valid` retry with `Одяг`, no retry for another provider error, duplicate fit-axis suppression in both item models, and server/AJAX alert attributes and placement.
- [ ] Add `NovaPoshtaInvalidDescriptionError`, retry exactly once only around `InternetDocument.save`, and keep the existing stable operator-facing error for a failed retry.
- [ ] Filter dropshipper option labels by machine fit axis, matching `OrderItem` behavior.
- [ ] Render form/API errors in the action panel immediately before the submit button, with `role="alert"`, `aria-live="assertive"`, and assertive AJAX state updates; keep blocked/page errors in their existing page state.
- [ ] Run focused tests GREEN and exercise the mobile waybill form in Playwright.

### Task 4: Post-payment and Meta event correctness

**Files:**
- Modify: `twocomms/storefront/views/utils.py`
- Modify: `twocomms/orders/facebook_conversions_service.py`
- Modify: `twocomms/twocomms_django_theme/templates/pages/order_success.html`
- Test: `twocomms/orders/tests/test_post_payment_recovery.py`
- Test: `twocomms/storefront/tests/test_analytics_tracking.py`

- [ ] Write RED tests for no-event Instagram orders becoming `skipped`, Telegram `already_sent` becoming `sent`, Meta ledger reading `fb_conversions_api.event_id`, persisted event time surviving a failed first send, and the success page not suppressing Pixel solely because CAPI was sent.
- [ ] Implement those minimal state/ledger changes and include terminal NP codes in event-time selection.
- [ ] Verify deterministic `order.get_purchase_event_id()` is used for both CAPI and Pixel, and preserve one internal Purchase action.
- [ ] Run focused post-payment and analytics tests GREEN, then run the broader checkout/Monobank/Telegram/Meta suite.

### Task 5: Verification, review, and delivery

**Files:**
- No new production files; review all task diffs and deployment evidence.

- [ ] Run focused tests, broader regression tests, `manage.py check`, compilation, migration drift, and `git diff --check` from the isolated worktree.
- [ ] Request an independent code review against `a30c7b33`; fix all critical/important findings.
- [ ] Commit task-specific files, push the branch, fast-forward `main`, and deploy with the user-provided SSH command.
- [ ] Run the cron installer on production and verify `--check`, the deployed SHA, cron heartbeat, active TTN batch behavior, idempotent reconciliation, no Purchase duplicates, persisted Meta/Telegram markers, and public `/healthz/`, `/`, `/cart/` 200 responses.
