# Conversion and Overlay Localization Audit

## Scope and status

- **Owner:** conversion, checkout, account, modal, toast, PWA, and offline
  surfaces.
- **Audited:** public UA, EN, and RU storefront routes, with source inspection
  and live browser checks on desktop and `390x844` mobile.
- **Production evidence:** live HTTPS DOM/network behavior was checked for UA,
  EN, and RU cart/catalog flows on desktop and `390x844` mobile. Production
  MariaDB was queried read-only for schema and order/payment-attempt counters;
  no translation, product, order, or payment-attempt content write was
  performed, and no local SQLite content was promoted. The separately recorded
  `storefront.0097` schema migration is not a content-translation claim.
- **Admin:** excluded by design.
- **Implementation:** Task 3 is source-complete, independently reviewed, and
  live-confirmed for CONV-P0-01 through CONV-P0-04 and CONV-P1-04. The initial
  matrix ran on `f239538c6`; final post-fix evidence runs through `3de4c6a7d`.
  The remaining PWA, Telegram, account, offline, and helper packages are not
  claimed complete.

## Executive summary

This workstream contains **14 independently testable work packages**:

| Priority | Work packages | Source-complete | Live-confirmed | Main risk |
| --- | ---: | ---: | ---: | --- |
| P0 | 7 | 4 | 4 | A shopper can reach a mixed-language PWA or Telegram/login flow. |
| P1 | 5 | 1 | 1 | High-visibility prompts and account actions switch back to Ukrainian. |
| P2 | 2 | 0 | 0 | Offline and helper states are inconsistent or locale-blind. |

The highest-value fixes are (1) locale-aware cart and mini-cart requests, (2)
all cart/Monobank dynamic copy and error paths, (3) PWA/push prompts, and (4)
Telegram verification. The server-rendered cart already has many `{% trans %}`
calls, but blank EN/RU `msgstr` values and later JavaScript overwrites make a
template-only fix insufficient.

## P0 findings

### CONV-P0-01: Cart server copy is mixed-language after render

- **Release status:** Live-confirmed on `f239538c6` for UA/RU/EN desktop and
  mobile cart loads, synchronized empty-cart state, and promo-vault SSR copy.

- **Routes/locales:** `/en/cart/`, `/ru/cart/`; authenticated and guest forms;
  desktop and `390x844`.
- **Live evidence:** the EN and RU cart snapshots show Ukrainian empty-cart,
  payment, promo, consultation, phone, and checkout controls after the cart
  page synchronizes. The same state is visible on mobile, where these controls
  are part of the primary conversion viewport.
- **Source:** [`cart.html`](../twocomms/twocomms_django_theme/templates/pages/cart.html)
  uses translatable strings around lines 407-518, 548-725, 729-752, and
  956-980. EN has blank entries for `Ваш номер телефону`, the payment method
  title/description, the manager help text, `Оплатити онлайн`, and `Картка` at
  [`django.po`](../twocomms/locale/en/LC_MESSAGES/django.po) lines
  11809-11825, 11851-11862, 11889-11894, and 12006-12015. RU has the same
  blank entries at lines 11853-11869, 11895-11906, 11933-11938, and
  12052-12061.
- **Why it matters:** payment method, delivery contact, and submit controls
  are conversion-critical, and users can no longer tell which language is
  active. Cart pages are `noindex`, but the UX and accessibility impact is P0.
- **Fix shape:** complete the EN/RU catalogs for every cart msgid, compile the
  catalogs, and add a rendered cart assertion for both authenticated and guest
  forms. Do not replace the source Ukrainian msgids; preserve the gettext
  contract.
- **Verification:** fresh cart load followed by cart-summary synchronization;
  assert no Ukrainian visible text in EN/RU, including payment, promo, custom
  moderation, phone hint, manager CTA, and Monobank status.
- **Classification:** code/gettext; no database dependency.

### CONV-P0-02: Cart JavaScript re-renders Ukrainian copy and currency

