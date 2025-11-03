# Покращення системи промокодів - 30.01.2025

## Зміни та виправлення

### 1. Оновлення кешу статичних файлів

**Проблема:** Старий кеш браузера показував застарілий код при додаванні товарів у кошик та роботі з промокодами.

**Рішення:**
- ✅ Оновлено версію `dropshipper.css` з `v=20251027promo` на `v=20250130promo` в `admin_promocodes.html`
- ✅ Оновлено версію `main.js` з `v=38` на `v=40` в `base.html`
- ✅ Додано версію до динамічного імпорту `cart.js?v=20250130` в `main.js`

**Файли змінено:**
- `twocomms/twocomms_django_theme/templates/pages/admin_promocodes.html`
- `twocomms/twocomms_django_theme/templates/base.html`
- `twocomms/twocomms_django_theme/static/js/main.js`

---

### 2. Покращення UX для незареєстрованих користувачів

**Проблема:** Незареєстрованим користувачам не було зрозуміло, чому вони не можуть використовувати промокоди.

**Рішення:**
- ✅ Додано спеціальну обробку помилки `auth_required` у фронтенді
- ✅ При спробі використати промокод без авторизації показується:
  1. Повідомлення про помилку з чітким поясненням
  2. Модальне вікно з пропозицією перейти до авторизації
  3. При підтвердженні - автоматичний редирект на `/login/`

**Файли змінено:**
- `twocomms/twocomms_django_theme/static/js/modules/cart.js`

**Код:**
```javascript
} else if (data && data.auth_required) {
  // Особлива обробка для незареєстрованих користувачів
  const authMessage = data.message || 'Промокоди доступні тільки для зареєстрованих користувачів';
  showPromoMessage(msgBox, authMessage, 'error');
  // Показуємо модальне вікно з пропозицією авторизуватися
  setTimeout(() => {
    if (confirm(authMessage + '.\n\nПерейти до авторизації?')) {
      window.location.href = '/login/';
    }
  }, 800);
}
```

---

### 3. Виправлення логіки використання промокодів

**Проблема:** Промокод використовувався двічі - один раз при `promo.use()` і ще раз через `record_usage()`.

**Рішення:**
- ✅ Змінено логіку в `create_order()` для використання тільки `record_usage()`
- ✅ Метод `record_usage()` вже викликає `use()` всередині себе
- ✅ Додано перевірку `can_be_used_by_user()` перед застосуванням промокоду
- ✅ Запис використання відбувається ПІСЛЯ збереження замовлення

**Файли змінено:**
- `twocomms/storefront/views/checkout.py`

**Логіка:**
```python
# 1. Застосування промокоду
promo_to_record = None
if promo_code_id:
    promo = PromoCode.objects.get(id=promo_code_id, is_active=True)
    can_use, _ = promo.can_be_used_by_user(request.user)
    if can_use:
        discount = promo.calculate_discount(total_sum)
        if discount > 0:
            order.discount_amount = discount
            order.promo_code = promo
            promo_to_record = promo  # Запам'ятовуємо для запису пізніше

# 2. Збереження замовлення
order.total_sum = final_total
order.save()

# 3. Запис використання ПІСЛЯ збереження
if promo_to_record:
    promo_to_record.record_usage(request.user, order)
```

---

### 4. Покращення обчислення знижок (Decimal precision)

**Проблема:** Можливі проблеми з точністю обчислень через використання float замість Decimal.

**Рішення:**
- ✅ Додано імпорт `ROUND_HALF_UP` з модуля `decimal`
- ✅ Всі ціни конвертуються в `Decimal` з квантуванням до 2 знаків після коми
- ✅ Додано перевірку, що знижка не перевищує суму замовлення
- ✅ Фінальна сума завжди квантується до 2 десяткових знаків

**Файли змінено:**
- `twocomms/storefront/views/checkout.py`

**Код:**
```python
from decimal import Decimal, ROUND_HALF_UP

# Конвертація цін
unit = Decimal(str(p.final_price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
qty_decimal = Decimal(str(it['qty']))
line = (unit * qty_decimal).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# Обробка знижки
discount = promo.calculate_discount(total_sum)
if not isinstance(discount, Decimal):
    discount = Decimal(str(discount))
discount = discount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# Скидка не може быть больше суммы заказа
if discount > total_sum:
    discount = total_sum

# Фінальна сума
final_total = (total_sum - discount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
```

---

### 5. Очищення сесії після створення замовлення

**Рішення:**
- ✅ Додано очищення `promo_code_data` з сесії після створення замовлення
- ✅ Це запобігає використанню застарілих даних про промокод

**Код:**
```python
request.session.pop('promo_code_id', None)
request.session.pop('promo_code_data', None)
```

---

## Як працює система промокодів

### Моделі

