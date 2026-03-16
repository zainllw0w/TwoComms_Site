# 🔴 FIX #1: Dot Distortion — Repulsion Physics + Static Field

> **Severity:** CRITICAL | **Файл:** `dtf/static/dtf/js/dtf.js` | **Функція:** `initHomeDotBackground()`
> **Рядки коду:** 1210–1667 (повна функція), 1461–1473 (CORE BUG)

---

## СУТЬ ПРОБЛЕМИ

### Дефект D-1: Velocity-Following замість Repulsion

**Що має бути:** Точки ВІДШТОВХУЮТЬСЯ від позиції курсора (repulsion). Курсор = магніт з полюсом "мінус", точки = однойменний полюс.

**Що зараз:** Точки "розмазуються" В НАПРЯМКУ РУХУ миші (velocity-following). Це зовсім ІНША фізика.

### Технічний розбір

Поточний код (рядки 1461–1473 у `dtf.js`):
```javascript
// ПОТОЧНИЙ КОД (ПОМИЛКОВИЙ):
for (let i = 0; i < dots.length; i += 1) {
  const dot = dots[i];
  const dx = px - dot.x;        // ← вектор ДО курсора (для distance)
  const dy = py - dot.y;
  const dist = Math.max(0.001, Math.hypot(dx, dy));
  let influence = 0;

  if (state.pointerInside && isMoving && dist < radius) {
    influence = 1 - dist / radius;
    const force = influence * influence * distortionStrength;
    dot.vx += state.pointerDx * force * velocityKick;  // ← BUG: pointerDx це ШВИДКІСТЬ МИШІ
    dot.vy += state.pointerDy * force * velocityKick;  // ← BUG: pointerDy це ШВИДКІСТЬ МИШІ
  }
  // ... далі spring-back, friction, etc.
}
```

**Проблеми:**
1. `state.pointerDx` / `state.pointerDy` — це **дельта позиції курсора між фреймами** (швидкість руху), а НЕ вектор "від курсора до точки"
2. Сила направлена **в бік руху курсора**, а не **від курсора**
3. Умова `isMoving` — якщо курсор стоїть нерухомо, ефект = 0 (нема взаємодії)

### Дефект D-2: Відсутнє статичне поле

**Специфікація** (`ITER3_05_UI_MICROPACK.md`, секція 8): `staticField ≈ 0.15` — навіть при нерухомому курсорі всередині grid має бути м'яке постійне відштовхування.

**Поточний код:** Умова `if (state.pointerInside && isMoving && ...)` — `isMoving` блокує будь-який ефект при нерухомому курсорі.

---

## ЩО ЗМІНИТИ

### Крок 1: Замінити velocity-following на repulsion

У функції `renderCanvas()` (рядки ~1461–1473), замінити блок розрахунку сили:

```javascript
// НОВА ЛОГІКА (REPULSION):
for (let i = 0; i < dots.length; i += 1) {
  const dot = dots[i];
  // Вектор ВІД курсора ДО точки (для repulsion)
  const dx = dot.x - px;  // ← ЗМІНЕНО: від курсора ДО точки
  const dy = dot.y - py;  // ← ЗМІНЕНО: від курсора ДО точки
  const dist = Math.max(0.001, Math.hypot(dx, dy));
  let influence = 0;

  if (state.pointerInside && dist < radius) {
    influence = 1 - dist / radius;
    const nx = dx / dist;  // normalized direction
    const ny = dy / dist;
    
    // Static repulsion (завжди активне коли курсор всередині)
    const staticForce = influence * 0.15;  // staticField ≈ 0.15
    dot.vx += nx * staticForce;
    dot.vy += ny * staticForce;
    
    // Dynamic repulsion (посилена при русі курсора)
    if (isMoving) {
      const dynamicForce = influence * influence * distortionStrength;
      dot.vx += nx * dynamicForce;
      dot.vy += ny * dynamicForce;
    }
  }
  
  // ЗБЕРІГТИ ВСЕ ДАЛІ (spring-back, friction, displacement clamp, etc.)
  dot.x += dot.vx * frameScale;
  dot.y += dot.vy * frameScale;
  dot.x += (dot.gridX - dot.x) * returnSpeed * frameScale;
  dot.y += (dot.gridY - dot.y) * returnSpeed * frameScale;
  // ...
}
```

