# AI, память, инструкции, продажи и follow-up

## Роли

**Conversation Agent:** формирует ответ, использует разрешённый контекст, возвращает structured output: intent, entities, proposed action, message, confidence. Не меняет критическое состояние напрямую.

**Analysis Agent:** классифицирует, обновляет признаки/память/funnel и предлагает escalation. Не отправляет сообщение напрямую без orchestration rule.

**Deterministic Orchestrator:** владеет transitions, timers, suppression, idempotency и side effects; валидирует AI output; не доверяет модели как факту оплаты/доставки.

## Контекст Gemini

Проверь передачу customer profile, языка, ownership, funnel, открытых заказов, payment link/expiry, товаров/размеров, предыдущих покупок/обменов/возвратов, последних сообщений, summary истории, business rules, разрешённых действий, suppression и ad context. У inferred memory должны быть confidence, source event IDs, updated_at и model version. Проверь, не открывается ли каждый раз пустой новый чат.

## Язык

Отвечать на языке текущего сообщения; не смешивать языки; сохранять названия/адреса; локализовать оплату/ТТН; безопасный fallback; тестировать украинский, русский, английский и дополнительный язык.

## Продажи

Быстро понимать intent; задавать минимум уточнений; не повторять известное; объяснять ценность по возражению; предлагать ясный следующий шаг; не создавать ложный дефицит; не давать скидку преждевременно; уважать отказ; эскалировать сложное менеджеру.

## Follow-up scheduler

Follow-up должен хранить persisted job, reason, due_at, template/version, eligibility snapshot, suppression, attempts/max, last activity, idempotency key, cancel reason и audit trail.

Гипотезы для проверки, а не слепой хардкод: payment link через 25–60 минут; второй контакт через 20–24 часа; финальный через 2–3 дня; «подумаю» через 24 часа и при необходимости 3–7 дней. После отказа не писать; после жалобы/возврата только сервис; после оплаты отменить sales follow-ups. Агент обязан определить финальные интервалы по данным и сроку действия ссылки.

## Скидка 10%

Отдельно различать sales discount и промокод за UGC. Sales discount — только после определения потребности, отработки ценности/альтернатив, подтверждения ценового барьера, проверки отсутствия прежней скидки и лимитов. Логировать решение, использовать ограниченный код и не продолжать спам после безрезультатной скидки.

## Типы переписок

`commerce_new`, `commerce_repeat`, `support_order`, `exchange`, `refund`, `complaint`, `collaboration`, `personal_owner`, `reaction_only`, `spam`, `unknown_needs_review`. Низкая уверенность — уточнение или менеджер, а не неверная sales funnel.
