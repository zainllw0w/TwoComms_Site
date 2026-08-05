# Custom Print Flow Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the custom-print configurator clear and resilient across devices, with product-specific details, corrected fabric/pricing rules, dedicated own-clothing and B2B flows, and readable Telegram output.

**Architecture:** Keep the existing Django configuration payload and lead submission contract. Move presentation differences into explicit mode/product metadata, normalize state whenever a previous step changes, and make the guided-studio renderer responsible for compact information rows, contextual errors, and mobile app-mode activation. Preserve existing server-side validation as the final authority and update shared labels in the config/notification layer so UI and Telegram use the same vocabulary.

**Tech Stack:** Django templates and i18n, vanilla JavaScript, existing custom-print state helpers, CSS, unittest/Django tests, Playwright/browser smoke checks, Passenger deploy.

---

### Task 1: Audit current state and contracts

**Files:**
- Inspect `twocomms/storefront/custom_print_config.py`
- Inspect `twocomms/twocomms_django_theme/templates/pages/custom_print.html`
- Inspect `twocomms/twocomms_django_theme/static/js/custom-print-configurator.js`
- Inspect `twocomms/twocomms_django_theme/static/js/custom-print-state.js`
- Inspect `twocomms/twocomms_django_theme/static/js/custom-print-submit-flow.js`
- Inspect `twocomms/storefront/custom_print_notifications.py`

**Steps:**
1. Trace mode/product/config/zones/artwork/quantity/gift/contact state and step rendering.
2. Record current regular/oversize fabric options, own-clothing base price, B2B discount thresholds, and labels.
3. Record every UI string that says `класична тканина`, `деталі худи`, `притбрати чорний і білий тло`, or `вибрати подарунок`.
4. Identify the existing draft normalization and validation focus/scroll functions.

### Task 2: Add regression coverage before changing behavior

**Files:**
- Modify `tests/test_custom_print_config_contract.py`
- Modify `tests/test_custom_print_pricing_source.py`
- Modify `tests/test_custom_print_guided_studio_source.py`
- Modify `tests/test_custom_print_notifications_unit.py`
- Add focused tests under `tests/` only if an existing source test cannot express the contract.

**Steps:**
1. Add failing assertions for regular tee labels/pricing, oversize thermo availability, own-clothing base price and no-size quantity, and B2B copy/threshold metadata.
2. Add failing assertions for product-specific step-3 detail labels, the corrected background-removal text, and the `Далі` gift CTA.
3. Add failing assertions that any configurator choice activates the mobile studio shell and that validation targets the missing section rather than an XS control.
4. Add failing Telegram notification assertions for `Звичайна тканина` and the updated own-clothing/B2B vocabulary.
5. Run the focused tests and capture the expected failures before implementation.

### Task 3: Correct configuration, pricing, and shared labels

**Files:**
- Modify `twocomms/storefront/custom_print_config.py`
- Modify `twocomms/storefront/custom_print_notifications.py`
- Update `twocomms/locale/uk/LC_MESSAGES/django.po` and compiled catalogs if required.

**Steps:**
1. Rename the regular tee fabric label everywhere to `Звичайна тканина`.
2. Set regular tee premium to `+150 грн`; keep oversize premium included in base and expose thermo only for oversize.
3. Set own-clothing base to `150 грн` and add delivery/color/quantity/photo metadata without inventing size requirements.
4. Add explicit B2B metadata for individual pricing and quantity tiers at multiples of eight, with a manager contact action.
5. Update notification formatters to consume the same resolved labels and concise B2B/own-clothing summaries.

### Task 4: Redesign step 3 and resilient navigation

**Files:**
- Modify `twocomms/twocomms_django_theme/templates/pages/custom_print.html`
- Modify `twocomms/twocomms_django_theme/static/js/custom-print-configurator.js`
- Modify `twocomms/twocomms_django_theme/static/js/custom-print-state.js`
- Modify `twocomms/twocomms_django_theme/static/css/custom-print-guided-studio.css`

**Steps:**
1. Replace persistent product-detail choice cards with compact product-specific information rows and optional disclosure text.
2. Add own-clothing step-3 controls for shipping method, buyer-paid return delivery notice, color swatches, optional garment photo, and quantity.
3. Add the B2B brief-first layout and visually prominent quantity-tier explanation without adding unnecessary wizard steps.
4. Normalize dependent state when navigating backward or changing product/design so stale brief text, prices, and validation flags cannot survive incompatible selections.
5. Activate the studio shell on the first meaningful configurator interaction, not only the hero CTA; preserve explicit exit/restart semantics.
6. Route validation to the actual missing group, render one aligned inline message, and scroll/focus that group. Disable impossible size increments instead of allowing over-allocation.
7. Replace gift-step copy with `Далі`, keeping gift selection optional.
8. Improve the fleece/grommet control with a labeled visual switch and state badge.

### Task 5: Verify and ship

**Steps:**
1. Run focused source/unit tests, Django checks, JS syntax checks, Python compilation, and `git diff --check`.
2. Run browser smoke checks at desktop and mobile viewports for regular tee, oversize tee, hoodie fleece/grommet, own clothing, B2B, back navigation, and validation focus.
3. Commit only intended tracked changes and push `main`.
4. On production run `git pull --ff-only`, `collectstatic --no-input`, `compress --force`, `manage.py check`, and `touch tmp/restart.txt` last.
5. Verify `/`, `/custom-print/`, and localized custom-print routes.
6. Resend only `CP19072026L001` using the existing resend command after clearing its notification throttle, then verify success and unchanged attachment count in the production database/logs.
