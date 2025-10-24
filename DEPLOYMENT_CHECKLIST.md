# Чек-лист деплоя оптимизаций TwoComms

## ✅ Предварительная подготовка

- [ ] 1. Создать резервную копию БД
```bash
ssh qlknpodo@195.191.24.169 "mysqldump -u USER -p DATABASE > backup_$(date +%Y%m%d_%H%M%S).sql"
```

- [ ] 2. Проверить текущую версию в git
```bash
git status
git log --oneline -5
```

## 📦 Деплой на сервер

### Шаг 1: Обновление кода
```bash
sshpass -p '[REDACTED_SSH_PASSWORD]' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && git pull'"
```

**Проверить**: 
- [ ] Код успешно подтянут
- [ ] Нет конфликтов слияния

### Шаг 2: Обновление зависимостей
```bash
sshpass -p '[REDACTED_SSH_PASSWORD]' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && pip install -r requirements.txt'"
```

**Проверить**:
- [ ] psycopg пакеты удалены (если были установлены)
- [ ] Все зависимости обновлены
- [ ] Нет ошибок установки

### Шаг 3: Применение миграций
```bash
sshpass -p '[REDACTED_SSH_PASSWORD]' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && python manage.py migrate'"
```

**Проверить**:
- [ ] Миграция 0030_remove_has_discount_field применена
- [ ] Нет ошибок миграции

### Шаг 4: Сборка статических файлов
```bash
sshpass -p '[REDACTED_SSH_PASSWORD]' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && python manage.py collectstatic --no-input'"
```

**Проверить**:
- [ ] Статика собрана успешно
- [ ] Нет ошибок сжатия

### Шаг 5: Перезагрузка приложения
```bash
sshpass -p '[REDACTED_SSH_PASSWORD]' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'touch /var/www/qlknpodo_pythonanywhere_com_wsgi.py'"
```

**Проверить**:
- [ ] Приложение перезагружено
- [ ] Нет ошибок 500

## 🧪 Функциональное тестирование

### Критические функции

- [ ] **Главная страница** загружается без ошибок
  - URL: https://twocomms.shop/
  - Проверить: товары отображаются, категории работают

- [ ] **API Категорий** работает быстрее
  - URL: https://twocomms.shop/api/categories/
  - Проверить: products_count отображается корректно
  - Время ответа: должно быть < 200ms (было > 300ms)

- [ ] **Каталог товаров** работает
  - URL: https://twocomms.shop/catalog/
  - Проверить: товары загружаются, фильтры работают

- [ ] **Поиск** функционирует
  - URL: https://twocomms.shop/search/?q=футболка
  - Проверить: результаты корректные
  - Время ответа: должно быть быстрее

- [ ] **Карточка товара** отображается
  - URL: https://twocomms.shop/product/[slug]/
  - Проверить: цены, изображения, описание

- [ ] **Корзина** работает
  - Добавление товара
  - Изменение количества
  - Удаление товара
  - Промокоды

- [ ] **Оформление заказа** функционирует
  - URL: https://twocomms.shop/checkout/
  - Проверить: создание заказа, оплата

- [ ] **Профиль пользователя** работает
  - Регистрация нового пользователя
  - Вход в систему
  - Редактирование профиля
  - Проверить: создание UserProfile и UserPoints автоматически

- [ ] **Избранное** работает
  - Добавление в избранное
  - Удаление из избранного

## 📊 Тестирование производительности

### Проверка N+1 запросов

1. **API Категорий (должен быть 1-2 запроса вместо N+1)**
```bash
# Включить Django Debug Toolbar или проверить логи запросов
# Ожидается: 1 запрос с annotate
```

2. **Каталог с категорией (должен быть N+1 вместо 2N)**
```bash
# URL: /catalog/hoodie/
# Проверить количество запросов в логах
```

3. **Поиск (должен быть 1 запрос вместо 2)**
```bash
# URL: /search/?q=test
# Проверить: используется Q objects, не UNION
```

### Время ответа

