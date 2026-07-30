# Instagram Assisted Checkout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace new Instagram direct Monobank links with a secure, mobile-first TwoComms proposal that creates a standard PaymentAttempt and drives verified payment, TTN, delivery, and review lifecycle events.

**Architecture:** `IgCheckoutProposal` freezes the Instagram commercial configuration and exposes a 12-hour bearer-token entrance to a clean first-party checkout page. Valid recipient, email, promo, and signed Nova Poshta data atomically create one existing `PaymentAttempt`; verified materialization is then bound back to `IgDeal`, `IgClient`, the commercial episode, and attribution. Payment, TTN, and Nova Poshta delivery transitions create durable lifecycle events consumed by the existing bot transport under Meta policy.

**Tech Stack:** Django 5.2, MariaDB/InnoDB, server-rendered templates, isolated CSS/vanilla JS, existing Nova Poshta directory/signing services, Monobank Acquiring API, Meta Pixel/CAPI, Instagram Login messaging transport, Django test runner, Node source-contract tests, Playwright visual verification.

---

## Execution rules

- Primary agent performs all writes. Subagents are read-only researchers/reviewers.
- Work only in `/Users/zainllw0w/.config/superpowers/worktrees/site/instagram-assisted-checkout`.
- Preserve legacy direct IG invoices and unrelated worktrees.
- Use `apply_patch` for manual edits.
- Follow TDD: failing focused test, minimal implementation, passing focused test,
  related regression suite, commit.
- Never send live customer, Monobank, Meta, or TikTok test events.
- Do not mark a checklist item complete without evidence.

## Requirement-to-task traceability

| User outcome | Implementation owner | Acceptance evidence |
| --- | --- | --- |
| The bot detects concrete buying/payment intent and completes the happy path without a manager | Tasks 2, 10 | Intent, missing-option, one-item, multi-item, and no-manager-path tests |
| Product discovery prefers three or four real photos instead of link spam | Task 11 | Catalog selection and Instagram transport payload tests |
| T-shirts require explicit classic/oversize fit, valid size, color, and quantity | Tasks 2, 10 | Strict configuration and bot conversation tests |
| The bot sends a first-party TwoComms proposal, never a new direct Monobank URL | Tasks 3, 8, 10 | URL, legacy compatibility, and provider-call boundary tests |
| The proposal lasts 12 hours, is forwardable, and can be paid by another browser | Tasks 3, 6, 8 | Token, grant, forwarded-browser, and first-submit-wins tests |
| Item changes happen through Direct on the same pre-invoice proposal | Tasks 2, 8, 10 | Revision, stale-page, cancellation, and supersession race tests |
| The page shows immutable product facts and collects required receipt email and Nova Poshta data | Tasks 4, 5, 6 | Render, form, signed-directory, accessibility, and visual tests |
| Promo is optional and does not silently stack with a negotiated discount | Tasks 2, 6 | Quote and promo eligibility tests |
| Monobank is created only after valid customer confirmation through the standard PaymentAttempt path | Tasks 7, 8 | PaymentAttempt, amount, idempotency, return, and webhook tests |
| Verified payment creates one Order and binds client, deal, episode, and attribution | Task 9 | Adapter, partial-crash, and reconciler tests |
| Checkout and Purchase analytics are deduplicated and Purchase occurs only after verified payment | Task 12 | Pixel/CAPI timing, event ID, value, and no-network serialization tests |
| A verified payment sends the deterministic Direct confirmation | Tasks 13, 14 | Lifecycle lease and payment-message tests |
| First committed TTN sends the number and official tracking URL independently of Telegram | Tasks 13, 15 | Transaction, duplicate-save, Telegram-failure, and Meta delivery tests |
| Canonical Nova Poshta delivery requests an honest review/tag | Tasks 13, 16 | Status-code, idempotency, opt-out, copy, and window-fallback tests |
| Management can see proposals awaiting payment without becoming part of the happy path | Task 17 | API, permission, masking, action, and responsive UI tests |
| Expiry, crashes, daemon restarts, and missed events recover safely | Tasks 13, 18 | Lease reclaim, bounded replay, dry-run, and idempotent rerun tests |
| Mobile visual quality is verified on real catalog imagery and all relevant states | Tasks 4, 5, 19 | Playwright screenshots, pixel checks, overflow, keyboard, and reduced-motion evidence |
| Deployment does not overwrite parallel agent work and is proven on production | Tasks 0, 20 | Rebase audit, migration graph, deployed SHA, runtime, table, route, and marker proof |

## Original brief reconciliation

The re-pasted source brief is the acceptance authority. This table records the
small details that are easy to lose during context changes.

| Source-brief clause | Locked interpretation | Owner and proof |
| --- | --- | --- |
| Do not send the user straight to Monobank checkout | New bot flow emits only a TwoComms own-domain proposal URL; legacy `IGDEAL-*` remains compatible but is never selected for a new proposal | Tasks 8 and 10; provider-call boundary and legacy webhook tests |
| The page is not the normal cart | Proposal page renders a frozen item snapshot and payment form directly; it never depends on browser cart/session state | Tasks 1, 4, 8; forwarded-browser and clean-page tests |
| Bot understands one or many products | One normalized item-list path handles one shirt, two shirts, hoodies, and bounded long lists | Task 2; one/multi-item tests |
| Bot must ask T-shirt fit and then size guide | Classic/oversize fit is mandatory when applicable, followed by the valid product size grid; no default inference | Tasks 2 and 10; missing-fit/size/conversation tests |
| Show selected color, fit, size, quantity, and exact agreed amount | Current revision snapshots all commercial facts and shows them before delivery fields | Tasks 1 and 4; template/security tests |
| Collect recipient, phone, first/last name, Nova Poshta, and email for receipt | Required normalized recipient form uses signed city/warehouse selectors and `orders.email_receipt` after verified payment | Task 6 and Task 7; form, receipt-email, and signed-token tests |
| User checks the proposal and presses one payment action | No redundant final bot confirmation; page CTA creates/reuses one standard PaymentAttempt only after valid submit | Tasks 6 and 8; duplicate-submit/concurrency tests |
| Promo code may be entered | Promo disclosure is optional, guest eligibility is explicit, negotiated discounts do not stack silently, and usage is reserved atomically | Tasks 2, 6, and 8; promo reservation tests |
| Link is unique, lasts about 12 hours, can be forwarded/copied | 256-bit token, clean URL grant, separate share token, independent payer browser, expiry state, and copy action | Task 3; token/forwarding/browser tests |
| Changes are requested in Direct | Before invoice the same proposal revision advances; after invoice only provider-confirmed cancellation permits a replacement | Tasks 2, 8, and 10; revision/supersession race tests |
| Payment result is visible and thank-you is shown only after real payment | Return page remains pending until server-side provider verification; verified Order enables thank-you and Purchase | Task 12; return/webhook/analytics tests |
| Instagram client and order must stay linked | Adapter binds Order, `IgDeal`, `IgClient`, commercial episode, `IgOrderAttribution`, and proposal idempotently | Task 9; partial-crash/replay tests |
| Telegram alert and Instagram message both happen | One committed domain event feeds independent Telegram and Instagram channels; Telegram is never the trigger and one channel cannot clear another | Tasks 0, 13, and 18; channel-outbox/recovery tests |
| TTN is sent when first created or inserted | First committed non-empty tracking transition emits `ttn_created` with official Nova Poshta URL, independent of `status=ship` and Telegram success | Task 15; transition/duplicate-save tests |
| Delivery pickup triggers a final review request | Canonical Nova Poshta delivered status after committed `done` emits one review/tag request, with Meta-window manager fallback | Task 16; status-code/idempotency/window tests |
| Page must be beautiful, mobile-first, light, and animated without overload | Real product imagery, compact facts, stable dimensions, restrained one-time motion, reduced-motion support, no visual clutter or nested card grid | Tasks 4, 5, and 19; Playwright screenshots/pixel/overflow tests |
| Bot should send catalog photos instead of unnecessary product links | Prefer 3-4 trusted catalog images/carousel; use links only when explicitly useful or requested | Task 11; media payload tests |
| Manager should not participate in the normal purchase path | Manager workspace is observability/recovery only; happy path is bot → proposal → PaymentAttempt → Order → lifecycle worker | Tasks 10, 13, and 17; no-manager-path tests |
| Production DB and bot may change during implementation | Task 0 waits for final integration SHA, allocates migrations from the rebased graph, and every later task rechecks overlap before commit/deploy | Tasks 0 and 20; rebase/migration/deployed-SHA proof |

## Canonical lifecycle trigger contract

Do not call a local HTTP webhook and do not use the Telegram alert as an
Instagram trigger. The owning transaction writes business truth; after commit,
an internal service creates one durable `IgLifecycleEvent`. Telegram and
Instagram then consume the same committed fact independently.

```text
verified PaymentAttempt materializes Order
  -> on_commit bind Order to proposal/deal/client/episode/attribution
  -> event key payment:<attempt_id>:verified
  -> Instagram payment confirmation worker

first empty -> non-empty Order tracking number transition
  -> on_commit event key ttn:<order_id>:<tracking_digest>
  -> Telegram operational notification (independent)
  -> Instagram TTN worker (independent)

Nova Poshta canonical delivered StatusCode committed to Order
  -> on_commit event key delivered:<order_id>:<status_code>
  -> existing Telegram/status reporting (independent)
  -> Instagram review-request worker (independent)
```

Every event stores the exact Order, `IgClient`, `IgDeal`, proposal, commercial
episode, attribution context, locale, minimal payload, lease, delivery state,
provider message ID, and error evidence. Inside Meta's conservative response
window the worker sends an ordinary automated response. Outside it, the worker
creates one deduplicated manager task plus one operational Telegram alert;
automated `HUMAN_AGENT` is prohibited. A bounded reconciler recreates missing
events from persisted order/payment/shipment truth after crashes.

