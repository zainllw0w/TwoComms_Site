# 10 — Visual Messaging: карточки, карусели, payment, ТТН и combined opt-in

Дата планирования: 2026-08-31

Проверенная quota code-граница: `071a4b5b2f65a91a36443fe98d10a1a322942542`

Режим этого документа: план реализации; он не является доказательством готовности кода.

## 0. Владелец контракта и границы документов

- [04_IMPLEMENTATION.md](04_IMPLEMENTATION.md) владеет порядком реализации, зависимостями и статусами checklist.
- [09_GEMINI_QUOTA_ROUTING_PLAN.md](09_GEMINI_QUOTA_ROUTING_PLAN.md) владеет только Gemini live routing, keys, quota/accounting, fallback и provider-free API observability.
- Этот файл владеет customer-facing visual orchestration: когда нужен текст, quick reply, button template, single card, carousel, payment/ТТН visual и как backend обрабатывает action.
- Analysis/Memory, funnel, business/platform eligibility и commerce policy принадлежат точным разделам `04`; quota/provider правила здесь не дублируются.
- Чекбоксы в `04` и outcomes `09` независимы; красивый preview не равен готовому commerce flow и не закрывает Gemini enforcement.

## 1. Текущая истина и честная граница готовности

### Уже реализовано и доказано на production

- Router V2, event-driven Gemini health, provider-free 4×6 cockpit и accounting shadow.
- Generic Template, Button Template, Quick Replies, text fallback, provider receipt и outgoing echo registry.
- Исправлена коллизия `_quick_reply_payload`, из-за которой исходящие quick replies молча исчезали.
- Versioned `twc:1:*` payload, deterministic preview/parcel postbacks до Gemini.
- Variant-aware catalog media foundation и exact revision checks.
- Production preview `2801–2806`: text, quick replies, button template, single product card, carousel и final selector получили Meta receipts.
- Preview taps проходят как `NO_MODEL` и не меняют purchase, consent, takeover или funnel state.
- Runtime на code-release sample: local/GitHub/server/supervisor SHA совпали;
  restart count `0`, health 200, app-origin browser errors `0`. Chrome smoke
  подтвердил current transport/UI foundation на 360px без horizontal overflow;
  это не закрывает будущий боевой VisualPlan.

### Что preview не доказал

- Нет единого production-path `commerce decision → visual plan → structured delivery`.
- Product/size/payment/TTN cards ещё не управляют реальной воронкой end-to-end.
- Нет scope-aware business consent ledger.
- Нет одного combined consent postback, создающего два auditable topic grants.
- Нет явного 20-hour internal safe deadline рядом с Meta 24-hour deadline.
- `PAYLINK_VIEWED` нельзя доказать нажатием Meta `web_url`.
- Analysis V2, Typed Memory, Assisted Checkout и funnel registry остаются `off`.
- Прежняя funnel migration `0186` остаётся в отдельной NO-GO ветке; после
  Gemini calibration/ranking migration `0186` она обязана получить следующий свободный номер
  и новую dependency, а не cherry-pick старый номер.
- 48-hour soak и два полных Pacific shadow days являются реальными временными gates.

### Почему нельзя использовать старые «90% / 60%» как acceptance

Фактические checkbox-маркеры после scope-сверки:

- `04`: done `341`, open `822`, partial `31`, blocked `18`, declined `10`;
  raw done ratio `341 / 1212 = 28,1%`;
- `09`: ровно девять Gemini provider outcomes — done `8`, open `1`, blocked `0`;
  functional completion `88,9%`.

Поэтому старые оценки «90% / 60%» заменяются evidence-статусами:

1. transport foundation — deployed;
2. customer visual orchestration — open;
3. accounting — shadow only;
4. Analysis/Memory/Checkout — schema deployed, behavior off;
5. funnel registry — NO-GO;
6. final soak — open.

## 2. Зафиксированные решения владельца

1. Интерактивные карточки должны использоваться часто, когда они уменьшают неоднозначность, но не превращать каждую реплику в витрину.
2. Consent UX имеет одну видимую кнопку и не показывает кнопку отказа.
3. Disclosure одной кнопки явно перечисляет оба назначения:
   - ТТН и статусы заказа;
   - бонусы, новинки и персональные предложения.
4. Один tap создаёт два отдельных backend grants:
   - `order_updates`;
   - `bonuses`.
