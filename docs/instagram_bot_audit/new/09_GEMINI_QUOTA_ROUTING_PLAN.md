# 09 — Gemini Router V2, квоты, live-классы и CRM-анализ

Дата фиксации контракта: 2026-08-30.

Статус: **первая production wave Gemini Router V2 и production hardening
задеплоены 2026-08-31. Code release local/GitHub/production/supervisor совпал на
`28707634c`; migrations
`orders.0057–0058` и `management.0177–0185` применены. Corrected live routing,
event-driven health, S3b accounting shadow и model-first cockpit работают на
production. Analysis V2, materiality, Typed Memory и Assisted Checkout
сознательно остаются `off`; funnel registry/analytics/consent/reminders ещё не
входят в production release. Транспорт visual preview задеплоен, но реальный
commerce/consent/payment/ТТН orchestration остаётся open и описан в
`10_VISUAL_MESSAGING.md`. Новый behavior soak идёт с baseline
`2026-08-31T18:37:02+03:00`; последующий docs-only parity reload является
объяснённым restart без изменения tracked Python и не закрывает gate раньше
`2026-09-02T18:37:02+03:00`.**

Оценка «≈65% большого плана» — ориентация по крупным блокам, не Definition of
Done. Shipped: routing/runtime/UI/schema/shadow foundation. Open: enforcement,
real p95/soak, Analysis/Memory canaries, funnel registry, last-100 analytics,
Assisted Checkout, combined consent/reminders/discount enablement и VisualPlan.

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

### 0.1 Текущая граница после production Gemini V2 release

