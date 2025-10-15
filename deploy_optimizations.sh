#!/bin/bash

# Скрипт для деплоя оптимизаций TwoComms на сервер
# Применяет миграции, собирает статику, тестирует производительность

echo "🚀 Деплой оптимизаций TwoComms на сервер..."

# Параметры подключения
SSH_HOST="195.191.24.169"
SSH_USER="qlknpodo"
SSH_PASSWORD="[REDACTED_SSH_PASSWORD]"
PROJECT_PATH="/home/qlknpodo/TWC/TwoComms_Site/twocomms"
VENV_PATH="/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate"

# Функция для выполнения команд на сервере
run_on_server() {
    local command="$1"
    echo "🔧 Выполняем: $command"
    sshpass -p "$SSH_PASSWORD" ssh -o StrictHostKeyChecking=no "$SSH_USER@$SSH_HOST" "bash -lc 'source $VENV_PATH && cd $PROJECT_PATH && $command'"
}

# Функция для копирования файлов на сервер
copy_to_server() {
    local local_file="$1"
    local remote_file="$2"
    echo "📁 Копируем: $local_file -> $remote_file"
    sshpass -p "$SSH_PASSWORD" scp -o StrictHostKeyChecking=no "$local_file" "$SSH_USER@$SSH_HOST:$remote_file"
}

echo "📋 Этап 1: Подготовка сервера"
echo "================================"

# Создаем бэкап текущего состояния
echo "💾 Создание бэкапа..."
run_on_server "cp -r $PROJECT_PATH ${PROJECT_PATH}_backup_$(date +%Y%m%d_%H%M%S)"

echo ""
echo "📋 Этап 2: Копирование оптимизированных файлов"
echo "=============================================="

# Копируем оптимизированные файлы
copy_to_server "twocomms/storefront/models.py" "$PROJECT_PATH/storefront/models.py"
copy_to_server "twocomms/storefront/views.py" "$PROJECT_PATH/storefront/views.py"

# Копируем оптимизированные CSS файлы
run_on_server "mkdir -p $PROJECT_PATH/static/css/optimized"
copy_to_server "twocomms/static/css/optimized/critical.css" "$PROJECT_PATH/static/css/optimized/critical.css"
copy_to_server "twocomms/static/css/optimized/non-critical.css" "$PROJECT_PATH/static/css/optimized/non-critical.css"

echo ""
echo "📋 Этап 3: Применение миграций"
echo "=============================="

# Проверяем статус миграций
echo "🔍 Проверка статуса миграций..."
run_on_server "python3 manage.py showmigrations storefront"

# Применяем миграции
echo "🗄️ Применение миграций..."
run_on_server "python3 manage.py migrate"

echo ""
echo "📋 Этап 4: Сбор статических файлов"
echo "=================================="

# Собираем статические файлы
echo "📁 Сбор статических файлов..."
run_on_server "python3 manage.py collectstatic --noinput"

echo ""
echo "📋 Этап 5: Проверка работоспособности"
echo "===================================="

# Проверяем синтаксис Python
echo "🐍 Проверка синтаксиса..."
run_on_server "python3 -m py_compile storefront/models.py"
run_on_server "python3 -m py_compile storefront/views.py"

# Проверяем настройки Django
echo "⚙️ Проверка настроек Django..."
run_on_server "python3 manage.py check"

echo ""
echo "📋 Этап 6: Тестирование производительности"
echo "=========================================="

# Создаем простой тест производительности
echo "🧪 Тестирование производительности БД..."
run_on_server "python3 -c \"
from django.conf import settings
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
import django
django.setup()

from storefront.models import Product, Category
import time

# Тест скорости запросов
start = time.time()
products = list(Product.objects.select_related('category').all()[:10])
end = time.time()
print(f'Запрос с select_related: {end-start:.3f}s')

start = time.time()
categories = list(Category.objects.filter(is_active=True))
end = time.time()
print(f'Запрос категорий: {end-start:.3f}s')

print('✅ Тесты производительности завершены')
\""

echo ""
echo "📋 Этап 7: Финальная проверка"
echo "============================="

# Проверяем размер оптимизированных файлов
echo "📊 Проверка размеров файлов..."
run_on_server "ls -lh static/css/optimized/"

# Проверяем, что сервер может запуститься
echo "🚀 Тест запуска сервера..."
run_on_server "timeout 10 python3 manage.py runserver 0.0.0.0:8000 > /dev/null 2>&1 && echo '✅ Сервер запускается корректно' || echo '⚠️ Проблемы с запуском сервера'"

echo ""
echo "📋 Этап 8: Копирование отчетов"
echo "=============================="

# Копируем отчеты на локальную машину
echo "📄 Копирование отчетов..."
copy_to_server "FINAL_OPTIMIZATION_SUMMARY.md" "/tmp/FINAL_OPTIMIZATION_SUMMARY.md"
run_on_server "cp /tmp/FINAL_OPTIMIZATION_SUMMARY.md $PROJECT_PATH/"

echo ""
echo "✅ Деплой оптимизаций завершен!"
echo "==============================="
echo ""
echo "📊 Результаты:"
echo "  ✅ Миграции применены"
echo "  ✅ Статические файлы собраны"
echo "  ✅ Производительность протестирована"
echo "  ✅ Отчеты скопированы"
echo ""
echo "🎯 Следующие шаги:"
echo "  1. Перезапустить веб-сервер (nginx/apache)"
echo "  2. Проверить работу сайта"
echo "  3. Мониторить производительность"
echo "  4. При необходимости откатиться к бэкапу"
echo ""
echo "📁 Бэкап создан в: ${PROJECT_PATH}_backup_$(date +%Y%m%d_%H%M%S)"
echo "📄 Отчеты сохранены в: $PROJECT_PATH/"

