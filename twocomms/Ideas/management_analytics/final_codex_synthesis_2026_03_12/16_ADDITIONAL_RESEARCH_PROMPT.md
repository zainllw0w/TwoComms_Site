# Дополнительный промпт для Deep Research — TwoComms Management (Раунд 2)

## ИНСТРУКЦИЯ ДЛЯ ИССЛЕДОВАТЕЛЬСКОГО ИИ

Ты — deep research agent. Тебе поставлена задача провести **глубокое аналитическое исследование по 5 специализированным вопросам** для проекта TwoComms Management.

Это **второй раунд исследования**. Первый раунд покрывал: KPI/payroll/probation, explainable coaching/next-best-action, call QA/calibration, dedupe/merge/migration patterns, telephony/reminder architecture. **Не дублируй эти темы.** Этот раунд покрывает **конкретные тяжёлые аналитические проблемы**, которые связаны с точностью формул, калибровкой порогов, доказательной базой для числовых решений и правильной подачей сложной статистики менеджерам.

**Ответ должен быть полностью на русском языке.**

---

## КТО МЫ И ЧТО СТРОИМ

`TwoComms Management` — management subdomain для **небольшой B2B wholesale-команды** (3–7 менеджеров). Это оптовая продажа одежды (fashion wholesale), подключение магазинов.

Мы строим многослойную систему оценки и контроля работы менеджеров:

**Базовая формула дня MOSAIC Score (6 осей):**
```
base_day = 0.40 * Result + 0.15 * SourceFairness + 0.15 * Process + 0.10 * FollowUp + 0.10 * DataQuality + 0.10 * VerifiedCommunication
```

Где:
- `Result = 0.35 * NewPaid + 0.20 * RepeatPaid + 0.25 * WeightedRevenue + 0.20 * VerifiedMilestones`
- `WeightedRevenue = min(100, 100 * sqrt(revenue_period / revenue_target_period))`
- `SourceFairness` — компенсация за сложность базы (cold_xml 1.5%, parser_cold 3%, manual_hunt 6%, warm_reactivation 18%, hot_inbound 30%)
- `Process` — next action, stage progression, response latency, pipeline regression
- `FollowUp` — callback on time, stale shops, rescue discipline
- `DataQuality` — valid reasons, no duplicate stuffing, data freshness
- `VerifiedCommunication` — email, telephony, system timestamps

**Trust coefficient:**
```
trust = clamp(0.70, 1.10, 0.78 + 0.16*verified_ratio + 0.08*qa_reliability + 0.04*reason_quality + 0.04*report_integrity - 0.06*duplicate_abuse - 0.06*anomaly_penalty)
```

**Discipline floor dampener:**
```
discipline_floor_dampener = max(0.85, 1 - 0.05 * count(axis < 20 for axis in [Process, FollowUp, DataQuality, VerifiedCommunication]))
```
- Rolling 10 business days, max dampening -15%.

**Gate system (cap):**
| Сценарий | Cap |
|---|---:|
| Есть оплата или admin-confirmed conversion | `100` |
| Verified commercial progress, но без оплаты | `78` |
| Только self-reported activity | `60` |
| 3+ рабочих дня без progress + callback breaches | `45` |

**Финальный score:**
```
manager_score_day = min(base_day * discipline_floor_dampener, gate_cap) * trust + portfolio_bonus
admin_score_day = 0.80 * manager_score_day + 0.10 * roi_score + 0.10 * qa_score
```

**Rolling:** EWMA с lambda = 0.033, half-life ≈ 21 день.

**Финансовое ядро:** 15 000 грн base, 2.5% за первый заказ, 5% за повторный. Акселератор +0.5% к repeat rate.

**Portfolio health:**
| State | Дней с последнего контакта |
|---|---:|
| Healthy | 0–21 |
| Watch | 22–35 |
| Risk | 36–45 |
| Rescue | 46–60 |
| Reassign Eligible | 61+ |

**Trust anomaly thresholds:**
| Signal | Caution | Critical |
|---|---:|---:|
| duplicate override rate | >3% | >6% |
| same reason share | >45% | >60% |
| short-call mismatch | >8% | >15% |
| missed callback rate | >15% | >25% |

