# 09 — Gemini Router V2: ключи, квоты, fallback и API-наблюдаемость

Дата первоначального контракта: 2026-08-30.
Последняя сверка scope: 2026-08-31.

Этот файл — единственный канонический implementation checklist только для
Gemini provider infrastructure:

- классификация live-запроса и выбор model chain;
- шесть независимых quota projects;
- project/model admission, fallback и request graph;
- event-driven health без расходующих квоту проверок;
- provider-free API/UI-наблюдаемость по четырём моделям и шести проектам.

Здесь больше не считаются выполнением Gemini Router:

- CRM Analysis, materiality и Typed Memory — Э3.4, Э3.5, Э3.12, Э5 и Э8.2
  [`04_IMPLEMENTATION.md`](04_IMPLEMENTATION.md);
- funnel registry и подворонки — Э4 `04`;
- last-100/product analytics — Э8.6/Э8.7 `04`;
- cards, checkout, consent, reminders, discounts и ТТН — Э1/Э6 `04` и
  [`10_VISUAL_MESSAGING.md`](10_VISUAL_MESSAGING.md);
- общий daemon/LSAPI/runtime hardening — Э8.1/Э8.4 `04`.

Эти требования не отменены: они перенесены в документы, которые владеют
соответствующим business state. Следующий агент не должен возвращать их сюда и
не должен создавать параллельные memory/funnel/commerce механизмы внутри Gemini
gateway.

Статус `done` означает: код, целевые тесты, deploy и production evidence. В functional
percentage входят только девять outcome-checkbox этого документа. Временные
soak/calibration gates показаны отдельно и не занижают готовность функционала.

---

## 0. Handoff snapshot

### 0.1 Текущая граница

| Область | Подтверждённое состояние | Открытая граница |
|---|---|---|
| Code release local/GitHub/production/runtime | `071a4b5b2f65a91a36443fe98d10a1a322942542`; migration `management.0186` applied, production tracked-clean, daemon healthy/restart_count=0 | финальный docs-only HEAD всегда сверять через `git rev-parse HEAD` |
| Live router | Ordinary начинает с Lite, Complex — с 3.7; calibrated G8 ranking балансирует проекты и skip-ит definite provider/RPD/RPM/calibrated-TPM/permit denial | полный all-consumer G7 enforcement остаётся gated |
| Project identity | шесть credentials сопоставлены шести opaque `project_identity`; secret/fingerprint/provider project ID не попадают в API/DOM | enforcement пока shadow |
| Health | hourly metadata owner удалён; UI/read API не вызывают `generateContent`; manual metadata GET — только явная диагностика capability | external 48-hour soak отдельно |
| Cockpit | `Квоти / Маршрути / Спроби`, 4×6, cooldown/assumed/degraded/external-drift states, redacted provider-free reads | G9 закрыт; повторять acceptance после будущих UI changes |
| Request graph | immutable plan, attempt FSM, one winner, reply/recovery/Meta receipt lineage; expired graph reaper provider-free | authoritative deny ещё не останавливает dispatch |
| Accounting | Pacific RPD, rolling RPM/TPM, permits, structured 429, calibrated 3.6/Lite estimator и conservative legacy/V2 headroom работают | 3.7/3.5 TPM calibration и full G7 enforcement ждут natural evidence |
| Runtime evidence | real 3.6 request создал один winner/snapshot; orphan graphs reconciled без provider replay; preview taps прошли `NO_MODEL` | representative live request→receipt p95 и текущий soak — external gates |

В Markdown запрещено помещать ключи, SSH-пароли, usernames, полный customer
text, provider bodies, HMAC fingerprints или реальные Google project IDs.

### 0.2 Точный functional dashboard

```text
done 8   open 1   blocked 0   total 9
functional completion: 8 / 9 = 88.9%
```

Это заменяет старый raw-счётчик `87/240`: он смешивал Gemini infrastructure с
CRM, funnel, checkout, visual UX, runtime soak и повторяющимися test-checkbox.
Историческая оценка около 65% была ближе к реальной зрелости provider
infrastructure, но теперь используется воспроизводимый счётчик outcomes.

### 0.3 Внешние и временные gates — не functional denominator