5. Отсутствие кнопки отказа не отменяет withdrawal: `STOP` / `стоп` / `відписатися` и management action должны отзывать consent.
6. Meta открывает стандартное 24-hour окно от provider timestamp входящего postback. `20h` — внутренний safe-send deadline, а не срок Meta.
7. Business consent не даёт право писать вне Meta-window. Closed-window auto-send остаётся запрещён без доказанной provider capability.
8. Payment truth принадлежит provider webhook/reconciliation, не кнопке и не модели.
9. На первой payment card кнопка `Я оплатил` не показывается. При задержке допустима отдельная `Перевірити оплату`, которая только запускает reconciliation.
10. Payment/banner assets могут появиться позднее; отсутствие ассета не блокирует безопасный текст/card fallback.

## 3. Неподвижные архитектурные инварианты

1. Один customer turn создаёт максимум один логический `VisualPlan`.
2. Карусель считается одним visual delivery, а не тремя независимыми сообщениями.
3. Модель может предложить intent/card kind, но не создаёт payload, URL, product ID, сумму, ТТН, discount или consent action.
4. `VisualPlan` строится только из backend authority snapshot.
5. Перед provider I/O повторно проверяются episode, line, revision, availability, price, payment, window и takeover/opt-out.
6. Action payload signed/versioned и связан с exact visual, client, episode/line, revision, expiry и nonce.
7. Известный postback всегда `NO_MODEL`.
8. Двойное нажатие идемпотентно по provider event ID + payload + visual revision.
9. Устаревший tap не меняет state: клиент получает мягкое актуальное состояние.
10. `HTTP 200` без provider message ID и timeout после provider boundary — `UNKNOWN`; blind retry и fallback запрещены.
11. Text fallback разрешён только после определённого template rejection до ambiguous boundary.
12. Essential facts находятся в text/projection, а не только на картинке.
13. Web URL tap, first-party GET и provider payment webhook — разные события.
14. Все transitions append-only либо имеют append-only audit event.
15. Visual orchestration не создаёт вторую commerce/funnel FSM.

## 4. Каноническая цепочка диалога

```text
CustomerTurn
→ routing / media artifact
→ commerce parser + authoritative resolver
→ episode / line / revision snapshot
→ VisualOrchestrator
→ immutable VisualPlan
→ eligibility + immediate revalidation
→ text / quick reply / button template / single card / carousel
→ receipt-backed delivery
→ versioned postback
→ deterministic state transition
→ следующий VisualPlan либо natural text
```

## 5. Матрица «событие → визуал → действие → authority»

| Событие / состояние | Формат | Кнопки / действие | Backend authority | Fallback |
|---|---|---|---|---|
| Приветствие, small talk | Plain text | нет | локальная policy / Ordinary Live | plain text |
| Благодарность, сомнение, жалоба | Эмпатичный plain text | карточка не первая | service/manager state | manager handoff |
| Broad browse без garment | Category carousel | `Футболки`, `Худі`, `Лонгсліви` | category registry | текстовый список |
| Garment уже известен, 0 products | Plain text + relax filters | категория/цвет/крой | resolver result | manager-safe text |
| Ровно 1 product | Single product card | `Обрати`, `Детальніше` | exact product snapshot | text + PDP URL |
| 2–3 products | Product carousel | `Обрати`, `Детальніше` | stable ranked page | numbered text list |
| 4+ products | Page из 3 + `Показати ще` | stable cursor | complete candidate digest | text + catalog URL |
| Product выбран, color/fit неизвестен | Quick replies / compact buttons | одно измерение за ход | sellable variants | natural question |
| 2–3 sizes | Quick replies либо exact card buttons | size | current stock/fit | text choices |
| 4–13 sizes | Quick replies + size-grid link | size / grid | current stock/SizeGrid | полный текстовый список |
| >13 / нужны замеры | Size-grid card | `Допоможіть обрати` | fit-specific SizeGrid | verified measurements text |
| Exact configuration ready | Order summary card | `Продовжити`, `Змінити` | checkout readiness | authoritative text digest |
| Proposal + invoice valid | Payment card | `Сплатити онлайн`, `Змінити` | proposal/generation | text + real paylink |
| Payment pending after return | Compact status card | `Перевірити оплату` | reconciliation | text status |
| Payment confirmed | Thank-you + combined consent button | `Так, отримувати` | provider truth + consent policy | localized disclosure text |
| TTN created | Shipment card | `Відстежити` | Order/IgOrderShipment | text + tracking URL |
| Parcel arrived at branch | Arrival card | `Відстежити`, `Нагадати пізніше` | Nova Poshta truth | text status |
| **Parcel picked up** | Plain text thank-you, затем UGC ask | `нет кнопки подтверждения` | **Nova Poshta status, не клиент** | text only |
| Positive post-delivery reply | UGC/follow card after text | explicit approved actions | UGC policy/manager | text only |
| Complaint / exchange / return | Empathy text, затем button template | exchange/return/help | post-sale FSM | manager handoff |
| Custom print | One branch card, затем text brief | has-art/describe/examples | custom-print subfunnel | natural brief |

