# CSRF Firewall Hardening Design

**Problem:** CrowdSec can block a real user IP when a browser repeatedly triggers Django `403` responses, especially on background or AJAX endpoints. We already proved one production source: `management/activity/pulse/` with a broken CSRF cookie reader.

**Observed Risk Pattern:** The dangerous pattern is not “all 403” but “frontend code reading `csrftoken` in a brittle way, then repeatedly or commonly POSTing with an empty/invalid `X-CSRFToken`”. Current code review shows this same pattern still exists in `management-stats.js` and a few inline admin templates.

## Approaches

### 1. Report only
- Document all hotspots and stop.
- Low risk, but leaves live code paths with the same root pattern.

### 2. Targeted prevention
- Patch all remaining high-risk cookie readers on live POST/fetch code paths.
- Add regression coverage for `management-stats.js`.
- Inventory dirty worktrees and define safe branch rules without auto-committing unrelated WIP.

**Recommendation:** Choose this. It removes the repeated root pattern without broad refactors.

### 3. Full CSRF helper unification
- Build a shared helper and migrate many templates/scripts.
- Cleaner long-term, but much more invasive and conflict-prone in this repository.

## Chosen Design

1. Patch `management-stats.js` to use the same safe CSRF resolution strategy as the fixed activity pulse:
- prefer DOM token,
- fallback to Django-style cookie parsing,
- avoid sending the request if token is invalid.

2. Patch inline admin helper functions that still use the duplicate-cookie-breaking parser:
- `twocomms_django_theme/templates/pages/admin_panel.html`
- `twocomms_django_theme/templates/partials/admin_collaboration_section.html`

3. Add a lightweight Node regression test for `management-stats.js` that reproduces duplicate `csrftoken` cookies and verifies a valid header is still sent.

4. Produce a git/worktree hygiene snapshot:
- identify dirty worktrees,
- group them by overlapping file sets,
- recommend “new work in dedicated `codex/*` branches only”,
- do not auto-commit unrelated WIP.

## Non-goals

- No mass refactor of all CSRF usage in the repo.
- No automatic commit of unrelated user work in dirty branches.
- No server-side CSRF exemptions unless new evidence shows a still-live repeated 403 source after client hardening.
