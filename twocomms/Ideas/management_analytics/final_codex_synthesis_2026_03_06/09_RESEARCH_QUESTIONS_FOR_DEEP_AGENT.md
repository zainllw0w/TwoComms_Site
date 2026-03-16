# Бриф для Deep Research по TwoComms Management

## 1. Назначение этого файла

Этот файл предназначен для другого ИИ-агента, который будет проводить глубокое исследование по интернету, статьям, документации, CRM-практикам, call QA, sales operations и похожим системам.

Его задача не в том, чтобы написать абстрактный обзор по CRM.
Его задача в том, чтобы исследовать **улучшения именно для проекта TwoComms Management** и вернуть выводы в контексте уже подготовленной архитектуры, формул и планируемых систем из этого пакета.

Ответ от deep-research агента должен быть **полностью на русском языке**.

## 2. Что это за проект

`TwoComms Management` это management subdomain для **небольшой B2B wholesale-команды**.

Это не:
- криптобиржа,
- трейдинг-платформа,
- retail support desk,
- массовый B2C колл-центр,
- и не generic enterprise CRM на сотни операторов.

Это ближе всего к следующему контексту:
- small-team outbound и semi-warm B2B sales,
- fashion wholesale и подключение магазинов,
- работа с холодными, тёплыми и горячими источниками,
- повторные заказы и удержание клиентского портфеля,
- перезвоны и follow-up дисциплина,
- KPI и зарплата менеджеров,
- контроль качества работы,
- admin supervision,
- explainable analytics,
- поэтапное внедрение IP-телефонии с прослушкой и оценкой звонков.

Ключевая цель проекта:
- повысить реальную продуктивность менеджеров,
- повысить качество конверсии,
- улучшить повторные продажи,
- уменьшить дубли,
- уменьшить пустую активность,
- сделать отчётность прозрачной,
- сделать зарплату и KPI понятными,
- внедрить evidence-based советы и админский контроль без токсичности.

## 3. Операционная модель бизнеса

Deep-research агент должен мыслить в следующей модели:

1. Менеджеры работают с магазинами и лидами, а не с анонимными розничными пользователями.
2. Источники лидов сильно отличаются по сложности:
- `cold_xml`,
- `parser_cold`,
- `manual_hunt`,
- `warm_reactivation`,
- `hot_inbound`.
3. Менеджер может создавать разные типы результата:
- первый оплаченный заказ,
- повторный оплаченный заказ,
- корректный follow-up,
- перезвон,
- качественную заметку,
- корректную причину отказа,
- восстановление клиента из риска,
- и позже подтверждённые telephony-события.
4. Система должна различать:
- verified business outcomes,
- self-reported activity,
- admin-reviewed quality,
- и шумные сигналы, которые нельзя делать основной правдой для зарплаты.
5. Текущий и планируемый размер команды ближе к `3-7 менеджерам`, а не к крупному call-center масштабу.
6. В нише есть сезонность, коллекции, просадки и волны спроса.
7. Система должна поддерживать одновременно:
- `new business`,
- `portfolio retention`,
- `repeat orders`,
- `execution discipline`,
- и `call quality`.

## 4. Что именно строится

Финальная система в этом пакете это не новая CRM с нуля, а развитие уже существующего management-контура.

Планируемые слои:

1. `MOSAIC score`
- справедливый score эффективности,
- с учётом сложности базы,
- с защитой от фейковой активности,
- с разделением verified и self-reported сигналов.

2. `KPI и payroll engine`
- KPI режимы,
- probation,
- зарплатная логика,
- процент с первого и повторного заказа,
- проверка базовых требований,
- оценка здоровья портфеля.

3. `Anti-duplication и follow-up engine`
- exact/fuzzy dedupe,
- merge rules,
- import preview,
- reminder ladder,
- overdue escalation,
- callback discipline.

4. `IP telephony и QA contour`
- записи звонков,
- прослушка админом,
- ручная оценка звонка,
- калибровка оценщиков,
- supervisor statistics,
- ограничения влияния субъективного фактора.

5. `Manager/Admin интерфейсы`
- action-first worklist,
- explainable score,
- admin queues,
- mobile-first сценарии,
- low-noise reminders,
- осмысленные дашборды.

6. `Implementation roadmap и guardrails`
- staged rollout,
- audit log,
- security,
- backup,
- performance budgets,
- защита от ошибок миграции и злоупотреблений.

