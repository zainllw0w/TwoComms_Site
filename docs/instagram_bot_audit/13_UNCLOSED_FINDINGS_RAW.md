# 13_UNCLOSED_FINDINGS_RAW — полный неранжированный реестр остатка

> Создано: 2026-08-06; повторно сверено 2026-08-10. Это первый из двух
> handoff-файлов: здесь намеренно
> **нет нового порядка работ**. Его задача — сохранить каждую незакрытую
> находку, улучшение, тестовую границу, блокер и source-of-truth конфликт в
> одном месте до приоритизации в 14_IMPLEMENT2.md.

## Как читать статусы

- [ ] OPEN — кода либо доказательства закрытия в current main нет.
- [ ] PARTIAL — часть реализации уже находится в main, но названный остаток
  обязателен; ставить [x] нельзя.
- BLOCKED — выполнение требует внешнего решения, достоверных исходных данных
  или отдельной тестовой инфраструктуры. Это не разрешение придумать данные.
- REFRAMED — старый способ решения отвергнут; нужный результат перенесён в
  другой пункт и не должен дублироваться.
- [x] переносится сюда только как release marker после актуального main и
  production proof; такие строки не входят в незакрытый остаток.

## Снимок, по которому сделана сверка

- Current runtime/code snapshot: Wave 3 releases `7ad632de`/`ade00668` in `origin/main` and
  production; migrations through `management.0154` are applied.
- Fresh production check 2026-08-13: `manage.py check` без ошибок, migrations
  through `management.0154` applied, daemon `running/alive`, dangerous backlog
  and pending reply/notification/analysis queues = 0. Runtime prompt/parser/
  authority probes W1.6 прошли без записи synthetic/customer/provider events.
- Read-only production status показывает 18 terminal failed analysis jobs:
  17 historical `trigger=reconcile` Gemini failures и новый job `292`, client
  `310`, `trigger=manager_message`, `attempts=5`,
  `last_error=stale_lease_retry_exhausted`. Новый случай зарегистрирован как
  `F-AI-018`; это не customer-delivery replay candidate.
- Каждый закрытый code commit из 08_COMPLETION_LOG.md проверен как предок
  current main. В этот реестр не включены завершённые F-*, IMP-* и IMPR-*.
- Незакоммиченная работа, старые worktree и branch-only патчи не являются
  доказательством. Они должны быть перечислены и сохранены до начала нового
  среза, но не дают права ставить `[x]` и не переносятся wholesale.

## Relevant WIP, который нельзя потерять или принять за completion

| Источник | Точное содержимое | Как продолжать |
|---|---|---|
| root worktree | modified `twocomms/management/tests_ig_commerce_state.py` с двумя receipt/reclaim regressions | Не включать автоматически в docs-коммит. Перед переносом сравнить с WIP `IMP-087` и определить владельца каждого теста. |
| `/Users/zainllw0w/.config/superpowers/worktrees/site/ig-commerce-durable-state` | modified `services/ig_commerce_state.py`, `services/instagram_bot.py`, `tests_ig_commerce_state.py`; new `services/ig_commerce_replies.py`, `tests_ig_commerce_delivery.py` | Narrow `IMP-087.A` selectively ported/reviewed into `main` as `7ad632de` plus follow-up `ade00668`; production migration `0154` and runtime proof are in `08/09`. Preserve any remaining root-worktree WIP separately; full `IMP-087` remains PARTIAL. |
| `docs/plans/2026-08-06-ig-commerce-durable-reply-delivery.md` | safety boundary и пошаговый release plan для narrow reply slice | Следовать плану, но заново проверить diff на current `origin/main`, provider receipt semantics и отсутствие price/stock/payment promises. |
| `codex/ig-bot-w4-completion` | old dirty paginator | SUPERSEDED текущим W7; не cherry-pick. |
| `codex/ig-followup-policies` | old-base policy/event WIP | Requirements already reimplemented as `IMP-102/103`; не переносить старую migration/code wholesale. |
| `codex/ig-crm-master-audit` | old-base Meta/ingress/analysis WIP | Только источник требований; live `instagram_login` и current analysis path проверяются заново. |
| `codex/instagram-assisted-checkout` | uncommitted `350px -> 390px` CSS/test breakpoint change | Новый `GAP-CHECKOUT-UX-001`: воспроизвести на current main и browser-test 320/375/390 до решения implement/reject. |
| `codex/management-bot-statistics-visuals` | modified `bot_views.py`, `services/ig_funnel_analytics.py`, `templates/management/bot.html`, `tests_ig_clients_ui.py`, `tests_ig_funnel_analytics.py`; untracked plan and `tests_ig_stats_visuals.py`; volatile tracked diff, inspect with fresh `git diff --stat` | Незакоммиченный code WIP для `IMP-093`, не plan-only. Проверить event-time semantics, review/rebase на current main и сохранить patch-unique tests/UI; не переписывать и не считать shipment. |
| `codex/management-bot-live-visuals` | detached dirty worktree с `AA` planning conflict на older base | Current live-visual code уже в main; сохранить только уникальное planning evidence вручную, не cherry-pick. |
| `codex/instagram-assisted-checkout-pre-split` | historical pre-split ref | Только источник требований для сравнения с current main/assisted-checkout; wholesale cherry-pick запрещён. |
| `codex/ig-lease-docs` | dirty documentation on older checkpoint | SUPERSEDED текущими audit files; не использовать как status authority. |

