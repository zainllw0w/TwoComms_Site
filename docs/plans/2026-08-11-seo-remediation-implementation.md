# TwoComms SEO/GEO Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** ship the production-backed SEO/GEO remediation from the 2026-08-10 audit in dependency order, with every completed slice proven after deploy.

**Architecture:** Establish URL ownership first, then route all metadata, schema, feeds, sitemaps and internal links through shared eligibility/locale/fact resolvers. Keep UI-only facets and selectors usable while allowing only evidence-backed clean landings and variant URLs into the indexable graph.

**Tech Stack:** Django 5 storefront, Python 3.14 production virtualenv, Django templates, JSON-LD/schema.org, XML sitemaps/merchant feeds, existing test suite and Playwright/crawl scripts.

**Baseline:** Fresh focused run after fast-forward to `4f1b0136` (2026-08-11): 28 tests, 25 passing and 3 pre-existing failures in synthetic top-menu expectations (`test_phase10b_seo_layout.py`). All Task 1 slug/price/stale-link assertions pass. The suite is explicitly not claimed green.

## Scope and decision gates

- **Custom Print is a no-touch boundary.** Exclude it from content, variant, schema, metadata, canonical and broad crawl audits. Do not change its configurator, state, pricing, media, cart, checkout, analytics, submission or notification behavior. The completed stale-link normalization changed an external category link, not Custom Print. Only a specifically reproduced RU/EN localization defect may receive the smallest locale-only patch; a wrong-locale canonical/hreflang is eligible only as part of that reproduced locale defect, with UK content and the working flow unchanged.
- **No ranking promise.** A task may claim only the directly verified result: fewer contradictory crawl/index signals, correct locale, truthful facts, correct selected variant state, or cleaner internal ownership. Position, traffic and revenue effects require post-release GSC/analytics observation.
- **Four verdicts control implementation.** `Confirmed` means a current defect with a deterministic acceptance test and may enter TDD. `Conditional` means a potentially useful strategy that waits for GSC/demand/inventory evidence and an explicit owner decision. `Rejected` means the proposed requirement is not supported by Google guidance. `Do not implement` means it creates material overoptimization, URL-bloat or migration risk.
- **Anti-overoptimization gate.** Do not generate pages, headings, FAQs, city lists or paraphrases to hit keyword density, n-gram uniqueness or text-length targets. A shorter shared policy statement is preferable when the fact is global. Variant-specific copy exists only for real differences useful to a buyer.
- **Source hierarchy.** Context7 is used for current Django implementation contracts and as a searchable mirror of official documentation. Google Search Central remains the primary SEO policy source; GSC, server logs, production DB and rendered HTML determine whether a recommendation applies to this site.

### Decision ledger before implementation

This ledger prevents a useful hypothesis from becoming an automatic SEO change. `Confirmed` items may enter TDD because the defect and a deterministic non-ranking acceptance check exist. `Conditional` items require demand/owner evidence first. `Rejected` and `Do not implement` items never enter the code queue without new primary evidence.

| Verdict | Exact item | Directly supportable positive result | Ranking/overoptimization boundary |
|---|---|---|---|
| Confirmed | Linked internal 404 destinations from catalog SEO rows | Removes dead navigation and crawler destinations; already deployed and live-crawled at zero linked 404 | No promise of recovered rankings or link equity; no blanket redirects without exact successor history |
| Confirmed | RU/EN standard catalog/PDP pages with Ukrainian H1, navigation, editorial or JSON-LD content | Makes visible language, URL and structured data agree and removes wrong-locale user journeys | Translate facts and UI, not keywords; do not create extra pages merely for language volume |
| Confirmed | Nine `futbolka-posmikhnys` variant URLs sharing a 160-character comma-list Ukrainian title across UK/RU/EN | Removes an explicit keyword-stuffed, wrong-locale title and restores concise owner/locale metadata | Fix the source field once; do not impose arbitrary character counts across unrelated titles |
| Confirmed | Generated PDP/catalog claims without an owned source, including guessed material, wash, shrinkage, delivery, exchange, packaging and donation statements | Removes factual contradictions across visible copy, schema, feeds and llms surfaces | One truthful shared policy is better than mechanically unique paraphrases; no keyword-density target |
| Confirmed | Editorial rails that link to noindex query facets or wrong-locale UK paths | Stops the site from repeatedly promoting non-owner/wrong-locale URLs and gives approved owners consistent links | Preserve useful UI filters; do not infer a penalty or block every query URL in robots.txt immediately |
| Confirmed | Variant URL, selected state, image, price, availability, cart identity, schema or feed disagreement | Makes buyer-visible and machine-readable variant identity consistent | Correct identity is required; long unique copy for every variant is not |
| Confirmed | Equivalent variant paths differing only by segment order or case are all `200` self-canonical | Consolidates duplicate path aliases into one deterministic owner without changing product state | Only exact equivalents receive one-hop `301`; invalid/ambiguous segments return `404` |
| Confirmed | Invalid facet/page values returning body-equivalent `200`, and page 2 canonical/body disagreement | Removes crawl aliases and contradictory owner signals while preserving valid pagination | `page=1` normalization is P3 hygiene, not a ranking gate; do not canonicalize distinct page 2 inventory to page 1 |
| Confirmed | Unsupported MemberProgram type and conflicting entity facts/counts | Makes structured data truthful and internally consistent | Validator correctness can affect eligibility, not guarantee rich results or rankings |
| Confirmed | Mobile clean-catalog filter badge showing an active filter | Fixes a reproduced UX/state bug | Treat as CRO/UX until field data proves a search effect |
| Conditional | Separate indexable color, fit or color x fit URLs | Can serve real preselected long-tail intent when inventory, media and demand exist | Google permits separate variant URLs but does not require them; duplicate counts alone cannot approve or remove an owner |
| Conditional | New clean color/fit/thematic landing | Can improve discovery of an evidenced intent with useful assortment and locale content | Requires a decision record with sellable inventory continuity, distinct user/query intent, matching media, factual localized content and internal source link; no uniqueness percentage |
| Conditional | City/local landing | Can support a real city-specific service or pickup intent | No city-name substitution; require actual local terms, proof and demand |
| Conditional | Numeric legacy redirect | Can preserve navigation and external signals when an exact successor exists | Exact mapping and history first; otherwise honest 404/410, never mass-301 to category/base |
| Conditional | Facet `robots.txt` restrictions | Can reduce crawl of non-indexable spaces after cleanup | First remove editorial links and let known URLs expose their current index policy; verify GSC/log effects before expansion |
| Rejected | `meta keywords`, fixed keyword density, mandatory title/description length or text-volume thresholds | None demonstrated | These are not implementation acceptance criteria |
| Do not implement | Hash-selected paraphrases, city lists, FAQ multiplication or near-duplicate blocks created only to appear unique | None; increases factual and scaled-content risk | Reuse one owned fact/policy when the underlying information is global |
| Do not implement | Index every selector combination or generate a city x color x fit x size matrix | None without independent intent and product value | Prevent Cartesian URL/content growth; selectors may remain UI-only |

**Per-task release protocol:**

1. Write a failing regression test and run it (RED).
2. Implement the smallest scoped fix and run focused plus regression tests (GREEN).
3. Run `manage.py check`, `git diff --check`, and the task's static/browser/crawl gate.
4. Commit the code/test slice with the task still marked `[ ]` for deployment.
5. Push the exact commit to `origin/main`; deploy production with the repository release gate; prove deployed SHA and live behavior.
6. After the code SHA is live-verified, prepare one checklist checkpoint with the task marked `[x]`, commit/push/deploy that document, and claim completion only after production proves the checkpoint SHA. No second self-referential documentation checkpoint is required; a failed checkpoint deploy must reopen or correct the status.

## Active priority queue (2026-08-11 continuation)

This queue is the execution order for the current continuation. It supersedes
the historical task numbering below; task numbers remain stable for evidence
links and do not imply that a lower number is a higher-risk fix.

1. **P0 already shipped:** remove the duplicate PDP editorial owner, suppress
   unreviewed generated PDP fallback copy, and deduplicate exact FAQ pairs at
   the shared visible/schema boundary. These changes have live proof recorded
   in Task 4.3a, 4.3b and 4.4a.
2. **P0 active:** make the shared RU/EN publication surface truthful. The
   production baseline is 71 published products, 65 with RU and EN core
   fields, and 836 active FAQ rows with both locale pairs. The first code slice
   is the confirmed generated `variant_meta` defect: remove unowned generated
   descriptions/keyword strings and stop emitting Ukrainian fit text on RU/EN
   variant routes. The next slice is locale-safe selected-color alt fallback.
