# Management Statistics Decision Cockpit Design

**Date:** 2026-08-08  
**Status:** Approved direction, implementation pending  
**Surface:** Instagram bot management statistics  
**Audience:** administrator who must understand activity, conversion, losses, advertising quality and commercial outcome in about two seconds, then inspect evidence without reading a wall of text.

## 1. Outcome

Replace the current table-heavy statistics area with a decision cockpit that has three levels:

1. **Scan:** five primary facts and one main diagnostic signal.
2. **Understand:** linked activity, funnel, advertising and product visuals.
3. **Verify:** a contextual drawer with definitions, exact counts, denominators and source facts.

The redesign is successful only if it is both easier to understand and more truthful. A visual that looks impressive but hides a denominator, mixes time semantics or invents missing Meta cost is rejected.

## 2. Evidence From The Current Interface

The supplied screenshots and current template show four structural problems:

- The one-day chart keeps the height of a multi-day chart and spends most of the viewport on one weak mark.
- Zero columns have a full-height dark background, so absence of data looks like a large value.
- The activity tooltip can cover adjacent content and repeats values without a clear hierarchy.
- Detailed data renders seven different analytical questions as visually identical tables. Current state, event cohort, duration, objections and operator participation therefore look interchangeable even though they use different units and time semantics.

The problem is not solved by restyling the tables. The content hierarchy and metric contract must change.

## 3. Design Alternatives

### A. Executive cockpit with drill-down

A short KPI rail, one activity visual, one funnel, one composition view and contextual details.

**Strengths:** fastest scan, minimal text, stable responsive layout.  
**Weakness:** deeper funnel diagnosis needs an explicit linked interaction.

### B. Funnel-first diagnostic workspace

The funnel is the dominant page object. Advertising, products and loss reasons follow the selected stage.

**Strengths:** best for conversion investigation and stage-by-stage reasoning.  
**Weakness:** daily operational overview becomes slower.

### C. Separate overview, advertising and product workspaces

Each domain gets a dense, specialist view.

**Strengths:** low clutter inside a domain.  
**Weakness:** the administrator loses the relationship between a campaign, a conversation and a verified payment while switching views.

### Decision

Use a hybrid of A and B. The executive cockpit is the default. The funnel is the primary diagnostic object. Advertising campaigns and product rows respond to the selected stage when evidence exists. Separate tabs remain, but the same period, scope and selection are preserved across them.

## 4. Non-Negotiable Truth Rules

1. Every percentage has an explicit numerator and denominator in its accessible label and details drawer.
2. A zero value means measured zero. Missing source data is shown as unavailable, never as zero.
3. Current client state is not presented as historical attribution.
4. Message activity uses provider-created time with local creation time as fallback.
5. Funnel conversion uses event cohorts and distinct commercial episodes.
6. Verified payment comes only from the existing verified-payment contract.
7. Revenue is net verified payment after recorded refunds where the amount is known.
8. Payments without a trustworthy amount remain visible as paid without amount.
9. Ad spend comes only from a durable Meta import/API source or an explicitly confirmed manual import for the selected period.
10. ROAS is verified attributed revenue divided by ad spend.
11. Revenue minus ad spend is labeled result after advertising, not profit.
12. Profit is unavailable until product cost, fulfillment, discounts, refunds and other required costs have a documented coverage contract.

## 5. Metric Source Matrix

