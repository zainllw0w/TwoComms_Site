# Storefront Localization P0 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to execute this plan task-by-task.

**Goal:** Remove Ukrainian fallback copy, locale-dropping requests, and false locale ownership from public P0 conversion surfaces while preserving truthful product data and the existing Django i18n architecture.

**Architecture:** A server-owned locale contract supplies active language, `Intl` locale, currency metadata, and page-scoped URLs/copy. Django emits it with `json_script`; JavaScript consumes it rather than hard-coded strings or root-relative storefront URLs. Generic UI copy remains gettext. Product and variant facts remain production-data-owned and fail closed for SEO if a reviewed RU/EN value is absent.

**Tech Stack:** Django 6.1, gettext/modeltranslation, `i18n_patterns`, vanilla JavaScript modules, Node built-in test runner, Django unittest, production MariaDB read-only reporting, browser verification.

**Execution rule:** Do not begin a later task until the preceding task has focused test evidence plus spec and quality review. Stage exact paths only. Do not alter `management/*`, admin behavior, prices, availability, or production data in source-only tasks.

---

### Task 1: Build the shared locale-contract foundation

**Files:**
- Create: `twocomms/storefront/services/locale_contract.py`
- Modify: `twocomms/storefront/context_processors.py`
- Modify: `twocomms/twocomms/settings.py`
- Modify: `twocomms/twocomms_django_theme/templates/base.html`
- Test: `twocomms/storefront/tests/test_context_processors.py`
- Test: `twocomms/storefront/tests/test_rendered_locale_matrix.py`

**Step 1: Write failing tests.**

Activate `uk`, `ru`, and `en`, render a public route, and assert a valid
`#storefront-locale-contract` payload with only stable fields:

```python
{
    "language": "en",
    "intlLocale": "en-UA",
    "currency": {"code": "UAH", "suffix": "UAH"},
}
```

Test reviewed UA/RU equivalents and assert no page endpoint, customer datum, or
product field is placed in the global payload.

**Step 2: Prove RED.**

```bash
TWC_PYTHON="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.venv/bin/python"
"$TWC_PYTHON" twocomms/manage.py test storefront.tests.test_context_processors storefront.tests.test_rendered_locale_matrix --settings=test_settings --verbosity 1
```

Expected: failure because the service, context payload, and script element do
not yet exist.

**Step 3: Implement the minimum.**

Create a pure helper that normalizes the active locale to `uk`, `ru`, or `en`,
maps it to `uk-UA`, `ru-UA`, or `en-UA`, and supplies currency metadata. Add
one context processor to the existing settings list and render it once with
`json_script` in `base.html`. Do not add page routes or user-facing copy here.

**Step 4: Verify GREEN.**

```bash
"$TWC_PYTHON" twocomms/manage.py test storefront.tests.test_context_processors storefront.tests.test_rendered_locale_matrix --settings=test_settings --verbosity 1
"$TWC_PYTHON" twocomms/manage.py check --settings=test_settings
git diff --check
```

**Step 5: Commit.**

```bash
git add twocomms/storefront/services/locale_contract.py twocomms/storefront/context_processors.py twocomms/twocomms/settings.py twocomms/twocomms_django_theme/templates/base.html twocomms/storefront/tests/test_context_processors.py twocomms/storefront/tests/test_rendered_locale_matrix.py
git commit -m "feat: add storefront locale contract"
```

### Task 2: Localize the catalog selector and root SEO rail

**Files:**
- Modify: `twocomms/storefront/views/catalog.py`
- Modify: `twocomms/twocomms_django_theme/templates/partials/catalog_smart_selector.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/catalog.html`
- Modify: `twocomms/twocomms_django_theme/static/js/catalog-smart-selector.js`
- Modify: `twocomms/storefront/services/general_catalog_seo.py`
- Modify: `twocomms/locale/en/LC_MESSAGES/django.po`
- Modify: `twocomms/locale/ru/LC_MESSAGES/django.po`
- Test: `twocomms/storefront/tests/test_category_smart_selector.py`
- Test: `twocomms/storefront/tests/test_rendered_locale_matrix.py`

**Step 1: Write failing tests.**

