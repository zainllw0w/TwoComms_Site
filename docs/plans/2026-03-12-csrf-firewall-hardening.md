# CSRF Firewall Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the remaining proven CSRF helper patterns that can produce repeated `403` responses and document git/worktree hygiene for safer future work.

**Architecture:** Apply minimal, local fixes to the remaining high-risk scripts/templates instead of attempting a repo-wide CSRF refactor. Back the `management-stats.js` change with a focused Node regression test and keep git hygiene work descriptive rather than auto-committing unrelated WIP.

**Tech Stack:** Django 5.2, plain browser JavaScript, Django templates, Node built-in test runner, git worktrees.

---

### Task 1: Add failing regression test for stats dismiss flow

**Files:**
- Create: `tests/js/management-stats.test.js`
- Test: `twocomms/twocomms_django_theme/static/js/management-stats.js`

**Step 1: Write the failing test**

Simulate:
- duplicate `csrftoken` cookies,
- stats page with dismiss URL,
- a click path that triggers `dismissAdvice`,
- expectation that a valid `X-CSRFToken` is sent.

**Step 2: Run test to verify it fails**

Run: `node --test tests/js/management-stats.test.js`
Expected: FAIL on current implementation.

### Task 2: Implement targeted CSRF hardening

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/js/management-stats.js`
- Modify: `twocomms/twocomms_django_theme/templates/pages/admin_panel.html`
- Modify: `twocomms/twocomms_django_theme/templates/partials/admin_collaboration_section.html`

**Step 1: Patch stats JS**

Use the same safe strategy as `management-activity.js`:
- DOM token first,
- Django-style cookie parsing fallback,
- don’t send dismiss request without a valid token.

**Step 2: Patch inline admin helpers**

Replace the duplicate-cookie-breaking `getCookie()` snippets with Django-style parsing in both inline admin templates.

### Task 3: Verify

**Files:**
- Test: `tests/js/management-activity.test.js`
- Test: `tests/js/management-stats.test.js`

**Step 1: Run JS regression tests**

Run:
```bash
node --test tests/js/management-activity.test.js
node --test tests/js/management-stats.test.js
```

**Step 2: Run Django management tests**

Run:
```bash
cd twocomms
SECRET_KEY=test-secret-key-for-testing-only-do-not-use-in-production python3 manage.py test management.tests --settings=test_settings --keepdb
```

### Task 4: Record git hygiene state

**Files:**
- Create: `docs/plans/2026-03-12-worktree-hygiene.md`

**Step 1: Summarize dirty worktrees**

Group current dirty worktrees by overlapping file sets and call out the safe rule:
- production hotfixes from clean release worktree,
- new work only in dedicated `codex/*` branches,
- no blind commits of unrelated WIP.

### Task 5: Commit and optionally release

**Files:**
- Only files touched in this hardening branch

**Step 1: Commit**

Run:
```bash
git add docs/plans/2026-03-12-csrf-firewall-hardening-design.md docs/plans/2026-03-12-csrf-firewall-hardening.md docs/plans/2026-03-12-worktree-hygiene.md tests/js/management-stats.test.js twocomms/twocomms_django_theme/static/js/management-stats.js twocomms/twocomms_django_theme/templates/pages/admin_panel.html twocomms/twocomms_django_theme/templates/partials/admin_collaboration_section.html
git commit -m "fix: harden remaining csrf-sensitive admin helpers"
```
