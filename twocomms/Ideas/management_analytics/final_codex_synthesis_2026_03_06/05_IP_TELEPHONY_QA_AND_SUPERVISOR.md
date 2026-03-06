# IP Telephony, QA and Supervisor Layer

## 1. Обязательное требование пользователя

IP-телефония должна поддерживать:
- запись разговоров,
- прослушку администратором,
- выставление баллов администратором,
- статистику по звонкам,
- контроль качества обработки,
- дальнейший coaching.

Значит телефония в TwoComms не просто канал связи.
Она должна стать ещё одним verified data source для CRM.

## 2. Финальная архитектурная цель

Нужны четыре слоя:
- `Call events`,
- `Call recordings and metadata`,
- `Supervisor actions`,
- `QA scoring and coaching`.

## 3. Режимы rollout

### 3.1 Phase 0: manual fallback
До полноценной телефонии:
- ручные call outcomes разрешены,
- trust ceiling ограничен,
- quality score строится с поправкой на self-reported nature.

### 3.2 Phase 1: soft launch
- click-to-call из CRM,
- входящие/исходящие события через webhook,
- запись разговоров,
- post-call modal,
- связка звонка с `Client`/`Lead`,
- админ видит playback и metadata.

### 3.3 Phase 2: supervisor mode
- live monitor,
- whisper,
- barge,
- queue statistics,
- scorecards,
- calibration sessions.

### 3.4 Phase 3: AI assist
Только после стабилизации ядра:
- transcription,
- keyword spotting,
- silence ratio,
- talk/listen balance,
- objection hints,
- auto-summary.

AI не должен идти раньше стабильной записи и webhook hygiene.

## 4. Что брать у агентов

### Из Gemini
- phased adoption,
- post-call forced outcome,
- short-call routing,
- incentive для перехода на verified channel.

### Из Codex
- graceful degradation,
- rollout safety,
- trust-aware scoring,
- admin-only disciplinary consequences.

### Из Opus
- data model,
- provider comparison,
- реалистичное место телефонии внутри общей CRM.

## 5. Рекомендованный call QA контур

### 5.1 Новые сущности
- `TelephonyCall`
- `TelephonyCallRecording`
- `TelephonyCallQAReview`
- `TelephonyQACalibrationSession`
- `TelephonySupervisorActionLog`
- `TelephonyProviderSyncLog`

### 5.2 QA scorecard
Админ/супервайзер оценивает звонок по рубрике:

| Блок | Вес |
|---|---|
| Greeting and opening | `10` |
| Need discovery | `20` |
| Offer fit and clarity | `15` |
| Objection handling | `15` |
| Next step commitment | `15` |
| Outcome accuracy in CRM | `10` |
| Brand tone and professionalism | `15` |

Итог:
- `qa_score_call = 0..100`,
- менеджер видит coaching summary,
- админ видит raw sub-scores.

### 5.3 QA impact
`qa_score` не должен сносить зарплату сам по себе.

Он влияет на:
- trust,
- coaching queue,
- accelerator eligibility,
- portfolio bonus eligibility,
- admin score.

## 6. Calibration

Одна из самых важных недостающих тем в исходных документах.

### 6.1 Правило
Если два супервайзера оценивают один звонок по-разному, система должна не спорить, а калиброваться.

### 6.2 Минимальный ритм
- `1` недельная calibration session,
- `5` общих звонков на сессию,
- variance threshold,
- фиксация rubric updates.

Без calibration QA превращается в субъективную лотерею.

## 7. Правила short-call and outcome integrity

Сильную идею Gemini оставляем.

Если звонок:
- слишком короткий,
- не был отвечен,
- завершился до meaningful contact,

то система не даёт выбрать outcome уровня:
- `not_interested`,
- `thinking`,
- `offer sent`,
- `order`.

Разрешённые исходы:
- `missed`,
- `busy`,
- `voicemail`,
- `secretary`,
- `wrong_number`.

## 8. Supervisor actions

Нужны три live режима, если провайдер их поддерживает:
- `monitor`,
- `whisper`,
- `barge`.

Каждое действие логируется:
- кто включил,
- когда,
- на каком звонке,
- с какой целью,
- был ли coaching outcome.

## 9. Статистика по звонкам

### 9.1 Менеджер
Видит:
- total calls,
- answered,
- talk time,
- callback creation rate,
- short-call ratio,
- QA trend,
- top hours.

### 9.2 Админ
Видит:
- queue load,
- missed vs answered,
- quality variance by manager,
- conversion by call type,
- silent or suspicious patterns,
- call-to-outcome mismatch.

## 10. Provider selection principle

Итоговый выбор провайдера должен идти не только по цене.

Фильтр обязательных возможностей:
- webhook events,
- call recording API,
- call control API,
- supervisor functions,
- browser softphone or stable app,
- stable number mapping to manager,
- recording retention,
- exportability.

Если дешёвый провайдер не даёт supervisor mode и стабильные webhooks, он не решит задачу пользователя.

## 11. Финальный тезис

Телефония должна стать вторым позвоночником системы после CRM.
Первый позвоночник — данные о клиентах.
Второй — фактическая правда о коммуникации.
