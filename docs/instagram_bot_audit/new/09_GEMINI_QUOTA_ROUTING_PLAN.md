# 09 — Gemini Router V2, квоты, live-классы и CRM-анализ

Дата фиксации контракта: 2026-08-30.

Статус: **runtime S1 задеплоен; первый soak завершился ранним SIGKILL, после
авторизованной S1b selector-коррекции 48-часовой gate запущен заново. Исправленный
Routing S2, schema S3a, S3b shadow writer, checkout Slice 1 + dormant series
Slice 2a + generation runtime S2b, materiality Slice 1, Analysis V2 A2,
Typed Memory V2 shadow и
privacy/correctness hardening
старой API-панели с Gemini V2 read API + model-first cockpit объединены только в локальной
integration-ветке, не задеплоены и поэтому не считаются production-complete**.

Этот документ — единственный подробный контракт для Gemini-маршрутизации,
учёта квот, event-driven health, API UI, durable CRM-анализа, typed memory и
связи анализа с будущими воронками. Общий порядок проекта остаётся в
`04_IMPLEMENTATION.md`; там не должна появляться вторая копия правил из этого
файла.

Чекбокс `[x]` допустим только после выполнения кода, целевых тестов, деплоя и
production-проверки соответствующего пункта. Наличие старого кода, локального
теста или миграции само по себе не закрывает V2.

---

## 0. Handoff snapshot

### 0.1 Текущая граница после production S1

| Область | Наблюдаемое состояние | Что обязательно перепроверить |
|---|---|---|
| Local/GitHub `main` | `e62bedf5df570af9a46fe0e760eb248819cccefa` | повторять parity перед каждым следующим merge |
| Production checkout | `e62bedf5df570af9a46fe0e760eb248819cccefa`; tracked diff clean, существующие untracked runtime/diagnostic files не тронуты | не смешивать следующий routing deploy с runtime soak evidence и не удалять untracked files |
| Running runtime | supervisor и child сообщают SHA `e62bedf5df570af9a46fe0e760eb248819cccefa`; supervisor PID/start-ticks identity совпадает | повторять SHA/PID/start-ticks proof после каждого deploy/reload |
| Daemon health | `state=running`; process pulse fresh; main progress fresh, `idle`, не stalled | 48-часовой soak и live-reply latency ещё не доказаны |
| Initial S1 soak | **FAILED early:** child PID `77835` получил внешний `SIGKILL` 2026-08-30 15:23:40 Europe/Kyiv после `124.943 s`; supervisor signal/reload/stop отсутствовали; recovery через 1 с сработал | не считать S1 soak закрытым и не стирать incident из baseline |
| Correlation | selector фактически передавал `LSAPI_CHILDREN=10`, несмотря на stale public `.htaccess` со значением 3; наблюдались expansion и повторные lswsgi `SIGKILL` | fPMEM недоступен: LVE/PMEM-причина высоко вероятна, но формально не доказана |
| Authorized S1b | production Selector изменён только `LSAPI_CHILDREN: 10→3`; добавлен `LSAPI_EXTRA_CHILDREN=0`; non-LSAPI digest сохранён, env count `75→76` | это external production state, а не tracked-file/SHA divergence |
| S1b runtime snapshot | selector/app restart выполнен под exact bot maintenance; health/home/catalog последовательно вернули 200; все lswsgi env показывают `3/0`; process group после старта master+2, верхняя цель master+3 | process/RSS цифры являются snapshots, не steady-state p95 |
| S1b memory snapshot | comparable RSS `950732→588240 KiB`, PSS `666577→390312 KiB`, private `583960→298036 KiB` | не выдавать snapshot за fPMEM или PMEM p95 proof |
| Active soak | baseline `2026-08-30T15:48:03+03:00`; deadline `2026-09-01T15:48:03+03:00`; automation active | gate закрывается только полной выборкой после deadline |
| Production migrations | migration set не менялся в S1; `0176_gemini_model_quota_usage` остаётся применённой, engine-registry gap закрыт в deployed code | локальные `0177–0185`, `orders.0057–0058` не применять до release gate |
| Runtime routing | production остаётся на legacy routing из `e62bedf5`; corrected S2 существует только в локальной integration-ветке | до deploy настроить private-media root, завершить soak и повторить preflight |
| Local integration code candidate | `8f3f20b4d`; Routing S2 + S2 correctness amendment + schema S3a/S3b + checkout terminalization/series/generation S2b + materiality Slice 1 + Analysis V2 A2 + Typed Memory V2 shadow + V2 read API + model-first cockpit; поверх него допустим только docs-only snapshot commit | SHA локальный, не GitHub/main/production; не использовать как running truth |
| Ключи | владелец подтвердил: шесть ключей принадлежат шести отдельным Google-проектам | явный безопасный mapping `project_identity`, без вывода ключей и project IDs |
| Cron ownership | один stdlib watchdog, один sequential Instagram coordinator; durable tasks и Nova Poshta используют общий heavy-process lock | cadence/LVE steady state подтвердить soak-выборкой |
| Removed owners | automatic metadata cron = 0; legacy Instagram periodic owner lines = 0 | manual metadata остаётся только явной диагностикой |
| Shared-host LVE | воспроизводились пики 1,25–1,28 GiB при лимите 1 GiB | 48-часовой soak после runtime-среза |
| S1 tests | 68 low-level + 134 Django + 97 deploy tests; local `manage.py check` и migration drift clean | production soak не заменяется локальными тестами |

Эти строки — handoff evidence, а не вечная истина. Каждый implementation-срез
сначала обновляет таблицу, не подменяя server truth локальными выводами. В
Markdown запрещено записывать API-ключи, SSH-пароли, реальные Google project IDs,
полные тексты клиентов, usernames, prompts и raw provider bodies.

### 0.2 Подтверждённые решения владельца

- Шесть credential slots соответствуют шести независимым quota projects.
- Обычный текстовый live должен начинаться с Gemini 3.5 Flash Lite.
- Неоднозначное изображение, аудио и сложный product/ad/fit reasoning должны
  начинаться с Gemini 3.7 Flash.
- Durable CRM-анализ должен обычно начинаться с Gemini 3.6 Flash; 3.7 — только
  отдельный high-value escalation.
- Health и UI не имеют права генерировать тестовый контент ради зелёного статуса.
- Состояние модели обновляется реальным traffic evidence; отсутствие ошибок без
  свежей генерации означает `available_assumed`, а не доказанный success.
- Модель не является источником истины для payment, order, price, stock,
  delivery, discount и manager authority.
- Анализ не повторяется без нового material evidence.
- Новый анализ обязан встраиваться в будущий versioned funnel registry, а не
  создавать параллельную FSM.

### 0.3 Открытые gates

- [x] S1 integration/deploy parity: local, GitHub, production checkout,
      supervisor и child совпадают на `e62bedf5df570af9a46fe0e760eb248819cccefa`;
      production tracked-clean.
- [x] Runtime ownership conversion подтверждена на production: один stdlib
      watchdog, один sequential coordinator, общий heavy-process lock для
      durable/Nova; metadata и legacy periodic owners отсутствуют.
- [x] Engine-registry code gap закрыт в deployed SHA; S1 не требовал новой
      migration.
- [ ] Завершить перезапущенный 48-часовой LVE/PMEM/NPROC/daemon-exit soak
      (`2026-08-30T15:48:03+03:00` → `2026-09-01T15:48:03+03:00`) и снять
      live-reply p95. Automation active; ранний pre-fix SIGKILL остаётся в evidence.
