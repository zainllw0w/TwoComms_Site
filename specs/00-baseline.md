# 00 — Baseline (DTF Redesign)

## Контекст и маршрутизация
- DTF поддомен обслуживается отдельным URLConf через middleware: `twocomms/twocomms/middleware.py` (SubdomainURLRoutingMiddleware).
- Для `dtf.*` используется `twocomms/twocomms/urls_dtf.py` → `include('dtf.urls')`.
- Основной домен (`/`) обслуживается `storefront` и не является целью редизайна.

## Django приложения и ключевые файлы
- DTF приложение: `twocomms/dtf` (views, forms, models, templates, static).
- Проектные настройки: `twocomms/twocomms/settings.py`.
- Основные URL:
  - `twocomms/twocomms/urls_dtf.py`
  - `twocomms/dtf/urls.py`

## Карта страниц (DTF)
Из `twocomms/dtf/urls.py`:
- `/` → `dtf.index` (landing)
- `/order/` → заказ
- `/order/thanks/<kind>/<number>/` → спасибо
- `/status/` → проверка статуса
- `/requirements/` → требования
- `/price/` → цены
- `/delivery-payment/` → доставка и оплата
- `/contacts/` → контакты
- `/lead/fab/` → POST лид из FAB

## Шаблоны (DTF)
`twocomms/dtf/templates/dtf/`:
- `base.html` (общий каркас, навигация, футер, модал менеджера)
- `index.html` (Home)
- `order.html` (Order)
- `status.html`
- `requirements.html`
- `price.html`
- `delivery_payment.html`
- `contacts.html`
- `thanks.html`

## Статика (DTF)
`twocomms/dtf/static/dtf/`:
- `css/dtf.css` (~13 KB)
- `js/dtf.js` (~6.9 KB)
- `assets/` (template-60cm.pdf, template-60cm.ai, hot-peel.gif)

## JS/интерактив
`dtf.js` реализует:
- Reveal on scroll (IntersectionObserver + prefers-reduced-motion)
- Табулятор для формы заказа (готовый ганг-лист vs помощь)
- Клиентский калькулятор цены (по data-атрибутам)
- Guard по формату файла (PDF/PNG)
- Скелетон-снятие на load изображений
- FAB модал + отправка лид-формы (fetch + CSRF)

## Сборка фронта
- Vite **не используется**.
- Есть PostCSS+PurgeCSS скрипт для темы основного сайта: `npm run build:css` → `twocomms/twocomms_django_theme/static/css/styles.purged.css`.
- DTF CSS/JS сейчас — отдельные статические файлы без сборщика.

## HTMX
- Атрибутов `hx-*` в репозитории не найдено.
- HTMX эндпоинты на DTF страницах отсутствуют (на текущем состоянии).

## Базовая оценка Web Vitals (грубая, по статике)
Основание: минимальные размеры CSS/JS, отсутствует тяжелый JS, hero без крупных изображений.
Оценка **предварительная** (без Lighthouse/field-данных, требует верификации после деплоя).

Home (`/`):
- LCP: ~1.8–2.6s (desktop), ~2.2–3.2s (mobile 4G)
- INP: ~40–90ms
- CLS: ~0.02–0.06

Order (`/order/`):
- LCP: ~1.7–2.5s (desktop), ~2.1–3.0s (mobile 4G)
- INP: ~50–100ms
- CLS: ~0.02–0.05

Примечание: после редизайна обязательно замерить Lighthouse/Web Vitals на проде.

## Риски и неизвестные
- DTF страницы не используют HTMX — возможна интеграция с нуля (нужна аккуратная прогрессивная деградация).
- Текущий дизайн светлый, минималистичный; новый стиль (Control Deck + Lab Proof) — значительная смена визуального языка.
- В DTF есть бизнес-логика на сервере (формы, pricing, уведомления) — нельзя ломать flow.
- Поддоменный роутинг: важно не трогать `storefront` и основной домен.

## Файлы, вероятно затрагиваемые в редизайне
- `twocomms/dtf/templates/dtf/*.html`
- `twocomms/dtf/static/dtf/css/dtf.css` (или новая структура токенов/компонентов)
- `twocomms/dtf/static/dtf/js/dtf.js` (инициализации, motion tiers, feature flags)
- `twocomms/twocomms/middleware.py` (только при необходимости, обычно нет)
- `specs/01-design-system.md`, `static/css/tokens.css`, `ASSETS_MANIFEST.md` (следующие фазы)

