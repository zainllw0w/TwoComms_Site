# Management Instagram Bot Visual System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Превратить management Instagram bot в спокойное, визуально ясное и live-обновляемое рабочее место менеджера, где новый inbound виден сразу, коммерческие статусы не лгут, а статистика читается одним взглядом.

**Architecture:** Сохраняем Django template + vanilla JavaScript и существующие API. Live inbox строится как server-authoritative polling/reconciliation с FLIP-анимацией, статистика — на правдивом расширенном API и лёгких CSS/HTML-диаграммах без тяжёлой chart library, коммерческий цвет — только на разделённых backend-фактах текущей оплаты, исторической покупки и доставки.

**Tech Stack:** Django, Django ORM, HTML/CSS, vanilla JavaScript, existing management APIs, Django TestCase/Client, browser QA, Passenger deployment.

---

## 0. Неподвижные продуктовые правила

- [x] Typing/seen уже выпущен отдельным срезом и не входит в этот цикл.
- [x] Live-перестановка клиентов — Release 1 и первый UI-код этого плана.
- [x] Равная геометрия трех панелей — Release 1.5 и второй крупный UI-релиз.
- [x] Статистика — Release 2 и третий крупный UI-релиз.
- [x] Новый inbound поднимает карточку наверх даже при открытом диалоге.
- [x] Новый inbound никогда не переключает менеджера на другого клиента автоматически.
- [x] Сохраняются выбранный клиент, поиск, фильтр, страница, фокус и scroll-контекст.
- [x] Порядок задаёт backend `-last_message_at, -id`; frontend ничего не выдумывает.
- [x] Цвет означает коммерческий факт, а не предположение модели или красивый декор.
- [x] Исторически завершённая покупка не равна подтверждённой текущей оплате.
- [x] Доставка показывается только из canonical tracking/order facts.
- [x] Анимация допускается, если объясняет изменение, сохраняет пространственную память или сокращает действие.
- [x] Не внедрять sound alerts, particles, постоянную пульсацию, fake countdown, принудительный auto-open, декоративные pie charts и выдуманные time-series.
- [x] После каждого релиза: focused tests → commit → push feature → merge local `main` → push `origin/main` → deploy → SHA/health verification.

## 1. Критерии отбора визуальных решений

Каждое изменение проходит один и тот же фильтр. Если оно не набирает 75/100 либо проваливает правдивость, оно не реализуется.

| Критерий | Вес | Вопрос перед внедрением |
|---|---:|---|
| Скорость решения менеджера | 25 | Быстрее ли понятно, что произошло и что делать? |
| Скорость визуального считывания | 20 | Можно ли понять смысл взглядом без длинного текста? |
| Правдивость | 20 | Есть ли canonical backend fact, timestamp и provenance? |
| Визуальная иерархия | 15 | Стало ли спокойнее, ровнее и яснее? |
| Интерактивность | 10 | Сократилось ли число действий или потеря контекста? |
| Адаптивность | 5 | Работает ли на 320/375/768/1440 px без overflow? |
| Поддержка | 5 | Есть ли тест, fallback и понятный rollback? |

### Запрещающие вопросы

- [ ] Если убрать эффект, теряется ли понимание? Если нет — эффект декоративный и не нужен.
- [ ] Есть ли у числа denominator и период? Если нет — процент не показывать.
- [ ] Есть ли server timestamp? Если нет — не строить countdown или freshness claim.
- [ ] Есть ли подтверждённый payment/order/tracking source? Если нет — не окрашивать как paid/shipped.
- [ ] Уменьшается ли текст за счёт понятного visual encoding? Если нет — не заменять текст случайной иконкой.

## 2. Release 0 — baseline и защита рабочего контекста

**Files:**

- Inspect: `twocomms/management/templates/management/bot.html`
- Inspect: `twocomms/management/bot_views.py`
- Inspect: `twocomms/management/services/bot_payment_truth.py`
- Test inventory: `twocomms/management/tests_bot_api.py` и management bot contract tests

### Checklist

