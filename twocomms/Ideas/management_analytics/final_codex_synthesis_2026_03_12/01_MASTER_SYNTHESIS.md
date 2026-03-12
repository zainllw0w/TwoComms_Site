# Master Synthesis

## 1. Зачем понадобилась новая версия пакета
Версия `2026-03-06` была сильной как skeleton, но после большого отчёта от `2026-03-12` стало видно, что старый пакет содержит пять классов несогласованностей:
- формулы, которые математически выглядят красиво, но опасны для маленькой команды;
- технологические зависимости, которые не подходят текущему shared hosting;
- идеи, которые хороши как shadow analytics, но не должны влиять на деньги прямо сейчас;
- разделы, не приземлённые на текущий код `management`;
- хорошие продуктовые идеи, не превращённые в точные точки внедрения.

Эта версия закрывает все пять классов проблем одновременно.

## 2. Что сохраняем как жёсткие инварианты
- `магазин добавлен = уже оплатил` остаётся максимально верифицированным исходом.
- `2.5%` на первый заказ и `5%` на повторный заказ остаются финансовым ядром модели.
- менеджерский и админский интерфейсы остаются раздельными по ролям и по уровню власти.
- советы, напоминания и score-сигналы обязаны быть explainable и evidence-based.
- текущая CRM и текущий management-контекст не выкидываются: всё строится поверх существующих моделей, статистики, follow-up и payout-логики.
- DTF и основной wholesale management по-прежнему не смешиваются в одну общую систему истины.

## 3. Что меняется принципиально

### 3.1 Технологический каркас
Из authoritative слоя полностью убираются предположения, что система может свободно опираться на `Redis`, `Celery`, `Docker` и `pg_trgm`.

Финальный стек для planning:
- фоновые задачи: `Django management commands + cron`;
- rate limiting и временные блокировки: `FileBasedCache`;
- dedupe: `SequenceMatcher` + blocking по `phone_last7` и normalized name;
- nightly analytics: DB snapshots, а не event bus и не CQRS с отдельной инфраструктурой.

### 3.2 Score-архитектура
Итоговая score-логика теперь описывается не как "ещё один рейтинг", а как безопасная надстройка над существующим `KPD`.

Финальные принципы:
- `MOSAIC` остаётся общей рамкой;
- `Result` реализуется через `EWR`, а не через плоское "orders / expected";
- shadow/admin churn для portfolio и rescue считается через `Weibull`, а не через линейную панику, с logistic fallback при низкой истории;
- `Trust` разделяется на `production` и `diagnostic`;
- DORMANT-компоненты не штрафуют менеджера;
- gates, dampener, onboarding, weekends, excused days и single-manager mode задаются явно, а не имплицитно.

### 3.3 Payroll и KPI
Главное изменение не в процентах, а в форме санкций и ожиданий:
- cliff penalty убирается в пользу `Soft Floor Cap`;
- weekly KPI делятся на `new` и `total`, чтобы цель была реалистична при текущей конверсии;
- `Earned Day` и `DMT` становятся phase-aware: без телефонии нельзя требовать метрики, которые неоткуда взять;
- portfolio logic получает `Snooze`, `Force Majeure`, `Red Card`, weekend/excused rules и single-manager-safe режим.

### 3.4 Dedupe, Follow-Up и Ownership
Дедупликация больше не строится как абстрактный matching engine "на будущее". Она описывается как минимально надёжная и реально внедряемая логика под текущие поля:
- exact phone match;
- review-level совпадение по `phone_last7 + similarity`;
- suggestion-level похожие названия;
- ownership disputes через audit trail и admin review;
- follow-up ladder учитывает физический лимит нагрузки, а не рисует бесконечный SLA.

### 3.5 UI/UX
UI перестаёт быть просто витриной красивых идей.

