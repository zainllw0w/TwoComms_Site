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
- TDD and local gates: the mixed-case fit regression reproduced RED (`classic` was selected instead of the stored `OverSize` code), then GREEN after the resolver retained the actual DB code. Focused `PathVariantUrlTests + Fable5VariantMerchandisingTests` passed `28/28`; `manage.py check`, `makemigrations --check --dry-run`, `py_compile` and `git diff --check` passed. The full `test_phase7_variants` module has `29` passing tests and four pre-existing failures (one sitemap expectation and three variant meta-title expectations) reproduced on the clean `4f1b0136` baseline; those unrelated assertions were not changed.
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
- [ ] **3.3** Remove query/noindex alternates from noindex facet pages while preserving full reciprocal self-inclusive hreflang on indexable owners.
- [ ] **3.4** Verify translated fields for the six products with missing RU/EN data; keep them consolidated or non-indexable until editorial data exists.
- [ ] **3.5** Do not run a general Custom Print SEO audit. Run only a focused RU/EN localization check. If a specific wrong-language visible-text or related wrong-locale canonical/hreflang defect is reproduced, add one focused failing test and the smallest locale-only fix; otherwise record `N/A`. Prove UK content, configurator state, cart, analytics and submission contracts unchanged without submitting a live request.
- [ ] **3.6** Run standard catalog/PDP locale HTML/schema/sitemap and browser language-switch checks. If 3.5 is triggered, add only its focused RU/EN regression and minimal UK no-submit non-regression. Commit/push/deploy and record evidence before checking Task 3.

**Files:** locale helpers/base template; `catalog.html`, color landing and product templates; `seo_utils.py`; localized tests and sitemap tests.

### Task 4: Replace unsafe generated editorial claims with fact-owned content

- [ ] **4.1** Add failing tests for exactly one rendered PDP editorial owner, deduplicated FAQ questions, and no service-only keyword sentence or hash-selected paraphrase used solely to change n-gram overlap.
- [ ] **4.2** Create a versioned fact registry contract (owner, source field/URL, locale, effective date) for material, weight, print method, wash durability, fit, care, delivery threshold, founding date, donation and location.
- [ ] **4.3** Remove/merge the second generated block across both `services/product_seo_landing.py` and `services/product_seo_block.py`; keep only useful product-specific facts. Do not manufacture lexical variants for uniqueness and keep Custom Print out of the content rewrite.
- [ ] **4.4** Deduplicate FAQ at the data/render/schema boundary; retain global policy answers once and product-specific answers only when materially different.
- [ ] **4.5** Add failing tests for the page-1 general catalog editorial block, then remove keyword/city insertion as a content objective and route every retained claim through the fact registry. Specifically verify delivery timing/exchange policy, material/weight, available cuts/sizes, wash durability, donation and location statements; do not replace the current city list with paraphrased city variants.
- [ ] **4.6** Run fact-lint across standard PDP/catalog HTML, JSON-LD, feeds, llms and checkout copy; commit/push/deploy and mark Task 4 only after live parity proof.

**Files:** `twocomms/storefront/views/product.py`; `seo_utils.py`; `services/product_seo_landing.py`; `services/product_seo_block.py`; `twocomms_django_theme/templates/pages/catalog.html`; PDP templates; FAQ models/services/tests; fact-registry docs/tests.

### Task 5: Normalize facets and pagination by route family

- [ ] **5.1** Add failing tests for page>=2 self-canonical/crawlable behavior and invalid, duplicate, empty-result or nonexistent combinations returning 404. Treat `page=1 -> clean` as a separate P3 normalization, not a ranking gate. Correct the crawler fixture/utility to resolve relative hrefs against the source final URL before trusting route-level inlink counts.
- [ ] **5.2** Remove SEO hreflang from noindex facets and stop editorial rails from linking to noindex query states.
- [ ] **5.3** Make grey/olive filter exceptions intentional: approved clean owners, or body-equivalent UI states consolidated to the correct owner. `index,follow + non-self canonical` is not automatically an error; reject only mismatched canonicals, unintended index owners and contradictory hreflang. Do not add blanket `noindex + canonical`.
- [ ] **5.4** Ensure page>=2 does not render the full page-1 editorial boilerplate; preserve distinct product lists, crawlable pagination and self-canonical URLs. Distinct pagination title/description is optional UX polish, not a hard Google requirement.
- [ ] **5.4a** Measure anonymous cache-key cardinality and catalog query timing for clean, valid facet, invalid facet and page>=2 requests; reject the release if UX selectors regress or invalid 200 aliases still populate cache.
- [ ] **5.5** Run parameter crawl and Search Console sampling, commit/push/deploy, and check Task 5 after live evidence.

**Files:** catalog views/templates, pagination/canonical helpers, `general_catalog_seo.py`, `color_seo_copy.py`, robots/hreflang helpers and tests.

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
