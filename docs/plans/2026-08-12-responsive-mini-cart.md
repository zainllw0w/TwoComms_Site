# Responsive Mini-Cart Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build one compact, stable, and accessible mini-cart hierarchy for desktop, tablet, and mobile without changing cart data or checkout behavior.

**Architecture:** Keep the existing desktop and mobile panel entry points used by `main.js`, but give both a shared semantic shell and a single dedicated stylesheet loaded after legacy bundles. Restructure the returned mini-cart partial into a scrolling item list plus fixed summary/actions so viewport height changes cannot hide checkout controls.

**Tech Stack:** Django templates and i18n, scoped CSS, existing vanilla JavaScript handlers, Django `SimpleTestCase` contract tests, Playwright/browser geometry QA.

---

### Task 1: Add RED mini-cart contracts

**Files:**
- Modify: `twocomms/storefront/tests/test_catalog.py`

**Step 1:** Add a contract test that expects `templates/base.html` to load `css/mini-cart.css` after `css/mobile-shell.css`.

**Step 2:** Assert both desktop and mobile shells expose `mini-cart-shell`, `mini-cart-shell__header`, and `mini-cart-shell__content`, while neither includes a `cart-sparks-container`, delivery menu, or information footer.

**Step 3:** Assert `partials/mini_cart.html` contains separate `mini-cart-list` and `mini-cart-footer` regions, an actionable empty state, stable media images, and no mini-cart mono checkout trigger.

**Step 4:** Assert the new CSS owns shared 56px media geometry, grid tracks, list overflow, fixed footer geometry, desktop viewport bounds, mobile shell bounds, and reduced-motion behavior.

**Step 5:** Run the focused test and confirm it fails because the new stylesheet and semantic regions do not exist.

Run:

```bash
SECRET_KEY=test-local-secret DEBUG=True NOVA_POSHTA_FALLBACK_ENABLED=False \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  storefront.tests.test_catalog.CatalogViewTests.test_mini_cart_uses_one_stable_responsive_visual_contract \
  --settings=test_settings --keepdb -v 2
```

Expected: FAIL on the missing `mini-cart.css` contract.

### Task 2: Create shared panel shells

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/partials/header.html`
- Modify: `twocomms/twocomms_django_theme/templates/base.html`
- Create: `twocomms/twocomms_django_theme/static/css/mini-cart.css`

**Step 1:** Add shared shell/header/content classes to both panels without changing IDs, close hooks, or loading targets.

**Step 2:** Remove spark markup, the delivery menu, and the informational footer from both panels.

**Step 3:** Load `mini-cart.css` after `mobile-shell.css` with a task-specific cache-busting query.

**Step 4:** Define restrained shared panel/header/content styles, explicit desktop width/height bounds, and mobile/tablet top/bottom constraints.

**Step 5:** Run the focused test; it should still fail on the content-partial expectations.

### Task 3: Restructure mini-cart content and actions

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/partials/mini_cart.html`
- Modify: `twocomms/twocomms_django_theme/static/css/mini-cart.css`

**Step 1:** Split populated content into `mini-cart-view`, `mini-cart-list`, and `mini-cart-footer`.

**Step 2:** Keep every cart/custom row data attribute and remove handler unchanged.

**Step 3:** Replace generic image sizing utilities with a dedicated `mini-cart-row__image` class and explicit `width`/`height` attributes.

**Step 4:** Flatten row visuals, clamp titles, wrap metadata, keep a stable price/remove column, and use tabular price numerals.

**Step 5:** Keep `Оформити замовлення` as the only orange primary action, convert `Продовжити покупки` into a neutral full-width secondary action, and remove the mini-cart mono checkout tile/status.

**Step 6:** Add an empty state with the existing `Перейти до покупок` translation and `data-mini-cart-continue` handler.

**Step 7:** Run the focused test and confirm GREEN.

### Task 4: Verify behavior and affected contracts

**Files:**
- Modify only if a regression is demonstrated by tests.

**Step 1:** Run focused catalog and cart suites.

```bash
SECRET_KEY=test-local-secret DEBUG=True NOVA_POSHTA_FALLBACK_ENABLED=False \
  /Users/zainllw0w/TwoComms/site/.venv/bin/python manage.py test \
  storefront.tests.test_catalog storefront.tests.test_cart \
  --settings=test_settings --keepdb -v 1
```

**Step 2:** Run `manage.py check`, template compilation checks if available, and `git diff --check`.

**Step 3:** Confirm `main.js` still binds `[data-mini-cart-continue]`, both close controls, and both content targets without changes.

### Task 5: Browser geometry and visual QA

**Files:**
- Store screenshots under: `output/playwright/mini-cart-responsive/`

**Step 1:** Start the local Django server on a free port using the existing test/development environment.

**Step 2:** Populate a session with long/short product names and verify 320x568, 375x667, 390x844, 430x932, and 768x1024.

**Step 3:** Verify 1024x768, 1280x800, and 1440x900 desktop panel bounds, 56px images, readable copy tracks, and visible primary/secondary actions.

**Step 4:** Exercise open, close, Escape, continue-shopping, cart navigation, list scrolling, empty state, long-title state, and custom-row-compatible layout.

**Step 5:** Measure `scrollWidth === clientWidth`, panel bounds within viewport, footer visibility, and zero console errors.

### Task 6: External design evaluation and fixes

**Files:**
- Modify only task-scoped templates/CSS/tests in response to validated findings.

**Step 1:** Have a design evaluator compare desktop and mobile screenshots against the design brief.

**Step 2:** Apply every priority correction through the implementation subagent.

**Step 3:** Re-run the evaluator for up to three rounds until PASS or document remaining non-blocking issues.

### Task 7: Release and production proof

**Files:**
- Commit only the design docs, tests, templates, and mini-cart CSS changed by this task.

**Step 1:** Run fresh focused suites, `manage.py check`, `git diff --check`, and the browser geometry checklist.

**Step 2:** Commit the implementation and push the branch commit to `origin/main` only after confirming it is a fast-forward.

**Step 3:** Deploy with the authorized SSH pull, then run `collectstatic --noinput`, `compress --force`, `check --deploy`, and Passenger restart.

**Step 4:** Confirm local/origin/server SHA parity.

**Step 5:** Repeat production browser checks at desktop, tablet, phone, and short-height viewports; confirm bounded images, stable panel geometry, visible actions, correct navigation, no overflow, and zero console errors.
