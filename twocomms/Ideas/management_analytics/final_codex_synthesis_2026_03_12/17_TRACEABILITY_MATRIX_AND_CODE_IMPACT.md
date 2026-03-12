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
| MOSAIC weights `40/10/20/10/10/10` | `COMPREHENSIVE_REPORT` §35.7; integration plan §1.1 | `02`, `12`, `14` | score composer in `stats_service.py` |
| Production / diagnostic trust | `COMPREHENSIVE_REPORT` §19.1, §33.3, §37.2 | `02`, `12`, `14` | `stats_service.py`, admin analytics |
| Gate levels `100/78/60/45` | `COMPREHENSIVE_REPORT` §36.3 | `02`, `12` | score composer, admin explainability |
| Final dampener | `COMPREHENSIVE_REPORT` §36.3 | `02`, `12` | `stats_service.py` |
| Soft Floor Cap | `COMPREHENSIVE_REPORT` §37.3; integration plan §1.5 | `03`, `12`, `15` | payout math in `views.py` / models |
| Portfolio thresholds `35/55/75` | `COMPREHENSIVE_REPORT` §35.10; integration plan §11.3 | `03`, `12` | `Client`, stats payload |
| `is_test` guard | `COMPREHENSIVE_REPORT` §30.2, §34.4 | `03`, `07`, `11`, `19` | `Client`, stats queries |
| Dedupe without `pg_trgm` | `COMPREHENSIVE_REPORT` §30.5, §33.6, §36.2; integration plan §2.3 | `04`, `07`, `11`, `13` | `lead_views.py`, `parsing_views.py`, `views.py` |
| `MAX_FOLLOWUPS_PER_DAY` | `COMPREHENSIVE_REPORT` §36.9 | `04`, `12`, `14` | `ClientFollowUp`, reminder logic |
| FileBasedCache rate limiting | `COMPREHENSIVE_REPORT` §33.9; Django docs via Context7 | `04`, `07`, `10`, `13` | `settings.py`, service/helper layer |
| `CallRecord` prep | `COMPREHENSIVE_REPORT` §30.3, §37.7 | `05`, `07`, `11`, `19` | `models.py`, webhook views |
| QA maturity gating | `COMPREHENSIVE_REPORT` §5, §37.2 | `05`, `14` | future QA models and views |
| Radar chart | `COMPREHENSIVE_REPORT` §31 | `06`, `11`, `19` | `stats.html`, JS/CSS |
| Salary simulator / what-if | `COMPREHENSIVE_REPORT` §6.3, §21.4 | `03`, `06`, `11` | stats/admin templates |
| Rescue top-5 / SPIFF | `COMPREHENSIVE_REPORT` §37.5 | `06`, `11` | stats payload + manager UI |
| Day status / Earned Day | `COMPREHENSIVE_REPORT` §33.4, §34.4, §36.5 | `03`, `12`, `15` | models, payout/admin logic |
| Force Majeure / Red Card | `COMPREHENSIVE_REPORT` §37.6, §37.2 | `03`, `13`, `15` | admin controls, status models |
| Nightly snapshots | `COMPREHENSIVE_REPORT` §37.7 | `07`, `11`, `15`, `19` | commands + models |

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
