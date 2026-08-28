# Production-аудит спама «техническая задержка» в Instagram-боте

Дата расследования: 27 августа 2026 года
Режим: только read-only расследование и подготовка handoff-документа; код не изменялся, commit/push/deploy не выполнялись.
Production checkout: /home/qlknpodo/TWC/TwoComms_Site/twocomms
Production SHA на момент финального снимка: cb4d6463b3f3adcccb0402e2adb32870ed6e5636 (main)
Время финального серверного снимка: 2026-08-27T17:34:34+03:00

Важно о времени: Django/MariaDB timestamps в примерах ниже показаны в UTC (+00:00); рядом указано время Europe/Kyiv (UTC+03:00), если это помогает читать хронологию.

---

## 1. Короткий вывод для implementation-planner

Наблюдаемая проблема реальна и состоит не из одной ошибки Gemini. Это цепочка из четырёх взаимно усиливающих дефектов:

1. Provider degradation действительно происходил. В production были реальные HTTP 503 UNAVAILABLE, HTTP 429 RESOURCE_EXHAUSTED и requests.ReadTimeout; это не только ошибка интерфейса и не только «переподключение».
2. Каждый новый inbound при provider outage заново отправляет один и тот же customer-facing holding. Holding-текст выбирается без client-scoped дедупликации и без состояния «для этого клиента уже отправлено сообщение о текущем инциденте». Поэтому несколько новых сообщений клиента за несколько минут дали несколько одинаковых извинений.
3. Recovery после holding имеет отдельную попытку генерации и сам принудительно добавляет apology-prefix. В переписке это проявилось как: «Вибачте за технічну затримку. Вибачте за затримку з відповіддю! ...».
4. Долгие последовательные provider calls блокируют общий daemon loop, а heartbeat обновляется только после завершения work cycle. На фоне 34–44-секундных цепочек Gemini watchdog видит stale heartbeat, фиксирует daemon_lock_stale, а production ledger показывает около сотни запусков демона за день.

Дополнительный amplification factor — manager Telegram alerts. В системе есть throttle для drain-цикла, но notify_manager с deliver_immediately=True отправляет многие события напрямую и обходит этот общий flow limiter. Кроме того, throttle реализован как неатомарный cache.get() + cache.set() на FileBasedCache.

### Итоговая формулировка

Проблема не должна решаться простым удалением текста «извините за задержку» или бездумным увеличением timeout. Нужен отдельный durable outage/incident state на уровне клиента/эпизода, один coalesced holding на инцидент, одна recovery-цель для актуального inbound, строгая политика «не более одного apology в logical turn», typed provider routing с явной project-group моделью, heartbeat/progress supervision и единый throttled notification outbox.

---

## 2. Границы и метод расследования

Проверены:

- production Git SHA, ветка, активный Python/Django runtime;
- реальные production settings через DJANGO_ENV_FILE=.env.production;
- MariaDB как authoritative runtime DB;
- текущий процесс run_instagram_bot --forever, cron и watchdog-файлы;
- InstagramBotLog, GeminiRequestAttempt, InstagramBotMessage, IgAiReplyRecoveryJob, IgBotNotification, IgFollowUpTask, InstagramBotTaskHeartbeat, GeminiKeyState и GeminiModelState;
- полная сохранённая переписка клиента _zhenya_963 (client_id=334);
- production-код live-reply, fallback/recovery, Gemini pool, daemon/watchdog и Telegram notification path;
- Context7 для официальных рекомендаций Gemini API, Requests и Django.

Не выполнялись:

- отправка искусственных сообщений клиенту в Meta/Instagram;
- тестовые customer-facing Send API события;
- изменение ключей, проекта Google Cloud, токенов Meta, cron, БД или кода;
- destructive cleanup старых recovery/notification rows;
- вывод секретов. SSH-секрет был взят локально из Keychain и передан только через env-based SSHPASS; значения ключей/API/токенов не выводились.

### Production evidence sources

Основные источники серверного снимка:

- MariaDB tables через Django shell: InstagramBotMessage, InstagramBotLog, GeminiRequestAttempt, IgAiReplyRecoveryJob, IgBotNotification, IgFollowUpTask, InstagramBotTaskHeartbeat, GeminiKeyState, GeminiModelState и IgClient.
- /home/qlknpodo/TWC/TwoComms_Site/twocomms/tmp/ig_bot_daemon.log — поток daemon events и live Gemini events.
- /home/qlknpodo/TWC/TwoComms_Site/twocomms/tmp/ig_bot_cron.log — watchdog stdout/stderr, включая daemon alive, spawn и CommandError.
- /home/qlknpodo/TWC/TwoComms_Site/twocomms/logs/check_ig_gemini_metadata_health.log — hourly metadata probes.
- /home/qlknpodo/TWC/TwoComms_Site/twocomms/ig_bot.log и django.log — дополнительные application traces.
- /home/qlknpodo/TWC/TwoComms_Site/twocomms/stderr.log* — Passenger/LSAPI и WSGI errors. Эти файлы важны для host/runtime контекста, но строки о Passenger child SIGKILL не считаются прямым доказательством убийства Instagram daemon.

