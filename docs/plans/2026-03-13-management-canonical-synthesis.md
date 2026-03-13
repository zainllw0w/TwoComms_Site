# Management Canonical Synthesis Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a new canonical management analytics synthesis package that supersedes the 2026-03-12 baseline and consolidates baseline, improvement, and code-reality layers into one implementation-ready handoff.

**Architecture:** The new package is a document-first canonical contract. Each thematic file merges authoritative baseline rules, validated improvement deltas, and real-code constraints. Separate traceability, decision, and handoff files prevent idea loss and reduce ambiguity for the next implementation agent.

**Tech Stack:** Markdown, Git, existing Django codebase as grounding context

---

### Task 1: Source Inventory And Coverage Skeleton

**Files:**
- Create: `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/15_TRACEABILITY_MATRIX_AND_SOURCE_COVERAGE.md`
- Modify: `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/00_INDEX_AND_AUTHORITY_MANIFEST.md`

**Step 1: Build the source list**

Record every source file from:
- `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_12/`
- `twocomms/Ideas/management_analytics/reports/tc_mosaic_improvements/`
- `twocomms/Ideas/management_analytics/reports/i1/`

**Step 2: Define coverage statuses**

Use only:
- `fully absorbed`
- `partially absorbed`
- `reference only`
- `superseded`

**Step 3: Wire index to coverage**

The index must state that no source is considered safely migrated until it appears in the traceability matrix.

**Step 4: Verify manually**

Run: `find twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_12 twocomms/Ideas/management_analytics/reports/tc_mosaic_improvements twocomms/Ideas/management_analytics/reports/i1 -type f -name '*.md' | wc -l`
Expected: stable source count used by the matrix

**Step 5: Commit**

```bash
git add docs/plans/2026-03-13-management-canonical-synthesis*.md twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13
git commit -m "docs: scaffold management canonical synthesis package"
```

### Task 2: Authoritative Thematic Contracts

**Files:**
- Create: `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/01_EXECUTIVE_CANONICAL_SYNTHESIS.md`
- Create: `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/02_SYSTEM_ARCHITECTURE_AND_INVARIANTS.md`
- Create: `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/03_SCORE_MOSAIC_EWR_CONFIDENCE.md`
- Create: `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/04_PAYROLL_KPI_PORTFOLIO_EARNED_DAY.md`
- Create: `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/05_IDENTITY_DEDUPE_FOLLOWUP_ANTI_ABUSE.md`
- Create: `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/06_TELEPHONY_QA_SUPERVISOR_VERIFIED_COMMUNICATION.md`
- Create: `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/07_MANAGER_ADMIN_UX_EXPLAINABILITY.md`
- Create: `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/08_ADMIN_ECONOMICS_FORECAST_DECISION_SAFETY.md`

**Step 1: Merge baseline and improvements**

Every thematic file must absorb:
- baseline invariants,
- improvement deltas,
- edge guards,
- explicit non-goals.

**Step 2: Promote only safe deltas**

If an improvement is not production-safe, label it `shadow/admin-only` or `backlog` instead of silently merging it into production rules.

**Step 3: Add implementation anchors**

Each thematic file must end with code-facing anchors and prohibited mistakes.

**Step 4: Verify thematic consistency**

Run: `rg -n "authoritative|shadow/admin-only|backlog|reference-only|rejected" twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/*.md`
Expected: status vocabulary appears across the package

### Task 3: Code-Reality And Rollout Contract

**Files:**
- Create: `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/09_CODE_REALITY_MODEL_SERVICE_ENDPOINT_MAP.md`
- Create: `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/10_GOVERNANCE_DATA_MODEL_JOBS_ROLLOUT.md`
- Create: `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/11_EDGE_CASES_FAILURE_MODES_AND_SCENARIOS.md`
- Create: `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/12_TEST_STRATEGY_VALIDATION_ACCEPTANCE.md`
- Create: `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/13_IMPLEMENTATION_BLUEPRINT_AND_DEPENDENCY_ORDER.md`

**Step 1: Absorb i1 code reality**

Capture existing models, services, views, Telegram integration, test infrastructure, migration order, and hidden business logic already present in code.

**Step 2: Normalize into implementable contracts**

Convert audits into declarative sections:
- extend vs create,
- blocking gaps,
- migration sequence,
- failure semantics,
- acceptance tests.

**Step 3: Add scenario safety**

The scenario file must cover leave, sickness, weekends, telephony outage, import bursts, shared phones, stale snapshots, peer benchmark privacy, and formula version drift.

**Step 4: Verify rollout completeness**

Run: `rg -n "migration|feature flag|command|snapshot|telegram|appeal|rollback|stale" twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/*.md`
Expected: rollout mechanics are explicitly described

### Task 4: Handoff, Decisions, And Change History

**Files:**
- Create: `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/14_AGENT_HANDOFF_BRIEF_FOR_IMPLEMENTATION_FILE.md`
- Create: `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/16_DECISION_LOG_REJECTED_IDEAS_AND_BACKLOG.md`
- Create: `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/17_PACKAGE_CHANGELOG_AND_SUPERSESSION.md`

**Step 1: Write the implementation handoff**

Give the next agent:
- reading order,
- authority rules,
- mandatory files,
- dangerous ambiguities to avoid,
- required outputs of the future implementation file.

**Step 2: Preserve non-adopted ideas**

Rejected, optional, and future ideas must be listed explicitly instead of disappearing.

**Step 3: Describe supersession**

Changelog must explain how the new package differs from the 2026-03-12 baseline and why it should replace it as the canonical source.

### Task 5: Verification, Commit, Push, Deploy

**Files:**
- Modify: `twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13/*`

**Step 1: Run document verification**

Run:
- `find twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13 -maxdepth 1 -type f -name '*.md' | sort`
- `rg -n "TODO|TBD|placeholder" twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13`
- `git diff --stat -- docs/plans/2026-03-13-management-canonical-synthesis-design.md docs/plans/2026-03-13-management-canonical-synthesis.md twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13`

Expected:
- complete file set,
- no unfinished placeholder markers,
- only intended files changed.

**Step 2: Commit only new package files**

```bash
git add docs/plans/2026-03-13-management-canonical-synthesis-design.md \
        docs/plans/2026-03-13-management-canonical-synthesis.md \
        twocomms/Ideas/management_analytics/final_codex_synthesis_2026_03_13
git commit -m "docs: add canonical management synthesis package"
```

**Step 3: Push**

```bash
git push
```

**Step 4: Deploy**

```bash
sshpass -p 'trs5m4t1' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 \
  "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && git pull'"
```

**Step 5: Record continuation context**

Create a short Linear document summarizing the package path, purpose, and reading order so work can resume safely if the local session is interrupted.
