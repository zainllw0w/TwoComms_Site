# Инструкция по настройке Telegram бота

## Шаг 1: Получение токена и Chat ID

1. **Токен бота**: Получите от @BotFather в Telegram
2. **Chat ID**: Получите через https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates

## Шаг 2: Настройка в sPanel

### Вариант 1: Через веб-интерфейс sPanel
1. Зайдите в sPanel
2. Найдите раздел "Environment Variables" или "Переменные окружения"
3. Добавьте:
   - `TELEGRAM_BOT_TOKEN` = ваш_токен_бота
   - `TELEGRAM_CHAT_ID` = ваш_chat_id

### Вариант 2: Через файл .env.production
Замените в файле `/home/qlknpodo/TWC/TwoComms_Site/twocomms/.env.production`:

```bash
TELEGRAM_BOT_TOKEN=ваш_реальный_токен_здесь
TELEGRAM_CHAT_ID=ваш_реальный_chat_id_здесь
```

## Шаг 3: Перезапуск приложения

После настройки переменных перезапустите приложение:
```bash
touch passenger_wsgi.py
```

## Шаг 4: Тестирование

Запустите тест:
```bash
python manage.py test_telegram --message "Тест уведомлений"
```

## Текущий статус

Файл .env.production содержит placeholder значения:
- TELEGRAM_BOT_TOKEN=your_bot_token_here
- TELEGRAM_CHAT_ID=your_chat_id_here

**Нужно заменить на реальные значения!**
