# Налаштування Google Pay для TwoComms

Кнопка Google Pay на сайті вже підключена в середовище sandbox. Щоб приймати реальні платежі та прибрати помилку `OR_BIBED_06`, потрібно виконати кроки нижче.

## 1. Зареєструвати бізнес у Google Pay Console
1. Відкрити [Google Pay & Wallet console](https://pay.google.com/business/console).
2. Створити профіль продавця та пройти перевірку (KYC):
   - юридична назва компанії та контактні дані;
   - домен магазину (верифікація файлом або мета-тегом);
   - інформація для служби підтримки.
3. Після схвалення з'явиться `Merchant ID` виду `BCR2DN...`.

## 2. Підключити платіжний шлюз
Google Pay передає криптограму у ваш платіжний сервіс – кошти безпосередньо не списуються.

1. Визначити сумісний шлюз (Stripe, LiqPay, Fondy, WayForPay тощо). Повний список: [Supported payment processors](https://developers.google.com/pay/api/web/guides/test-and-deploy/payment-processors).
2. У кабінеті обраного шлюзу увімкнути Google Pay й отримати параметри токенізації:
   - `gateway` – код провайдера (наприклад, `stripe`);
   - `gatewayMerchantId` – ідентифікатор магазину в шлюзі.
3. Якщо інтегруєтесь напряму з банком, замість `gateway` використовується тип `DIRECT` з власними ключами (`protocolVersion`, `publicKey`, `signature`).

## 3. Оновити конфіг у коді
У файлі `twocomms/twocomms_django_theme/templates/pages/cart.html` замінити плейсхолдери:

```js
const gpayTokenizationSpecification = {
  type: 'PAYMENT_GATEWAY',
  parameters: {
    gateway: 'stripe',              // ← ваш шлюз
    gatewayMerchantId: 'your-merchant-id' // ← merchant ID зі шлюзу
  }
};
...
merchantInfo: {
  merchantName: 'TwoComms',
  merchantId: 'your-merchant-id'    // ← Merchant ID з Google
}
```

- Для production виставити `environment: 'PRODUCTION'` у `PaymentsClient`.
- Не забути підняти версію статичних файлів (`styles.min.css?v=…`, `main.js?v=…`).

## 4. Бекенд-обробка
Функція `google_pay_success` вже створює замовлення і позначає його як сплачене. Для продакшену потрібно:
- перевіряти підпис/токен через SDK платіжного шлюзу або REST API;
- підтверджувати (capture) транзакцію і лише після цього виставляти `payment_status='paid'`;
- логувати відповіді шлюзу, обробляти помилки та повторні спроби.

## 5. Тестування
- Залишити `environment: 'TEST'` до моменту запуску в production.
- Використовувати тестові картки: [офіційний набір Google Pay](https://developers.google.com/pay/api/web/guides/resources/test-card-suite).
- Перевірити сценарії: авторизований користувач, гість, скасування платежу, повторне відкриття кнопки.

Після виконання кроків 1–4 Google схвалить продавця, шлюз прийме Google Pay токени, і помилка `OR_BIBED_06` зникне.
