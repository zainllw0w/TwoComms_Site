# 🔴 FIX #2: Лампочка (icon-bulb) → Homepage

> **Severity:** CRITICAL | **Файли:** `index.html`, `icons.css`
> **Користувач побачив:** "лампочку я нігде на сайті не побачив"

---

## СУТЬ ПРОБЛЕМИ

### Що має бути
`icon-bulb.svg` — у секції `why-us` на **головній сторінці** (`index.html`), поруч із текстом "Стабільне виробництво — друкуємо без пауз".

### Що зараз
`icon-bulb.svg` знаходиться ТІЛЬКИ в:
- `constructor_app.html` рядок 159 — всередині `preflight-terms` (НЕПРАВИЛЬНЕ місце)
- `order.html` рядок 105 — всередині `preflight-terms` (НЕПРАВИЛЬНЕ місце)

На `index.html` лампочка **ВІДСУТНЯ**.

---

## ЩО ЗРОБИТИ

### Крок 1: Додати icon-bulb в `index.html`

Знайти секцію `why-us` (рядок ~271) і в списку `<ul class="list">` знайти елемент з текстом "Стабільне виробництво — друкуємо без пауз" (рядок ~280).

**Замінити:**
```html
<li>{% if current_lang == 'ru' %}Стабильное производство — печатаем без пауз.{% elif current_lang == 'en' %}Stable production — printing without pauses.{% else %}Стабільне виробництво — друкуємо без пауз.{% endif %}</li>
```

**На:**
```html
<li>
  <span class="dtf-icon dtf-icon-bulb" aria-hidden="true">
    {% include 'dtf/svg/icon-bulb.svg' %}
  </span>
  {% if current_lang == 'ru' %}Стабильное производство — печатаем без пауз.{% elif current_lang == 'en' %}Stable production — printing without pauses.{% else %}Стабільне виробництво — друкуємо без пауз.{% endif %}
</li>
```

> [!IMPORTANT]
> Зверни увагу: НЕ додавай клас `dtf-icon-animate` статично! Анімація буде додаватись через JS (див. FIX #3).

### Крок 2: Стилізація для inline-іконки

У `dtf.css` або в окремий CSS, додати стиль для іконки всередині `<li>`:

```css
.list li .dtf-icon {
  vertical-align: middle;
  margin-right: 6px;
  color: var(--dtf-accent, #f97316);
  width: 20px;
  height: 20px;
}
```

### Крок 3: Перевірити CSS анімацію (окремо від FIX #3)

У `icons.css` поточна анімація `soft-glow` для bulb (рядок 45-46):
```css
.dtf-icon-bulb.dtf-icon-animate {
  animation: soft-glow 2.4s ease-in-out infinite;  /* ← НЕПРАВИЛЬНО */
}
```

**Повна заміна виконується у FIX #3**, але для bulb:
- Має бути: blink раз на 7-9 секунд, тривалість 200-260ms
- НЕ `animation: infinite` — а JS `setInterval()` який додає/прибирає клас

---

## ПЕРЕВІРКА

1. Відкрити `https://dtf.twocomms.shop/` (або локально)
2. Прокрутити до секції "Чому з нами спокійніше"
3. Біля "Стабільне виробництво — друкуємо без пауз" має бути видима іконка лампочки оранжевого кольору
4. Перевірити на 3 мовах (UA/RU/EN)
5. Перевірити на мобільному (320px) — іконка не ламає layout
