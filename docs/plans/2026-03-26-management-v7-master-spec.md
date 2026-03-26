# Management V7 Master Spec

> Canonical implementation contract for the management analytical subdomain. `v4`, `v5`, and `v6` remain source material, not executable truth.

## Implemented Core
- `Report` is observational only. Sending a report no longer mutates open `ClientFollowUp` rows.
- `ClientFollowUp` now carries semantic fields required by `v7`: `followup_kind`, `close_reason`, `completion_quality`, `source_interaction`, `reschedule_count`, `priority_snapshot`.
- New additive analytical tables are live in schema and wired through service-layer dual-write:
  - `WorkingCalendarProfile`
  - `WorkingCalendarAssignment`
  - `WorkingCalendarException`
  - `FollowUpEvent`
  - `ClientStageEvent`
  - `ReasonSignal`
  - `VerifiedWorkEvent`
  - `ManagerDayFact`
  - `ScoreAmendment`
- `record_client_interaction()` is now atomic and writes `ClientStageEvent`, `ReasonSignal`, and `VerifiedWorkEvent` after evidence/link completion.
- `sync_client_followup()` now uses row-level close/open handling under transaction control and emits `FollowUpEvent` lineage instead of relying on bulk state mutation.
- `persist_nightly_snapshot()` now embeds a `payload["v7"]` section derived from `ManagerDayFact`.
- Appeals create/update `ScoreAmendment` records so amendments have an explicit queueable lineage.
- `backfill_management_v7_analytics` provides an idempotent seed path for legacy data.

## Source Of Truth Matrix
| Concern | Source of truth | Notes |
|---|---|---|
| Follow-up operational truth | `ClientFollowUp` + `FollowUpEvent` | `ClientFollowUp` is current state, `FollowUpEvent` is lineage. `Report` must never close follow-ups. |
| Interaction evidence truth | `ClientInteractionAttempt` | Dual-write materializes `ReasonSignal`, `ClientStageEvent`, `VerifiedWorkEvent`. |
| Manager day override | `ManagerDayStatus` | Still authoritative per-day override. `WorkingCalendar*` only seeds defaults/context. |
| Manager day analytical read model | `ManagerDayFact` | Daily scoring inputs must come from here, not ad hoc joins in views. |
| Snapshot/read model | `NightlyScoreSnapshot.payload["v7"]` | Legacy payload remains available during staged rollout. |
| Appeal/amendment lineage | `ScoreAppeal` + `ScoreAmendment` | Appeal creates pending amendment; resolution updates amendment status. |

## Keep / Rework / Drop
| Item | Decision | Reason |
|---|---|---|
| Shadow snapshot shell and explainability surfaces | Keep | Existing UX already carries useful decomposition/readiness patterns. |
| Bulk report-driven follow-up closure | Drop | Semantically wrong and race-prone. |
| Bulk follow-up state updates without per-row lineage | Rework | Replaced by transactional row handling plus `FollowUpEvent`. |
| Ad hoc raw-table scoring reads | Rework | `v7` score lineage must come from `ManagerDayFact`. |
| Manual snapshot editing in admin | Rework | Snapshot admin is read-only to protect parity and lineage. |
| Writable follow-up admin as routine correction path | Rework | Follow-up admin is read-only; correction should flow through explicit service paths. |

## Rollout Contract
- Default runtime state remains staged: legacy/previous shadow behavior can coexist while `payload["v7"]` matures.
- Production activation of `v7` scoring must require:
  - parity checks against current live metrics,
  - backfill completion,
  - stale-data checks,
  - late-event rerun validation,
  - appeal/amendment visibility in admin.
- Any score formula that cannot point to a concrete source field, freshness rule, and backfill path stays shadow-only.

## Verification Baseline
- Regression tests cover the P0 report/follow-up bug.
- Dual-write tests cover:
  - interaction -> reason/stage/verified events,
  - follow-up open/close lineage,
  - manager-day fact materialization,
  - snapshot `v7` embedding,
  - idempotent backfill reruns.
- `twocomms/test_settings.py` is now self-sufficient for local management tests and disables HTTPS redirects during test execution.
