# 00_PROGRESS — журнал прогресса аудита Instagram-бота

> **Единственная точка входа для продолжения работ. Читать первым.**
> Текущие per-ID статусы находятся в `07_IMPLEMENTATION_PLAN.md`, полный
> незакрытый inventory — в `13_UNCLOSED_FINDINGS_RAW.md`, а активный порядок
> выполнения — в `14_IMPLEMENT2.md`. Более поздние по тексту разделы сохранены
> как хронологический журнал и могут описывать состояние конкретной волны.

## Быстрая сводка

| Поле | Значение |
|---|---|
| Текущая фаза | **Implement2 W2.4 Gemini API Checker released and production-verified; `IMP-044` remains PARTIAL, while `IMP-106` core is already in main/production and its consented Graph capability, incentive calibration and privacy-policy gates remain open** |
| Дата старта / обновления | 2026-08-14 (W2.1 lifecycle release) |
| Исходный baseline аудита | `2f75f9d9` — исторический, больше не использовать для новых веток |
| База внедрения | Current runtime/code checkpoint — W2.1 commits `51db3058`/`8d8c5d05` в `origin/main` и production; migrations `management.0152`/`0153`/`0154`/`0156` применены. |
| **Статус 105 IMP-задач** | **81 закрыта, 14 открыты, 10 частично закрыты (`IMP-028`, `IMP-043`, `IMP-081`, `IMP-082`, `IMP-083`, `IMP-084`, `IMP-085`, `IMP-086`, `IMP-087`, `IMP-088`)** |
| Прод-сервер | `qlknpodo@195.191.25.63`, `/home/qlknpodo/TWC/TwoComms_Site/twocomms` |
| Прод-БД | MariaDB/MySQL `qlknpodo_MySQL_DB`; главный источник реальных переписок/товаров/сделок/оплат. Discovery — read-only; concurrency/destructive tests — только disposable MariaDB |
| Локальная SQLite | **не источник business/data истины и не MariaDB acceptance**; только быстрый unit/regression слой, не проверяет locks, concurrent constraints, triggers и `varchar(max_length)`, см. F-TEST-003 |
| Реестр находок | **187 уникальных `F-*` идентификатора: 143 закрыты, 32 OPEN, 1 BLOCKED, 11 PARTIAL**; W2.1 lifecycle truth закрыт, `F-AI-018` и release-gates `F-DEPLOY-001…004` остаются открыты |
| Улучшения / решения | **51 `IMPR-*` / 11 `DR-*`; 17 улучшений закрыто, 34 незавершено** |
| Задач чек-листа закрыто | **120 / 120** (домены A–L) |
| Задач в плане внедрения | **105** в W0–W12, включая W4B/W4C/W4D и IMP-062…105 |

## Документы

| Файл | Состояние |
|---|---|
| `00_PROGRESS.md` | каноническая точка входа, общий статус и реестр восстановленных источников |
| `03_FINDINGS_REGISTER.md` | 187 уникальных `F-*` и post-implementation evidence, включая production SQL/API |
| `04_DECISION_LOG.md` | 11 решений (DR-001…DR-011) с обоснованием отклонённых вариантов |
| `05_IMPROVEMENTS_REGISTER.md` | 51 улучшение + канонический crosswalk каждого ID к DONE/PARTIAL/OPEN и `IMP-*` |
| `06_FUNNEL_CLOSING_DESIGN.md` | дизайн добивки: 9 каскадов с текстами, возражения, статистика, контекст-бюджет |
| `07_IMPLEMENTATION_PLAN.md` | историческая каноническая status matrix 105 IMP-задач, 187 F-* и 51 IMPR-*; активный порядок задаёт `14` |
| `13_UNCLOSED_FINDINGS_RAW.md` | полный handoff inventory: unchecked IDs, test boundaries, blockers, rules, gaps, WIP и resolved DOC conflicts |
| `14_IMPLEMENT2.md` | активный topological execution plan; после каждого release синхронизировать с `00/07/13` и evidence logs |
| `01_SYSTEM_MAP.md` | оформлен; карта production-контуров и границ ответственности |
| `02_AUDIT_CHECKLIST.md` | оформлен; 120/120 доменных проверок с evidence |
| `06_TEST_MATRIX.md` | оформлен; 51 acceptance-сценарий и текущие gates |
| `08`–`12` | completion, deploy, blockers, validation и source reconciliation; более старые цифры читаются как historical evidence |

> ⚠️ **Особенность репозитория:** `.gitignore:227` содержит `*_PLAN.md`, поэтому
> `07_IMPLEMENTATION_PLAN.md` пришлось добавить через `git add -f`. Он уже
> в трекинге, дальнейшие правки коммитятся обычным `git add`. Но если файл
> когда-нибудь удалят из индекса — его снова нужно будет добавлять с `-f`.

## Активный остаток

| Статус | Задачи |
|---|---|
| Открыто, W4B | — |
| Открыто, W5 | `IMP-028` (PARTIAL: authority/budget/variant-price slice задеплоен, sales playbooks и FAQ остаются), `IMP-095` (production merchandising белого варианта товара 110) |
| Открыто, W8 | `IMP-044`–`IMP-046`, `IMP-061`, `IMP-094`, `IMP-096` (provenance ролей импорта), `IMP-100` (дедупликация UI-лога), `IMP-101` (убрать небезопасные config defaults) |
| Частично, W8 | `IMP-043` |
| Частично, W9 | `IMP-081` опубликована как semantic/inventory foundation; `IMP-082`/`IMP-083` имеют production graph/ranker и точный prompt price/size parity на `0ad694bc`; `IMP-084` имеет exact warehouse/catalog availability и proposal reservation wiring; `IMP-085` имеет bounded parser/runtime; `IMP-086` дополнительно защищает paid commitments и warehouse write-off в `a7857ada`; `IMP-087` создаёт durable selection/transition/decision state и reducer запускается до classifier/Gemini на production `bc4ec2d5`. `7ad632de`/`ade00668` также задеплоили narrow `IMP-087.A` receipt-backed informational delivery и `0154` synthetic inbound dedupe; exchange/return остаются post-sale flow. Открыты candidate anchoring, burst coalescing, payable/price delivery, manager review UI и полный topology |
| Частично, W9 | `IMP-088` (digest/proposal workspace foundation есть; freshness, review UI, audit/backfill, MariaDB/deploy proof остаются) |
| Открыто, W10/W11 | `IMP-090`–`IMP-093`, `IMP-098`; `IMP-090`, `IMP-096` и baseline `IMP-093` не зависят от завершения полного commerce chain. F-PAY-010 внутри IMP-098 закрыта на `7440bb98`, F-CORE-003 — на `18ddc636`, остальные orphan-находки остаются открыты |
| Открыто, W12 | — |

## Implement2 W1.7 historical attachment hardening (2026-08-12)

`214ae4b9` уже был reachable from current `origin/main` through merge
`b9bab236`; follow-up W1.7 commit adds the missing historical-provenance guard
in payment vision and a live download-failure telemetry regression. The focused
gate is `162/162`; production migration `0153` is applied on MariaDB.

Production read-only reconciliation: 2,522 Instagram messages (337 webhook),
29 structured attachment rows, every persisted attachment is
`historical_import`/`metadata_only`, no `live_webhook`/`owned` media and no
`media_capture_eligible` rows. No post-migration live analysis exists, so the
media telemetry contract is verified locally and the absence of live telemetry
is retained as a limitation. `F-AI-018` remains under `IMP-044`.

## Implement2 W1.6 structured control closure (2026-08-10)

`130cd920` находится в `origin/main` и production; migration
`management.0152_harden_ig_stage_prompt` применена. Typed immutable JSON
response contract и fail-closed legacy adapter блокируют unknown, malformed,
duplicate, conflicting, whitespace/zero-width и truncated controls до любых
side effects. Customer text не может объявить application-owned payment,
stock, consent, order, manager или hard-stage truth без evidence.

Fresh local gate: 240/240, Django check, migration drift, compileall и diff
check. Production read-only proof: exact SHA `130cd920`, `0152=[X]`, stored
custom prompt остаётся операторским, но assembled runtime содержит JSON
contract и hard-stage guard; legacy bracket protocol отсутствует. Parser
probes вернули `valid=false` и чистый reply для четырёх obfuscated/truncated
tokens; common authority wording распознано, negated status не превращён в
ложный claim. `twocomms.shop/healthz/` и management `/bot/health/` вернули
`200/ok`, bot `running`, dangerous backlog и pending queues `0`. Ни customer,
provider, payment, order, notification или analysis event не создавался.

## Implement2 W2.2 T41 MariaDB checkout-concurrency gate (2026-08-14)

The disposable MariaDB workflow now reaches and passes the checkout proposal
lock/race assertion on the pinned MariaDB 11.4.12 service. CI run
`31761170448` at sanitized SHA `8f4459f689ebe20b1b4cdda51b1e88c11cddc11b`
passed the runner/workflow and settings contract steps, the lifecycle suite,
and the `checkout-concurrency` suite. The fresh local runner/workflow packet is
`29/29`. Exact artifact evidence names disposable schemas
`test_twocomms_ig_0d322be43f2f` and `test_twocomms_ig_f6383867aa07`; both
reported `cleanup=verified`. The preceding errno `1644` was traced to Django
`TransactionTestCase` teardown issuing `DELETE` against an append-only event
trigger. The scoped test teardown now uses `TRUNCATE` via
`reset_sequences=True` without weakening production triggers.

The post-teardown sanitizer follow-up was independently RED/green tested for
free-form test lines, child/cleanup exception names, and the CLI fallback.
It retains only fixed failure categories plus a numeric MariaDB errno. Artifact
`mariadb-gate-evidence` (`9204756023`) has digest
`sha256:12ce607d8a867317d1f4b502e0a657d465333fffb8108d9ade877129ae0570ce`.

The release boundary was then verified on current `main` at
`9ed640b06c7324f610330d2d9b40fd3cd0e8c2b0`. Manual workflow run
`31762702125` checked out that exact SHA and passed both disposable gates;
artifact `9205282515` (digest
`sha256:2598b0fc7e9acbfcc7a1d641c48a0f16d048cdf546ba151ba7b916cd0c2bab06`)
reported fresh generated schemas and `cleanup=verified` for lifecycle and
checkout-concurrency. The prescribed SSH `git pull` was executed and returned
`Already up to date`; read-only production evidence showed
`HEAD == origin/main == 9ed640b06c7324f610330d2d9b40fd3cd0e8c2b0`, clean
`manage.py check`, and bot `state=running`, `running=True`,
`daemon_online=True`, `provider_transport=instagram_login`, pending
notification/analysis queues at zero, failed/unknown/dead-letter notification
rows at zero, and no recorded error.
Production also emitted a fail-safe warning that `CACHE/manifest.json` is older
than static sources, so offline compression is disabled until an approved
static refresh is run. The required git-pull-only deployment rule prevented
running that refresh; this remains additional `F-DEPLOY-003` evidence and is
not claimed as fixed.

This is a narrow T41 evidence boundary only. The full management MariaDB
parity matrix, `F-TEST-002`, `G-INFRA`, and immutable release/rollback gates
under `IMP-094` remain open.

## Implement2 W2.1 authoritative order lifecycle and delivery truth (2026-08-14)

The lifecycle/delivery release is now in production at exact SHA
`8d8c5d05c647c2cfcc9fb4f70d7ee206f8f0359e`. The prescribed SSH `git pull` was
followed by the targeted application of
`management.0156_ig_order_event_delivery_receipts`. MariaDB `11.4.12` proves
`provider_message_id=varchar(255)` and
`delivery_provider_message_ids=LONGTEXT` with the exact `JSON_VALID`
constraint; the management app has no migration drift.

Post-deploy runtime proof: bot `running=True`, `daemon_online=True`,
`provider_transport=instagram_login`, `last_error=''`, dangerous backlog `0`,
all pending/unknown/failed/dead-letter queues `0`; storefront
`https://twocomms.shop/healthz/` and management
`https://management.twocomms.shop/bot/health/` both returned HTTP `200`.
The no-send baseline is unchanged: canonical lifecycle
messages/send markers/provider receipts `0`, legacy order-customer events `5`,
and one historical delivered fact. No customer, provider, payment, order or
synthetic event was created. The full unscoped production migration check still
reports pre-existing storefront SEO drift; it is recorded as an `IMP-094`
follow-up and was not generated or applied during this release. `IMP-106` core
is implemented in current main/production. The Meta capability contract,
separate coupon calibration and privacy-policy decisions remain open; without a
consented target and matched app/token, state stays `unknown` and the follow
CTA is suppressed.

## Implement2 W2.4 Gemini API Checker (2026-08-18)

The admin-only `API` tab, six-key live capsules, independent 24-hour
`gemini-3.7-flash`/`gemini-3.6-flash` rails, passive refresh/countdown and
explicit manual probe are released through `7372f0b6b`, with the stable
countdown follow-up in `8bfb6c5ea`/`7fde498fb` and the API proof reconciliation
in `7b289ab05`; production-proof documentation is in `c6ee5697b`. The hourly
metadata checker is token-free,
3.7-first with conditional 3.6 fallback, bounded by one shared deadline and a
single managed cron owner.

Fresh focused evidence: checker/API/metadata tests `53/53`, cron installer
`18/18`, normal-settings `manage.py check`, management migration drift,
compileall, shell syntax and `git diff --check` all passed. The current
canonical local/remote/production checkpoint is `debcef315`; `7b289ab05` is an
ancestor containing the API proof update. A read-only
MariaDB snapshot shows six key rows with two model rows each and metadata
observations present, while `GeminiRequestAttempt` and `GeminiKeyState` counts
remain unchanged across passive snapshot reads. No provider generation,
customer message or synthetic production fixture was created.

This slice improves operator visibility only and does not close the broader
`IMP-044` slow-drip cancellation, typed worker telemetry, jitter or MariaDB
competition/reclaim gates.

## Implement2 W2.4 API Checker alignment follow-up (2026-08-19)

The API Checker alignment follow-up is implemented in the local `main`
worktree; production deployment and the approved SSH pull remain pending for
this slice. No docs-only push/pull or new production SHA is claimed here. The
hourly metadata checker now starts all six aliases concurrently, keeps the
3.7-first/conditional-3.6 order inside each alias, rejects late evidence at
the shared logical deadline, joins workers before releasing the hourly owner,
and writes the completed ledger batch in one coordinator transaction. A rare
executor submission failure is also joined safely. The dashboard model rows
use a fixed desktop evidence track and preserve local rail scrolling at narrow
widths.

