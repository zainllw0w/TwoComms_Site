#!/bin/bash
#
# ПОЛНЫЙ АУДИТ TWOCOMMS НА PRODUCTION СЕРВЕРЕ
# Запустите этот скрипт на сервере для детального анализа
#
# Использование:
#   1. Скопируйте на сервер: scp server_audit_script.sh user@server:/path/
#   2. Запустите: bash server_audit_script.sh
#

set -e

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║          ПОЛНЫЙ АУДИТ TWOCOMMS PRODUCTION СЕРВЕРА                   ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

REPORT_DIR="audit_report_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$REPORT_DIR"

echo -e "${GREEN}📁 Создана папка отчёта: $REPORT_DIR${NC}"
echo ""

# ============================================================================
# 1. СИСТЕМНАЯ ИНФОРМАЦИЯ
# ============================================================================
echo -e "${YELLOW}[1/15] Сбор системной информации...${NC}"

cat > "$REPORT_DIR/01_system_info.txt" << EOF
=== СИСТЕМНАЯ ИНФОРМАЦИЯ ===
Дата аудита: $(date)
Hostname: $(hostname)
OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)
Kernel: $(uname -r)
Uptime: $(uptime)

=== CPU ===
$(lscpu | grep -E "Model name|CPU\(s\)|Thread|Core")

=== ПАМЯТЬ ===
$(free -h)

=== ДИСК ===
$(df -h)

=== ЗАГРУЗКА ===
$(top -bn1 | head -20)
EOF

echo -e "${GREEN}✅ Системная информация собрана${NC}"

# ============================================================================
# 2. СТРУКТУРА ПРОЕКТА
# ============================================================================
echo -e "${YELLOW}[2/15] Анализ структуры проекта...${NC}"

cd /home/qlknpodo/TWC/TwoComms_Site/twocomms || exit 1

cat > "$REPORT_DIR/02_project_structure.txt" << EOF
=== СТРУКТУРА ПРОЕКТА ===
Рабочая директория: $(pwd)

=== РАЗМЕРЫ ПАПОК ===
$(du -sh * 2>/dev/null | sort -h)

=== КОЛИЧЕСТВО ФАЙЛОВ ===
Всего файлов: $(find . -type f | wc -l)
Python файлов: $(find . -name "*.py" | wc -l)
HTML файлов: $(find . -name "*.html" | wc -l)
CSS файлов: $(find . -name "*.css" | wc -l)
JS файлов: $(find . -name "*.js" | wc -l)
Изображений: $(find media -type f \( -name "*.jpg" -o -name "*.png" -o -name "*.webp" \) 2>/dev/null | wc -l)