---

## 3. Production baseline на финальном снимке

| Факт | Значение |
|---|---|
| Git branch/SHA | main / cb4d6463... |
| Python | 3.14.7 |
| Django | 6.1 |
| DB engine | django.db.backends.mysql (MariaDB production) |
| Django cache | django.core.cache.backends.filebased.FileBasedCache |
| CONN_MAX_AGE | 0 |
| Bot enabled | true |
| AI enabled | true |
| Configured model | gemini-3.7-flash |
| Polling backstop | receive_via_poll=false (event-driven webhook) |
| Gemini aliases | 6/6 configured; redacted fingerprints различаются |
| GEMINI_KEY_PROJECT_GROUPS | не задан (runtime возвращает {}) |
| Current daemon | один run_instagram_bot --forever, финальный PID 888285 |
| Current watchdog heartbeat | fresh на финальном снимке |
| InstagramBotSettings.last_error | пусто, несмотря на live generation failures |
| Applied migrations | до management.0169_ig_followup_manager_approval |
| manage.py check | System check identified no issues (0 silenced) |

Важное различие: last_error singleton settings отражает не весь live provider incident, а отдельные operational paths. Поэтому dashboard может выглядеть зелёным, пока live generation получает 429/503/timeout.

---

## 4. Непосредственная переписка _zhenya_963

### 4.1. Состояние клиента

На финальном снимке:

- client_id=334;
- username _zhenya_963, display name zhenya;
- language uk;
- stage lead_manager;
- bot_paused=true, manager_takeover=true, paused_reason=manager_takeover;
- last_manager_message_at=2026-08-27T13:14:40.863Z;
- после takeover поздние inbound остаются observed/done и не получают автоматический ответ. Это правильная защитная граница, а не причина спама.

### 4.2. Хронология

| UTC | Kyiv | Row | Событие | Результат |
|---|---:|---:|---|---|
| 12:47:43 | 15:47:43 | 2730 | inbound: «А це не ваш бренд Полуничка?» | Входящее принято |
| 12:48:22 | 15:48:22 | — | Gemini provider failure | 3.7/3.6 цепочка исчерпала live budget |
| 12:48:23 | 15:48:23 | 2731 | customer holding | первое техническое извинение |
| 12:48:35 | 15:48:35 | 2732 | inbound: «Ви менеджер?» | Следующий ход получил 3.7 |
| 12:48:59 | 15:48:59 | 2733 | model reply | ответ о бренде/менеджере |
| 12:49:13 | 15:49:13 | 2734 | inbound: «Добре» | Следующий ход получил 3.7 |
| 12:49:23 | 15:49:23 | 2735 | model reply | «Гарного дня! Менеджер незабаром вам напише» |
| 12:49:42 | 15:49:42 | 2736 | inbound: «Можете розказати коротко що у вас в асортименті» | новый клиентский ход |
| 12:50:20 | 15:50:20 | 2737 | customer holding | второе одинаковое извинение |
| 12:53:11 | 15:53:11 | 2738 | recovery model reply | holding + recovery; apology повторён |
| 12:53:35 | 15:53:35 | 2739 | inbound: «Я спитав щоб знати просто що у вас» | новый ход во время degraded period |
| 12:54:16 | 15:54:16 | 2740 | customer holding | третье одинаковое извинение |
| 12:58:39 | 15:58:39 | 2741 | manager inbound | начат takeover |
| 13:51:42 | 16:51:42 | 2759 | поздний custom-print inbound | observed, без bot reply |
| 13:56:25 | 16:56:25 | 2760 | inbound «?» | observed, без bot reply |
| 14:05:02 | 17:05:02 | 2761 | inbound «?» | observed, без bot reply |

### 4.3. Что именно увидел клиент

Перед подключением менеджера клиент получил:

1. 2731: «Перепрошую за технічну затримку. Я відновлюю деталі й невдовзі відповім вам тут.»
2. 2733: нормальный ответ Gemini 3.7.
3. 2735: нормальный ответ Gemini 3.7.
4. 2737: тот же holding про техническую задержку.
5. 2738: «Вибачте за технічну затримку. Вибачте за затримку з відповіддю! ...».
6. 2740: тот же holding в третий раз.

Это не один Meta message, ошибочно повторённый UI: у 2731, 2737 и 2740 разные provider message IDs. Это три реально отправленных сообщения, инициированные тремя разными inbound rows, плюс отдельный recovery reply 2738.

### 4.4. Recovery state

| Recovery | Source | Holding | Status | Attempts | Причина/итог |
|---:|---:|---:|---|---:|---|
| 5 | 2730 | 2731 | cancelled | 1 | newer_inbound_or_manager_reply |
| 6 | 2736 | 2737 | sent | 3 | 2738 отправлен с provider receipt |
| 7 | 2739 | 2740 | failed | 3 | recovery_generation_failed |

