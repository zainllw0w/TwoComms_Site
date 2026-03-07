# Deep Research Brief for TwoComms Management Subdomain

## 1. Purpose of this file

This file is the briefing document for another AI agent that will perform deep research.

Its job is not to produce a generic CRM report.
Its job is to research improvements for the **actual TwoComms management project** and to evaluate ideas in the context of the existing planned architecture in this folder.

The agent must understand:
- what kind of business this is,
- what management system is being planned,
- what metrics and formulas already exist,
- which ideas are already accepted,
- which areas still require external evidence,
- and what kind of recommendations would be useless or harmful for this project.

## 2. Project snapshot

`TwoComms Management` is a management subdomain for a **small B2B wholesale sales team**.

The context is not crypto, not a trading platform, not a support desk, not a generic enterprise call center, and not consumer ecommerce.

The closest context is:
- small-team outbound and semi-warm B2B sales,
- fashion wholesale and shop onboarding,
- lead parsing and lead import from different sources,
- repeat orders and client portfolio management,
- callback discipline,
- manager KPI and payroll,
- admin supervision,
- explainable statistics,
- and later IP telephony with call QA.

The target outcome is not just "more activity".
The target outcome is:
- higher conversion quality,
- higher repeat revenue,
- better callback discipline,
- lower duplicate leakage,
- less fake reporting,
- fairer manager evaluation,
- stronger admin visibility,
- and clearer payroll logic.

## 3. Operating model of the business

The deep-research agent must reason in the following operating model:

1. Managers work with shops and leads, not with anonymous retail consumers.
2. Lead sources differ a lot in difficulty:
- cold XML / parser lists,
- parsed cold lead streams,
- manually found leads,
- warm reactivations,
- hot inbound demand.
3. A manager can generate:
- first paid order,
- repeat paid order,
- callbacks,
- notes,
- disqualification reasons,
- follow-up chains,
- portfolio recovery,
- and later telephony events.
4. The system must separate:
- verified business outcomes,
- manager-reported activity,
- admin-reviewed quality,
- and noisy signals that should not dominate payroll.
5. The current and planned team size is closer to `3-7 managers` than to `50+`.
6. Seasonality matters because fashion wholesale has uneven demand and collection cycles.
7. The system must support both:
- new-business acquisition,
- and retention / repeat ordering from the portfolio.

## 4. What is being built

The final architecture in this folder is not a greenfield CRM fantasy.
It is a practical management operating system with these planned layers:

1. `MOSAIC score`
- a fair daily efficiency system,
- source-aware,
- anti-abuse aware,
- not purely activity-based.

2. `Payroll and KPI engine`
- salary support,
- KPI compliance,
- dual probation,
- portfolio bonus,
- repeat-order incentives.

3. `Anti-duplication and follow-up engine`
- exact and fuzzy duplicate detection,
- merge rules,
- batch import safety,
- reminder ladder,
- overdue control.

4. `Telephony and QA contour`
- phased IP telephony rollout,
- recordings,
- supervisor listening,
- admin scores,
- reliability calibration,
- call statistics.

5. `Manager/Admin UI`
- action-first manager console,
- admin queues,
- explainable score breakdown,
- mobile-first worklist.

6. `Implementation roadmap and guardrails`
- staged rollout,
- audit logging,
- security,
- backup,
- performance budgets.

## 4.1 Existing domain objects and signals the agent should assume are real

The current project already has management-related entities and signals.
The research should assume evolution of an existing system, not invention from zero.

Known domain objects and event types include:
- `Client`
- `ManagementLead`
- `ClientFollowUp`
- `Shop`
- `ShopCommunication`
- `CommercialOfferEmailLog`
- `ManagementDailyActivity`
- `ManagerCommissionAccrual`
- `ManagerPayoutRequest`
- `ReminderSent`

This matters because recommendations should fit a model where:
- lead, shop, follow-up and communication data already exist,
- reminders already exist in some form,
- commissions and payout requests already exist,
- and analytics should be layered on top of those realities.

## 5. Fixed assumptions and non-negotiable principles

The deep-research agent may challenge thresholds and formulas, but it must respect the following core principles unless it presents strong evidence to replace them.

### 5.1 Business truth hierarchy

- Verified outcomes are more important than self-reported activity.
- A manager should not get a high score from volume alone.
- A manager should not be punished by source difficulty without normalization.

### 5.2 Compensation truth

