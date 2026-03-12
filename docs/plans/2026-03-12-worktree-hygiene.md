# Worktree Hygiene Snapshot

## Current Safe Baseline

- **Release/hotfix workspace:** `/private/tmp/twocomms-main-release-20260310`
- **Current hardening branch:** `codex/csrf-hardening-20260312`
- **Rule:** production-facing fixes should be prepared only from a clean release worktree, never from the main interactive workspace.

## Dirty Worktree Inventory

### 1. Main interactive workspace
- **Path:** `/Users/zainllw0w/PycharmProjects/TwoComms`
- **Branch:** `codex/iter3-copy-ui`
- **State:** large mixed WIP
- **Notes:** combines tracked UI changes (`.htaccess`, management template/JS) with many untracked idea/docs folders and temporary artifacts. This is not a safe place for release commits.

### 2. Nova Poshta / analytics / order-success cluster
These worktrees overlap heavily on the same files and should not all continue in parallel:

- `/Users/zainllw0w/.cursor/worktrees/TwoComms/5Q9H5`
- `/Users/zainllw0w/.cursor/worktrees/TwoComms/6fca2`
- `/Users/zainllw0w/.cursor/worktrees/TwoComms/6p7qS`
- `/Users/zainllw0w/.cursor/worktrees/TwoComms/DwCp2`
- `/Users/zainllw0w/.cursor/worktrees/TwoComms/EGwve`
- `/Users/zainllw0w/.cursor/worktrees/TwoComms/HeINs`
- `/Users/zainllw0w/.cursor/worktrees/TwoComms/NP4T8`
- `/Users/zainllw0w/.cursor/worktrees/TwoComms/u_bqp`
- `/Users/zainllw0w/.cursor/worktrees/TwoComms/V44V7`
- `/Users/zainllw0w/.cursor/worktrees/TwoComms/WJw9v`
- `/Users/zainllw0w/.cursor/worktrees/TwoComms/zr64x`

**Shared files repeatedly dirty across this cluster:**
- `twocomms/orders/management/commands/update_tracking_statuses.py`
- `twocomms/orders/nova_poshta_service.py`
- `twocomms/twocomms_django_theme/static/js/analytics-loader.js`
- `twocomms/twocomms_django_theme/templates/base.html`
- `twocomms/twocomms_django_theme/templates/pages/order_success.html`

**Assessment:** this is the main merge-conflict hotspot. Pick one canonical branch/worktree for this theme and either commit there or archive the duplicates.

### 3. Performance checklist duplicates
- `/Users/zainllw0w/.cursor/worktrees/TwoComms/60Aa4`
- `/Users/zainllw0w/.cursor/worktrees/TwoComms/B8pJf`
- `/Users/zainllw0w/.cursor/worktrees/TwoComms/QVwRx`

**Assessment:** same document-only task duplicated three times. Keep one, close/remove the other two.

### 4. Performance analysis branch
- `/Users/zainllw0w/.cursor/worktrees/TwoComms/3857K`

**Assessment:** dirty but self-contained doc/monitoring work. Low risk for code conflicts if kept isolated.

### 5. OAuth branch
- `/Users/zainllw0w/.cursor/worktrees/TwoComms/3rk3A`

**Assessment:** moderate risk because it touches `twocomms/twocomms/settings.py`, frontend analytics, and base template.

## Recommended Rules Going Forward

1. **All new work starts from a dedicated `codex/*` branch in a clean worktree.**
2. **Production hotfixes are prepared in a clean release worktree only.**
3. **Do not auto-commit mixed WIP from dirty branches.** First decide whether the branch is:
   - releasable,
   - still experimental,
   - duplicate and removable.
4. **Collapse duplicate branch families** before new work on the same file set.
5. **One theme = one active branch/worktree** when files overlap heavily.

## Immediate Cleanup Recommendation

- Keep using `/private/tmp/twocomms-main-release-20260310` for hardening/hotfixes.
- Do **not** release from `/Users/zainllw0w/PycharmProjects/TwoComms`.
- For the Nova Poshta cluster, choose one keeper branch and freeze the rest until you explicitly reconcile them.
- For the performance checklist trio, keep one and delete/close the duplicates after extracting anything important.