Exact-once для одной recovery-цели в целом сработал. Но механизм не coalesce-ит несколько outage recovery jobs одного клиента, поэтому защищает от технического duplicate send, но не от UX-спама нескольких logically equivalent holding.

### 4.5. Системность

У client_id=335 в тот же период были три аналогичных holding rows (2727, 2729, 2754) и три recovery jobs. Следовательно, дефект общий, а не связан с конкретным текстом _zhenya_963.

---

## 5. Production-метрики и временное окно инцидента

### 5.1. Окно 12:20–13:20 UTC (15:20–16:20 Kyiv)

| Метрика | Значение |
|---|---:|
| Chat GeminiRequestAttempt rows | 71 |
| Top-level event=gemini level=error | 15 |
| gemini_fallback events | 6 |
| Customer apology/holding rows | 7 |
| stale_requeue | 2 |
| daemon_start | 8 |
| 3.7 successes | 6 |
| 3.7 HTTP 503 | 7 |
| 3.7 HTTP 429 | 23 |
| 3.7 ReadTimeout | 11 |
| 3.6 ReadTimeout | 19 |
| 3.5 ReadTimeout | 5 |

Успешные 3.7 ответы перемежались с длительными деградациями. Поэтому состояние могло выглядеть «иногда работает», но отдельный клиент во время provider incident получал несколько holding.

### 5.2. День 27 августа

На момент финального снимка:

- не менее 101 daemon_start и 99 daemon_spawn с полуночи UTC;
- 17 top-level Gemini error events;
- 8 gemini_fallback events;
- 7 customer apology rows за день;
- 3 stale_requeue;
- 3 Telegram ig_task_failure alerts по daemon_lock_stale;
- 2 Telegram ig_task_health alerts;
- 14 операционных Telegram notifications, не считая регистрационных: 2 ai_reply_fallback, 3 ai_reply_recovery_exhausted, 3 escalation, 3 ig_task_failure, 2 ig_task_health, 1 takeover.

Эти 14 событий не означают 14 повторов одного сообщения. Они показывают, что один degraded period создаёт много разных событий и они приходят в один management channel без достаточной incident aggregation.

---

## 6. End-to-end trace

### 6.1. Нормальный live path

    Meta webhook
      -> InstagramBotMessage(role=user, status=pending)
      -> _claim_next() / status=processing / attempts += 1
      -> _acquire_client_automation_lease()
      -> gemini_generate()
      -> _run_chat_with_pool()
      -> validated reply / fallback
      -> send_text() через Meta Send API
      -> model history row + receipt
      -> optional manager notification

### 6.2. Degraded path сейчас

    Gemini provider failure
      -> gemini_generate() returns None + failure_context[kind=provider_outage]
      -> build_ai_failure_fallback(row, provider_outage=True)
      -> _outage_holding_reply(language)       # всегда один текст
      -> outage_recovery_required=True
      -> schedule_recovery(row, activate=False)
      -> send_text(holding)
      -> activate recovery after holding receipt
      -> next inbound arrives
      -> same path starts again for new row
      -> second/third holding to same client

### 6.3. Главная архитектурная ошибка

schedule_recovery() делает dedupe по source_message (ig-ai-recovery:<source_id>). Это правильная защита exact-once для одной logical turn, но недостаточная политика для outage incident. Нет durable ключа вида:

    client + conversation episode + provider incident window

Система отвечает на вопрос «не повторить ли recovery одного source?» положительно, но не отвечает на вопрос «нужно ли вообще отправлять ещё один outage holding этому же клиенту через 30 секунд?».

---

## 7. Доказанные причины по слоям

### P0-A. Нет client-scoped suppression/coalescing для holding

Код: management/services/bot_reply_fallback.py:255–283, 339–374.

- _outage_holding_reply() возвращает одну фиксированную фразу для языка.
- build_ai_failure_fallback() выбирает этот текст для любого generic + provider_outage.
- Нет проверки уже отправленного holding, открытого provider incident, активной recovery для клиента, количества holding за окно или manager takeover.
- _rate_exceeded() ограничивает общий reply count, но не понимает, что holding — технический статус, а не содержательный ответ.
- _defer_for_gemini_cooldown() возвращает claim в pending, но не является customer-facing dedupe.

Production proof: client_id=334 получил rows 2731, 2737, 2740 за 5 минут 53 секунды; client_id=335 получил три аналогичных rows.

### P0-B. Recovery гарантирует apology, но не «один apology на logical turn»

Код: management/services/ig_ai_reply_recovery.py:43–53, 99–118, 659–688, 901–920.

- _ensure_recovery_apology() добавляет локализованный prefix при отсутствии узкого exact stem.
- Prompt recovery также требует начать с короткого извинения.
- Если holding уже доставлен, recovery всё равно является отдельным customer message и снова содержит apology.
- Семантически эквивалентные варианты («вибачте за очікування», «перепрошую, що довелося чекати») не удаляются.

Production proof: row 2738 начинается с двух apology-смыслов подряд.

