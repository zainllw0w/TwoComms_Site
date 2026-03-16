# 🔴 ITER3 V2 — Глобальний Звіт Дефектів

> **Дата:** 2026-03-02 | **Метод:** Аналіз коду + візуальна перевірка в браузері  
> **Цей файл містить ТІЛЬКИ дефекти** — те, що зроблено неправильно, не так підключено, не інтегровано, або не реалізовано взагалі.  
> Він буде використаний для створення промта Agent3
> для виправлення всіх проблем.

---

## Зміст

1. [S-1: Відсутній HANDOVER файл](#s-1-відсутній-handover-файл)
2. [S-2: 7 з 15 SVG іконок не інтегровані](#s-2-7-з-15-svg-іконок-не-інтегровані)
3. [S-3: Лампочка (icon-bulb) розміщена в неправильному місці](#s-3-лампочка-icon-bulb-розміщена-в-неправильному-місці)
4. [D-1: Dot Distortion — неправильна фізика (velocity-following замість repulsion)](#d-1-dot-distortion--неправильна-фізика)
5. [D-2: Dot Distortion — відсутнє статичне поле](#d-2-dot-distortion--відсутнє-статичне-поле)
6. [A-1: CSS анімації іконок — неправильний timing](#a-1-css-анімації-іконок--неправильний-timing)
7. [A-2: Card entrance — розрив CSS ↔ JS](#a-2-card-entrance--розрив-css--js)
8. [A-3: Відсутній JS-тригер для іконних анімацій](#a-3-відсутній-js-тригер-для-іконних-анімацій)
9. [F-1: Заборонені терміни "preflight" залишились у коді](#f-1-заборонені-терміни-preflight-залишились-у-коді)
10. [F-2: Заборонений термін "QC" у CSS-класах](#f-2-заборонений-термін-qc-у-css-класах)
11. [M-1: Ротатор — 1 фраза замість 3+](#m-1-ротатор--1-фраза-замість-3)
12. [M-2: Контекстні Telegram prefill тексти не реалізовані](#m-2-контекстні-telegram-prefill-тексти-не-реалізовані)
13. [M-3: FAQ на /faq/ — інший формат ніж на homepage](#m-3-faq-на-faq--інший-формат-ніж-на-homepage)

**Також не зроблено (P1, нижчий пріоритет):** Sticky CTA, Demo-бейджі на галереї.

---

## S-1: Відсутній HANDOVER файл

### 🔴 Severity: CRITICAL — зламав весь пайплайн синхронізації

### Що очікувалось
Agent4 (згідно `ITER3_07_PROMPT_AGENT4_GEMINI.md`, секція 8) **мав створити** файл `ITER3_AGENT4_HANDOVER.md` з:
- Повним переліком всіх створених файлів (шляхи)
- Списком CSS-класів та як їх підключити
- Інструкціями для Agent3 щодо інтеграції

### Що зроблено
Файл **НЕ створено**. Пошук `find_by_name("ITER3_AGENT4_HANDOVER")` повернув 0 результатів.

### Чому це проблема
Цей файл — **єдиний механізм синхронізації** між Agent4 (який створює ассети) та Agent3 (який інтегрує їх у шаблони). Без нього Agent3:
- Не знає, які SVG іконки існують і де їх використовувати
- Не знає, які CSS-класи застосовувати для анімацій
- Не знає, як підключити CSS-файли (хоча їх підключення було зроблено правильно в `base.html`)

### Наслідки
- 7 з 15 SVG іконок **ніде не використовуються** (див. S-2)
- Лампочка розміщена в неправильному місці (див. S-3)
- Анімації іконок не мають JS-тригерів (див. A-3)

### Як виправити
Agent3 має створити цей файл ретроспективно, або отримати повний список ассетів з цього аудит-звіту.

---

## S-2: 7 з 15 SVG іконок не інтегровані

### 🟡 Severity: MAJOR

### Результат перевірки `grep_search` по всіх шаблонах

| Іконка | Файл існує | Інтегрована | Де використовується |
|--------|-----------|-------------|---------------------|
| `icon-check.svg` | ✅ | ✅ | constructor_app.html:152, order.html:98, preflight.html:100,108 |
| `icon-info.svg` | ✅ | ✅ | constructor_app.html:153, order.html:99 |
| `icon-warning.svg` | ✅ | ✅ | constructor_app.html:154, order.html:100, preflight.html:104 |
| `icon-fix.svg` | ✅ | ✅ | constructor_app.html:155, order.html:101 |
| `icon-bulb.svg` | ✅ | ⚠️ Не там | constructor_app.html:159, order.html:105 (НЕ на homepage) |
| `icon-telegram.svg` | ✅ | ✅ | constructor_app.html:176, order.html:122 |
| `icon-upload.svg` | ✅ | ✅ | constructor_app.html:177, order.html:123 |
| `icon-shield.svg` | ✅ | ✅ | constructor_app.html:178, order.html:124 |
| `icon-file.svg` | ✅ | ❌ | **Нігде** |
| `icon-scan.svg` | ✅ | ❌ | **Нігде** |
| `icon-truck.svg` | ✅ | ❌ | **Нігде** |
| `icon-sheet60.svg` | ✅ | ❌ | **Нігде** |
| `icon-palette.svg` | ✅ | ❌ | **Нігде** |
| `icon-clock.svg` | ✅ | ❌ | **Нігде** |
| `icon-calculator.svg` | ✅ | ❌ | **Нігде** |

### Де мають бути не-інтегровані іконки

| Іконка | Рекомендоване місце | Логіка |
|--------|---------------------|--------|
| `icon-file` | Dropzone / upload-секція | Відображає "файл" — основний об'єкт роботи |
| `icon-scan` | Preflight process / file check | "Перевірка файлу" |
| `icon-truck` | Доставка (index.html delivery блок, status.html) | Логістика / Nova Poshta |
| `icon-sheet60` | Конструктор / "Зібрати лист 60 см" | Ключовий продукт |
| `icon-palette` | "Як це працює" кроки / вимоги до кольорів | Кольоровий профіль |
| `icon-clock` | Терміни виробництва / FAQ "Скільки часу" | Час виготовлення |
| `icon-calculator` | Калькулятор цін (index.html, price.html) | Розрахунок вартості |

### Наслідки
Agent4 створив якісні SVG-іконки, але вони **не видимі для користувача**. 47% ассетів лежать "мертвим вантажем" — файли існують, CSS анімації для деяких з них готові, але HTML їх не включає.

---

## S-3: Лампочка (icon-bulb) розміщена в неправильному місці

### 🔴 Severity: CRITICAL — користувач помітив цю проблему

### Що очікувалось
Згідно `ITER3_05_UI_MICROPACK.md` (секція 1, P0):
- **Де:** В блоці переваг/довіри на **головній сторінці** (index.html), НЕ в hero
- **Контекст:** Поруч з текстом "Стабільне виробництво — друкуємо без пауз"
- **Анімація:** Раз на 7–9 сек короткий blink (200–260ms) + легкий glow
- **Mobile:** 1 раз при вході у viewport через IntersectionObserver

### Що зроблено
`icon-bulb.svg` інтегрована ТІЛЬКИ в:
- `constructor_app.html` рядок 159 — всередині `preflight-terms` блоку
- `order.html` рядок 105 — всередині `preflight-terms` блоку

На **index.html** (головна сторінка) лампочка **ВІДСУТНЯ**.

### Візуальне підтвердження (браузер)

![Секція "Чому ми" без лампочки](file:///Users/zainllw0w/.gemini/antigravity/brain/6a20aab0-377a-432a-8d6a-ee6233742935/homepage_why_us_1772447789949.png)

Текст "Стабільне виробництво — друкуємо без пауз" відображається як звичайний `<li>` без будь-якої іконки чи анімації.

### Чому це сталося
Agent3 асоціював лампочку з технічним процесом перевірки файлу ("preflight"), а не з маркетинговим повідомленням про стабільність виробництва. Без HANDOVER файлу Agent3 не мав чітких інструкцій щодо цільового розміщення.

### Як виправити
1. **index.html**, рядок ~280 (секція `why-us`):
```html
<li>
  <span class="dtf-icon dtf-icon-bulb dtf-icon-animate" aria-hidden="true">
    {% include 'dtf/svg/icon-bulb.svg' %}
  </span>
  Стабільне виробництво — друкуємо без пауз.
</li>
```
2. Оновити CSS timing для `soft-glow` (див. дефект A-1)
3. Додати IntersectionObserver для mobile one-shot trigger

---

## D-1: Dot Distortion — неправильна фізика

### 🔴 Severity: CRITICAL — основна візуальна фіча не працює як задумано

### Що очікувалось
Згідно `ITER3_01_DECISIONS.md` + `ITER3_05_UI_MICROPACK.md`:
- **Поточна поведінка:** pull / flashlight → **Нова:** repulsion
- Точки **відштовхуються** від позиції курсора
- Формула зі специфікації:
```javascript
const dx = dot.gridX - mouseX;
const dy = dot.gridY - mouseY;
const dist = Math.sqrt(dx * dx + dy * dy);
const force = smoothstep(0, radius, dist) * strength;
dot.renderX = dot.gridX + (dx / dist) * force;
dot.renderY = dot.gridY + (dy / dist) * force;
```

### Що реалізовано
`dtf.js`, функція `initHomeDotBackground()`, рядки 1384–1389:
```javascript
if (state.pointerInside && isMoving && dist < radius) {
  influence = 1 - dist / radius;
  const force = influence * influence * distortionStrength;
  dot.vx += state.pointerDx * force * velocityKick;  // ← НЕПРАВИЛЬНО
  dot.vy += state.pointerDy * force * velocityKick;   // ← НЕПРАВИЛЬНО
}
```

### Технічний розбір помилки

| Аспект | Специфікація (repulsion) | Реалізація (velocity-following) |
|--------|--------------------------|--------------------------------|
| **Вхідний вектор** | `dx = dot.x - mouse.x` (позиція) | `state.pointerDx` (швидкість миші) |
| **Напрямок сили** | ВІД курсора до точки | В напрямку РУХУ курсора |
| **Результат** | Точки "тікають" від курсора | Точки "розмазуються" вздовж руху |
| **Статичний курсор** | Працює (точки відштовхнуті) | НЕ працює (isMoving = false) |
| **Візуальний ефект** | "Магнітне відштовхування" | "Кінетичне розмазування" |

### Візуальне підтвердження
Браузерна перевірка підтвердила: точки на canvas видимі, дихання (breathing) працює, але при наведенні курсора **точки не реагують відштовхуванням**.

### Наслідки
Це — найбільш помітна візуальна фіча сайту. Вона повинна створювати "wow-ефект" при першому відвідуванні, але замість цього виглядає як звичайна точкова сітка.

### Як виправити
Замінити velocity-following на repulsion в `dtf.js`:
```javascript
// ЗА: velocity-following
dot.vx += state.pointerDx * force * velocityKick;
dot.vy += state.pointerDy * force * velocityKick;

// НА: repulsion
const dx = dot.gridX - state.pointerX;
const dy = dot.gridY - state.pointerY;
const dist = Math.sqrt(dx * dx + dy * dy);
if (dist > 0 && dist < radius) {
  const influence = 1 - dist / radius;
  const force = influence * influence * distortionStrength;
  dot.vx += (dx / dist) * force;
  dot.vy += (dy / dist) * force;
}
```

---

## D-2: Dot Distortion — відсутнє статичне поле

### 🟡 Severity: MAJOR

### Що очікувалось
`ITER3_05_UI_MICROPACK.md` вказує: `staticField ≈ 0.15` — навіть коли курсор нерухомий всередині grid'а, має бути м'яке постійне відштовхування.

### Що реалізовано
```javascript
if (state.pointerInside && isMoving && dist < radius) {
```
Умова `isMoving` означає: якщо курсор стоїть нерухомо — **жодного ефекту**.

### Як виправити
Додати окрему гілку для staticField:
```javascript
if (state.pointerInside && dist < radius) {
  // Static repulsion (always active when cursor is inside)
  const staticForce = (1 - dist / radius) * 0.15;
  dot.vx += (dx / dist) * staticForce;
  dot.vy += (dy / dist) * staticForce;
  
  // Dynamic repulsion (stronger when moving)
  if (isMoving) {
    const dynamicForce = influence * influence * distortionStrength;
    dot.vx += (dx / dist) * dynamicForce;
    dot.vy += (dy / dist) * dynamicForce;
  }
}
```

---

## A-1: CSS анімації іконок — неправильний timing

### 🟡 Severity: MAJOR

### Детальний розбір кожної проблемної анімації

#### `soft-glow` для icon-bulb

| Параметр | Специфікація | Реалізація | Статус |
|----------|-------------|------------|--------|
| Тривалість blink | 200–260ms | 2.4s | ❌ |
| Інтервал | Раз на 7–9 сек | Безперервно (infinite) | ❌ |
| Механізм | JS SetInterval + CSS class toggle | Чистий CSS infinite loop | ❌ |

**Наслідок:** Лампочка (коли її перенесуть на homepage) буде постійно "дихати" замість рідкого тонкого спалаху. Це виглядатиме нав'язливо і відволікатиме від контенту.

#### `soft-glow` для icon-telegram

| Параметр | Специфікація | Реалізація |
|----------|-------------|------------|
| Тип | One-shot glow ≤ 400ms, без повторів | 2.8s infinite |

**Наслідок:** Іконка Telegram в кнопках постійно мерехтить. Має блиснути одноразово при події.

#### `upload-bounce` для icon-upload

| Параметр | Специфікація | Реалізація |
|----------|-------------|------------|
| Тип | Bounce при тригері (upload action) | Infinite loop |

#### `truck-slide` для icon-truck

| Параметр | Специфікація | Реалізація |
|----------|-------------|------------|
| Тип | Тригер при статусі "Відправка" | Infinite loop |

### Як виправити
1. Змінити CSS `animation:` з `infinite` на `none` за замовчуванням
2. Активувати через `.dtf-icon-animate.active` клас
3. Для bulb: JS `setInterval(() => { toggleBlink() }, 7000 + Math.random() * 2000)` з `opacity` flash тривалістю 230ms
4. Для telegram: `animation-iteration-count: 1;` 
5. Для upload/truck: only play on trigger event

---

## A-2: Card entrance — розрив CSS ↔ JS

### 🟡 Severity: MAJOR

### Суть проблеми
Agent4 створив CSS в `animations.css` для card entrance, який таргетує певні класи. Одночасно в `dtf.js` існує IntersectionObserver (`initCardReveal`), який таргетує ІНШІ класи. Вони не збігаються повністю.

### Матриця відповідності

| CSS-клас (animations.css) | JS-селектор (initCardReveal) | Збіг? |
|---------------------------|------------------------------|-------|
| `.work-card` | `.work-card` | ✅ |
| `.proof-card` | `.proof-card` | ✅ |
| `.price-row` | — | ❌ **CSS є, JS немає** |
| `.feature-card` | — | ❌ **CSS є, JS немає** |
| `.step-card` | — | ❌ **CSS є, JS немає** |
| — | `.hero-card` | ❌ **JS є, CSS немає** |
| — | `.info-card` | ❌ **JS є, CSS немає** |

### Наслідки
- `.price-row` елементи мають `opacity: 0` в CSS, але JS ніколи не додасть їм `.is-visible`. Вони потенційно **невидимі** або видимі через override в `dtf.css`.
- `.feature-card` та `.step-card` — те саме: `opacity: 0` без тригера.
- `.hero-card` та `.info-card` отримують `.is-visible` від JS, але CSS для них анімації не визначено.

### Чому це могло не зламати сайт
Основний stylesheet `dtf.css` має власну reveal-систему через `[data-reveal]`:
```css
body.reveal-ready [data-reveal].is-visible {
  opacity: 1;
  transform: translateY(0);
}
```
Ця система працює на **контейнерному** рівні (`data-reveal` на батьківському div), тому вміст стає видимим. Але дочірні `.price-row` елементи всередині можуть мати конфлікт між `opacity: 0` (animations.css) та успадкованою видимістю.

### Як виправити
1. Додати `.price-row, .feature-card, .step-card` до JS-селектора `initCardReveal()`
2. Або видалити ці класи з `animations.css` якщо вони вже покриваються `[data-reveal]` системою

---

## A-3: Відсутній JS-тригер для іконних анімацій

### 🟡 Severity: MODERATE

### Що очікувалось
Специфікація передбачала:
- Desktop: іконки анімуються при певних подіях (hover, status change, interval)
- Mobile: іконки анімуються ОДИН раз при вході у viewport (IntersectionObserver)
- Клас `.dtf-icon-animate` повинен тригерити анімацію, не запускати назавжди

### Що реалізовано
Клас `dtf-icon-animate` додається **статично в HTML** і CSS animations запускаються відразу при рендері:
```html
<span class="dtf-icon dtf-icon-check dtf-icon-animate" aria-hidden="true">
```
```css
.dtf-icon-check.dtf-icon-animate .icon-path { animation: check-draw 0.6s ... }
```

### Чому це проблема
- Анімації запускаються при завантаженні сторінки, навіть якщо елемент поза viewport
- Користувач може не побачити анімацію, бо вона вже відіграла до прокрутки
- На mobile витрачаються ресурси на анімації, які ніхто не бачить

### Як виправити
1. Не додавати `dtf-icon-animate` в HTML статично
2. Написати JS:
```javascript
function initIconAnimations() {
  const icons = document.querySelectorAll('.dtf-icon[class*="dtf-icon-"]');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('dtf-icon-animate');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.5 });
  icons.forEach(icon => observer.observe(icon));
}
```

---

## F-1: Заборонені терміни "preflight" залишились у коді

### 🟡 Severity: MODERATE

### Знайдені випадки

| Файл | Рядок | Контекст | Тип |
|------|-------|----------|-----|
| `constructor_app.html` | 19 | `data-preflight-url="/..."` | data-attr |
| `constructor_app.html` | 98 | `constructor-preflight-card` | CSS class |
| `constructor_app.html` | 102 | `data-preflight-loader` | data-attr |
| `constructor_app.html` | 155–178 | `data-preflight-upload-fixed`, `data-preflight-print-as-is` | data-attrs |
| `order.html` | 42 | `data-preflight-url` | data-attr |
| `order.html` | 84 | `preflight-block` | CSS class |
| `order.html` | 122–124 | `data-preflight-upload-fixed`, `data-preflight-print-as-is` | data-attrs |

### Що каже специфікація
`ITER3_GLOSSARY.md`, секція "Forbidden" → UI-строкам NOT: preflight, safe area (у RU/UA), QC.

### Практичний аспект
Ці терміни знаходяться в **data-атрибутах та CSS-класах**, які не видимі звичайному користувачу. Однак:
- Вони видимі через DevTools
- Вони можуть потрапити в accessibility tree
- Це порушує принцип "canonical terminology everywhere"

### Як виправити
Замінити:
- `data-preflight-*` → `data-filecheck-*`
- `preflight-block` → `filecheck-block`
- `constructor-preflight-card` → `constructor-filecheck-card`

> [!WARNING]
> Зміна data-атрибутів потребує відповідних змін у JS-коді (`dtf.js`, `constructor.js`), де ці атрибути використовуються як селектори!

---

## F-2: Заборонений термін "QC" у CSS-класах

### 🟡 Severity: MODERATE

### Знайдені випадки
`status.html`, рядки 104–127:
```html
<div class="qc-list">
  <div class="qc-item">
    <span class="qc-label">{{ event.from_label }} → {{ event.to_label }}</span>
    <span class="qc-status ok">{{ event.created_at }}</span>
  </div>
</div>
```

Також рядок 85: `status-preflight.svg` — ім'я ассету містить заборонений термін.

### Як виправити
- `qc-list` → `check-list`
- `qc-item` → `check-item`
- `qc-label` → `check-label`
- `qc-status` → `check-status`
- `status-preflight.svg` → `status-filecheck.svg` (+ оновити посилання)
- Оновити відповідний CSS у `dtf.css`

---

## M-1: Ротатор — 1 фраза замість 3+

### 🟡 Severity: MODERATE

### Що очікувалось
Ротатор у `header-topbar` з ≥3 фразами, що не дублюють hero. Фрази з `ITER3_02_COPY_UA.md`:
1. "Друкуємо від 1 метра · відправка по Україні"
2. "Безкоштовна перевірка файлу перед друком"
3. "Гаряче зняття · стабільний результат"

### Що реалізовано
`base.html` рядки 162–170 — **одна статична фраза**:
```html
<span class="header-status-chip">
  Друкуємо від 1 метра · відправка по Україні
</span>
```
Немає JS для ротації. Немає масиву фраз.

### Як виправити
1. Додати масив фраз у HTML або JS
2. Написати JS для плавної ротації (fade out → change text → fade in) з інтервалом 5–7 сек
3. Забезпечити 3-мовність кожного елемента ротації

---

## M-2: Контекстні Telegram prefill тексти не реалізовані

### 🟡 Severity: MODERATE

### Що очікувалось
`ITER3_02_COPY_UA.md`, секція K4 визначає **різні** prefill тексти для кожної сторінки:
- **K4.home:** "Привіт! Хочу замовити DTF-друк 60 см..."
- **K4.faq:** "Привіт, тут [описати питання]..."
- **K4.requirements:** "Привіт! Хочу перевірити вимоги файлу..."
- **K4.price:** "Привіт! Хочу уточнити ціну DTF-друку 60 см..."
- **K4.status:** "Привіт! Хочу дізнатись статус замовлення..."

### Що реалізовано
Один і той же текст `"Привіт! Хочу замовити DTF-друк 60 см..."` скрізь (header, hero, footer, mobile dock, FAQ, constructor, order).

### Як виправити
Для кожної сторінки додати відповідний `?text=` параметр. Враховуючи, що посилання в header/footer — глобальні (base.html), потрібно:
1. Передавати `page_tg_text` з Django view через контекст
2. Або використовувати `{% block tg_prefill %}` з різним текстом для кожного шаблону

---

## M-3: FAQ на /faq/ — інший формат ніж на homepage

### 🟢 Severity: MINOR

### Що очікувалось
Формат "Коротко: ... / Детальніше: ..." з кастомним CSS (`.faq-item`, `.faq-q`, `.faq-a`).

### Що реалізовано
- **Homepage (index.html):** Використовує кастомний `faq-item`/`faq-q`/`faq-a` формат ✅
- **FAQ page (faq.html):** Використовує нативний `<details>`/`<summary>` всередині `<article class="info-card">` ❌

### Архітектурна невідповідність
Два різних UI-компоненти для однієї функції = непослідовний UX + подвійна підтримка.

### Як виправити
Уніфікувати: або перевести FAQ page на `faq-item` формат (щоб анімації з `animations.css` працювали), або навпаки.

---

## 📊 Зведена Матриця Пріоритетів

| Дефект | Severity | Складність фіксу | Пріоритет фіксу |
|--------|----------|------------------|-----------------|
| **S-3** Лампочка → homepage | 🔴 CRITICAL | Низька (HTML edit) | **#1** |
| **D-1** Dot distortion physics | 🔴 CRITICAL | Середня (JS rewrite) | **#2** |
| **D-2** Static field | 🔴 CRITICAL | Низька (JS add) | **#3** |
| **A-1** Icon timing | 🟡 MAJOR | Середня (CSS + JS) | **#4** |
| **S-2** 7 SVGs не інтегровані | 🟡 MAJOR | Низька (HTML edits) | **#5** |
| **A-2** Card entrance CSS↔JS | 🟡 MAJOR | Низька (JS selector fix) | **#6** |
| **A-3** Icon trigger JS | 🟡 MODERATE | Середня (new JS) | **#7** |
| **F-1** preflight | 🟡 MODERATE | Висока (HTML+CSS+JS) | **#8** |
| **F-2** QC | 🟡 MODERATE | Середня (HTML+CSS) | **#9** |
| **M-1** Rotator | 🟡 MODERATE | Середня (HTML+JS) | **#10** |
| **M-2** TG prefills | 🟡 MODERATE | Низька (HTML) | **#11** |
| **M-3** FAQ format | 🟢 MINOR | Середня (HTML) | **#12** |

---

## 🎬 Відео-запис інспекції

![Запис браузерної інспекції](file:///Users/zainllw0w/.gemini/antigravity/brain/6a20aab0-377a-432a-8d6a-ee6233742935/live_site_inspection_1772447647198.webp)
