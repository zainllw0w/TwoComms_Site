#!/bin/bash

# Скрипт для выполнения миграций Django к MySQL базе данных
# Использование: ./migrate_to_mysql.sh

echo "🚀 Начинаем миграцию к MySQL базе данных..."

# Загружаем переменные окружения
export $(cat db_config.env | grep -v '^#' | xargs)

echo "📊 Настройки подключения к базе данных:"
echo "   Host: $DB_HOST"
echo "   Port: $DB_PORT"
echo "   Database: $DB_NAME"
echo "   User: $DB_USER"

# Проверяем подключение к базе данных
echo "🔍 Проверяем подключение к MySQL..."
python -c "
import os
import django
from django.conf import settings

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
django.setup()

from django.db import connection
try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    print('✅ Подключение к базе данных успешно!')
except Exception as e:
    print(f'❌ Ошибка подключения к базе данных: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Не удалось подключиться к базе данных. Проверьте настройки."
    exit 1
fi

# Выполняем миграции
echo "📦 Выполняем миграции..."

echo "1️⃣ Создаем миграции для всех приложений..."
python manage.py makemigrations

echo "2️⃣ Применяем миграции к базе данных..."
python manage.py migrate

echo "3️⃣ Создаем суперпользователя (если нужно)..."
echo "   Логин: zainllw0w"
echo "   Пароль: 123"
python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='zainllw0w').exists():
    User.objects.create_superuser('zainllw0w', 'admin@twocomms.shop', '123')
    print('✅ Суперпользователь создан!')
else:
    print('ℹ️  Суперпользователь уже существует')
"

echo "4️⃣ Собираем статические файлы..."
python manage.py collectstatic --noinput

echo "5️⃣ Проверяем состояние базы данных..."
python manage.py showmigrations

echo "✅ Миграция завершена успешно!"
echo ""
echo "🌐 Теперь вы можете:"
echo "   - Запустить сервер: python manage.py runserver"
echo "   - Открыть админку: http://localhost:8000/admin/"
echo "   - Логин: zainllw0w / Пароль: 123"
echo ""
echo "📋 Информация о базе данных:"
echo "   - Тип: MySQL"
echo "   - База: $DB_NAME"
echo "   - Пользователь: $DB_USER"
