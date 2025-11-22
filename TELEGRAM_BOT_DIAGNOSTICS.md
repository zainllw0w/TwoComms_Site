# Диагностика Telegram бота

## Проблема
Бот не отвечает на сообщения. Webhook не работает.

## Шаги диагностики через SSH

### 1. Подключение к серверу
```bash
sshpass -p '[REDACTED_SSH_PASSWORD]' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && bash'"
```

### 2. Проверка токена бота
```bash
python manage.py shell -c "from django.conf import settings; print('Token:', getattr(settings, 'TELEGRAM_BOT_TOKEN', 'NOT SET')[:20] + '...')"
```

### 3. Проверка и установка webhook
```bash
python manage.py setup_telegram_webhook
```

Или только проверка:
```bash
python manage.py setup_telegram_webhook --check-only
```

### 4. Тестирование endpoint локально
```bash
python test_telegram_webhook.py
```

### 5. Проверка webhook через Telegram API
```bash
python setup_telegram_webhook.py
```

### 6. Проверка логов
```bash
# Логи Django
tail -f /var/log/django.log

# Или если логи в другом месте
tail -f /home/qlknpodo/TWC/TwoComms_Site/twocomms/logs/*.log
```

### 7. Проверка доступности URL
```bash
curl -X POST https://twocomms.shop/accounts/telegram/webhook/ \
  -H "Content-Type: application/json" \
  -d '{"update_id": 1, "message": {"message_id": 1, "from": {"id": 123, "username": "test"}, "chat": {"id": 123}, "text": "test"}}'
```

## Возможные проблемы и решения

### Проблема 1: Webhook не установлен
**Решение:**
```bash
python manage.py setup_telegram_webhook
```

### Проблема 2: URL недоступен
**Проверка:**
- Убедитесь, что сайт доступен по HTTPS
- Проверьте, что URL правильный: `https://twocomms.shop/accounts/telegram/webhook/`
- Проверьте настройки ALLOWED_HOSTS в production_settings.py

### Проблема 3: Токен неверный
**Решение:**
```bash
# Установить токен через переменную окружения
export TELEGRAM_BOT_TOKEN="ваш_токен"

# Или через .env файл
echo "TELEGRAM_BOT_TOKEN=ваш_токен" >> .env
```

### Проблема 4: Ошибки в коде
**Проверка:**
```bash
# Проверить синтаксис
python -m py_compile accounts/telegram_bot.py
python -m py_compile accounts/telegram_views.py

# Запустить тесты
python test_telegram_webhook.py
```

### Проблема 5: Django не настроен правильно
**Проверка:**
```bash
python manage.py check
```

## Тестирование webhook вручную

### Отправить тестовое сообщение через curl:
```bash
curl -X POST https://twocomms.shop/accounts/telegram/webhook/ \
  -H "Content-Type: application/json" \
  -d '{
    "update_id": 123456789,
    "message": {
      "message_id": 1,
      "from": {
        "id": 123456789,
        "is_bot": false,
        "first_name": "Test",
        "username": "testuser"
      },
      "chat": {
        "id": 123456789,
        "first_name": "Test",
        "username": "testuser",
        "type": "private"
      },
      "date": 1234567890,
      "text": "/start"
    }
  }'
```

## Проверка через Telegram API

### Получить информацию о webhook:
```bash
TOKEN="ваш_токен"
curl "https://api.telegram.org/bot${TOKEN}/getWebhookInfo"
```

### Установить webhook вручную:
```bash
TOKEN="ваш_токен"
URL="https://twocomms.shop/accounts/telegram/webhook/"
curl -X POST "https://api.telegram.org/bot${TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"${URL}\"}"
```

## Логи для отладки

Все логи должны выводиться в консоль с префиксами:
- 🔵 - Информационные сообщения
- 🟡 - Предупреждения
- ✅ - Успешные операции
- ❌ - Ошибки

Проверьте логи при отправке сообщения боту.