=== РАЗМЕР MEDIA ===
$(du -sh media/* 2>/dev/null)
EOF

echo -e "${GREEN}✅ Структура проекта проанализирована${NC}"

# ============================================================================
# 3. GIT СОСТОЯНИЕ
# ============================================================================
echo -e "${YELLOW}[3/15] Проверка Git репозитория...${NC}"

cat > "$REPORT_DIR/03_git_status.txt" << EOF
=== GIT СТАТУС ===
$(git status 2>&1)

=== ПОСЛЕДНИЕ 10 КОММИТОВ ===
$(git log --oneline -10 2>&1)

=== ВЕТКИ ===
$(git branch -a 2>&1)

=== ИЗМЕНЁННЫЕ ФАЙЛЫ ===
$(git diff --stat 2>&1)

=== ПРОВЕРКА НА СЕКРЕТЫ В GIT ===
Файлы .env в Git:
$(git ls-files | grep -E '\.env' || echo "Не найдено")

Большие файлы (>1MB):
$(git ls-files | xargs ls -lh 2>/dev/null | awk '$5 ~ /M/ {print $5, $9}' | head -20)
EOF

echo -e "${GREEN}✅ Git статус проверен${NC}"

# ============================================================================
# 4. PYTHON ОКРУЖЕНИЕ
# ============================================================================
echo -e "${YELLOW}[4/15] Анализ Python окружения...${NC}"

source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate

cat > "$REPORT_DIR/04_python_env.txt" << EOF
=== PYTHON ВЕРСИЯ ===
$(python --version)

=== VIRTUALENV ===
$(which python)

=== УСТАНОВЛЕННЫЕ ПАКЕТЫ ===
$(pip list)

=== УСТАРЕВШИЕ ПАКЕТЫ ===
$(pip list --outdated)

=== УЯЗВИМОСТИ (pip-audit) ===
$(pip-audit 2>&1 || echo "pip-audit не установлен. Установите: pip install pip-audit")
EOF

echo -e "${GREEN}✅ Python окружение проанализировано${NC}"

# ============================================================================
# 5. БАЗА ДАННЫХ
# ============================================================================
echo -e "${YELLOW}[5/15] Анализ базы данных...${NC}"

python << PYEOF > "$REPORT_DIR/05_database_analysis.txt"
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')

import django
django.setup()

from django.db import connection
from django.apps import apps

print("=== БАЗА ДАННЫХ ===")
print(f"Engine: {connection.settings_dict['ENGINE']}")
print(f"Name: {connection.settings_dict['NAME']}")
print(f"Host: {connection.settings_dict.get('HOST', 'localhost')}")
print("")

print("=== МОДЕЛИ ===")
for model in apps.get_models():
    count = model.objects.count()
    print(f"{model.__name__}: {count} записей")
print("")

print("=== ТАБЛИЦЫ И ИНДЕКСЫ ===")
with connection.cursor() as cursor:
    # Получить список таблиц
    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]
    
    for table in tables[:20]:  # Первые 20 таблиц
        print(f"\n--- Таблица: {table} ---")
        cursor.execute(f"SHOW INDEX FROM {table}")
        indexes = cursor.fetchall()
        for idx in indexes:
            print(f"  Index: {idx[2]}, Column: {idx[4]}, Unique: {idx[1]}")
        
        # Размер таблицы
        cursor.execute(f"""
            SELECT 
                table_name,
                ROUND((data_length + index_length) / 1024 / 1024, 2) AS size_mb
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
            AND table_name = '{table}'
        """)
        size_info = cursor.fetchone()
        if size_info:
            print(f"  Размер: {size_info[1]} MB")
PYEOF

echo -e "${GREEN}✅ База данных проанализирована${NC}"

# ============================================================================
# 6. МЕДЛЕННЫЕ ЗАПРОСЫ
# ============================================================================
echo -e "${YELLOW}[6/15] Поиск медленных запросов...${NC}"

python << PYEOF > "$REPORT_DIR/06_slow_queries.txt"
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')

import django
django.setup()

from django.db import connection, reset_queries
from django.conf import settings

# Включить логирование запросов
settings.DEBUG = True

# Импортировать модели
from storefront.models import Product, Category
from orders.models import Order

print("=== ТЕСТ ПРОИЗВОДИТЕЛЬНОСТИ ЗАПРОСОВ ===\n")

# Тест 1: Загрузка всех продуктов
reset_queries()
products = list(Product.objects.all()[:100])
print(f"Тест 1: Product.objects.all()[:100]")
print(f"Запросов: {len(connection.queries)}")
print(f"Время: {sum(float(q['time']) for q in connection.queries):.4f}s")
for i, q in enumerate(connection.queries[:5], 1):
    print(f"  Query {i}: {q['sql'][:100]}... ({q['time']}s)")
print("")

# Тест 2: Продукты с категориями (без оптимизации)
reset_queries()
products = list(Product.objects.all()[:50])
for p in products:
    _ = p.category.name
print(f"Тест 2: Products + Category (N+1)")
print(f"Запросов: {len(connection.queries)}")
print(f"Время: {sum(float(q['time']) for q in connection.queries):.4f}s")
print("")

# Тест 3: Продукты с категориями (с оптимизацией)
reset_queries()
products = list(Product.objects.select_related('category')[:50])
for p in products:
    _ = p.category.name
print(f"Тест 3: Products + Category (select_related)")
print(f"Запросов: {len(connection.queries)}")
print(f"Время: {sum(float(q['time']) for q in connection.queries):.4f}s")
print("")

# Тест 4: Заказы с товарами
reset_queries()
orders = list(Order.objects.all()[:20])
print(f"Тест 4: Orders.objects.all()[:20]")
print(f"Запросов: {len(connection.queries)}")
print(f"Время: {sum(float(q['time']) for q in connection.queries):.4f}s")
print("")

settings.DEBUG = False
PYEOF

echo -e "${GREEN}✅ Медленные запросы найдены${NC}"

# ============================================================================
# 7. СТАТИЧЕСКИЕ ФАЙЛЫ
# ============================================================================
echo -e "${YELLOW}[7/15] Анализ статических файлов...${NC}"

cat > "$REPORT_DIR/07_static_files.txt" << EOF
=== СТАТИЧЕСКИЕ ФАЙЛЫ ===

=== CSS ФАЙЛЫ ===
$(find static staticfiles -name "*.css" -exec ls -lh {} \; 2>/dev/null | awk '{print $5, $9}' | sort -h)

=== ВСЕГО CSS ===
Файлов: $(find static staticfiles -name "*.css" 2>/dev/null | wc -l)
Размер: $(du -sh static/css staticfiles/css 2>/dev/null)
Строк кода: $(find static staticfiles -name "*.css" -exec wc -l {} + 2>/dev/null | tail -1)

=== JS ФАЙЛЫ ===
$(find static staticfiles -name "*.js" -exec ls -lh {} \; 2>/dev/null | awk '{print $5, $9}' | sort -h)

=== ВСЕГО JS ===
Файлов: $(find static staticfiles -name "*.js" 2>/dev/null | wc -l)
Размер: $(du -sh static/js staticfiles/js 2>/dev/null)
Строк кода: $(find static staticfiles -name "*.js" -exec wc -l {} + 2>/dev/null | tail -1)
EOF

echo -e "${GREEN}✅ Статические файлы проанализированы${NC}"

# ============================================================================
# 8. ИЗОБРАЖЕНИЯ
# ============================================================================
echo -e "${YELLOW}[8/15] Анализ изображений...${NC}"

cat > "$REPORT_DIR/08_images_analysis.txt" << EOF
=== АНАЛИЗ ИЗОБРАЖЕНИЙ ===

=== ОБЩАЯ СТАТИСТИКА ===
Всего изображений: $(find media -type f \( -name "*.jpg" -o -name "*.png" -o -name "*.webp" -o -name "*.gif" \) 2>/dev/null | wc -l)
Общий размер: $(du -sh media 2>/dev/null | awk '{print $1}')

=== ПО ФОРМАТАМ ===
JPG: $(find media -name "*.jpg" -o -name "*.jpeg" 2>/dev/null | wc -l) файлов
PNG: $(find media -name "*.png" 2>/dev/null | wc -l) файлов
WebP: $(find media -name "*.webp" 2>/dev/null | wc -l) файлов
GIF: $(find media -name "*.gif" 2>/dev/null | wc -l) файлов

=== ТОП-30 САМЫХ БОЛЬШИХ ИЗОБРАЖЕНИЙ ===
$(find media -type f \( -name "*.jpg" -o -name "*.png" -o -name "*.webp" \) -exec ls -lh {} \; 2>/dev/null | sort -k5 -hr | head -30 | awk '{print $5, $9}')

=== НЕОПТИМИЗИРОВАННЫЕ (>500KB) ===
$(find media -type f \( -name "*.jpg" -o -name "*.png" \) -size +500k -exec ls -lh {} \; 2>/dev/null | awk '{print $5, $9}' | head -50)
EOF

echo -e "${GREEN}✅ Изображения проанализированы${NC}"

# ============================================================================
# 9. ЛОГИ
# ============================================================================
echo -e "${YELLOW}[9/15] Анализ логов...${NC}"

cat > "$REPORT_DIR/09_logs_analysis.txt" << EOF
=== АНАЛИЗ ЛОГОВ ===

=== DJANGO ЛОГИ ===
$(tail -100 django.log 2>/dev/null || echo "Лог не найден")

=== ОШИБКИ В ЛОГАХ ===
$(grep -i "error\|exception\|traceback" django.log 2>/dev/null | tail -50 || echo "Нет ошибок")

=== СИСТЕМНЫЕ ЛОГИ (последние 50 строк) ===
$(tail -50 /var/log/syslog 2>/dev/null || tail -50 /var/log/messages 2>/dev/null || echo "Нет доступа к системным логам")
EOF

echo -e "${GREEN}✅ Логи проанализированы${NC}"

# ============================================================================
# 10. ПРОЦЕССЫ И СЕРВИСЫ
# ============================================================================
echo -e "${YELLOW}[10/15] Проверка процессов и сервисов...${NC}"

cat > "$REPORT_DIR/10_processes.txt" << EOF
=== ПРОЦЕССЫ PYTHON ===
$(ps aux | grep python | grep -v grep)

=== GUNICORN/UWSGI ===
$(ps aux | grep -E "gunicorn|uwsgi" | grep -v grep || echo "Не найдено")

=== NGINX ===
$(ps aux | grep nginx | grep -v grep || echo "Не найдено")

=== REDIS ===
$(ps aux | grep redis | grep -v grep || echo "Не найдено")

=== АКТИВНЫЕ СОЕДИНЕНИЯ ===
$(netstat -tuln | grep -E ":80|:443|:8000|:6379" || ss -tuln | grep -E ":80|:443|:8000|:6379")
EOF

echo -e "${GREEN}✅ Процессы проверены${NC}"

# ============================================================================
# 11. REDIS
# ============================================================================
echo -e "${YELLOW}[11/15] Проверка Redis...${NC}"

cat > "$REPORT_DIR/11_redis.txt" << EOF
=== REDIS СТАТУС ===
$(redis-cli ping 2>&1 || echo "Redis недоступен")

=== REDIS INFO ===
$(redis-cli info 2>&1 | head -50 || echo "Не удалось получить info")

=== REDIS ПАМЯТЬ ===
$(redis-cli info memory 2>&1 || echo "Не удалось получить memory info")

=== КОЛИЧЕСТВО КЛЮЧЕЙ ===
$(redis-cli dbsize 2>&1 || echo "Не удалось получить dbsize")
EOF

echo -e "${GREEN}✅ Redis проверен${NC}"

# ============================================================================
# 12. БЕЗОПАСНОСТЬ
# ============================================================================
echo -e "${YELLOW}[12/15] Проверка безопасности...${NC}"

cat > "$REPORT_DIR/12_security.txt" << EOF
=== ПРОВЕРКА БЕЗОПАСНОСТИ ===

=== ФАЙЛЫ .env ===
$(find . -name ".env*" -type f 2>/dev/null || echo "Не найдено")

=== PERMISSIONS ===
Права на settings.py:
$(ls -la */settings.py 2>/dev/null || ls -la twocomms/settings.py 2>/dev/null)

