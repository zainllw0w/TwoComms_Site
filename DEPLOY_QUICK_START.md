# ⚡ Быстрый деплой - Шпаргалка

## 🔄 Обновление проекта (5 минут)

```bash
# 1. Подключиться к серверу
ssh qlknpodo@195.191.24.169
# Пароль: [REDACTED_SSH_PASSWORD]

# 2. Активировать окружение и перейти в проект
source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms

# 3. Получить изменения
git pull origin main

# 4. Перезапустить веб-сервер
sudo systemctl restart gunicorn

# 5. Проверить статус
sudo systemctl status gunicorn
```

---

## 🔄 Форсировать обновление фида (1 команда)

```bash
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate && /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/python manage.py generate_google_merchant_feed --output twocomms/static/google_merchant_feed.xml && cp -f twocomms/static/google_merchant_feed.xml media/google-merchant-v3.xml && echo "✅ ГОТОВО!" && ls -lh media/google-merchant-v3.xml && grep -c "<item>" media/google-merchant-v3.xml | xargs -I {} echo "📦 Товаров: {}"
```

---

## ✅ Быстрая проверка Meta Pixel (3 шага)

### 1. Открыть Events Manager
- [Facebook Events Manager](https://business.facebook.com/events_manager2/)
- Test Events → События в реальном времени

### 2. Проверить ViewContent
- Открыть товар на сайте
- В Events Manager должно появиться `ViewContent`
- Проверить `content_ids` (например: `["TC-0007-BLK-M"]`)

### 3. Проверить AddToCart → Purchase
- Добавить в корзину
- Оформить тестовый заказ
- Проверить, что `content_ids` в Purchase совпадает с ViewContent/AddToCart

---

## 🔍 Проверка соответствия с фидом

**Фид:** `https://twocomms.shop/media/google-merchant-v3.xml`

**Проверка:**
1. Открыть фид в браузере
2. Найти товар по его ID
3. Проверить, что `<g:id>TC-0007-BLK-M</g:id>` совпадает с `content_ids` в событиях

✅ **Должно совпадать точно!**

---

## 📝 Формат content_ids

```
TC-{product_id:04d}-{COLOR_SLUG}-{SIZE}
```

**Примеры:**
- `TC-0007-BLK-M` (товар 7, черный, размер M)
- `TC-0012-CV2-L` (товар 12, вариант 2, размер L)

---

**Полная инструкция:** см. `DEPLOYMENT_AND_META_PIXEL_CHECKLIST.md`

















