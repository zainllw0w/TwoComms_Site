# Edge Cases, Failure Modes And Scenarios

## Canonical Role

This file codifies the scenarios that most often distort fairness, trust or rollout safety. Each scenario is treated as an explicit contract, not an afterthought.

## Scenario Matrix

| Scenario | Canonical handling |
|---|---|
| Weekend | no punitive daily judgement; weekly logic uses working factor |
| Vacation week | weekly KPI and soft-floor are prorated |
| Sick day mid-week | capacity-aware week normalization |
| Half-day / training / internal work | use `capacity_factor`, not fake full-day logic |
| New manager day 10 | onboarding protection visible and explicit |
| New manager day 20 | onboarding decay stored in snapshot/state |
| Single-manager portfolio dominance | no authoritative peer compare from tiny data |
| Telephony outage | telephony health triggers `TECH_FAILURE`-style safe interpretation |
| Import burst with old due dates | imported backlog grace window |
| Shared switchboard phone | shared-phone registry and review-first dedupe |
| Seasonal gap | explicit planned-gap reason/until/confidence |
| Rescue top-5 during overload | actionability + load cap + DQ grace |
| End-of-day mass logging | repeated-pattern review, not one-shot punishment |
| Honest repeated weak reasons | entropy + concentration, not single crude threshold |
| Long empty grind | test `EWR-v2` in shadow, do not rush production penalty |
| One lucky order on tiny sample | confidence/Wilson/admin caution |
| Payout dispute with unclear freeze | freeze reason line + SLA + evidence drawer |
| Formula version changes | versioned snapshots and no blind cross-version comparison |
| Nightly job missed | stale banner + health widget |
| QA rubric changes | rubric versioning and calibration cycle id |
| 3-person peer benchmark | no manager-facing benchmark |
| Force majeure overlaps payouts | scope field separates score, DMT and payout freeze impact |
| Return after long leave | reintegration capacity curve |
| Admin overuses analytics as payroll verdict | confidence routing limits direct decision use |
| DTF bridge bleeds into wholesale | explicit separate adapter and non-mixing rule |

## Failure Modes To Guard Against

### Data failure

- stale snapshot;
- partial job completion;
- missing call reconciliation;
- shared-phone false positives;
- imported backlog misread as negligence.

### Semantics failure

- shadow data read as final;
- low confidence read as decision-grade;
- minimum-day completion read as healthy pace;
- onboarding protection treated as absence semantics.

### Organizational failure

- ownership fishing for commission;
- admin review through opaque chat-only history without evidence consolidation;
- punitive use of QA before reliability;
- peer pressure by quasi-anonymous tiny-team comparison.

## Required Safe Responses

| Failure class | Mandatory response |
|---|---|
| stale analytics | state badge + admin incident + no fake precision |
| import shock | grace window + separate label |
| provider outage | incident window + telephony suppression |
| long absence return | reintegration mode |
| disputed payout | visible freeze reason + appeal SLA |
| version drift | changelog + versioned snapshots + reset validation window |

## Existing Production Realities To Preserve

- weekends and excused days already should not destroy daily interpretation;
- import, reminders and Telegram flows already exist and must stay operable;
- shop/test/stale signals already exist in code and should be integrated into scenario thinking.

## Implementation Mistakes To Avoid

- handling edge cases only in prose and not in data model/service tests;
- collapsing multiple exception types into one vague `EXCUSED` bucket;
- letting provider outages or stale data create manager blame;
- leaving tiny-team benchmark privacy implicit.