| Metric | Unit | Source | Time basis | Denominator | Primary visual |
| --- | --- | --- | --- | --- | --- |
| Conversations | distinct sender/conversation | visible Instagram messages | message event time | none | KPI |
| Messages | message events | InstagramBotMessage | provider time or created time | none | activity chart |
| Customer messages | message events | message role user | message event time | all messages | stacked activity segment |
| Bot replies | message events | message role model | message event time | all messages | stacked activity segment |
| Manager messages | message events | message role manager | message event time | all messages | stacked activity segment |
| Qualified | current client facts for selected scope | buying readiness | declared snapshot basis | scoped conversations | KPI with scope badge |
| Product matched | current client facts | current product | declared snapshot basis | scoped conversations | funnel/supporting metric |
| Funnel entered | distinct commercial episodes | IgFunnelStepEvent | event occurred time | none | funnel stage count |
| Funnel advanced | same episodes at next event | IgFunnelStepEvent | event occurred time | entered at stage | funnel continuation segment |
| Drop-off | classified drop-off facts | IgFunnelDropOff | drop-off occurred time | entered at mapped stage | funnel loss segment |
| In progress | entered minus advanced minus drop-off | derived event cohort | event occurred time | entered at stage | neutral funnel segment |
| Stage conversion | advanced / entered | event cohort | event occurred time | entered at stage | percent badge |
| Time on step | hours | first event to next event | event occurred time | episodes with both facts | median/P90 interval plot |
| Current stage | clients | IgClient stage with payment truth | current snapshot filtered by last interaction | scoped conversations | segmented distribution |
| Objection clients | clients | primary objection | current snapshot | clients with an objection | ranked bars |
| Objection signals | events | IgConversationSignal | signal created time | all matching signals | secondary evidence only |
| Bot-only episodes | distinct episodes | funnel events | event occurred time | episodes with first bot reply | split bar |
| Manager-touched episodes | distinct episodes | funnel events | event occurred time | episodes with bot or manager evidence | split bar |
| Discount offered | events/episodes | funnel events | event occurred time | episodes with offer evidence | bridge diagram |
| Discount purchase | distinct episodes | offer intersect verified outcome | event occurred time | episodes with offer | bridge conversion |
| Product interest | clients | current product | declared snapshot basis | scoped product-known clients | product demand bar |
| Paid product units | units | verified IgDealItem | verified payment time | none | paid bar |
| Attributed ad conversations | clients/conversations | persisted ad identity | current-client attribution snapshot | scoped conversations | attribution ring |
| Campaign payment | verified deals | deal/payment projection | verified payment time | campaign attributed conversations | campaign mini-funnel |
| Campaign revenue | currency | verified payment amount minus refund | verified payment time | none | money metric |
| Meta spend | currency | Meta insight ledger or confirmed import | Meta reporting date | none | spend metric |
| ROAS | ratio | attributed revenue / spend | selected aligned period | spend | ratio metric |
| Cost per conversation | currency | spend / attributed conversations | selected aligned period | attributed conversations | efficiency metric |
| Cost per verified payment | currency | spend / verified attributed payments | selected aligned period | verified attributed payments | efficiency metric |

## 6. Page Architecture

### 6.1 Scope bar

The top bar is sticky inside the statistics panel and contains:

- period presets and custom range;
- one compact scope status, for example Activity time, Event cohort or Current snapshot;
- generated-at freshness;
- refresh icon;
- a data-quality indicator that opens the source summary.

The date is not repeated in every card. Each module carries only a short basis badge when it differs from the main scope.

### 6.2 Two-second decision rail

Five stable slots:

1. Conversations.
2. Qualified.
3. Pay links issued.
4. Verified payments.
5. Verified revenue.

Each slot contains one large value, one short label and at most one small supporting relation. Missing comparison data uses a dash. No explanatory paragraph appears in a KPI.

The rail also exposes one sentence-sized diagnostic chip, such as Biggest loss: payment link not opened. It is derived only when the event sample is adequate.

### 6.3 Main analysis row

Desktop uses a 7/5 split:

- left: adaptive activity chart;
- right: compact conversation composition ring and response ownership split.

Tablet stacks these modules. Mobile keeps the activity chart first and renders the composition as a compact horizontal distribution instead of forcing a tiny ring.

### 6.4 Primary funnel

The funnel is a stepped rail with ten canonical stages. Every stage shows:

- entered count;
- advanced count;
- lost count;
- in-progress count;
- conversion only when the sample supports it.