| Gate | Статус | Что доказывает |
|---|---|---|
| 48-hour runtime/LVE soak с ranking baseline `2026-08-31T21:40:35+03:00` | идёт до `2026-09-02T21:40:35+03:00` | отсутствие unexplained exits/resource regressions |
| Два полных calibrated Pacific days shadow | ещё не завершены | readiness до G7 enforcement |
| Representative real live request→attempt→reply/Meta receipt и p95 | ждёт естественного traffic evidence | end-to-end latency/lineage без synthetic message |
| Production estimator calibration | 3.6 n=15 и Lite n=2, underestimates=0; 3.7/3.5 pending | TPM deny используется только для подтверждённых моделей |

Ни один gate не разрешает synthetic generation probe, новое customer test
message или широкий production crawl.

### 0.4 Следующий конкретный шаг

`management.0186` задеплоена и закрыла G8/G9: append-only calibrated profiles,
provider-free snapshot, conservative legacy/V2 ranking, typed pair skip и
provider-free 4×6 edge states доказаны на production. Единственный functional
outcome — G7: полный authoritative admission для всех consumers. Его нельзя
маскировать словом «ranking» и нельзя включать до calibrated time gate.

Нельзя параллельно включать CRM Analysis V2, Typed Memory, funnel или VisualPlan:
это отдельные reversible releases по `04`/`10`.

---

## 1. Неподвижные provider-инварианты

1. До provider I/O существует versioned `RoutingDecision` и immutable полный
   candidate plan.
2. Один logical customer turn получает не более одного customer-facing winner.
3. Все provider consumers пересекают одну accounting/admission boundary;
   диагностическая команда является явно quota-consuming и отказана без
   специального флага.
4. Quota/cooldown принадлежит `(project_identity, model)`, а не env alias.
5. Provider evidence сильнее local estimate; UI никогда не обещает точный
   remaining, которого provider API не отдаёт.
6. После `provider_started` reservation не возвращается из-за timeout/cancel:
   provider мог принять запрос.
7. Network I/O не выполняется внутри DB transaction.
8. Late success/loser не создаёт второй Meta send.
9. Page load, polling, charts и health endpoints выполняют zero provider calls.
10. Отсутствие ошибок без свежей generation означает `available_assumed`, а не
    доказанный success.
11. Ключ, project identity, prompt, customer text и raw provider error не
    сохраняются в публичной telemetry.
12. Модель не становится authority для payment/order/stock/price/discount/
    delivery/permission; эти границы принадлежат backend и `04`/`10`.

---

## 2. Закрытые outcomes

### G1. Versioned live classification и deterministic `NO_MODEL`

- [x] Backend создаёт `RoutingDecision`; `NO_MODEL`, `ORDINARY_LIVE` и
      `COMPLEX_LIVE` определяются typed facts/reason codes, а не словом, длиной
      сообщения или legacy model setting.

Canonical decision:

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

`NO_MODEL` используется только когда outcome полностью задан backend truth:
postback, dedupe, opt-out/takeover, verified order/payment/delivery status,
exact resolver answer или safe UGC acknowledgement. Gemini fallback «для
красоты» запрещён; event/send idempotency остаётся обязательной.

Evidence: classification regression, exact-price/not-complex regression,
story acknowledgement без chat Gemini, production preview postbacks `NO_MODEL`.

### G2. Model-major Ordinary/Complex fallback через шесть проектов

- [x] Ordinary и Complex используют immutable model-major chains, все шесть
      projects присутствуют в candidate plan, fast key/project errors вращают
      кандидата, slow timeout ограничен общим deadline и сохраняет skipped
      reasons.

Ordinary:

```text
3.5 Flash Lite × available projects
→ 3.5 Flash × available projects
→ 3.6 Flash × available projects
→ 3.7 Flash emergency-only
→ deterministic fallback / manager route
```

Complex:

```text
3.7 Flash × available projects
→ 3.6 Flash × available projects
→ 3.5 Flash × available projects
→ 3.5 Flash Lite × available projects
→ clarification / manager route
```

Scarce 3.7/3.6/3.5 hedging запрещён. Lite hedge — максимум два реально
dispatched calls и только по explicit SLA policy. Один slow timeout не даёт
права ждать ещё пять полных timeout.

