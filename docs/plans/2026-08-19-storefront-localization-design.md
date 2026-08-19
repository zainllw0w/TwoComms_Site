# Storefront Localization Design

**Date:** 2026-08-19

## Goal

Make every public Ukrainian, Russian, and English conversion surface language
consistent without inventing translations for product facts or creating a
second client-side i18n system. The Django admin remains out of scope.

## Decision

Use a hybrid locale contract built on the existing Django patterns:

1. Django owns the active language, route reversal, stable gettext strings,
   and formatted currency/unit metadata.
2. `base.html` exposes a compact, safe base payload for universal client code.
   Interactive pages extend it with page-specific `json_script` payloads.
3. JavaScript reads payload values only. It must not embed Ukrainian display
   fallbacks, fixed `uk-UA`, or root-relative public endpoints that lose the
   `/ru/` or `/en/` prefix.
4. Backend APIs return stable error codes plus localized messages at the
   request boundary. A client never treats a Ukrainian server error as its
   display dictionary.
5. Database-backed product, variant, fit, material, SizeGrid, image-alt, and
   editorial SEO content is locale-owned. Missing RU/EN data is not copied or
   machine-translated; it remains non-owner/noindex until editorially reviewed.

## Data and SEO Ownership

Source-owned UI labels are corrected in gettext catalogs and released with
regression tests. Product and variant data uses the existing modeltranslation
and sparse i18n-row primitives where they already fit. Production MariaDB is
the only authority for inventory and backfill decisions.

An advertised alternate, canonical, JSON-LD page identity, or sitemap entry
must have matching `Content-Language`, `html[lang]`, visible decision copy, and
locale-owned factual data. Organization identity stays rooted at the stable
site URL; page nodes use the locale-specific canonical URL.

## Rollout Order

1. Build and test the shared locale payload and URL/currency contract.
2. Repair P0 conversion paths: catalog selector, cart/checkout/Monobank/PWA,
   Telegram verification, and Custom Print.
3. Repair P0 PDP post-selection/restock behavior and add truthful owner guards
   for selection-state data.
4. Repair P1 static copy, account chrome, catalog/theme SEO, and JSON-LD.
5. Run a read-only production MariaDB coverage report, then execute reviewed
   editorial data backfills in separate changes.

## Verification

Each behavior follows red-green-refactor: a focused test first reproduces the
locale leak; minimal code then passes it; relevant existing suites remain
green. Release verification covers UA/RU/EN, desktop and mobile interaction,
rendered text, locale-preserving endpoints/redirects, head/schema ownership,
and no console errors. A package is complete only after local evidence,
production deployment, and live browser evidence are recorded in
`Translator_all`.

## Non-goals

This phase does not mass-translate long descriptions, fabricate product names,
alter prices or availability, translate the admin, or replace the existing
Django i18n stack.