- `2.5%` first order / `5%` repeat order remains the financial core unless there is a very strong reason to propose a better structure.
- Payroll logic must stay explainable to both admin and manager.

### 5.3 Hard verified signal

- `shop added = already paid` is treated as a hard verified business event.

### 5.4 Behavioral principle

- The system must improve real selling discipline, not generate fake activity.
- It must reduce spam, duplicate work, empty reminders, and performative KPI chasing.

### 5.5 Organizational principle

- `manager view` and `admin view` must stay separated.
- Public humiliation mechanics are not acceptable.
- A fully public aggressive leaderboard is not the default.

### 5.6 Technical principle

- Recommendations should fit a Django + Celery + Redis style management stack.
- The system should be realistic for phased rollout, not dependent on a perfect data warehouse from day one.

### 5.7 Product boundary principle

- Management analytics for wholesale managers should not be mixed into unrelated product areas.
- `DTF` and other domains should not be collapsed into the same core performance truth for this management system.

## 6. Current baseline numbers that research should validate, tune, or replace

These are the current starting numbers in the final package.
The deep-research agent must not blindly accept them.
It should evaluate whether they are strong, weak, or should be adjusted for small-team B2B wholesale.

### 6.1 Current daily score architecture

Current authoritative score formula:

`0.40 Result + 0.15 SourceFairness + 0.15 Process + 0.10 FollowUp + 0.10 DataQuality + 0.10 VerifiedCommunication`

### 6.2 Current source fairness baselines

Starting baselines:
- `cold_xml = 1.5%`
- `parser_cold = 3%`
- `manual_hunt = 6%`
- `warm_reactivation = 18%`
- `hot_inbound = 30%`

Recalibration policy:
- quarterly review,
- bounded adjustment,
- default cap `+/-25%` per recalibration cycle.

### 6.3 Current gate defaults

Current start thresholds:
- `100` if paid order exists,
- `78` if strong pipeline proof exists,
- `60` if verified communication and disciplined execution exist,
- `45` after `3+` business days if only lower-grade progress exists.

### 6.4 Current KPI presets

Current operating presets:

`TESTING`
- `20` daily meaningful contacts,
- `1` new paid per week,
- `80%` callback SLA,
- `85%` report compliance,
- duplicate abuse `<5%`

`NORMAL`
- `35` daily meaningful contacts,
- `2` new paid per week,
- `85%` callback SLA,
- `90%` report compliance,
- duplicate abuse `<3%`

`HARDCORE`
- `50` daily meaningful contacts,
- `3` new paid per week,
- `90%` callback SLA,
- `95%` report compliance,
- duplicate abuse `<2%`

### 6.5 Current telephony maturity caps

Current `VerifiedCommunication` maturity cap:
- `manual_only = 60`
- `soft_launch = 80`
- `supervised = 100`

### 6.6 Current portfolio cadence

Current client portfolio timing:
- `Healthy = 0-21 days`
- `Watch = 22-35 days`
- `Risk = 36-45 days`
- `Rescue = 46-60 days`
- `Reassign Eligible = 61+ days`

### 6.7 Current micro-feedback philosophy

Micro-feedback is allowed only as a bounded secondary layer.
It must never become the main payroll truth.

## 7. Scope guardrails for the research

The deep-research agent must search for evidence in contexts similar to this project.

### 7.1 In-scope source patterns

Prioritize:
- B2B sales operations,
- small-team CRM operations,
- outbound sales QA,
- callback management,
- telephony supervision,
- duplicate management in CRM,
- incentive design for repeat business,
- explainable performance scoring,
- benchmarking from CRM, call QA and sales operations products,
- and relevant academic work on motivation, measurement reliability, performance management and alert fatigue.

### 7.2 Out-of-scope patterns

Avoid using unrelated benchmarks from:
- crypto exchanges,
- retail trading desks,
- generic support-only call centers,
- mass-volume B2C telesales,
- gig-platform ranking systems,
- or high-scale enterprise environments that assume huge teams and massive process overhead.

### 7.3 Wrong-answer patterns

Recommendations are weak if they:
- optimize raw activity instead of revenue quality,
- ignore source difficulty,
- let subjective admin opinion dominate payroll,
- rely on perfect data quality from day one,
- require unrealistic implementation effort for a phased rollout,
- or create shame-driven competition instead of disciplined execution.

## 8. Mandatory context pack

The deep-research agent should use the uploaded final synthesis documents as its primary context pack inside the ChatGPT project.
Assume the files are available by **file name**, not by filesystem path.
When making recommendations, explicitly cite the exact file name that informed the conclusion.