**Report integrity:** min 20 resolved cases, ≥0.85 strong, 0.70–0.84 neutral, 0.55–0.69 caution, <0.55 critical.

**Fuzzy duplicate matching:**
```
similarity = 0.40 * shop_name_similarity + 0.30 * phone_similarity + 0.20 * city_match + 0.10 * owner_similarity
```
Thresholds: ≥0.95 exact/auto-block, ≥0.70 review queue, ≥0.50 suggestion, <0.50 ignore.

**Стек:** Django 5.2 + Celery + Redis. Команда маленькая (3–7 менеджеров).

**Инварианты, которые нельзя ломать:**
- Verified outcomes важнее self-reported activity.
- Commission truth строится только из verified paid orders.
- Manager view и admin view разделены.
- Субъективное мнение администратора не должно напрямую ломать зарплату без ограничений.
- Рекомендации должны быть реалистичны для Django + Celery + Redis и 3–7 менеджеров.

---

## ФОРМАТ ОТВЕТА

В начале ответа дать:
- **10 главных выводов** по всем 5 вопросам
- **5 самых ценных изменений / корректировок**, которые стоит внедрять раньше всего
- **3 самых опасных риска** если оставить текущие числа без валидации

Для каждого из 5 вопросов вернуть:

1. **Executive summary** (5–7 предложений)
2. **Benchmark numbers** — конкретные числа, диапазоны, формулы из авторитетных источников
3. **5–10 авторитетных источников** (peer-reviewed journals, industry reports, CRM documentation, academic books). Для каждого:
   - название, автор(ы)/организация, год, URL если есть, краткое описание релевантности
4. **Конкретная рекомендация для TwoComms** — с формулами/числами, что именно изменить
5. **Что рискованно** — для нашего масштаба
6. **Финальная рекомендация** — 3–5 предложений простым языком
7. **Integration impact** — какие числа/формулы/пороги в системе должны быть скорректированы

---

## ВОПРОС 1: Как валидировать и калибровать веса composite scoring формулы (MOSAIC) для малой B2B команды

### Проблема

У нас composite score с 6 осями и весами `0.40/0.15/0.15/0.10/0.10/0.10`. Эти веса выбраны **экспертной интуицией**, не на основе данных. Ось Result внутри делится на `0.35/0.20/0.25/0.20`. Сверху — trust coefficient, gate system, discipline dampener.

Мы планируем валидировать score через корреляцию `rolling MOSAIC ↔ attributed revenue`:
- r² < 0.30 = recalibration needed
- 0.30–0.49 = medium validity
- ≥ 0.50 = strong enough

Мы **не знаем**:
- правильные ли наши пороги r² для sales performance scoring
- как вообще валидировать composite score при 3–7 менеджерах (tiny N)
- не коррелируют ли оси друг с другом (multicollinearity), делая веса бессмысленными
- как откалибровать веса на основе реальных данных, а не интуиции
- насколько устойчива формула к малым изменениям весов

### Что нужно исследовать

1. **Какие методы валидации composite performance scores существуют в HR analytics и sales operations research?**
   - Criterion validity (predicting revenue), construct validity (axes measure what they should), convergent/discriminant validity
   - Какие correlation/r² benchmarks считаются адекватными для performance scoring в sales? Наши 0.30/0.50 — это завышено, занижено или нормально?

2. **Какой минимальный sample size нужен для статистически значимой валидации?**
   - При N = 3–7 менеджеров и 20–50 рабочих дней за период — какие методы реально работают?
   - Bootstrap, permutation tests, Bayesian approaches, Leave-One-Out Cross-Validation для tiny datasets
   - Когда статистическая валидность вообще невозможна, и нужно опираться только на экспертное суждение?

3. **Как обнаружить мультиколлинеарность между осями?**
   - `Result` и `SourceFairness` могут коррелировать (хороший source mix → лучший result). `VerifiedCommunication` и `Process` тоже.
   - VIF, PCA, factor analysis — что подходит при 6 осях и tiny N?
   - Если оси коррелируют — что делать? Объединять? Менять формулу?

4. **Как калибровать веса на основе данных?**
   - AHP (Analytic Hierarchy Process), Elastic Net regression, DEA (Data Envelopment Analysis) — что применимо для sales scoring weight calibration?
   - Как это делают Salesforce Einstein, Zoho Zia, Gong.io для своих performance metrics?
   - Можно ли использовать Lasso/Ridge regression для автоматической калибровки весов при tiny N?