### Task 0: Rebase, resolve integration blockers, and establish a green baseline

**Files:**
- Inspect only: `/private/tmp/twocomms-ig-verify.dIoXh3`
- Diagnose ownership in: `twocomms/storefront/views/utils.py`
- Preserve/strengthen assertions in: `twocomms/storefront/tests/test_monobank_webhook.py`
- Update: `docs/plans/2026-07-30-instagram-assisted-checkout-research.md`

- [x] **Step 1: Inspect integration state**

Run:

```bash
git fetch origin main
git log --oneline --decorate -8 origin/main
git -C /private/tmp/twocomms-ig-verify.dIoXh3 status --short --branch
git -C /private/tmp/twocomms-ig-verify.dIoXh3 diff --name-only
```

Expected: exact current integration SHA and explicit list of overlapping files.
Do not begin migrations or edit overlapping Instagram files until the parallel
agent has either supplied its commit SHA for integration or explicitly confirmed
that its uncommitted work is out of scope. Record that decision in the research
document and re-run the migration graph check afterward.

- [x] **Step 2: Rebase safely**

Run:

```bash
git rebase origin/main
```

Expected: clean rebase or explicit conflicts limited to this feature's future
surface. Resolve by understanding both versions; do not restore stale files.

- [x] **Step 3: Reproduce the two baseline failures**

Run:

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  storefront.tests.test_monobank_webhook.PostPaymentEventsDeferralTests -v 2
```

Expected before fix: two callback-count failures (`2 != 1`).

- [x] **Step 4: Fix the callback boundary, not the assertion**

Ensure one post-commit dispatcher records durable pending markers for each
required side effect before any external work. Keep the DB write inside the
transaction and schedule one dispatcher that only claims those markers:

```python
if payment_became_verified:
    transaction.on_commit(
        lambda order_id=order.pk: enqueue_verified_payment_side_effects(order_id)
    )
```

Persist separate lease/idempotency markers for Telegram, receipt email, CAPI
Purchase, browser-success eligibility, and the Instagram lifecycle event.
The request-owned daemon thread must not be the only retry path. A bounded
reconciler must keep a row pending until every mandatory marker is confirmed or
classified as permanently unavailable. Do not weaken the tests to accept
duplicate callbacks.

- [x] **Step 5: Run the baseline suite**

Run:

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py check
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_paylink_fix management.tests_ig_shipment \
  orders.tests.test_payment_attempts storefront.tests.test_monobank_webhook -v 1
```

Expected: 74 tests pass, zero failures.

- [ ] **Step 6: Commit**

```bash
git add twocomms/storefront/views/utils.py \
  twocomms/storefront/tests/test_monobank_webhook.py \
  docs/plans/2026-07-30-instagram-assisted-checkout-research.md
git commit -m "fix: restore single post-payment dispatch boundary"
```

### Task 1: Add proposal, revision, token, and lifecycle models

**Files:**
- Modify: `twocomms/management/ig_bot_models.py`
- Modify: `twocomms/management/models.py`
- Create: one migration in `twocomms/management/migrations/`, named by
  `makemigrations` from the final rebased migration graph
- Test: `twocomms/management/tests_ig_checkout_models.py`

- [x] **Step 1: Write failing model tests**

Create `IgCheckoutProposalModelTests` with these exact contracts:

- `test_active_proposal_has_positive_total_and_future_expiry` rejects zero or
  negative totals and non-future expiry for an active proposal;
- `test_revision_is_append_only` rejects update/delete of an existing revision;
- `test_access_token_stores_digest_not_raw_token` proves the raw token appears
  in no persisted token field;
- `test_lifecycle_event_key_is_unique` creates the same event key twice and
  expects the database uniqueness constraint;
- `test_paid_proposal_cannot_be_superseded` locks a paid proposal and proves no
  replacement relationship can be written;
- `test_deal_retains_historical_proposals_with_one_active_pointer` proves one
  deal can retain multiple immutable proposals but exactly one current pointer;
- `test_concurrent_replacement_creation_serializes_on_deal` proves two workers
  cannot create two current replacements;
- `test_confirmed_cancelled_invoice_can_be_replaced` proves the provider-cancel
  gate, while an ambiguous invoice remains non-replaceable;
- `test_archiving_client_or_deal_cannot_cascade_financial_evidence` proves the
  protected retention policy;
- `test_invoice_proposal_requires_episode_and_lifecycle_attribution` proves a
  proposal stores the exact `ensure_episode_for_deal()` result and every
  order-bound lifecycle event stores the exact `IgOrderAttribution`.

Run:

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_models -v 2
```

Expected: import/model failures.

- [x] **Step 2: Add model choices and fields**

Use explicit choices and indexes:

```python
class IgCheckoutProposal(models.Model):
    class Status(models.TextChoices):
        READY = "ready", _("Ready")
        VIEWED = "viewed", _("Viewed")
        DETAILS_LOCKED = "details_locked", _("Details locked")
        INVOICE_CREATED = "invoice_created", _("Invoice created")
        PAID = "paid", _("Paid")
        CANCELLED = "cancelled", _("Cancelled")
        EXPIRED = "expired", _("Expired")
        REVOKED = "revoked", _("Revoked")
        SUPERSEDED = "superseded", _("Superseded")

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    client = models.ForeignKey("management.IgClient", on_delete=models.PROTECT)
    deal = models.ForeignKey(
        "management.IgDeal",
        on_delete=models.PROTECT,
        related_name="checkout_proposals",
    )
    commercial_episode = models.ForeignKey(
        "management.IgCommercialEpisode",
        on_delete=models.PROTECT,
        related_name="checkout_proposals",
    )
    revision = models.PositiveIntegerField(default=1)
    quoted_total = models.DecimalField(max_digits=12, decimal_places=2)
    expires_at = models.DateTimeField(db_index=True)
    payment_attempt = models.OneToOneField(
        "orders.PaymentAttempt", null=True, blank=True, on_delete=models.SET_NULL
    )
```

Add these complete related records and constraints:

- `IgCheckoutProposal.deal`: protected foreign key so one deal retains multiple
  historical/replacement proposals. Add nullable
  `IgDeal.active_checkout_proposal` as the current OneToOne pointer. Proposal
  creation locks the `IgDeal`, supersedes/cancels its old current proposal,
  creates the replacement, and updates the pointer in one transaction. Do not
  rely on a conditional partial unique constraint because production MariaDB
  cannot enforce the required Django conditional-unique behavior;
- `IgCheckoutProposalItem`: proposal/product/color-variant relations plus
  immutable title, SKU, image, color, size, fit, option, quantity, catalog price,
  quoted price, price-source, evidence-message, and ordering snapshots;
- `IgCheckoutRevision`: proposal, revision number, digest, PII-free item/price
  JSON, source, evidence IDs, source watermark, and created timestamp, unique on
  proposal plus revision;
- `IgCheckoutAccessToken`: proposal, SHA-256 digest, kind, expiry/revocation,
  use count, and last-used timestamp; never store raw tokens;
- `IgCheckoutInventoryReservation`: proposal/item/product/variant, quantity,
  reservation fingerprint, active/released/consumed state, expiry, release reason,
  and timestamps; reservation starts only when invoice creation is owned, never
  for the full unconfirmed proposal lifetime;
- `IgLifecycleEvent`: unique key, kind, client/deal/proposal/order/episode,
  attribution, locale, PII-minimal payload, state, due time, attempts, lease
  token/expiry, provider message ID, last error, and completion timestamps;
- database constraints for positive totals/quantities, unique current proposal
  pointer, unique proposal revision, unique token digest, and unique event key;
  use `PROTECT` for client/deal/episode relations so financial evidence remains
  queryable after a profile is archived.

- [x] **Step 3: Generate and inspect migration**

Run:

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py makemigrations management
git diff -- twocomms/management/migrations/
```

Expected: dependency on the actual rebased migration graph; no collision with
another agent's migration and no unsafe engine assumption.

- [x] **Step 4: Run tests and migration drift**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_models -v 2
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py makemigrations --check --dry-run
```

Expected: pass; no pending migrations.

- [ ] **Step 5: Commit**

```bash
git add twocomms/management/ig_bot_models.py twocomms/management/models.py \
  twocomms/management/migrations/ \
  twocomms/management/tests_ig_checkout_models.py
git commit -m "feat: add Instagram checkout proposal lifecycle"
```

### Task 2: Build the strict proposal configuration service

**Files:**
- Create: `twocomms/management/services/ig_checkout.py`
- Modify: `twocomms/management/services/bot_orders.py`
- Reuse: `twocomms/management/services/ig_commercial_episodes.py`
- Test: `twocomms/management/tests_ig_checkout_service.py`
- Modify: `twocomms/management/tests_bot_orders.py`

- [ ] **Step 1: Write failing strict-validation tests**

Add cases for missing size, missing fit, missing required color, wrong variant,
inactive fit, invalid size, unpublished product, stock failure, multi-item,
negotiated aggregate discount, and identical replay.

```python
def test_tshirt_requires_fit_size_and_color(self):
    with self.assertRaises(CheckoutConfigurationError) as ctx:
        build_proposal(self.client, items=[{"product_id": self.shirt.pk, "qty": 1}])
    self.assertEqual(ctx.exception.missing_fields, {"size", "fit", "color"})
```

- [ ] **Step 2: Run tests to verify failure**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_service management.tests_bot_orders -v 2
```

Expected: missing service and current single-item gaps.

