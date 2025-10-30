# Реализация Monobank Invoice для prepay_200 и online_full

## Проблема
Функция `monobank_create_invoice` отсутствует, что приводит к ошибке 500 при попытке оплаты.

## Решение

Создать функцию которая:
1. Получает данные из POST (full_name, phone, city, np_office, pay_type)
2. Создает заказ с товарами из корзины
3. В зависимости от pay_type создает MonoPay инвойс:
   - **prepay_200**: инвойс на 200 грн, payment_status='prepaid' при успехе → Lead событие
   - **online_full**: инвойс на полную сумму, payment_status='paid' при успехе → Purchase событие

## Логика работы

### prepay_200 (Предоплата 200 грн)
1. Пользователь выбирает "Передплата 200 грн" в корзине
2. Нажимает кнопку "Внести передплату 200 грн"
3. POST → `/cart/monobank/create-invoice/` с `pay_type=prepay_200`
4. Backend создает Order с `total_sum` = полная сумма товаров, `pay_type='prepay_200'`
5. Создает MonoPay инвойс на **200 грн**
6. После успешной оплаты через webhook:
   - `payment_status` = 'prepaid'
   - Facebook Pixel/Conversions API → Lead событие
7. Товар отправляется, клиент получает
8. Nova Poshta автоматически обновляет `payment_status` = 'paid'
9. Facebook Conversions API → Purchase событие

### online_full (Полная оплата)
1. Пользователь выбирает "Онлайн оплата (повна сума)"
2. Нажимает кнопку "Перейти до оплати"
3. POST → `/cart/monobank/create-invoice/` с `pay_type=online_full`
4. Backend создает Order с `total_sum` = полная сумма, `pay_type='online_full'`
5. Создает MonoPay инвойс на **полную сумму**
6. После успешной оплаты через webhook:
   - `payment_status` = 'paid'
   - Facebook Pixel/Conversions API → Purchase событие

## Файлы для изменения

### 1. `twocomms/storefront/views/monobank.py`
Добавить:
- `class MonobankAPIError(Exception)`
- `def _monobank_api_request(method, endpoint, json_payload=None)`
- `def monobank_create_invoice(request)`

### 2. `twocomms/storefront/views/__init__.py`
Добавить импорт:
```python
from .monobank import (
    monobank_create_invoice,
    monobank_webhook,
    monobank_return,
)
```

### 3. Webhook обновление
Обновить логику webhook чтобы правильно устанавливать:
- prepay_200 успех → payment_status='prepaid' → Lead
- online_full успех → payment_status='paid' → Purchase

## Статус
- [ ] Создать MonobankAPIError
- [ ] Создать _monobank_api_request
- [ ] Создать monobank_create_invoice
- [ ] Обновить webhook
- [ ] Протестировать prepay_200
- [ ] Протестировать online_full

