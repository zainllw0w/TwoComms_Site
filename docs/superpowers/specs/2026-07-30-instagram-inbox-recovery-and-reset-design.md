# Instagram Inbox Recovery and Funnel Reset Design

## Goal

Keep normal Instagram Direct handling webhook-first and immediate, while giving
an administrator a durable manual recovery action for missed conversations and
a safe per-client test reset. Hidden clients must consume no profile, history,
or Gemini work until explicitly restored.

## Agreed decisions

The requirements were supplied and repeatedly approved in the incident thread:

- webhooks remain the permanent primary ingress;
- there is no continuous full-conversation polling;
- recovery starts only from an explicit “Оновити всіх користувачів” action;
- the UI shows durable progress and survives reloads;
- each eligible conversation imports at most the latest 20 messages;
- recovered history is stored and analyzed but never mass-replied to;
- hidden clients remain in a separate list and are excluded before expensive
  provider or AI work;
- funnel reset preserves facts and history and clears only derived automation
  state.

## Approaches considered

### 1. Reuse the existing continuous polling switch

Rejected. `poll_ingest()` is coupled to reply eligibility and daemon cadence.
Leaving it enabled repeats unchanged Graph reads, creates a dangerous path for
historical auto-replies, and does not provide durable operator progress.

### 2. Run the entire refresh inside one HTTP request

Rejected. A full account refresh can exceed shared-host request deadlines,
cannot safely survive process restarts, and provides misleading browser-only
progress.

### 3. Durable database-backed recovery run

Selected. The button creates or returns one open run. The existing singleton
daemon processes short leased slices, persists progress after every slice, and
can resume after a restart. The browser polls only a local status endpoint.

## Credential and ingress contract

- `IG_INSTAGRAM_BOT`: Instagram User access token for `twocomms`.
- `IG_APP_SECRET`: Instagram Login app secret used by the live BotTG-IG
  webhook signature contract.
- `META_APP_SECRET`: parent DIRECT_BOT Meta secret for legacy OAuth and Meta
  compliance signed requests.
- `IG_BOT_VERIFY_TOKEN`: operator-generated callback verification token.

Process/cPanel variables are authoritative. `.env.production` fills only
missing values. Webhook POST remains fail-closed and accepts no access token as
an HMAC key.

## Durable manual refresh

Add `IgInboxRefreshRun` with one open run per provider owner:

- identity: provider owner, transport, open-slot uniqueness;
- lifecycle: `pending`, `running`, `cancel_requested`, `completed`, `failed`,
  `cancelled`;
- phase: `discovery`, `sync`, `analysis`, `finalize`;
- ownership: requester and request/start/finish/cancel timestamps;
- resume state: discovery cursor, bounded pending conversation IDs, current
  index;
- progress: discovered, eligible, hidden/excluded, synced, failed,
  messages-persisted, analyses-scheduled;
- worker safety: lease token, lease expiry, attempts, next attempt, bounded last
  error.

Only an administrator can start or cancel a run. A second start while a run is
open returns that run instead of creating another.

### Discovery

The daemon requests conversation IDs with participant and updated-time metadata
using bounded validated pagination. It persists enough state to resume and
never trusts provider pagination URLs outside the approved Graph host/version.

For Instagram Login, the sole external participant is resolved before message
history. If a matching local client is hidden, the conversation is counted as
excluded and no profile endpoint, message-history endpoint, media download, or
Gemini call occurs. Ambiguous participant envelopes fail closed.

### Conversation synchronization

For each eligible conversation, load exactly one provider-readable window with
at most the latest 20 messages. Normalize Instagram attachment envelopes and
persist rows idempotently by provider message ID.

Recovered messages use `source=manual_refresh` and are observed-only:

- customer rows are stored as `done`, not `pending`;
- manager and bot echoes are stored in their real roles;
- no reply queue row or Send API action is created;
- one coalesced conversation-analysis job is scheduled after the local
  transcript changes.

The run checks cancellation and lease ownership between Graph requests and DB
slices. Transient failures use bounded backoff; permission/configuration errors
remain visible and do not spin continuously.

## Hidden-client invariant

Hiding a client immediately:

- increments the reply-permission epoch;
- cancels pending follow-ups and unsent automation;
- invalidates pending analysis work;
- marks known conversation cursors excluded.

All schedulers, claims, refresh discovery, profile refresh, message sync, and
Gemini analysis re-check hidden state immediately before expensive work. An
analysis leased before the hide action must be invalidated before the provider
call. Unhiding removes only the hidden exclusion; it does not automatically
send or refresh. The next webhook or explicit manual refresh resumes normal
observation.

## Funnel/context reset

Add append-only `IgFunnelResetAudit` containing client, actor, unique
idempotency key, reason, policy version, before snapshot, after snapshot,
affected counts, and timestamp.

The API requires administrator JSON access, a reason, an idempotency key, and
an exact confirmation phrase. It locks the client and relevant open automation
inside `transaction.atomic()`. An active provider send with
`send_state=sending` returns `409` and changes nothing.

### Preserved facts

- all messages, raw events, processed-message dedupe and analysis snapshots;
- payment events/projections/reviews/decisions;
- orders, order attribution and order-link events;
- verified paid/order-created deals and commercial episodes;
- refund/exchange/post-sale cases;
- customer identity/profile/contact and ad/referral attribution;
- purchases, spend and verified conversion facts;
- opt-out, hidden status, manager takeover/pause and notification audit.

### Cleared derived state

- intent/readiness/objection/lost-reason predictions;
- current product, size, color, quantity and confidence;
- sales context and AI memory summary;
- discount rescue and follow-up state;
- delivery diagnostic fields and automation lease;
- pending follow-ups and unsent queue work;
- active unpaid commercial episode, closed with an append-only cancellation
  event;
- analysis job revision/watermark, rescheduled only when the client is neither
  hidden nor opted out.

The operational stage resets to the strongest immutable truth: verified paid,
order created, or completed fulfillment remains authoritative; otherwise the
client returns to `new`.

## UI

The bot page gains one primary recovery control:

- idle: “Оновити всіх користувачів”;
- running: animated progress with phase and counters;
- cancel requested: disabled pending-cancel state;
- completed: concise summary and completion time;
- failed: bounded error plus retry action.

The browser polls a local status endpoint with visibility-aware backoff. It
never calls Meta directly and refreshes the client list after completion.

Each client detail gains “Скинути воронку”. The confirmation dialog explains
what is preserved and cleared, requires the exact phrase, and returns the
updated client projection plus audit ID. Hidden and manager-takeover state stay
visibly unchanged.

## Testing and acceptance

- TDD for env precedence and separated secret sources.
- Model/lease/idempotency/cancel/restart tests for refresh runs.
- Hidden-before-profile/messages/Gemini tests, including hide-after-lease.
- Latest-20, attachment-envelope, duplicate-mid and observed-only tests.
- Reset preservation and clearing matrix, idempotency, `409` active-send and
  immutable paid/order/refund truth tests.
- API authorization/validation and UI state tests.
- Focused Instagram/Gemini/chat suites, Django check, migration drift,
  compilation, JavaScript syntax and diff checks.
- Production migrate/static/restart, daemon/DB/queue/outbox checks and deployed
  SHA proof.
- Final live proof: a fresh customer DM returns webhook `200`, creates one raw
  event and queue row, reaches Gemini once, Send API succeeds once, and the
  reply is visible in Instagram.