- [ ] Выпустить corrected S2 только после soak/preflight/private-media config;
      локальные blockers закрыты, но checkbox остаётся открытым до deploy и
      production proof.
- [ ] Включить S3b shadow writer после Pacific midnight; schema S3a сама по
      себе ничего не считает и не меняет routing.
- [ ] Выпустить materiality Slice 1 после release gate: локально он прошёл три
      цикла NO-GO/fix/review, MariaDB kill/resume и финальный PASS, но остаётся
      `off` и не считается production-complete.
- [ ] Подготовить S3b production shadow rollout: локально все NO-GO исправлены,
      final independent review PASS и integration tests зелёные; включение
      возможно только после explicit six-project mapping, dedicated HMAC key и
      следующей Pacific midnight, затем два полных Pacific days наблюдения.
- [ ] Дальше внедрять V2 отдельными reversible slices; не смешивать schema,
      enforcement, policy, analysis, funnel и UI.

### 0.4 S1 soak failure и авторизованная S1b-коррекция

Supervisor доказал исход, который раньше терялся: child PID `77835` завершён
внешним `SIGKILL` 2026-08-30 15:23:40 Europe/Kyiv, uptime `124.943 s`.
Supervisor не получал signal, reload или stop request; штатный backoff 1 с
восстановил child. Это **failed initial soak**, а не успешная устойчивость.

Read-only корреляция показала расширение lswsgi process group и фактический
selector runtime `LSAPI_CHILDREN=10`, хотя stale public `.htaccess` показывал 3;
рядом наблюдались повторные lswsgi `SIGKILL`. Метрика fPMEM на этом аккаунте
недоступна, поэтому memory/LVE root cause оценивается как высоко вероятный, но не
формально доказанный.

В рамках явно авторизованной S1b изменено только external CloudLinux Selector
state:

- полный 75-variable map был прочитан и преобразован в памяти без вывода его
  содержимого; `LSAPI_CHILDREN` изменён `10→3`, добавлен
  `LSAPI_EXTRA_CHILDREN=0`;
- digest всех non-LSAPI значений сохранился; число переменных `75→76`;
- selector и приложение перезапущены под exact bot maintenance; health, home и
  catalog проверены последовательно и вернули HTTP 200;
- все lswsgi processes получили `LSAPI_CHILDREN=3` и
  `LSAPI_EXTRA_CHILDREN=0`; начальная группа — master+2, разрешённый максимум —
  master+3;
- supervisor и child остались на
  `e62bedf5df570af9a46fe0e760eb248819cccefa`; status `running`, process/main
  fresh, main `idle`;
- comparable account snapshots: RSS `950732→588240 KiB`, PSS
  `666577→390312 KiB`, private `583960→298036 KiB`.

Selector — внешняя production-конфигурация, поэтому это изменение не создаёт
tracked-file или Git SHA divergence. Memory numbers выше — только before/after
snapshots, не fPMEM, не p95 и не 48-часовое доказательство.

Новый soak baseline: `2026-08-30T15:48:03+03:00`; deadline:
`2026-09-01T15:48:03+03:00`. Автоматизация мониторинга активна. До дедлайна все
soak/fault/PMEM/p95 checkboxes остаются открытыми.

Последний read-only sample `2026-08-31T10:04:19+03:00`: supervisor и child
identity совпадают с deployed SHA `e62bedf5`; `healthy=true`, `restart_count=0`,
process/main heartbeat fresh, main `idle`, lswsgi process count `3`. Это
промежуточная точка, не завершение
48-часового gate.

### 0.5 S2 review gate — первоначальный NO-GO закрыт локально, deploy всё ещё закрыт

Первоначальный независимый review `62070f6eb` + `ec34e1734` не разрешил deploy
и потребовал закрыть следующие темы без переноса их в будущий S3:

- один canonical media pass/artifact вместо повторного strong-вызова; рабочий
  voice/audio path и deterministic UGC acknowledgement при временно недоступных
  provider-native post/reel bytes;
- project-aware rotation после 404, deterministic mapping рекламной кампании до
  3.7 и сохранение исходного complex decision в recovery;
- multilingual product-switch parsing без утечки старого товара/цены;
- UGC review end-to-end: notification-bound chat/message/generation,
  evidence/product context, очередь для реального `needs_manager_review`, запрет
  actor-less discount и корректный 5%/10% customer snapshot;
- health по фактической adaptive chain/cross-key request, безопасный fallback для
  неполного 429 envelope и opaque UI slots вместо env aliases.

Исправленный стек `62070f6eb..a945d5f1` прошёл повторные scoped reviews и локально
cherry-picked в integration. Он добавляет single-pass image/audio artifact,
deterministic UGC acknowledgement, project-aware 404 rotation, typed ad
resolver, приватное media ownership/erasure fencing, opaque 4×6 health slots,
429 fail-closed accounting и retry-safe `0177`. Полный routing regression на
integration: `930` tests, `OK`, `4` intentional skips. Disposable MariaDB 11.4
kill/resume для `0177` завершился повторным применением без пропусков; целевые
таблицы подтверждены InnoDB.

Это **локальное доказательство**, не `[x]`: corrected S2 отсутствует в `main`,
GitHub и production. До deploy обязательно создать explicit `IG_PRIVATE_MEDIA_ROOT`
вне checkout/MEDIA_ROOT, проверить owner/mode `0700`, затем повторить SHA,
migration, cron и runtime preflight. Model-scoped permits, rolling/input TPM и
полный parent request/attempt FSM остаются отдельным S3.

### 0.6 Локальные additive-срезы после S2

