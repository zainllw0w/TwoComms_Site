# Management Follow-Up Redesign Design

**Date:** 2026-03-17

**Goal:** Rebuild the management shell callback experience so profile/header layout is stable on all widths, callback actions look intentional, callback timing uses one consistent Kyiv-time policy, and phase follow-up UX stays informative without cognitive overload.

## Context

The current management shell has three overlapping problems:

1. The sidebar profile header still allows identity text and action buttons to compete for the same space.
2. Callback state is computed inconsistently across the shell, reminders, and analytics.
3. Follow-up phases expose too much repeated information while still failing to show the right summary context for the next call.

The production environment runs on a hosted server with MySQL and SSH deployment, so local browser validation is useful for DOM/CSS behavior, but final confidence must come from application tests plus server verification after deploy.

## Constraints

- Keep the existing Django/MySQL data model unless a schema change becomes strictly necessary.
- Reuse the existing `ClientFollowUp.grace_until` field instead of adding parallel grace-window storage.
- Treat `Europe/Kiev` as the canonical business timezone for scheduling, display, and validation.
- Avoid introducing a callback UI that depends on truncating role labels or relying on a specific monitor width.
- Preserve backward compatibility for existing client rows and follow-up records already stored in production.

## Approved Approach

Use a controlled system redesign rather than a cosmetic patch. The implementation will combine:

- structural layout fixes for the profile rail and action rail,
- one shared callback-state policy derived from follow-up records,
- stricter Kyiv-time scheduling validation,
- simplified phase presentation with progressive disclosure.

This keeps the change cohesive without rewriting unrelated management flows.

## Design

### 1. Profile Rail Layout

The top profile card will use a reserved two-zone layout:

- left: fixed avatar column,
- center: identity stack with name and role,
- right: fixed-width action-button stack with equal button sizes.

At standard rail widths, name and role stay to the right of the avatar. At narrower widths, the action buttons move into a controlled secondary row instead of forcing the role text under or behind them. The role label remains fully readable by default. Truncation is allowed only as a last-resort visual fallback, not as the primary collision strategy.

### 2. Sidebar Navigation Density

The sidebar `Парсинг` entry will be removed from the rail because the route already exists in the top navigation. This frees vertical space for the shell rail without changing routing behavior.

### 3. Callback Policy

The application will stop treating raw `Client.next_call_at` as the sole source of truth for UI state. The effective callback state must be derived from the active `ClientFollowUp` record and evaluated in Kyiv local time.

Effective states:

- `scheduled`: due time is still in the future,
- `due_now`: due time has passed but the 2-hour grace window is still open,
- `missed`: due time plus grace window has expired and the callback was not completed or rescheduled,
- `cleared`: there is no active callback cycle.

Rules:

- New or updated scheduled callbacks receive a `grace_until = due_at + 2 hours`.
- The shell, reminder digest, grouped client rows, and management metrics must all consume the same effective-state policy.
- A follow-up that was previously overdue but later receives a real callback/reschedule should no longer count as an active missed callback in current shell state.
- Analytics should count missed follow-ups from follow-up records, not from comparing `Client.next_call_at` against today’s date.

### 4. Kyiv-Time Scheduling Validation

Scheduling defaults and validation will be aligned to Kyiv time.

Client-side behavior:

- the default callback time is computed from local Kyiv time and rounded forward into a valid future slot,
- the user cannot start with a past day or a past time for the current day,
- editing an existing stale callback still shows stored data, but resaving a scheduled callback requires a future-valid slot.

Server-side behavior:

- view-level parsing continues to build aware datetimes with Django timezone utilities,
- scheduled callbacks in the past are rejected instead of silently accepted,
- server validation remains authoritative in case browser timezone or local environment differs from production.

This follows Django’s aware-datetime behavior from the official timezone documentation checked through Context7.

### 5. Client Row Action Rail

The callback action rail will be redesigned so the phone action is visually aligned with edit/delete and never fights table text.

Desktop behavior:

- reserve stable width for the actions column,
- render `Передзвонити` as a compact vertical rail button by default,
- expand leftward on hover/focus as an overlay layer above row content,
- keep edit and delete in the same visual stack.

Card/mobile behavior:

- preserve the same ordering,
- keep the callback button compact first,
- expand as an overlay panel without reflowing the rest of the card.

The action rail must use its own stacking context so the expanding button sits above table text instead of behind it.

### 6. Phase Visibility

Phase chips will only appear when there is meaningful multi-step callback progression.

Rule:

- hide phase labels when there have not yet been at least two callback attempts with follow-up progression,
- show phase labelling only when the client is genuinely entering the next callback phase.

This removes false complexity from single-attempt or early callback rows.

### 7. Follow-Up Modal Simplification

The follow-up modal will be split into two cognitive layers:

1. compact read-only recap of the previous interaction,
2. clean input area for the current callback result.

The recap block will show:

- previous result label,
- previous interaction timestamp,
- short previous summary,
- persistent manager note if present.

Older phase history moves into a collapsible section. Editing previous phase details will not be mixed into the new callback input path; it remains part of normal client editing rather than the active next-phase flow.

## Impacted Areas

- `twocomms/management/templates/management/base.html`
- `twocomms/management/templates/management/home.html`
- `twocomms/twocomms_django_theme/static/css/management.css`
- `twocomms/management/views.py`
- `twocomms/management/context_processors.py`
- `twocomms/management/services/followups.py`
- `twocomms/management/services/followup_sync.py`
- `twocomms/management/stats_service.py`
- management shell and follow-up tests

## Testing Strategy

Testing will follow TDD and cover:

- profile header layout contracts in rendered HTML,
- sidebar navigation removal,
- callback-state derivation with scheduled, due-now, missed, and recovered scenarios,
- Kyiv-time validation for default and submitted callback times,
- hidden vs visible phase badges,
- simplified follow-up modal context rendering,
- updated shell metrics and reminder behavior,
- row/card action-rail markup contracts.

## Rollout And Verification

- Implement on a dedicated `codex/` branch.
- Verify locally with targeted Django tests and browser checks.
- Push branch, fast-forward `main`, and deploy via SSH pull on the server.
- Re-check the deployed commit hash on the server to ensure production and repository state match.
