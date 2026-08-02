# Воронки, события, оплаты, Nova Poshta и Meta

## Event catalog

Для каждого события: producer, source of truth, consumer, idempotency key, allowed transitions, retry/DLQ и user message.

Минимум: `instagram.message.received`, `conversation.owner.changed`, `bot.paused`, `lead.intent.updated`, `checkout.link.created/expired`, `payment.succeeded/failed`, `order.created`, `order.linked_to_instagram`, `shipment.ttn_created`, `shipment.status_changed/received`, `order.exchange_requested`, `order.refund_requested/refunded`, `customer.followup_due/cancelled`, `promo.issued`, `meta.purchase.sent`.

## State machines

Разделить `conversation_stage`, `commerce_stage`, `order_lifecycle`, `service_case_stage`, `followup_state`. Определить states, transitions, trigger event, guards, side effects, terminal states, возврат назад и reconciliation. Exchange/refund не должен отменять факт покупки.

## Checkout/payment

Проверить proposal/order reference, товары/размер/цвет/qty, recipient/email/Nova Poshta, promo, подпись ссылки, expiry, защиту цены, повторное открытие, другого плательщика, server callback, exactly-once order creation, reconciliation, локализованное подтверждение оплаты и отмену follow-up.

## Pixel/CAPI

Проверить официальную документацию. Browser/server Purchase дедуплицировать одним `event_id`; согласовать value/currency/content_ids/order_id; server event — после подтверждения; retries не меняют event ID; Test Events; privacy-safe user matching; внутренний заказ не зависит от доставки Meta; refund не стирает факт покупки.

## Nova Poshta

Проверить цепочку: order↔Instagram user; ТТН; event store; Telegram alert; bot job; ownership/pause guard; localized TTN message; canonical status mapping; received; UGC; promo один раз. Не связывать логику с текстовым названием внешнего статуса.

## Instagram labels

По актуальной Meta API документации выяснить, можно ли программно менять нужные labels. Если да — mapping internal state→label, idempotency и logs; label не источник истины. Если нет — документировать ограничение и сделать внутренние labels/fallback в UI.

## Ownership/pause

Перед каждым side effect проверять owner=bot, not paused, conversation active, no complaint/refund suppression, no newer message, no cancelling payment/order event, unused idempotency key. Смена ownership отменяет/замораживает jobs.