| Slice | Local evidence | Production status |
|---|---|---|
| S3a accounting schema | `0178–0181`; request/attempt/quota/profile contracts; `31` schema tests (`3` Maria-only skips); disposable MariaDB partial-DDL resume, все пять таблиц InnoDB | не применён; runtime writer `off`/отсутствует |
| Checkout terminalization Slice 1 | `orders.0057`; `396` integrated tests (`5` skips); MariaDB partial-DDL resume; две реальные MariaDB concurrency гонки прошли без deadlock/duplicate order | не применён |
| Runtime capacity auditor | безопасная selector/process/flock атрибуция; `37` targeted tests | не задеплоен, чтобы не сбросить активный soak SHA |
| Materiality Slice 1 | `0182`; passive content-free ledger; atomic claim cursor; 90s/10m **projected telemetry**; manager-evidence guard; constant-query selector; `486` integrated tests (`3` skips); MariaDB partial-DDL resume на 15 Job fields + InnoDB/unique/real append-only triggers; final independent PASS. Worker claim пока использует legacy `due_at`, поэтому 90s/10m ещё не управляет реальным cadence | не применён; defaults `off` + selector `legacy` |
| Gemini V2 cockpit | boundary-wide alias redaction, opaque request refs, exact six stable slots/schema v5, generation/metadata separation, winner-bound fallback/request-start ordering; model-first `Квоти/Маршрути/Спроби`, external CSS/JS, one live region, 360/768/1440 responsive. Integration `49` UI/API tests; frontend-skill evaluation round 1 `NEEDS REVISION`, localization fix, round 2 `PASS` | не задеплоен; Claude cross-provider evaluator был недоступен без login, единственный fallback evaluator — отдельный GPT-5.5 |
| S3b shadow writer | default-off parent graph/FSM/quota state; exact provider boundary; linked skipped candidates; manual-first immutable plan without routing change; recovery receipt linkage; conflict-safe reply link; HMAC/explicit identity; rolling input-token shadow admission; selected-pair profile rotation; bounded remainder write; final independent PASS. Integration: `165` standard combined tests + `48` migration-enabled; disposable Maria concurrency `2/2`, one shadow permit deny, `in_flight=0`, all V2 tables InnoDB | не задеплоен; mode `off`, enforcement отсутствует |
| Checkout Series Slice 2a | dormant `orders.0058`: nullable series/generation/winner identity, exact physical defaults/CHECK/UNIQUE/indexes, strict pure key helpers, no runtime writer; final independent PASS. Integration focused `77` tests (`2` skips); disposable Maria kill/resume, malformed shapes/default/CHECK и irreversible reverse proof | не применён; `IG_ASSISTED_CHECKOUT_V2=off`; TTL/provider/Order behavior unchanged |
| Gemini V2 read API | admin-only provider-free `quotas/routes/attempts`; permanent 4×6 matrix, off/unknown fail-closed, executable chains/pin, encrypted keyset cursor, redacted request/attempt/reply graph, query budgets `≤6/≤2/≤4`; final independent PASS. Model-first cockpit уже реализован отдельным локальным slice и прошёл evaluation round 2. Integration combined API/UI `51` tests | не задеплоен; production по-прежнему показывает legacy panel/runtime |
| Analysis V2 A2 | default-off immutable Result + generic Proposal, one existing provider result, nullable evidence-bound probability, PII-free HMAC/opaque refs, shadow-only projector/no business mutations, diagnostics-only current selector; retry-safe `0183`, final independent PASS. Integration focused `44`; broad `375` (`3` skips); fresh Maria kill/resume, both InnoDB, six INSERT/UPDATE/DELETE guards including raw PII/identity claims | не применён; mode `off`, extended prompt canary отдельно off, consumer switch отсутствует |
| S2 correctness amendment | expired classified quota blocks корректно возвращаются в `available_assumed`; frozen candidate plan совпадает с dispatch; один DB-unique graph на `(source_message,lane)`; exact candidate admission; stale boundary не пересекает HTTP; единый lock order; legacy hedge выключен при shadow. Merged integration gate: `572` runtime/routing + `31` migration-enabled tests; real Maria unique/concurrency/kill-resume PASS; final independent review функционально PASS | не задеплоен; shadow остаётся `off`, enforcement отсутствует |
| Checkout generation S2b | `management.0184`; 12h proposal без stock hold, 25m generation/provider validity, default full payment, direct-question 200+COD, exact amount/identity/HMAC terminal proof, winner-before-Order, ambiguity/reissue/privacy/promo reconciliation, append-only evidence. Final dual review PASS. Merged integration: `325` checkout/payment + `20` migration tests; four Maria kill points/InnoDB/CHECK/triggers/winner-loser race PASS | не применён; `IG_ASSISTED_CHECKOUT_V2=off`, никаких consent/reminder sends |
| Typed Memory V2 shadow | `management.0185`; immutable Fact/Evidence, bounded exact Head chain, assert/invalidate/expire tombstones, Analysis v2.2 claim-specific user evidence, key-independent semantic identity + versioned HMAC rotation, provider-free publisher/reconcile, privacy-fenced purge, exact physical CHECK/UNIQUE/trigger validation. Final review PASS. Merged integration: `188` standard + `104` migration-enabled tests; integrated Maria kill-after-30 восстановил 3 InnoDB tables/9 triggers | не применён; mode `off`, `typed_prompt` отсутствует, legacy `MEMORY_EVERY=8` сохранён до parity gate |

**Следующий конкретный шаг:** automation продолжает S1b soak до
`2026-09-01T15:48:03+03:00`; следующий additive slice — versioned funnel
registry shadow как `management.0186` поверх merged Analysis/Memory contracts.
До закрытия soak не
менять production SHA и не применять новые migrations; S3b/Analysis/Memory
shadow не включать до explicit environment preflight и ближайшей последующей
Pacific midnight.

---

## 1. Неподвижные инварианты архитектуры

1. Один customer turn получает не более одного customer-facing результата и не
   более одного canonical media-intelligence artifact.
2. До provider I/O существует versioned routing decision и полный candidate
   plan. Отсутствие попытки всегда имеет сохранённую причину.
3. Все Gemini consumers проходят через один gateway и один quota/accounting
   контракт.
4. UI, polling, charts и health endpoints никогда не вызывают
   `generateContent`.
5. Quota state принадлежит паре `(project_identity, model)`, а не alias и не
   ключу целиком.
6. Provider evidence сильнее локального счётчика. Локальный остаток — оценка, а
   не обещание доступности.
7. Network I/O не выполняется внутри долгой DB-транзакции.
8. После пересечения provider boundary reservation не возвращается только из-за
   timeout/cancel: провайдер мог принять запрос.
9. Analysis создаёт evidence-bound proposals; deterministic projector решает,
   применимы ли они к текущему episode/line/revision.
10. Manager text не становится customer intent и не маскируется под роль модели.
11. Payment/order/stock/price/delivery/discount/permission изменяются только из
    authoritative backend evidence.
12. Meta transport capability и внутреннее business consent — разные сущности.
13. Любая customer-visible деградация дедуплицируется по logical turn/incident,
    а не по отдельной provider attempt.
14. Исторические snapshots, attempts и funnel transitions append-only; текущая
    проекция может смениться, evidence не переписывается.

---

## 2. Единица маршрутизации

До любого Gemini-вызова backend создаёт immutable `RoutingDecision`:

```text
lane
task_class
reason_codes[]
authority_snapshot_version
requires_media_reasoning
commercial_risk
model_chain
deadline_ms
policy_version
```

Решение строится по typed backend-сигналам. Нельзя определять сложность по одному
слову «цена», «размер», «товар», по длине сообщения или по имени модели,
выбранной старым кодом.

### 2.1 Приоритет классификации

Порядок обязателен:

1. Проверить `NO_MODEL`: существует ли готовый authoritative outcome и
   безопасный локализованный ответ/действие.
2. Применить deterministic security/content guard.
3. Проверить typed multimedia/ambiguity/high-impact reasons для `COMPLEX_LIVE`.
4. Если backend facts определены и модели остаётся только формулировка —
   `ORDINARY_LIVE`.
5. Analysis, UGC assessment и background jobs не относятся к live-классам и
   получают собственные lane/task.

Один и тот же вопрос о цене может быть:

- `NO_MODEL`, если exact product, authoritative price и готовая формулировка уже
  определены;
- `ORDINARY_LIVE`, если факты известны, но нужен контекстный естественный ответ;
- `COMPLEX_LIVE`, если сначала требуется понять, о каком из нескольких товаров
  или изображений спрашивает клиент.

### 2.2 Базовые reason codes

Перечень versioned и расширяемый; свободный текст причиной не является.

```text
NO_MODEL_AUTHORITY_REPLY
NO_MODEL_POSTBACK
NO_MODEL_PERMISSION_OR_TAKEOVER
NO_MODEL_DEDUPE
NO_MODEL_UGC_ACK

ORDINARY_BACKEND_FACTS_READY
ORDINARY_SINGLE_CLARIFICATION
ORDINARY_SOCIAL_REPLY

COMPLEX_MEDIA_IMAGE
COMPLEX_MEDIA_AUDIO
COMPLEX_AMBIGUOUS_PRODUCT
COMPLEX_PERSONAL_FIT
COMPLEX_MULTI_LINE_OR_RECIPIENT
COMPLEX_CUSTOM_PRINT
COMPLEX_CONFLICTING_INTENT
COMPLEX_UNRESOLVED_AD_REFERRAL
COMPLEX_COMPARISON
COMPLEX_COMMERCIAL_RISK

ANALYSIS_MATERIAL_TURN
ANALYSIS_AUTHORITY_CHANGE
ANALYSIS_EPISODE_OR_LINE_CHANGE
ANALYSIS_HIGH_VALUE_ESCALATION
```