Historical local evidence for the preceding UI/runtime release was `121/121`
focused Gemini/API tests plus `18/18` cron-installer tests, with browser QA at
1920/1280/640/375 px rendering six rows and 12 rails without document
overflow. The current local focused gate is `28/28` after the UI copy
alignment; no current production check, exact SHA, natural hourly batch, provider
probe, customer message or fixture is claimed for this follow-up. A successful
token-free 3.7 metadata GET intentionally records the corresponding 3.6 row as
`not_needed` rather than issuing a second provider request.

`IMP-044` remains PARTIAL: hard wall-clock cancellation for slow-drip reads,
typed worker telemetry, bounded jitter and disposable MariaDB competition/
reclaim proof are still open.

## W1.4 reviewer/operator PII technical boundary (2026-08-08)

Source commit `71498170` находится в локальном `main`, `origin/main` и на
production. Reviewer status теперь fail-closed и содержит только
`state/running/daemon_online/pending`; stats отвечают `403` до business queries,
clients/log пусты, stats DOM не рендерится. Admin status/stats сохранили `200`.
Telegram/operator alerts принимают только типизированные локальные факты и CRM
links; payment-review receipt evidence остаётся в restricted CRM и не попадает в
notification `media`/`sendPhoto`, а IG checkout больше не вызывает legacy
payment-attempt notifier с customer/order/provider PII.

Локальный gate: `144/144`, Django check, migration drift, compile и diff check;
два final-reviewer verdict — без блокеров. Production: MariaDB `11.4.12`, оба
health endpoint `200/ok`, bot `running`, `dangerous_backlog=0`,
`notification_unresolved=0`. Mocked-transport production-DB probe не нашёл в
payload имя, телефон, email, IGSID, provider invoice, receipt URL или `media`,
вызвал `sendMessage` один раз и `sendPhoto` ноль раз; cleanup оставил ноль
synthetic client/notification/review/auth rows. Это закрывает только первый
checkbox W1.4; retention/access policy и итоговый `G-PII` acceptance остаются
открытыми.

## Synchronized production verification before Implement2 docs release (2026-08-07)

`main`, `origin/main` и production находятся на
`19f5ef70f20e1b3d5da5975786359fe8c7e06df4`. На production Git-root —
`/home/qlknpodo/TWC/TwoComms_Site`, а Django application directory — его
`twocomms/` child; поэтому `deploy.sh` корректно существует в Git-root, а не
в application directory. Blob `deploy.sh` на сервере равен Git blob
`37c26433...`, executable mode сохранён, а `git status --porcelain
--untracked-files=no` пуст: tracked production tree синхронизирован с main.

Read-only MariaDB check увидел 18 `IgConversationAnalysisJob` со статусом
`FAILED`: 17 historical `trigger=reconcile`, `attempts=5`, 2026-07-30…2026-08-03
и `last_error` класса `CallAIAnalysisError` с Gemini (у трёх строк literal
`429`), плюс job `292`, client `310`, `trigger=manager_message`, attempts=5,
`last_error=stale_lease_retry_exhausted`. Pending rows отсутствуют. Historical
reconcile rows остаются bounded terminal budget; новый manager-message случай
зарегистрирован как `F-AI-018` и требует typed provider/process/lease telemetry.
Failed analysis не является customer-delivery replay candidate и не имеет права
менять operational episode/payment/order truth.

Первый docs-only Implement2 release `f327ac36` fast-forwarded на production.
`deploy.sh` завершил migrate/collectstatic/compress/restart, `manage.py check`
чистый, migration `0146` applied, daemon `running/alive`, очереди reply/
notification/analysis = 0. Dependency step снова не собрал wheel `cffi`, но
продолжил как non-fatal с активным venv. Runtime здоров, однако этот повторяемый
dependency-drift risk остаётся открытым evidence `F-TEST-002` / `IMP-094`.

Два незавершённых code-WIP также сохранены локально и не считаются shipment:
`ig-commerce-durable-state` был selectively интегрирован в `7ad632de`; narrow
`IMP-087.A` теперь задеплоен, а
`codex-management-bot-statistics-visuals` содержит volatile tracked diff в
`bot_views.py`, `ig_funnel_analytics.py`, `bot.html` и тестах плюс новые plan/test
files для `IMP-093`; снять свежий `git diff --stat` перед recovery. Оба требуют
current-main review/rebase; второй нельзя описывать как plan-only. Dirty `codex-management-bot-live-visuals` и historical
`codex/instagram-assisted-checkout-pre-split` также внесены в source matrix и не
подлежат wholesale cherry-pick.

## Current checkpoint: durable commerce state activation (2026-08-05)

`bc4ec2d5` находится в `main`, `origin/main` и production. Вместе с
`33d63d40` он закрывает опасную дыру между parser и реальным worker path:

- `IgCommerceSelectionSession`, append-only transition и durable decision/outbox
  применены migration `management.0146`; trusted URL и текущая коррекция
  редуцируются до classifier, media pin и Gemini, а затем session снова
  проецируется в legacy `current_*` только как compatibility view.
- `rejected_product_ids` больше не остаются prompt-only фактом: отказ от
  активного товара сохраняется с причиной `customer_rejected_product`, очищает
  product/configuration/price/allocation поля и сохраняет только явно названные
  параметры следующего выбора. Exact URL или коррекция не дают shared-media
  matcher вернуть старый товар.
- `98bb160e` materializes `repeat_intent` только для подтверждённого покупателя.
  При этом новый `IgCommercialEpisode` получает новую пустую
  `IgCommerceSelectionSession`, а предыдущая сессия закрывается: старые товар,
  configuration, price, allocation и candidate anchor не попадают в следующий
  заказ. Exchange/return по-прежнему исключаются из repeat parser и проходят
  существующий post-sale case flow.
- RED/Green: новый worker regression и rejection regression; на unified HEAD
  прошли 94 W9/parser/agentic теста и 143 bot-UI теста, `check`, migration
  drift, compile и diff clean.
- Production: migration `0146` applied; MariaDB содержит четыре trigger guards
  (`ig_com_tr_no_upd`, `ig_com_tr_no_del`, `ig_com_dec_identity_upd`,
  `ig_com_dec_no_del`); daemon `running=True`, `alive=True`,
  `instagram_login`, свежий heartbeat, `last_error=''`, pending user rows = 0.
  Проверка не создавала commerce session и не отправляла сообщения клиентам.

`IMP-087` остаётся `[ ] PARTIAL`: candidate anchoring, burst reduction,
safe delivery reconciliation, payable replies и operational manager-review
consumer ещё не подключены. `IMP-088` теперь `[ ] PARTIAL`: digest и proposal
workspace foundation уже есть; payable lifecycle, freshness/audit, review UI и
disposable MariaDB race/constraint suite требуют отдельной реализации и evidence.

## Previous checkpoint: lease/reclaim, late-payment inventory and episode-scoped presentation (2026-08-05)

`fbe33a68` — актуальный синхронизированный production checkpoint. Он включает
три независимых исправления, каждое с отдельными regression tests:

- `18ddc636` закрывает F-CORE-003: lease автоматизации всегда строго длиннее
  reclaim threshold, небезопасная env-конфигурация нормализуется к безопасному
  отношению, а граница reclaim остаётся строгой.
- `b23dfeed` дополняет закрытую F-CAT-011: время подтверждённой оплаты берётся
  из provider observation, поэтому callback после TTL не выдаёт повторно уже
  перераспределенную последнюю единицу. Такой случай идёт в единственный
  idempotent `OVERBOOKED_REVIEW`/manager task; своевременная оплата сохраняет
  reservation только когда stock не был перераспределён.
- `fbe33a68` закрывает F-STATE-011 / IMP-105: визуальные `paid`/`shipped` и
  `?view=paid` читают только текущий commercial episode. Lifetime purchase и
  хронология остаются видны как история покупателя, но старые payment/shipment
  больше не окрашивают новый DRAFT/repeat episode.

Предыдущий `dd93f9f3` — предок этого checkpoint, а не альтернативная база.
Новый F-STATE-011 не закрывает W9: durable reducer, candidate anchoring,
readiness/alternatives consumer, manager-review UI и disposable MariaDB proof
по-прежнему обязательны.

## Previous checkpoint: F-CAT-011 paid warehouse commitment guard (2026-08-05)

`a7857ada` устраняет окно повторной продажи оплаченной последней единицы:
`ACTIVE` защищает остаток только до `expires_at`, а `PAID_COMMITTED` защищает его
до фактического fulfillment независимо от исходного 25-минутного TTL. Тот же
`protected_stock_quantity()` теперь используется при создании proposal и при
любом отрицательном `adjust_stock_item()`.

- Списание с точным `order` может потребить только собственный
  `PAID_COMMITTED`; active и commitments других заказов остаются защищены.
- RED: 5 новых сценариев дали 3 ожидаемых failure; GREEN: focused `92/92`,
  полный `management warehouse` `2897`, skipped 3, `OK`.
- `dd93f9f3` отдельно сделал старый reduced-motion assertion устойчивым к
  добавлению соседних live-inbox selectors; inbox/UI gate `188/188`.
- Production fast-forward и deploy завершены на `dd93f9f3`; daemon
  `running=True`, `alive=True`, `instagram_login`, `last_error=''`, рабочие
  reply/notification queues пусты.
- `IMP-086` остаётся PARTIAL: ещё нужны disposable MariaDB concurrency proof и
  полный manager-review UI. `IMP-094` остаётся OPEN из-за отдельного MariaDB gate.

## Previous checkpoint: F-PAY-010 human prepayment authority (2026-08-05)

`7440bb98` запрещает модели и клиенту создавать сумму предоплаты из собственного
текста. Денежный факт устанавливает только persisted сообщение
`manager`/`human_manager`/`operator`/`admin`, после которого клиент явно
подтверждает предложение. Повторённая клиентом сумма обязана совпасть; counteroffer,
receipt-текст и сообщение с несколькими различными суммами fail closed до
`invalid_payment_amount`, без создания deal/invoice/proposal.

- RED подтверждён на четырёх исходно уязвимых сценариях; после исправления
  41/41 focused payment/paylink/thermo-price тестов GREEN.
- Production fast-forward, migrate, collectstatic, compress, Passenger restart
  и `run_instagram_bot --ensure` завершены. Server SHA = `7440bb98`, daemon
  `running=True`, `alive=True`, transport `instagram_login`, `last_error=''`.
- MariaDB rollback-fixture доказал customer/model/multi-amount = `ambiguous`,
  human 350 грн = `accepted` с exact offer+acceptance IDs; после rollback
  синтетических клиентов не осталось.
- `IMP-098` остаётся открытой для F-CORE-003…006, F-SCORE-010 и остатков
  F-SEC-004/009; закрыта только её самостоятельная подзадача F-PAY-010.

## Previous checkpoint: IMP-103/104 and sender observability (2026-08-05)

The previous historical paragraphs below mention `414e639e` and an open
`IMP-103`; those statements describe the earlier checkpoint only. At that
checkpoint the runtime code baseline was `1849441d`; the current synchronized
baseline is recorded in the quick summary and current checkpoint above.

- `IMP-103` is closed by `4dfff3a2` + `35d3bd93` and migration
  `management.0143_igfollowuptask_event_continuation`. Follow-up continuation
  is materialized from immutable event key/payload/time, uses absolute policy
  offsets, rechecks invoice/restock truth before send, and exposes audited
  continuation APIs. Focused event/FSM/checkout/restock coverage is 255 tests.
- `IMP-104` is closed by `1f5dcb70`, `7fdbe613` and `1f8cead2`. Configuration
  price is authoritative from selection through proposal, deal and hosted
  checkout; generic/no-variant options, unavailable/zero-choice axes and
  ambiguous multi-price speech fail closed. Customer-facing checkout renders
  selected labels, unit prices and line totals. Focused authoritative-price
  coverage is 12 tests.
- `13bedf8f` makes `typing_on`, `typing_off` and `mark_seen` sender actions
  token-free, provider-aware and observable through typed results and redacted
  logs. `d3e2c51b`/`0d471ebe`/`c0f9fd1f` add a bounded perceptible typing window,
  typing-off-before-marker/send ordering and permission-transition claim cleanup;
  the focused live-visual suite is 13 tests.
- Production migrations `0143`, `0144` and `0145` are applied; one daemon is running/alive on
  `instagram_login`, with fresh heartbeat and empty reply/notification queues.
- `IMP-084` is partial on `90fdd0ec`: exact warehouse/catalog allocation
  decisions, aggregate basket quantities, proposal reservation wiring and
  ambiguous mapping fail-closed guards are live; a production-like MariaDB
  allocation gate and full readiness/alternative consumer remain open.
- `IMP-085` is partial on `1849441d`: bounded parser facts reach the Gemini turn
  note and exact trusted URLs pin the published product; free-text/model IDs and
  options do not mutate payable state. Durable commerce-session reduction,
  candidate anchoring and full production-like parser proof remain open.
- `IMP-086` is partial on `a7857ada`: reservation states, warehouse payment
  commit, late-payment overbook state, write-off/reversal links, migration
  `0145` deterministic lock/revision/stale-callback hardening and paid commitment
  capacity protection are deployed.
  MariaDB concurrency/constraint proof and the final manager UI contract remain.

Любой новый срез начинается от актуального `origin/main`. При завершении агент
обязан обновить минимум этот раздел, соответствующую запись в
`03_FINDINGS_REGISTER.md` и checkbox в `07_IMPLEMENTATION_PLAN.md`, затем
интегрировать изменения в `main`. Статус из feature-ветки не является итоговым.

Правила статуса едины для всех последующих агентов:

- `[x]` ставится только когда код находится в `origin/main`, задеплоен и имеет
  свежую проверку;
- `[ ] РЕАЛИЗОВАНО В ВЕТКЕ` означает сохранённую работу, которую ещё нужно
  перенести на актуальный `main`, перепроверить и задеплоить;
- `[ ] PARTIAL` означает, что опубликована только часть требований, а явно
  перечисленный остаток всё ещё обязателен.

## IMP-102: durable follow-up delivery FSM закрыт и задеплоен (2026-08-05)

