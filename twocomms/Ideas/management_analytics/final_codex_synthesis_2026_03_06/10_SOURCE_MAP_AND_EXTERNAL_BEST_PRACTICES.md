# Source Map and External Best Practices

## 1. Зачем этот файл

Ниже перечислены внешние источники, которые реально повлияли на финальные решения, а не просто были прочитаны “для красоты”.

## 2. CRM duplicate management

### Salesforce
Источник:
- https://help.salesforce.com/s/articleView?id=platform.matching_rules_about.htm&type=5
- https://help.salesforce.com/s/articleView?id=platform.duplicate_rules.htm&type=5

Что подтверждает:
- duplicate prevention нельзя делать только одной уникальностью по полю,
- нужны matching rules,
- нужны separate duplicate rules,
- нужны action policies до и после сохранения.

Как использовано:
- exact/likely/conflict duplicate model,
- create-or-append flow,
- admin duplicate review queue.

### HubSpot
Источник:
- https://knowledge.hubspot.com/records/merge-records
- https://knowledge.hubspot.com/records/manage-duplicate-records

Что подтверждает:
- merge/review workflows должны быть отдельным управленческим контуром,
- dedupe требует ручного review на спорных совпадениях.

Как использовано:
- identity graph + review queues,
- отказ от попытки “всё решить одним unique”.

## 3. Dashboard and actionability

### Salesforce dashboard guidance
Источник:
- https://www.salesforce.com/ap/blog/sales-dashboard/

Что подтверждает:
- dashboard должен быть action-oriented,
- ключевые показатели должны вести к решению, а не просто к наблюдению.

Как использовано:
- manager action stack,
- admin action center,
- prioritization of actionable blocks over decorative charts.

## 4. Call monitoring and supervisor mode

### RingCentral
Источник:
- https://www.ringcentral.com/au/en/blog/definitions/call-monitoring/
- https://www.ringcentral.com/au/en/blog/whisper-barge-monitor/
- https://www.ringcentral.com/content/dam/rc-www/en_us/documents/office/admin-guide.pdf

Что подтверждает:
- monitor/whisper/barge это стандартный supervisor contour,
- live supervision и review должны быть встроены в операционную модель.

Как использовано:
- отдельный QA/Supervisor console,
- SupervisorActionLog,
- phase-2 telephony roadmap.

## 5. Quality management and calibration

### NICE
Источник:
- https://help.nice-incontact.com/content/qmanalytics/calibrations/calibrations.htm
- https://help.nice-incontact.com/content/qmanalytics/plan/qualityplans/aboutqualityplans.htm

Что подтверждает:
- QA без calibration неустойчив,
- scorecards и calibration должны быть процессом, а не разовой оценкой.

Как использовано:
- TelephonyQACalibrationSession,
- weekly calibration cadence,
- QA variance review.

## 6. Gamification and performance motivation

### Genesys
Источник:
- https://www.genesys.com/en-sg/blog/post/gamification-101-how-games-can-help-improve-agent-performance

Что подтверждает:
- gamification полезна, когда она усиливает performance coaching,
- но она должна быть безопасной, ясной и не разрушать культуру.

Как использовано:
- сохраняем `salary simulator`, `golden hour`, `shadow rival`,
- убираем токсичные версии `Shark Pool` и `Doomsday Screen`.

## 7. Lead management and follow-up discipline

### HubSpot tasks and sequences
Источник:
- https://knowledge.hubspot.com/tasks/use-tasks
- https://knowledge.hubspot.com/sequences/use-sequences

Что подтверждает:
- follow-up должен быть task-driven,
- work queue и sequence logic важнее, чем просто список напоминаний.

Как использовано:
- Today Action Stack,
- reminder ladder,
- queue-first manager interface.

## 8. Django implementation guidance

### Django official constraints docs
Источник:
- https://github.com/django/django/blob/5.2.6/docs/ref/models/constraints.txt

Что подтверждает:
- `UniqueConstraint`,
- conditional uniqueness,
- expression-based constraints.

Как использовано:
- identity keys,
- partial uniqueness,
- controlled duplicate-prevention schema.

## 9. Celery periodic jobs and overlap safety

### Celery official docs
Источник:
- https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html
- https://docs.celeryq.dev/en/stable/tutorials/task-cookbook.html

Что подтверждает:
- должен быть только один scheduler,
- periodic tasks могут overlap,
- нужен locking pattern и idempotency.

Как использовано:
- один active beat,
- overlap-sensitive jobs under lock,
- dedupe key design for reminders,
- idempotent finalization and scans.

## 10. Итог

Внешние источники не заменили агентские идеи.
Они сделали две вещи:
- подтвердили, какие решения стоит оставить,
- подсветили, где красивые идеи надо приземлить в безопасный operating model.

## 11. Academic anchors used for decision quality

Ниже не “абсолютная истина”, а исследовательские опоры, которые полезны для проверки логики решений:
- `Brown, 1956` — exponential smoothing,
- `Wilson, 1927` — confidence interval for small samples,
- `Bernardo & Smith, 2000` — Bayesian updating,
- `Bullen, 2003` — bounded treatment of unbalanced composite dimensions,
- `Kahneman & Tversky, 1979` — loss aversion,
- `Yerkes-Dodson, 1908` — excessive stress hurts performance,
- `Locke & Latham, 2002` — specific goals improve results,
- `Csikszentmihalyi, 1990` — immediate feedback supports flow,
- `Hamari et al., 2014` — gamification can improve engagement,
- `Thaler, 1980` — endowment effect,
- `Reichheld / Bain, 2003` — retention and profit relationship,
- `Ribeiro et al., 2016` — explainability improves trust,
- `Deming, 1982` — punitive quality regimes corrupt reporting.

Как это использовано:
- exponential smoothing → EWMA for rolling MOSAIC and trend analytics,
- Wilson + Bayesian ideas → low-sample protection and shadow recalibration for `SourceFairness`,
- bounded composite logic → discipline floor dampener instead of raw over-penalization,
- loss aversion → portfolio health and orphan logic,
- goal setting → presets and KPI numbers,
- flow → micro-feedback layer,
- gamification → seasonal ladder and safe UI rewards,
- explainability → mandatory score breakdown,
- anti-punitive quality stance → QA affects coaching and trust, not instant blind punishment.