- [x] Работать в `/Users/zainllw0w/.config/superpowers/worktrees/site/codex-management-bot-live-visuals`.
- [x] Ветка `codex/management-bot-live-visuals` отделена от dirty main checkout.
- [x] Зафиксирована актуальная база `90fdd0ec` после синхронизации с `origin/main`.
- [x] Установлено, что текущий client refresh работает раз в 20 секунд только при `!activeId`.
- [x] Установлено, что `load(q)` полностью уничтожает и пересоздаёт список.
- [x] Установлено, что API уже отдаёт `last_message_at` и сортирует по `-last_message_at, -id`.
- [x] Установлено, что conversation incremental polling уже использует `after_id`.
- [ ] Найти точные существующие тестовые классы для clients/stats API и JS contract assertions.
- [ ] Снять baseline screenshots desktop/mobile до Release 1.
- [ ] Выполнить focused baseline tests и записать существующие failures отдельно от новых.

## 3. Release 1 — live inbox с FLIP-перестановкой

**Value:** новый inbound появляется без reload, карточка визуально перемещается в новое место, а менеджер сохраняет открытый диалог и понимает, кто написал последним.

**Recommended approach:** bounded polling существующего clients API + keyed DOM reconciliation + FLIP. SSE/WebSocket отложены: они увеличивают инфраструктуру, но не дают достаточного выигрыша при текущем масштабе и уже существующем polling-контракте.

**Files:**

- Modify: `twocomms/management/templates/management/bot.html`
- Modify if contract needs metadata: `twocomms/management/bot_views.py`
- Test: existing management bot API/template contract test module
- Browser QA: management bot page at 320/375/768/1440 px

### 3.1 RED — API и DOM identity

- [x] Добавить failing test: каждая rendered client row имеет стабильный `data-client-id`.
- [x] Добавить failing test: payload содержит `last_message_at` для каждого клиента.
- [x] Добавить failing test: API order остаётся `-last_message_at, -id`.
- [x] Добавить failing test: search/filter/page parameters сохраняются при background refresh.
- [x] Запустить focused tests и подтвердить ожидаемое падение по отсутствующему keyed reconcile contract.

### 3.2 GREEN — безопасный live polling

- [x] Ввести единое состояние list request: generation id + `AbortController`.
- [x] Отменять устаревший request при новом search/filter/page request.
- [x] Poll только когда видим panel `bot` и `document.visibilityState === 'visible'`.
- [x] Poll выполняется независимо от `activeId`.
- [x] Использовать bounded interval 4–6 секунд без одновременных overlapping requests.
- [x] После network failure сохранить текущий список, не заменять его empty state.
- [x] После двух пропущенных циклов показать компактный stale marker.
- [x] После восстановления показать один короткий reconnect marker и убрать stale state.
- [x] Не менять selected client, filter, q, page и focus target.

### 3.3 RED — reconciliation и пространственная память

- [x] Добавить failing JS/template contract: reconcile keyed по client id, а не `replaceChildren` всего списка.
- [x] Добавить failing contract: selected row сохраняет active class после reorder.
- [x] Добавить failing contract: новый верхний клиент не вызывает `select()`/detail load.
- [x] Добавить failing contract: повторный identical snapshot не создаёт duplicate rows.
- [x] Добавить failing contract: reduced-motion отключает transform transition.
- [x] Подтвердить RED отдельным запуском.

### 3.4 GREEN — FLIP-анимация

- [x] Перед изменением порядка сохранить `getBoundingClientRect()` существующих rows.
- [x] Обновить content существующих nodes in-place и создать только действительно новые nodes.
- [x] Переставить nodes в server order через keyed fragment/reconcile.
- [x] После layout вычислить delta и применить invert transform.
- [x] В следующий animation frame анимировать transform к нулю за 180–220 ms.
- [x] Предыдущая первая карточка плавно опускается, новая/обновлённая поднимается; без drag cursor и без имитации ручного DnD.
- [x] Новая карточка получает короткий `new activity` rail/chip highlight до 900 ms, без полной цветной вспышки.
- [ ] Coalesce несколько изменений в один render frame.
- [x] Для `prefers-reduced-motion` сразу применить новый порядок и оставить только спокойный activity marker.
- [x] Не анимировать initial load, filter switch, search submit и pagination как inbound reorder.
- [x] Сохранять keyboard focus на той же client row; если row ушла из filter result, переводить focus на list heading.

### 3.5 Live conversation coordination

- [x] Оставить существующий `after_id` polling текущего диалога.
- [x] При inbound выбранного клиента обновить его preview/time и поднять row, не пересоздавая transcript.
- [x] При inbound другого клиента поднять его row, но не открывать его conversation.
- [x] При отсутствии selected client не auto-open нового клиента.
- [x] Не скроллить list к top принудительно, если менеджер изучает нижнюю часть; показать компактный `Нові зверху · N` action для явного возврата.
- [x] При нажатии `Нові зверху · N` плавно вернуть list к top и убрать counter.

