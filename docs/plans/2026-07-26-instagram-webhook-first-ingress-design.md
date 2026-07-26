# Instagram Webhook-First Ingress Design

## Goal

Make Instagram CRM updates event-driven and durable without spending Meta or
Gemini quota on permanent short polling. Customer, bot and manager messages
must remain visible and analyzable while payment and funnel labels stay
evidence-bound.

## Decision

Use **signed webhook primary ingress with bounded adaptive reconciliation**.

Rejected alternatives:

1. Webhook-only has no recovery path for provider delivery gaps or deploy
   windows.
2. Continuous Graph polling adds latency and rate-limit pressure, cannot solve
   missing Meta permissions, and must never be coupled to opening a chat.
3. Webhook-primary plus bounded recovery gives immediate normal delivery and a
   controlled repair path without claiming polling can replace App Review or a
   missing app secret.

## Event Flow

1. The HTTP endpoint verifies `X-Hub-Signature-256` and fails closed when
   `IG_APP_SECRET` is absent.
2. The endpoint parses a bounded payload, persists each message idempotently by
   Meta message ID, updates only mandatory local safety state, schedules durable
   work, and returns `200`. No Graph, Gemini, catalog-media fetch, payment
   matching or Telegram transport runs before the response.
3. Customer messages eligible for a reply enter the existing durable reply
   queue. Explicit opt-out remains an immediate local routing barrier.
4. Every stored customer, manager or bot message advances one per-client
   analysis watermark. The existing analysis job coalesces a burst for 30
   seconds, so a manager sending several messages creates one high-reasoning
   conversation analysis rather than one call per message.
5. Manager echoes immediately pause customer automation and cancel follow-ups,
   but never create an automatic reply. The durable analysis job includes the
   manager role and treats manager text as authoritative operational evidence,
   not as customer intent.
6. A successful bot reply is stored before its analysis watermark is advanced.
   The next coalesced analysis therefore sees the customer question and the
   actual bot answer together.
7. The browser reads only MariaDB-backed incremental APIs. Active visible chats
   may poll the local endpoint; hidden tabs back off or stop. UI refresh never
   calls Meta Graph.

## Recovery Polling

- Conversation discovery and message catch-up are recovery jobs only.
- Every cycle has page, request and wall-clock budgets, safe pagination-host
  validation, per-conversation cursors and round-robin fairness.
- Eligible fallback discovery uses the production-proven page endpoint and a
  small `limit=10`; message reads use a 12-second timeout because an observed
  valid Meta response took more than five seconds. These values are operational
  evidence, not a claim that Meta guarantees them.
- `429` and Meta throttle codes (`4`, `17`, `32`, `613`) enter backoff. Usage
  pressure from response headers must reduce the polling budget. Permission and
  configuration errors are actionable/degraded and are not retried every few
  seconds. Transport/5xx failures use exponential backoff with jitter.
- A complete successful refresh clears only refresh degradation; a complete
  successful message pass clears only poll degradation. A budget-truncated pass
  cannot clear prior evidence.

## Payment And Funnel Truth

The interface must not render a receipt awaiting manager review beside an
unqualified `Оплачено` label. It exposes separate facts:

- customer claim or receipt observed;
- manager review pending/approved/rejected;
- provider payment unverified/confirmed/refunded;
- order linked/created and fulfillment stage.

The prominent operational stage is derived from the strongest authoritative
fact. A raw analytical `paid` prediction remains diagnostic only and cannot
override a pending manager/provider truth. A manager-verified linked order may
advance to order/fulfillment even when provider truth is unavailable, but the UI
must label that source explicitly.

## Meta Evidence And Blockers

Context7 MCP was requested but is not connected in this runtime. Official Meta
documentation was checked directly instead:

- Rate limits: <https://developers.facebook.com/docs/graph-api/overview/rate-limiting/>
- Instagram Messaging API: <https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging-api>

The current Meta rate-limit page states that all Graph requests are rate
limited, page-token requests can use Business Use Case limits, usage may be
reported in response headers, and throttle codes include `4`, `17`, `32` and
`613`. It does not justify a fixed request-every-second design.

Current production blockers remain external and must be shown honestly:

- `IG_APP_SECRET` is absent, so signed webhook ingress remains fail-closed.
- the app lacks Advanced Access to `instagram_manage_messages` for Yana; code
  cannot grant this permission.

## Acceptance

- A valid signed event is durably stored and acknowledged without classifier,
  Gemini, Graph, media download or notification transport on the request path.
- Duplicate webhook delivery creates no duplicate message, reply, signal,
  analysis job, payment review or post-sale case.
- A manager burst is stored message-for-message but coalesced into one due
  high-reasoning job and never sends a bot reply.
- A bot reply advances the same analysis watermark.
- Local chat updates show new messages and corrected operational stage without
  calling Meta.
- Pending receipt, manager truth, provider truth and fulfillment never conflict
  in the main label.
- A real fresh signed message is the final production proof. Until the secret
  and Advanced Access exist, production status remains degraded rather than
  falsely green.
