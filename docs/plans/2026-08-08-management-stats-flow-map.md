# Management Statistics Flow Map Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the misleading funnel bars with a truthful, responsive and interactive flow map for any selected date range.

**Architecture:** Keep the existing event-cohort API contract and derive a compact view model in the existing vanilla-JS template. Each event step becomes a button node with a measured rail, count, transition facts and a single detail surface. CSS density classes adapt layout without changing semantics.

**Tech Stack:** Django 5, existing `bot_stats_api`, vanilla JavaScript/CSS, Django contract tests, Playwright visual QA.

---

### Task 1: Add RED contracts for the flow map

**Files:**
- Modify: `twocomms/management/tests_ig_stats_visuals.py`

**Steps:**
1. Add a template contract requiring `renderFlowMap`, `bot-stats-flow-map`, `data-flow-step`, `data-flow-detail`, explicit `advanced/drop_off/in_progress` fields and a zero-width guard.
2. Add an interaction contract for Escape/outside close and reduced-motion support.
3. Run the focused tests and confirm they fail because the new contract is absent.

### Task 2: Implement the view model and HTML

**Files:**
- Modify: `twocomms/management/templates/management/bot.html`

**Steps:**
1. Add `flowRows` to normalize `entered`, `advanced`, `drop_off`, `in_progress`, `cr_percent` and the monotonic flag.
2. Add `renderFlowMap` with density-aware classes, explicit zero values and only one bottleneck marker.
3. Replace the overview and advertising funnel call sites with `renderFlowMap`.
4. Add the click/keyboard detail handler and close behavior.
5. Run the focused tests and inline JavaScript syntax check.

### Task 3: Add the visual system

**Files:**
- Modify: `twocomms/management/templates/management/bot.html`

**Steps:**
1. Add node, rail, connector, loss marker and detail styles consistent with the existing dark operations console.
2. Add mobile density rules for 320px without horizontal overflow.
3. Add reduced-motion rules for the new classes.
4. Run `git diff --check` and the full management visual/client contract suites.

### Task 4: Browser and production verification

**Files:**
- Create: `docs/qa/2026-08-08-management-stats-flow-map-qa.md`

**Steps:**
1. Run local browser checks at 1440, 768, 390 and 320px for populated, empty, one-day and custom periods.
2. Check click, Enter, Escape, outside click, reduced motion and no overflow.
3. Compare production API totals with rendered non-zero flow values.
4. Record evidence, commit, push the feature branch, fast-forward `main`, deploy and verify the live SHA.