| Область | Наблюдаемое состояние | Что обязательно перепроверить |
|---|---|---|
| Code release local/GitHub `main` | `28707634cf4f26ea47f7844676134414ee6b5dd8`; финальный docs-only HEAD читать через `git rev-parse HEAD`, потому что commit не может самоссылочно хранить собственный hash | повторять parity перед каждым следующим merge |
| Production checkout | code release `28707634cf4f26ea47f7844676134414ee6b5dd8`; tracked diff clean, существующие untracked runtime/diagnostic files не тронуты | после документационного commit снова fast-forward и parity proof |
| Running runtime | supervisor/child code SHA `28707634cf4f26ea47f7844676134414ee6b5dd8`; sample PID `704548`, identity true, `restart_count=0` | новый 48-hour soak и live-reply p95 ещё открыты |
| Daemon health | `state=running`; process pulse fresh; main progress fresh, `idle`, не stalled | 48-часовой soak и live-reply latency ещё не доказаны |
| Initial S1 soak | **FAILED early:** child PID `77835` получил внешний `SIGKILL` 2026-08-30 15:23:40 Europe/Kyiv после `124.943 s`; supervisor signal/reload/stop отсутствовали; recovery через 1 с сработал | не считать S1 soak закрытым и не стирать incident из baseline |
| Correlation | selector фактически передавал `LSAPI_CHILDREN=10`, несмотря на stale public `.htaccess` со значением 3; наблюдались expansion и повторные lswsgi `SIGKILL` | fPMEM недоступен: LVE/PMEM-причина высоко вероятна, но формально не доказана |
| Authorized S1b | production Selector изменён только `LSAPI_CHILDREN: 10→3`; добавлен `LSAPI_EXTRA_CHILDREN=0`; non-LSAPI digest сохранён, env count `75→76` | это external production state, а не tracked-file/SHA divergence |
| S1b runtime snapshot | selector/app restart выполнен под exact bot maintenance; health/home/catalog последовательно вернули 200; все lswsgi env показывают `3/0`; process group после старта master+2, верхняя цель master+3 | process/RSS цифры являются snapshots, не steady-state p95 |
| S1b memory snapshot | comparable RSS `950732→588240 KiB`, PSS `666577→390312 KiB`, private `583960→298036 KiB` | не выдавать snapshot за fPMEM или PMEM p95 proof |
| Active soak | behavior baseline `2026-08-31T18:37:02+03:00`; deadline `2026-09-02T18:37:02+03:00`; heartbeat должен быть обновлён после финального docs parity | release/hotfix сбросили предыдущий gate; закрывать только полной новой выборкой |
| Production migrations | `management.0177–0185` и `orders.0057–0058` applied; требуемые 13 таблиц существуют, IG non-InnoDB count `0` | Analysis/Memory/Checkout feature modes остаются off |
| Runtime routing | corrected S2 deployed: Ordinary начинает с Lite, Complex — с 3.7, NO_MODEL не вызывает provider; legacy `gemini_model=3.7` больше не является routing authority | доказать реальным traffic trail и reply p95 |
| Production UI | Chrome authenticated smoke: `Квоти / Маршрути / Спроби`, 4 model rows × 6 projects, routes=4, attempts rows=18; 360px без horizontal overflow, controls=44px, app console errors=0 | future UI changes снова проходят 360/768/1440 |
| Ключи | шесть credentials + explicit `gemini-project-1…6`; dedicated accounting HMAC; private media root pre-created owner/mode `0700` | opaque identities не являются реальными Google project IDs и не выводятся в DOM |
| Cron ownership | один stdlib watchdog, один sequential Instagram coordinator; durable tasks и Nova Poshta используют общий heavy-process lock | cadence/LVE steady state подтвердить soak-выборкой |
| Removed owners | automatic metadata cron = 0; legacy Instagram periodic owner lines = 0 | manual metadata остаётся только явной диагностикой |
| Production hotfix | `ig_follow_intelligence` collation loop исправлен mysqlclient option `utf8mb4_unicode_ci`; HTML-as-JSON guard добавлен; после нового daemon spawn follow errors `0`, health `200`, clients API JSON `200` | продолжать проверку console/API в soak |
| Post-release visual transport | `3ec06d308`: native quick-reply collision fixed; `2a5406781`: receipt-first Button/Generic Template + safe preview actions; `3e94b8e24`: false historical purchase correction; `7fd83f838`: 30s worker-recovery UX | это transport/data/runtime evidence, не закрытие боевого VisualPlan/funnel |
| Owner visual proof | preview `2801–2806` receipt-backed; два preview tap прошли `NO_MODEL`; purchase/consent/takeover mutations `0` | permanent choreography/acceptance — `10_VISUAL_MESSAGING.md` |
| Legacy analysis debt | 22 terminal failed jobs остаются отдельным typed-retry debt; 10 orphan request graphs idempotently terminalized без provider replay; после deploy real 3.6 `conversation_reanalysis` succeeded одним candidate и создал snapshot | typed job failure/reopen policy; не bulk-reset без evidence |
| False-purchase/memory repair | superseded review не воскресает; buyer=false, purchases=0, current episode сохранён, stage `checkout`; stale cross-episode summary подавлен; double reconcile `0/0/0` | Typed Memory projector всё ещё off/open |
| Shared-host LVE | воспроизводились пики 1,25–1,28 GiB при лимите 1 GiB | 48-часовой soak после runtime-среза |
| LSAPI request pressure | immediate relief deployed: 20 rows, 130147 B/21 SQL с middleware против 564KB/405 SQL; poll 15–120s, hidden zero, status 5s/30s, last-good UI | revision/delta, multi-tab coalescing и zero-new-503 soak остаются |
| Release tests | `579` combined + `264` routing/health/UI + `31` full-schema tests; focused MariaDB InnoDB/reaper race PASS; check/migration drift clean | fresh full MariaDB graph отдельно открыт на pre-existing `storefront.0097` assertion |

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
- Customer-facing visual orchestration принадлежит
  `10_VISUAL_MESSAGING.md`; один turn создаёт не более одного logical
  VisualPlan, а model не создаёт payload/URL/price/ТТН/consent actions.
- Combined opt-in показывает одну кнопку без decline; один tap создаёт два
  отдельно аудируемых grants `order_updates` и `bonuses`.
- Meta-window = 24h от inbound provider timestamp; 20h — internal proactive
  safe deadline. Business consent не является closed-window capability.