- **Release status:** Live-confirmed on `f239538c6` for the locale payload,
  empty-cart/payment copy, UAH formatting, mocked promo apply/remove mutation,
  and desktop/mobile overflow/error checks. Populated authenticated-cart edge
  cases remain covered by the focused regression suite and are not a DB-content
  claim.

- **Routes/locales:** every localized cart route, especially after add, remove,
  quantity change, payment-method change, promo application, or an empty-cart
  transition.
- **Source:** [`cart.js`](../twocomms/twocomms_django_theme/static/js/modules/cart.js)
  hard-codes the empty-cart template and CTA at lines 9-24, formats every
  amount with `toLocaleString('uk-UA')` and `грн` at lines 50-57, and replaces
  payment CTA text with Ukrainian at lines 207-225. Additional fallback and
  error paths occur around lines 321-552, 558-714, 800-843, 908-1065.
  Defaults for `itemsEndpoint`, `summaryEndpoint`, and `contactUrl` at lines
  136-138 are also root-relative.
- **Live/source distinction:** the live mixed cart state is reproduced after
  the client sync; this is separate from the blank gettext entries in
  `CONV-P0-01`.
- **Fix shape:** expose one structured locale payload from the cart template
  (strings, locale, currency label, and locale-aware fallback URLs), use it for
  every dynamic branch, and format amounts with the selected storefront locale.
  Keep numeric values server-authoritative.
- **Verification:** DOM assertions after each mutation (add, remove, qty +/-,
  empty, custom moderation, full payment, prepayment, and failed request) on
  UA/RU/EN desktop and mobile. Confirm links stay in the active locale.
- **Classification:** JavaScript/template; no database dependency.

### CONV-P0-03: Mini-cart AJAX drops the locale prefix

- **Release status:** Live-confirmed on `f239538c6`; `/cart/mini/` was fetched
  through the locale payload on all three locales and both viewports, returned
  `200`, and rendered the matching empty-state language.

- **Routes/locales:** EN/RU pages with a header mini-cart, including catalog,
  PDP, and cart transitions.
- **Live evidence:** EN/RU browser performance logs show a request to
  `https://twocomms.shop/cart/mini/`; that response is Ukrainian. The same
  fragment is correctly localized when requested directly as
  `/en/cart/mini/` or `/ru/cart/mini/`.
- **Source:** [`main.js`](../twocomms/twocomms_django_theme/static/js/main.js)
  line 976 calls `fetch('/cart/mini/')`; the quantity update at lines 1057-1061
  similarly calls `/cart/update/`. The storefront routes are wrapped by
  `i18n_patterns` in [`urls.py`](../twocomms/twocomms/urls.py) lines 125-131.
  [`mini_cart.html`](../twocomms/twocomms_django_theme/templates/partials/mini_cart.html)
  is already translatable, so the immediate defect is the request URL.
- **Fix shape:** render the mini-cart and update endpoint URLs through `{% url
  %}` data attributes or a locale config object and read them in `main.js`.
  Never derive a localized endpoint by string concatenation in JavaScript.
- **Verification:** assert the request URL remains `/en/...` or `/ru/...` and
  that the returned fragment has the matching language after add, remove, and
  quantity changes. Include a direct regression for root-route prevention.
- **Classification:** JavaScript/template routing; no database dependency.

### CONV-P0-04: Checkout and Monobank requests/errors are locale-blind

- **Release status:** Live-confirmed on `f239538c6` for locale-prefixed invoice
  endpoints and safe empty-cart `400 cart_empty` responses in UA/RU/EN, plus
  mocked promo/provider paths. Post-fix SHA `3de4c6a7d` also returns the exact
  localized missing-order message on UA/RU/EN and redirects to the matching
  cart locale. No real invoice or payment event was created.

- **Routes/locales:** cart online payment and quick custom/cart checkout on EN
  and RU routes.