### 3.6 Release 1 verification and delivery

- [x] Focused Django/API tests pass.
- [x] JavaScript syntax/execution check passes in the real browser with no page errors from the client workspace.
- [x] `python manage.py check` passes.
- [x] `python manage.py makemigrations --check --dry-run` shows no drift.
- [x] `git diff --check` passes.
- [x] Desktop browser: inbound from row 2 moves to row 1 плавно.
- [x] Desktop browser: open row remains selected while another row moves to top.
- [x] Mobile browser: no horizontal overflow and no forced auto-open.
- [x] Reduced-motion browser emulation: order updates without FLIP.
- [ ] Network failure/recovery: list stays usable, stale/reconnect states correct.
- [ ] Commit only Release 1 files.
- [ ] Push `codex/management-bot-live-visuals`.
- [ ] Merge/fast-forward into local `main` without touching unrelated WIP.
- [ ] Push `origin/main`.
- [ ] Server `git pull --ff-only origin main` and run deploy sequence.
- [ ] Verify deployed SHA equals pushed `main` SHA.
- [ ] Verify management bot health/heartbeat and live page assets.

## 4. P0.5 — payment truth and «салат» visual correctness

**Production evidence, 2026-08-05:** найден один matching client: `stage=done`, `purchases_count=0`, `is_buyer=false`; три deals имеют `unpaid/cancelled`, provider projection `cancelled`, заказа и assignment нет. При этом существует manager decision `historical_fulfilled` / `historical_paid_archived`, которое широкая CRM-функция `client_has_confirmed_purchase()` превращает в текущий зелёный state `Оплачено`.

**Decision:** сохранить исторический CRM-факт, но отделить его от текущего payment state. Зелёный `Оплачено` означает текущую подтверждённую оплату/оплаченный связанный заказ; историческая завершённая покупка получает отдельный спокойный buyer-history marker и не окрашивает текущую карточку как paid.

**Files:**

- Modify: `twocomms/management/services/bot_payment_truth.py`
- Modify: `twocomms/management/bot_views.py`
- Modify: `twocomms/management/templates/management/bot.html`
- Test: payment truth service and bot client card tests

### Checklist

- [x] Выполнить read-only production evidence query без synthetic events.
- [x] RED: historical archived review without paid order/provider truth must not produce current `commercial_visual_state=paid`.
- [x] RED: legitimate provider-confirmed payment remains green.
- [x] RED: legitimate manager-verified current payment with source-qualified decision remains green.
- [x] RED: paid linked order remains green.
- [x] RED: historical fulfilled buyer remains discoverable through separate buyer-history payload/marker.
- [x] Implement separate predicates/presentation facts for `current_payment_confirmed` and `historical_purchase_confirmed`.
- [x] Do not mutate production rows automatically; correct presentation semantics first.
- [x] Add concise evidence tooltip/popover naming `provider`, `manager`, `paid order` or `historical archive`.
- [x] Re-run focused tests and payment inconsistency report read-only.
- [x] Browser QA exact «салат» state with production-like fixture.
- [x] Commit, push feature, merge main, push main, deploy and verify SHA/heartbeat (`6e03980a`).

## 4.5 Release 1.5 — равная высота трех рабочих панелей

**Value:** список клиентов, переписка и контекст образуют один ясно ограниченный рабочий холст. Сотни клиентов и длинные настройки больше не растягивают страницу, а история сообщений использует всю доступную высоту средней панели.

**Recommended approach:** один desktop height contract на контейнере workspace, внутренние flex/grid scroll regions и сохранение текущего responsive drawer на ширинах до 1200 px. Высота задается через `clamp()` и `100dvh`, но имеет устойчивый минимум; на мобильных возвращается естественный document flow без вложенного вертикального scroll trap.

**Files:**

- Modify: `twocomms/management/templates/management/bot.html`
- Modify: `twocomms/management/tests_ig_clients_ui.py`
- Browser QA: clients workspace at 1440, 768 and 375 px

### 4.5.1 RED — geometry contracts

