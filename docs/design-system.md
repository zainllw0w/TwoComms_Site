# Design System — DTF Redesign

## Подключение
`tokens.css` подключается в `base.html` перед `dtf.css`:
```html
<link rel="stylesheet" href="{% static 'dtf/css/tokens.css' %}">
<link rel="stylesheet" href="{% static 'dtf/css/dtf.css' %}">
```

## Typography
- Display: `Space Grotesk`
- UI: `Manrope`
- Mono: `JetBrains Mono`

Utility‑классы:
- `.font-display` — display headings
- `.font-ui` — body/UI
- `.font-mono` — тех. метки
- `.tabular-nums` — цены/таблицы/метрики (tabular nums + slashed zero)

## Numeric formatting
Для цен/таблиц/метрик используем:
```css
font-variant-numeric: tabular-nums slashed-zero;
font-feature-settings: "tnum" 1, "zero" 1;
```

## Tokens
Полный перечень токенов: `twocomms/dtf/static/dtf/css/tokens.css`.