- [ ] **Step 3: Implement one item normalizer and validator**

Public contracts:

- `validate_checkout_items(*, client, item_specs, evidence) -> ValidatedQuote`
  normalizes the one-item and multi-item paths and returns only fully sellable
  immutable item snapshots plus catalog/negotiated totals;
- `create_or_update_proposal(*, client, pay_type, item_specs,
  negotiated_total=None, requested_payment_amount=None) -> IgCheckoutProposal`
  row-locks the active deal/proposal, appends a PII-free revision, replaces the
  current item snapshot atomically before invoice creation, and refuses mutation
  after an invoice can accept money.

Within the same deal lock, synchronize the authoritative commercial snapshot:

- update `IgDeal.pay_type`, `amount`, `requested_payment_amount`, status, and
  evidence fields from the validated quote;
- replace `IgDealItem` rows from the same normalized item snapshots used by the
  proposal, including fit/size/color/options/prices/evidence;
- call `ensure_episode_for_deal(deal)` after the deal/items write and store that
  exact episode on `IgCheckoutProposal.commercial_episode`;
- assert `payment_truth_snapshot()`, attribution item provenance, proposal
  items, deal items, and the episode product snapshot all describe the same
  revision/digest.

Add rollback and concurrent-revision tests so proposal and deal/items can never
commit different commercial contracts.

Internally reuse:

- `resolve_product_sizes()`
- `ProductFitOption`
- `variant_allows_purchase()`
- `effective_cart_unit_price()`
- existing evidence-bound price/prepayment validators

The validator must distinguish availability revalidation from price mutation:
the current revision keeps its frozen quoted unit/line totals until expiry. If
catalog price, negotiated evidence, product publication, variant ownership, or
sellable stock no longer matches, return a stale-quote error and require a new
Direct revision. Never silently recalculate a buyer-approved total during form
submit.

Delete no legacy direct-invoice code. Route only new proposal calls to this
service.

- [ ] **Step 4: Run focused and related tests**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_service management.tests_bot_orders \
  management.tests_ig_current_product -v 1
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add twocomms/management/services/ig_checkout.py \
  twocomms/management/services/bot_orders.py \
  twocomms/management/tests_ig_checkout_service.py \
  twocomms/management/tests_bot_orders.py
git commit -m "feat: validate Instagram checkout configurations"
```

### Task 3: Add access-token handshake and secure proposal grants

**Files:**
- Modify: `twocomms/management/services/ig_checkout.py`
- Create: `twocomms/storefront/views/instagram_checkout.py`
- Modify: `twocomms/storefront/views/__init__.py`
- Modify: `twocomms/storefront/urls.py`
- Modify: `twocomms/twocomms/settings.py` or the established request-rate-limit
  module used by this checkout
- Test: `twocomms/storefront/tests/test_instagram_checkout_access.py`

- [ ] **Step 1: Write failing access tests**

Cover valid token redirect, malformed token, expired token, revoked token,
token-free clean URL, independent forwarded session, grant expiry, share-token
CSRF, and headers.

```python
response = self.client.get(reverse("instagram_checkout_access", args=[raw_token]))
self.assertRedirects(response, reverse("instagram_checkout", args=[proposal.public_id]))
self.assertNotIn(raw_token, response["Location"])
```

- [ ] **Step 2: Run to verify failure**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  storefront.tests.test_instagram_checkout_access -v 2
```

Expected: missing routes/services.

- [ ] **Step 3: Implement token issue/consume helpers**

```python
def issue_access_token(proposal, *, kind, expires_at=None) -> str:
    raw = secrets.token_urlsafe(32)
    IgCheckoutAccessToken.objects.create(
        proposal=proposal,
        digest=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        kind=kind,
        expires_at=expires_at or proposal.expires_at,
    )
    return raw

def consume_access_token(raw_token, *, now=None) -> IgCheckoutProposal:
    now = now or timezone.now()
    digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    token = IgCheckoutAccessToken.objects.select_related("proposal").get(
        digest=digest,
        revoked_at__isnull=True,
        expires_at__gt=now,
    )
    proposal = token.proposal
    if proposal.expires_at <= now or proposal.status not in {
        proposal.Status.READY,
        proposal.Status.VIEWED,
        proposal.Status.DETAILS_LOCKED,
        proposal.Status.INVOICE_CREATED,
        proposal.Status.PAID,
    }:
        raise InvalidCheckoutAccess
    IgCheckoutAccessToken.objects.filter(pk=token.pk).update(
        use_count=F("use_count") + 1,
        last_used_at=now,
    )
    return proposal
```

Use constant-time comparison/query by digest, bounded use metadata, and signed
session grant containing proposal ID/revision/expiry.

- [ ] **Step 4: Implement routes and headers**

Create:

```text
/offer/a/<token>/                 token entrance
/offer/<uuid:public_id>/          clean page
/offer/<uuid:public_id>/share/    POST token issue
```

Set `no-store`, robots, and no-referrer headers on all proposal responses.
Apply bounded rate limits by IP, proposal ID, token digest, share endpoint, and
invoice-submit endpoint. Configure the proxy/access-log layer to omit or
normalize the bearer path before logging; Django application logs must record a
request correlation ID and proposal public ID, never the raw token. Verify this
with a captured test log line, not only a response-header assertion.

- [ ] **Step 5: Run tests and commit**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  storefront.tests.test_instagram_checkout_access -v 2
git add twocomms/management/services/ig_checkout.py \
  twocomms/storefront/views/instagram_checkout.py \
  twocomms/storefront/views/__init__.py twocomms/storefront/urls.py \
  twocomms/storefront/tests/test_instagram_checkout_access.py
git commit -m "feat: add secure Instagram proposal access"
```

### Task 4: Render proposal states and the delivery form

**Files:**
- Create: `twocomms/twocomms_django_theme/templates/pages/instagram_checkout.html`
- Create: `twocomms/twocomms_django_theme/templates/pages/instagram_checkout_success.html`
- Modify: `twocomms/storefront/views/instagram_checkout.py`
- Test: `twocomms/storefront/tests/test_instagram_checkout_view.py`
- Test: `tests/test_instagram_checkout_template_source.py`

- [ ] **Step 1: Write failing render/security tests**

Assert real product facts, no Instagram username/chat PII, masked locked state,
locale, expiry, pending, paid, expired, superseded, image fallback, form labels,
and absence of token in template context/source.

- [ ] **Step 2: Run tests to verify failure**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  storefront.tests.test_instagram_checkout_view -v 2
python -m unittest tests.test_instagram_checkout_template_source -v
```

- [ ] **Step 3: Implement state view models**

Keep templates simple by returning a structured state:

```python
context = {
    "proposal": proposal_public_context(proposal, request=request),
    "state": proposal.status,
    "items": proposal_item_context(proposal),
    "delivery_locked": bool(proposal.details_locked_at),
    "masked_delivery": masked_delivery_context(proposal.payment_attempt),
}
```

Render no raw token and no unmasked PII after lock.

- [ ] **Step 4: Add semantic HTML**

Use real form labels, `autocomplete`, `inputmode`, field error associations,
stable image dimensions, accessible share/Direct actions, and server-rendered
states. Keep the checkout itself on the first screen; no marketing landing hero.

- [ ] **Step 5: Run tests and commit**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  storefront.tests.test_instagram_checkout_view -v 2
python -m unittest tests.test_instagram_checkout_template_source -v
git add twocomms/twocomms_django_theme/templates/pages/instagram_checkout*.html \
  twocomms/storefront/views/instagram_checkout.py \
  twocomms/storefront/tests/test_instagram_checkout_view.py \
  tests/test_instagram_checkout_template_source.py
git commit -m "feat: render Instagram checkout proposal states"
```

### Task 5: Implement the mobile-first visual system and interactions

**Files:**
- Create: `twocomms/twocomms_django_theme/static/css/instagram-checkout.css`
- Create: `twocomms/twocomms_django_theme/static/js/instagram-checkout.js`
- Reuse: `twocomms/twocomms_django_theme/static/js/modules/nova-poshta-form-bridge.js`
- Modify: `twocomms/twocomms_django_theme/templates/pages/instagram_checkout.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/instagram_checkout_success.html`
- Test: `tests/instagram-checkout-ui-contract.test.cjs`

- [ ] **Step 1: Write failing source/UI contract tests**

Assert explicit aspect ratios, 320 px no-overflow constraints, reduced-motion,
stable CTA height, no gradients/orbs/infinite animations, clean token-free share
request, visibility revision refresh, and accessible selectors.

- [ ] **Step 2: Run to verify failure**

```bash
node --test tests/instagram-checkout-ui-contract.test.cjs
```

Expected: missing assets/contracts.

- [ ] **Step 3: Add CSS**

Implement:

- 320-560 px primary column;
- 1040 px desktop grid at 42/58;
- near-black frame, light form surface, orange CTA, verified green;
- stable 4:5 media and compact product facts;
- sticky mobile total/CTA;
- visible focus and 44 px targets;
- reduced-motion override.

Do not modify global cart CSS unless an existing shared Nova Poshta selector
requires a narrowly scoped compatibility rule.

- [ ] **Step 4: Add JavaScript**

Implement progressive enhancement only:

```javascript
// share token request, copy confirmation, countdown, stable submit loading,
// Nova Poshta bridge initialization, revision refresh on visibilitychange,
// bounded pending-payment polling
```

No framework, token logging, uncontrolled polling, or layout-changing text.

- [ ] **Step 5: Run tests and commit**

```bash
node --test tests/instagram-checkout-ui-contract.test.cjs
git add twocomms/twocomms_django_theme/static/css/instagram-checkout.css \
  twocomms/twocomms_django_theme/static/js/instagram-checkout.js \
  twocomms/twocomms_django_theme/templates/pages/instagram_checkout*.html \
  tests/instagram-checkout-ui-contract.test.cjs
