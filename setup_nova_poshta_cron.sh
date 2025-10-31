#!/bin/bash
# ==============================================================================
# НАСТРОЙКА CRON: ПРОВЕРКА СТАТУСОВ NOVA POSHTA КАЖДЫЕ 5 МИНУТ
# ==============================================================================
#
# Этот скрипт настраивает автоматическую проверку статусов посылок
# через API Новой Почты каждые 5 минут
#
# Использование:
#   ssh qlknpodo@195.191.24.169 'bash -s' < setup_nova_poshta_cron.sh
#   или
#   bash setup_nova_poshta_cron.sh (если уже на сервере)
#
# ==============================================================================

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=============================================="
echo -e "  НАСТРОЙКА CRON: NOVA POSHTA TRACKING"
echo -e "==============================================${NC}"
echo ""

# Пути (настраиваются под ваш сервер)
PROJECT_DIR="/home/qlknpodo/TWC/TwoComms_Site/twocomms"
VENV_PYTHON="/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/python"
LOG_FILE="/home/qlknpodo/TWC/TwoComms_Site/twocomms/logs/nova_poshta_cron.log"

# Создаем директорию для логов если её нет
mkdir -p "$(dirname "$LOG_FILE")"

# Показываем текущую настройку
echo -e "${YELLOW}[1/4]${NC} Проверка текущих задач Nova Poshta..."
echo ""
CURRENT_JOBS=$(crontab -l 2>/dev/null | grep -i "update_tracking_statuses\|nova.*poshta" || echo "")

if [ -z "$CURRENT_JOBS" ]; then
    echo -e "${YELLOW}⚠ Задачи для Nova Poshta не найдены${NC}"
else
    echo -e "${BLUE}Найденные задачи:${NC}"
    echo "$CURRENT_JOBS" | nl
    echo ""
fi

# Удаляем старые задачи и добавляем новую
echo -e "${YELLOW}[2/4]${NC} Настройка новой задачи каждые 5 минут..."
echo ""

# Удаляем старые задачи Nova Poshta и добавляем новую
(crontab -l 2>/dev/null | \
    grep -v "update_tracking_statuses" | \
    grep -v "Nova Poshta\|nova.*poshta\|Нова Пошта" | \
    grep -v "^#.*Nova Poshta"; \
echo "# Nova Poshta: автоматическая проверка статусов посылок каждые 5 минут (обновлено $(date +%Y-%m-%d\ %H:%M))"; \
echo "*/5 * * * * cd $PROJECT_DIR && $VENV_PYTHON manage.py update_tracking_statuses >> $LOG_FILE 2>&1") | crontab -

echo -e "${GREEN}✅ CRON задача настроена!${NC}"
echo ""

# Показываем новую настройку
echo -e "${YELLOW}[3/4]${NC} Проверка новой настройки..."
echo ""
echo -e "${CYAN}=============================================="
echo -e "  НОВАЯ НАСТРОЙКА:"
echo -e "==============================================${NC}"
crontab -l | grep -A 2 "update_tracking_statuses"
echo -e "${CYAN}==============================================${NC}"
echo ""

# Интерпретация расписания
echo -e "${BLUE}Интерпретация:${NC}"
echo "  Расписание: */5 * * * * (каждые 5 минут)"
echo "  Команда: python manage.py update_tracking_statuses"
echo "  Лог файл: $LOG_FILE"
echo ""

# Подсчет задач
TOTAL=$(crontab -l | grep -v "^#" | grep -v "^$" | wc -l | tr -d ' ')
NOVA_POSHTA_COUNT=$(crontab -l | grep -c "update_tracking_statuses" || echo "0")

echo -e "${BLUE}Статистика:${NC}"
echo "  Всего CRON задач: $TOTAL"
echo "  Задач Nova Poshta: $NOVA_POSHTA_COUNT"
echo ""

# Проверка и создание лог файла
echo -e "${YELLOW}[4/4]${NC} Проверка лог файла..."
echo ""
if [ -f "$LOG_FILE" ]; then
    echo -e "${GREEN}✓ Лог файл существует: $LOG_FILE${NC}"
    LOG_SIZE=$(ls -lh "$LOG_FILE" | awk '{print $5}')
    echo "  Размер: $LOG_SIZE"
    echo ""
    echo -e "${BLUE}Последние 10 строк лога:${NC}"
    tail -10 "$LOG_FILE" 2>/dev/null || echo "  (лог пуст)"
else
    echo -e "${YELLOW}⚠ Лог файл будет создан при первом запуске: $LOG_FILE${NC}"
    touch "$LOG_FILE"
    chmod 644 "$LOG_FILE"
    echo -e "${GREEN}✓ Лог файл создан${NC}"
fi
echo ""

# Рекомендации
echo -e "${CYAN}=============================================="
echo -e "  РЕКОМЕНДАЦИИ И КОМАНДЫ"
echo -e "==============================================${NC}"
echo ""
echo -e "${BLUE}Полезные команды:${NC}"
echo ""
echo "  # Просмотр всех cron задач:"
echo "  crontab -l"
echo ""
echo "  # Просмотр логов в реальном времени:"
echo "  tail -f $LOG_FILE"
echo ""
echo "  # Ручной запуск проверки статусов:"
echo "  cd $PROJECT_DIR && $VENV_PYTHON manage.py update_tracking_statuses"
echo ""
echo "  # Проверка конкретного заказа:"
echo "  cd $PROJECT_DIR && $VENV_PYTHON manage.py update_tracking_statuses --order-number TWC..."
echo ""
echo "  # Dry-run (показать что будет обновлено без изменений):"
echo "  cd $PROJECT_DIR && $VENV_PYTHON manage.py update_tracking_statuses --dry-run"
echo ""

# Проверка переменных окружения
echo -e "${BLUE}Проверка настроек:${NC}"
echo ""
if [ -f "$PROJECT_DIR/.env" ] || [ -f "$PROJECT_DIR/env" ]; then
    echo -e "${GREEN}✓ Файл .env найден${NC}"
    if grep -q "NOVA_POSHTA_API_KEY" "$PROJECT_DIR/.env" 2>/dev/null || grep -q "NOVA_POSHTA_API_KEY" "$PROJECT_DIR/env" 2>/dev/null; then
        echo -e "${GREEN}✓ NOVA_POSHTA_API_KEY настроен${NC}"
    else
        echo -e "${YELLOW}⚠ NOVA_POSHTA_API_KEY не найден в .env${NC}"
        echo "  Убедитесь что ключ API установлен в переменных окружения"
    fi
else
    echo -e "${YELLOW}⚠ Файл .env не найден${NC}"
    echo "  Переменные окружения могут быть настроены в другом месте"
fi
echo ""

echo -e "${GREEN}=============================================="
echo -e "  ГОТОВО! 🎉"
echo -e "==============================================${NC}"
echo ""
echo -e "${CYAN}CRON задача будет запускаться каждые 5 минут и:${NC}"
echo "  1. Проверять статусы всех заказов с ТТН"
echo "  2. Автоматически обновлять статус заказа при получении"
echo "  3. Менять payment_status на 'paid' при получении"
echo "  4. Отправлять Purchase событие в Facebook Conversions API"
echo "  5. Отправлять уведомления в Telegram админу и пользователю"
echo ""

