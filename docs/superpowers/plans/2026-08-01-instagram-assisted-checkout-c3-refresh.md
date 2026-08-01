# Instagram Assisted Checkout C3 Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the approved C3 assisted-checkout page with one authoritative 25-minute lifetime, an accessible conversion-focused payment rail, strict recoverable delivery validation with optional receipt email, truthful promo handling, and complete mobile/browser verification.

**Architecture:** Keep the existing `IgCheckoutProposal` -> clean session grant -> signed Nova Poshta form -> atomic `PaymentAttempt` -> Monobank flow. Change only the proposal deadline and presentation contract: server time remains authoritative, all derived tokens/reservations/invoices are capped by the proposal, and the browser renders/focuses stable public validation codes without becoming a financial source of truth. Reuse existing receipt, promo reservation, analytics, Direct, legal-route, and lifecycle services.

**Tech Stack:** Django 5.2, MariaDB/InnoDB, server-rendered Django templates, isolated CSS and vanilla JavaScript, Node source-contract tests, Django TestCase, Playwright/browser screenshots.

---

## Execution Rules

- Work only in `/Users/zainllw0w/.config/superpowers/worktrees/site/instagram-assisted-checkout`.
- Do not edit frozen `management.0116` or `management.0117`; no management schema change is expected.
- Do not touch CRM reconciliation or parallel P0 live-reply code beyond existing checkout-specific copy.
- Preserve legacy direct-invoice compatibility while generating only own-domain links for new assisted checkouts.
- Use test-first RED/GREEN cycles for every behavior change.
- Do not send live Monobank, Nova Poshta, Meta, TikTok, Telegram, email, or Instagram messages.
- Treat MariaDB/InnoDB and production payment semantics as authoritative; SQLite is only an isolated test fixture.
- Do not push, deploy, migrate production, or merge main while unified HEAD remains uncoordinated.

## File Ownership

| Unit | Responsibility | Files |
| --- | --- | --- |
| Deadline domain | New proposal lifetime and caps for every derived payment artifact | `twocomms/management/ig_bot_models.py`, `twocomms/management/services/ig_checkout.py`, `twocomms/management/services/ig_checkout_payment.py` |
| Customer copy | Consistent 25-minute and recovery wording in bot/page/knowledge | `twocomms/management/services/instagram_bot.py`, `twocomms/management/bot_knowledge/brand.md`, `twocomms/storefront/views/ig_checkout.py` |
| Checkout markup | Semantic countdown, help, legal, exit dialog, rail, validation anchors | `twocomms/twocomms_django_theme/templates/pages/ig_checkout.html` |
| Checkout behavior | Countdown/expiry, client validation/focus, promo disclosure, exit dialog, one-time rail readiness | `twocomms/twocomms_django_theme/static/js/instagram-checkout.js` |
| Checkout styling | C3 dark brand surface and responsive/accessibility states | `twocomms/twocomms_django_theme/static/css/instagram-checkout.css` |
| Contracts | Server, UI-source, locale, browser, and MariaDB compatibility evidence | listed test files below |

### Task 1: Make 25 Minutes the Authoritative Proposal Deadline

**Files:**
- Modify: `twocomms/management/ig_bot_models.py`
- Modify: `twocomms/management/services/ig_checkout_payment.py`
- Test: `twocomms/management/tests_ig_checkout_models.py`
- Test: `twocomms/management/tests_ig_paylink_fix.py`

- [ ] **Step 1: Write the failing default-expiry test**

Add a test that freezes `timezone.now()` and proves the callable returns exactly 25 minutes later:

```python
@patch("management.ig_bot_models.timezone.now")
def test_default_checkout_proposal_expiry_is_twenty_five_minutes(self, now_mock):
    now = timezone.now().replace(microsecond=0)
    now_mock.return_value = now
    self.assertEqual(default_checkout_proposal_expiry(), now + timedelta(minutes=25))
```

- [ ] **Step 2: Run the test and verify RED**

Run from `twocomms/`:

```bash
python manage.py test --settings=test_settings \
  management.tests_ig_checkout_models.IgCheckoutProposalModelTests.test_default_checkout_proposal_expiry_is_twenty_five_minutes -v 2
```

Expected: FAIL because the current callable returns 12 hours.

- [ ] **Step 3: Implement the minimum deadline change**

```python
def default_checkout_proposal_expiry():
    return timezone.now() + timedelta(minutes=25)
```

Do not create or edit a migration: this changes a callable runtime default, not the frozen schema.

- [ ] **Step 4: Write failing cap and boundary tests**

Add assertions that:

```python
self.assertLessEqual(access_token.expires_at, proposal.expires_at)
self.assertLessEqual(attempt.invoice_expires_at, proposal.expires_at)
provider_create.assert_not_called()  # when server time reaches proposal.expires_at
```

Cover bot token, share token, inventory reservation, promo reservation, and Monobank invoice expiry.

- [ ] **Step 5: Run the boundary tests and verify RED**

```bash
python manage.py test --settings=test_settings \
  management.tests_ig_paylink_fix.IgCheckoutPaymentTests -v 2
```

Expected: at least the old 12-hour invoice cap or edge-submit assertion fails.

- [ ] **Step 6: Cap all derived lifetimes**

Use the proposal deadline directly:

```python
invoice_expires_at = min(locked.expires_at, now + timedelta(minutes=25))
if locked.expires_at <= now:
    raise CheckoutPaymentError("expired", "Термін дії пропозиції завершився.")
```

Keep the expiry check inside the locked transaction and before any provider call.

- [ ] **Step 7: Run the focused domain suite and commit**

```bash
python manage.py test --settings=test_settings \
  management.tests_ig_checkout_models management.tests_ig_paylink_fix -v 1
git add twocomms/management/ig_bot_models.py \
  twocomms/management/services/ig_checkout_payment.py \
  twocomms/management/tests_ig_checkout_models.py \
  twocomms/management/tests_ig_paylink_fix.py
git commit -m "fix(ig): cap assisted checkout at 25 minutes"
```

Expected: focused tests pass and no migration is generated.

### Task 2: Align Bot, Page, and Knowledge Copy

**Files:**
- Modify: `twocomms/management/services/instagram_bot.py`
- Modify: `twocomms/management/bot_knowledge/brand.md`
- Modify: `twocomms/storefront/views/ig_checkout.py`
- Test: `twocomms/management/tests_ig_paylink_fix.py`
- Test: `twocomms/storefront/tests/test_ig_checkout_view.py`

- [ ] **Step 1: Add failing copy contracts**

Assert Ukrainian, Russian, and English copy contains the equivalent of exactly 25 minutes and no old duration:

```python
self.assertIn("25 хвилин", uk_message)
self.assertNotIn("12 год", uk_message)
self.assertEqual(context["copy"]["secure_payment"],
                 "Дані картки вводяться на захищеній сторінці Monobank")
```

Add equivalent assertions for Russian and English plus Direct replacement wording.

- [ ] **Step 2: Run and verify RED**

```bash
python manage.py test --settings=test_settings \
  management.tests_ig_paylink_fix storefront.tests.test_ig_checkout_view -v 1
```

Expected: FAIL on obsolete 12-hour and generic security copy.

- [ ] **Step 3: Replace customer-facing copy consistently**

Use locale-native text. Ukrainian canonical strings are:

```python
"expires_explanation": "Посилання діє 25 хвилин від створення.",
"secure_payment": "Дані картки вводяться на захищеній сторінці Monobank",
"optional": "Необов'язково",
"email_hint": "Якщо вкажете email, надішлемо сюди чек і підтвердження. Без розсилок.",
"direct_help": (
    "Щось не так із товаром, розміром, сумою чи доставкою? "
    "Напишіть у той самий Direct — ми оновимо пропозицію або сформуємо нове посилання."
),
```

Keep the original two-minute form-completion estimate separate from the 25-minute expiry.

- [ ] **Step 4: Run copy tests and commit**

```bash
python manage.py test --settings=test_settings \
  management.tests_ig_paylink_fix storefront.tests.test_ig_checkout_view -v 1
git add twocomms/management/services/instagram_bot.py \
  twocomms/management/bot_knowledge/brand.md \
  twocomms/storefront/views/ig_checkout.py \
  twocomms/management/tests_ig_paylink_fix.py \
  twocomms/storefront/tests/test_ig_checkout_view.py
git commit -m "fix(ig): explain assisted checkout expiry and recovery"
```

### Task 3: Render the C3 Rail, Countdown, Help, Legal, and Exit Dialog

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/pages/ig_checkout.html`
- Modify: `twocomms/storefront/views/ig_checkout.py`
- Test: `tests/instagram-checkout-ui-contract.test.cjs`
- Test: `twocomms/storefront/tests/test_ig_checkout_view.py`

- [ ] **Step 1: Add failing semantic markup contracts**

Require stable hooks rather than visual-string-only tests:

```javascript
assert.match(template, /data-countdown-ring/);
assert.match(template, /data-payment-amount/);
assert.match(template, /data-payment-trust/);
assert.match(template, /data-direct-help/);
assert.match(template, /data-exit-dialog/);
assert.match(template, /data-checkout-exit/);
assert.doesNotMatch(template, /ig-action--pay[^>]*>[\s\S]{0,120}(lock|замок)/i);
```

The Django view test must resolve `returns`, `privacy_policy`, and configured optional legal routes without inventing URLs.

- [ ] **Step 2: Run and verify RED**

```bash
node --test tests/instagram-checkout-ui-contract.test.cjs
python manage.py test --settings=test_settings \
  storefront.tests.test_ig_checkout_view -v 1