git commit -m "feat: style mobile Instagram checkout"
```

### Task 6: Validate Nova Poshta delivery, email, promo, and recipient locking

**Files:**
- Modify: `twocomms/storefront/views/instagram_checkout.py`
- Modify: `twocomms/management/services/ig_checkout.py`
- Reuse: `twocomms/orders/nova_poshta_checkout.py`
- Reuse: `twocomms/storefront/views/cart.py`
- Modify: `twocomms/storefront/models.py`
- Create: one `PromoCodeReservation` migration in
  `twocomms/storefront/migrations/`, named from the final rebased graph
- Modify: `twocomms/twocomms_django_theme/static/js/modules/nova-poshta-selector.js`
  only to expose the existing signed selection adapter to this isolated page
- Reuse and initialize: `twocomms/twocomms_django_theme/static/js/modules/nova-poshta-form-bridge.js`
- Test: `twocomms/storefront/tests/test_instagram_checkout_form.py`
- Modify: `twocomms/storefront/tests/test_nova_poshta_checkout_validation.py`

- [ ] **Step 1: Write failing form tests**

Cover phone/email normalization, missing email, unsigned city/warehouse, branch
versus post-locker, stale revision, expired proposal, promo eligibility,
negotiated-promo stacking rejection, first-submit-wins, and masked reopen. The
bridge and browser contract must also cover mocked city/warehouse responses,
keyboard selection, branch/locker switching, signed hidden selection tokens,
stale-token rejection, and wrong-city warehouse rejection.

- [ ] **Step 2: Run to verify failure**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  storefront.tests.test_instagram_checkout_form \
  storefront.tests.test_nova_poshta_checkout_validation -v 2
```

- [ ] **Step 3: Implement one atomic validation boundary**

```python
@transaction.atomic
def lock_delivery_and_prepare_attempt(proposal_id, *, revision, grant, form,
                                      request) -> PaymentAttempt:
    proposal = IgCheckoutProposal.objects.select_for_update().get(pk=proposal_id)
    validate_proposal_mutable(proposal, revision=revision, grant=grant)
    delivery = resolve_delivery_selection(form)
    quote = revalidate_current_quote(proposal, promo_code=form.get("promo_code"))
    return create_or_reuse_attempt(proposal, delivery=delivery, quote=quote,
                                   request=request)
```

Store PII only in PaymentAttempt. The proposal stores timestamps/status, not raw
recipient fields.
Persist `promo_code`, guest eligibility, and an atomic usage reservation on the
attempt. An anonymous payer may use only a currently valid promo with
`one_time_per_user=False` and no account-scoped group restriction. Never fall
back from `can_be_used_by_user()` to unrestricted `can_be_used()` for an
account-scoped code. Broader guest redemption requires an explicit persisted
PromoCode policy flag.

`PromoCodeReservation` links promo, proposal, PaymentAttempt, expiry, and
`reserved/consumed/released` state, unique per attempt. Under a `PromoCode` row
lock require `current_uses + active_unexpired_reservations < max_uses` for
limited codes. Consume once after verified Order materialization; release only
after definite invoice cancellation/expiry/failure. Reconciliation pulls
provider status before releasing stale reservations. Add a two-worker test for
one remaining use and prove only one invoice receives the discount.

- [ ] **Step 4: Run tests and commit**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  storefront.tests.test_instagram_checkout_form \
  storefront.tests.test_nova_poshta_checkout_validation -v 1
git add twocomms/storefront/views/instagram_checkout.py \
  twocomms/management/services/ig_checkout.py \
  twocomms/storefront/models.py twocomms/storefront/migrations/ \
  twocomms/twocomms_django_theme/static/js/modules/nova-poshta-selector.js \
  twocomms/storefront/tests/test_instagram_checkout_form.py \
  twocomms/storefront/tests/test_nova_poshta_checkout_validation.py
git commit -m "feat: validate Instagram checkout delivery"
```

### Task 7: Extend PaymentAttempt for evidence-bound prepayment

**Files:**
- Modify: `twocomms/accounts/payment.py`
- Modify: `twocomms/orders/models.py`
- Create: one migration in `twocomms/orders/migrations/`, named by
  `makemigrations` from the final rebased migration graph
- Modify: `twocomms/orders/payment_attempts.py`
- Modify: `twocomms/storefront/views/monobank.py`
- Modify: `twocomms/orders/telegram_notifications.py`
- Modify: `twocomms/orders/email_receipt.py`
- Modify: `twocomms/orders/tests/test_payment_attempts.py`
- Modify: `twocomms/storefront/tests/test_payment_contract.py`

- [ ] **Step 1: Write failing prepayment tests**

```python
def test_generic_prepayment_materializes_prepaid_order_with_full_value(self):
    attempt = make_attempt(
        pay_type=PaymentAttempt.PayType.PREPAYMENT,
        payable_amount=Decimal("1800.00"),
        payment_amount=Decimal("500.00"),
    )
    order, created = materialize_payment_attempt(
        attempt.pk, status="success", payload={"amount": 50000}
    )
    self.assertTrue(created)
    self.assertEqual(order.payment_status, "prepaid")
    self.assertEqual(order.total_sum - order.discount_amount, Decimal("1800.00"))
    self.assertEqual(order.payment_payload["paid_value"], "500")
    self.assertEqual(order.get_prepayment_amount(), Decimal("500.00"))
```

Also assert no Lead, exactly one Purchase at full discounted value 1800, one
receipt email with the requested customer email, correct Telegram payment label,
and a remaining balance of 1300. Test the legacy `prepay_200` path separately.

- [ ] **Step 2: Run to verify failure**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  orders.tests.test_payment_attempts storefront.tests.test_payment_contract -v 2
```

- [ ] **Step 3: Add choice and shared semantic helpers**

```python
class PayType(models.TextChoices):
    ONLINE_FULL = "online_full", _("Online full payment")
    PREPAYMENT = "prepayment", _("Evidence-bound prepayment")
    PREPAY_200 = "prepay_200", _("Legacy prepayment 200")

def is_prepayment(pay_type):
    return pay_type in {PaymentAttempt.PayType.PREPAYMENT,
                        PaymentAttempt.PayType.PREPAY_200}
```

Use it in `accounts/payment.py` normalization, `Order.get_prepayment_amount`,
PaymentAttempt materialization, analytics routing, receipt copy, Telegram labels,
admin totals, and amount reconciliation. Unknown values must fail closed rather
than silently becoming `online_full`; keep legacy 200 behavior explicitly.

- [ ] **Step 4: Run tests/migration drift and commit**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  orders.tests.test_payment_attempts storefront.tests.test_payment_contract -v 1
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py makemigrations --check --dry-run
git add twocomms/accounts/payment.py twocomms/orders/models.py \
  twocomms/orders/migrations/ twocomms/orders/email_receipt.py \
  twocomms/orders/telegram_notifications.py \
  twocomms/orders/payment_attempts.py twocomms/storefront/views/monobank.py \
  twocomms/orders/tests/test_payment_attempts.py \
  twocomms/storefront/tests/test_payment_contract.py
git commit -m "feat: support evidence-bound payment attempts"
```

### Task 8: Create one Monobank invoice under forwarded-browser concurrency

**Files:**
- Modify: `twocomms/management/services/ig_checkout.py`
- Modify: `twocomms/orders/models.py`
- Create: one migration in `twocomms/orders/migrations/` for durable invoice
  ownership/ambiguity fields, named from the final rebased graph
- Modify: `twocomms/orders/payment_attempts.py`
- Modify: `twocomms/storefront/models.py`
- Create: one migration in `twocomms/storefront/migrations/` for atomic promo
  reservations, named from the final rebased graph
- Modify: `twocomms/storefront/views/instagram_checkout.py`
- Modify: `twocomms/storefront/views/monobank.py`
- Test: `twocomms/storefront/tests/test_instagram_checkout_payment.py`
- Modify: `twocomms/storefront/tests/test_monobank_webhook.py`

- [ ] **Step 1: Write failing concurrency tests**

Use `TransactionTestCase` and two clients/threads to assert:

- one fingerprint by proposal+revision;
- one PaymentAttempt;
- one provider create call;
- one invoice reused by both browsers;
- provider success followed by DB-save crash is recovered without a second
  invoice;
- provider timeout becomes `invoice_creation_ambiguous` and is never blindly
  retried;
- stale creation lease is reclaimed without a second create call;
- a non-owner forwarded browser never calls the provider;
- a webhook/pull matching the stable PaymentAttempt reference heals an
  ambiguous create;
- one Order under webhook/return race;
- verified payment wins a correction race;
- exact minor amount and currency are required;
- provider invoice ID/reference must match the attempt and currency must be
  UAH/980;
- `hold`, `processing`, unknown, overpaid, underpaid, refund, and reversal are
  not treated as a clean paid terminal state;
- item reservations prevent a second checkout from selling the reserved last
  unit, and release on cancellation/expiry;
- promo `max_uses` cannot be over-reserved by concurrent guest proposals.
- delayed verified success after local expiry wins over local expiry truth.

- [ ] **Step 2: Run to verify failure**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  storefront.tests.test_instagram_checkout_payment \
  storefront.tests.test_monobank_webhook -v 2
```

- [ ] **Step 3: Implement fingerprint and provider payload**

```python
fingerprint = hashlib.sha256(
    f"ig-proposal:{proposal.pk}:revision:{proposal.revision}".encode("utf-8")
).hexdigest()
```