=== ОТКРЫТЫЕ ПОРТЫ ===
$(netstat -tuln 2>/dev/null || ss -tuln)

=== FIREWALL ===
$(sudo iptables -L 2>/dev/null || echo "Нет доступа к iptables")

=== SSH КОНФИГУРАЦИЯ ===
$(grep -E "PermitRootLogin|PasswordAuthentication|PubkeyAuthentication" /etc/ssh/sshd_config 2>/dev/null || echo "Нет доступа")
EOF

echo -e "${GREEN}✅ Безопасность проверена${NC}"

# ============================================================================
# 13. ДУБЛИРОВАНИЕ КОДА
# ============================================================================
echo -e "${YELLOW}[13/15] Поиск дублирования кода...${NC}"

cat > "$REPORT_DIR/13_code_duplication.txt" << EOF
=== ДУБЛИРОВАНИЕ КОДА ===

=== ПОВТОРЯЮЩИЕСЯ СТРОКИ В PYTHON ===
$(find . -name "*.py" -type f -exec md5sum {} \; 2>/dev/null | sort | uniq -w32 -D | head -50 || echo "Не найдено")

=== ПОХОЖИЕ ФУНКЦИИ ===
$(grep -rn "^def " --include="*.py" . 2>/dev/null | cut -d: -f2 | sort | uniq -c | sort -rn | head -20)