- Initial payment card не содержит `Я оплатил`; payment truth принадлежит
  provider webhook/reconciliation, а `PAYLINK_VIEWED` — first-party checkout GET.

### 0.3 Открытые gates

- [x] Current integration/deploy parity: local, GitHub, production checkout,
      supervisor и child совпали на code release
      `28707634cf4f26ea47f7844676134414ee6b5dd8`;
      production tracked-clean. `e62bedf5`/`e7258a059` остаются historical
      release evidence, не current SHA.
- [x] Runtime ownership conversion подтверждена на production: один stdlib
      watchdog, один sequential coordinator, общий heavy-process lock для
      durable/Nova; metadata и legacy periodic owners отсутствуют.
- [x] Engine-registry code gap закрыт в deployed SHA; S1 не требовал новой
      migration.
- [x] First-wave release parity: migrations/static/runtime proof на
      `e7258a059`; post-release fixes/hardening fast-forward до `28707634c`;
      migrations 0177–0185/0057–0058, static/compress и narrow smoke зелёные.
- [ ] Завершить перезапущенный 48-часовой LVE/PMEM/NPROC/daemon-exit soak
      (`2026-08-31T18:37:02+03:00` → `2026-09-02T18:37:02+03:00`) и снять
      live-reply p95. Automation active; ранний pre-fix SIGKILL остаётся в evidence.
- [ ] Corrected S2 задеплоен и UI/health proof зелёный; закрыть пункт после
      real `request_id → attempt graph → reply/Meta receipt` и p95 evidence.
- [ ] S3b shadow writer включён с Pacific-midnight timestamp; дождаться двух
      полных Pacific days без behavior change перед enforcement.
- [ ] Выпустить materiality Slice 1 после release gate: локально он прошёл три
      цикла NO-GO/fix/review, MariaDB kill/resume и финальный PASS, но остаётся
      `off` и не считается production-complete.
- [x] S3b production shadow prerequisites: explicit six-project labels,
      dedicated HMAC, schema/InnoDB/read APIs и observational writer deployed.
      **Не закрывает** следующий пункт: два Pacific days/enforcement ещё open.
- [ ] Funnel registry `0186`: исправить десять NO-GO из `04`/`10`, затем merge,
      migration, shadow parity и production proof. Отдельная ветка не считается
      current main.
- [ ] Last-100 analytics: sanitized episode/read model без raw transcript scan.
- [ ] Combined consent/reminders/discount policy и customer VisualPlan:
      реализовать по section 8 и `10`; preview transport не равен enablement.
- [x] Immediate LSAPI relief: list page20, 15–120s backoff, hidden zero,
      status 5s/30s, last-good JSON и constant query budget задеплоены; production
      130147 B/21 SQL, provider delta 0.
- [ ] Завершить LSAPI pressure track: revision/delta endpoint, multi-tab
      coalescing и zero new origin 503 soak; children не увеличивать.
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

Последний release sample `2026-08-31T14:04:42+03:00`: local/GitHub/server/
supervisor = `e7258a059`; health `200`, dangerous backlog `0`, daemon running,
main `idle`, `restart_count=0`, lswsgi process count `3`. Это новый baseline,
не завершение 48-часового gate.

### 0.5 S2 review gate — первоначальный NO-GO исправлен и first wave deployed

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

Этот стек задеплоен в release `e7258a059`; private root/mapping/migrations/UI
проверены. `[x]` для полного S2 всё ещё ждёт real customer traffic trace и p95.

### 0.6 Локальные additive-срезы после S2