### P0-C. Recovery повторно потребляет degraded Gemini pool

Код: ig_ai_reply_recovery.py:901–908; call_ai_analysis.py:780–1024.

- Holding отправляется после live failure.
- Recovery worker через 20 секунд и далее снова вызывает полноценный gemini_generate().
- MAX_RECOVERY_ATTEMPTS=3, retry base 20s, max 300s.
- При общем quota/provider incident recovery не имеет отдельной deterministic low-cost strategy.
- После трёх неудач создаётся ai_reply_recovery_exhausted manager alert.

Production proof: recovery 7 для source 2739 трижды завершил generation с recovery_generation_failed.

### P0-D. Project-group routing не настроен

Код: management/services/gemini_keys.py:134–163, 354–359, 643–675, 775–833; call_ai_analysis.py:905–918.

- Production key_project_groups() возвращает {}.
- Различающиеся fingerprints доказывают разные строки ключей, но не разные Google Cloud projects.
- При пустой group _project_aliases() возвращает только текущий alias.
- mark_429() ставит cooldown только на alias.
- Telemetry пишет decision=cooldown_project при project_group="".

Production proof: все GeminiRequestAttempt.project_group пусты; GEMINI_KEY_PROJECT_GROUPS unset; в окне 23 quota_429.

Что доказано: routing не знает project identity.
Что не доказано: делят ли шесть ключей один Google Cloud project, несколько проектов с общей model quota или независимые проекты.

### P0-E. Sequential live retry budget конфликтует с heartbeat

Код: call_ai_analysis.py:67–84, 698–720, 780–1024; run_instagram_bot.py:477–530, 855–882.

- Ordinary chat deadline 35 секунд, complex 45 секунд.
- Primary 3.7 допускает до двух slow attempts; затем 3.6/3.5 до общего deadline.
- process_pending() обрабатывает rows последовательно.
- _run_work_cycle() обновляет heartbeat только после возврата из process_pending() и других операций.
- Один 34–44-секундный provider sequence легко пересекает HB_ALIVE_WINDOW=45s.

Production proof:

- около сотни daemon_start за день;
- 8 daemon starts в hour window;
- watchdog alerts с daemon_lock_stale;
- stale_requeue после зависания rows в processing.

Вероятная связь: долгий provider call делает heartbeat stale; watchdog ждёт освобождения OS singleton lock и фиксирует ошибку.
Не доказано: точный механизм убийства конкретного Python daemon. В stderr есть многочисленные Passenger child SIGKILL/SIGTERM, но это не прямое доказательство убийства Instagram daemon.

### P1-F. Manager notification flow частично обходит throttle

Код: management/services/instagram_bot.py:4093–4145, 4226–4363; management/services/ig_alerts.py:381–426.

- drain_manager_notifications() применяет throttle_gate() только к due_ids.
- notify_manager() с default deliver_immediately=True напрямую вызывает _deliver_manager_notification().
- _queue_manager_handoff(), _escalate_manager_for_row(), _notify_recovery_exhausted() и другие пути вызывают immediate delivery.
- throttle_gate() делает cache.get() и cache.set() раздельно.
- Production cache — FileBasedCache, не Redis token bucket.
- При ошибке cache throttle fail-open и разрешает отправку.

Production proof: один provider incident дал fallback/recovery/task/escalation alerts разного типа; dedupe уменьшил часть повторов, но не агрегировал incident в один summary.

### P1-G. Один daemon выполняет слишком много независимой работы

Код: run_instagram_bot.py:477–530, 808–847.

В одном long-lived process работают inbox/reply processing, manager notification drain, payment backstop, profile refresh, conversation discovery, CRM analysis, AI reply recovery, permission transitions, inbox refresh, checkout lifecycle и follow intelligence. Часть вынесена в threads, но основной work cycle всё равно последовательно делает notification drain, payment poll, profile refresh и process_pending().

### P1-H. Request-level lineage недостаточен

Код: management/models.py:4119–4148; call_ai_analysis.py:801, 855–872; instagram_bot.py:6615–6643.

GeminiRequestAttempt хранит request_id, alias, model, outcome и classification, но не хранит source_message_id, client_id/episode, recovery_job_id, lane, attempt_index, not-attempted reason или final reply reference. InstagramBotMessage также не получает request ID. Для production RCA это не даёт строгой цепочки source -> attempts -> reply.

### P1-I. Metadata health green не доказывает generation health

Код: management/services/gemini_metadata_health.py:18–127, 219–335.

Hourly checker делает GET /models/{model} и проверяет supportedGenerationMethods. Он сознательно хранит generation_quota_proven=False. Поэтому repeated output «Scanned 6 Gemini aliases ... 0 deadline skips» совместим с generation 429/503/timeouts в ту же минуту.

### P1-J. HTTP 400 INVALID_ARGUMENT и invalid controls требуют отдельного контракта

Production зафиксировал два 3.7 invalid_payload:

- 08:51:01Z, HTTP 400 INVALID_ARGUMENT, GEMINI_API;
- 08:52:50Z, HTTP 400 INVALID_ARGUMENT, GEMINI_API.

Live payload использует responseMimeType=application/json и responseJsonSchema с anyOf, minLength/maxLength, controls и enum. Официальная документация описывает ограниченное JSON Schema subset. Возможная причина 400 — неподдерживаемое поле/keyword, но raw error body намеренно не сохраняется, поэтому точное поле не доказано.

Дополнительные daily warnings: 10 gemini_invalid_controls и 8 invalid_model_controls.

### P2-K. Повторные takeover events шумят журнал

После фактического takeover каждый manager message создавал takeover log event. Telegram dedupe оставил один внешний alert, что хорошо, но внутренний warning-stream содержит повторные «менеджер подключился». Нужно разделять transition false -> true и idempotent observation.

---

## 8. Gemini-пул и ожидание «шесть страхующих ключей»

| Role | Own aliases | Borrow aliases |
|---|---|---|
| chat | GEMINI_API, GEMINI_API2 | GEMINI_API3..6 |
| management | GEMINI_API3, GEMINI_API4 | GEMINI_API5, GEMINI_API6 |
| checker | GEMINI_API5, GEMINI_API6 | GEMINI_API3, GEMINI_API4 |

Chat chain:

    gemini-3.7-flash
      -> gemini-3.6-flash
      -> gemini-3.5-flash
      -> gemini-3.5-flash-lite

iter_live_chat_attempts() использует model-major порядок и поддерживает приоритет 3.7, но:

- candidates snapshot строится в начале logical request;
- lease-busy/quarantine/deadline candidates не всегда получают полноценную durable row;
- unknown project groups не coalesce-ятся;
- primary slow calls ограничены двумя, поэтому порядок iterator не доказывает фактическое исчерпание всех 3.7 кандидатов;
- metadata health и pool_status.available не равны generation availability.

### Почему 429 каскадирует

При неизвестных project groups возможен такой поток:

    API2/3.7 -> 429 -> cooldown только API2
    API/3.7  -> 429 -> cooldown только API
    API3/3.7 -> 429 -> cooldown только API3
    API4/3.7 -> 429 -> cooldown только API4
    API5/3.7 -> 429 -> cooldown только API5
    API6/3.7 -> timeout/429

Если это один Google Cloud project, после первой 429 нужен group-wide cooldown. Если это независимые проекты, текущий alias-level подход может быть приемлем, но это должно быть подтверждено явным non-secret mapping и observed quota.

### Почему 503 и ReadTimeout нельзя смешивать

- HTTP 503: provider вернул HTTP status и сообщил временную недоступность.
- ReadTimeout: response не пришёл в read deadline, HTTP status отсутствует.
- HTTP 429: quota/rate limit; нужен RetryInfo и scope.
- HTTP 400: request/schema contract; повторять тот же payload вслепую нельзя.

Typed classes в _gemini_call_once() уже различают эти классы, что является хорошей базой. Но верхний UX routing сводит transient markers к provider_outage, а recovery не использует разницу между коротким 503, project quota exhaustion и network timeout.

---

## 9. Context7 и официальные best practices

Проверенные Context7 libraries:

- Gemini API: /websites/ai_google_dev_gemini-api
- Requests: /psf/requests
- Django: /django/django

### 9.1. Gemini API

Ссылки:

- https://ai.google.dev/gemini-api/docs/api-errors
- https://ai.google.dev/gemini-api/docs/troubleshooting
- https://ai.google.dev/gemini-api/docs/structured-output

Из официальных материалов:

- error body содержит programmatic error code и message; классифицировать нужно по типизированным полям, а не по одному свободному тексту;
- 429 RESOURCE_EXHAUSTED и 503 UNAVAILABLE являются transient и допускают exponential backoff;
- custom retry должен иметь exponential backoff с jitter, bounded retry count и allowlist 408/429/5xx; 400/403 не следует ретраить вслепую;
- structured output нужно ограничивать JSON Schema и валидировать приложением;
- schema должна соответствовать поддерживаемому subset конкретного API/model;
- fallback после exhaustion должен быть осознанным, а не бесконечным повторением того же request.

Применение:

1. Сохранить typed distinctions в durable telemetry.
2. Не использовать provider_outage как единственную категорию UX decision.
3. Добавить bounded error.code и field/path для INVALID_ARGUMENT без хранения provider body.
4. Проверить responseJsonSchema на documented subset; сначала RED-тест на текущий 400.
5. Разделить provider retry budget, recovery budget и customer holding policy.

### 9.2. Requests

Ссылки:

- https://github.com/psf/requests/blob/main/docs/user/advanced.md
- https://github.com/psf/requests/blob/main/src/requests/exceptions.py
- https://github.com/psf/requests/blob/main/src/requests/adapters.py

Из официальных материалов:

- connect и read timeout задаются раздельно как timeout=(connect, read);
- ReadTimeout означает, что сервер не прислал данные в allotted read timeout;
- retries не следует применять к запросам, где data уже дошла до server;
- automatic retries требуют status allowlist, ограничения методов и bounded attempts.

Применение:

- Gemini generation не имеет customer side effect и может иметь ограниченный retry;
- Meta Send API timeout/unknown нельзя превращать в blind resend;
- Telegram unknown result нужно сохранять как UNKNOWN, а не сразу повторять.

### 9.3. Django long-running process

Ссылки:

- https://docs.djangoproject.com/en/6.1/ref/databases/#persistent-connections
- https://docs.djangoproject.com/en/6.1/ref/models/querysets/#select-for-update

Из официальных материалов:

- connection в long-running process остаётся открытой до явного закрытия или timeout;
- close_old_connections() следует вызывать в long-running jobs;
- select_for_update() удерживает row lock до конца transaction;
- external network I/O нельзя выполнять внутри долгой transaction/row-lock scope.

Применение:

- текущие close_old_connections() — правильная защитная база;
- heartbeat должен иметь отдельный liveness/progress pulse;
- lock scope должен включать только claim/state transition;
- outbox фиксирует state до внешнего вызова и receipt после него.

---

## 10. Варианты исправления

### Вариант A — минимальный hotfix

1. Перед _outage_holding_reply() проверить durable/cache state клиента: holding уже отправлен в последние N минут для текущего incident fingerprint.
2. Не более одного holding на client + episode + incident window.
3. Новые inbound coalesce-ить в одну pending recovery с latest watermark.
4. Если holding уже отправлен, recovery не должен начинаться с apology; либо apology удаляется, либо recovery становится продолжением.
5. После recovery generation failure не отправлять новый customer holding; в management — один deduped incident alert.

Плюс: быстро снимает видимый спам.
Минус: routing/heartbeat/notification architecture остаются частично хрупкими.

### Вариант B — рекомендуемый staged hardening

Разделить три logical plane:

    Live customer plane
      inbound -> client claim -> provider router -> customer outbox

    Provider resilience plane
      typed outcomes -> key/project/model circuits -> request lineage -> budgets

    Operations plane
      incident aggregation -> Telegram outbox -> atomic throttle -> CRM review

Ключевые элементы:

- durable ProviderIncident/ClientDegradation state;
- one holding per incident, not per inbound;
- one recovery cursor per client/episode;
- separate generation and delivery state machines;
- explicit alias-to-project-group mapping;
- group-wide 429 cooldown только при known mapping;
- model circuit после policy threshold, не после одного arbitrary error;
- heartbeat с inflight_operation, progress_at и last_completed_cycle;
- один dispatcher для external Telegram sends;
- incident summary вместо alert per source row.

### Вариант C — отдельные сервисы/очередь

Вынести live replies, provider calls и notifications в отдельные workers с per-client partitioning и distributed token bucket. Это сильнее изолирует latency, но является большим operational scope. Не выбирать как первый hotfix до измеряемого результата варианта B.

### Рекомендация

Начать с варианта B по независимым slices. Не смешивать все slices в один большой release.

---

## 11. Предлагаемый порядок implementation slices

Это handoff-рекомендация, а не утверждённый implementation plan.

### Slice 0 — RED observability before behavior change

Добавить durable correlation:

- logical_turn_id/source_message_id;
- client_id/episode reference;
- lane: live, holding, recovery, analysis, metadata_probe;
- request_id, attempt_index, candidate_index;
- key_alias, project_group, project_identity_known;
- outcome, failure_kind, http_code, safe provider code/reason;
- not_attempted_reason;
- final reply_message_id/recovery_job_id linkage.

Acceptance: по одному production-like source строится source -> attempts -> fallback/holding -> recovery -> receipt; provider body и customer text не попадают в telemetry.

### Slice 1 — Client/episode outage incident and holding coalescing

Целевое состояние:

    OPEN -> HOLDING_SENT -> RECOVERY_PENDING -> RECOVERED
                           |-> MANUAL
                           |-> SUPERSEDED/CANCELLED

Acceptance:

- 10 inbound одного клиента во время одного incident создают максимум один holding;
- новый inbound обновляет latest watermark, но не отправляет второй apology;
- manager takeover/opt-out/hidden client отменяет unsent recovery;
- новый incident после resolved window может создать новый holding.

### Slice 2 — Recovery semantic contract

- holding + recovery дают не более одного apology;
- generated text «Вибачте за затримку...» не получает второй prefix;
- semantic apology variants нормализуются;
- exhaustion даёт один manager incident и не даёт второй customer holding;
- old logical turn superseded latest source.

### Slice 3 — Provider router and six-key policy

- заполнить явный non-secret alias-to-project-group mapping после проверки Google Cloud;
- unknown mapping не называть cooldown_project;
- group-wide 429 cooldown только при доказанной общей project identity;
- отдельные counters/circuits для quota, 503, timeout, connect error, invalid payload, auth, model not found;
- сохранить practical priority 3.7 и документировать reserve budget;
- durable attempted/not-attempted evidence для всех кандидатов.