Recommended reading order:

1. `00_INDEX.md`
2. `01_MASTER_SYNTHESIS.md`
3. `02_MOSAIC_SCORE_SYSTEM.md`
4. `03_PAYROLL_KPI_AND_PORTFOLIO.md`
5. `04_ANTI_DUPLICATION_AND_FOLLOWUP_ENGINE.md`
6. `05_IP_TELEPHONY_QA_AND_SUPERVISOR.md`
7. `06_UI_UX_AND_MANAGER_CONSOLE.md`
8. `07_IMPLEMENTATION_ROADMAP.md`
9. `10_SOURCE_MAP_AND_EXTERNAL_BEST_PRACTICES.md`
10. `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md`
11. `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`
12. `13_CROSS_SYSTEM_GUARDRAILS.md`

Quick meaning of each file:

- `00_INDEX.md`
  - entry point and reading order.
- `01_MASTER_SYNTHESIS.md`
  - why the final architecture looks the way it does.
- `02_MOSAIC_SCORE_SYSTEM.md`
  - score layers, formulas, gates, trust and comparative logic.
- `03_PAYROLL_KPI_AND_PORTFOLIO.md`
  - KPI, salary logic, meaningful contact, probation, portfolio ownership.
- `04_ANTI_DUPLICATION_AND_FOLLOWUP_ENGINE.md`
  - dedupe logic, merge rules, callback ladder, reminder model.
- `05_IP_TELEPHONY_QA_AND_SUPERVISOR.md`
  - telephony rollout, provider thinking, QA, calibration, retention.
- `06_UI_UX_AND_MANAGER_CONSOLE.md`
  - worklist logic, manager/admin UX, mobile-first constraints.
- `07_IMPLEMENTATION_ROADMAP.md`
  - rollout sequencing and practical implementation phases.
- `10_SOURCE_MAP_AND_EXTERNAL_BEST_PRACTICES.md`
  - already collected external anchor sources.
- `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md`
  - module-oriented backlog for implementation.
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`
  - all current baseline numbers in one place.
- `13_CROSS_SYSTEM_GUARDRAILS.md`
  - audit, security, backup, performance, and system-wide protections.

If the files are uploaded into a ChatGPT project, the agent should:
- search by exact file name,
- quote or reference file names directly,
- and avoid depending on local paths or repository structure.

## 9. How the agent must use the file context

The agent should not just answer the 5 questions abstractly.
It must compare external evidence with the current proposed architecture and say one of the following for each important point:

- `keep as is`,
- `tune upward`,
- `tune downward`,
- `replace`,
- `defer to later phase`.

If the agent recommends change, it must specify:
- what exact part of the current package changes,
- which file it affects,
- why the existing assumption is weak,
- and what better replacement looks like.

Whenever possible, the agent should point to the relevant file by name.
Use file names exactly as uploaded, for example:
- `02_MOSAIC_SCORE_SYSTEM.md`
- `03_PAYROLL_KPI_AND_PORTFOLIO.md`
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`

## 10. Required output format

The research result should be structured like this:

### 10.1 Executive synthesis

The agent must begin with:
- the top 10 practical findings for TwoComms,
- the 5 highest-impact changes worth making first,
- the 5 ideas that should be rejected or delayed,
- and the 3 biggest implementation risks.

### 10.2 Per-question response structure

For each research question, the agent must provide:
- a short executive summary,
- relevant benchmarks and ranges,
- 5-10 strong sources,
- what to implement now,
- what to defer,
- what is risky or overengineered for TwoComms,
- and a final plain-language recommendation.

### 10.3 Required style of recommendations

Recommendations must be:
- concrete,
- numerically specific where possible,
- contextual to a small B2B fashion wholesale sales team,
- realistic for staged rollout,
- and explainable to both admin and manager.

## 11. Five research questions

## 11.1 KPI thresholds and operating modes for small-team B2B fashion wholesale sales

Research in the context of:
- cold and warm lead mixes,
- small teams `3-7 managers`,
- seasonality,
- first-order vs repeat-order economics,
- and the risk of fake activity caused by badly chosen quotas.

Validate or challenge:
- the current `TESTING / NORMAL / HARDCORE` presets,
- the current concept of `meaningful contact`,
- weekly and monthly planning ranges,
- callback SLA expectations,
- report compliance expectations,
- and duplicate-abuse tolerance.

