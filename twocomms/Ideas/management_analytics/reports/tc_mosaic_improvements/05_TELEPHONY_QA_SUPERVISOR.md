# 05. Telephony, QA и supervisor layer — безопасное усиление

## 1. Что пакет уже сделал правильно
- telephony не forced as phase-0 prerequisite;
- `VerifiedCommunication` до rollout = `DORMANT`;
- meaningful call >30s включается только после maturity;
- QA не участвует в деньгах до calibration;
- есть `CallRecord`, `CallQAReview`, supervisor actions и retention idea.

Это правильный фундамент.

## 2. Главный остаточный риск telephony-layer
Пакет хорошо описал **что считать после запуска**, но слабее описал **что делать, когда provider/data pipeline работает нестабильно**.

Самая опасная ошибка здесь такая:
сбой провайдера или reconciliation gap выглядит как manager underperformance.

## 3. Что нужно добавить обязательно

### 3.1 `TelephonyHealthSnapshot`
Нужен ежедневный или intra-day health payload:
- webhook lag
- unmatched call ratio
- missing recording ratio
- provider 5xx/timeout burst
- reconciliation backlog size
- snapshot freshness

Идея:
- если health падает ниже порога,
- system suggests `TECH_FAILURE` window or at least disables punitive telephony interpretations.

### 3.2 `call_reconciliation_status`
Для каждого `CallRecord` нужен status:
- `matched_exact`
- `matched_last7_reviewed`
- `unmatched`
- `manual_proxy`
- `provider_orphan`

Это резко улучшает explainability при disputes и QA review.

### 3.3 `connected_talk_seconds`
Если провайдер даёт только общую длительность, есть риск считать hold/ring time meaningful conversation.
Поэтому по возможности нужен separate field:
- `ring_seconds`
- `connected_seconds`
- `talk_seconds`

Если провайдер не даёт таких деталей, UI и QA должны показывать lower confidence.

## 4. QA: что ещё стоит формализовать

### 4.1 Rubric versioning
Каждая review должна знать:
- `rubric_version`
- `reviewer_id`
- `calibration_cycle_id`

Иначе через время невозможно сравнивать оценки между версиями rubric.

### 4.2 Sampling contract
Нужна не только review queue, но и явная sampling semantics.
Рекомендация для старта:
- min `3` calls/week/manager or `5%` of eligible calls, whichever is higher;
- stratify by:
  - short/long
  - successful/unsuccessful outcome
  - source type
  - new vs repeat portfolio touch

Это помогает не получить иллюзию качества на случайной мягкой выборке.

### 4.3 Blind double-review в calibration window
До любого score-sensitive usage:
- часть записей должна оцениваться двумя reviewers;
- disagreement log виден supervisor/admin;
- until stable reliability -> coaching only.

### 4.4 Review SLA
Иначе queue перестанет быть operationally useful.
Предлагаю:
- mismatch review -> within `1` working day
- regular QA coaching review -> within `3` working days
- dispute-linked call review -> priority same/next day

## 5. Manual/proxy phase тоже стоит усилить
Пока телефония не ACTIVE, полезно сделать чуть более сильный evidence ladder:
- CP email log
- CommercialOfferEmailLog
- message delivery evidence where available
- manual note only = weakest

Это не превращает proxy в telephony truth, но снижает хаос Phase 0.

## 6. Supervisor layer: чего не хватает

### 6.1 Outcome mismatch matrix
Нужна матрица вида:
- short call + strong outcome
- no recording + strong outcome
- repeated weak outcomes on long calls
- same-day stage jump without matching call evidence

Это должно идти в review queue как grouped patterns, а не как россыпь тревог.

### 6.2 Coaching artifact
После QA review менеджеру нужен не full punitive rubric dump, а:
- `1 main strength`
- `1 main fix`
- `1 next experiment`
- link to evidence

Это улучшает adoption и не превращает QA в эмоциональное наказание.

## 7. AI assist: что стоит заранее ограничить
Даже если позже добавите transcription/AI:
- AI summary never becomes payroll truth;
- AI tags = draft until human accepted;
- disputes always rely on raw record + timeline, not AI impression.

## 8. Наиболее вероятные баги без этих улучшений

### Bug 1 — provider outage becomes manager fault
Из-за отсутствия health bridge.

### Bug 2 — rubric drift destroys comparability
Из-за отсутствия rubric versioning.

### Bug 3 — “meaningful call” будет измерять не разговор, а общую длительность соединения
Если не появится talk/connected distinction.

### Bug 4 — QA queue станет случайной и предвзятой
Если не закрепить sampling contract.

## 9. Что менять в каких файлах
- `05_IP_TELEPHONY_QA_AND_SUPERVISOR.md` — health snapshot, reconciliation statuses, sampling contract, rubric versioning
- `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md` — new models/services
- `07_IMPLEMENTATION_ROADMAP.md` — добавить telephony-health acceptance criteria
- models -> `TelephonyHealthSnapshot`, `rubric_version`, `reconciliation_status`
- commands -> health rollup, orphan reconciliation, mismatch queue builder

## 10. Приоритет внедрения
1. webhook log + reconciliation status
2. telephony health snapshot
3. rubric versioning
4. QA sampling contract
5. blind double-review and disagreement analytics
6. coaching artifact output
