# IP Telephony, QA and Supervisor Layer

## 1. Роль этого файла
Этот документ фиксирует telephony/QA слой как пошаговое расширение management-системы, а не как скрытую зависимость первой реализации.

Главный принцип:
- телефония важна;
- телефония не должна ломать Phase 0;
- всё, что зависит от записей и call duration, должно оставаться нейтральным до фактического запуска интеграции.

## 2. Текущий статус и главный вывод
Сейчас менеджеры работают без production IP-телефонии. Значит:
- `VerifiedCommunication` остаётся `DORMANT`;
- QA scorecard остаётся `DORMANT`;
- DMT не может требовать звонки `>30s`;
- telephony данные не могут участвовать в payroll truth.

## 3. Финальная phase-модель

### 3.1 Phase 0: Manual fallback
Что реально делаем сейчас:
- готовим модели и API-слой;
- разрешаем manual / CRM-backed proxy signals;
- не включаем telephony metrics в деньги;
- используем telephony only as architectural target.

### 3.2 Phase 1: Soft launch
После подключения провайдера:
- начинаем принимать webhook records;
- связываем calls с `Client` по телефону;
- считаем `VerifiedCommunication` как shadow/admin-visible ось;
- QA пока остаётся выборочным и coaching-oriented.

### 3.3 Phase 2: Supervisor mode
После стабилизации записи звонков:
- появляется полноценный supervisor queue;
- QA rubric становится repeatable;
- возможны calibration sessions;
- часть telephony evidence может участвовать в production trust, но не в raw punitive fashion.

### 3.4 Phase 3: AI assist / enriched coaching
Только после накопления достаточного call corpus:
- AI summaries;
- talk-pattern analytics;
- coaching hints;
- optional script-vs-improvisation diagnostics.

## 4. Data model

### 4.1 Минимальная основа
Нормативно нужен минимум такой слой:
```python
class CallRecord(models.Model):
    client = models.ForeignKey("Client", on_delete=models.CASCADE, related_name="call_records")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    source = models.CharField(max_length=20, default="manual")
    started_at = models.DateTimeField()
    duration_seconds = models.PositiveIntegerField(default=0)
    direction = models.CharField(max_length=10, choices=[("in", "Incoming"), ("out", "Outgoing")])
    outcome = models.CharField(max_length=64, blank=True)
    recording_url = models.URLField(blank=True)
    provider_call_id = models.CharField(max_length=120, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
```

### 4.2 Что ещё пригодится
- `TelephonyWebhookLog` / similar inbox table для raw webhooks;
- `CallQAReview`;
- optional `CallTag` / rubric result storage;
- links from `CallRecord` to follow-up and disputes.

## 5. Provider strategy

### 5.1 Что реально важно
Выбор провайдера определяется не красивым набором маркетинговых обещаний, а следующими критериями:
- webhook support;
- recording access;
- стабильная привязка к номеру;
- acceptable cost for Ukraine;
- простота эксплуатации на вашем текущем хостинге и доменной схеме.

### 5.2 Shortlist как planning-layer
Для дальнейшего planning можно держать shortlist:
- `Binotel`
- `Ringostat`
- `Stream Telecom`
- `Zadarma`

Но конкретный выбор не должен блокировать Phase 0 и Phase 1 preparation work.

## 6. Verified communication rules

### 6.1 До подключения телефонии
Нельзя считать call duration, connect rate и QA в боевом контуре.

Допустимые proxy-сигналы:
- CRM update;
- отправка сообщения;
- email / КП;
- follow-up completion.

### 6.2 После подключения
Минимальная telephony truth:
- provider-confirmed call exists;
- phone matched to known client;
- duration stored;
- timestamp stored.

### 6.3 Meaningful call
Боевой threshold meaningful call:
- `>30s` only after telephony is ACTIVE;
- короткие соединения могут учитываться как touch evidence, но не как полноценный quality event.

### 6.4 Short-call integrity defaults
Чтобы telephony не стала лёгким способом "набить касания":
- `<15s` не могут закрывать `not_interested`, `thinking`, `offer sent` или `order`;
- `<30s` допускают только weak outcomes, если recording/QA не доказывают meaningful exchange;
- weak outcomes по умолчанию: `missed`, `busy`, `voicemail`, `secretary`, `wrong_number`;
- short call + immediate CRM success outcome without evidence должны уходить в mismatch review.

## 7. Omni-touch и short-call handling

