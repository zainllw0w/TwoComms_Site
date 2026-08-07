# Management Statistics Visual Audit

**Date:** 2026-08-08  
**Scope:** Instagram management statistics, overview, advertising attribution, funnel, activity and detail panels.  
**Audience:** manager/operator who must understand the state of sales in one scan, then drill into one cause.

## Evidence First

| Observation | Evidence | Root implication |
| --- | --- | --- |
| Real messages do not reach the activity series | Production MySQL: `totals.messages=291`, but every `message_series.items[*].messages=0`; ORM `TruncDate(Coalesce(...))` returns one `bucket=None` row | Backend aggregation is not a trustworthy chart source on MariaDB |
| The visible dark column is not a value | `.bot-stats-activity-stack` has a full-height background even when all segment bases are `0%` | A no-data state is visually misread as a large value |
| One-day mode wastes the whole panel | One item still renders a 150px chart rail with a single centered column | Density must control the visualization, not only the data range |
| Tooltip can cover neighboring content | Tooltip is absolutely positioned inside a column and is not clamped to the scroll viewport | Tooltip placement needs viewport-aware edge anchoring |
| Advertising looks absent rather than measurable | Production `ad_analytics.totals` is zero and the UI collapses the section into one sentence | Empty attribution needs an explicit diagnostic state, not a blank card |
| Details are technically complete but visually scattered | Screenshot shows long tables with large unused right-side areas and repeated `0 / 0% / Мало даних` | Sparse values need compact visual summaries and progressive disclosure |
| Event cohorts are not always monotonic | Production funnel has `entered=101` then `entered=6` and event-specific gaps | A single descending bar implies false causality; show cohort counts and conversion separately |

## Visual Thesis

> **A quiet dark operations console with one luminous signal per decision:** a ring for composition, a compact time pulse for movement, a stepped funnel for loss, and a campaign/product ledger for action.

This is an application surface, not a marketing dashboard. The design uses the existing typography and color language, removes decorative containers where they do not add meaning, and spends emphasis only on verified state, bottleneck and change.

## Content Model

Every statistics view must answer these questions in this order:

1. **Scope:** What period and timezone am I looking at?
2. **Scale:** How many conversations, messages and verified sales exist?
3. **Movement:** Did the selected period become more or less active?
4. **Loss:** At which event step did the cohort stop progressing?
5. **Attribution:** Which paid campaign or product contributed, and how certain is that link?
6. **Action:** Which row can I open to inspect the underlying clients or event facts?

Anything that does not answer one of these questions belongs in a disclosure, a tooltip or the audit log.

## Design Alternatives Considered

### A. Full circular dashboard

Many donuts for messages, funnel, ads and products.

**Rejected.** Rings are good for a part-to-whole relationship, but several rings make comparison slow, hide absolute counts and cannot show day-to-day movement. One ring is retained for the selected composition only.

### B. Sankey-style funnel

A flow diagram connecting every event with variable-width paths.

**Rejected for the first release.** It looks impressive but makes sparse cohorts and non-monotonic event facts ambiguous. It also needs a canvas/SVG layer and is difficult to scan on mobile. The design keeps a future-compatible event model without shipping a decorative flow.

### C. Hybrid operator view (recommended)

Compact KPI rail, one composition ring, density-aware activity chart, stepped funnel with explicit `entered / advanced / drop-off`, and ranked campaign/product rows.

**Chosen.** It preserves truthful absolute values, gives the requested circular visual where percentages are meaningful, and keeps the temporal graph legible for one day through one year.

## Component Decisions

### 1. Period control

- Keep `Сьогодні / 7 днів / 30 днів / Увесь час / Власний період` as a compact segmented control.
- Show one small scope line: `07.08 · Europe/Kiev · оновлено 18:42`.
- Do not repeat date range in every section.
- A custom range must be rendered as two dates with no prose paragraph.

### 2. KPI rail

- Four stable slots: `Діалоги`, `Повідомлення`, `Кваліфіковані`, `Підтверджені`.
- Each slot has one number, one short label and one delta/quality marker.
- No card contains a second paragraph by default.
- A missing comparison is shown as a neutral dash, never as a fabricated `0%` delta.

