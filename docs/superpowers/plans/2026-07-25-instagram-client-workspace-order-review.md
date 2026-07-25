# Instagram Client Workspace and Order Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an evidence-bound Instagram client workspace that separates manager/provider payment truth, supports create/link order actions, preserves product/price/delivery attribution, and replaces raw signal counters with useful pattern episodes.

**Architecture:** Keep the existing Django management app and provider ledger. Add narrow management-owned decision, attribution, link, and pattern projections with explicit source/actor/evidence fields. Extend the client detail JSON contract and rebuild the existing vanilla-JS client detail into a responsive workspace with a contextual payment drawer.

**Tech Stack:** Django 5.x, MySQL production, Django migrations, `TestCase`, existing management APIs, vanilla JavaScript/CSS, existing Telegram notification outbox, existing Nova Poshta directory validation.

---

### Task 1: Payment decision truth and rejection lifecycle

**Files:**
- Create: `twocomms/management/migrations/0103_ig_payment_review_truth.py`
- Modify: `twocomms/management/ig_bot_models.py`
- Modify: `twocomms/management/services/ig_payment_review.py`
- Modify: `twocomms/management/bot_views.py`
- Test: `twocomms/management/tests_ig_payment_review_truth.py`

- [x] **Step 1: Write failing tests** for `manager_verified`, `manager_rejected`, idempotent replay, required rejection reason, provider projection immutability, stage event, and reanalysis scheduling.
- [x] **Step 2: Run the focused tests and verify RED** with missing model/service behavior.
- [x] **Step 3: Add the decision model, migration, and transactional service**. Store `verification_source`, `decision`, `reason_code`, `reason_text`, actor, timestamp, watermark, and immutable previous state. Keep `IgPaymentProjection` unchanged.
- [x] **Step 4: Extend action API** to accept `manager_verify` and structured rejection; return source-qualified payment state and next action.
- [x] **Step 5: Run focused tests and verify GREEN**, then run existing payment-review suites.
- [x] **Step 6: Commit** `feat: add source-qualified instagram payment decisions`.

### Task 2: Order attribution, existing-order linking, and item provenance

**Files:**
- Create: `twocomms/management/migrations/0104_ig_order_attribution.py`
- Create: `twocomms/management/services/ig_order_links.py`
- Modify: `twocomms/management/ig_bot_models.py`
- Modify: `twocomms/orders/services/order_builder.py`
- Modify: `twocomms/storefront/views/manual_orders.py`
- Test: `twocomms/management/tests_ig_order_links.py`
- Test: `twocomms/storefront/tests/test_manual_orders.py`

- [x] **Step 1: Write failing tests** for one client/many orders, exact identifier linking, cross-client rejection, idempotent repeated link, automatic/manual/linked origin, fit/negotiated-price snapshots, and manager/provider payment source.
- [x] **Step 2: Run tests and verify RED.**
- [x] **Step 3: Add attribution/link models and atomic service** with active-link conflict checks, evidence, actor, matcher version, and unlink reason.
- [x] **Step 4: Add review-form action** to search/select an existing order and link it, while preserving the existing editable create flow.
- [x] **Step 5: Persist item fit/option/price provenance and attribution** from both automatic and manual paths.
- [x] **Step 6: Run focused and related order/payment suites; commit** `feat: link instagram clients to attributed orders`.

**Task 2 evidence (2026-07-25):** commit `7a319f4f` is present on
`origin/main`, `origin/codex/ig-crm-master-audit`, and production. The changed
order/payment/manual-order suite passed `142` tests (`OK`, 2 expected skips),
`manage.py check`, `makemigrations --check --dry-run`, compile and diff checks
passed. Production MariaDB `11.4.12` has migration `0104` applied, both new
tables are `InnoDB`, all four append-only triggers exist, and a rollback-only
synthetic-row smoke blocked `UPDATE`/`DELETE` without touching real orders or
payments. Existing-order links return an absolute storefront admin URL;
unresolved new orders retain the editable manual-order flow. Production
`poll_ig_deal_payments --limit 5` created zero orders and zero notifications.

### Task 3: Nova Poshta validation and fulfillment gates

**Files:**
- Create: `twocomms/management/migrations/0105_ig_deal_delivery_truth.py`
- Modify: `twocomms/management/ig_bot_models.py`
- Modify: `twocomms/management/services/bot_orders.py`
- Modify: `twocomms/orders/services/order_builder.py`
- Test: `twocomms/management/tests_ig_fulfillment_truth.py`

- [x] **Step 1: Write failing tests** proving text-only city/office cannot auto-create an order, canonical refs survive into `Order`, and unresolved lines create manager work instead.
- [x] **Step 2: Run tests and verify RED.**
- [x] **Step 3: Add validated delivery fields/state and require signed directory refs** before automatic fulfillment.
- [x] **Step 4: Preserve classic/oversize and negotiated totals** through deal → order materialization without catalog-price substitution.
- [ ] **Step 5: Run focused payment/order/Nova Poshta suites; commit** `fix: gate instagram fulfillment on validated delivery data`.

Task 3 implementation is currently green locally (`24` focused tests):
`IgDeal` now stores directory Refs and a source-qualified delivery status;
text-only delivery creates one skipped manager task and never materializes an
order; validated selections copy settlement/city/warehouse Refs to `Order`.
Step 5 stays open until migration `0105` is applied and verified on production
MariaDB.

### Task 4: Client workspace API contract

**Files:**
- Modify: `twocomms/management/bot_views.py`
- Test: `twocomms/management/tests_ig_clients_ui.py`

