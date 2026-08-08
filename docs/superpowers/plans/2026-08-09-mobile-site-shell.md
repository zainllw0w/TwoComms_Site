# Mobile Site Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship one consistent, performant mobile header/menu/bottom navigation across the public storefront while preserving the approved catalog reference and desktop layout.

**Architecture:** Keep `partials/header.html` as the single global owner. Add a mobile-only shell block plus focused `mobile-shell.css` and `mobile-shell.js`; catalog root keeps only its reference content and delegates filters to the existing smart-selector sheet.

**Tech Stack:** Django templates/i18n, existing static CSS, vanilla JavaScript modules, Django `TestCase`, Playwright or browser viewport checks.

---

### Task 1: Global shell markup and server-rendered contracts

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/partials/header.html`
- Modify: `twocomms/twocomms_django_theme/templates/base.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/catalog.html`
- Test: `twocomms/storefront/tests/test_catalog.py`

- [ ] Add one mobile shell block with reference header, menu links, language links, cart trigger, and contextual bottom-nav links.
- [ ] Remove the old mobile cart dock markup and make the existing desktop navbar desktop-only below the mobile breakpoint.
- [ ] Expose catalog filter trigger data attributes without duplicating filter options.
- [ ] Hide the catalog root's duplicate local header/menu/dock while retaining its content.
- [ ] Run focused template tests.

### Task 2: Mobile shell styling and geometry

**Files:**
- Create: `twocomms/twocomms_django_theme/static/css/mobile-shell.css`
- Modify: `twocomms/twocomms_django_theme/templates/base.html`
- Modify: `twocomms/twocomms_django_theme/static/css/catalog-redesign.css`

- [ ] Implement fixed header, menu panel, language segmented control, contextual dock, safe-area padding, and reduced-motion state below 992px.
- [ ] Reserve header/dock space explicitly and bound the shell to the viewport to prevent CLS/overflow.
- [ ] Use warm orange/graphite reference palette and remove purple from the mobile dock.
- [ ] Add low-contrast floating marks to the root custom-print card without obscuring copy.
- [ ] Add a static hero progress marker.
- [ ] Run `git diff --check` and CSS/template checks.

### Task 3: Mobile shell behavior

**Files:**
- Create: `twocomms/twocomms_django_theme/static/js/mobile-shell.js`
- Modify: `twocomms/twocomms_django_theme/templates/base.html`
- Modify: `twocomms/twocomms_django_theme/static/js/catalog-smart-selector.js`

- [ ] Implement menu open/close, outside press, Escape, focus return, and body-scroll lock.
- [ ] Implement search toggle/focus and localized language links.
- [ ] Connect the catalog dock action to `[data-smart-open-filters]` and synchronize the active count.
- [ ] Preserve existing bottom-nav hide/show scroll behavior by retaining `.bottom-nav` and its established JS contract.
- [ ] Run focused JavaScript syntax and catalog smart-selector tests.

### Task 4: Verification

**Files:**
- Test: `twocomms/storefront/tests/test_catalog.py`
- Inspect: catalog/PDP/cart/checkout templates and browser output

- [ ] Run `python manage.py check --settings=test_settings`.
- [ ] Run the focused catalog suite and existing smart-selector tests.
- [ ] Verify 320/375/390/430px viewport geometry, no horizontal overflow, sticky header, dock hide/show, menu, language, cart, and filter interactions.
- [ ] Verify desktop 1280px layout and representative PDP/cart/checkout routes are unchanged.
- [ ] Record any residual risk before commit/push/deploy.
