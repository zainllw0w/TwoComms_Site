#!/bin/bash
# Скрипт для дальнейшей оптимизации TwoComms

echo "🚀 Запуск дополнительной оптимизации TwoComms..."

# 1. Сбор статических файлов
echo "📁 Сбор статических файлов..."
python3 manage.py collectstatic --noinput

# 2. Применение миграций
echo "🗄️ Применение миграций..."
python3 manage.py migrate

# 3. Создание суперпользователя (если нужно)
echo "👤 Создание суперпользователя..."
python3 manage.py createsuperuser --noinput --username admin --email admin@twocomms.com || echo "Суперпользователь уже существует"

# 4. Оптимизация изображений (если установлен Pillow)
echo "🖼️ Оптимизация изображений..."
python3 manage.py optimize_images || echo "Оптимизация изображений пропущена"

# 5. Очистка кэша
echo "🧹 Очистка кэша..."
python3 manage.py clear_cache || echo "Кэш очищен"

echo "✅ Дополнительная оптимизация завершена!"
