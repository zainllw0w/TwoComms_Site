# Storefront Localization Program

## Objective

Make the public Ukrainian, Russian, and English storefront internally
consistent across the conversion journey on desktop and mobile. The admin
interface is explicitly out of scope.

## Ground Rules

- Production behavior and production MariaDB are authoritative for public
  runtime and content checks; local SQLite is a fast regression-test layer.
- Do not overwrite or infer translated product descriptions, titles, or SEO
  fields from the local database. Record such gaps for a dedicated data audit.
- Each finding must include the locale(s), live or source evidence, affected
  route/component, priority, implementation owner, and verification method.
- Code, template, JavaScript, and gettext fixes are separate from production
  database content fixes. They may be released together only after each has
  been verified independently.
- No admin routes or staff UI are included in this program.

## Priority Model

| Priority | Definition | Examples |
| --- | --- | --- |
| P0 | Blocks, misroutes, misprices, or materially confuses a shopper in a conversion path | Cart/checkout errors, submit feedback, mandatory labels, locale-breaking links |
| P1 | Prominent public copy or controls are inconsistent across UA/RU/EN | Catalog filters, variant/fit controls, size guides, mobile navigation, modal CTAs |
| P2 | Important crawlability, supplemental content, or non-blocking polish | JSON-LD language fields, metadata, FAQs, optional product text |
| Deferred data | Product-localized titles, descriptions, and per-product SEO fields needing production DB review | Do not auto-fill from code or a local database |

## Workstreams

| File | Scope | Audit state | Implementation state |
| --- | --- | --- | --- |
| `01-catalog.md` | Catalog root, category pages, filters, sorting, navigation, mobile catalog | Complete | 3 / 8 source-complete; 3 / 8 live-confirmed (37.5%) |
| `02-product-detail.md` | PDP, variants, fits, size grids/advisor, technologies, product schema | Complete | Awaiting approved implementation design and DB inventory |
| `03-custom-print.md` | Custom Print configurator, form, localized routes, schema | Complete | Awaiting approved implementation design |
| `04-conversion-and-overlays.md` | Cart, checkout, payment, alerts, toasts, PWA/install and other overlays | Complete | 5 / 14 source-complete; 5 / 14 live-confirmed (35.7%) |
| `05-static-pages.md` | Home, ProBrand, delivery/payment, support pages, shared customer chrome | Complete | Awaiting approved implementation design |
| `06-seo-geo-and-data.md` | Cross-cutting head/schema/sitemap ownership and production content coverage | Complete | Awaiting approved implementation design and DB inventory |

## Baseline and Constraints

- Public live checks begin with `https://twocomms.shop` and explicit `/ru/`
  and `/en/` routes where present.
- The primary checkout has extensive pre-existing untracked files. All
  localization commits must stage exact paths only; unrelated files are never
  included.
- SSH deployment and MariaDB checks use the local secret-safe credential
  loader; no password is copied into this repository or its ledgers.

## Acceptance Checks Per Released Batch

- UA/RU/EN route, `<html lang>`, canonical, hreflang, title, headings, and
  visible conversion controls agree with the selected locale.
- Locale-aware links preserve the current language through the conversion
  path.
- Mobile and desktop checks cover the affected public control or overlay.
- Existing focused tests plus new regression tests prove the original mixed
  language state and the correction.
- Production deployment uses a scoped commit on `main`, a push to
  `origin/main`, then the approved SSH `git pull` procedure and live checks.

## Progress

| Metric | Current value |
| --- | --- |
| Workstreams audited | 6 / 6 complete (100%) |
| Confirmed work packages | 53 final: 18 P0, 28 P1, 7 P2 |
| Confirmed P0 findings fixed | 7 / 18 (38.9%) |
| Confirmed P1 findings fixed | 1 / 28 (3.6%) |
| Confirmed P2 findings fixed | 0 / 7 (0%) |
| Overall remediation | 8 / 53 (15.1%) |
| Source-complete P0 findings | 7 / 18 (38.9%) |
| Source-complete P1 findings | 1 / 28 (3.6%) |
| Source-complete work packages | 8 / 53 (15.1%) |
| Production DB content findings verified | 0 (SSH used for schema/counters only; no translation inventory or writes) |
| Locally reviewed source tasks | 3 / 8 plan tasks (37.5%): locale-contract foundation, catalog selector/root rail, and cart/checkout |
| Last consolidated update | 2026-08-19: final localization runtime SHA `3de4c6a7d`; later `main` commits do not change this localization code. The historical `f239538c6` matrix covered 24 catalog and 12 cart/mini-cart UA/RU/EN desktop/mobile probes, then post-fix checks confirmed localized Smart Selector and Monobank return states. Focused tests, Django/gettext/JS checks, and independent reviews passed. Production counters stayed at `orders=64`, `payment_attempts=12`; product DB translation inventory remains deferred. |

## Current Implementation Checkpoint

| Plan task | Local implementation evidence | Review evidence | Release status |
| --- | --- | --- | --- |
| Task 1: shared locale-contract foundation | Commit `25b8768f1`; 11 focused tests, locale normalization matrix, Django check, and diff check passed | Independent specification and code-quality reviews found no blocking issues | Integrated as the deployed contract dependency; exercised by the catalog/cart production matrices (not counted as a separate customer package) |
| Task 2: catalog selector and root SEO rail | Source-complete; 67 focused tests, Django check, gettext compilation, JS syntax, and diff check passed | Independent specification and code-quality reviews found no blocking issues | Live-confirmed for CATALOG-P0-01..03 through final SHA `3de4c6a7d` across UA/RU/EN, desktop/mobile; thematic landings, hreflang policy, and DB-owned product copy remain open |
| Task 3: cart, mini-cart, checkout, and Monobank | Source-complete; 65 focused tests, Django check, gettext compilation, four JS syntax checks, and diff check passed. The full Nova/Monobank module has no new regression versus clean `origin/main` (`5F/6E` versus baseline `7F/6E`; all remaining names are shared fixture-contract failures). | Independent specification and code-quality reviews returned `APPROVED` after the EN/RU payment-error regression was fixed | Live-confirmed for CONV-P0-01..04 and CONV-P1-04 through final SHA `3de4c6a7d`; safe missing-reference return messages are UA/RU/EN and no live invoice/payment event was created |

The production-confirmed `8 / 53` remediation figure counts only the eight
packages with both focused regression coverage and fresh production browser
evidence. The source-complete figure is equal for this batch; the remaining
audited findings are intentionally not promoted by source tests alone.

## Implementation Boundary

The shared implementation design proposed in `MASTER.md` is the gate before
source changes begin. It combines a server-rendered base locale contract,
page-specific `json_script` payloads, Django-reversed public routes, gettext
for stable interface text, and explicit locale ownership for database-backed
merchandising data. It prevents JavaScript, templates, and production data from
making inconsistent language decisions.

## Deferred Backlog

- Production-first audit of product `title_ru`, `title_en`, descriptions,
  technical attributes, and product-specific SEO fields.
- Editorial translation of missing product content only after exact source
  records and merchandising semantics (fit, color, material) are reviewed.
