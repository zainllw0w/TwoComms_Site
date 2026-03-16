# 07. Admin economics, validation, forecast и decision safety

## 1. Что в пакете уже очень сильное
- admin economics отделены от payroll truth;
- есть cost model и contribution proxy;
- snapshots задуманы как source for heavy diagnostics;
- validation protocol уже ушёл от naïve raw correlation;
- confidence labels уже есть как concept.

Дальше систему стоит усиливать не в сторону “больше денег и графиков”, а в сторону **лучшего decision quality**.

## 2. Что я считаю главным незавершённым блоком
Сейчас admin economics хорошо описывает **что хочется видеть**, но ещё не до конца описывает **как именно это читать и где не верить цифре слишком сильно**.

Поэтому я рекомендую сделать этот слой максимально confidence-aware.

## 3. `score_confidence` должен стать главным safety key admin-layer
Я бы использовал его не как косметическую метку, а как routing rule:

- `LOW` -> observe only
- `MEDIUM` -> coaching / support / pipeline review
- `HIGH` -> обсуждение KPI escalation / staffing / lead mix decisions

Но не наоборот. Нельзя сначала принять кадровое решение, а потом задним числом посмотреть label.

## 4. Что я бы добавил в admin economics

### 4.1 Revenue concentration risk
Очень важный small-team signal:
```python
concentration_top3 = top3_repeat_revenue / max(1, total_repeat_revenue)
```

Если один менеджер выглядит brilliant только за счёт 2-3 крупных old clients, это должен видеть admin.

### 4.2 Cohort view: new -> repeat conversion
Нужен cohort table:
- 30d repeat
- 60d repeat
- 90d repeat
- 180d repeat

Это помогает увидеть:
- кто просто закрывает первый order;
- кто реально строит retention-quality portfolio.

### 4.3 Rescue ROI
Для rescue economics нужен admin-only контур:
```python
rescue_roi = rescued_revenue_90d / max(1, rescue_spiff_paid + estimated_rescue_time_cost)
```

Это не payroll truth, а способ проверить, окупается ли сама rescue-механика.

### 4.4 Forecast aging penalty
Сейчас stage weights already good, но им не хватает age semantics.
Нужен множитель:

```python
if stage_age_days <= stage_sla_days:
    aging_penalty = 1.0
elif stage_age_days <= 2 * stage_sla_days:
    aging_penalty = 0.85
else:
    aging_penalty = 0.65
```

Тогда “старый красивый pipeline” не будет выглядеть слишком оптимистично.

### 4.5 Forecast band, а не одна цифра
Admin dashboard должен показывать:
- optimistic
- base
- pessimistic
- confidence note

Идеально ещё и объяснение, за счёт чего сценарии расходятся:
- pipeline age
- recent conversion trend
- verified coverage
- repeat concentration

## 5. Validation: что усилить

### 5.1 Считать не только `CV-R²`
Добавить ещё:
- `Kendall tau` rank stability
- top-bucket lift
- stability of manager ordering across adjacent windows

Почему это полезно:
для small-team B2B иногда ranking stability и lift полезнее, чем raw variance explanation.

### 5.2 Fresh validation windows after major formula change
Это уже partially учтено, но стоит жёстко прописать:
- новый `Result` variant;
- новый trust logic;
- новый gate ladder;
- новый churn priority term

=> всегда запускают новый validation window, не наследуя старые proof claims.

### 5.3 False-confidence guard
Если:
- data volume low,
- verified coverage low,
- volatility high,
- snapshot stale,

то UI должен показывать не “LOW, but available for decisions”, а “LOW — observation only”.

## 6. Contribution proxy: что стоит улучшить
Пока margin model нет, и это правильно признаётся.
Но можно всё равно улучшить proxy accuracy через optional fields:
- estimated returns/adjustments
- source acquisition cost proxy
- rescue time cost proxy
- onboarding amortization horizon

Всё это строго admin-only.

## 7. Наиболее вероятные bugs без этих улучшений

### Bug 1 — admin принимает решение по score, который выглядит точнее, чем есть
Из-за слабой confidence semantics.

### Bug 2 — сильный repeat revenue скрывает unhealthy concentration
И менеджер выглядит устойчивее, чем есть в реальности.

### Bug 3 — weighted pipeline систематически завышает прогноз на stale stages
Если age penalty не введён.

### Bug 4 — rescue economics выглядит хорошо по revenue, но реально ест слишком много времени
Если нет rescue ROI/proxy.

## 8. Что менять в каких файлах
- `15_ADMIN_ECONOMICS_AND_EARNED_DAY.md` — concentration, cohort, rescue ROI, decision routing by confidence
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md` — constants for concentration alert, stage aging penalties, cohort windows
- `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md` — forecast and economics payload builders
- snapshots -> add fields for concentration, cohort stats, forecast confidence reasons

## 9. Приоритет внедрения
1. explicit score_confidence formula
2. forecast aging penalty
3. concentration risk
4. cohort retention table
5. rescue ROI
6. expanded validation metrics
