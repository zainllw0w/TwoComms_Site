#!/bin/bash
# Скрипт для проверки работы Telegram бота

echo "=========================================="
echo "ПРОВЕРКА TELEGRAM БОТА"
echo "=========================================="
echo ""

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Проверка токена бота
echo "1. Проверка токена бота..."
TOKEN=$(python3 -c "
import os
import sys
import django
sys.path.insert(0, '/home/qlknpodo/TWC/TwoComms_Site/twocomms')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()
from django.conf import settings
token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
print(token)
" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo -e "${RED}❌ Токен бота НЕ НАЙДЕН${NC}"
    echo "   Проверьте переменную окружения TELEGRAM_BOT_TOKEN"
else
    echo -e "${GREEN}✅ Токен найден: ${TOKEN:0:10}...${TOKEN: -5}${NC}"
fi
echo ""

# 2. Проверка webhook URL
echo "2. Проверка webhook URL..."
WEBHOOK_URL="https://twocomms.shop/accounts/telegram/webhook/"
echo "   URL: $WEBHOOK_URL"

# Проверка доступности URL
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$WEBHOOK_URL" -H "Content-Type: application/json" -d '{"test": "data"}' 2>/dev/null)
if [ "$HTTP_CODE" == "200" ] || [ "$HTTP_CODE" == "400" ] || [ "$HTTP_CODE" == "405" ]; then
    echo -e "${GREEN}✅ Endpoint доступен (HTTP $HTTP_CODE)${NC}"
else
    echo -e "${RED}❌ Endpoint недоступен (HTTP $HTTP_CODE)${NC}"
fi
echo ""

# 3. Проверка статуса webhook через Telegram API
if [ ! -z "$TOKEN" ]; then
    echo "3. Проверка статуса webhook в Telegram..."
    WEBHOOK_INFO=$(curl -s "https://api.telegram.org/bot${TOKEN}/getWebhookInfo")
    
    if echo "$WEBHOOK_INFO" | grep -q '"ok":true'; then
        echo -e "${GREEN}✅ Запрос к Telegram API успешен${NC}"
        
        # Извлекаем информацию
        URL=$(echo "$WEBHOOK_INFO" | grep -o '"url":"[^"]*' | cut -d'"' -f4)
        PENDING_COUNT=$(echo "$WEBHOOK_INFO" | grep -o '"pending_update_count":[0-9]*' | cut -d':' -f2)
        LAST_ERROR=$(echo "$WEBHOOK_INFO" | grep -o '"last_error_message":"[^"]*' | cut -d'"' -f4)
        
        echo "   Webhook URL: $URL"
        echo "   Ожидающих обновлений: $PENDING_COUNT"
        
        if [ ! -z "$LAST_ERROR" ]; then
            echo -e "${RED}   Последняя ошибка: $LAST_ERROR${NC}"
        fi
        
        if [ -z "$URL" ] || [ "$URL" == "null" ]; then
            echo -e "${RED}❌ Webhook НЕ УСТАНОВЛЕН${NC}"
            echo "   Нужно установить webhook командой:"
            echo "   python manage.py shell -c \"from accounts.telegram_bot import telegram_bot; telegram_bot.set_webhook('$WEBHOOK_URL')\""
        else
            if [ "$URL" == "$WEBHOOK_URL" ]; then
                echo -e "${GREEN}✅ Webhook установлен правильно${NC}"
            else
                echo -e "${YELLOW}⚠️  Webhook установлен на другой URL: $URL${NC}"
                echo "   Ожидаемый URL: $WEBHOOK_URL"
            fi
        fi
    else
        echo -e "${RED}❌ Ошибка при запросе к Telegram API${NC}"
        echo "$WEBHOOK_INFO"
    fi
else
    echo -e "${YELLOW}⚠️  Пропущено (нет токена)${NC}"
fi
echo ""

# 4. Проверка Django endpoint через Python
echo "4. Проверка Django endpoint..."
python3 << 'PYTHON_SCRIPT'
import os
import sys
import django
import json
import requests

sys.path.insert(0, '/home/qlknpodo/TWC/TwoComms_Site/twocomms')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from django.conf import settings
from django.test import RequestFactory
from accounts.telegram_views import telegram_webhook

# Создаем тестовый запрос
factory = RequestFactory()
test_data = {
    "update_id": 123456789,
    "message": {
        "message_id": 1,
        "from": {
            "id": 123456789,
            "is_bot": False,
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
}

request = factory.post(
    '/accounts/telegram/webhook/',
    data=json.dumps(test_data),
    content_type='application/json'
)

try:
    response = telegram_webhook(request)
    print(f"✅ Endpoint работает, ответ: {response.status_code}")
    print(f"   Содержимое: {response.content.decode()[:200]}")
except Exception as e:
    print(f"❌ Ошибка при тестировании endpoint: {e}")
    import traceback
    traceback.print_exc()
PYTHON_SCRIPT

echo ""
echo "=========================================="
echo "ПРОВЕРКА ЗАВЕРШЕНА"
echo "=========================================="