## Порядок доверия к источникам

1. current main, reachable Git history, код и воспроизводимый тест;
2. production evidence с SHA, соответствующим reachable main;
3. свежие разделы 00_PROGRESS.md и checkbox matrix в 07_IMPLEMENTATION_PLAN.md;
4. подробные причины из 03_FINDINGS_REGISTER.md и
   05_IMPROVEMENTS_REGISTER.md;
5. исторические разделы, старые worktree и старые deployment checkpoints.

Если источник ниже по списку противоречит источнику выше, следующий агент
должен оставить пункт [ ] и записать конфликт в evidence, а не «закрыть по
старому тексту».

### Database boundary, которую нельзя забывать

- Local development использует SQLite и подходит для быстрых unit/regression
  tests. Она не является копией production data и не доказывает MariaDB locks,
  concurrent constraints, max-length, triggers или migration behavior.
- Production использует MariaDB/MySQL `qlknpodo_MySQL_DB` и содержит реальные
  переписки, товары, сделки, платежи и очереди. Для business/data conclusions
  это главный источник истины; проверка до фикса выполняется read-only и с
  минимальным выводом PII.
- Destructive/concurrent acceptance выполняется только на отдельной disposable
  MariaDB schema. Production нельзя использовать как test target, а отсутствие
  локальных SQLite rows нельзя трактовать как отсутствие production flow.

## Полный список носителей реализации IMP-*

Эти 25 пунктов не заменяют находки ниже: они являются work packages, через
которые они должны закрываться.