#### PromoCode
- **Поля:**
  - `code` - унікальний код промокоду
  - `promo_type` - тип (regular/voucher/grouped)
  - `discount_type` - тип знижки (percentage/fixed)
  - `discount_value` - значення знижки
  - `group` - FK до PromoCodeGroup (необов'язково)
  - `max_uses`, `current_uses` - ліміти використання
  - `one_time_per_user` - одноразове використання на користувача
  - `min_order_amount` - мінімальна сума замовлення
  - `valid_from`, `valid_until` - період дії

#### PromoCodeGroup
- **Логіка "один на акаунт":**
  - Якщо `one_per_account=True`, користувач може використати тільки один промокод з цієї групи
  - Перевірка через `PromoCodeUsage.objects.filter(user=user, group=self.group).exists()`

#### PromoCodeUsage
- **Трекінг використання:**
  - Зберігає інформацію про те, хто, коли і який промокод використав
  - Використовується для перевірки групових обмежень

### Ключові методи

#### `can_be_used_by_user(user)`
```python
def can_be_used_by_user(self, user):
    """Перевіряє, чи може користувач використати промокод"""
    if not user or not user.is_authenticated:
        return False, 'Промокоди доступні тільки для зареєстрованих користувачів'
    
    # Перевірка груп
    if self.group and self.group.one_per_account:
        if PromoCodeUsage.objects.filter(user=user, group=self.group).exists():
            return False, f'Ви вже використали промокод з групи "{self.group.name}"'
    
    return True, 'OK'
```

#### `calculate_discount(total_amount)`
```python
def calculate_discount(self, total_amount):
    """Розраховує знижку для вказаної суми"""
    total = Decimal(str(total_amount))
    discount_value = Decimal(str(self.discount_value))
    
    if self.discount_type == 'percentage':
        return (total * discount_value) / 100
    else:
        # Для ваучерів та фіксованої знижки
        return min(discount_value, total)
```

#### `record_usage(user, order)`
```python
def record_usage(self, user, order=None):
    """Записує використання промокоду користувачем"""
    usage = PromoCodeUsage.objects.create(
        user=user,
        promo_code=self,
        group=self.group,
        order=order
    )
    self.use()  # Збільшує current_uses
    return usage
```

---

## Правила використання

1. **Авторизація обов'язкова**: Тільки зареєстровані користувачі можуть використовувати промокоди
2. **Групове виключення**: Якщо користувач використав будь-який промокод з групи, він не може використати інші з цієї ж групи
3. **Одноразове використання**: Опціональне обмеження на рівні промокоду
4. **Глобальний ліміт**: Поле `max_uses` (0 = необмежено)

---

## Адмін-панель

**URL:** `/admin-panel/?section=promocodes`

### Особливості:
- ✅ Темна тема через `dropshipper.css`
- ✅ Три вкладки: Промокоди, Групи, Статистика
- ✅ Drag-and-drop для призначення промокодів до груп
- ✅ Швидкий пошук та фільтрація
- ✅ Детальна статистика використання

---

## Тестування

### Сценарії для перевірки:

1. **Незареєстрований користувач:**
   - [ ] Спроба використати промокод
   - [ ] Отримання повідомлення про необхідність авторизації
   - [ ] Редирект на /login/ при підтвердженні

2. **Зареєстрований користувач:**
   - [ ] Успішне застосування промокоду
   - [ ] Коректний розрахунок знижки (site discount + promo discount)
   - [ ] Відображення загальної економії

3. **Групові обмеження:**
   - [ ] Використання першого промокоду з групи - успішно
   - [ ] Спроба використати другий промокод з тієї ж групи - помилка
   - [ ] Правильне повідомлення про групове обмеження

4. **Створення замовлення:**
   - [ ] Промокод правильно застосовується
   - [ ] Записується в PromoCodeUsage
   - [ ] current_uses збільшується
   - [ ] Фінальна сума коректна (з квантуванням)

5. **Кеш:**
   - [ ] Оновлення корзини без перезавантаження сторінки
   - [ ] Коректне відображення промокодів після додавання товарів
   - [ ] Адмін-панель відображається в темній темі

---

## Файли, змінені в цьому update:

1. `twocomms/twocomms_django_theme/templates/pages/admin_promocodes.html`
2. `twocomms/twocomms_django_theme/templates/base.html`
3. `twocomms/twocomms_django_theme/static/js/main.js`
4. `twocomms/twocomms_django_theme/static/js/modules/cart.js`
5. `twocomms/storefront/views/checkout.py`

---

## Наступні кроки

1. ✅ Протестувати всі сценарії використання промокодів
2. ✅ Перевірити темну тему адмін-панелі в різних браузерах
3. ✅ Переконатися, що кеш правильно оновлюється
4. ✅ Перевірити розрахунки знижок на різних сумах замовлень
5. ✅ Протестувати групові обмеження з реальними промокодами

---

## Контакти

При виникненні проблем або питань:
- Перевірте логи в консолі браузера (F12)
- Перевірте Django логи на сервері
- Переконайтеся, що кеш браузера очищений (Ctrl+Shift+R)

---

_Документ створено: 30.01.2025_
_Версія: 1.0_
