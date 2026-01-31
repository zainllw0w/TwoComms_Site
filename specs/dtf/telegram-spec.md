# DTF Subdomain — Telegram Notifications Spec

## Events
- new_lead
- new_order
- need_fix (с причиной)
- awaiting_payment (после проверки)
- paid (ручная отметка)
- shipped (с ТТН)

## Payload (пример)
- Тип события, номер заявки/заказа
- Контакты: имя, телефон, канал связи
- Данные заказа: метраж, копии, цена
- Ссылки: /status, /admin (если уместно)

## Failure Handling
- Логи об ошибках отправки.
- Не блокировать основной flow при ошибке Telegram.

## Acceptance Criteria
- [ ] Все события отправляются менеджеру.
- [ ] Ошибки логируются.
