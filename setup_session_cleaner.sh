#!/bin/bash
# ==============================================================================
# СКРИПТ УСТАНОВКИ АВТОМАТИЧЕСКОЙ ОЧИСТКИ СТАРЫХ СЕССИЙ DJANGO
# ==============================================================================
# 
# Этот скрипт добавляет cron задачу для ежедневной очистки устаревших сессий
# из базы данных Django. Это необходимо для поддержания производительности
# и предотвращения роста таблицы сессий.
#
# Использование:
#   1. Загрузить на сервер: scp setup_session_cleaner.sh qlknpodo@195.191.24.169:~/
#   2. Запустить: ssh qlknpodo@195.191.24.169 "bash ~/setup_session_cleaner.sh"
#
# Что делает:
#   - Создает лог-директорию если её нет
#   - Добавляет cron задачу (если её еще нет)
#   - Проверяет существующие cron задачи
#
# ==============================================================================

set -e  # Остановить при ошибке

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Константы
PROJECT_DIR="/home/qlknpodo/TWC/TwoComms_Site/twocomms"
VENV_PYTHON="/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python"
LOG_DIR="/home/qlknpodo/logs"
LOG_FILE="$LOG_DIR/clearsessions.log"

# Cron задача (запуск каждый день в 3:00 утра)
CRON_COMMAND="0 3 * * * cd $PROJECT_DIR && $VENV_PYTHON manage.py clearsessions >> $LOG_FILE 2>&1"
CRON_COMMENT="# Django: очистка устаревших сессий (добавлено автоматически $(date +%Y-%m-%d))"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Установка очистки сессий Django${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 1. Создать лог-директорию
echo -e "${YELLOW}[1/4]${NC} Создание лог-директории..."
mkdir -p "$LOG_DIR"
echo -e "${GREEN}✓${NC} Лог-директория готова: $LOG_DIR"
echo ""

# 2. Проверить существующие cron задачи
echo -e "${YELLOW}[2/4]${NC} Проверка существующих cron задач..."
EXISTING_CRON=$(crontab -l 2>/dev/null || echo "")

if echo "$EXISTING_CRON" | grep -q "clearsessions"; then
    echo -e "${YELLOW}⚠${NC}  Cron задача для clearsessions уже существует!"
    echo ""
    echo "Текущие задачи clearsessions:"
    echo "$EXISTING_CRON" | grep "clearsessions"
    echo ""
    echo -e "${YELLOW}Хотите заменить? (y/n)${NC}"
    read -r REPLACE
    
    if [[ "$REPLACE" != "y" ]]; then
        echo -e "${RED}Отменено пользователем${NC}"
        exit 0
    fi
    
    # Удалить старые задачи clearsessions
    echo -e "${YELLOW}Удаление старых задач...${NC}"
    NEW_CRON=$(echo "$EXISTING_CRON" | grep -v "clearsessions")
    echo "$NEW_CRON" | crontab -
    echo -e "${GREEN}✓${NC} Старые задачи удалены"
fi
echo ""

# 3. Добавить новую cron задачу
echo -e "${YELLOW}[3/4]${NC} Добавление новой cron задачи..."
(crontab -l 2>/dev/null || echo ""; echo "$CRON_COMMENT"; echo "$CRON_COMMAND") | crontab -
echo -e "${GREEN}✓${NC} Cron задача добавлена"
echo ""

# 4. Проверить результат
echo -e "${YELLOW}[4/4]${NC} Проверка установки..."
echo ""
echo "Текущие cron задачи:"
echo "-------------------------------------------"
crontab -l | grep -A 1 "Django:" || crontab -l
echo "-------------------------------------------"
echo ""

# 5. Тестовый запуск clearsessions
echo -e "${YELLOW}Запустить тестовую очистку сейчас? (y/n)${NC}"
read -r RUN_TEST

if [[ "$RUN_TEST" == "y" ]]; then
    echo -e "${YELLOW}Запуск тестовой очистки...${NC}"
    cd "$PROJECT_DIR"
    
    # Активировать virtualenv и запустить команду
    source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate
    python manage.py clearsessions
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} Тестовая очистка выполнена успешно!"
    else
        echo -e "${RED}✗${NC} Ошибка при выполнении clearsessions"
        exit 1
    fi
fi
echo ""

# Итоговая информация
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✓ УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Информация:"
echo "  • Время запуска: Каждый день в 3:00 утра"
echo "  • Команда: python manage.py clearsessions"
echo "  • Лог файл: $LOG_FILE"
echo "  • Проект: $PROJECT_DIR"
echo ""
echo "Для проверки логов:"
echo "  tail -f $LOG_FILE"
echo ""
echo "Для ручного запуска:"
echo "  cd $PROJECT_DIR && $VENV_PYTHON manage.py clearsessions"
echo ""
echo -e "${GREEN}Готово! 🎉${NC}"
