# ITER3_FILE_MAP — Карта файлов проекта

> Где что лежит. Агент-исполнитель НЕ тратит токены на поиск — смотрит сюда.

---

## Шаблоны (templates) → URL → Секция copy

| URL | Django template | View name | Секция copy | data-page |
|-----|----------------|-----------|-------------|-----------|
| `/` | `dtf/index.html` | `landing` | B) Головна | `home` |
| `/price/` | `dtf/price.html` | `price` | C) Ціни | `price` |
| `/order/` | `dtf/order.html` | `order` | D) Замовлення | `order` |
| `/order/thanks/<kind>/<number>/` | `dtf/thanks.html` | `thanks` | D) Post-submit | — |
| `/requirements/` | `dtf/requirements.html` | `requirements` | E) Вимоги | `requirements` |
| `/templates/` | `dtf/templates.html` | `templates` | F) Шаблони | `templates` |
| `/quality/` | `dtf/quality.html` | `quality` | G) Якість | `quality` |
| `/gallery/` | `dtf/gallery.html` | `gallery` | H) Кейси | `gallery` |
| `/faq/` | `dtf/faq.html` | `faq` | I) FAQ | `faq` |
| `/constructor/app/` | `dtf/constructor_app.html` | `constructor_app` | J) Конструктор | `constructor` |
| `/delivery-payment/` | `dtf/delivery_payment.html` | `delivery_payment` | L) Оплата | — |
| `/returns/` | `dtf/legal/returns.html` | `returns` | M) Возврат | — |
| `/privacy/` | `dtf/legal/privacy.html` | `privacy` | N) Конфіденційність | — |
| `/terms/` | `dtf/legal/terms.html` | `terms` | O) Оферта | — |
| `/sample/` | `dtf/sample.html` | `sample` | P) Безкоштовний тест | `sample` |
| `/blog/` | `dtf/blog.html` | `blog` | — (база знань) | `blog` |
| `/contacts/` | `dtf/contacts.html` | `contacts` | — | `contacts` |
| `/about/` | `dtf/about.html` | `about` | — | `about` |

## Базовый шаблон

- `dtf/base.html` — header, footer, nav, dock, rotator, meta

## Статические файлы

### CSS (основные)
```
dtf/static/dtf/css/tokens.css        — CSS-переменные (цвета, шрифты, размеры)
dtf/static/dtf/css/dtf.css           — основной CSS (исходник)
dtf/static/dtf/css/dtf.min.css       — минифицированный CSS
dtf/static/dtf/css/fonts-local.css   — шрифты
```

### CSS (компоненты — существующие)
```
dtf/static/dtf/css/components/floating-dock.css
dtf/static/dtf/css/components/multi-step-loader.css
dtf/static/dtf/css/components/effect.*.css    — эффекты (bg-beams, compare, pointer-highlight и др.)
```

### JS (основные)
```
dtf/static/dtf/js/dtf.js             — главный JS (2393 строки, все эффекты)
dtf/static/dtf/js/dtf.min.js         — минифицированный
dtf/static/dtf/js/vendor/htmx.min.js — HTMX
```

### JS (компоненты — существующие)
```
dtf/static/dtf/js/components/core.js
dtf/static/dtf/js/components/_utils.js
dtf/static/dtf/js/components/floating-dock.js
dtf/static/dtf/js/components/multi-step-loader.js
dtf/static/dtf/js/components/effect.*.js      — эффекты
dtf/static/dtf/js/components/effects-bundle.js — бандл всех эффектов
```

### SVG (пока нет — создаёт Agent4)
```
dtf/static/dtf/svg/icon-*.svg         — иконки от Agent4
```

## Ключевые функции в dtf.js (для ориентации)

| Функция | Строка | Что делает |
|---------|--------|-----------|
| `initHomeDotBackground()` | ~1124 | Dot background на главной (МЕНЯТЬ физику) |
| `initPrintheadScan()` | ~957 | Scan-эффект в hero |
| `initHeroTilt()` | ~1346 | Tilt-эффект hero card |
| `initSpotlight()` | ~1381 | Spotlight на карточках |
| `initInkDroplets()` | ~1413 | Ink droplets (legacy) |
| `resolveAmbientTier()` | ~944 | Определение тира устройства (0-4) |
| `resolveScanTier()` | ~919 | Тир для scan-эффекта |
| `allowAmbientEffects()` | — | Проверка prefers-reduced-motion |

## CSS-переменные (уже определены в tokens.css)

Агент должен **использовать существующие** переменные, не создавать дублей:
```
--dtf-accent, --dtf-success, --dtf-warning, --dtf-danger, --dtf-info, --dtf-border
```
