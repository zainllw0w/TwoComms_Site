# Homepage Pagination Window Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the homepage's full page-number list with a compact windowed pager that still works with `Показати ще`, real page URLs, and mobile scaling.

**Architecture:** Keep pagination-window logic on the backend only. Render the homepage pager through a dedicated partial on first load and return the same partial as `pagination_html` from `load_more_products`, while the frontend only swaps the DOM and re-runs the existing layout sync.

**Tech Stack:** Django views/templates/tests, vanilla JS module on the homepage, existing homepage CSS.

---

### Task 1: Add red tests for compact pagination rules

**Files:**
- Create: `twocomms/storefront/tests/test_homepage_pagination_window.py`
- Reference: `twocomms/storefront/views/catalog.py`

**Step 1: Write the failing helper tests**

Add tests for these cases:

```python
def test_build_homepage_pagination_items_shows_all_pages_below_threshold(self):
    items = build_homepage_pagination_items(current_page=3, total_pages=5, base_path="/")
    assert [item["page"] for item in items if item["type"] == "page"] == [1, 2, 3, 4, 5]

def test_build_homepage_pagination_items_compacts_start(self):
    items = build_homepage_pagination_items(current_page=1, total_pages=15, base_path="/")
    assert [item["type"] for item in items] == ["prev", "page", "page", "page", "ellipsis", "page", "next"]

def test_build_homepage_pagination_items_compacts_middle(self):
    items = build_homepage_pagination_items(current_page=8, total_pages=15, base_path="/")
    assert [item["type"] for item in items] == ["prev", "page", "ellipsis", "page", "page", "page", "ellipsis", "page", "next"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && cd twocomms && python manage.py test storefront.tests.test_homepage_pagination_window --settings=test_settings -v 2
```

Expected: failure because `storefront.pagination` and `build_homepage_pagination_items` do not exist yet.

**Step 3: Write minimal implementation**

Create:

- `twocomms/storefront/pagination.py`

Add a pure helper that returns ordered `prev/page/ellipsis/next` items with URLs based on `base_path`.

**Step 4: Run test to verify it passes**

Run the same test command.

Expected: helper tests pass.

**Step 5: Commit**

```bash
git add twocomms/storefront/pagination.py twocomms/storefront/tests/test_homepage_pagination_window.py
git commit -m "feat: add homepage pagination window helper"
```

### Task 2: Add red tests for homepage and AJAX integration

**Files:**
- Modify: `twocomms/storefront/tests/test_homepage_pagination_window.py`
- Reference: `twocomms/storefront/views/catalog.py`

**Step 1: Write the failing integration tests**

Add tests that:

- create enough published products for `8+` homepage pages,
- assert the homepage response contains `…` and does not contain every page number in a flat sequence,
- assert `/load-more-products/?page=2` returns `pagination_html`,
- assert returned `pagination_html` marks page 2 as current.

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && cd twocomms && python manage.py test storefront.tests.test_homepage_pagination_window --settings=test_settings -v 2
```

Expected: failure because views and templates still render the old full pager and AJAX response has no `pagination_html`.

**Step 3: Write minimal implementation**

Update:

- `twocomms/storefront/views/catalog.py`

Pass helper output into homepage render context and include `pagination_html` in the AJAX response.

**Step 4: Run test to verify it passes**

Run the same test command.

Expected: integration tests pass.

**Step 5: Commit**

```bash
git add twocomms/storefront/views/catalog.py twocomms/storefront/tests/test_homepage_pagination_window.py
git commit -m "feat: serve compact homepage pagination from backend"
```

### Task 3: Extract homepage pager partial and switch template to it

**Files:**
- Create: `twocomms/twocomms_django_theme/templates/partials/home_pagination.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/index.html`
- Test: `twocomms/storefront/tests/test_homepage_pagination_assets.py`

**Step 1: Write the failing template-level assertion**

Extend asset/template tests with checks that:

- homepage pagination now uses the partial shell,
- the template no longer loops over raw `paginator.page_range` for the homepage pager.

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && cd twocomms && python manage.py test storefront.tests.test_homepage_pagination_assets --settings=test_settings -v 2
```