```

Expected: FAIL because the ring, dialog, help band, and legal route hooks are missing.

- [ ] **Step 3: Add semantic template structure**

The rail must follow this structure:

```html
<div class="ig-payment-rail" data-payment-rail>
  <div class="ig-payment-rail__amount" data-payment-amount>...</div>
  <button class="ig-action ig-action--pay" data-payment-submit>
    <span data-action-label>{{ copy.pay }}</span><span aria-hidden="true">→</span>
  </button>
  <p class="ig-payment-rail__trust" data-payment-trust>{{ copy.secure_payment }}</p>
</div>
```

Add a native `<dialog>` with a heading, description, `Залишитися`, and a confirmed navigation action. Legal links use `target="_blank"`; catalog/home links use `data-checkout-exit`.

- [ ] **Step 4: Run markup tests and commit**

```bash
node --test tests/instagram-checkout-ui-contract.test.cjs
python manage.py test --settings=test_settings storefront.tests.test_ig_checkout_view -v 1
git add tests/instagram-checkout-ui-contract.test.cjs \
  twocomms/storefront/tests/test_ig_checkout_view.py \
  twocomms/storefront/views/ig_checkout.py \
  twocomms/twocomms_django_theme/templates/pages/ig_checkout.html
git commit -m "feat(ig): render C3 checkout payment controls"
```

### Task 4: Implement Recoverable Client Validation and Promo Focus

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/js/instagram-checkout.js`
- Modify: `tests/instagram-checkout-ui-contract.test.cjs`
- Test: `twocomms/storefront/tests/test_ig_checkout_view.py`

- [ ] **Step 1: Add failing behavior/source contracts**

Require functions/hooks for first-invalid recovery, promo disclosure, and safe messages:

```javascript
assert.match(script, /focusFirstInvalid/);
assert.match(script, /scrollMarginBottom/);
assert.match(script, /promo.*open/is);
assert.match(script, /paymentErrorMessage/);
assert.doesNotMatch(script, /errorBox\.textContent\s*=\s*(payload|error)\.(message|stack)/);
```

- [ ] **Step 2: Run and verify RED**

```bash
node --test tests/instagram-checkout-ui-contract.test.cjs
```

Expected: FAIL because validation currently reports without focusing the actual field.

- [ ] **Step 3: Implement the focused recovery helper**

```javascript
const focusFirstInvalid = (fieldName = "") => {
  const field = fieldName ? form.elements.namedItem(fieldName) : form.querySelector(":invalid");
  if (!(field instanceof HTMLElement)) return;
  field.closest("details")?.setAttribute("open", "");
  field.setAttribute("aria-invalid", "true");
  field.style.scrollMarginBottom = `${(paymentRail?.offsetHeight || 0) + 24}px`;
  field.scrollIntoView({block: "center", behavior: prefersReducedMotion ? "auto" : "smooth"});
  window.setTimeout(() => field.focus({preventScroll: true}), prefersReducedMotion ? 0 : 220);
};
```

Use public error codes to map server failures. If a promo error occurs, open the disclosure and focus `promo_code`. Do not show a promo success state before a successful server response.

- [ ] **Step 4: Run UI and form regression suites and commit**

```bash
node --test tests/instagram-checkout-ui-contract.test.cjs
python manage.py test --settings=test_settings \
  storefront.tests.test_ig_checkout_view \
  storefront.tests.test_nova_poshta_checkout_validation -v 1
git add tests/instagram-checkout-ui-contract.test.cjs \
  twocomms/twocomms_django_theme/static/js/instagram-checkout.js
git commit -m "fix(ig): focus assisted checkout validation errors"
```