3. **P0 blocked by an owner decision:** reconcile the shipping threshold and
   other cross-surface facts before centralizing them. Current evidence still
   contains both `2500` and `3000`; no code may choose a value by guesswork.
4. **P1:** publish a real locale completeness gate for the six untranslated
   products and synchronize sitemap/hreflang/indexability with that gate. Do
   not silently copy Ukrainian text into a claimed RU/EN owner, and do not
   create extra pages to compensate for missing translations.
5. **P1/P2:** finish facet/hreflang cleanup and variant-owner decisions only
   after the locale and fact contracts are stable. Preserve selectors and cart
   state; approve a clean color/fit owner only with inventory, media, intent
   and same-locale source evidence.
6. **P2/P3:** process media completeness, individual product corrections and
   alt backfills after the shared system is fixed. Custom Print remains a
   no-touch boundary except for a separately reproduced RU/EN defect.

Each numbered code slice remains independently tested, committed, pushed,
deployed and live-verified before its checklist mark changes to `[x]`.

### Active P0 slice: locale-safe variant metadata

- [x] **P0.1** Remove unowned generated variant descriptions and `meta keywords`,
  localize factual fit/size labels from the active URL locale, and accept a
  variant SEO override only when its source belongs to the requested locale.
  This slice covers standard storefront PDPs only; Custom Print and the DTF
  subdomain/blog remain outside scope.

#### P0.1 release evidence

- Code/test commit: `837e34a56848e80753c1f1e012cacb92b9347f62`
  (`fix(seo): localize variant metadata and remove generated claims`) was
  pushed to `origin/main`, pulled on production, and activated with
  `tmp/restart.txt`.
- Local gates: the focused variant/PDP suite passed `51/51`; `manage.py check`,
  `makemigrations --check --dry-run`, touched-file `py_compile`, and
  `git diff --check` passed. The suite output included expected unrelated
  Nova Poshta fallback logging under SQLite; no test failed.
- Live UK/RU/EN fit-only proof: `/product/classic-tshirt/oversize/`,
  `/ru/product/classic-tshirt/oversize/`, and
  `/en/product/classic-tshirt/oversize/` returned `200`, emitted localized
  factual titles (`оверсайз` / `oversize`), `index, follow`, and self-canonical
  URLs. A size-bearing `/black/m/classic/` URL remained consolidated to the
  base PDP as designed, with a self-inclusive reciprocal hreflang cluster.
- Boundary proof: no `dtf/`, DTF blog/subdomain, Custom Print, product content,
  or catalog data was edited in this slice. DTF wording that remains in an
  existing standard product description is not part of the subdomain and was
  intentionally left untouched.
- This checkpoint claims metadata ownership, locale correctness for the
  tested variant paths, and removal of generated unsupported claims only. It
  makes no ranking, traffic, or conversion claim; full locale publication,
  selected-color alt fallback, and fact-registry work remain open below.

- [x] **P0.2** Keep standard storefront image alt metadata locale-safe when a
  legacy `ProductColorImage.alt_text` value has no RU/EN ownership. UK may
  continue to use the reviewed stored alt; RU/EN use the active locale title
  and localized color with a concise factual fallback. The same resolver feeds
  the SSR hero/gallery, `og:image:alt`, `twitter:image:alt`, and the image AJAX
  response. Custom Print and the DTF subdomain/blog remain outside scope.

#### P0.2 release evidence

- Code/test commit: `3b0b4e5a272162856b8ddc2eca60efa33cb53de1`
  (`fix(seo): keep standard PDP image alts locale-safe`) was pushed to
  `origin/main`. The later catalog-editor recovery merge did not alter this
  SEO diff; it only restored the missing `product_catalog` tables required by
  the storefront runtime.
- TDD/local gates: the new regression reproduced RED against the Ukrainian
  stored alt, then passed GREEN after the locale-owned fallback was added. The
  focused pre-merge SEO/PDP set passed `30/30`; `manage.py check`, touched-file
  compilation, and `git diff --check` passed. A broader post-merge test run is
  blocked by the unrelated catalog-editor migration/test-database baseline;
  that blocker is not part of this SEO diff.
- Production recovery prerequisite: after the catalog release was repaired
  at `e886a8e2592db3b1b3469b97328e7df382afce3d`, `/catalog/` and standard PDP
  routes returned to HTTP 200. The guarded preflight correctly refused a
  duplicate legacy/current table state; no schema-adoption write was performed
  by this SEO checkpoint.
- Live UK/RU/EN proof at production SHA `e886a8e2`: `/ru/product/lord-of-the-
  lending/black/`, `/en/product/bentejne-ts/coyote/`,
  `/ru/product/classic-tshirt/black/`, `/en/product/classic-tshirt/black/`,
  and the UK `/product/classic-tshirt/black/` all returned `200`. Each sampled
  page emitted a locale-consistent selected-color/hero alt in the visible
  image, `og:image:alt`, and `twitter:image:alt`; RU/EN no longer exposed the
  Ukrainian stored alt. Each page emitted `index, follow`, a self-canonical
  URL, and a reciprocal UK/RU/EN/`x-default` hreflang cluster. UK retained its
  stored/manual alt behavior.
- Boundary proof: no `dtf/`, DTF subdomain/blog, Custom Print, configurator,
  product content, or catalog data was edited in this slice. Existing DTF
  wording inside an ordinary standard-product description was intentionally
  left unchanged.
- This checkpoint claims only locale-safe image metadata and verified runtime
  parity. It makes no ranking, traffic, rich-result, or conversion promise.
  Reviewed locale-owned media fields, publication gating, and broader locale
  content parity remain open under Task 3/7.

### Active P1 slice: standard Product locale publication gate

- [x] **P1.1** Publish RU/EN standard Product pages only when raw locale-owned
  title, SEO title, SEO description, at least one editorial/product field and
  every active FAQ pair are present. An incomplete locale remains crawlable
  with `200 + noindex, follow`, is excluded from Product sitemap language
  tuples, and emits no indexable hreflang cluster. UK remains the canonical
  owner; the language switcher and all product/fit/color/cart behavior remain
  available. This slice does not cover CategoryColorLanding, DTF, DTF blogs or
  the Custom Print boundary.

#### P1.1 release evidence

- Code/test commit: `f19b8298a7e87ffc448ec0ad68bd36f37dda9437`
  (`fix(seo): gate untranslated product locales`) was pushed to
  `origin/main`, pulled on production and activated with `tmp/restart.txt`.
- Local TDD gates: the focused multilingual/PDP and pure resolver suite passed
  `29/29` under `test_settings`; `manage.py check`, template compilation,
  touched-file `py_compile` and `git diff --check` passed. The repository's
  existing `makemigrations --check --dry-run` drift remains separate: it
  proposes storefront migration `0090` indexes and was not generated by this
  slice.
- Production raw-data preflight before deploy: `71` published Products;
  exactly `6` had empty RU/EN title, SEO and editorial columns
  (`futbolka-posmikhnys`, `futbolka-bez-zhodnykh-sumniviv`,
  `futbolka-kharkiv-forever`, `futbolka-boiova-kvitochka`,
  `futbolka-kharkiv-vokzalna`, `futbolka-pravyl-nemaie`). No FAQ locale
  incompleteness was found in the remaining published set.
- Live proof at production SHA `f19b8298`: the UK untranslated-product owner
  returned `200`, `index, follow`, and only UK/x-default hreflang; its RU and
  EN pages returned `200`, `noindex, follow`, no hreflang links, and titles/H1
  were not promoted as locale owners. `sitemap-products.xml` returned `201`
  URL rows, retained the UK row and omitted both RU/EN rows for the six
  products. A translated `classic-tshirt/black/` sample returned `200`,
  `index, follow`, and the full reciprocal UK/RU/EN/x-default cluster on all
  three URLs.
- Context7/Django 5.2 verification confirms `Sitemap.get_languages_for_item`
  is the supported per-item language filter and that sitemap alternates are
  generated from the resulting language set. The implementation uses that
  contract instead of disabling multilingual sitemaps globally.
- Boundary proof: no DTF subdomain/blog/module, Custom Print flow or ordinary
  product wording was rewritten. This checkpoint claims only truthful locale
  publication signals and makes no ranking, traffic, rich-result or conversion
  promise.

### Active P1 slice: Product facet alternate suppression and schema locale parity