5. **Sensitivity analysis — насколько устойчива наша формула?**
   - Если сдвинуть Result с 0.40 на 0.35 или 0.45 — насколько меняется итоговый ранг менеджеров?
   - Monte Carlo sensitivity analysis для small-team scoring
   - Robust alternative: нужны ли вообще фиксированные веса, или лучше бандитный/адаптивный подход?

### Ответ, который нужен

- Конкретный **протокол валидации**: «после 90 дней данных сделай X, посчитай Y, если Z — пересмотри веса»
- Скорректированные пороги r² (или альтернативная метрика вместо r²) с обоснованием
- Рекомендация: нужно ли менять наши 0.40/0.15/0.15/0.10/0.10/0.10 или они адекватны
- Ссылки на peer-reviewed research по sales performance measurement и composite index construction

---

## ВОПРОС 2: Как калибровать Trust Coefficient и Report Integrity — где научная основа для коэффициентов и порогов

### Проблема

Наш trust coefficient:
```
trust = clamp(0.70, 1.10, 0.78 + 0.16*verified_ratio + 0.08*qa_reliability + 0.04*reason_quality + 0.04*report_integrity - 0.06*duplicate_abuse - 0.06*anomaly_penalty)
```

Каждый коэффициент (0.78 base, +0.16, +0.08, +0.04, -0.06 и т.д.) выбран **интуитивно**. Мы не знаем:
- правильная ли 0.78 как стартовая точка (почему не 0.80 или 0.75?)
- правильный ли вес verified_ratio (0.16) — self-reported vs verified — какое соотношение справедливо?
- какие thresholds для anomaly signals (duplicate override >3%/>6%, same reason share >45%/>60%, short-call mismatch >8%/>15%) реально отражают abuse?
- как определить report_integrity thresholds (0.55/0.70/0.85) — откуда эти числа?
- какая bounded range для trust ([0.70, 1.10]) правильная — почему именно 0.70 floor и 1.10 ceiling?

### Что нужно исследовать

1. **Как строятся trust/reliability coefficients в performance management systems?**
   - Существуют ли academic frameworks для data quality weighting в CRM analytics?
   - Как Salesforce Shield, HubSpot Data Quality, или enterprise BI-платформы определяют "data trustworthiness"?
   - Multilevel reliability models — применимы ли они к нашему масштабу?

2. **Какие пороги для abuse/anomaly signals подтверждены эмпирически?**
   - Duplicate override rates: 3%/6% — это взято из практики или из воздуха? Что используют Salesforce duplicate management, HubSpot dedup rules?
   - Same reason share: 45%/60% — какой процент «одинаковых причин» действительно сигнализирует о лени/padding?
   - Short-call vs outcome mismatch: 8%/15% — есть ли benchmark из call center QA research?
   - Missed callback rates: 15%/25% — как это соотносится с операционными SLA в B2B sales?

3. **Как правильно калибровать verified_ratio и self-reported weighting?**
   - В каком соотношении система должна верить verified events vs self-reported status?
   - Dual-signal validation frameworks из audit/compliance research
   - Как уменьшать weight self-reported данных по мере роста verified coverage?

4. **Как определить оптимальные boundaries для trust coefficient?**
   - Floor 0.70 означает, что даже при плохом trust менеджер получает 70% score — это слишком мягко?
   - Ceiling 1.10 означает bonus max +10% за хорошее доверие — это достаточно?
   - Как подобные bounded systems работают в credit scoring, insurance underwriting, HR reliability scoring?

5. **Report integrity: как правильно измерять расхождение между reported и verified outcomes?**
   - Какие метрики accuracy/integrity используются в data quality research? (precision, recall, F1 для CRM data?)
   - Правильные ли наши thresholds 0.55/0.70/0.85?
   - Как учитывать leads, которые ещё not resolved? Наша политика — не штрафовать за open leads, но это может создать лазейку.

### Ответ, который нужен

- Обоснованная рекомендация по каждому коэффициенту в trust формуле: «измените X на Y потому что Z»
- Скорректированные thresholds для anomaly signals с ссылками на research/industry standards
- Рекомендация по report integrity measurement methodology
- Ответ прямым текстом: наши числа завышены, занижены или адекватны?

