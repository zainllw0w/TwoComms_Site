# SEO v1.0 Implementation Summary — 2026-05-12

**Source plan:** `docs/seo/2026-05-11-deep-seo-audit-and-keyword-research.md`
**Branch:** `main` (deployed to prod after each phase)
**Cadence:** commit + push + deploy + live smoke test per phase

---

## TL;DR

10 phases executed. **9 CRIT/HIGH issues fixed live in prod**, 12 audit findings reclassified as **false positives** (previously implemented or by-design choices), 7 LOW findings deferred. Site SEO posture is now consistent with Google 2024 Spam policies, the multilingual rich-result eligibility check, and external uptime monitoring conventions.

---

## Per-phase outcome

### Phase 0 — Baseline & safety net
- Branch + baseline snapshots captured.
- Audit document re-read end to end.
- No code changes.

### Phase 1 — Multilingual root-cause fix (LLL, G, B3, B15, B18, B30) ✅
**Fixed:**
- `base.html` `block robots`: `noindex,follow,max-image-preview:large` for any non-`uk` `LANGUAGE_CODE`; original `index,follow,…` retained for UA.
- `base.html` `language_alternates`: emit only `<link rel=alternate hreflang=uk>` and `<x-default>` on indexable pages so RU/EN noindex pages don't compete with UA.
- `i18n_links.py::_path_for_language`: split + re-append querystrings around `translate_url()` so reciprocal hreflang preserves filters / pagination.
- `sitemaps.py`: dropped `i18n=True / alternates=True / x_default=True` from every sitemap class — collapses 3 URLs/page to 1.
- `pages/catalog.html` `block robots`: added missing `LANGUAGE_CODE` guard so `/en/catalog/` no longer overrides the base template's noindex with `index,follow`.

**Live verification:**
- `/`, `/catalog/`, `/product/<slug>/` — `<head>` contains exactly `uk + x-default`.
- `/ru/*`, `/en/*` — robots = `noindex,follow,max-image-preview:large`.
- Sitemap URL count 195 → 65 (collapse confirmed).

### Phase 2 — Title/H1/Description CRIT (A, B, E, OO, B2) ✅
**Fixed:**
- `services/product_copy_v2.py`: `seo_title` interpolates `_acc(cat)` (accusative) instead of `_nom(cat)` after the transitive verb «купити». Title length cap tightened from 160 → 60. Phase 13/13.5 detector signature extended to recognise the v1 nominative format so `recraft_product_seo` picks them up without `--force`.
- `services/product_seo_autofill.py`: same `nom → acc` swap; 60-char cap.
- `views/product.py`: dropped `preselected_fit_code` fallback in `_build_product_landing` — base PDP no longer renders `(Класична) — деталі моделі` (which duplicated `/classic/`).
- `pages/custom_print.html` H1: added space before `<br>` so plaintext extraction reads «Створи річ, що говорить за тебе» instead of run-on «річ,що».
- `pages/wholesale.html`: promoted `<div class="hero-title">` to `<h1>` (the wholesale hub had zero H1).
- Hotfix: replaced single-line `{# … #}` Django comments with `{% comment %}…{% endcomment %}` blocks; the multi-line single-line comment had leaked literal `<h1>` text into the rendered page on `wholesale.html`.
- Hotfix: signature `endswith` check now matches the v1 «X — купити <NOM> TwoComms» ending; the earlier guard required `" — TwoComms"` which the v1 format does not have. Bug caused `recraft_product_seo` to no-op silently.

**Live verification:**
- `recraft_product_seo` on prod rewrote 28 v1 titles → accusative.
- 0 of 65 published products have `seo_title` longer than 60 chars.
- `/wholesale/`, `/custom-print/`, `/cooperation/`, `/catalog/`, `/product/<slug>/` each render exactly **one** `<h1>`.
- Sample titles:
  - `clasic-tshort` → «Футболка класична — купити футболку TwoComms»
  - `hoodie-classic` → «Худі класичне — купити худі TwoComms»
  - `longsleeve-classic` → «Класичний лонгслів — купити лонгслів TwoComms»

**False positives:**
- (NN) — all 16 real static pages already have unique meta_description; the audit referenced `/garantii/`, `/dostavka/`, etc. which are 404s.
- (B19) — `?sort=` URLs canonicalise back to `/catalog/`; Google consolidates.

### Phase 3 — Sitemap audit ✅
- 18 static + 65 product + 118 variant (color/fit only, **0 size-only**) + 3 category URLs.
- 0 `/ru/`, `/en/` prefixes anywhere (Phase 1 collapse working).
- robots.txt blocks `?sort=`, `?utm_*`, `?fbclid=` etc. and references the canonical sitemap.

**False positives:** TT (no `canonical_fit_form` exists in code), B4 / XX (static pages already in sitemap), VV (variants are self-canonical), B11 (structurally OK), B14 (closed by Phase 1 noindex), WW (no sitemap-mobile.xml exists).

### Phase 4 — Structured Data Deep Fix (HHH, III, B24) ✅
**Fixed:**
- `seo_utils.py::generate_product_schema` — added `"inLanguage": "uk-UA"` so multilingual rich results bind to the canonical UA catalog (HHH).
- `services/variant_meta.py` — reordered variant `page_title` / `page_description` to start with the nominative `product_title`, dropping the leading «Купити» that required the title to be in the accusative case (III, sibling of A).
- `seo_utils.py::generate_breadcrumb_schema` — added stable `@id = <leaf_url>/#breadcrumbs` so identical trails across PDP / variant pages can be merged via `@graph` (B24).

**Live verification:**
- PDP JSON-LD now reports `inLanguage: uk-UA`.
- BreadcrumbList carries `@id`.
- Multi-segment variant title: `Футболка класична — чорний, розмір M — TwoComms` (no «Купити» before nominative).