Коммиты `0d4d38c0`, `0e9e9ba5`, `4cb86743` и `414e639e` находятся в
`origin/main` и production. `IgFollowUpTask` теперь имеет явные
`PROCESSING/SENT/AMBIGUOUS/COMPLETED`, lease и provider receipt; timeout, 5xx,
unknown outcome и success без provider ID не повторяются вслепую, а переходят
в наблюдаемый `AMBIGUOUS`. Receipt сохраняется до fallible CRM/policy
finalization, recovery завершает receipt-committed строку без повторной
отправки, а конкурентный recovery не может откатить уже финальный `SENT`.

- Manager UI показывает actionable ambiguous delivery и пишет audited решение
  `delivered` / `not_delivered`; такие задачи не скрываются новыми follow-up и
  не удаляются generic cancellation/global stop.
- Fresh local gates: 23/23 focused delivery FSM и 160/160 expanded regression,
  Django check, migration drift, compileall и `git diff --check`.
- Production HEAD `414e639eced30a01ff2c5553b08605099465478c`, migration
  `management.0141` applied. Ровно один daemon: `running=True`, `alive=True`,
  `instagram_login`, `last_error=''`; `processing`, `ambiguous`,
  `sent_without_message` и `delivery_reviews` пусты.
- Закрыты `IMP-102`, `IMPR-FUP-014` и F-FUP-013. `IMP-103` /
  `IMPR-FUP-015` остаются открытыми: immutable event payload/time, absolute
  policy timeline и immediate invoice/restock fact recheck ещё не реализованы.

## F-PAY-015: daemon collision закрыта и задеплоена (2026-08-05)

Production на `d4500dbc` периодически падал при startup-reconcile: audit-ссылки
superseded payment review на canonical `order/deal` ошибочно становились
ownership edges и соединяли два коммерческих эпизода клиента `59`. Коммит
`93ae8684` сохраняет отдельную audit timeline, оставляет duplicate episode в
`lost / superseded_duplicate_payment_review`, использует `superseded_at` для
terminal chronology и очищает stale `current_commercial_episode`.

- Fresh local gate: 134 payment/commercial tests, Django check,
  migration-drift, compileall и `git diff --check`.
- Production MariaDB: `reconcile_ig_commercial_episodes --passes 3` завершён с
  `deals=0, reviews=0, attributions=0`; client `59` имеет отдельные episodes
  `2/3/7`, current pointer пуст.
- После static/compress/restart новый daemon: `running=True`, `alive=True`,
  transport `instagram_login`, heartbeat 1.0 с, `last_error=''`, pending reply,
  notification и analysis queues = 0.

## IMP-081 и catalog authority checkpoint (2026-08-05)

`bf4e0d80`, `674d6858`, `3678ddf4` находятся в `main` и production. Закрыты
F-CAT-005 (пустые/generic/punctuation aliases) и F-CAT-006 (revocation без
authoritative actor/reason). На MariaDB применены `storefront.0088` и
`product_catalog.0008`; три таблицы InnoDB, 77 inventory policies (`29 warehouse`,
`48 untracked`), append-only revision table защищена UPDATE/DELETE triggers.
`IMP-081` остаётся `[ ] PARTIAL`: semantic/policy foundation ещё не имеет
полного runtime/admin consumer и отдельного disposable MariaDB test gate.

## IMP-082/083 и F-CAT-007 price/size parity checkpoint (2026-08-05)

Price-aware graph/ranker foundation `7b5d5cc7`/`1c4d6d48` была интегрирована
историческим checkpoint `29684475`. Коммиты `e44d1440` и `0ad694bc` затем
исправили F-CAT-007 в текущем `main`/production: prompt-каталог связывает размеры
с точными `variant + fit` и отличает authoritative пустой size contract от
отсутствия variant-specific источника.

- Fresh gates: 188 focused, весь `management` 2675 (3 skipped), Django check,
  migration drift, compileall и `git diff --check`.
- Production product 110 prompt contract: `variant_id=81`, thermo green,
  1450 грн, `oversize=XS/M`; ложный product-wide ряд `XS/S/M/L/XL/XXL`
  удалён. Runtime: один daemon, `running=True`, `alive=True`, heartbeat 0.1 с,
  `instagram_login`, `last_error=''`, pending reply/notification queues = 0.
- `IMP-082/083` остаются `[ ] PARTIAL`: graph/ranker ещё не подключены к
  durable commerce session, отсутствуют stale-candidate binding, relaxed
  alternatives и полный print/blank/media topology. Исправленный prompt parity
  не закрывает эти остатки.
- `F-CAT-007` = `FIXED / VERIFIED`; она больше не входит в открытый остаток.

## IMP-077 / F-OPS-009: W8 alert lifecycle закрыт (2026-08-04)

`221cf37d` находится в `origin/main` и production. Завершены все восемь
пунктов F-OPS-009: глобальный flow-throttle, windowed entity dedupe, batch
summary и admin links были в `31f8151f`; финальный срез добавил proactive
monitor для `UNKNOWN`/`DEAD_LETTER`, раздельные lifecycle keys и украинские
операторские тексты, а также исключил два Telegram-алерта на один failed
paylink. Monitor не повторяет terminal provider outcome, а создаёт одну
почасовую summary-задачу после bounded drain; errors redacted, в summary есть
ссылка `/bot/`. Local regression: 75 tests; production `manage.py check`,
`run_instagram_bot --ensure`, SHA `221cf37d`, `running=True`, `alive=True`,
`instagram_login`, empty `last_error` и terminal outbox counts = 0.

## IMP-094: reliability checkpoint (2026-08-04, deployed; still OPEN)

### W2.1 bounded local baseline slice (2026-08-13)

The no-network baseline is now executable from any CWD via
`scripts/run_ig_baseline.py`. It creates a sanitized `0600` evidence JSON,
uses SQLite plus `test_settings_no_network`, denies external TCP/UDP/DNS,
fails fast, and parses Django summaries from either stdout or stderr. The
manager-echo queue failure was fixed at its transaction boundary: exceptions
from `schedule_analysis` are no longer swallowed and `_handle_echo` rolls back
the staged message, transition job and takeover state before the webhook
returns `503`.

Fresh evidence: the mandatory package ran **207 tests, 0 failures, 0 errors,
0 skipped** three times from the repository root, `twocomms/`, and `/tmp`;
telephony ran **62/62 OK**; runner contract tests **7/7 OK**. `F-DEBT-007`
remains open because isolated telephony success does not prove the historical
order/global-state flake is eliminated. `IMP-094`, `F-TEST-002` and `T41`
remain open for disposable MariaDB parity and full release provenance evidence;
the T40 rollback-fixture boundary is recorded below.

В рабочей ветке `codex/ig-bot-imp028-prompt` устранены три источника
ложных падений/гонок в SQLite-gate: ночные тесты с плавающим «сегодня» переведены
на фиксированное локальное время, регистрационный notifier и post-commit
fulfillment wake-up отключены только при `TESTING=True`, а recovery-schedule
failure теперь сохраняет явный `status=FAILED`, `send_state=failed` и
`processed_at`. Для MariaDB-профиля добавлена защита от эффективного
production-host `localhost`, когда `DB_HOST` не задан.

Доказательство: полный `management` suite прошёл **2619 тестов, 3 skipped**
из корня worktree и отдельным запуском из каталога `twocomms` (оба `OK`);
фокусный regression-пакет — **136 тестов `OK`**, дополнительный smoke-пакет —
**6 тестов `OK`**. Это только локальная SQLite-проверка: отдельная disposable
MariaDB не предоставлена, поэтому `IMP-094` и `F-TEST-002` остаются открытыми.
Commit `15147ded` находится в `origin/main` и на production: `manage.py check`
и migration-drift прошли, после restart штатный `run_instagram_bot --ensure`
подтвердил `running=True`, `alive=True`, transport `instagram_login` и пустой
`last_error`. Production MySQL не использовался как test database.

## IMP-041 и IMP-059 закрыты и задеплоены (2026-08-04)

Коммиты `f2a84717` и `244cbbd3` находятся в `origin/main` и на production.
Миграция `management.0135_instagrambottaskheartbeat` применена на MariaDB.

- Каждая из пяти production cron-задач пишет durable heartbeat с длительностью
  и безопасным типом ошибки; daemon проверяет stale/failure и ставит
  дедуплицированный Telegram-alert через durable outbox. Публичный
  `/bot/health/` учитывает daemon, ingress и cron.
- `ig_bot` пишет warning/error в отдельный rotating `ig_bot.log`, поэтому UI
  таблица на 500 строк больше не является единственным носителем диагностики.
  Высокий процент webhook `4xx` за пять минут (не менее 5 и 25%) создаёт один
  outbox-alert и переводит health в `rejections_degraded`; восстановление
  возможно только после фактического падения доли ниже порога.
- Production verification в 17:08 UTC: `db_vendor=mysql`, бот `enabled=True`,
  пять heartbeat без `last_error`, `/bot/health/` = HTTP 200,
  `bot_state=running`, `cron_unhealthy=0`.
- Отдельное улучшение дедупликации повторов именно в UI-таблице **не** выдано
  за готовое: оно остаётся открытым как `IMPR-OPS-002` / `IMP-100`.

## IMP-042 закрыта и задеплоена (2026-08-04)

`32985a63` находится в `origin/main` и на production. Миграция
`management.0136_encrypt_instagram_bot_settings_secrets` применена на MariaDB.

- `custom_direct_token` и `custom_gemini_key` теперь хранятся как versioned
  Fernet ciphertext в прежних DB-колонках; свойства модели расшифровывают их
  только для runtime. Legacy plaintext конвертируется миграцией.
- UI fail-closed: без корректного `FIELD_ENCRYPTION_KEY` новый custom credential
  не сохраняется. На production key создан только в private `.env.production`;
  все три private env-файла имеют mode `0600`.
- На production custom поля были пусты, рабочий provider-token остаётся из ENV;
  `db_vendor=mysql`, migration `0136=[X]`, daemon `running`, `/bot/health/` =
  HTTP 200. Профильный пакет: 75 encryption/privacy/runtime и 71
  observability/daemon тестов зелёные.
- `F-SEC-001` не был ошибочно закрыт: перенос небезопасных model defaults в
  явную конфигурацию остаётся открытым как `IMP-101`.

## IMP-028: authority и бюджет prompt — частично реализовано и задеплоено (2026-08-04)

Коммит `042c48c8` находится в `origin/main` и на production. Это не закрывает
широкий `IMP-028`: закрыт только безопасный runtime-срез, необходимый прежде
всего для честной цены варианта.

- `get_catalog_context(compact=True)` сохраняет все товарные строки, `variant_id`,
  цены конфигураций, фасоны/размеры и короткий visual fingerprint; обычный полный
  каталог не изменён для media/workflow. На production MySQL: 71/71 строк,
  19 696 символов compact против 27 157 full.
- В каждый system prompt добавлен единый порядок истины: verified payment/order
  facts → checkout/selected configuration → current turn/client state → live
  directives/playbooks → legacy style. Явная UA/RU/EN просьба и язык текущего
  сообщения выше старой формулировки; скидка каталога означает факт цены, а не
  право самостоятельно делать rescue-offer.
- Изменяемые brand knowledge, live directives, playbooks и quick links получили
  независимые лимиты по целым абзацам/инструкциям/строкам. Ни URL, ни цена, ни
  правило не режутся посередине. Production prompt с текущими данными: 35 495
  символов, canonical authority block присутствует.
- На этом историческом IMP-028-срезе товар `id=110` не подменялся: в production
  был только `variant_id=81` «Термо-зелена» за 1450 грн, а prompt ещё показывал
  product-wide XS–XXL. Позднее F-CAT-007 закрыта: текущий prompt `0ad694bc`
  показывает только authoritative oversize XS/M. Белая конфигурация 1090 грн
  всё ещё отсутствует в вариантах, media и rules: это `F-DATA-016` / `IMP-095`.
- Остаток `IMP-028`: реальные playbook-тексты для size/exchange/price/thinking,
  FAQ в `BotInstruction`, concrete close и voice, golden conversations и
  production acceptance ответов модели. Поэтому checkbox задачи остаётся `[ ]`.

## IMP-058 закрыта и задеплоена (2026-08-03)

Ветка `codex/ig-bot-imp058-funnel-analytics` проверена, слита с актуальным
`origin/main` и опубликована коммитами `274c2c61`, `79882368`, `92d46c5a`.
В production применена миграция `management.0133_ig_funnel_step_analytics`;
после restart heartbeat демона свежий, `state=running`, `last_error=''`.

- `IgFunnelStepEvent` записывает факты в транзакции бизнес-мутаций; фактический
  набор содержит 17 типов (`payment_confirmed` добавлен к исходным 16).
- `IgFunnelDropOff` хранит reason/stage/recoverability/recovery и разделяет
  silence, explicit refusal, opt-out, spam, unreachable и superseded.
- Event-time cohort API/UI сверены с raw MySQL: 197 events и 96 drop-offs.
  Backfill создал 5 канонических исторических событий; silence scan применил
  96 детерминированных фактов для лидов без verified payment/open episode.
- Исправлен production-only timestamp gap: `orders.Order` использует `created`
  и `updated`, а не `created_at`/`updated_at`; добавлен regression test.
- Focused gates: 53 funnel/follow-up, 161 analysis/inbox/intelligence,
  103 commercial/funnel; `check`, migration drift и compileall зелёные.

Срез до закрытия IMP-089 сохранён ниже как исторический журнал и не
переопределяет текущую сводку.

## IMP-089 закрыта и задеплоена — bounded recovery superseded invoices (2026-08-03)

Для исторических `superseded_invoice_ids` добавлен отдельный
`IgDealInvoiceLifecycle` и migration `0134`. Webhook и cron/daemon теперь
используют один ledger: старые invoice ID опрашиваются ограниченно, после
`paid/failed/cancelled/expired/unknown` получают terminal marker, а старый
платёж никогда автоматически не меняет новую товарную или платёжную
конфигурацию сделки. Legacy JSON materialization ограничена batch-лимитом;
manager alert идемпотентен по invoice ID.

- Локальный gate: 104 теста (`superseded_invoice`, TTL, payment backstop,
  funnel analytics/journal), `manage.py check`, compileall и `git diff --check`
  зелёные.