Set `tracking_payload.checkout_source = "instagram_assisted_checkout"`, original
client/deal/proposal IDs, payer browser attribution, `customerEmails`, basket,
and invoice `validity` equal to remaining proposal seconds (max 43200).

Before the network call, create/reuse the single `PaymentAttempt`, assign a
durable invoice-creation owner token/lease and provider reference, reserve promo
usage and sellable inventory, then commit. The owner performs the provider call.
On confirmed response, persist provider invoice ID/URL/status under the same
owner token. On timeout or crash after provider acceptance but before DB save,
mark `invoice_creation_ambiguous`, look up/poll by the stable provider reference
when supported, and require reconciliation or manager review before any new
create call. Never assume timeout means the provider created nothing.
Only the lease owner may persist invoice ID/URL after it re-locks the attempt.
Confirmed provider rejection may become a classified retryable failure;
timeout, connection loss, malformed response, process loss, or ownership loss
becomes `invoice_creation_ambiguous`. That state is healed only by a trusted
provider event/reference lookup or audited manager resolution.

Assert the sum of Monobank basket lines plus explicit negotiated/promo discount
adjustments equals the exact invoice minor amount. The frozen proposal quote is
never silently repriced during submit.

Reserve item quantities only for the payable invoice lifetime, not for the
whole unopened proposal lifetime. Consume reservations when the verified Order
materializes; release them on confirmed cancellation, expiry, failed creation,
or supersession. Unsupported/unreservable inventory blocks automation and opens
review instead of accepting an oversell silently.

- [ ] **Step 4: Implement cancellation/supersession guard**

Mock and verify the Monobank cancellation endpoint. Do not enable a replacement
invoice until provider cancellation is confirmed. Unknown cancellation state
or `invoice_creation_ambiguous` creates a review and blocks duplicate payment
creation and replacement.

Provider verification accepts only the documented captured/success terminal
state with matching invoice ID/reference, exact UAH/980 currency, and exact
expected minor amount. Underpayment and overpayment remain in checking/review
and emit no Purchase. Treat `hold` as
pending unless the current provider contract proves captured funds. Refund or
reversal after materialization must update PaymentAttempt, Order payment truth,
proposal/deal projection, fulfillment blocking, analytics reversal markers,
and lifecycle review state idempotently.

- [ ] **Step 5: Run tests and commit**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  storefront.tests.test_instagram_checkout_payment \
  storefront.tests.test_monobank_webhook -v 1
git add twocomms/management/services/ig_checkout.py \
  twocomms/orders/models.py twocomms/orders/migrations/ \
  twocomms/orders/payment_attempts.py \
  twocomms/storefront/models.py twocomms/storefront/migrations/ \
  twocomms/storefront/views/instagram_checkout.py \
  twocomms/storefront/views/monobank.py \
  twocomms/storefront/tests/test_instagram_checkout_payment.py \
  twocomms/storefront/tests/test_monobank_webhook.py
git commit -m "feat: create idempotent Instagram checkout invoices"
```

### Task 9: Bind converted attempts to Instagram commercial truth

**Files:**
- Create: `twocomms/management/services/ig_checkout_payments.py`
- Modify: `twocomms/orders/payment_attempts.py`
- Reuse/modify: `twocomms/management/services/ig_order_links.py`
- Reuse/modify: `twocomms/management/services/ig_commercial_episodes.py`
- Test: `twocomms/management/tests_ig_checkout_payments.py`
- Modify: `twocomms/management/tests_ig_order_links.py`

- [ ] **Step 1: Write failing adapter/replay tests**

Assert verified attempt creates one payment event/projection, binds deal/order,
creates one attribution, binds episode, marks client/proposal paid, schedules one
lifecycle event, sends no second Purchase, and repairs every partial crash state.
Add separate cases for promo full payment, negotiated discount, generic
prepayment, legacy `prepay_200`, refund/reversal after materialization,
fulfillment blocking, and the old direct-IG `IGDEAL-*` invoice path.
Cover reversal after complete Instagram binding and reversal during each partial
adapter crash boundary; both must converge to one append-only reversal event,
non-paid commercial truth, blocked unfulfilled fulfillment, and one manager
review without a second Purchase.

- [ ] **Step 2: Run to verify failure**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_payments management.tests_ig_order_links -v 2
```

- [ ] **Step 3: Implement post-commit adapter**

```python
def schedule_ig_checkout_binding(attempt, order):
    if (attempt.tracking_payload or {}).get("checkout_source") != \
            "instagram_assisted_checkout":
        return
    transaction.on_commit(
        lambda: bind_verified_attempt(attempt_id=attempt.pk, order_id=order.pk)
    )

@transaction.atomic
def bind_verified_attempt(*, attempt_id, order_id):
    attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt_id)
    order = Order.objects.select_for_update().get(pk=order_id)
    assert_verified_attempt_matches_order(attempt, order)
    proposal = lock_trusted_attempt_proposal(attempt)
    payment_event = record_attempt_payment_truth(proposal, attempt, order)
    sync_projection_from_attempt_scope(proposal.deal, attempt, order)
    attribution = create_order_attribution(
        order,
        client=proposal.client,
        creation_mode="provider_auto",
        payment_source="provider_attempt",
        deal=proposal.deal,
    )
    sync_episode_payment(deal=proposal.deal)
    bind_episode_order(
        proposal.commercial_episode,
        order,
        attribution=attribution,
        creation_mode="provider_auto",
        payment_source="provider_attempt",
    )
    mark_assisted_order_created_state(proposal, order, payment_event)
    emit_payment_verified(proposal, attempt, order)
    return attribution
```

The adapter must be idempotent and must not roll back a valid paid Order if its
post-commit work fails.
`IgPaymentProjection` must use the trusted PaymentAttempt scope, not only
`deal.payable_amount()`: full payment compares against the invoice/order amount,
generic prepayment compares against the requested paid amount while retaining
full order value, and promo/negotiated discounts are stored as explicit evidence.
The final state is proposal=`paid`, deal=`order_created`, client
stage=`order_created`, with the episode bound to the Order. Before applying that
state, disable the old
`fulfill_ready_paid_deals`/legacy direct-invoice creator for this assisted
source so it cannot race to create a second Order.

- [ ] **Step 4: Add reconciliation entry point**

`reconcile_converted_instagram_attempts(*, limit=100, cursor=None)` must scan
only converted `PaymentAttempt` rows with
`tracking_payload.checkout_source == "instagram_assisted_checkout"`, call the
same idempotent binding service, return processed/repaired/failed counts plus a
stable next cursor, and never resend already confirmed external side effects.

Bound the batch, preserve a cursor, and repair only trusted source attempts.

- [ ] **Step 5: Run tests and commit**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_payments management.tests_ig_order_links \
  management.tests_ig_commercial_episodes -v 1
git add twocomms/management/services/ig_checkout_payments.py \
  twocomms/orders/payment_attempts.py \
  twocomms/management/services/ig_order_links.py \
  twocomms/management/services/ig_commercial_episodes.py \
  twocomms/management/tests_ig_checkout_payments.py \
  twocomms/management/tests_ig_order_links.py
git commit -m "feat: bind assisted payments to Instagram orders"
```

### Task 10: Replace new bot paylinks with proposal URLs

**Files:**
- Modify: `twocomms/management/models.py`
- Create: one narrow management data migration for exact legacy prompt fragments,
  named from the final rebased graph
- Modify: `twocomms/management/services/instagram_bot.py`
- Modify: `twocomms/management/services/bot_orders.py`
- Modify: `twocomms/management/services/bot_payments.py`
- Modify: `twocomms/management/services/bot_playbooks.py`
- Modify: `twocomms/management/management/commands/seed_ig_bot_sales_playbooks.py`
- Modify: `twocomms/management/tests_ig_paylink_fix.py`
- Modify: `twocomms/management/tests_ig_instructions.py`
- Create: `twocomms/management/tests_ig_checkout_bot.py`

- [ ] **Step 1: Write failing bot behavior tests**

Cover `How can I pay?`, missing choices, complete one/multi-item proposal,
12-hour/share copy, Direct correction, same pre-invoice revision, post-invoice
supersession, no new direct provider URL, legacy invoice compatibility, Meta 508
or closed-window proposal delivery fallback, and `[ORDER]` remaining legacy-only.

- [ ] **Step 2: Run to verify failure**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_bot management.tests_ig_paylink_fix -v 2
```

- [ ] **Step 3: Update payment protocol and finalizer**

Keep `[PAYLINK]` parsing but replace the implementation boundary:

```python
proposal = ig_checkout.create_or_update_proposal(
    client=client,
    pay_type=pay_type,
    item_specs=_control_item_specs(control),
    negotiated_total=negotiated_total,
    requested_payment_amount=requested_payment_amount,
)
raw_token = ig_checkout.issue_access_token(proposal, kind="bot")
url = build_absolute_proposal_access_url(raw_token)
```

Visible copy must explain products are locked, delivery/email are entered on
site, checkout takes about two minutes, changes happen in Direct, the link lasts
12 hours, and it may be forwarded.

`bot_payments.create_payment_link()` remains for legacy deals only and receives
an explicit compatibility comment/test. New proposal code must not call it.

Replace `_invoice_deal_for_reply()` and
`_queue_payment_link_delivery_review()` with a source-aware payment-delivery
resolver that recognizes the exact assisted proposal URL/token delivery record,
not only `IgDeal.invoice_url` or Monobank regex. A Meta 508/window failure must
create one proposal-specific manager task and deduplicated alert without
stripping the own-domain URL or claiming delivery succeeded.

- [ ] **Step 4: Update playbook seeding safely**

Update all prompt authorities together:

