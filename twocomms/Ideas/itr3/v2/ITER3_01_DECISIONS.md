# ITER3_01 — Decisions & priorities (P0 / P1 / P2)

Цель Iter3: **доточить Iter2** без поломки структуры/дизайна.  
Фокус: убрать "ИИ-язык" и техжаргон, сделать первый экран проще, заякорить цену, повысить доверие и скорость контакта (Telegram), при этом не навредить перформансу.

> **📱 Mobile-first:** Большинство трафика — мобильный. Все решения проверять на 320/360/390px. Touch targets ≥ 44px.

---

## P0 — обязательно в этом релизе (высокий ROI, низкий риск)

### P0.1 Цена-якорь вместо диапазона
- В hero-карточке и везде, где показываем цену на главных экранах:  
  **`від 280 грн/м` / `от 280 грн/м` / `from 280 UAH/m`**  
- Диапазоны (280–350) — убрать с первого экрана (можно оставить внутри таблицы цен на /price/).

### P0.2 Telegram deep-link с предзаполненным текстом
- Все CTA "Telegram" должны вести на **deep-link** с `?text=` (и корректным URL-encode).
- Текст — разный для Home/Price/Requirements/Order-success/Quality (см. K4 в copy-файлах Iter3).

### P0.3 Hero: упрощение до 6–7 смысловых элементов
- Убираем перегруз: **убрать eyebrow/дубли**, не повторять "контроль белого/QC/preflight".
- Микро-обещание переносим в карточку цены: `✅ Погоджуємо нюанси перед друком`.

### P0.4 Убрать англицизмы и непонятные термины из UA/RU UI
Запрещены в UI (UA/RU): `preflight`, `gang sheet/ганг-лист`, `hot peel`, `QC`, `Summary`, `Knowledge Base`, `Safe area`, `OK/INFO/WARN/FAIL`.

### P0.5 Формулировка про электричество
- **Генератор НЕ упоминать** (его нет).
- `Стабільне виробництво — друкуємо без пауз` (и аналоги RU/EN)

### P0.6 Fix локализационных артефактов
- UA/RU: убрать "половина англ/половина укр" в кнопках.

### P0.7 Навигация
- `Конструктор` → `Зібрати лист 60 см` (UA) / `Собрать лист 60 см` (RU) / `Build a 60 cm sheet` (EN)

### P0.8 Footer trust
- `Файл перевіряємо до друку. Нюанси погоджуємо в Telegram.` (UA) + аналоги RU/EN

### P0.9 Demo-маркировка
- Placeholder-карточки пометить `DEMO / оновлюємо`.

---

## P1 — после P0 (сильный эффект, но требует аккуратной реализации)

### P1.1 Multi-Step Loader
- SVG-иконки + аккуратная анимация (CSS only / минимум JS).
- Не делать тяжёлых эффектов, не ронять FPS.

### P1.2 Калькулятор: сценарий "по размерам"
- Улучшить тексты, подсказки, ошибки.

### P1.3 Sticky CTA без конфликта с dock
- Если dock виден — sticky скрывается (IntersectionObserver).

### P1.4 🔵 Dot Distortion Background — обновление физики
**Что:** Модифицировать существующий dot background на главной.  
**Зачем:** Текущий эффект = "фонарик" (притяжение + halo). Нужен более приятный, как [Aceternity Dot Distortion Shader](https://ui.aceternity.com/blocks/shaders/dot-distortion-shader).

**Ключевые изменения:**
| Сейчас | Нужно |
|--------|-------|
| Pull (притяжение) | **Repulsion (отталкивание)** |
| Flashlight halo | **Убрать.** Только dot-level glow |
| Нет breathing | **Breathing** ±15% размера (инд. фаза) |
| Нет glow pulses | **Random glow** на отдельных точках |
| Нет spring-back | **Spring-back** к grid |

**Подробная спецификация:** см. `ITER3_05_UI_MICROPACK.md`, секция 8.

### P1.5 🎨 Component Visual Polish
**Что:** Микро-улучшения визуала без полной переработки.  
**Список:**
- Кнопки: hover `scale(1.02)` + shadow elevation
- Карточки: staggered fade-in-up через IntersectionObserver
- FAQ: аккордеон `max-height` + left border accent
- Инпуты: animated underline на focus
- Dropzone: dashed border pulse при drag-over
- Price badge: shimmer gradient
- Mobile dock: slide-up entrance

**Подробная спецификация:** см. `ITER3_05_UI_MICROPACK.md`, секция 9.

---

## P2 — "вау", только если не трогаем скорость

### P2.1 One-shot микро-эффекты (на 1 экран максимум)
- "Сканер файла" при статусе `Перевіряємо файл…`
- Мягкий "glow" Telegram-иконки при первом появлении dock
- Деликатный pulse у Secondary CTA

---

## Definition of Done (DoD) — как понять, что Iter3 готова

### ✅ Тексты
1) `rg` по DTF-части: 0 вхождений запрещённых терминов (P0.4) в UI-строках.  
2) Все H1 соответствуют copy-файлам (3 языка).  
3) CTA Primary ≤ 14 символов на UA (320px safe).  
4) Rotator: ≥ 3 фразы, НЕ дублирующие Hero.  
5) FAQ: формат «Коротко / Детальніше» (UA/RU/EN).  
6) Post-submit: 🎉 + время ожидания + доп. ссылки.  
7) Footer trust line обновлён.

### ✅ Визуал
8) Hero ≤ 7 информационных элементов.  
9) Ценовой якорь = `від 280 грн/м` (не диапазон).  
10) Нет негатива на первом экране.  
11) Telegram link = deep-link с `?text=` (K4).  
12) Demo-контент помечен.

### ✅ Mobile
13) Hero на 320/360/390 px: не ломается.  
14) CTA не уезжают и не накладываются.  
15) Dock не перекрывает CTA и input-поля.  
16) **Touch targets ≥ 44×44px** на всех интерактивных элементах.

### ✅ Performance
17) Все анимации — `transform`/`opacity` only.  
18) `prefers-reduced-motion: reduce` — анимации выключаются.  
19) Lighthouse Mobile ≥ текущий master.  
20) **Dot background: ≤620 dots на mobile (tier 2), не ронять FPS.**

### ✅ i18n
21) Все 3 языка обновлены синхронно.  
22) Нет смешения языков на одной странице.  
23) K1/K2/K3/K4 на всех языках.

### ✅ Safety & Deploy
24) Изменения ТОЛЬКО в `twocomms/dtf/`.  
25) `collectstatic` выполнен.  
26) Cache version обновлён (?v=).  
27) Все коммиты осмысленные.  
28) **Component visual polish не ломает существующий layout.**