| Checkbox | ID и статус | Полный остаток и человеческий смысл | Зависимости / запреты |
|---|---|---|---|
| [ ] | IMP-028 — PARTIAL | Завершить сценарные sales playbooks: выбор размера, реактивный обмен, «дорого», «подумаю», нет размера, один вопрос, ненавязчивость, конкретный close, голос продавца и FAQ. (Бот уже не должен фантазировать цену, но пока отвечает непоследовательно в важных продажных сценариях.) | Сначала golden-conversation tests; не путать с уже закрытым versioning prompt. |
| [ ] | IMP-043 — PARTIAL | Показать честное «источник рекламы неизвестен» и разделить bot-only, manager-assisted и manager-created продажи. (Сейчас отчёт способен спутать работу менеджера/бота и заявить нулевую конверсию рекламы при отсутствии данных.) | Parser рекламных полей BLOCKED до ответа владельца о click-to-message рекламе. |
| [ ] | IMP-044 — OPEN, P1 | Включить atomic lease Gemini key в runtime, jitter retry, derived key status и единый allowlist модели; закрыть fresh F-AI-018 typed telemetry/timing failure. | Current lease 180s, management deadline 75s; MariaDB concurrency/reclaim, provider/daemon telemetry, data migration и deployment proof. |
| [ ] | IMP-045 — OPEN | Классифицировать примерно 60 except Exception: pass по доменам. (Настоящие бизнес-сбои не должны исчезать без следа.) | pass допустим только для подписанной telemetry; менять малыми domain commits. |
| [ ] | IMP-046 — OPEN | **046.A рано:** заново проверить current checkout call graph/production rows и выбрать BUILD или migration-backed REMOVE для `F-DATA-001`. **046.B поздно:** после решения удалить только доказанный dead code/UI/data residue. (Current main уже имеет proposal/reservation/TTL/token foundation, поэтому старое «пять пустых таблиц» не является достаточной архитектурной истиной.) | Не удалять IgLifecycleEvent; assignments/live status активны; `log_items`, CSS и entry points удалять только после current call-site/browser proof. |
| [ ] | IMP-061 — OPEN | Убрать только наши diagnostic requests с hub.verify_token из query, маскировать параметр в web-server log где возможно, затем ротировать token. (Meta GET verification protocol остаётся совместимым, но secret не должен оставаться в долгоживущих логах и backup.) | Safe diagnostics без token в URL, log-redaction/rotation proof. |
| [ ] | IMP-081 — PARTIAL | Довести product semantic/inventory foundation до runtime и admin consumer. (Таблицы, policy и triggers есть, но ещё не весь продуктовый путь.) | Нужен isolated disposable MariaDB gate; не тестировать locks на production. |
| [ ] | IMP-082 — PARTIAL | Завершить print/blank/media/canonical-link topology и сделать typed graph источником durable commerce session. (Цена и prompt parity уже безопаснее, но topology неполна.) | После/вместе с IMP-081; не возвращать old W9 branch. |
| [ ] | IMP-083 — PARTIAL | Добавить relaxed alternatives, durable candidate-to-session revision binding и stale revalidation. (Бот не должен дать старый или неподходящий вариант после изменения выбора.) | Typed graph, durable session и no blind alternative after hard mismatch. |
| [ ] | IMP-084 — PARTIAL | Подключить readiness/alternative consumer к exact availability и доказать locks/constraints. (Нельзя обещать товар, если точный color/fit/size не подтверждён.) | Product policy foundation есть; MariaDB contract gate обязателен. |
| [ ] | IMP-085 — PARTIAL | Довести parser до burst ordering, candidate anchoring и полного selection/reply consumer. (Факты из сообщения уже извлекаются, но ещё не полностью управляют безопасным ответом.) | Trusted URL и reducer не должны регрессировать. |
| [ ] | IMP-086 — PARTIAL | Закрыть concurrent MariaDB proof и full manager-review UI для reservation/allocation lifecycle. (Оплаченная последняя единица защищена, но операторский и DB acceptance контур неполны.) | После exact availability; не считать SQLite достаточным. |
| [ ] | IMP-087 — PARTIAL | Подключить candidate reply anchoring с provider receipts, burst reduction, delivery reconciliation и operational manager-review consumer. (Состояние выбора durable; bounded informational 087.A уже использует durable receipt/review boundary.) | Full candidate/payable delivery ждёт remaining F-CORE-004/005 и `088.B`; never blind-resend. |
| [ ] | IMP-088 — PARTIAL | Current main уже имеет deterministic quote/proposal digest и proposal workspace/preview/action API. Остаток: 088.A catalog freshness/read-only audit можно делать рано; 088.B authoritative payable digest обязателен до price/availability/payment reply; затем review UI/backfill/unified MariaDB proof. | Не создавать цикл с IMP-087: full price-bearing 087 delivery зависит от 088.B, а 088.A не ждёт full commerce chain. |
| [ ] | IMP-090 — OPEN | Model-authored proactive follow-up под deterministic policy/opt-out/factual guards и локальным fallback. (Сообщение может стать персональным, но не должно отправляться против правил или исчезать при AI outage.) | Event/claim layer закрыт; после relevant IMP-044 timeout/reliability gate, но независимо от full commerce. Не отправлять без truthful facts. |
| [ ] | IMP-091 — OPEN, decision-gated | Retention: reactivation, two-step review/UGC, loyalty, preorder. (Это затрагивает клиентов и скидки, поэтому без policy нельзя запускать массовые отправки.) | Нужны решения по discounts, preorder и segments. |
| [ ] | IMP-092 — OPEN | Fact-based manager lead priority и честный after-hours mode. (Менеджер должен видеть, кому ответить сначала, а клиент — правду о режиме.) | Сохранить Meta 24-hour window и opt-out. |
| [ ] | IMP-093 — OPEN | Episode sparkline, единый timeline message/payment/TTN/FSM и KPI grouping. Сохранён незакоммиченный code WIP с пятью modified и двумя untracked files; diff volatile, нужен свежий stat и review/rebase. (Админка должна объяснять воронку, деньги и сервис без выдуманных метрик.) | Period metrics считать из immutable/event-time facts, не mutable current `stage`/`lost_reason`; baseline может идти независимо от commerce completion. |
| [ ] | IMP-094 — OPEN | Deterministic deploy gate: cwd-independent suite, clean global state, MariaDB locks/constraints/max-length и immutable release/rollback proof. (SQLite-green и случайно проходящий тест не являются доказательством безопасности деплоя.) | 094.A stable no-network baseline — Wave 0; T40 fixture boundary is GREEN on production MariaDB, while 094.B disposable MariaDB and release provenance remain open. Production is not a concurrent test target. |
| [ ] | IMP-095 — OPEN | Создать реальный белый ProductColorVariant для товара 110, 1090 грн, с фото и fit/size/default rules. (Не выдавать thermo image или выдуманную белую конфигурацию за товар.) | BLOCKED только на authoritative white assets/rules; не зависит от завершения всей commerce chain. Затем отдельный PDP/bot catalog/checkout QA 1090–1450. |
| [ ] | IMP-096 — OPEN | Provenance ролей imported conversation, read-only report и evidence-only dry-run backfill. (Старые bot replies не должны считаться сообщениями менеджера.) | Никогда не менять role по textual similarity. |
| [ ] | IMP-098 — OPEN | Закрыть orphan F-CORE-004/005/006, F-SCORE-010 и остатки F-SEC-004/009. (Это независимые availability, idempotency и PII границы, которым раньше не дали отдельных задач.) | Отдельный regression + production-like proof + deployed SHA на каждый ID. |
| [ ] | IMP-100 — OPEN | Bounded dedupe InstagramBotLog по level/event/detail с count/last-seen в UI. (UI-лог не должен тонуть в дублях, но полный rotating incident log нельзя потерять.) | Migration, MariaDB concurrency/retention test, deploy. |
| [ ] | IMP-101 — OPEN | Убрать account IDs, allowed_senders и debug reply из model defaults в explicit singleton config. (Fresh install не должен наследовать production-like доступ.) | Fresh-settings regression, whitelist warning и production config proof. |

