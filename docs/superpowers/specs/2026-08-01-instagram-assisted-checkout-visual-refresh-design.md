# Instagram Assisted Checkout C3 Visual Refresh

**Date:** 2026-08-01  
**Status:** Approved visual direction, implementation contract pending written review  
**Surface:** Personal TwoComms checkout proposal opened from Instagram Direct

## 1. Outcome

The page is a ready-to-pay, first-party checkout for an order already agreed in
Instagram Direct. It is not a landing page and does not recreate the storefront
cart. The page must help a mobile buyer do four things without uncertainty:

1. recognise that the proposal is personal and belongs to TwoComms;
2. verify the exact products, variants, quantity, and fixed price;
3. enter receipt and Nova Poshta delivery details;
4. continue to a Monobank invoice before the proposal expires.

The approved visual direction is **C3 / Brand Night**: a quiet dark TwoComms
surface with restrained warm-gold light, real catalog imagery, compact content,
and a small number of purposeful motion details. It must feel designed and
personal without competing with the payment task.

## 2. Product Principles

- **Mobile first:** the 320-430 px experience defines hierarchy and behavior;
  tablet and desktop expand it without changing the decision path.
- **Personal before administrative:** the first emotional anchor is
  `Вітаємо, {first_name}`. Proposal identifiers and service labels stay quiet.
- **Specific before persuasive:** real products, selected color, fit, size,
  quantity, and total are visible before the form.
- **One primary action:** only `Перейти до оплати` receives primary visual
  emphasis. Share, Direct, catalog, and legal links remain secondary.
- **Truthful trust:** explain what is protected and where card data is entered;
  do not use unexplained locks, fabricated badges, or unsupported guarantees.
- **Motion communicates state:** animation acknowledges page readiness,
  completion, copy, validation, and expiry. It never runs continuously merely
  to attract attention.
- **No dead ends:** every terminal state offers one safe next step, normally
  returning to the existing Instagram Direct conversation.

## 3. Proposal Lifetime

Every new assisted-checkout proposal is valid for **25 minutes from server-side
creation**. The server timestamp is authoritative.

- Bot, page, share grant, share token, inventory/promo reservation, and payment
  creation all use the same proposal deadline.
- A copied link may be paid in another browser, but it does not extend the
  deadline.
- Reopening or refreshing the page does not restart the timer.
- A Monobank invoice may never outlive the proposal deadline.
- The server rechecks expiry inside the payment-creation transaction. A browser
  showing a positive timer does not override server time.
- Once expired, the form and CTA become unavailable and no provider call is
  made. The page offers `Отримати нове посилання в Direct`.
- A verified provider payment that completed before local cleanup remains the
  payment truth; expiry must not overwrite a verified payment.

### Countdown

The ready state includes a fixed-size circular countdown beside the compact
proposal status. It displays `MM:SS` for the full 25-minute window and updates
once per second without resizing surrounding content.

- Neutral/gold ring above five minutes.
- Muted warning color during the final five minutes, without pulsing.
- At zero: `00:00`, expired label, disabled CTA, and an accessible status
  announcement.
- The ring uses CSS progress driven by the server expiry timestamp. It is not a
  decorative canvas and remains readable when CSS animation is unavailable.
- With reduced motion, only the numeric text and static progress update; no
  transition is applied.

## 4. Screen Hierarchy

### 4.1 Brand header

- Use the real `/static/img/logo.svg` mark and quiet `TwoComms` wordmark.
- A secondary catalog/home link is available but does not compete with checkout.
- Opening the catalog/home route triggers the exit-confirmation dialog described
  in section 10.

### 4.2 Personal introduction

- Primary line: `Вітаємо, {first_name}`.
- Supporting line: `Ваше замовлення вже зібране. Перевірте деталі та додайте
  дані для доставки.`
- A compact confirmed-state line communicates `Товари й ціна зафіксовані`.
- Do not lead with `Перевірте замовлення`, a proposal number, an oversized
  security claim, or repeated price labels.

### 4.3 Proposal utility row

