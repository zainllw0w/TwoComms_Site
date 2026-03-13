# Manager/Admin UX And Explainability

## Canonical Role

UI must make the system operationally useful and psychologically readable:
- action-first for managers;
- evidence-first for admins;
- freshness and confidence always visible where ambiguity matters;
- no shadow state masquerading as final truth.

## Manager Console Contract

### Required top layer

- period selector;
- current mode and state badges;
- concise KPI and score summary;
- direct path to action surfaces.

### Hero block

Manager hero must contain:
- current KPD and shadow MOSAIC relationship;
- Radar preview;
- delta vs previous period;
- main recovery hint;
- freshness state.

### Today Action Stack

Required groups:
- overdue follow-ups;
- critical today clients;
- rescue top-5;
- pending next steps;
- blockers.

Action stack should split into:
- `must do today`
- `best opportunities today`

## Required Explainability Surfaces

### `Why changed today`

Required mini-surface near the hero:
- concrete positive and negative drivers;
- shadow-only changes labeled clearly;
- direct link to decomposition.

### Waterfall / decomposition

Every score-sensitive number must open a readable breakdown:
- base value;
- trust effect;
- gate;
- dampener;
- onboarding or hold-harmless effect;
- confidence and freshness.

### Correctability

If a surface can affect payout, score-sensitive review or freeze:
- show explicit `Appeal / Оспорить`;
- open evidence-first flow, not free-text chaos.

## State And Badge Contract

Manager and admin surfaces must distinguish:
- `ACTIVE`
- `SHADOW`
- `DORMANT`
- `FROZEN`
- `STALE`
- `LOW CONFIDENCE`

These states must not share the same visual weight.

## Minimum vs Target Pace

UI must separate:
- `minimum day achieved`;
- `target pace healthy`;
- `recovery needed`.

This distinction is mandatory to prevent optimization toward the bare minimum.

## Manager Widgets

### Radar

- explanatory only, not payroll truth by itself;
- supports self and previous period comparison;
- comparative overlay hidden or banded in tiny teams;
- low-data axes show explicit lower-confidence styling.

### Rescue top-5

Card must show:
- `value at risk`;
- `time urgency`;
- confidence;
- planned gap or snooze if present;
- potential SPIFF if applicable.

### Salary simulator

Must show:
- current truth;
- shadow candidate;
- delta explanation;
- confidence/freshness;
- freeze items with explicit status line.

### Client communication timeline

Must unify:
- calls;
- messages / CP emails;
- notes;
- follow-ups;
- invoices / orders;
- ownership changes;
- QA/dispute flags where relevant.

## Advice Contract

### Copy style

Allowed semantics:
- recovery-first;
- next action;
- room for improvement;
- evidence-backed suggestion.

Forbidden semantics:
- humiliation;
- hidden threat;
- opaque decline without recovery path.

### Advice lifecycle

Required fields:
- title;
- core reason;
- evidence;
- CTA;
- dismiss behavior.

Required controls:
- `cooldown_hours`
- `dismiss_ttl`
- reappear only on state change

Existing dismissal mechanism must be reused instead of rebuilt.

## Admin Control Center Contract

### Mandatory widgets

- formula/defaults/snapshot health;
- queue presets;
- low-confidence and stale states;
- evidence-first compare drawer;
- freeze/review/appeal queues;
- admin economics and forecast summary.

### Queue presets

At minimum:
- duplicate review;
- payout freeze;
- appeals nearing SLA breach;
- low-confidence managers;
- follow-up overload;
- telephony mismatch.

## Benchmarking Contract

Manager-facing comparative benchmark must be stricter than baseline:
- `N < 5` -> no peer benchmark;
- `N = 3-4` -> self vs previous period only or banded team range;
- full comparative view belongs to admin, not manager, in tiny teams.

## Mobile-First Contract

Critical mobile requirements:
- one-screen action access;
- compact state chips;
- sticky quick actions only where work is being done;
- report/notes flow without desktop-only friction;
- no heavy component required for basic manager work.

## Existing Production Realities To Preserve

- `stats.html` and `stats_views.py` are the primary extension surface;
- current advice engine already exists;
- admin and Telegram-driven workflows already exist and must stay aligned;
- current manager base template already exposes Telegram binding state and should remain operationally coherent.

## Implementation Landing

- extend `stats.html`, `stats_admin_*`, `admin.html` and supporting assets;
- split large templates into includes for radar, rescue, simulator, explanation and timeline;
- surface freshness and confidence from snapshots, not ad hoc frontend guesses.

## Implementation Mistakes To Avoid

- rendering shadow values without explicit labels;
- showing stale analytics like current truth;
- presenting anonymous peer comparison in a 3-person team;
- building a beautiful dashboard that hides next actions.
