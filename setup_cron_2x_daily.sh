#!/bin/bash
# ==============================================================================
# НАСТРОЙКА CRON: 2 РАЗА В ДЕНЬ (4:00 и 16:00)
# ==============================================================================

ssh qlknpodo@195.191.24.169 'bash -s' << 'ENDSSH'

echo "🔄 Настройка CRON на 2 раза в день..."
echo ""

# Показываем текущую настройку
echo "📋 Текущие задачи merchant feed:"
crontab -l 2>/dev/null | grep -i "merchant\|google.*feed" || echo "  (не найдено)"
echo ""

# Удаляем старые задачи merchant feed и добавляем новую
(crontab -l 2>/dev/null | grep -v "generate_google_merchant_feed" | grep -v "Django: обновление Google Merchant feed" | grep -v "Google Merchant feed"; 
echo "# Django: обновление Google Merchant feed 2 раза в день (обновлено $(date +%Y-%m-%d\ %H:%M))"; 
echo "0 4,16 * * * cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python manage.py generate_google_merchant_feed --output twocomms/static/google_merchant_feed.xml && cp -f twocomms/static/google_merchant_feed.xml media/google-merchant-v3.xml >> /home/qlknpodo/TWC/TwoComms_Site/twocomms/cron.log 2>&1") | crontab -

echo "✅ CRON задача обновлена!"
echo ""
echo "=============================================="
echo "📋 НОВАЯ НАСТРОЙКА:"
echo "=============================================="
crontab -l | grep -B 1 "4,16"
echo "=============================================="
echo ""

# Подсчет всех задач
TOTAL=$(crontab -l | grep -v "^#" | grep -v "^$" | wc -l | tr -d ' ')
echo "📊 Всего CRON задач: $TOTAL"
echo ""

# Проверка что именно одна задача merchant
MERCHANT_COUNT=$(crontab -l | grep -c "generate_google_merchant_feed" || echo "0")
echo "📦 Задач Google Merchant Feed: $MERCHANT_COUNT"

if [ "$MERCHANT_COUNT" -eq 1 ]; then
    echo "   ✅ Отлично! Настроена одна задача."
elif [ "$MERCHANT_COUNT" -gt 1 ]; then
    echo "   ⚠️  Внимание! Обнаружено несколько задач - возможны дубликаты."
else
    echo "   ❌ Ошибка! Задача не найдена."
fi
echo ""

# Интерпретация
echo "⏰ Новое расписание:"
echo "   • 4:00 - утреннее обновление feed"
echo "   • 16:00 - вечернее обновление feed"
echo ""

# Следующий запуск
CURRENT_HOUR=$(date +%H | sed 's/^0*//')
if [ -z "$CURRENT_HOUR" ]; then CURRENT_HOUR=0; fi

if [ "$CURRENT_HOUR" -lt 4 ]; then
    HOURS_UNTIL=$((4 - CURRENT_HOUR))
    echo "⏰ Следующий запуск: сегодня в 4:00 (через $HOURS_UNTIL ч.)"
elif [ "$CURRENT_HOUR" -lt 16 ]; then
    HOURS_UNTIL=$((16 - CURRENT_HOUR))
    echo "⏰ Следующий запуск: сегодня в 16:00 (через $HOURS_UNTIL ч.)"
else
    HOURS_UNTIL=$((24 - CURRENT_HOUR + 4))
    echo "⏰ Следующий запуск: завтра в 4:00 (через $HOURS_UNTIL ч.)"
fi
echo ""

# Показать где логи
echo "📝 Логи обновлений:"
echo "   tail -f /home/qlknpodo/TWC/TwoComms_Site/twocomms/cron.log"
echo ""

# Показать URL feed
echo "🌐 URL feed:"
echo "   https://twocomms.shop/media/google-merchant-v3.xml"
echo ""

echo "✅ Настройка завершена успешно!"

ENDSSH

echo ""
echo "=============================================="
echo "  ✅ ГОТОВО!"
echo "=============================================="

















