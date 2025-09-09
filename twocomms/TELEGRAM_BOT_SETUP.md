# Настройка Telegram бота для подтверждения пользователей

## Описание

Telegram бот `@twocommsbot` автоматически подтверждает пользователей для получения уведомлений о статусе заказов. Пользователь просто пишет любое сообщение боту, и он автоматически связывает Telegram аккаунт с профилем на сайте.

## Как работает

1. **Пользователь нажимает кнопку "Получать статусы"** в профиле или заказах
2. **Открывается Telegram бот** `@twocommsbot`
3. **Пользователь пишет любое сообщение** (например, "Привет" или "/start")
4. **Бот автоматически находит пользователя** по telegram username
5. **Сохраняет telegram_id в базу данных**
6. **Отправляет подтверждающее сообщение**

## Создание бота

### 1. Создать бота через BotFather

1. Откройте Telegram и найдите `@BotFather`
2. Отправьте команду `/newbot`
3. Введите имя бота: `TwoComms Bot`
4. Введите username бота: `twocommsbot`
5. Сохраните полученный токен

### 2. Настроить webhook

```bash
# Установить webhook (замените YOUR_BOT_TOKEN на реальный токен)
curl -X POST "https://api.telegram.org/botYOUR_BOT_TOKEN/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://twocomms.shop/accounts/telegram/webhook/"}'
```

### 3. Добавить токен в настройки

Добавьте в sPanel Environment Variables:
- `TELEGRAM_BOT_TOKEN` = токен вашего бота

## Логика работы бота

### Обработка сообщений

Бот обрабатывает два типа сообщений:

1. **Команда `/start`** - приветствие и инструкции
2. **Любое другое сообщение** - автоматическое подтверждение

### Поиск пользователя

Бот ищет пользователя по telegram username в двух форматах:
- `username` (без @)
- `@username` (с @)

### Сохранение данных

При успешном подтверждении:
- Сохраняется `telegram_id` в поле `UserProfile.telegram_id`
- Отправляется подтверждающее сообщение
- Пользователь начинает получать уведомления

## Уведомления

После подтверждения пользователь получает уведомления о:

- **Новых заказах** - детальная информация о заказе
- **Изменении статуса посылок** - обновления от Nova Poshta
- **Получении заказов** - специальное уведомление о доставке

## Тестирование

### Локальное тестирование

```python
# Создать тестового пользователя с telegram username
from accounts.models import UserProfile
from django.contrib.auth.models import User

user = User.objects.create_user('testuser', 'test@example.com')
profile = UserProfile.objects.create(user=user, telegram='testuser')

# Симулировать сообщение от бота
webhook_data = {
    'message': {
        'from': {'id': 123456789, 'username': 'testuser'},
        'text': 'Привет!'
    }
}

from accounts.telegram_bot import telegram_bot
result = telegram_bot.process_webhook_update(webhook_data)
```

### Проверка в базе данных

```python
# Проверить, что telegram_id сохранен
profile = UserProfile.objects.get(user__username='testuser')
print(f"Telegram ID: {profile.telegram_id}")
```

## Безопасность

- Бот проверяет, что пользователь не подтвержден повторно
- Используется только telegram_id для отправки сообщений
- Нет доступа к личным данным пользователей

## Мониторинг

### Логи

Бот записывает ошибки в консоль Django. Для мониторинга:

```bash
# Просмотр логов Django
tail -f django.log
```

### Webhook статус

```bash
# Проверить статус webhook
curl "https://api.telegram.org/botYOUR_BOT_TOKEN/getWebhookInfo"
```

## Устранение неполадок

### Бот не отвечает

1. Проверьте токен бота в настройках
2. Убедитесь, что webhook установлен правильно
3. Проверьте логи Django на ошибки

### Пользователь не подтверждается

1. Убедитесь, что telegram username введен в профиле
2. Проверьте формат username (с @ или без @)
3. Убедитесь, что пользователь не подтвержден ранее

### Уведомления не приходят

1. Проверьте, что `telegram_id` сохранен в профиле
2. Убедитесь, что `TELEGRAM_BOT_TOKEN` настроен
3. Проверьте логи отправки сообщений

## API Endpoints

- `POST /accounts/telegram/webhook/` - webhook для получения обновлений от Telegram
- `POST /accounts/telegram/link/` - ручное связывание аккаунта (не используется)

## Файлы

- `accounts/telegram_bot.py` - основная логика бота
- `accounts/telegram_views.py` - webhook обработчики
- `accounts/urls.py` - маршруты для бота
- `orders/telegram_notifications.py` - отправка уведомлений