- **Source:** [`checkout-mono.js`](../twocomms/twocomms_django_theme/static/js/modules/checkout-mono.js)
  posts to `/cart/add/` (line 162), `/cart/monobank/quick/` (lines 220 and
  272), and `/cart/monobank/create-invoice/` (line 461). Client fallbacks and
  validation messages are Ukrainian around lines 172-178, 495-501, and
  536-545. [`monobank.py`](../twocomms/storefront/views/monobank.py) returns
  raw Ukrainian JSON errors at lines 605-713 and 861, including empty cart,
  profile, delivery, payment-type, phone, unavailable variant, and provider
  failures.
- **User impact:** even if the surrounding cart is translated, a failed
  payment or validation state switches language at the exact point where trust
  and completion are most sensitive.
- **Fix shape:** pass localized endpoint URLs and a locale-aware error map to
  the module; translate backend messages with Django gettext before serializing
  JSON (or return stable error codes plus localized client messages). Preserve
  payment semantics and never translate monetary values by string replacement.
- **Verification:** mocked 400/401/502 responses and field-validation failures
  for UA/RU/EN; assert status text, focus behavior, and retry controls. Do not
  create real Monobank invoices or send live payment events.
- **Classification:** backend + JavaScript; production DB is not required for
  the copy fix.

#### 2026-08-19 implementation note: quick Checkout response boundary

- Runtime resolution showed that `monobank_quick_invoice` still dispatched to
  the redirect-only `legacy_stubs.monobank_create_checkout`; the implementation
  in `views.py.backup` was not listed in `_LEGACY_VIEW_NAMES` and therefore was
  never installed into the public route.
- The local Task 3 slice now activates the existing Checkout implementation,
  returns JSON with stable error codes, translates validation and payment
  errors through gettext, and prevents Monobank/provider diagnostics from
  entering the response body. Payment/order semantics were not redesigned.
- Added focused EN/RU regressions for empty-cart JSON dispatch and mocked
  provider failure, plus a locale-aware fallback assertion for the CAPI
  checkout source URL. These checks use no live invoice, order, analytics
  event, or production data.
- **State:** source-complete, independently reviewed, deployed, and
  live-confirmed. Missing-reference return probes ended on `/cart/`,
  `/en/cart/`, and `/ru/cart/` with the reviewed UA/EN/RU message respectively;
  no payment reference, invoice, or payment event was created.

### CONV-P0-05: PWA install prompt is always Ukrainian

- **Routes/locales:** any public route that receives `beforeinstallprompt`,
  confirmed on `/en/` with a synthetic install event.
- **Live evidence:** the EN synthetic prompt rendered `Встановити TwoComms як
  застосунок?`, Ukrainian body copy, and `Пізніше`/`Встановити` actions.
- **Source:** [`pwa-install.js`](../twocomms/twocomms_django_theme/static/js/modules/pwa-install.js)
  builds the prompt at lines 229-254 and is globally imported from
  [`main.js`](../twocomms/twocomms_django_theme/static/js/main.js) lines 20-29.
  The prompt has no locale payload or gettext boundary.
- **Fix shape:** provide translated prompt strings from the localized base
  template/config payload, with a safe English fallback only when locale data
  is unavailable. Keep install event handling and dismissal persistence
  unchanged.
- **Verification:** synthetic `beforeinstallprompt` on UA/RU/EN desktop and
  mobile; assert title, body, buttons, accessible labels, and no language
  fallback after dismiss/reopen.
- **Classification:** template/JavaScript; no database dependency.

### CONV-P0-06: Telegram verification overwrites localized modal copy and loses locale on API/redirects

- **Routes/locales:** login/register, mini-profile login, profile linking, and
  restock notification flows on EN/RU.
- **Source:** [`telegram-verify.js`](../twocomms/twocomms_django_theme/static/js/telegram-verify.js)
  uses root-relative endpoints at lines 23-26 and root-relative profile
  fallback redirects around lines 306-311 and 566-574. Its runtime labels,
  success/error notifications, and full modal markup are Ukrainian around
  lines 313-336 and 447-530. The initial template can be localized, but the JS
  mount replaces it. [`telegram_verify_views.py`](../twocomms/accounts/telegram_verify_views.py)
  returns raw Ukrainian errors at lines 180-207 and 220-234. Login/register
  templates have Ukrainian fallback alerts at `auth_login.html:105-107` and
  `auth_register.html:126-128`.