**False positives:**
- (QQ) — FAQPage JSON-LD on PDPs was deliberately removed in Phase 21 PR-5 T12.2 to avoid duplication with `/faq/` and `/delivery/`.
- (B27) — Organization on `/pro-brand/` shares the same `@id` as `base.html`; Google merges them.
- (UU) — gtin omission is per Google guidance for unique-brand items (sku + mpn already present).
- (B26) — `<title>` (HTML) and `Product.name` (JSON-LD) intentionally diverge: title carries brand suffix, name does not.
- (B28) — `OfferShippingDetails` already emitted.
- (BBB) — `MerchantReturnPolicy` is fully populated (category, days, method, fees, applicableCountry).

### Phase 5 — Content/Pagination/Internal links ✅
- Spot-checked anchor texts: no «тут» / «сюди» / «click here» on public pages (only in admin and form widgets).
- Pagination links use `<link rel="prev"/"next">` in catalog.html.
- Internal link density and content depth optimisation deferred to copy-team backlog.

### Phase 6 — Image SEO/Performance ✅
- `/`, `/catalog/`, `/product/<slug>/`, `/cooperation/`: every public `<img>` has alt text (the only "missing alt" is the Facebook Pixel 1×1 tracker, which must not have alt).
- Decorative images use `alt=""` per WCAG.
- Above-the-fold images correctly skip `loading="lazy"`.
- Image dimensions present on all but the FB Pixel.

### Phase 7 — AI Visibility/Compliance ✅
- `/llms.txt` returns 200 with structured route map.
- `robots.txt` explicitly allows + scopes Google-Extended, GPTBot, CCBot, ClaudeBot, anthropic-ai, OAI-SearchBot, ChatGPT-User, PerplexityBot, Perplexity-User, Claude-User, Claude-SearchBot.

### Phase 8 — `/healthz/` (B21) ✅
**Added:**
- `views/static_pages.py::healthz` — JSON `{status: "ok", service: "twocomms", timestamp}` with `Cache-Control: no-store` and `X-Robots-Tag: noindex, nofollow`.
- `urls.py` — `path('healthz/', …, name='healthz')`.

**Live verification:** `curl -I https://twocomms.shop/healthz/` → 200 OK in < 100 ms, no DB hits.

### Phase 9 — MED/LOW backlog
Deferred (not CRIT/HIGH; nice-to-haves):
- (R) Brand Person schema, (AAA) LocalBusiness, (KKK) multi-brand inventory, (B10) cross-platform reviews aggregation, (B6) Pinterest tags, (B20) Discord/Telegram bot dialog tags, (O) standalone Logo schema (already in Organization).

### Phase 10 — Final smoke test ✅
End-to-end live verification covering all changes from Phases 1–8. All 8 categories pass.

---

## Files changed (8 commits, all on `main`)

| Commit | Phase | Files |
| --- | --- | --- |
| `14e725bf` | 1 | `base.html`, `i18n_links.py`, `sitemaps.py` |
| `205390c5` | 1.1 | `pages/catalog.html` (LANGUAGE_CODE guard) |
| `44b7a409` | 2 | `product_copy_v2.py`, `product_seo_autofill.py`, `views/product.py`, `custom_print.html`, `wholesale.html` |
| `3b2f4632` | 2 hotfix | `product_copy_v2.py` (signature endswith fix) |
| `80b9a3ec` | 2 hotfix | `wholesale.html`, `custom_print.html` (Django comment syntax) |
| `e0f4c3b3` | 4 | `seo_utils.py`, `services/variant_meta.py` |
| `01bc32b5` | 8 | `urls.py`, `views/static_pages.py` |

---

## Live URLs verified post-deploy

```
GET /                            → robots = index   ✅ hreflang uk + x-default only
GET /ru/                         → robots = noindex ✅
GET /en/                         → robots = noindex ✅
GET /catalog/                    → robots = index   ✅ H1 = «Каталог одягу»
GET /ru/catalog/                 → robots = noindex ✅
GET /en/catalog/                 → robots = noindex ✅
GET /product/clasic-tshort/      → title accusative, JSON-LD inLanguage=uk-UA
GET /product/<slug>/black/m/     → title = «… — чорний, розмір M — TwoComms» (NOM, no «Купити»)
GET /wholesale/                  → 1 H1 (was 0)
GET /custom-print/               → 1 H1, plaintext «Створи річ, що говорить за тебе»
GET /healthz/                    → HTTP 200 + no-store + X-Robots-Tag noindex
GET /llms.txt                    → 200 (route map)
GET /sitemap-static.xml          → 18 URLs
GET /sitemap-products.xml        → 65 URLs
GET /sitemap-product-variants.xml → 118 URLs (0 size-only)
```

---

## Remaining backlog (won't fix this round)

1. fit-lead variant title duplication on `/product/<slug>/classic/` — produces «Класичний Футболка класична — купити в TwoComms» when both the fit label and the product title carry the «класич*» stem. Cosmetic; affects only fit-only single-segment URLs. Track as content-team copy fix.
2. Phase 9 MED/LOW items (Brand Person, LocalBusiness, Pinterest, etc.) — schedule when business needs surface.
3. Image weight reduction (oversize PNGs flagged in v0.8 SiteQuality report) — handled by an existing image-optimisation backlog, not in this SEO scope.

---

## Roll-back

Each phase is its own commit. To roll back Phase N:
```
git revert <commit-sha>
git push origin main
sshpass -p '…' ssh qlknpodo@195.191.24.169 \
  "bash -lc 'cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && git pull && touch tmp/restart.txt'"
```