## Все незакрытые и частичные F-* находки

### Core, idempotency и безопасность webhook

- [ ] F-CORE-004 — OPEN: blocking flock в web-thread ограничить LOCK_NB или
  bounded retry не более одной секунды **только для HTTP pause/opt-out
  transitions**; customer-send serialization сохранить. Process acceptance:
  другой процесс удерживает lock, webhook отвечает ≤1 секунды, transition
  durable-recovered ровно один раз и send не обходит permission boundary.
  Evidence: 03_FINDINGS_REGISTER.md:176-194, ig_maintenance.py.
- [ ] F-CORE-005 — OPEN, decision-gated: **сначала** добавить alert с точным
  count доставленных chunks, provider IDs, planned count и полным исходным
  reply text в restricted audit boundary; manager alert redacted. **Отдельно** записать
  security/UX решение, проверять ли epoch только до первого chunk либо
  останавливать send между chunks. (Иначе клиент получает оборванный ответ без
  понятного recovery, а агент самовольно меняет смысл паузы.) Evidence:
  03:196-218.
- [x] F-CORE-006 — FIXED/VERIFIED in bounded Wave 3 slice (`7ad632de`, migration
  `0154`, disposable MariaDB race and production proof): обязательный synthetic
  dedupe key для inbound без
  Meta mid из sender, provider timestamp, normalized text и stable attachment
  identity. Повтор одного event дедуплицируется, но тот же текст позже остаётся
  новым сообщением. Full `IMP-087` delivery remains PARTIAL. Evidence: 03:220-239.

### AI, prompt и Gemini

- [ ] F-AI-003 — OPEN: runtime должен реально acquire/release atomic Gemini
  lease в finally. (Иначе несколько workers одновременно расходуют один key.)
- [ ] F-AI-004 — OPEN: bounded retry jitter. (Иначе синхронные retry усиливают
  429 и provider outage.)
- [ ] F-AI-009 — PARTIAL: очистить оставшиеся противоречия prompt и сделать
  scenario acceptance. (Порядок authority уже добавлен, но старый DB prompt и
  golden conversations отсутствуют.)
- [x] F-AI-010 — FIXED/VERIFIED (`130cd920`): typed JSON controls, immutable
  validation и fail-closed legacy adapter; malformed, unknown, duplicate,
  conflicting, whitespace/zero-width и truncated control tokens не попадают
  клиенту и не создают operational action.
- [x] F-AI-011 — FIXED/VERIFIED (`130cd920`): adversarial worker tests и
  application-evidence gates не дают customer text подтвердить payment, stock,
  consent, order или manager authority; common UA/RU/EN claims и unrelated
  negation проверены отдельно.
- [ ] F-AI-012 — OPEN: adaptive intent-aware context budget. (На простом
  приветствии не нужен большой дорогой prompt.)
- [ ] F-AI-013 — OPEN: единый DB value, allowlist и UI model options. (Админ
  не должен видеть или сохранять модель, которой runtime не может пользоваться.)
- [ ] F-AI-018 — OPEN, P1: свежий `manager_message` analysis job `292` для
  client `310` исчерпал пять stale leases и завершился
  `stale_lease_retry_exhausted` без actionable provider/process telemetry.
  Нужно различать provider call, зависший дольше lease, потерю daemon/worker и
  обычное lease expiry. Current analysis lease = 180 секунд, management deadline
  = 75 секунд; telemetry каждого attempt содержит phase, alias/model,
  start/end, effective deadline и daemon heartbeat. Deadline provider должен
  помещаться внутри lease либо lease должен доказуемо продлеваться. Failed analysis не имеет права менять
  operational episode, payment, order или customer delivery state. Carrier:
  `IMP-044`; production evidence: read-only check 2026-08-07.

### Catalog, context и коммерческая семантика

- [ ] F-CAT-004 — PARTIAL: добавить readiness/alternative consumer и manager
  UI к existing stock-policy foundation; explicitly preserve four WIP-derived
  contracts: quantity-aware VariantSizeRule, is_dropship_available не
  выводится из нулевого stock, реальный shortage создаёт manager/event signal,
  missing_fields сохраняется до следующего уточнения. (Наличие должно быть
  точным не только в data model, и бот не должен выдать «нет» либо «есть» из
  неполного факта.)
- [ ] F-CTX-001 — PARTIAL: adaptive prompt context по текущей задаче. (Bounded
  blocks не равны релевантному контексту.)
- [x] F-CTX-003 — FIXED/VERIFIED (`130cd920`, migrations `0151`/`0152`):
  duplicate saved legacy protocol удалён точечно, runtime использует один JSON
  protocol и добавляет hard-stage guard к существующему custom stored prompt.

### Данные, event contracts и import provenance