- [x] Add failing template contract for one bounded desktop workspace height.
- [x] Add failing contract: sidebar, conversation and context shell inherit exactly `height:100%` with `min-height:0`.
- [x] Add failing contract: client list owns its vertical scroll while search, filters, live status and pager remain stable.
- [x] Add failing contract: conversation is a flex column and message history is `flex:1 1 auto; min-height:0; overflow-y:auto`.
- [x] Add failing contract: context drawer body is the only scrolling region inside the right pane.
- [x] Add failing contract: closed context uses a smooth two-column reflow and the context shell is removed from layout.
- [x] Add failing responsive contract: tablet/mobile use natural height and avoid nested vertical scrolling.

### 4.5.2 GREEN — bounded desktop workspace

- [x] Set one desktop height on `.bot-clients-workspace`, approximately `clamp(620px, calc(100dvh - stable chrome offset), 760px)`.
- [x] Give all three direct panes `height:100%; min-height:0; align-self:stretch` and one shared border/radius treatment.
- [x] Remove competing sticky/min-height rules that create different bottoms.
- [x] Keep the page itself stable while list, messages and context content scroll internally.
- [x] Preserve pager visibility at the bottom of the client pane.
- [x] Make `.bot-client-pane-empty` fill its pane without changing geometry.

### 4.5.3 Conversation fill and settings toggle

- [x] Make `.bot-client-conversation` a flex column.
- [x] Keep header, commercial summary, linked order and role legend content-sized.
- [x] Let `.bot-conversation-messages` consume every remaining pixel and scroll internally.
- [x] Keep the gear as a true open/close toggle with correct `aria-expanded`.
- [x] On desktop close, hide the context column and animate grid tracks/opacity without a layout jump.
- [x] On reopen, restore the same top/bottom boundary and the prior context scroll position where practical.

### 4.5.4 Responsive behavior

- [x] 1440 px: three visible panes have identical top, bottom and measured height.
- [x] 768 px: list/conversation mobile tabs use natural page flow; context remains an overlay drawer.
- [x] 375 px: no horizontal overflow, no nested scroll trap and conversation remains readable.
- [x] Reduced motion removes nonessential grid/opacity transition.

### 4.5.5 Verification and delivery

- [x] Focused template/UI tests pass.
- [x] Programmatic browser measurements confirm equal desktop pane heights within 1 px.
- [x] Programmatic browser measurements confirm message history fills the remaining conversation height and has positive scroll capacity for long content.
- [x] Screenshots saved for 1440, 768 and 375 px with context open and desktop context closed.
- [x] No page-level horizontal overflow at any required viewport.
- [ ] Commit, push feature, merge local `main`, push `origin/main`, deploy and verify SHA/heartbeat.

## 5. Release 2 — визуальная статистика без выдуманных данных

**Value:** менеджер одним взглядом видит объём, качество, verified conversion и узкое место, а подробные таблицы остаются доступными по раскрытию.

**Recommended approach:** расширить существующий stats API additive fields и отрисовать semantic HTML/CSS bars. Не подключать тяжёлую chart library: horizontal bars, proportional funnel и compact KPI дают лучший контроль плотности и адаптивности.

**Files:**

- Modify: `twocomms/management/bot_views.py`
- Modify: `twocomms/management/templates/management/bot.html`
- Test: stats API tests and period/timezone contracts
- Browser QA: stats panel desktop/tablet/mobile

### 5.1 RED — truthful stats API

- [ ] Test `generated_at` and `schema_version`.
- [ ] Test `totals.messages`, `inbound_messages`, `bot_replies`, `manager_messages`.
- [ ] Test `unique_conversations` uses distinct clients in selected period.
- [ ] Test `paid` uses verified/current payment truth, not stage alone and not historical archive alone.
- [ ] Test `qualified` definition and denominator.
- [ ] Test `lost_or_refused` definition from canonical stage/reason/analysis categories.
- [ ] Test custom date range timezone boundaries.
- [ ] Test zero/empty dataset returns zeros/arrays, never invented deltas.
- [ ] Confirm existing API fields remain backwards compatible.

### 5.2 GREEN — stats API contract

- [ ] Add additive totals without deleting current funnel/interactions/products/ads/meta data.
- [ ] Return period label and exact UTC/local boundary metadata.
- [ ] Keep revenue separate from counts.
- [ ] Cap ranked lists server-side only where full list remains available in disclosure payload.
- [ ] Avoid N+1 queries; record focused query-count ceiling where practical.

### 5.3 Visual hierarchy