The answer should produce:
- recommended daily, weekly and monthly KPI ranges,
- mode-switch rules,
- seasonality modifiers,
- thresholds that are too harsh,
- thresholds that are too soft,
- and a final recommendation for the starting production presets.

Primary context files:
- `03_PAYROLL_KPI_AND_PORTFOLIO.md`
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`
- `01_MASTER_SYNTHESIS.md`

## 11.2 Comparative rating engine for TwoComms

Research which comparative system best fits:
- a small team,
- uneven source difficulty,
- absences and return after absence,
- small sample sizes,
- and the need for motivation without noise.

Compare:
- no public rating,
- private seasonal ladder,
- hybrid ladder,
- Glicko-2 style systems,
- and any stronger alternative for a small sales team.

The answer should produce:
- the recommended default comparative mode,
- the recommended advanced mode,
- switch criteria for when a more complex rating system becomes justified,
- formula or pseudo-formula candidates,
- and rules for combining daily score, micro-feedback and long-term standing.

Primary context files:
- `02_MOSAIC_SCORE_SYSTEM.md`
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`
- `06_UI_UX_AND_MANAGER_CONSOLE.md`

## 11.3 Call QA and calibration model that improves sales without becoming subjective surveillance

Research in the context of:
- outbound or semi-warm B2B selling,
- small-team supervisor review,
- explainable QA scoring,
- and payroll-safe boundaries.

Validate or challenge:
- how QA should affect coaching,
- how QA should affect trust,
- how QA should affect compensation,
- calibration frequency,
- reliability thresholds such as kappa or equivalent,
- and what supervisor tools are must-have vs optional.

The answer should produce:
- a practical QA rubric,
- scorecard categories and weights,
- calibration cadence,
- reliability thresholds,
- QA-to-coaching policy,
- QA-to-compensation limits,
- and short-call handling rules.

Primary context files:
- `05_IP_TELEPHONY_QA_AND_SUPERVISOR.md`
- `13_CROSS_SYSTEM_GUARDRAILS.md`
- `07_IMPLEMENTATION_ROADMAP.md`

## 11.4 Dedupe, merge and migration patterns for a CRM with lead parsing, batch import and telephony

Research in the context of:
- dirty historical data,
- partial identifiers,
- multiple lead origins,
- future telephony integration,
- and the need to avoid accidental merges.

Validate or challenge:
- exact matching rules,
- fuzzy thresholds,
- conflict resolution logic,
- batch import preview,
- merge rollback windows,
- and migration sequencing.

The answer should produce:
- recommended exact rules,
- recommended fuzzy thresholds,
- merge decision rules,
- rollback windows,
- migration checklist,
- operator review workflow,
- and safe defaults for v1 rollout.

Primary context files:
- `04_ANTI_DUPLICATION_AND_FOLLOWUP_ENGINE.md`
- `07_IMPLEMENTATION_ROADMAP.md`
- `13_CROSS_SYSTEM_GUARDRAILS.md`

## 11.5 Telephony architecture and reminder/coaching architecture for TwoComms

Research in the context of:
- Ukraine and comparable markets,
- supervisor listening and scoring,
- webhook maturity,
- recording economics,
- mobile admin workflow,
- alert fatigue,
- and staged adoption.

Validate or challenge:
- provider shortlist,
- provider comparison logic,
- recording retention periods,
- reminder ladder timing,
- notification channel split,
- and the order in which telephony should affect score and admin workflows.

The answer should produce:
- a provider shortlist,
- pricing bands if available,
- rollout phases,
- recording retention recommendation,
- reminder architecture,
- manager/admin notification policy,
- and the biggest operational risks.

Primary context files:
- `05_IP_TELEPHONY_QA_AND_SUPERVISOR.md`
- `04_ANTI_DUPLICATION_AND_FOLLOWUP_ENGINE.md`
- `06_UI_UX_AND_MANAGER_CONSOLE.md`

## 12. Final instruction to the deep-research agent

Research for the project that is actually being built here.
Do not answer as if this were a generic CRM article.
Do not optimize for vanity metrics.
Do not recommend systems that are elegant in theory but fragile in a small real sales team.

The best answer is the one that:
- improves manager productivity,
- improves reporting quality,
- improves repeat revenue and callback discipline,
- reduces duplicates and noisy reminders,
- keeps payroll fair,
- limits subjective human-factor damage,
- and stays implementable inside the staged TwoComms management roadmap.