### G3. Один canonical media-intelligence artifact

- [x] Complex image/audio turn создаёт максимум один evidence-bound artifact;
      live reply переиспользует его, duplicate media identity не делает второй
      strong pass, artifact не становится catalog/payment truth.

Artifact содержит content/provider identity, media kind, transcript/description,
bounded candidates, confidence/evidence, model/project/attempt и schema version.
Product image начинает с 3.7; voice создаёт transcript+intent за один pass;
provider-native UGC получает deterministic acknowledgement и отдельный bounded
assessment без второго chat Gemini.

### G4. Event-driven health без расходующих квоту проверок

- [x] Hourly metadata cron/automatic batch и synthetic `generateContent` canary
      удалены; page load/refresh/polling читают только local snapshot; manual
      diagnostics явно отделяют metadata capability от generation/quota health.

Legacy generation probe требует explicit quota-spend confirmation. Manual
metadata GET допустим только по клику администратора и не может маркировать
generation как healthy.

### G5. Opaque 4×6 identity и provider-free cockpit

- [x] UI/API всегда строят четыре модели × шесть opaque projects из config
      manifest с left join usage state; zero traffic не требует 24 заранее
      созданных ledger rows; secrets и provider identities redacted.

Модели:

- Gemini 3.7 Flash;
- Gemini 3.6 Flash;
- Gemini 3.5 Flash;
- Gemini 3.5 Flash Lite.

Cockpit показывает `Квоти`, `Маршрути`, `Спроби`: local-estimate RPM/TPM/RPD,
reserved/in-flight, blocks/reset, lane/task usage, fallback, latency и redacted
request graph. На 360 px модель — accordion; controls ≥44×44, text ≥14 px,
keyboard/focus/WCAG AA и один polite live-region.

Emergency pin ограничен 60 минутами; usage counters и provider 429 нельзя
редактировать вручную.

### G6. Durable request graph и observational quota semantics

- [x] Deployed graph хранит immutable candidate plan, provider-boundary FSM,
      atomic winner, not-attempted reasons и receipt lineage; quota shadow
      реализует Pacific RPD, rolling RPM/TPM, permits и conservative settlement.

Attempt FSM:

```text
planned
→ reserved
→ provider_started
→ succeeded | failed | timeout_ambiguous | succeeded_late
```

Только `cancelled_pre_dispatch` возвращает reservation. Structured 429 хранит
metric/quota identifier/dimensions/retry delay без raw body и сильнее local
remaining. Unknown model/project/profile никогда не трактуется как unlimited.

Expired graph reaper provider-free и idempotent; late success сохраняет
conservative spend и не создаёт второй reply.

---

## 3. Quota outcomes: один open, два закрыты

### G7. Authoritative V2 admission/enforcement

- [ ] Перевести observational shadow в atomic authoritative admission для всех
      provider consumers и доказать, что deny действительно предотвращает
      provider dispatch без изменения request lineage.

Обязательный контракт:

- один gateway для live/recovery/background/manual override; intentional manual
  diagnostic остаётся отдельной явно quota-consuming boundary;
- static inventory/test запрещает новый прямой `generateContent` вне gateway и
  явной diagnostic allowlist;
- reservation создаётся непосредственно перед dispatch;
- короткий DB lock проверяет active quota profile, Pacific RPD, rolling RPM,
  input TPM, metric-specific provider block и model-scoped permit;
- network I/O происходит после transaction;
- settlement idempotent по attempt ID и original dispatch day;
- timeout сохраняет conservative input estimate;
- background при accounting outage defer; live получает максимум один emergency
  Lite call, затем deterministic/manager fallback; scarce models fail closed;
- shadow profile/token estimator сначала калибруется на реальном traffic; media
  или неизвестный budget не получают ложный `ALLOW`;
- rollout: background → recovery → live 5% → 25% → 100%; rollback только mode/
  flag/revert, telemetry не удаляется.

Definition of Done: deny-path regression пересчитывает provider-call count=0;
MariaDB concurrency сохраняет один permit/reservation/settlement; два полных
Pacific days не показывают unexplained drift; production canary не создаёт
customer-visible regression.