Выполнить несколько запросов и замерить время:

```bash
# Главная страница
time curl -s https://twocomms.shop/ > /dev/null

# API Категорий
time curl -s https://twocomms.shop/api/categories/ > /dev/null

# Каталог
time curl -s https://twocomms.shop/catalog/ > /dev/null

# Поиск
time curl -s https://twocomms.shop/search/?q=футболка > /dev/null
```

**Ожидаемые результаты**:
- Главная: < 800ms
- API Категорий: < 200ms (улучшение ~40-60%)
- Каталог: < 600ms (улучшение ~20-30%)
- Поиск: < 500ms (улучшение ~15-25%)

## 🔍 Проверка логов

### Проверить логи на ошибки
```bash
sshpass -p '[REDACTED_SSH_PASSWORD]' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'tail -n 100 /home/qlknpodo/TWC/TwoComms_Site/twocomms/django.log'"
```

**Искать**:
- [ ] Нет ошибок импорта
- [ ] Нет ошибок подключения к БД
- [ ] Нет ошибок в сигналах Django
- [ ] Нет warnings о deprecated функциях

### Проверить логи ошибок
```bash
sshpass -p '[REDACTED_SSH_PASSWORD]' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'tail -n 100 /home/qlknpodo/TWC/TwoComms_Site/twocomms/stderr.log'"
```

**Проверить**:
- [ ] Нет критических ошибок
- [ ] Нет traceback'ов

## 🔒 Проверка безопасности

### HSTS заголовки (исправлена критическая ошибка!)
```bash
curl -I https://twocomms.shop/ | grep -i "strict-transport-security"
```

**Ожидается**:
```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

- [ ] Заголовок присутствует
- [ ] includeSubDomains установлен (была ошибка с кириллицей!)
- [ ] preload установлен

### Другие заголовки безопасности
```bash
curl -I https://twocomms.shop/
```

**Проверить наличие**:
- [ ] Content-Security-Policy
- [ ] X-Content-Type-Options: nosniff
- [ ] X-Frame-Options: SAMEORIGIN
- [ ] Referrer-Policy: strict-origin-when-cross-origin

## 🐛 Rollback план (на случай проблем)

### Если что-то пошло не так:

1. **Откатить код**
```bash
sshpass -p '[REDACTED_SSH_PASSWORD]' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && git reset --hard HEAD~1'"
```

2. **Откатить миграции**
```bash
sshpass -p '[REDACTED_SSH_PASSWORD]' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && python manage.py migrate storefront 0029'"
```

3. **Восстановить БД из бэкапа** (если нужно)
```bash
ssh qlknpodo@195.191.24.169 "mysql -u USER -p DATABASE < backup_YYYYMMDD_HHMMSS.sql"
```

4. **Перезагрузить приложение**
```bash
sshpass -p '[REDACTED_SSH_PASSWORD]' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'touch /var/www/qlknpodo_pythonanywhere_com_wsgi.py'"
```

## 📝 После деплоя

- [ ] Обновить документацию
- [ ] Уведомить команду об изменениях
- [ ] Мониторить логи следующие 24 часа
- [ ] Проверить аналитику производительности через неделю
- [ ] Записать результаты тестирования в отчет

## ⚡ Ключевые изменения в этом деплое

1. ✅ **КРИТИЧНО**: Исправлена безопасность HSTS (кириллица в настройке)
2. ✅ Удалено неиспользуемое поле `has_discount` в Product
3. ✅ Оптимизированы сигналы Django (3 → 1)
4. ✅ Исправлены N+1 запросы в CategorySerializer, ViewSet, catalog view
5. ✅ Оптимизирован поиск (Q objects вместо UNION)
6. ✅ Удален код PostgreSQL (используем только MySQL и SQLite)
7. ✅ Очищены неиспользуемые импорты

---

**Дата деплоя**: __________  
**Время начала**: __________  
**Время окончания**: __________  
**Ответственный**: __________  
**Результат**: ☐ Успешно  ☐ С проблемами  ☐ Откачено