- [ ] Replace 11 equal KPI boxes with four primary KPI cards: `Повідомлення`, `Діалоги`, `Підтверджені оплати`, `Відмови / втрати`.
- [ ] Each KPI has icon, number, short label and focus/click definition tooltip; no permanent paragraph.
- [ ] Show `Оновлено …` from server `generated_at`, not browser guess.
- [ ] Secondary metrics live in one compact expandable strip.
- [ ] Use tabular numbers and consistent card heights.
- [ ] Animate only changed values with 120 ms crossfade; no count-up theatre.

### 5.4 Funnel and charts

- [ ] Add proportional horizontal funnel: conversations → qualified → product → checkout/payment → verified paid.
- [ ] Widths normalize to the first stage; exact count and percent remain visible/focusable.
- [ ] Zero stages render an honest empty rail, not a misleading minimum bar.
- [ ] Add compact horizontal bars for conversation categories.
- [ ] Add compact ranked product bars with top values first.
- [ ] Add ads visual with separate columns/bars for chats, paid and revenue; top 5 first, remaining in disclosure.
- [ ] Keep cohort/drop-off/time-on-step/manager-vs-bot/discount tables inside `Детальні дані` disclosure.
- [ ] Hide empty analytical sections instead of rendering repeated empty cards.
- [ ] Add clear empty state describing selected period, not generic `Немає даних`.

### 5.5 Responsive and interaction

- [ ] 1440 px: balanced 4-column KPI row and 2-column chart area.
- [ ] 768 px: 2-column KPI row and single-column charts.
- [ ] 375/320 px: horizontally stable single-column cards, labels wrap without clipping.
- [ ] Tooltips open on hover/focus desktop and tap mobile; Escape returns focus.
- [ ] Date range controls collapse into compact disclosure on narrow screens.
- [ ] Loading uses stable skeleton geometry; error keeps previous successful data with retry action.
- [ ] No chart depends on color alone; labels and values stay visible for ordinary visual reading.

### 5.6 Release 2 verification and delivery

- [ ] Stats API focused tests pass.
- [ ] Zero/one/many data fixtures pass.
- [ ] Timezone and custom range tests pass.
- [ ] Browser screenshot matrix 320/375/768/1440 passes.
- [ ] No horizontal overflow or clipped labels.
- [ ] Definition tooltips and disclosures work by keyboard and touch.
- [ ] Commit, push feature, merge main, push main, deploy.
- [ ] Verify server SHA, health, static asset hash and live stats response shape.

## 6. Release 3 — conversation focus improvements

- [ ] Append new messages through existing `after_id`, never rebuild transcript.
- [ ] Add session-local `Нові повідомлення` divider without pretending server unread truth.
- [ ] Show `До останнього` only when manager is away from bottom.
- [ ] Preserve scroll anchor while loading older history.
- [ ] Add date separators only on date change.
- [ ] Group adjacent same-role messages visually while retaining timestamps.
- [ ] Show active takeover in header as one concise operational state.
- [ ] Add copy actions for TTN/provider message id with short feedback.
- [ ] Test long transcript, focus, scroll, mobile one-column and reduced-motion.
- [ ] Commit/push/merge/deploy as separate release.

## 7. Release 4 — commercial evidence and delivery lifecycle

- [ ] Add click/focus evidence popover: source, amount, order id, verifier time.
- [ ] Never expose tokens, raw webhook payloads or unnecessary PII.
- [ ] Delivery line uses canonical statuses only: not shipped, shipped, in transit, branch, received, unverified.
- [ ] TTN alone never implies movement.
- [ ] Empty delivery/history sections do not render.
- [ ] Show one next action only when API explicitly supports it.
- [ ] Payment timer exists only with real `expires_at`.
- [ ] Use subtle rail/chip transitions for real fact changes.
- [ ] Test paid/shipped/pending/refunded/reversed/unknown presentation matrix.
- [ ] Commit/push/merge/deploy as separate release.

## 8. Release 5 — filters, context and control ergonomics

- [ ] Keep primary filters minimal; move rare filters into one disclosure.
- [ ] Add counts only where they help prioritization.
- [ ] Show active filter chips with one-click clear.
- [ ] Add server-authoritative sorting: recent, needs action, payment, delivery.
- [ ] Preserve q/filter/page/client in URL deep-link without weakening auth.
- [ ] Keep settings gear as true toggle with width transition and responsive reflow.
- [ ] When settings closes, list and conversation columns expand symmetrically.
- [ ] Normalize three-column heights/min-widths and prevent internal overflow.
- [ ] Keep user action buttons in symmetric primary/secondary grid.
- [ ] Disabled action explains why on focus/tap.
- [ ] POST actions keep stable width, bounded busy state and recoverable error.
- [ ] Touch target minimum 44 px for actionable controls.
- [ ] Commit/push/merge/deploy as independent cohesive slices, not one mega-commit.

