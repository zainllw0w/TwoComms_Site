# Code Reality, Model, Service And Endpoint Map

## Canonical Role

This file is the anti-duplication bridge between design and current code. It defines what already exists, what must be extended, and what must be created.

## Existing Production Modules

| File | Reality | Action |
|---|---|---|
| `management/models.py` | 20+ existing domain models and workflows | `extend carefully` |
| `management/stats_service.py` | current KPD, advice, shop metrics, caching | `extend then decompose` |
| `management/views.py` | large admin/Telegram/payout/contracts workflow hub | `avoid parallel rewrite` |
| `management/stats_views.py` | score and stats surface | `primary extension target` |
| `management/lead_views.py` | lead flows | `extend for dedupe only where needed` |
| `management/management/commands/notify_test_shops.py` | existing command + Telegram pattern | `reuse as command pattern` |

## Existing Models That Must Be Recognized

### Already present and must not be rediscovered

- `Client`
- `ManagementLead`
- `ReminderSent`
- `ReminderRead`
- `CommercialOfferEmailLog`
- `Shop`
- `ManagementDailyActivity`
- `ClientFollowUp`
- `ManagementStatsAdviceDismissal`
- `ManagementStatsConfig`
- `ManagerCommissionAccrual`
- `ManagerPayoutRequest`
- contract-related admin Telegram models

### Critical existing business layers

- shop subsystem for retail/test conversion and stale relationship tracking;
- CP email system with send analytics;
- Telegram-based admin workflows for payouts and contracts;
- manual override and freeze mechanisms already present in the codebase.

## Extend vs Keep vs Create

### Models

| Model / entity | Action | Note |
|---|---|---|
| `Client` | `EXTEND` | add portfolio/dedupe helpers, not `is_test` if test truth belongs to `Shop` |
| `ManagementStatsConfig` | `EXTEND` | add MOSAIC/defaults/formula version fields rather than new registry model |
| `ClientFollowUp` | `EXTEND` | add richer ladder and audit semantics |
| `ManagerCommissionAccrual` | `KEEP` | `frozen_until` already exists |
| `ManagerPayoutRequest` | `KEEP` | workflow already exists |
| `NightlyScoreSnapshot` | `CREATE` | new |
| `ComponentReadiness` | `CREATE` | new |
| `CommandRunLog` | `CREATE` | new |
| `ScoreAppeal` or aligned appeal model | `CREATE/ALIGN` | new or mapped to existing dispute patterns |
| `ManagerDayStatus` | `CREATE` | new |
| `CallRecord` | `CREATE` | later-phase new |

### Services

| Service | Action |
|---|---|
| current KPD compute | `KEEP` during transition |
| current advice generator | `EXTEND`, do not replace blindly |
| source normalization helper | `KEEP/EXTEND` |
| `compute_ewr` | `CREATE` |
| `compute_mosaic` | `CREATE` |
| `compute_trust_production` | `CREATE` |
| `compute_churn_weibull` | `CREATE` |
| `compute_score_confidence` | `CREATE` |
| `find_duplicates_safe` | `CREATE` |
| `build_rescue_top5` | `CREATE` |

## Existing Hidden Logic That Must Influence The Design

### Shop subsystem

Already computes:
- stale shops;
- overdue tests;
- tests converted to full shops;
- shipments and communication activity.

Canonical implication:
- shop health and test-to-full conversion must be integrated into portfolio/result thinking;
- implementation must not ignore `managed_by` vs `created_by`.

### ManagementDailyActivity

Already part of current KPD effort semantics.

Canonical implication:
- do not treat active-tab time as purely hypothetical future metric;
- if downgraded to admin-only later, the transition must be explicit.

### CP email analytics

Already present through `CommercialOfferEmailLog`.

Canonical implication:
- CP send/failure and communication evidence can feed process/proxy communication logic;
- no need to invent a fresh communication log from zero.

### Existing advice infrastructure

Already present through current advice generation and dismissal mechanics.

Canonical implication:
- extend `generate_advice()` semantics instead of creating a parallel tips engine;
- reuse `ManagementStatsAdviceDismissal` for cooldown/dismiss logic;
- preserve existing advice families like source comparison, shop health and follow-up discipline as the base layer, then add MOSAIC-aware cards on top.

## Existing Risks And Gotchas

1. `points_override` exists and can create transition inconsistency if ignored.
2. `xml_connected` points drift exists between docs and current code and must be resolved explicitly, not assumed.
3. `normalize_phone()` is limited in scope; treat it as current implementation reality.
4. current stats payload uses cache with a short TTL, so snapshot-vs-live semantics must be explicit.
5. `WholesaleInvoice` integrations already exist and may fail soft if dependency unavailable.
6. existing advice and dismissal logic can be accidentally duplicated if the implementation file treats tips as a new subsystem.

## Endpoint And Template Landing

### Existing surfaces to extend

- `stats.html`
- `stats_admin_list.html`
- `stats_admin_user.html`
- `admin.html`
- payout-related templates
- `base.html` if new navigation state is needed

### Existing routing style

Use current URL/view patterns. New endpoints should be added surgically rather than introducing a parallel application surface.

## Existing Telegram Pattern To Reuse

Current code already supports:
- admin chat id discovery;
- manager chat id usage;
- message/document send;
- idempotent reminder send via `ReminderSent`;
- webhook processing for admin decisions.

Future stale/freeze/appeal/incident alerts should reuse this pattern.

## Implementation Landing

- introduce `services/` decomposition rather than keep all new logic in `stats_service.py`;
- add models in small migrations;
- map new UI surfaces to existing templates rather than parallel frontend stack;
- keep commands cron-friendly and idempotent.

## Implementation Mistakes To Avoid

- re-creating existing CP, payout or Telegram workflows under new names;
- using `Shop.created_by` as the live portfolio owner when `managed_by` is the operational reality;
- writing design as if management app starts from zero;
- treating existing dismissal, freeze and reminder mechanisms as missing.