---

## ВОПРОС 3: Какие gaming patterns и anti-abuse detection подходы доказано работают в scoring и KPI-системах для отделов продаж

### Проблема

Любая scoring/KPI система создаёт incentives для gaming. У нас есть:
- duplicate abuse threshold (<3% для NORMAL)
- trust coefficient с наказанием
- report integrity signal
- data entry freshness
- short-call mismatch detection

Но мы **не исследовали систематически**:
- какие конкретные gaming patterns возникают в sales CRM scoring (не абстрактно, а конкретно)
- какие statistical detection методы работают при N = 3–7 менеджеров
- как отличить gaming от естественной вариативности
- какие наши текущие пороги (3%/6% duplicate, 45%/60% same reason, 8%/15% short-call) адекватны
- где граница между «тревога» (admin alert) и «автоматическая санкция» (trust reduction)

### Что нужно исследовать

1. **Таксономия подтверждённых gaming patterns в sales operations и CRM-системах:**
   - Activity stuffing (раздувание количества звонков/контактов)
   - Stage inflation (перевод лидов в продвинутые стадии без основания)
   - Report padding (одинаковые причины, copy-paste заметки)
   - Callback cycling (запись callback → отмена → новый callback для score)
   - Ownership manipulation (передача лидов для credit farming)
   - Cherry-picking (работа только с тёплыми лидами, игнорирование холодных)
   - Batch logging (внесение данных в конце дня задним числом)
   - Каждый паттерн — с конкретным detection rule

2. **Goodhart's Law и Campbell's Law в контексте sales KPIs:**
   - Какие конкретные последствия документированы в academic literature?
   - Harvard Business Review, MIT Sloan, Journal of Personal Selling & Sales Management — есть ли case studies?
   - Как зрелые системы (Salesforce, SAP Commissions, Xactly) защищаются от gaming?

3. **Statistical anomaly detection для tiny datasets (N = 3–7):**
   - z-score outlier detection — работает при таком N?
   - IQR-based methods — применимы?
   - Benford's Law для CRM activity data — реально ли?
   - Threshold-based rules vs ML detection — что лучше для 20-50 daily records на менеджера?
   - Какой false positive rate приемлем?

4. **Как разделять «gaming» от «strong performance» и «natural variability»?**
   - Type I (ложная тревога) vs Type II (пропуск gaming) error tradeoff
   - Как не превратить anti-abuse в параноидальный контроль, который убивает доверие?
   - Transparency paradox: если менеджер знает правила — обходит; если не знает — воспринимает как несправедливость

5. **Конкретные detection формулы для наших паттернов:**
   - Для activity stuffing: `if daily_contacts > mean + k*std AND verified_progress = 0 → alert`. Какое k?
   - Для report padding: `if same_reason_share > X% AND n >= Y → alert`. Правильные ли наши 45%/60%?
   - Для batch logging: `if 80%+ of daily entries within last 30 min → caution`. Адекватно ли 80%?
   - Для callback cycling: как определить аномальный callback pattern?

### Ответ, который нужен

- **Таксономия** gaming patterns с конкретными detection формулами и порогами
- Рекомендация: какие наши пороги (3%/6%, 45%/60%, 8%/15%) правильные, а какие нужно менять
- Протокол: «начни с X, калибруй каждые Y дней, используй метрику Z»
- Чёткое разделение: что должно быть admin alert, а что automatic trust reduction
- Ссылки на research и case studies по anti-gaming в sales performance systems

---

## ВОПРОС 4: Как правильно подать сложную аналитику и scoring менеджерам — explainability, perceived fairness и UX-форматы

### Проблема

Наша система сложная: 6 осей, trust, gate, dampener, micro-feedback, advisory cards, portfolio health, heatmap, salary simulator. Менеджер должен:
- понять, почему его score именно такой
- знать, что делать, чтобы улучшить score
- не чувствовать, что система несправедлива или непонятна
- не перегружаться информацией

