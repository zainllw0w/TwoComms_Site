# ITER3_05 — UI Micro-Pack (микро-графика + микро-анимации)

Цель: добавить "вау" и ощущение контролируемого процесса, **не убивая скорость**.  
Весь пакет — CSS-only или минимальный vanilla JS.

> **💡 Код ниже — ОРИЕНТИР, не копипаст.** Агент-исполнитель должен взять идею, оценить, можно ли сделать ЛУЧШЕ, и реализовать оптимальный вариант. Копировать дословно — только если вариант уже идеален.

> **📱 Mobile-first:** Большинство пользователей заходят с мобильных. Все эффекты должны быть проверены на 320/360/390px и на слабых устройствах (2 GB RAM, 2 cores).

---

## 0) Performance budgets (ОБЯЗАТЕЛЬНО)
1) Любой новый JS: **≤ 2 KB gzip** (предпочтение — без JS; если надо — только IntersectionObserver).
2) Анимации: только `transform`/`opacity`/`filter` (осторожно), без layout-триггеров (`top/left/width/height`).
3) Не анимировать "тяжёлые" `box-shadow` на больших элементах. Glow — через псевдоэлемент с blur.
4) Всё уважает `prefers-reduced-motion: reduce`:
   - или выключаем анимации,
   - или делаем 1 статичный стейт без мерцания.
5) Один "wow-эффект" на экран максимум (hero не превращаем в "ёлку").
6) **Touch targets ≥ 44×44px** на всех интерактивных элементах (кнопки, ссылки, иконки).

---

## P0 — вместе с текстами (низкий риск)

### 1) "Лампочка" для месседжа о стабильности (без слова "генератор")
**Где:** в блоке преимуществ/доверия (НЕ в hero).  
**Смысл:** визуально подчеркнуть `Стабільне виробництво — друкуємо без пауз`.

**SVG:** маленькая line-иконка лампочки (см. промпт Agent4).  
**Анимация (CSS):**
- раз на 7–9 сек короткий "blink" (200–260ms) + лёгкий glow
- hover/focus (desktop): плавное "on"
- mobile: 1 раз при входе в viewport (IntersectionObserver)

**Текст рядом (UA):** `Стабільне виробництво — друкуємо без пауз`

---

### 2) "Сканирование файла" (иконка + scan-line) для статуса проверки
**Где:** /order/ + /constructor/app/ (где есть статус `Перевіряємо файл…`).  
**Смысл:** показать, что "что-то реально происходит", снять тревожность.

**HTML (пример):**
```html
<div class="file-scan" aria-live="polite">
  <svg class="file-scan__icon" ...></svg>
  <span class="file-scan__text">Перевіряємо файл…</span>
  <span class="file-scan__line" aria-hidden="true"></span>
</div>
```

**CSS (пример):**
```css
.file-scan { position: relative; display: inline-flex; gap: .5rem; align-items: center; }
.file-scan__line{
  position:absolute; left:0; right:0; top:0;
  height:2px; opacity:.55;
  transform: translateY(0);
  animation: scan 1.35s linear infinite;
}
@keyframes scan{
  0%{ transform: translateY(0); }
  100%{ transform: translateY(26px); }
}

@media (prefers-reduced-motion: reduce){
  .file-scan__line{ animation:none; opacity:.25; }
}
```

**После проверки (переключение состояний):**
- OK → короткий "draw" галочки (250ms)
- Recommendation/Needs attention → 2 мягких pulses контура (без красного)
- Needs fix → статичный стейт + текст (без мерцания)

---

### 3) Secondary CTA "Безкоштовний тест" — спокойный breathing-pulse
**Где:** hero + /quality/ (1 раз на 10–12 сек).  
**Цель:** подсветить опцию теста, не конкурируя с Primary.

```css
.btn-secondary.breathe{
  animation: breathe 11s ease-in-out infinite;
}
@keyframes breathe{
  0%, 92%, 100%{ transform: scale(1); }
  95%{ transform: scale(1.02); }
}
@media (prefers-reduced-motion: reduce){
  .btn-secondary.breathe{ animation:none; }
}
```

---

### 4) Telegram-glow в mobile dock (one-shot)
**Где:** mobile dock.  
**Триггер:** при первом появлении dock (1 раз).  
**Правило:** glow ≤ 400ms, без повторов.

---

## P1 — когда дойдёте до loader и sticky (осторожно)

### 5) Multi-Step Loader (в стиле "аккуратный Aceternity", но лёгкий)
**Где:** /order/ и /constructor/app/ (после "Отправить").  
**Идея:** 4 шага с иконками:
1) `Файл отримано`
2) `Перевірка файлу`
3) `Друк`
4) `Відправка`

**Анимация:** только на активном шаге:
- лёгкий shimmer линии прогресса
- иконка "пульсирует" 1.00→1.03→1.00 (раз на 2–3 сек)
- завершённый шаг — галочка (stroke-draw)

**Нужно:** SVG-иконки от Agent4.

---

