# Management Statistics Detail Modal Repair Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Repair the production statistics detail experience by replacing the narrow side drawer with a centered responsive modal and converting raw analytical codes into grouped, human-readable diagnostics.

**Architecture:** Keep the existing statistics API and drawer controller, but change the modal geometry and the client-side presentation layer in `bot.html`. Add small pure JavaScript helpers for loss-reason normalization, structural-event filtering, aggregation, and human duration formatting; verify them through the existing Django template contract suite and browser QA.

**Tech Stack:** Django template, vanilla JavaScript, CSS Grid/Flexbox, Django `SimpleTestCase`, Playwright CLI.

---

### Task 1: Add failing presentation contracts

**Files:**
- Modify: `twocomms/management/tests_ig_stats_visuals.py`

**Step 1: Write the failing tests**

Add template contracts that require:

```python
def test_detail_dialog_is_centered_and_wide(self):
    for contract in (
        "place-items:center",
        "width:min(1080px,calc(100vw - 48px))",
        "max-height:min(88dvh,780px)",
        "@media(max-width:700px)",
    ):
        self.assertIn(contract, self.template)

def test_detail_copy_hides_internal_analytics_vocabulary(self):
    for contract in (
        "function aggregateLossReasons",
        "function isStructuralLossReason",
        "function formatDurationHours",
        "Немає відповіді",
        "Інші причини",
        "90% діалогів до",
        "Ще тривають",
        "Розподіл поточних етапів",
        "Недостатньо даних",
    ):
        self.assertIn(contract, self.template)
```

Also assert that visible-rendering strings no longer contain `remaining loss`, `total до Top-N`, `sample · right-censored`, or `Мало даних CR`.

**Step 2: Run the tests and verify RED**

Run:

```bash
cd twocomms
python manage.py test --settings=test_settings management.tests_ig_stats_visuals.StatsDashboardTemplateContractTests
```

Expected: FAIL because the centered modal contracts and normalization helpers do not exist.

**Step 3: Commit the RED test only if execution is split**

```bash
git add twocomms/management/tests_ig_stats_visuals.py
git commit -m "test(management): define readable statistics detail modal"
```

### Task 2: Normalize loss reasons and technical copy

**Files:**
- Modify: `twocomms/management/templates/management/bot.html`
- Test: `twocomms/management/tests_ig_stats_visuals.py`

**Step 1: Implement the minimal normalization helpers**

Add:

```javascript
function isStructuralLossReason(code){
  return ['new_deal_episode','new_review_episode','new_attribution_episode'].includes(String(code||''));
}

function aggregateLossReasons(rows){
  const grouped=new Map();
  (rows||[]).forEach(row=>{
    const code=String(row.reason_code||row.kind||'other');
    if(isStructuralLossReason(code))return;
    const label=reasonLabel(row);
    const current=grouped.get(label)||{reason_code:code,label,recoverable:0,unrecoverable:0,recovered:0};
    current.recoverable+=num(row.recoverable);
    current.unrecoverable+=num(row.unrecoverable);
    current.recovered+=num(row.recovered);
    grouped.set(label,current);
  });
  return Array.from(grouped.values());
}
```

Extend the label map so silence values render as `Немає відповіді` and structural codes never fall through to visible English text.

**Step 2: Replace visible internal copy**

- `remaining loss` -> `Інші причини`.
- `total до Top-N` -> `найчастіші причини`.
- `Поточний snapshot` -> `Розподіл поточних етапів`.
- `Мало даних CR` -> `Недостатньо даних`.
- remove visible `sample`, `right-censored`, `rc`, and `n` shorthand.

**Step 3: Run focused tests and verify GREEN**

Run the template contract test command from Task 1.

Expected: PASS.

### Task 3: Redesign the detail surface as a centered modal

**Files:**
- Modify: `twocomms/management/templates/management/bot.html`
- Test: `twocomms/management/tests_ig_stats_visuals.py`

**Step 1: Replace side-drawer geometry**

Use a viewport-centered dialog:

```css
.bot-stats-detail-drawer{
  position:fixed;
  inset:0;
  display:grid;
  place-items:center;
  padding:24px;
}
.bot-stats-detail-drawer-panel{
  width:min(1080px,calc(100vw - 48px));
  max-height:min(88dvh,780px);
}
```

Keep one internal scroll container and make the header sticky inside the panel.

**Step 2: Add responsive layout contracts**

- two diagnostic columns on desktop;
- one column below 780 px;
- full-width/full-height dialog below 700 px;
- cohort facts use five aligned columns on desktop and a labeled compact layout on mobile;
- no horizontal scrolling.

**Step 3: Preserve interaction behavior**

Keep the existing controller contract for:

- Escape close;
- backdrop close on desktop;
- focus trap;
- focus return;
- reduced motion.

**Step 4: Run focused tests**

Run:

```bash
cd twocomms
python manage.py test --settings=test_settings management.tests_ig_stats_visuals.StatsDashboardTemplateContractTests
```

Expected: PASS.

### Task 4: Make time and cohort diagnostics readable

**Files:**
- Modify: `twocomms/management/templates/management/bot.html`
- Test: `twocomms/management/tests_ig_stats_visuals.py`

**Step 1: Add human duration formatting**

Implement `formatDurationHours(value)`:

- below one hour -> rounded minutes;
- below 24 hours -> hours with at most one decimal;
- 24 hours and above -> days with at most one decimal;
- unavailable -> `—`.

**Step 2: Rewrite duration rows**

Render visible facts as:

```text
Зазвичай 4 хв
90% діалогів до 4 хв
Діалогів 5
Ще тривають 5
```

Keep exact technical definitions only in the accessible `title`/`aria-label` where useful.

**Step 3: Rewrite cohort facts**

Use the section title `Переходи між етапами` and readable column labels. Ensure `Недостатньо даних` spans or wraps without breaking adjacent values.

**Step 4: Run focused tests**

Expected: PASS.

### Task 5: Independent design evaluation and visual QA

**Files:**
- Create: `twocomms/output/playwright/stats-detail-modal-repair/` screenshots
- Modify if needed: `twocomms/management/templates/management/bot.html`

**Step 1: Run the template and statistics suite**

```bash
cd twocomms
python manage.py test --settings=test_settings \
  management.tests_ig_stats_visuals \
  management.tests_ig_funnel_analytics
```

Expected: PASS.

**Step 2: Run browser QA**

Check `npx`, then use the Playwright wrapper. Capture the closed dashboard and open modal at 1440, 1280, 768, 390, and 320 px.

For every viewport verify:

```javascript
document.documentElement.scrollWidth === window.innerWidth
```

Also verify the modal panel bounding rectangle stays inside the viewport and no visible raw service label remains.

**Step 3: Run independent design evaluation**

Evaluate hierarchy, legibility, density, modal geometry, and mobile behavior. Apply every priority correction and repeat visual QA.

**Step 4: Run final verification**

```bash
cd twocomms
python manage.py check
git diff --check
```

Expected: no errors.

### Task 6: Commit, push, and deploy

**Files:**
- Modify: `twocomms/management/templates/management/bot.html`
- Modify: `twocomms/management/tests_ig_stats_visuals.py`
- Create: `docs/plans/2026-08-08-management-stats-detail-modal-repair-design.md`
- Create: `docs/plans/2026-08-08-management-stats-detail-modal-repair.md`

**Step 1: Commit implementation**

```bash
git add docs/plans/2026-08-08-management-stats-detail-modal-repair-design.md \
  docs/plans/2026-08-08-management-stats-detail-modal-repair.md \
  twocomms/management/templates/management/bot.html \
  twocomms/management/tests_ig_stats_visuals.py
git commit -m "fix(management): repair statistics detail modal"
```

**Step 2: Push to main**

```bash
git push origin HEAD:main
```

**Step 3: Deploy using the established fast-forward flow**

Run server `git pull --ff-only`, touch `twocomms/tmp/restart.txt`, and verify exact server SHA.

**Step 4: Verify production health**

- storefront health returns `200`;
- management bot health returns `200` and `bot_state=running`;
- tracked server checkout is clean;
- the deployed SHA equals `origin/main`.