## 4.1 Что уже существует в проекте

Исследование должно исходить из того, что проект уже имеет реальные сущности и сигналы, а не стартует с нуля.

Известные доменные объекты и события:
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

Это означает, что рекомендации должны быть совместимы с системой, где:
- лиды, магазины, follow-up и коммуникации уже существуют,
- reminders уже частично существуют,
- комиссии и payout requests уже существуют,
- аналитика должна наслаиваться на текущую модель, а не переписывать всё как будто ничего нет.

## 5. Неподвижные принципы и инварианты

Deep-research агент может спорить с цифрами и thresholds, но не должен ломать эти принципы без очень сильной аргументации.

### 5.1 Иерархия истины

- Verified outcomes важнее, чем self-reported activity.
- Менеджер не должен получать высокий score только за объём действий.
- Сложность источника не должна автоматически ломать справедливость оценки.

### 5.2 Финансовое ядро

- `2.5%` за первый заказ и `5%` за повторный заказ это текущая финансовая основа.
- Если предлагать замену, то только с очень сильным бизнес-обоснованием.
- Зарплатная логика должна оставаться объяснимой и для админа, и для менеджера.

### 5.3 Жёсткий verified-сигнал

- `магазин добавлен = уже оплатил` считается сильным подтверждённым бизнес-событием.

### 5.4 Поведенческий принцип

- Система должна усиливать реальную дисциплину продаж, а не создавать фиктивную активность.
- Нельзя строить механику, которая заставляет менеджеров спамить, кликать ради score или подгонять отчёты.

### 5.5 Организационный принцип

- `manager view` и `admin view` должны оставаться разделёнными.
- Унижающие публичные рейтинги не являются дефолтной моделью.
- Субъективное мнение администратора не должно напрямую ломать зарплату без ограничений и проверки.

### 5.6 Технический принцип

- Рекомендации должны быть реалистичны для Django + Celery + Redis подобного management-стека.
- Нельзя строить предложения, которым нужен идеальный data warehouse и идеальная чистота данных с первого дня.

### 5.7 Граница продукта

- Management analytics для wholesale-менеджеров не должны смешиваться с чужими продуктовыми контурами.
- `DTF` и другие домены нельзя складывать в одну общую performance truth для этой management-системы.

## 6. Стартовые числа, которые нужно проверить, подтвердить, скорректировать или заменить

Ниже не "истина", а текущие стартовые параметры из финального пакета.
Deep-research агент должен оценить, насколько они адекватны именно для small-team B2B fashion wholesale.

### 6.1 Текущая базовая формула дневного score

Текущая authoritative-формула:

`0.40 Result + 0.15 SourceFairness + 0.15 Process + 0.10 FollowUp + 0.10 DataQuality + 0.10 VerifiedCommunication`

### 6.2 Текущие baseline по сложности источников

Стартовые ориентиры:
- `cold_xml = 1.5%`
- `parser_cold = 3%`
- `manual_hunt = 6%`
- `warm_reactivation = 18%`
- `hot_inbound = 30%`

Текущая политика пересмотра:
- quarterly review,
- bounded adjustment,
- cap по умолчанию `+/-25%` за цикл пересмотра.

### 6.3 Текущие gate thresholds

Стартовые ориентиры:
- `100` если есть paid order,
- `78` если есть strong pipeline proof,
- `60` если есть verified communication и дисциплина выполнения,
- `45` если спустя `3+` рабочих дня есть только lower-grade progress.

### 6.4 Текущие KPI-режимы

`TESTING`
- `20` meaningful contacts в день,
- `1` новый оплаченный заказ в неделю,
- `80%` callback SLA,
- `85%` report compliance,
- duplicate abuse `<5%`

`NORMAL`
- `35` meaningful contacts в день,
- `2` новых оплаченных заказа в неделю,
- `85%` callback SLA,
- `90%` report compliance,
- duplicate abuse `<3%`

`HARDCORE`
- `50` meaningful contacts в день,
- `3` новых оплаченных заказа в неделю,
- `90%` callback SLA,
- `95%` report compliance,
- duplicate abuse `<2%`

### 6.5 Текущие maturity caps для коммуникации

`VerifiedCommunication` сейчас ограничен так:
- `manual_only = 60`
- `soft_launch = 80`
- `supervised = 100`

### 6.6 Текущая логика по здоровью портфеля

