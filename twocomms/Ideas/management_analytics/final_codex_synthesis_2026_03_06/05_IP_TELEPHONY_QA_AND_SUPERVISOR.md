# IP Telephony, QA and Supervisor Layer

## 1. Обязательное требование пользователя

IP-телефония должна давать:
- запись разговоров,
- прослушку администратором,
- ручную QA-оценку администратором,
- статистику звонков,
- контроль качества,
- coaching and dispute evidence.

То есть телефония в TwoComms не “ещё один канал”.
Она должна стать verified source of truth.

## 2. Что изменено после Opus-аудита

После аудита я добавил:
- provider matrix под украинский рынок,
- recording retention policy,
- inter-rater reliability thresholds,
- конкретные short-call rules,
- зрелый supervisor contour без premature AI overkill,
- coaching-safe competency profile вместо сырого "DNA payroll",
- script-vs-improvisation analytics как будущий quality insight, а не как штраф.

## 3. Rollout phases

### 3.1 Phase 0: manual fallback
- manual call outcomes allowed,
- trust ceiling limited,
- no punitive QA without strong evidence.

### 3.2 Phase 1: soft launch
- click-to-call,
- webhook ingest,
- recordings,
- post-call modal,
- call-to-client linking,
- admin playback.

### 3.3 Phase 2: supervisor mode
- monitor,
- whisper,
- barge,
- QA scorecards,
- calibration sessions,
- disagreement tracking.

### 3.4 Phase 3: AI assist
Только после стабильного capture quality:
- transcription,
- talk/listen balance,
- silence ratio,
- keyword spotting,
- coaching hints,
- auto-summary.

## 4. Provider matrix for Ukraine

Точные коммерческие условия надо перепроверять перед контрактом.
Ниже не прайс-лист, а decision matrix.

| Provider | Webhooks | Recording API | Supervisor features | Browser softphone | CRM fit | Cost band | Decision note |
|---|---|---|---|---|---|---|---|
| `Binotel` | strong | strong | strong | yes | strong | medium/high | safest business fit if supervisor tooling confirmed |
| `Ringostat` | strong | strong | medium | yes | strong | medium/high | best analytics orientation |
| `UniTalk` | medium/strong | strong | verify manually | yes | medium | medium | good if supervisor features pass verification |
| `Zadarma` | medium | medium | weak | yes | medium/weak | low | budget fallback, not ideal for QA-heavy mode |

### Recommended selection rule
- если нужен быстрый production-safe supervisor contour, сначала проверять `Binotel`,
- если критична аналитика и marketing/call intelligence, смотреть `Ringostat`,
- `UniTalk` брать только после ручной проверки supervisor and webhook maturity,
- `Zadarma` рассматривать только как budget fallback.

## 5. QA contour

### 5.1 Core entities
- `TelephonyCall`
- `TelephonyCallRecording`
- `TelephonyCallQAReview`
- `TelephonyQACalibrationSession`
- `TelephonySupervisorActionLog`
- `TelephonyProviderSyncLog`

### 5.2 QA scorecard

| Block | Weight |
|---|---:|
| Greeting and opening | `10` |
| Need discovery | `20` |
| Offer fit and clarity | `15` |
| Objection handling | `15` |
| Next step commitment | `15` |
| Outcome accuracy in CRM | `10` |
| Brand tone and professionalism | `15` |

### 5.3 QA impact
QA:
- влияет на trust,
- открывает coaching tasks,
- влияет на accelerator eligibility,
- влияет на admin score,
- но не должен сам по себе instantly сносить зарплату.

### 5.4 Call competency profile
Идею “портрета менеджера” я принимаю, но перевожу её в production-safe формат.

Используем не `DNA`, а `Call Competency Profile`.

Он нужен для:
- coaching,
- quality review,
- learning path,
- supervisor explanation,
- script evolution.

Он не нужен для:
- прямого payroll truth,
- мгновенных санкций,
- публичной стигматизации.

Стартовые измерения:
- opening quality,
- discovery depth,
- offer clarity,
- objection handling,
- next-step commitment,
- listening balance,
- brand tone and professionalism,
- empathy / rapport.

### 5.5 Script vs improvisation analytics
Поздний, но полезный слой:
- supervisor помечает `script-followed` или `meaningful-deviation`,
- система сравнивает outcome quality у этих двух режимов,
- если deviation системно лучше, это повод улучшить script,
- если script лучше, это повод усиливать discipline.

Это аналитика для развития команды, а не штрафной слой.

## 6. Calibration and reliability

### 6.1 Cadence
- `1` calibration session weekly,
- `5` shared calls minimum,
- explicit rubric review,
- discrepancy notes.

### 6.2 Inter-rater reliability
Используем базовые thresholds:
- `kappa >= 0.80` = QA reliable,
- `0.60 <= kappa < 0.80` = coaching-only zone,
- `kappa < 0.60` = stop score-sensitive QA usage until recalibration.

Это сильно уменьшает человеческий фактор и “рандомную строгость” разных админов.

### 6.3 Human-factor limits
Чтобы QA не превратился в субъективную власть администратора:
- no score-sensitive QA use below reliable calibration,
- no payroll-sensitive use on tiny sample,
- one harsh review never changes money by itself,
- every score-sensitive QA action must have recording and rubric evidence,
- disagreement patterns between reviewers must be visible in supervisor analytics.

## 7. Recording retention

### 7.1 Policy
- active storage = `90 дней`,
- archive = `12 месяцев`,
- legal hold = until dispute resolved,
- delete after retention window if no legal/business hold.

### 7.2 Why
- хватает для QA, disputes and coaching,
- не раздувает storage бесконтрольно,
- оставляет доказательную базу для конфликтов по commission and ownership.

## 8. Short-call and outcome integrity

### 8.1 Rules
- `< 15 сек` нельзя ставить `not_interested`, `thinking`, `order`, `offer sent`,
- `< 30 сек` допускает только weak outcomes unless recording proves meaningful exchange,
- allowed weak outcomes:
- `missed`,
- `busy`,
- `voicemail`,
- `secretary`,
- `wrong_number`.

### 8.2 Meaningful contact
Для телефонии meaningful contact = answered call `>= 30 секунд` или QA-validated shorter meaningful exchange.

## 9. Supervisor actions

Нужны режимы:
- `monitor`,
- `whisper`,
- `barge`.

Каждое действие логируется:
- кто,
- когда,
- на каком звонке,
- с какой целью,
- был ли coaching outcome.

## 10. Manager and admin statistics

### 10.1 Manager
- total calls,
- answered,
- talk time,
- callback creation rate,
- short-call ratio,
- QA trend,
- top hours.

### 10.2 Admin
- queue load,
- answered vs missed,
- quality variance,
- conversion by call type,
- call-to-outcome mismatch,
- suspicious short-call patterns,
- calibration reliability,
- competency-profile distribution,
- script-vs-improvisation comparison where enough data exists.

## 11. What not to do

- не строить punitive QA before calibration,
- не включать AI transcription as first milestone,
- не выбирать провайдера только по цене,
- не смешивать raw call activity with trusted sales outcomes,
- не считать telephony rollout complete без dispute evidence and playback tooling,
- не превращать competency profile в прямой зарплатный multiplier,
- не делать AI-derived personality claims без very high evidence.
