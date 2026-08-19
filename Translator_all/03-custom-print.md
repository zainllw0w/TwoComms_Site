# Custom Print Localization Audit

## Scope and Status

- **Owner:** Custom Print configurator, public lead/cart submission paths,
  Telegram verification, preview UI, and Custom Print SEO schema.
- **Audited:** live `/custom-print/`, `/ru/custom-print/`, and
  `/en/custom-print/`; source configuration, templates, client modules, form
  validation, and gettext catalogs.
- **Status:** audit complete. This file records findings only; no application,
  gettext, database, deployment, or production-order change was made.
- **Safety:** no lead was submitted, no cart was changed, and no live payment
  or analytics event was intentionally generated.

## What Already Works

- RU and EN routes return the correct `html[lang]`, translated title/H1, and a
  locale-specific canonical URL.
- `build_custom_print_config()` already generates locale-specific submit,
  safe-exit, and add-to-cart URLs. The localization problem is not the
  endpoint builder itself, but untranslated payload values and separate
  hard-coded client/template strings.

## Confirmed P0 Findings

### CP-P0-01: Post-submit dialog is Ukrainian and sends RU/EN shoppers into Ukrainian routes

- **Locales/routes:** `/ru/custom-print/` and `/en/custom-print/`.
- **Live evidence:** both locale pages render `Заявка вже у менеджера`,
  Ukrainian success copy, `На головну`, `Перейти до кошика`, and
  `Залишитися на сторінці`; the home/cart anchors are `/` and `/cart/`.
- **Source:**
  [`custom_print.html`](../twocomms/twocomms_django_theme/templates/pages/custom_print.html)
  lines 951-964 hard-code the complete dialog and root-relative links.
  [`custom-print-submit-flow.js`](../twocomms/twocomms_django_theme/static/js/custom-print-submit-flow.js)
  also replaces its success state in Ukrainian and forces home/cart defaults.
- **Impact:** a successful conversion confirmation switches language at the
  trust-critical moment and can redirect an RU/EN shopper to the Ukrainian
  storefront.
- **Required fix:** supply translated dialog strings plus locale-aware home/cart
  URLs from the template/configuration; make the submit-flow use those values
  for both lead and cart outcomes.
- **Regression:** simulate lead and cart success on UA/RU/EN, assert dialog
  copy, focus/close behavior, and destination prefixes without submitting a
  real lead or cart item.

### CP-P0-02: Required configurator choices and price/B2B payload stay Ukrainian on RU/EN

- **Locales/routes:** `/ru/custom-print/`, `/en/custom-print/`; all desktop and
  mobile configurator steps.
- **Live evidence:** `#customPrintConfiguratorConfig` on both routes includes
  Ukrainian values for `mode_required`, `product_required`,
  `artwork_service_required`, `artwork_file_required`, and `contact_required`.
  It also includes Ukrainian T-shirt detail notes and all B2B tier labels,
  notes, and quantity hint.
- **Source:**
  [`custom_print_config.py`](../twocomms/storefront/custom_print_config.py)
  lines 23-76 defines `B2B_TIER`, progress labels, and `UI_STRINGS`; lines
  586-658 define T-shirt fit/fabric/thermo data. These values are wrapped in
  gettext, then serialized at lines 1469-1499.
- **Catalog evidence:** the EN and RU `django.po` files have blank `msgstr`
  values for the mandatory `UI_STRINGS` ids, including the ids at PO lines
  4544-4585. The current payload proves this is deployed, not merely a source
  hypothesis.
- **Impact:** a user cannot understand a mandatory decision, error, fabric
  state, or bulk-price tier in their selected language.
- **Required fix:** complete reviewed RU/EN translations for every reachable
  Custom Print config msgid, compile catalogs, and add a payload-level locale
  contract test. Do not duplicate the config strings in JavaScript.
- **Regression:** render the config for UA/RU/EN and assert validation, B2B,
  product/fit/fabric, color, service, and quantity labels are all in the
  selected locale.

### CP-P0-03: Client-side validation and final-action feedback contain reachable Ukrainian fallbacks

- **Locales:** RU and EN configurator interactions, including incomplete
  configuration, upload, manager lead, and add-to-cart paths.
- **Source:**
  [`custom-print-configurator.js`](../twocomms/twocomms_django_theme/static/js/custom-print-configurator.js)
  has reachable Ukrainian fallbacks in manager summaries (503-543), artwork
  validation (1090-1170), B2B brief handling (1200-1280), dynamic option and
  upload UI (1368-2446), final validation/status (3300-3500 and 3680-3760),
  and lead/cart feedback (4440-4620). Examples include failed submission,
  unavailable cart, add-to-cart success, and server-unavailable states.
  [`custom-print-submission-policy.js`](../twocomms/twocomms_django_theme/static/js/custom-print-submission-policy.js)
  lines 31-50 independently produces Ukrainian lead/cart hints.
- **Impact:** translated initial HTML is overwritten after a shopper acts,
  producing a mixed-language or Ukrainian-only conversion flow.
- **Required fix:** make one server-provided locale dictionary the mandatory
  source for dynamic strings; remove user-visible Ukrainian fallbacks from the
  modules or replace them with locale-keyed fallback values. Preserve raw
  numeric/pricing logic.
- **Regression:** DOM-level checks for empty/incomplete form, each artwork
  service, B2B brief, custom garment, upload requirement, network failure,
  successful lead, successful cart, and unavailable cart in UA/RU/EN.