For `/ru/catalog/`, `/en/catalog/`, `/ru/catalog/tshirts/`, and
`/en/catalog/tshirts/`, assert a selector-specific JSON payload and selector
labels for apply, reset, sort, quick facets, empty results, load-more, and
selected-count suffix in the active language. Assert root rail labels and every
generated internal link retain the current locale. Keep the global
`#storefront-locale-contract` exact and do not place selector copy in it.

**Step 2: Prove RED.**

```bash
"$TWC_PYTHON" twocomms/manage.py test storefront.tests.test_category_smart_selector storefront.tests.test_rendered_locale_matrix --settings=test_settings --verbosity 1
```

**Step 3: Implement the minimum.**

Build a selector-specific gettext payload in `_build_smart_selector_context()`
and emit it with `json_script` from the selector partial. Replace JS
`sheetModes`, quick-facet defaults, selected-count suffix, and dynamic states
with its values. Generate rail routes through `reverse()` under the active
locale. Add reviewed EN/RU gettext entries, including all selector controls and
the six root-rail labels. Bump the versioned selector asset in `catalog.html`.
Do not change filter/query semantics or the global locale contract.

**Step 4: Verify GREEN.**

```bash
"$TWC_PYTHON" twocomms/manage.py test storefront.tests.test_category_smart_selector storefront.tests.test_rendered_locale_matrix --settings=test_settings --verbosity 1
"$TWC_PYTHON" twocomms/manage.py compilemessages --settings=test_settings
node --check twocomms/twocomms_django_theme/static/js/catalog-smart-selector.js
```

**Step 5: Commit.**

Commit only the listed files with `feat: localize catalog selector flows`.

