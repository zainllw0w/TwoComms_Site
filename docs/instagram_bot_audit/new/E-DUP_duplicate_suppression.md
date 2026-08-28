# Э-DUP — Duplicate Reply and Media Suppression

**Status 2026-08-28 — closed. Production incident 28.08 reproduced and fixed.**

## Production incident 28.08

User asked "хочу футболку з Харковом" from their personal account at 19:40:58. Bot responded with 3 photos at 19:41:22, then sent identical text "Спасибо! Проверю это по системным данным и сразу уточню ответ 🙌" that exposed internal terminology and made an unfulfillable promise. User asked "что именно ты проверишь по системным данным?" at 19:41:45. Bot waited **6 minutes**, then at 19:48:02 sent the exact same 3 photos again, followed by the exact same text again at 19:48:05.

Root causes identified:

1. **Authority claim guard too aggressive.** User asked for Kharkiv t-shirts. Model listed matching products. Pattern matched `футболк... є` triggering stock authority claim. No specific variant selected yet (`_has_exact_stock_evidence` → False), so entire useful reply replaced with technical fallback message. When user asked what would be verified, same pattern matched again → same replacement text.

2. **Stale processing replay.** Daemon crashed or restarted mid-turn (≥100/day on production). Row hung in `PROCESSING` without `send_state`, reclaim_stale_processing returned it to pending after 300s timeout, entire turn ran again → same reply, same photos, 6 minutes later.

3. **Incomplete product presentation.** 10 Kharkiv items published (4 t-shirts), bot showed 3 photos. No indication more exist. Customer reads 3 as "це все".

4. **Technical message exposed internals.** Fallback text promised follow-up that never scheduled, mentioned "системні дані", discarded useful response entirely.

## Fixes applied

### A. Stock claim backed by catalog resolver

`_catalog_presentation_backs_stock_claim()`: listing assortment is **catalog presentation**, not operational stock claim. Catalog is our own authoritative data. After Э3.7 we have `ig_offer_resolver` giving status per product. Proof: mentioned products resolve to `in_stock` or `made_to_order`. Fail-closed preserved: if no products identified or resolver gives `unknown`/`unavailable` → no proof.

Authority guard now checks both exact evidence (variant+fit+size selected) and catalog presentation (products resolve to available states). Browse queries pass through; transactional claims still gated.

### B. Strip unproven sentences, keep useful reply

`_reply_without_unproven_claims()`: split reply into sentences, remove only those containing unproven claim patterns, keep rest. If substantive text remains (≥20 chars), append honest replacement per claim kind instead of generic technical phrase. If nothing substantive remains, honest clarification without exposing internals or making unfulfillable promises.

Replacements per locale:
- `payment`: "Оплату ще не бачу підтвердженою."
- `stock`: "Наявність цієї позиції зараз уточнюю."
- `order`: "Замовлення ще не оформлене."

No mention of "системні дані", no promise of follow-up that won't happen.

### C. Duplicate text suppression

`_recent_identical_reply_exists()`: check if same normalized text sent to this client within 15min window. Normalization: collapse whitespace, casefold. Last barrier before send—even if all higher guards allowed, duplicate looks like technical failure.

If detected, mark row `DONE` without sending, log `duplicate_reply_suppressed`.

### D. Duplicate media suppression

`_identical_media_recently_sent()`: check if same product set already delivered within 15min window. Compares normalized titles of `catalog_media` rows. If detected, skip media send, log `catalog_media_duplicate`.

### E. Stale processing won't replay answered turns

Before `reclaim_stale_processing` requeues a `PROCESSING` row, check if model reply with provider receipt already exists for this client after this inbound message. If so, mark `DONE` instead of requeue, log `stale_already_answered`. Turn already produced customer output—don't replay.

### F. Append "more products" hint

`_append_more_products_hint()`: if `selection.truncated_product_count > 0`, append sentence with catalog link. Without this, 3 photos read as "це все".

Locale-specific: "У нас є більше моделей із цим принтом — ось повна підбірка: {url}"

Applied **after** `_strip_customer_urls` so the hint link isn't stripped.

## What this does NOT fix

- **Latency**: 6-minute gap from daemon restart + stale timeout. Fix E prevents replay, but initial timeout remains. Separate work: reduce `STALE_PROCESSING_SECONDS` or improve daemon stability.
- **Typing during media**: Already correct—typing window calculated per text reply length after provider work. Production gap was from stale retry, not typing implementation.

## Tests

9 new tests in `tests_ig_duplicate_suppression`:
- Identical text within window → detected
- Normalized comparison (whitespace/case)
- Different text → not duplicate
- Old duplicate beyond window → not flagged
- Identical media set → detected
- Partial match → not flagged
- Unproven claim stripping preserves rest
- Fully stripped → honest fallback
- Multiple failures → replacement per kind appended
