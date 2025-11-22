#!/bin/bash

# 🔍 Скрипт автоматического анализа изменений
# Дата: 24 октября 2025
# Linear: TWO-6

set -e  # Exit on error

echo "🔍 АНАЛИЗ ИЗМЕНЕНИЙ 23-24 ОКТЯБРЯ"
echo "=================================="
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Директория для отчетов
REPORT_DIR="analysis_reports_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$REPORT_DIR"

echo "📁 Директория отчетов: $REPORT_DIR"
echo ""

# 1. Найти коммиты за период
echo "1️⃣  Поиск коммитов за 23-24 октября..."
git log --since="2025-10-23 00:00" --until="2025-10-24 23:59" \
    --format="%H|%ai|%an|%s" > "$REPORT_DIR/commits_list.txt"

COMMIT_COUNT=$(wc -l < "$REPORT_DIR/commits_list.txt")
echo -e "${GREEN}✅ Найдено коммитов: $COMMIT_COUNT${NC}"
echo ""

# 2. Коммиты с критическими исправлениями
echo "2️⃣  Поиск критических исправлений..."
git log --since="2025-10-23" --format="%H|%s" | \
    grep -iE "(fix|critical|критич|ошибка|error|bug)" > "$REPORT_DIR/critical_fixes.txt" || true

CRITICAL_COUNT=$(wc -l < "$REPORT_DIR/critical_fixes.txt")
echo -e "${YELLOW}⚠️  Критических фиксов: $CRITICAL_COUNT${NC}"
echo ""

# 3. Исправления корзины
echo "3️⃣  Поиск исправлений корзины..."
git log --since="2025-10-23" --format="%H|%s" | \
    grep -iE "(cart|корзин)" > "$REPORT_DIR/cart_fixes.txt" || true

CART_COUNT=$(wc -l < "$REPORT_DIR/cart_fixes.txt")
echo -e "${YELLOW}🛒 Исправлений корзины: $CART_COUNT${NC}"
echo ""

# 4. Исправления checkout
echo "4️⃣  Поиск исправлений checkout..."
git log --since="2025-10-23" --format="%H|%s" | \
    grep -iE "(checkout|monobank|payment|оплат)" > "$REPORT_DIR/checkout_fixes.txt" || true

CHECKOUT_COUNT=$(wc -l < "$REPORT_DIR/checkout_fixes.txt")
echo -e "${YELLOW}💳 Исправлений checkout: $CHECKOUT_COUNT${NC}"
echo ""

# 5. Список измененных файлов
echo "5️⃣  Анализ измененных файлов..."
git diff --name-status HEAD~80 HEAD > "$REPORT_DIR/changed_files.txt"

CHANGED_COUNT=$(wc -l < "$REPORT_DIR/changed_files.txt")
echo -e "${GREEN}📝 Измененных файлов: $CHANGED_COUNT${NC}"
echo ""

# 6. Критические файлы Python
echo "6️⃣  Фильтрация критических Python файлов..."
git diff --name-status HEAD~80 HEAD | \
    grep -E "\.(py)$" | \
    grep -E "(views|models|serializers|urls|settings|middleware)" \
    > "$REPORT_DIR/critical_python_files.txt" || true

CRITICAL_PY_COUNT=$(wc -l < "$REPORT_DIR/critical_python_files.txt")
echo -e "${YELLOW}🐍 Критических Python файлов: $CRITICAL_PY_COUNT${NC}"
echo ""

# 7. Diff для критических файлов
echo "7️⃣  Создание diff для критических файлов..."

CRITICAL_FILES=(
    "twocomms/storefront/views/cart.py"
    "twocomms/storefront/views/checkout.py"
    "twocomms/storefront/views/utils.py"
    "twocomms/storefront/serializers.py"
    "twocomms/storefront/models.py"
    "twocomms/twocomms/settings.py"
)

for file in "${CRITICAL_FILES[@]}"; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        echo "  📄 Анализ $filename..."
        git log --oneline -p --since="2025-10-23" "$file" > "$REPORT_DIR/diff_$filename.txt" 2>/dev/null || echo "Файл не изменялся"
    fi
done
echo ""

# 8. Статистика изменений по файлам
echo "8️⃣  Статистика изменений..."
git diff --stat HEAD~80 HEAD > "$REPORT_DIR/diff_stats.txt"
echo -e "${GREEN}✅ Статистика сохранена${NC}"
echo ""

# 9. Поиск IndentationError и синтаксических ошибок
echo "9️⃣  Поиск упоминаний ошибок в коммитах..."
git log --since="2025-10-23" --format="%H|%s" | \
    grep -iE "(IndentationError|SyntaxError|ImportError|NameError)" > "$REPORT_DIR/syntax_errors.txt" || true

SYNTAX_COUNT=$(wc -l < "$REPORT_DIR/syntax_errors.txt")
if [ "$SYNTAX_COUNT" -gt 0 ]; then
    echo -e "${RED}❌ Найдено упоминаний синтаксических ошибок: $SYNTAX_COUNT${NC}"
else
    echo -e "${GREEN}✅ Упоминаний синтаксических ошибок не найдено${NC}"
fi
echo ""

# 10. Merge конфликты
echo "🔟 Поиск merge коммитов..."
git log --since="2025-10-23" --merges --format="%H|%s" > "$REPORT_DIR/merge_commits.txt" || true

MERGE_COUNT=$(wc -l < "$REPORT_DIR/merge_commits.txt")
echo -e "${YELLOW}🔀 Merge коммитов: $MERGE_COUNT${NC}"
echo ""