The stage fill is a three-part rail, not one decorative width: continued, lost, in progress. This makes the denominator visible. The largest evidence-backed loss gets one restrained amber outline. It does not pulse continuously.

Clicking or tapping a stage:

- keeps the stage selected;
- updates the linked loss, product and campaign modules when a filterable relation exists;
- opens a contextual detail drawer on demand;
- never silently changes the global date range.

### 6.5 Contextual detail drawer

The current full-width Detailed data disclosure is removed. A right-side drawer on desktop and bottom sheet on mobile contains:

- plain-language definition in one line;
- numerator, denominator and percentage;
- source model and time basis;
- exact values in a compact key/value grid;
- relevant top reasons or evidence rows;
- a link to the filtered clients list only when a stable filter can be guaranteed.

This drawer is the only place for longer explanations. Hover is optional enhancement; tap and keyboard focus provide the same information.

## 7. Replacement For Current Detailed Tables

### 7.1 Cohort funnel diagnostic

**Current problem:** a six-column table requires row-by-row reading and repeats Low data.  
**Replacement:** the primary stepped funnel plus a small detail matrix for the selected stage.  
**Why:** position, color and segment length explain continuation and loss before text is read.

### 7.2 Loss reasons

**Replacement:** ranked horizontal bars with two nested portions, recoverable and irreversible. Recovered cases appear as a small positive marker on the recoverable portion.  
**Default:** top five reasons. Remaining reasons live in the drawer.  
**Empty state:** No classified losses in this period.

### 7.3 Time on step

**Replacement:** horizontal interval plot. A dot shows median; a thin whisker ends at P90. Sample size is a small label.  
**Why:** the distance between typical and slow cases becomes visible immediately.  
**Rule:** no bar for sample zero; no fabricated zero hours.

### 7.4 Bot and manager

**Replacement:** one 100% split rail with Bot only, Shared cycle and Manager involved. Absolute episode counts sit below.  
**Why:** the management load is a part-to-whole question, not a table question.

### 7.5 Discounts

**Replacement:** a three-node bridge: Offered -> Bought after offer, plus Bought without discount as a separate baseline.  
**Why:** it reveals conversion after an offer without implying that every non-discount purchase rejected a discount.

### 7.6 Current conversation stages

**Replacement:** segmented distribution bar on desktop and ranked stage list on narrow screens.  
**Why:** a long list of zeros disappears while the shape of active work remains visible.  
**Truth badge:** Current snapshot.

### 7.7 Objections

**Replacement:** ranked bars of clients with a primary objection. Raw signal volume is a separate optional view.  
**Why:** client count and event count cannot share one chart without confusing the denominator.

## 8. Activity Visualization By Date Density

| Range | Visual | Height | Labels |
| --- | --- | --- | --- |
| One day | compact role pulse plus hourly sparkline when hourly data exists | 96-120 px | selected date and role totals |
| 2-7 days | stacked daily columns | 140-170 px | every day |
| 8-31 days | stacked daily columns | 160-190 px | selected labels, first/last/max |
| 32-180 days | weekly columns | 170-200 px | week starts |
| More than 180 days | monthly columns | 170-200 px | month labels |

Zero values use a baseline mark. The chart background never resembles a bar. Tooltips are clamped to the chart viewport and show the total first, then role composition. On touch, tapping a column locks the tooltip until dismissal.

## 9. Advertising Workspace

### 9.1 Immediate answers

The first row answers:

- how many conversations are confidently attributed;
- how much of the selected conversation population has reliable attribution;
- how many verified payments are linked;
- what verified revenue is linked;
- whether spend is connected and aligned to the selected period.

### 9.2 Attribution quality

Use one ring only because coverage is a part-to-whole relation:

- confirmed identity;
- partial identity;
- unattributed.

The center shows coverage percent. The legend shows absolute counts. A basis badge explicitly says Current client attribution until historical identity facts exist.

### 9.3 Campaign rows