- [ ] F-DATA-001 — OPEN: current checkout foundation уже имеет proposal,
  reservation, TTL/token и hosted paths; выполнить fresh production/call-graph
  re-audit и принять BUILD versus migration-backed REMOVE decision.
- [ ] F-DATA-002 — PARTIAL: довести lifecycle event producer/consumer до
  доказанного полного production flow. (Writer уже есть; исходная формулировка
  «нет writer» устарела, но coverage/usage ещё не доказаны.)
- [ ] F-DATA-003 — PARTIAL: безопасная Meta CAPI policy, stable event_id и
  proof. (Не слать маркетинговые события без продуктового контракта.)
- [ ] F-DATA-004 — BLOCKED: получить click-to-message attribution source.
  (В 438 payload нет ad/referral field; parser нельзя выдумывать.)
- [ ] F-DATA-009 — OPEN: отделить manager_observation от sales analytics.
  (Служебный шум не должен быть большей частью продающих snapshots.)
- [ ] F-DATA-010 — OPEN: объяснить пустые commercial episodes и доказать
  episode-to-deal/order lifecycle. (Иначе воронка создаёт пустые циклы.)
- [ ] F-DATA-012 — OPEN: derived current Gemini key state вместо stale
  last_status. (UI не должен вечно показывать старый 429.)
- [ ] F-DATA-015 — OPEN: source-qualified role provenance, read-only report и
  dry-run backfill. (Bot reply не должен увеличивать manager participation.)
- [ ] F-DATA-016 — OPEN: authoritative white 1090 variant товар 110.
  (Это merchandising data, а не подстановка кода.)

### Technical debt, cron и UI debt

- [ ] F-DEBT-001 — OPEN: удалить с migration либо подключить
  InstagramBotProcessedMessage к конкретному dedupe contract. (Сейчас это
  мёртвый заявленный safeguard.)
- [ ] F-DEBT-002 — OPEN: явный policy/permission contract send_text_tagged.
  (Особый send path не должен расходиться с общими guard.)
- [ ] F-DEBT-003 — OPEN: call-graph decision для resolve_gemini_key и
  ensure_instagram_subscription. (Dead entry points создают ложную архитектуру.)
- [ ] F-DEBT-004 — OPEN: убрать silent swallowing кроме documented telemetry.
  (Операционные ошибки должны классифицироваться и наблюдаться.)
- [ ] F-DEBT-006 — PARTIAL (W2.1 local slice): manager-echo queue failure no
  longer leaves partial state; cwd-independent no-network gate is 207/207 with
  0 failures/errors/skips on three documented CWDs. Full management baseline,
  disposable-MariaDB and release parity remain separate.
  (Следующий агент должен отличать свой regression от старого failure.)
- [ ] F-DEBT-007 — OPEN: root-cause flaky telephony test и минимум три
  повторяемых full runs. (Один зелёный прогон не доказательство.)
- [ ] F-OPS-002 — OPEN: удалить, оправдать или дать очередь пустому
  reconcile_ig_checkout cron. (720 пустых запусков в день не являются контролем.)
- [ ] F-UX-011 — OPEN, scope corrected: assignments и provider-aware live status активны;
  остались current call-site audit unused `log_items`, доказанные CSS leftovers
  и реально dead entry points. Старый список не является разрешением blind-delete.

### Payments, score и attribution

- [ ] F-PAY-002 — PARTIAL: reserve/TTL/access/share-token foundation уже есть;
  остаются production reachability, BUILD/REMOVE decision и полный supported
  proposal→checkout→order flow.
- [ ] F-PAY-003 — PARTIAL: current materialization использует
  `ig-deal:{deal.pk}`, но legacy `ig-episode:*` остаётся в manual/order paths;
  нужны compatibility decision и two-deals-in-one-episode regression.
- [ ] F-PAY-006 — PARTIAL: share-token/access foundation уже есть; остаётся
  payer/recipient/order-buyer E2E contract с expiry и manager evidence.
- [ ] F-PAY-008 — OPEN: stable policy-controlled Meta CAPI event id.
  (Атрибуция не должна быть неидемпотентной.)
- [ ] F-SCORE-007 — OPEN: separate satisfaction/service-risk/repeat-potential
  metrics. (Один процент не описывает всю работу с клиентом.)
- [ ] F-SCORE-010 — OPEN: analysis agent не имеет права менять operational
  episode/history без отдельного event contract. (Анализ не должен сдвигать
  funnel watermark.)
- [ ] F-SCORE-012 — OPEN: удалить либо писать пять мёртвых signal types.
  (Аналитика не должна обещать несуществующие показатели.)
- [ ] F-SCORE-014 — PARTIAL: reader/UX для bot-only, manager-assisted и
  manager-created sales. (Источник assignment.Source есть, но отчёт его не
  читает.)

### Privacy, access и test evidence

- [ ] F-SEC-001 — OPEN: safe defaults вместо hardcoded account/debug values.
  (Fresh install не должен молча получить неправильный доступ.)