- **User impact:** a shopper selecting EN/RU sees a mixed modal and may be
  redirected to an unprefixed profile/cart route after successful verification.
- **Fix shape:** pass localized labels and endpoint/redirect URLs from the
  page payload; localize backend JSON by stable error code or gettext; use the
  current locale when constructing `next` and fallback profile URLs. Keep
  manager/admin-only purposes out of the public-language surface where
  applicable.
- **Verification:** mocked start/status/cancel/complete states (success,
  expired, unauthorized, provider unavailable, copy-link failure) on all three
  locales; assert modal text, alerts, and final URL prefix.
- **Classification:** backend + JavaScript/template; no product DB dependency.

### CONV-P0-07: Cart, payment, and account fallbacks contain unscoped root URLs

- **Source:** besides the dedicated defects above, `cart.js` falls back to
  `/cart/...`, `checkout-mono.js` posts to root `/cart/...`, favorites and
  Telegram use root account URLs, and auth templates default to
  `/profile/setup/`. These paths bypass `i18n_patterns` even when the initial
  page was localized.
- **Fix shape:** centralize public locale-aware URL generation in the page
  context and forbid root-relative storefront/API URL literals in localized
  modules. API endpoints that intentionally remain unprefixed must be
  explicitly documented and return locale-aware copy.
- **Verification:** static scan for root-relative public endpoints plus browser
  network assertions for EN/RU conversion journeys.
- **Classification:** routing contract; cross-cutting P0 because it can undo
  otherwise correct translations.

## P1 findings

### CONV-P1-01: Web-push prompts and retry/profile UI are Ukrainian

- **Routes/locales:** global home/catalog/cart/order-success prompts and manual
  profile settings.
- **Live/source evidence:** EN DOM contains the push config and visible or
  mounted overlay candidates. [`web-push.js`](../twocomms/twocomms_django_theme/static/js/modules/web-push.js)
  hard-codes prompt copy for order-success/cart/manual/default at lines 473-510,
  iOS install and retry states at lines 538-604, and notifications/errors at
  lines 716-775 and 867-1025. [`context_processors.py`](../twocomms/storefront/context_processors.py)
  already emits `web_push_config` at lines 152-181, so localized copy belongs
  in that payload rather than another hard-coded language table.
- **Additional bug:** `hasBlockingOverlay()` at lines 630-635 treats every
  `[aria-modal="true"]` node as open, including hidden mobile mini-cart,
  language suggestion, and Telegram nodes. This can suppress or surface a push
  prompt at the wrong time.
- **Fix shape:** add locale-scoped copy for default/cart/order/manual/iOS/retry
  states to `web_push_config`; check visibility (`hidden`, computed display,
  and open classes) in the overlay guard; keep browser permission semantics
  unchanged.
- **Verification:** EN/RU/UA manual, cart, order-success, iOS, retry, and
  denied-permission flows at desktop/mobile; assert no prompt over an actually
  open modal and no Ukrainian copy on EN/RU.
- **Classification:** context processor + JavaScript; no database dependency.

### CONV-P1-02: Favorites requests/toasts lose locale and fall back to Ukrainian

- **Source:** [`favorites.js`](../twocomms/twocomms_django_theme/static/js/modules/favorites.js)
  posts/checks root `/favorites/...` at lines 72 and 151. Error fallback
  messages are Ukrainian at lines 137-143; server `data.message` is not
  guaranteed to be localized when the root endpoint is used.
- **Fix shape:** use localized endpoint URLs and a localized fallback map;
  preserve the server message when it carries the selected locale. Do not use a
  live favorite toggle as a test because it mutates production user state.
