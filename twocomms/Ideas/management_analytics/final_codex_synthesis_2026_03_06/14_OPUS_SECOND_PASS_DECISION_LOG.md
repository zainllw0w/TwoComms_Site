# Opus Second Pass Decision Log

## 1. Зачем нужен этот файл

После `opus_4.6_codex_final_synthesis_report.md` и `opus_4.7_counter_analysis_codex_rejections.md` стало понятно, что одной интеграции идей недостаточно.

Нужен отдельный журнал решений:
- что реально усиливает точность,
- что стоит принять только в ослабленном виде,
- что должно остаться admin-only,
- что выглядит умно, но опасно для production,
- и почему именно так.

Этот файл защищает MOSAIC от двух крайностей:
- от консервативного “ничего не добавлять”,
- и от хаотичного “добавить все умные формулы сразу”.

## 2. Принцип отбора

Каждое предложение из второго прохода Opus оценивалось по 5 критериям:
- повышает ли оно точность или предсказуемость,
- не создаёт ли оно double-counting,
- не усиливает ли субъективный человеческий фактор,
- можно ли его объяснить менеджеру и админу,
- реалистично ли его внедрить по фазам.

## 3. Принято в authoritative core

### 3.1 Exponential temporal weighting
Статус:
- `принято`

Почему:
- исправляет temporal bias,
- быстро показывает реальное улучшение или ухудшение,
- не требует новых данных.

