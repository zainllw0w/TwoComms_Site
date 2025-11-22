#!/bin/bash
# ==============================================================================
# СКРИПТ ВЕРИФИКАЦИИ GOOGLE MERCHANT FEED
# ==============================================================================
# 
# Проверяет корректность и актуальность Google Merchant feed
#
# Использование:
#   bash verify_google_feed.sh
#
# Или через SSH:
#   ssh qlknpodo@195.191.24.169 "bash -s" < verify_google_feed.sh
#
# ==============================================================================

set -e

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Путь к feed
FEED_FILE="/home/qlknpodo/TWC/TwoComms_Site/twocomms/media/google-merchant-v3.xml"
PROJECT_DIR="/home/qlknpodo/TWC/TwoComms_Site/twocomms"
VENV_PYTHON="/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/python"

echo -e "${BLUE}=================================="
echo -e "  ВЕРИФИКАЦИЯ GOOGLE MERCHANT FEED"
echo -e "==================================${NC}"
echo ""

# 1. Проверка существования файла
echo -e "${YELLOW}[1/7]${NC} Проверка существования файла..."
if [ -f "$FEED_FILE" ]; then
    echo -e "${GREEN}✓${NC} Файл найден: $FEED_FILE"
else
    echo -e "${RED}✗${NC} Файл НЕ найден: $FEED_FILE"
    exit 1
fi
echo ""

# 2. Размер файла
echo -e "${YELLOW}[2/7]${NC} Проверка размера файла..."
FILE_SIZE=$(ls -lh "$FEED_FILE" | awk '{print $5}')
FILE_SIZE_BYTES=$(stat -f%z "$FEED_FILE" 2>/dev/null || stat -c%s "$FEED_FILE")

echo -e "Размер: ${GREEN}$FILE_SIZE${NC} ($FILE_SIZE_BYTES bytes)"

if [ "$FILE_SIZE_BYTES" -lt 1000 ]; then
    echo -e "${RED}⚠ Предупреждение: Файл слишком маленький!${NC}"
elif [ "$FILE_SIZE_BYTES" -gt 100000 ]; then
    echo -e "${GREEN}✓${NC} Размер файла нормальный"
else
    echo -e "${YELLOW}⚠${NC} Размер файла подозрительно маленький"
fi
echo ""

# 3. Последнее изменение
echo -e "${YELLOW}[3/7]${NC} Проверка даты последнего обновления..."
LAST_MODIFIED=$(stat -f '%Sm' "$FEED_FILE" 2>/dev/null || stat -c '%y' "$FEED_FILE")
echo -e "Последнее изменение: ${BLUE}$LAST_MODIFIED${NC}"

# Проверка, не старше ли 2 дней
FILE_AGE_SECONDS=$(($(date +%s) - $(stat -f%m "$FEED_FILE" 2>/dev/null || stat -c%Y "$FEED_FILE")))
FILE_AGE_HOURS=$((FILE_AGE_SECONDS / 3600))

if [ "$FILE_AGE_HOURS" -lt 24 ]; then
    echo -e "${GREEN}✓${NC} Файл свежий (обновлен $FILE_AGE_HOURS ч. назад)"
elif [ "$FILE_AGE_HOURS" -lt 48 ]; then
    echo -e "${YELLOW}⚠${NC} Файл обновлялся $FILE_AGE_HOURS ч. назад"
else
    echo -e "${RED}⚠ Предупреждение: Файл не обновлялся $FILE_AGE_HOURS ч. ($((FILE_AGE_HOURS/24)) дней)${NC}"
fi
echo ""

# 4. Валидация XML
echo -e "${YELLOW}[4/7]${NC} Проверка валидности XML..."
if xmllint --noout "$FEED_FILE" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} XML структура валидна"
elif command -v xmllint &> /dev/null; then
    echo -e "${RED}✗${NC} XML невалиден!"
    xmllint --noout "$FEED_FILE" 2>&1 | head -5
else
    echo -e "${YELLOW}⚠${NC} xmllint не установлен, пропускаем XML валидацию"
    # Простая проверка
    if head -1 "$FEED_FILE" | grep -q "<?xml"; then
        echo -e "${GREEN}✓${NC} XML заголовок присутствует"
    else
        echo -e "${RED}✗${NC} XML заголовок отсутствует!"
    fi
fi
echo ""

# 5. Подсчет товаров
echo -e "${YELLOW}[5/7]${NC} Подсчет товаров в feed..."
PRODUCT_COUNT=$(grep -c "<item>" "$FEED_FILE" || echo "0")
echo -e "Товаров в feed: ${GREEN}$PRODUCT_COUNT${NC}"

if [ "$PRODUCT_COUNT" -eq 0 ]; then
    echo -e "${RED}✗${NC} В feed нет товаров!"
elif [ "$PRODUCT_COUNT" -lt 10 ]; then
    echo -e "${YELLOW}⚠${NC} Подозрительно мало товаров"
else
    echo -e "${GREEN}✓${NC} Количество товаров нормальное"
fi
echo ""

# 6. Проверка структуры товаров
echo -e "${YELLOW}[6/7]${NC} Проверка структуры товаров..."