Финальная UX-концепция:
- сохранить сильное текущее ядро `stats.html` и `admin.html`;
- поверх него добавить `Radar`, `Salary Simulator`, `Top-5 rescue`, `Golden Hour`, explainable advice и admin control center;
- rescue-widget ограничивается `Top-5`, показывает scaled `SPIFF` и не должен перегружать менеджера более чем `3` rescue-leads/day;
- любые copy-штрафы переводятся в recovery-first framing;
- manager должен видеть action surfaces, а не просто историю своих провалов.

## 4. Что принимаем полностью

| Тема | Финальное решение |
|---|---|
| Shared-hosting stack | `management commands + cron + FileBasedCache` |
| Result axis | `EWR` как blend outcome/effort/revenue |
| MOSAIC weights | `40 / 10 / 20 / 10 / 10 / 10` с phase-aware redistribution |
| Trust | `production` clamp `[0.85, 1.05]` + `diagnostic` 90-day trend |
| Payroll safety | `Soft Floor Cap`, а не cliff |
| Portfolio churn | `Weibull + logistic fallback + planned-gap guard` |
| Follow-up discipline | neutral при `0 due`, `MAX_FOLLOWUPS_PER_DAY`, ladder escalation |
| Dedup | `SequenceMatcher`, `phone_last7`, review queues |
| Change management | `Component Readiness Registry` + `Shadow Mode` |
| Force protection | `Client Snooze`, `Force Majeure`, `Red Card` |
| Admin analytics | `NightlyScoreSnapshot` + score-to-money validation |

## 5. Что принимаем частично

| Идея | Что берём | Что ограничиваем |
|---|---|---|
| Telephony-heavy truth model | `CallRecord`, maturity gating, QA contour | до подключения IP-телефонии не влияет на payroll |
| Bayesian / Beta logic | diagnostic trend | не используем как production multiplier при текущем N |
| Omni-touch | Phase 0 proxy через CRM + messenger/email | не делаем главным источником commission-truth |
| Seasonality | архитектуру и поля | не активируем до накопления реальных 12+ месяцев данных |
| Top-5 gamification | rescue focus, scaled `SPIFF (500-2000 грн)`, micro-feedback | без humiliating leaderboard, без punitive UI и без перегруза rescue-pool |

## 6. Что сознательно отклоняем
- любую архитектуру, где отсутствие компонента автоматически снижает score;
- жёсткий cliff по повторной комиссии на весь оборот;
- прямую зависимость денег от raw QA, пока нет зрелой QA-калибровки;
- публичный стыдящий leaderboard для маленькой команды;
- автоматический `Shark Pool` и любые токсичные auto-reassign сценарии;
- сезонные коэффициенты "из головы", если ещё нет real historical fit;
- Redis/Celery-планы как обязательную часть первой реализации;
- сложные CQRS/streaming схемы, которые не увеличивают шансы на внедрение на текущем хостинге.

## 7. Главная новая идея пакета
Старый синтез искал лучшие идеи. Новый синтез фиксирует систему перехода от идей к внедрению.

Эта система перехода строится на четырёх уровнях:
1. `Authoritative design`: что считаем финальным на уровне продукта и формул.
2. `Code impact`: где именно это будет жить в текущем `management`.
3. `Phase readiness`: что можно включать сейчас, что только в shadow, а что пока должно быть DORMANT.
4. `Operational safety`: как не сломать деньги, мотивацию, UX и инфраструктуру во время внедрения.

## 8. Итоговый тезис
Финальный `management` subdomain должен стать не просто панелью статистики и не просто CRM-экраном.

Он должен стать:
- CRM-ядром текущей команды;
- execution OS для менеджера;
- admin control center для супервайзинга, выплат и корректирующих действий;
- low-noise системой follow-up и reminders;
- explainable score engine, которая не карает за отсутствие ещё не внедрённых компонентов;
- и документированным, безопасным фундаментом для следующего этапа: построения implementation plan и реального внедрения в код.