- [x] **P1.2** Suppress hreflang on standard Product query-facet responses
  (`?color`, `?fit`, `?size`) while keeping those selectors crawlable and
  `noindex, follow`; preserve the full reciprocal cluster on eligible clean
  Product owners; align English Product JSON-LD `inLanguage` with the existing
  `en-UA` HTML/hreflang market locale; refresh stale base-template policy
  comments. This does not change path-owned variant policy, selectors, cart,
  Product content, DTF, DTF blogs or Custom Print.

#### P1.2 release evidence

- Code/test commit: `3e99d9e0e73fa01b04eb699530b44475ef1053bb`
  (`fix(seo): harden product locale signals`) was pushed to `origin/main`,
  pulled on production and activated with `tmp/restart.txt`.
- TDD/local gates: the new RED tests reproduced the facet hreflang leak,
  missing partial-locale ownership coverage and `en-US` schema mismatch; the
  focused locale/sitemap suite passed `35/35`, the path/legacy variant suite
  passed `25/25`, `manage.py check`, template loading, touched-file
  compilation and `git diff --check` passed. A separate 23-test legacy schema
  slice retains three unrelated baseline failures in organization/home schema
  assertions; none exercises this diff's locale contract.
- Live proof at production SHA `3e99d9e0`: `/product/futbolka-posmikhnys/`
  returned `200`, `index, follow`, and only `uk-UA`/`x-default`; its `/ru/`
  and `/en/` owners returned `200`, `noindex, follow`, with no hreflang
  links. `/ru/product/classic-tshirt/?color=black&seo_probe=3e99d9e0`
  returned `200`, `noindex, follow`, and no Product alternate cluster.
  `/en/product/classic-tshirt/black/` returned `200`, `index, follow`,
  `inLanguage: en-UA`, and reciprocal `uk-UA`/`ru-UA`/`en-UA`/`x-default`.
  The live Product sitemap retained UK-only rows for untranslated products
  and full locale rows for translated products; `/healthz/` returned `200`.
- Boundary proof: no DTF subdomain/blog/module, Custom Print flow, product
  wording, catalog data or variant inventory was changed. This checkpoint
  claims only consistent crawl/index signals and schema locale metadata; it
  makes no ranking, traffic, rich-result or conversion promise.

## Priority and dependency checklist

### Task 1: Eliminate linked 404 destinations

- [x] **1.1** Verify current production-backed category rows and URL owners: a published `extra.product_id` resolves to its current slug, missing/draft/malformed references do not render, and the stale `/catalog/custom-print/` destination resolves to the existing same-locale owner.
- [ ] **1.1a** Before adding any legacy numeric redirect, inspect external backlink/GSC/analytics history for the 24 old numeric URLs and map only an exact successor. This does not block removal of internal dead links; it intentionally blocks blanket redirects.
- [x] **1.2** Add service/template regression tests proving published `extra.product_id` rows render a locale-aware current slug URL and authoritative live price, missing/draft references render no link, and `/catalog/custom-print/` normalizes to the matching-locale custom-print owner.
- [x] **1.3** Implement URL and price resolution in `twocomms/storefront/services/category_seo_blocks.py`; do not change the Custom Print configurator view/template/state or create blanket numeric redirects.
- [x] **1.4** Run `storefront.tests.test_phase10_category_seo_blocks`, `storefront.tests.test_phase10b_seo_layout`, and rendered UK/RU/EN assertions. All new assertions pass; retain the three pre-existing synthetic top-menu failures as an explicit baseline, not a green-suite claim.
- [x] **1.5** Commit, push, deploy and live-crawl. Record the deployed SHA, 0 linked 404 and the existing Custom Print locale owners as a link non-regression only; do not use this as authority to inspect or change the configurator.
- [x] **1.6** Prepare this single Task 1 checklist checkpoint with completed code/live evidence, then commit/push/deploy it. Task 1 is considered complete only after production proves this checkpoint SHA; no second docs-only loop is required.

**Files:** `twocomms/storefront/services/category_seo_blocks.py`; `twocomms/storefront/tests/test_phase10_category_seo_blocks.py`; add a focused regression module only if the existing test boundary cannot express URL normalization. No data migration until DB mapping proves it is required.

#### Task 1 execution evidence (checkpoint prepared)

- SEO implementation: `e20ec3932715d05537757dbb9909adae463f4c4b` (`fix(seo): resolve category block product owners`). The slice resolves published product references to the current locale-aware slug and live final price, removes unresolved/draft product references from rendered rails, and normalizes only the known stale Custom Print route to the existing locale owner. It does not modify the Custom Print view, template, state, checkout, analytics or submission contracts.
- Release-gate hardening required to deploy the SEO slice: `ca0437c2` and `157e95d42a231d5e2fd76aba30e26993deb266f6`. The second commit covers the real nested-checkout status path (`twocomms/passenger_wsgi.py`) while preserving fail-closed behavior for staged or unrelated tracked drift.
- Live crawl after `e20ec393`: `output/seo-remediation-2026-08-11/task1-live-e20ec393-20260811T005452Z/crawl/`. It fetched 1,354 URLs, all with final status `200`; linked `404` count is zero, and sitemap/canonical/hreflang crawl assertions passed.
- Independent production proof on 2026-08-11 after deploying `157e95d4`: live branch `main`, `HEAD == origin/main == 157e95d4`, tracked status empty, active venv/static release targets match `157e95d4`, maintenance is absent, and `/healthz/` plus `/` return `200`.
- Canonical deploy evidence: `/home/qlknpodo/TWC/TwoComms_Site/releases/evidence/release-157e95d42a231d5e2fd76aba30e26993deb266f6-1786415906-609b78107e5b4a1d8060fb4f300d1236.json`. It records `status=activated`, previous SHA `e20ec393`, `rolled_back=false`, `rollback_needed=false`, `maintenance_lease_retained=false` and `rollback_status=not_needed`.
- A one-time no-submit link non-regression run covered UK/RU/EN on desktop/mobile and passed 6/6. It is not a Custom Print SEO audit, is not a prerequisite for later catalog work and must not be expanded. An earlier invalid run that emitted tracking POSTs is excluded from evidence.
- External backlink/history mapping for the 24 numeric URLs was not performed. Therefore no redirect conclusion is claimed; 1.1a remains open and independent from the completed internal-link fix.
- The `[x]` state in 1.6 is the checkpoint being prepared by this document. It becomes final only after this exact documentation commit is pushed, deployed and proven on production.

### Task 2: Inventory variant owners, then choose single-page or multi-page policy

- [x] **2.0a** Add failing route/canonical tests proving lowercase canonical segment order and one-hop normalization for exact permutations/case variants; duplicate, conflicting and ambiguous segments must return `404` without partially changing the selected state.
- [x] **2.0b** Implement only the shared path normalizer, run representative color/fit/size selected-state browser checks, commit/push/deploy, prove one final URL and then mark this independent slice complete. Do not change sitemap membership or variant ownership in this slice.

#### Task 2.0 release evidence