### CP-P0-04: Server form errors are returned raw in Ukrainian

- **Locales/route:** invalid POST to localized Custom Print lead endpoints.
- **Source:**
  [`forms.py`](../twocomms/storefront/forms.py) lines 172-223 and 309-352
  construct validation messages directly in Ukrainian. The lead view at
  [`static_pages.py`](../twocomms/storefront/views/static_pages.py) lines
  1563-1572 serializes them unchanged into JSON.
- **Impact:** client code correctly preserves server validation text, so every
  backend error leaks Ukrainian into RU/EN precisely when a form cannot be
  submitted.
- **Required fix:** wrap form messages with gettext or return stable error
  codes that are localized through the same Custom Print payload. Keep exact
  validation conditions and security error semantics intact.
- **Regression:** test malformed JSON, phone, WhatsApp, Telegram, custom
  placement, brand, custom garment, artwork, unsupported extension, and file
  size errors in all three active locales.

## Confirmed P1 Findings

### CP-P1-01: Telegram verification is dynamically rewritten in Ukrainian

- **Source:**
  [`custom-print-telegram-verify.js`](../twocomms/twocomms_django_theme/static/js/custom-print-telegram-verify.js)
  contains Ukrainian runtime modal status, reset, copy-link success/error, and
  retry copy around lines 243-351 and 392-400. Initial template strings are
  translatable, so the later JavaScript rewrite defeats them.
- **Required fix:** pass a Custom Print Telegram locale dictionary and use
  locale-aware fallback URLs/endpoints where the module leaves the page.
- **Regression:** mock start, polling, verified, expired, cancel, copy-link,
  and provider-error states for UA/RU/EN. Do not contact Telegram in tests.

### CP-P1-02: Preview price format and measurement unit are fixed to Ukrainian

- **Source:**
  [`custom-print-preview.js`](../twocomms/twocomms_django_theme/static/js/custom-print-preview.js)
  uses Ukrainian `см` labels around lines 171/188 and formats price with fixed
  `uk-UA`/`грн` behavior.
- **Impact:** non-UA users see Ukrainian currency/unit presentation even when
  the rest of a step is translated.
- **Required fix:** provide `Intl` locale, currency display label, and unit
  label from the server locale contract.

### CP-P1-03: Dynamic accessibility labels and mobile controls have Ukrainian defaults

- **Source:** reachable client markup in `custom-print-configurator.js` covers
  material modal labels, zone hints, upload state, step labels, toggles, and
  receipt/status UI. These need the same dictionary as P0-03 rather than an
  independent ad-hoc translation table.
- **Impact:** screen-reader labels and smaller mobile-only controls are often
  the first state produced after a choice or an upload.
- **Regression:** inspect accessible names and visible mobile controls at a
  390px viewport through all configurator steps.

### CP-P1-04: Service JSON-LD has a Ukrainian URL on RU/EN pages

- **Live evidence:** the RU/EN Service schema name is translated, but its
  `url` remains `https://twocomms.shop/custom-print/`; it has no `inLanguage`.
- **Source:**
  [`custom_print.html`](../twocomms/twocomms_django_theme/templates/pages/custom_print.html)
  lines 22-38 hard-code the Ukrainian service URL.
- **SEO/GEO impact:** the page canonical is localized while its Service entity
  points at another locale, producing inconsistent ownership signals for
  crawlers.
- **Required fix:** emit the localized canonical URL via the named route and
  add `inLanguage` using the active locale. Keep `areaServed: UA`.
- **Regression:** parse JSON-LD for UA/RU/EN and assert schema URL, canonical,
  language, and breadcrumb owner agree.

## P2 and Deferred Data Work

- The Custom Print long-form content, FAQ, technology headings, and modal
  template text are gettext/code-owned. They must be included in the RU/EN
  gettext completeness pass once P0 behavior is safe; they are not evidence
  that a production database row is missing.
- The PDP-to-Custom Print prefill at
  [`static_pages.py`](../twocomms/storefront/views/static_pages.py) lines
  1532-1545 reads `Product.title` and `slug`. A missing RU/EN product title is
  a separate production-data problem and must not be fabricated in this
  Custom Print patch.
- Custom Print FAQ/configuration content is code/gettext driven. No production
  MariaDB mutation is required to correct the confirmed P0/P1 items above.

## Implementation Order

1. Add a tested Custom Print locale contract for dialog text/URLs, config UI,
   dynamic JS strings, currency/unit formatting, and Telegram status.
2. Fill and compile exact RU/EN gettext entries used by
   `custom_print_config.py` and `custom_print.html`.
3. Replace hard-coded client strings with that contract and localize backend
   JSON validation errors.
4. Correct Service JSON-LD URL/`inLanguage` and add schema assertions.
5. Run the complete UA/RU/EN desktop/mobile regression matrix before staging
   only the scoped Custom Print paths.

## Acceptance Matrix

- All Custom Print states retain the active locale from landing through
  validation, upload, Telegram verification, lead/cart feedback, and success
  dialog.
- Success and cart links remain locale-prefixed on RU/EN.
- No real order, lead, Telegram request, payment event, or analytics event is
  used as a test fixture.
- HTML `lang`, title/H1, canonical, Service JSON-LD, and dynamic visible/ARIA
  strings match for UA/RU/EN.
- Production product title/description completeness remains a separately
  verified MariaDB/editorial backlog.
