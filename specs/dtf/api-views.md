# DTF Subdomain — API/Views Spec

## Public routes
- `/` — Landing (DTF)
- `/order` — Форма заказа (tabs: ready/help)
- `/order/thanks` — Спасибо (order/lead)
- `/status` — Статус заказа
- `/requirements` — Требования к файлам + шаблоны
- `/price` — Правила расчета и примеры
- `/delivery-payment` — Доставка/оплата
- `/contacts` — Контакты и реквизиты

## Forms & Validation
**Order (ready)**
- Файл: PDF/PNG (green). Иное → предупреждение, рекомендации перейти в help.
- length_m: обязательна, если не удалось автоопределение.
- copies: min 1, max (настраиваемо). При превышении — флаг requires_review.
- phone: min 10 символов.

**Order (help)**
- Файлы: multiple или ссылка на папку (минимум одно из двух).
- Описание задачи: min 10 символов.

**Lead (FAB)**
- Имя, телефон обязательны.

## Errors
- Дружелюбные, конкретные сообщения.
- Валидация в форме + в UI.

## Acceptance Criteria
- [ ] Все маршруты доступны на dtf субдомене.
- [ ] Форма order валидирует файл/длину/копии/контакты.
- [ ] /status ищет по номеру и телефону.
