# Custom Print Hero Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Пересобрать hero страницы `custom-print` в минималистичную text-first композицию с лёгкой motion-системой и ясным DTF/Telegram copy, без изменения production-логики конфигуратора.

**Architecture:** Меняем presentation layer в шаблоне и CSS, плюс добавляем маленький scroll-linked эффект в existing JS. Существующая форма, шаги, stage-card, lead flow и расчёты остаются без изменений.

**Tech Stack:** Django templates, статический CSS, существующие SVG/PNG-ассеты бренда.

---

### Task 1: Зафиксировать новую hero-разметку

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/pages/custom_print.html`

**Step 1: Обновить структуру hero**
- Заменить перегруженный hero на:
  - узкий brand block с логотипом `TwoComms`;
  - новый headline/subcopy;
  - CTA-группу;
  - декоративный background-art без самостоятельной “правой панели”.

**Step 2: Сохранить совместимость**
- Не трогать `data-start-flow` и существующую кнопку Telegram.
- Не менять расположенный ниже `<form id="customPrintConfiguratorForm">`.

**Step 3: Проверить шаблон**
- Убедиться, что HTML остаётся валидным, а все новые классы согласованы с CSS.

### Task 2: Пересобрать стили hero

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/css/custom-print-configurator.css`

**Step 1: Обновить desktop-композицию**
- Сделать hero одноколоночным по смыслу, с текстом как главным фокусом.
- Оставить глубину и премиальный свет, но без перегруза декоративными модулями.

**Step 2: Добавить brand-first детали**
- Стили для brand block, badge, text column, background glow, logo mark и faint garment silhouette.

**Step 3: Обновить mobile-версию**
- Сохранить одну колонку, чистый ритм и полную ширину CTA.
- Упростить декоративные элементы, чтобы mobile не выглядел шумным.

**Step 4: Проверить отсутствие побочных эффектов**
- Убедиться, что новые стили не ломают stage-card, waterfall и финальные блоки.

### Task 3: Добавить деликатное движение

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/js/custom-print-configurator.js`

**Step 1: Scroll-linked effect**
- Добавить очень лёгкий parallax для hero background через CSS custom property.

**Step 2: Accessibility**
- Отключать motion при `prefers-reduced-motion`.

**Step 3: Safety**
- Не трогать логику конфигуратора и draft flow за пределами hero.

### Task 4: Визуальная проверка

**Files:**
- Verify only

**Step 1: Поднять локальную страницу**
- Запустить локальный сервер или использовать существующий dev entrypoint.

**Step 2: Проверить desktop**
- Открыть `custom-print` и сделать визуальную проверку hero на desktop.

**Step 3: Проверить mobile**
- Открыть ту же страницу в мобильном viewport и убедиться, что hero не разваливается и CTA читаемы.

**Step 4: Проверить регрессии**
- Убедиться, что переход к конфигуратору и блоки ниже hero работают как раньше.