- **Verification:** mocked success/error/network failures on EN/RU/UA, plus a
  network assertion that no locale-aware page calls the root endpoint.
- **Classification:** JavaScript/routing; no database copy change.

### CONV-P1-03: Survey modal dates, errors, and login return are locale-blind

- **Source:** [`survey.js`](../twocomms/twocomms_django_theme/static/js/modules/survey.js)
  formats expiry dates with `uk-UA` at lines 5-12, has Ukrainian fallback
  labels/errors around lines 23, 92-104, 186-193, 258, 271, 409, 432-433,
  518, and 549, and sends Telegram login to `next: '/cart/'` at line 285.
  The homepage template emits `data-login-url="{% url 'login' %}?next=/cart/"`
  at [`index.html`](../twocomms/twocomms_django_theme/templates/pages/index.html)
  line 833, so EN/RU survey completion can return to the Ukrainian cart.
- **Fix shape:** supply all survey UI strings and `Intl.DateTimeFormat` locale
  from the template payload; generate a locale-prefixed cart return URL.
- **Verification:** mocked survey load/submit/auth/copy states on all locales,
  including expiry rendering and login return URL.
- **Classification:** JavaScript/template; no database dependency for UI copy.

### CONV-P1-04: Global `ui-fallback.js` can overwrite the cart with Ukrainian

- **Release status:** Live-confirmed on `f239538c6` as part of the same cart
  synchronization and mutation matrix; no cross-locale fallback copy or
  visible overflow/errors appeared on the tested desktop/mobile surfaces.

- **Source:** [`base.html`](../twocomms/twocomms_django_theme/templates/base.html)
  loads `ui-fallback.js` globally at lines 1388-1395. The fallback contains a
  second hard-coded empty-cart renderer at lines 175-183, Ukrainian clean-cart
  confirmation at lines 308-325, and Ukrainian add/error alerts around lines
  428-433. It can run after the primary module and mask a correct translation.
- **Fix shape:** remove duplicate user-facing literals from the fallback,
  consume the same locale payload as `cart.js`, and keep the helper limited to
  behavior that cannot render visible copy.
- **Verification:** disable/late-load the primary cart module in a test harness
  and assert the fallback still renders the selected locale; test clear-cart,
  add failure, and empty-cart paths.
- **Classification:** JavaScript/template; no database dependency.

### CONV-P1-05: Mini-profile account chrome has blank EN/RU translations

- **Source:** [`mini_profile.html`](../twocomms/twocomms_django_theme/templates/partials/mini_profile.html)
  line 114 displays `Бали • замовлення • обране`. EN and RU gettext entries are
  blank at `django.po:16430-16431` and `16484-16485` respectively.
- **Fix shape:** add reviewed EN/RU translations and compile catalogs. Keep
  points/order/favorites terminology consistent with the account pages and SEO
  vocabulary.
- **Verification:** open the header/profile menu on desktop and mobile for all
  locales; assert the account summary is never Ukrainian on EN/RU.
- **Classification:** gettext/template; no database dependency.

## P2 findings

### CONV-P2-01: Offline fallback is a single Ukrainian page and loses locale

- **Routes/locales:** service-worker navigation fallback for any public locale.
- **Source:** [`sw.js`](../twocomms/static/sw.js) caches one
  `/static/offline.html` at lines 1-15 and serves it on navigation failures at
  lines 197-213. [`offline.html`](../twocomms/twocomms_django_theme/static/offline.html)
  declares `lang="uk"` and Ukrainian title/body/actions at lines 1-7 and
  146-159, with a root `/` home link at line 155.
- **Fix shape:** choose a locale-aware offline resource (or inject the last
  known locale into a safe static shell) and preserve the locale on the home
  link. Do not cache cart, checkout, or personal data.
- **Verification:** offline navigation from UA/RU/EN pages on desktop/mobile;
  assert language, retry action, and locale-preserving home link.
- **Classification:** service worker/static asset; no database dependency.