### 2.3 `NO_MODEL`

**Определение:** действие и customer-facing содержание полностью определены
backend-истиной; Gemini не может улучшить бизнес-решение и способен только
добавить задержку или выдумать факт.

Примеры:

- verified payment, order status, ТТН и факт получения;
- postback/quick reply с точным payload;
- opt-out, pause, manager takeover/release;
- готовая exact price/stock/paylink формулировка из authoritative resolver;
- безопасная благодарность за story mention/repost;
- duplicate webhook и already-delivered reply;
- известный Meta-window denial;
- подтверждённый manager handoff.

Правила:

- [ ] Ответ локализуется детерминированным шаблоном.
- [ ] Gemini fallback «для красоты» отсутствует.
- [ ] Story/repost acknowledgement не подтверждает покупку и не обещает скидку.
- [ ] Действие имеет максимальный приоритет и минимальный latency budget.
- [ ] Повторное событие не создаёт второй send.

### 2.4 `ORDINARY_LIVE`

**Определение:** короткий customer-facing ответ, для которого backend уже собрал
факты, а модель только формулирует их естественным языком. Ошибка модели не
должна менять business outcome.

Признаки:

- текст не требует визуальной или голосовой интерпретации;
- product/variant однозначен либо ответ не зависит от его выбора;
- модель сообщает готовую size table или задаёт одно уточнение, но не выбирает
  размер за клиента;
- price/stock/payment/delivery уже пришли из backend snapshot;
- нет конфликта episodes, recipients или lines;
- нет сложного custom-print brief, сравнения или неразрешённого ad referral.

Примеры:

- приветствие, благодарность, обычный small talk;
- способы оплаты и доставки;
- exact-price вопрос при закреплённом товаре;
- повтор уже известных характеристик;
- короткое уточнение цвета или количества;
- естественная формулировка catalog/payment/order snapshot.

Model-major chain:

```text
Gemini 3.5 Flash Lite: все доступные проекты
→ Gemini 3.5 Flash: все доступные проекты
→ Gemini 3.6 Flash: все доступные проекты
→ Gemini 3.7 Flash: аварийный последний fallback
→ deterministic safe response / manager route
```

Требования:

- [ ] Все шесть проектов присутствуют в immutable candidate plan.
- [ ] Быстрые 429/auth/not-found позволяют немедленно перейти к следующему
      допустимому проекту.
- [ ] Один медленный timeout не запускает ещё пять полных последовательных
      timeout.
- [ ] SLA/quota guard может остановить wave, но сохраняет
      `not_attempted_reason` для каждого кандидата.
- [ ] Проекты ранжируются по rolling RPM, remaining RPD, in-flight permits,
      cooldown и latency; первый проект не выжигается до нуля.

### 2.5 `COMPLEX_LIVE`

**Определение:** customer-facing ход, где понимание неоднозначного или
мультимодального входа существенно влияет на товар, конфигурацию, следующую ветвь
воронки или полноту ответа.

Typed triggers:

- изображение или аудио нужно понять, а не только подтвердить получение;
- deterministic resolver оставил несколько product/print/variant candidates;
- нужна персональная fit/size рекомендация;
- клиент меняет товар, получателя или создаёт вторую order line;
- complex custom-print request;
- конфликт: exchange vs repeat purchase, новый подарок vs старый заказ;
- ad referral не сопоставился однозначно;
- сравнение нескольких вариантов;
- ошибка интерпретации направит клиента в неверную sub-funnel.

Не является sufficient trigger:

- отдельное слово «цена», «размер» или «товар»;
- точный backend payment/order/stock outcome;
- story mention, для которого достаточно acknowledgement;
- prompt-injection текст сам по себе: сначала deterministic guard.

Model-major chain:

```text
Gemini 3.7 Flash
→ Gemini 3.6 Flash
→ Gemini 3.5 Flash
→ Gemini 3.5 Flash Lite
→ clarification / manager route
```

Требования:

- [ ] `reason_codes` объясняют, почему ход получил scarce 3.7 capacity.
- [ ] Exact SKU/stock/purchase/discount подтверждает resolver, не 3.7.
- [ ] При insufficient confidence ответ уточняет или передаёт менеджеру, а не
      угадывает.
- [ ] Ошибка complex-классификации видна в analytics и доступна для review.

### 2.6 Canonical `TurnIntelligenceArtifact`

Один customer turn создаёт максимум один artifact:

```text
turn_id
media_kind
content_digest
provider_object_id
transcript_or_description
candidate_entities[]
confidence
evidence
model/project/attempt
schema_version
created_at
```

- [ ] Product image: один 3.7 multimodal pass создаёт candidates, confidence и
      evidence.
- [ ] Voice: один сильный pass создаёт transcript и typed intent/facts.
- [ ] Live reply и durable analysis переиспользуют artifact.
- [ ] Повторный signed media URL с тем же provider object не создаёт новый pass.
- [ ] Provider-native UGC получает deterministic acknowledgement и один
      dedicated 3.6 assessment; chat Gemini не вызывается.
- [ ] Artifact не становится authoritative catalog/payment truth.

### 2.7 `DURABLE_ANALYSIS`

Это background lane, которая не задерживает customer reply.

```text
Gemini 3.6 Flash
→ Gemini 3.5 Flash
→ Gemini 3.5 Flash Lite
→ durable retry/defer
```

Отдельный 3.7 escalation разрешён только если одновременно:

1. основной 3.6-result schema-valid;
2. projector нашёл low confidence, conflict или missing high-value fact;
3. результат влияет на episode/line/funnel proposal;
4. свободна 3.7 quota;
5. для этого materiality digest escalation ещё не выполнялся.

Недоступность 3.6 сама по себе не является причиной тратить 3.7.

---

## 3. Event-driven health и API UI

### 3.1 Запрет постоянных проверок

- [ ] Удалить hourly metadata health cron, countdown и automatic batch.
- [ ] Запретить synthetic `generateContent` canary во всех обычных режимах.
- [ ] Старую generation-probe команду сделать явной quota-consuming diagnostic,
      которая без специального флага отказывается работать.
- [ ] Page load, refresh, polling и charts читают только DB/cache snapshot.
- [ ] Manual metadata GET допустим только по явному клику администратора в
      раскрываемой диагностике.
- [ ] Metadata-result маркируется как `auth/model capability`, а не quota или
      generation health.

### 3.2 Состояния project/model

Закрытый набор:

```text
confirmed_recent_success
available_assumed
in_flight
rpm_limited
tpm_limited
rpd_exhausted_until_reset
provider_degraded
auth_failed
model_unavailable_for_project
accounting_unknown
not_configured
```

Семантика:

- `confirmed_recent_success` — свежая реальная generation attempt завершилась
  success; freshness задаётся versioned UI policy;
- `available_assumed` — credential настроен, активного provider-confirmed block
  нет, но свежего generation evidence тоже нет;
- после истечения block/cooldown без новой попытки состояние становится
  `available_assumed`, а не зелёным success;
- реальный 429 задаёт metric-specific block даже при положительном local
  remaining;
- UI никогда не обещает точный provider remaining, которого API не отдаёт.

Пример безопасной подписи:

```text
Доступна по локальному состоянию
Последняя реальная генерация: …
Активных ошибок или известных лимитов нет
```

Пример provider drift:

```text
Gemini 3.7 Flash · Проект 4
Дневная квота исчерпана по ответу провайдера
Локально учтено: 18/20
Возможен расход вне этого приложения
Сброс: <точное Pacific reset time>
```

### 3.3 Матрица четыре модели × шесть проектов

В UI всегда существуют строки:

- Gemini 3.7 Flash;
- Gemini 3.6 Flash;
- Gemini 3.5 Flash;
- Gemini 3.5 Flash Lite.

Матрица строится из configuration manifest + left join к usage state. Нулевой
traffic не требует заранее создавать 24 ledger rows.

По модели показывать:

- aggregate RPM/TPM/RPD pool;
- used/limit/remaining **local estimate**;
- in-flight/reserved;
- provider-confirmed blocks и reset;
- usage по lane/task;
- fallback/downgrade counts;
- p50/p95 latency;
- last real success/failure.

Раскрытие показывает `Проект 1 … Проект 6`:

- safe quota identity label;
- configured state;
- current model state;
- RPM/TPM/RPD;
- last real request/failure;
- cooldown/reset;
- lane/task, потратившие quota.

API/DOM не содержат key value, env alias, HMAC fingerprint, реальный Google
project ID, prompt, customer text или raw provider error.

### 3.4 Model-first UX

Три вкладки:

1. `Квоты` — модели, pool totals и раскрытие шести проектов;
2. `Маршруты` — определения live-классов, chains, active policy и emergency pin;
3. `Попытки` — redacted request graph.

Request graph:

```text
customer turn
→ routing decision
→ candidate plan / waves
→ attempted / not attempted candidates
→ provider outcomes
→ winner
→ reply / holding / recovery / manager route
→ Meta receipt
```

Admin capabilities:

- [ ] Видеть active routing/accounting policy versions.
- [ ] Включать `pinned` live-model максимум на 60 минут; default — `adaptive`.
- [ ] Смотреть dry-run preview и прогноз расхода по lane до применения policy.
- [ ] Применять новую immutable policy version с audit actor/time/reason.
- [ ] Не иметь возможности вручную переписать usage или скрыть provider 429.

Responsive/accessibility:

- [ ] 360 px — model accordions, RPM/TPM/RPD вертикально, без page-level
      horizontal scroll.
- [ ] Текст не меньше 14 px; interactive targets не меньше 44×44.
- [ ] Keyboard, visible focus, WCAG AA, reduced motion.
- [ ] Один `aria-live=polite` region; polling не зачитывает всю таблицу заново.
- [ ] Сохраняется Django template + vanilla JS и TwoComms dark visual language.

---

## 4. Quota/accounting V2

### 4.1 Project identity

- [ ] Настроить шесть стабильных `project_identity`, не содержащих секрет.
- [ ] Связать quota/cooldown с `(project_identity, model)`.
- [ ] Ротация credential сохраняет quota identity.
- [ ] CUSTOM/ENV duplicates дедуплицировать по HMAC fingerprint; digest не
      возвращать клиенту и не логировать публично.
- [ ] Неизвестный CUSTOM не считается седьмым quota project.
- [ ] Configuration check падает на duplicate/unknown mapping до включения
      enforcement.

### 4.2 Durable request graph

`GeminiRequest`:

```text
request_id
lane / task_class
logical_turn_id / source lineage
policy_version
authority_snapshot_version
immutable_candidate_plan
deadline
winner_attempt_id
terminal_resolution
timestamps
```

`GeminiAttempt` или расширенный `GeminiRequestAttempt` хранит одну попытку
кандидата. FSM:

```text
planned
→ reserved
→ provider_started
→ succeeded | failed | timeout_ambiguous | succeeded_late
```

Отдельный terminal `cancelled_pre_dispatch` разрешён только до
`provider_started` и единственный возвращает quota reservation.

- [ ] Каждый considered candidate имеет row/event или immutable plan entry.
- [ ] `not_attempted_reason` покрывает circuit, lease, quota, deadline,
      superseded wave и policy stop.
- [ ] Один atomic winner; late success не создаёт второй reply/send.
- [ ] Reply/recovery/Meta receipt связаны с request ID.
- [ ] Нельзя сохранять key value, prompt или provider body.

### 4.3 `GeminiQuotaState` и policy profiles

State key: `(project_identity, model)`.

Хранить:

- Pacific RPD day, used/reserved и conservative uncertainty;
- rolling 60-second RPM events;
- rolling input/prompt TPM events;
- model-scoped in-flight permits;
- active metric-specific provider block;
- external usage/drift flag;
- last success/failure/latency;
- quota profile version, source, observed/effective dates.

Правила:

- [ ] `ZoneInfo("America/Los_Angeles")`, включая PST/PDT transitions.
- [ ] RPD относится к Pacific calendar day.
- [ ] RPM/TPM — rolling 60 seconds, не fixed window от первой попытки.
- [ ] TPM считает input/prompt tokens; output tokens показываются отдельно.
- [ ] Estimated input резервируется до dispatch; actual usage reconciles
      idempotently.
- [ ] Timeout сохраняет conservative input estimate.
- [ ] Settlement относится к original dispatch day даже после midnight.
- [ ] Structured 429 хранит metric/quota ID/dimensions/retry delay без raw body.
- [ ] Provider 429 сильнее local estimate и ставит `external_usage_suspected`.
- [ ] Unknown model/budget/project — system-check error, не unlimited capacity.

### 4.4 Admission и DB boundaries

- [ ] Один gateway обслуживает live, recovery, CRM analysis, memory, UGC/media,
      reports, checker и manual override.
- [ ] Статический тест запрещает прямой `generateContent` вне gateway.
- [ ] Candidate snapshot загружается bulk; до первого provider call — не более
      шести SQL reads.
- [ ] Reservation берётся непосредственно перед dispatch, не на весь будущий
      plan.
- [ ] Admission под коротким lock проверяет RPD, rolling RPM/TPM, block и permit.
- [ ] Network I/O выполняется вне DB transaction.
- [ ] Settlement idempotent по attempt ID.
- [ ] Background/accounting outage приводит к defer.
- [ ] Live при accounting outage получает максимум один emergency Lite call,
      затем deterministic/manager fallback; scarce models fail closed.

### 4.5 Concurrency и hedging

- Один model-scoped permit для 3.7/3.6/3.5 на проект.
- До двух concurrent Lite calls на проект.
- Analysis 3.6 не блокирует live Lite того же проекта.
- Scarce-model hedging по умолчанию отсутствует.
- Bounded Lite hedge имеет максимум два реально dispatched calls; второй
  запускается адаптивно по latency evidence.
- Lease/reservation живут до реального completion, не до выбора winner.
- Slow timeout ограничивает дальнейшие calls по deadline; полный candidate plan
  всё равно сохраняется.

### 4.6 Schema и shadow rollout

- [ ] Additive V2 schema, все behavior flags выключены.
- [ ] Новые таблицы InnoDB на disposable production-shaped MariaDB.
- [ ] Исправить engine registry для существующей quota-таблицы.
- [ ] Shadow начать после ближайшей Pacific midnight, а не с ложного mid-day 0.
- [ ] Старые attempts backfill только как telemetry, не как точный remaining.
- [ ] Собрать два полных Pacific days shadow data без изменения route.
- [ ] Проверить: каждый `provider_started` имеет одну reservation и settlement.
- [ ] Enforcement включать: background → recovery → live 5% → 25% → 100%.
- [ ] Routing policy canary отделён от accounting enforcement.
- [ ] Rollback — режим/feature flag/revert; telemetry не удалять и migrations не
      откатывать разрушительно.

