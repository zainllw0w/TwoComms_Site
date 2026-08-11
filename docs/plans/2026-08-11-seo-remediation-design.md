# TwoComms SEO/GEO Remediation Design

**Status:** approved for implementation by the user's explicit request to proceed sequentially from the production audit.

**Goal:** remove confirmed crawl/indexability defects from the standard catalog and PDP surface, then make variant, locale, content, structured-data and GEO signals describe one coherent set of public URL owners.

## Context and constraints

- The presentation's first nine slides are excluded; the production audit covers slides 10–86 plus independent code/DB/crawl evidence for the standard catalog/PDP surface.
- The current worktree contains unrelated PDP/mobile changes. SEO remediation runs in an isolated worktree and publishes only its reviewed commits.
- Custom Print is excluded from content, variant, schema, metadata, canonical and broad crawl review. The deployed `/catalog/custom-print/` normalization was external category-link hygiene and grants no follow-up scope. Only a specifically reproduced RU/EN localization defect may receive a locale-only fix; UK content and the working flow must remain unchanged.
- No mass city pages, Cartesian product variants, blanket redirects, or blanket `robots.txt` blocks will be introduced without an owner, demand/inventory evidence and a reversible migration map.
- No page or paragraph is created to satisfy keyword density, n-gram uniqueness, fixed title length or text-volume targets. Shared facts stay shared; variant copy exists only for real buyer-visible differences.
- Every code slice uses test-first verification, an independent spec/quality review, a fresh commit, push to `origin/main`, production fast-forward deploy, restart when required, and live proof before its checklist item is marked complete.

## Selected approach

Use a staged URL-owner and source-of-truth approach rather than a global canonical/noindex sweep:

1. Keep the already-deployed dead-link fix as the first completed slice. It resolves published product references to current slug URLs and drops unavailable rows; its stale `/catalog/custom-print/` normalization was external category-link hygiene, not a Custom Print audit.
2. For standard catalog products only, first normalize exact-equivalent segment order/case to one URL without changing ownership. Then decide variant ownership from GSC/demand/inventory/media evidence and implement a shared resolver. The resolver will feed sitemap, canonical/hreflang, meta, selected UI, schema and merchant feeds so color, fit and size cannot drift independently.
3. Make standard catalog/PDP locale publication conditional on translated visible content and locale-correct structured data. Missing translations are reported and consolidated, not silently copied from Ukrainian. Custom Print follows only the narrow RU/EN exception above.
4. Replace generated PDP boilerplate with one fact-owned editorial block and deduplicated FAQ content. Claims must have a source, locale and effective date before they reach HTML, JSON-LD, feeds or llms files.
5. Normalize facet and pagination behavior by route family, then link only approved clean landings. Measure crawl-distribution changes and field behavior after deployment; do not assume crawl reduction or ranking gains, and do not treat lab Lighthouse output as a field ranking penalty.

## Alternatives rejected

| Approach | Why it is rejected |
|---|---|
| Block every query parameter in `robots.txt` immediately | Google may not see existing `noindex`; valid page 2 and approved landing discovery can be lost; current policy is mixed. |
| Canonicalize all color/fit/size URLs to the base PDP | Can consolidate variant signals into the base owner and is unsuitable where evidence supports an independently useful, preselected variant intent. Google's support for separate variant URLs is permission, not a mandate to index every variant. |
| Generate a page for every city x color x fit x size | Creates a high risk of scaled/thin content, crawl expansion and intent cannibalization when demand, inventory and local value are not evidenced. |
| Rewrite every title/body until each URL is lexically unique | Google does not require long unique variant copy; hash/paraphrase generation can preserve false facts while increasing scaled-content risk. |

## Release and rollback model

The branch `codex/seo-remediation-2026-08-11` is pushed directly to `origin/main` only after the slice passes local tests and review. Production is pulled with `git pull --ff-only`, runs the required Django checks/static/compressor steps, and Passenger is restarted through `tmp/restart.txt` when Python/template code changes. A failed live gate leaves the checklist open and triggers rollback to the last verified SHA; no production DB mutation is performed without a separate reviewed data migration or management command.

## Acceptance principles

- HTTP, sitemap, canonical, hreflang, visible copy, JSON-LD and feeds are checked together for representative standard catalog/PDP UK/RU/EN pages. Custom Print receives only route/link non-regression, plus a focused RU/EN locale regression if its narrow exception is triggered.
- A finding is marked fixed only with fresh evidence: test output, deployed SHA and live response/browser or crawl proof.
- No claim of ranking growth is made without dated GSC/GA4/CrUX/RUM measurement; Context7 guidance is used for technical contracts, not as a promise of traffic.
