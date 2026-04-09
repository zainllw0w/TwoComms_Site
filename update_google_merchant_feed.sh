#!/bin/bash
# ==============================================================================
# СКРИПТ ОБНОВЛЕНИЯ GOOGLE MERCHANT FEED И ПРОВЕРКИ CRON
# ==============================================================================
# 
# Этот скрипт обновляет Google Merchant feed и проверяет/настраивает cron задачу
# для автоматического обновления.
#
# Использование:
#   1. Загрузить на сервер: scp update_google_merchant_feed.sh qlknpodo@195.191.24.169:~/
#   2. Запустить: ssh qlknpodo@195.191.24.169 "bash ~/update_google_merchant_feed.sh"
#
# Что делает:
#   - Генерирует Google Merchant feed с актуальными ценами и товарами
#   - Копирует файл в media/google-merchant-v3.xml
#   - Проверяет существующую cron задачу
#   - Создает/обновляет cron задачу если нужно
#
# ==============================================================================

set -e  # Остановить при ошибке

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Константы
PROJECT_DIR="/home/qlknpodo/TWC/TwoComms_Site/twocomms"
VENV_PYTHON="/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python"
CRON_LOG="/home/qlknpodo/TWC/TwoComms_Site/twocomms/cron.log"
OUTPUT_FILE="twocomms/static/google_merchant_feed.xml"
MEDIA_FILE="media/google-merchant-v3.xml"

# Cron задача (запуск каждый день в 4:00 утра)
CRON_COMMAND="0 4 * * * cd $PROJECT_DIR && $VENV_PYTHON manage.py generate_google_merchant_feed --output $OUTPUT_FILE && cp -f $OUTPUT_FILE $MEDIA_FILE >> $CRON_LOG 2>&1"
CRON_COMMENT="# Django: обновление Google Merchant feed (добавлено автоматически $(date +%Y-%m-%d))"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Обновление Google Merchant Feed${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 1. Переход в директорию проекта
echo -e "${YELLOW}[1/5]${NC} Переход в директорию проекта..."
cd "$PROJECT_DIR" || {
    echo -e "${RED}✗ Ошибка: Не удалось перейти в $PROJECT_DIR${NC}"
    exit 1
}
echo -e "${GREEN}✓${NC} Текущая директория: $(pwd)"
echo ""

# 2. Запуск генерации feed
echo -e "${YELLOW}[2/5]${NC} Генерация Google Merchant feed..."
echo -e "${BLUE}Команда: $VENV_PYTHON manage.py generate_google_merchant_feed --output $OUTPUT_FILE${NC}"
echo ""

$VENV_PYTHON manage.py generate_google_merchant_feed --output "$OUTPUT_FILE" 2>&1 | tee /tmp/feed_generation.log

if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓${NC} Feed успешно сгенерирован!"
    
    # Проверить размер файла
    if [ -f "$OUTPUT_FILE" ]; then
        FILE_SIZE=$(ls -lh "$OUTPUT_FILE" | awk '{print $5}')
        echo -e "${GREEN}✓${NC} Размер файла: $FILE_SIZE"
        
        # Подсчитать количество товаров
        PRODUCT_COUNT=$(grep -c "<item>" "$OUTPUT_FILE" || echo "0")
        echo -e "${GREEN}✓${NC} Товаров в feed: $PRODUCT_COUNT"
    fi
else
    echo -e "${RED}✗${NC} Ошибка при генерации feed!"
    exit 1
fi
echo ""

# 3. Копирование в media
echo -e "${YELLOW}[3/5]${NC} Копирование в media директорию..."
cp -f "$OUTPUT_FILE" "$MEDIA_FILE"

if [ -f "$MEDIA_FILE" ]; then
    echo -e "${GREEN}✓${NC} Файл скопирован: $MEDIA_FILE"
    ls -lh "$MEDIA_FILE"
else
    echo -e "${RED}✗${NC} Ошибка: Файл не скопирован!"
    exit 1
fi
echo ""

# 4. Проверка существующих cron задач
echo -e "${YELLOW}[4/5]${NC} Проверка cron задачи..."
EXISTING_CRON=$(crontab -l 2>/dev/null || echo "")

if echo "$EXISTING_CRON" | grep -q "generate_google_merchant_feed"; then
    echo -e "${GREEN}✓${NC} Cron задача уже существует!"
    echo ""
    echo "Текущая задача:"
    echo "$EXISTING_CRON" | grep "generate_google_merchant_feed"
    echo ""
    echo -e "${YELLOW}Обновить cron задачу? (y/n)${NC}"
    read -r UPDATE_CRON
    
    if [[ "$UPDATE_CRON" == "y" ]]; then
        # Удалить старые задачи
        echo -e "${YELLOW}Обновление cron задачи...${NC}"
        NEW_CRON=$(echo "$EXISTING_CRON" | grep -v "generate_google_merchant_feed" | grep -v "Django: обновление Google Merchant feed")
        echo "$NEW_CRON" | crontab -
        
        # Добавить новую
        (crontab -l 2>/dev/null || echo ""; echo "$CRON_COMMENT"; echo "$CRON_COMMAND") | crontab -
        echo -e "${GREEN}✓${NC} Cron задача обновлена"
    fi
else
    echo -e "${YELLOW}⚠${NC}  Cron задача не найдена. Создать? (y/n)"
    read -r CREATE_CRON
    
    if [[ "$CREATE_CRON" == "y" ]]; then
        (crontab -l 2>/dev/null || echo ""; echo "$CRON_COMMENT"; echo "$CRON_COMMAND") | crontab -
        echo -e "${GREEN}✓${NC} Cron задача создана"
    fi
fi
echo ""

# 5. Показать текущие cron задачи
echo -e "${YELLOW}[5/5]${NC} Текущие cron задачи Django:"
echo "-------------------------------------------"
crontab -l | grep -E "(Django:|generate_google_merchant_feed|clearsessions)" || echo "Нет Django cron задач"
echo "-------------------------------------------"
echo ""

# Итоговая информация
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✓ ОБНОВЛЕНИЕ ЗАВЕРШЕНО УСПЕШНО!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Информация:"
echo "  • URL feed: https://twocomms.shop/media/google-merchant-v3.xml"
echo "  • Локальный файл: $PROJECT_DIR/$MEDIA_FILE"
echo "  • Время обновления: Каждый день в 4:00 утра"
echo "  • Лог файл: $CRON_LOG"
echo ""
echo "Для проверки feed в браузере:"
echo -e "  ${BLUE}https://twocomms.shop/media/google-merchant-v3.xml${NC}"
echo ""
echo "Для ручного обновления:"
echo "  cd $PROJECT_DIR && $VENV_PYTHON manage.py generate_google_merchant_feed --output $OUTPUT_FILE && cp -f $OUTPUT_FILE $MEDIA_FILE"
echo ""
echo "Для проверки cron логов:"
echo "  tail -f $CRON_LOG"
echo ""
echo -e "${GREEN}Готово! 🎉${NC}"
