### Крок 2: Видалити або адаптувати `velocityKick`

Змінна `velocityKick` більше не потрібна для repulsion. Видали або закоментуй рядок:
```javascript
// ВИДАЛИТИ АБО ЗАКОМЕНТУВАТИ:
const velocityKick = ambientTier >= 4 ? 0.3 : ambientTier >= 3 ? 0.285 : 0.24;
```

### Крок 3: Тестування параметрів

Параметри, які потрібно налаштувати (почни з цих значень і підбери найкращі):

| Параметр | Значення | Опис |
|----------|---------|------|
| `staticField` | 0.15 | Сила статичного відштовхування |
| `distortionStrength` | Залишити поточні (1.0 / 1.12 / 1.2 по тірам) | Сила динамічного відштовхування |
| `influenceRadius` | Залишити поточні (82-110 по тірам) | Радіус впливу |
| `returnSpeed` | Залишити (0.052-0.06) | Швидкість повернення до grid |
| `friction` | Залишити (0.9-0.92) | Тертя |
| `spring` | Залишити (0.017-0.02) | Пружність |

---

## ЩО ЗБЕРЕГТИ (НЕ ЧІПАТИ)

- ✅ Систему тірів (`resolveAmbientTier`, tier 0-4)
- ✅ Палітру кольорів (blue/amber profiles)
- ✅ Canvas-підхід і весь рендеринг кольорів (рядки 1503-1543)
- ✅ CSS-fallback змінні (`--dot-pointer-x`, etc.)
- ✅ `is-static` для prefers-reduced-motion
- ✅ Throttling по `frameBudget`
- ✅ `document.hidden` перевірку
- ✅ Breathing (дихання ±15%) — `breathe = 1 + Math.sin(time * breathingSpeed + dot.phase) * 0.15`
- ✅ Random glow pulses — `glowChance` → `dot.glowUntil`
- ✅ Spring-back до grid — `returnSpeed` + `spring`
- ✅ Friction — `dot.vx *= friction`
- ✅ Displacement clamp — `maxDisp`
- ✅ Orb parallax рух — `orbs.forEach()`
- ✅ Всі event listeners (`updateTarget`, `resetTarget`, `boot`)
- ✅ Canvas resize logic

---

## ВІЗУАЛЬНИЙ ТЕСТ

Після зміни ти повинен побачити:

1. **Desktop:** При наведенні курсора на точки — точки "тікають" від курсора у всі сторони. Рух курсора створює "хвилю" що розштовхує точки.
2. **Нерухомий курсор:** Якщо курсор стоїть нерухомо всередині grid — точки навколо нього м'яко відштовхнуті (staticField).
3. **Після відведення курсора:** Точки м'яко повертаються на місце (spring-back).
4. **Дихання:** Точки продовжують дихати (±15%) незалежно від курсора.
5. **Glow:** Випадкові точки інколи яскраво спалахують.

---

## MOBILE СПЕЦИФІКА

- Tier 1-2 (mobile): `influenceRadius` вже зменшений до 82-92px — залишити
- Touch: `touchmove` / `pointermove` вже підключені через `updateTarget()` — залишити
- Max dots: ≤620 (tier 2) — вже обмежено через `quality.maxDots`
- Дихання: вже уповільнене через `breathingSpeed` — залишити
- Glow: вже знижена ймовірність — залишити

---

## ❌ ЧОГО НЕ РОБИТИ

- Не використовувати WebGL/шейдери
- Не додавати blur/filter на canvas
- Не збільшувати кількість точок
- Не робити анімацію при `saveData` або `2g`
- Не видаляти існуюючі fallback-и
