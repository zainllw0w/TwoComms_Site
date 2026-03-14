# Telephony, QA, Supervisor And Verified Communication

## Canonical Role

This file defines the maturity-gated telephony and QA layer. The target state is richer evidence and coaching quality, not a premature payroll dependency.

## Phase Model

| Phase | Meaning | Consequence |
|---|---|---|
| `Phase 0` | manual/CRM-backed proxy only | `VerifiedCommunication` stays `DORMANT` |
| `Phase 1` | provider connected, calls ingested | telephony visible in shadow/admin-only mode |
| `Phase 2` | supervisor mode and stable QA | some trust inputs may activate cautiously |
| `Phase 3` | AI assist and enriched coaching | still not direct payroll truth |

## Minimal Data Model

### Required entities

- `CallRecord`
- `TelephonyWebhookLog` or equivalent inbox
- `CallQAReview`
- `TelephonyHealthSnapshot`
- supervisor action log

### Mandatory fields on or around call records

- client link
- owner
- provider call id
- started timestamp
- duration
- direction
- outcome
- raw payload
- reconciliation status

Preferred extension:
- `ring_seconds`
- `connected_seconds`
- `talk_seconds`

## Verified Communication Contract

### Before telephony activation

Allowed proxy signals:
- CRM updates;
- message/email/CP evidence;
- follow-up completion.

These signals are useful for process and coaching but do not activate `VerifiedCommunication` as production score axis.

### After activation

Minimum telephony truth:
- provider-confirmed call exists;
- phone matched to known client or review queue;
- timestamp and duration stored;
- reconciliation status visible.

### Meaningful call rule

- `>30s` only becomes production-relevant after telephony maturity;
- `<15s` cannot justify strong outcomes;
- `<30s` may be weak touch evidence, not full quality proof;
- short call + strong CRM success without evidence goes to mismatch review.

## Telephony Health Contract

`TelephonyHealthSnapshot` is mandatory and must store:
- webhook lag;
- unmatched call ratio;
- missing recording ratio;
- provider error burst;
- reconciliation backlog size;
- snapshot freshness.

If health falls below threshold:
- telephony-based punitive interpretations are suppressed;
- incident state is visible to admin;
- operational window may map to `TECH_FAILURE`.

## Reconciliation Contract

Every call record or equivalent event must have a status:
- `matched_exact`
- `matched_last7_reviewed`
- `unmatched`
- `manual_proxy`
- `provider_orphan`

This status must be visible in disputes and supervisor review.

## QA Contract

### Rubric

QA reviews must store:
- `rubric_version`
- `reviewer_id`
- `calibration_cycle_id`

### Sampling

Minimum safe starting rule:
- `3 calls/week/manager` or `5% of eligible calls`, whichever is higher;
- stratify by short/long, successful/unsuccessful, source type, new/repeat touch.

### Reliability

| Reliability band | Rule |
|---|---|
| `kappa >= 0.80` | reliable enough for score-sensitive use |
| `0.60-0.79` | coaching only |
| `<0.60` | stop score-sensitive use and recalibrate |

### Calibration

Blind double-review is required during calibration windows.

## Supervisor Contract

### Actions

- `monitor`
- `whisper`
- `barge`

Each action must be logged with call id, actor, time and reason.

### Outcome mismatch matrix

Grouped review patterns are required:
- short call + strong outcome;
- no recording + strong outcome;
- long call + repeated weak outcomes;
- same-day stage jump without comms evidence.

### Coaching artifact

Manager-facing coaching output should contain:
- one main strength;
- one main fix;
- one next experiment;
- evidence link.

## AI Assist Contract

- AI summary is draft only;
- AI tags do not become payroll truth;
- dispute resolution always relies on raw records and timeline, not AI impression.

## Existing Production Realities To Preserve

- telephony is not phase-0 prerequisite;
- current Telegram and CP evidence patterns already exist;
- `CommercialOfferEmailLog` and message delivery evidence are useful proxy signals in Phase 0;
- legal hold and retention must be planned from the start.

## Implementation Landing

- add telephony models and commands;
- add provider adapter interface and webhook authentication;
- add health rollups and orphan reconciliation job;
- add QA review queue only after data ingestion is stable;
- connect admin/supervisor views before any payroll-sensitive usage.

## Implementation Mistakes To Avoid

- treating provider outage as manager underperformance;
- using total call duration as talk quality when talk seconds are unavailable;
- starting QA as punitive system before calibration;
- allowing AI-generated interpretation to overrule raw evidence.
