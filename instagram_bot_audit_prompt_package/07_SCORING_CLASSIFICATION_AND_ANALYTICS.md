# Скоринг, классификация и точная аналитика

## Не использовать один «процент клиента»

Раздели показатели:

| Показатель | Значение |
|---|---|
| `purchase_probability` | вероятность ближайшей покупки |
| `commercial_intent` | выраженность коммерческого намерения |
| `engagement_quality` | содержательность взаимодействия |
| `satisfaction_score` | довольство опытом/решением |
| `relationship_health` | состояние отношений с брендом |
| `repeat_purchase_potential` | потенциал повторной покупки |
| `service_risk` | риск жалобы/эскалации |
| `decision_friction` | сложность принятия решения |
| `urgency` | срочность |
| `confidence` | уверенность оценки |

Факт покупки — immutable event, а не просто высокий score.

## Кейс обмена/возврата

Если клиент купил, попросил обмен размера, получил решение и благодарен: `has_purchased=true`; conversion не отменяется; `service_case=exchange`; satisfaction может временно снизиться и восстановиться; repeat potential считается отдельно; exchange/refund — отдельные метрики. Нельзя ставить 0% из-за слова «вернуть».

## Explainable event factors

Каждое изменение score хранит metric, before, after, delta, factor, source_event_id, rule_version и confidence. Не считать частоту слова самоцелью. Преобразовывать события в признаки: exact size, delivery data, payment link, price objection, repeated product changes, thanks, refusal, no response, resolved complaint, repeat customer.

## Repeated indecision

Различай нормальное сравнение, отсутствие размера, ожидание денег, покупку для другого, вовлечённость без готовности, возвращение без прогресса и support-only. `repeated_indecision` строится на временном окне, количестве осмысленных циклов и отсутствии progression events.

## Метрики

Определи glossary/source of truth для unique conversations, qualified leads, ad conversations, bot-only, manager-assisted, handoffs, payment links, paid orders, order creator, conversion by source/campaign/creative/product, follow-up, discounts, exchanges/refunds/complaints, repeat purchase, shipment received и UGC/promo.

## Периоды

Today, yesterday, 3d, 7d, 30d/month, custom range. Явно определить timezone и отмечать неполный текущий день.

## Проверка точности

Synthetic fixtures; ручная ground-truth выборка; confusion matrix; precision/recall критичных классов; отдельные тесты exchange/refund/personal/ad; сверка dashboard с raw events; duplicate/late events; versioned metric definitions.

## Рекламный источник

Сохранять доступные source, campaign/adset/ad/creative, referral/post context, prefilled question, first product intent, first/last touch. Если API не даёт поле — не выдумывать; документировать fallback.