| Slice | Local evidence | Production status |
|---|---|---|
| S3a accounting schema | `0178–0181`; request/attempt/quota/profile contracts; `31` schema tests; five InnoDB tables | applied on production; 4 profiles seeded |
| Checkout terminalization Slice 1 | `orders.0057`; `396` integrated tests; MariaDB partial-DDL/concurrency proof | applied; runtime feature off |
| Runtime capacity auditor | безопасная selector/process/flock атрибуция; `37` targeted tests | code deployed; new 48h soak open |
| Materiality Slice 1 | `0182`; passive content-free ledger; atomic claim cursor; 90s/10m projected telemetry; final independent PASS | applied; mode off + selector legacy |
| Gemini V2 cockpit | model-first `Квоти/Маршрути/Спроби`, 4×6, responsive/a11y; evaluation round 2 PASS | deployed; authenticated provider-free production smoke PASS |
| S3b shadow writer | parent graph/FSM/quota state; exact provider boundary; HMAC/explicit identity; rolling input-token shadow; final independent PASS | applied + shadow active; enforcement absent |
| Checkout Series Slice 2a | `orders.0058`; exact series/generation/winner identity and guards | applied; Assisted Checkout off |
| Gemini V2 read API | provider-free 4×6 quotas/routes/attempts; redacted graph/query budgets | deployed; production `200`, zero provider/write deltas |
| Analysis V2 A2 | immutable Result + generic Proposal; PII-free shadow contracts | applied; mode off |
| S2 correctness amendment | one canonical graph, exact admission, deadline/fallback evidence, lock order | deployed; accounting shadow active |
| Checkout generation S2b | `0184`; 12h proposal, 25m invoice, amount/identity/HMAC/winner/privacy/promo guards | applied; feature off |
| Typed Memory V2 shadow | `0185`; bounded HMAC chain, v2.2 evidence, privacy purge, exact physical schema | applied; mode off, no typed prompt, MEMORY_EVERY=8 |
| Graph/polling/truth hardening | `1ebe3affa`, `d0e35d120`, `9e3dedd80`, `28707634c`; frozen background candidates, provider-free reaper, page20/backoff/N+1 removal, correction tombstone + fresh memory guard | deployed; real 3.6 winner, 10 reconciled graphs, false buyer repair, authenticated Chrome/UI proof |

**Следующий конкретный шаг:** automation ведёт новый production soak до
`2026-09-02T18:37:02+03:00`; real 3.6 request→attempt→snapshot evidence уже
получен, но representative live reply→Meta receipt/p95 ещё открыт. Terminal
legacy 3.6 jobs требуют typed audited retry без generation probes и bulk reset.
Funnel registry `0186` остаётся отдельным NO-GO и не
входит в production. VisualPlan/combined consent — по `10`. Analysis/Memory/
Checkout включать только отдельными canary после shadow/soak gates.

### 0.7 Completion dashboard для handoff

Счётчик после production hardening/code release `28707634c`:

```text
done 87     open 152     blocked 1
raw checklist closure: 87 / 240 = 36.3%
```

Raw percentage консервативен: один schema checkbox и один 48-hour production
gate имеют одинаковый вес. Прежнее «≈65%» — weighted architecture estimate,
которое учитывало deployed foundation; использовать его как DoD нельзя.

| Блок | Evidence status | Что осталось |
|---|---|---|
| First production wave | **100% deployed** | final soak/p95 — отдельный gate |
| Routing/health/cockpit | deployed | representative real traffic trail, 2 admin policy actions |
| Quota/accounting | schema + semantics + shadow deployed | 2 Pacific days, enforcement, full consumer gateway |
| Analysis/Materiality | schema/shadow code deployed, consumer off | typed failures, 3.6 terminal-job recovery, canary |
| Typed Memory | schema deployed, mode off | projector/prompt parity, supersede/invalidate, remove legacy summary |
| Funnel registry | **blocked / NO-GO** | 10 blockers, merge/migrate/shadow/deploy |
| Last-100 analytics | open | sanitized episode read model, zero raw scan |
| Assisted Checkout | schema applied, feature off | behavior canary and payment visual |
| Consent/reminders/discounts | open/legacy partial | combined CTA, 20h guard, capability, enablement |
| Visual messaging | transport/preview deployed | VisualPlan + real catalog/payment/ТТН actions |

Следующий агент обновляет эти counts после каждого docs reconciliation; не
пересчитывает весь план с нуля и не повышает percentage без done-evidence.

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

