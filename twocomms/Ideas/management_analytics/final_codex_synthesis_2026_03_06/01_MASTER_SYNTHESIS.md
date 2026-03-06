# Master Synthesis

## 1. Что было лучшим у каждого агента

| Тема | Лучшее у Gemini | Лучшее у Codex | Лучшее у Opus/HES | Финальный выбор |
|---|---|---|---|---|
| Справедливость скоринга | EV по типу базы | hard gate + trust | B2B-калибровка и 0-100 heatmap | EV-aware score + trust + staged gate |
| Anti-abuse | short-call routing, trust ceiling без телефонии | trust tiers, mandatory validations, audit trail | provisional logic, velocity cap, follow-up discipline | Codex backbone + Opus cadence + Gemini telephony rules |
| KPI и зарплата | 2.5% new / 5% repeat, portfolio logic | dual KPI, promotion/readiness, unit economics | business fit для cold B2B | 2.5/5 + dual KPI + portfolio health |
| Дедупликация | Smart merge ideas | clear duplicate decision flow | глубокая проблема дублей и reminder layer | identity graph + exact/likely/conflict duplicates |
| Интерфейс | Tamagotchi, salary simulator, golden hour, no-touch report | role separation, worklists, explainability | heatmap и workflow focus | action-first UI + portfolio UX + admin action center |
| Телефония | phased adoption, x1.5 trust bonus, forced outcome | graceful degradation, rollout safety | data model, provider comparison, operational fit | phased IP rollout + supervisor QA contour |
| Alerts | coaching and scripts | no-report policy, severity, dedupe keys | reminder cadence and follow-up logic | event ladder with low-noise escalation |
| Implementation readiness | слабая | сильнейшая | средняя | берём Codex как каркас |

## 2. Что просил пользователь и что зафиксировано

Ниже список вещей, которые обязательно должны дожить до внедрения:
- сильное улучшение производительности менеджеров,
- прозрачная отчётность для менеджера и администратора,
- KPI и расчёт зарплаты,
- проверка базовых требований и дисциплины,
- интеллектуальная система советов на статистике,
- антидубляж,
- продуманная система перезвонов,
- система напоминаний,
- дизайн и интерфейс нового уровня,
- IP-телефония с прослушкой, статистикой и оценкой звонков администратором,
- подготовка к внедрению на subdomain management,
- сохранение уже имеющегося контекста, а не выдумывание CRM с нуля.

## 3. Что сохраняем без изменений

- `магазин добавлен = уже оплатил` остаётся hard verified событием.
- `2.5% первый заказ / 5% повторный` остаётся ядром мотивации.
- обязательные причины для слабых исходов остаются.
- `manager view` и `admin view` разделяются.
- DTF не смешивается в одну общую цифру с основным wholesale management.
- напоминания и советы обязаны быть evidence-based.

## 4. Что улучшаем принципиально

### 4.1 Формула эффективности
Нельзя брать ни чистый `ELO`, ни чистый `HES`, ни чистый `MMR`.

Финальная система должна:
- учитывать сложность базы,
- отделять verified и self-reported сигналы,
- не разрешать высокий score без верифицированного прогресса,
- не ломаться на маленькой команде из 3-6 менеджеров.

### 4.2 Лидерборд
Для текущего размера команды чистый weekly `ELO` слишком шумный.

Финальное решение:
- менеджер видит rolling personal progress,
- менеджер видит `shadow rival`,
- админ видит full ranking,
- публичная жёсткая лестница включается только если команда вырастает минимум до 5-7 активных менеджеров.

### 4.3 Напоминания
Скан каждые 30 минут на всё подряд создаёт fatigue.

Финальное решение:
- reminder ladder по событиям,
- отдельный `T-15m`,
- отдельный `overdue`,
- отдельный `EOD breach`,
- отдельный `Day-2` и `Day-3` escalation,
- admin получает не спам, а собранные action queues.

### 4.4 Retention и ownership клиента
Gemini правильно увидел главное: менеджер должен мыслить клиентами как портфелем, а не одноразовыми продажами.

Но автоматическая токсичная кража базы плоха.

Финальное решение:
- `portfolio health`,
- `orphan risk`,
- `rescue eligible`,
- reassign только по правилу + лог + при необходимости admin approval.

## 5. Что отбрасываем

- автоматический `Shark Pool` без контроля,
- `Doomsday Screen` с блокировкой экрана,
- MMR без предела и без seasonal reset,
- слишком короткий 5+3 как единственный тест реальной коммерческой пригодности,
- чистый score только по активности,
- штрафы за дисциплину без admin verification,
- write-heavy DTF v1,
- советы без объяснения сигналов,
- сравнение всех менеджеров в одном публичном humiliating leaderboard.

## 6. Новая общая идея поверх всех агентов

Новая система должна оценивать не просто звонки и не просто заказы, а четыре контура:

1. `New Business`
Факт первого подключения, прогресс по воронке, адекватность работы с холодной базой.

2. `Portfolio`
Повторные заказы, здоровье клиентского портфеля, риск оттока, своевременные касания.

3. `Execution`
Перезвоны, причины отказов, отчёты, качество данных, отсутствие дублей и ложных событий.

4. `Call Quality`
Что реально происходит в разговоре после перехода на IP-телефонию: запись, QA rubric, admin score, coaching notes.

Именно это делает систему сильнее любой из трёх исходных по отдельности.

## 7. Итоговый продуктовый тезис

Финальный management subdomain не должен быть просто “панелью статистики”.
Он должен стать:
- CRM ядром,
- execution OS для менеджера,
- QA-пультом для администратора,
- pay and KPI engine,
- low-noise reminder system,
- системой удержания клиентского портфеля,
- контуром объяснимой аналитики.