- [ ] F-SEC-004 — PARTIAL: reviewer PII sandbox/redacted view задеплоен на
  `71498170` (allowlisted status, empty clients/log, stats `403` before queries,
  no stats DOM). Остаток — только намеренно разрешённый и атрибутируемый DR-006
  demo-control плюс общий owner access-policy scope.
- [ ] F-SEC-009 — PARTIAL: DB log и Telegram/operator payload технически
  минимизированы на `71498170`; customer/provider text, receipt media и checkout
  PII больше не уходят в notifications. Открыты owner-controlled retention,
  access/audit policy и итоговый `G-PII` acceptance.
- [ ] F-SEC-010 — OPEN: не использовать token в собственных diagnostic URL,
  маскировать его в web-server access-log где возможно и затем rotate.
  (Meta GET verification protocol совместим; secret не должен жить в наших
  server logs/backup.)
- [ ] F-TEST-002 — OPEN: repeatable deployment gate и disposable MariaDB run.
  SQLite не проверяет реальные locks, constraints и max length. Deploy
  `f327ac36` также повторил `cffi` wheel build failure, который `deploy.sh`
  считает non-fatal; required/optional dependency policy, installed-version/
  lock verification и fail-closed required dependency gate остаются открыты.
  Emergent `F-DEPLOY-001` requires the CI-built `http-ece` wheel SHA in the
  immutable install requirements; `F-DEPLOY-002` forbids selector environment
  JSON in deployment evidence because it exposes production credentials.

## Все незакрытые и частичные IMPR-* улучшения

### Prompt и sales — все зависят от IMP-028 и golden conversations

- [ ] IMPR-SALES-001 — PARTIAL: обязательный size protocol с рекомендацией,
  а не выдача сетки.
- [ ] IMPR-SALES-002 — PARTIAL: reactive-only exchange flow после реальной
  жалобы о размере, без проактивного обещания exchange.
- [ ] IMPR-SALES-003 — PARTIAL: один конкретный contextual upsell и реальная
  multi-item basket, с прекращением после отказа.
- [ ] IMPR-SALES-004 — PARTIAL: «дорого» без неавторизованной скидки, только с
  настоящими alternatives.
- [ ] IMPR-SALES-005 — PARTIAL: «подумаю» — найти blocker, мягко завершить,
  не держать несуществующий stock.
- [ ] IMPR-SALES-006 — PARTIAL: нет размера — тот же товар/цвет, совместимый
  размер, alternative, затем restock queue.
- [ ] IMPR-SALES-007 — PARTIAL: один вопрос на сообщение и progressive discovery.
- [ ] IMPR-SALES-008 — PARTIAL: доказуемая ненавязчивость beyond one CTA limit.
- [ ] IMPR-SALES-009 — PARTIAL: scarcity только из exact availability.
- [ ] IMPR-SALES-010 — PARTIAL: concrete order summary, amount и next step.
- [ ] IMPR-SALES-011 — OPEN: человеческий seller voice вместо канцелярского
  operator tone.
- [ ] IMPR-TXT-006 — OPEN: versioned BotInstruction FAQ для safe delivery,
  tracking и reactive exchange.

### Catalog, inventory, checkout

- [ ] IMPR-CAT-004 — PARTIAL: reliable fit-selector, material и fabric-weight
  facts в bot consumer.
- [ ] IMPR-CAT-006 — OPEN: catalog cache invalidation/split. (Текущий cache
  600 seconds без invalidation может продавать устаревший stock.)
- [ ] IMPR-FEAT-001 — PARTIAL: explainable runtime size recommendation.
- [ ] IMPR-FEAT-002 — OPEN: exact color/fit/size availability.
- [ ] IMPR-FEAT-003 — PARTIAL: durable trustworthy alternative after unavailable
  requested size.
- [ ] IMPR-FEAT-004 — PARTIAL: durable restock subscription from warehouse
  truth, не просто IG event.
- [ ] IMPR-FEAT-005 — PARTIAL: полноценная multi-item basket, не только
  IgDealItem record.
- [ ] IMPR-FEAT-014 — PARTIAL: checkout link от session/configuration truth.
- [ ] IMPR-FEAT-015 — PARTIAL: end-to-end gift/other-payer payment.
- [ ] IMPR-INV-001 — OPEN: inventory как explicit availability source,
  exact allocation и reservation last unit.
- [ ] IMPR-CAT-002 — REFRAMED: прежнее aggregate-stock решение не выполнять;
  результат уже охвачен IMPR-FEAT-002/IMPR-INV-001 и IMP-084/086.

### Follow-up, retention, operations и analytical UX

- [ ] IMPR-FUP-013 — OPEN: model-authored follow-up с deterministic opt-out
  и factual fallback.
- [ ] IMPR-FEAT-008 — OPEN, decision-gated: reactivation бывших покупателей
  без нарушения opt-out/Meta window.