### Task 3: Make cart, mini-cart, checkout, and Monobank locale-safe

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/pages/cart.html`
- Modify: `twocomms/twocomms_django_theme/templates/partials/mini_cart.html`
- Modify: `twocomms/twocomms_django_theme/static/js/modules/cart.js`
- Modify: `twocomms/twocomms_django_theme/static/js/modules/checkout-mono.js`
- Modify: `twocomms/twocomms_django_theme/static/js/main.js`
- Modify: `twocomms/storefront/views/monobank.py`
- Modify: `twocomms/locale/en/LC_MESSAGES/django.po`
- Modify: `twocomms/locale/ru/LC_MESSAGES/django.po`
- Test: `twocomms/storefront/tests/test_cart.py`
- Create: `twocomms/storefront/tests/test_cart_locale_contract.py`

**Step 1: Write failing tests.**

Render cart and mini-cart fragments in UA/RU/EN. Assert page payloads contain
reversed item, summary, update, mini-cart, promo, contact, and Monobank URLs.
Assert RU/EN empty-cart and payment errors have no Ukrainian fallback. Mock
server errors and assert stable error code plus active-language message; never
create an invoice or event.

**Step 2: Prove RED.**

```bash
"$TWC_PYTHON" twocomms/manage.py test storefront.tests.test_cart storefront.tests.test_cart_locale_contract --settings=test_settings --verbosity 1
```

**Step 3: Implement the minimum.**

Add a `cart-locale-config` payload with strings, `intlLocale`, currency suffix,
and reversed URLs. Make cart, checkout, and mini-cart modules consume it.
Format numeric amounts only with selected locale metadata. Replace raw Ukrainian
Monobank JSON display errors with stable codes and gettext at the response
boundary. Preserve calculations, CSRF, and provider behavior.

**Step 4: Verify GREEN.**

Run focused tests, `node --check` on the three JS files, compile messages, and
inspect EN/RU rendered URLs.

**Step 5: Commit.**

Commit only listed paths with `feat: localize cart and checkout flows`.

### Task 4: Localize PWA install and Telegram verification

**Files:**
- Modify: `twocomms/storefront/context_processors.py`
- Modify: `twocomms/twocomms_django_theme/templates/base.html`
- Modify: `twocomms/twocomms_django_theme/static/js/modules/pwa-install.js`
- Modify: `twocomms/twocomms_django_theme/static/js/telegram-verify.js`
- Modify: `twocomms/accounts/telegram_verify_views.py`
- Modify: `twocomms/twocomms_django_theme/templates/pages/auth_login.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/auth_register.html`
- Modify: `twocomms/locale/en/LC_MESSAGES/django.po`
- Modify: `twocomms/locale/ru/LC_MESSAGES/django.po`
- Create: `twocomms/storefront/tests/test_conversion_locale_overlays.py`

**Step 1: Write failing tests.**

Assert base payload PWA copy and Telegram endpoint/redirect values at UA/RU/EN.
Mock Telegram start/status/cancel/complete error responses; assert a stable
code, localized message, and locale-prefixed profile fallback.

**Step 2: Prove RED.**

```bash
"$TWC_PYTHON" twocomms/manage.py test storefront.tests.test_conversion_locale_overlays --settings=test_settings --verbosity 1
```

**Step 3: Implement the minimum.**

Extend existing `web_push_config` with PWA copy. Give Telegram its own payload
with reversed endpoints and terminal redirects. Make both modules read payload
values. Preserve install event/dismissal keys and Telegram session protocol.

**Step 4: Verify GREEN and commit.**

Run the test module, both `node --check` commands, `compilemessages`, inspect
EN/RU JSON for no root storefront endpoints, then commit only listed paths with
`feat: localize install and telegram flows`.

### Task 5: Localize Custom Print conversion and error states

**Files:**
- Modify: `twocomms/storefront/custom_print_config.py`
- Modify: `twocomms/storefront/views/static_pages.py`
- Modify: `twocomms/twocomms_django_theme/templates/pages/custom_print.html`
- Modify: `twocomms/twocomms_django_theme/static/js/custom-print-configurator.js`
- Modify: `twocomms/twocomms_django_theme/static/js/custom-print-telegram-verify.js`
- Modify: `twocomms/locale/en/LC_MESSAGES/django.po`
- Modify: `twocomms/locale/ru/LC_MESSAGES/django.po`
- Test: `twocomms/storefront/tests/test_custom_print.py`
- Create: `twocomms/storefront/tests/test_custom_print_locale_contract.py`

**Step 1: Write failing tests.**

For UA/RU/EN, assert `customPrintConfiguratorConfig` contains mandatory-choice,
price/B2B, validation, success-dialog, accessibility, unit/currency, API, and
home/cart values. Assert server validation returns stable code plus active
language. Test links only; do not submit a lead or invoke notifications.

**Step 2: Prove RED.**

```bash
"$TWC_PYTHON" twocomms/manage.py test storefront.tests.test_custom_print storefront.tests.test_custom_print_locale_contract --settings=test_settings --verbosity 1
```

**Step 3: Implement the minimum.**

Extend the established configurator config rather than creating a second object.
Replace Ukrainian literals, fixed `uk-UA`, and raw home/cart URLs in both client
modules. Localize form errors at the server boundary. Preserve snapshots,
pricing, lead creation, event-id deduplication, and manager notifications.

**Step 4: Verify GREEN and commit.**

Run focused Django tests, JS syntax checks, `compilemessages`, inspect all
language payloads, then commit only listed paths with
`feat: localize custom print conversion`.

### Task 6: Repair PDP selection, restock, and locale-owner safety

**Files:**
- Modify: `twocomms/storefront/views/product.py`
- Modify: `twocomms/storefront/services/locale_publication.py`
- Modify: `twocomms/twocomms_django_theme/templates/pages/product_detail.html`
- Modify: `twocomms/twocomms_django_theme/static/js/product-detail.js`
- Modify: `twocomms/twocomms_django_theme/templates/partials/product_restock_modal.html`
- Modify: `twocomms/locale/en/LC_MESSAGES/django.po`
- Modify: `twocomms/locale/ru/LC_MESSAGES/django.po`
- Test: `twocomms/storefront/tests/test_product.py`
- Test: `twocomms/storefront/tests/test_locale_publication.py`
- Test: `twocomms/twocomms_django_theme/static/js/product-detail.test.js`

**Step 1: Write failing tests.**

Create a fixture with an owned base RU/EN product and missing colour, fit,
material, and alt selection facts. Assert initial and post-selection payloads
cannot insert Ukrainian factual copy. Assert generic fit UI uses gettext but a
missing factual row yields a non-owner/noindex selection. Add Node tests for
locale-controlled money, restock, and selection labels.

**Step 2: Prove RED.**

```bash
"$TWC_PYTHON" twocomms/manage.py test storefront.tests.test_product storefront.tests.test_locale_publication --settings=test_settings --verbosity 1
node --test twocomms/twocomms_django_theme/static/js/product-detail.test.js
```

**Step 3: Implement the minimum.**

Use existing sparse i18n data where present. Localize generic UI in the PDP
payload and resolve image-alt fallbacks from owned product/colour data. Extend
publication eligibility with a selection-level guard. Do not manufacture colour,
material, price-reason, disabled-fit text, prices, or stock.

**Step 4: Verify GREEN and commit.**

Run both focused suites, `node --test`, `node --check`, and inspect
`#variant-data` for UA/RU/EN fixtures. Commit only listed paths with
`feat: guard localized product selection`.

