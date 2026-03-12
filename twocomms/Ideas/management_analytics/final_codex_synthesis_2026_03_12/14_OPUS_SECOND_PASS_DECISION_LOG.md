# Consolidated Decision Log

> Legacy filename retained for continuity with older synthesis packages.

## 1. Роль этого файла
Этот файл теперь фиксирует не только второй проход Opus, а итоговый consolidated decision log после мартовской ревизии.

Его задача:
- показать, что именно принято в authoritative core;
- отделить partial/shadow решения;
- явно зафиксировать, что отвергнуто и почему.

## 2. Принято в authoritative core

| Решение | Статус | Почему |
|---|---|---|
| `management commands + cron` | accepted | совместимо с current hosting |
| `FileBasedCache` | accepted | заменяет недоступный Redis-layer |
| `EWR` for Result | accepted | лучше учитывает cold B2B reality |
| MOSAIC `40/10/20/10/10/10` | accepted | безопаснее и стабильнее старых весов |
| `Component Readiness Registry` | accepted | снимает риск штрафа за DORMANT-компоненты |
| `Soft Floor Cap` | accepted | убирает destructive cliff |
| `MAX_FOLLOWUPS_PER_DAY` | accepted | учитывает физическую пропускную способность |
| `SourceFairness` confidence guards | accepted | защищает от low-sample noise |
| phase-aware DMT | accepted | без телефонии нельзя требовать telephony metrics |
| default portfolio thresholds `35/55/75` | accepted | безопаснее старых порогов |
| `ForceMajeureEvent` as source of truth | accepted | системное exemption-событие безопаснее, чем разрозненные ручные day-status overrides |
| `EWMA_LAMBDA_FLOOR = 0.05` | accepted | предотвращает freeze и соответствует hardened report лучше, чем старый draft `0.015` |

## 3. Принято частично

| Идея | Что принято | Что ограничено |
|---|---|---|
| Telephony truth layer | `CallRecord`, maturity gating, webhook prep | не участвует в production пока не ACTIVE |
| QA scoring | rubric, supervisor queue, calibration logic | не влияет на деньги без maturity |
| Bayesian / windowed trust | diagnostic admin layer | не используется как main production multiplier |
| Omni-touch | phase-appropriate proxy idea | не становится easy score exploit |
| Seasonality | архитектура и explicit DORMANT state | не включается в production до data maturity |

## 4. Оставлено в shadow / admin-only
- benchmarking and overlays;
- anti-gaming heuristics;
- trust diagnostic trend;
- velocity / consistency;
- telephony coaching signals;
- advanced supervisor analytics;
- score-to-money validation visuals.

## 5. Оставлено в backlog / later phase
- full telephony provider rollout;
- QA calibration and reliability measurement;
- validation suite;
- seasonality activation;
- advanced AI coaching;
- broader multi-manager ranking logic.

## 6. Явно отклонено

| Идея | Почему отклонена |
|---|---|
| hard dependency on `Redis` / `Celery` | не совместимо с реальным хостингом |
| `pg_trgm` as mandatory dedupe engine | не гарантированно доступен |
| direct punitive QA before calibration | слишком рискованно |
| public humiliating leaderboard | токсично для маленькой команды |
| auto-shark-pool / auto-reassign | риск злоупотреблений и разрушения доверия |
| cliff repeat penalty on full turnover | финансово деструктивно |
| DORMANT components as zero-weight punishment | наказывает за отсутствие системы |

## 7. Ключевые конфликты, которые решены этой версией
- `Result` old vs `EWR` -> final authoritative = `EWR`
- `Redis/Celery` vs shared hosting -> final authoritative = commands + cron + FileBasedCache
- old portfolio thresholds vs safer thresholds -> final authoritative = `35/55/75` default
- aggressive trust / QA coupling vs current reality -> final authoritative = bounded production trust + diagnostic trust
- old follow-up logic without capacity guard -> final authoritative = follow-up ladder with `MAX_FOLLOWUPS_PER_DAY`
- conflicting EWMA lambda drafts `0.015` vs `0.05` -> final authoritative = `0.05`

## 8. Как читать этот лог
- если идея находится в `accepted`, она должна считаться частью будущего implementation plan;
- если идея находится в `partial` или `shadow`, её нельзя автоматически делать production truth;
- если идея находится в `rejected`, возвращать её обратно можно только через новый явный decision cycle.
