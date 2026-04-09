# 🔄 Обновление Google Merchant Feed - Полное Руководство

## 📋 Содержание
1. [Быстрое обновление (одна команда)](#быстрое-обновление)
2. [Полное обновление с проверками](#полное-обновление)
3. [Проверка и настройка CRON](#проверка-cron)
4. [Мониторинг и верификация](#мониторинг)
5. [Troubleshooting](#troubleshooting)

---

## 🚀 Быстрое обновление

### Вариант 1: Одна команда SSH (РЕКОМЕНДУЕТСЯ)

Скопируйте и выполните эту команду в терминале:

```bash
ssh qlknpodo@195.191.24.169 'cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python manage.py generate_google_merchant_feed --output twocomms/static/google_merchant_feed.xml && cp -f twocomms/static/google_merchant_feed.xml media/google-merchant-v3.xml && echo "✓ Feed обновлен!" && ls -lh media/google-merchant-v3.xml && grep -c "<item>" media/google-merchant-v3.xml | xargs -I {} echo "✓ Товаров в feed: {}"'
```

**Что делает эта команда:**
- ✅ Генерирует новый feed с актуальными ценами
- ✅ Копирует в media/google-merchant-v3.xml
- ✅ Показывает размер файла
- ✅ Показывает количество товаров

### Вариант 2: Через скрипт

```bash
# Загрузить скрипт на сервер
scp update_feed_now.sh qlknpodo@195.191.24.169:~/

# Запустить
ssh qlknpodo@195.191.24.169 "bash ~/update_feed_now.sh"
```

---

## 🔧 Полное обновление с проверками

Для полного обновления с проверкой CRON и детальной диагностикой:

```bash
# 1. Загрузить скрипт на сервер
scp update_google_merchant_feed.sh qlknpodo@195.191.24.169:~/

# 2. Запустить с проверками
ssh qlknpodo@195.191.24.169 "bash ~/update_google_merchant_feed.sh"
```

**Этот скрипт:**
- ✅ Обновляет feed
- ✅ Проверяет существующую CRON задачу
- ✅ Предлагает создать/обновить CRON
- ✅ Показывает детальную статистику
- ✅ Проверяет размер и количество товаров

---

## ⏰ Проверка CRON

### Проверить существующие задачи

```bash
ssh qlknpodo@195.191.24.169 "crontab -l | grep -E '(generate_google_merchant_feed|Django)'"
```

**Ожидаемый результат:**
```
# Django: обновление Google Merchant feed (добавлено автоматически)
0 4 * * * cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python manage.py generate_google_merchant_feed --output twocomms/static/google_merchant_feed.xml && cp -f twocomms/static/google_merchant_feed.xml media/google-merchant-v3.xml >> /home/qlknpodo/TWC/TwoComms_Site/twocomms/cron.log 2>&1
```

### Создать/обновить CRON задачу вручную

```bash
ssh qlknpodo@195.191.24.169 << 'ENDSSH'
# Добавляем комментарий и задачу
(crontab -l 2>/dev/null | grep -v "generate_google_merchant_feed" | grep -v "Django: обновление Google Merchant feed"; 
echo "# Django: обновление Google Merchant feed (обновлено $(date +%Y-%m-%d))"; 
echo "0 4 * * * cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python manage.py generate_google_merchant_feed --output twocomms/static/google_merchant_feed.xml && cp -f twocomms/static/google_merchant_feed.xml media/google-merchant-v3.xml >> /home/qlknpodo/TWC/TwoComms_Site/twocomms/cron.log 2>&1") | crontab -
echo "✓ CRON задача обновлена"
crontab -l | grep "generate_google_merchant_feed"
ENDSSH
```

### Удалить CRON задачу (если нужно)

```bash
ssh qlknpodo@195.191.24.169 "crontab -l | grep -v 'generate_google_merchant_feed' | grep -v 'Django: обновление Google Merchant feed' | crontab -"
```

---

## 📊 Мониторинг и Верификация

### 1. Проверить последнее обновление

```bash
ssh qlknpodo@195.191.24.169 "ls -lh /home/qlknpodo/TWC/TwoComms_Site/twocomms/media/google-merchant-v3.xml"
```

### 2. Проверить содержимое feed

```bash
ssh qlknpodo@195.191.24.169 << 'ENDSSH'
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
echo "📊 Статистика Google Merchant Feed:"
echo "=================================="
echo "Файл: media/google-merchant-v3.xml"
ls -lh media/google-merchant-v3.xml
echo ""
echo "Последнее изменение: $(stat -c %y media/google-merchant-v3.xml 2>/dev/null || stat -f '%Sm' media/google-merchant-v3.xml)"
echo ""
PRODUCTS=$(grep -c "<item>" media/google-merchant-v3.xml || echo "0")
echo "✓ Товаров в feed: $PRODUCTS"
echo ""
echo "Примеры товаров:"
grep -A 1 "g:title" media/google-merchant-v3.xml | head -20
ENDSSH
```

### 3. Проверить CRON логи

```bash
ssh qlknpodo@195.191.24.169 "tail -50 /home/qlknpodo/TWC/TwoComms_Site/twocomms/cron.log"
```

### 4. Проверить feed в браузере

Откройте в браузере:
```
https://twocomms.shop/media/google-merchant-v3.xml
```

### 5. Полная верификация (загрузить и запустить скрипт)

```bash
# Загрузить скрипт верификации
scp verify_google_feed.sh qlknpodo@195.191.24.169:~/

# Запустить
ssh qlknpodo@195.191.24.169 "bash ~/verify_google_feed.sh"
```

---

## 🔍 Troubleshooting

### Проблема: Feed не обновляется

**Проверка 1: Убедитесь, что команда работает**
```bash
ssh qlknpodo@195.191.24.169 'cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python manage.py generate_google_merchant_feed --dry-run'
```

**Проверка 2: Проверьте права доступа**
```bash
ssh qlknpodo@195.191.24.169 "ls -la /home/qlknpodo/TWC/TwoComms_Site/twocomms/media/ | grep google-merchant"
```

**Проверка 3: Проверьте место на диске**
```bash
ssh qlknpodo@195.191.24.169 "df -h /home/qlknpodo/TWC/TwoComms_Site/twocomms/"
```

### Проблема: CRON не запускается

**Проверка: Посмотрите логи**
```bash
ssh qlknpodo@195.191.24.169 "tail -100 /home/qlknpodo/TWC/TwoComms_Site/twocomms/cron.log | grep -A 5 -B 5 'error\|Error\|ERROR'"
```

**Решение: Проверьте синтаксис CRON**
```bash
ssh qlknpodo@195.191.24.169 "crontab -l | grep generate_google_merchant_feed | head -1"
```

### Проблема: Неправильные цены в feed

**Проверка: Сравните цены в БД и feed**
```bash
ssh qlknpodo@195.191.24.169 << 'ENDSSH'
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
echo "🔍 Проверка цен..."

# Получить цену первого товара из БД
/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python manage.py shell << 'PYEOF'
from storefront.models import Product
p = Product.objects.first()
if p:
    print(f"БД: {p.title[:50]} - {p.price} UAH (со скидкой: {p.final_price} UAH)")
PYEOF

# Получить цену из feed
echo ""
echo "Feed (первые 3 товара):"
grep -A 2 "g:price" media/google-merchant-v3.xml | head -12
ENDSSH
```

### Проблема: Feed не доступен по URL

**Проверка: Проверьте веб-сервер**
```bash
curl -I https://twocomms.shop/media/google-merchant-v3.xml
```

**Решение: Проверьте настройки Nginx/Apache**
```bash
ssh qlknpodo@195.191.24.169 "grep -r 'media' /etc/nginx/ 2>/dev/null || grep -r 'media' /etc/apache2/ 2>/dev/null"
```

---

## 📈 Рекомендации

### Частота обновления
- **Текущая:** Каждый день в 4:00 утра
- **Рекомендуемая:** 1-2 раза в день (для активного магазина)
- **При изменении цен:** Немедленное обновление

### Изменить время CRON

Для обновления 2 раза в день (4:00 и 16:00):
```bash
ssh qlknpodo@195.191.24.169 << 'ENDSSH'
(crontab -l 2>/dev/null | grep -v "generate_google_merchant_feed" | grep -v "Django: обновление Google Merchant feed"; 
echo "# Django: обновление Google Merchant feed (обновлено $(date +%Y-%m-%d))"; 
echo "0 4,16 * * * cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python manage.py generate_google_merchant_feed --output twocomms/static/google_merchant_feed.xml && cp -f twocomms/static/google_merchant_feed.xml media/google-merchant-v3.xml >> /home/qlknpodo/TWC/TwoComms_Site/twocomms/cron.log 2>&1") | crontab -
echo "✓ CRON обновлен: теперь запускается в 4:00 и 16:00"
ENDSSH
```

### Мониторинг через Google Merchant Center

1. Войдите в [Google Merchant Center](https://merchants.google.com/)
2. Перейдите в **Продукты > Фиды**
3. Проверьте статус фида
4. Просмотрите ошибки (если есть)

### Автоматические уведомления

Добавьте email уведомления при ошибках в CRON:
```bash
# В начало crontab добавьте:
MAILTO=your-email@example.com
```

---

## 📝 Полезные команды

### Просмотр всех CRON задач
```bash
ssh qlknpodo@195.191.24.169 "crontab -l"
```

### Редактирование CRON вручную
```bash
ssh qlknpodo@195.191.24.169 "crontab -e"
```

### Тестовый запуск команды
```bash
ssh qlknpodo@195.191.24.169 'cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python manage.py generate_google_merchant_feed --dry-run'
```

### Backup текущего feed
```bash
ssh qlknpodo@195.191.24.169 "cp /home/qlknpodo/TWC/TwoComms_Site/twocomms/media/google-merchant-v3.xml /home/qlknpodo/google-merchant-backup-$(date +%Y%m%d-%H%M%S).xml && echo 'Backup создан'"
```

---

## ✅ Checklist после обновления

- [ ] Feed успешно сгенерирован
- [ ] Файл скопирован в media/
- [ ] Размер файла адекватный (> 100 KB)
- [ ] Количество товаров соответствует ожиданиям
- [ ] Feed доступен по URL https://twocomms.shop/media/google-merchant-v3.xml
- [ ] CRON задача настроена и работает
- [ ] Логи CRON не содержат ошибок
- [ ] Цены в feed актуальные
- [ ] Google Merchant Center показывает обновленные данные

---

## 🎯 Быстрая справка

| Действие | Команда |
|----------|---------|
| **Обновить feed сейчас** | `ssh qlknpodo@195.191.24.169 'cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python manage.py generate_google_merchant_feed --output twocomms/static/google_merchant_feed.xml && cp -f twocomms/static/google_merchant_feed.xml media/google-merchant-v3.xml'` |
| **Проверить CRON** | `ssh qlknpodo@195.191.24.169 "crontab -l \| grep merchant"` |
| **Посмотреть логи** | `ssh qlknpodo@195.191.24.169 "tail -50 /home/qlknpodo/TWC/TwoComms_Site/twocomms/cron.log"` |
| **Проверить feed** | `curl -I https://twocomms.shop/media/google-merchant-v3.xml` |
| **Подсчитать товары** | `ssh qlknpodo@195.191.24.169 "grep -c '<item>' /home/qlknpodo/TWC/TwoComms_Site/twocomms/media/google-merchant-v3.xml"` |

---

**📞 Поддержка:**
- Management команда: `twocomms/storefront/management/commands/generate_google_merchant_feed.py`
- Логи CRON: `/home/qlknpodo/TWC/TwoComms_Site/twocomms/cron.log`
- URL feed: `https://twocomms.shop/media/google-merchant-v3.xml`

**🔗 Полезные ссылки:**
- [Google Merchant Center](https://merchants.google.com/)
- [Google Merchant Feed Specification](https://support.google.com/merchants/answer/7052112)
- [Crontab Guru](https://crontab.guru/) - помощник по CRON синтаксису

















