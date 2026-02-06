# Effects Map (DTF)

## Rules
- Heavy: максимум 1 на страницу
- Medium: максимум 3 на страницу
- Micro: максимум 8 на страницу
- Fallback: при `prefers-reduced-motion` heavy/medium упрощаются или отключаются

## Implemented

### `/` Home
- Heavy:
  - `Flip Words` в hero-заголовке (группа `hero`)
- Medium:
  - `Background Beams` (animated beams layer)
  - Scan-pass/hero glow (существующий hero scan layer)
- Micro:
  - Stateful CTA кнопки
  - Hover/shine на кнопках
  - Reveal-on-scroll
  - Compare slider
  - Lens zoom/modal
  - FAQ toggles

### `/order`
- Heavy: нет
- Medium:
  - Tabs indicator + динамический калькулятор HTMX
- Micro:
  - Stateful submit
  - Upload dropzone/paste
  - Form focus/validation
  - Draft autosave

### `/status`
- Heavy: нет
- Medium: нет
- Micro:
  - Stateful submit
  - Status flash
  - Copy link feedback

### `/gallery`
- Heavy: нет
- Medium:
  - Compare cards
  - Lens modal
- Micro:
  - Hover effects карточек/кнопок
  - Reveal-on-scroll

### `/quality`, `/requirements`, `/templates`, `/contacts`, `/legal/*`
- Heavy: нет
- Medium: точечно (контентные акценты)
- Micro:
  - hover/focus states
  - единая кнопочная система и micro-feedback

### `/blog/`
- Heavy/Medium:
  - Tracing Beam timeline (lazy update + fallback на mobile/reduced-motion)
- Micro:
  - Cards on click overlay
  - Hover/focus подсказки
  - Stateful links

### `/blog/<slug>/`
- Heavy: нет
- Medium: нет
- Micro:
  - Reading progress bar
  - Related links / internal linking
