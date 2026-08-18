# API Checker Alignment and Parallel Health Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep all six Gemini aliases in one deterministic hourly metadata run and make every API Checker row/rail align independently of evidence text length.

**Architecture:** `run_hour()` submits one `check_alias()` job per configured alias concurrently, while each job keeps the existing primary-first fallback sequence. Worker threads perform provider GETs only; the coordinator joins them, rejects late evidence at the shared logical deadline, and writes the complete batch in one short database transaction. Slow-drip HTTP reads are not hard-cancelled and remain `IMP-044` work. The browser surface uses fixed grid tracks and constrained metadata blocks so labels, 3.7/3.6 rails, and actions occupy the same columns for every key at desktop and responsive widths.

**Tech Stack:** Django service/tests, Python `ThreadPoolExecutor`, server-rendered Django template with scoped CSS/JavaScript, Playwright visual smoke.

---

### Task 1: Prove concurrent alias scheduling

**Files:**
- Modify: `twocomms/management/tests_gemini_metadata_health.py`
- Modify: `twocomms/management/services/gemini_metadata_health.py`

1. Add a failing regression that blocks six mocked alias jobs on a barrier and asserts they overlap while preserving canonical result order.
2. Run the focused test and confirm it fails against the sequential implementation.
3. Implement concurrent submission and deterministic collection, preserving per-alias `3.7 -> conditional 3.6` behavior. Keep ORM writes off worker threads, join already-submitted workers even when a later submission fails, and atomically persist the completed batch.
4. Run the focused metadata suite and confirm the new regression and existing contracts pass.

### Task 2: Prove stable rail geometry

**Files:**
- Modify: `twocomms/management/tests_gemini_api_ui.py`
- Modify: `twocomms/management/templates/management/bot.html`

1. Add a failing template contract for fixed model-stat columns, constrained text, and equal rail sizing.
2. Run the focused UI contract and confirm it fails against the content-sized `auto` column.
3. Set fixed rail metadata tracks, minimum row heights, and two-line overflow handling at desktop and responsive breakpoints.
4. Run the focused UI contract and browser screenshots at desktop/mobile widths.

### Task 3: Reconcile evidence and ship

**Files:**
- Modify: `docs/instagram_bot_audit/14_IMPLEMENT2.md`
- Modify: `docs/instagram_bot_audit/15_IMPLEMENT2_EMERGENT_FINDINGS.md`

1. Record the parallel scheduling and alignment fixes with exact local/production verification commands.
2. Run the narrow release gate, commit only scoped files, push `main`, pull production with the approved SSH command, and verify the exact SHA plus read-only checker health.