- [x] Удалить hourly metadata health cron, countdown и automatic batch.
- [x] Запретить synthetic `generateContent` canary во всех обычных режимах.
- [x] Старую generation-probe команду сделать явной quota-consuming diagnostic,
      которая без специального флага отказывается работать.
- [x] Page load, refresh, polling и charts читают только DB/cache snapshot.
- [x] Manual metadata GET допустим только по явному клику администратора в
      раскрываемой диагностике.
- [x] Metadata-result маркируется как `auth/model capability`, а не quota или
      generation health.

Initial production proof на `7fd83f838`, revalidated на `28707634c`: crontab
metadata owner `0`; authenticated
quotas/routes/attempts API `200`; 4×6 read не изменил Gemini request/attempt
counts (`17/3034` до и после); generation probe требует
`--confirm-quota-spend`.

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

- [x] Видеть active routing/accounting policy versions.
- [x] Включать `pinned` live-model максимум на 60 минут; default — `adaptive`.
- [ ] Смотреть dry-run preview и прогноз расхода по lane до применения policy.
- [ ] Применять новую immutable policy version с audit actor/time/reason.
- [x] Не иметь возможности вручную переписать usage или скрыть provider 429;
      current cockpit read-only, policy mutation UI ещё не реализован.

Responsive/accessibility:

- [x] 360 px — model accordions, RPM/TPM/RPD вертикально, без page-level
      horizontal scroll.
- [x] Текст не меньше 14 px; interactive targets не меньше 44×44.
- [x] Keyboard, visible focus, WCAG AA, reduced motion.
- [x] Один `aria-live=polite` region; polling не зачитывает всю таблицу заново.
- [x] Сохраняется Django template + vanilla JS и TwoComms dark visual language.

---

## 4. Quota/accounting V2

### 4.1 Project identity

- [x] Настроить шесть стабильных `project_identity`, не содержащих секрет.
- [x] Связать quota/cooldown с `(project_identity, model)` в V2 shadow ledger.
- [x] Ротация credential сохраняет quota identity.
- [x] CUSTOM/ENV duplicates дедуплицировать по HMAC fingerprint; digest не
      возвращать клиенту и не логировать публично.
- [x] Неизвестный CUSTOM не считается седьмым quota project.
- [x] Configuration check падает на duplicate/unknown mapping до включения
      enforcement.

Production labels — opaque `gemini-project-1…6`, не реальные Google IDs;
dedicated HMAC configured. `[x]` здесь доказывает identity/schema/shadow, а не
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

- [x] Каждый considered candidate имеет row/event или immutable plan entry в
      accounting shadow graph.
- [x] `not_attempted_reason` покрывает circuit, lease, quota, deadline,
      superseded wave и policy stop.
- [x] Один atomic winner; late success не создаёт второй reply/send.
- [x] Reply/recovery/Meta receipt связаны с request ID.
- [x] Нельзя сохранять key value, prompt или provider body.

Production sample содержит durable graph (`17` requests / `3034` attempts на
момент smoke); read API redacted/provider-free. Real representative
request→attempt→reply p95 gate остаётся section 0.3.

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

- [x] `ZoneInfo("America/Los_Angeles")`, включая PST/PDT transitions.
- [x] RPD относится к Pacific calendar day.
- [x] RPM/TPM — rolling 60 seconds, не fixed window от первой попытки.
- [x] TPM считает input/prompt tokens; output tokens показываются отдельно.
- [x] Estimated input резервируется до dispatch; actual usage reconciles
      idempotently.
- [x] Timeout сохраняет conservative input estimate.
- [x] Settlement относится к original dispatch day даже после midnight.
- [x] Structured 429 хранит metric/quota ID/dimensions/retry delay без raw body.
- [x] Provider 429 сильнее local estimate и ставит `external_usage_suspected`.
- [x] Unknown model/budget/project — system-check error, не unlimited capacity.

Эти `[x]` относятся к deployed observational accounting semantics. Admission
enforcement по ним остаётся off и не считается закрытым.