=== БОЛЬШИЕ ФАЙЛЫ (>1000 строк) ===
$(find . -name "*.py" -exec wc -l {} \; 2>/dev/null | sort -rn | head -20)

=== TODO/FIXME КОММЕНТАРИИ ===
$(grep -rn "TODO\|FIXME\|XXX\|HACK" --include="*.py" . 2>/dev/null | head -30)
EOF

echo -e "${GREEN}✅ Дублирование найдено${NC}"

# ============================================================================
# 14. ПРОИЗВОДИТЕЛЬНОСТЬ
# ============================================================================
echo -e "${YELLOW}[14/15] Тест производительности...${NC}"

cat > "$REPORT_DIR/14_performance.txt" << EOF
=== ТЕСТ ПРОИЗВОДИТЕЛЬНОСТИ ===

=== ВРЕМЯ ОТКЛИКА ГЛАВНОЙ СТРАНИЦЫ ===
$(curl -o /dev/null -s -w "Time: %{time_total}s\nSize: %{size_download} bytes\nStatus: %{http_code}\n" https://twocomms.shop/ 2>&1)

=== ВРЕМЯ ОТКЛИКА КАТАЛОГА ===
$(curl -o /dev/null -s -w "Time: %{time_total}s\nSize: %{size_download} bytes\nStatus: %{http_code}\n" https://twocomms.shop/catalog/ 2>&1)

=== ВРЕМЯ ОТКЛИКА API ===
$(curl -o /dev/null -s -w "Time: %{time_total}s\nSize: %{size_download} bytes\nStatus: %{http_code}\n" https://twocomms.shop/cart/summary/ 2>&1)
EOF

echo -e "${GREEN}✅ Производительность протестирована${NC}"

# ============================================================================
# 15. ИТОГОВЫЙ ОТЧЁТ
# ============================================================================
echo -e "${YELLOW}[15/15] Генерация итогового отчёта...${NC}"

cat > "$REPORT_DIR/00_SUMMARY.txt" << EOF
╔══════════════════════════════════════════════════════════════════════════╗
║                    ИТОГОВЫЙ ОТЧЁТ АУДИТА СЕРВЕРА                         ║
╚══════════════════════════════════════════════════════════════════════════╝

Дата аудита: $(date)
Сервер: $(hostname)
Проект: /home/qlknpodo/TWC/TwoComms_Site/twocomms

════════════════════════════════════════════════════════════════════════════

СОЗДАННЫЕ ФАЙЛЫ:
$(ls -1 "$REPORT_DIR")

════════════════════════════════════════════════════════════════════════════

СЛЕДУЮЩИЕ ШАГИ:
1. Проверьте все файлы в папке $REPORT_DIR
2. Скачайте отчёты на локальную машину:
   scp -r user@server:$REPORT_DIR ./
3. Изучите критичные находки
4. Примените рекомендации из отчёта

════════════════════════════════════════════════════════════════════════════
EOF

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    ✅ АУДИТ ЗАВЕРШЁН УСПЕШНО!                            ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "📁 Отчёты сохранены в: ${YELLOW}$REPORT_DIR${NC}"
echo ""
echo "Для скачивания отчётов выполните на локальной машине:"
echo -e "${YELLOW}scp -r qlknpodo@195.191.24.169:/home/qlknpodo/TWC/TwoComms_Site/twocomms/$REPORT_DIR ./${NC}"
echo ""