### Task 7: Repair source-owned static, thematic, and JSON-LD copy

**Files:**
- Modify: `twocomms/storefront/views/catalog.py`
- Modify: `twocomms/twocomms_django_theme/templates/pages/index.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/pro_brand.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/contacts.html`
- Modify: `twocomms/twocomms_django_theme/templates/partials/footer.html`
- Modify: `twocomms/twocomms_django_theme/templates/partials/mini_profile.html`
- Modify: `twocomms/storefront/services/size_guides.py`
- Modify: `twocomms/twocomms_django_theme/templates/pages/support_page.html`
- Modify: `twocomms/locale/en/LC_MESSAGES/django.po`
- Modify: `twocomms/locale/ru/LC_MESSAGES/django.po`
- Test: `twocomms/storefront/tests/test_rendered_locale_matrix.py`
- Test: `twocomms/storefront/tests/test_home_catalog_h1_localization.py`

**Step 1: Write failing locale/head/schema tests.**

Cover source-owned static pages and all four thematic landing configurations.
For every language assert visible copy, H1/title/description, breadcrumb,
canonical URL, WebPage `@id`/`url`, and internal route ownership agree. Include
the basic-T-shirt terminology and account/footer labels.

**Step 2: Implement and verify.**

Use `reverse()` and existing gettext or small explicit editorial locale
structures. Do not index a foreign landing until complete source-owned fields
and structured data exist. Compile messages and run focused locale tests after
each small change.

**Step 3: Commit.**

Commit source-only P1 changes separately from data policy changes.

### Task 8: Inventory production data, backfill editorial values, and release

**Files:**
- Create or modify after proof of a recurring gap only:
  `twocomms/storefront/management/commands/check_translation_coverage.py`,
  `twocomms/storefront/management/commands/audit_translations.py`, or one
  narrow report command.
- Update: `Translator_all/00_PROGRESS.md` and `Translator_all/MASTER.md` after
  each independently deployed batch.

**Step 1: Run a read-only production inventory.**

Once `TWOCOMMS_DEPLOY_PASSWORD` is present in the environment, use the approved
SSH workflow. Capture aggregate counts and published IDs/slugs only for Product,
VariantDetailsI18n, VariantCombinationProfileI18n, VariantImageAltI18n,
ColorProfile, fit rules, and SizeGrid. Do not write production rows in this
step and never use a secret pasted into chat.

**Step 2: Review ownership and backfill one batch at a time.**

Classify each gap as generic UI, existing sparse row, modeltranslation field,
schema change, or deliberate non-owner. Use reviewed editorial translations;
never mass-copy Ukrainian text or local SQLite values.

**Step 3: Integrate and deploy only verified source batches.**

Before merge run `git diff --check`, focused Django/Node suites,
`compilemessages`, `manage.py check --settings=test_settings`, and
`makemigrations --check --dry-run --settings=test_settings`. Merge reviewed
commits into `main`, push, then run the approved server `git pull --ff-only
origin main` procedure and post-pull runtime checks.

**Step 4: Verify live behavior and ledger status.**

Use isolated browser sessions at UA/RU/EN desktop and mobile. Test catalog →
PDP → cart/mini-cart → mocked checkout errors and Custom Print without sending
real payment, lead, or analytics events. Parse head/schema and request paths.
Update a ledger item only after fresh local and production evidence.