- `DEFAULT_BOT_SYSTEM_PROMPT` no longer asks assisted buyers for delivery after
  payment and does not emit `[ORDER]` for assisted checkout;
- `PAYMENT_PROTOCOL_NOTE` requires full sellable item controls and proposal URL;
- the seeded `Product / SKU Context` instruction sends size/fit/color selection
  to the website delivery flow rather than collecting delivery in Direct;
- a narrow data migration rewrites only exact known legacy fragments in existing
  `InstagramBotSettings.system_prompt`, preserving all administrator custom text;
- `[ORDER]` runtime remains only for legacy `IGDEAL-*` invoices and existing
  post-payment Direct collection.

Add migration/idempotency tests and preserve short UA/RU replies plus unrelated
sales policy.

- [ ] **Step 5: Run suites and commit**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_bot management.tests_ig_paylink_fix \
  management.tests_ig_instructions management.tests_ig_sales_automation \
  management.tests_ig_current_product -v 1
git add twocomms/management/models.py twocomms/management/migrations/ \
  twocomms/management/services/instagram_bot.py \
  twocomms/management/services/bot_orders.py \
  twocomms/management/services/bot_payments.py \
  twocomms/management/services/bot_playbooks.py \
  twocomms/management/management/commands/seed_ig_bot_sales_playbooks.py \
  twocomms/management/tests_ig_checkout_bot.py \
  twocomms/management/tests_ig_paylink_fix.py \
  twocomms/management/tests_ig_instructions.py
git commit -m "feat: send TwoComms proposals from Instagram"
```

### Task 11: Add deterministic product-media recommendations

**Files:**
- Modify: `twocomms/management/services/instagram_bot.py`
- Create: `twocomms/management/services/ig_catalog_media.py`
- Modify: `twocomms/management/services/bot_catalog.py`
- Test: `twocomms/management/tests_ig_catalog_media.py`
- Modify: `twocomms/management/tests_ig_media_workflow.py`
- Modify: `twocomms/management/tests_ig_instagram_login.py`

- [ ] **Step 1: Write failing selection/transport tests**

Assert 3-4 published product images, selected color image, trusted host/MIME,
bounded payload, no Gemini external URL, native supported carousel payload, and
deterministic sequential fallback with partial-send classification.

- [ ] **Step 2: Run to verify failure**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_catalog_media management.tests_ig_media_workflow \
  management.tests_ig_instagram_login -v 2
```

- [ ] **Step 3: Implement catalog-owned media selection**

`select_product_media(product_ids, *, color_variant_ids=None, limit=4)` returns
at most four catalog-owned, published, host/MIME/size-validated images in stable
product order, preferring the selected color variant. Then
`build_provider_media_messages(selection, *, transport)` emits either one
provider-supported multi-image payload or a bounded ordered image sequence plus
one caption, and returns a transport batch with explicit partial/ambiguous
delivery semantics.

Use only catalog media. If the verified active transport does not support a
true multi-image message, send a bounded sequence and one caption.

- [ ] **Step 4: Add hidden control and delivery path**

Parse a strict catalog-ID control such as `[SHOW_PRODUCTS:12,15,18]`. The
provider send function must return confirmed/partial/ambiguous status and must
not be mixed into payment-link fallback logic.

- [ ] **Step 5: Run tests and commit**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_catalog_media management.tests_ig_media_workflow \
  management.tests_ig_instagram_login -v 1
git add twocomms/management/services/ig_catalog_media.py \
  twocomms/management/services/bot_catalog.py \
  twocomms/management/services/instagram_bot.py \
  twocomms/management/tests_ig_catalog_media.py \
  twocomms/management/tests_ig_media_workflow.py \
  twocomms/management/tests_ig_instagram_login.py
git commit -m "feat: show catalog media in Instagram Direct"
```

### Task 12: Add proposal analytics and verified success behavior

**Files:**
- Modify: `twocomms/storefront/views/instagram_checkout.py`
- Modify: `twocomms/twocomms_django_theme/templates/pages/instagram_checkout.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/instagram_checkout_success.html`
- Modify: `twocomms/twocomms_django_theme/static/js/instagram-checkout.js`
- Modify: `twocomms/storefront/views/monobank.py`
- Modify: `twocomms/orders/facebook_conversions_service.py`
- Test: `twocomms/storefront/tests/test_instagram_checkout_analytics.py`
- Modify: `twocomms/storefront/tests/test_meta_pixel_configuration.py`

- [ ] **Step 1: Write failing event-timing tests**

Assert token entrance, crawler/preload, validation failure, ambiguous invoice,
pending return, and failed/reversed payment send no prohibited event. Each clean
session grant gets its own ViewContent/InitiateCheckout occurrence; original and
forwarded payer grants have distinct Initiate IDs, while Pixel/CAPI for the same
grant share one ID. AddPaymentInfo occurs only after invoice ID/URL are durably
stored. Verified webhook sends one CAPI Purchase even without browser return;
repeated verified success pages reuse the Order Purchase ID. Browser events
respect the site's consent gate and server events respect approved privacy/
exclusion policy.

- [ ] **Step 2: Run to verify failure**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  storefront.tests.test_instagram_checkout_analytics \
  storefront.tests.test_meta_pixel_configuration -v 2
```

- [ ] **Step 3: Implement deterministic IDs and event payloads**

```python
initiate_event_id = hmac_event_id(
    "InitiateCheckout",
    proposal.pk,
    proposal.revision,
    signed_grant.grant_id,
)
add_payment_event_id = attempt.add_payment_event_id
purchase_event_id = order.get_purchase_event_id()
```

Each signed clean-page grant contains a random `grant_id`; never expose the raw
session key or grant secret. Derive ViewContent/InitiateCheckout IDs with a
server HMAC. The first valid submit freezes that payer browser's `_fbp`, `_fbc`,
IP, and UA into PaymentAttempt; later viewers cannot overwrite them. Use full
discounted order value and separate paid value. Never emit Lead for prepayment.

- [ ] **Step 4: Add bounded pending status endpoint**

Return only `pending`, `verified`, `failed`, or `expired` plus a safe redirect.
The browser polls with bounded exponential backoff and no PII.

- [ ] **Step 5: Run mocked/no-network tests and commit**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  storefront.tests.test_instagram_checkout_analytics \
  storefront.tests.test_meta_pixel_configuration \
  storefront.tests.test_monobank_webhook -v 1
git add twocomms/storefront/views/instagram_checkout.py \
  twocomms/storefront/views/monobank.py \
  twocomms/orders/facebook_conversions_service.py \
  twocomms/twocomms_django_theme/templates/pages/instagram_checkout*.html \
  twocomms/twocomms_django_theme/static/js/instagram-checkout.js \
  twocomms/storefront/tests/test_instagram_checkout_analytics.py \
  twocomms/storefront/tests/test_meta_pixel_configuration.py
git commit -m "feat: track assisted checkout conversions"
```

### Task 13: Implement the leased lifecycle outbox worker

**Files:**
- Create: `twocomms/management/services/ig_checkout_lifecycle.py`
- Modify: `twocomms/management/services/instagram_bot.py`
- Modify: `twocomms/management/management/commands/run_instagram_bot.py`
- Test: `twocomms/management/tests_ig_checkout_lifecycle.py`

- [ ] **Step 1: Write failing lease/idempotency tests**

Cover unique emission, claim, lease expiry, stale reclaim, ownership recheck,
confirmed send, window closed, ambiguous send, retryable rejection, opt-out,
hidden client, takeover/pause, duplicate worker processes, provider message ID
persistence, tuple-compatible legacy callers, and opt-out/takeover racing exactly
between pre-send validation and the Meta request.

- [ ] **Step 2: Run to verify failure**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_lifecycle -v 2
```

- [ ] **Step 3: Implement emission and claim APIs**

Implement three explicit service boundaries:

- `emit_lifecycle_event(*, event_key, kind, client, order, deal=None,
  proposal=None, commercial_episode=None, attribution=None, locale="uk",
  payload=None)` uses the canonical key to create-or-return one event and
  validates that order, client, deal, proposal, and episode belong to the same
  commercial chain;
- `claim_lifecycle_events(limit=20, lease_seconds=120)` atomically claims only
  due/reclaimable rows and returns event IDs with unguessable lease tokens;
- `process_lifecycle_event(event_id, lease_token)` rechecks lease ownership,
  opt-out/takeover/client state, business truth, and Meta-window eligibility,
  then records confirmed, ambiguous, retryable, or manager-review outcome.

Revalidate state, lease token, expiry, opt-out, and payment/order truth
immediately before send and immediately before final state write.

Add a structured delivery receipt path in `instagram_bot.py` containing
`ok`, classified outcome, hint, provider message ID, ambiguity, and retryability.
Preserve the existing `(ok, kind, hint)` tuple contract for legacy callers via a
wrapper. Lifecycle delivery must execute inside the established
`reply_execution_boundary` and `customer_send_boundary`, so opt-out, takeover,
pause, and ownership cannot change between the final authorization check and
the provider call. Mark `sent` only from a confirmed receipt with provider ID.

- [ ] **Step 4: Integrate bounded processing into daemon**

Process a small batch per loop without starving inbound replies. Use the current
Meta rate/circuit state. Automatic `HUMAN_AGENT` remains rejected before token
or network access.

- [ ] **Step 5: Run tests and commit**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_lifecycle management.tests_ig_shipment -v 1
git add twocomms/management/services/ig_checkout_lifecycle.py \
  twocomms/management/services/instagram_bot.py \
  twocomms/management/management/commands/run_instagram_bot.py \
  twocomms/management/tests_ig_checkout_lifecycle.py