Как включено:
- `02_MOSAIC_SCORE_SYSTEM.md`
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`

Ограничение:
- используется для rolling analytics и multi-day summaries,
- не переписывает сам факт paid order.

### 3.2 Low-sample protection for SourceFairness
Статус:
- `принято`

Почему:
- small-team B2B не даёт права делать жёсткие выводы на `0/3`.

Как включено:
- confidence blending + Wilson-style interpretation,
- low-sample pairs уходят в neutral band.

### 3.3 Bayesian shadow recalibration
Статус:
- `принято с ограничениями`

Почему:
- quarterly review слишком медленный, если рынок сдвинулся раньше.

Как включено:
- weekly shadow posterior,
- bounded soft movement,
- quarterly hard cap остаётся главным.

Почему не включено в raw auto-mode:
- иначе система начнёт дёргаться на шуме.

### 3.4 Report integrity inside trust
Статус:
- `принято`

Почему:
- нужна защита от систематического stage inflation,
- но без сырого наказания за ещё не дозревшие лиды.

Как включено:
- как bounded trust sub-signal,
- только на resolved cases,
- только при достаточной выборке.

### 3.5 Discipline floor dampener
Статус:
- `принято в production-safe версии`

Почему:
- высокий `Result` действительно может частично маскировать катастрофическую operational discipline.

Как включено:
- только по operational axes,
- только на rolling basis,
- cap `-15%`,
- не применяется в onboarding, leave и manual-only telephony phase.

Почему не включено в жёстком виде Opus:
- штраф по всем осям и на daily level был бы слишком шумным.

## 4. Принято, но только как bounded / partial logic

### 4.1 Long-cycle deal idea
Статус:
- `принято частично`

Что было у Opus:
- сильный multiplier за долгую сделку.

Что включено:
- bounded `nurture persistence credit`.

Почему не принят сильный multiplier:
- слишком легко превратить его в incentive to stall.

### 4.2 Effort intensity
Статус:
- `принято частично`

Что включено:
- signal of meaningful effort,
- мягкое влияние только внутри `Process`,
- без прямого штрафа в payroll contour.

Почему:
- пользователь прав, что `15` и `100` meaningful contacts нельзя считать одинаково,
- но нельзя награждать просто за суету.

### 4.3 Response latency
Статус:
- `принято частично`

Что включено:
- response latency bands,
- только для inbound/warm/callback contexts.

Почему:
- для холодного outbound это не такой же по смыслу сигнал.

### 4.4 Data entry freshness
Статус:
- `принято частично`

Что включено:
- freshness как DataQuality sub-signal,
- evidence-only,
- clustered end-of-day logging как risk pattern.

Почему:
- delayed entry реально ухудшает качество данных,
- но нельзя штрафовать без source timestamp.

## 5. Принято как admin / coaching only

### 5.1 MOSAIC velocity
Статус:
- `admin/dashboard only`

Почему:
- это отличный coaching signal,
- но плохая идея делать его денежной истиной.

### 5.2 Workload consistency
Статус:
- `admin/coaching only`

Почему:
- полезно видеть bursty behaviour,
- но прямой payroll penalty был бы слишком грубым.

### 5.3 Funnel integrity
Статус:
- `admin alert only`

Почему:
- помогает ловить “50 interested, 0 outcome”,
- но по одному интервалу нельзя наказывать автоматически.

### 5.4 Churn risk signal
Статус:
- `portfolio / action stack / coaching`

Почему:
- полезен для rescue priorities,
- не должен напрямую менять commission truth.

### 5.5 Territory balance
Статус:
- `admin analytics only`

Почему:
- root cause unfairness часто в плохом source distribution,
- это управленческий сигнал, а не личный штраф менеджеру.

### 5.6 Call competency profile
Статус:
- `QA coaching only`

Почему:
- идея сильная,
- но personality-like interpretation нельзя включать в payroll truth.

### 5.7 Script vs improvisation analytics
Статус:
- `future QA analytics`

Почему:
- полезно для эволюции script,
- вредно как быстрый punishment layer.

## 6. Оставлено в backlog / later phase

### 6.1 Achievements
Статус:
- `later phase`

Почему:
- безопасно, если zero-score,
- но не должно отвлекать от core execution OS.

### 6.2 Micro-learning snippets
Статус:
- `later phase`

Почему:
- хорошее усиление coaching,
- но зависит от зрелого competency profile и QA evidence.

### 6.3 Keyboard shortcuts and contextual help
Статус:
- `later phase, but accepted`

Почему:
- реальная операционная ценность есть,
- просто это не часть score-core.

### 6.4 Communication timeline
Статус:
- `accepted into UI/backlog`

Почему:
- это очень полезно для реальной работы менеджера,
- но это UI/data integration work, а не formula work.

## 7. Отклонено или жёстко ограничено

### 7.1 Direct efficiency modifier on Result
Статус:
- `отклонено как authoritative formula`

Почему:
- уже есть `SourceFairness`,
- прямой result-efficiency modifier создаёт double-counting.

Что вместо этого:
- efficiency vs expected в explainability и coaching.

### 7.2 Strong LCCM multipliers
Статус:
- `отклонено`

Почему:
- x2-x3 multiplier слишком легко геймить затягиванием pipeline.

### 7.3 DNA as payroll layer
Статус:
- `отклонено`

Почему:
- слишком много human-factor noise,
- слишком слабая защита от субъективности,
- риск ложной “психологизации”.

### 7.4 Burnout Risk Index
Статус:
- `отклонено`

Почему:
- погранично invasive,
- слабая operational explainability,
- риск ошибочной интерпретации.

### 7.5 Team synergy bonus
Статус:
- `отклонено`

Почему:
- смешивает индивидуальную оценку с командным luck/context,
- может создавать новые вопросы по справедливости.

### 7.6 Multi-touch as default commission model
Статус:
- `отклонено как default`

Почему:
- повышает сложность и конфликтность.

Что вместо этого:
- optional admin-approved split only for complex disputes.

### 7.7 Random reinforcement / variable rewards
Статус:
- `отклонено`

Почему:
- слишком легко скатиться в манипулятивную UX-механику,
- не повышает explainability.

## 8. Главный вывод

Opus был прав не в том, что “нужно включить всё”.
Opus был прав в другом:
- системе реально не хватало temporal precision,
- защиты от малых выборок,
- integrity-layer,
- admin-only early-warning signals,
- и более аккуратного разделения между truth и diagnostics.

Итоговая архитектура после второго прохода стала сильнее по 4 направлениям:
- точнее в математике,
- безопаснее к шуму,
- лучше защищена от double-counting,
- и яснее разделяет payroll truth, coaching signals и будущие фичи.