Стартовые интервалы:
- `Healthy = 0-21 дней`
- `Watch = 22-35 дней`
- `Risk = 36-45 дней`
- `Rescue = 46-60 дней`
- `Reassign Eligible = 61+ дней`

### 6.7 Текущая философия micro-feedback

Micro-feedback допустим только как ограниченный вторичный слой.
Он не должен становиться главной правдой для payroll или KPI.

### 6.8 Ключевые формулы и правила, которые нужно валидировать

Deep-research агент не должен ограничиваться словами вроде “сделайте более справедливую формулу”.
Нужно проверять и при необходимости критиковать конкретные формулы и bounded-rules из текущего пакета.

Ключевые формулы и правила:

1. Базовая authoritative-формула дня:
`base_day = 0.40 * Result + 0.15 * SourceFairness + 0.15 * Process + 0.10 * FollowUp + 0.10 * DataQuality + 0.10 * VerifiedCommunication`

2. Revenue-aware часть:
`weighted_revenue_score = min(100, 100 * sqrt(revenue_period / revenue_target_period))`

3. Confidence-blending для малого sample в `SourceFairness`:
`sf_effective = 50 * (1 - confidence) + sf_raw * confidence`

4. Bayesian shadow recalibration для source baselines:
- rolling `90d`,
- weekly shadow estimate,
- monthly soft move `±10%`,
- quarterly hard cap `±25%`.

5. Trust formula:
`trust = clamp(0.70, 1.10, 0.78 + 0.16*verified_ratio + 0.08*qa_reliability + 0.04*reason_quality + 0.04*report_integrity - 0.06*duplicate_abuse - 0.06*anomaly_penalty)`

6. Discipline floor dampener:
- operational axes only,
- floor `20`,
- rolling `10 business days`,
- `-5%` per failed axis,
- max `-15%`.

7. Финальная manager-формула:
`manager_score_day = min(base_day * discipline_floor_dampener, gate_cap) * trust + portfolio_bonus`

8. Priority formula для `Today Action Stack`:
`priority = 0.30 * pipeline_value + 0.25 * portfolio_urgency + 0.15 * response_probability + 0.15 * overdue_urgency + 0.10 * churn_risk + 0.05 * response_latency_urgency`

9. Churn risk operational signal:
`churn_signal = (days_since_last_order - avg_order_interval) / max(1, avg_order_interval)`

10. Admin economics validation rules:
- `rolling MOSAIC ↔ attributed revenue`,
- `r² < 0.30` = recalibration needed,
- `0.30..0.49` = medium validity,
- `>= 0.50` = strong enough.

11. `Earned Day` / `DMT` safe policy:
- `>= 5` verified meaningful contacts,
- callback completion or clean reschedule `>= 80%`,
- `0` critical abuse flags,
- CRM day not empty,
- no critical fake-activity evidence.

Если deep-research агент предлагает замену любой из этих формул, он должен:
- показать новую формулу полностью,
- объяснить, почему старая слабее,
- описать risk of abuse,
- указать expected business effect,
- и написать, в какой файл это изменение должно лечь.

### 6.9 Какие integration points агент обязан учитывать

Нужно исследовать не только “какая формула лучше”, но и как она встроится в систему.

Deep-research агент обязан учитывать следующие integration touchpoints:

1. `Data / models`
- существующие management entities,
- snapshot tables,
- identity / duplicate review objects,
- telephony entities,
- payroll and payout entities.

2. `Services / jobs`
- daily score calculation,
- rolling recalculation,
- reminder scheduler,
- dedupe pre-check,
- telephony ingest,
- QA calibration checks,
- admin economics aggregation.

3. `UI surfaces`
- manager home,
- Today Action Stack,
- admin action center,
- payroll / economics screen,
- QA console,
- client timeline,
- manager advisory cards.

4. `External integrations`
- IP telephony providers,
- email/CP logs,
- possible Telegram notifications,
- import pipelines,
- future transcription / AI assist layer.

5. `Operational guardrails`
- audit log,
- rate-limiting / webhook verification,
- rollback windows,
- backup and restore,
- feature flags / shadow mode,
- policy/legal review for salary-affecting mechanics.

## 7. Ограничения области исследования

### 7.1 Что исследовать в первую очередь

Искать похожие практики и доказательства в контексте:
- B2B sales operations,
- small-team CRM,
- outbound/semi-warm sales,
- callback management,
- telephony supervision,
- duplicate management,
- repeat-order мотивации,
- explainable score systems,
- call QA,
- motivation design,
- measurement reliability,
- performance management,
- alert fatigue,
- admin oversight without abuse.

