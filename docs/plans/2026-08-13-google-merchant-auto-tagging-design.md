# Google Merchant Auto-Tagging Design

## Problem

Google Merchant Center auto-tagging appends `srsltid` to product URLs opened
from Google Search. TwoComms accepts the parameter on product pages but the
strict catalog query validator rejects it with HTTP 404. Clarity recordings
confirm that real Google organic visitors reached localized catalog URLs and
received the error.

The current analytics pipeline also ignores `srsltid`, `gbraid`, and `wbraid`.
As a result, accepting the request alone would restore the page but would not
provide durable attribution from landing page to product view and order.

## Google Contract

Merchant Center auto-tagging requires the destination site to accept
`srsltid`. If the destination redirects, it must preserve the parameter until
the final landing page. `srsltid` identifies free-listing traffic; it is not a
catalog filter or product variant selector.

Google Ads identifiers remain a separate channel:

- `gclid`, `gbraid`, and `wbraid`: paid Google traffic.
- `srsltid`: Google Merchant free-listing traffic.

Merchant feed `link` values and HTML canonical URLs remain clean, stable URLs.
Tracking identifiers are accepted on inbound requests but do not become page,
cache, sitemap, or feed identities.

## Architecture

Define one shared attribution-query contract in `storefront.utm_utils` and use
it from request identity, UTM middleware, catalog validation, robots policy,
and order tracking. This prevents the current drift where catalog accepts some
identifiers that analytics does not store.

For a first `srsltid` landing:

1. `AnalyticsIdentityMiddleware` captures the token, landing path, referrer,
   and normalized `google / organic` attribution in first-touch data.
2. `UTMTrackingMiddleware` creates a durable `UTMSession` and stores the raw,
   bounded token.
3. `SimpleAnalyticsMiddleware` links the same first-touch data to
   `SiteSession` and records the page view.
4. Product actions inherit first-touch metadata and keep their product ID.
5. Checkout includes the identifier in the order tracking payload and links
   the order to the UTM session.
6. Custom-admin session detail exposes the identifier and distinguishes
   `Google Shopping free listings` from paid Google Ads.

## Routing And SEO

Catalog validation continues to reject unsupported parameters owned by the
catalog (`page`, `sort`, and facets). Opaque external parameters are accepted
as Google requires, excluded from content identity, marked `noindex`, and
bypass anonymous page-cache reads and writes. Known attribution identifiers
are additionally captured; unknown future parameters remain harmless without
being persisted as attribution.

The response remains HTTP 200 instead of redirecting solely to remove
`srsltid`. This avoids an extra navigation and eliminates the risk of losing
the token before attribution middleware runs. The HTML canonical remains the
query-free request path. Existing variant canonical redirects preserve all
non-variant tracking parameters, including `srsltid`.

Robots query-noise rules include both `?srsltid=` and `&srsltid=` forms, while
the destination stays crawlable when Google requests the canonical page.

## Merchant Feed

Google V3 keeps exact variant paths in `g:link`, without UTM or click IDs.
Feed verification must check XML validity, duplicate offer IDs, query-free
links, the expected canonical domain, and that every unique product landing
URL resolves successfully. `canonical_link` is unnecessary while `g:link`
already matches the page canonical.

## Verification

- Regression tests cover Ukrainian, Russian, and English catalog landings.
- Alias redirects preserve `srsltid`.
- First-touch, UTM session, user action, and order tracking retain the token.
- Paid Google identifiers remain `google / cpc`; `srsltid` is
  `google / organic` and labeled as free-listing traffic.
- Canonical HTML and V3 feed links contain no tracking query.
- All live V3 product links return a successful landing response.
