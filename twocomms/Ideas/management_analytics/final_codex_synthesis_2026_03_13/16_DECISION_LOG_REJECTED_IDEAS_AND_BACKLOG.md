# Decision Log, Rejected Ideas And Backlog

## Fully Accepted Into The Canonical Contract

- shared-hosting-first execution model;
- KPD -> shadow MOSAIC transition;
- EWR as `Result` core;
- `score_confidence`;
- capacity-aware KPI and reintegration;
- soft-floor instead of cliff penalties;
- repeat vs reactivation split;
- explicit `Weibull` churn contract with logistic fallback, planned-gap neutrality and `k` cap;
- shared-phone registry and normalization pipeline;
- import burst grace;
- soft score-cap anti-gaming that preserves operational audit trail;
- telephony health snapshot and reconciliation statuses;
- QA rubric versioning and calibration gating;
- freshness and `why changed today`;
- admin economics routed by confidence;
- versioned snapshots and command run logs;
- appeal and correctability surfaces;
- rollout DICE checkpoint and `+10%` manager-overhead guard.

## Accepted Partially

| Idea | Final status | Reason |
|---|---|---|
| `EWR-v2` | `shadow/admin-only` | promising but not yet production-safe |
| `Wilson` conversion metric | `shadow/admin-only` | diagnostic, not replacement for EWR |
| workload consistency / active tab time | `admin-only diagnostic` | existing reality acknowledged, but no hidden surveillance expansion |
| weighted attribution split for deals | `rare admin-approved exception` | not default operating mode |
| DTF bridge | `late-phase read-only backlog` | useful, but strictly separated from wholesale truth |
| telephony-derived trust inputs | `later-phase conditional` | only after health and QA maturity |

## Explicitly Rejected

- direct production dependency on Celery or Redis;
- `pg_trgm` as baseline dedupe requirement;
- auto-merge on fuzzy match alone;
- automatic punitive QA before calibration;
- one-shot heuristic punishments from low sample noise;
- shadow metrics rendered as final payroll truth;
- DTF metrics mixed into wholesale score;
- hidden monitoring or silent employee surveillance layer.

## Explicitly Unresolved And Must Be Decided In Implementation Planning

1. `xml_connected` points drift between docs and current code.
2. whether `Client.is_test` is needed at all if test truth belongs to `Shop`.
3. exact migration shape for appeals: standalone model vs aligned extension of existing dispute workflows.
4. exact storage granularity for raw snapshots vs compact snapshots.
5. extent of international phone normalization beyond current scope.

These are decision items, not silent assumptions.

## Later-Phase Backlog

- telephony AI assist;
- richer supervisor analytics;
- safe DTF read-only bridge;
- additional admin what-if tools;
- broader forecast and cohort intelligence once data matures.

## Historical Items Preserved As Reference Only

- older superiority-analysis narratives;
- research prompts and deep-research briefs;
- legacy audit prose already folded into the current decisions.

## Canonical Interpretation Rule

If an idea appears in old sources but not here:
- check `15_TRACEABILITY_MATRIX_AND_SOURCE_COVERAGE.md`;
- if it is `reference only` or `superseded`, do not revive it silently;
- if it is accepted partially, keep the canonical status boundary;
- if it is unresolved, surface it explicitly in the future implementation file.