### 5.1. Кнопки, которых не должно существовать, и почему

Это не список вкуса, а список кнопок, каждая из которых либо спрашивает то, что
система уже знает, либо не имеет состояния, либо выдаёт автомат.

| Кнопка | Почему её нет |
|---|---|
| `Забрав` / `Ще не отримав` | Факт получения даёт **API Нової Пошти** по ТТН, привязанному к заказу. Backend видит смену статуса и знает о получении раньше, чем клиент успеет нажать. Спрашивать об этом — лишний шаг и прямой сигнал, что отвечает бот |
| `Написати менеджеру` | Клиент **уже пишет** в этот диалог. Кнопка не ускоряет ничего и превращает переписку в меню |
| `Зателефонувати` | В боте нет номера; это handoff в CRM, а не действие клиента |
| `Замовити ще раз` | Чтобы что-то значить, кнопка обязана знать состав прошлого заказа. Сказать «хочу ще одне худі» и дешевле, и естественнее |
| `Скасувати` / `Ні, дякую` | Отказ — это **отсутствие нажатия**. Вторая кнопка не создаёт состояния, зато снижает конверсию. Вместо неё в тексте: «або напишіть, що саме шукаєте» |
| `Оверсайз` / `Не оверсайз` | Все худі сейчас слегка оверсайзные. Выбора нет, значит кнопка ничего не выбирает |
| `Я оплатив` на первой payment card | Claim клиента не является платёжной истиной (§10.9). Появляется только `Перевірити оплату` в pending/recovery |

**Правило для новых кнопок.** Прежде чем добавить, ответить на три вопроса: какое
состояние она меняет; что произойдёт, если её нажать через неделю; и знает ли
система ответ без неё. Если состояние не меняется, если старое нажатие даёт
неверное действие, или если ответ уже есть в БД — кнопки не будет.

### 5.2. Pickup → благодарность → UGC (зачем нужен marketing opt-in)

Это единственный сценарий, который **оправдывает** сбор marketing-consent, поэтому
он описан целиком.

1. Nova Poshta меняет статус ТТН на «отримано». Backend уже опрашивает API, и это
   authoritative event — клиента ни о чём не спрашиваем.
2. Внутри окна (или при активном consent) бот отправляет **текст**, не карточку:
   благодарность за конкретную покупку, названную по факту заказа, а не «за
   замовлення».
3. Затем — просьба отметить магазин в сторис, с конкретной выгодой: **+10% на
   следующий заказ, суммируется с другими скидками**. Формулировка обязана
   называть выгоду и условие, а не «зробіть репост».
4. **Guard, без которого сценарий вредит:** если по заказу открыт case обмена или
   возврата, есть жалоба, или post-delivery reply отрицательный — UGC-просьба
   **не отправляется**, остаётся только благодарность. Просить сторис у человека
   с браком хуже, чем не просить ничего.
5. UGC-reward остаётся отдельным durable фактом; повторная просьба по тому же
   заказу запрещена.

Отсюда и формулировка opt-in: не «дозволяєте надсилати повідомлення», а перечень
того, что клиент получит — ТТН, статус доставки, промокод и скидки. Одна кнопка
`Так, отримувати`, без кнопки отказа (§5.1).

## 6. Candidate cardinality и paging

### Категории

- Если пользователь уже написал «футболки Харькова», category carousel запрещена: показывается product carousel, отфильтрованный по футболкам и Харькову.
- Category carousel нужна только при реально неизвестном garment или прямом запросе «что у вас есть».

