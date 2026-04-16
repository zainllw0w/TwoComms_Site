# TwoComms Custom Print Configurator — UX Redesign Vision V4

> **Автор:** Глубокий аудит текущей реализации + синтез V1/V2/V3 + собственное видение
> **Дата:** 13 апреля 2026
> **Цель:** Конкретный, технически выполнимый план того, ЧТО сломано, ПОЧЕМУ это плохо и КАК это починить — без абстрактных манифестов

---

## 0. Что я реально увидел (факты, не мнения)

После детального анализа живого сайта (twocomms.shop/custom-print/), HTML-шаблона (412 строк), CSS (873 строки), всех четырёх документов (doctrine v7.1, V1, V2, V3), и визуального прохода через весь flow — ниже зафиксировано то, что реально происходит на экране.

### Структура страницы сейчас

```
[Hero block — full-width]
    ├── [Copy слева: заголовок + CTA]  │  [Панель справа: описание + bullet points]
    
[Build Strip — 5 чипов, горизонтальный scroll]
    ├── Старт │ Формат │ Виріб │ Макет │ Фінал

[Workbench — two columns]
    ├── LEFT (≈60%): Stage Card
    │     ├── "Виріб на сцені" eyebrow + заголовок
    │     ├── CSS-силуэт худі (не изображение, а div'ы)
    │     ├── Zone pins ("Спереду", "На рукаві")
    │     ├── Meta-блоки ("Головний сценарій: Худі", "Активні зони: Спереду")
    │     └── Toolbar (Telegram + Передати менеджеру + inline ціна)
    │
    └── RIGHT (≈340-440px): Panel Column
          ├── Active Step Card (quickstart / mode / product / artwork / quantity / review)
          └── Price Capsule (попередня вартість + breakdown + CTA)

[Mobile Bar — fixed bottom, hidden on desktop]
```

---

## 1. Конкретные проблемы (пронумерованные, с локализацией в коде)

### 🔴 P1. «Худі-синдром» — виріб відображається ДО того, як користувач його обрав

**Що:** Користувач відкриває `/custom-print/` і першою візуальною домінантою є CSS-силует худі зліва. Але на кроці "1. Старт" праворуч пропонується "З чого почати" (три варіанти). Користувач ще не зробив жодного вибору, а худі вже стоїть як факт.

**Чому це погано:**
- Когнітивний дисонанс: "Я ще нічого не обрав, а худі вже тут. Це вже замовлено?"
- Руйнується відчуття відкритого вибору — здається, що худі — дефолт, а решта — "відхилення від норми"
- Doctrine v7.1, §3.8 прямо каже: `[A] — не робити auto-start`

**Де в коді:** `custom_print.html:84-91` — гармент-шелл завжди відрисовує `cp-garment--hoodie` при першому рендері. Конфіг-дефолти (`custom_print_config.defaults.product.type = 'hoodie'`) автоматично встановлюють худі.

---

### 🔴 P2. Непропорційний desktop-лейаут: Stage Card ≈ 60% vs Panel ≈ 340px

**Що:** На десктопі `cp-workbench` використовує `grid-template-columns: minmax(0, 1fr) minmax(360px, 440px)`. Це означає, що Stage Card (з CSS-худі) займає ~60%+ екрану, а панель з кроками — вузьку колонку 360-440px справа.

**Чому це погано:**
- Stage Card з CSS-силуетом не потребує 60% ширини — він виглядає розтягнутим з великою кількістю порожнього простору
- Панель справа виглядає затиснутою ("клаустрофобія правої колонки", як вірно зазначено у V3)
- На 1920px моніторі Stage Card виглядає непропорційно великим, а опції — непропорційно малими
- Картки опцій в 3-column grid (`cp-option-grid--three`) в 440px ширини дають ~130px на картку — це тісно

**Де в коді:** `custom-print-configurator.css:266-271`

---

### 🟡 P3. «Помаранчеві» активні картки — неправильна фізика стану "обрано"

