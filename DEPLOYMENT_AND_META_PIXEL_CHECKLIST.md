# 🚀 Инструкция по деплою и проверке Meta Pixel

## 📋 Содержание
1. [Обновление боевого проекта](#обновление-боевого-проекта)
2. [Форсирование пересъёма фида](#форсирование-пересъёма-фида)
3. [Чек-лист проверки Meta Pixel событий](#чек-лист-проверки-meta-pixel-событий)

---

## 🔄 Обновление боевого проекта

### Шаг 1: Подключение к серверу

Если у вас есть доступ через SSH напрямую (не через ограничения политики), используйте:

```bash
ssh qlknpodo@195.191.24.169
```

**Пароль:** `[REDACTED_SSH_PASSWORD]`

### Шаг 2: Активация виртуального окружения и переход в директорию проекта

```bash
source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
```

### Шаг 3: Получение последних изменений из репозитория

```bash
git pull origin main
```

**Ожидаемый результат:** 
- Изменения будут получены успешно
- Возможны изменения в файлах:
  - `twocomms/storefront/models.py`
  - `twocomms/storefront/utils/analytics_helpers.py`
  - `twocomms/storefront/views.py`
  - `twocomms/storefront/views/cart.py`
  - `twocomms/twocomms_django_theme/static/js/analytics-loader.js`
  - `twocomms/twocomms_django_theme/static/js/main.js`
  - `twocomms/twocomms_django_theme/templates/base.html`
  - `twocomms/twocomms_django_theme/templates/pages/cart.html`
  - `twocomms/twocomms_django_theme/templates/pages/order_success.html`
  - `twocomms/twocomms_django_theme/templates/pages/product_detail.html`
  - И другие файлы шаблонов

### Шаг 4: Проверка изменений (опционально)

```bash
git status
git log -5 --oneline
```

### Шаг 5: Перезапуск веб-сервера (если используется systemd)

```bash
# Проверить статус службы
sudo systemctl status gunicorn

# Перезапустить службу
sudo systemctl restart gunicorn

# Проверить логи
sudo journalctl -u gunicorn -f --lines=50
```

**Или**, если используется другой метод запуска (через supervisor, screen, tmux и т.д.), найдите и перезапустите соответствующий процесс.

### Шаг 6: Проверка работоспособности

Откройте в браузере:
- Главная страница: `https://twocomms.shop`
- Страница товара: `https://twocomms.shop/catalog/...`
- Корзина: `https://twocomms.shop/cart/`

Убедитесь, что:
- ✅ Сайт загружается без ошибок
- ✅ Товары отображаются корректно
- ✅ Корзина работает

---

## 🔄 Форсирование пересъёма фида

### Вариант 1: Форсировать пересъём СЕЙЧАС (рекомендуется)

**Если Meta должен увидеть актуальные ID немедленно**, выполните:

```bash
# На сервере (после активации виртуального окружения)
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms

# Генерация нового фида
/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/python manage.py generate_google_merchant_feed --output twocomms/static/google_merchant_feed.xml

# Копирование в media директорию (откуда отдается фид)
cp -f twocomms/static/google_merchant_feed.xml media/google-merchant-v3.xml

# Проверка результата
echo "✅ Feed обновлен!"
ls -lh media/google-merchant-v3.xml
grep -c "<item>" media/google-merchant-v3.xml | xargs -I {} echo "📦 Товаров в feed: {}"
```

**Одна команда (копируйте целиком):**
```bash
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate && /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/python manage.py generate_google_merchant_feed --output twocomms/static/google_merchant_feed.xml && cp -f twocomms/static/google_merchant_feed.xml media/google-merchant-v3.xml && echo "✅ ГОТОВО!" && ls -lh media/google-merchant-v3.xml && grep -c "<item>" media/google-merchant-v3.xml | xargs -I {} echo "📦 Товаров в feed: {}"
```

### Вариант 2: Дождаться планового обновления

Плановое обновление фида настроено через CRON:
- **Расписание:** 2 раза в день (04:00 и 16:00)
- **Команда:** автоматически запускается `generate_google_merchant_feed`

**Проверка CRON задачи:**
```bash
crontab -l | grep "generate_google_merchant_feed"
```

**Просмотр логов последнего обновления:**
```bash
tail -20 /home/qlknpodo/TWC/TwoComms_Site/twocomms/cron.log | grep -i merchant
```

### Проверка доступности фида

После обновления фида проверьте его доступность:

**URL фида:** `https://twocomms.shop/media/google-merchant-v3.xml`

Откройте в браузере и убедитесь:
- ✅ Файл доступен
- ✅ XML валидный (можно открыть в браузере или проверить валидность)
- ✅ Содержит актуальные товары

**Проверка конкретного offer_id в фиде:**
```bash
# На сервере
grep -o "TC-[0-9]*-[A-Z]*-[A-Z]*" /home/qlknpodo/TWC/TwoComms_Site/twocomms/media/google-merchant-v3.xml | head -10
```

---

## ✅ Чек-лист проверки Meta Pixel событий

### 📊 Важно: Формат content_ids

**Формат offer_id в фиде и событиях:**
```
TC-{product_id:04d}-{COLOR_SLUG}-{SIZE}
```

**Примеры:**
- `TC-0007-BLK-M` (товар ID 7, цвет "BLK", размер M)
- `TC-0012-CV2-L` (товар ID 12, цветовой вариант 2, размер L)
- `TC-0023-DEFAULT-S` (товар ID 23, дефолтный цвет, размер S)

**Критически важно:** `content_ids` в событиях Meta Pixel должны **точно совпадать** с `g:id` в Google Merchant feed.

---

### 🎯 Шаг 1: Подготовка к тестированию

#### 1.1. Откройте Facebook Events Manager

1. Перейдите в [Facebook Events Manager](https://business.facebook.com/events_manager2/)
2. Выберите ваш Pixel (ID: `823958313630148` или ваш актуальный)
3. Перейдите в раздел **"Test Events"** или **"Test Events"** (события в реальном времени)

#### 1.2. Установите Facebook Pixel Helper (Chrome расширение)

1. Установите [Facebook Pixel Helper](https://chrome.google.com/webstore/detail/facebook-pixel-helper/fdgfkebogiimcoedlicjlajpkdmockpc)
2. Откройте сайт `https://twocomms.shop`
3. Нажмите на иконку расширения в браузере
4. Убедитесь, что Pixel загружен и активен

#### 1.3. Откройте Chrome DevTools

1. Нажмите `F12` или `Cmd+Option+I` (Mac) / `Ctrl+Shift+I` (Windows/Linux)
2. Перейдите во вкладку **Console**
3. Включите фильтр для событий (опционально)

---

### 📦 Шаг 2: Проверка ViewContent события

#### 2.1. Откройте страницу товара

1. Перейдите на любую страницу товара, например:
   - `https://twocomms.shop/catalog/...`
2. **Запишите `offer_id` этого товара:**
   - Откройте DevTools → Console
   - Введите: `document.querySelector('[data-product-offer-id]')?.getAttribute('data-product-offer-id')`
   - Или найдите в коде страницы атрибут `data-product-offer-id`

#### 2.2. Проверьте событие ViewContent в Events Manager

**В Facebook Events Manager (Test Events):**
- ✅ Должно появиться событие `ViewContent`
- ✅ Проверьте параметры события:
  ```javascript
  {
    content_ids: ["TC-0007-BLK-M"],  // ← Должно совпадать с offer_id из фида!
    content_type: "product",
    content_name: "Название товара",
    value: 2199.00,
    currency: "UAH"
  }
  ```

#### 2.3. Проверьте событие через Pixel Helper

- ✅ В расширении Facebook Pixel Helper должно отображаться событие `ViewContent`
- ✅ Нажмите на событие, чтобы увидеть детали
- ✅ Проверьте, что `content_ids` содержит правильный `offer_id`

#### 2.4. Проверьте соответствие с фидом

1. Откройте фид: `https://twocomms.shop/media/google-merchant-v3.xml`
2. Найдите товар по его ID
3. Проверьте, что `g:id` в фиде **точно совпадает** с `content_ids` в событии ViewContent

**Пример:**
```xml
<!-- В фиде -->
<g:id>TC-0007-BLK-M</g:id>

<!-- В событии ViewContent -->
content_ids: ["TC-0007-BLK-M"]
```

✅ **Должно совпадать точно!**

---

### 🛒 Шаг 3: Проверка AddToCart события

#### 3.1. Добавьте товар в корзину

1. На странице товара выберите:
   - **Цвет** (если есть варианты)
   - **Размер** (S, M, L, XL, XXL)
2. Нажмите кнопку **"Добавить в корзину"**

#### 3.2. Проверьте событие AddToCart

**В Facebook Events Manager (Test Events):**
- ✅ Должно появиться событие `AddToCart`
- ✅ Проверьте параметры:
  ```javascript
  {
    content_ids: ["TC-0007-BLK-M"],  // ← Должно совпадать с ViewContent!
    content_type: "product",
    content_name: "Название товара",
    value: 2199.00,                  // ← Цена товара × количество
    currency: "UAH",
    contents: [
      {
        id: "TC-0007-BLK-M",         // ← Тот же offer_id
        quantity: 1,
        item_price: 2199.00
      }
    ]
  }
  ```

#### 3.3. Проверьте соответствие

✅ **Убедитесь:**
- `content_ids` в `AddToCart` = `content_ids` в `ViewContent`
- `content_ids` = `offer_id` из фида для этого товара (с учетом выбранного цвета и размера)

**Важно:** Если на странице товара выбрали другой цвет или размер, `offer_id` должен измениться!

**Пример:**
- ViewContent: `TC-0007-BLK-M` (черный, размер M)
- Пользователь выбрал **синий** и **L**: AddToCart должен быть `TC-0007-BLU-L` (или соответствующий цветовой slug)

---

### 💳 Шаг 4: Проверка Purchase события

#### 4.1. Оформите тестовый заказ

⚠️ **Важно:** Используйте тестовые данные или режим разработки!

1. Перейдите в корзину: `https://twocomms.shop/cart/`
2. Заполните форму заказа:
   - Имя, фамилия
   - Телефон
   - Email (для Advanced Matching)
   - Адрес доставки
3. Выберите способ оплаты (можно выбрать "Наложенный платеж" для тестирования)
4. Нажмите **"Оформить заказ"**

#### 4.2. Проверьте событие Purchase на странице успеха

После оформления заказа вы попадете на страницу `order_success`.

**В Facebook Events Manager (Test Events):**
- ✅ Должно появиться событие `Purchase`
- ✅ Проверьте параметры:
  ```javascript
  {
    value: 2199.00,                  // ← Общая сумма заказа
    currency: "UAH",
    content_ids: ["TC-0007-BLK-M"], // ← Должно совпадать с AddToCart!
    content_type: "product",
    contents: [
      {
        id: "TC-0007-BLK-M",        // ← offer_id из фида
        quantity: 1,
        item_price: 2199.00
      }
    ]
  }
  ```

#### 4.3. Проверьте Advanced Matching

**В Events Manager проверьте Advanced Matching данные:**
- ✅ `em` (email) - должен быть в формате lowercase
- ✅ `ph` (phone) - только цифры, без пробелов и символов
- ✅ `fn` (first name) - lowercase
- ✅ `ln` (last name) - lowercase
- ✅ `ct` (city) - lowercase

#### 4.4. Проверьте соответствие content_ids

✅ **Критическая проверка:**
1. Откройте фид: `https://twocomms.shop/media/google-merchant-v3.xml`
2. Найдите все товары из заказа по их `offer_id`
3. Убедитесь, что **каждый** `g:id` в фиде совпадает с `content_ids` в событии Purchase

**Пример для заказа с несколькими товарами:**
```xml
<!-- В фиде -->
<g:id>TC-0007-BLK-M</g:id>
<g:id>TC-0012-CV2-L</g:id>
```

```javascript
// В событии Purchase
content_ids: ["TC-0007-BLK-M", "TC-0012-CV2-L"]
```

✅ **Все ID должны совпадать точно!**

---

### 🔍 Шаг 5: Проверка через Console (для разработчиков)

#### 5.1. Проверка через JavaScript

На любой странице откройте Console и выполните:

```javascript
// Проверка загрузки Pixel
console.log('FB Pixel loaded:', typeof window.fbq !== 'undefined');

// Проверка последних событий (если есть возможность)
// Обычно события отправляются асинхронно, поэтому сложно перехватить вручную
```

#### 5.2. Проверка отправленных событий через Network

1. Откройте DevTools → **Network**
2. Отфильтруйте по `facebook.com` или `fbcdn.net`
3. Выполните действие (просмотр товара, добавление в корзину, покупка)
4. Найдите запросы к Facebook Pixel
5. Проверьте payload запроса на наличие `content_ids`

---

### 📋 Итоговый чек-лист

После выполнения всех проверок убедитесь:

- [ ] ✅ `content_ids` в **ViewContent** совпадает с `g:id` в фиде
- [ ] ✅ `content_ids` в **AddToCart** совпадает с выбранным вариантом товара (цвет + размер)
- [ ] ✅ `content_ids` в **Purchase** совпадает с `content_ids` из предыдущих событий
- [ ] ✅ Все `content_ids` в Purchase совпадают с `g:id` товаров в фиде
- [ ] ✅ Формат `content_ids`: `TC-{ID:04d}-{COLOR}-{SIZE}` (например, `TC-0007-BLK-M`)
- [ ] ✅ Advanced Matching работает (email, phone, name, city отправляются)
- [ ] ✅ События видны в Facebook Events Manager / Test Events
- [ ] ✅ Pixel Helper показывает все события корректно

---

## 🚨 Частые проблемы и решения

### Проблема 1: content_ids не совпадают с фидом

**Причина:** Фид не обновлен после изменений в коде.

**Решение:**
1. Форсируйте пересъём фида (см. раздел "Форсирование пересъёма фида")
2. Подождите 5-10 минут для распространения фида
3. Повторите проверку

### Проблема 2: События не появляются в Events Manager

**Причина:** 
- Pixel не загружен на странице
- События блокируются блокировщиками рекламы
- Неправильный Pixel ID

**Решение:**
1. Проверьте загрузку Pixel через Pixel Helper
2. Отключите блокировщики рекламы
3. Проверьте правильность Pixel ID в настройках сайта

### Проблема 3: content_ids содержит старый формат (только product_id)

**Причина:** Используется старый код, который не генерирует `offer_id`.

**Решение:**
1. Убедитесь, что проект обновлен (git pull)
2. Проверьте, что используется функция `get_offer_id()` из `analytics_helpers.py`
3. Перезапустите веб-сервер

### Проблема 4: Advanced Matching не работает

**Причина:** 
- Пользователь не авторизован (для гостевых пользователей Advanced Matching может не отправляться)
- Неправильный формат данных (email не lowercase, phone содержит символы)

**Решение:**
1. Убедитесь, что пользователь авторизован
2. Проверьте формат данных в коде (должен быть lowercase для email, name, city; только цифры для phone)

---

## 📞 Контакты и поддержка

Если возникли проблемы:
1. Проверьте логи на сервере: `tail -50 /home/qlknpodo/TWC/TwoComms_Site/twocomms/cron.log`
2. Проверьте логи веб-сервера (Gunicorn, Nginx и т.д.)
3. Проверьте консоль браузера на наличие ошибок JavaScript

---

**Дата создания:** Январь 2025  
**Версия:** 1.0  
**Статус:** ✅ Готово к использованию