- Code/test commit: `2d4d44c88997aef4ce5860c389cc1d5c566b228a` (`fix(seo): normalize equivalent variant paths`), pushed to `origin/main` and pulled on production. The code diff is limited to `twocomms/storefront/views/product.py` and `twocomms/storefront/tests/test_phase7_variants.py`; `.serena/project.yml` remains an unrelated local change.
- TDD and local gates: the mixed-case fit regression reproduced RED (`classic` was selected instead of the stored `OverSize` code), then GREEN after the resolver retained the actual DB code. Focused `PathVariantUrlTests + VariantMerchandisingTests` passed `28/28`; `manage.py check`, `makemigrations --check --dry-run`, `py_compile` and `git diff --check` passed. The full `test_phase7_variants` module has `29` passing tests and four pre-existing failures (one sitemap expectation and three variant meta-title expectations) reproduced on the clean `4f1b0136` baseline; those unrelated assertions were not changed.
- Local browser gate: case/order alias `OVERSIZE/BLACK/?...&fit=classic` produced exactly `301 -> 200` at `/black/oversize/`, preserved `utm_source`/`gclid`, removed the variant query, selected `black + oversize + S`, rendered hero `Black 1`, `1 518 грн` and an enabled Add to Cart. Size-only `M/?...&size=l` produced `301 -> 200` at `/m/?utm_source=audit`, selected `M` and kept Add to Cart enabled. Conflicting/repeated `olive/black/` returned `404`.
- Production browser gate after pull and Passenger restart: `https://twocomms.shop/product/classic-tshirt/CLASSIC/M/BLACK/?utm_source=audit&gclid=live-20&fit=oversize` produced exactly `301 -> 200` at `/product/classic-tshirt/black/m/classic/?utm_source=audit&gclid=live-20`; the owner rendered black variant `29`, size `M`, fit `classic`, offer `TC-0001-ЧОРНИЙ-M`, price `788 грн`, adaptive hero `/media/products/optimized/c3_768w.avif` with original `/media/products/c3.webp`, and enabled Add to Cart. Repeated color `/black/black/` returned `404`. Production `HEAD` and `origin/main` equal `2d4d44c8`; `manage.py check` passed. Existing untracked server diagnostics were preserved.
- Scope boundary: no sitemap membership, canonical ownership policy, schema, metadata text, SEO blocks, variant inventory, Custom Print behavior or Task 2.1 inventory was changed. This task only removes equivalent path aliases and rejects invalid/ambiguous path axes; it makes no ranking or traffic claim.
- [ ] **2.1** Commit a versioned inventory of the full locale surface, not only the 210 UK sitemap entries. Current evidence baseline: 630 indexable locale variant URLs; 196/210 semantic paths (588/630 locale URLs) are current UI/base states; 14 UK color paths (42 locales) are candidates only. Record URL, locale, product, axes, stock policy, media, selected price/availability/cart identity, canonical/hreflang/sitemap/internal links, demand placeholder and proposed owner.
- [ ] **2.2** Obtain GSC/query/landing-page/backlink evidence and decide the contract per axis: a single-page ProductGroup owner, a useful self-canonical multi-page variant, or a non-owner UI state. An allowlist is a site strategy, not a Google requirement; do not approve or remove URLs solely from duplicate-title counts.
- [ ] **2.3** After the decision, add failing tests for approved owners versus UI states, invalid/empty combinations and no unintended Cartesian sitemap emission.
- [ ] **2.4** Implement one shared resolver used by `views/product.py`, `services/variant_meta.py`, schema, chosen sitemap representation and internal-link helpers. Preserve existing selection/cart identity and keep Custom Print out of the diff.
- [ ] **2.5** Define redirect/canonical behavior for changed URLs only after exact owner mapping: exact successor -> one-hop 301; duplicate UI state -> consistent canonical policy; no successor -> 404/410. Do not mass-301 to a category/base and do not combine `noindex` with canonical as a blanket rule.
- [ ] **2.6** Run canonical, hreflang, sitemap and browser preselection checks for representative color-only, fit-only, color×fit and size URLs, plus an explicit regression matrix for the seven confirmed wrong-SSR-hero candidates: `bentejne-ts/coyote`, `death-gbs-ass-ts/coyote`, `kharkiv-district-ts/coyote`, `lord-of-the-lending/black`, `my-little-baby/black`, `pojuy-ts/black`, `where-mi-present-ts/black`. Each URL must either be consolidated to its proven owner or show the right SSR/hydrated image, price, availability and cart identity; unique long copy is not required.
- [x] **2.6a** Align the initial server-rendered PDP hero, LCP preload and social image metadata with the actually active color variant. Keep the base PDP social image owner stable when `main_image` exists, preserve `product.display_image` as the missing-color-image fallback, and verify selected color, hero, price, availability, offer/cart identity, canonical and hreflang across UK/RU/EN without submitting cart or analytics events. This is an independently deployed correctness slice; it does not approve any variant URL as an index owner or complete 2.6.
- [ ] **2.6b** Resolve the independent product-identity mismatch reproduced at `lord-of-the-lending`: product/slug/id `31`, selected black media, image alt and search metadata identify `Lord Of The Lending`, while the live product title and H1 identify `Це Моя Посадка` / `Это Моя Посадка`. Trace the authoritative DB/import owner first, then add a failing identity-parity regression and correct only the proven stale field(s); do not guess whether the slug or title should win and do not mass-rewrite product copy.
- [ ] **2.7** Commit, push, deploy, live-verify and then mark Task 2 `[x]` in a docs checkpoint commit.

#### Task 2.6a release evidence (checkpoint prepared)

- Code/test commit: `10474862bf11ebc2df68d59f87df68d018a58cda` (`fix(seo): align PDP hero and social media assets`), pushed to `origin/main`, pulled on production and activated with a Passenger restart. Production `HEAD` and `origin/main` were both proven at this SHA before the live checks.
- TDD/local gates: five focused SSR/social metadata regressions passed, including selected-color hero, AVIF preload/body source parity, base PDP social-image ownership, self-canonical color social alt and the no-`main_image` fallback where default color differs from `order`. The 20-test `PathVariantUrlTests` plus preload regression passed; `manage.py check`, `makemigrations --check --dry-run`, `py_compile` and `git diff --check` passed. Three unrelated pre-existing `ProductDetailTests` failures remain outside this diff and are not represented as green.
- Raw production HTML: `lord-of-the-lending/black/` immediately rendered `/media/product_colors/2.3.webp`; `bentejne-ts/coyote/` immediately rendered `/media/product_colors/17.3.webp`. In both cases visible hero, OG image, Twitter image and their alt values agreed on the selected asset, while self-canonical and reciprocal UK/RU/EN/x-default links remained intact. These two legacy color assets have no responsive siblings, so no image preload is emitted. The responsive `classic-tshirt/black/m/classic/` control emitted matching `c3` stems in the AVIF preload, body `<picture>`, fallback hero and social image.
- No-submit browser gate: UK and RU `lord-of-the-lending/black/` plus EN `bentejne-ts/coyote/` all returned `200`; selected color, current variant, price, enabled size, active fit, mapped offer ID, Add-to-Cart product ID and hydrated hero matched. Third-party analytics hosts and every non-GET/HEAD request were aborted before navigation; exactly one attempted analytics request per page was blocked, no cart/checkout request was sent, and there were no unexpected JavaScript errors.
- Residual findings are intentionally open rather than hidden by this checkbox: `lord-of-the-lending` has the separate product-title identity mismatch tracked in 2.6b, and RU/EN selected-color image alts remain Ukrainian and are tracked in 3.2b. Neither defect invalidates the verified selected-asset/offer consistency of 2.6a, and neither is claimed fixed by `10474862`.

**Files:** `twocomms/storefront/views/product.py`; `twocomms/storefront/services/variant_meta.py`; sitemap modules; product templates/tests; production inventory evidence under `output/seo-audit-2026-08-10/`.

### Task 3: Make RU/EN publication and structured data genuinely localized

- [ ] **3.1** Add a rendered locale matrix test for standard catalog/PDP pages that fails when RU/EN title, H1, main editorial content, critical commerce UI, FAQ or JSON-LD remains Ukrainian, except approved brand names, SKUs and proper nouns. Exclude Custom Print from this matrix; do not fail on every isolated borrowed word or decorative asset.
- [ ] **3.2** Fix locale-aware URL builders and fallback policy for categories, color landings, PDPs, pro-brand OfferCatalog and FAQ.
- [ ] **3.2a** Add a failing regression for the nine `futbolka-posmikhnys/beige[/classic|oversize]/` locale URLs, then replace the shared 160-character comma-list Ukrainian title at its source with concise descriptive metadata for each actual locale/approved owner. Do not apply a sitewide character-count rewrite.
- [ ] **3.2b** Add a failing selected-color media-alt matrix for standard RU/EN PDP HTML, OG and Twitter metadata, then resolve alt text from reviewed locale-owned fields or a concise factual locale fallback. Current production examples on RU `lord-of-the-lending/black/` and EN `bentejne-ts/coyote/` render Ukrainian alt. Do not translate SKUs/brand names, generate keyword lists or touch Custom Print.
- [x] **3.3** Remove query/noindex alternates from noindex facet pages while preserving full reciprocal self-inclusive hreflang on indexable owners. See P1.2 evidence above.
- [ ] **3.4** Verify translated fields for the six products with missing RU/EN data; keep them consolidated or non-indexable until editorial data exists.
- [ ] **3.5** Do not run a general Custom Print SEO audit. Run only a focused RU/EN localization check. If a specific wrong-language visible-text or related wrong-locale canonical/hreflang defect is reproduced, add one focused failing test and the smallest locale-only fix; otherwise record `N/A`. Prove UK content, configurator state, cart, analytics and submission contracts unchanged without submitting a live request.
- [ ] **3.6** Run standard catalog/PDP locale HTML/schema/sitemap and browser language-switch checks. If 3.5 is triggered, add only its focused RU/EN regression and minimal UK no-submit non-regression. Commit/push/deploy and record evidence before checking Task 3.

**Files:** locale helpers/base template; `catalog.html`, color landing and product templates; `seo_utils.py`; localized tests and sitemap tests.

### Task 4: Replace unsafe generated editorial claims with fact-owned content