# Подсчет обязательных полей
ID_COUNT=$(grep -c "<g:id>" "$FEED_FILE" || echo "0")
TITLE_COUNT=$(grep -c "<g:title>" "$FEED_FILE" || echo "0")
PRICE_COUNT=$(grep -c "<g:price>" "$FEED_FILE" || echo "0")
LINK_COUNT=$(grep -c "<g:link>" "$FEED_FILE" || echo "0")
IMAGE_COUNT=$(grep -c "<g:image_link>" "$FEED_FILE" || echo "0")

echo -e "  g:id:         $ID_COUNT"
echo -e "  g:title:      $TITLE_COUNT"
echo -e "  g:price:      $PRICE_COUNT"
echo -e "  g:link:       $LINK_COUNT"
echo -e "  g:image_link: $IMAGE_COUNT"

if [ "$ID_COUNT" -eq "$PRODUCT_COUNT" ] && [ "$TITLE_COUNT" -eq "$PRODUCT_COUNT" ] && [ "$PRICE_COUNT" -eq "$PRODUCT_COUNT" ]; then
    echo -e "${GREEN}✓${NC} Все обязательные поля присутствуют"
else
    echo -e "${YELLOW}⚠${NC} Некоторые обязательные поля могут отсутствовать"
fi
echo ""

# 7. Примеры товаров
echo -e "${YELLOW}[7/7]${NC} Примеры товаров из feed..."
echo -e "${BLUE}Первые 3 товара:${NC}"
echo "-------------------------------------------"

# Извлекаем первые 3 названия товаров
grep "<g:title>" "$FEED_FILE" | head -3 | sed 's/.*<g:title>\(.*\)<\/g:title>.*/  • \1/'

echo "-------------------------------------------"
echo ""

# Проверка цен
echo -e "${BLUE}Примеры цен:${NC}"
grep "<g:price>" "$FEED_FILE" | head -5 | sed 's/.*<g:price>\(.*\)<\/g:price>.*/  • \1/'
echo ""

# 8. Сравнение с базой данных
echo -e "${YELLOW}[Бонус]${NC} Сравнение количества товаров с БД..."
cd "$PROJECT_DIR"

DB_PRODUCT_COUNT=$($VENV_PYTHON manage.py shell -c "from storefront.models import Product; print(Product.objects.count())" 2>/dev/null || echo "N/A")

if [ "$DB_PRODUCT_COUNT" != "N/A" ]; then
    echo -e "Товаров в БД: ${BLUE}$DB_PRODUCT_COUNT${NC}"
    
    # В feed товары умножаются на варианты (цвет × размер)
    # Обычно это 5 размеров минимум
    EXPECTED_MIN=$((DB_PRODUCT_COUNT * 5))
    EXPECTED_MAX=$((DB_PRODUCT_COUNT * 10))
    
    echo -e "Ожидается в feed: ${BLUE}$EXPECTED_MIN - $EXPECTED_MAX${NC} (с учетом вариантов)"
    
    if [ "$PRODUCT_COUNT" -ge "$EXPECTED_MIN" ] && [ "$PRODUCT_COUNT" -le "$EXPECTED_MAX" ]; then
        echo -e "${GREEN}✓${NC} Количество соответствует ожиданиям"
    else
        echo -e "${YELLOW}⚠${NC} Количество отличается от ожидаемого"
    fi
else
    echo -e "${YELLOW}⚠${NC} Не удалось получить данные из БД"
fi
echo ""

# 9. Проверка доступности по URL
echo -e "${YELLOW}[Веб-доступность]${NC} Проверка доступности feed через веб..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://twocomms.shop/media/google-merchant-v3.xml" || echo "000")

if [ "$HTTP_STATUS" = "200" ]; then
    echo -e "${GREEN}✓${NC} Feed доступен по URL (HTTP $HTTP_STATUS)"
    echo -e "  ${BLUE}https://twocomms.shop/media/google-merchant-v3.xml${NC}"
elif [ "$HTTP_STATUS" = "000" ]; then
    echo -e "${YELLOW}⚠${NC} Не удалось проверить (возможно, нет curl или нет интернета)"
else
    echo -e "${RED}✗${NC} Feed недоступен (HTTP $HTTP_STATUS)"
fi
echo ""

# Итоговый результат
echo -e "${GREEN}=================================="
echo -e "  ✓ ВЕРИФИКАЦИЯ ЗАВЕРШЕНА"
echo -e "==================================${NC}"
echo ""

# Сводка
echo -e "${BLUE}📊 Сводка:${NC}"
echo "  • Файл: $FEED_FILE"
echo "  • Размер: $FILE_SIZE"
echo "  • Товаров: $PRODUCT_COUNT"
echo "  • Обновлен: $FILE_AGE_HOURS ч. назад"
echo "  • URL: https://twocomms.shop/media/google-merchant-v3.xml"
echo ""

# Рекомендации
if [ "$FILE_AGE_HOURS" -gt 48 ]; then
    echo -e "${YELLOW}💡 Рекомендация: Обновите feed вручную или проверьте CRON${NC}"
    echo ""
fi

if [ "$PRODUCT_COUNT" -eq 0 ]; then
    echo -e "${RED}⚠️  КРИТИЧНО: В feed нет товаров! Требуется немедленное обновление.${NC}"
    echo ""
fi

echo -e "${GREEN}Готово! 🎉${NC}"

















