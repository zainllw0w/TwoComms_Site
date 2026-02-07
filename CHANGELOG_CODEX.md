# CHANGELOG CODEX

## 2026-02-07 02:05 UTC
- Scope: Part 3 execution protocol hardening and QA/evidence updates for `dtf.twocomms.shop`.
- Summary:
  - Added operational runbook artifacts and refreshed QA evidence (tests, pip-audit, curl matrix, lighthouse).
  - Synced checklist/docs to Part 3 definition-of-done flow.
  - Kept isolation: DTF-only workflows and verification; main-domain behavior unchanged.
- Files:
  - `specs/dtf-codex/CHECKLIST.md`
  - `specs/dtf-codex/QA.md`
  - `specs/dtf-codex/DEPLOY.md`
  - `specs/dtf-codex/EVIDENCE.md`
  - `DTF_CHECKLIST.md`
  - `MCP_TODO.md`
  - `EVIDENCE.md`
  - `DEPLOY.md`
- Rollback note:
  - Docs-only rollback: checkout previous commit and restore docs.
  - If deployed and any regression appears: checkout last good commit on server, run `collectstatic`, then `touch tmp/restart.txt`.
