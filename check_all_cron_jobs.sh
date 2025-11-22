#!/bin/bash
# ==============================================================================
# ПОЛНАЯ ПРОВЕРКА ВСЕХ CRON JOBS (CPANEL + SYSTEM)
# ==============================================================================
#
# Этот скрипт проверяет ВСЕ настроенные cron задачи:
# - User crontab (через crontab -l)
# - Системные cron файлы
# - Частоту запуска
# - Логи последних запусков
#
# Использование:
#   ssh qlknpodo@195.191.24.169 "bash -s" < check_all_cron_jobs.sh
#
# ==============================================================================

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=============================================="
echo -e "  ПОЛНАЯ ПРОВЕРКА CRON JOBS"
echo -e "==============================================${NC}"
echo ""

# 1. Проверка USER CRONTAB (настройки через cPanel попадают сюда)
echo -e "${YELLOW}[1/6]${NC} Проверка USER CRONTAB (cPanel настройки)..."
echo ""

USER_CRON=$(crontab -l 2>/dev/null)

if [ -z "$USER_CRON" ]; then
    echo -e "${RED}✗ User crontab ПУСТОЙ!${NC}"
    echo "  Это означает что cron jobs не настроены через cPanel или командную строку."
else
    echo -e "${GREEN}✓ User crontab найден${NC}"
    echo ""
    echo -e "${BLUE}Все задачи в user crontab:${NC}"
    echo "=============================================="
    crontab -l | nl
    echo "=============================================="
    echo ""
    
    # Подсчет задач
    TOTAL_JOBS=$(crontab -l | grep -v "^#" | grep -v "^$" | wc -l | tr -d ' ')
    echo -e "Всего активных задач: ${GREEN}$TOTAL_JOBS${NC}"
fi
echo ""

# 2. Поиск задач для Google Merchant Feed
echo -e "${YELLOW}[2/6]${NC} Поиск задач Google Merchant Feed..."
echo ""

MERCHANT_JOBS=$(crontab -l 2>/dev/null | grep -i "google.*merchant\|merchant.*feed\|generate_google_merchant_feed" | grep -v "^#")

if [ -z "$MERCHANT_JOBS" ]; then
    echo -e "${RED}✗ Google Merchant Feed задачи НЕ НАЙДЕНЫ!${NC}"
    echo "  CRON для автообновления feed НЕ настроен!"
else
    echo -e "${GREEN}✓ Найдены задачи для Google Merchant Feed:${NC}"
    echo "=============================================="
    echo "$MERCHANT_JOBS" | nl
    echo "=============================================="
    echo ""
    
    # Анализ расписания каждой задачи
    echo -e "${CYAN}Анализ расписания:${NC}"
    echo ""
    
    COUNTER=1
    while IFS= read -r job; do
        if [ -n "$job" ]; then
            echo -e "${BLUE}Задача #$COUNTER:${NC}"
            echo "$job"
            echo ""
            
            # Извлекаем расписание (первые 5 полей)
            SCHEDULE=$(echo "$job" | awk '{print $1, $2, $3, $4, $5}')
            MINUTE=$(echo "$SCHEDULE" | awk '{print $1}')
            HOUR=$(echo "$SCHEDULE" | awk '{print $2}')
            DAY=$(echo "$SCHEDULE" | awk '{print $3}')
            MONTH=$(echo "$SCHEDULE" | awk '{print $4}')
            WEEKDAY=$(echo "$SCHEDULE" | awk '{print $5}')
            
            echo "  Расписание: $SCHEDULE"
            echo ""
            
            # Интерпретация
            if [ "$MINUTE" = "0" ] && [ "$HOUR" != "*" ] && [ "$DAY" = "*" ] && [ "$MONTH" = "*" ] && [ "$WEEKDAY" = "*" ]; then
                if echo "$HOUR" | grep -q ","; then
                    HOURS=$(echo "$HOUR" | tr ',' ' ')
                    echo -e "  ${GREEN}Интерпретация: Каждый день в $HOURS:00${NC}"
                else
                    echo -e "  ${GREEN}Интерпретация: Каждый день в $HOUR:00${NC}"
                fi
            elif [ "$MINUTE" != "*" ] && [ "$HOUR" = "*" ] && [ "$DAY" = "*" ]; then
                echo -e "  ${YELLOW}Интерпретация: КАЖДЫЙ ЧАС в $MINUTE минут${NC}"
            elif [ "$MINUTE" = "*" ] && [ "$HOUR" = "*" ]; then
                echo -e "  ${RED}Интерпретация: КАЖДУЮ МИНУТУ (слишком часто!)${NC}"
            else
                echo -e "  ${CYAN}Интерпретация: Сложное расписание${NC}"
                echo "  Используйте https://crontab.guru/#$SCHEDULE для расшифровки"
            fi
            echo ""
            
            COUNTER=$((COUNTER + 1))
        fi
    done <<< "$MERCHANT_JOBS"
fi
echo ""

# 3. Проверка других Django задач
echo -e "${YELLOW}[3/6]${NC} Поиск других Django задач..."
echo ""

DJANGO_JOBS=$(crontab -l 2>/dev/null | grep -i "manage.py\|django\|python.*twocomms" | grep -v "^#" | grep -v "merchant")

if [ -z "$DJANGO_JOBS" ]; then
    echo -e "${CYAN}Других Django задач не найдено${NC}"
else
    echo -e "${GREEN}✓ Найдены другие Django задачи:${NC}"
    echo "=============================================="
    echo "$DJANGO_JOBS" | nl
    echo "=============================================="
fi
echo ""