The countdown, share action, and proposal status form one compact utility area.
It explains:

- `Посилання діє 25 хвилин від створення`;
- `Можна передати іншій людині для оплати`;
- copying creates/reuses the existing bounded share flow and never exposes the
  raw bot bearer token.

Copy feedback is local and temporary: `Посилання скопійовано`. The action keeps
its dimensions while loading or confirming.

### 4.4 Product list

- Use current catalog images and stable aspect ratios.
- Each item shows title, selected color, fit, size, quantity, unit price when
  useful, and line total.
- One item remains visually strong; multiple items become a calm vertical list,
  not a masonry layout or nested card grid.
- Missing imagery uses the existing fallback without shifting layout.
- Product links may open in a new tab only when the exact catalog product URL is
  trusted. They remain secondary and do not replace the checkout state.

### 4.5 Price summary

- Show item subtotal, negotiated discount when present, validated promo discount
  only after server confirmation, and final payable amount.
- The same payable amount appears in the payment rail; it is not editable in the
  browser.
- `Ціна зафіксована для цієї пропозиції` explains the commercial guarantee
  without implying unlimited duration.

## 5. Delivery Form

The form is a single unframed flow with compact groups and familiar icons.
Required fields are:

- full name with at least first and last name;
- valid Ukrainian telephone number;
- Nova Poshta city selected from a signed result;
- Nova Poshta branch or parcel locker selected from a signed result.

Email copy is explicit and calm:

- label: `Email для чека`;
- optional marker: `Необов'язково`;
- hint: `Якщо вкажете email, надішлемо сюди чек і підтвердження. Без розсилок.`

Email is optional because forgetting or not having access to an address must not
block payment. A blank or whitespace-only value is normalized to an empty
string and omits Monobank `customerEmails`; a non-empty invalid address is
rejected before provider I/O. When present, the address reuses the ordinary cart
receipt path and template. It is never presented as newsletter consent.

Nova Poshta autocomplete must preserve the existing signed-selection contract.
Typing visible city/office text is insufficient: a signed current option must
be selected. City changes clear a previously selected office. Keyboard
navigation, touch targets, loading, empty, and provider-unavailable states are
first-class.

Completed fields receive a quiet check treatment that does not change their
height. Focus uses a warm border and subtle surface lift. Neither state relies
on color alone.

## 6. Validation and Error Recovery

Client validation provides fast guidance; server validation is authoritative.
Submitting an incomplete or invalid form must:

1. keep every valid value already entered;
2. reveal a localized summary near the form heading;
3. mark the first invalid field with `aria-invalid=true` and a field-level
   message;
4. open the promo disclosure when the error belongs to the promo code;
5. scroll the first invalid control to a position above the sticky payment rail;
6. focus that control after scrolling;
7. use immediate scrolling when reduced motion is requested.

The summary uses one helpful sentence such as `Перевірте виділене поле, щоб
продовжити`. It does not duplicate every error or display exception text.

Provider/network failures use stable public error codes mapped to localized
copy. Raw MariaDB, Nova Poshta, Monobank, traceback, response body, token, or
provider exception text must never reach the page.

The CTA enters a stable loading state only after client validation passes. It
cannot be double-submitted. On a recoverable server error, it restores its label
and focus path; on ambiguous invoice creation it does not invite a blind retry.

## 7. Promo Code

Promo remains optional and uses the existing atomic server reservation. The UI
is a compact disclosure, closed by default:

- trigger: `Маєте промокод?`;
- field label: `Промокод`;
- hint: `Перевіримо перед переходом до оплати`.

Opening the disclosure reveals one input. The page must not show `Застосовано`,
change the total, or use a success style before the server validates and
reserves the code during checkout submission.

- Invalid, exhausted, ineligible, account-only, or non-stackable codes return a
  safe localized error and focus the open promo input.
- A server-confirmed discount updates the frozen payment attempt and summary;
  browser arithmetic is never the financial source of truth.
- Promo failure does not erase recipient or delivery data.

## 8. Payment Rail

