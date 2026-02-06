# Decision Log (DTF backlog re-run, 2026-02-06)

## D-001: Keep strict DTF isolation
- Decision: Implement and validate changes only in DTF app/routes/assets and keep main storefront untouched.
- Why: User requirement: `dtf.twocomms.shop` must behave as a separate site.
- Evidence: `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/twocomms/middleware.py`, `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/twocomms/urls_dtf.py`.

## D-002: Canonical pricing route is `/price/`
- Decision: Preserve `/price/` as canonical and maintain permanent redirect `/prices/ -> /price/`.
- Why: Avoid broken links and keep SEO stable.
- Evidence: `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/urls.py`, test `DtfP0RoutesTests.test_prices_redirects_to_price`.

## D-003: DTF robots/sitemap served by DTF app and host-aware
- Decision: Use request host when rendering `robots.txt` and `sitemap.xml`; include only DTF URLs.
- Why: DTF subdomain must not leak/consume main-domain SEO artifacts.
- Evidence: `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/views.py`.

## D-004: Upload security implemented without new infra dependency
- Decision: Enforce ext/mime/magic/size checks plus random safe filenames in server-side forms/utilities.
- Why: Secure default behavior without adding hosting-sensitive dependencies.
- Evidence: `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/forms.py`, `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/utils.py`.

## D-005: Modal/menu visual polish uses existing token system
- Decision: Increase panel/modal opacity, keep blur controlled, add body lock classes and focus-safe close behavior.
- Why: Fix excessive transparency and interaction overlap while preserving current visual style and motion model.
- Evidence: `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/static/dtf/css/dtf.css`, `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/static/dtf/js/dtf.js`.

## D-006: Replace unclear rotating hero element with explicit “Hot Peel” badge
- Decision: Remove spinning gif marker and introduce static, branded badge block with clear label.
- Why: Better meaning clarity and cleaner visual hierarchy on desktop/mobile.
- Evidence: `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/templates/dtf/index.html`.

## D-007: Compare slider supports both range input and direct drag
- Decision: Keep semantic `<input type="range">` for accessibility and add pointer drag on media area for UX parity.
- Why: Fix “before/after slider not working” reports on touch and desktop.
- Evidence: `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/static/dtf/js/dtf.js` (`initCompare`), `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/static/dtf/css/dtf.css` (`.compare-*`).

## D-008: Add EN language in addition to UA/RU
- Decision: Expand `dtf_lang` handling to `uk/ru/en`, add EN switch link, and ship EN locale catalog.
- Why: Direct user request and improved multi-language UX.
- Evidence: `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/utils.py`, `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/views.py`, `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/locale/en/LC_MESSAGES/django.po`.

## D-009: Add DTF legal pages as TEMP-complete placeholders (no lorem)
- Decision: Implement `/privacy/`, `/terms/`, `/returns/`, `/requisites/` with explicit `TEMP:` content and footer links.
- Why: Backlog requires working legal routes if missing, while allowing staged legal copy updates.
- Evidence: `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/templates/dtf/legal/privacy.html`, `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/templates/dtf/legal/terms.html`, `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/templates/dtf/legal/returns.html`, `/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/templates/dtf/legal/requisites.html`.
