# Management Statistics Decision Cockpit - Stage 2 QA

Date: 2026-08-08

## Scope

Stage 2 replaces text-heavy statistics details with a compact decision surface:

- five primary period metrics with explicit basis, time field, and completeness;
- truthful single-day activity with a 24-hour baseline;
- reconciled funnel facts (`entered`, `advanced`, `lost`, `in_progress`);
- persistent stage selection and a contextual details drawer;
- visual modules for loss reasons, time on stage, ownership, discounts, current stages, and objections;
- separate customer objections and technical signal events;
- reduced-motion behavior for all Stage 2 transitions.

## Browser Matrix

| Viewport | Decision rail | Funnel | Horizontal overflow |
| --- | --- | --- | --- |
| 1440 | 5 equal columns | 5-column lanes | none |
| 1280 | 5 equal columns | 5-column lanes | none |
| 768 | 3-column rail | 5-column lanes | none |
| 390 | 2-column rail | vertical timeline | none |
| 320 | 2-column rail, revenue spans final row | vertical timeline | none |

Measured `document.documentElement.scrollWidth === window.innerWidth` at every viewport.

## Round 3 Evidence

- At 320 px the rail resolves to `124.5px 124.5px`; the revenue slot spans `1 / -1`.
- A zero-activity day renders 24 hourly markers, all with the zero baseline, in a 72 px plot.
- A simulated six-stage funnel keeps every desktop node at 256 px; the second lane does not stretch its single node.
- The same six-stage funnel becomes a one-column timeline at 390 px.
- First and last activity tooltips remain inside the activity card.
- Desktop drawer closes through backdrop, Escape returns focus, and Tab/Shift+Tab stay inside the dialog.
- Mobile drawer is a bottom sheet at 390 and 320 px; the hidden backdrop does not close it and the close button works.
- With `prefers-reduced-motion: reduce`, stage, fill, and drawer transition durations resolve to `0s`.
- Browser console and page error collections were empty.

## Automated Verification

- Statistics, funnel, and inline UI suite: 234 tests.
- Commerce regression suite: 36 tests.
- Django system check: no issues.
- `git diff --check`: clean.

The only observed warning is the existing test-environment warning about a missing offline-compress manifest. It is not an application error and is handled by the normal deployment asset build.

## Local Visual Artifacts

Artifacts are stored under `twocomms/output/playwright/stage2-current/`, including:

- `current-1440.png`
- `current-768.png`
- `current-390.png`
- `current-320.png`