Each campaign is one compact diagnostic row with:

- campaign/ad label and persisted identifier;
- miniature stage rail: conversations -> qualified -> product -> pay link -> verified payment;
- verified revenue;
- loss count;
- top product thumbnail when trustworthy;
- data-quality marker.

The rail uses absolute counts in the tooltip and stage-to-stage percentages only when the same cohort semantics are valid. Eight rows are shown initially; more are disclosed.

### 9.4 Spend and profitability contract

The UI supports three source states:

1. **Connected Meta ledger:** imported daily spend with account, campaign and reporting date.
2. **Confirmed manual import:** administrator supplies spend for an exact date range and optional campaign key; the record is persisted with author and timestamp.
3. **Unavailable:** the card says Spend source not connected and no efficiency ratio is calculated.

Required stored fields for a spend record:

- source type;
- Meta account ID when known;
- campaign/ad identity when known;
- reporting date;
- currency;
- spend amount;
- imported/entered at;
- imported/entered by;
- source payload hash or external row ID for idempotency.

Money hierarchy:

- Verified revenue.
- Ad spend.
- Result after advertising = revenue minus spend.
- ROAS = revenue divided by spend.
- Cost per conversation.
- Cost per verified payment.

The term profit is not used until a separate cost-coverage contract is implemented.

### 9.5 Meta comparison

The workspace shows a compact reconciliation strip:

- Meta conversations/results when available;
- conversations persisted by the bot;
- difference in absolute count and percent;
- attribution coverage;
- selected date/timezone and attribution window.

This is a diagnostic comparison, not an automatic correction. Divergence opens the source drawer with likely causes such as timezone, attribution window, missing identity and unsupported placement.

## 10. Product Workspace

Each product row contains a real image when available, product title and two independent scales:

- conversation interest;
- verified paid units.

Independent scales are visually labeled so a small number of paid units does not disappear beside a large interest count. A compact conversion badge uses paid orders divided by interested conversations only when both belong to a compatible cohort; otherwise it is omitted.

Product detail opens:

- interested conversations;
- verified paid orders;
- paid units;
- verified revenue when item pricing provenance is reliable;
- top linked campaigns;
- top drop-off stage.

Unknown product attribution remains a visible bucket and is never redistributed among known products.

## 11. Interaction Model

- Single click/tap selects a chart mark or stage and updates linked modules.
- Second click or Escape clears the selection.
- Details open in a drawer/sheet without page navigation.
- View switches preserve period and selected entity when compatible.
- Refresh preserves scroll and selection if the selected identity still exists.
- Changed values receive a short tint and count transition without layout shift.
- No drag-and-drop is added; it does not improve this decision workflow.
- No automatic sound is added. A future critical anomaly sound requires an explicit preference.

## 12. Motion

Motion communicates continuity:

- view transition: 180-220 ms opacity and 6 px movement;
- drawer/sheet: 220-260 ms with focus transfer;
- value change: 220 ms tint/count interpolation;
- chart update: 280-360 ms from previous measured value;
- selection: 160-200 ms emphasis and linked-module response;
- refresh success: one small freshness pulse.

No continuous decorative animation, no chart replay from zero on every refresh and no motion that delays an action. Reduced-motion removes transforms and interpolation but preserves state changes.

## 13. Visual Direction

The page remains a quiet operational console, not a marketing dashboard.

- Existing dark surface and typography are retained for product consistency.
- Neutral borders define regions; large floating cards are avoided.
- Blue represents customer/activity, teal verified automation/continuation, green verified commercial outcome, amber attention/loss, red only irreversible failure.
- Color is paired with label and shape.
- Text labels use normal letter spacing and compact sizes appropriate to an admin surface.
- Icons replace repeated action words only when the symbol is familiar and has a tooltip.
- Charts use stable dimensions and never resize due to a tooltip or value.

## 14. Responsive Contract

### Desktop 1280-1600