### 7.2 Что не брать как основную опору

Не делать главной базой:
- криптобиржи,
- retail trading,
- support-only колл-центры,
- массовый B2C telesales,
- gig-platform rating systems,
- huge enterprise процессы, рассчитанные на сотни людей и отдельные департаменты аналитики.

### 7.3 Какие ответы будут считаться плохими

Плохой ответ это тот, который:
- оптимизирует raw activity вместо качества и revenue,
- игнорирует сложность источника,
- слишком усиливает субъективный человеческий фактор,
- требует нереалистичного внедрения,
- не привязан к уже существующим файлам и формулам,
- или предлагает красивую теорию, которая развалится в маленькой команде.

## 8. Обязательный context pack для исследования

Эти файлы будут загружены в ChatGPT Project.
Исходи из того, что ты можешь искать их **по имени файла**, а не по пути.

При анализе и рекомендациях нужно **ссылаться на точные имена файлов**.

Рекомендуемый порядок чтения:

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
13. `14_OPUS_SECOND_PASS_DECISION_LOG.md`
14. `15_ADMIN_ECONOMICS_AND_EARNED_DAY.md`

Краткая роль каждого файла:

- `00_INDEX.md`
  - точка входа и порядок чтения.
- `01_MASTER_SYNTHESIS.md`
  - почему финальная архитектура выбрана именно такой.
- `02_MOSAIC_SCORE_SYSTEM.md`
  - score layers, formula, gate logic, trust, explainability.
- `03_PAYROLL_KPI_AND_PORTFOLIO.md`
  - KPI, payroll, probation, meaningful contact, portfolio rules.
- `04_ANTI_DUPLICATION_AND_FOLLOWUP_ENGINE.md`
  - dedupe, merge, callback ladder, reminder logic.
- `05_IP_TELEPHONY_QA_AND_SUPERVISOR.md`
  - telephony rollout, QA, calibration, supervisor actions.
- `06_UI_UX_AND_MANAGER_CONSOLE.md`
  - manager/admin UX и mobile-first сценарии.
- `07_IMPLEMENTATION_ROADMAP.md`
  - фазы внедрения и practical rollout.
- `10_SOURCE_MAP_AND_EXTERNAL_BEST_PRACTICES.md`
  - уже собранные внешние опоры и источники.
- `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md`
  - модульный backlog для внедрения.
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`
  - единое место со стартовыми цифрами и thresholds.
- `13_CROSS_SYSTEM_GUARDRAILS.md`
  - audit/security/backup/performance guardrails.
- `14_OPUS_SECOND_PASS_DECISION_LOG.md`
  - что принято, ограничено, переведено в shadow layer или отвергнуто после второго прохода Opus.
- `15_ADMIN_ECONOMICS_AND_EARNED_DAY.md`
  - admin economics analytics, score-to-money validation и safe variant системы `Earned Day`.

## 9. Как deep-research агент должен использовать контекст файлов

Нельзя отвечать на вопросы абстрактно.
Нужно сопоставлять внешние данные с текущей архитектурой и для каждого важного вывода писать один из вариантов:

- `оставить как есть`,
- `поднять`,
- `снизить`,
- `заменить`,
- `отложить на следующую фазу`.

Если предлагается изменение, нужно обязательно указать:
- что именно меняется,
- в каком файле это затрагивается,
- почему текущая версия слабая или рискованная,
- и какая замена лучше.

Если речь идёт о формуле, нужно обязательно указать:
- полную старую формулу или правило,
- полную новую формулу или правило,
- bounded impact,
- и integration impact.

Ссылаться нужно по имени файла, например:
- `02_MOSAIC_SCORE_SYSTEM.md`
- `03_PAYROLL_KPI_AND_PORTFOLIO.md`
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`

## 10. Формат ответа, который должен вернуть deep-research агент

Ответ должен быть **полностью на русском языке**.

### 10.1 Executive synthesis

В начале ответа обязательно дать:
- 10 главных выводов для TwoComms,
- 5 самых ценных изменений, которые стоит внедрять раньше всего,
- 5 идей, которые лучше отклонить или отложить,
- 3 самых опасных риска внедрения.

### 10.2 Формат по каждому вопросу

