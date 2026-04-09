#!/bin/bash
# ==============================================================================
# СКРИПТ ПРОВЕРКИ CRON ДЛЯ GOOGLE MERCHANT FEED
# ==============================================================================
#
# Быстрая проверка состояния CRON задачи для обновления feed
#
# Использование:
#   bash check_merchant_cron.sh
#
# Или через SSH:
#   ssh qlknpodo@195.191.24.169 "bash -s" < check_merchant_cron.sh
#
# ==============================================================================

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

CRON_LOG="/home/qlknpodo/TWC/TwoComms_Site/twocomms/cron.log"

echo -e "${BLUE}======================================"
echo -e "  ПРОВЕРКА CRON: Google Merchant Feed"
echo -e "======================================${NC}"
echo ""

# 1. Проверка наличия CRON задачи
echo -e "${YELLOW}[1/4]${NC} Проверка CRON задачи..."
CRON_EXISTS=$(crontab -l 2>/dev/null | grep -c "generate_google_merchant_feed" || echo "0")

if [ "$CRON_EXISTS" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} CRON задача найдена"
    echo ""
    echo -e "${BLUE}Текущая задача:${NC}"
    echo "-------------------------------------------"
    crontab -l | grep -B 1 "generate_google_merchant_feed"
    echo "-------------------------------------------"
else
    echo -e "${RED}✗${NC} CRON задача НЕ найдена!"
    echo ""
    echo -e "${YELLOW}💡 Совет: Создайте CRON задачу командой:${NC}"
    echo ""
    echo "(crontab -l 2>/dev/null; echo '# Django: обновление Google Merchant feed'; echo '0 4 * * * cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python manage.py generate_google_merchant_feed --output twocomms/static/google_merchant_feed.xml && cp -f twocomms/static/google_merchant_feed.xml media/google-merchant-v3.xml >> /home/qlknpodo/TWC/TwoComms_Site/twocomms/cron.log 2>&1') | crontab -"
    echo ""
fi
echo ""

# 2. Расписание CRON
if [ "$CRON_EXISTS" -gt 0 ]; then
    echo -e "${YELLOW}[2/4]${NC} Расписание запуска..."
    
    CRON_SCHEDULE=$(crontab -l | grep "generate_google_merchant_feed" | grep -v "^#" | awk '{print $1, $2, $3, $4, $5}')
    echo -e "Расписание: ${BLUE}$CRON_SCHEDULE${NC}"
    
    # Расшифровка
    MINUTE=$(echo "$CRON_SCHEDULE" | awk '{print $1}')
    HOUR=$(echo "$CRON_SCHEDULE" | awk '{print $2}')
    
    if [ "$HOUR" != "*" ] && [ "$MINUTE" != "*" ]; then
        echo -e "Интерпретация: ${GREEN}Каждый день в $HOUR:$(printf "%02d" $MINUTE)${NC}"
    else
        echo -e "Интерпретация: ${YELLOW}Сложное расписание (см. crontab)${NC}"
    fi
    
    echo ""
    echo -e "${BLUE}💡 Используйте https://crontab.guru/ для расшифровки${NC}"
    echo ""
fi

# 3. Проверка логов
echo -e "${YELLOW}[3/4]${NC} Проверка логов..."

if [ -f "$CRON_LOG" ]; then
    echo -e "${GREEN}✓${NC} Лог файл найден: $CRON_LOG"
    
    LOG_SIZE=$(ls -lh "$CRON_LOG" | awk '{print $5}')
    echo -e "Размер лога: ${BLUE}$LOG_SIZE${NC}"
    echo ""
    
    # Последние записи
    echo -e "${BLUE}Последние 10 строк лога:${NC}"
    echo "-------------------------------------------"
    tail -10 "$CRON_LOG" 2>/dev/null || echo "(лог пустой)"
    echo "-------------------------------------------"
    echo ""
    
    # Проверка на ошибки
    ERROR_COUNT=$(grep -ci "error\|failed\|exception" "$CRON_LOG" 2>/dev/null || echo "0")
    
    if [ "$ERROR_COUNT" -gt 0 ]; then
        echo -e "${RED}⚠ Найдено ошибок в логе: $ERROR_COUNT${NC}"
        echo ""
        echo -e "${YELLOW}Последние ошибки:${NC}"
        grep -i "error\|failed\|exception" "$CRON_LOG" | tail -5
        echo ""
    else
        echo -e "${GREEN}✓${NC} Ошибок в логе не найдено"
    fi
    
else
    echo -e "${YELLOW}⚠${NC} Лог файл не найден: $CRON_LOG"
    echo "  (возможно, CRON еще не запускался)"
fi
echo ""

# 4. Следующий запуск
if [ "$CRON_EXISTS" -gt 0 ]; then
    echo -e "${YELLOW}[4/4]${NC} Оценка следующего запуска..."
    
    CURRENT_HOUR=$(date +%H)
    CURRENT_MINUTE=$(date +%M)
    
    if [ "$HOUR" != "*" ]; then
        HOUR_NUM=$((10#$HOUR))
        CURRENT_HOUR_NUM=$((10#$CURRENT_HOUR))
        
        if [ "$CURRENT_HOUR_NUM" -lt "$HOUR_NUM" ]; then
            HOURS_UNTIL=$((HOUR_NUM - CURRENT_HOUR_NUM))
            echo -e "Следующий запуск: ${GREEN}через ~$HOURS_UNTIL ч.${NC}"
        else
            HOURS_UNTIL=$((24 - CURRENT_HOUR_NUM + HOUR_NUM))
            echo -e "Следующий запуск: ${GREEN}через ~$HOURS_UNTIL ч. (завтра)${NC}"
        fi
    else
        echo -e "${YELLOW}Невозможно точно определить (сложное расписание)${NC}"
    fi
fi
echo ""

# Итог
echo -e "${GREEN}======================================"
echo -e "  ✓ ПРОВЕРКА ЗАВЕРШЕНА"
echo -e "======================================${NC}"
echo ""

# Быстрые команды
echo -e "${BLUE}📝 Полезные команды:${NC}"
echo ""
echo "Просмотр всех CRON задач:"
echo "  crontab -l"
echo ""
echo "Редактирование CRON:"
echo "  crontab -e"
echo ""
echo "Просмотр логов в реальном времени:"
echo "  tail -f $CRON_LOG"
echo ""
echo "Ручной запуск обновления:"
echo "  cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python manage.py generate_google_merchant_feed --output twocomms/static/google_merchant_feed.xml && cp -f twocomms/static/google_merchant_feed.xml media/google-merchant-v3.xml"
echo ""

if [ "$CRON_EXISTS" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  ВНИМАНИЕ: CRON задача не настроена! Feed не будет обновляться автоматически.${NC}"
    echo ""
fi

echo -e "${GREEN}Готово! 🎉${NC}"
