---

## 5. Durable CRM analysis

### 5.1 Materiality вместо бесконечных проходов

Для `(client, episode)` хранится materiality digest. Новый pass создаётся только
если:

- появился новый завершённый `CustomerTurn`;
- изменился authoritative payment/order/delivery fact;
- изменились product/line/recipient;
- возникла новая objection/defer/UGC/media/manager boundary;
- snapshot отсутствует, stale либо относится к другой revision/episode.

Не запускают analysis:

- bot echo, reaction, одиночное «ок» без material change;
- unchanged postback;
- inactivity без нового evidence;
- повтор того же watermark/revision/digest;
- уже обработанный media artifact;
- таймерная проверка «оплатил ли клиент».

Cadence:

```text
due_at = min(last_relevant_event + 90 секунд,
             first_unanalysed_event + 10 минут)
```

Quiet window сдвигают только material events. Один pending job coalesces новые
события и обрабатывает новый watermark; он не создаёт параллельные passes.

### 5.2 Payment wait — backend event, не LLM polling

1. Клиент сообщает о намерении оплатить.
2. Backend фиксирует `awaiting_payment`, proposal/invoice expiry и ожидаемый
   webhook.
3. Gemini не перепроверяет состояние через 10 минут.
4. Verified webhook немедленно обновляет authoritative state.
5. Изменение создаёт один material analysis job.
6. При отсутствии оплаты 12-часовой proposal expiry обрабатывается backend.
7. Gemini вызывается только если нужен новый смысловой customer response.

### 5.3 Immutable `AnalysisSnapshot`

Snapshot содержит:

- client/episode/line, watermark, revision, materiality digest;
- interaction type;
- purchase probability `0..1` и confidence;
- evidence message IDs и source roles;
- active objection;
- product/garment/print/fit/size/color/qty proposals;
- recipient/gift/occasion, только если это сообщил клиент;
- deferred intent/date condition;
- repeat-purchase/LTV signals;
- detected language;
- uncertainties/conflicts;
- prompt-injection/adversarial risk;
- live-agent inconsistency signal;
- suggested funnel transitions и next action;
- model/project/attempt, prompt/schema/routing policy versions;
- latency/tokens/timestamps.

Purchase probability rules:

- paid/order truth задаётся backend, а не score;
- manager-only evidence не повышает customer intent;
- explicit no-buy/opt-out имеет deterministic effect;
- язык, страна и стиль речи не являются признаками платёжеспособности;
- score append-only time series; старое значение не переписывается;
- current projection читает только fresh compatible snapshot.

### 5.4 Proposals и deterministic projector

Допустимые proposals:

```text
close_node
invalidate_node
open_subfunnel
switch_active_line
start_repeat_episode
record_objection
record_deferred_intent
update_probability
request_clarification
```

Projector проверяет:

- source role и evidence IDs;
- current episode/line/revision;
- current payment/order truth;
- product/variant applicability;
- manager authority;
- opt-out/takeover;
- confidence threshold;
- superseding events.

Модель никогда напрямую не создаёт order/invoice, не отмечает payment, не
подтверждает stock/price, не выдаёт discount, не снимает takeover, не отправляет
reminder и не меняет durable transcript.

### 5.5 Manager evidence и freshness

- [ ] Один current-snapshot selector проверяет episode, line, watermark,
      materiality digest, authority fingerprint и compatible schema/policy.
- [ ] Несовпадение возвращает `stale/unknown`, а не старый current intent.
- [ ] Manager-only claims нормализуются в `MANAGER_OBSERVATION`.
- [ ] Mixed transcript разделяет claims по source role.
- [ ] Follow-up и probability игнорируют manager-only evidence.
- [ ] Исторический snapshot остаётся доступным в timeline с датой и причиной
      supersede.

### 5.6 Prompt-injection boundary

- Customer, manager и previous-model text — untrusted data.
- Evidence/quotes отделены от system instructions.
- Analysis output ограничен versioned schema.
- Injection сохраняется как redacted risk signal, не как автоматический бан.
- Risk signal не способен изменить routing policy, payment, discount или system
  prompt.
- `ORDINARY_LIVE` проходит тот же deterministic guard до provider call.
- Повторные attacks уменьшают compute budget и создают human review, но не
  скрывают легитимные customer messages.

### 5.7 Typed memory

`IgMemoryFact`:

```text
scope: client | episode | line | order | case
fact_key / schema_version
typed_value
confidence
source_role / evidence_message_ids
producer / policy_version
observed_at / valid_until
invalidated_at / superseded_by
sensitivity / retention_class
```

- [ ] Analysis snapshot — источник proposals, не готовая исполняемая память.
- [ ] Deterministic projector применяет facts.
- [ ] Старый `MEMORY_EVERY = 8` Gemini summary-call удалить после shadow parity.
- [ ] Narrative summary хранить отдельно как untrusted display artifact.
- [ ] Manager text сохранять как manager observation/note.
- [ ] Live prompt загружает только relevant facts current episode/line.
- [ ] Authoritative payment/order/price/stock не дублируются как memory truth.
- [ ] Inbound без исходящего ответа всё равно может обновить durable analysis.

---

## 6. Future funnel registry и подворонки

Gemini V2 не заменяет funnel registry. Analysis пишет generic proposals;
versioned backend definitions и projector владеют переходами.

### 6.1 Branch types

```text
catalog_purchase
custom_print
repeat_purchase
gift_recipient
payment_follow
post_purchase_ltv
exchange_return
support_case
ugc_reward
```

### 6.2 Definition и state

```text
client_id
episode_id
branch_type
line_id / recipient_id
definition_key / definition_version
required | optional
open | satisfied | invalidated | superseded | blocked
typed_value
evidence
closure_method
confidence / reason
timestamps
```

Все transitions append-only. Новая definition version не переписывает старый
episode.

### 6.3 Checkout-link blockers

- exact product;
- garment;
- print либо explicit `not_applicable`;
- fit;
- size;
- sellable color/variant;
- required option axes;
- quantity;
- exact current price.

Contact/delivery/payment details собираются на checkout и сами по себе не
блокируют выдачу ссылки.

### 6.4 Transition rules

- [ ] Product switch инвалидирует dependent print/fit/size/color/options/price
      и proposal.
- [ ] Новый recipient создаёт отдельную line/sub-funnel.
- [ ] Repeat purchase создаёт новый episode до генерации ответа.
- [ ] Exchange/return не становится новой продажей без explicit purchase intent.
- [ ] Gift/occasion сохраняется пассивно, если сообщил клиент; бот не обязан
      спрашивать.
- [ ] `from_history`/`inferred` nodes требуют подтверждения до irreversible
      checkout action.
- [ ] Custom print имеет отдельные base garment, fit/size/color/qty,
      artwork/design/placement/zones, manufacturability и final-price approval.
- [ ] Future agent добавляет definition/nodes без изменения Gemini gateway.

---

## 7. Analytics read model

Для каждого episode хранить sanitized current outcome projection:

- starting source/ad/product;
- highest reached funnel node;
- current/final state;
- conversion probability timeline;
- primary objection и drop-off reason;
- discount steps;
- manager takeover;
- repeat/LTV status;
- authoritative purchase/payment/order outcome;
- customer/bot/manager turn counts;
- model usage, fallback и provider failures;
- apology/holding/recovery;
- reply latency;
- analysis version/freshness.