### 7.1 Phase 0 omni-touch
До телефонии допускается proxy-связка:
- CRM activity;
- messenger/email touch;
- narrow time window between them.

Это admin/coaching сигнал, а не commission truth.

### 7.2 Phase 1+ omni-touch
После телефонии можно связывать:
- short call;
- follow-up message;
- email / КП;
- next-step update.

Но omni-touch не должен становиться лёгким способом набить score.

## 8. QA contour

### 8.1 Что оцениваем
QA scorecard должен оценивать:
- ясность открытия разговора;
- квалификацию потребности;
- fit и clarity оффера;
- работу с objection handling;
- корректность next step;
- точность фиксации результата;
- соответствие policy and brand tone.

### 8.2 Что не делаем
- не превращаем QA в субъективный инструмент наказания;
- не привязываем деньги к raw QA before calibration;
- не считаем QA обязательной частью первой реализации.

### 8.3 Calibration
QA начинает влиять только после:
- стабильной записи разговоров;
- понятной rubric;
- calibration sessions;
- inter-rater agreement на приемлемом уровне.

### 8.4 Call Competency Profile
Coaching-safe слой `Call Competency Profile` сохраняется как отдельная supervisor/admin surface.

Он нужен для:
- coaching;
- learning path;
- explanation, почему QA pattern повторяется;
- script evolution;
- calibration between reviewers.

Он не нужен для:
- прямого payroll multiplier;
- personality claims;
- публичной стигматизации менеджера.

Стартовые измерения:
- opening quality;
- discovery depth;
- offer clarity;
- objection handling;
- next-step commitment;
- listening balance;
- brand tone and professionalism;
- empathy / rapport.

### 8.5 Reliability thresholds
QA может становиться score-sensitive только после явной проверки reliability:
- `kappa >= 0.80` -> QA reliable;
- `0.60 <= kappa < 0.80` -> coaching-only zone;
- `kappa < 0.60` -> stop score-sensitive QA usage until recalibration.

Даже при reliable QA:
- one harsh review must not change money by itself;
- disagreement patterns between reviewers должны быть видимы в supervisor analytics;
- tiny samples не дают права делать payroll-sensitive выводы.

### 8.6 Recording retention
Recording retention policy должна быть зафиксирована заранее, а не оставлена "на потом":
- active storage = `90 дней`;
- archive = `12 месяцев`;
- legal hold = until dispute resolved;
- delete after retention window if no legal/business hold.

## 9. Supervisor layer

### 9.1 Supervisor actions
Нормативные live actions:
- `monitor`;
- `whisper`;
- `barge`.

Каждое действие логируется с:
- reviewer/admin;
- call id;
- timestamp;
- reason;
- follow-up coaching outcome where applicable.

### 9.2 Что видит супервайзер / админ
- queue новых звонков на review;
- flagged short calls;
- повторяющиеся bad outcomes;
- coaching notes;
- dispute-related evidence;
- call competency profile;
- QA reliability state;
- script-vs-improvisation diagnostics when data is sufficient.

### 9.3 Что видит менеджер
- собственные review outcomes;
- понятные coaching notes;
- no public humiliation surfaces.

## 10. Интеграция с trust и MOSAIC

### 10.1 Production rule
Telephony и QA до maturity не имеют права штрафовать production score.

### 10.2 После maturity
- `VerifiedCommunication` может стать `ACTIVE`;
- call evidence может мягко участвовать в `trust_production`;
- QA остаётся bounded и сначала проходит через `diagnostic/shadow` stage.

## 11. Execution model на текущем хостинге
Telephony ingestion и post-processing должны быть совместимы с вашим стеком:
- webhook endpoint -> DB log;
- `management command` для обработки накопленных записей;
- cron scheduling;
- retry and error capture in DB.

Нельзя делать ставку на Celery/Redis как обязательный первый слой.

## 12. Приземление в текущий код

### 12.1 Основные точки будущего внедрения
- `management/models.py` — `CallRecord`, webhook-log, QA review, supervisor action log and retention metadata;
- `management/urls.py` и `views.py` — webhook endpoint(s);
- `management/stats_service.py` — future verified communication axis and diagnostic hints;
- `management/templates/management/stats.html` и admin surfaces — telephony widgets and QA panels;
- `management/management/commands/` — webhook processing / reconciliation jobs.

### 12.2 Что нельзя делать в первой реализации
- нельзя требовать meaningful calls без telephony;
- нельзя включать telephony-heavy trust в production before rollout;
- нельзя делать QA прямым payroll gate до калибровки.