### Task 5: Implement the Real-Time Countdown and Honest Expired State

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/js/instagram-checkout.js`
- Modify: `twocomms/twocomms_django_theme/static/css/instagram-checkout.css`
- Modify: `tests/instagram-checkout-ui-contract.test.cjs`

- [ ] **Step 1: Add failing countdown contracts**

```javascript
assert.match(script, /1000/);
assert.match(script, /--countdown-progress/);
assert.match(script, /paymentButton\.disabled\s*=\s*true/);
assert.match(css, /conic-gradient/);
assert.match(css, /is-expiring/);
assert.match(css, /is-expired/);
```

- [ ] **Step 2: Run and verify RED**

```bash
node --test tests/instagram-checkout-ui-contract.test.cjs
```

Expected: FAIL because the old timer updates only every 30 seconds and does not disable payment.

- [ ] **Step 3: Render exact remaining time and disable at zero**

Compute progress from `data-created-at` and `data-expires-at`; never reset it from page load:

```javascript
const duration = Math.max(1, expiresAt - createdAt);
const remaining = Math.max(0, expiresAt - Date.now());
root.style.setProperty("--countdown-progress", `${(remaining / duration) * 360}deg`);
countdown.textContent = `${String(minutes).padStart("2", "0")}:${String(seconds).padStart("2", "0")}`;
if (remaining <= 0) expireCheckout();
```

`expireCheckout()` disables the form and CTA, adds `is-expired`, updates an `aria-live` status, and exposes the Direct replacement action. The server remains authoritative on submit.

- [ ] **Step 4: Run contract tests and commit**

```bash
node --test tests/instagram-checkout-ui-contract.test.cjs
git add tests/instagram-checkout-ui-contract.test.cjs \
  twocomms/twocomms_django_theme/static/js/instagram-checkout.js \
  twocomms/twocomms_django_theme/static/css/instagram-checkout.css
git commit -m "feat(ig): show exact proposal countdown"
```

### Task 6: Finish the C3 Visual System and Purposeful Motion

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/css/instagram-checkout.css`
- Modify: `twocomms/twocomms_django_theme/templates/pages/ig_checkout.html`
- Modify: `tests/instagram-checkout-ui-contract.test.cjs`

- [ ] **Step 1: Add failing CSS contracts**

Assert fixed rail tracks, 44 px targets, safe-area spacing, field focus/error offsets, one-shot sheen, and reduced-motion override:

```javascript
assert.match(css, /grid-template-columns:[^;]*minmax/);
assert.match(css, /env\(safe-area-inset-bottom\)/);
assert.match(css, /@keyframes ig-rail-sheen/);
assert.match(css, /prefers-reduced-motion:s*reduce/);
assert.doesNotMatch(css, /animation[^;]*(infinite)/);
```

- [ ] **Step 2: Run and verify RED**

```bash
node --test tests/instagram-checkout-ui-contract.test.cjs
```

Expected: FAIL on the new rail sheen/countdown layout contract.

- [ ] **Step 3: Implement the approved C3 styling**

Use one broad integrated warm radial light, deep charcoal rather than pure black, off-white text, warm accent, stable 8 px-or-less radii, and no nested cards. Add the one-shot sheen only when JS applies `is-payment-ready`; never use infinite animation.

```css
.ig-payment-rail.is-payment-ready .ig-action--pay::after {
  animation: ig-rail-sheen 620ms ease-out 1;
}
@media (prefers-reduced-motion: reduce) {
  .ig-payment-rail.is-payment-ready .ig-action--pay::after { animation: none; }
}
```

At mobile sizes the rail stays above `safe-area-inset-bottom`; at 960 px it becomes a sticky in-column panel. Long prices and translations must not resize the button track.

- [ ] **Step 4: Run UI contract tests and commit**

```bash
node --test tests/instagram-checkout-ui-contract.test.cjs
git add tests/instagram-checkout-ui-contract.test.cjs \
  twocomms/twocomms_django_theme/templates/pages/ig_checkout.html \
  twocomms/twocomms_django_theme/static/css/instagram-checkout.css
git commit -m "feat(ig): polish C3 assisted checkout rail"
```

### Task 7: Verify Receipt, Promo, Payment, and MariaDB Contracts Together

**Files:**
- Verify: `twocomms/orders/email_receipt.py`
- Verify: `twocomms/orders/promo_reservations.py`
- Verify: `twocomms/orders/payment_attempts.py`
- Verify: `twocomms/storefront/migrations/0087_promocodegroup_innodb.py`
- Test: `twocomms/orders/tests/test_promo_atomicity.py`
- Test: `twocomms/orders/tests/test_post_payment_recovery.py`

- [ ] **Step 1: Run the focused integration suite**

```bash
python manage.py test --settings=test_settings \
  management.tests_ig_checkout_models \
  management.tests_ig_paylink_fix \
  management.tests_ig_lifecycle \
  orders.tests.test_payment_attempts \
  orders.tests.test_promo_atomicity \
  orders.tests.test_post_payment_recovery \
  storefront.tests.test_ig_checkout_view \
  storefront.tests.test_nova_poshta_checkout_validation \
  storefront.tests.test_analytics_loader -v 1
```

