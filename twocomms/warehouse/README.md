# Warehouse / Storage Subdomain

Внутрішній склад TwoComms на окремому субдомені **`storage.twocomms.shop`**.

## Що це

Mobile-first PWA для адмінів складу. Облік:
- одягу (футболки/худі/лонгсліви) у розрізі **категорія → крій (підкатегорія) → колір × розмір**;
- принтів з кольоровими варіантами (Зелений / Білий / Золотий тощо);
- руху товарів з аудит-логом і верифікацією.

## Архітектура

```
storage.twocomms.shop  ───►  middleware вибирає urlconf 'twocomms.urls_storage'
                                  │
                                  ▼
                          warehouse app
                          ├── models, views, services
                          ├── PWA (manifest, sw)
                          ├── Telegram bot (вечірнє нагадування)
                          └── Інтеграція з orders (кнопка "Списати зі складу")
```

## Доступ

- `is_staff = True` + членство в Django Group **`warehouse_admins`** (або `is_superuser`).
- Логін: Google OAuth (як на основному сайті/management) або email+password.
- Сесія розшарена через `SESSION_COOKIE_DOMAIN=.twocomms.shop`.

Швидке надання прав:
```bash
python manage.py seed_warehouse_admin <username_or_email>
python manage.py seed_warehouse_admin <username> --remove
```

## Потрібні env-змінні

| Змінна | Призначення |
|---|---|
| `TELEGRAM_STORAGE_BOT_TOKEN` | Токен окремого Storage-бота (з @BotFather) |
| `TELEGRAM_STORAGE_CHAT_IDS` | Cписок chat_id адмінів (через кому) |
| `TELEGRAM_STORAGE_WEBHOOK_SECRET` | Випадковий секрет (≥ 32 символи) для webhook URL та X-Telegram-Bot-Api-Secret-Token |
| `WAREHOUSE_SUBDOMAIN_URL` | Базовий URL (default: `https://storage.twocomms.shop`) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Уже задано — додайте `https://storage.twocomms.shop/oauth/complete/google-oauth2/` у redirect_uri |

## Перший запуск (production)

```bash
# 1. Pull + міграції + статика
sshpass -p 'XXXX' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 \
  "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate \
   && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms \
   && git pull \
   && python manage.py migrate warehouse \
   && python manage.py collectstatic --noinput | tail -5 \
   && touch tmp/restart.txt'"

# 2. cPanel → Domains → Add subdomain `storage` → той самий document root
# 3. cPanel → SSL/TLS → AutoSSL для storage.twocomms.shop
# 4. cPanel → Setup Python App → перевірити що passenger обслуговує storage.*
# 5. Додати Google redirect_uri:
#    https://storage.twocomms.shop/oauth/complete/google-oauth2/

# 6. Telegram: створити бота через @BotFather, отримати токен.
#    Згенерувати webhook secret:
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 7. Додати в env (cPanel Setup Python App → Environment variables):
#    TELEGRAM_STORAGE_BOT_TOKEN=...
#    TELEGRAM_STORAGE_WEBHOOK_SECRET=...

# 8. Встановити webhook
python manage.py setup_storage_webhook

# 9. Зробити себе warehouse-адміном
python manage.py seed_warehouse_admin yourusername

# 10. Cron (через cPanel Cron jobs) — щодня 22:00 (Europe/Kyiv):
#     0 22 * * * cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && \
#       /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python \
#       manage.py send_storage_reminder
```

## Структура

```
warehouse/
├── models.py              # 8 моделей складу
├── permissions.py         # warehouse_admin_required
├── signals.py             # auto-create group on migrate
├── apps.py
├── admin.py               # Django admin (для аварій)
├── tasks.py               # Celery / cron task для нагадування
├── telegram_views.py      # Webhook для Storage-бота
├── urls.py                # /, /categories/, /prints/, /history/, ...
├── views/
│   ├── dashboard.py       # головна + сторінка сьогодні
│   ├── categories.py      # категорії + матриця + AJAX adjust
│   ├── prints.py          # принти + варіанти
│   ├── write_off.py       # сторінка списання за заказом
│   ├── history.py         # історія + фільтри
│   ├── finance.py         # фін.дашборд + графік
│   ├── auth_views.py      # логін / логаут
│   └── errors.py
├── services/
│   ├── inventory.py       # adjust_stock_item / adjust_print_variant
│   ├── matching.py        # OrderItem → StockItem
│   ├── finance.py         # агрегати "заморожено"
│   ├── order_links.py     # build_storage_writeoff_url
│   └── telegram_storage.py # API клієнт Storage-бота
├── management/commands/
│   ├── setup_storage_webhook.py
│   ├── send_storage_reminder.py
│   └── seed_warehouse_admin.py
├── templates/warehouse/   # mobile-first PWA шаблони
├── static/warehouse/      # CSS + JS + manifest + service worker
└── tests/                 # unit + integration tests
```

## Бот замовлень: нова кнопка

У `orders/telegram_notifications.py._build_order_management_reply_markup()`
додано кнопку **«📦 Списати зі складу»**, яка веде на:
```
https://storage.twocomms.shop/order/<UUID>/write-off/
```
Адмін відкриває сторінку, обирає підкатегорію (крій), принт і кількість, тисне «Списати»
→ `StockMovement(reason=order_write_off)` записується в БД, кількість зменшується.

## Storage-бот: вечірнє нагадування

Storage-бот має одну функцію — щодня о 22:00 (cron) шле адмінам повідомлення:
> 🌙 Сьогодні зафіксовано N рухів (не перевірено: M).
> Чи всі зміни перевірено?
> [✅ Все ок]  [📝 Перевірити]

- `[Все ок]` — масово відмічає всі сьогоднішні `StockMovement.verified = True`.
- `[Перевірити]` — deeplink на `/today/` для ручної верифікації.

## Тести

```bash
DEBUG=True SECRET_KEY=dev python manage.py test warehouse -v 2
```

27 тестів, покривають:
- моделі (auto-slug, unique constraints, frozen_value);
- inventory services (adjust, set, validation);
- matching (OrderItem → StockItem за category+size+color);
- views (доступ, AJAX, dashboard);
- write-off flow (build URL, render, submit, decrement).

## Поведінкові деталі (з вимог)

- **Підкатегорія/крій** ніколи не показується клієнту — це чисто внутрішня класифікація.
- При списанні за заказом адмін бачить **усі** позиції з відповідним розміром+кольором у всіх підкатегоріях, обирає вручну.
- Принт за замовчуванням підставляється з `Print.default_products`, але можна змінити.
- Сесія розшарена з основним сайтом і management — login на одному == login на всіх.