- [ ] **4.1** Add failing tests for exactly one rendered PDP editorial owner, deduplicated FAQ questions, and no service-only keyword sentence or hash-selected paraphrase used solely to change n-gram overlap.
- [ ] **4.2** Create a versioned fact registry contract (owner, source field/URL, locale, effective date) for material, weight, print method, wash durability, fit, care, delivery threshold, founding date, donation and location.
- [ ] **4.3** Remove/merge the second generated block across both `services/product_seo_landing.py` and `services/product_seo_block.py`; keep only useful product-specific facts. Do not manufacture lexical variants for uniqueness and keep Custom Print out of the content rewrite.
- [x] **4.3a** Remove the duplicate rendered `product_seo_block` owner from the standard PDP while retaining the existing `product_seo_landing` owner, FAQ, commerce content and interactive selectors. This is a narrow ownership fix; unsafe generated fallback claims remain open for the later 4.1-4.6 fact/content work.
- [x] **4.3b** Disable the generated `product_seo_landing` long-form fallback when no reviewed `Product.seo_bottom_html` override exists. Preserve product query chips, category navigation and the admin override path; the fact-owned replacement remains a later 4.1-4.6 task.
- [ ] **4.4** Deduplicate FAQ at the data/render/schema boundary; retain global policy answers once and product-specific answers only when materially different.
- [x] **4.4a** Add deterministic intra-document exact-pair deduplication at the shared standard-PDP visible/schema boundary. Keep the first active pair by editorial `order,id`, ignore case/whitespace-only duplicates, and preserve conflicting answers for explicit fact review. Global policy/product ownership and DB cleanup remain open in 4.4.
- [ ] **4.5** Add failing tests for the page-1 general catalog editorial block, then remove keyword/city insertion as a content objective and route every retained claim through the fact registry. Specifically verify delivery timing/exchange policy, material/weight, available cuts/sizes, wash durability, donation and location statements; do not replace the current city list with paraphrased city variants.
- [ ] **4.6** Run fact-lint across standard PDP/catalog HTML, JSON-LD, feeds, llms and checkout copy; commit/push/deploy and mark Task 4 only after live parity proof.

**Files:** `twocomms/storefront/views/product.py`; `seo_utils.py`; `services/product_seo_landing.py`; `services/product_seo_block.py`; `twocomms_django_theme/templates/pages/catalog.html`; PDP templates; FAQ models/services/tests; fact-registry docs/tests.

#### Task 4.3a execution evidence (checkpoint prepared)

- Code/test commit: `b2e79884c7f0f092b1b76ec6246c7611988278b0` removes only the `{% product_seo_block product %}` render from the standard PDP and updates the content-order regression to require one editorial owner. The service, helper and tag remain available for the later fact-registry/fallback work because `product_search_keywords.py` still imports shared topic helpers.
- Local gates: focused SEO/PDP suite passed `48/48`; `manage.py check` passed; `makemigrations --check --dry-run` reported no changes; touched Python files compiled; `git diff --check` passed. The unrelated `.serena/project.yml` change was not staged.
- Production deploy: `origin/main`, server `HEAD` and live release are `b2e79884`; the server pulled fast-forward and Passenger was restarted with `tmp/restart.txt`.
- Live UK/RU/EN PDP proof: `/product/my-little-baby/`, `/ru/product/my-little-baby/` and `/en/product/my-little-baby/` all returned `200`, each contained exactly one `data-product-seo-landing`, zero `data-general-product-seo`, and retained `FAQPage` markup. `/custom-print/` and `/healthz/` returned `200` as route/non-regression checks only.
- Scope boundary: this checkpoint does not claim that generated fallback copy is factual, that FAQ questions are globally deduplicated, that variant ownership or locale publication is complete, or that rankings improved. The fallback content risk remains open for the next content/fact task.

#### Task 4.3b execution evidence (checkpoint prepared)

- Code/test commit: `d3642cb81e6fe69267192e9e762531d95eaf4b33` changes only the no-override branch of `build_landing()` to return empty `landing_html`; the top-query/category navigation and `seo_bottom_html` override branch are retained. Tests now fail if generated city, donation, delivery or fit-template copy is published without an editorial owner.
- TDD/local gates: the new RED assertion reproduced the previous 1,886-character generated fallback. After the fix, targeted Phase 15/fit/PDP tests passed `19/19`; `manage.py check`, `makemigrations --check --dry-run`, `py_compile` and `git diff --check` passed. The broader 42-test audit slice retained only the known unrelated baseline failures (two old variant-meta title expectations and one robots color rule fixture).
- Production deploy: the SEO code is `d3642cb8`; after a concurrent cart release (`7366ebd9`) advanced `main`, the checkpoint was merged and the final `origin/main`/server/live release is `7a63b62b`. The server pulled fast-forward and Passenger was restarted with `tmp/restart.txt`; the cart CSS/template release was not modified by this SEO slice.
- Live UK/RU/EN proof: `/product/my-little-baby/`, `/ru/product/my-little-baby/` and `/en/product/my-little-baby/` returned `200`, retained one `data-product-seo-landing` section with tabs, and contained zero `data-general-product-seo`. The generated landing markers `Збройних Сил` and `Київ` were absent; `Новою Поштою` remained only in other factual/support UI blocks, not as generated landing copy.
- Scope boundary: no fact registry, FAQ dedupe, locale translation, variant-owner, sitemap, feed or Custom Print content change is claimed by this checkbox. No ranking or traffic uplift is claimed.

#### Task 4.4a execution evidence (checkpoint prepared)

- Code/test commit: `a6ecf08c81bcd3a882c99b0d704046cdb44d1e5b` adds `_dedupe_product_faq_items()` and routes the existing `product_faq_items` context through it. Because both the visible PDP tab and `faq_schema` consume that one context list, exact-pair suppression cannot drift between HTML and JSON-LD.
- TDD/local gates: the RED import/test proved the boundary did not exist; after implementation, the exact-pair and visible/schema tests passed `2/2`. `manage.py check`, `makemigrations --check --dry-run`, `py_compile` and `git diff --check` passed. An outdated assertion that contradicted its own test name and the restored FAQPage template contract was corrected from schema absence to schema presence.
- Production deploy: `origin/main`, server `HEAD` and the live code release are `a6ecf08c`; the server pulled fast-forward and Passenger was restarted with `tmp/restart.txt`.
- Live UK/RU/EN proof on `my-little-baby`: each locale returned `200` and rendered `5` visible `.tc-faq-item` entries plus `5` `FAQPage.mainEntity` entries, with `0` exact normalized duplicate pairs.
- Regression hardening: `b575f53d` adds a route-level duplicate-row assertion for one visible FAQ and one matching JSON-LD Question, and corrects the template comment to describe the actual evidence boundary without citation promises. The deployed `where-mi-present-hd` control returned `visible=5`, `schema=5`, `exact_duplicates=0`.
- Scope boundary: this does not delete or rewrite production FAQ rows, classify global versus product-specific ownership, resolve conflicting answers, translate FAQ content, or complete 4.4. Custom Print was not inspected or changed. No rich-result, ranking or citation uplift is claimed.

### Task 5: Normalize facets and pagination by route family