Запрос «последние 100 клиентов» читает:

1. typed episode summaries;
2. funnel node outcomes;
3. analysis snapshots;
4. technical attempt/incident aggregates.

Raw transcript нужен только для точечного drilldown аномалии.

Отчёт обязан отвечать:

- где чаще всего останавливается покупка;
- какие objections лидируют;
- каких product/size/print facts чаще не хватает;
- какие nodes чаще откатываются;
- какие ads приводят к каким products;
- сколько repeat purchases;
- где происходят bot errors/fallback/apology;
- какой model/RPD расход у каждой lane;
- какие manager decisions коррелируют с закрытием;
- какие patterns коррелируют с purchase, без заявления причинности.

Aggregates используют distinct clients/episodes, явное time window, timezone,
cohort, exclusions и sample cutoff.

---

## 8. Assisted checkout, consent, reminders и discounts

### 8.1 Assisted checkout

- [ ] Proposal/access link живёт 12 часов как commercial snapshot.
- [ ] Это не 12-часовая stock hold: stock/price проверяются повторно.
- [ ] Inventory/promo reservation и provider invoice живут 25 минут.
- [ ] Monobank payload получает `validity=1500`.
- [ ] Живой invoice переиспользуется; expired перевыпускается после revalidation.
- [ ] Invoice attempts append-only one-to-many.
- [ ] Ambiguous invoice не перевыпускается до reconciliation.
- [ ] Late payment старого invoice не создаёт второй order.
- [ ] Legacy bot-payment invoice остаётся 24-часовым.
- [ ] По умолчанию предлагается полная online payment и полная цена сайта.
- [ ] Только по прямому вопросу о COD объяснять 200 грн prepayment; эта сумма
      входит в полную стоимость, остаток оплачивается при получении.
- [ ] Custom print — полная оплата.
- [ ] Verified 200/full payment создают одну Purchase на full discounted order
      value и отдельный paid value; дополнительный Lead/Purchase запрещён.
- [ ] Provider-confirmed pickup детерминированно закрывает COD remainder.

### 8.2 Consent и Meta transport

- [ ] После verified 200/full payment, только внутри реально открытого Meta
      window, отправить thank-you и одну прозрачную кнопку `Так, отримувати`.
- [ ] Business consent хранит client/order, topics, exact localized copy/version,
      source click/message, channel, time, policy и revocation.
- [ ] Topics `order_updates` и `bonuses` раздельны, даже если UI объединяет CTA.
- [ ] Transactional status не содержит promo без `bonuses` consent.
- [ ] Meta transport capability/token хранится отдельно от business consent.
- [ ] Payment success page всегда содержит безопасный `Вернуться в Direct` CTA.
- [ ] Web click сам по себе не открывает messaging window; inbound/postback — да.
- [ ] Вне окна auto-send разрешён только при доказанной Meta capability.
- [ ] `HUMAN_AGENT` автоматическим ботом не используется.
- [ ] Без capability создаётся manager task или ожидание следующего inbound.
- [ ] Opt-out/revocation немедленно прекращает обе темы.

### 8.3 `IgReminderIntent`

```text
client / episode / line
reason / product snapshot
desired_at Europe/Kyiv
evidence
revision
channel eligibility
status / cancellation reason
```

- [ ] Расплывчатое «после зарплаты» требует уточнить дату/условие; таймер не
      выдумывается.
- [ ] Новый inbound, purchase, product switch, opt-out, takeover или superseding
      episode отменяет stale reminder до provider I/O.
- [ ] No new evidence означает no repeated Gemini analysis.
- [ ] Parcel arrival code 7, pickup и storage deadline берутся только из Nova
      Poshta truth.
- [ ] Неподтверждённый срок хранения не показывается.
- [ ] `Нагадати пізніше` должен иметь receipt-backed delivery; manager-task,
      который sender не отправляет, не считается готовым.
- [ ] Closed-window reminder не отправляется ботом без transport capability.

### 8.4 UGC и price-objection discounts

Общий gate:

- любая новая скидка требует authenticated idempotent Telegram callback;
- перед send callback повторно проверяет actor, evidence, current episode,
  refund/return/service case, lifetime reward, opt-out и Meta eligibility;
- auto-grant запрещён;
- approval вне окна становится `approved_waiting_transport`;
- existing rewards не переписываются.

UGC policy:

- one lifetime reward, one use, 90 days;
- qualified promised positive story: клиент в TwoComms, видимая отметка бренда,
  не hidden; manager actions `10% / отказ`;
- unsolicited/borderline UGC без обещания: `5% / 10% / отказ`;
- customer-visible enablement проходит отдельный legal/platform policy gate;
- reward привязан к evidence и не доказывает purchase без order truth.

Price-objection policy:

1. Явная дороговизна + сохранённый purchase intent; молчание не objection.
2. Сначала бот объясняет только проверяемую ценность товара.
3. Никаких утверждений о «китайской ткани» конкурентов или внутренней марже.
4. Затем manager alert; бот говорит только, что уточнит возможность.
5. Первая рекомендуемая ступень — 5%.
6. После явного отказа именно из-за цены допустим один 10%-alert.
7. После отказа от 10% ladder закрывается для текущего episode.
8. Точный процент сообщается только после approval.

---

## 9. Runtime stabilization и integration order

### 9.1 До новых workers

- [x] Lightweight stdlib supervisor: parent ждёт child и записывает SHA,
      PID/start ticks, uptime, exit code/signal и shutdown phase.
- [ ] Обработать SIGTERM/SIGHUP/SIGINT, outer fatal journal,
      `threading.excepthook`, bounded rotation и stack dump. Сигналы, fatal
      journal, exception hook и bounded files покрыты S1; stack dump ещё не
      доказан, поэтому составной пункт открыт.
- [ ] Разделить `process_alive`, `main_progress`, `active_lane` и worker pulses.
      Process/main разделены и production показывает fresh `idle`; отдельный
      `active_lane`/worker-pulse contract остаётся открытым.
- [x] Один bounded background coordinator под общим flock.
- [x] Не более одного heavy background Django process одновременно обеспечено
      единым cron admission lock и подтверждённой production crontab topology.
- [x] Каждая lane имеет одного owner; daemon/cron duplicate owners удалены.
- [ ] В daemon оставить latency-sensitive inbound/recovery/permission work.
      Daemon всё ещё содержит существующие bounded threads анализа, discovery,
      lifecycle и follow intelligence; дальнейшее сужение не доказано.
- [x] Analysis остаётся durable queue и не вынесен в отдельный новый process.
- [x] Hourly Gemini metadata job и scheduled health expectation удалены;
      metadata доступна только как manual diagnostic.
- [x] UI/status/watchdog используют общий process/main health contract;
      production snapshot: `running`, main `idle`, fresh, not stalled.
- [ ] Restart backoff: 1s → 5s → 15s → 60s; три short exits за 10 минут дают
      один technical alert, не customer message. Логика покрыта тестами, но
      production restart-storm outcome и 48-часовой exit rate ещё не доказаны.

**S1 verification evidence (2026-08-30):**

- local/GitHub/server/supervisor/child SHA:
  `e62bedf5df570af9a46fe0e760eb248819cccefa`;
- server tracked-clean; migration set unchanged;
- supervisor PID/start-ticks identity и supervisor/child release SHA совпадают;
- production status: process fresh, main fresh/`idle`, `running`, not stalled;
- crontab: one stdlib watchdog + one sequential coordinator; durable tasks и
  Nova Poshta используют один heavy lock; automatic metadata и legacy Instagram
  periodic lines отсутствуют;
