# Instagram Manual Order Binding Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe manager-driven website-order binding/unbinding to Instagram clients, canonical TTN actions, origin visibility, and localized fulfillment follow-up.

**Architecture:** Keep immutable payment attribution intact and add a mutable current assignment projection plus append-only audit events. Route all automatic/manual links through one row-locked service; drive UI and fulfillment messages from assignment-first truth.

**Tech Stack:** Django 5.2, MariaDB/MySQL production, SQLite tests, server-rendered HTML/vanilla JS, existing Meta Send API boundary, Playwright CLI.

---

### Task 1: Assignment models and migration

**Files:**
- Modify: `twocomms/management/ig_bot_models.py`
- Create: `twocomms/management/migrations/0119_ig_order_assignments.py`
- Create: `twocomms/management/tests_ig_order_assignments.py`

- [ ] Write failing model tests for one row per order, append-only events,
  operation-id uniqueness, version defaults, and legacy attribution backfill.
- [ ] Run `DEBUG=True NOVA_POSHTA_FALLBACK_ENABLED=False .venv/bin/python twocomms/manage.py test management.tests_ig_order_assignments -v 2` and confirm model import/migration failures.
- [ ] Add `IgOrderAssignment`, `IgOrderAssignmentEvent`, and
  `IgOrderCustomerEvent` with bounded choices/indexes and append-only event
  querysets.
- [ ] Generate and edit migration 0119 with a reversible attribution backfill.
- [ ] Re-run the model tests and confirm green.

### Task 2: Atomic assignment service

**Files:**
- Create: `twocomms/management/services/ig_order_assignments.py`
- Modify: `twocomms/management/services/ig_order_links.py`
- Modify: `twocomms/management/tests_ig_order_assignments.py`
- Modify: `twocomms/management/tests_ig_order_links.py`

- [ ] Write failing service tests for exact-number link, another-owner conflict,
  same-owner idempotency, operation replay, stale version, reason-required
  unlink, re-link after unlink, and immutable attribution preservation.
- [ ] Implement assignment-first resolvers and row-lock mutation commands.
- [ ] Call the assignment service from `create_order_attribution` so provider
  and assisted-checkout orders populate the same projection.
- [ ] Verify manual binding never mutates payment/order truth and automatic
  binding reports its source.
- [ ] Run both assignment and legacy order-link suites to green.

### Task 3: Management API and current-reader migration

**Files:**
- Modify: `twocomms/management/bot_views.py`
- Modify: `twocomms/management/urls.py`
- Modify: `twocomms/management/services/ig_post_sale.py`
- Modify: `twocomms/management/services/bot_orders.py`
- Modify: `twocomms/management/tests_ig_clients_ui.py`
- Modify: `twocomms/management/tests_ig_post_sale.py`

- [ ] Write failing API tests for authorization, exact-order link, versioned
  unlink, 409 conflict, actor/source payload, candidate blocked labels, and
  assignment-first client/order history.
- [ ] Add link and unlink endpoints using `_require_admin_json` and stable JSON
  error codes.
- [ ] Extend candidate ownership checks to current assignments before legacy
  attribution/deal/review checks.
- [ ] Serialize origin, actor, version, unlink capability, TTN capability,
  canonical staff action URL, and tracking URL.
- [ ] Change post-sale and shipment readers to assignment-first truth with a
  legacy-attribution fallback only when no assignment row exists.
- [ ] Run API/client/post-sale/shipment suites to green.

### Task 4: Manual-order client context

**Files:**
- Modify: `twocomms/storefront/views/manual_orders.py`
- Modify: `twocomms/storefront/tests/test_manual_orders.py`

- [ ] Write failing tests that a staff-only `ig_client` context prefills the
  manual order and assigns the newly created order without asserting payment.
- [ ] Preserve the client id through the signed/validated form payload and call
  the assignment service after order creation.
- [ ] Reject hidden/missing clients and retain ordinary manual-order behavior.
- [ ] Run focused manual-order and assignment tests to green.

### Task 5: Localized durable fulfillment events

**Files:**
- Create: `twocomms/management/services/ig_order_fulfillment.py`
- Modify: `twocomms/management/management/commands/poll_ig_deal_payments.py`
- Create: `twocomms/management/tests_ig_order_fulfillment.py`

- [ ] Write failing tests for locale normalization, exact UK/RU/EN TTN and
  review copy, dedupe keys, claim/lease ownership, stale-assignment cancel,
  response-window/manual-review behavior, and received-order production.
- [ ] Implement reconciliation from assignment plus order truth and claim
  events before provider I/O.
- [ ] Revalidate assignment/version and customer send permission at the final
  send boundary; never automatically retry ambiguous sends.
- [ ] Add bounded event reconciliation/dispatch to the existing polling command.
- [ ] Run fulfillment, reply-boundary, shipment, and payment polling tests.

### Task 6: Desktop-first interaction design

**Files:**
- Modify: `twocomms/management/templates/management/bot.html`
- Modify: `twocomms/management/tests_ig_clients_ui.py`

- [ ] Write failing template/API contract assertions for the header icon,
  drawer controls, accessible candidate reasons, origin line, version token,
  unlink reason, and TTN capabilities.
- [ ] Add the compact package-link icon before settings and reuse the existing
  focus-trapped client drawer.
- [ ] Render assignment cards, exact search, link, confirmed unlink, tracking,
  canonical TTN action, and new-order action without reloading the page.
- [ ] Keep unavailable candidates keyboard-focusable with `aria-disabled` and
  server-rendered reason labels.
- [ ] Verify fixed desktop dimensions, focus visibility, reduced motion, and no
  nested-card or layout-overlap regressions.

### Task 7: Integration, review, and deployment

**Files:**
- Review all changed files and migration state.

- [ ] Run focused management/order/storefront suites, `manage.py check`,
  `makemigrations --check --dry-run`, compileall, and `git diff --check`.
- [ ] Start the local server and run Playwright at 1440x900 and 1920x1080 for
  link, conflict, unlink, re-link, and TTN action states; capture screenshots.
- [ ] Run independent code and design reviews; fix every high-confidence issue
  and rerun affected tests.
- [ ] Rebase/merge latest `origin/main` without taking uncommitted parallel-agent
  files; rerun the complete verification set.
- [ ] Commit scoped files, push `codex/ig-order-fulfillment-links`, merge to
  `main`, and push `origin/main`.
- [ ] On production: pull fast-forward, migrate MySQL, check, collectstatic,
  compress, restart Passenger/bot daemons, run no-send reconciliation smoke.
- [ ] Prove deployed SHA, applied migration, assignment/backfill counts,
  event queue states, daemon heartbeat, and management endpoint health.