git commit -m "feat: process Instagram order lifecycle events"
```

### Task 14: Emit and send verified-payment confirmation

**Files:**
- Modify: `twocomms/management/services/ig_checkout_payments.py`
- Modify: `twocomms/management/services/ig_checkout_lifecycle.py`
- Test: `twocomms/management/tests_ig_checkout_payment_message.py`

- [ ] **Step 1: Write failing message tests**

Assert event only after verified materialization and exact order/client binding.
The message goes only to the original bound Instagram conversation, never to a
forwarded payer browser, and repeats the confirmed recipient full name, phone,
Nova Poshta city, branch/post-locker, and order number exactly as stored so the
customer can catch a delivery mistake. Also assert deterministic UA/RU/EN text,
one send, provider message ID, and no message for reversed/unverified payment.

- [ ] **Step 2: Run to verify failure**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_payment_message -v 2
```

- [ ] **Step 3: Implement deterministic renderer**

```python
def render_payment_verified(event):
    return localized_template(
        event.locale,
        order_number=event.order.order_number,
        recipient=event.order.full_name,
        phone=event.order.phone,
        delivery=format_order_delivery(event.order),
    )
```

Do not ask Gemini to reconstruct payment or address facts. The forwardable web
page and management lists still mask PII; this full confirmation is restricted
to the already-bound original Instagram conversation and is covered by an
explicit privacy test.

- [ ] **Step 4: Run and commit**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_payment_message \
  management.tests_ig_checkout_payments -v 1
git add twocomms/management/services/ig_checkout_payments.py \
  twocomms/management/services/ig_checkout_lifecycle.py \
  twocomms/management/tests_ig_checkout_payment_message.py
git commit -m "feat: confirm assisted payments in Direct"
```

### Task 15: Emit TTN creation from the canonical order transition

**Files:**
- Modify: `twocomms/orders/signals.py`
- Modify: `twocomms/management/services/ig_checkout_lifecycle.py`
- Modify: `twocomms/management/services/bot_orders.py`
- Test: `twocomms/management/tests_ig_checkout_ttn.py`
- Modify: `twocomms/management/tests_ig_shipment.py`
- Modify: `twocomms/orders/tests/test_tasks.py`

- [ ] **Step 1: Write failing transition tests**

Cover first TTN, repeated save, changed TTN, attribution-only order, deal-bound
order, TTN before/after status `ship`, Telegram failure, transaction rollback,
Meta send success/failure, and legacy `shipped_notified_at` compatibility.

- [ ] **Step 2: Run to verify failure**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_ttn management.tests_ig_shipment \
  orders.tests.test_tasks -v 2
```

- [ ] **Step 3: Emit after commit beside Telegram**

Track the transition in `pre_save`, but schedule domain emission after the
successful save/transaction:

```python
if not old_tracking and new_tracking:
    transaction.on_commit(
        lambda order_id=instance.pk: emit_ttn_created_for_order(order_id)
    )
```

The emitter resolves `IgOrderAttribution`/deal/episode, normalizes the TTN, and
uses `ttn:<order>:<digest>` as the unique key. It is independent of Telegram
delivery and does not require `status == "ship"`.

- [ ] **Step 4: Render and send TTN message**

Use the official Nova Poshta tracking URL. Mark `shipped_notified_at` only after
confirmed Direct delivery. Outside the window, create one prepared manager task
and alert.

- [ ] **Step 5: Run and commit**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_ttn management.tests_ig_shipment \
  orders.tests.test_tasks -v 1
git add twocomms/orders/signals.py \
  twocomms/management/services/ig_checkout_lifecycle.py \
  twocomms/management/services/bot_orders.py \
  twocomms/management/tests_ig_checkout_ttn.py \
  twocomms/management/tests_ig_shipment.py twocomms/orders/tests/test_tasks.py
git commit -m "feat: send Instagram TTN lifecycle updates"
```

### Task 16: Emit delivered-order review requests from Nova Poshta truth

**Files:**
- Modify: `twocomms/orders/nova_poshta_service.py`
- Modify: `twocomms/management/services/ig_checkout_lifecycle.py`
- Test: `twocomms/management/tests_ig_checkout_delivery_review.py`
- Modify: `twocomms/storefront/tests/test_nova_poshta_tracking_dedup.py`

- [ ] **Step 1: Write failing delivery tests**

Cover canonical delivered StatusCode, localized text mismatch, repeated poll,
transaction rollback, existing done order, COD compatibility, exact Instagram
binding, review copy, window fallback, opt-out, and no duplicate request.

- [ ] **Step 2: Run to verify failure**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_delivery_review \
  storefront.tests.test_nova_poshta_tracking_dedup -v 2
```

- [ ] **Step 3: Emit from committed provider transition**

When `_apply_tracking_update()` reports `is_delivery=True`, schedule:

```python
transaction.on_commit(
    lambda order_id=order.pk, status_code=status_code:
        emit_delivered_review_for_order(order_id, status_code=status_code)
)
```

Use provider status code in the event key. Do not parse the localized
`shipment_status` string.

- [ ] **Step 4: Add deterministic localized review copy**

Request a short review/story tag without discount, pressure, false urgency, or
invented facts. Keep `@twocomms` explicit. Outside the response window, preserve
the prepared message in one manager task and one deduplicated alert.

- [ ] **Step 5: Run and commit**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_delivery_review \
  storefront.tests.test_nova_poshta_tracking_dedup -v 1
git add twocomms/orders/nova_poshta_service.py \
  twocomms/management/services/ig_checkout_lifecycle.py \
  twocomms/management/tests_ig_checkout_delivery_review.py \
  twocomms/storefront/tests/test_nova_poshta_tracking_dedup.py
git commit -m "feat: request Instagram reviews after delivery"
```

### Task 17: Add the Awaiting Payment management workspace

**Files:**
- Modify: `twocomms/management/bot_views.py`
- Modify: `twocomms/management/urls.py`
- Modify: `twocomms/management/templates/management/bot.html`
- Test: `twocomms/management/tests_ig_checkout_workspace.py`
- Modify: `twocomms/management/tests_ig_clients_ui.py`

- [ ] **Step 1: Write failing API/render tests**

Assert pending count, state filters, expiry, revision, amount, item facts,
masked/no PII payload, no bearer token, safe preview, copy token, resend/revoke,
history, permissions, provider-cancellation gate, and existing filter
compatibility. Revoke/supersede must refuse while an invoice is payable or
ambiguous; only trusted pull-confirmed non-payable state can move it to
`cancelled`, `revoked`, or a replacement proposal.

- [ ] **Step 2: Run to verify failure**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_workspace management.tests_ig_clients_ui -v 2
```

- [ ] **Step 3: Extend API payload and filters**

Add an `awaiting_payment` view that includes proposal state without merging
unpaid proposals into confirmed order counts. All link issuance occurs through
a POST action and returns a newly issued access URL only to authorized staff.

- [ ] **Step 4: Extend existing template**

Use the existing Orders workspace patterns. Add one filter and proposal detail
surface; do not add a separate nested card system or oversized explanatory UI.

- [ ] **Step 5: Run and commit**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_workspace management.tests_ig_clients_ui -v 1
git add twocomms/management/bot_views.py twocomms/management/urls.py \
  twocomms/management/templates/management/bot.html \
  twocomms/management/tests_ig_checkout_workspace.py \
  twocomms/management/tests_ig_clients_ui.py
git commit -m "feat: show pending Instagram checkouts"
```

### Task 18: Add expiry and crash reconciliation commands

**Files:**
- Create: `twocomms/management/management/commands/reconcile_ig_checkouts.py`
- Create: `twocomms/management/management/commands/process_ig_lifecycle_events.py`
- Modify: `twocomms/management/management/commands/poll_ig_deal_payments.py`
- Create: `twocomms/orders/management/commands/reconcile_order_post_payment_events.py`
- Modify: `twocomms/orders/management/commands/reconcile_order_telegram_notifications.py`
  into a compatibility wrapper or retire it only after cron migration
- Modify: `twocomms/storefront/views/utils.py`
- Modify: `twocomms/management/services/ig_checkout.py`
- Modify: `twocomms/management/services/ig_checkout_payments.py`
- Modify: `twocomms/management/services/ig_checkout_lifecycle.py`
- Test: `twocomms/management/tests_ig_checkout_reconciliation.py`
- Modify: `twocomms/management/tests_ig_polling.py`
- Create: `twocomms/orders/tests/test_reconcile_order_post_payment_events.py`

- [ ] **Step 1: Write failing reconciliation tests**

Cover expired ready proposal, expired invoice/attempt, converted attempt missing
deal link, missing attribution, missing payment event, missing TTN event, missing
delivery event, stale lifecycle lease, bounded cursor, and idempotent rerun. Add
process-loss cases before dispatcher start; Telegram success followed by process
loss before CAPI; CAPI success followed by receipt failure; replay of missing
channels only; disabled Meta/TikTok reaching explicit skipped state; ambiguous
invoice creation healing; stale promo/inventory release; and AddPaymentInfo CAPI
marker recovery. Prove `poll_ig_deal_payments --check-only` performs no database
write and no Instagram/Telegram/provider send.

- [ ] **Step 2: Run to verify failure**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_reconciliation -v 2
```

- [ ] **Step 3: Implement bounded commands**

Commands must accept `--limit`, avoid unbounded full-table scans, print counts,
and support `--dry-run` with zero external side effects. In normal mode,
`reconcile_order_post_payment_events` and `process_ig_lifecycle_events` perform
only missing channels through the same idempotent send functions. Dry-run may
inspect/classify but must not persist delivery markers or call Telegram, email,
Meta, TikTok, or Instagram providers.

