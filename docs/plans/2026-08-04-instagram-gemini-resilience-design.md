# Instagram Gemini Resilience Design

Date: 2026-08-04
Status: approved by the user
Scope: management-subdomain Instagram Direct bot

## Incident evidence

The latest customer reply failed because the live-chat scheduler exhausted its
75-second wall-clock budget on three `gemini-3.6-flash` read timeouts. Each
attempt received the full 25-second read timeout, so `GEMINI_API3`,
`GEMINI_API4`, `GEMINI_API5`, and every fallback model were never attempted.
The provider returned no HTTP response; the application incorrectly labelled
the transport `ReadTimeout` as overload/HTTP 503.

The independent CRM-analysis worker succeeded 7.8 seconds later with
`GEMINI_API4` and `gemini-3.5-flash`, proving that the six-key configuration,
server egress, and Gemini service were not globally unavailable. The generic
fallback then became terminal, incorrectly promised a manager, and created no
durable path back to the unanswered customer turn.

## Goals

1. Prefer the strongest production model for customer replies.
2. Keep all six configured keys useful without multiplying slow timeouts.
3. Preserve chat quota and latency ahead of background analysis.
4. Classify failures by key, project, model, request, and transport scope.
5. Persist redacted attempt evidence and provider delivery receipts.
6. Recover provider-outage turns safely without duplicate Meta sends.
7. Keep deep CRM analysis independent from the live reply SLA.

## Non-goals

- Migrating the whole integration from `generateContent` to another Gemini API
  during an active incident.
- Removing the full product catalog without product-accuracy evaluation.
- Claiming mathematical exactly-once delivery from Meta Send API, which has no
  application idempotency key.
- Sending synthetic customer or advertising events during verification.

## Model-quality policy

The live-chat quality chain is:

1. `gemini-3.6-flash` — authoritative primary.
2. `gemini-3.5-flash` — quality fallback after the strong phase is exhausted.
3. `gemini-3.5-flash-lite` — terminal low-latency emergency reserve.

Older 3.1/2.5 models are removed from the customer-chat chain. They may remain
in separately bounded background/checker flows where their capabilities are
explicitly required.

Ordinary conversational turns use low reasoning and a 1536-token output cap.
Product, size, payment, order, catalog, and media decisions retain high
reasoning and a 4096-token output cap. The selected task remains unchanged
when the scheduler falls back to another model.

## Six-key topology

| Tier | Aliases | Purpose |
|---|---|---|
| Hot chat | `GEMINI_API`, `GEMINI_API2` | Reserved for customer replies |
| Shared reserve | `GEMINI_API3`, `GEMINI_API4` | Deep analysis primary; borrowable by live chat |
| Last reserve | `GEMINI_API5`, `GEMINI_API6` | Checker/background reserve; borrowable by live chat |

Background work can never borrow the two hot-chat aliases or known aliases in
the same Google project. Live chat may borrow all six. Within a tier, selection
prefers an available unleased key, a not-yet-tried project, recent success,
lower latency EWMA, and finally stable alias order.

Gemini quotas are project-scoped. `GEMINI_KEY_PROJECT_GROUPS` remains the
authoritative non-secret alias-to-project mapping. Unknown identities are not
guessed and remain visibly flagged in diagnostics. Known siblings share quota
cooldowns and leases.

## Adaptive live scheduler

The live scheduler is separate from the longer-running management/checker
runner.

- Ordinary chat hard deadline: 35 seconds.
- Complex chat hard deadline: 45 seconds.
- A protected reserve is kept for at least one 3.5 fallback attempt.
- Each HTTP timeout is clipped to the remaining phase and global deadline.
- No exponential sleep occurs inside a live customer request.
- A call is not started when less than two usable seconds remain.

Failure routing:

| Failure | Scope and next action |
|---|---|
| `400` with `API_KEY_INVALID`, or `401` | Quarantine the key; remain on 3.6 and rotate immediately |
| `403 PERMISSION_DENIED` | Quarantine key/project; remain on 3.6 on another project |
| `429 RESOURCE_EXHAUSTED` | Apply provider retry metadata to the project/model quota; no live sleep |
| `404 NOT_FOUND` | Open model circuit; move to the next model |
| timeout, transport, `408`, `5xx` | One more 3.6 attempt on a distinct project, then degrade model |
| other `400 INVALID_ARGUMENT` | Fail the shared payload once; never repeat it on six keys |
| empty/MAX_TOKENS | One adapted attempt if budget permits, otherwise degrade model |
| safety block | Do not rotate keys; use the safe application path |

Fast key-specific failures may traverse all six aliases while preserving 3.6.
Slow model/transport failures are capped, because another API key does not fix
model latency and may consume the same project quota.

## Durable key and model state

`GeminiKeyState` gains a short lease, failure classification, HTTP status,
consecutive failures, and latency EWMA. A new `GeminiModelState` stores the
cross-process circuit state. Claim/release transactions are short and never
span provider I/O. Expired leases are reclaimable and a token mismatch cannot
release another worker's lease.

A redacted `GeminiRequestAttempt` row records request UUID, role, alias,
project group, model, outcome, provider status/reason, latency, remaining
deadline, and usage counters. It never stores prompts, provider bodies,
customer text, credentials, or raw responses.

## Durable customer recovery

A dedicated `IgAiReplyRecoveryJob` represents one recovery intent for one
failed inbound message. It is not an `IgFollowUpTask`: sales cadence,
discounting, and ordinary follow-up cancellation have different semantics.

Generic provider exhaustion sends a short localized holding response without a
false manager promise, persists the Meta message ID, and activates the recovery
job. Deterministic factual order/support fallbacks and genuine human handoffs do
not create automatic recovery.

Before generation and immediately before Meta send, recovery revalidates:

- global bot enablement;
- hidden, blocked, paused, takeover, and durable opt-out state;
- reply permission epochs and client automation lease;
- current funnel message floor;
- no newer inbound or manager reply;
- no existing substantive bot reply;
- response-window expiry;
- current ownership of the job lease.

The recovery draft is persisted before crossing the Meta boundary. A confirmed
provider message ID finalizes the reply without another request. A stale
`sending` job with no provider ID is terminal `ambiguous` and is sent to manual
review, never replayed. This provides one durable intent and at most one
automatic Meta request; it does not overstate the provider's guarantees.

The recovered text is one natural message in the customer's language: a brief
apology followed immediately by the substantive answer. It does not mention
Gemini, keys, AI, or internal errors. Recovery never executes stale irreversible
controls such as payment creation, order creation, or a new manager handoff.

## Delivery consistency

Normal and recovery sends request a `ProviderDeliveryReceipt`. A successful
model-history row stores `provider_message_id`, and `IgClient.last_bot_reply_at`
is updated in the same post-send transaction. HTTP 200 without a message ID is
treated as ambiguous rather than confirmed.

## Production rollout

1. Run schema checks and focused/related tests in the isolated worktree.
2. Probe all six aliases redacted against 3.6, 3.5 Flash, and Flash-Lite.
3. Fast-forward the approved commits into `main` and push `origin/main`.
4. On production: pull fast-forward, migrate, check, collect/compress static,
   restart Passenger, and ensure the Instagram daemon.
5. Confirm deployed SHA, migrations, daemon heartbeat, empty/expected queues,
   key/project/model states, and no unrequested customer sends.
6. Schedule the legacy incident by source message ID 2468 through the guarded
   recovery command.
7. Prove one provider-confirmed apology-plus-answer row and idempotent replay.
