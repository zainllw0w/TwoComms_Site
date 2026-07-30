# Instagram CRM reconciliation: 2026-07-30

## Root causes

- Historical inbox refresh classified every recovered message with operational side effects. Each receipt-bearing row could create a new payment review, episode, and Telegram alert.
- Empty receipt fingerprints fell back to a moving message watermark, so the same receipt was not stable across refresh pages.
- Post-sale detection missed the Ukrainian noun `заміни`; an older exchange could also be skipped after a newer projection and never become an immutable case.
- Bare `принт`, DTF vendor text, and a complaint about the wrong print were treated as custom-print requests.
- Gemini repeat intent was accepted from any user message ID and could move a paid client back to `qualifying`.
- The list card collapsed a real exchange/return into a generic manager-warning color, and stats had no explicit local date range.

## Implemented safeguards

- Historical refresh runs deterministic rules without payment-review or analysis side effects and schedules one bounded analysis job per conversation.
- Receipt fingerprints are stable without catalog context; terminal (`cancelled`/`superseded`) reviews cannot be reused as active reviews.
- Exchange/return cases are projected before mutable watermark checks and are shown independently from the paid/order stage.
- Custom print requires explicit manufacturing/design-change language, with support and collaboration precedence.
- Repeat intent requires explicit repeat wording and is rejected for exchange/return evidence.
- `historical_paid_archived` is an audited resolution for confirmed legacy full payments without a local `Order`; it never fabricates an order and resolves the duplicate manager alert.
- Client cards expose post-sale type/status, keep paid/order green, and include bounded episode message-role counts.
- Stats accept Europe/Kyiv `date_from`/`date_to` with an exclusive next-day boundary and reject malformed/reversed ranges.

## Production reconciliation checklist

1. Verify deployed SHA and migration `0116`/`0117` state before changing data.
2. Supersede duplicate reviews into their canonical review; cancel the false-positive review without receipt evidence.
3. Create the confirmed client's exchange case from the exact source message and known order; do not infer the original size.
4. Manager-verify the three historical canonical reviews with exact amounts, then archive them as `historical_paid_archived` without creating orders that are not in the orders database.
5. Run one bounded refresh and confirm: no duplicate Telegram alerts, no customer sends from history, hidden clients skipped, no MID conflicts, one analysis job per client.
6. Verify the separate assisted-checkout branch is merged without changing invoice/link lifecycle code.
