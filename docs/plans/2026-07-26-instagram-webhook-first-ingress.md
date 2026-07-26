# Instagram Webhook-First Ingress Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make signed webhooks the fast durable primary ingress, coalesce customer/bot/manager analysis, keep Graph polling bounded recovery-only, and render one evidence-backed operational funnel state.

**Architecture:** Persist Meta messages idempotently before analysis, keep the customer reply queue separate from a per-client debounced high-reasoning job, and read chats only from MariaDB. Recovery polling uses small pages, cursors, budgets and provider-aware backoff; it never runs because a manager opened the UI.

**Tech Stack:** Django 5, Python 3.14, MariaDB 11.4 production, Django cache, Meta Graph API v25, existing daemon and analysis job, vanilla JavaScript, Django TestCase.

---

### Task 1: Ship the evidenced fallback parameter correction

**Files:**
- Modify: `twocomms/management/services/instagram_bot.py`
- Test: `twocomms/management/tests_ig_polling.py`
- Modify: `docs/qa/IG_CRM_ORDER_ATTRIBUTION_CHECKLIST_2026-07-25.md`

1. Keep the RED/GREEN expectations for `limit=10` and the 12-second message timeout.
2. Run the focused polling/status tests, expanded ingress/funnel suite, related
   payment/order/post-sale suite, Django check, migration drift, compile and
   diff checks.
3. Commit only this slice and its checklist evidence.
4. Push, validate a new MariaDB gzip backup, deploy, restart Passenger/daemon,
   then verify deployed SHA, health, queue, discovery and poll telemetry.
5. Do not claim Yana ingress restored while Advanced Access/app secret are absent.

### Task 2: Make the webhook request path persistence-only

**Files:**
- Modify: `twocomms/management/services/instagram_bot.py`
- Modify: `twocomms/management/bot_webhook.py`
- Test: `twocomms/management/tests_ig_webhook_security.py`
- Test: `twocomms/management/tests_ig_intelligence.py`

1. Write a failing endpoint test that patches classifier, Gemini, Graph HTTP,
   media recovery and notification delivery to raise if called before response.
2. Verify the signed POST currently fails that contract for a normal inbound.
3. Add an explicit persistence-only ingress mode used by the webhook. Preserve
   immediate opt-out and manager takeover routing barriers, but schedule durable
   analysis instead of executing full classifier/payment/post-sale work inline.
4. Remove per-request processing threads; the singleton daemon owns queue work.
5. Verify duplicate signed POSTs are idempotent and the endpoint still fails
   closed without `IG_APP_SECRET`.

### Task 3: Coalesce customer, manager and bot analysis

**Files:**
- Modify: `twocomms/management/services/instagram_bot.py`
- Modify: `twocomms/management/services/bot_conversation_analysis.py`
- Test: `twocomms/management/tests_ig_conversation_analysis_jobs.py`
- Test: `twocomms/management/tests_ig_intelligence.py`

1. Add RED tests showing three manager echoes create three timeline messages but
   one pending job whose watermark is the last message and whose due time moves
   forward.
2. Add a RED test showing a stored successful bot reply advances the same job.
3. Schedule analysis directly after durable storage with role-specific triggers;
   do not generate replies for manager/model roles.
4. Run the rule classifier in the reply worker before customer generation so
   opt-out/no-buy/reaction routing stays deterministic.
5. Verify job lease, superseded revision, retry and reconciliation tests.

### Task 4: Add adaptive recovery scheduling and usage telemetry

**Files:**
- Modify: `twocomms/management/services/instagram_bot.py`
- Modify: `twocomms/management/management/commands/run_instagram_bot.py`
- Test: `twocomms/management/tests_ig_polling.py`
- Test: `twocomms/management/tests_ig_daemon.py`

1. Add RED tests for 429/throttle, permission 4xx, 5xx/transport and success.
2. Persist/cache a bounded next-recovery time and failure class.
3. Apply exponential backoff plus deterministic jitter for transient failures;
   suspend frequent retries for permission/config failures.
4. Parse only documented Meta usage headers, record bounded percentages, and
   reduce/skip recovery when pressure is high. Never log tokens or raw PII.
5. Prove UI and local incremental chat calls do not invoke `poll_ingest`.

### Task 5: Unify payment-review and operational-funnel projection

**Files:**
- Modify: `twocomms/management/bot_views.py`
- Modify: `twocomms/management/templates/management/bot.html` only if the API contract alone cannot remove ambiguity
- Test: `twocomms/management/tests_ig_clients_ui.py`
- Test: `twocomms/management/tests_ig_payment_review.py`

1. Reproduce receipt-pending versus raw-paid conflict in an API test.
2. Define one server-side operational projection using provider truth, manager
   decision, order attribution and fulfillment; keep `stage_raw` diagnostic.
3. Return explicit claim/review/provider/order facts and render the operational
   label consistently in list, header, funnel and incremental response.
4. Verify manager-verified linked order, provider-paid order, pending receipt,
   rejected receipt, refund/exchange and repeat-order cases.
5. Run authenticated browser QA at 1440, 768, 390 and 320 px with no overflow,
   stale label after incremental update, console error or Meta request.

### Task 6: Release and real-event proof

1. Run focused and related suites, `manage.py check`, migration drift, scoped
   compile, JavaScript syntax and `git diff --check`.
2. Independently review the diff and verify no fixed customer amounts/IDs.
3. Commit/push one independently deployable slice at a time.
4. Before each deploy validate a fresh MariaDB backup; then migrate, collect
   static, compress, restart Passenger and daemon, and verify SHA/health/queues.
5. After `IG_APP_SECRET` and Meta Advanced Access are supplied, prove one fresh
   signed inbound is stored, debounced, analyzed and reflected in chat/funnel.
   For Yana, an exchange message must attach one post-sale case to order 296 and
   create no duplicate order.