У нас есть:
- explainability breakdown (каждый день — что толкнуло score вверх/вниз)
- advisory cards (max 3 одновременно)
- recovery-first copy (вместо «ты потерял 8 баллов» → «до лучшего уровня не хватает: callbacks +4, rescue +2»)
- progressive onboarding (Day 1-3 minimal, Day 8-14 full open)
- anonymous benchmark (ваше значение, медиана, верхний квартиль)

Но мы **не знаем**:
- какие форматы explainability реально повышают perceived fairness (text? visual? decomposition chart?)
- сколько информации optimal — 3 сигнала или 5? 1 совет или 3?
- как anonymous benchmark влияет на мотивацию в tiny teams — работает или вредит?
- какие UX-паттерны РЕАЛЬНО улучшают принятие сложных scoring систем
- как нас предупреждает research о типичных ошибках в presentation performance data

### Что нужно исследовать

1. **Explainability research для performance scoring систем:**
   - Ribeiro et al. (LIME, 2016) и Lundberg (SHAP, 2017) — как их принципы применяются к non-ML scoring?
   - Какие форматы объяснения (narrative text, bar chart decomposition, waterfall chart, traffic light) лучше влияют на perceived fairness?
   - HBR, organizational psychology journals — что работает для sales teams?

2. **Procedural justice theory и implied acceptance of scoring:**
   - Leventhal's criteria (consistency, bias suppression, correctability, representativeness, accuracy, ethicality) — как каждый критерий реализуется в нашей системе?
   - Colquitt (2001) meta-analysis on organizational justice — какие элементы критичны?
   - Voice effect: как дать менеджеру влиять на систему без game-ability?

3. **Information overload vs actionability:**
   - Сколько метрик/scores/cards можно показать menеджеру одновременно до потери эффективности?
   - Miller's Law (7±2), cognitive load theory — как это применяется к dashboards?
   - Few (2006, 2012) «Information Dashboard Design» — конкретные рекомендации
   - Нашего правило «max 3 advisory cards» — это по науке или интуиция?

4. **Anonymous benchmark в маленькой команде:**
   - При 3–5 менеджерах benchmark = фактически identifiable. Работают ли anonymous comparisons при таком N?
   - Social comparison theory (Festinger, 1954) — upward vs downward comparison effects
   - Competitive vs collaborative framing — что лучше для small B2B teams?
   - Какой threshold N нужен, чтобы anonymous benchmark был реально anonymous и безопасный?

5. **Negativity bias и framing в scoring:**
   - Loss framing vs gain framing — какой подход к отображению score работает лучше?
   - Recovery-first copy — подтверждено ли research, что это улучшает поведение менеджеров?
   - Каков оптимальный баланс positive/negative feedback в scoring interface? (3:1? 5:1?)

6. **Progressive disclosure / onboarding:**
   - Наш план Day 1-3 minimal → Day 15+ full — это по research или по интуиции?
   - Какие benchmarks progressive onboarding существуют для workplace analytics tools?
   - Krug's «Don't Make Me Think» и продуктовый onboarding research — что применимо?

### Ответ, который нужен

- Конкретная рекомендация по формату: «покажи менеджеру X в формате Y, не показывай Z»
- Обоснование или корректировка нашего правила «max 3 advisory cards»
- Обоснование или корректировка anonymous benchmark для tiny teams
- Рекомендация по positive/negative feedback ratio с ссылкой на research
- Рекомендация по progressive onboarding timing с ссылкой на research

---

## ВОПРОС 5: Как правильно настроить fuzzy matching для дедупликации B2B клиентов — точность, recall и оптимальные пороги

### Проблема

Наша формула дедупликации:
```
similarity = 0.40 * shop_name_similarity + 0.30 * phone_similarity + 0.20 * city_match + 0.10 * owner_similarity
```

Пороги:
- ≥ 0.95 = exact / auto-block
- ≥ 0.70 = likely / review queue
- ≥ 0.50 = suggestion / show in UI
- < 0.50 = ignore

Мы **не знаем**:
- правильные ли веса (0.40/0.30/0.20/0.10) для B2B wholesale data
- правильные ли пороги (0.95/0.70/0.50) — какие false positive и missed duplicate rates при этих порогах?
- какой алгоритм для `shop_name_similarity` лучше (trigram, Jaro-Winkler, Levenshtein, phonetic)
- как обрабатывать transliteration (кириллица-латиница, украинский-русский варианты написания)
- какой precision/recall tradeoff приемлем в CRM-дедупликации (лучше пропустить дубль или создать ложное совпадение?)
- как scale-ить fuzzy matching при росте базы (100 → 500 → 2000+ клиентов)

