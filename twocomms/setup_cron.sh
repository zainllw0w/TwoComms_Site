#!/bin/bash
# Скрипт для настройки автоматического обновления статусов посылок

echo "=== Настройка автоматического обновления статусов Новой Почты ==="

# Путь к проекту
PROJECT_PATH="/home/qlknpodo/TWC/TwoComms_Site/twocomms"
PYTHON_PATH="/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/python"

# Создаем команду для cron
CRON_COMMAND="*/30 * * * * cd $PROJECT_PATH && $PYTHON_PATH manage.py update_tracking_statuses >> /tmp/nova_poshta_update.log 2>&1"

echo "Команда для cron:"
echo "$CRON_COMMAND"
echo ""

# Проверяем, есть ли уже такая команда в crontab
if crontab -l 2>/dev/null | grep -q "update_tracking_statuses"; then
    echo "⚠️  Команда уже существует в crontab"
    echo "Текущий crontab:"
    crontab -l | grep "update_tracking_statuses"
else
    echo "✅ Команда не найдена в crontab"
    echo ""
    echo "Для добавления команды выполните:"
    echo "crontab -e"
    echo ""
    echo "И добавьте строку:"
    echo "$CRON_COMMAND"
fi

echo ""
echo "=== Проверка настроек ==="

# Проверяем наличие API ключа
echo "Проверка API ключа Новой Почты..."
cd $PROJECT_PATH
source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate
python manage.py shell -c "
from django.conf import settings
api_key = getattr(settings, 'NOVA_POSHTA_API_KEY', '')
print(f'API ключ настроен: {bool(api_key)}')
if api_key:
    print(f'API ключ: {api_key[:10]}...')
"

echo ""
echo "Проверка заказов с ТТН..."
python manage.py shell -c "
from orders.models import Order
orders_with_ttn = Order.objects.filter(tracking_number__isnull=False).exclude(tracking_number='')
print(f'Заказов с ТТН: {orders_with_ttn.count()}')
for order in orders_with_ttn[:3]:
    print(f'  {order.order_number}: {order.tracking_number} - {order.shipment_status or \"Не установлен\"}')
"

echo ""
echo "=== Готово! ==="
echo "Система готова к автоматическому обновлению статусов посылок"