- Five KPI slots in one row.
- Activity/composition split.
- Funnel full-width.
- Linked diagnostics in two columns.
- Detail drawer maximum 420 px.

### Tablet 768-1024

- KPI grid 3+2 or horizontally scrollable stable rail.
- Analysis modules stack.
- Funnel keeps horizontal stage order only if labels remain readable; otherwise becomes vertical.

### Mobile 390 and 320

- KPI rail becomes a two-column summary with the money metric full width.
- Activity chart uses compact labels and touch tooltips.
- Funnel becomes a vertical stage timeline; no two-column miniature nodes with unreadable labels.
- Ring becomes a horizontal distribution when its legend would be compressed.
- Detail drawer becomes a full-width bottom sheet.
- No horizontal page overflow. Only an explicitly cued chart rail may scroll.

## 15. Empty, Loading And Failure States

- Empty selected period keeps the scope bar and five zero KPIs, then one compact neutral state. It does not render empty charts or ten zero funnel stages.
- No advertising attribution shows organic/unattributed population and explains that no campaign identity was persisted.
- Missing spend shows unavailable, not zero.
- Partial payment amount shows verified payment count plus amount unavailable.
- Loading uses stable skeleton dimensions.
- Refresh failure preserves the last successful snapshot with stale status and retry.
- Integrity mismatch shows a compact warning and suppresses derived percentages for the affected module.

## 16. Candidate Decision Register

Each candidate is accepted only when it improves at least two of scan speed, truthfulness, actionability, responsive clarity and error recovery.

