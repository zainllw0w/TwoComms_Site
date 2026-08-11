# TwoComms SEO/GEO Remediation Design

**Status:** approved for implementation by the user's explicit request to proceed sequentially from the production audit.

**Goal:** remove confirmed crawl/indexability defects, then make variant, locale, content, structured-data and GEO signals describe one coherent set of public URL owners without breaking the Custom Print configurator.

## Context and constraints

- The presentation's first nine slides are excluded; the production audit covers slides 10–86 plus independent code/DB/crawl evidence.
- The current worktree contains unrelated PDP/mobile changes. SEO remediation runs in an isolated worktree and publishes only its reviewed commits.
- Custom Print is a working commerce flow. Its behavior, state model, media and analytics are out of scope; only stale links or narrowly proven redirects may change.
- No mass city pages, Cartesian product variants, blanket redirects, or blanket `robots.txt` blocks will be introduced without an owner, demand/inventory evidence and a reversible migration map.
- Every code slice uses test-first verification, an independent spec/quality review, a fresh commit, push to `origin/main`, production fast-forward deploy, restart when required, and live proof before its checklist item is marked complete.

## Selected approach

Use a staged URL-owner and source-of-truth approach rather than a global canonical/noindex sweep:

1. Remove dead internal destinations first. Resolve published product references to current slug URLs, drop unavailable product rows, and normalize only the stale Custom Print path.
2. Define an explicit variant allowlist and a shared resolver. The resolver will feed sitemap, canonical/hreflang, meta, selected UI, schema and merchant feeds so color, fit and size cannot drift independently.
3. Make locale publication conditional on translated visible content and locale-correct structured data. Missing translations are reported and consolidated, not silently copied from Ukrainian.
4. Replace generated PDP boilerplate with one fact-owned editorial block and deduplicated FAQ content. Claims must have a source, locale and effective date before they reach HTML, JSON-LD, feeds or llms files.
5. Normalize facet and pagination behavior by route family, then link only approved clean landings. Measure crawl reduction and field behavior after deployment; lab Lighthouse output is not treated as a ranking penalty.

## Alternatives rejected

| Approach | Why it is rejected |
|---|---|
| Block every query parameter in `robots.txt` immediately | Google may not see existing `noindex`; valid page 2 and approved landing discovery can be lost; current policy is mixed. |
| Canonicalize all color/fit/size URLs to the base PDP | Destroys legitimate long-tail owners and conflicts with Google's supported preselected variant URLs. |
| Generate a page for every city x color x fit x size | Creates thin/scaled content, crawl bloat and cannibalization without evidence of local service or demand. |

## Release and rollback model

The branch `codex/seo-remediation-2026-08-11` is pushed directly to `origin/main` only after the slice passes local tests and review. Production is pulled with `git pull --ff-only`, runs the required Django checks/static/compressor steps, and Passenger is restarted through `tmp/restart.txt` when Python/template code changes. A failed live gate leaves the checklist open and triggers rollback to the last verified SHA; no production DB mutation is performed without a separate reviewed data migration or management command.

## Acceptance principles

- HTTP, sitemap, canonical, hreflang, visible copy, JSON-LD and feeds are checked together for representative UK/RU/EN pages.
- A finding is marked fixed only with fresh evidence: test output, deployed SHA and live response/browser or crawl proof.
- No claim of ranking growth is made without dated GSC/GA4/CrUX/RUM measurement; Context7 guidance is used for technical contracts, not as a promise of traffic.