- [x] **5.1** Add failing tests for page>=2 self-canonical/crawlable behavior and invalid, duplicate or nonexistent page/facet aliases returning 404. Valid `page>=2` remains a distinct `200`, indexable, self-canonical product slice. Valid filter combinations with zero inventory remain the interactive catalog's `200 + noindex, follow` empty state so Smart Selector controls do not turn into broken 404 links; only body-equivalent invalid aliases are rejected. Treat `page=1 -> clean` as a separate P3 normalization, not a ranking gate. The repository crawler utilities already resolve relative hrefs with `urljoin(source_final_url, href)`, so no crawler-code change was required.
- [x] **5.2** Remove SEO hreflang from noindex facets and stop editorial rails from linking to noindex query states. Editorial-link half shipped in 5.2a; catalog/search hreflang half in 5.2b; standard Product facet coverage remains recorded in P1.2.
- [x] **5.2a** Remove internal UI-state query links (`color`, `fit`, `size`, `sort`, `theme`, `page`, `q`, `availability`, `category`, `collection`) from generated and admin-authored editorial rails while preserving the same URLs in interactive catalog controls. Shipped as `78e28c4c` and live-verified on UK/RU/EN catalog and hoodie routes; the catalog/search hreflang half is now closed separately in 5.2b.
- [x] **5.2b** Suppress SEO hreflang on noindex catalog/search query states while preserving the language switcher, valid query controls and reciprocal alternates on clean owners and page>=2. Do not remove locale alternates from published clean color landings.
- [x] **5.3** Make grey/olive filter exceptions intentional: approved clean owners, or body-equivalent UI states consolidated to the correct owner. `index,follow + non-self canonical` is not automatically an error; reject only mismatched canonicals, unintended index owners and contradictory hreflang. Do not add blanket `noindex + canonical`.
- [x] **5.4** Ensure page>=2 does not render the full page-1 editorial boilerplate; preserve distinct product lists, crawlable pagination and self-canonical URLs. Distinct pagination title/description is optional UX polish, not a hard Google requirement.
- [ ] **5.4a** Measure anonymous cache-key cardinality and catalog query timing for clean, valid facet, invalid facet and page>=2 requests; reject the release if UX selectors regress or invalid 200 aliases still populate cache.
- [x] **5.4a.1** Restore the documented OR contract within the color facet while keeping different inventory axes intersected on the same eligible color variant. This release gate was triggered by production-backed selector evidence, not by a keyword or ranking hypothesis.
- [ ] **5.4a.2** Canonicalize validated cache identities, reject or bypass invalid 200 aliases, align page and fragment invalidation versions, and remeasure default/fragments cardinality without flushing production caches.
- [x] **5.4a.2a** Align page and catalog-fragment invalidation versions so product/category changes cannot leave a stale catalog grid after a page-cache miss. Semantic identity and pagination serialization remain open in 5.4a.2c/2d.
- [x] **5.4a.2b** Canonicalize validated cache identities, reject or bypass invalid 200 aliases, and remeasure default/fragments cardinality without flushing production caches.
- [ ] **5.4a.2c** Decide and implement a low-query semantic identity for redundant parent-theme plus child-collection facets (for example, `theme=brigades&collection=225`) only after measuring the current collection contract; do not add a database query to every cache hit.
- [x] **5.4a.2d** Make pagination query serialization deterministic for equivalent facet permutations while preserving the deliberate tracking-parameter propagation policy; add a cached-response regression before changing link output.
- [ ] **5.5** Run parameter crawl and Search Console sampling, commit/push/deploy, and check Task 5 after live evidence.

**Files:** catalog views/templates, pagination/canonical helpers, `general_catalog_seo.py`, `color_seo_copy.py`, robots/hreflang helpers and tests.

#### Task 5.2a execution evidence (checkpoint prepared)

- `74abf09d` implemented the shared `seo_link_policy` boundary and regression coverage; after the concurrent cart release landed, the rebased production SHA is `78e28c4c`.
- Focused local gate: 50 tests passed, including policy, generated/admin copy, category blocks, catalog UI-filter preservation and clean-owner rendering. The broader 67-test slice retains six pre-existing failures outside this change: three synthetic top-menu expectations and three legacy swatch-shape expectations.
- Production: `HEAD=78e28c4cee60400410bb2bbb14f7993dbd99959d`, tracked/staged diff empty, `manage.py check` clean, `/healthz/` and `/` return `200`.
- Live UK/RU/EN `/catalog/` and `/catalog/hoodie/` responses contain zero query-facet anchors inside editorial scopes while interactive filter controls still contain query links. `/catalog/?color=black` remains `noindex, follow` with the base canonical. `/custom-print/` returns `200` and remains a route-only non-regression check.
- This checkpoint closes only 5.2a. It does not claim hreflang removal, strict facet validation, clean landing ownership, ranking growth or any Custom Print SEO change.

#### Task 5.2b execution evidence (checkpoint prepared)

- Code/test commit: `fb3b9e12` (`fix(seo): suppress hreflang on catalog facets`)
  adds one explicit `suppress_hreflang` context contract for catalog/search
  query states and makes the shared `language_alternates` tag honor it. The
  language-switch helper remains separate and continues to preserve query
  state for users.
- TDD/local gates: the existing rendered regression reproduced RED on
  `/ru/catalog/tshirts/?color=black`: `noindex, follow` and the clean category
  canonical were present, but four query-bearing hreflang links leaked. After
  the fix, the locale/catalog set passed `74/74`; `manage.py check`, touched-file
  `py_compile` and `git diff --check` passed.
- Production deploy: the code was pushed and pulled fast-forward at final SHA
  `3c8e435ad7e0e9fea7c901e1b5af1b94e01a5d45`; Passenger was restarted with
  `tmp/restart.txt`.
- Live proof: UK `?color=black` and RU `?color=coyote` category facets returned
  `200`, `noindex, follow`, a clean same-locale canonical and zero SEO
  hreflang links. The UK black facet retained `29` color-control occurrences
  plus UK/RU/EN language-switch URLs with `?color=black`. The indexable hoodie
  `?page=2` control retained its self-canonical URL and all four reciprocal
  hreflang entries. `/search/?q=hoodie` remained `200 + noindex, follow` with
  zero SEO hreflang; `/healthz/` returned `200`.
- Scope boundary: no clean landing ownership, inventory, product copy, DTF
  subdomain/blog/module or Custom Print behavior was changed. This checkpoint
  claims signal consistency only and makes no ranking, traffic or conversion
  claim.

#### Task 5.1 execution evidence (checkpoint prepared)

- Code/test commit: `6239a64896c82890cfcfc079d6739096abdf8e25`
  (`fix(seo): reject invalid catalog pagination aliases`) was pushed to
  `origin/main`, pulled on production, and activated with `tmp/restart.txt`.
- The implementation introduces one strict paginator for public catalog,
  thematic and category-colour HTML routes. It uses Django's strict
  `Paginator.page()` contract: missing `page` means page 1; malformed,
  duplicate, non-positive and out-of-range values raise `404`; valid page 2+
  keeps its own product slice and canonical URL. The category-colour landing
  canonical now includes `?page=N` for N>1 instead of pointing at page 1.
- Facet validation rejects unsupported route axes, empty values, unknown
  values and duplicate copies of one value before rendering. Existing color
  comma/repeated-key normalization and valid multi-select values remain
  unchanged. A valid filter that simply has no matching inventory remains a
  crawlable UI state with `200 + noindex, follow`; changing that state to 404
  would break the working selector/empty-state workflow and is intentionally
  outside this slice.
- Local gates: the focused catalog/color/facet/selector/editorial suite passed
  `134/134`; `manage.py check`, touched-file `py_compile` and `git diff --check`
  passed. Context7 Django 5.2 documentation confirms that `get_page()` clamps
  invalid input while `page()` raises `InvalidPage`; the release uses the
  latter only on public HTML catalog routes. Existing crawler scripts already
  call `urljoin(page_url, href)` for relative links, so no fixture change was
  necessary.
- Live proof at production SHA `6239a648`: `/healthz/` returned `200`;
  `/catalog/tshirts/?page=2` returned `200`, `index, follow`, self-canonical
  `?page=2`, and a different product slice; `/catalog/tshirts/?page=abc`,
  `?page=999999`, `?fit=not-a-fit`, `?size=3XL` and duplicate `fit` returned
  `404`; `/catalog/tshirts/black/?page=2` returned `200` with a self-canonical
  page-2 URL, while its `?page=999999` returned `404`. A valid color filter
  remains `200 + noindex, follow` with its existing UI behavior.
- Boundary proof: no DTF subdomain/blog/module, Custom Print flow/content,
  product wording, catalog data or variant inventory was changed. This
  checkpoint claims crawl-alias removal and pagination owner consistency only;
  it makes no ranking, traffic, rich-result or conversion promise.

#### Task 5.4 execution evidence (checkpoint prepared)

- Code/test commit: `8aa28228` (`fix(seo): suppress duplicate catalog editorial pagination copy`)
  adds the page-2 regression and gates all category/thematic/color editorial
  sections behind page 1 in both the redesigned catalog and Smart Selector
  template branches. H1, product cards, filters, cart controls and pagination
  remain rendered on page 2.
- TDD/local gates: the new test reproduced RED when the Smart Selector partial
  still rendered the stored category intro on page 2, then passed GREEN after
  the shared partial was corrected. The regression covers both Smart Selector
  and legacy branches. The adjacent catalog/general-selector/color suite
  passed `111/111`; the full Phase 10b module is `9/12` because three
  pre-existing synthetic `top_menu` expectations still fail independently of
  this diff. `manage.py check`, touched-file `py_compile` and `git diff --check`
  passed. Context7 Django 5.2 documentation confirms nested `{% if %}` block
  evaluation and the `page_obj` pagination contract used by the templates.
- Production deploy: code was pushed to `origin/main` and pulled fast-forward
  on production at final SHA `53ec5f4a0bec` (including the concurrent
  `5f251ed6` catalog migration commit); Passenger was restarted with
  `tmp/restart.txt`.
