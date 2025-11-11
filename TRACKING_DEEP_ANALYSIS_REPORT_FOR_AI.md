# 🔍 ГЛУБОКИЙ АНАЛИЗ СИСТЕМЫ ТРЕКИНГА META/TIKTOK - ОТЧЕТ ДЛЯ ИСПРАВЛЕНИЯ

**Дата анализа:** 2025-01-30  
**Аналитик:** AI Deep Analysis System  
**Версия:** 1.0 - Comprehensive Deep Analysis  
**Цель:** Детальный отчет для другого ИИ с конкретными проблемами и решениями

---

## 📋 ОГЛАВЛЕНИЕ

1. [Критические проблемы](#критические-проблемы)
2. [Анализ кода по компонентам](#анализ-кода-по-компонентам)
3. [Проблемы дедупликации](#проблемы-дедупликации)
4. [Проблемы передачи данных](#проблемы-передачи-данных)
5. [Конкретные исправления](#конкретные-исправления)
6. [Чеклист проверки](#чеклист-проверки)

---

## 🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ

### Проблема #1: Meta External ID покрытие 0% на сервере

**Симптомы из отчетов:**
- External ID: 0% на сервере, 0% покрытие событий
- Event ID: 70.59% в браузере, 67.88% на сервере, 19.92% покрытие

**Причина:**
1. **В `checkout.py` (строки 255-270):** external_id определяется, но может быть `None` если:
   - Нет `request.user.is_authenticated` (но это проверяется выше)
   - Нет `order.session_key` (заказ только что создан)
   - Нет `request.session.session_key` (сессия не создана)
   - Нет `order.order_number` (заказ еще не сохранен)

2. **В `facebook_conversions_service.py` (строки 155-166):** 
   - Сначала читается из `tracking_data.get('external_id')`
   - Если нет - генерируется заново из `order.user_id`/`session_key`/`order_number`
   - **ПРОБЛЕМА:** На клиенте external_id генерируется по другой логике (order_success.html строки 1873-1886)

3. **Несоответствие формата:**
   - Клиент: `'user:' + userId` или `'session:' + sessionKey` или `'order:' + orderNumber`
   - Сервер: `f"user:{order.user_id}"` или `f"session:{order.session_key}"` или `f"order:{order.order_number}"`
   - **НО:** На клиенте используется `orderId` (число), на сервере `order_number` (строка типа "TWC...")

**Файлы для проверки:**
- `twocomms/storefront/views/checkout.py` (строки 255-270)
- `twocomms/orders/facebook_conversions_service.py` (строки 155-166)
- `twocomms/twocomms_django_theme/templates/pages/order_success.html` (строки 1873-1886)

**Решение:**
1. Убедиться, что external_id **ВСЕГДА** определяется в checkout.py
2. Сохранять external_id в payment_payload.tracking.external_id **до** сохранения заказа
3. Использовать **одинаковый формат** на клиенте и сервере
4. Проверить, что external_id хешируется одинаково на клиенте и сервере

---

### Проблема #2: Meta FBP покрытие 3.83% на сервере (0% покрытие)

**Симптомы из отчетов:**
- FBP: 100% в браузере, 3.83% на сервере, 0% покрытие событий

**Причина:**
1. **В `checkout.py` (строки 236-242):** fbp читается из cookies только если cookie существует
2. **Проблема:** Если cookie `_fbp` отсутствует (блокировщик рекламы, приватный режим, первое посещение), fbp не сохраняется
3. **На клиенте:** analytics-loader.js читает fbp из cookies (строка 87), но если cookie нет - не передается в Meta Pixel

**Важно:** FBP генерируется Meta Pixel автоматически при первом посещении. Если cookie заблокирована, fbp не будет.

**Файлы для проверки:**
- `twocomms/storefront/views/checkout.py` (строки 236-242)
- `twocomms/twocomms_django_theme/static/js/analytics-loader.js` (строки 87-88, 175-179)
- `twocomms/orders/facebook_conversions_service.py` (строки 147-149)

**Решение:**
1. **Проверить:** Всегда ли fbp передается в payment_payload при создании заказа
2. **Улучшить:** Добавить fallback - если fbp нет в cookies, попытаться получить из JavaScript (передать через скрытое поле формы)
3. **Проверить:** Что fbp передается в CAPI даже если он отсутствует (опциональный параметр)

---

### Проблема #3: Meta FBC (Click ID) не передается

**Симптомы из отчетов:**
- Рекомендация Meta: "Отправьте ID клика (fbc) для увеличения конверсий на 57.55%"
- FBC не упоминается в отчетах дедупликации

**Причина:**
1. **В `checkout.py` (строки 243-248):** fbc читается из cookies, но может отсутствовать
2. **На клиенте:** В order_success.html fbc **НЕ передается** в `__meta`
3. **В analytics-loader.js:** fbc читается из cookies (строка 88), но если cookie нет - не передается

**Важно:** FBC генерируется только при клике на рекламу Meta. Если пользователь не пришел из рекламы, fbc не будет.

**Файлы для проверки:**
- `twocomms/storefront/views/checkout.py` (строки 243-248)
- `twocomms/twocomms_django_theme/templates/pages/order_success.html` (строки 2008-2014, 2069-2075)
- `twocomms/twocomms_django_theme/static/js/analytics-loader.js` (строки 88, 178-179)

**Решение:**
1. **Проверить:** Передается ли fbc из checkout.py в payment_payload
2. **Исправить:** В order_success.html добавить передачу fbc в `__meta` (если есть в cookies)
3. **Улучшить:** В analytics-loader.js убедиться, что fbc передается в metaOptions если есть

---

### Проблема #4: Meta покрытие через Conversions API всего 20% (цель 75%)

**Симптомы из отчетов:**
- Покрытие событий: 20% (цель ≥75%)
- Event ID покрытие: 19.92%
- Низкий коэффициент событий пикселя, охватываемых через Conversions API

**Причина:**
1. **Недостаточно совпадающих ключей дедупликации:**
   - Event ID: 70.59% в браузере, 67.88% на сервере (почти совпадает, но не 100%)
   - External ID: 0% на сервере
   - FBP: 100% в браузере, 3.83% на сервере
   - FBC: не упоминается в отчетах

2. **Event ID может не совпадать:**
   - Клиент: `'{{ order.get_facebook_event_id }}'` (шаблон Django)
   - Сервер: `order.get_facebook_event_id()` (метод модели)
   - **Проверить:** Всегда ли они генерируют одинаковый ID

3. **События отправляются в разное время:**
   - Клиент: сразу при загрузке order_success.html
   - Сервер: при изменении payment_status (может быть позже)

**Файлы для проверки:**
- `twocomms/orders/models.py` (метод `get_facebook_event_id`, строки 115-127)
- `twocomms/twocomms_django_theme/templates/pages/order_success.html` (строка 1999)
- `twocomms/orders/facebook_conversions_service.py` (строка 284)
- `twocomms/storefront/views/utils.py` (строки 387-445)

**Решение:**
1. **Убедиться:** Event ID генерируется одинаково на клиенте и сервере
2. **Улучшить:** Всегда передавать event_id, fbp, fbc, external_id в CAPI
3. **Проверить:** Синхронизацию времени отправки событий (клиент и сервер)

---

### Проблема #5: TikTok Purchase 0 событий (ожидает первого события)

**Симптомы из отчетов:**
- Purchase: 0 событий, "Ожидание первого события"
- PlaceAnOrder: 0 событий, "Ожидание первого события"
- Search: 0 событий, "Ожидание первого события"

**Причина:**
1. **TikTok Events API может быть не настроен:**
   - В `tiktok_events_service.py` (строки 31-43): проверяется `TIKTOK_EVENTS_ACCESS_TOKEN` и `TIKTOK_EVENTS_PIXEL_CODE`
   - Если не установлены - `enabled = False`
   - **Проверить:** Установлены ли эти переменные в settings.py или ENV

2. **События не отправляются:**
   - В `utils.py` (строки 447-494): TikTok события отправляются при изменении payment_status
   - Но если `tiktok_service.enabled = False`, события не отправляются

3. **Ошибки в отправке не логируются:**
   - В `tiktok_events_service.py` (строки 229-253): ошибки логируются, но могут быть незамечены

**Файлы для проверки:**
- `twocomms/orders/tiktok_events_service.py` (строки 29-43)
- `twocomms/twocomms/settings.py` (проверить наличие TIKTOK_EVENTS_*)
- `twocomms/storefront/views/utils.py` (строки 447-494)

**Решение:**
1. **Проверить:** Установлены ли `TIKTOK_EVENTS_ACCESS_TOKEN` и `TIKTOK_EVENTS_PIXEL_CODE` в ENV
2. **Проверить:** Работает ли TikTok Events API (отправить тестовое событие)
3. **Улучшить:** Добавить логирование когда TikTok Events API отключен

---

### Проблема #6: TikTok все события только через браузер

**Симптомы из отчетов:**
- Все активные события: "Способ подключения: Только браузер"
- Нет серверной отправки через Events API

**Причина:**
1. **TikTok Events API не настроен или не работает** (см. Проблема #5)
2. **События отправляются только на клиенте:**
   - В `analytics-loader.js` есть поддержка TikTok Pixel (строки 240-310)
   - Но серверная отправка через Events API может не работать

**Файлы для проверки:**
- `twocomms/twocomms_django_theme/static/js/analytics-loader.js` (строки 240-310)
- `twocomms/orders/tiktok_events_service.py` (весь файл)

**Решение:**
1. **Настроить TikTok Events API** (см. Проблема #5)
2. **Проверить:** Отправляются ли события через Events API при изменении payment_status
3. **Улучшить:** Добавить логирование всех отправок в TikTok Events API

---

### Проблема #7: Meta качество сопоставления 3.0/10

**Симптомы из отчетов:**
- Purchase: 3.0/10
- InitiateCheckout: 3.0/10
- AddToCart: 3.0/10
- Рекомендации: отправить fbc (+57.55%), email (+88.29%), phone (+21.65%)

**Причина:**
1. **Недостаточно данных для сопоставления:**
   - Email: передается только для авторизованных пользователей
   - Phone: передается, но может быть не в правильном формате
   - FBC: не передается (см. Проблема #3)

2. **Данные не хешируются правильно:**
   - Email должен быть lowercase и хеширован SHA-256
   - Phone должен быть только цифры и хеширован SHA-256
   - **Проверить:** Правильно ли хешируются данные на клиенте и сервере

**Файлы для проверки:**
- `twocomms/twocomms_django_theme/templates/pages/order_success.html` (строки 1888-1938, функция `buildMetaUserData`)
- `twocomms/orders/facebook_conversions_service.py` (строки 89-103, метод `_hash_data`)
- `twocomms/twocomms_django_theme/static/js/analytics-loader.js` (строки 181-182)

**Решение:**
1. **Проверить:** Правильно ли хешируются email и phone на клиенте и сервере
2. **Улучшить:** Всегда передавать email и phone в CAPI (если есть)
3. **Исправить:** Передавать fbc если есть (см. Проблема #3)

---

## 📊 АНАЛИЗ КОДА ПО КОМПОНЕНТАМ

### Компонент 1: Клиентская отправка событий (order_success.html)

**Файл:** `twocomms/twocomms_django_theme/templates/pages/order_success.html`

**Строки 1997-2026: Purchase событие**
```javascript
var eventId = '{{ order.get_facebook_event_id }}';
var purchaseMeta = {
    event_id: eventId,
    user_data: fbUserData
};
if (externalHash) {
    purchaseMeta.external_id = externalHash;
}
```

**Проблемы:**
1. ❌ **fbp НЕ передается** в `purchaseMeta`
2. ❌ **fbc НЕ передается** в `purchaseMeta`
3. ⚠️ `externalHash` передается только если определен (строка 2012-2013)

**Строки 2066-2086: Lead событие**
```javascript
var leadEventId = '{{ order.get_facebook_event_id }}_lead';
var leadMeta = {
    event_id: leadEventId,
    user_data: fbUserData
};
if (externalHash) {
    leadMeta.external_id = externalHash;
}
```

**Проблемы:**
1. ❌ **fbp НЕ передается** в `leadMeta`
2. ❌ **fbc НЕ передается** в `leadMeta`
3. ⚠️ `externalHash` передается только если определен

**Строки 1873-1886: Генерация external_id**
```javascript
var externalSource = '';
if (userIdAttr) {
    externalSource = 'user:' + userIdAttr;
} else if (sessionKey) {
    externalSource = 'session:' + sessionKey;
} else if (orderNumber) {
    externalSource = 'order:' + orderNumber;
} else if (orderId) {
    externalSource = 'order:' + orderId;
}
```

**Проблема:**
- Используется `orderId` (число) или `orderNumber` (строка)
- На сервере используется `order_number` (строка типа "TWC...")
- **Может не совпадать!**

---

### Компонент 2: Серверная отправка событий (facebook_conversions_service.py)

**Файл:** `twocomms/orders/facebook_conversions_service.py`

**Строки 143-179: Метод `_prepare_user_data`**
```python
tracking_data = {}
if order.payment_payload and isinstance(order.payment_payload, dict):
    tracking_data = order.payment_payload.get('tracking') or {}

fbp_value = tracking_data.get('fbp')
if fbp_value:
    user_data.fbp = fbp_value

fbc_value = tracking_data.get('fbc')
if fbc_value:
    user_data.fbc = fbc_value

external_source = tracking_data.get('external_id')
if not external_source:
    if order.user_id:
        external_source = f"user:{order.user_id}"
    elif order.session_key:
        external_source = f"session:{order.session_key}"
    elif order.order_number:
        external_source = f"order:{order.order_number}"
```

**Проблемы:**
1. ⚠️ `fbp_value` и `fbc_value` могут быть `None` если не в tracking_data
2. ⚠️ `external_source` генерируется заново если не в tracking_data
3. ⚠️ Формат может не совпадать с клиентским

**Строки 155-166: Генерация external_id**
```python
external_source = tracking_data.get('external_id')
if not external_source:
    # Fallback генерация
    if order.user_id:
        external_source = f"user:{order.user_id}"
    elif order.session_key:
        external_source = f"session:{order.session_key}"
    elif order.order_number:
        external_source = f"order:{order.order_number}"
```

**Проблема:**
- На клиенте используется `orderId` (число) или `orderNumber` (строка)
- На сервере используется `order.order_number` (строка типа "TWC...")
- **Может не совпадать!**

---

### Компонент 3: Сбор tracking данных (checkout.py)

**Файл:** `twocomms/storefront/views/checkout.py`

**Строки 236-272: Сбор tracking_context**
```python
tracking_context = {}
try:
    fbp_cookie = request.COOKIES.get('_fbp')
except Exception:
    fbp_cookie = None
if fbp_cookie:
    tracking_context['fbp'] = fbp_cookie

try:
    fbc_cookie = request.COOKIES.get('_fbc')
except Exception:
    fbc_cookie = None
if fbc_cookie:
    tracking_context['fbc'] = fbc_cookie

external_source = None
if request.user.is_authenticated:
    external_source = f"user:{request.user.id}"
elif order.session_key:
    external_source = f"session:{order.session_key}"
```

**Проблемы:**
1. ⚠️ `fbp_cookie` и `fbc_cookie` могут быть `None` (cookie заблокирована или отсутствует)
2. ⚠️ `external_source` может быть `None` если нет userId/sessionKey
3. ⚠️ `order.session_key` может быть `None` если заказ только что создан

---

## 🔄 ПРОБЛЕМЫ ДЕДУПЛИКАЦИИ

### Проблема: Event ID не всегда совпадает

**Клиент (order_success.html, строка 1999):**
```javascript
var eventId = '{{ order.get_facebook_event_id }}';
```

**Сервер (facebook_conversions_service.py, строка 284):**
```python
event_id = order.get_facebook_event_id()
```

**Метод get_facebook_event_id (models.py, строки 115-127):**
```python
def get_facebook_event_id(self):
    timestamp = int(self.created.timestamp()) if self.created else int(time.time())
    return f"{self.order_number}_{timestamp}"
```

**Потенциальная проблема:**
- Если `order.created` изменится между клиентской и серверной отправкой, timestamp может быть разным
- **НО:** `order.created` не должен изменяться после создания заказа

**Проверка:**
- ✅ Event ID должен быть одинаковым на клиенте и сервере (используется один метод)
- ⚠️ **НО:** Нужно проверить, что `order.created` не изменяется

---

### Проблема: External ID не совпадает

**Клиент (order_success.html, строки 1873-1886):**
```javascript
var externalSource = '';
if (userIdAttr) {
    externalSource = 'user:' + userIdAttr;
} else if (sessionKey) {
    externalSource = 'session:' + sessionKey;
} else if (orderNumber) {
    externalSource = 'order:' + orderNumber;
} else if (orderId) {
    externalSource = 'order:' + orderId;
}
```

**Сервер (checkout.py, строки 255-270):**
```python
external_source = None
if request.user.is_authenticated:
    external_source = f"user:{request.user.id}"
elif order.session_key:
    external_source = f"session:{order.session_key}"
```

**Проблема:**
- На клиенте используется `orderId` (число) или `orderNumber` (строка)
- На сервере используется `order.user.id` или `order.session_key`
- **Может не совпадать!**

**Решение:**
- Использовать **одинаковую логику** на клиенте и сервере
- Предпочтительно: `user:{userId}` или `session:{sessionKey}` или `order:{orderNumber}`

---

### Проблема: FBP/FBC не всегда передаются

**Клиент:**
- FBP/FBC читаются из cookies в analytics-loader.js (строки 87-88)
- **НО:** Не передаются в `__meta` в order_success.html

**Сервер:**
- FBP/FBC читаются из cookies в checkout.py (строки 238-248)
- Сохраняются в payment_payload.tracking
- Читаются в facebook_conversions_service.py (строки 147-153)

**Проблема:**
- Если cookies заблокированы или отсутствуют, FBP/FBC не будут переданы
- **НО:** Это нормально - FBP/FBC опциональные параметры

**Решение:**
- Передавать FBP/FBC в `__meta` на клиенте если они есть в cookies
- Убедиться, что FBP/FBC всегда передаются в CAPI если они есть в payment_payload

---

## 🔧 КОНКРЕТНЫЕ ИСПРАВЛЕНИЯ

### Исправление #1: Передача fbp/fbc в __meta на клиенте

**Файл:** `twocomms/twocomms_django_theme/templates/pages/order_success.html`

**Строки 2008-2014: Purchase событие**
```javascript
// БЫЛО:
var purchaseMeta = {
    event_id: eventId,
    user_data: fbUserData
};

// ДОЛЖНО БЫТЬ:
function getCookie(name) {
    var value = "; " + document.cookie;
    var parts = value.split("; " + name + "=");
    if (parts.length === 2) return parts.pop().split(";").shift();
    return null;
}

var purchaseMeta = {
    event_id: eventId,
    user_data: fbUserData
};
var fbpValue = getCookie('_fbp');
var fbcValue = getCookie('_fbc');
if (fbpValue) {
    purchaseMeta.fbp = fbpValue;
}
if (fbcValue) {
    purchaseMeta.fbc = fbcValue;
}
```

**Аналогично для Lead события (строки 2069-2075)**

---

### Исправление #2: Убедиться что external_id всегда определяется

**Файл:** `twocomms/storefront/views/checkout.py`

**Строки 255-270:**
```python
# БЫЛО:
external_source = None
if request.user.is_authenticated:
    external_source = f"user:{request.user.id}"
elif order.session_key:
    external_source = f"session:{order.session_key}"
else:
    try:
        session_key = request.session.session_key
    except Exception:
        session_key = None
    if session_key:
        external_source = f"session:{session_key}"
if not external_source and order.order_number:
    external_source = f"order:{order.order_number}"

# ДОЛЖНО БЫТЬ:
external_source = None
if request.user.is_authenticated:
    external_source = f"user:{request.user.id}"
else:
    # Пытаемся получить session_key
    try:
        session_key = request.session.session_key
        if session_key:
            external_source = f"session:{session_key}"
    except Exception:
        pass
    
    # Если нет session_key, используем order_number
    if not external_source and order.order_number:
        external_source = f"order:{order.order_number}"
    
    # Если нет order_number, используем order.id
    if not external_source and order.id:
        external_source = f"order:{order.id}"

# ВСЕГДА должно быть значение
if not external_source:
    external_source = f"order:unknown_{int(time.time())}"
```

---

### Исправление #3: Синхронизация external_id на клиенте и сервере

**Файл:** `twocomms/twocomms_django_theme/templates/pages/order_success.html`

**Строки 1873-1886:**
```javascript
// БЫЛО:
var externalSource = '';
if (userIdAttr) {
    externalSource = 'user:' + userIdAttr;
} else if (sessionKey) {
    externalSource = 'session:' + sessionKey;
} else if (orderNumber) {
    externalSource = 'order:' + orderNumber;
} else if (orderId) {
    externalSource = 'order:' + orderId;
}

// ДОЛЖНО БЫТЬ:
// Используем тот же формат что и на сервере
var externalSource = '';
if (userIdAttr) {
    externalSource = 'user:' + userIdAttr;
} else if (sessionKey) {
    externalSource = 'session:' + sessionKey;
} else if (orderNumber) {
    // Используем orderNumber (строка типа "TWC..."), а не orderId (число)
    externalSource = 'order:' + orderNumber;
} else {
    // Fallback - использовать orderId только если нет orderNumber
    externalSource = 'order:' + (orderId || 'unknown');
}
```

---

### Исправление #4: Проверка настроек TikTok Events API

**Файл:** `twocomms/twocomms/settings.py`

**Добавить:**
```python
# TikTok Events API
TIKTOK_EVENTS_ACCESS_TOKEN = os.environ.get('TIKTOK_EVENTS_ACCESS_TOKEN', '')
TIKTOK_EVENTS_PIXEL_CODE = os.environ.get('TIKTOK_EVENTS_PIXEL_CODE', '')
TIKTOK_EVENTS_TEST_EVENT_CODE = os.environ.get('TIKTOK_EVENTS_TEST_EVENT_CODE', None)
```

**Проверить в ENV:**
- `TIKTOK_EVENTS_ACCESS_TOKEN` должен быть установлен
- `TIKTOK_EVENTS_PIXEL_CODE` должен быть установлен

---

### Исправление #5: Улучшение логирования TikTok Events API

**Файл:** `twocomms/orders/tiktok_events_service.py`

**Строки 29-43:**
```python
# БЫЛО:
if not self.access_token or not self.pixel_code:
    logger.warning(
        "TikTok Events API не настроен! "
        "Необходимо установить TIKTOK_EVENTS_ACCESS_TOKEN и TIKTOK_EVENTS_PIXEL_CODE в ENV."
    )
    self.enabled = False

# ДОЛЖНО БЫТЬ:
if not self.access_token or not self.pixel_code:
    logger.error(
        "❌ TikTok Events API не настроен! "
        "Необходимо установить TIKTOK_EVENTS_ACCESS_TOKEN и TIKTOK_EVENTS_PIXEL_CODE в ENV. "
        f"Access Token: {'установлен' if self.access_token else 'НЕ установлен'}, "
        f"Pixel Code: {'установлен' if self.pixel_code else 'НЕ установлен'}"
    )
    self.enabled = False
else:
    logger.info(
        f"✅ TikTok Events API настроен: Pixel Code={self.pixel_code[:10]}..."
    )
```

---

## ✅ ЧЕКЛИСТ ПРОВЕРКИ

### Критические проверки (сделать немедленно):

- [ ] **Проверить Event ID синхронизацию:**
  - [ ] Клиент: `'{{ order.get_facebook_event_id }}'`
  - [ ] Сервер: `order.get_facebook_event_id()`
  - [ ] Убедиться, что они всегда одинаковые

- [ ] **Проверить External ID синхронизацию:**
  - [ ] Клиент: формат `'user:{id}'` или `'session:{key}'` или `'order:{number}'`
  - [ ] Сервер: тот же формат
  - [ ] Убедиться, что external_id всегда определяется

- [ ] **Проверить FBP передачу:**
  - [ ] В order_success.html: передается ли fbp в `__meta`
  - [ ] В checkout.py: сохраняется ли fbp в payment_payload
  - [ ] В CAPI: передается ли fbp если есть

- [ ] **Проверить FBC передачу:**
  - [ ] В order_success.html: передается ли fbc в `__meta`
  - [ ] В checkout.py: сохраняется ли fbc в payment_payload
  - [ ] В CAPI: передается ли fbc если есть

- [ ] **Проверить TikTok Events API:**
  - [ ] Установлены ли `TIKTOK_EVENTS_ACCESS_TOKEN` и `TIKTOK_EVENTS_PIXEL_CODE`
  - [ ] Работает ли отправка событий (проверить логи)
  - [ ] Отправляются ли Purchase события при payment_status='paid'

### Средние проверки (сделать в ближайшее время):

- [ ] **Проверить хеширование данных:**
  - [ ] Email: lowercase и SHA-256 на клиенте и сервере
  - [ ] Phone: только цифры и SHA-256 на клиенте и сервере
  - [ ] External ID: SHA-256 на клиенте и сервере

- [ ] **Проверить покрытие событий:**
  - [ ] Meta: покрытие должно быть ≥75%
  - [ ] Проверить в Meta Events Manager → Event Coverage
  - [ ] Проверить дедупликацию (должно быть 1 событие, не 2)

- [ ] **Проверить качество сопоставления:**
  - [ ] Meta: качество должно быть ≥7/10
  - [ ] Проверить в Meta Events Manager → Event Quality
  - [ ] Убедиться, что email/phone/fbc передаются

### Желательные проверки (можно отложить):

- [ ] **Проверить Google Tags:**
  - [ ] Настроены ли Google Tags в GTM
  - [ ] Если нет - удалить или настроить

- [ ] **Проверить неактивные события:**
  - [ ] CompleteRegistration: почему неактивен
  - [ ] TestEvent: удалить если не нужен

---

## 📝 ЗАКЛЮЧЕНИЕ

Этот отчет содержит детальный анализ всех проблем системы трекинга Meta и TikTok. Исполнитель должен:

1. **Изучить все найденные проблемы** и их причины
2. **Применить все исправления** в указанном порядке
3. **Проверить** все точки из чеклиста
4. **Протестировать** изменения в тестовой среде
5. **Мониторить** метрики после развертывания

**Важно:** После исправлений проверить:
- Meta Events Manager → Event Coverage (должно быть ≥75%)
- Meta Events Manager → Event Quality (должно быть ≥7/10)
- Meta Events Manager → Deduplication (должно быть 100%)
- TikTok Events Manager → Purchase события должны появиться

---

**Дата создания:** 2025-01-30  
**Версия:** 1.0  
**Статус:** ✅ Готово к использованию














