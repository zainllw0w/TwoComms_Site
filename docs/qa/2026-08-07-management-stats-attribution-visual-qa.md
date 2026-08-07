# Management Statistics Attribution Visual QA

**Date:** 2026-08-07  
**Scope:** advertising attribution coverage, commercial signal path, responsive layout and date-range interaction in the Instagram management statistics view.  
**Branch:** `codex/management-bot-statistics-redesign`

## Design Decision

The advertising view now uses two complementary visual primitives:

- A single coverage ring for the part-to-whole question: confirmed advertising, partial linkage and conversations without attribution. The center keeps the absolute denominator visible, so a percentage cannot be read without its population.
- A six-step signal path for operational movement: conversations, qualification, product recognition, payment-link issue, payment-link view and verified payment. Each step keeps its absolute count and a proportional rail. This is deliberately labelled as separate signals, not a descending cohort, because the source events are not guaranteed to be monotonic.

The empty state keeps the same geometry but changes the ring to a neutral outline and uses a baseline message for zero activity. This preserves the meaning of “no events in the selected period” without inventing a bar or removing the diagnostic surface.

## Server Contract

The API exposes the attribution population explicitly:

`conversation_population`, `confirmed_conversations`, `partial_conversations`, `unattributed_conversations`, `coverage_percent`, `status` and `campaign_count`.

Partial attribution is only counted when an ad source or creative URL exists without a campaign identity. Organic conversations are not guessed to be advertising traffic. The attribution basis remains visible as `current_client_snapshot`; the UI does not claim historical event attribution that is not persisted.

## Verification Matrix

| Check | Result | Evidence |
| --- | --- | --- |
| API attribution contract | PASS | `management.tests_ig_stats_visuals`: `31/31 OK` |
| UI/template contracts | PASS | `ClientWorkspaceTemplateContractTests`: `77/77 OK` |
| Inline JavaScript parse | PASS | `test_bot_page_inline_scripts_have_valid_javascript_syntax`: `1/1 OK` |
| Populated fixture | PASS | 4 conversations, 1 confirmed attribution, 1 partial, 2 unattributed, ring shows `25%`; first signal rail has target width `25` |
| Attribution detail | PASS | Click segment -> `Підтверджена реклама / 1 · 25% від діалогів у періоді`; Escape and outside click close it |
| Signal detail | PASS | Click step -> count/share detail; Escape closes it |
| Preset periods | PASS | `1`, `7`, `30` and `0` days return live API responses and update the ring |
| Custom period | PASS | `2026-08-01` to `2026-08-07` updates the same view without a page reload |
| Empty custom period | PASS | `2020-01-01` returns neutral ring, zero rails and `Немає діалогів у періоді` |
| Responsive overflow | PASS | `scrollWidth == clientWidth` at `1440`, `768`, `390` and `320` px |
| Browser runtime | PASS | No `pageerror` or console errors in the populated range matrix |

## Visual Evidence

Screenshots captured from the isolated QA server:

- `/tmp/stats-attribution-polished-1440.png`
- `/tmp/stats-attribution-polished-768.png`
- `/tmp/stats-attribution-polished-390.png`
- `/tmp/stats-attribution-polished-320.png`
- `/tmp/stats-attribution-polished-empty-390-after.png`

The mobile signal path wraps to two columns and adds a short vertical bridge between rows. Labels are slightly increased below 390px, while the exact values remain available through the button label and the in-flow detail.

## Release Gate

Before shipping this branch, rerun the focused tests, `manage.py check`, migration drift, JavaScript syntax extraction and `git diff --check`. Then commit the QA evidence with the implementation, push the feature branch, fast-forward `main`, deploy and verify the deployed SHA plus authenticated stats responses for preset and custom ranges.