- [ ] IMPR-FEAT-009 — PARTIAL: two-step satisfaction then review/UGC flow.
- [ ] IMPR-FEAT-010 — OPEN, decision-gated: loyalty/repeat-order promotion.
- [ ] IMPR-FEAT-011 — OPEN, decision-gated: preorder unavailable product.
- [ ] IMPR-FEAT-012 — OPEN: fact-based priority queue менеджера.
- [ ] IMPR-FEAT-013 — PARTIAL: honest out-of-hours reply и operational
  continuation.
- [ ] IMPR-OPS-002 — OPEN: bounded repeated UI-log dedupe с count.
- [ ] IMPR-UX-002 — OPEN: current episode score history/sparkline.
- [ ] IMPR-UX-004 — PARTIAL: one timeline message/payment/TTN/FSM, не только
  shipment history.
- [ ] IMPR-UX-005 — PARTIAL: KPI groups funnel/money/service/ads с definitions.
- [ ] GAP-UX-001 — OPEN: state-transition/action feedback и
  loading skeletons list/chat с prefers-reduced-motion. (Не добавлять
  декоративную анимацию вместо понятного состояния.)
- [ ] GAP-CHECKOUT-UX-001 — OPEN: uncommitted assisted-checkout
  breakpoint `350px -> 390px` не имеет current-main browser evidence.
  Воспроизвести на 320/375/390 px; затем либо реализовать scoped CSS/test slice,
  либо записать terminal REJECTED с причиной. Branch-only diff не evidence.

## Незакрытые acceptance/test границы

- [ ] T03 — ad context: BLOCKED до появления real attribution source.
- [ ] T04 — product/size/color/quantity: partial до IMP-082–088.
- [ ] T08 — Pixel/CAPI: нужен live evidence, local contract недостаточен.
- [ ] T20 — received/UGC: two-step automation относится к decision-gated IMP-091.
- [ ] T21 — promo for tag: сохранить manual evidence/staff gate; не
  автоматизировать ради зелёной галочки.
- [ ] T38 — multiple open orders: partial до complete durable commerce session.
- [x] T40 — rollback fixture boundary GREEN on production MariaDB (`c09c4ab97`); full immutable deploy/rollback gate remains IMP-094.
- [ ] T41 — SQLite green недостаточен: disposable MariaDB test database обязателен.
- [ ] T44 — sales semantic/inventory policy: partial до IMP-081 runtime/admin consumer.
- [ ] T45 — price graph/candidates: partial до durable binding и stale protection.
- [ ] T47 — exact availability: partial до MariaDB lock/constraint proof.
T51 current-episode presentation уже GREEN/verified. Он остаётся только
необходимым regression guard: это доказательство presentation truth, а не
незакрытая implementation-задача и не замена W9/MariaDB concurrency contracts.

## Внешние блокеры и жёсткие правила

- [ ] BLOCKER-INFRA-001: provision isolated disposable MariaDB with test
  credentials. Production не использовать для concurrent tests. Блокирует
  DB-sensitive acceptance IMP-044, IMP-081, IMP-084, IMP-086, IMP-088,
  IMP-094, IMP-100 и migration-ветвь IMP-046.B, но не pure/read-only audit,
  parser/cache logic или browser UI.
- [ ] BLOCKER-DATA-001: предоставить authoritative white images, fit/size rules
  и default policy для product 110. Без этого `F-DATA-016`/`IMP-095` не начинать.
- [ ] BLOCKER-POLICY-001: решить, существуют ли click-to-message ads и откуда
  приходит attribution; иначе parser не писать. Блокирует `F-DATA-004`,
  actor/attribution claims `IMP-043`/`T03`; CAPI `F-DATA-003`/`F-PAY-008`/`T08`
  дополнительно требуют отдельной consent/event policy.
- [ ] BLOCKER-POLICY-002: решить policy discounts, preorder, segments и
  reactivation до `IMP-091` и `IMPR-FEAT-008…011`, `T20`, `T21`; никаких mass
  sends заранее.
- RULE-BRANCH-001: не cherry-pick wholesale old W9/follow-up/Meta worktree.
  Брать только требования/тесты, затем reimplement на current main.
- RULE-DATA-001: импортный role/backfill только по provider message ID или
  outgoing registry; текстовое сходство не доказательство.
- RULE-SEND-001: не отправлять synthetic customer/Meta/payment/ad events
  для теста без отдельного разрешения.

## Supplementary management-UI backlog, не входящий в 105 IMP

07_IMPLEMENTATION_PLAN.md отдельно сохраняет 100 visual recommendations. Это
не должно подменять canonical bugs, но незакрытые номера нельзя потерять:

Полные заголовок, priority, rationale, benefit, cost и risk каждого номера
находятся в docs/audits/2026-08-05-management-bot-visual-improvements.md:
1–10 commercial state; 11–20 client list/filtering; 21–30 conversation;
31–40 client context/actions; 41–50 overview/operational metrics; 51–60 live
synchronization; 61–70 animation/micro-interactions; 71–80 accessibility and
responsive UX; 81–90 performance/reliability/security; 91–100 measurement,
rollout and modernization. Перед реализацией любого номера открыть именно его
пункт там; список номеров ниже — статус, а не попытка заменить его критерии.

