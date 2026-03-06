# MOSAIC Score System

## 1. Почему новая система нужна

У прошлых подходов были сильные стороны, но ни один не закрывал всё сразу:
- `Gemini` слишком силён в мотивации, но слаб в production safety.
- `Codex` очень силён в rollout и защите, но недокалиброван для холодного B2B.
- `Opus/HES` ближе всех к бизнес-логике, но не доводит implementation contract до конца.

`MOSAIC` фиксирует итоговую систему, где:
- есть справедливость к источнику базы,
- есть ограничение на искусственно раздутый score,
- есть trust-модель,
- есть portfolio logic,
- есть объяснимый UI.

## 2. Финальные сущности score

### 2.1 Менеджерский итог
`manager_score_day` нужен менеджеру как понятная оперативная цифра 0..115.

### 2.2 Админский итог
`admin_score_day` нужен админу как контрольная цифра с ROI, QA и incident-risk.

### 2.3 Сравнительный слой
Вместо чистого ELO по умолчанию используем `Seasonal Ladder`.

Это безопаснее для маленькой команды:
- `70%` — rolling 28-day normalized score,
- `30%` — improvement vs own baseline.

Если активных менеджеров становится `>= 7`, можно включить optional comparative `Glicko/ELO` layer.

## 3. Ядро MOSAIC

### 3.1 Базовая формула дня
`base_day = 0.35 * Result + 0.20 * SourceFairness + 0.15 * Process + 0.10 * FollowUp + 0.10 * DataQuality + 0.10 * VerifiedCommunication`

Все оси нормализуются в `0..100`.

### 3.2 Оси

#### Result
Содержит только hard или near-hard outcomes:
- новые оплаченные подключения,
- оплаченные повторные заказы,
- созданные и подтверждённые invoice milestones,
- conversion from processed to paid/approved outcome.

#### SourceFairness
Это главное улучшение поверх Codex и Opus.

Логика:
- холодная база не равна тёплой,
- XML не равен вручную найденному лиду,
- warm inbound и reactivation не должны оцениваться одинаково с cold outbound.

Формула уровня недели:
`fairness_ratio = actual_verified_progress / expected_verified_progress_by_source_mix`

Источник даёт ожидаемую норму:
- `cold_xml`: baseline very low,
- `parser_cold`: low,
- `manual_hunt`: medium,
- `warm_reactivation`: high,
- `hot_inbound`: highest.

Итог:
- менеджер на сложной базе не получает ложный провал,
- менеджер на тёплой базе не прячется за общий объём.

#### Process
Показывает, движет ли менеджер лидов дальше:
- next action set,
- stage progression,
- CP linkage,
- approved invoice flow,
- no stalled pipeline clusters.

#### FollowUp
Показывает дисциплину обещаний:
- callback on time,
- reschedule before breach,
- stale shops handled,
- test shops reviewed on time.

#### DataQuality
Показывает, насколько данные пригодны для бизнеса:
- valid reasons,
- no duplicate stuffing,
- no blank/garbage outcomes,
- clean ownership changes,
- no suspicious overrides.

#### VerifiedCommunication
Показывает долю верифицируемых взаимодействий:
- email CP logs,
- telephony calls,
- system timestamps,
- confirmed follow-up completion,
- QA-reviewed call outcomes.

## 4. Гейты

Жёсткий gate из Codex нужен, но в B2B его надо сделать многоуровневым.

### 4.1 Gate tiers

| Сценарий | Потолок |
|---|---|
| Есть оплаченная или админ-подтверждённая ключевая конверсия | `100` |
| Нет оплаты, но есть verified commercial progress | `78` |
| Есть только self-reported activity и слабый verified progress | `60` |
| `3+` дня без verified progress + breaches по callback | `45` |

### 4.2 Что считается verified commercial progress
- подтверждённый CP-email link,
- назначенный и выполненный callback,
- админ-подтверждённая invoice stage,
- QA-confirmed call outcome,
- shop contact logged against real shop,
- accepted test growth package step.

Это сильнее старого hard gate, потому что:
- не демотивирует B2B-cold cycle,
- но не позволяет “набить зелёную зону” на пустых кликах.

## 5. Trust coefficient

### 5.1 Диапазон
`trust_coeff = 0.70 .. 1.10`

### 5.2 Формула v1
`trust = clamp(0.70, 1.10, 0.78 + 0.18*verified_ratio + 0.08*qa_reliability + 0.06*reason_quality - 0.06*duplicate_abuse - 0.06*anomaly_penalty)`

### 5.3 Сигналы trust
- verified ratio,
- доля short-call mismatch,
- duplicate override frequency,
- одинаковые причины отказа,
- overdue callback streak,
- manual override without evidence,
- QA disagreement rate.

## 6. Итоговые score

### 6.1 Manager
`manager_score_day = min(base_day, gate_cap) * trust_coeff + portfolio_bonus`

### 6.2 Admin
`admin_score_day = 0.80 * manager_score_day + 0.10 * roi_score + 0.10 * qa_score`

### 6.3 Portfolio bonus
Это улучшение поверх всех трёх агентов.

Нельзя делать retention просто побочным эффектом 5%.
Нужно считать здоровье портфеля.

`portfolio_bonus = 0..10`

Он начисляется только если одновременно:
- `portfolio_health >= threshold`,
- `reactivation discipline` в норме,
- нет orphan negligence,
- нет критичных QA incidents.

## 7. Heatmap

Heatmap пользователя остаётся обязательной частью системы.

### 7.1 Цвета
- `gray` — нет осмысленной активности,
- `red` — score `< 30`,
- `orange` — `30..49`,
- `yellow` — `50..69`,
- `green` — `70..89`,
- `dark_green` — `90+`.

### 7.2 Что показывать по hover
- итоговый score,
- main blocker of the day,
- best action of the day,
- verified progress count,
- missed callback count.

## 8. Golden Hour

Идею Gemini сохраняем, но делаем аналитической, а не gimmick.

Система раз в неделю считает:
- часы с лучшей конверсией,
- часы с лучшим callback completion,
- часы с лучшим repeat reactivation.

Менеджеру показывается:
- `ваше окно силы`,
- `ваше окно провалов`,
- `лучшее время для cold`,
- `лучшее время для portfolio reactivation`.

## 9. Seasonal Ladder

Вместо unstable ELO по умолчанию:
- сезон = `28 дней`,
- score = `70% rolling MOSAIC average + 30% improvement vs previous season`,
- есть ранги `Bronze / Silver / Gold / Platinum`, но без бесконечной инфляции.

Season reset:
- сохраняет историю,
- обнуляет соревновательный азарт,
- не превращает ветерана в вечного победителя.

## 10. Что менеджер должен понимать

Score обязан быть explainable.

Каждый день менеджер видит:
- итог,
- что толкнуло score вверх,
- что его ограничило,
- какой gate сработал,
- какие 3 действия быстрее всего поднимут tomorrow score.

Если система не объяснима, она проиграет даже при математической правильности.
