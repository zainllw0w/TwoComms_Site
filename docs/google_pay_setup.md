# Онлайн-оплата карткою через monobank

Інтернет-еквайринг на TwoComms переведено з Google Pay на прямі рахунки monobank. Нижче — короткий чеклист по налаштуванню та відмові від старих GPay-параметрів.

## 1. Доступи monobank
1. У бізнес-кабінеті [https://web.monobank.ua](https://web.monobank.ua) згенеруйте інтеграційний токен (Merchant → Налаштування → Інтернет-еквайринг).
2. Задайте його у середовищі:
   ```bash
   export MONOBANK_TOKEN="<your-monobank-token>"
   ```
   У продакшн-оточенні краще зберігати токен у `.env`/секретах замість дефолтного значення в `settings.py`.
3. За потреби можна перевизначити webhook-адресу:
   ```bash
   export MONOBANK_WEBHOOK_URL="https://twocomms.shop/payments/monobank/webhook/"
   ```
   Якщо змінна не задана, бекенд самостійно будує абсолютну URL на основі `request`.

## 2. Серверна логіка
- Кнопка «Онлайн оплата карткою» викликає `POST /cart/monobank/create-invoice/`. View формує/оновлює замовлення, рахує кошик, створює рахунок через `POST https://api.monobank.ua/api/merchant/invoice/create` і повертає `pageUrl` для редіректу.
- Після повернення користувача на `payments/monobank/return/` бекенд запитує статус `GET …/invoice/status?invoiceId=` і оновлює `payment_status`.
- Вебхук `payments/monobank/webhook/` приймає асинхронні `status`-івенти (success/processing/failure) і синхронізує замовлення. Підпис наразі не перевіряється — якщо потрібна валідація, можна реалізувати через `GET /api/merchant/pubkey` і RSA-перевірку `X-Signature`.
- У таблиці `orders_order` додано поля `payment_provider`, `payment_invoice_id`, `payment_payload`, `session_key` — вони допомагають відстежувати оплату й уникати дубльованих інвойсів для одного сеансу.

## 3. Фронтенд
- У `cart.html` кнопка monobank оформлена за брендбуком (градієнт, напис `mono·pay`). Стани «loading / success / error» обробляються без перезавантаження сторінки.
- Перед запитом фронтенд перевіряє, що обрано тип оплати «Повна передоплата», і надсилає дані доставки в JSON. Успішний виклик робить редірект без додаткових попапів.
- Трекінг (`window.trackEvent`) оновлено: події `InitiateCheckout` та `StartPayment` тепер маркуються як `payment_method: 'monobank'`.

## 4. Тестування
1. Для smoke-тестів достатньо створити рахунок із незначною сумою (наприклад 1 грн = `amount: 100`) і впевнитися, що повертається робочий `pageUrl`.
2. Статус можна перевірити вручну:
   ```bash
   curl -H "X-Token: $MONOBANK_TOKEN" \
        "https://api.monobank.ua/api/merchant/invoice/status?invoiceId=XXXXX"
   ```
3. Вебхук легко симулювати через `curl` на `/payments/monobank/webhook/`, передавши JSON із `invoiceId` та `status`.
4. У разі потреби додайте кастомну логіку для підтвердження холдових операцій (`status = hold`) — зараз вони трактуються як успішна оплата.

## 5. Прибирання Google Pay
- Скрипт `https://pay.google.com/gp/p/js/pay.js` і весь JS-код для Google Pay видалено з `base.html` та `cart.html`.
- Документацію по GPay можна архівувати або перейменувати файл, якщо потрібна історія. Поточний файл описує лише інтеграцію з monobank.

Монобанк готовий до продуктивної роботи — достатньо розгорнути зміни, оновити змінні середовища та пройти тестову оплату.