### G8. Quota-aware ranking и fallback

- [x] Ранжировать project/model candidates по authoritative quota snapshot:
      provider block, remaining RPD/RPM/TPM, in-flight permit, latency и recent
      real outcomes; не выжигать первый проект до нуля и не менять frozen plan
      после его сохранения.

Текущий scoreboard уже учитывает recent success, key fault и latency, но не
authoritative V2 remaining/permit. Требуется один pre-dispatch snapshot:

```text
eligible/block reason
remaining local estimate
rolling rpm/tpm pressure
in_flight / permit_limit
latency evidence
confidence/freshness
```

Fast 429/auth/project-specific 403/404 вращает project внутри текущей model tier.
Model-wide unavailable или исчерпанный deadline переводит на следующий model
tier. Каждый исключённый candidate получает bounded `not_attempted_reason`.
Unknown/stale accounting не делает scarce candidate доступным.

Definition of Done: deterministic tests доказывают model-major ordering,
fairness между шестью identities, correct external-drift priority, bounded slow
timeouts и неизменность persisted plan.

Production proof `071a4b5b2`: `management.0186` добавила восемь append-only
profiles; 3.6/Lite estimator подтверждён 17 real samples без underestimation,
3.7/3.5 остаются TPM-uncalibrated. Один snapshot делает не более трёх V2 reads,
полный plan — не более шести SELECT; ranking mode=`enforce`, accounting=`shadow`.
Production Lite matrix показала шесть eligible projects, calibrated
RPD/RPM/input-TPM/in-flight; plan read создал zero Gemini graphs/attempts.
Model-major order и conservative `min(legacy,V2)` доказаны regression suite.

### G9. Полные API/UI edge states

- [x] Довести provider-free quotas/routes/attempts API и cockpit до точной
      семантики cooldown expiry, empty/stale/accounting-error и external drift;
      production read не вызывает provider и не маскирует 429.

Закрытый state set:

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

Правила:

- success имеет versioned freshness window;
- cooldown expiry без новой generation становится `available_assumed`;
- structured provider block показывает metric и точный известный reset, но не
  выдумывает provider remaining;
- local/provider mismatch маркируется `external_usage_suspected`;
- zero rows всё равно дают полную 4×6 matrix;
- error/stale snapshot показывает last-good data и явную freshness, не зелёный
  status;
- API/DOM не содержат key alias, fingerprint, project ID, prompt/customer text;
- load/refresh/polling и charts имеют provider-call delta=0.

Definition of Done: edge-state table tests, authenticated 360/768/1440 smoke,
real traffic меняет только свою project/model pair, production API/read counters
не изменяют request/attempt ledger.

Production proof после `0186`: quotas/routes/attempts вернули JSON/HTTP 200;
4×6 matrix содержит `available_assumed`/`provider_degraded`, а три API reads дали
provider graph delta=0 и attempt delta=0. Cooldown expiry, accounting unknown,
active/expired metric blocks и external drift покрыты deployed edge-state tests.

---

## 4. Identity, concurrency и quota profile contract

### 4.1 Identity

- Шесть credentials — шесть independent quota projects по решению владельца.
- State key — `(project_identity, model)`; credential rotation сохраняет
  project quota.
- Duplicate credentials дедуплицируются keyed HMAC fingerprint без сохранения
  секрета.
- Unknown CUSTOM не создаёт седьмой project и fail-closed до provider I/O при
  enforcement.
- Public labels — только `Проект 1 … Проект 6`.

### 4.2 Quota profiles

Versioned profile хранит model, RPM, input TPM, RPD, permit limit, source,
observed/effective dates и estimator version. Semantics:

- `ZoneInfo("America/Los_Angeles")`, включая DST;
- RPD — Pacific calendar day;
- RPM/input TPM — rolling 60 seconds;
- prompt estimate резервируется до dispatch, actual usage reconciles после;
- settlement относится к original dispatch day даже после midnight;
- provider 429 создаёт metric-specific block и external drift signal;
- profile transition не заменяет историческую telemetry.

### 4.3 Permits