Expected: all pass, with only the documented migration-trigger skip if still applicable.

- [ ] **Step 2: Verify MariaDB-oriented schema properties without mutating production**

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py sqlmigrate storefront 0087
```

Inspect SQL for explicit InnoDB conversion and compatible relationships. Do not treat syncdb SQLite trigger behavior as production evidence.

- [ ] **Step 3: Verify receipt reuse and no duplicate financial path**

Confirm tests prove assisted orders call `orders.email_receipt.send_order_receipt_email()` and the standard receipt template after verified payment, while promo validation uses one atomic reservation and PaymentAttempt materializes one Order.

- [ ] **Step 4: Commit only if verification exposes a tested defect**

Any fix follows a new failing test and a narrow commit. Otherwise record evidence in the checklist without code churn.

### Task 8: Browser QA Across Mobile, Desktop, States, and Accessibility

**Files:**
- Modify: `docs/plans/2026-07-30-instagram-assisted-checkout-checklist.md`
- Remove before commit: `.playwright-cli/`, `twocomms/twocomms/ig_browser_settings.py`, browser SQLite artifacts

- [ ] **Step 1: Start the isolated fixture server**

Run with a non-production test database/config and no external sends. Use an available localhost port and seed only synthetic proposal/product data.

- [ ] **Step 2: Capture and inspect five target viewports**

Use Playwright at `320x568`, `375x812`, `430x932`, `768x1024`, and `1440x900`. Verify pixel output is nonblank and product imagery, form, rail, countdown, and footer do not overlap or overflow.

- [ ] **Step 3: Exercise the full ready-state interaction path**

Verify:

- empty submit focuses full name above the rail;
- missing/blank email remains valid, while invalid non-empty email shows a
  localized field error without losing values or calling the provider;
- typed-only Nova Poshta city/office is rejected; signed selections pass;
- invalid promo opens its disclosure and focuses the input;
- share copies a bounded clean URL and preserves the current form;
- main-site exit shows the dialog, cancel returns focus, confirm navigates;
- legal links open a new tab and preserve the checkout;
- countdown reaches honest expired UI and prevents a provider request;
- reduced motion removes smooth scrolling and sheen;
- no raw token or PII appears in visible URL, analytics payloads, or console.

- [ ] **Step 4: Exercise every terminal state**

Capture ready, locked, pending, paid, failed, expired, unavailable, superseded, cancelled, and cancellation-ambiguous states. Verify no terminal state exposes an active-looking payment button.

- [ ] **Step 5: Run static and full scoped verification**

```bash
node --test tests/instagram-checkout-ui-contract.test.cjs
python manage.py check
python manage.py makemigrations --check --dry-run
python -m compileall management orders storefront
git diff --check
```

- [ ] **Step 6: Update evidence and clean temporary artifacts**

Record commands, pass counts, viewport/state evidence, and any deliberate skip in the authoritative checklist. Remove test-only settings, SQLite files, screenshot caches, and stop every local server/session.

- [ ] **Step 7: Prepare scoped final commit**

```bash
git status --short
git diff --name-only
git add docs/plans/2026-07-30-instagram-assisted-checkout-checklist.md \
  docs/superpowers/plans/2026-08-01-instagram-assisted-checkout-c3-refresh.md \
  tests/instagram-checkout-ui-contract.test.cjs \
  twocomms/management/ig_bot_models.py \
  twocomms/management/services/ig_checkout_payment.py \
  twocomms/management/services/instagram_bot.py \
  twocomms/management/bot_knowledge/brand.md \
  twocomms/management/tests_ig_checkout_models.py \
  twocomms/management/tests_ig_paylink_fix.py \
  twocomms/storefront/tests/test_ig_checkout_view.py \
  twocomms/storefront/views/ig_checkout.py \
  twocomms/twocomms_django_theme/templates/pages/ig_checkout.html \
  twocomms/twocomms_django_theme/static/css/instagram-checkout.css \
  twocomms/twocomms_django_theme/static/js/instagram-checkout.js
git diff --cached --check
git commit -m "feat(ig): finish mobile assisted checkout"
```

Do not push or deploy. Report the exact HEAD, commit list, tests, migration leaf, dirty files, and preferred integration order with the separate P0 commits.

## Completion Gate

All eight tasks must be checked in the acceptance checklist. Completion requires fresh automated and browser evidence, not the existence of code. Any unresolved UI overlap, lost form data, misleading promo state, provider call after expiry, receipt-path divergence, MariaDB migration incompatibility, raw error leakage, or active payment affordance in a terminal state keeps the task open.
