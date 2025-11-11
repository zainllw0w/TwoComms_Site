#!/bin/bash
# ==============================================================================
# БЫСТРОЕ ОБНОВЛЕНИЕ GOOGLE MERCHANT FEED (БЕЗ ИНТЕРАКТИВНЫХ ЗАПРОСОВ)
# ==============================================================================
# 
# Использование:
#   ssh qlknpodo@195.191.24.169 "bash -s" < update_feed_now.sh
#
# Или через один запрос:
#   ssh qlknpodo@195.191.24.169 'cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/python manage.py generate_google_merchant_feed --output twocomms/static/google_merchant_feed.xml && cp -f twocomms/static/google_merchant_feed.xml media/google-merchant-v3.xml && echo "✓ Feed обновлен успешно!" && ls -lh media/google-merchant-v3.xml'
#
# ==============================================================================

set -e

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}🔄 Обновление Google Merchant feed...${NC}"
echo ""

# Переход в директорию
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms

# Генерация feed
echo -e "${YELLOW}Генерация feed...${NC}"
/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/python manage.py generate_google_merchant_feed --output twocomms/static/google_merchant_feed.xml

# Копирование
echo ""
echo -e "${YELLOW}Копирование в media...${NC}"
cp -f twocomms/static/google_merchant_feed.xml media/google-merchant-v3.xml

# Проверка
echo ""
echo -e "${GREEN}✓ Feed успешно обновлен!${NC}"
echo ""
echo "Информация о файле:"
ls -lh media/google-merchant-v3.xml
echo ""

# Подсчет товаров
PRODUCT_COUNT=$(grep -c "<item>" media/google-merchant-v3.xml || echo "0")
echo -e "${GREEN}✓ Товаров в feed: $PRODUCT_COUNT${NC}"
echo ""
echo -e "${GREEN}URL: https://twocomms.shop/media/google-merchant-v3.xml${NC}"
echo ""