- один concurrent permit для 3.7/3.6/3.5 на project;
- до двух Lite calls на project;
- background 3.6 не блокирует live Lite;
- lease/reservation живут до real completion;
- slow timeout ограничивает дальнейшие dispatch общим deadline;
- full candidate plan сохраняется даже при ранней остановке.

---

## 5. Migration и integration boundary

Текущий Gemini calibration/ranking slice занимает management migration
**`0186_calibrated_gemini_quota_profiles`**. Это additive provider-infrastructure
migration, не authoritative enforcement и не funnel registry.

Существующая отдельная funnel branch, в которой migration ранее называлась
`0186`, не может быть cherry-picked как есть. Агент Э4 обязан:

1. rebase на актуальный `main` после quota slice;
2. получить следующий свободный migration number;
3. обновить dependency на deployed Gemini `0186`;
4. повторить migration graph/engine/MariaDB review;
5. не смешивать funnel schema с Gemini enforcement commit.

Integration order:

1. [done] `0186` profile calibration, G8 ranking и G9 API production proof;
2. отдельный G7 schema/code release;
3. calibrated shadow consistency proof;
4. authoritative background admission;
5. recovery canary;
6. live 5% → 25% → 100%.

Не делать historical attempts backfill источником exact remaining. Старые rows
допустимы только как telemetry и не нужны для закрытия functional outcomes.

---

## 6. Acceptance evidence, которое сохраняется прозой

Уже доказано foundation:

- routing classification, exact-price Ordinary и ambiguous-image Complex;
- story acknowledgement: zero chat Gemini, one bounded assessment;
- voice/media: one canonical artifact;
- deterministic ad resolver before strong-model ambiguity path;
- model-major six-project chains, fast 429 rotation и bounded slow timeout;
- Pacific DST/cross-midnight, rolling windows, structured RetryInfo;
- timeout ambiguity, one winner/receipt, expired reaper↔late success;
- full provider-free 4×6 matrix и redaction;
- UI accessibility/responsive contract;
- deploy через `main`, supported SSH pull, narrow smoke without broad crawl.

Перед закрытием оставшегося G7 обязательны:

- shared CPython 3.14.6 / Django 6.1;
- `manage.py check`, target suites, migration drift, `git diff --check`;
- disposable MariaDB/InnoDB migration/ranking proof для `0186` profiles;
- production migration/check/health/daemon parity;
- provider-call counters до/после UI reads;
- no synthetic customer messages/generation probes;
- продолжение external 48-hour soak независимо от functional percentage.

---

## 7. Историческая foundation — не новые задачи

Production wave 2026-08-30/31 установила:

- Router V2, event-driven health, opaque 4×6 cockpit;
- additive accounting schema/shadow и explicit six-project mapping;
- single-boundary background rotation и provider-free expired-graph reaper;
- LSAPI selector correction `10→3`, `LSAPI_EXTRA_CHILDREN=0` и bounded process
  topology;
- removal automatic metadata/legacy periodic owners;
- collation/HTML-as-JSON/runtime recovery fixes;
- receipt-backed Quick Reply/Button/Generic Template preview transport.

Эти факты остаются audit evidence, но не создают повторные checkboxes. Runtime,
CRM Analysis, Memory, funnel и VisualPlan maturity считаются только в `04`/`10`.

---

## 8. Handoff следующему агенту

Не перестраивать уже задеплоенные RouterDecision, 4×6 identity, request graph,
event-driven health, ranking или cockpit. Начинать с текущих gateway/accounting
services и единственного G7 outcome.

Если обнаружено расхождение:

1. проверить current local/GitHub/server/running SHA;
2. снять read-only request/attempt/quota evidence;
3. отличить provider drift от local accounting bug;
4. исправлять минимальный owning layer;
5. не отправлять live customer test message и не запускать generation probe;
6. обновить dashboard только после code+tests+deploy+production proof.

## 9. Ссылки

- [Общий implementation plan](04_IMPLEMENTATION.md)
- [Visual Messaging contract](10_VISUAL_MESSAGING.md)
- [Production incident handoff](07_PRODUCTION_TECHNICAL_DELAY_SPAM_HANDOFF_2026-08-27.md)
- [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Meta Instagram API collection](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api)