### 6) Sticky CTA bar (контекстная) без конфликта с dock
**Где:** home/price/requirements/quality после ~35% скролла.  
**Вид:** тонкая панель над dock: 1 короткий текст + 1 кнопка.

**Анимация:** slide-up 180–220ms, без bounce.  
**Важно:** не перекрывать input-поля и системные тосты.

---

### 7) FAQ-аккордеон (Коротко/Детальніше)
**Где:** /faq/  
**Поведение:** клик на вопрос раскрывает "Детальніше".

```css
.faq-answer {
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.35s ease-out, opacity 0.25s ease-out;
  opacity: 0;
}
.faq-item.is-open .faq-answer {
  max-height: 200px; /* или auto через JS */
  opacity: 1;
}
.faq-item.is-open {
  border-left: 3px solid var(--dtf-accent, #f97316);
}
@media (prefers-reduced-motion: reduce) {
  .faq-answer { transition: none; }
}
```

---

### 8) 🔵 Dot Distortion Background — ОБНОВЛЕНИЕ физики

> **Приоритет P1.** Это улучшение СУЩЕСТВУЮЩЕГО эффекта, а не новый компонент.  
> **Файл:** `dtf/static/dtf/js/dtf.js` → функция `initHomeDotBackground()` (строка ~1124)  
> **⚠️ Псевдокод ниже — ОРИЕНТИР.** Агент должен изучить текущую реализацию, понять физику, и написать СВОЙ вариант, который будет лучше. Можно и нужно экспериментировать с параметрами (force, damping, radius) для достижения максимально приятного ощущения.

#### 8.1 Что менять (текущее → новое)

| Аспект | Сейчас | Нужно |
|--------|--------|-------|
| **Физика мышки** | Pull (притяжение к курсору) | **Repulsion (отталкивание от курсора)** |
| **Halo/flashlight** | Radial gradient "фонарик" поверх всего | **Убрать.** Оставить только dot-level glow |
| **Breathing** | Нет | **Да:** каждая точка плавно пульсирует ±15% размера (индивидуальная фаза) |
| **Glow pulses** | Нет | **Да:** случайные точки изредка ярко мигают (1-2 в секунду, staggered) |
| **Spring-back** | Точки не возвращаются | **Да:** точки мягко пружинят к оригинальной позиции в grid |
| **Влияние радиуса** | Глобальное | **Локальное:** только точки в радиусе ~120-180px от курсора |

#### 8.2 Целевая физика (псевдокод)

```javascript
// Для каждой точки на каждом кадре:
const dx = dot.x - mouseX;
const dy = dot.y - mouseY;
const dist = Math.hypot(dx, dy);
const influenceRadius = 150; // px, зависит от tier

if (dist < influenceRadius) {
  const influence = 1 - dist / influenceRadius;
  const force = influence * influence * 25; // квадратичное затухание
  // REPULSION — отталкиваем от курсора:
  dot.renderX = dot.gridX + (dx / dist) * force;
  dot.renderY = dot.gridY + (dy / dist) * force;
} else {
  // Spring-back к оригинальной позиции:
  dot.renderX += (dot.gridX - dot.renderX) * 0.08;
  dot.renderY += (dot.gridY - dot.renderY) * 0.08;
}

// Breathing (индивидуальная фаза):
dot.size = baseSize + Math.sin(time * 0.002 + dot.phase) * baseSize * 0.15;

// Random glow pulse (вероятность ~0.1% на кадр на точку):
if (Math.random() < 0.001) dot.glowUntil = time + 400;
const isGlowing = time < dot.glowUntil;
dot.alpha = baseAlpha + (isGlowing ? 0.5 : 0);
```

#### 8.3 Сохранить из текущей реализации
- ✅ Систему тиров (`resolveAmbientTier`, tier 0-4)
- ✅ Оранжевую палитру (rgb 255, 136-178, 26-94)
- ✅ Canvas-подход
- ✅ CSS-fallback переменные (`--dot-pointer-x`, etc.)
- ✅ `is-static` для prefers-reduced-motion
- ✅ Throttling по `frameBudget`
- ✅ `document.hidden` проверку

#### 8.4 Mobile-специфика
- **Tier 1-2 (mobile):** influenceRadius уменьшить до 80-100px
- **Touch:** использовать `touchmove` / `pointermove` для позиции distortion
- **Max dots mobile:** оставить ≤620 (tier 2), spacing ≥34px
- **Breathing:** замедлить до `time * 0.0012` (экономия CPU)
- **Glow pulses:** снизить вероятность до 0.0005 на mobile
- **Tier 0:** полностью статичная сетка (CSS dots через `radial-gradient`)

#### 8.5 CSS fallback (prefers-reduced-motion: reduce)
```css
.home-dot-distortion.is-static {
  background-image: radial-gradient(
    circle, rgba(255, 140, 40, 0.12) 1px, transparent 1px
  );
  background-size: 32px 32px;
}
```

#### 8.6 Что НЕ делать
- ❌ Не использовать WebGL/шейдеры (слишком тяжело для low-end mobile)
- ❌ Не добавлять blur/filter на canvas (дорого)
- ❌ Не увеличивать количество точек сверх текущих лимитов
- ❌ Не делать анимацию при `saveData` или `2g`