The bottom rail is the strongest conversion element and must feel like a
purpose-built checkout control rather than a generic black footer.

### Mobile

- Sticky above the safe-area inset and virtual-keyboard-aware.
- Compact payable amount at left: label `До сплати`, value below it.
- Large primary CTA at right: `Перейти до оплати` with a forward arrow.
- No lock icon inside the CTA.
- One full-width trust line below:
  `Дані картки вводяться на захищеній сторінці Monobank`.
- The rail has stable tracks and button dimensions, so price, loading text,
  errors, or timer updates do not move it.
- While a form field is focused and the software keyboard is open, the rail may
  collapse to preserve input visibility, but the current field and error must
  remain reachable.

### Desktop

The rail becomes a quiet sticky payment panel aligned with the form column. It
keeps the same amount -> action -> trust hierarchy and does not become a second
large order summary.

### Motion

One short sheen may run once when the rail first becomes ready or when all
required fields become valid. Duration is 500-700 ms. There is no repeating
shimmer, pulse, bouncing arrow, or permanent glow. Reduced-motion mode removes
the sheen and all positional transitions.

## 9. Direct Help

Below the form, before legal navigation, show a calm help band:

`Щось не так із товаром, розміром, сумою чи доставкою? Напишіть у той самий
Direct — ми оновимо пропозицію або сформуємо нове посилання.`

The action is `Написати в Direct`. The text does not promise that the current
URL can always be changed after invoice creation; safe cancellation or
supersession rules remain authoritative.

## 10. Exit and Legal Navigation

### Main-site exit confirmation

Catalog/home navigation from the checkout opens an accessible confirmation
dialog:

- title: `Залишити оформлення?`;
- body: `Введені дані залишаться на цій сторінці, але час посилання продовжить
  спливати.`;
- primary-safe action: `Залишитися`;
- secondary action: `Перейти на сайт`.

Escape and backdrop close the dialog, focus is trapped while open, and focus
returns to the triggering link. Browser refresh, Monobank redirect, Direct, and
legal links are not intercepted by this dialog.

### Footer

Use existing trusted routes for:

- `Повернення та обмін`;
- `Політика приватності`;
- optionally `Доставка` and `Умови користування` when configured.

Legal routes open in a new tab so the form survives. The footer is one quiet
line/group, not a repeated navigation bar. Direct remains visually easier to
find than legal text.

## 11. Visual System

- Base surfaces: deep neutral charcoal, not pure black.
- Main text: softened off-white, not pure white over large areas.
- Accent: warm TwoComms gold/orange used for focus, countdown progress, CTA,
  and small completion details.
- Supporting accents may include muted green for confirmed state and restrained
  red only for actual validation/terminal errors.
- Background uses one broad, low-contrast warm radial light integrated into the
  page surface. No isolated orbs, bokeh, or decorative blobs.
- Cards, where semantically justified for products, use no more than an 8 px
  radius and do not contain nested cards.
- Typography follows the storefront stack. Display size is reserved for the
  personal greeting; panel headings remain compact with zero letter spacing.
- All icons come from the existing icon system or Lucide when already available;
  no hand-drawn security symbols.

## 12. Localization

Ukrainian is the primary copy. Russian and English must have equivalent meaning,
not word-for-word fragments. All three locales cover:

- greeting and proposal status;
- 25-minute lifetime, share, and expiry;
- field labels, hints, signed Nova Poshta selection, and validation;
- promo disclosure and every stable promo error;
- amount, CTA/loading, and the precise Monobank trust line;
- Direct help and replacement wording;
- exit dialog, returns/exchange, privacy, delivery, and terms;
- ready, locked, pending, paid, failed, expired, unavailable, superseded,
  cancelled, and cancellation-ambiguous states.

No locale may fall back to mojibake, replacement glyphs, or raw internal code.

## 13. Accessibility and Responsive Contract