### Slice 4 — Live worker isolation and heartbeat

- не держать customer processing за manager drain и maintenance calls;
- ограничить work-cycle budget или вынести notification/analysis в отдельные process;
- отдельный liveness pulse с inflight/progress;
- watchdog различает process_alive_but_busy, progress_stalled, lock_stale и child_exited;
- reclaim по operation lease/progress, не только wall-clock.

### Slice 5 — Единственный manager notification outbox

- notify_manager по умолчанию только создаёт durable intent;
- один dispatcher делает Telegram I/O;
- deliver_immediately не обходит token bucket;
- atomic Redis Lua/token bucket либо DB row lock;
- cache failure переводит в bounded safe mode;
- одно incident summary содержит counts и максимум несколько sample IDs;
- takeover transition уведомляется один раз.

### Slice 6 — Structured-output contract

- проверить schema на documented Gemini subset;
- при необходимости упростить anyOf/validation keywords;
- application-side validation сохранить обязательной;
- сохранять bounded error.code и field/path;
- invalid controls остаются proposal-only.

---

## 12. Тестовая матрица

### Customer anti-spam

- один provider outage + один inbound -> максимум один holding;
- три inbound за 5 минут -> максимум один holding и один coalesced recovery;
- holding delivered + recovery success -> один apology total;
- holding delivered + recovery failed -> no second holding, один manager incident;
- новый incident после закрытия старого -> новый holding допустим;
- takeover/opt-out/hidden/block/epoch change -> no bot send;
- newer inbound supersedes old source.

### Gemini provider

- 503 на первом alias, 3.7 success на втором;
- 503 threshold открывает circuit по policy threshold;
- ReadTimeout отличается от 503;
- 429 RetryInfo использует bounded delay;
- shared cooldown только для known group;
- unknown group не пишет misleading project decision;
- 400 invalid argument fails fast и сохраняет safe code/path;
- 404/403 не создают infinite retry;
- шесть кандидатов имеют durable attempted/not-attempted evidence;
- metadata probe success не объявляет generation healthy.

### Worker/DB

- close_old_connections вокруг long-running iterations;
- network I/O отсутствует внутри select_for_update transaction;
- 40-секундный provider call не создаёт ложный stale heartbeat;
- stale reclaim race не позволяет старому worker finish;
- process kill во время generation/recovery оставляет safe durable state;
- MariaDB concurrency tests, не только SQLite.

### Telegram

- immediate path проходит тот же global throttle;
- concurrent senders не превышают flow rate;
- cache outage даёт bounded safe mode;
- 20 same-incident events агрегируются в один summary;
- Telegram 429 уважает retry_after;
- unknown Telegram result остаётся UNKNOWN;
- recovery exhaustion/task-health dedupe по incident fingerprint.

---

## 13. Production verification checklist

Перед release:

1. git diff --check, focused tests, Django check, migration drift, compile.
2. Точный commit pushed to main.
3. SSH git pull --ff-only origin main.
4. Migrations applied and verified.
5. Один daemon owner, PID, OS lock, heartbeat/progress и process start time.
6. MariaDB counts pending/processing/recovery/notification.
7. Шесть aliases configured без вывода значений; project-group mapping state.
8. Runtime model chain and routing policy.
9. Нет stale recovery для клиента с takeover.
10. Customer holding count за controlled observation window.
11. Telegram outbox rate/dedupe.
12. Fresh logs: provider classes, lineage, no duplicate holding, no stale watchdog false positive, no daemon_lock_stale, no notification burst.
13. Только небольшие sequential endpoint probes; не использовать broad crawler smoke на shared host.
14. Не отправлять synthetic Meta customer events без явного разрешения.

После release:

- наблюдать полный provider degradation window;
- сравнить p50/p95/p99 latency;
- считать holding per incident/client;
- считать manager alerts per incident/client;
- проверять not_attempted reasons;
- проверять recovery terminal states и provider receipts;
- следить за process churn несколько часов.

---

## 14. Что не следует делать

- Не просто удалить fallback message.
- Не увеличить общий Gemini timeout до 75–90 секунд.
- Не смешивать ReadTimeout с HTTP 503.
- Не считать шесть API keys шестью независимыми projects без evidence.
- Не ставить все ключи в общий cooldown при unknown project identity.
- Не делать retry Meta Send API после ambiguous timeout.
- Не отправлять manager alert напрямую из customer critical path по умолчанию.
- Не лечить notification spam только TTL одного dedupe_key.
- Не удалять исторические recovery/notification rows без audit trail.
- Не считать hourly metadata health доказательством generation availability.
- Не смешивать outage dedupe, model migration, Meta auth и worker architecture в одном непроверяемом release.

---

## 15. Подтверждённые факты и гипотезы

### CONFIRMED

