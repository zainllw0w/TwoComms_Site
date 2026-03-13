# Agent Handoff Brief For The Implementation File

## Purpose

This brief is for the next agent that will generate the single implementation file. The agent must treat this package as the only canonical synthesis layer and use older folders only through the traceability matrix.

## Mandatory Reading Order

1. `00_INDEX_AND_AUTHORITY_MANIFEST.md`
2. `01_EXECUTIVE_CANONICAL_SYNTHESIS.md`
3. `02_SYSTEM_ARCHITECTURE_AND_INVARIANTS.md`
4. `03`-`08` thematic files
5. `09_CODE_REALITY_MODEL_SERVICE_ENDPOINT_MAP.md`
6. `10_GOVERNANCE_DATA_MODEL_JOBS_ROLLOUT.md`
7. `11_EDGE_CASES_FAILURE_MODES_AND_SCENARIOS.md`
8. `12_TEST_STRATEGY_VALIDATION_ACCEPTANCE.md`
9. `13_IMPLEMENTATION_BLUEPRINT_AND_DEPENDENCY_ORDER.md`
10. `15_TRACEABILITY_MATRIX_AND_SOURCE_COVERAGE.md`
11. `16_DECISION_LOG_REJECTED_IDEAS_AND_BACKLOG.md`

## Required Mindset

- work from current code outward, not from abstract clean-slate architecture;
- extend before create when existing production mechanisms already exist;
- treat every unresolved drift as an explicit decision item, not a hidden assumption;
- keep shadow/admin-only and payroll-final logic clearly separated.

## Required Output Shape For The Future Implementation File

The implementation file should contain:
- goal and scope;
- current code anchors;
- unresolved explicit decisions;
- model changes by migration order;
- service creation/extension map;
- endpoint/template changes;
- command and cron plan;
- test plan with exact modules;
- rollout / hold-harmless / rollback rules;
- deploy and verification steps.

## Explicit Hotspots That Must Not Be Missed

1. `ManagementDailyActivity` already exists.
2. Shop subsystem already exists and matters.
3. `CommercialOfferEmailLog` already exists.
4. `ManagementStatsConfig` must be extended, not bypassed.
5. Telegram admin patterns already exist.
6. `points_override` exists and needs transition semantics.
7. `xml_connected` drift must be resolved deliberately.
8. `views.py` and `stats_service.py` are already large and need decomposition planning.

## Mandatory Separation Rules

| Topic | Rule |
|---|---|
| KPD | keep during transition |
| MOSAIC | shadow-first |
| Telephony | no payroll dependency before maturity |
| QA | coaching before consequence |
| Admin economics | decision support only |
| DTF | separate read-only optional bridge |

## How To Treat Old Sources

- do not quote old folders as direct authority;
- use `15_TRACEABILITY_MATRIX_AND_SOURCE_COVERAGE.md` to see where each old source was absorbed;
- if something appears missing, verify in the matrix before reintroducing it.

## Required Non-Goals

- no new parallel CRM app;
- no silent monitoring layer;
- no direct import of research numbers into runtime code;
- no unconditional telephony-first redesign;
- no payroll decisions based on low-confidence analytics.

## Final Instruction

The future implementation file must be deterministic enough that another agent can implement it without reopening all old report layers. If a section forces the reader to go back to the old folders for basic meaning, the implementation file is incomplete.