# 4. Проверка логов CRON
echo -e "${YELLOW}[4/6]${NC} Проверка логов CRON..."
echo ""

CRON_LOG="/home/qlknpodo/TWC/TwoComms_Site/twocomms/cron.log"

if [ -f "$CRON_LOG" ]; then
    echo -e "${GREEN}✓ Лог файл найден: $CRON_LOG${NC}"
    
    LOG_SIZE=$(ls -lh "$CRON_LOG" | awk '{print $5}')
    echo "  Размер: $LOG_SIZE"
    echo ""
    
    # Последние 20 строк
    echo -e "${BLUE}Последние 20 строк лога:${NC}"
    echo "=============================================="
    tail -20 "$CRON_LOG"
    echo "=============================================="
    echo ""
    
    # Проверка на ошибки
    ERROR_COUNT=$(grep -ci "error\|failed\|exception\|traceback" "$CRON_LOG" 2>/dev/null || echo "0")
    if [ "$ERROR_COUNT" -gt 0 ]; then
        echo -e "${RED}⚠ Найдено ошибок в логе: $ERROR_COUNT${NC}"
        echo ""
        echo -e "${YELLOW}Последние ошибки:${NC}"
        grep -i "error\|failed\|exception" "$CRON_LOG" | tail -5
        echo ""
    else
        echo -e "${GREEN}✓ Ошибок в логе не найдено${NC}"
    fi
    
    # Подсчет запусков по дням
    echo ""
    echo -e "${CYAN}Частота запусков (последние упоминания merchant):${NC}"
    grep -i "merchant\|generate_google_merchant_feed" "$CRON_LOG" 2>/dev/null | tail -10 | while read -r line; do
        echo "  $line"
    done
    
else
    echo -e "${YELLOW}⚠ Лог файл не найден: $CRON_LOG${NC}"
    echo "  (возможно cron еще не запускался)"
fi
echo ""

# 5. Проверка системных cron файлов (для полноты)
echo -e "${YELLOW}[5/6]${NC} Проверка системных cron директорий..."
echo ""

if [ -d "/var/spool/cron/crontabs" ]; then
    USER_CRON_FILE="/var/spool/cron/crontabs/$(whoami)"
    if [ -f "$USER_CRON_FILE" ]; then
        echo -e "${CYAN}Файл user crontab: $USER_CRON_FILE${NC}"
        ls -lh "$USER_CRON_FILE"
    fi
fi
echo ""

# 6. Рекомендации
echo -e "${YELLOW}[6/6]${NC} Анализ и рекомендации..."
echo ""

MERCHANT_COUNT=$(crontab -l 2>/dev/null | grep -ci "generate_google_merchant_feed" || echo "0")

if [ "$MERCHANT_COUNT" -eq 0 ]; then
    echo -e "${RED}⚠️  КРИТИЧНО: Google Merchant Feed CRON не настроен!${NC}"
    echo ""
    echo "Нужно настроить автообновление feed."
    echo ""
elif [ "$MERCHANT_COUNT" -eq 1 ]; then
    echo -e "${GREEN}✓ Настроена ОДНА задача для Google Merchant Feed (норма)${NC}"
    echo ""
elif [ "$MERCHANT_COUNT" -gt 1 ]; then
    echo -e "${YELLOW}⚠️  ВНИМАНИЕ: Найдено $MERCHANT_COUNT задач для Google Merchant Feed!${NC}"
    echo ""
    echo "Возможно настроены дубликаты. Рекомендуется оставить только одну."
    echo ""
fi

# Проверка частоты
if crontab -l 2>/dev/null | grep -q "^\* .* .* python.*generate_google_merchant_feed"; then
    echo -e "${RED}⚠️  ВНИМАНИЕ: Feed обновляется КАЖДУЮ МИНУТУ - это слишком часто!${NC}"
    echo "Рекомендуется: 1-2 раза в день"
    echo ""
elif crontab -l 2>/dev/null | grep "generate_google_merchant_feed" | grep -q ".* \* .* .* .*"; then
    echo -e "${YELLOW}⚠️  Feed обновляется КАЖДЫЙ ЧАС${NC}"
    echo "Для интернет-магазина это приемлемо, но можно оптимизировать до 2-3 раз в день."
    echo ""
else
    echo -e "${GREEN}✓ Частота обновления feed выглядит нормально${NC}"
    echo ""
fi

# Итоговый отчет
echo -e "${CYAN}=============================================="
echo -e "  ИТОГОВЫЙ ОТЧЕТ"
echo -e "==============================================${NC}"
echo ""

if [ -z "$USER_CRON" ]; then
    echo -e "Статус: ${RED}CRON не настроен${NC}"
else
    echo -e "Статус: ${GREEN}CRON активен${NC}"
    echo "Задач в crontab: $TOTAL_JOBS"
    echo "Задач для Merchant Feed: $MERCHANT_COUNT"
fi

echo ""
echo -e "${BLUE}Для просмотра/редактирования:${NC}"
echo "  crontab -l    # Просмотр"
echo "  crontab -e    # Редактирование"
echo ""
echo -e "${BLUE}Полезные команды:${NC}"
echo "  # Просмотр логов:"
echo "  tail -f $CRON_LOG"
echo ""
echo "  # Ручной запуск обновления:"
echo "  cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && \\"
echo "  /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/python \\"
echo "  manage.py generate_google_merchant_feed \\"
echo "  --output twocomms/static/google_merchant_feed.xml && \\"
echo "  cp -f twocomms/static/google_merchant_feed.xml media/google-merchant-v3.xml"
echo ""

echo -e "${GREEN}Готово! 🎉${NC}"

















