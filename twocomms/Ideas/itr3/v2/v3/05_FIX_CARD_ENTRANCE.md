# 🟡 FIX #5: Card Entrance — CSS↔JS Sync

> **Severity:** MAJOR | **Файли:** `animations.css`, `dtf.js`
> **Дефект:** A-2 — Розрив між CSS таргетами і JS тригером

---

## СУТЬ ПРОБЛЕМИ

### CSS (animations.css, рядки ~72-130) визначає анімації для:
```css
.work-card, .proof-card, .hero-card, .info-card, 
.price-row, .feature-card, .step-card
```

Кожен з цих класів потребує `.is-visible` для активації (через `opacity: 0` → `opacity: 1` і `translateY(18px)` → `translateY(0)`).

### JS (dtf.js, initCardReveal, рядки ~409-448):
```javascript
const cards = collectTargets(root, 
  '.work-card, .proof-card, .hero-card, .info-card, .price-row, .feature-card, .step-card'
);
```

**Селектори в JS і CSS СПІВПАДАЮТЬ** — це вже виправлено в dtf.js.

### ПРОТЕ:

**Проблема 1:** CSS stagger через `--card-stagger` НЕ завжди правильно працює. У CSS анімаціях stagger ≠ `transition-delay` у деяких випадках.

**Проблема 2:** `.step-card` → в HTML це `.step`, НЕ `.step-card`. JavaScript таргетить `.step-card`, а в `index.html` (рядки 228-264) клас = `.step`.

---

## ЩО ЗРОБИТИ

### Крок 1: Виправити невідповідність `.step` vs `.step-card`

**Варіант A (рекомендований):** Додати `.step` до JS:
```javascript
const cards = collectTargets(root, 
  '.work-card, .proof-card, .hero-card, .info-card, .price-row, .feature-card, .step-card, .step'
);
```

**Варіант B:** Змінити клас в HTML на `.step-card`. Але це ризикований рефакторинг — можуть зламатися CSS стилі.

### Крок 2: Додати CSS анімацію для `.step`

У `animations.css`, додати `.step` до блоку card entrance:

```css
.step {
  opacity: 0;
  transform: translateY(18px);
  transition: opacity 0.5s ease, transform 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94);
  transition-delay: var(--card-stagger, 0ms);
}
.step.is-visible {
  opacity: 1;
  transform: translateY(0);
}
```

### Крок 3: Перевірити інші можливі невідповідності

Запустити пошук:
```bash
grep -rn 'data-reveal' twocomms/dtf/templates/ | head -40
```

Перевірити, що `data-reveal` завжди на батьку, а НЕ на самих картках. Якщо `data-reveal` на батьку — існуючий JS `initCardReveal` таргетить його дітей через `collectTargets()`.

### Крок 4: Перевірити stagger логіку

Поточний JS:
```javascript
const applyStagger = (card, index) => {
  card.style.setProperty('--card-stagger', `${Math.min((index % 6) * 70, 280)}ms`);
};
```

Це дає: 0ms, 70ms, 140ms, 210ms, 280ms, 280ms (capped). Для 4 кроків (steps) це адекватно. Перевірити візуально.

---

## ПЕРЕВІРКА

1. Скролити сторінку — картки і кроки з'являються з анімацією (знизу вверх, послідовно)
2. На мобільному (320px) — без лагів, анімації плавні
3. `prefers-reduced-motion` — елементи видимі одразу, без анімації
4. Кроки "Як це працює" (4 штуки) анімуються послідовно з stagger