---

### 9) 🎨 Component Visual Polish (микро-улучшения)

> **Приоритет P1.** Мелкие визуальные штрихи, которые делают сайт "живым", без полной переработки.  
> **⚠️ CSS ниже — ОРИЕНТИР.** Агент берёт идею и реализует свой вариант, который может быть красивее и чище. Эти примеры показывают НАПРАВЛЕНИЕ, а не финальный код.

#### 9.1 Кнопки (все CTA)

```css
/* Primary CTA — hover эффект */
.btn-primary {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.btn-primary:hover {
  transform: scale(1.02);
  box-shadow: 0 4px 16px rgba(249, 115, 22, 0.25);
}
.btn-primary:active {
  transform: scale(0.98);
}

/* Secondary CTA — ghost hover */
.btn-secondary {
  transition: border-color 0.2s ease, color 0.2s ease, transform 0.2s ease;
}
.btn-secondary:hover {
  border-color: var(--dtf-accent);
  transform: scale(1.01);
}

/* Mobile: увеличить touch target */
@media (pointer: coarse) {
  .btn-primary, .btn-secondary {
    min-height: 48px;
    padding-block: 14px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .btn-primary, .btn-secondary {
    transition: none;
  }
  .btn-primary:hover, .btn-secondary:hover { transform: none; }
}
```

#### 9.2 Карточки (entrance animation)

```css
.work-card, .proof-card, .hero-card {
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.5s ease-out, transform 0.5s ease-out;
}
.work-card.is-visible, .proof-card.is-visible, .hero-card.is-visible {
  opacity: 1;
  transform: translateY(0);
}
/* Stagger: каждая следующая карточка +100ms */
.work-card:nth-child(2) { transition-delay: 0.1s; }
.work-card:nth-child(3) { transition-delay: 0.2s; }
.work-card:nth-child(4) { transition-delay: 0.3s; }

@media (prefers-reduced-motion: reduce) {
  .work-card, .proof-card, .hero-card {
    opacity: 1; transform: none; transition: none;
  }
}
```

**JS (IntersectionObserver):**
```javascript
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('is-visible');
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.15 });
document.querySelectorAll('.work-card, .proof-card').forEach(el => observer.observe(el));
```

#### 9.3 Form input focus

```css
.form-input {
  border-bottom: 2px solid var(--dtf-border, #e5e7eb);
  transition: border-color 0.2s ease;
  position: relative;
}
.form-input:focus {
  border-color: var(--dtf-accent, #f97316);
  outline: none;
}
/* Animated underline (pseudo-element) */
.form-group::after {
  content: '';
  position: absolute;
  bottom: 0; left: 50%; right: 50%;
  height: 2px;
  background: var(--dtf-accent, #f97316);
  transition: left 0.25s ease, right 0.25s ease;
}
.form-group:focus-within::after {
  left: 0; right: 0;
}
@media (prefers-reduced-motion: reduce) {
  .form-group::after { transition: none; }
}
```

#### 9.4 Dropzone (drag-over pulse)

```css
.dropzone.is-drag-over {
  animation: dropzone-pulse 0.8s ease-in-out infinite;
  border-color: var(--dtf-accent);
}
@keyframes dropzone-pulse {
  0%, 100% { border-style: dashed; opacity: 0.7; }
  50% { border-style: dashed; opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .dropzone.is-drag-over { animation: none; opacity: 1; }
}
```

#### 9.5 Price badge shimmer

```css
.hero-card .price-badge {
  position: relative;
  overflow: hidden;
}
.hero-card .price-badge::after {
  content: '';
  position: absolute;
  top: 0; left: -100%; width: 60%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
  animation: shimmer 4s ease-in-out infinite;
}
@keyframes shimmer {
  0%, 80%, 100% { left: -100%; }
  40% { left: 150%; }
}
@media (prefers-reduced-motion: reduce) {
  .hero-card .price-badge::after { animation: none; display: none; }
}
```

#### 9.6 Mobile dock entrance

```css
.mobile-dock {
  transform: translateY(100%);
  transition: transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.mobile-dock.is-visible {
  transform: translateY(0);
}
@media (prefers-reduced-motion: reduce) {
  .mobile-dock { transform: none; transition: none; }
}
```

---

## P2 — только если всё быстро и стабильно

### 10) "Peel & reveal" (scroll-анимация плёнки)
**Риск:** легко убить FPS на Android.  
**Как безопасно:** только desktop, 1 секция, мобилка = static fallback.

---

## Mini SVG kit (в одном стиле)
Набор SVG-иконок (16/20/24px, `stroke="currentColor"`, rounded caps):
- файл + проверка (сканер)
- лист 60 см
- чистый край
- цвет/палитра
- доставка (НП/посылка)
- лампочка (стабильность)
- Telegram
- upload (загрузка)
- часы (сроки)
- щит (гарантия)
- калькулятор (расчёт)

> См. отдельный промпт: `ITER3_07_PROMPT_AGENT4_GEMINI.md`
