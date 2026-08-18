# Gemini API Health Dashboard Design

**Date:** 2026-08-18  
**Status:** Approved by the product request in this thread

## Goal

Add a dedicated `API` tab to the Instagram bot management page where an
administrator can understand the health of all six configured Gemini aliases,
the observed behavior of `gemini-3.7-flash` and `gemini-3.6-flash`, and the
evidence-based reason a request fell back from 3.7 to 3.6.

## Product decisions

- The surface is a first-class bot tab named `API`, not part of LeadOps Checker.
- The default view is passive. Loading or refreshing the tab never calls
  Gemini and never consumes tokens.
- A manual probe is available for one selected alias and one selected model.
  It uses the existing redacted health-probe path, a tiny bounded payload, a
  short timeout, and a per-alias/model cooldown. It never includes customer
  messages or conversation context.
- Secret values, raw provider bodies, prompt text, and token values are never
  returned to the browser. Aliases are rendered as `API key 1` through
  `API key 6`.
- Sparse telemetry is shown as `insufficient observations`; the UI must not
  claim contractual uptime from a handful of live requests.

## Recommended architecture

### Read API

Add an admin-only GET endpoint beside the bot APIs:

`/bot/api/gemini-health/`

The response contains a schema version, generation timestamp, a bounded
24-hour window, aggregate counts, the current derived pool state, six rows,
and the latest fallback explanation. The server performs all aggregation in
one bounded query path from `GeminiRequestAttempt` plus the current
`GeminiKeyState`/`GeminiModelState` snapshots. The endpoint returns no raw
attempt body and caps the number of records considered.

Each row contains:

- stable display alias and role/project metadata;
- current derived state (`available`, `busy`, `cooldown`, `unconfigured`);
- per-model (`3.7`, `3.6`) observed state, success/failure counts, last
  observation, latency, and a 24-segment history rail;
- the latest normalized fallback reason, if a request first failed on 3.7 and
  later succeeded on 3.6;
- an explicit no-data state when there is no observation for a model.

The 24 segments represent observation buckets over the selected window, not
scheduled checks. Segment colors are semantic:

- green: successful observation;
- amber: a transient failure/retry recovered within the request or bucket;
- red: a terminal failure or an unrecovered failure;
- gray: no observation.

Every segment also has text/ARIA metadata, so color is never the only signal.

### Manual probe API

Add an admin-only POST endpoint:

`/bot/api/gemini-health/probe/`

The request accepts only an allowlisted alias and model (`gemini-3.7-flash` or
`gemini-3.6-flash`). It rejects reviewer mode, missing aliases, invalid models,
and a still-active cooldown. A cache lock prevents concurrent probes for the
same alias/model and a short rate limit prevents repeated clicks. The probe
uses no customer context and a minimal output budget. Its bounded result is
persisted through the existing redacted attempt telemetry with role
`health_probe`, then the read API can display it in the next refresh.

There is no cron, page-load probe, or global polling loop. The tab loads on
activation, refreshes only while visible at a conservative interval, pauses
when hidden, and exposes a manual refresh that reads the database only.

### UI

The `API` tab follows the existing dark management visual system:

- a compact summary strip with six configured, available, cooldown, and
  unavailable counts plus `updated_at`;
- a fallback explanation line showing the effective model and the latest
  normalized reason, for example `3.7 timeout -> 3.6 succeeded`;
- six responsive rows. Each row has a state dot and label, two labeled rails
  (`3.7` and `3.6`), observed success/latency metrics, and a small row-level
  probe control;
- a visible legend for green/amber/red/gray and a plain-language note that
  the rail reflects real observations, not hourly synthetic uptime checks.

The layout remains a sibling panel rather than nested cards, collapses to a
stack on narrow screens, supports horizontal rail scrolling on very narrow
screens, and honors `prefers-reduced-motion`.

## Fallback classification

The server maps persisted bounded failure kinds to short explanations:

`read_timeout` -> `3.7 timed out`; `http_5xx`/overload -> `provider
overload`; `quota_429` -> `quota cooldown`; `model_not_found` or
`permission_denied` -> `model unavailable`; `invalid_key` -> `invalid key`;
`invalid_payload`/`empty` -> `invalid response`; `lease_busy` or
`quarantined` -> `key busy/quarantined`.

The explanation is emitted only when the persisted request sequence proves a
3.7 failure followed by a 3.6 attempt. It is never inferred from the current
select value or from token counts.

## Error and privacy handling

- A database/API failure renders a non-blocking stale-data message and keeps
  the rest of the bot settings usable.
- A probe timeout is classified as a timeout, not as an HTTP 5xx.
- Provider error detail is normalized server-side and truncated to the
  existing bounded classification fields.
- Reviewer/sandbox users receive neither the tab data nor probe endpoint.
- All endpoint payloads are JSON-schema-shaped and versioned so the UI can
  fail closed if fields are missing.

## Verification strategy

Use a focused, non-spammy gate:

1. Unit-test the aggregation and fallback-sequence classifier with synthetic
   `GeminiRequestAttempt` rows, including no-data, retry-recovered, terminal,
   and mixed-model cases.
2. Test GET/POST authorization, allowlists, rate limiting, redaction, and
   response shape without network calls (mock `probe_key`).
3. Test the bot template/tab lifecycle and reviewer exclusion, plus the
   existing JavaScript syntax check.
4. Run `manage.py check`, migration drift, targeted management tests,
   `compileall`, and `git diff --check`; verify the browser surface once on
   desktop and once on a narrow viewport.
5. After commit and push, pull `main` on production through the approved SSH
   command and verify the deployed SHA, endpoint authorization, six-row
   payload, and no provider calls on a read-only refresh.

## Explicit non-goals

- No hourly synthetic uptime claim.
- No continuous background provider polling.
- No customer-context replay or production message generation.
- No migration of the existing LeadOps Checker UI in this slice; it remains
  available separately while the bot gains the discoverable API surface.