### 3. Composition ring

- Use one CSS conic-gradient ring for the selected cohort composition: `Клієнт / Бот / Менеджер` or funnel outcome mix.
- Put the total in the center; place only three legend rows beside it.
- If total is zero, render an outlined neutral ring with `Немає подій` in the center.
- The ring is not used for time series and never carries more than four segments.
- Hover/tap focuses one segment and dims the others; tooltip contains count and share.

### 4. Activity visualization

- API returns normalized, non-null buckets and `has_data`, `max_total`, `granularity` and `density` metadata.
- `1 day`: a compact pulse strip with three role counters and a 64px sparkline, not a tall bar chart.
- `2-7 days`: stacked daily bars with every day label.
- `8-31 days`: daily bars with selective labels and a highlighted max/last day.
- `32-180 days`: weekly bars; `>180 days`: monthly bars.
- A zero item is a hairline baseline marker, never a full-height dark block.
- Tooltip is placed with a clamped left/right position inside the scroll viewport and is keyboard/tap accessible.
- No chart animates from zero to a false visible bar; segments animate only when their target is non-zero.

### 5. Funnel visual

- Keep a left-to-right or vertical stepped rail with ten canonical event steps.
- Each step has a count, a small conversion badge and a proportional rail.
- The bottleneck is the largest `entered - advanced` loss and receives one amber outline plus a short `Втрачено на етапі` marker.
- Event cohorts may be non-monotonic. The UI must label them `події`, not imply that every row is the same people.
- Add a ring beside the rail for `дошли до оплаты / не дошли / в процессе` only when the cohort is non-zero.
- Clicking a step opens the existing details disclosure filtered to that event type.

### 6. Advertising view

- Always render the view, including zero-attribution periods.
- The first row shows `Рекламні діалоги`, `Кваліфіковані`, `Оплати`, `Дохід` and an attribution quality badge.
- Zero attribution state has a compact diagnostic strip: `0 діалогів · 42 органічні · attribution не зафіксована`.
- Campaign rows show one horizontal conversion rail: conversations -> qualified -> paylink -> paid.
- Product rows show thumbnail, interest count, paid quantity and paid share; no empty image box.
- Campaigns over eight rows stay behind disclosure with a count.

### 7. Details and sparse data

- Replace repeated full-width tables with two-column compact grids.
- Every table must have a meaningful empty state: `Немає подій у вибраному періоді` plus scope, not repeated zeros.
- `Мало даних` appears once in a section note and never once per row.
- Long labels are shortened visually and explained in a tooltip.
- Tables use sticky first column only when horizontal scrolling is unavoidable.

### 8. Interaction and motion

- Section entrance: 160ms opacity/translate only on first render.
- KPI value change: 220ms number tint, no layout shift.
- Bars/ring: 360ms ease-out from previous measured value to next measured value.
- Disclosure: height/opacity transition with focus moved to the opened heading.
- New live data: a small `Оновлено` pulse, never a full-page flash.
- Respect `prefers-reduced-motion` by removing transforms, pulses and delayed reveals.

### 9. Responsive rules

- Desktop: two-column analysis grid, ring and activity share one row.
- Tablet: one-column analysis flow, ring stays beside KPI only if width allows.
- Mobile: KPI one-column, ring becomes a 160px side-by-side block, tables stack as rows.
- No fixed minimum width or chart tooltip may create horizontal page overflow.

### 10. Truth and failure states

- API failure: compact alert with `Повторити`, preserve the last valid snapshot with a stale marker.
- Empty period: show scope, zero totals and a neutral visual; never hide the module.
- Missing attribution: distinguish `органічно` from `атрибуція не зафіксована`.
- Unknown amount: show `сума не визначена`, never `0 грн`.
- All percentage denominators are explicit in accessible labels.

## 100 Candidate Improvements: Decision Register

The register deliberately includes ideas that are **not** implemented. A candidate is accepted only when it improves at least two of: scan speed, truthfulness, actionability, responsive clarity, or error recovery.

### Data and scope (1-10)