- Live UK page proof at `https://twocomms.shop/catalog/hoodie/` and
  `?page=2`: both returned `200`. Page 1 emitted one each of
  `catalog-category-intro`, `catalog-category-seo-blocks` and
  `catalog-category-description`; page 2 emitted zero of all three and a
  distinct product-link slice. Page 2 title was
  `Худі TwoComms — теплі моделі зі стрітвеар-принтами — сторінка 2`,
  `robots=index, follow`, canonical was the exact `?page=2` URL, and the
  response exposed a `prev` link; page 1 exposed `next`. `/healthz/` returned
  `200`.
- Scope boundary: no DTF subdomain/blog/module, DTF route, Custom Print
  content/configurator, product text, catalog data or variant inventory was
  inspected or changed in this slice. No ranking, traffic, rich-result or
  conversion uplift is claimed.

#### Task 5.4a.1 execution evidence (checkpoint prepared)

- Root cause: the legacy color service, selector chip contract and existing
  integration regression all define multiple colors as an OR choice, but the
  shared inventory-facet resolver required every selected color to exist on
  one product. Production DB evidence made the user impact concrete: `65`
  published products owned black or coyote, only `7` owned both, so the
  `black+coyote` selector suppressed `58` valid OR matches.
- Code/test commit: `5809a221` (`fix(catalog): restore multi-color OR filtering`)
  filters the already fit/thermo-eligible variant set to any selected color.
  Size and availability checks then continue on that filtered set, preventing
  a disjoint color variant from satisfying another selected inventory axis.
- TDD/local gates: the existing multi-color regression reproduced RED by
  returning only the both-color product. A second RED regression proved that
  `color=black,coyote&size=M` must keep the coyote variant with sellable M and
  reject a black-only variant whose M is disabled. Both passed GREEN; the
  color/canonical suite passed `29/29`, the merchandising/selector suite passed
  `64/64`, and `manage.py check`, `py_compile` and `git diff --check` passed.
- Production deploy: `origin/main` and server code were advanced to
  `5809a22186bd810f047b3135e43f2d316ae073fb`; Passenger was restarted. A
  fresh valid `?sort=recommended&color=black,coyote` response returned `200`
  with `16` product links on the first page instead of the previous seven,
  retained both color controls and remained `noindex, nofollow`. Single black
  and coyote controls remained operational; `/healthz/` returned `200`.
- Scope boundary: this changes selector result correctness only. It creates no
  indexable facet URL, SEO copy, landing, canonical, hreflang, product data,
  DTF/subdomain/blog behavior or Custom Print behavior, and makes no ranking
  or traffic claim.

#### Task 5.4a.2a execution evidence (checkpoint prepared)

- Root cause: the anonymous page-cache prefix read product/category versions
  from the default cache alias, while catalog/home/search/thematic contexts and
  the outer catalog grid fragment read the same version names from the
  `fragments` alias. Signals and admin reorder invalidated only the default
  alias; product saves that omitted `updated_at` and variant edits also exposed
  an insufficient inner product-card key. A warmed catalog could therefore
  reuse stale cards after a valid page-cache miss.
- Code/test commit: `e56b6637` (`fix(cache): align catalog fragment
  invalidation`) makes the default alias the single version source and adds
  shared product/category versions to the inner catalog card fragment key.
- TDD/local gates: the warm-catalog title-change regression reproduced RED
  before the fix and passed GREEN after it. Seven focused cache/version tests,
  the catalog/color/merchandising/selector suite (`117/117`), template
  compilation, Django check, touched-file compilation and `git diff --check`
  passed. The full `test_public_product_ordering` module remains `10/11` only
  because of an unrelated existing admin taxonomy expectation for
  `.catalog-taxonomy-row`; that test was not changed in this slice.
- Production release: code was pulled at `e56b6637`; `collectstatic --noinput`
  completed with `0` copied and `1039` post-processed files, followed by
  `compress --force`, `check --deploy`, and the Passenger restart marker.
  `check --deploy` reported only the pre-existing `security.W008` and
  `security.W009` warnings and exited `0`.
- Live proof at the deployed SHA: `/healthz/` returned `200`; clean
  `/catalog/`, valid `/catalog/?color=black`, and `/catalog/?page=2` each
  returned `200`. The clean catalog remained `index, follow` with a self
  canonical, the valid facet remained `noindex, follow` with the clean owner
  canonical, and page 2 remained a distinct `index, follow` self-canonical
  slice with `prev`/`next` pagination. No selector, cart or language-switcher
  behavior was changed.
- Scope boundary: this checkpoint changes cache invalidation only. It does not
  inspect or modify the DTF subdomain/blog/module, DTF route, Custom Print
  content/configurator, product copy, catalog data, variant inventory or SEO
  ownership policy. It makes no ranking, traffic, rich-result or conversion
  claim. Semantic facet identity and pagination serialization remain open in
  5.4a.2c/2d.

#### Task 5.4a.2b execution evidence (checkpoint prepared)

- Code/test commit: `0cec998539ca92afcf7281779b0c17c3c8673b5d`
  (`fix(cache): normalize catalog request identities`) keeps catalog-specific
  identity normalization in `_build_catalog_cache_query()` and restores the
  generic helper's original color-only behavior. It adds cache callbacks for
  the catalog, a resolved-locale identity with `Accept-Language` fallback,
  tracking-parameter page-cache bypass, strict invalid-query rejection,
  page/default-sort redirects, fit-alias normalization and the v6 outer
  fragment identity. The homepage regression proves a warmed `/?page=01`
  cannot suppress the existing `/?page=1` `301`.
- TDD/local gates: the new regressions were RED before the fixes and GREEN
  afterward. The catalog/cache/selector suite passed `131/131`; adjacent
  color/pagination/cache suites passed `42/42`; `manage.py check`, catalog
  template loading, touched-file `py_compile` and `git diff --check` passed.
  The separate `test_public_product_ordering` baseline remains `10/11` only
  because of its unrelated existing `.catalog-taxonomy-row` expectation.
  Context7 Django 5.2 documentation confirms that fragment keys vary by the
  `{% cache %}` arguments and can be reproduced with
  `make_template_fragment_key`; this supports one normalized catalog identity
  for the page and outer grid fragment without flushing production caches.
- Production release: `origin/main`, server `HEAD` and the live release are
  `0cec998539ca92afcf7281779b0c17c3c8673b5d`. `collectstatic --noinput`,
  `compress --force`, `check --deploy` and the Passenger restart completed;
  only the pre-existing `security.W008` and `security.W009` warnings remain.
- Live route proof: `/healthz/`, clean catalog, valid color facet, page 2,
  RU catalog and EN catalog returned `200`; clean/page-2 responses remained
  `index, follow` with self-canonicals, while the color facet remained
  `noindex, follow` with the clean canonical. `page=01` and `page=02`
  redirected one hop to clean/page-2 URLs; `sort=recommended` was removed
  without dropping the category. Invalid sort/category/unknown-key,
  duplicate-category, nonexistent-page, invalid-fit/size and a 5000-digit
  page all returned `404`. The homepage warm-alias proof remained
  `/?page=01 -> 200` followed by `/?page=1 -> 301 /`.
- Tracking proof: `utm_*`, `wbraid`, `gbraid`, `msclkid`, `yclid`, `ref` and
  `ref_` catalog requests returned normal `200` responses and did not write
  anonymous page-cache entries. Equivalent category permutations and
  `regular`/`standard` fit aliases produced identical live response bodies.
- Cache occupancy was measured before and after the live matrix without any
  flush: default file cache `6903 -> 6913 / 8000` (86.4%), fragments
  `10986 -> 11006 / 12000` (91.7%). The small bounded increase is from the
  clean valid identities exercised by the matrix; tracking and invalid aliases
  did not create page-cache writes. No ranking, traffic, rich-result or
  conversion uplift is claimed.
- Residual P2 decisions are explicitly left open in 5.4a.2c: semantic
  parent-theme/child-collection redundancy currently needs a low-query design.
  No DTF subdomain/blog/module, DTF route, Custom Print content/configurator,
  product copy, catalog data or inventory was changed or inspected in this
  slice.

#### Task 5.4a.2d execution evidence (checkpoint prepared)

- Code/test commit: `b82c501d` made cacheable catalog pagination links use the
  same normalized facet identity as the catalog cache (`theme -> collection ->
  audience -> availability -> fit -> size -> color -> thermo`) while leaving
  tracking-parameter requests on the existing raw propagation path. Hotfix
  `36bb1358` added the catalog-only cache version
  `catalog-pagination-v2-20260812`, so already-warmed full-page responses cannot
  continue serving the pre-release parameter order. The fragment identity and
  product/category data contracts were not changed.
