# Traceability Matrix and Code Impact

## 1. Роль этого файла
Этот документ нужен, чтобы ни одна важная идея из мартовского синтеза не потерялась между:
- исходными отчётами;
- authoritative docs;
- будущими кодовыми изменениями.

## 2. Traceability matrix

| Тема | Ключевые источники | Куда встроено в пакете | Будущие кодовые зоны |
|---|---|---|---|
| Shared-hosting stack | `COMPREHENSIVE_REPORT` §28, §36.2; integration plan §2 | `00`, `07`, `10`, `13` | `settings.py`, `management/commands/` |
| `EWR` / new Result | `COMPREHENSIVE_REPORT` §35.3, §36.6; integration plan §1.6 | `02`, `12` | `stats_service.py`, snapshots |
| `Wilson` diagnostic KPI | `COMPREHENSIVE_REPORT` §35.4; integration plan control links | `02`, `12`, `15`, `11` | `stats_service.py`, nightly snapshots, admin analytics |
| MOSAIC weights `40/10/20/10/10/10` | `COMPREHENSIVE_REPORT` §35.7; integration plan §1.1 | `02`, `12`, `14` | score composer in `stats_service.py` |
| Production / diagnostic trust | `COMPREHENSIVE_REPORT` §19.1, §33.3, §37.2 | `02`, `12`, `14` | `stats_service.py`, admin analytics |
| Gate levels `100/78/60/45` | `COMPREHENSIVE_REPORT` §36.3 | `02`, `12` | score composer, admin explainability |
| Final dampener | `COMPREHENSIVE_REPORT` §36.3 | `02`, `12` | `stats_service.py` |
| Soft Floor Cap | `COMPREHENSIVE_REPORT` §37.3; integration plan §1.5 | `03`, `12`, `15` | payout math in `views.py` / models |
| Repeat vs reactivation `180-day` split | `COMPREHENSIVE_REPORT` §34.6.D6 | `03`, `12`, `07`, `11` | payout math, client history logic |
| Commission dispute workflow | baseline package `03` / `11`; historical payroll carry-forward | `03`, `07`, `11` | payout review flow, accrual disputes, admin queue |
| Optional weighted attribution for complex disputes | baseline package `03`; historical payroll carry-forward | `03`, `07` | admin-only exception flow, evidence-backed payout adjustment |
| `Weibull` churn + logistic fallback + `k` cap | `COMPREHENSIVE_REPORT` §37.1; integration plan §1.3, §12.10 | `02`, `03`, `07`, `11`, `12`, `19` | `stats_service.py`, snapshots, portfolio payload |
| Portfolio thresholds `35/55/75` | `COMPREHENSIVE_REPORT` §35.10; integration plan §11.3 | `03`, `12` | `Client`, stats payload |
| `is_test` guard | `COMPREHENSIVE_REPORT` §30.2, §34.4 | `03`, `07`, `11`, `19` | `Client`, stats queries |
| Dedupe without `pg_trgm` | `COMPREHENSIVE_REPORT` §30.5, §33.6, §36.2; integration plan §2.3 | `04`, `07`, `11`, `13` | `lead_views.py`, `parsing_views.py`, `views.py` |
| Batch Import Dry-Run | `COMPREHENSIVE_REPORT` §34.5.D5; integration plan §7.1 | `04`, `07`, `11`, `19` | `LeadParsingJob`, `LeadParsingResult`, parsing views |
| Merge rollback / master-record rule | `COMPREHENSIVE_REPORT` improvements §14-§18 | `04`, `11`, `13`, `19` | duplicate dispute model / merge audit layer |
| `MAX_FOLLOWUPS_PER_DAY` | `COMPREHENSIVE_REPORT` §36.9 | `04`, `12`, `14` | `ClientFollowUp`, reminder logic |
| FileBasedCache rate limiting | `COMPREHENSIVE_REPORT` §33.9; Django docs via Context7 | `04`, `07`, `10`, `13` | `settings.py`, service/helper layer |
| `CallRecord` prep | `COMPREHENSIVE_REPORT` §30.3, §37.7 | `05`, `07`, `11`, `19` | `models.py`, webhook views |
| QA maturity gating | `COMPREHENSIVE_REPORT` §5, §37.2 | `05`, `14` | future QA models and views |
| Call Competency Profile | legacy telephony package `05`; historical carry-forward | `05`, `07`, `11` | QA review payloads, supervisor/admin surfaces |
| QA reliability thresholds / recording retention | legacy telephony package `05`; audit hardening | `05`, `07`, `11` | QA calibration flow, retention metadata, supervisor audit logs |
| Radar chart | `COMPREHENSIVE_REPORT` §31 | `06`, `11`, `19` | `stats.html`, JS/CSS |
| Client communication timeline | legacy UI package `06`; historical carry-forward | `06`, `07`, `11`, `19` | `stats.html`, client detail payloads, interaction timeline builder |
| Mobile-first manager shell | legacy UI package `06`; historical carry-forward | `06`, `07`, `11`, `19` | `base.html`, `stats.html`, mobile-safe JS flows |
| Clickable waterfall / explainable score card | `COMPREHENSIVE_REPORT` §12.3 | `06`, `07`, `15` | `stats.html`, admin panels, simulator surfaces |
| Rescue top-5 / `Expected LTV Loss` | `COMPREHENSIVE_REPORT` §37.5 | `03`, `06`, `07`, `11`, `12` | stats payload + manager UI |
| Rescue `SPIFF` + `max 3/day` capacity guard | `COMPREHENSIVE_REPORT` §37.5; integration plan §3.6 | `03`, `06`, `07`, `11`, `12` | payout attribution, rescue widget, admin payout review |
| Salary simulator / what-if | `COMPREHENSIVE_REPORT` §6.3, §21.4 | `03`, `06`, `11` | stats/admin templates |
| Shadow hold-harmless | `COMPREHENSIVE_REPORT` §14, rollout notes | `03`, `06`, `07` | salary simulator + shadow rollout |
| Score confidence labels | `COMPREHENSIVE_REPORT` improvement 20 | `06`, `12`, `15` | snapshots, admin views |
| Validation protocol | `COMPREHENSIVE_REPORT` §13, §33, §36 | `07`, `12`, `15` | commands, admin analytics |
| Break-even / payback / forecast admin economics | legacy admin economics package `15`; historical carry-forward | `06`, `11`, `15`, `19` | admin analytics payloads, payout/admin surfaces |
| Day status / Earned Day | `COMPREHENSIVE_REPORT` §33.4, §34.4, §36.5 | `03`, `12`, `15` | models, payout/admin logic |
| Force Majeure / Red Card | `COMPREHENSIVE_REPORT` §37.6, §37.2 | `03`, `07`, `11`, `13`, `15`, `19` | admin controls, status models, exemption event layer |
| Nightly snapshots | `COMPREHENSIVE_REPORT` §37.7 | `07`, `11`, `15`, `19` | commands + models |
| DICE rollout guardrails | `COMPREHENSIVE_REPORT` §12.1 | `06`, `07`, `21` | rollout reviews, simulator enablement, change-management checklists |
| Optional DTF read-only bridge | legacy package `07` / `11`; historical carry-forward | `07`, `11`, `19`, `22` | optional `dtf` adapter, separate read-only cards/routes |