### CONV-P2-02: Phone normalizer hints expose Ukrainian text on non-UA checkout

- **Source:** [`phone.js`](../twocomms/twocomms_django_theme/static/js/modules/phone.js)
  contains Ukrainian default and transformation hints at lines 1-118. The
  cart currently hides some hints in CSS, but checkout validation can still
  expose them through `syncUkraineCheckoutPhoneHint`.
- **Fix shape:** keep the Ukrainian-number normalization rules, but move all
  user-facing hints into the locale payload and explicitly state the Ukrainian
  Nova Poshta requirement in each language.
- **Verification:** valid/invalid phone input on UA/RU/EN cart and Monobank
  paths, including mobile keyboard/error states.
- **Classification:** JavaScript copy; no database dependency.

## Reviewed and intentionally not duplicated

- [`nova-poshta-selector.js`](../twocomms/twocomms_django_theme/static/js/modules/nova-poshta-selector.js)
  already has UA/RU/EN labels and localized selector states. Re-test it as part
  of the cart batch, but do not create a second translation implementation.
- [`language-suggestion.js`](../twocomms/twocomms_django_theme/static/js/modules/language-suggestion.js)
  already selects EN/RU-aware copy. Its hidden DOM nodes are relevant to the
  web-push overlay guard, not a separate translation finding.
- Product descriptions, titles, fit/color notes, and other database-owned copy
  remain in the deferred production-MariaDB workstream. This report does not
  claim that local or live product records are complete.

## Proposed regression matrix

1. **Locale/device matrix:** UA, RU, EN at desktop and `390x844` mobile; assert
   `<html lang>`, visible text, endpoint prefixes, and return URLs.
2. **Cart initial/sync:** empty and populated cart before and after JS sync;
   mini-cart request, cart summary, add/remove/quantity, promo apply/remove,
   custom moderation, full payment, and prepayment states.
3. **Payment/error matrix:** mocked Monobank 400, 401, 502, invalid phone,
   invalid delivery, unavailable variant, and provider retry; assert localized
   status and no real invoice/event.
4. **PWA/push:** synthetic install event; push default/cart/order/manual/iOS/
   retry/denied states; hidden modal and visible modal overlay-guard cases.
5. **Telegram/auth:** mocked start/status/cancel/complete success, expiry,
   unauthorized, provider failure, copy-link failure, and locale-preserving
   login/profile redirects.
6. **Fallbacks:** favorites success/error/network toasts, survey load/submit/
   auth/expiry/copy states, global UI fallback, offline service-worker shell,
   and phone validation hints.
7. **Static/source checks:** fail CI for new user-facing Ukrainian literals in
   localized modules and for unannotated root-relative storefront endpoints.

## Implementation order and tally

1. **Batch A (P0):** CONV-P0-01 through CONV-P0-07; add locale payload and
   endpoint helpers first, then cart/payment/Telegram/PWA copy and tests.
2. **Batch B (P1):** CONV-P1-01 through CONV-P1-05; reuse the same payload and
   overlay visibility helper.
3. **Batch C (P2):** CONV-P2-01 and CONV-P2-02; verify service-worker behavior
   and helper copy after conversion paths are stable.
4. **Deferred data:** production MariaDB report and editorial backfill for
   product-owned titles/descriptions/SEO fields, tracked outside this file.

**Current workstream tally:** `5 / 14 source-complete (35.7%)`; `5 / 14`
live-confirmed. Live-confirmed packages are CONV-P0-01 through CONV-P0-04 and
CONV-P1-04. The fresh cart matrix covered six locale/device combinations;
the mini-cart probe covered another six. Production counters remained
`orders=64`, `payment_attempts=12` after the final safe return probes.

An item may move from `audit-confirmed` to `verified locally` only after a
focused regression test; it may move to `verified live` only after deployment
from `main` and a fresh UA/RU/EN browser check. This batch satisfies that gate
for the five package IDs above. SSH/MariaDB remains authoritative for the
deferred production translation inventory, which is intentionally still open.