- [ ] NEXT RELEASE: 2, 3, 4, 8, 12, 14, 15, 16, 17, 20, 22, 23, 25, 27, 30,
  32, 33, 37, 38, 39, 42, 45, 47, 48, 50, 53, 54, 56, 57, 59, 61, 62, 63,
  65, 66, 68, 70, 71, 72, 73, 74, 75, 76, 77, 79, 80, 83, 85, 86, 87, 89,
  90, 96, 97, 98.
- [ ] AFTER BASELINE: 1, 5, 6, 7, 9, 10, 11, 19, 21, 24, 26, 28, 29, 31,
  34, 35, 36, 41, 43, 44, 46, 49, 52, 55, 58, 60, 64, 67, 69, 78, 81, 84,
  88, 91, 92, 93, 94, 95, 99, 100.
- [ ] DEFERRED UNTIL MEASURED: 18, 40, 51, 82 (density/context profiles,
  SSE and virtualization).
- REJECTED: 13; также не возвращать sound alerts, forced auto-open, fake
  countdowns, decorative particles и delivery claims без evidence.

Каждый visual slice требует своего contract, browser matrix и deployment proof;
скриншот либо branch-only код не закрывает его.

## Найденные документные конфликты и их terminal resolution

- [x] DOC-001: stale implementation count находится в историческом
  `11_FINAL_VALIDATION_REPORT.md`, не в current `07`. Current authority:
  105 = 81 DONE + 14 OPEN + 10 PARTIAL; `IMP-088` reclassified PARTIAL because
  current main already has digest/proposal workspace foundations.
- [x] DOC-002: после Wave 3 current matrix содержит 187 finding:
  143 checked + 32 OPEN + 1 BLOCKED + 11 PARTIAL. Исторические counts в `11` не являются
  текущим статусом.
- [x] DOC-003: fresh live check 2026-08-07 подтвердил local/origin/production
  SHA `19f5ef70`; equality больше не выводится из старой записи.
- [x] DOC-004: исторический F-DATA-011 404 incident не реанимирован.
  Его independent new-import hardening `IMP-060` закрыт в W1.7; broader
  `F-AI-018` provider/process/lease telemetry остаётся отдельным `IMP-044`.
- [x] DOC-005: 2877/2897 сохранены только как historical run evidence. До новой
  команды не использовать ни одно число как definitive gate evidence.
- [x] DOC-006: часть заголовков `06_FUNNEL_CLOSING_DESIGN.md` историческая.
  W4B/W6/analytics уже закрыты; актуальные residuals там должны читаться
  через current `00/07/13/14` и Git, а не как новый P0 backlog.
- [x] DOC-007: `F-CAT-004` и `F-DATA-002/003` классифицированы PARTIAL:
  foundations/writers есть, полного production consumer evidence нет. Handoff
  также переклассифицировал `F-PAY-002/003/006` в PARTIAL по current-main
  foundation evidence. Текущий итог после дальнейших закрытий: 32 OPEN +
  1 BLOCKED + 11 PARTIAL.
- [x] DOC-008: `10_OPEN_QUESTIONS_AND_BLOCKERS.md` больше не называет
  `IMP-087` OPEN; narrow receipt-backed WIP и оставшийся полный scope записаны
  как PARTIAL.

## Контроль полноты

- Covered implementation carriers: 24 open/partial IMP tasks.
- Covered canonical findings: 44 unchecked F-* rows after Wave 3 and
  `F-DEPLOY-001…004`. Canonical 07 and this handoff use
  32 OPEN + 1 BLOCKED + 11 PARTIAL.
- Covered improvements: 34 unchecked IMPR-* rows (including one REFRAMED
  duplicate) plus two non-ID gaps: `GAP-UX-001` and
  `GAP-CHECKOUT-UX-001`.
- Included: 11 incomplete acceptance boundaries plus GREEN regression guard
  `T51`, 4 external/policy blockers, 3 standing safety rules, the complete
  supplementary visual backlog and 8 resolved documentation-truth conflicts.

Первичные источники: 00_PROGRESS.md; 01_SYSTEM_MAP.md; 02_AUDIT_CHECKLIST.md;
03_FINDINGS_REGISTER.md; 04_DECISION_LOG.md; 05_DATA_AND_EVENT_CATALOG.md;
05_IMPROVEMENTS_REGISTER.md; 06_FUNNEL_CLOSING_DESIGN.md; 06_TEST_MATRIX.md;
07_IMPLEMENTATION_PLAN.md; 08_COMPLETION_LOG.md; 09_DEPLOYMENT_LOG.md;
10_OPEN_QUESTIONS_AND_BLOCKERS.md; 11_FINAL_VALIDATION_REPORT.md;
12_SOURCE_RECONCILIATION.md; this raw inventory; `14_IMPLEMENT2.md` as the
active prioritized execution plan.