- В production 27 августа были реальные 429, 503 и ReadTimeout.
- В окне 12:20–13:20 UTC было 71 chat provider attempts, 15 top-level errors, 6 fallback events и 7 customer apology rows.
- _zhenya_963 получил четыре logically similar technical-delay customer rows, включая holding + recovery с повторным apology.
- Recovery dedupe действует только на source message, не на client incident.
- Recovery 7 исчерпал три generation attempts и завершился failed.
- Manager takeover клиента 334 остановил последующие bot replies корректно.
- Client 335 показал тот же holding/recovery pattern.
- GEMINI_KEY_PROJECT_GROUPS не настроен; project_group пуст.
- Metadata health показывал 6/6 configured при одновременных generation failures.
- В daily ledger было не менее 101 daemon starts и три watchdog daemon_lock_stale alerts.
- Immediate manager notification path существует и частично обходит drain throttle.

### UNVERIFIED / NEEDS CALIBRATION

- Делят ли шесть Gemini aliases один Google Cloud project или quota bucket.
- Точный механизм daemon exits: CloudLinux/LVE kill, process limit, host restart, Python exit или комбинация.
- Точное поле/keyword, вызвавшее два HTTP 400 INVALID_ARGUMENT.
- Возникали ли provider-side duplicates в отдельных ambiguous Meta sends.
- Полная causal correlation между каждым daemon restart и конкретным Gemini request.

---

## 16. Минимальный handoff prompt

Используй этот файл как evidence-backed input, но не как непогрешимый канон. Сначала перепроверь production facts и текущий SHA. Реализуй slices по порядку: lineage, client/episode outage coalescing, one-apology recovery contract, project-aware Gemini routing, heartbeat/worker isolation, unified Telegram outbox, structured-output contract. Для каждого slice добавь RED regression, MariaDB/concurrency proof и отдельную production acceptance. Не отправляй synthetic Meta customer events. Докажи source_message -> request attempts -> fallback/holding -> recovery -> provider receipt, отсутствие второго holding в одном incident, отсутствие двойного apology, отсутствие notification burst и отсутствие daemon watchdog churn.

---

## 17. Code surfaces

- twocomms/management/services/bot_reply_fallback.py:255–374
- twocomms/management/services/ig_ai_reply_recovery.py:43–53, 99–231, 234–289, 603–688, 877–1025
- twocomms/management/services/call_ai_analysis.py:67–84, 698–720, 780–1024, 1228–1289
- twocomms/management/services/gemini_keys.py:37–67, 134–168, 354–359, 460–544, 617–675, 775–833
- twocomms/management/services/instagram_bot.py:3079–3120, 3519–3643, 4093–4145, 4226–4363, 6443–6643, 9518–9660, 9941–10666, 11079–11159, 11373–11423
- twocomms/management/management/commands/run_instagram_bot.py:477–530, 672–767, 774–892
- twocomms/management/services/ig_task_health.py:133–239, 241–297, 417–446
- twocomms/management/services/ig_alerts.py:381–426
- twocomms/management/models.py:3626–3957, 4057–4148

## 18. Implementation plan

Пошаговый план реализации на основе этого документа находится в
`04_IMPLEMENTATION.md`, этап **ЭА — Аварийная стабилизация деградации
провайдера** (пункты ЭА.0–ЭА.24, с чекбоксами, метриками, откатами и приёмочным
контрактом из девяти инвариантов). Соответствие находок пунктам плана:

| Находка | Пункты плана |
|---|---|
| P0-A (нет client-scoped suppression) | ЭА.2, ЭА.3, ЭА.4, ЭА.7 |
| P0-B (apology не ограничен одним на ход) | ЭА.6, ЭА.7 |
| P0-C (recovery добивает деградированный пул) | ЭА.8 |
| P0-D (project-group routing не настроен) | ЭА.10, ЭА.11, ЭА.12 |
| P0-E (retry budget против heartbeat) | ЭА.13, ЭА.14 |
| P1-F (обход throttle уведомлений) | ЭА.16, ЭА.17 |
| P1-G (демон делает слишком много) | ЭА.15 |
| P1-H (недостаточный lineage) | ЭА.1 |
| P1-I (metadata health ≠ generation health) | ЭА.19 |
| P1-J (HTTP 400 INVALID_ARGUMENT) | ЭА.20 |
| P2-K (повторные takeover events) | ЭА.18 |
| разделы 9.2, 14 (Meta ambiguous send) | ЭА.21 |
| раздел 12 (тестовая матрица) | ЭА.22 |
| раздел 13 (production verification) | ЭА.0, ЭА.24 |

Пункты плана без находки в этом документе (`ЭА-NEW-01…06`: intent-gate, тихая
деградация через индикатор набора, детерминированный уровень L3, health-скорборд,
fault-injection harness, runbook) — это предложения, а не подтверждённые дефекты.
У них нет production-доказательства и требуется отдельный baseline.

## 19. Final status

Документ создан как production-backed analysis/handoff. На текущем этапе не заявляется, что проблема исправлена: customer spam mechanism, provider degradation, daemon churn и manager alert amplification требуют implementation slices, тестов, deploy и live verification.