- No horizontal overflow at 320 x 568, 375 x 812, or 430 x 932.
- Tablet 768 x 1024 and desktop 1440 x 900 preserve the same information order.
- Interactive targets are at least 44 x 44 CSS px.
- Product media, countdown, controls, and payment rail use stable dimensions.
- Form labels are persistent; placeholders are examples, not labels.
- Focus is always visible and never hidden behind the rail.
- Dialog, disclosure, autocomplete, validation summary, countdown expiry, copy
  feedback, and payment state are keyboard and screen-reader operable.
- `prefers-reduced-motion: reduce` disables decorative animation and smooth
  scrolling while retaining state changes.
- Page remains usable at 200% text zoom and with long Ukrainian labels.

## 14. Analytics and Privacy

- View/checkout/purchase events keep the existing consent and server-verification
  boundaries.
- `Purchase` fires only for verified payment and keeps browser/server event ID
  deduplication.
- Opening promo, validation failures, countdown ticks, and legal navigation do
  not create synthetic purchase intent.
- Proposal/share tokens, recipient PII, Nova Poshta signed data, email, phone,
  and provider response bodies are not placed in analytics payloads or URLs.
- The clean proposal URL remains the visible browser URL after grant exchange.

## 15. State Behavior

- **Ready:** full C3 form, timer, share, products, promo, payment rail.
- **Locked:** recipient summary and safe continuation; no silent edits.
- **Pending:** existing invoice continuation/status check, no new invoice CTA.
- **Paid:** receipt/Direct follow-up confirmation, no payment controls.
- **Failed:** safe Direct recovery based on provider truth.
- **Expired:** timer at zero, disabled form/payment, new-link Direct action.
- **Unavailable/revoked:** no product or recipient leakage beyond already-safe
  display rules; Direct recovery.
- **Superseded:** point to the latest Direct message, never guess a new URL.
- **Cancelled:** no payment action; request a replacement in Direct.
- **Cancellation ambiguous:** explicitly prohibit retry until reconciliation.

Every state uses the same brand shell and legal footer. No terminal state leaves
an active-looking payment button.

## 16. Implementation Boundaries

Expected changes stay narrowly within:

- `templates/pages/ig_checkout.html`;
- `static/css/instagram-checkout.css`;
- `static/js/instagram-checkout.js`;
- localized checkout context in `storefront/views/ig_checkout.py`;
- proposal expiry and checkout creation services/tests;
- bot and knowledge copy that states proposal validity;
- current design/implementation/checklist documents and UI contract tests.

Frozen management migrations 0116 and 0117 are not edited. No management schema
change is required for this refresh. Existing PaymentAttempt, promo reservation,
receipt email, analytics, signed Nova Poshta, lifecycle, and reconciliation
contracts are reused rather than duplicated.

## 17. Verification

Implementation is acceptable only after all of the following pass:

- TDD coverage for 25-minute default expiry and boundary submit rejection;
- access/share token and inventory/promo/invoice expiry cap tests;
- bot-copy and locale contract tests with no obsolete duration;
- required-field, optional-email, signed Nova Poshta, promo-focus,
  double-submit, and safe public error tests;
- Node UI contract tests for countdown, rail, dialog, reduced motion, and CSP;
- focused Django checkout, PaymentAttempt, receipt, lifecycle, Pixel/CAPI, and
  analytics suites;
- `manage.py check`, migration drift check, compilation, and diff check;
- MariaDB/InnoDB compatibility verification for affected persistence behavior;
- Playwright screenshots and interaction QA at all five target viewports;
- overflow, focused-field visibility, virtual keyboard, expiry, share, promo,
  exit dialog, terminal states, 200% text, and reduced-motion checks;
- no live Monobank, Meta, TikTok, email, Telegram, or customer Direct test send.

## 18. Acceptance Criteria

The refresh is complete when a mobile buyer can immediately identify the
personal order, verify real products and fixed price, understand the exact
remaining lifetime and share behavior, finish all required delivery fields,
recover from any omission without losing progress, understand promo validation,
and continue through a visually clear CTA to a single server-created Monobank
invoice. The page must remain recognisably TwoComms, honest about security and
expiry, accessible without animation, and free of navigation traps or false
success states.