Before the payment transaction commits, persist `post_payment_pending=True` and
separate channel states for Telegram, receipt email, Meta Purchase, TikTok
Purchase, and Instagram lifecycle emission. A channel completes only when
confirmed sent, explicitly not applicable, or permanently disabled. One
successful channel never clears another channel's pending state.

The order reconciler selects recent verified PaymentAttempt orders whenever any
mandatory post-payment channel remains pending, regardless of Telegram state.
It claims one order with a lease and invokes the same idempotent per-channel
functions. A separate bounded query scans invoice-backed attempts missing the
persisted AddPaymentInfo CAPI marker. Checkout reconciliation also resolves
proposal expiry, binding gaps, invoice ambiguity, promo reservations, inventory
reservations, and lifecycle event gaps from provider/order truth.

- [ ] **Step 4: Run twice and assert no duplicate work**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_reconciliation -v 2
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py reconcile_ig_checkouts \
  --limit 20 --dry-run
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py \
  reconcile_order_post_payment_events --limit 20 --dry-run
```

- [ ] **Step 5: Commit**

```bash
git add twocomms/management/management/commands/reconcile_ig_checkouts.py \
  twocomms/management/management/commands/process_ig_lifecycle_events.py \
  twocomms/management/management/commands/poll_ig_deal_payments.py \
  twocomms/orders/management/commands/reconcile_order_post_payment_events.py \
  twocomms/orders/management/commands/reconcile_order_telegram_notifications.py \
  twocomms/orders/tests/test_reconcile_order_post_payment_events.py \
  twocomms/storefront/views/utils.py \
  twocomms/management/services/ig_checkout*.py \
  twocomms/management/tests_ig_checkout_reconciliation.py \
  twocomms/management/tests_ig_polling.py
git commit -m "feat: reconcile Instagram checkout lifecycle"
```

### Task 19: Run full automated and browser verification

**Files:**
- Create: `tests/instagram-assisted-checkout.spec.cjs`
- Update: `docs/plans/2026-07-30-instagram-assisted-checkout-checklist.md`
- No production source changes unless a verified defect is found.

- [ ] **Step 1: Run focused Python suites**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_checkout_models \
  management.tests_ig_checkout_service \
  management.tests_ig_checkout_bot \
  management.tests_ig_checkout_payments \
  management.tests_ig_checkout_lifecycle \
  management.tests_ig_checkout_payment_message \
  management.tests_ig_checkout_ttn \
  management.tests_ig_checkout_delivery_review \
  management.tests_ig_checkout_workspace \
  management.tests_ig_checkout_reconciliation \
  storefront.tests.test_instagram_checkout_access \
  storefront.tests.test_instagram_checkout_view \
  storefront.tests.test_instagram_checkout_form \
  storefront.tests.test_instagram_checkout_payment \
  storefront.tests.test_instagram_checkout_analytics -v 1
```

Expected: all pass.

- [ ] **Step 2: Run related regression suites**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  management.tests_ig_paylink_fix \
  management.tests_bot_orders \
  management.tests_bot_payments \
  management.tests_ig_current_product \
  management.tests_ig_order_links \
  management.tests_ig_commercial_episodes \
  management.tests_ig_shipment \
  management.tests_ig_sales_automation \
  management.tests_ig_instagram_login \
  management.tests_ig_conversation_analysis_jobs \
  orders.tests.test_payment_attempts \
  storefront.tests.test_monobank_webhook \
  storefront.tests.test_nova_poshta_checkout_validation \
  storefront.tests.test_nova_poshta_tracking_dedup \
  storefront.tests.test_analytics_loader \
  storefront.tests.test_analytics_tracking \
  storefront.tests.test_external_analytics \
  storefront.tests.test_meta_pixel_configuration -v 1
```

Expected: zero failures. Record any newly discovered pre-existing failure with
an isolated reproduction before changing its owner.

- [ ] **Step 3: Run static/system checks**

```bash
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py check
DEBUG=1 SECRET_KEY=local-baseline-only \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py makemigrations --check --dry-run
node --test tests/instagram-checkout-ui-contract.test.cjs
git diff --check
```

Expected: clean.

- [ ] **Step 4: Run local server and Playwright**

Start on an unused port with mocked Monobank and no live analytics transport.
Verify screenshots/states at 320x568, 375x812, 430x932, 768x1024, and
1440x900. Check one/two/four/long item lists, keyboard navigation, reduced
motion, error/loading/pending/paid/expired/superseded, CSP console, image pixels,
token-free analytics URLs, and zero overlap/overflow.

Mock the Nova Poshta city/warehouse endpoints and verify the real
`nova-poshta-form-bridge.js` integration: city keyboard selection,
branch/post-locker switching, warehouse keyboard selection, signed hidden city
and warehouse tokens, stale-token rejection, wrong-city warehouse rejection,
and no free-text submit fallback.

With an authenticated management session, verify Awaiting Payment on mobile and
desktop: filter/count, proposal detail, safe preview, copy-token, resend, revoke,
revision/lifecycle history, permission rejection, keyboard focus order, no
horizontal overflow, and no raw PII/bearer token in DOM or network payloads.

- [ ] **Step 5: Independent read-only reviews**

Assign read-only agents to:

- checkout/payment/idempotency/security;
- Instagram bot/Meta policy/lifecycle;
- mobile UI/accessibility/analytics.

Primary agent evaluates and implements only justified findings, then reruns the
affected and full suites.

- [ ] **Step 6: Update checklist and commit**

Check only evidence-backed items and link test/screenshot evidence in notes.

```bash
git add tests/instagram-assisted-checkout.spec.cjs \
  docs/plans/2026-07-30-instagram-assisted-checkout-checklist.md
git commit -m "test: verify Instagram assisted checkout"
```

### Task 20: Reconcile current main, push, deploy, and prove production state

**Files:**
- Update: `docs/plans/2026-07-30-instagram-assisted-checkout-checklist.md`
- No unrelated source edits.

- [ ] **Step 1: Final integration review**

```bash
git fetch origin main
git log --oneline --left-right --cherry-pick HEAD...origin/main
git status --short
git diff --stat origin/main...HEAD
```

Rebase/merge deliberately, rerun all required tests, and ensure staged scope
contains only this feature.

- [ ] **Step 2: Push the agreed branch/main flow**

Push `codex/instagram-assisted-checkout`, reconcile it with the then-current
`origin/main`, rerun the integration gate, and land the reviewed feature onto
`main` with a non-destructive fast-forward/merge. Push `main`, confirm its
remote SHA, and never force-push shared history.

- [ ] **Step 3: Deploy through the verified server environment**

On the server:

```bash
git pull --ff-only origin main
python manage.py migrate
python manage.py check
python manage.py collectstatic --noinput
python manage.py compress --force
python manage.py seed_ig_bot_sales_playbooks
touch tmp/restart.txt
python manage.py run_instagram_bot --ensure
python manage.py reconcile_ig_checkouts --limit 100 --dry-run
python manage.py reconcile_order_post_payment_events --limit 100 --dry-run
python manage.py process_ig_lifecycle_events --limit 5 --dry-run
python manage.py poll_ig_deal_payments --limit 5 --check-only
```

Install guarded recurring execution with the existing production scheduler and
absolute virtualenv Python path:

- `reconcile_ig_checkouts --limit 100` every two minutes under its own
  non-blocking `flock`;
- `reconcile_order_post_payment_events --limit 100` every two minutes under a
  separate non-blocking `flock`;
- lifecycle delivery stays in the bounded Instagram daemon loop, with the
  standalone command retained for controlled recovery.

Preserve all unrelated cron entries and prove the effective crontab/service
definition after installation. Add and test `--check-only` before using
`poll_ig_deal_payments`: the current normal command mutates projections, can
materialize Orders, and can send Instagram shipment messages. Check-only may
fetch/classify at most five legacy invoices but must not persist or send
anything. Do not create a new direct invoice.

Use the user-provided SSH secret through a protected environment variable; do
not echo, store, or commit it.

- [ ] **Step 4: Verify production proof**

Confirm:

- server HEAD equals intended commit;
- migrations applied and new tables/indexes are InnoDB;
- proposal access/clean routes have correct headers;
- management Awaiting Payment state loads;
- daemon heartbeat and queue/outbox are healthy;
- playbooks are current;
- no duplicate active proposal/invoice/order constraints are violated;
- no live customer, Meta, TikTok, or Monobank test event was emitted;
- one approved non-payable preview or controlled fixture renders correctly;
- persisted adapter/lifecycle reconciliation markers are present for any
  authorized test fixture;
- non-event-emitting analytics proof confirms the live bridge/payload,
  token-free source URL, configured Pixel availability, deterministic event IDs,
  consent gating, and persisted AddPaymentInfo/Purchase CAPI markers from an
  authorized existing fixture;
- effective cron/daemon configuration is active and a second bounded dry run
  reports no duplicate work;
- legacy `poll_ig_deal_payments` completes without breaking old `IGDEAL-*`
  invoices.

- [ ] **Step 5: Close the checklist and commit final evidence**

```bash
git add docs/plans/2026-07-30-instagram-assisted-checkout-checklist.md
git commit -m "docs: record assisted checkout production proof"
git push origin main
```

Because this evidence commit changes `main`, pull it on production once more,
verify local/origin/server SHA equality, and rerun the minimal `manage.py check`,
daemon heartbeat, route-header, and scheduler proof. Do not report the earlier
feature SHA as final after a later documentation commit.

## Execution handoff

The user has already chosen the execution model: the primary agent implements
in this worktree, while subagents remain read-only reviewers. Before Task 0,
re-read the user's original full requirement message and reconcile it against
the design and acceptance checklist. Then invoke `superpowers:executing-plans`
and execute tasks sequentially with the documented verification and commit
checkpoints.