По каждому вопросу обязательно вернуть:
- короткий executive summary,
- benchmark numbers или диапазоны,
- 5-10 сильных источников,
- что внедрять сейчас,
- что отложить,
- что выглядит рискованным или overengineered,
- финальную рекомендацию простым языком,
- блок `что менять в каких файлах`,
- и блок `integration impact`.

В `integration impact` обязательно перечислять:
- какие модели или сущности затрагиваются,
- какие jobs/services нужны,
- какие UI-экраны меняются,
- какие внешние интеграции затронуты,
- и в какую фазу roadmap это лучше ставить.

### 10.3 Стиль рекомендаций

Рекомендации должны быть:
- конкретными,
- по возможности численно определёнными,
- реалистичными для phased rollout,
- привязанными к маленькой B2B wholesale-команде,
- и объяснимыми для менеджера и админа.

## 11. Приоритетность исследования

Не все вопросы одинаково важны.
Приоритет исследования должен быть таким:

1. `KPI / payroll / source of truth`
2. `Explainable advice / next-best-action / coaching engine`
3. `Call QA / calibration / supervisor control`
4. `Dedupe / merge / migration safety`
5. `Telephony / reminders / notification architecture`

Если какие-то выводы по более поздним вопросам влияют на более ранние, это нужно явно отметить.

## 12. Пять исследовательских вопросов

## 12.1 Какие KPI, probation-правила и payroll guardrails лучше всего подходят small-team B2B fashion wholesale sales

Нужно исследовать в контексте:
- холодных и тёплых лидов,
- маленькой команды `3-7 менеджеров`,
- сезонности,
- первого и повторного заказа,
- риска фиктивной активности из-за неудачных квот.

Нужно проверить или оспорить:
- текущие `TESTING / NORMAL / HARDCORE` режимы,
- текущие требования к `meaningful contact`,
- weekly/monthly ranges,
- callback SLA,
- report compliance,
- duplicate abuse thresholds,
- dual probation,
- `EWMA` vs simple rolling average,
- low-sample protection и confidence intervals,
- Bayesian shadow recalibration для source baselines,
- bounded long-cycle persistence credit,
- `Earned Day` / `DMT` как policy-safe payroll contour,
- break-even / payback / contribution proxy для admin analytics,
- границу между `commission truth` и `diagnostic signals`,
- и то, как KPI должны влиять на зарплату и последствия.

Нужно получить:
- рекомендуемые daily/weekly/monthly ranges,
- rules для переключения режимов,
- seasonality modifiers,
- рекомендации по temporal weighting для rolling KPI,
- рекомендации по min sample rules и confidence-blending,
- рекомендации по bounded source recalibration,
- рекомендации по policy-safe версии `Earned Day`,
- рекомендации по тому, какие economics метрики должны видеть только админ,
- что слишком жёстко,
- что слишком мягко,
- как лучше разделить `base requirements`, `KPI`, `payroll truth`, `discipline`,
- и финальную рекомендацию для production presets.

