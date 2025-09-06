#!/bin/bash

# Быстрый скрипт для выполнения миграций
echo "🚀 Быстрая миграция к MySQL..."

# Загружаем переменные окружения
export $(cat db_config.env | grep -v '^#' | xargs)

# Выполняем миграции
python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic --noinput

echo "✅ Миграция завершена!"