- test evidence: 68 low-level, 134 Django runtime и 97 deploy tests; local
  `manage.py check` и migration drift clean;
- initial soak **не прошёл**: supervisor зафиксировал внешний SIGKILL child PID
  `77835` после `124.943 s` и восстановил его через 1 с без supervisor
  signal/reload/stop;
- после S1b Selector correction текущий runtime остаётся на том же SHA, status
  `running`, process/main fresh, main `idle`; external selector state `3/0` не
  является Git divergence;
- RSS/PSS/private before/after из раздела 0.4 — snapshots, а не p95/fPMEM proof.

Runtime gate:

Baseline перезапущен с `2026-08-30T15:48:03+03:00`; deadline
`2026-09-01T15:48:03+03:00`; automation active. Pre-fix SIGKILL остаётся в
истории и не исключается из incident evidence.

- [ ] 48 часов без unexplained daemon exits.
- [ ] PMEM p95 ≤750 MiB, max ≤850 MiB.
- [ ] Zero PMEM/NPROC faults.
- [ ] Не более одного heavy background Python process.
- [ ] Нет duplicate lane owners, stale locks и MariaDB connection incidents.
- [ ] Live reply p95 не ухудшился.

### 9.2 Integration barrier

- [ ] Перед каждым slice: refs, worktrees, dirty status и overlap audit.
- [ ] Чужие dirty changes не переносить механически.
- [ ] Новый upstream commit в затронутом файле отменяет прежний review до
      повторной проверки.
- [ ] Работать в clean isolated worktree от актуального `origin/main`.
- [ ] Production fast-forward только через supported procedure из `AGENTS.md`.
- [ ] Untracked operational server files не менять.

### 9.3 Release slices

1. docs/parity;
2. daemon/cron stabilization;
3. immediate routing/reply correctness;
4. V2 schema;
5. shadow accounting;
6. enforcement;
7. adaptive routing policy;
8. analysis/memory;
9. funnel registry;
10. checkout/consent/reminders;
11. API UI.

Каждый slice имеет собственные migrations/tests/feature flags/production proof.
Не объединять schema expansion с live enforcement.

---

## 10. Test matrix и acceptance gates

### 10.1 Routing

- [ ] Classification table для `NO_MODEL`, `ORDINARY_LIVE`, `COMPLEX_LIVE`.
- [ ] Exact price при exact product не становится complex по слову «цена».
- [ ] Ambiguous product image становится complex и создаёт один artifact.
- [ ] Story mention: deterministic ack, zero chat Gemini, один assessment.
- [ ] Voice: один artifact, без повторного analysis.
- [ ] Ad referral: deterministic resolver first, 3.7 только при ambiguity.
- [ ] Ordinary/complex chains работают model-major через шесть проектов.
- [ ] Fast 429 rotating projects; slow timeout соблюдает SLA и пишет skipped.
- [ ] Emergency pin истекает максимум через 60 минут.

### 10.2 Accounting/concurrency

- [ ] Pacific DST: winter/summer reset, spring/fall transitions.
- [ ] Rolling RPM/TPM boundary и request across midnight.
- [ ] Последний RPD/RPM/TPM slot под MariaDB concurrency.
- [ ] External quota drift и structured `RetryInfo`.
- [ ] 401/403/404/408/429/5xx, invalid payload, safety, empty response.
- [ ] Timeout ambiguity не возвращает consumed reservation.
- [ ] One winner/receipt under hedge and crash.
- [ ] 50-turn burst: bounded threads/connections и один reply на turn.
- [ ] Статический запрет прямого provider call вне gateway.

### 10.3 UI/health

- [ ] Load/refresh/polling делают zero provider calls.
- [ ] Полная 4×6 zero-usage matrix без заранее созданных DB rows.
- [ ] Real traffic меняет только соответствующую project/model пару.
- [ ] Cooldown expiry даёт `available_assumed`, не fake success.
- [ ] Secrets/project IDs/customer text отсутствуют в API/DOM.
- [ ] Empty/stale/error/external-drift states.
- [ ] Playwright 360/768/1440; axe serious/critical = 0.

### 10.4 Analysis/memory/funnel

- [ ] No new evidence → no new analysis job.
- [ ] 90s quiet / 10m max-staleness и coalescing.
- [ ] `awaiting_payment` ждёт webhook/12h expiry без LLM polling.
- [ ] Manager-only evidence не повышает probability и не создаёт follow-up.
- [ ] Prompt injection не меняет business/system state.
- [ ] Typed memory supersede/invalidate/reset boundaries.
- [ ] Product/recipient/repeat branch transitions.
- [ ] Required checkout nodes блокируют ссылку, optional gift — нет.
- [ ] Last-100 report не сканирует raw transcript.

### 10.5 Commerce/consent/reminders/discounts

- [ ] 12h proposal не удерживает stock 12 часов.
- [ ] 25m invoice reuse/reissue/ambiguous/late payment.
- [ ] 200/full payment дают одну Purchase.
- [ ] Consent exact copy/version, topics, revoke и closed-window no-send.
- [ ] Payment success CTA сам не открывает window.
- [ ] Reminder cancellation on inbound/purchase/switch/opt-out/takeover.
- [ ] Authoritative Nova Poshta dates only.
- [ ] UGC promise-aware 5/10/reject и one-lifetime constraint.
- [ ] Price ladder 5 → 10 → closed, stale callback blocked.

### 10.6 Final release proof

- [ ] Shared CPython 3.14.6 / Django 6.1 runtime использован для команд.
- [ ] `manage.py check`, related suites, compile и migration drift зелёные.
- [ ] Disposable MariaDB migration/interrupt/retry и InnoDB engine audit зелёные.
- [ ] `git diff --check` зелёный.
- [ ] Никаких synthetic messages живым клиентам, Meta test events или generation
      probes.
- [ ] Production deploy только через `main` и supported SSH pull.
- [ ] Небольшой последовательный endpoint smoke, без broad crawl.
- [ ] `local = GitHub = production = running daemon SHA`.
- [ ] Migrations/engines/queues/leases/PID здоровы.
- [ ] 48-hour production soak завершён без unexplained exits.

---

## 11. Defaults для следующего агента

- Ordinary live означает: backend facts готовы, модель только формулирует.
- Complex live означает: media/ambiguity materially меняет выбор или funnel.
- Изображение/аудио/сложный product-ad-fit reasoning начинает с 3.7.
- Durable analysis начинает с 3.6; 3.7 — только gated escalation.
- Все шесть проектов входят в candidate plan, но это не означает шесть
  одновременных provider calls.
- Health строится по реальному traffic evidence без probes.
- Нет traffic и нет active failure = `available_assumed`.
- Analysis не повторяется без нового materiality digest.
- Memory и aggregate statistics строятся из typed snapshots/events.
- Python/Django сохраняются: bottleneck — process fan-out, DB coordination и
  provider latency, а не язык.
- Production MariaDB — runtime/business truth; SQLite — быстрый структурный
  test layer.
- Сильная модель не получает право менять authoritative business state.

## 12. Ссылки

- Общий implementation order: `04_IMPLEMENTATION.md`.
- Production incident handoff: `07_PRODUCTION_TECHNICAL_DELAY_SPAM_HANDOFF_2026-08-27.md`.
- Gemini quota semantics: <https://ai.google.dev/gemini-api/docs/rate-limits>.
- Meta Instagram API collection: <https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api>.