- Regression coverage includes pure serializer tests, a cache-version assertion,
  and a two-request cached-response test with 17 published smart-selector
  products and both `classic`/`oversize` fit options. The combined catalog,
  merchandising, selector, cache-hygiene, pagination, color-filter and variant
  suite passed `178/178`; `manage.py check`, touched-file `py_compile` and
  `git diff --check` passed. Context7 Django 5.2 documentation confirms that
  repeated query parameters are preserved by query-string serialization and
  that cache keys must vary by the effective URL identity; this release keeps
  that identity deterministic without caching tracking requests.
- Production release: `origin/main`, server `HEAD` and the live code are
  `36bb13581c02ad9b5a1df1a92f552646fb87344a`. The server pulled the commit and
  Passenger was reloaded with `tmp/restart.txt` after the first pull-only smoke
  showed an old cached HTML response. `/healthz/` returned `200`. Two sequential
  requests to `/catalog/tshirts/?size=M&size=L&fit=oversize&fit=classic&page=2`
  both returned `200` and emitted the deterministic previous-page URL
  `?fit=classic&fit=oversize&size=L&size=M&page=1`; no raw `size -> fit` order
  remained after reload. No DTF subdomain/blog/module, DTF route, Custom Print
  content/configurator, product copy, catalog data or inventory was changed.
- This checkpoint makes no ranking, traffic, rich-result or conversion claim.
  Semantic parent-theme/child-collection identity (`5.4a.2c`) and parameter
  crawl/Search Console sampling (`5.5`) remain open for separate evidence.

#### Task 5.3 execution evidence (checkpoint prepared)

- Production-backed triage found no remaining grey/olive indexability exception
  to patch. The published standard color slugs are `beige`, `black`, `coyote`,
  `menthol`, `pink`, `termo-zelena`, `white` and `white-burgundy`; published
  `CategoryColorLanding` rows exist only for `black` and `coyote`. `grey` and
  `olive` therefore have no approved clean owner and must not be promoted to
  indexable SEO pages or retained as query aliases.
- Regression hardening: `test_unowned_grey_and_olive_color_aliases_redirect_to_clean_category`
  asserts that both unowned aliases return one `301` to the category path.
  Existing valid color-filter coverage continues to require `200 + noindex,
  follow` for an interactive state with no inventory. Context7 Django
  documentation confirms `HttpResponsePermanentRedirect` is a 301 response
  with the supplied `Location` target, matching this owner-consolidation
  contract.
- Live no-follow header proof at production `ba6a3567`: `GET
  /catalog/tshirts/?color=grey` and `?color=olive` each returned `301` with
  `Location: /catalog/tshirts/`; valid `black` and `coyote` returned `200` with
  `noindex, follow` and the category self-canonical. No grey/olive URL emitted
  an indexable body, non-self canonical, or hreflang cluster.
- This slice intentionally adds no city/color landing, no keyword variant,
  and no blanket redirect for valid colors. Smart Selector/query controls
  remain available for actual inventory; clean landing ownership remains
  limited to published, evidenced rows. No DTF subdomain/blog/module or
  Custom Print content/configurator was inspected or changed.

### Task 6: Link only approved clean landings in matching locale

- [ ] **6.1** Add failing tests for same-locale category → color/fit landing links and absence of editorial links to UI-only query facets.
- [ ] **6.2** Implement locale-aware landing URL builders and an allowlist-backed internal-link helper; keep Smart Selector/query state operational.
- [ ] **6.3** For every proposed landing, write a decision record covering sellable inventory continuity, distinct user/query intent, matching media, factual locale content, schema support and at least one same-locale source link before inclusion in the chosen discovery graph. These are evidence categories, not Google-defined numeric thresholds; do not create copy merely to pass a uniqueness percentage.
- [ ] **6.4** Commit/push/deploy and mark Task 6 after crawl/browser proof.

**Files:** `services/color_seo_copy.py`, `services/general_catalog_seo.py`, Smart Selector helpers, category/color landing templates/tests.

### Task 7: Complete variant media, alt text and fit data

- [ ] **7.1** Add data-quality tests that fail when an approved multi-page variant lacks matching media, accurate informative-image alt where needed, sellable rows or applicable measurements. Decorative images may keep empty alt; do not keyword-stuff alt.
- [ ] **7.2** Backfill only verified production assets/measurements; do not invent classic/oversize photos or claim a color image that does not exist.
- [ ] **7.3** Hide or consolidate unsupported fit states while retaining the working selector for valid UI states.
- [ ] **7.4** Run representative mobile/desktop browser checks and schema/media audits; commit/push/deploy and check Task 7.

**Files:** variant/media models and assignment services; PDP gallery/alt helpers/templates; focused data-quality tests and reviewed admin/backfill command.

### Task 8: Align ProductGroup, MemberProgram, Offer counts and merchant feeds

- [ ] **8.1** Add failing tests that compare homepage `offerCount`, sitemap, feed and eligible public products from one queryset/snapshot.
- [ ] **8.2** Implement the shared public eligibility predicate and variant resolver in schema, feeds and llms generation.
- [ ] **8.3** Replace unsupported `MemberProgramTierBenefit` with documented truthful enumeration plus `membershipPointsEarned`, or remove MemberProgram until the business rule is verified.
- [ ] **8.4** Make selected variant schema/feed URLs, images, price and availability agree with the rendered page and canonical policy.
- [ ] **8.5** Run Rich Results/Schema Validator checks and feed parsers, then commit/push/deploy and mark Task 8.

**Files:** `twocomms/storefront/seo_utils.py`; ProductGroup/Offer schema builders; merchant feed modules; llms generator; tests and validator evidence.

### Task 9: Correct mobile filter state and performance bottlenecks

- [ ] **9.1** Add failing browser/JS tests for a clean URL showing filter badge `0` and for back/forward state transitions.
- [ ] **9.2** Fix state derivation without changing catalog availability or analytics contracts; preserve Custom Print.
- [ ] **9.3** Run three sequential mobile Lighthouse traces per representative catalog/PDP URL and record median/p75; do not call lab opportunities a field ranking penalty.
- [ ] **9.4** Obtain dated CrUX/GSC/RUM evidence where available, then commit/push/deploy and mark Task 9.

**Files:** catalog filter JS/templates/styles; Lighthouse runner and browser tests; no real ad/purchase test events.

### Task 10: GEO/AI factuality and monitoring contract

- [ ] **10.1** Add a fact/entity registry test covering founding date, delivery threshold, address/hours, donation and price range across visible text, schema, feeds and llms.
- [ ] **10.2** Remove unverified ClothingStore coordinates/hours and conflicting founding/entity claims unless the business owner supplies current evidence.
- [ ] **10.3** Replace request-time `dateModified=now()` with source `updated_at` and localize pro-brand OfferCatalog URLs.
- [ ] **10.4** Create a monthly UK/RU/EN query/citation ledger with date, country, device, model/search engine, cited URL and factuality result; no promise of citation boost.
- [ ] **10.5** Commit/push/deploy and mark Task 10 only after the monitoring baseline is reproducible.

**Files:** entity/schema helpers, pro-brand template, llms/robots generators, governance docs, monitoring script/tests.

## Final release gate

- [ ] Remediation-owned standard catalog/PDP sitemap + one-hop crawl has 0 linked 404 and no unintended SEO redirect chains. Custom Print is route/link non-regression only.
- [ ] All remediation-owned standard catalog/PDP sitemap URLs are approved owners with 200, indexability and self-canonical.
- [ ] Standard catalog/PDP RU/EN visible content and JSON-LD are locale-correct; hreflang is reciprocal and self-inclusive. Custom Print is governed only by the focused 3.5 exception.
- [ ] Variant selected state, media, metadata, schema and feed agree.
- [ ] Facts are single-source and no duplicate/contradictory PDP blocks remain.
- [ ] Mobile purchase path, cart and analytics pass for remediation-owned catalog/PDP changes. Custom Print remains outside remediation; only run the smallest no-submit shared-dependency regression when a shared dependency changed or 3.5 was triggered.
- [ ] No task created URLs/text for keyword density, n-gram uniqueness, city substitution or exhaustive color×fit×size coverage; every new owner has documented user value and evidence.
- [ ] GSC/CrUX/RUM limitations and residual risks are recorded; no ranking-growth claim is made without measurement.