Expected: failure because the homepage still renders inline pager markup.

**Step 3: Write minimal implementation**

Render the pager through a stable replacement shell such as:

```django
<div id="home-pagination-shell">
  {% include "partials/home_pagination.html" %}
</div>
```

The partial should render:

- page links for `page` items,
- non-interactive `…` items for `ellipsis`,
- current-page state and prev/next disabled state.

**Step 4: Run test to verify it passes**

Run the same asset test command.

Expected: asset/template tests pass.

**Step 5: Commit**

```bash
git add twocomms/twocomms_django_theme/templates/pages/index.html twocomms/twocomms_django_theme/templates/partials/home_pagination.html twocomms/storefront/tests/test_homepage_pagination_assets.py
git commit -m "feat: render homepage pagination through compact partial"
```

### Task 4: Update homepage JS to replace pager HTML after `Показати ще`

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/js/modules/homepage.js`
- Test: `twocomms/storefront/tests/test_homepage_pagination_assets.py`

**Step 1: Write the failing JS asset assertion**

Add assertions that the JS module:

- references `pagination_html`,
- replaces a stable homepage pagination shell,
- re-queries the pager element after replacement instead of relying on the initial DOM reference.

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && cd twocomms && python manage.py test storefront.tests.test_homepage_pagination_assets --settings=test_settings -v 2
```

Expected: failure because JS still keeps the initial `paginationNav` reference forever.

**Step 3: Write minimal implementation**

Update `homepage.js` so that:

- pager lookup is done through a getter,
- AJAX success path applies `data.pagination_html` to `#home-pagination-shell`,
- the module reacquires the current nav element before syncing pagination state and layout.

**Step 4: Run test to verify it passes**

Run the same asset test command.

Expected: asset tests pass.

**Step 5: Commit**

```bash
git add twocomms/twocomms_django_theme/static/js/modules/homepage.js twocomms/storefront/tests/test_homepage_pagination_assets.py
git commit -m "fix: refresh homepage pager after load more"
```

### Task 5: Add any minimal pager styles for ellipsis and verify end-to-end

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/css/home.css`
- Test: `twocomms/storefront/tests/test_homepage_pagination_assets.py`

**Step 1: Write the failing style assertion**

Add a targeted assertion for compact pager ellipsis styling, for example a non-interactive `.page-item-ellipsis`.

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && cd twocomms && python manage.py test storefront.tests.test_homepage_pagination_assets --settings=test_settings -v 2
```

Expected: failure because ellipsis styles do not exist yet.

**Step 3: Write minimal implementation**

Add only the styles needed for:

- non-clickable ellipsis,
- preserved active and disabled states,
- compatibility with the existing mobile scaling hook.

**Step 4: Run tests and browser verification**

Run:

```bash
source .venv/bin/activate && cd twocomms && python manage.py test storefront.tests.test_homepage_pagination_window storefront.tests.test_homepage_pagination_assets --settings=test_settings -v 2
```

Then verify in browser:

- homepage with `8+` pages shows compact pagination,
- `Показати ще` updates the active page and pager window,
- mobile viewport stays inside bounds.

**Step 5: Commit**

```bash
git add twocomms/twocomms_django_theme/static/css/home.css twocomms/storefront/tests/test_homepage_pagination_assets.py twocomms/storefront/tests/test_homepage_pagination_window.py
git commit -m "feat: compact homepage pagination for large page counts"
```

### Task 6: Push and deploy after fresh verification

**Files:**
- Modify: none

**Step 1: Run fresh verification**

Run:

```bash
source .venv/bin/activate && cd twocomms && python manage.py test storefront.tests.test_homepage_pagination_window storefront.tests.test_homepage_pagination_assets --settings=test_settings -v 2
```

Expected: all targeted tests pass.

**Step 2: Push**

Run:

```bash
git push origin main
```

**Step 3: Deploy**

Run:

```bash
./run_deploy.exp
./run_restart.exp
```

**Step 4: Post-deploy browser verification**

Verify:

- compact pager is visible on production,
- `Показати ще` still works,
- mobile pager stays inside viewport.