1. Five fixed KPIs: **accept**.
2. More than seven primary KPIs: **reject**.
3. One composition ring: **accept**.
4. Donut for every metric: **reject**.
5. Adaptive one-day pulse: **accept**.
6. Full-height one-day chart: **reject**.
7. Hourly sparkline for one day when supported: **accept later with API data**.
8. Synthetic hourly distribution: **reject**.
9. Stacked daily role columns: **accept**.
10. Zero-value full column background: **reject**.
11. Stepped funnel with three-part rails: **accept**.
12. Single descending funnel width for non-monotonic event facts: **reject**.
13. Largest-loss outline: **accept**.
14. Continuous bottleneck pulse: **reject**.
15. Click stage to link diagnostics: **accept**.
16. Global filter change on stage click: **reject**.
17. Contextual drawer: **accept**.
18. Full detail tables by default: **reject**.
19. Numerator/denominator in drawer: **accept**.
20. Hover-only definitions: **reject**.
21. Ranked loss bars: **accept**.
22. Pie chart for many loss reasons: **reject**.
23. Recoverable/irreversible nested loss rail: **accept**.
24. Hide unclassified losses: **reject**.
25. Median/P90 interval plot: **accept**.
26. Zero-hour bar for no sample: **reject**.
27. Bot/manager split bar: **accept**.
28. Separate cards for every bot/manager count: **reject**.
29. Discount bridge: **accept**.
30. Claim discount causality from correlation: **reject**.
31. Current-stage segmented distribution: **accept**.
32. Mix current stages with historical funnel: **reject**.
33. Client objection ranked bars: **accept**.
34. Mix signal events with client objections: **reject**.
35. One attribution coverage ring: **accept**.
36. Hide advertising view when zero: **reject**.
37. Campaign mini-funnel: **accept**.
38. Long campaign prose cards: **reject**.
39. Campaign creative thumbnail when persisted: **accept**.
40. External image URL without provenance: **reject**.
41. Product real thumbnail: **accept**.
42. Decorative placeholder image blocks: **reject**.
43. Independent interest and paid scales: **accept**.
44. One shared scale that hides paid values: **reject**.
45. Unknown product bucket: **accept**.
46. Distribute unknown interest proportionally: **reject**.
47. Meta spend API ledger: **accept**.
48. Browser-only spend input as source of truth: **reject**.
49. Audited manual spend import: **accept as fallback**.
50. Show missing spend as 0: **reject**.
51. ROAS from verified attributed revenue: **accept**.
52. Call revenue minus spend net profit: **reject**.
53. Cost per attributed conversation: **accept**.
54. Cost per message as primary metric: **reject**.
55. Cost per verified payment: **accept**.
56. Cost per pay-link view as primary metric: **reject**.
57. Meta vs bot reconciliation strip: **accept when Meta result data exists**.
58. Automatically overwrite bot facts with Meta totals: **reject**.
59. Data-quality badge: **accept**.
60. Repeated quality paragraph per card: **reject**.
61. Preserve selection on refresh: **accept**.
62. Full dashboard rerender with scroll reset: **reject**.
63. Previous-to-new chart interpolation: **accept**.
64. Replay all charts from zero: **reject**.
65. Focus transfer to drawer: **accept**.
66. Mouse-only interaction: **reject**.
67. Escape clears selection: **accept**.
68. Custom drag-and-drop dashboard: **reject**.
69. Sticky scope bar: **accept**.
70. Repeat period in every panel: **reject**.
71. Compact source basis badge: **accept**.
72. Hide mixed time semantics: **reject**.
73. Snapshot/cohort distinction: **accept**.
74. Pretend current attribution is historical: **reject**.
75. Paid without amount state: **accept**.
76. Convert unknown amount to 0 currency: **reject**.
77. Empty state with one diagnosis: **accept**.
78. Render ten zero-stage blocks: **reject**.
79. Stale snapshot preservation: **accept**.
80. Clear all data after refresh error: **reject**.
81. 320 px vertical funnel: **accept**.
82. Two-column tiny funnel nodes at 320 px: **reject**.
83. Mobile bottom detail sheet: **accept**.
84. Desktop-width table inside mobile sheet: **reject**.
85. Stable chart height by density: **accept**.
86. Viewport-scaled font size: **reject**.
87. Clamped tooltips: **accept**.
88. Tooltips outside scroll viewport: **reject**.
89. First/last/max labels for dense series: **accept**.
90. Every date label for 30 days: **reject**.
91. Initial 180 ms entrance: **accept**.
92. Continuous decorative motion: **reject**.
93. Important value-change tint: **accept**.
94. Sound on normal refresh: **reject**.
95. RED contract tests for every denominator: **accept**.
96. Screenshot-only verification: **reject**.
97. Browser QA at 1440/1280/768/390/320: **accept**.
98. Production data mutation for visual QA: **reject**.
99. API schema and production snapshot smoke: **accept**.
100. Commit/push/deploy without deployed-SHA and live checks: **reject**.

## 17. Implementation Boundaries

The first implementation must refactor the current Django/vanilla JavaScript statistics surface. It must not introduce a standalone dashboard framework or a new chart dependency unless native CSS/DOM rendering cannot truthfully express the selected visual.

The work is split into independently testable slices:

1. Metric semantics and module metadata.
2. Adaptive activity chart.
3. Funnel and linked selection state.
4. Visual detail modules and contextual drawer.
5. Product workspace refinement.
6. Advertising and spend-source contract.
7. Responsive, motion and failure-state QA.

## 18. Acceptance Gates

- The administrator can identify activity volume, verified payments, revenue and largest loss in one viewport.
- No default detail surface is a raw full-width table.
- Every chart has a meaningful unit and denominator.
- One-day, seven-day, thirty-day, custom and all-time ranges remain compact and legible.
- Current snapshot and event cohort facts are visibly distinguished.
- Advertising zero, partial attribution, full attribution and missing spend are all testable states.
- Meta spend and ROAS are not shown until source and period alignment are valid.
- Every interactive mark works with mouse, keyboard and touch.
- No incoherent overlap or horizontal page overflow at 320 px.
- Reduced-motion behavior preserves meaning.
- Focused backend and template contract tests pass.
- Browser screenshots and pixel/overflow checks pass at required viewports.
- Production API schema, deployed SHA and live rendering are verified after integration.