# 11. Найти последний "хороший" коммит (без слов fix, critical в названии)
echo "1️⃣1️⃣  Поиск последнего стабильного коммита..."
git log --since="2025-10-23 00:00" --until="2025-10-23 12:00" --format="%H|%ai|%s" | \
    grep -viE "(fix|critical|критич|ошибка)" | head -5 > "$REPORT_DIR/stable_commits.txt" || true

STABLE_COUNT=$(wc -l < "$REPORT_DIR/stable_commits.txt")
if [ "$STABLE_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✅ Найдено потенциально стабильных коммитов: $STABLE_COUNT${NC}"
    echo "Первые кандидаты:"
    head -3 "$REPORT_DIR/stable_commits.txt"
else
    echo -e "${YELLOW}⚠️  Стабильные коммиты не найдены${NC}"
fi
echo ""

# 12. Создание summary отчета
echo "1️⃣2️⃣  Создание итогового отчета..."

cat > "$REPORT_DIR/SUMMARY_REPORT.md" << EOF
# 📊 SUMMARY ОТЧЕТ ОБ ИЗМЕНЕНИЯХ

**Дата анализа:** $(date)
**Период:** 23-24 октября 2025

---

## 📈 СТАТИСТИКА

- **Всего коммитов:** $COMMIT_COUNT
- **Критических фиксов:** $CRITICAL_COUNT
- **Исправлений корзины:** $CART_COUNT
- **Исправлений checkout:** $CHECKOUT_COUNT
- **Измененных файлов:** $CHANGED_COUNT
- **Критических Python файлов:** $CRITICAL_PY_COUNT
- **Merge коммитов:** $MERGE_COUNT
- **Упоминаний ошибок:** $SYNTAX_COUNT

---

## 🚨 КРИТИЧЕСКИЕ НАБЛЮДЕНИЯ

### Проблемы с корзиной ($CART_COUNT исправлений):
$(cat "$REPORT_DIR/cart_fixes.txt" | head -10 | sed 's/^/- /')

### Проблемы с checkout ($CHECKOUT_COUNT исправлений):
$(cat "$REPORT_DIR/checkout_fixes.txt" | head -10 | sed 's/^/- /')

### Синтаксические ошибки ($SYNTAX_COUNT упоминаний):
$(cat "$REPORT_DIR/syntax_errors.txt" | sed 's/^/- /')

---

## 📝 КРИТИЧЕСКИЕ ФАЙЛЫ

\`\`\`
$(cat "$REPORT_DIR/critical_python_files.txt" | head -20)
\`\`\`

---

## 🎯 РЕКОМЕНДАЦИИ

1. **Проверить критические файлы:**
   - twocomms/storefront/views/cart.py
   - twocomms/storefront/views/checkout.py
   - twocomms/storefront/views/utils.py

2. **Откатить на стабильную версию:**
$(cat "$REPORT_DIR/stable_commits.txt" | head -3 | awk -F'|' '{print "   - " $1 " | " $2 " | " $3}')

3. **Провести тестирование:**
   - Корзина (add, update, remove)
   - Checkout (form, payment)
   - Chrome DevTools проверка

---

## 📁 ФАЙЛЫ ОТЧЕТА

- \`commits_list.txt\` - все коммиты
- \`critical_fixes.txt\` - критические исправления
- \`cart_fixes.txt\` - исправления корзины
- \`checkout_fixes.txt\` - исправления checkout
- \`changed_files.txt\` - измененные файлы
- \`critical_python_files.txt\` - критические Python файлы
- \`diff_*.txt\` - diff для каждого файла
- \`syntax_errors.txt\` - синтаксические ошибки
- \`merge_commits.txt\` - merge коммиты
- \`stable_commits.txt\` - стабильные коммиты

---

**Создано:** $(date)
**Скрипт:** analyze_changes.sh
EOF

echo -e "${GREEN}✅ Итоговый отчет создан: $REPORT_DIR/SUMMARY_REPORT.md${NC}"
echo ""

# 13. Вывод итогов
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ АНАЛИЗ ЗАВЕРШЕН"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📁 Все отчеты сохранены в: $REPORT_DIR/"
echo ""
echo "📊 Основные метрики:"
echo "   - Коммитов: $COMMIT_COUNT"
echo "   - Критических фиксов: $CRITICAL_COUNT ($(echo "scale=1; $CRITICAL_COUNT*100/$COMMIT_COUNT" | bc)%)"
echo "   - Исправлений корзины: $CART_COUNT"
echo "   - Исправлений checkout: $CHECKOUT_COUNT"
echo ""

if [ "$CRITICAL_COUNT" -gt 20 ]; then
    echo -e "${RED}⚠️  ВНИМАНИЕ: Большое количество критических исправлений!${NC}"
    echo -e "${RED}   Это указывает на серьезные проблемы после миграции.${NC}"
    echo ""
fi

if [ "$CART_COUNT" -gt 10 ]; then
    echo -e "${YELLOW}⚠️  ВНИМАНИЕ: Корзина исправлялась $CART_COUNT раз!${NC}"
    echo -e "${YELLOW}   Рекомендуется откат этого модуля.${NC}"
    echo ""
fi

echo "📖 Следующие шаги:"
echo "   1. Прочитать: $REPORT_DIR/SUMMARY_REPORT.md"
echo "   2. Проверить: $REPORT_DIR/stable_commits.txt"
echo "   3. Выполнить: Chrome DevTools тестирование"
echo "   4. Откатить: критические файлы (если необходимо)"
echo ""
echo "🔗 Linear: TWO-6"
echo "📋 Чеклист: PRIORITY_CHECKLIST.md"
echo "📚 Анализ: CRITICAL_ROLLBACK_ANALYSIS.md"
echo ""
echo -e "${GREEN}🎯 Готово к действию!${NC}"


