- Production: migration `0134` применена; `poll_ig_deal_payments --check-only
  --limit 50` вернул `projections=0 provider_invoices=0
  superseded_invoices=0 orders=0`; lifecycle rows = 0, потому что исторических
  superseded ID на сервере нет; daemon `running=True`, `last_error=''` после
  краткого transient worker error.

Следующий незакрытый блок — W8 (наблюдаемость/долг), затем W9/W10; старые
исторические абзацы ниже сохраняют состояние на дату своего среза и не
переопределяют эту сводку.

## Восстановление веток и WIP (2026-08-03)

Проверены все локальные и remote refs, worktree, reflog и недостижимые stash-
коммиты. В истории найдено 41 first-parent коммит, менявший эту папку (57 по всем refs); вся цепочка W0–W8
включена в `main`. Разошедшаяся `docs/ig-bot-audit-w0` содержит эквивалентные
ранние коммиты и не имеет уникальных идентификаторов.

| Источник | Что сохранено в `main` | Граница статуса |
|---|---|---|
| `codex/ig-bot-w1-data-safety`, W2, W3, W4/W4C/W4D, W5/W6/W7/W8 | Все изменения шести файлов этой папки по линейной истории до `1380db8e` | Закрытие только по evidence внутри реестра и плана |
| Старая локальная копия до fast-forward | Сверено 242 идентификатора против 310 в актуальной папке; локально-уникальных нет | Архивирована в stash `pre-instagram-audit-consolidation-2026-08-03`, не источник истины |
| WIP stash W3/IMP-013 и W4D | Уникальных `F-*`/`IMP-*`/`DR-*` нет; содержание вошло в последующие коммиты | Не применять поверх текущих файлов |
| `codex/ig-crm-master-audit` | 23 строки ingress-review сохранены в `docs/qa/IG_CRM_ORDER_ATTRIBUTION_CHECKLIST_2026-07-25.md` | Это локальное WIP-evidence; live acceptance остаётся открытым |
| `codex/ig-crm-master-audit` dirty worktree | Шесть незакоммиченных ingress/Meta-файлов находятся на базе, отстающей от `main`; поверх них нельзя делать вывод о production | Не интегрировано и не закрывает `IMP-*`; сначала rebase/перенос по файлам, затем отдельный Meta-contract review |
| `codex/ig-order-fulfillment-links`, `20dd44b2` | Searchable order-assignment drawer семантически присутствует в актуальном `main`: отдельный drawer, поиск кандидатов, blocked reasons, keyboard/focus и тесты | Сам старый коммит не cherry-pick: текущая реализация новее и входит в W7 (`bca7e4e2`) |
| `codex/ig-bot-w4-completion` dirty W7 | Локальный незавершённый paginator сравнен с `main`; текущий `main` уже имеет Django `Paginator`, API-контракт и полный UI W7 | Не переносить: старый diff удаляет новые метрики, drawer UX и актуальный pagination contract |
| `codex/management-bot-visual-refinement` | Четыре UI code slices (`d7f10477`/`8a2f9ee1`/`233297b3`/`6e05c6b2`) и отдельный docs shortlist (`e262c0c4`) | IN MAIN / SUPERSEDED branch base; current-main UI tests 135/135, историческая ветка 129/129 |
| `.claude/worktrees/ig-bot-w1` dirty W6 | Арбитр, FSM, журнал переходов и funnel-ветви находятся в `main` (`34d1e165`) | Не переносить старый working diff: он основан на W3 и откатывает значительную часть текущего `instagram_bot.py` |
| `.claude/worktrees/ig-bot-w1` unique `tests_ig_stock_policy.py` | В WIP сохранились полезные требования: quantity-aware `VariantSizeRule`, явный `is_dropship_available=False`, manager/event при реальном дефиците, сохранение `missing_fields` | Восстановить требования тестами поверх актуального `main` в IMP-056/084/086; файл целиком не переносить, потому что его база откатывает IMP-080 и W6 |
| `codex/ig-refresh-dedup` и stash manual inbox refresh | Durable refresh, poll cursors и link-restriction circuit уже опубликованы более полным коммитом `7fe26280` | Старую ветку/stash не переносить; она отстаёт от `main` и не содержит дополнительного закрытия |
| `codex/instagram-assisted-checkout` | Добавлены design/plan product reselection, 339 строк поздних уточнений и статусы 13 задач; сохранены ссылки на пять исторических code-коммитов | IMP-081 перенесена независимо; IMP-082/083 переработаны и задеплоены через `7b5d5cc7`/`1c4d6d48`; availability из `e9d982df` перенесена как `17f5b672`; `dc9889c3` остаётся source для IMP-085, без wholesale cherry-pick |
| `codex/ig-followup-policies` dirty worktree | Старый W4B-код плюс уникальные требования delivery FSM и materialized event continuation | Delivery boundary и event continuation заново реализованы в main как IMP-102/103 и IMPR-FUP-014/015 (`434428ad`); wholesale cherry-pick запрещён из-за старой базы и конфликтующей migration `0131` |
| `instagram_bot_audit_prompt_package/` | Исходный prompt, 120 audit-задач, gates и acceptance matrix сохранены рядом с репозиторием | Источник требований, не журнал выполнения |

## Родственные документы, которые нельзя потерять

Они остаются отдельными, потому что описывают разные контракты и содержат свои
чек-листы. Их нельзя объявлять закрытыми только потому, что закрыта похожая
`IMP-*` задача:

- `docs/plans/2026-07-22-management-instagram-bot-super-upgrade-plan.md` —
  исторический CRM/Meta/Gemini master-plan; часть checkbox устарела и требует
  evidence-mapping, но содержание сохранено полностью.
- `docs/qa/IG_CRM_ORDER_ATTRIBUTION_CHECKLIST_2026-07-25.md` — order attribution,
  ingress и management workspace; после восстановления остаётся 25 прямых
  незакрытых checkbox.
- `docs/plans/2026-07-30-instagram-assisted-checkout-checklist.md` — отдельный
  checkout-контракт; 12 прямых checkbox остаются открытыми.
- `docs/superpowers/specs/2026-08-02-instagram-product-reselection-intelligence-design.md`
  и парный implementation plan — восстановленный дизайн. IMP-081 и partial
  IMP-082/083 уже перенесены на актуальный `main`; availability foundation
  IMP-084 опубликована как `17f5b672` и proposal reservation wiring завершена
  в `90fdd0ec`; IMP-085 parser/runtime и IMP-086 hardening опубликованы как
  `1849441d`. Они остаются PARTIAL до durable session/candidate anchoring,
  manager-review UI и disposable MariaDB proof.

## Исторические выводы исходного аудита (снимок W0)

> Раздел ниже объясняет, почему задачи появились. Для текущего состояния
> использовать сводку и активный остаток выше, а не исходные числовые значения.

1. **Система почти не работает как автоматизация.** 149 входящих webhook →
   **16 ответов** бота. 115 отклонённых webhook по подписи. Gemini вызывался 12 раз.
   Это инвертирует приоритеты: качество ответов бессмысленно улучшать,
   пока входящие теряются.
2. **Backstop платежей мёртв с 8 июля** (~24 дня): `poll_ig_deal_payments`
   удалён из crontab. При недоставленном webhook Monobank оплата не будет
   замечена никогда.
3. **Post-purchase цепочка простаивает из-за привязки, не из-за отправки:**
   `IgOrderAssignment` = 2 записи на 289 клиентов. Механизм доставки ТТН
   исправен и локализован (uk/ru/en). Причина — привязка заказа требует
   ручного ввода точного номера, хотя поиск кандидатов уже реализован рядом.
