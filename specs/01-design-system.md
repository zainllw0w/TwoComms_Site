# 01 — Design System (DTF Redesign)

## Цель
Зафиксировать дизайн‑токены и базовый визуальный язык (Control Deck × Lab Proof), чтобы все последующие страницы были консистентны.

## Файлы
- `twocomms/dtf/static/dtf/css/tokens.css` — источник токенов.
- `twocomms/dtf/static/dtf/css/dtf.css` — потребитель токенов.
- `twocomms/dtf/templates/dtf/base.html` — подключение шрифтов и токенов.

## 6.2.A Шрифты (фиксировано)
**Display / Headings:** `Space Grotesk`  
- Причина: ink traps → ассоциация с ink spread/печатью.  
- Настройка: `letter-spacing: -0.02em` для крупных заголовков (`h1/h2`, hero).

**UI / Body:** `Manrope`  
- Причина: инженерный характер, удобочитаемость в цифрах.  
- Настройка: для всех цен/таблиц/метрик использовать  
  `font-feature-settings: "tnum" on, "zero" on`  
  (также дублируется через `font-variant-numeric: tabular-nums slashed-zero`).

**Mono / Tech:** `JetBrains Mono`  
- Назначение: артикулы, статусы, параметры файлов, тех. метки/overline.

## Базовые компоненты (UI skeleton)
- Buttons:
  - Primary: molten gradient, L1 hover/active, min-height 40px (48px на mobile)
  - Secondary/Outline: glass‑surface с тонкой рамкой
  - Ghost: прозрачный фон, тонкая рамка
  - Focus: `:focus-visible` с `--c-molten`
- Inputs:
  - `font-size: 16px` для iOS (no zoom)
  - `caret-color: --c-molten`
  - `aria-invalid="true"` → `--c-heat` + subtle ring
  - Helper text: muted, 0.8rem, line-height 1.3
- Cards/Panels: surface + тонкая рамка + мягкая тень
- Badges/Chips: mono, uppercase, letter-spacing 0.04em
- Tabs: pill‑container с индикатором (L1/L2)
- Tables: tabular nums, thin separators, header contrast
- Toasts: small, non-blocking, color‑coded borders (success/warn/error)
- Status timeline: vertical line, dots for stages, mono labels for codes

## A11y
- Skip link добавлен в `base.html`
- `:focus-visible` активен для интерактивных элементов

## Цветовые токены (ядро)
Опираемся на Monolith v7 (углубляется в фазе 2):
- `--c-bg-void`, `--c-surface-1`, `--c-surface-2`
- `--c-text`, `--c-muted`, `--c-border`
- `--c-molten`, `--c-heat`, `--c-powder`
- Micro‑CMYK: `--c-cyan`, `--c-magenta`, `--c-yellow`, `--c-key`

## Применение палитры
- Legacy токены (`--bg`, `--surface`, `--text` и т.д.) переведены на тёмную Control Deck палитру.

## Размеры и ритм
- Spacing: `--space-1..8` (4–64px)
- Радиусы: `--r-1..4` (6–24px)
- Тени: `--shadow-1..2`

## Z‑Index (строго по токенам)
Используем только `--z-*` из `tokens.css` (без `9999`).

## Motion (подготовка)
Токены скорости: `--motion-fast/base/slow`, `--motion-ease`.  
Уровни L0–L4 реализуются в фазах 2–4.

## Примечания
- `tokens.css` подключен в `base.html` до `dtf.css`.
- В `tokens.css` временно сохранены legacy‑токены (для совместимости текущего DTF UI).
- Уточнение языка: UA по умолчанию, RU доступен; EN планируется после финализации контента (см. `specs/dtf/i18n-spec.md`).
