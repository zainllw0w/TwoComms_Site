#!/bin/bash

# Скрипт автоматического деплоя TwoComms
# Использование: ./deploy.sh "commit message"

set -e  # Остановить при ошибке

echo "🚀 Начинаем деплой TwoComms..."

# Проверка аргументов
if [ -z "$1" ]; then
    echo "❌ Ошибка: Укажите сообщение коммита"
    echo "Использование: ./deploy.sh \"ваше сообщение\""
    exit 1
fi

COMMIT_MESSAGE="$1"
SERVER_USER="qlknpodo"
SERVER_HOST="195.191.24.169"
SERVER_PATH="/home/qlknpodo/TWC/TwoComms_Site/twocomms"
SERVER_PASSWORD="trs5m4t1"

echo "📝 Коммит: $COMMIT_MESSAGE"

# 1. Коммит локальных изменений
echo "1️⃣ Добавляем файлы в git..."
git add -A

echo "2️⃣ Коммитим изменения..."
git commit -m "$COMMIT_MESSAGE" || echo "Нет изменений для коммита"

echo "3️⃣ Пушим в GitHub..."
git push origin main

# 2. Деплой на сервер
echo "4️⃣ Подключаемся к серверу и делаем git pull..."
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_HOST} << 'EOF'
    cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
    
    echo "   📥 Получаем изменения с GitHub..."
    git pull origin main
    
    echo "   📦 Активируем виртуальное окружение..."
    source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate
    
    echo "   📚 Собираем статические файлы..."
    python manage.py collectstatic --noinput
    
    echo "   🔄 Перезапускаем сервер..."
    touch twocomms/wsgi.py
    
    echo "   ✅ Деплой на сервере завершен!"
EOF

echo ""
echo "✅ Деплой успешно завершен!"
echo "🌐 Сайт обновлен: https://twocomms.shop"