- [ ] **Step 1: Write failing API tests** for active review, decision history, media grouped by role, catalog links, draft uncertainty, attributed orders, source-qualified payment, automation owner, and pattern episodes.
- [ ] **Step 2: Run tests and verify RED.**
- [ ] **Step 3: Build a bounded client-detail payload** with independent `automation`, `interaction`, `payment`, `fulfillment`, `review`, `orders`, and `patterns` objects.
- [ ] **Step 4: Add review action endpoints** for confirm/reject/create/link with permission and hidden-client guards.
- [ ] **Step 5: Run focused API tests and existing client UI tests; commit** `feat: expose instagram client commercial context`.

**Product approval placement requirement:** product approval is not rendered as
an always-on card in the main bot overview. The API must expose a separate,
bounded approval queue/count and a client-scoped approval collection. A client
detail action opens that client's contextual approval drawer/tab with evidence
media, matched catalog candidates, quantity/fit/price, uncertainty, and the
actions `Погодити`/`Відхилити`. Approval must offer an explicit choice between
linking an existing custom-admin order and opening the editable create-order
flow; it must never silently create or link an order.

The same contract also powers a dedicated `Замовлення` section after
statistics, with the views `Потрібна дія`, `Підтверджені`, and `Усі`. Its order
card shows the client, lines, negotiated amount, manager/provider payment truth,
delivery state, linked custom-admin order status/number, and a direct admin
link. The card is reachable from this section, the client workspace, and the
Telegram review alert without creating three divergent representations.

### Task 5: Responsive workspace and payment drawer

**Files:**
- Modify: `twocomms/management/templates/management/bot.html`
- Test: `twocomms/management/tests_ig_clients_ui.py`
- Test: browser smoke under the existing management browser harness

- [ ] **Step 1: Write failing template/DOM contract tests** for no duplicate category/stage text, role/time labels, pending review CTA, rejection reason field, product/receipt sections, and mobile layout hooks.
- [ ] **Step 2: Run tests and verify RED.**
- [ ] **Step 3: Replace the single vertical detail renderer** with semantic sections, safe DOM construction, right rail/drawer, keyboard/focus behavior, and Ukrainian explanatory copy with exact English technical terms retained.
- [ ] **Step 4: Add reduced-motion pulse and responsive 1440/1280/768/390/320 behavior** with no nested scroll trap.
- [ ] **Step 5: Run focused template tests and browser screenshots; commit** `feat: rebuild instagram client workspace UX`.

**UX acceptance:** the main overview shows only a compact pending-approval
badge/entry, not the approval cards themselves. The separate approval tab is
scannable by client and count, while the per-client drawer remains contextual,
keyboard-accessible, responsive, and free of duplicate facts. Confirmed,
rejected, linked-existing, and create-new states remain visually distinct.
The `Замовлення` section follows the same pattern after statistics; its three
filters and client/order cards are reused by the client drawer and Telegram
deep-link, with no approval/order card mounted in the general overview.

### Task 6: Pattern episodes and honest analytics

**Files:**
- Create: `twocomms/management/migrations/0106_ig_conversation_patterns.py`
- Create: `twocomms/management/services/bot_conversation_patterns.py`
- Modify: `twocomms/management/ig_bot_models.py`
- Modify: `twocomms/management/services/bot_sales_classifier.py`
- Modify: `twocomms/management/bot_views.py`
- Test: `twocomms/management/tests_ig_pattern_lifecycle.py`

- [ ] **Step 1: Write failing tests** for repeated manager messages collapsing into one activity episode, four size messages producing four occurrences/one episode, resolution transitions, payment/order outcomes, hidden exclusion, and distinct-user versus event denominators.
- [ ] **Step 2: Run tests and verify RED.**
- [ ] **Step 3: Add occurrence/episode/transition projections** with actor/origin/evidence/version and deterministic grouping rules.
- [ ] **Step 4: Replace raw signal chips and aggregate counters** with episode summaries and explicit statistics metadata.
- [ ] **Step 5: Run focused pattern/statistics suites and commit** `feat: model instagram conversation pattern episodes`.

### Task 7: Telegram review action, media audit, and release verification

**Files:**
- Modify: `twocomms/management/services/ig_payment_review.py`
- Modify: `twocomms/management/views.py`
- Modify: `twocomms/management/models.py`
- Test: `twocomms/management/tests_ig_payment_review.py`
- Test: `twocomms/management/tests_ig_media_workflow.py`
- Test: `twocomms/management/tests_ig_notifications.py`

- [ ] **Step 1: Write failing callback tests** for authorized staff, exact message binding, idempotent replay, independent media retry, and product/receipt captions.
- [ ] **Step 2: Run tests and verify RED.**
- [ ] **Step 3: Implement the callback/media contract** without coupling decision state to media delivery.
- [ ] **Step 4: Run the full related Instagram/Gemini/chat suite, `manage.py check`, migration drift, compile and diff checks.**
- [ ] **Step 5: Commit, push, deploy using the established server flow, and verify SHA, migrations, Passenger, daemon singleton, DB/cache heartbeat, queues/outbox, and browser/API behavior.**

---

## Self-review coverage

- Paused conversations remain analyzed; hidden clients remain excluded.
- Product screenshots, receipts, custom-print references, and unknown images remain separate and evidence-bound.
- Negotiated prices never silently become catalog prices; prepayment and total are separate.
- Multiple fits/products remain separate through order creation.
- Manual and provider payment truth remain distinct but auditable.
- New and existing orders, Instagram identity, source, origin, amount, delivery, and TTN are linked.
- Signals become explainable episodes with outcomes and honest denominators.
- UI is Ukrainian except exact technical/product names, responsive, keyboard-accessible, and free of duplicate facts.
