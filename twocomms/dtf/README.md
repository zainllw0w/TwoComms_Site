# DTF module

## Опис
DTF-субдомен `dtf.twocomms.shop` — лендинг + модуль замовлення + трекінг статусу для DTF друку.

## Запуск (локально)
```bash
export DEBUG=1
export SECRET_KEY=dev
python manage.py runserver
```
Відкривати з заголовком `Host: dtf.twocomms.shop` або через локальний hosts.

## Залежності
- Django i18n + LocaleMiddleware
- Pillow (для перевірки PNG)

## Налаштування (env)
- `DTF_MAX_FILE_MB` — ліміт розміру файлу (default 50)
- `DTF_MAX_COPIES` — поріг копій для ручної перевірки (default 500)
- `DTF_MAX_METERS_REVIEW` — метраж для ручної перевірки (default 200)
- `DTF_PRICING` — словник з базовою ціною та tier
- `DTF_TG_BOT_TOKEN` — окремий токен Telegram-бота саме для DTF
- `DTF_TG_CHAT_ID`/`DTF_TG_ADMIN_ID` — chat-id для DTF (якщо не задано, fallback на `TELEGRAM_CHAT_ID`/`TELEGRAM_ADMIN_ID`)

## Файли
- Замовлення: `MEDIA_ROOT/dtf/orders/`
- Ліди/вкладення: `MEDIA_ROOT/dtf/leads/`
- Роботи: `MEDIA_ROOT/dtf/works/`

## Адмінка
Django Admin:
- DtfOrder (actions: approve mockup, need fix, awaiting payment, shipped)
- DtfLead
- DtfWork

## Деплой чекліст
- Додати `dtf.twocomms.shop` в DNS + ALLOWED_HOSTS/CSRF
- `python manage.py migrate`
- `python manage.py collectstatic`
- `python manage.py compilemessages`
- Перевірити Telegram env vars