### Товары

- `0`: честный текст, какие ограничения не дали результат; 2–3 безопасных способа ослабить фильтр.
- `1`: single card; карусель из одного элемента запрещена.
- `2–3`: одна carousel page.
- `4+`: top 3 + `Показати ще`; Meta limit 10 не является UX-целью.
- Полный ordered candidate digest сохраняется до показа первой страницы.
- `Показати ще` использует stable cursor/page и новую visual revision.
- Нельзя показывать три товара так, будто это весь ассортимент.
- Перед каждым `Обрати` повторно проверяются product status, variant, stock, price и current revision.

### Размеры

- Показываются **только те размеры, которые есть в наличии** для конкретного
  варианта. Кнопка на отсутствующий размер — не удобство, а обещание, которое мы
  не выполним, и клиент узнаёт об этом уже после выбора.
- Классика доходит до шести значений (`XS…2XL`), поэтому размеры идут **quick
  replies**, а не кнопками карточки: кнопок на элемент максимум три, quick replies
  — до тринадцати. Это ограничение провайдера, а не предпочтение.
- Если в наличии один размер — кнопки не нужны совсем: это факт, а не выбор.
- Крой кнопками **не выбирается**: все худі сейчас слегка оверсайзные.
- Заголовок карточки не повторяет то, что уже сказано в диалоге. Если разговор про
  худі, писать «Худі Premium» в заголовке — визуальный шум; достаточно названия
  принта или модели.

## 7. VisualPlan и delivery ledger

### Новый чистый тип `VisualPlan`

```text
kind
policy_version
locale / copy_version
client / episode / line
authority_revision
source_key
correlation_key
candidate_digest / page
cards[] / actions[]
fallback_text
projection_text
expires_at
reason_codes[]
```

### Durable `IgVisualDelivery`

```text
public_id
client / episode / source_message
source_kind / source_key
kind / plan_version / authority_revision
plan_digest / safe plan payload
fallback / projection
state: planned → reserved → provider_started
       → sent | rejected | unknown | fallback_sent | cancelled
provider_message_ids
attempt / boundary / timestamps
transcript_message
```

### `IgVisualInteraction`

Append-only:

```text
visual_delivery
provider_event_id
payload/action
observed_revision
outcome
reason_code
created_at
```

`plan payload` запрещает secrets, raw provider bodies, customer free text и arbitrary URLs.

## 8. Postback V2

Production actions переходят с preview-схемы на opaque signed payload:

```text
twc:2:<visual_public_id>:<action>:<nonce>:<signature>
```

Проверки до mutation:

1. signature и expiry;
2. client/message correlation;
3. provider event dedupe;
4. current episode/line/revision;
5. действие есть в immutable VisualPlan;
6. current product/payment/consent authority;
7. permission epoch, takeover, opt-out;
8. atomic append-only interaction + domain transition.

## 9. Combined consent contract

### Copy

```text
Дякуємо за замовлення 🤍
Надсилати сюди ТТН, статус доставки, бонуси та новинки TwoComms?

[ Так, отримувати ]
```

RU/EN — отдельные exact copy versions. Button label ≤20 symbols.

### Schema

`IgBusinessConsentEvent` append-only:

```text
client / order / episode
bundle_id
topic: order_updates | bonuses
decision: granted | withdrawn
disclosure_version / exact localized copy digest
source visual / interaction / provider timestamp
channel / policy version
evidence message
idempotency key
created_at
```

`IgBusinessConsentState` — current projection per `(client, topic)` with last event.

Один click создаёт в одной transaction два `granted` events с общим `bundle_id`.

### Window

```text
meta_window_deadline = provider inbound timestamp + 24h
safe_send_deadline   = provider inbound timestamp + 20h
```

- Auto marketing/reminder/shipping разрешён только до `safe_send_deadline`.
- Между 20h и 24h разрешён только reactive reply либо отдельно утверждённая policy.
- После 24h — manager task / wait inbound / proven transport capability.
- Consent хранится дольше окна, но не подменяет platform capability.
- Игнорирование CTA означает отсутствие grant.
- STOP отзывает оба topic или выбранный topic и отменяет pending tasks до provider I/O.

## 10. Payment card contract

