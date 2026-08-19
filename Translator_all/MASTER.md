# TwoComms Localization Master

## Objective

Bring the public Ukrainian, Russian, and English storefront surfaces to
language-consistent, conversion-safe, and crawler-readable parity. The Django
admin is explicitly out of scope.

## Status

- Audit coverage: 6 of 6 workstreams complete (100%)
- Confirmed implementation coverage: 0 of 53 work packages (0%)
- Source foundation: Task 1 is locally implemented and independently reviewed;
  merge, production deployment, and live browser verification are pending
- Production database verification: blocked pending safe SSH credential access
- Source of truth for live browser behavior: public production routes

## Audit Snapshot (2026-08-19)

| Workstream | Audit | Confirmed packages | Implementation |
| --- | --- | ---: | --- |
| Catalog | Complete | 4 P0, 3 P1, 1 P2 | 0% |
| PDP, fit, technology, and size | Complete | 2 P0, 4 P1, 1 P2 | 0% |
| Custom Print | Complete | 4 P0, 4 P1 | 0% |
| Cart, checkout, overlays, and PWA | Complete | 7 P0, 5 P1, 2 P2 | 0% |
| Static customer pages | Complete | 8 P1, 2 P2 | 0% |
| SEO/GEO and database ownership | Complete | 1 P0, 4 P1, 1 P2 | 0% |

Final total: **53 independently verifiable packages**: **18 P0**, **28 P1**,
and **7 P2**. A package is not counted as implemented until its focused
regression test and production browser check both pass.

## Priority Order

1. P0 conversion: catalog filters, product selection, cart, checkout, payment,
   delivery, Custom Print, alerts, dialogs, and PWA install prompts.
2. P1 public navigation and static pages: home, catalog landings, ProBrand,
   delivery, contacts, cooperation, size guides, care, FAQ, and account chrome.
3. P1 SEO/GEO: HTML language, canonical/hreflang, titles, meta descriptions,
   JSON-LD, headings, alt text, and locale-aware internal links.
4. P2 database-backed product copy: descriptions, SEO descriptions, keywords,
   FAQs, fit-specific and colour-specific content where a translated value is
   missing.

## Proposed Shared Locale Contract

The audits converge on one root cause: Django gettext, JavaScript strings,
root-relative endpoints, and database-backed merchandising data currently make
independent locale decisions. The proposed implementation design is deliberately
hybrid, rather than a browser-side translator or a blind database copy:

1. A small server-rendered base locale payload owns the active language,
   locale-aware routes, currency/unit formatting, and universal semantic copy.
2. Each interactive page supplies an explicit `json_script` extension for its
   own controls. JavaScript reads this payload only; it does not embed Ukrainian
   fallback text, fixed `uk-UA`, or unprefixed public endpoints.
3. Django `reverse()` supplies every public endpoint and redirect. Backend
   validation returns stable error codes or localized gettext messages, never
   Ukrainian display text for client-side reuse.
4. Stable interface labels use the existing gettext catalogs. Product, colour,
   fit, material, SizeGrid, alt, and editorial SEO data retain explicit locale
   ownership and are never auto-translated or copied from local SQLite.
5. A locale without reviewed data is treated as a non-owner for indexing and
   sitemap/hreflang publication until its production MariaDB data is complete.

This design is approved. Its Task 1 foundation preserves the project's existing
Django i18n, `reverse`, `json_script`, and sparse i18n-row patterns, instead of
introducing a second translation framework.

## Release Batches

1. **Foundation:** the minimal locale payload is locally implemented and
   independently reviewed; it awaits integration and live verification. The
   remaining locale-safe URL, page-copy, and gettext work belongs to the
   page-specific tasks below.
2. **P0 conversion flows:** catalog selector and rail; cart, mini-cart,
   checkout, Monobank, Telegram verification, PWA; and Custom Print
   configurator, errors, dialogs, and redirects.
3. **P0 product selection:** PDP variant/restock state and the production-owned
   colour/fit/material contract. Source-only UI can ship first; factual product
   data waits for the production inventory.
4. **P1 public and SEO:** support/static copy, account chrome, themes,
   WebPage JSON-LD, canonical/hreflang/sitemap ownership, and source-owned
   accessibility labels.
5. **Editorial data backfill:** production-first titles, descriptions, variant
   details, SizeGrid, images, and per-product SEO. This batch is separately
   reviewed and does not block source-code P0 deployment.

## Confirmed Production Findings

- `/en/catalog/` mobile filters include the Ukrainian CTA `Показати товари`.
- `/en/cart/` and `/ru/cart/` mix Ukrainian text into the empty-cart and
  payment flow, including payment options and the discount-safe dialog.
- `/en/` leaks Ukrainian product titles/copy where database translations fall
  back to Ukrainian.
- `/en/cooperation/`, `/ru/cooperation/`, `/en/contacts/`, `/ru/contacts/`,
  `/en/rozmirna-sitka/`, and both language variants of the care guide contain
  Ukrainian customer-visible text.
- `/en/custom-print/` shows Ukrainian mandatory-configurator, B2B,
  validation, and success-dialog content after interaction; some successful
  paths link back to the Ukrainian home/cart route.
- `/en/product/` and `/ru/product/` can show Ukrainian product titles, fit,
  colour, thermochromic, size-guide, and post-selection client-side content.
- Home `WebPage` JSON-LD uses the Ukrainian URL on RU/EN pages; some catalog
  and Custom Print schemas similarly disagree with their localized canonical.
- EN/RU PDP selection data can replace localized controls with Ukrainian colour,
  thermochromic, material, fit, price-reason, and image-alt data after an
  interaction; this is both P0 conversion and SEO/GEO ownership failure.

## Working Protocol

- One audit file per ownership area under this directory.
- Record each finding with route, locale, visible evidence, source, priority,
  and verification requirement before implementation.
- Mark an item implemented only after a focused test and a production-browser
  check. Production database updates require SSH verification against MariaDB.
- Keep product long descriptions and other large database copy in the final
  dedicated backfill phase, unless they directly block a current conversion or
  SEO surface.
- Keep the audit ledgers current after every batch: implemented count, priority
  count, test evidence, production-browser evidence, and remaining percentage.