1. Normalize null time buckets -> **Do**; otherwise real messages disappear from charts.
2. Add `has_data` metadata -> **Do**; lets UI distinguish zero from missing.
3. Add `max_total` metadata -> **Do**; keeps scaling server-truthful.
4. Add local/UTC period boundaries -> **Keep**; prevents date disputes.
5. Add event-time provenance -> **Keep**; explains provider versus creation time.
6. Add comparison period -> **Later**; useful after baseline volume is stable.
7. Add synthetic trend when no data -> **Reject**; violates truthfulness.
8. Count hidden clients in public KPIs -> **Reject**; hidden is an operational state.
9. Infer ad attribution from message text -> **Reject**; not evidence.
10. Add server generated timestamp -> **Do**; supports freshness trust.

### KPI and composition (11-20)

11. Four stable KPI slots -> **Do**; prevents layout shift.
12. More than six primary KPIs -> **Reject**; scanning becomes slower.
13. One composition ring -> **Do**; best part-to-whole visual.
14. Donut for every metric -> **Reject**; comparison is weak.
15. Center total in ring -> **Do**; preserves absolute scale.
16. Ring hover/tap isolation -> **Do**; connects color to value.
17. Ring with more than four segments -> **Reject**; unreadable legend.
18. KPI delta without a comparison -> **Reject**; fabricated precision.
19. KPI skeleton while loading -> **Do**; prevents jumping layout.
20. KPI click to filter all panels -> **Later**; useful, but needs server-side filter contract.

### Activity chart (21-30)

21. One-day pulse mode -> **Do**; avoids a giant empty panel.
22. Daily stacked bars for 2-7 days -> **Do**; direct day comparison.
23. Weekly bars for 32-180 days -> **Do**; controls density.
24. Month bars for long periods -> **Do**; keeps chart legible.
25. Full-height background behind zero -> **Reject**; exactly the reported visual bug.
26. Zero baseline hairline -> **Do**; zero remains visible without implying volume.
27. Tooltip clamped to viewport -> **Do**; prevents overlap and clipping.
28. Tooltip only on hover -> **Reject**; unusable on touch.
29. Show every date label on 30 days -> **Reject**; creates collisions.
30. Animated bar growth from zero on every refresh -> **Reject**; noisy and misleading.

### Funnel and loss (31-40)

31. Stepped event rail -> **Do**; preserves order without false cohort assumptions.
32. One linear bar for non-monotonic events -> **Reject**; implies invalid conversion.
33. Entered/advanced/drop-off triad -> **Do**; explains where volume changed.
34. Bottleneck outline -> **Do**; focuses operator attention.
35. Ring for outcome mix -> **Do** when cohort non-zero; fast percentage comprehension.
36. Ring for every funnel step -> **Reject**; visual noise.
37. Click step to open details -> **Do**; connects summary to evidence.
38. Infer loss from current stage only -> **Reject**; mutable state is not an event fact.
39. Show low-sample note once per section -> **Do**; avoids repeated noise.
40. Hide empty funnel -> **Reject**; operator must know it is empty for this scope.

### Advertising (41-50)

41. Always-visible advertising tab -> **Do**; zero is a valid result.
42. Attribution quality badge -> **Do**; distinguishes organic and unknown.
43. Campaign conversion rail -> **Do**; better than a text list.
44. Campaign cards with long descriptions -> **Reject**; action is in numbers.
45. Product thumbnail only when available -> **Do**; no broken image boxes.
46. Show campaign creative image as default -> **Later**; only if persisted URL is trusted.
47. Mix organic into paid totals -> **Reject**; corrupts ROAS decisions.
48. Add ad spend/ROAS now -> **Later**; requires a durable spend import contract.
49. Show `0 рекламных` alone -> **Reject**; no diagnosis.
50. Disclosure for campaigns over eight -> **Do**; compact first scan.

### Product and order context (51-60)

51. Interest versus paid quantity -> **Do**; shows demand-to-sale gap.
52. Product rank by interest -> **Do**; answers what attracts attention.
53. Product rank by paid revenue only -> **Later**; needs reliable amount provenance.
54. Include unavailable/unknown product rows -> **Do** as a separate bucket; preserves attribution gaps.
55. Full product table by default -> **Reject**; too dense.
56. Product row click to client cohort -> **Later**; needs filter endpoint.
57. Order lifecycle timeline in stats -> **Later**; belongs in order workspace first.
58. Treat TTN as a sale conversion -> **Reject**; delivery is post-sale.
59. Use product colors as status colors -> **Reject**; conflicts with commercial state palette.
60. Show image alt text visibly in every row -> **Reject**; keep it accessible, not noisy.

