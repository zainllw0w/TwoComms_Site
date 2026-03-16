# 🔴 FIX #10: Image Compare Slider — Повне Виправлення

> **Severity:** CRITICAL | **Файли:** `effect.compare.js`, `effect.compare.css`
> **Шаблони:** `index.html` (proof-grid), `quality.html`, `gallery.html`, `effects_lab.html`

---

## СУТЬ ПРОБЛЕМИ (ВІД КОРИСТУВАЧА)

Користувач описав проблеми:
1. **"Движение не совсем правильное"** — slider handle рухається неочікувано
2. **"Одна картинка увеличивается"** — замість "reveal" ефекту (одна покриває іншу), зображення масштабується
3. **Общий polish** — slider не виглядає premium

---

## ПОТОЧНА РЕАЛІЗАЦІЯ

### HTML структура (`index.html`, рядки 522-591):
```html
<article class="proof-card compare-card" 
         data-compare 
         data-effect="compare" 
         data-compare-mode="hover"          <!-- mode: hover / drag / autoplay -->
         data-autoplay="true" 
         data-autoplay-duration="6000">
  <div class="compare-media asset-slot">
    <div class="compare-layer compare-before">
      <picture>...</picture>
    </div>
    <div class="compare-layer compare-after">
      <picture>...</picture>
    </div>
    <div class="compare-handle" aria-hidden="true"></div>
  </div>
  <input class="compare-range" type="range" min="0" max="100" value="55"
         aria-label="{% trans 'Порівняння якості' %}">
  <div class="proof-meta">...</div>
</article>
```

### CSS (`effect.compare.css`, 203 рядки):

Ключовий механізм — CSS variable `--compare`:
```css
.compare-media {
  --compare: 55;  /* position 0-100 */
}
.compare-before {
  clip-path: inset(0 calc((100 - var(--compare)) * 1%) 0 0);
  /* ← Ось ЦЕ може бути проблемою! */
}
.compare-after {
  clip-path: inset(0 0 0 calc(var(--compare) * 1%));
  /* ← Це правильний підхід */
}
```

### JS (`effect.compare.js`, 240 рядків):

Три режими:
- **drag** — перетягування handle
- **hover** — handle слідує за позицією миші
- **autoplay** — автоматичне quality (left-right-left)

---

## ПРОБЛЕМИ В ПОТОЧНОМУ КОДІ

### Проблема 1: `clip-path: inset()` vs `width`

Поточний CSS використовує `clip-path: inset(...)` — це ПРАВИЛЬНИЙ підхід для compare slider. ОДНАК перевірити що `compare-before` і `compare-after` обидва мають `position: absolute` і `inset: 0` (або `width: 100%; height: 100%`).

Якщо один з шарів НЕ absolute — він буде "масштабуватись" замість "обрізатись", що створює ефект "збільшення".

**Перевірити:**
```css
.compare-layer {
  position: absolute;
  inset: 0;
  /* АБО */
  width: 100%;
  height: 100%;
}
```

### Проблема 2: Handle position sync

JS встановлює `--compare` через:
```javascript
function setPosition(pct) {
  var clamped = Math.max(0, Math.min(100, pct));
  node.style.setProperty('--compare', String(clamped));
  // range input sync:
  if (rangeInput) rangeInput.value = String(clamped);
}
```

Handle CSS:
```css
.compare-handle {
  left: calc(var(--compare) * 1%);
  /* ^^^ має відповідати clip-path розрахунку */
}
```

**Перевірити:** чи `left: calc(var(--compare) * 1%)` точно відповідає позиції clip-path. Якщо `--compare: 55` → handle на 55%, clip-path обрізає before на 45% справа, after на 55% зліва. Це означає "лінія поділу" на 55% ширини.

### Проблема 3: Hover mode — надто чутливий

Hover mode:
```javascript
function handleHover(event) {
  if (!mouseDown) return;  // ← Це для drag mode, не для hover!
  var rect = media.getBoundingClientRect();
  var pct = ((event.clientX - rect.left) / rect.width) * 100;
  setPosition(pct);
}
```

**Перевірити:** Чи hover mode правильно працює без кліку. Якщо `mouseDown` перевірка блокує hover — потрібно прибрати для hover mode.

### Проблема 4: Autoplay — анімація "дрибка"

Autoplay використовує `requestAnimationFrame` і лінійну інтерполяцію. Може виглядати нерівномірно на слабких пристроях.

**Рекомендація:** Використовувати ease-in-out cryptog (bezier) замість лінійної:
```javascript
// Замість лінійної:
var progress = elapsed / duration;
// Використати ease:
var progress = elapsed / duration;
var eased = progress < 0.5
  ? 2 * progress * progress
  : 1 - Math.pow(-2 * progress + 2, 2) / 2;
var position = startPos + (endPos - startPos) * eased;
```