## 3. Ничего не потерять: правило использования
- если идея есть в большом отчёте, но не попала в эту таблицу, она либо сознательно отклонена, либо ещё не привязана к authoritative docs;
- если идея есть в authoritative doc, но здесь нет code-impact зоны, implementation planning для неё ещё не завершён;
- если идея есть и тут, и в code-impact map, она считается fully staged for planning.

## 4. Самые чувствительные темы

### 4.1 Деньги
Деньги завязаны на:
- `03_PAYROLL_KPI_AND_PORTFOLIO.md`
- `15_ADMIN_ECONOMICS_AND_EARNED_DAY.md`

Любые implementation changes вокруг этих тем должны идти только после повторной сверки с `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`.

### 4.2 Формулы
Формулы завязаны на:
- `02_MOSAIC_SCORE_SYSTEM.md`
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`
- `14_OPUS_SECOND_PASS_DECISION_LOG.md`

### 4.3 Инфраструктура
Инфраструктурные допущения завязаны на:
- `07_IMPLEMENTATION_ROADMAP.md`
- `10_SOURCE_MAP_AND_EXTERNAL_BEST_PRACTICES.md`
- `13_CROSS_SYSTEM_GUARDRAILS.md`

## 5. Что использовать на следующем этапе
Для построения детального implementation plan в первую очередь опираться на:
1. `07_IMPLEMENTATION_ROADMAP.md`
2. этот traceability matrix
3. `19_MANAGEMENT_CODEBASE_ALIGNMENT_MAP.md`
4. `02`, `03`, `04`, `12`, `13`, `15`
