#!/bin/bash
# Скрипт для настройки автоматических email отчетов UTM Dispatcher
# Запускать от имени пользователя, под которым работает Django

set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}UTM Dispatcher - Настройка Email Отчетов${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Определяем пути
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$SCRIPT_DIR/twocomms"
VENV_DIR="$SCRIPT_DIR/.venv"
MANAGE_PY="$PROJECT_DIR/manage.py"

# Проверяем наличие виртуального окружения
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${RED}✗ Виртуальное окружение не найдено: $VENV_DIR${NC}"
    echo -e "${YELLOW}Попробуйте путь к Python напрямую или укажите правильный путь${NC}"
    exit 1
fi

# Активируем виртуальное окружение
source "$VENV_DIR/bin/activate"

# Проверяем manage.py
if [ ! -f "$MANAGE_PY" ]; then
    echo -e "${RED}✗ manage.py не найден: $MANAGE_PY${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Окружение настроено${NC}"
echo ""

# Запрашиваем email для отчетов
echo -e "${YELLOW}Введите email адреса для получения отчетов (через запятую):${NC}"
read -p "Email: " EMAILS

if [ -z "$EMAILS" ]; then
    echo -e "${RED}✗ Email не может быть пустым${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Выберите частоту отправки отчетов:${NC}"
echo "1) Ежедневно (сегодняшняя статистика)"
echo "2) Еженедельно по понедельникам (недельная статистика)"
echo "3) Ежемесячно 1-го числа (месячная статистика)"
read -p "Выбор (1-3): " FREQUENCY

case $FREQUENCY in
    1)
        CRON_SCHEDULE="0 9 * * *"  # Каждый день в 9:00
        PERIOD="today"
        DESCRIPTION="ежедневно в 9:00"
        ;;
    2)
        CRON_SCHEDULE="0 9 * * 1"  # Каждый понедельник в 9:00
        PERIOD="week"
        DESCRIPTION="еженедельно по понедельникам в 9:00"
        ;;
    3)
        CRON_SCHEDULE="0 9 1 * *"  # 1-го числа каждого месяца в 9:00
        PERIOD="month"
        DESCRIPTION="ежемесячно 1-го числа в 9:00"
        ;;
    *)
        echo -e "${RED}✗ Неверный выбор${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${YELLOW}Прикреплять CSV файлы к отчету? (y/n):${NC}"
read -p "Выбор: " ATTACH_CSV

if [ "$ATTACH_CSV" = "y" ] || [ "$ATTACH_CSV" = "Y" ]; then
    CSV_FLAG="--attach-csv"
else
    CSV_FLAG=""
fi

# Команда для cron
CRON_COMMAND="cd $SCRIPT_DIR && $VENV_DIR/bin/python $MANAGE_PY send_utm_report --period $PERIOD --recipients \"$EMAILS\" $CSV_FLAG >> $SCRIPT_DIR/logs/utm_email_reports.log 2>&1"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Настройка завершена!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Добавьте следующую строку в crontab:${NC}"
echo ""
echo "$CRON_SCHEDULE $CRON_COMMAND"
echo ""
echo -e "${YELLOW}Для редактирования crontab выполните:${NC}"
echo "crontab -e"
echo ""
echo -e "${YELLOW}Отчеты будут отправляться:${NC} $DESCRIPTION"
echo -e "${YELLOW}Получатели:${NC} $EMAILS"
echo -e "${YELLOW}Период:${NC} $PERIOD"
echo ""

# Предлагаем тестовую отправку
echo -e "${YELLOW}Отправить тестовый отчет сейчас? (y/n):${NC}"
read -p "Выбор: " TEST_SEND

if [ "$TEST_SEND" = "y" ] || [ "$TEST_SEND" = "Y" ]; then
    echo ""
    echo -e "${GREEN}Отправка тестового отчета...${NC}"
    python "$MANAGE_PY" send_utm_report --period "$PERIOD" --recipients "$EMAILS" $CSV_FLAG
    echo ""
    echo -e "${GREEN}✓ Тестовый отчет отправлен!${NC}"
    echo -e "${YELLOW}Проверьте почту: $EMAILS${NC}"
else
    echo ""
    echo -e "${GREEN}✓ Настройка сохранена${NC}"
    echo -e "${YELLOW}Не забудьте добавить команду в crontab!${NC}"
fi

echo ""
echo -e "${GREEN}Готово!${NC}"