1. Source: frozen `IgCheckoutProposal` 12h.
2. Stock/promo reservation и provider invoice: 25m, `validity=1500`.
3. Card существует только при `can_issue_link=True`.
4. Отображает exact product/variant/fit/size/color/qty/current price/discount/expiry.
5. `Сплатити онлайн` (uk) / `Оплатить онлайн` (ru) / `Pay online` (en) — только
   allowlisted current provider URL. Кнопка существует именно чтобы клиент не
   видел длинный URL: он видит действие.
6. Meta web button не создаёт `PAYLINK_VIEWED`.
7. First-party signed checkout GET создаёт `PAYLINK_VIEWED` идемпотентно.
8. Provider-reported click, если появится, хранится отдельно.
9. Initial card не содержит `Я оплатил`.
10. `Перевірити оплату` появляется только в pending/recovery context и запускает reconciliation.
11. Customer claim никогда не создаёт order/Purchase/TTN и не снимает stock.
12. Ambiguous invoice не перевыпускается до reconciliation.
13. Late success старого invoice не создаёт duplicate order.
14. Image/banner — presentation only; сумма/expiry/link остаются в text/projection.

## 11. TTN, delivery и reminders

- TTN создаётся только из authoritative shipment event.
- Dedupe: `(order, tracking_number, canonical_status)`.
- Tracking URL allowlisted/versioned.
- Arrival/storage date показывается только из Nova Poshta truth.
- Shipment card не пытается заново получить consent, если оба grants активны.
- Без consent/window delivery event ждёт inbound либо создаёт manager task.
- `Нагадати пізніше` планируется до 20h safe deadline и отменяется при pickup/new inbound/opt-out/takeover/superseding event.
- Уход за товаром — не вторая карточка в тот же turn; это compact text либо следующий уместный turn.
- После delivery первым идёт естественный вопрос; UGC-card — только после positive evidence.

## 12. Card rhythm

1. Никогда не отправлять карточку первым приветствием.
2. Никогда не отвечать карточкой первым сообщением на жалобу, страх или благодарность.
3. Максимум один VisualPlan на customer turn.
4. Следующая карточка допустима сразу только после явного tap в режиме выбора.
5. После двух последовательных selection taps — natural text summary.
6. Смысл и typed alternative присутствуют в text/projection.
7. Card-turn share >50% — guardrail violation, а не успех.
8. Empty/missing asset деградирует до text/card without image, не до выдуманного фото.

## 13. Assets и локализация

**Словарь подписей.** Единственный источник подписей кнопок —
`services/ig_message_templates.BUTTON_LABELS`: каждый ключ содержит `uk`, `ru`
и `en`, fallback на `uk`. Динамически собранных подписей быть не должно: одна
украинская подпись в русском диалоге сразу выдаёт автомат, а длина каждой
подписи проверяется тестом в каждом языке против лимита Meta (20 символов).
Язык берётся из состояния клиента; `uk` основной, `ru` и `en` полноправные.

Добавить registry `IgVisualAsset` либо эквивалентный versioned config:

```text
key / locale / version
image / public immutable URL
alt / aspect / file digest
active_from / retired_at
```

Правила:

- first-party HTTPS only;
- immutable versioned URL;
- exact `uk/ru/en`, затем neutral fallback;
- essential copy не находится только на изображении;
- payment, shipment, arrival, consent, care, custom и UGC assets независимы;
- product cards используют current exact catalog asset;
- asset визуально проверяется в реальном iOS/Android Instagram;
- desktop/web получает достаточный text fallback.

## 14. Dependency-ordered implementation waves

### Wave 0 — Документальная истина

- Обновить handoff `04/09`: quota release `071a4b5b2`, ranking soak baseline
  `2026-08-31T21:40:35+03:00`, deadline `2026-09-02T21:40:35+03:00`.
- Старые SHA оставить только как historical evidence.
- Зафиксировать preview transport proof, не помечая Э1.5–Э1.12 готовыми.
- Исправить Э1.1 под combined CTA / two backend topics.
- Исправить Э1.6: Meta web_url tap не равен `PAYLINK_VIEWED`.
- Добавить эту choreography matrix в Э1; `09` только ссылается на owning visual
  документы и не дублирует choreography.

### Wave 1 — E0.4 eligibility + Visual foundation, behavior off

Файлы:

- новый `management/services/ig_visual_plan.py`;
- новый `management/services/ig_visual_orchestrator.py`;
- новый `management/services/ig_visual_delivery.py`;
- `management/ig_bot_models.py`, migration;
- `ig_message_templates.py`, `instagram_bot.py`, `ig_reply_boundary.py`.

Работа:

- pure outbound eligibility decision с `policy_basis`;
- immutable VisualPlan/ledger;
- receipt/UNKNOWN/fallback lifecycle;
- v2 signed postbacks + idempotency;
- current paths dual-write shadow only.

### Wave 2 — Combined consent

Файлы:

- новый `management/services/ig_business_consent.py`;
- `ig_postback_router.py`;
- `ig_permission_transitions.py`;
- `bot_followups.py`, `ig_lifecycle.py`, `bot_views.py`;
- models/migration/admin timeline.

Работа:

- append-only grants/projection;
- one button/two grants;
- no decline button;
- STOP/withdrawal;
- 20h/24h guards;
- marketing no-send without bonuses grant.

### Wave 3 — Catalog visual orchestration

Файлы:

- `ig_catalog_candidates.py`, `ig_catalog_media.py`;
- `ig_commerce_state.py`, `ig_commerce_replies.py`;
- `instagram_bot.py`, `ig_postback_router.py`;
- `ig_funnel_analytics.py`.

Работа:

- 0/1/2–3/4+ matrix;
- stable pages of 3;
- exact product/variant/fit/size cards;
- current revision revalidation;
- product switch invalidation;
- text/PDP fallback.

### Wave 4 — Checkout/payment visuals

Файлы:

- `ig_checkout.py`;
- `ig_checkout_generation.py`;
- `ig_checkout_payment.py`;
- `ig_checkout_reconciliation.py`;
- `bot_payments.py`;
- first-party checkout views;
- VisualPlan builders.

Работа:

- authoritative payment card;
- first-party view event;
- pending `Перевірити оплату`;
- no customer-claim payment truth;
- proposal/invoice/late/ambiguous contracts.

### Wave 5 — TTN/post-purchase visuals

Файлы:

- `ig_lifecycle.py`;
- `ig_order_fulfillment.py`;
- `ig_checkout_reconciliation.py`;
- `bot_followups.py`;
- `ig_postback_router.py`.

Работа:

- shipment/arrival cards;
- canonical shipment dedupe;
- combined consent eligibility;
- parcel quick replies;
- reminder cancellation;
- post-delivery rhythm.

### Wave 6 — Visual assets/admin/analytics

- Asset registry/admin upload/preview.
- Consent timeline.
- Visual delivery/interaction drilldown.
- rendered/viewed/selected/paid metrics с fixed cohorts.
- Ни один aggregate не перечитывает raw transcript.

### Wave 7 — Accounting enforcement gates

- Исправить analysis graph timeout ownership: one dispatch/frozen candidate,
  rotate project, terminalize every exceptional exit/remainder.
- Reconcile expired unresolved analysis graphs idempotently до enforcement.
- Завершить current 48h soak.
- Получить real request → attempts → reply/receipt trail и p95.
- Накопить два полных Pacific shadow days.
- Enforcement: background → recovery → live 5% → 25% → 100%.
- Routing canary отдельно от accounting.

### Wave 8 — Analysis V2 + Typed Memory

- Correction tombstone сильнее legacy episode backfill; daemon runtime reconcile
  не переписывает newer state/events.
- False purchase correction восстанавливает stage/current episode projection и
  prompt consistency idempotently.
- Legacy memory summary старше current episode/reset подавляется до typed parity.
- Включить materiality selector shadow.
- `no new evidence → no analysis`.
- Analysis proposals → deterministic projector.
- Typed Memory shadow parity.
- Старый `MEMORY_EVERY=8` удалить только после parity.
- Prompt загружает current episode/line facts.
- Persona/recipient/gift facts имеют subject scope/date/evidence и не смешивают
  клиента с получателем/quoted/manager observation.

### Wave 9 — Funnel registry, следующий номер после Gemini `0186`

Сначала rebase старой NO-GO branch на `main`, переименовать её migration в
следующий свободный номер и направить dependency на deployed Gemini calibration/
ranking `0186`.
Старую funnel `0186` не cherry-pick как есть.

До deploy исправить все NO-GO:

1. quoted JSON paths и fail-closed extraction;
2. element-level positive unique evidence IDs;
3. index direction validation;
4. artifact digest current-source validation;
5. reset continuation после 500 rows;
6. opaque/HMAC line и recipient identities;
7. Decimal canonicalization до HMAC;
8. digest no-op query budget;
9. реальный recipient/gift producer либо исключение Phase 1;
10. direct-SQL MariaDB/SQLite regressions.

Только после этого registry становится единственным owner typed funnel transitions.

### Wave 10 — Assisted Checkout/consent/reminders enablement

- Shadow → internal owner account → limited canary → 100%.
- Каждый behavior flag включается отдельно.
- Closed-window send остаётся off без Meta capability.

### Wave 11 — Final closure

- Полная visual/business test matrix `04/10` плюс compatibility с provider
  boundary `09` без изменения его quota policy.
- MariaDB concurrency/kill-resume/InnoDB.
- `uk/ru/en`, iOS/Android/web fallback.
- narrow production owner-account receipts.
- final 48h soak после последнего runtime release.
- exact local/GitHub/server/supervisor SHA.
- Только затем `[x]` и production proof в `04/10`; outcomes `09` меняются только
  provider enforcement/ranking/observability работой.

## 15. Обязательные tests

### Visual/core

- `0/1/2/3/4+/ >10` candidates.
- one VisualPlan/turn.
- signed payload tamper/expiry/client/revision.
- duplicate/stale taps.
- exact media mismatch.
- deterministic rejection fallback.
- timeout/200-without-ID → UNKNOWN/no retry.
- echo registry and one transcript projection.

### Consent/window

- one button creates exactly two grants.
- no decline button in payload.
- duplicate tap creates zero duplicate grants.
- STOP withdraws and cancels tasks.
- `20h < now < 24h` blocks proactive automation.
- web click does not open window.
- postback provider timestamp opens 24h window.
- consent without capability does not allow closed-window send.

### Catalog

- exact category skips category carousel.
- stable top3 paging/no silent truncation.
- unavailable candidate not rendered.
- product switch invalidates dependent facts.
- size list never hides available sizes.
- stale card returns current state, no Gemini.

### Payment

- card blocked until HARD nodes complete.
- exact amount/link/expiry.
- first-party GET only marks viewed.
- customer claim never marks paid.
- duplicate/late/out-of-order webhook.
- ambiguous invoice no reissue.
- one Purchase full order value + paid value.

### Delivery/post-purchase

- TTN only authoritative event.
- tracking/status dedupe.
- unknown storage date omitted.
- remind-later inside safe deadline.
- complaint gets text before card.
- UGC/discount requires manager approval.

### Regression/production

- existing card/parcel/customer-turn/commerce/checkout suites.
- CPython 3.14.6 / Django 6.1.
- migration drift, check, diff check.
- disposable MariaDB.
- no synthetic Gemini probes.
- no broad production crawl.
- owner test account only after explicit authorization.

## 16. Rollback

- Additive schema first; no destructive migration in enablement releases.
- Flags separately control visual core, consent, catalog, payment, shipment and analysis.
- `off` reverts to current text behavior but retains telemetry/audit rows.
- Provider UNKNOWN rows are never deleted or replayed by rollback.
- Consent grants are not erased when feature UI is off; withdrawal remains available.
- Payment/order/TTN truth is never rolled back by disabling cards.

## 17. Честные external/time gates

Нельзя закрыть кодом в текущий момент:

1. 48-hour soak до фактического deadline.
2. Два полных Pacific days shadow accounting.
3. Closed-window auto-send без документированной Meta capability.
4. Visual QA payment banners, пока владелец не предоставил assets.
5. Real traffic p95/CTR/conversion до достаточной выборки.

Эти пункты остаются `[ ]`/`[!]`, а не маскируются процентом.

## 18. Следующий конкретный шаг

1. После выхода из planning mode обновить только docs `04/09` по Wave 0.
2. Не менять checkbox `[x]`, кроме transport/runtime пунктов с уже имеющимся production proof.
3. Начать Wave 1 с RED tests для `VisualPlan`, outbound eligibility, UNKNOWN и signed postback V2.
4. Включать VisualPlan только shadow dual-write до clean MariaDB/integration review.
5. Параллельно продолжать текущий read-only soak; любой новый runtime release сбрасывает его baseline.
