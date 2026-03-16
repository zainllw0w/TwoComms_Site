# 🟡 FIX #7: Telegram Prefill — Контекстні Тексти (K4)

> **Severity:** MODERATE | **Файли:** `base.html`, `index.html`, `order.html`, `quality.html`, `constructor_app.html`, та інші
> **Дефект:** K4 — Всюди однаковий текст "Хочу замовити DTF-друк 60 см"

---

## СУТЬ ПРОБЛЕМИ

Telegram-посилання у header, footer, hero, mobile-dock, тощо — ВСІ містять ОДНАКОВИЙ prefill:
```
Привіт! Хочу замовити DTF-друк 60 см. Підкажіть, будь ласка, по ціні та термінах.
```

За специфікацією кожна сторінка повинна мати **контекстний** prefill.

---

## ПЛАН ЗАМІН

### 1. HOME (`index.html`)
Залишити поточний текст (він вже контекстний для головної):
- UA: `Привіт! Хочу замовити DTF-друк 60 см. Підкажіть, будь ласка, по ціні та термінах.`

### 2. ORDER (`order.html`)
- UA: `Привіт! Заповнюю замовлення на сайті, маю питання щодо мого файлу.`
- RU: `Привет! Заполняю заказ на сайте, есть вопрос по моему файлу.`
- EN: `Hi! I'm filling out an order on your site and have a question about my file.`

### 3. CONSTRUCTOR (`constructor_app.html`, `constructor_landing.html`)
- UA: `Привіт! Збираю лист 60 см у конструкторі, потрібна допомога з розкладкою.`
- RU: `Привет! Собираю лист 60 см в конструкторе, нужна помощь с раскладкой.`
- EN: `Hi! I'm building a 60 cm sheet in the constructor and need help with the layout.`

### 4. QUALITY (`quality.html`)
- UA: `Привіт! Переглядаю сторінку якості, хочу дізнатись більше про ваші стандарти друку.`
- RU: `Привет! Смотрю страницу качества, хочу узнать больше о ваших стандартах печати.`
- EN: `Hi! Looking at your quality page, I'd like to know more about your print standards.`

### 5. GALLERY (`gallery.html`)
- UA: `Привіт! Бачу приклади у галереї — хочу обговорити друк подібного.`
- RU: `Привет! Вижу примеры в галерее — хочу обсудить печать подобного.`
- EN: `Hi! I see examples in the gallery — I'd like to discuss printing something similar.`

### 6. PRICE (`price.html`)
- UA: `Привіт! Переглядаю прайс. Підкажіть по моєму обсягу.`
- RU: `Привет! Смотрю прайс. Подскажите по моему объему.`
- EN: `Hi! Checking your prices. Can you advise on my volume?`

### 7. REQUIREMENTS (`requirements.html`)
- UA: `Привіт! Маю питання щодо вимог до файлу.`
- RU: `Привет! Есть вопрос по требованиям к файлу.`
- EN: `Hi! I have a question about file requirements.`

### 8. FAQ (`faq.html`)
- UA: `Привіт! Прочитав FAQ, але маю додаткове питання.`
- RU: `Привет! Прочитал FAQ, но есть дополнительный вопрос.`
- EN: `Hi! Read the FAQ, but have another question.`

### 9. HEADER / FOOTER / MOBILE DOCK (`base.html`)

**Глобальний fallback** (для сторінок без спеціального prefill):
Використовувати поточний загальний текст.

**Підхід для base.html:**
```html
<a href="https://t.me/twocomms?text={% block tg_prefill %}{% if current_lang == 'ru' %}{{ 'Привет! Хочу заказать DTF-печать 60 см. Подскажите, пожалуйста, по цене и срокам.'|urlencode }}{% elif current_lang == 'en' %}{{ 'Hi! I want to order DTF print (60 cm). Please tell me the price and timing.'|urlencode }}{% else %}{{ 'Привіт! Хочу замовити DTF-друк 60 см. Підкажіть, будь ласка, по ціні та термінах.'|urlencode }}{% endif %}{% endblock %}" ...>
```

Кожен дочірній шаблон може override `{% block tg_prefill %}`.

---

## ТЕХНІЧНА РЕАЛІЗАЦІЯ

### Варіант A — Django Template Block (рекомендований)
Замінити hardcoded text у `base.html` на `{% block tg_prefill %}...{% endblock %}`.
В кожному child template override цей блок.

### Варіант B — Data attribute на body
```html
<body data-page="order" data-tg-prefill="...">
```
JS зчитує і підставляє у всі Telegram-лінки. Більш складно.

### Варіант C — Context variable
У Django views: `context['tg_prefill'] = '...'` → template usage `{{ tg_prefill|urlencode }}`.

> **Рекомендую Варіант A** (найпростіший, без JS, без backend змін).

---

## ПЕРЕВІРКА

1. Відкрити кожну сторінку
2. Натиснути на Telegram-лінк у header/footer/hero
3. У Telegram має відкритись діалог з **контекстним** текстом
4. Порівняти з таблицею вище
5. Перевірити на 3 мовах