### 4.4 Admission и DB boundaries

> **Статус:** candidate graph/reservation/settlement работают в shadow, но
> authoritative admission enforcement и полный запрет direct provider calls
> ещё не включены для всех consumers. Поэтому составные пункты ниже остаются
> open до static inventory + canary.

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

- [x] Additive V2 schema deployed; enforcement/consumer behavior flags остаются
      выключены.
- [x] Новые таблицы InnoDB на disposable production-shaped MariaDB и production.
- [x] Исправить engine registry для существующей quota-таблицы.
- [x] Shadow начат с Pacific-day boundary, а не с ложного mid-day 0.
- [ ] Старые attempts backfill только как telemetry, не как точный remaining.
- [ ] Собрать два полных Pacific days shadow data без изменения route.
- [ ] Проверить: каждый `provider_started` имеет одну reservation и settlement.
- [ ] Enforcement включать: background → recovery → live 5% → 25% → 100%.
- [ ] Routing policy canary отделён от accounting enforcement.
- [ ] Rollback — режим/feature flag/revert; telemetry не удалять и migrations не
      откатывать разрушительно.

---

## 5. Durable CRM analysis

> **Production truth 2026-08-31:** legacy analysis chain действительно начинает
> с `gemini-3.6-flash` и дала latest success `15:45:34+03:00`; 328 snapshots
> stored. Materiality/Analysis V2 selector modes остаются off/legacy. Найден
> liveness gap: 22 terminal `FAILED/attempts=5`, 12 с unanalysed watermark;
> quota/timeout/untyped failures после Pacific reset автоматически не reopen.
> Исправление — typed failure/retry/reopen + exact job→request lineage; bulk
> requeue запрещён. Request-graph P0 при этом закрыт в `28707634c`: 10 expired
> graphs terminalized provider-free, а первый post-deploy real pass дал один
> successful 3.6 attempt/winner/snapshot. Implementation checklist — Э8.2 `04`.

- [ ] Типизировать failure kind/quota scope/retry boundary и связать job с
      `GeminiRequest` по revision/materiality digest.
- [ ] Day quota defer до Pacific reset, minute quota `RetryInfo`, timeout/5xx
      bounded retry, config faults terminal.
- [ ] Idempotently reopen только expired historical quota terminal jobs;
      no-new-evidence jobs остаются закрыты.
- [ ] Перевести analysis на V2 model-scoped permits до заявления «все шесть
      проектов»: legacy management path фактически использует API3–API6.
- [x] Один frozen candidate пересекает provider boundary максимум один раз;
      ambiguous timeout rotates дальше. Любой exception terminalize parent graph
      и remaining plan; expired unresolved graphs reconciles idempotently.

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

> **Статус:** schema/migration `0185` deployed, consumer mode off; legacy
> `MEMORY_EVERY=8` summary остаётся. Наличие таблицы не закрывает projector,
> prompt parity или supersede/invalidate semantics.
> Production proof до fix: legacy summary старше current episode попадал в
> 33k prompt; для тестового клиента prompt одновременно содержал old `<records>`,
> `done/100%` и unverified-payment warning. До Typed Memory нужен fail-closed
> age/episode/reset gate; затем stage/episode correction P0 из Э3.2 `04`.
> Оба immediate guards задеплоены в `28707634c`: stale summary suppressed,
> false buyer=false и current stage=`checkout`; это не включает Typed Memory V2.

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
- [ ] Persona/recipient/gift/occasion/repeat facts имеют dated observation,
      subject scope и episode/line. `Я девушка`, `для девушки` и manager/model
      quote не сливаются в один current client-gender fact.
- [ ] Contradicting newer evidence supersede/invalidate old current fact; history
      остаётся в timeline, live prompt получает только fresh compatible state.
- [x] Legacy compatibility: summary старше current episode/reset не загружается;
      fresh same-episode summary остаётся до typed-memory parity.

---

## 6. Future funnel registry и подворонки

