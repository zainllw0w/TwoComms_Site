# Executive Canonical Synthesis

## Final Thesis

TwoComms Management должна развиваться как эволюция текущего `management`, а не как новая CRM. Итоговая система строится вокруг пяти опор:
- current Django code as reality anchor;
- canonical docs as implementation contract;
- shadow-first rollout for score-sensitive logic;
- payroll-safe interpretation of performance;
- explicit explainability, freshness and appeal paths.

## What Is Fixed As Hard Invariants

1. `verified money truth` важнее любой аналитики.
2. `Result` остаётся доминирующей осью.
3. `DORMANT` компоненты не наказывают менеджера.
4. `trust` может корректировать только evidence-sensitive part, но не уничтожать verified outcome.
5. `telephony` и `QA` не участвуют в деньгах до maturity.
6. `leave`, `tech failure`, `force majeure`, `import burst`, `shared phone` и `tiny-team benchmark` должны иметь explicit guards.
7. никакая новая логика не должна ломать уже существующие CP, Telegram, payout, contract и shop workflows.

## Canonical Target Architecture

| Layer | Final role |
|---|---|
| Legacy KPD | existing production baseline during transition |
| Shadow MOSAIC | new analytical contract validated next to KPD |
| Snapshot layer | stores heavy computations, versions and confidence |
| Manager console | action-first, recovery-first, freshness-aware |
| Admin control center | evidence-first review, routing by confidence |
| Governance layer | versions, incidents, logs, rollout states, appeals |

## Major Upgrades Compared To Baseline

### 1. Authority hardening
- one manifest for authoritative vs superseded vs reference sources;
- no direct reuse of research/reference numbers in code;
- source coverage matrix becomes mandatory.

### 2. Score precision hardening
- explicit `axis_to_slice_contract`;
- `score_confidence` becomes a shared contract, not cosmetic label;
- `EWR-v2` allowed only as `shadow/admin-only` candidate;
- `SourceFairness` must distinguish assigned base from self-selected warm mix;
- `churn_confidence` and stale/freshness semantics added to admin reading.

### 3. Payroll fairness hardening
- weekly KPI becomes capacity-aware;
- `capacity_factor` and reintegration mode are mandatory;
- `repeat` vs `reactivation` split preserved;
- `Soft Floor Cap` preserved, but aligned with working-factor reality;
- appeals, freeze reason and recovery path become explicit.

### 4. Identity and follow-up hardening
- multi-step normalization before fuzzy matching;
- shared-phone registry;
- import burst grace;
- callback cycling and batch logging review patterns;
- per-action rate limits instead of one generic limiter.

### 5. Telephony and QA hardening
- `VerifiedCommunication` stays dormant until provider maturity;
- `TelephonyHealthSnapshot` and reconciliation status become mandatory;
- QA requires rubric versioning, sampling contract and calibration reliability;
- AI assist can only be draft/coaching support.

### 6. UX hardening
- freshness banner;
- confidence badges on disputed surfaces;
- `why changed today`;
- strict separation of `minimum day`, `target pace`, `shadow`, `stale`, `frozen`;
- peer benchmark becomes more conservative for tiny teams.

### 7. Implementation hardening
- code-reality map integrated into the package;
- test strategy, migration safety and rollout order become first-class docs;
- next agent gets a dedicated handoff brief instead of reconstructing context manually.

## Key Existing Production Realities That Must Survive

- `ManagementDailyActivity` already exists and is part of current KPD effort logic.
- Shop subsystem already exists and must be integrated, not rediscovered.
- `CommercialOfferEmailLog` already exists and can become a process/communication signal.
- Telegram-driven admin workflows already exist for payouts and contracts.
- `ManagementStatsConfig` already exists and should be extended, not replaced.
- Current advice engine already exists and should be extended, not rebuilt from zero.

## Canonical Reading Of Money And Performance

| Domain | Rule |
|---|---|
| Money | invoice/payment/approved workflow truth only |
| Score | production-safe performance interpretation |
| Shadow score | visible, explainable, not payroll-final |
| Admin economics | decision support only, not direct payroll verdict |
| QA | coaching until reliability is proven |
| Appeals | required near any consequence-sensitive surface |

## Non-Goals

- no silent surveillance layer;
- no hidden employee ranking from low-confidence data;
- no DTF metric mixing with wholesale truth;
- no forced telephony dependency in phase-0 payroll logic;
- no rewrite of `management` as a new app before rollout even starts.

## Final Instruction For The Next Step

Следующий implementation file должен строиться уже не как набор идей, а как sequence of grounded changes over current code, with explicit separation between:
- extend existing;
- create new;
- keep legacy during transition;
- defer to later phase.