## 9. Release 6 — overview cleanup and final visual modernization

- [ ] Remove `Як працює` permanently from Overview.
- [ ] Re-audit cards for equal rhythm, padding, line length and empty states.
- [ ] Replace explanatory paragraphs with concise label + icon + on-demand help only where comprehension improves.
- [ ] Remove duplicate headings and repeated status text.
- [ ] Ensure meaningful state is visible in first viewport without card overload.
- [ ] Add only functional micro-interactions: drawer transition, disclosure transition, saved feedback, live state transition.
- [ ] No visual effect without an observable state change.
- [ ] Final screenshot comparison against original four supplied screenshots.
- [ ] Final browser matrix and operational workflow walkthrough.
- [ ] Final commit/push/merge/deploy and deployed SHA record.

## 10. 100-recommendation decision ledger

The detailed 100-item reasoning remains in:

- `docs/audits/2026-08-05-management-bot-visual-improvements.md`
- `docs/plans/2026-08-05-management-bot-visual-refinement-design.md`
- `docs/plans/2026-08-05-management-bot-visual-refinement.md`

### Implement in this cycle

- [ ] Live keyed refresh, FLIP reorder, activity marker, stale/reconnect state.
- [ ] Selected-client preservation and live transcript/list coordination.
- [ ] Current payment vs historical buyer semantics.
- [ ] Commercial evidence and truthful delivery lifecycle.
- [ ] Compact primary statistics and proportional funnel.
- [ ] Ranked category/product/ad visuals.
- [ ] On-demand analytical detail.
- [ ] Compact filters, symmetric controls and responsive settings drawer.
- [ ] Focus, keyboard, touch and reduced-motion behavior.
- [ ] Stable loading/error/empty states.

### Implement only after baseline evidence

- [ ] Saved filter presets.
- [ ] Manager presence indicators.
- [ ] Density profiles.
- [ ] UI telemetry without PII.
- [ ] Virtualized client list.
- [ ] SSE/WebSocket transport.

### Explicitly reject

- [x] Sound alerts without a separate operator opt-in study.
- [x] Auto-opening whichever client wrote last.
- [x] Fake timers and fake freshness.
- [x] Decorative particles, glowing gradients and permanent pulse.
- [x] Pie/donut charts when bars communicate ranking better.
- [x] Hidden global command palette for primary operations.
- [x] Delivery status inferred from TTN or message text alone.
- [x] Color-only commercial semantics.

## 11. Universal release gate

Before every commit:

- [ ] A failing test was observed before production implementation.
- [ ] Focused tests pass after implementation.
- [ ] Adjacent management bot tests pass.
- [ ] JavaScript syntax check passes.
- [ ] `python manage.py check` passes.
- [ ] Migration drift check passes.
- [ ] `git diff --check` passes.
- [ ] No unrelated dirty files are staged.
- [ ] Browser QA covers the changed interaction.

Before every deploy:

- [ ] Feature branch pushed successfully.
- [ ] Exact release commit integrated into local `main` safely.
- [ ] `origin/main` contains the release commit.
- [ ] Server pull is fast-forward only.
- [ ] Migrations/check/collectstatic/compress complete successfully when applicable.
- [ ] Passenger restart and bot daemon ensure complete.
- [ ] Server HEAD equals pushed main SHA.
- [ ] Heartbeat/health is fresh.
- [ ] No synthetic customer, Meta, payment or ad events were sent.

## 12. Final definition of done

- [ ] Release 1 live reorder works with selected and unselected clients.
- [ ] «Салат» no longer appears currently paid without current payment truth.
- [ ] Statistics communicate messages, conversations, qualification, verified payments and losses at a glance.
- [ ] Detailed analytics remain available without dominating the first viewport.
- [ ] Commercial colors and shipment states have visible factual provenance.
- [ ] Settings, filters, action controls and three-column layout are symmetrical and responsive.
- [ ] All chosen visual effects explain state change or preserve context.
- [ ] Original problem screenshots have explicit before/after validation.
- [ ] Every shipped slice is present in feature history, local main, origin/main and production.
- [ ] Final deployed SHA and residual intentionally deferred items are documented.