Gemini V2 не заменяет funnel registry. Analysis пишет generic proposals;
versioned backend definitions и projector владеют переходами.

> **Статус `[!]` NO-GO:** migration/registry `0186` находится только в отдельной
> ветке и не входит в current main. До merge обязательны десять blockers из
> Э4 `04` и Wave 9 `10`. Customer VisualPlan читает/предлагает typed actions, но
> не становится владельцем state.

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

> **Статус: open.** Legacy funnel/analysis tables дают частичные aggregates, но
> sanitized V2 episode read model и last-100 query без raw transcript scan не
> доказаны.

- [ ] Materialize one current sanitized projection per episode/revision.
- [ ] Last-100 query читает projections/nodes/snapshots/technical aggregates и
      делает zero raw-message reads в обычном режиме.
- [ ] Distinct client/episode cohort, timezone/window/cutoff/exclusions
      зафиксированы и покрыты тестами.
- [ ] Drilldown raw transcript доступен только по конкретной anomaly с audit.

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

Payment visual contract — section 10
[`10_VISUAL_MESSAGING.md`](10_VISUAL_MESSAGING.md): initial card без
`Я оплатил`; `Перевірити оплату` только reconciliation signal; Meta `web_url`
tap не равен `PAYLINK_VIEWED`, который создаётся first-party signed checkout
GET.

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

Visual/copy/postback choreography — section 9
[`10_VISUAL_MESSAGING.md`](10_VISUAL_MESSAGING.md). Этот раздел
владеет business/platform eligibility policy.

- [ ] После verified 200/full payment, только внутри реально открытого Meta
      window, отправить thank-you и **одну** прозрачную кнопку
      `Так, отримувати`; initial payload не содержит decline/cancel button.
- [ ] Один idempotent tap атомарно создаёт два append-only grants с общим
      bundle: `order_updates` и `bonuses`.
- [ ] Business consent хранит client/order/episode, topic, exact localized copy
      digest/version, source visual/click/message, provider timestamp, channel,
      policy и revocation. Current projection per `(client, topic)`.
- [ ] Transactional status не содержит promo без `bonuses` consent.
- [ ] Meta transport capability/token хранится отдельно от business consent.
- [ ] Meta deadline = inbound/postback provider timestamp +24h; internal
      proactive safe deadline = +20h. Между 20h и 24h proactive automation
      blocked; reactive reply policy рассматривается отдельно.
- [ ] Payment success page всегда содержит безопасный `Вернуться в Direct` CTA.
- [ ] Web click сам по себе не открывает messaging window; inbound/postback — да.
- [ ] Вне окна auto-send разрешён только при доказанной Meta capability.
- [ ] `HUMAN_AGENT` автоматическим ботом не используется.
- [ ] Без capability создаётся manager task или ожидание следующего inbound.
- [ ] Opt-out/revocation немедленно прекращает обе темы.

**Неподвижное ограничение:** одна красивая CTA — UX bundling, но не один
неразличимый consent и не «вечное окно». Business grants сохраняются раздельно;
closed-window право появляется только из отдельно доказанной Meta capability.

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

**Historical S1 verification evidence (2026-08-30):**

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

Capacity sample `7fd83f838`: selector `3/0`; observed lswsgi
master+2; one supervisor + one daemon; RSS/PSS/private aggregate на sample
`649792/521380/469400 KiB`; status `running`, queue `0`, recent error events `0`,
read APIs JSON `200`. Это sample, не p95/fPMEM и не завершение soak.

Runtime gate:

Behavior baseline перезапущен с `2026-08-31T18:37:02+03:00`; deadline
`2026-09-02T18:37:02+03:00`; automation должна быть обновлена после final docs
parity. Pre-fix SIGKILL остаётся в
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