### Что нужно исследовать

1. **Record linkage и entity resolution research — что говорит наука:**
   - Fellegi-Sunter model (1969) — классическая теория record linkage
   - Probabilistic record linkage vs deterministic — что лучше для B2B CRM с грязными данными?
   - Active learning approaches для record linkage (Sarawagi, Bhamidipaty 2002) — применимо для малых баз?
   - Duke/Linkage frameworks — что рекомендуют?

2. **Оптимальные string similarity метрики для бизнес-наименований:**
   - Jaro-Winkler vs trigram (pg_trgm) vs Levenshtein vs Soundex/Metaphone
   - Какой алгоритм лучше для коротких торговых наименований, часто с числами, аббревиатурами, транслитерацией?
   - Какие benchmarks performance и accuracy существуют для каждого?
   - Compound names (ИП Петренко vs Петренко О.М.) — какой подход даёт лучший recall?

3. **Phone number matching:**
   - Наш вес 0.30 для phone — адекватно ли? Телефон — самый точный идентификатор, нужно ли повышать вес?
   - Partial phone matching (последние 7 цифр, city code variations) — какие правила работают?
   - Множественные телефоны у одного клиента — как влияет на scoring?

4. **Оптимальные пороги (precision vs recall tradeoff):**
   - В CRM-дедупликации что дороже: пропущенный дубль (duplicate leads, wasted effort, trust reduction) или ложное совпадение (merged different clients, lost data)?
   - Какие threshold tuning методики используются? (ROC curve, precision-recall curve, F-beta score)
   - Существуют ли industry benchmarks для «приемлемого» false positive rate в B2B dedup? (Salesforce, HubSpot, Dedupe.io)
   - Наши пороги 0.95/0.70/0.50 — как они соотносятся с тем, что рекомендует research?

5. **Batch import dedup:**
   - Blocking strategies для ускорения matching при batch import (sorted neighborhood, canopy clustering)
   - Каковы performance bounds при 2000+ записей с fuzzy matching в PostgreSQL?
   - Как снизить O(n²) complexity?

6. **Transliteration и multilingual matching (украинский/русский/латиница):**
   - Как лучше нормализовать бизнес-наименования с кириллицей до сравнения?
   - Phonetic matching для славянских языков — есть ли адаптированные алгоритмы?
   - Какие практики используют CRM-платформы на постсоветском рынке?

### Ответ, который нужен

- Обоснованная рекомендация по весам: нужно ли менять 0.40/0.30/0.20/0.10?
- Рекомендация по алгоритму shop_name_similarity для кириллических бизнес-имён
- Скорректированные thresholds с обоснованием (precision/recall tradeoff)
- Рекомендация по phone weight и partial matching rules
- Конкретная рекомендация по blocking strategy для batch import
- Performance expectations для PostgreSQL pg_trgm при 1000-5000 клиентов

---

## ОБЩИЕ ПРАВИЛА

1. **Источники должны быть авторитетными:**
   - Peer-reviewed journals (Journal of Personal Selling & Sales Management, Journal of Marketing, Industrial Marketing Management, Journal of Data Quality, VLDB, ACM SIGMOD)
   - Industry reports (Gartner, Forrester, McKinsey)
   - CRM documentation (Salesforce, HubSpot, Zoho, Gong.io, Xactly)
   - Academic books (Christen «Data Matching», Few «Information Dashboard Design», Colquitt organizational justice research)
   - **НЕ** блоги без attribution, **НЕ** generic motivation posts.

2. **Ответы должны быть с числами, формулами и порогами**, а не абстрактные рассуждения вроде «нужно больше данных».

3. **Для каждого предложения указать risk of abuse** — как это может быть exploit-ировано.

4. **Рекомендации должны быть реалистичны для Django + Celery + Redis и 3–7 менеджеров.**

5. **Если точных данных нет** — дать ближайший proxy и явно указать, что это proxy.

6. **Прямо указывать**: «ваше текущее число X — завышено / занижено / адекватно, рекомендуемый диапазон Y–Z, потому что [ссылка на research]».