Основные файлы контекста:
- `03_PAYROLL_KPI_AND_PORTFOLIO.md`
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`
- `01_MASTER_SYNTHESIS.md`
- `15_ADMIN_ECONOMICS_AND_EARNED_DAY.md`

## 12.2 Как построить explainable систему советов, next-best-action и coaching на статистике, а не на шуме

Этот вопрос важнее, чем отдельное исследование игрового рейтинга.

Нужно исследовать:
- как строить персональные советы менеджеру на основе статистики,
- как выделять следующий лучший шаг по лиду или портфелю,
- как связывать советы с проблемой, а не с абстрактной мотивацией,
- какие сигналы реально полезны для coaching,
- как не превратить систему советов в спам,
- как использовать `velocity`, `response latency`, `churn risk`, `workload consistency`,
- как показывать `conversion efficiency vs expected`, не ломая основную формулу,
- как использовать anonymous benchmark без токсичности,
- нужен ли вообще comparative layer,
- и если нужен, то в каком ограниченном виде.

Нужно проверить или оспорить:
- идею explainable hints,
- роль micro-feedback,
- роль shadow rival / private ladder / comparative layer,
- сочетание `daily score + portfolio state + follow-up discipline + QA`,
- роль client communication timeline,
- роль report integrity и funnel integrity как coaching triggers,
- и правила, при которых совет должен быть жёстким, мягким или вообще не показываться.

Нужно получить:
- архитектуру explainable advice engine,
- список top recommendation types,
- приоритеты сигналов,
- anti-noise rules,
- anti-fatigue rules,
- логику evidence-based coaching,
- правила разделения `authoritative` и `shadow` signals,
- и вывод, нужен ли comparative rating как отдельный слой сейчас, позже или вообще не нужен.

Основные файлы контекста:
- `02_MOSAIC_SCORE_SYSTEM.md`
- `03_PAYROLL_KPI_AND_PORTFOLIO.md`
- `04_ANTI_DUPLICATION_AND_FOLLOWUP_ENGINE.md`
- `06_UI_UX_AND_MANAGER_CONSOLE.md`

## 12.3 Какая модель call QA и calibration действительно улучшает продажи, а не превращается в субъективный контроль

Нужно исследовать в контексте:
- outbound и semi-warm B2B selling,
- small-team supervisor review,
- explainable QA scorecard,
- и payroll-safe ограничений.

Нужно проверить или оспорить:
- как QA должен влиять на coaching,
- как QA должен влиять на trust,
- как QA должен влиять на зарплату,
- частоту calibration,
- reliability thresholds,
- competency profile vs simple scorecard,
- script-following vs useful improvisation analytics,
- must-have и optional supervisor features.

Нужно получить:
- practical QA rubric,
- scorecard categories и weights,
- cadence для калибровки,
- kappa или equivalent thresholds,
- QA-to-coaching policy,
- QA-to-compensation limits,
- role of competency profile in coaching,
- where to stop human-factor claims and keep only evidence-backed review,
- правила обработки short calls,
- и границы субъективного влияния администратора.

Основные файлы контекста:
- `05_IP_TELEPHONY_QA_AND_SUPERVISOR.md`
- `13_CROSS_SYSTEM_GUARDRAILS.md`
- `07_IMPLEMENTATION_ROADMAP.md`

## 12.4 Какие dedupe, merge и migration patterns лучше всего подходят для CRM с lead parsing, batch import и будущей телефонией

Нужно исследовать в контексте:
- грязных исторических данных,
- неполных идентификаторов,
- разных источников лида,
- будущих telephony-сигналов,
- и риска случайных merge-ошибок.

Нужно проверить или оспорить:
- exact matching rules,
- fuzzy thresholds,
- conflict resolution,
- batch import preview,
- rollback window,
- migration sequencing,
- operator review workflow.

Нужно получить:
- рекомендуемые exact rules,
- рекомендуемые fuzzy thresholds,
- merge decision rules,
- rollback windows,
- migration checklist,
- safe defaults для v1,
- и анти-ошибочные guardrails.

Основные файлы контекста:
- `04_ANTI_DUPLICATION_AND_FOLLOWUP_ENGINE.md`
- `07_IMPLEMENTATION_ROADMAP.md`
- `13_CROSS_SYSTEM_GUARDRAILS.md`

## 12.5 Какую telephony, reminder и notification architecture лучше выбрать именно для TwoComms

Нужно исследовать в контексте:
- Украины и сопоставимых рынков,
- supervisor listening,
- webhook maturity,
- recording economics,
- mobile admin workflow,
- alert fatigue,
- staged adoption.

Нужно проверить или оспорить:
- provider shortlist,
- provider comparison logic,
- recording retention,
- reminder ladder timing,
- notification channels,
- момент, когда telephony должна начинать влиять на score, coaching и admin actions.

Нужно получить:
- shortlist провайдеров,
- cost bands если их реально можно собрать,
- rollout phases,
- recording retention recommendation,
- manager/admin reminder ladder,
- notification policy,
- и главные операционные риски.

Основные файлы контекста:
- `05_IP_TELEPHONY_QA_AND_SUPERVISOR.md`
- `04_ANTI_DUPLICATION_AND_FOLLOWUP_ENGINE.md`
- `06_UI_UX_AND_MANAGER_CONSOLE.md`

## 13. Финальная инструкция deep-research агенту

Исследуй не "рынок CRM вообще", а конкретный проект, который реально строится здесь.

Лучший ответ это тот, который:
- повышает продуктивность менеджеров,
- улучшает качество отчётности,
- повышает repeat revenue,
- усиливает follow-up дисциплину,
- уменьшает дубли и пустые напоминания,
- делает payroll справедливее,
- ограничивает вред субъективного человеческого фактора,
- и остаётся внедряемым в staged roadmap TwoComms Management.
