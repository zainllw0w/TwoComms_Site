# Настройка Telegram уведомлений

## Создание Telegram бота

1. Найдите бота @BotFather в Telegram
2. Отправьте команду `/newbot`
3. Введите имя бота (например: "TwoComms Notifications")
4. Введите username бота (например: "twocomms_notifications_bot")
5. Сохраните полученный токен

## Получение Chat ID

1. Добавьте бота в группу или начните с ним диалог
2. Отправьте любое сообщение боту
3. Перейдите по ссылке: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Найдите `"chat":{"id":` в ответе - это ваш Chat ID

## Настройка переменных окружения

Добавьте в файл `.env.production`:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

## Тестирование

Запустите команду для тестирования:

```bash
python manage.py test_telegram --message "Тест уведомлений"
```

## Функции

- Автоматические уведомления при создании нового заказа
- Уведомления об изменении статуса заказа
- Подробная информация о заказе в сообщении
