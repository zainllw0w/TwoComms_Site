# 🟡 FIX #4: Інтеграція 7 Невикористаних SVG Іконок

> **Severity:** MAJOR | **Файли:** різні шаблони HTML
> **Дефект:** S-2 — 7 з 15 SVG іконок не інтегровані (47% ассетів "мертвий вантаж")

---

## СУТЬ ПРОБЛЕМИ

Agent4 створив 15 якісних SVG іконок. Agent3 використав тільки 8 з них. Решта 7 лежать у `dtf/static/dtf/svg/` без підключення до HTML.

### Поточний стан

| Іконка | Файл існує | Впроваджена | Де використовується |
|--------|-----------|-------------|---------------------|
| `icon-check.svg` | ✅ | ✅ | constructor_app, order, preflight |
| `icon-info.svg` | ✅ | ✅ | constructor_app, order |
| `icon-warning.svg` | ✅ | ✅ | constructor_app, order, preflight |
| `icon-fix.svg` | ✅ | ✅ | constructor_app, order |
| `icon-bulb.svg` | ✅ | ⚠️ | Неправильне місце (FIX #2) |
| `icon-telegram.svg` | ✅ | ✅ | constructor_app, order |
| `icon-upload.svg` | ✅ | ✅ | constructor_app, order |
| `icon-shield.svg` | ✅ | ✅ | constructor_app, order |
| **`icon-file.svg`** | ✅ | ❌ | **Нігде** |
| **`icon-scan.svg`** | ✅ | ❌ | **Нігде** |
| **`icon-truck.svg`** | ✅ | ❌ | **Нігде** |
| **`icon-sheet60.svg`** | ✅ | ❌ | **Нігде** |
| **`icon-palette.svg`** | ✅ | ❌ | **Нігде** |
| **`icon-clock.svg`** | ✅ | ❌ | **Нігде** |
| **`icon-calculator.svg`** | ✅ | ❌ | **Нігде** |

---

## ПЛАН РОЗМІЩЕННЯ

### 1. `icon-file.svg` — Dropzone / upload секція

**Де:** `order.html` та `constructor_app.html` — біля зони завантаження файлу.

```html
<span class="dtf-icon dtf-icon-file" aria-hidden="true">
  {% include 'dtf/svg/icon-file.svg' %}
</span>
```

**Контекст:** Поруч із текстом "Завантажити файл" або в dropzone placeholder.

### 2. `icon-scan.svg` — Статус перевірки файлу

**Де:** `order.html` та `constructor_app.html` — біля статусу "Перевіряємо файл…"

```html
<span class="dtf-icon dtf-icon-scan" aria-hidden="true">
  {% include 'dtf/svg/icon-scan.svg' %}
</span>
```

**Контекст:** Поруч із лоадером/статусом перевірки. Анімація `scan-line` вже готова в `icons.css`.

### 3. `icon-truck.svg` — Доставка

**Де:** 
- `index.html` — крок 4 "Відправляємо Новою поштою" (рядок ~256, `.step-icon[data-step="4"]`)
- `delivery_payment.html` — секція доставки
- `status.html` — біля статусу "Відправлено"

```html
<span class="dtf-icon dtf-icon-truck" aria-hidden="true">
  {% include 'dtf/svg/icon-truck.svg' %}
</span>
```

### 4. `icon-sheet60.svg` — Конструктор / Лист 60 см

**Де:**
- `constructor_landing.html` або `constructor_app.html` — у заголовку або інструкції
- `index.html` — крок 1 "Надсилаєте лист 60 см" (рядок ~229, `.step-icon[data-step="1"]`)

```html
<span class="dtf-icon dtf-icon-sheet60" aria-hidden="true">
  {% include 'dtf/svg/icon-sheet60.svg' %}
</span>
```

### 5. `icon-palette.svg` — Кольори / якість

**Де:**
- `requirements.html` — секція про кольори / колірний профіль
- `quality.html` — секція про кольоропередачу
- `index.html` — "Як це працює" крок 2 (рядок ~238, `.step-icon[data-step="2"]`)

### 6. `icon-clock.svg` — Терміни / час

**Де:**
- `index.html` — FAQ "Скільки чекати?" (рядок ~789)
- `delivery_payment.html` — інформація про терміни
- `price.html` — біля коментаря "24-48 год"

### 7. `icon-calculator.svg` — Калькулятор / розрахунок

**Де:**
- `index.html` — секція `estimate-section` (рядок ~170), біля "ОРІЄНТИР ЦІНИ"
- `price.html` — біля калькулятора/таблиці цін

---

## ФОРМАТ ВСТАВКИ

Для КОЖНОЇ іконки однаковий паттерн:

```html
<span class="dtf-icon dtf-icon-{NAME}" aria-hidden="true">
  {% include 'dtf/svg/icon-{NAME}.svg' %}
</span>
```

Де `{NAME}` = file, scan, truck, sheet60, palette, clock, calculator.

> [!IMPORTANT]
> НЕ додавай клас `dtf-icon-animate` статично! Це робить JS (FIX #3).

---

## ПЕРЕВІРКА

1. Відкрити сторінку з іконкою
2. Іконка видима, правильного кольору (inherit від батьківського)
3. Не ламає layout на мобільному (320px)
4. `aria-hidden="true"` присутній
5. Іконка правильного розміру (24×24 або як визначено батьківським `.dtf-icon`)

---

## МОЖЛИВІ ПОКРАЩЕННЯ (НА РОЗСУД AGENT3)

- Замінити поточні SVG-ікони кроків (`step-upload.svg`, `step-preflight.svg`, тощо у `index.html` рядки 230-257) на нові `icon-*` іконки, якщо вони виглядають краще
- Додати іконки до info-card блоків для візуального збагачення
- Враховувати, що деякі іконки можуть бути не потрібні на кожній сторінці — використовуй здоровий глузд