**Що:** Обрані картки отримують клас `is-active` із стилями:
```css
border-color: var(--cp-border-strong);  /* rgba(236, 197, 127, 0.42) */
background: linear-gradient(180deg, rgba(242, 211, 155, 0.1), rgba(255, 255, 255, 0.025));
```

**Чому це неоднозначно:**
- Це не "вдавлена кнопка" (V2/V3 перебільшують цю проблему), але і не яскраво-виділений елемент
- Проблема в тому, що золотий бордер (`0.42` opacity) виглядає як "підсвічений hover", а не як чітке "ОБРАНО"
- На кроці "quickstart" усі три картки мають однаковий візуальний вес — перша має `is-active` від народження (`{% if item.value == custom_print_config.defaults.quick_start_mode %}is-active{% endif %}`), що виглядає як "уже обрано", хоча користувач ще нічого не натискав
- Відсутній будь-який індикатор (✓ чекмарка, бейдж, анімація) — тільки субтільна зміна бордеру

**Де в коді:** `custom-print-configurator.css:550-554` + HTML template lines 127, 156, 180, 196

---

### 🟡 P4. Нульові анімації між переходами кроків

**Що:** Перехід між кроками реалізований через `display: none` → `display: block`:
```css
.cp-card--step { display: none; }
.cp-card--step.is-current { display: block; }
```

**Чому це погано:**
- Моменальне "моргання" контенту руйнує просторову пам'ять
- Doctrine v7.1, §8 прямо специфікує motion-токени, які НЕ використовуються
- Немає відчуття "я рухаюсь вперед" чи "повертаюсь назад"
- Modern web UX очікує хоча б fade або slide

**Де в коді:** `custom-print-configurator.css:289-295`, JS переключення через `is-current` клас

---

### 🟡 P5. Шаг «Виріб» = мегашаг-монстр (Product Step overload)

