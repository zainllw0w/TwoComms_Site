# 🔍 ДИАГНОСТИКА TELEGRAM БОТА

## Проблема
Бот не отвечает на сообщения. Webhook не работает.

## ⚡ БЫСТРАЯ ПРОВЕРКА ЧЕРЕЗ SSH

### Шаг 1: Подключение к серверу
```bash
sshpass -p 'trs5m4t1' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && bash'"
```

### Шаг 2: Проверка токена бота
```bash
python manage.py shell -c "from django.conf import settings; token = getattr(settings, 'TELEGRAM_BOT_TOKEN', ''); print('✅ Token found' if token else '❌ Token NOT found'); print('Token:', token[:20] + '...' if token else 'NOT SET')"
```

### Шаг 3: Проверка и установка webhook (ГЛАВНАЯ КОМАНДА)
```bash
python manage.py setup_telegram_webhook
```

Эта команда:
- ✅ Проверит токен
- ✅ Покажет текущий статус webhook
- ✅ Установит webhook если нужно
- ✅ Покажет ошибки если есть

### Шаг 4: Проверка endpoint локально
```bash
python test_telegram_webhook.py
```

### Шаг 5: Проверка доступности URL
```bash
curl -X POST https://twocomms.shop/accounts/telegram/webhook/ \
  -H "Content-Type: application/json" \
  -d '{"update_id": 1, "message": {"message_id": 1, "from": {"id": 123, "username": "test"}, "chat": {"id": 123}, "text": "test"}}'
```

## 🔧 ВОЗМОЖНЫЕ ПРОБЛЕМЫ И РЕШЕНИЯ

### ❌ Проблема 1: Webhook не установлен
**Симптомы:** Бот не отвечает, в логах нет запросов

**Решение:**
```bash
python manage.py setup_telegram_webhook
```

### ❌ Проблема 2: Токен не установлен
**Симптомы:** Ошибка "Token not found"

**Решение:**
```bash
# Проверить переменные окружения
env | grep TELEGRAM

# Установить через .env файл или переменные окружения
export TELEGRAM_BOT_TOKEN="ваш_токен"
```

### ❌ Проблема 3: URL недоступен
**Симптомы:** Telegram показывает ошибку при установке webhook

**Проверка:**
```bash
# Проверить доступность сайта
curl -I https://twocomms.shop

# Проверить endpoint
curl -X POST https://twocomms.shop/accounts/telegram/webhook/ \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

### ❌ Проблема 4: Ошибки в коде
**Симптомы:** Webhook установлен, но бот не отвечает

**Проверка:**
```bash
# Проверить синтаксис
python -m py_compile accounts/telegram_bot.py
python -m py_compile accounts/telegram_views.py

# Запустить тесты
python test_telegram_webhook.py
```

### ❌ Проблема 5: Django не настроен
**Проверка:**
```bash
python manage.py check
```

## 📋 ПОЛНАЯ ДИАГНОСТИКА

### 1. Проверка через Telegram API
```bash
TOKEN="ваш_токен"
curl "https://api.telegram.org/bot${TOKEN}/getWebhookInfo"
```

Должен вернуть:
```json
{
  "ok": true,
  "result": {
    "url": "https://twocomms.shop/accounts/telegram/webhook/",
    "has_custom_certificate": false,
    "pending_update_count": 0
  }
}
```

### 2. Установка webhook вручную
```bash
TOKEN="ваш_токен"
URL="https://twocomms.shop/accounts/telegram/webhook/"
curl -X POST "https://api.telegram.org/bot${TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"${URL}\"}"
```

### 3. Тестирование webhook
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

## 📊 ЛОГИ ДЛЯ ОТЛАДКИ

Все логи выводятся с префиксами:
- 🔵 - Информация
- 🟡 - Предупреждения  
- ✅ - Успех
- ❌ - Ошибки

Проверьте логи при отправке сообщения:
```bash
# Если логи в файле
tail -f /var/log/django.log

# Или в другом месте
tail -f logs/*.log
```

## ✅ ЧЕКЛИСТ ПРОВЕРКИ

- [ ] Токен бота установлен
- [ ] Webhook установлен на правильный URL
- [ ] URL доступен извне (HTTPS)
- [ ] Endpoint отвечает на POST запросы
- [ ] Нет ошибок в коде
- [ ] Django приложение работает
- [ ] Логи показывают входящие запросы

## 🚀 ПОСЛЕ ИСПРАВЛЕНИЯ

1. Установите webhook: `python manage.py setup_telegram_webhook`
2. Отправьте тестовое сообщение боту
3. Проверьте логи - должны быть записи о входящем сообщении
4. Бот должен ответить

## 📞 ЕСЛИ НЕ РАБОТАЕТ

1. Проверьте все пункты чеклиста выше
2. Запустите полную диагностику
3. Проверьте логи на наличие ошибок
4. Убедитесь, что сайт доступен по HTTPS
5. Проверьте, что токен правильный



