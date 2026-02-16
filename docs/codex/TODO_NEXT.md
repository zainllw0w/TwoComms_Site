# Next Improvements (Not Implemented in This Scope)

1. Add RU/EN versions for blog posts at DB level (either linked translation model or language-specific post table) while keeping UA canonical URLs.
2. Add Playwright smoke suite for `/:lang` variants covering:
- Header/footer contact links.
- FAQ route availability.
- Legal pages load and language switch.
- Order preflight risk-check reveal on "print as-is".
3. Add automated broken-link check in CI for DTF templates and sitemap URLs.
4. Normalize legal EN copy where source file contains mixed-language terms, after approved legal-text update.
5. Add schema.org FAQPage JSON-LD to `/faq/` for all locales.
6. Add regression tests asserting seeded blog slugs and metadata from migration `0008`.
7. Add explicit i18n snapshot tests to prevent cross-language leakage in template branches.
8. If needed, move repeated hook strings to centralized i18n dictionary helper to avoid drift.