- [x] Classification table для `NO_MODEL`, `ORDINARY_LIVE`, `COMPLEX_LIVE`.
- [x] Exact price при exact product не становится complex по слову «цена».
- [x] Ambiguous product image становится complex и создаёт один artifact.
- [x] Story mention: deterministic ack, zero chat Gemini, один assessment.
- [x] Voice: один artifact, без повторного analysis.
- [x] Ad referral: deterministic resolver first, 3.7 только при ambiguity.
- [x] Ordinary/complex chains работают model-major через шесть проектов.
- [x] Fast 429 rotating projects; slow timeout соблюдает SLA и пишет skipped.
- [x] Emergency pin истекает максимум через 60 минут.

Routing contract прошёл integrated regression и deployed. Representative real
traffic p95/request→attempt→receipt остаётся отдельным open gate 0.3.

### 10.2 Accounting/concurrency

- [x] Pacific DST: winter/summer reset, spring/fall transitions.
- [x] Rolling RPM/TPM boundary и request across midnight.
- [x] Последний RPD/RPM/TPM slot под MariaDB concurrency.
- [x] External quota drift и structured `RetryInfo`.
- [x] 401/403/404/408/429/5xx, invalid payload, safety, empty response.
- [x] Timeout ambiguity не возвращает consumed reservation.
- [x] One winner/receipt under hedge and crash.
- [x] Expired reaper ↔ late success на disposable MariaDB/InnoDB сходится в
      `succeeded_late`, correct winner, conservative RPD и zero in-flight.
- [ ] 50-turn burst: bounded threads/connections и один reply на turn.
- [ ] Статический запрет прямого provider call вне gateway.

### 10.3 UI/health

- [x] Load/refresh/polling делают zero provider calls.
- [x] Полная 4×6 zero-usage matrix без заранее созданных DB rows.
- [x] Real traffic меняет только соответствующую project/model пару: первый
      post-deploy pass обновил ровно одну 3.6 pair и создал один winner/snapshot.
- [ ] Cooldown expiry даёт `available_assumed`, не fake success.
- [x] Secrets/project IDs/customer text отсутствуют в API/DOM.
- [ ] Empty/stale/error/external-drift states.
- [x] Playwright/evaluation 360/768/1440 и accessibility contract зелёные для
      deployed cockpit; повторить после будущих UI changes.

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

- [x] Shared CPython 3.14.6 / Django 6.1 runtime использован для команд.
- [x] `manage.py check`, related suites, tracked compile и migration drift
      зелёные; untracked AppleDouble файл не удалялся и не относится к imports.
- [ ] Disposable MariaDB migration/interrupt/retry и InnoDB engine audit зелёные.
      Focused accounting/InnoDB/race proof зелёный; общий fresh graph остаётся
      open из-за независимого `storefront.0097` WebPush HASH assertion
      (`FRESH-MARIADB-WEBPUSH-001` в Э0.1 `04`).
- [x] `git diff --check` зелёный.
- [x] Никаких synthetic messages живым клиентам, Meta test events или generation
      probes.
- [x] Production deploy только через `main` и supported SSH pull.
- [x] Небольшой последовательный endpoint + authenticated Chrome smoke, без
      broad crawl; healthz/bot health=200, app-origin console errors=0.
- [x] Code release `local = GitHub = production = running daemon SHA`; после
      docs-only commit parity повторяется и доказывается отдельно.
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
- Customer-facing cards/buttons/carousels/payment/ТТН и combined opt-in
  реализуются только по [`10_VISUAL_MESSAGING.md`](10_VISUAL_MESSAGING.md).
- Красивый visual preview/receipt доказывает transport, но не закрывает
  commerce/funnel/consent action без signed revision-safe backend path.

## 12. Ссылки

- [Visual Messaging plan](10_VISUAL_MESSAGING.md) — канонический visual UX,
  VisualPlan, card/carousel/payment/ТТН/consent choreography.

- Общий implementation order: `04_IMPLEMENTATION.md`.
- Production incident handoff: `07_PRODUCTION_TECHNICAL_DELAY_SPAM_HANDOFF_2026-08-27.md`.
- Gemini quota semantics: <https://ai.google.dev/gemini-api/docs/rate-limits>.
- Meta Instagram API collection: <https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api>.
