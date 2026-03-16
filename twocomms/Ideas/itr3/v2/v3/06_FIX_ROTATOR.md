# 🟡 FIX #6: Header Rotator — 3+ Фрази

> **Severity:** MODERATE | **Файли:** `base.html`, `dtf.js`
> **Дефект:** UI-2 — Показує лише одну фразу замість трьох

---

## СУТЬ ПРОБЛЕМИ

У `base.html` (рядки 162-170) є `header-status-chip`:
```html
<span class="header-status-chip">
  {% if current_lang == 'ru' %}
    Печатаем от 1 метра · отправка по Украине
  {% elif current_lang == 'en' %}
    Printing from 1 meter · shipped across Ukraine
  {% else %}
    Друкуємо від 1 метра · відправка по Україні
  {% endif %}
</span>
```

Це **СТАТИЧНИЙ** текст. За специфікацією має бути ротатор — мінімум 3 фрази, що змінюються з анімацією.

---

## ЩО ЗРОБИТИ

### Крок 1: Змінити HTML на data-driven ротатор

Замінити блок `header-status-chip` у `base.html` (рядки ~162-170):

```html
<span class="header-status-chip" 
      data-rotator
      data-rotator-interval="5000"
      data-rotator-phrases='{% if current_lang == "ru" %}["Печатаем от 1 метра · отправка по Украине","Файл проверяем до печати · нюансы согласуем","Бесплатный тест-пак · оплата только доставки"]{% elif current_lang == "en" %}["Printing from 1 meter · shipped across Ukraine","File checked before printing · details confirmed","Free test pack · shipping only"]{% else %}["Друкуємо від 1 метра · відправка по Україні","Файл перевіряємо до друку · нюанси погоджуємо","Безкоштовний тест-пак · оплата лише доставки"]{% endif %}'>
  {% if current_lang == 'ru' %}
    Печатаем от 1 метра · отправка по Украине
  {% elif current_lang == 'en' %}
    Printing from 1 meter · shipped across Ukraine
  {% else %}
    Друкуємо від 1 метра · відправка по Україні
  {% endif %}
</span>
```

> Перша фраза видна одразу (SSR/no-JS fallback). JS підхоплює і ротує.

### Крок 2: Додати JS ротатор у `dtf.js`

Додати нову функцію `initHeaderRotator()`:

```javascript
function initHeaderRotator() {
  var chip = document.querySelector('[data-rotator]');
  if (!chip) return;
  if (prefersReduced) return;  // без анімації
  
  var phrasesAttr = chip.getAttribute('data-rotator-phrases');
  var phrases = [];
  try {
    phrases = JSON.parse(phrasesAttr);
  } catch(e) { return; }
  if (phrases.length < 2) return;
  
  var interval = parseInt(chip.getAttribute('data-rotator-interval') || '5000', 10);
  var currentIndex = 0;
  
  setInterval(function() {
    currentIndex = (currentIndex + 1) % phrases.length;
    chip.style.opacity = '0';
    chip.style.transform = 'translateY(-4px)';
    
    setTimeout(function() {
      chip.textContent = phrases[currentIndex];
      chip.style.opacity = '1';
      chip.style.transform = 'translateY(0)';
    }, 260);
  }, interval);
  
  // Додати CSS transition
  chip.style.transition = 'opacity 250ms ease, transform 250ms ease';
}
```

### Крок 3: Підключити у `initAll()`

```javascript
initHeaderRotator();
```

### Крок 4: CSS підтримка

Додати у `dtf.css` (або `animations.css`):
```css
.header-status-chip[data-rotator] {
  transition: opacity 250ms ease, transform 250ms ease;
}
@media (prefers-reduced-motion: reduce) {
  .header-status-chip[data-rotator] {
    transition: none;
  }
}
```

---

## ФРАЗИ (3 мови × 3 фрази)

| # | UA | RU | EN |
|---|----|----|-----|
| 1 | Друкуємо від 1 метра · відправка по Україні | Печатаем от 1 метра · отправка по Украине | Printing from 1 meter · shipped across Ukraine |
| 2 | Файл перевіряємо до друку · нюанси погоджуємо | Файл проверяем до печати · нюансы согласуем | File checked before printing · details confirmed |
| 3 | Безкоштовний тест-пак · оплата лише доставки | Бесплатный тест-пак · оплата только доставки | Free test pack · shipping only |

---

## ПЕРЕВІРКА

1. При завантаженні — видна перша фраза
2. Через 5 сек — плавне перемикання на другу
3. Ще через 5 сек — третя
4. Далі цикл повторюється
5. `prefers-reduced-motion` — ротація без анімації або тільки перша фраза
6. No-JS — видна перша фраза (SSR fallback)
7. Перевірити на 3 мовах