---

## ЩО ЗРОБИТИ

### Крок 1: Перевірити CSS `.compare-layer`

Переконатись що ОБИДВА шари:
```css
.compare-layer {
  position: absolute;
  inset: 0;
  overflow: hidden;
}
.compare-layer img,
.compare-layer picture {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
```

> Якщо `object-fit: cover` відсутній — зображення може масштабуватись/розтягуватись.

### Крок 2: Виправити hover mode

У `effect.compare.js`, для hover mode:
```javascript
if (mode === 'hover') {
  media.addEventListener('mousemove', function(event) {
    var rect = media.getBoundingClientRect();
    var pct = ((event.clientX - rect.left) / rect.width) * 100;
    setPosition(pct);
  });
  media.addEventListener('mouseleave', function() {
    // Повернутись до центру
    smoothTo(initialValue);
  });
}
```

> НЕ використовувати `mouseDown` перевірку для hover mode.

### Крок 3: Покращити autoplay easing

Замінити лінійну інтерполяцію на smooth:
```javascript
function autoplayStep(time) {
  if (!autoplayActive) return;
  if (!autoplayStart) autoplayStart = time;
  var elapsed = time - autoplayStart;
  var progress = Math.min(elapsed / autoplayDuration, 1);
  
  // Ease in-out quad:
  var eased = progress < 0.5
    ? 2 * progress * progress
    : 1 - Math.pow(-2 * progress + 2, 2) / 2;
  
  var position = autoplayFrom + (autoplayTo - autoplayFrom) * eased;
  setPosition(position);
  
  if (progress >= 1) {
    // Reverse direction
    autoplayStart = time;
    var temp = autoplayFrom;
    autoplayFrom = autoplayTo;
    autoplayTo = temp;
  }
  
  requestAnimationFrame(autoplayStep);
}
```

### Крок 4: Touch support

Перевірити touch events:
```javascript
// Touch: використовувати touches[0].clientX
media.addEventListener('touchmove', function(event) {
  event.preventDefault();
  var touch = event.touches[0];
  var rect = media.getBoundingClientRect();
  var pct = ((touch.clientX - rect.left) / rect.width) * 100;
  setPosition(pct);
}, { passive: false });
```

### Крок 5: Visual polish

У CSS додати/перевірити:
```css
/* Handle styling */
.compare-handle {
  width: 3px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(4px);
  box-shadow: 0 0 12px rgba(0, 0, 0, 0.3);
  pointer-events: none;
  z-index: 10;
  transition: transform 50ms ease; /* smooth follow */
}

/* Handle grip circles */
.compare-handle::before,
.compare-handle::after {
  content: '';
  position: absolute;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.95);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

/* Active state */
.compare-media:active .compare-handle {
  width: 4px;
}
```

### Крок 6: Keyboard accessibility

Перевірити що range input працює:
```javascript
rangeInput.addEventListener('input', function() {
  setPosition(parseFloat(this.value));
});
```

---

## LENS (Збільшувальне скло) — Додаткові перевірки

### Поточна реалізація (`dtf.js`, рядки 2396-2459):

Lens працює через:
1. `.lens-glass` div з `background-image` = те саме фото
2. `background-size: width * zoom, height * zoom`
3. `background-position` оновлюється при mousemove

**Відомі потенційні проблеми:**
- При resize `.lens-glass` background-size не оновлюється (є `updateSize` на `resize` — перевірити)
- На touch (mobile) — відкривається modal замість glass lens (поведінка OK)
- Zoom factor = 2x — може бути недостатньо для macro photos

**Рекомендація:** Збільшити `zoom` до 2.5-3x для кращого ефекту на macro фотографіях:
```javascript
const zoom = 2.8;  // ← Було 2
```

---

## ПЕРЕВІРКА

### Drag mode:
1. Перетягнути handle зліва направо — обидва зображення видні, handle чітко на лінії поділу
2. Зображення НЕ масштабуються — тільки обрізаються (clip-path)
3. Touch на мобільному працює

### Hover mode:
1. Навести мишу на compare area — handle слідує за мишею
2. Відвести мишу — handle повертається до центру
3. Плавність ≥ 30fps

### Autoplay mode:
1. Handle плавно рухається з easing (не "рвано")
2. Зупиняється при взаємодії користувача
3. Відновлюється після ≥2 сек без взаємодії

### Lens:
1. Навести на lens-card — з'являється кругле "скло" з збільшеним фрагментом
2. Скло слідує за мишею
3. Зображення у склі відповідає позиції під мишею (без зміщення)
4. На мобільному — відкривається modal з повнорозмірним фото