**Що:** На кроці "3. Виріб" (`cp-step-product`) зібрано ВСЕ:
1. Вибір виробу (Худі / Футболка / Лонгслів / Свій одяг) — 3-4 картки
2. Посадка (Regular / Oversize) — chip-row
3. Тканина — chip-row
4. Колір виробу — swatch-row
5. Зони друку — chip-row + textarea для нестандартної
6. Деталі виробу (addon'и) — chip-row
7. Навігаційні кнопки (Назад / Далі до макета)

**Чому це погано:**
- Це 6+ рішень на одному екрані — прямо порушує doctrine §4.1 ("не більше 3-6 видимих опцій")
- На мобільному це перетворюється на довге полотно скролу, де користувач губиться
- Фактично це "форма-анкета" замасковані під "крок" — саме те, що doctrine v7.1 §1.2 каже не робити
- Зони друку (front, back, sleeve) змішані з вибором тканини і кольору — це різні рівні рішення

**Де в коді:** `custom_print.html:171-246` — одна секція `cp-step-product` містить 6 блоків конфігурації

---

### 🟡 P6. Мобільний досвід — функціональний, але не інтуїтивний

**Що:** На `<720px`:
- Workbench стає single-column (Stage card зверху, Panel знизу)
- Stage card перестає бути sticky (position: relative)
- Price Capsule ховається за mobile-bar
- Build Strip горизонтально скролиться

**Що конкретно не так:**
- Коли Stage card вгорі (CSS-худі ~360px мін висоти) + Build Strip + заголовок кроку — користувач бачить ТІЛЬКИ худі і чіпи, а опції за межами екрану
- Scroll вниз до опцій → втрачається зв'язок зі Stage Card (вже не видно, як змінюється худі)
- Build Strip з 5 чіпами по 168px кожен = 840px → горизонтальний скрол, але користувач не бачить, що є ще чіпи праворуч (немає індикатора скролу)
- Mobile bar ("Ціну уточнюємо" + "Надіслати") — виглядає відірваним від контексту

**Де в коді:** `custom-print-configurator.css:780-859`

---

### 🟢 P7. CSS-силует замість рендерів — виглядає як прототип

**Що:** Stage використовує CSS-фігури (`cp-garment-body`, `cp-garment-hood`, `cp-garment-sleeve`) замість реальних зображень.

**Де в коді:** `custom-print-configurator.css:369-447`, `custom_print.html:84-91`

**Контекст:** Doctrine v7.1 §6.3 передбачає "base renders / prepared assets" (WebP). CSS-силует — це тимчасове рішення, яке можна залишити для v1, але воно повинно чітко сприйматися як "preview", а не як "placeholder незавершеного додатку". Потрібна хоча б стилізація під "sketch / wireframe" стиль, а не просто прямокутники з заокругленими кутами.

---

### 🟢 P8. Price Capsule на десктопі — загублена в правій колонці

**Що:** Price Capsule (`cp-capsule`) живе всередині `cp-panel-column`, під активним кроком. На десктопі це означає, що вона часто за межами viewport (потрібно скролити вниз по правій колонці).

**Чому це не ідеально:** Doctrine §6.7 вимагає Price Capsule завжди рядом і завжди доступною. V1 план передбачав sticky для desktop, але в реальному CSS це не реалізовано для ціни — sticky є тільки для Stage Card.

---

## 2. Що V2 і V3 пропонують правильно

| Ідея | V2 | V3 | Моя оцінка |
|------|----|----|------------|
| Прибрати початкове худі, почати з Lobby/вибору виробу | ✅ | ✅ | **Обов'язково.** Це найбільша UX-проблема |
| Center Stage + Bottom Tray layout | ✅ | ✅ | **Частково.** Гарна ідея, але full-screen `height: 100vh; overflow: hidden` — ризиковано для accessibility і не відповідає стилю сайту |
| Premium states замість "вдавлених кнопок" | ✅ | ✅ | **Так**, але без перебільшення — "neon glow" занадто агресивний, достатньо чіткого golden border + ✓ badge |
| Горизонтальний slide між кроками | ✅ | ✅ | **Обов'язково.** `translateX` + `opacity` — стандартний, надійний паттерн |
| Zoom при виборі зони друку | — | ✅ | **Гіпотеза [C].** Виглядає ефектно, але CSS zoom на stage може конфліктувати з layout. Залишити як enhancement, не блокувати v1 |
| Cross-fade при зміні кольору | ✅ | ✅ | **Так**, необхідний мінімум motion |
| Розбити Product Step на окремі кроки | ❌ | ❌ | Жоден документ не пропонує. **Це моя головна пропозиція.** |

---

## 3. Що V2 і V3 пропонують НЕПРАВИЛЬНО або РИЗИКОВАНО

### ⚠️ Full-screen locked viewport (V2/V3)

Обидва документи пропонують `height: 100vh; overflow: hidden` — тобто конфігуратор як повноекранний "app". 

**Чому це погано для TwoComms:**
- Руйнує зв'язок з рештою сайту (header, footer, nav)
- Doctrine v7.1 §2.1 `[A]`: "конфігуратор повинен виглядати як природне продовження поточного сайту TwoComms"
- Проблеми з accessibility: screen readers, keyboard navigation, focus management в заблокованому viewport
- Не працює нормально на iPhone з Dynamic Island / Safe Areas
- Потрібно додаткове відображення для scroll content, overflow menus — зайва складність

### ⚠️ "Magnetic Click" з `scale: 0.96` (V3)

V3 пропонує мікро-сжаття при кліку. Це cute, але:
- Конфліктує з `prefers-reduced-motion`
- Додає latency до відгуку (150ms на "сжаття" перед відгуком)
- На слабких Android-телефонах виглядає як "лаг"

### ⚠️ Порядок: "Силует → Цвет → Зона" (V2/V3)

V2 і V3 пропонують Тип → Силует → Цвет → Зона → Файл. Це добре, але упущено:
- **Ткань** зникає з явного шагу (у V2 взагалі не згадується)
- **Розмір** зникає як окремий шаг
- **Деталі** (люверси, шнурки) не згадуються

---

## 4. Моє бачення: Progressive Studio Flow

### 4.1 Філософія

Ми не будуємо ні "форму-анкету" (поточна проблема), ні "повноекранну app-студію" (V2/V3 ризик). 

Ми будуємо **"Progressive Studio"** — звичайна сторінка Django, яка поступово розкривається по мірі вибору. Кожен крок — один тип рішення. Stage росте разом з контекстом.

### 4.2 Ключові принципи

1. **Stage народжується з вибору, а не до нього** — до вибору виробу Stage = стильний placeholder або компактний preview
2. **Один крок = одне рішення** — не більше 3-6 опцій на екран
3. **Panel РОЗШИРЕНА** — не 440px, а 50% desktop ширини, або навіть full-width bottom tray при потребі
4. **Анімації між кроками** — обов'язково, горизонтальний slide
5. **Зберігаємо контекст сайту** — header, footer, brand identity залишаються

### 4.3 Новий Flow (порівняння з поточним)

```
ПОТОЧНИЙ (6 кроків, один мегашаг):          ПРОПОНОВАНИЙ (8 коротких кроків):
─────────────────────────────────           ───────────────────────────────────
1. Старт (quickstart)                       0. Hero + Entry (Для себе / Для команди)
2. Формат (B2C/B2B)                          1. Quickstart (З нуля / Файл / Стилі)
3. Виріб ← МЕГАШАГ:                         2. Lobby — Вибір виробу (центральні картки)
   • Тип виробу                              3. Крій / Силует
   • Посадка                                 4. Тканина + Колір
   • Тканина                                 5. Зони друку + Деталі
   • Колір                                   6. Файл / Reference / Допомога
   • Зони друку                              7. Кількість + Розмір
   • Деталі                                  8. Контакт + Review + Submit
4. Макет (file/brief)
5. Кількість
6. Контакт + Review
```

### 4.4 Детальна архітектура кожного кроку

---

#### STEP 0: Hero + Entry

**Що бачить користувач:** Існуючий Hero (він гарний, залишаємо), але після кліку "Створити свій дизайн" → inline-expand з вибором "Для себе / Для команди", і відразу → перехід до Step 1.

**Зміни:**
- Прибрати з Hero видимість Build Strip і Stage Card (вони з'являються тільки після entry)
- Додати м'яку анімацію appear для inline-expand

---

#### STEP 1: Quick Start

**Layout:** Full-width панель (не split-view). Три картки по центру — стандартний варіант тої частини що вже існує.

**Зміна:** `is-active` не ставиться по дефолту ні на що. Користувач повинен клікнути сам.

---

#### STEP 2: Lobby — Вибір виробу 🆕

**Layout:** Це ключовий новий крок. До цього моменту Stage Card НЕ ПОКАЗУЄ худі. Замість цього:

```
Desktop:
┌─────────────────────────────────────────────────────────────────┐
│  ★ ОБЕРІТЬ ВИРІБ                                               │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │          │  │          │  │          │  │          │       │
│  │  [Худі   │  │ [Футбол- │  │ [Лонг-   │  │ [Свій    │       │
│  │   render]│  │  ка      │  │  слів    │  │  одяг]   │       │
│  │          │  │  render] │  │  render] │  │          │       │
│  │          │  │          │  │          │  │          │       │
│  │  Худі    │  │ Футболка │  │ Лонгслів │  │ Свій одяг│       │
│  │  від 1850│  │  від 700 │  │ від 1400 │  │ Estimate │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│                                                                 │
│  Build Strip: [✓ Старт] [→ Виріб] [○ Крій] [○ Колір] [+3]     │
└─────────────────────────────────────────────────────────────────┘

Mobile:
┌────────────────────┐
│ ★ ОБЕРІТЬ ВИРІБ    │
│                    │
│ ┌──────┐ ┌──────┐  │
│ │ Худі │ │Футб. │  │
│ │ 1850 │ │ 700  │  │
│ └──────┘ └──────┘  │
│ ┌──────┐ ┌──────┐  │
│ │Лонг  │ │ Свій │  │
│ │ 1400 │ │  ?   │  │
│ └──────┘ └──────┘  │
│                    │
│ [  Strips ←→ ]     │
└────────────────────┘
```

**Після вибору:** Stage Card з'являється (animate entrance) зліва, Panel стискається вправо → стандартний split-view для решти кроків.

**Анімація входу:**
1. Обрана картка отримує golden glow + ✓ badge
2. Інші картки м'яко зменшуються і зникають (`opacity: 0, scale: 0.95, 300ms`)
3. Stage Card вливається зліва (`translateX: -40px → 0, opacity: 0 → 1, 400ms`)
4. Panel slide-in справа для наступного кроку

---

#### STEPS 3-5: Конфігурація виробу (РОЗБИТИЙ мегашаг)

Замість одного кроку "Виріб" з 6 блоками, маємо три компактних кроки:

**Step 3: Крій / Силует**
- 2 картки: Regular / Oversize (тільки для худі)
- Для футболки/лонгсліву — пропускається автоматично
- Зміна кроя → Stage Card анімовано оновлює силует (cross-fade)

**Step 4: Тканина + Колір**
- Тканина: 2-3 chip-кнопки (Стандарт / Преміум)
- Під тканиною: Колір — ряд swatch-кружків
- Зміна кольору → Stage Card оновлює fill (cross-fade, `--cp-garment-fill`)
- Ці два — разом, бо обидва візуальні і пов'язані

**Step 5: Зони друку + Деталі**
- Зони: chip-кнопки (Грудь / Спина / Рукав / Нестандартне) — мультиселект
- Деталі: toggle-chip'и (люверси, шнурки, флис)
- Вибір зони → Stage Card підсвічує відповідну зону overlay

---

#### STEPS 6-8: Artwork, Кількість, Review (без значних змін)

Step 6, 7, 8 — залишаються схожими на поточні, але:
- Step 7 (Кількість + Розмір) — об'єднати з Розміром, це одне рішення
- Step 8 (Контакт + Review) — додати Trust block, покращити review summary

---

### 4.5 Новий Desktop Layout — збалансованість Stage і Panel

**Пропозиція: 50/50 замість 60/40**

```css
.cp-workbench {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  /* замість minmax(0, 1fr) minmax(360px, 440px) */
}
```

**Це дає:**
- Stage Card: 50% — достатньо для CSS-силуету чи рендера
- Panel: 50% — значно більше простору для опцій
- На 1440px: ~720px на кожну колонку (замість ~1000+440)
- Для Step 2 (Lobby): Panel ховається, картки центруються

**Альтернатива для малих кроків (Крій з 2 картками):**
Панель може адаптивно звужуватися: `minmax(320px, 500px)` замість жорсткого розміру. Але 50/50 — найпростіший і найчистіший варіант.

---

### 4.6 Рішення для мобільного

**Проблема:** Stage Card вгорі + скрол до опцій = втрата зв'язку.

**Рішення: Compact Stage + Sticky Build Strip**

```
Mobile layout (<640px):
┌────────────────────┐
│ Build Strip (sticky)│ ← завжди видно при scroll
├────────────────────┤
│ Stage (compact)    │ ← auto-height, не min-height: 360px
│ [     Худі     ]   │    максимум 200px на mobile
├────────────────────┤
│                    │
│  Step Content      │ ← повна ширина, більше простору
│  (active step)     │
│                    │
│  [Назад] [Далі]   │
│                    │
├────────────────────┤
│ [≈1850₴] [Далі →] │ ← mobile bar (fixed bottom)
└────────────────────┘
```

**Ключові зміни:**

1. **Stage compact mode на mobile:**
```css
@media (max-width: 639px) {
  .cp-stage-frame {
    min-height: 160px;  /* замість 360px */
    max-height: 200px;
    padding: 0.4rem;
  }
  .cp-garment-shell {
    width: min(80%, 180px);
    aspect-ratio: 0.85;
  }
}
```

2. **Build Strip sticky на mobile:**
```css
@media (max-width: 639px) {
  .cp-build-strip {
    position: sticky;
    top: 0;
    z-index: 20;
    background: var(--cp-bg);
    padding: 0.6rem 0;
    /* gradient fade для індикації скролу */
    mask-image: linear-gradient(90deg, black 90%, transparent);
  }
}
```

3. **Індикатор горизонтального скролу для chips:**
```css
.cp-build-strip::after {
  content: "";
  position: sticky;
  right: 0;
  width: 32px;
  background: linear-gradient(90deg, transparent, var(--cp-bg));
  pointer-events: none;
}
```

---

### 4.7 Система станів кнопок (Button State Architecture)

**Поточна проблема:** `is-active` виглядає як "ледве підсвічений" — тільки субтільний border.

**Нова система:**

```
State      │ Border                │ Background                      │ Badge  │ Transform
───────────┼───────────────────────┼─────────────────────────────────┼────────┼──────────
default    │ rgba(255,255,255,0.08)│ rgba(255,255,255,0.025)         │ —      │ —
hover      │ rgba(255,214,138,0.2) │ rgba(255,255,255,0.05)          │ —      │ translateY(-2px)
selected   │ var(--cp-accent) solid│ linear-gradient gold → subtle   │ ✓ gold │ translateY(-2px)
disabled   │ rgba(255,255,255,0.04)│ rgba(255,255,255,0.01)          │ —      │ — opacity: 0.5
```

**CSS для selected state:**
```css
.cp-option-card.is-active,
.cp-product-card.is-active,
.cp-mini-chip.is-active {
  position: relative;
  border-color: var(--cp-accent);
  background: linear-gradient(180deg, rgba(215, 164, 80, 0.16), rgba(255, 255, 255, 0.03));
  box-shadow: 0 0 0 1px var(--cp-accent), 0 8px 24px rgba(215, 164, 80, 0.12);
  transform: translateY(-2px);
}

/* ✓ Badge */
.cp-option-card.is-active::after,
.cp-product-card.is-active::after {
  content: "✓";
  position: absolute;
  top: -6px;
  right: -6px;
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--cp-accent);
  color: #141214;
  font-size: 12px;
  font-weight: 700;
  box-shadow: 0 2px 6px rgba(0,0,0,0.3);
  animation: badge-pop 200ms cubic-bezier(0.2, 0, 0, 1);
}

@keyframes badge-pop {
  from { transform: scale(0); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}
```

**Критична зміна:** Прибрати `is-active` з дефолтних значень у Django-шаблоні. Замість:
```html
{% if item.value == custom_print_config.defaults.quick_start_mode %}is-active{% endif %}
```
→ Не ставити `is-active` взагалі до кліку користувача. Default value зберігати в JS state, а візуальний `is-active` — тільки після user interaction.

---

### 4.8 Система анімацій між кроками

**Архітектура:** Замість `display: none / block`, використовуємо CSS-трансформації у контейнері:

```css
/* Контейнер кроків */
.cp-step-viewport {
  position: relative;
  overflow: hidden;
}

/* Кожен крок */
.cp-card--step {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  opacity: 0;
  transform: translateX(40px);
  pointer-events: none;
  transition: opacity 300ms cubic-bezier(0.2, 0, 0, 1),
              transform 300ms cubic-bezier(0.2, 0, 0, 1);
}

/* Поточний крок */
.cp-card--step.is-current {
  position: relative;
  opacity: 1;
  transform: translateX(0);
  pointer-events: auto;
}

/* Крок, що пішов назад (вліво) */
.cp-card--step.is-exiting-left {
  transform: translateX(-40px);
  opacity: 0;
}

/* Крок, що пішов вперед (вправо) — для кнопки "Назад" */
.cp-card--step.is-exiting-right {
  transform: translateX(40px);
  opacity: 0;
}
```

**JS логіка:**
```javascript
function transitionToStep(fromStep, toStep, direction = 'forward') {
  const exitClass = direction === 'forward' ? 'is-exiting-left' : 'is-exiting-right';
  const enterFrom = direction === 'forward' ? 'translateX(40px)' : 'translateX(-40px)';
  
  // 1. Виходящий крок
  fromStep.classList.add(exitClass);
  fromStep.classList.remove('is-current');
  
  // 2. Вхідний крок — спочатку налаштовуємо початкову позицію
  toStep.style.transform = enterFrom;
  toStep.style.opacity = '0';
  toStep.classList.add('is-current');
  
  // 3. Trigger reflow, потім анімуємо вхідний крок
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      toStep.style.transform = '';
      toStep.style.opacity = '';
    });
  });
  
  // 4. Cleanup після анімації
  setTimeout(() => {
    fromStep.classList.remove(exitClass);
  }, 350);
}
```

---

### 4.9 Stage Card — анімація оновлення

**Cross-fade при зміні виробу/кольору:**
```css
.cp-garment {
  transition: opacity 250ms ease, transform 250ms ease;
}

.cp-garment.is-transitioning {
  opacity: 0;
  transform: scale(0.97);
}
```

**Підсвічування зони при виборі:**
```css
.cp-zone-pin.is-active {
  animation: zone-pulse 1.5s ease-in-out infinite alternate;
}

@keyframes zone-pulse {
  from { box-shadow: 0 0 0 0 rgba(215, 164, 80, 0.3); }
  to { box-shadow: 0 0 0 8px rgba(215, 164, 80, 0); }
}
```

---

### 4.10 Build Strip — покращення навігації

**Поточна проблема:** Чіпи мають тільки `is-active` і `is-done` стани, без чіткої візуальної різниці.

**Нові стани:**

```css
/* Done — пройдений крок, можна повернутися */
.cp-build-chip.is-done {
  border-color: rgba(156, 206, 142, 0.25);
  background: rgba(156, 206, 142, 0.06);
}
.cp-build-chip.is-done::before {
  content: "✓";
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--cp-success);
  color: #141214;
  font-size: 10px;
  font-weight: 700;
  margin-right: 6px;
}

/* Current — поточний крок */
.cp-build-chip.is-active {
  border-color: var(--cp-accent);
  background: rgba(215, 164, 80, 0.12);
  box-shadow: 0 0 0 1px var(--cp-accent);
}

/* Pending — ще не досягнутий */
.cp-build-chip:not(.is-active):not(.is-done) {
  opacity: 0.5;
  cursor: default;
  pointer-events: none;
}
```

---

## 5. Чеклист змін (технічний)

### 5.1 CSS (`custom-print-configurator.css`)

| # | Зміна | Пріоритет |
|---|-------|-----------|
| 1 | Desktop grid: `1fr 1fr` замість `1fr minmax(360px,440px)` | 🔴 Must |
| 2 | Видалити `min-height: 520px` / `360px` для Stage Frame на mobile → max-height: 200px | 🔴 Must |
| 3 | Додати step transition animations (translateX + opacity) замість display toggle | 🔴 Must |
| 4 | Покращити `is-active` стан: golden border + ✓ badge + subtle glow | 🔴 Must |
| 5 | Build Strip: sticky на mobile + scroll indicator | 🟡 Should |
| 6 | Додати cross-fade transition для garment зміни | 🟡 Should |
| 7 | Додати zone-pulse анімацію для зон друку | 🟡 Should |
| 8 | Build Strip chip стани: done (green ✓) / current (gold) / pending (dimmed) | 🟡 Should |
| 9 | Покращити CSS-силует (subtle gradient, реалістичніший вигляд) | 🟢 Nice |

### 5.2 HTML (`custom_print.html`)

| # | Зміна | Пріоритет |
|---|-------|-----------|
| 1 | Розбити `cp-step-product` на 3 окремих кроки (крій, тканина+колір, зони) | 🔴 Must |
| 2 | Додати Step 2 "Lobby" — full-width вибір виробу ДО появи Stage Card | 🔴 Must |
| 3 | Прибрати `is-active` дефолти зі ВСІХ кнопок, що рендеряться серверно | 🔴 Must |
| 4 | Обгорнути кроки у `.cp-step-viewport` для анімацій | 🟡 Should |
| 5 | Додати `data-direction` атрибути для forward/backward navigation | 🟡 Should |
| 6 | Додати Build Strip чіп стани через data-атрибути | 🟡 Should |

### 5.3 JS (`custom-print-configurator.js`)

| # | Зміна | Пріоритет |
|---|-------|-----------|
| 1 | Імплементувати `transitionToStep()` з forward/backward анімаціями | 🔴 Must |
| 2 | Stage Card visibility: прихований до Step 2 → animated entrance | 🔴 Must |
| 3 | `is-active` встановлювати ТІЛЬКИ на user click, не при ініціалізації | 🔴 Must |
| 4 | Cross-fade логіка для garment зміни (колір, тип, крій) | 🟡 Should |
| 5 | Build Strip автоматичне оновлення done/current/pending станів | 🟡 Should |
| 6 | Scroll-to-step: при переході на mobile — scroll до нового step content | 🟡 Should |

### 5.4 Backend (`custom_print_config.py`, `views`)

| # | Зміна | Пріоритет |
|---|-------|-----------|
| 1 | Прибрати `defaults.product.type: 'hoodie'` як видимий дефолт | 🟡 Should |
| 2 | Розбити конфіг на sub-steps для нового flow | 🟡 Should |

---

## 6. Порядок реалізації

```
Phase 1 (Критичні UX-фікси):
1. Розбити product-step на 3 кроки (HTML + JS + CSS)
2. Додати Lobby (Step 2) з вибором виробу по центру
3. Прибрати is-active дефолти
4. Додати step transitions (translateX/opacity)

Phase 2 (Візуальний polish):
5. Покращити is-active стан (golden glow + badge)
6. Desktop grid: 50/50 замість 60/40
7. Mobile Stage compact + sticky Build Strip
8. Cross-fade garment transitions

Phase 3 (Enhancement):
9. Build Strip state management (done/current/pending)
10. Zone pulse animation
11. Mobile scroll indicators
12. Price Capsule sticky на desktop
```

---

## 7. Що НЕ робити (антипаттерни)

| Не робити | Чому |
|-----------|------|
| `height: 100vh; overflow: hidden` | Ломає сайт, accessibility, mobile Safari |
| Magnetic click з `scale: 0.96` | Input latency, reduced-motion конфлікт |
| "Neon glow" з `box-shadow: 0 0 15px` | Занадто агресивний, не бренд TwoComms |
| Full CSS zoom для зон друку | Layout breaks, потребує перерахунку координат |
| Видалення header/footer | Doctrine §2.1 [A]: природне продовження сайту |
| Position: fixed для Stage на mobile | Забирає 55% viewport, нічого не залишає для контенту |
| Горизонтальний скрол для опцій (V2, "карусель цветов") | На desktop це антипаттерн, на mobile chip-wrap краще |

---

## 8. Резюме: 5 найважливіших змін

1. **🏠 Lobby Step** — користувач обирає виріб ДО того, як побачить Stage з худі
2. **📐 Розбивка мегашагу** — Step "Виріб" розбити на 3 окремих кроки (Крій, Тканина+Колір, Зони+Деталі)
3. **🎭 Step Transitions** — горизонтальний slide між кроками замість миттєвого моргання
4. **✓ Premium Selected State** — чіткий golden border + ✓ badge замість субтільного підсвічування
5. **📱 Mobile Compact Stage** — зменшити Stage на mobile до max 200px, зробити Build Strip sticky

Ці п'ять змін адресують ВСІ скарги користувача (порядок кроків, пропорції layout, стан кнопок, анімації, мобільний UX) і залишаються в межах doctrine v7.1, не виходячи на ризиковану територію повноекранної "app-студії".
