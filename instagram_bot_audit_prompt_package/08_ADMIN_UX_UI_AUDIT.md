# Глубокий desktop-first UX/UI-аудит

## Область

Отдельно аудитировать список переписок, карточку клиента, чат, заказы, привязку user↔order, funnel, follow-up timers, AI analysis/scores, events, Nova Poshta, статистику, настройки, API keys, ownership/pause и alerts/errors.

## Обязательные гипотезы для проверки

- шестерёнка и привязка заказа визуально неразличимы или открывают одинаково понятные панели;
- существующий заказ вводится вручную вместо dropdown;
- funnel не показывает refund, exchange, repeat/additional order и follow-up;
- карточка не показывает timer следующего действия;
- client card и chat расходятся по состояниям;
- clickable/non-clickable элементы не различаются;
- есть overflow, асимметрия и элементы, уходящие вниз;
- статистика не объясняет определения.

Подтвердить или опровергнуть evidence.

## Каждый экран

Проверить цель, visual hierarchy, primary/secondary actions, consistency, labels, icons/tooltips, hit area, keyboard/focus, loading/empty/error/success/disabled, optimistic/stale states, timestamps/timezone, destructive confirmations/undo, responsiveness, contrast, overflow, long/multilingual text, latency feedback, audit trail, links и accessibility.

## Funnel visual

Различать: потребность, товар, данные, ссылка, ожидание оплаты, paid, order, production, ТТН, sent, received, repeat, exchange, refund, complaint, follow-up due, manager takeover, paused, abandoned/closed. Не делать один линейный progress для взаимоисключающих веток; использовать основной lifecycle и side flows/badges.

## Карточка клиента

Показывать язык/source, ownership/pause, current intent, открытые заказы, товары/размеры, next best action, next follow-up timer+reason, payment link, shipment, satisfaction/service risk, scores с факторами, значимые события, notes и personal/collaboration flag. Администратор должен понять состояние и следующий шаг за несколько секунд.

## Статистика

KPI с определениями, funnel counts/rates, bot-only/assisted/manager, source/campaign/product, trends, refunds/exchanges/complaints, follow-up effectiveness, drill-down, freshness, timezone, date filters, zero states и предупреждение о неполных данных.

## Visual polish

Анимации только для подтверждения действия, перехода состояния и загрузки; не замедлять работу; учитывать reduced motion. Красота не подменяет ясность.