4. **Жалоба заказчика воспроизведена на живых данных** (клиент #59): оплатил,
   обмен размера в пути — карточка показывает «cold · Підтримка / скарга · 0%».
   Цепочка из 6 звеньев, все подтверждены кодом.
5. **`purchases_count` = 0 у всех 289 клиентов.** Система не знает ни одного покупателя.
6. **Атрибуция рекламы = 0 у всех 289.** Дашборд по рекламе структурно пуст.
7. **Промокода 10% за UGC не существует**, хотя просьба отметить бренд отправляется.
8. **Шесть машин состояний без арбитра** — корень класса симптомов. Клиент #59
   противоречит себе одновременно в пяти представлениях.
9. **987 сигналов пишутся и не читаются при генерации** — прямой ответ на вопрос
   заказчика: да, сигналы «просто есть».
10. **Два P0 по безопасности:** анонимный POST удаляет клиента и всю переписку
    по публичному username; удаление логов по подстроке стирает чужие записи.
11. **Модель Gemini выбрана верно** (`gemini-3.6-flash`, актуальная по документации),
    логика приоритета корректна (model-major по всем 6 ключам). Дефект только
    в мусорном значении в БД, которое молча нормализуется и утекает в лог.
12. **Размеров нет в контексте бота вообще** — при том что `resolve_product_sizes`
    и `SizeGrid.guide_data` уже написаны. Бот не может вести размерный диалог,
    а это барьер №1 в онлайн-одежде.
13. **Восемь конфликтов паттернов классификации** с конкретными примерами:
    «Скільки коштує доставка?» → бот предлагает скидку; «it's ok» → вопрос
    о размере; телефон в тексте → +40 к готовности покупать.
14. **Много готового и неподключённого:** `RestockSubscription`,
    `IgCheckoutAccessToken` (включая `Kind.SHARE`), `IgDealItem`,
    `SizeGrid.guide_data`, `sales_context`, `IgLifecycleEvent`, `manual_confirmation_q`.
    Большинство дешёвых улучшений — подключить существующее, а не писать новое.

## W4 опубликована; W4B оставалась частичной на историческом срезе (2026-08-02)

- IMP-020–024 и IMP-054 подтверждены в `origin/main` и на production.
- Текст обычной ТТН сообщает только факт пути, номер, tracking URL и ориентир
  1-3 рабочих дня. Нет заявлений об оплате/доплате и инициативного обмена.
- Подтверждённая замена сообщает факт замены и известный размер, но не делает
  платёжных заявлений и не предлагает следующий обмен.
- UGC-награда выдаётся менеджером вручную только после проверки evidence и
  только для полученного заказа; автоматического Direct/Meta сообщения нет.
- На момент этого среза IMP-058 и найденная при payment-аудите IMP-089 были открыты;
  IMP-051/053/055/056 закрыты отдельными production-срезами
  `2a89d860`/`cd070cba`/`efc0ee10`.
- Production работает на SHA `d0098d0b`; серверная БД подтверждена как MySQL,
  миграции `management.0130`–`management.0132` применены.

## IMP-056 закрыта: событийная добивка и durable claim (2026-08-03)

Событийные шаги больше не остаются только в таблице policy. Истечение
оплатной ссылки материализуется из `invoice_expires_at` с уникальным ключом;
возврат размера после stock-gap поднимает restock-событие при следующей
readiness-проверке. Follow-up-задача захватывается атомарно через
`claim_token`/`claim_until` поверх client lease, поэтому второй daemon не
отправляет её параллельно. `send_text(return_receipt=True)` сохраняет Meta
`provider_message_id`; отсутствие подтверждённого receipt и ambiguous outcome
закрываются fail-closed. Event/manager-шаг после отправки продолжает ту же
policy, а активные задачи одного `(client, kind, level)` заменяются явно.

Проверки: `python manage.py check`, migration drift check, 72 теста цены,
policy и event/claim; полный management-suite остаётся нестабильным по
предсуществующим F-TEST-002 (11 failures/4 errors при запуске из корня), поэтому deploy gate —
фокусный пакет и production MySQL migration/contract check.

## IMP-057 закрыта: lifecycle возражений (2026-08-03)

Вопрос о цене и настоящее возражение разведены: нейтральное «скільки коштує?»
остаётся ценовым intent, а `дорого` открывает lifecycle. Добавлены 12 типов
возражений, `IgObjection`/`IgObjectionAttempt`, verified fingerprint для
`[OBJHANDLE:type:method]`, повторное открытие после re-objection, граница
текущего эпізоду/ресета и отдельный prompt-блок с историей неудачных методов.
Compound-turn материализует каждое распознанное возражение, а не только первый
regex-match.

Критичный денежный инвариант: `CHECKOUT_STARTED` теперь даёт только
`accepted`/рост readiness; `purchased` выставляется только по confirmed payment.
Provider send создаёт локальный MODEL-ledger до необязательной objection
аналитики, поэтому её сбой не теряет доказательство отправленного ответа.

Проверки: 23/23 `tests_ig_objections`, 147/147 связанных classifier/routing/
intelligence/payment тестов, `check`, migration drift и compileall. Production:
SHA `d0098d0b`, migration `0132`, обе новые таблицы `InnoDB`, 12 active objection
playbooks, daemon `running`, heartbeat 0.9 с, `instagram_login`, `last_error` пуст.

## Что закрыто в этой итерации (было незакрытым)

- ✅ **Домен K (K01–K10), UX/UI:** инвентарь 6 табов, ~60 интерактивных элементов,
  2 drawer'а. **Все шесть гипотез задания подтверждены**, включая более сильную
  форму: ⇄ и ⚙ открывают не «похожие», а **одну и ту же** панель.
- ✅ **Домен L (L01–L10), безопасность/тесты/наблюдаемость:** права всех
  bot-эндпоинтов, CSRF, PII, секреты, покрытие критичных путей, feature flags.
  Гипотеза «любой залогиненный меняет промпт» **опровергнута**; найдены два
  других P0.
- ✅ **Воронка и согласованность состояний:** 15 путей записи `stage`,
  матрица конфликтов, карта зависимостей «изменение → влияет на».
- ✅ **Паттерны классификации:** полный список + 8 конфликтов порядка.
- ✅ **Реестр улучшений:** отдельный документ, 48 пунктов с готовыми текстами.

## Исторический незакрытый список после исходного аудита

> Часть пунктов ниже позднее закрыта в W0–W7. Текущий список находится в
> разделе «Активный остаток» в начале файла.

- **`01_SYSTEM_MAP.md` и диаграммы A08–A10** (sequence входящего сообщения,
  checkout→payment→order, data lineage). Данные для них собраны в findings,
  но Mermaid не нарисован.
- **`06_TEST_MATRIX.md`** — 40 приёмочных сценариев из `12_ACCEPTANCE_TEST_MATRIX.md`
  не расписаны по фактическому покрытию. Частично покрытие есть в findings
  волны 5 (домен L, раздел «Тестовое покрытие»).
- **Открытые вопросы W0** (блокируют 3 P0-задачи):
  причина `bad_signature`; есть ли рекламные поля в 425 сырых событиях;
  HTTP-коды `image_download`; почему `failed` при `attempts=1`.
- **Историческая пометка о браузере снята для W7:** workspace проверен живым
  рендером на 1440x900 и 390x844, включая stacking, overflow, keyboard tabs,
  Escape и возврат фокуса. Остальные поверхности старого UX-аудита этим не
  считаются автоматически перепроверенными.
- **4 решения от заказчика** (см. конец плана): промокод 10%, судьба
  checkout-домена, судьба `IgLifecycleEvent`, приоритет W5 против W7.

## Правила безопасности аудита (соблюдены)

1. На проде только read-only: `SELECT`, `SHOW`, `COUNT`, `crontab -l`, `tail` логов.
   Ни одного `INSERT/UPDATE/DELETE`, ни одной миграции.
2. Реальные заказы, ТТН, платежи, сообщения клиентам не создавались.
3. Секреты в файлы репозитория не попадали — только имена переменных окружения.
4. PII не выносилась: клиенты обозначены как `IgClient#59`, содержимое
   переписок не копировалось.
5. Код не менялся до завершения аудита (требование `01_MASTER_PROMPT.md` §3.1).

## W0 закрыта — результаты (2026-08-01)

Все четыре открытых вопроса закрыты. Evidence — `03_FINDINGS_REGISTER.md`,
раздел «Волна W0». Решения по изменению плана — `04_DECISION_LOG.md`, DR-005.

| Вопрос | Задача | Результат |
|---|---|---|
| Причина 115 `bad_signature` | IMP-001 ✅ | Реальный отказ ingress **24–30.07, ~2268 отклонённых POST от Meta**, уже устранён. Август — 0 отказов |
| Рекламные поля в сырых событиях | IMP-002 ✅ | Meta **не присылает их вообще** (полная инвентаризация 438 payload'ов). Код не виноват |
| HTTP-коды `image_download` | IMP-003 ✅ | **100% HTTP 404**; 73 из 97 — ретраи мёртвых ссылок из импорта истории |
| `failed` при `attempts=1` | IMP-004 ✅ | Не активный баг: legacy-кластер 14.06–10.07, текущим кодом невоспроизводим |

**Главный вывод W0.** F-CORE-011 («бот почти не отвечает») объясняется
инфраструктурой, а не качеством ответов. Два документированных отказа подряд:
**14.06–10.07 бот не мог отправлять** (26 permanent-отказов Meta Send,
вероятно Graph #200 / Advanced Access), **24–30.07 бот не мог принимать**
(подпись webhook). 16 ответов на 149 входящих — следствие этого,
а не промпта. DR-004 подтверждён и усилен.

**Три из четырёх P0-обоснований снялись.** Что изменилось в плане (DR-005):
- IMP-001…004 — закрыты.
- **IMP-012: P0 → P1 и переформулирован.** Подпись НЕ трогаем (нет
  воспроизводимого дефекта, есть риск регрессии в только что стабилизированном
  месте). Вместо этого — наблюдаемость: логгер `ig_bot` в handler,
  сохранение сырого тела до `json.loads`, алерт на долю 4xx.
- **IMP-043 (атрибуция рекламы): P1 → P3 + вопрос заказчику.** Источника
  данных не существует, парсер писать не на чем. Отдельно и независимо:
  пустая таблица `ad_rows` дезинформирует («0 конверсий» вместо «данных нет»).
- **F-DATA-011: P1 → P2.** Направление: не качать вложения импортированных
  сообщений, сохранять байты при приёме живого webhook.
- **F-CORE-010:** только инвариант-тест
  `failed ⇒ (attempts>=MAX_ATTEMPTS) OR (send_state != '')`. Данные не трогать.

**Новые находки, обнаруженные в ходе W0:**
- **F-OPS-004 (P1)** — `LOG_KEEP_ROWS=500` уничтожил 95% следов шестидневного
  отказа всего входящего контура. Отказ ingress технически ненаблюдаем;
  обнаружен случайно, по access-логам веб-сервера. Слить с IMP-041.
- **F-SEC-010 (P2)** — `hub.verify_token` попадает в access-log в открытом виде,
  в том числе из наших собственных диагностических скриптов.

**Незакрытый остаток W0:** вывод «ingress здоров» опирается на 11 запросов
августа — выборка мала. **Перед началом W2 повторно проверить долю 403
на `/bot/webhook/`.** Если она ненулевая — DR-005 неверно, вернуться
к правке подписи.

## ⚠️ Расхождение baseline (обнаружено 2026-08-01 при попытке push)

Утверждение «`2f75f9d9` синхронен с origin/main и с продом» **неверно**.
Фактически:

- `origin/main` = `b450b5c2`, это **+18 коммитов** над `2f75f9d9`.
- **Прод работает на `b450b5c2`**, не на baseline.
- Объём расхождения в моём домене: `git diff --shortstat 2f75f9d9 origin/main
  -- twocomms/management/` → **37 файлов, +6379 / −230**.
  В том числе `services/instagram_bot.py` +348, `bot_views.py` +381,
  `services/ig_order_fulfillment.py` +66. Появился целый домен
  assisted checkout (`bot_catalog.py`, `bot_orders.py`, `bot_payments.py`,
  `ig_bot_models.py`, `poll_ig_deal_payments.py` и др.).

**Что это значит для аудита:** ссылки `файл:строка` во всех находках
относятся к `2f75f9d9`. В двух самых «горячих» файлах нумерация сдвинута.
Само содержание находок при выборочной проверке подтвердилось:

| Находка | Статус на `origin/main` |
|---|---|
| F-SEC-002 (анонимное удаление) | **присутствует**, `bot_views.py:189` (было `:187`) |
| F-SEC-003 (удаление логов по подстроке) | **присутствует**, `bot_views.py:161` (было `:159`) |

**Правило для следующего агента:** перед каждой задачей проверять текущее
состояние файла на `origin/main`, а не доверять номеру строки из реестра.
Часть находок могла быть закрыта коммитами assisted checkout — проверять,
а не предполагать.

**Почему я не переключил локальный main:** в рабочем дереве лежат
незакоммиченные правки другого агента по домену `custom_print`
(9 изменённых файлов). `git pull --rebase` потребовал бы autostash их работы —
это риск для чужой незавершённой задачи. Работа W0 сохранена на ветке
`docs/ig-bot-audit-w0`. Для W1 нужен изолированный worktree на `origin/main`.

## W1 закрыта — безопасность данных (2026-08-01)

Внедрено на базе `b450b5c2`. Evidence — `03_FINDINGS_REGISTER.md`,
раздел «Волна W1». Решение по правам reviewer — DR-006.

| Задача | Находка | Результат |
|---|---|---|
| IMP-005 | F-SEC-002 (P0) | ✅ Публичная форма больше не удаляет: заявка `pending_verification` + исполнение менеджером через `fulfill_ig_data_deletion`. Путь Meta (HMAC) не тронут |
| IMP-006 | F-SEC-003 (P0) | ✅ Логи удаляются только по структурной принадлежности IGSID. Совпадение по подстроке и username исключено |
| IMP-006 | F-SEC-009 (P2) | ✅ Текст сообщения клиента больше не пишется в `InstagramBotLog.detail` |
| IMP-005 сл.3 | F-SEC-002 | ✅ Новый rate-limit класс `public_destructive` = 10/60с вместо 600/60с |
| IMP-007 | F-SEC-004 (P1) | ✅ Частично: 403 на мутации реальных карточек, запрет смены модели и транспорта; демо-контроль оставлен и атрибутирован (DR-006) |

**Что red-тесты доказали до правки** (это и есть подтверждение аудита
на исполняемом коде, а не на чтении):
- идентификатор `"0"` удалял **5 из 6** строк операционного лога;
- лог **другого** клиента стирался, если в его тексте упоминался username удаляемого;
- поиск по username при этом **не** удалял логи самого клиента — код и
  переудалял, и недоудалял одновременно;
- анонимный POST удалял карточку клиента целиком;
- все 8 мутирующих эндпоинтов пускали внешнего Meta-reviewer с ответом 200.

**Осознанно изменены два существующих теста**, закреплявших уязвимое
поведение как ожидаемое (`tests_ig_privacy_policy.py`). Исходный смысл
каждого сохранён и усилен — подробности в разделе W1 реестра.

**Тесты:** 57 в затронутых модулях — зелёные. Широкий IG-прогон — 1262 теста,
единственное падение `PaymentLinkGateTests` воспроизведено на чистом
`origin/main` до моих правок → занесено как **F-DEBT-005 (P3)**,
не связано с W1.

**Новое в коде:** `services/ig_data_deletion.py`,
`management/commands/fulfill_ig_data_deletion.py`,
`tests_ig_data_deletion_safety.py`, `tests_ig_reviewer_sandbox.py`,
миграция `0120_bot_deletion_pending_verification` (только `choices`).

**Операционное замечание для менеджера:** заявки на удаление данных теперь
надо исполнять руками. Список ожидающих —
`python manage.py fulfill_ig_data_deletion --list`,
предпросмотр объёма — `--dry-run`, исполнение — `--code=XXX --actor=имя`.
Уведомление о новой заявке приходит в Telegram.

## W2 закрыта — проходимость контура (2026-08-01)

Evidence — `03_FINDINGS_REGISTER.md`, раздел «Волна W2».
Gate из W0 пройден: доля 403 на `/bot/webhook/` в августе — **ноль**.

| Задача | Находка | Результат |
|---|---|---|
| IMP-008 | F-CORE-001 (P0) | ✅ `notify_shipped_deals` соблюдает `is_enabled`, `bot_paused`, `manager_takeover`, `is_blocked`, `hidden_at`, opt-out; отправка внутри `customer_send_boundary`. Обе ветки — сделки и эпизоды |
| IMP-009 | F-OPS-001 (P0) | ✅ cron `poll_ig_deal_payments` восстановлен с `flock`, каждые 4 минуты. Радиус замерен до включения: 0 сообщений клиентам |
| IMP-010 | F-PAY-001 (P0) | ✅ `superseded_invoice_ids` + поиск по истории в webhook + алерт менеджеру. Миграция `0121` |
| IMP-011 | F-AI-001/002 (P0) | ✅ `_prompt_section` / `_pin_control_product`: сбой контекста пишет `error` с именем источника |
| IMP-012 | F-CORE-002, F-SEC-007 | ✅ битый payload оставляет `webhook_bad_payload` без PII; логгер `ig_bot` объявлен |
| IMP-004 | F-CORE-010 | ✅ инвариант закреплён тестом, проверен инъекцией регресса |
| — | F-DEBT-005 (P3) | ✅ закрыт одной строкой |

**Что red-тесты доказали до правки:** сообщение с ТТН уходило клиенту на
паузе, с opt-out, заблокированному, скрытому, с перехватом менеджера — и даже
при выключенном боте, то есть кнопка «стоп» этот путь не останавливала.
Для деградации промпта red-green проверен откатом фикса: 5 тестов из 6 падают.

**Радиус восстановления cron замерен заранее** (read-only) и проверен фактом
после включения. Проба предсказала 1 эпизод-кандидат, реальность — **0**:
проба не воспроизвела исключение по активной привязке заказа. Ошибка была
в безопасную сторону. Первый прогон cron: `0; 0; 0; 0`, ни одного исходящего
сообщения, задач менеджеру не создано.

**Оговорка о проверке guard'ов:** живого случая в проде не было — очередь
отправки ТТН пуста. Корректность guard'ов подтверждена 10 unit-тестами,
включая регресс «чистый клиент по-прежнему получает ТТН», а не
продакшен-наблюдением.

**Тесты:** 1295 в IG-домене, 0 падений. `makemigrations --check` чист.

## W3 в работе — истина о покупателе (2026-08-02)

Evidence — `03_FINDINGS_REGISTER.md`, раздел «Волна W3». Уточнение DR-001 — DR-007.

| Задача | Находка | Результат |
|---|---|---|
| IMP-013 | F-DATA-005 (P0) | ✅ `purchases_count` перестал быть нулём у всех. Прод: 2 покупателя из 289, #59 → 1 покупка / 2100.00 |
| IMP-013 | F-SCORE-004 (P0) | ✅ «дякую» от покупателя больше не снимает 10 баллов: red-тест 50→40 до правки, 50→100 после |
| IMP-013 | F-SCORE-005 (P0) | ✅ Ручное подтверждение и привязанный оплаченный заказ признаны доказательством покупки |
| IMP-013 | **F-DATA-013 (P1, новая)** | ✅ `manual_confirmation_q` привязан к `IgDeal`, а у всех 28 прод-review `deal_id IS NULL` → рецепт DR-001 давал ноль совпадений |
| IMP-013 | **F-PAY-012 (P0, новая)** | ✅ Два денежных пути читают `client_has_verified_payment`; расширение сломало бы повторные продажи. Строгий предикат не тронут |
| IMP-013 | **F-DATA-014 (P1, новая)** | ✅ У агрегатов было два писателя с разными единицами (перезапись vs инкремент). Остался один |
| IMP-014 | F-SCORE-003 (P0) | ✅ `paid` перестал быть недостижимым. До правки — 0 записей из 1945 снапшотов прода |
| — | **F-DEBT-006 (P2, новая)** | 20 красных тестов на `origin/main`. Базовая линия зафиксирована, множество падений после правки идентично |
| — | **F-OPS-005 (P1, новая)** | Событие с ТТН клиента #303 залипло в `waiting_window`, 53 попытки, без дедлайна и эскалации. Клиент ТТН не получил |
| — | **F-STATE-009 (P2, новая)** | У #303 оплаченный отправленный заказ, но `stage='new'`: стадия пересчитывается только от входящего сообщения |

**Главный урок W3 на текущий момент.** Два раза подряд уже принятое решение
аудита оказалось неисполнимым в буквальном виде, и оба раза причина одна:
предикат/функция существует, выглядит подходящей, но отвечает **не на тот
вопрос**. Проверка «есть ли функция» не заменяет проверки «даёт ли она
непустой результат на живых данных». Правило для следующих задач: перед
переиспользованием готового предиката прогонять его на проде read-only
и смотреть на число строк.

## W3 закрыта полностью (2026-08-02)

| Задача | Находка | Результат |
|---|---|---|
| IMP-015 | F-SCORE-002/006 (P0) | ✅ `exchange_request`/`return_request`, тон `service`, реальная жалоба остаётся жалобой. Найден мёртвый `RETURN_RE` для «поверніть» |
| IMP-016 | F-SCORE-009, F-CTX-002 | ✅ Гашение на трёх уровнях: follow-up, тег `sales`, guardrails промпта |
| IMP-017 | F-PAT-001 (P1) | ✅ Явная `INTENT_PRIORITY`, все 8 конфликтов закрыты |
| IMP-017 | **F-PAT-002 (P1, новая)** | ✅ `DELIVERY_RE` и `PREPAY_RE` не матчили живой язык: `intent=delivery` — 0 из 289, `objection=prepayment` — 0, сигнал — 0 из 989 |
| IMP-018 | F-SCORE-008, F-STATE-008 | ✅ Наложение факта вместо выбора снапшота; гейт кейса по формулировке + состоянию (DR-008) |
| IMP-018 | **F-UX-014 (P2, новая)** | ✅ Бейдж обмена больше не светится вечно и показывает статус |
| IMP-019 | F-SCORE-001 (P0) | ✅ «намір купити зараз» вместо «ймовірність», бейдж покупателя с честным происхождением суммы |
| **IMP-062** | **F-OPS-006 (P1, новая)** | ✅ Журнал `IgOrderShipment`: ТТН обмена привязана к тому же заказу, три ноги видны таймлайном (DR-009) |
| — | **F-DEBT-007 (P3, новая)** | Флейковый тест `test_ack_state_reflected` — не моя регрессия |

**Главный урок волны, повторившийся три раза.** Формулировки задач в плане
описывали правильные **цели** и неверные **механизмы**, потому что писались из
чтения кода, а не из данных. Каждый раз механизм ломался на конкретном факте
прода:

1. IMP-013: `manual_confirmation_q` привязан к `IgDeal`, а у всех 28 review
   `deal_id IS NULL` → ноль совпадений.
2. IMP-013: `client_has_verified_payment` читают два **денежных** пути →
   расширение сломало бы повторные продажи.
3. IMP-018: `IgOrderAssignment` = 2 записи на 289 клиентов → гейт «только
   покупателю» отменил бы сам механизм постпродажных кейсов.

**Правило для остатка плана:** перед реализацией пункта прогонять на проде
read-only те таблицы и регексы, на которые пункт опирается, и считать строки.
Проверка «функция существует» не заменяет проверки «даёт непустой результат».
Регексы проверять на живых строках: два из них оказались нерабочими, и по коду
это не читалось.

## Следующий шаг

1. ~~W0: 4 открытых вопроса~~ — **сделано**.
2. ~~W1: два P0 по безопасности данных~~ — **сделано**.
3. ~~W2: проходимость контура (IMP-008 → 009 → 010 → 011 → 012)~~ — **сделано**.
4. ~~W3: IMP-013…019 + новая IMP-062~~ — **сделано**.
5. ~~W4 — доставка сообщений клиенту~~ — **сделано**.
6. ~~W4C — диалог ведёт модель, а не скрипт~~ — **сделано и задеплоено**
   (`3191e08c`).
7. **Через сутки после деплоя** пересчитать долю 403 на `/bot/webhook/` по
   access-логу. Прямая проба корректна, но окно отказов закончилось само до
   рестарта, поэтому наблюдения за реальным потоком пока мало. Именно на этом
   ошиблась W0.
8. Исторический остаток W4B: IMP-058 и IMP-089; позднее IMP-058 закрыта
   production-срезом `92d46c5a`, а IMP-089 — `280c07e8`; W4B закрыта полностью.
   IMP-051/053/055/056/057 закрыты и задеплоены; следующий по порядку —
   статистика переходов и отвалов IMP-058.
9. Решения заказчика: checkout-домен, `IgLifecycleEvent`, приоритет W5 против
   W7. Промокод 10% решён в W4 (вариант B — ручная выдача).
10. **W8 / IMP-094:** F-DEBT-006 (предсуществующие красные тесты),
   F-DEBT-007 (флейк), F-OPS-005 (ТТН-событие без дедлайна эскалации),
   F-STATE-009 (оплаченный заказ не двигает стадию), **F-OPS-008** (лог живёт
   4 часа), **F-DATA-015** (ответы бота помечены как сообщения менеджера),
   F-TEST-002/003 (недетерминированный suite и SQLite/MySQL contract parity).

## История обновлений

| Дата | Что сделано |
|---|---|
| 2026-08-01 | G0: baseline, доступы, инвентарь прод-таблиц, структура docs |
| 2026-08-01 | Волна 1: ядро обработки сообщений (17 находок) |
| 2026-08-01 | Волна 2: AI-слой, денежный контур, скоринг (+34) |
| 2026-08-01 | Волна 3: находки из данных прода (+12), кейс клиента #59 |
| 2026-08-01 | Волна 4: crontab, post-purchase, промокод (+5, 2 переоценки severity) |
| 2026-08-01 | Приоритизация через sequential thinking, план v1, DR-001…DR-004 |
| 2026-08-01 | Волна 5: домены K и L, воронка, паттерны (+14); реестр улучшений (48); план v2 |
| 2026-08-01 | **W0: диагностика закрыта.** 4 вопроса → 4 ответа; 3 P0-обоснования снялись; +2 новые находки (F-OPS-004, F-SEC-010); DR-005. Код не менялся |

## W4 / W4B — ядро закрыто, остаток назван честно (2026-08-02)

**Разведка перед волной (субагент, read-only прод) дала факт, который изменил
приоритеты внутри W4B:** `InstagramBotMessage.role` — user 1165, manager 1152,
**model 20**. Бот ответил 20 раз на 289 клиентов, 249 диалогов вёл человек.
Значит длинные каскады добивки строятся на пути, который почти не исполнялся,
и первое, что нужно, — чтобы этот путь был **безопасным и наблюдаемым**,
а не длинным.

| Задача | Статус | Результат |
|---|---|---|
| IMP-020 | ✅ **уже было сделано** | `renderAssignmentPicker` + `bot_order_candidates_api`, ⇄ и ⚙ разведены на разные drawer'ы (коммиты assisted checkout). Реестр в этой части устарел |
| IMP-052 | ✅ закрыта | Частотный лимит (≤1 автосообщение в 18 ч, ≤5 за 30 дней), `opted_out` как самостоятельная причина, подавление `COLD`/`LEAD_TO_MANAGER`/`wholesale_b2b`/`collaboration`, дедуп текста. Задача менеджеру в лимит не входит |
| IMP-049 | ✅ закрыта | Выход за окно Meta даёт `MANAGER_TASK` со `status=PENDING` и `reason=meta_window_closed` вместо `SKIPPED`. ≈половина «подумаю»-добивок больше не исчезает молча |
| IMP-047 | ✅ закрыта | `Kind.FINAL` 10% достижим; rescue разрешён для `NEW`/`QUALIFYING`; `COLD`/`LEAD_TO_MANAGER` отсекаются раньше, в suppression |
| IMP-048 | ✅ закрыта | `deal=` передаётся в `schedule_after_bot_reply`; платёжная ветка перестала зависеть от того, записалась ли стадия |
| IMP-021 | ✅ закрыта | `Kind.PAYMENT_CONFIRMED` через тот же durable-путь (идемпотентность, guard'ы, lease, uk/ru/en). **Только до появления ТТН:** после отправки клиенту нужен номер, а «оплату отримали» постфактум читается как сбой |
| IMP-050 | ✅ закрыта | `validity=86400` в payload Monobank, `IgDeal.invoice_expires_at`, `invoice_link_state()`. Истёкшая ссылка больше не переиспользуется, старый `invoice_id` уходит в `superseded_invoice_ids` |
| — | **F-UX-015 (новая)** | ✅ Медиа приклеивалось к чужому сообщению; исправлено на построение из транскрипта |
| — | **F-OPS-007 (новая)** | ✅ Быстрый возврат НП по той же ТТН + поле плательщика |
| — | **регресс правки W3** | ✅ `tags_for_client` выбрасывал `discount`, но инструкция на проде размечена `price, discount` и проходила по `price`. Подавление измеряется по итоговому блоку инструкций, а не по имени тега |

**`invoice_link_state` намеренно умеет отвечать `unknown`.** Для ссылки,
выданной до появления TTL, срок неизвестен, и сказать «не знаю» дешевле, чем
угадать неверно в лицо клиенту. `NULL` в поле означает «не знаем», а не «истекла»,
иначе первый же прогон переиздал бы ссылки всем историческим сделкам.

## Что в W4/W4B осталось и почему остановился здесь

На момент этой исторической остановки не было сделано:
**IMP-051, IMP-053, IMP-055, IMP-056, IMP-057, IMP-058.** Текущий статус выше:
IMP-051/053/055/056/057/058 и позднее IMP-089 закрыты на production.

IMP-022/023/024 и IMP-054 закрыты последующими срезами W4. IMP-047–050/052
повторно подтверждены 2026-08-03 фокусным прогоном 47/47 тестов; основной
checklist синхронизирован с этим фактом.

Причины, по каждой группе:

- **IMP-053 (policy-таблица 9 каскадов), IMP-057 (возражения как жизненный цикл:
  модели `IgObjection` + `IgObjectionAttempt`, тег `[OBJHANDLE]`, валидатор
  отпечатков, 12 `BotInstruction`), IMP-058 (статистика падений:
  `IgFunnelStepEvent` на 16 типов событий + `IgFunnelDropOff` + cohort-логика)** —
  это три отдельные подсистемы с новыми моделями и миграциями. Каждая по объёму
  сравнима со всей W3. Делать их «в темпе» — гарантированно получить то, что
  трижды случилось в W3: правильную цель и неверный механизм.
- **Зависимость IMP-058 на IMP-032 уже снята в W6:** FSM и журнал переходов
  опубликованы. IMP-058 закрыта отдельным production-срезом `92d46c5a`;
  фактический runtime-набор содержит 17 типов из-за `payment_confirmed`.
- **IMP-051 (перенос `poll_pending_deals` в тикер демона)** сняла класс отказа
  «cron исчез». Но cron восстановлен в W2 и работает, а TTL ссылки (IMP-050)
  уже даёт факт истечения **в момент выдачи**, не завися от опроса. То есть
  runtime-ценность задачи — независимый backstop и отсечение terminal truth;
  закрыто на production `2a89d860`.

**Историческая рекомендация этого checkpoint была:** начать с IMP-053, затем
IMP-051. IMP-053/051/055/056/057/058 и IMP-089 теперь выполнены; следующий
активный блок указан в верхней сводке.

## Разведка W5 — выводы, которые надо учесть до начала волны

| Пункт | Ловушка, найденная на данных |
|---|---|
| IMP-025 | Версионирование поля `system_prompt` покрывает **11.7%** промпта (3136 из ~26 900 символов). Поле дословно равно константе кода, `settings_saved` — **0 записей**: форму настроек не сохраняли ни разу. Остальные 88% — код и git-версионированный `brand.md`. Ценность есть только для `BotInstruction` (7 записей) и `knowledge_base` |
| IMP-026 | «Свойства ответа» непроверяемы: выход Gemini во всех тестах замокан константой. Исполнимы два других механизма — property-тесты **промпта** (инфраструктура готова, `tests_ig_playbook.py:75-110`) и property-тесты **пост-обработки** |
| IMP-027 | **Уже сделано** коммитом `770872ec`: каталог содержит `фасони/розміри` в 49/49 строк и `variant_id`. «Опора на `resolve_product_sizes`» — **регресс**: он даёт `S..XXL` вместо `classic S..XXXL` + `oversize XS..XXL`. Правильная опора — `resolve_effective_sizes` |
| IMP-027 | IMPR-CAT-002 (ложное наличие) на проде **не существует**: `stock>0` у **0 из 81** варианта |
| IMP-028 | Блок «дорого без скидки» по тегам `price`/`discount` сработает на **вопрос** о цене: `HARD_PRICE_OBJECTION_RE` даёт **0 совпадений на 1113** живых сообщений, а `objection=price` у 27 клиентов — это «скільки коштує» |
| IMP-028 | FAQ через `BotInstruction`: на проде **0 инструкций без тегов**, а 202 из 289 клиентов матчат только инструкцию #1. FAQ обязан быть untagged или `global`/`core`, иначе не дойдёт до 70% |
| IMP-029 | «тип + последнее значение + давность» — **значения нет**: `value` пуст в 149 из 150, `payload` в 150 из 150. Доступно только «тип + давность + confidence» |
| IMP-030 | «Структурированный профиль вместо свободного резюме» — заменять нечего: `memory_summary` есть у **1 клиента из 289**, потому что `maybe_update_memory` вызывается только после успешной отправки бота (20 раз). Плюс `ig_funnel_reset.py:192` обнуляет **весь** `sales_context`, то есть профиль будет терять факты при каждом сбросе воронки |

## F-CAT-001 (P1, НОВАЯ): каталог молча обрезается, 22 товара бот не видит

`bot_catalog` собирает каталог и обрезает его по `MAX_CHARS=16000`. Фактический
размер на проде — **16 118 символов**, то есть в промпт попадают **49 published
товаров из 71**, а 22 бот не видит вообще. Обрезка происходит без записи в лог.

Следствие для W5: любой новый блок в промпте (размерные сетки ~600–900 символов,
блок сигналов, блок возражений) **вытесняет товары**. Прежде чем добавлять
блоки, нужен либо бюджет контекста с приоритетами, либо отбор товаров по
релевантности вместо усечения по длине.

## F-PAT-003 (P1, НОВАЯ): размеры кириллицей не распознаются

Тот же класс, что F-PAT-002. Клиенты пишут размер кириллицей чаще, чем латиницей:

| раскладка | токены |
|---|---|
| латиница | `l` 10, `xl` 10, `s` 9, `m` 8, `xxl` 3, `xs` 3 — **43** |
| кириллица | `м` 23, `с` 15, `л` 4, `хл` 4 — **46** |

`SIZE_TOKEN_RE` содержит только латиницу. **41 сообщение** содержит только
кириллический размер, это **31 клиент**, и у **24 из них `current_size` пуст**.
Все значения `sales_context["size"]` на проде латинские — кириллических нет ни
одного.

Правка не в один регекс: одиночные `s|m|l` сознательно убраны в W3 (F-PAT-001 #2,
«it's ok»), поэтому кириллические одиночные `м`/`с`/`л` нужно принимать только
с контекстом (короткая фраза-ответ или рядом слово «розмір»), иначе вернётся
та же ошибка в другой раскладке.

## Блок A — качество данных классификатора (2026-08-02)

Шесть дефектов, каждый измерен на живой базе.

| Находка | Что было | Что стало |
|---|---|---|
| **F-PAT-003** | Размеры кириллицей не распознавались: 46 токенов «м/с/л/хл» против 43 латинских, 41 сообщение только с кириллицей, 31 клиент, у 24 пустой `current_size` | `extract_size_tokens` + `normalize_size_token`; одиночная кириллическая буква принимается только с контекстом, иначе вернулась бы ошибка «it's ok» в другой раскладке |
| **F-AI-008** | Язык перезаписывался каждым определением: 229 переключений у 99 клиентов из 168 | `_sticky_language` с гистерезисом: смена требует подтверждения вторым определением, первое применяется сразу |
| **IMP-054** | Две несогласованные конфигурации тишины: `bot_followups` 10:00–19:00, `config_versions` 21:00–08:00 | Окно инициации 10:00–21:30 (вечер — самое живое время в IG), аварийное 09:00–22:30 только когда иначе задача умрёт от окна Meta. Реактивный ответ через это не проходит и остаётся 24/7 |
| **F-CAT-001** | Каталог обрезался по символам молча: 16 118 при лимите 16 000 → 22 published товара из 71 не попадали в промпт, последняя строка обрывалась посередине | `truncate_catalog_lines` режет по целым товарам, пишет в лог и добавляет строку «показано N із M» с инструкцией не выдумывать отсутствующее |
| **F-OPS-005** | Событие с ТТН висело в `waiting_window` 53 попытки без верхней границы; клиент #303 оплатил 3428 грн и номер не получил | Эскалация в `MANAGER_REVIEW` после 40 попыток или 12 часов с текстом «надішліть ТТН вручну» |
| **F-STATE-009** | Оплаченный отправленный заказ не двигал стадию: у #303 `stage='new'` | `_advance_stage_from_order` при привязке; `done`-заказ даёт `DONE`, стадия никогда не регрессирует |

## Блок B — W5, механизмы переопределены по данным (2026-08-02)

| Задача | Формулировка плана | Что сделано и почему иначе |
|---|---|---|
| **IMP-025** | Версионировать `system_prompt` с diff и откатом | Поле = 3136 из ~26 900 символов (11.7%), дословно равно константе кода, `settings_saved` — **0 записей**: форму не сохраняли ни разу. Версионируется реально правимый и отсутствующий в git слой: `BotInstruction` и `knowledge_base`. Модель `BotPromptRevision` (append-only, diff, откат), и **сам откат тоже пишется в историю** — иначе журнал утверждал бы, что текущий текст пришёл из последней правки |
| **IMP-026** | Golden-диалоги со свойствами ответа | Выход Gemini во всех тестах замокан константой — проверялась бы наша же строка. Сделаны property-тесты **промпта**: `assemble_system_instruction` вынесена из `gemini_generate`, `build_prompt_snapshot(client)` собирает то же, что уходит в модель, и 9 тестов проверяют присутствие/отсутствие блоков |
| **IMP-029** | Сигналы в промпт: «тип + последнее значение + давность» | **Значения нет**: `value` пуст в 149 из 150 сигналов, `payload` в 150 из 150. Блок `[СИГНАЛИ КЛІЄНТА]` даёт тип и давность; `manager_takeover` (85% всех сигналов) исключён как шум; пустой блок не выводится вовсе, чтобы не занимать бюджет промпта |
| **IMP-029** | Контекст: стадия, язык, размеры, постпродажный статус | Блок `[СТАН ДІАЛОГУ]`: стадия, язык, выбранный размер, «постійний клієнт, покупок: N», открытый сервисный кейс с размером и статусом |
| **IMP-030** | Структурированный профиль **вместо** свободного резюме | Заменять нечего: `memory_summary` есть у **1 клиента из 289**, потому что `maybe_update_memory` вызывается только после успешной отправки бота (20 раз). Профиль сделан узким: половина предложенной схемы дублировала существующие колонки, а дубль — это второй источник истины. Реально новое — **история возражений** (append-only, `primary_objection` было одним перезаписываемым полем). Профиль **переживает сброс воронки**: `reset_funnel` обнулял весь `sales_context`, а названный клиентом размер не перестаёт быть правдой от перезапуска воронки |
| **IMP-027** | Размеры в каталоге | **Уже сделано** коммитом `770872ec`: 49/49 строк каталога содержат `фасони/розміри` и `variant_id`. «Опора на `resolve_product_sizes`» была бы регрессом — он даёт `S..XXL` вместо `classic S..XXXL` + `oversize XS..XXL`. Ничего не менял |
| **IMP-028** | FAQ через `BotInstruction` «ноль кода» | Проверено: на проде **0 инструкций без тегов**, 202 из 289 клиентов матчат только инструкцию #1. Запись FAQ обязана быть untagged или `global`/`core`. Занесено как операционное требование, а не как код |

## W4C закрыта — диалог ведёт модель, а не скрипт (2026-08-02)

Волна не планировалась. Её вызвала прямая жалоба заказчика: бот не выдаёт
ссылки, бесконечно просит размер, отвечает украиноязычному клиенту по-русски и
на вопрос «чому ти відповідаєш російською?» повторяет ту же русскую фразу
дословно. Всё подтверждено на живых переписках прода (клиенты #2 и #5).

| Задача | Находка | Результат |
|---|---|---|
| IMP-063 | **F-CORE-012 (P0, новая)** | ✅ 92% webhook Meta отклонялось: 496 ответов 403 против 44 успешных. Причина — один настроенный секрет из двух. **Вывод W0 «ingress здоров» опровергнут** |
| IMP-064 | **F-AI-014 (P0, новая)** | ✅ Шаблон больше не подменяет ответ Gemini. Подмена попадала в историю как «ответ модели» и самоусиливалась |
| IMP-065 | — | ✅ `ig_checkout_readiness`: факты о готовности заказа идут в промпт **до** генерации, блоком `[СТАН ОФОРМЛЕННЯ]` |
| IMP-066 | **F-PAT-004 (P0, новая)** | ✅ `detect_language` не выдаёт «ru» при неопределённости; прямая просьба о языке перекрывает гистерезис |
| IMP-067 | **F-CAT-002 (P0, новая)** | ✅ Нулевой `stock` перестал означать «нет в наличии»: было 1 из 81, а сайт продаёт все 71 товар |
| IMP-068 | **F-CORE-013 (P1, новая)** | ✅ `[FIT]`/`[SIZE]`/`[QTY]` сохраняются каждым ходом — это и был механизм бесконечного уточнения |
| IMP-069 | **F-CORE-014 (P1, новая)** | ✅ Ссылка клиента на товар читается как выбор; смену подтверждает модель |
| IMP-070 | **F-PAT-005 (P1, новая)** | ✅ Вопрос про сетку не переписывает платёжный выбор фасона |
| IMP-071 | **F-PAY-013 (P1, новая)** | ✅ Купивший однажды снова может купить |
| IMP-072 | — | ✅ «Уточню у менеджера» стало правдой: менеджер получает запрос отсутствующего размера |
| — | **F-OPS-008 (P1, открыта)** | Лог живёт 4 часа: 468 из 500 строк заняты одним повторяющимся отказом |
| — | **F-DATA-015 (P2, открыта)** | Импорт пометил ответы бота как `role=manager` — статистика участия человека завышена |

**Главный урок волны.** Три из четырёх P0 — это не «недоделано», а **регрессы,
внесённые предыдущими исправлениями**:

1. Шаблонные ответы ввёл коммит `c696ee9e` («fix(ig): build assisted checkout
   links from customer intent») за четыре часа до жалобы. До него дефект был
   другим: обещание ссылки висело без URL.
2. Сужение набора секретов до одного пришло с коммитом `e4f3d91a`
   («migrate Instagram bot to Instagram Login»).
3. Гистерезис языка из W3 (F-AI-008) сам по себе корректен, но поверх сломанного
   детектора он стал **консервировать ошибку** вместо стабилизации правильного
   значения — раньше язык хотя бы переключался обратно.

Отсюда правило для следующих волн: правка, которая добавляет в код текст для
клиента или сужает набор принимаемых входных данных, требует проверки на живой
переписке, а не только на тестах. Оба регресса прошли зелёные тесты — потому что
тесты закрепляли именно новое, неверное поведение как ожидаемое.

**Второй урок, про приоритеты.** W0 закрыла вопрос про `bad_signature` выводом
«ingress здоров» на выборке из 11 запросов. На полной выборке access-лога
отношение оказалось 496 к 44. Вывод «здоров» держался почти сутки и всё это
время объяснял симптом «бот не отвечает» качеством промпта, хотя причина была
на пороге. Малая выборка хуже отсутствия выборки: она даёт ложную уверенность.

**Проверка на живых данных (read-only), что модель теперь видит:**
- клиент #2: `бракує: фасон` + «РОЗБІЖНІСТЬ: збережено російська, а клієнт щойно
  писав українська»;
- клиент #5: `бракує: розмір`, ссылка на `classic-tshirt` распознана как другой
  товар с инструкцией поставить `[PRODUCT:1]`;
- валидацию заказа проходят 13 из 15 проверенных опубликованных товаров
  (раньше прошёл бы 1).

**Тесты:** 30 новых, 9 существующих переписаны осознанно. Регрессионный прогон
IG-домена — 635 тестов; список падений совпадает с чистым `origin/main`
(32 предсуществующих, лимит потоков хостинга).

## Деплой W4 + W4C — выполнен и проверен на проде (2026-08-02)

| Что | Значение |
|---|---|
| Коммиты | `305a4748`, `c6339073`, `3191e08c` |
| `origin/main` | `3191e08c` |
| Прод HEAD | `3191e08c` (совпадает) |
| Миграции | `management.0128_ig_ugc_reward` применена |
| Статика | `collectstatic` (991 post-processed), `compress --force` (4 блока) |
| Рестарт | `tmp/restart.txt`, демон перезагрузился (`daemon_reload` → `daemon_start`) |
| Sanity | `/` 200, `/product/classic-tshirt/` 200, `/catalog/` 200, `/admin-panel/` 302, `management.` 302 |

### Инцидент при деплое: миграция упала на FK к MyISAM

`0128_ig_ugc_reward` не применилась с ошибкой
`(1005, "Can't create table … errno: 150 Foreign key constraint is incorrectly formed")`.

Причина не в модели: в этой базе **205 таблиц MyISAM**, включая `auth_user`,
`django_migrations`, `django_content_type`, весь домен `dtf_*` и `accounts_*`.
InnoDB получают только новые таблицы. FK из InnoDB на MyISAM невозможен, а
миграция объявляла `reviewed_by → auth_user` с констрейнтом.

Решение — `db_constraint=False`, то есть ровно то, что в проекте уже сделано для
`RestockSubscription.user`. Это принятый способ, а не обход ради деплоя.

Побочный след: неудачная миграция успела создать таблицу (DDL в MariaDB не
транзакционен) — 0 строк, 5 из 6 FK, при этом в `django_migrations` записи не
было. Перед повторным применением таблица удалена скриптом с тремя
предохранителями: миграция не должна быть отмечена применённой, таблица должна
существовать и содержать ноль строк. Иначе скрипт отказывался работать.

**Вывод для следующих миграций:** новая таблица с FK на `auth_user` или на любую
таблицу из этих 205 в этой базе не создастся. Проверять движок целевой таблицы
до генерации миграции, а не после падения деплоя.

### Что подтверждено на живом продакшене, а не в тестах

1. **Ingress восстановлен.** Прямая проба на `management.twocomms.shop/bot/webhook/`
   с пустым `entry`: оба наших секрета → HTTP 200, чужой секрет → HTTP 403.
   До правки второй секрет давал 403.
2. **Живой трафик подтверждает.** В логе бота дважды появилось
   `webhook_signature_source: підпис підтверджено секретом meta_app` — то есть
   реальные события Meta приходят подписанными родительским секретом, и до
   правки они отклонялись.
3. **Бот ответил клиенту.** `reply_sent → 955313600823130` в 12:38 UTC, после
   рестарта, живой ответ модели (не шаблон).
4. **Каталог полный.** Было 48 товаров из 71 при весе 15 977/16 000; стало
   **71 из 71** при весе 24 518/48 000. Базовые модели `id=1..3`, из-за
   отсутствия которых бот говорил «однотонной черной нет в наличии», теперь
   видны.
5. **Заказы валидируются.** Read-only прогон `validate_checkout_items`:
   13 из 15 проверенных опубликованных товаров проходят (раньше прошёл бы 1),
   остальные два просят уточнить цвет — это вопрос, а не отказ.
6. **Промпт содержит факты.** Для клиента #2 — «бракує: фасон» и
   «РОЗБІЖНІСТЬ: збережено російська, а клієнт щойно писав українська»;
   для клиента #5 — «бракує: розмір» и распознанная ссылка на `classic-tshirt`
   как другой товар.

### Чего проверка не покрывает (честно)

- Ответ модели живому клиенту в проблемном сценарии **не воспроизводился
  специально**: писать реальным людям ради теста нельзя. Проверено то, что
  модель получает правильные факты, и то, что ссылка технически создаётся.
- Доля 403 после деплоя измерена на малой выборке: окно отказов закончилось
  само в 13:46, до рестарта. Прямая проба показывает корректность, но
  наблюдение за реальным потоком нужно повторить через сутки. **Не повторять
  ошибку W0** — не считать малую выборку доказательством.
- Тесты запускались на серверном worktree с SQLite (`--settings=test_settings`).
  Поведение под MariaDB покрыто только фактом применения миграции и read-only
  прогонами на живых данных.

## W4D закрыта — бот замолкал сам на себя (2026-08-02)

Волна не планировалась. Заказчик наблюдал два одинаковых случая подряд: клиент
попросил показать футболки → бот прислал два фото → тишина. У клиента #2 фото
пришли вообще без подписи, и её следующие два сообщения остались без ответа.

| Задача | Находка | Результат |
|---|---|---|
| IMP-073 | **F-CORE-015 (P0, новая)** | ✅ Эхо своих же картинок больше не считается приходом менеджера. Распознавание по `message_id`, а не по тексту: в медиа-echo текста нет. **57 клиентов из 289 (20%) висели в takeover** |
| IMP-074 | **F-CORE-016 (P0, новая)** | ✅ Пауза от менеджера снимается через 12 часов тишины. Раньше только вручную; самый старый takeover — с 19 июня |
| IMP-075 | **F-CORE-017 (P0, новая)** | ✅ Система помнит порядок показанных фото. «Давай першу» стало фактом вместо угадывания |
| IMP-076 | **F-AI-015 (P1, новая)** | ✅ Фото — после уточняющего вопроса и всегда с подписью; «класична/стандартна» = базовая модель с логотипом |
| — | **F-OPS-009 (P1, FIXED / VERIFIED)** | `221cf37d`: завершён alert lifecycle — terminal summary, раздельные lifecycle keys, один actionable alert на failed paylink и единый украинский tone; IMP-077 закрыта |
| — | **F-AI-016 (P1, открыта)** | Инструкции без триггеров: 70% клиентов получают одну инструкцию из семи; половина маппинга тегов — мёртвый код → IMP-078 (W5) |

**Главное в этой волне — цепочка, а не отдельный баг.** Один незамеченный дефект
дал четыре разных симптома, и по каждому симптому в отдельности причина не
находилась:

1. Медиа-echo не распознано → включился `manager_takeover`.
2. Takeover поднял `reply_permission_epoch`, а карусель уходит **до** текста —
   поэтому `customer_send_boundary` отменил отправку уже сгенерированного
   ответа. Клиент получил картинки без подписи, и текст не сохранился нигде.
3. Пауза сделала входящие `observed` — клиент писал дважды и молчание.
4. Отправленные фото не попали в транскрипт, поэтому «давай першу» модель
   могла только угадать — и угадала неверно.

Заказчик описал это как четыре разные проблемы («не те фото», «без подписи»,
«переключило на менеджера непонятно почему», «описал не тот товар»). Причина
одна. Урок: при разборе жалобы стоит сначала искать общее событие в таймлайне, а
не объяснять каждый симптом отдельно.

**Второй урок — про направление fail-safe.** Логика «сомневаемся → считаем, что
это менеджер» выглядела безопасной: не перебивать человека. На практике цена
ложного срабатывания оказалась выше цены пропуска — бот замолкал навсегда, а
снять это можно было только руками. Поэтому решение расщеплено: строка в
транскрипт создаётся всегда (данные терять нельзя), а необратимая остановка
автоматики требует положительного признака «это точно не наше».

**Тесты:** 16 новых, 2 переписаны осознанно. Регрессионный прогон IG-домена —
**747 тестов, 0 падений**.

## Деплой W4D — выполнен и подтверждён на живом трафике (2026-08-02)

| Что | Значение |
|---|---|
| Коммиты | `e4e410bf` (W4D), `98e6d7f7` (падение демона) |
| `origin/main` = прод HEAD | `98e6d7f7` |
| Миграции | `management.0129_ig_outgoing_message_id` применена |
| Рестарт | `tmp/restart.txt`, демон онлайн (`daemon_start`, pid 2203054) |
| Sanity | `/` 200, `/product/classic-tshirt/` 200, `management.` 302 |

### Инцидент при деплое: демон падал на каждом старте

В логе `daemon_spawn` каждую минуту и **ни одного** `daemon_start`. Watchdog
поднимал демона, тот сразу падал с
`CommandError: Instagram commercial backfill collision on deal_id`.
`reconcile_ig_commercial_episodes` вызывается на каждом старте после reload
(`run_instagram_bot.py:245`), поэтому падение было гарантированным.

Коллизии в данных не было. Проверка в `0106_ig_commercial_episodes` требовала,
чтобы при пустом значении компонента поле эпизода тоже было пустым:
`current_value not in {None, value}` при `value=None` сводится к
`current_value not in {None}`. То есть любой эпизод, уже связанный со сделкой,
валил весь прогон, если компонент про сделку не знал.

Ровно такая пара сложилась после W4C: у клиента #5 появился эпизод со сделкой
(ep#4, deal=5, review=3), а все 28 payment review на проде имеют
`deal_id IS NULL` — это уже зафиксировано аудитом как **F-DATA-013**. То есть
дефект существовал давно, а вскрылся, когда бот наконец начал выдавать ссылки.

Проверка приведена в соответствие с блоком записи ниже, который пустые значения
и так игнорирует (`if value and ...`). После правки:
`reconcile_ig_commercial_episodes` → `deals=0, reviews=0, attributions=0`,
демон поднялся.

**Урок:** команда, которая выполняется на каждом старте демона и умеет падать с
`CommandError`, — это единая точка отказа всего бота. Её падение выглядело как
проблема демона, а причина лежала в проверке данных внутри исторической миграции.
Стоит рассмотреть отдельно (в W8): reconcile при старте не должен убивать демона,
достаточно алерта.

### Что подтверждено на живом трафике, а не в тестах

Диалог клиента #2 (`lesiakolt`), 13:36, после деплоя:

1. **Бот ответил текстом и с нумерацией.** Сообщение 2453: «Звісно! Для дівчат у
   нас є дуже класні варіанти: 1) Рожева футболка TWOCOMMS «Reality Bends»:
   Future 2026 — 88…». Раньше в этом же месте приходили две картинки без единого
   слова.
2. **Порядок показанного сохранён:** `shown_products` = позиции 1→103, 2→110,
   3→105. Лог `shown_products 851011504321866: 1=103, 2=110, 3=105`.
3. **Карусель попала в транскрипт как наша:** три строки
   `role=model, source=catalog_media` с заполненным `provider_message_id`
   (2450, 2451, 2452).
4. **Ложного takeover не произошло:** `paused=False`, `takeover=False`, и за
   40 минут после деплоя **ноль** записей `role=manager, source=echo` с
   вложениями. До фикса ровно такая отправка гарантированно давала два ложных
   «сообщения менеджера» и паузу.
5. **Язык держится:** `language=uk` у клиента, который до этого получал русские
   шаблоны.
6. **Ingress:** `webhook_signature_source: підпис підтверджено секретом meta_app`
   — события Meta, подписанные родительским секретом, продолжают приниматься.

### Чего проверка не покрывает

- **57 клиентов всё ещё в `manager_takeover`.** Авто-снятие срабатывает в момент,
  когда клиент напишет снова (`enqueue_inbound`), — сознательно, чтобы не
  «будить» разом 57 спящих диалогов и не создать поток уведомлений менеджеру.
  Клиент #2 уже разблокирован. Проверить убыль этого числа через несколько дней.
- Автоснятие takeover проверено тестами и логикой, но живого случая «менеджер
  молчал 12 часов, клиент написал» пока не наблюдалось.
- Разрешение «давай першу» проверено на данных (`shown_products` заполнен и блок
  промпта собирается), но не на живой реплике клиента с этим текстом.

## Срочный фикс цены варианта IMP-080 — задеплоен (2026-08-02)

| Что | Значение |
|---|---|
| Коммит / `origin/main` / прод HEAD | `8ccac4f9` |
| Миграции | Новых нет; `migrate` → `No migrations to apply` |
| Django / assets | `check` без ошибок; `collectstatic` и `compress --force` завершены |
| Демон | `is_enabled=True`, transport `instagram_login`, DB/cache heartbeat ≈ 1 c |
| Товар 110, «Бойова квіточка» | Точная цена **1450 грн**, только `variant_id=81` «Термо-зелена» |
| Товар 91 | Диапазон **800–950 грн**: classic 800, oversize 950 |

Проверка выполнена через новый `resolve_product_pricing` непосредственно на
production MySQL и через принудительную пересборку `get_catalog_context(force=True)`.
В строке товара 110 агент видит `1450 грн`, `variant_id=81` и причину
«термохромна тканина»; в строке товара 91 — диапазон и цены обоих фасонов.
Клиентам и в Meta тестовые сообщения не отправлялись.

Белая версия товара 110 за 1090 грн не создавалась автоматически: в production
нет соответствующего `ProductColorVariant`, изображений и правил доступности.
Это остаётся открытой задачей данных **F-DATA-016**.

## W7 закрыта и задеплоена — UX админки (2026-08-03)

| Что | Значение |
|---|---|
| Коммит / `origin/main` / production HEAD | `bca7e4e2` |
| Задачи | IMP-035–040 ✅ |
| Миграции | Новых нет; `migrate` → `No migrations to apply` |
| Django / assets | `check` без ошибок; `collectstatic` (991 post-processed), `compress --force` (4 блока) |
| Демон | `is_enabled=True`, transport `instagram_login`, heartbeat 0.6 c, `last_error` пуст |
| Production DB/API | MySQL; 289 `IgClient`; API view `all` — 245 строк, page 1 = 100 строк, `1–100`, 3 страницы |

**Что изменилось:** desktop workspace стал трёхколоночным, контекст остался
доступным drawer'ом на меньшей ширине; опасные действия требуют подтверждения;
ошибки запросов и сохранения KB больше не исчезают; follow-up показывает
относительное/просроченное время; список клиентов пагинирован; статистика имеет
единый период, 12 стабильных строк воронки, определения метрик, доступные табы и
человеческие подписи вместо provider/override-жаргона.

**Проверка:** 159 связанных Django-тестов, `manage.py check`, отсутствие migration
drift, inline-JS parse и `git diff --check`. Browser 390x844 подтвердил видимый
заголовок/close поверх global header, отсутствие horizontal overflow и возврат
фокуса по Escape; 1440x900 — три непересекающиеся колонки 320/568/380 px.
Отдельно найден и закрыт **F-UX-016** — мобильный drawer был заперт в stacking
context ниже глобальной шапки.

## IMP-053 закрыта и задеплоена — policy-каскады W4B (2026-08-03)

| Что | Значение |
|---|---|
| Коммит / `origin/main` / production HEAD | `cd070cba` |
| Policy | 9 сценариев / 25 шагов; time, event и reactive triggers описаны явно |
| Runtime | условия перепроверяются перед отправкой; следующий time-шаг планируется после успешной доставки; terminal sales-сценарии идут в `COLD` через FSM |
| Безопасность | лимит 18 часов и Meta-window не ослаблены; небезопасные шаги становятся видимыми `MANAGER_TASK` |
| Проверка | 15/15 policy-тестов; production MySQL 11.4.12; `manage.py check` без ошибок |
| Демон | `running=True`, transport `instagram_login`, account `17841467101471112`, heartbeat около 1 секунды, notification pending/failed/unknown/dead-letter = 0 |

**На момент закрытия IMP-053 остатком W4B были:** IMP-056
(event trigger + двухфазный claim), IMP-057 (жизненный цикл возражений) и
IMP-058 (cohort/drop-off статистика), а также новый superseded-invoice
backstop IMP-089. Позднее IMP-056/057/058/089 закрыты; W4B завершена.
Реальных сообщений клиентам при production-проверке IMP-053 не отправлялось.

## IMP-051 закрыта и задеплоена — payment backstop в daemon (2026-08-03)

| Что | Значение |
|---|---|
| Code commit / `origin/main` / production | `2a89d860` |
| Runtime | daemon и cron делят mutex/cadence; payment poll работает даже при выключенных автоответах |
| Queryset | pre-order status + authoritative projection; terminal truth/order исключены; batch ≤50 |
| Production MySQL | 3 сделки, 1 invoice с truth `cancelled`; runtime-кандидатов после фикса 0 |
| Проверка | 160/160 связанных тестов, Django check, migration drift, compile и diff check зелёные |
| Демон | `running=True`, `instagram_login`, DB/cache heartbeat 0.4 с |

При проверке IMP-051 был найден **F-PAY-014 / IMP-089**: заменённые invoice ID
восстанавливались через webhook, но не через polling. Позднее IMP-089 закрыла
этот остаток bounded per-invoice lifecycle с terminal marker; см. актуальную
сводку в начале файла.

## Сверка улучшений больше не является неформальным списком (2026-08-03)

На этом историческом checkpoint все существовавшие тогда 48 `IMPR-*` получили
явный `DONE/PARTIAL/OPEN/REFRAMED`, ссылку на каноническую задачу в
`05_IMPROVEMENTS_REGISTER.md` и собственный checkbox в
`07_IMPLEMENTATION_PLAN.md`. Добавлены IMP-090–093 для
model-authored follow-up, retention, операционной приоритизации и аналитического
UX; раньше эти пункты существовали только в тексте улучшений и могли снова
исчезнуть при старте из новой ветки.

Поздняя branch-reconciliation 2026-08-05 добавила `IMPR-FUP-014/015`; текущий
канонический итог равен **51** и отражён в быстрой сводке и матрице `07`.

## IMP-055 закрыта и задеплоена — сбор доставки после оплаты (2026-08-03)

| Что | Значение |
|---|---|
| Code commit | `efc0ee10` |
| Production HEAD после исправления gates | `4ba4212d` |
| Модель / миграция | `IgFollowUpTask.Kind.FULFILLMENT`; `management.0130` применена |
| Runtime | G1 +20 минут, G2 +3 часа, G3 +20 часов; G3 создаёт idempotent Telegram-эскалацию со ссылкой |
| Guards | hidden/spam/takeover/pause/opt-out/service/payment reversal/Meta window сохранены; verified payment и sales frequency limit fulfillment не подавляют |
| Терминалы | заполнение доставки или создание заказа отменяет pending fulfillment; повтор оплаты не переносит G1 |
| Проверка | 98/98 follow-up/order/sales тестов и 44/44 production-contract/payment-review тестов |
| Production MySQL | `qlknpodo_MySQL_DB`; pending fulfillment = 0, потому что оплаченных сделок без доставки сейчас нет; pending payment = 1 |
| Демон | PID 398089, `running=True`, `instagram_login`, DB/cache heartbeat 1.5 с, `last_error` пуст, maintenance отсутствует |

Rollback-contract сначала остановил deploy и тем самым нашёл две независимые
тестовые дыры. Fixture моделировал ещё не доставленные media и не сохранял
digest суммы; после его исправления MariaDB обнаружила 33-символьный
`payment_review_confirmed_telegram` в `varchar(32)`. Коммиты `7c8c0434` и
`4ba4212d` обновили fixture и сократили код до
`payment_review_confirmed_tg`. Оба сбоя записаны как F-TEST-002/003;
дальнейшая стабилизация полного management-suite вынесена в IMP-094.