### Detail tables (61-70)

61. Compact two-column grid -> **Do**; fixes screenshot whitespace.
62. Repeat `Мало даних` on every row -> **Reject**; move to section note.
63. Sticky table headers -> **Do** for long disclosures; aids scanning.
64. Sticky first column on mobile -> **Do** only for truly wide tables.
65. Show all details expanded -> **Reject**; hides the primary signal.
66. Disclosure count badge -> **Do**; sets expectation before opening.
67. Hover-only explanations -> **Reject**; not mobile-safe.
68. Tap/focus definition popover -> **Do**; keeps copy out of default layout.
69. Arbitrary empty decorative boxes -> **Reject**; empty means no visual container.
70. Export button in first slice -> **Later**; useful after metric contract stabilizes.

### Interaction (71-80)

71. Period change preserves scroll position -> **Do**; reduces disorientation.
72. Focus opened disclosure heading -> **Do**; keyboard context remains clear.
73. Tap toggles chart tooltip -> **Do**; touch parity.
74. Escape closes tooltip/disclosure -> **Do**; expected desktop behavior.
75. Tooltip anchored to bar only -> **Reject**; edge clipping.
76. Live refresh full-page rerender -> **Reject**; causes flicker.
77. Freshness pulse only on changed data -> **Do**; attention without noise.
78. Sound on every metric refresh -> **Reject**; disruptive.
79. Sound for critical payment anomaly -> **Later** behind explicit preference.
80. Drag-and-drop chart reordering -> **Reject**; no operational value.

### Responsive and accessibility (81-90)

81. 320px no overflow -> **Do**; production support requirement.
82. Mobile stacked product rows -> **Do**; avoids horizontal table strain.
83. Horizontal scroll cue for unavoidable tables -> **Do**; affordance must be visible.
84. Color-only meaning -> **Reject**; pair with labels and shape.
85. ARIA labels include denominator -> **Do**; percentages become interpretable.
86. Reduced-motion override -> **Do**; motion must be optional.
87. Font scaling with viewport width -> **Reject**; text stability matters.
88. Hover-only bottleneck highlight -> **Reject**; persistent concise marker needed.
89. Focus ring on bars and controls -> **Do**; keyboard parity.
90. Decorative gradients/orbs -> **Reject**; visual clutter without meaning.

### Reliability and QA (91-100)

91. RED regression for null bucket -> **Do**; locks the production root cause.
92. RED regression for one-day compact mode -> **Do**; prevents regression to oversized chart.
93. Fixture with attributed campaign -> **Do**; validates the non-empty advertising view.
94. Fixture with zero attribution -> **Do**; validates honest empty state.
95. Browser test at 1/7/30/custom periods -> **Do**; range behavior is the feature.
96. Pixel screenshot only at desktop -> **Reject**; misses mobile overflow.
97. JS syntax check -> **Do**; inline template scripts can fail silently.
98. Production API schema smoke -> **Do**; local SQLite is not MariaDB.
99. Synthetic production data mutation -> **Reject**; no pollution without approval.
100. Deploy SHA/health verification -> **Do**; branch-only is not completion.

## Acceptance Gate

The redesign is accepted only when all of these are true:

- Production-like MariaDB response has no null time buckets and totals reconcile with series sums.
- The one-day view never renders a full-height zero/background column.
- A non-empty ad fixture renders campaign, product and funnel visuals without copy-only fallback.
- A zero-attribution period still explains the absence in one compact diagnostic state.
- Funnel percentages use an explicit denominator and mark event-cohort semantics.
- Tooltip, ring segment focus, disclosure and date changes work with mouse, keyboard and touch.
- 1440/1024/768/390/375/320 screenshots have no overlap or horizontal page overflow.
- Reduced motion removes transforms, pulses and delayed transitions.
