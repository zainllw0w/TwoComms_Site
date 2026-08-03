# Nova Poshta Order Lifecycle Design

**Date:** 2026-08-03

## Goal

Restore reliable Nova Poshta order progression, make automatic waybill creation resilient to the confirmed `Description is not valid` provider rejection, remove duplicate order variant text, and make payment/Meta/Telegram side effects durable and idempotent.

## Evidence and constraints

- Production outage was caused by the Instagram cron installation replacing the existing `update_tracking_statuses` entry.
- The current legacy `TrackingDocument.getStatusDocuments` endpoint accepts at most 100 documents per request. A read-only production-contract check confirmed 100 succeeds and 101 returns error `20001401153`.
- The current project runs under shared Passenger workers without Celery/beat or a guaranteed Redis broker, so a management command guarded by `flock` remains the durable scheduler.
- Nova Post v1 Basic Tracking and webhooks require a separate JWT/onboarding contract. The current legacy API key is not assumed compatible, and official webhook retry timing is not specified. Polling therefore remains the source-of-truth reconciliation path until that contract is provisioned.

## Design

### Tracking

1. Use one legacy API request per chunk of up to 100 unique normalized TTNs, with one reusable HTTP session per command run.
2. Match provider responses by normalized TTN, never array position. Reordered, partial, duplicate, and unknown responses are handled explicitly.
3. Treat numeric provider codes as authoritative. Delivery success is exactly `{9, 10, 11}`; return/refusal/failure codes are never inferred from localized text.
4. Persist the numeric code, provider movement time, checked time, terminal time, failure count, and next eligible check time. Terminal rows and old shipments are removed from the polling queryset.
5. Poll active rows every five minutes, waiting/storage states every fifteen minutes, and use a bounded row limit. A failed batch never publishes a healthy heartbeat and the command exits nonzero.
6. After a new TTN is committed from the operator action, perform one best-effort immediate lookup. A lookup failure cannot roll back the saved waybill.
7. Keep repeated terminal-success handling idempotent: it may heal missing analytics markers, but cannot create a second internal Purchase or external Purchase event.

### Automatic waybill creation

1. Normalize user and generated descriptions before the first request.
2. If and only if `InternetDocument.save` returns the exact case-insensitive provider error `Description is not valid`, retry once with the canonical ASCII-safe Ukrainian fallback `Одяг`.
3. Never retry unrelated validation, authentication, network, or recipient errors. Surface a stable Ukrainian message to the operator.
4. Keep recipient creation and local order writes transactional; compensate a provider-created document if the local write fails.

### Order variants and UI

- Treat fit as a machine axis (`fit`, `посадка`, `крій`, `крой`) and suppress duplicate fit values for both `OrderItem` and `DropshipperOrderItem`.
- Page-level errors remain for invalid links, unavailable integration, and blocked actions. Form/API errors render directly before the submit control, with `role="alert"`, `aria-live="assertive"`, and the same placement for AJAX responses.

### Payment, Telegram, and Meta

1. A normal storefront order without an Instagram lifecycle event is `instagram_lifecycle=skipped`, not perpetually `pending`.
2. Telegram `already_sent` is a successful `sent` ledger state, so retries do not look failed.
3. Meta channel metadata reads the persisted `fb_conversions_api.event_id`, while the deterministic order event ID remains shared by browser Pixel (`eventID`) and CAPI (`event_id`).
4. Persist `purchase_event_time` before the network attempt. Retries reuse the original verified payment time.
5. The success page always allows the browser Pixel to send the deterministic Purchase ID even when CAPI already succeeded. Meta performs the intended Pixel/CAPI deduplication; local session storage still prevents ordinary reload spam.
6. Internal `UserAction(purchase)` and provider markers remain idempotent; no live test events are emitted.

## Deferred webhook adapter

When Nova Post provides a JWT and callback secret, add a verified webhook endpoint as a fast path, subscribe `creator` and `numbers`, and retain legacy batch polling as a reconciliation fallback. Webhook payloads are cumulative and not cryptographically signed by the documented contract, so callbacks must be authenticated with a required shared secret and deduplicated by numeric status/event time.

## Acceptance criteria

- Active orders are updated in bounded batch calls, terminal shipments stop polling, and a second clean reconciliation run is a no-op.
- Codes 9, 10, and 11 complete an order; localized text alone never completes it.
- Exact invalid-description rejection retries once with `Одяг`; unrelated errors make one provider attempt.
- Fit text appears once in Telegram/order displays; the waybill error is adjacent to the action and accessible.
- A normal paid order is not reprocessed forever; Telegram and Meta channel states are truthful; Pixel and CAPI share one deterministic Purchase ID.
- Focused tests, broader regression tests, Django checks, browser smoke tests, and live deployment evidence all pass.
