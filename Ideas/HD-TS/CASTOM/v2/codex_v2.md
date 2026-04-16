# TwoComms Custom Print V2 — Consolidated Master Plan (Codex)

Цей документ — моя зведена архітектура V2 на основі глибокого аудиту поточного коду та блюпрінта `TWOCOMMS_CUSTOM_PRINT_V2_HANDOFF_ANALYSIS.md`. Я беру кращі ідеї з handoff-документа, додаю власні уточнення (узгодженість з існуючими Django моделями, Telegram-нотифікаціями та кошиком), і формую конкретний план реалізації.

---

## 0. Кредо реалізації

- **Жодного автовибору.** Стан стартує порожнім (`null`), рендер показує placeholder.
- **Waterfall** замість Tabs: завершені кроки згортаються у рядок, наступний плавно з’являється знизу.
- **Stage Receipt** всередині картки виробу: ціна живе на сцені, біля візуалу.
- **Прозорі мікро-транзакції:** ціна прямо на кнопці (+300 грн, +500 грн, +100 грн).
- **Per-zone uploads:** кожна обрана зона отримує свою dropzone, бекенд вже вміє обробляти через `placement_specs.file_index` + `CustomPrintLeadAttachment.placement_zone`.
- **Smart Sizing:** qty=1 → чіп-ряд XS…2XL; qty>1 → матриця з полями розмірів.
- **Dual Finale:** дві кнопки — «Додати в кошик» (сесійна позиція) і «Передати менеджеру» (існуючий Telegram-flow).
- **B2B окрема гілка:** живий калькулятор, поле бренду обов’язкове.
- **Роздрібна гілка:** поле бренду повністю прибирається.

---

## 1. Флоу (Progressive Waterfall)

Єдиний лінійний waterfall без tab-swap. Кроки:

| # | ключ | назва | умова |
|---|------|-------|-------|
| 1 | `mode`     | Для кого кастом (B2C / B2B)           | завжди |
| 2 | `product`  | Виріб                                 | завжди |
| 3 | `config`   | Крій + тканина + колір                | якщо виріб має fits/fabrics |
| 4 | `zones`    | Зони друку + преміум-деталі            | завжди |
| 5 | `artwork`  | Послуга (готове / допрацювати / дизайн) + per-zone dropzones + бриф | завжди |
| 6 | `quantity` | Кількість + розміри (смарт)            | завжди |
| 7 | `gift`     | Подарункова послуга (+100 грн)         | завжди (опційна галочка) |
| 8 | `contact`  | Контакт + (для B2B) бренд + дві фінальні кнопки | завжди |

Квік-старт (`quickstart`) та `starter_style` прибираються з UI. Поле `starter_style` у бекенді лишаю (щоб не ламати історичні ліди), але в JS ніколи не записується.

**Поведінка waterfall**:
- Кожна секція — `<section class="cp-step" data-step="mode">`.
- Усі кроки лежать у DOM у правильному порядку. На старті лише перший має `.is-active`, решта — `.is-pending` (невидимі).
- Коли крок валідно завершується, він одержує клас `.is-done` (колапсується до рядка-резюме `✅ Формат: Для себе · [Змінити]`). Наступний крок одержує `.is-active` і розкривається через `max-height` + `opacity` transition.
- Клік на згорнутий рядок → крок знову стає `.is-active` (попередній залишається `.is-done`, змінюється значення). Наступні кроки перевіряють свою валідність; якщо залежності порушені — зісковзують у `.is-pending`.
- Ніколи не використовуємо `transform: translateX` swap-анімацію. Тільки vertical waterfall.

---

## 2. Stage Card → Stage Receipt (ціна на сцені)

- Старий `<aside class="cp-capsule">` і `<div class="cp-mobile-bar">` — видаляються повністю.
- У `.cp-stage-card` з’являється `<div class="cp-stage-receipt">`:
  - `Підсумок` / `— грн` (поки немає продукту) → динамічно оновлюється.
  - Брейкдаун (база, зони, послуга, люверси, подарунок, знижка B2B).
  - Підказка під ціною (сегмент, кількість, зона).
- `.cp-stage-card` прикріплюється `position: sticky; top: 80px` на десктопі.
- На мобайлі stage card рендериться `position: static` зверху першого кроку, receipt-рядок закріплюється внизу viewport за допомогою нового sticky band на рівні `.cp-shell`.

---

## 3. Крок 1: Формат (mode)

- Дві картки `Для себе` / `Для бренду (Опт)`.
- За замовчуванням — нічого не обрано. Поки юзер не клікне, наступні кроки приховані.
- B2C:
  - Поле «бренд» не показується ніде.
  - Калькулятор працює у роздрібному режимі.
- B2B:
  - У крокі `contact` обов’язкове поле «Назва бренду / Instagram».
  - На `quantity` показується жива смуга знижок: `кожні 5 шт = -10 грн/од`.

---

## 4. Крок 2: Виріб

- 4 карточки (hoodie, tshirt, longsleeve, customer_garment).
- Жодного автофокуса, жодного placeholder-вибору.
- При виборі:
  - Записуємо `productType`, скидаємо fit/fabric/color/zones/add_ons у `null`/`[]` (жоден дефолт не ставимо).
  - Прибираємо `QUICK_START_MODES`, `STARTER_STYLES` з логіки (поле starter_style в state = "").
  - Запускаємо waterfall: `config` стає `is-active` (або одразу `zones`, якщо product не має fits).

## 5. Крок 3: Config (тільки для hoodie)

- Три блоки: Посадка (регуляр / оверсайз), Тканина (залежить від fit), Колір.
- Рівень 0 (порожньо): stage показує сіру «mockup»-маску.
- Перехід далі тільки після валідного вибору fit (якщо fits є), fabric (якщо є для цього fit), color.

## 6. Крок 4: Зони + Преміум-деталі

- Чіп-ряд зон (`front/back/sleeve/custom` — з `product.zones`). Мульти-select. Старт з нуля.
- Якщо обрано `custom` → показуємо textarea «опишіть нестандартну зону».
- Блок `Преміум-деталі` виключно для hoodie:
  - Картка `Люверси зі шнурками (+300 грн)` з SVG-іконкою (еyelets + drawstrings). Одна опція на пункт 1.4.
  - На кнопці напис `+300 грн` завжди видимий.
  - Backend: новий single add-on `lacing` з `delta = 300`. Старі `inside_label`, `hem_tag`, `grommets` видаляю зі списку, але у sanitizer лишаю fallback на `lacing` для старих драфтів.

## 7. Крок 5: Макет

- Три чіп-кнопки артворк-послуг з ціною inline:
  - `Готовий файл (0 грн)` — без знаку «+» для безкоштовної.
  - `Потрібно доопрацювати (+300 грн)`.
  - `Потрібен дизайн (+500 грн)`.
- Ціни зчитуються з `data-price-modifier` атрибутів (HTML → JS). JS більше не хардкодить.
- Блок Per-zone upload:
  - Для кожної зони з `state.zones.selected[]` рендеримо окрему dropzone `[ Макет для {ZoneLabel} ]`.
  - Drop/Click обробляється уніфіковано. Файли живуть у `state.zones[zone].files[]`.
  - Бекенд: формуємо `FormData` з іменами `zone_{key}_files` → view читає ці ключі й перетворює у стандартний `files` з `placement_specs_json`, щоб `CustomPrintLeadForm.save()` позначав `placement_zone`.
- Триадж (опційне поле) лишаю як «запис у лід», але UI не блокує: при `ready` робимо `triage_status="print-ready"` автоматично після аплоаду; при інших — `needs-review`.
- Textarea «Бриф/задача» — єдина на всю заявку (оскільки бот зараз так споживає).

## 8. Крок 6: Кількість + Smart Sizing

- Поле `quantity` (number) — без дефолта (`null`). Поки не введено, наступні кроки — pending.
- Якщо `quantity === 1`: відображаємо ряд з 6 чіпів [XS S M L XL 2XL]. Вибір одного → передається як `sizes_note = "XS"` і `size_mode = "single"`.
- Якщо `quantity > 1`: відкривається матриця розмірів:
  - Для кожного з XS, S, M, L, XL, 2XL показуємо input-number. Сума має зійтися з `quantity` (live-перевірка). Якщо не співпадає → warning-плашка, кнопка далі блокується.
  - Кнопка «уточнити з менеджером» → `size_mode = "manager"`, матриця ховається, `sizes_note` стає порожнім з fallback-повідомленням «розміри узгоджуємо після макета».
- При `state.mode === "brand"` відразу показуємо підказку B2B: `Кожні 5 шт = -10 грн/од. Поточна знижка: -{current}`.

## 9. Крок 7: Подарункова послуга (Gift Service +100)

- Новий крок (не toggle на `quantity`!). Одна картка-перемикач:
  - Верх: `+100 грн` чітко.
  - Текст: «Ми упакуємо, додамо листівку і заховаємо ціну. Бонус — унікальний промокод -10% на наступні покупки».
  - При активації розкривається `<textarea>` з підказкою «Введіть текст побажання. Або залиште поле порожнім — ми покладемо пусту листівку для вашого почерку».
  - Значення зберігається у `state.addons.gift_text`.
- Кнопка `Пропустити` на крок далі (гіфт опційний).

## 10. Крок 8: Контакт + Фінал (Dual Action)

- Ім’я, канал зв’язку, контакт.
- B2B only: поле `Бренд/Instagram` (обов’язкове). B2C — ховаємо.
- `cp-final-actions`:
  - Primary: `🛒 Додати в кошик` (якщо ціна прораховується, тобто `estimate_required === false`). Якщо `estimate_required` — кнопка вимикається з поясненням «Ціна потребує ручного прорахунку. Надішліть менеджеру, і ми повернемося з фінальним рахунком».
  - Secondary: `💬 Надіслати менеджеру на узгодження` — завжди активна.
- Обидві кнопки мають індикатор ціни (subtitle): `≈ {final_total} грн` / `Узгодимо з менеджером`.

---

## 11. Сase for new pricing config

`custom_print_config.py` змінюю так:

- `ARTWORK_SERVICES` набуває `price_delta`:
  ```python
  ARTWORK_SERVICES = [
      {"value": "ready",  "label": "Готовий файл",            "price_delta": 0,   "hint": "Ваш макет готовий до друку."},
      {"value": "adjust", "label": "Потрібно доопрацювати",   "price_delta": 300, "hint": "Причистимо, адаптуємо, підготуємо."},
      {"value": "design", "label": "Потрібен дизайн",         "price_delta": 500, "hint": "Зробимо макет з нуля за вашим брифом."},
  ]
  ```
- Hoodie add-ons стає єдиний `lacing` з ціною 300:
  ```python
  "add_ons": [
      {"value": "lacing", "label": "Люверси зі шнурками", "price_delta": 300,
       "hint": "Преміум-апгрейд з унікальним шнурком.", "icon": "lacing"},
  ]
  ```
- Нові конфіги:
  ```python
  GIFT_SERVICE = {"price": 100, "bonus_promo": "GIFT10"}
  B2B_TIER_STEP = {"unit_step": 5, "discount_per_unit": 10}
  SIZE_GRID = ["XS", "S", "M", "L", "XL", "2XL"]
  ```
- Прибираю primary використання `QUICK_START_MODES` / `STARTER_STYLES` у `build_custom_print_config` (залишаю тільки для сумісності з існуючими лідами, UI їх не показує).

## 12. Бекенд: «додати в кошик» (новий endpoint)

Рішення: не створювати реальний Django `Product` для кожного кастому. Замість цього — **session-based custom cart** у сесії.

- Новий endpoint `POST /custom-print/add-to-cart/` (`storefront/views/static_pages.py::custom_print_add_to_cart`).
  - Приймає JSON снапшот + FormData з файлами (інша mime-підрозділка). Для простоти: JSON → створюємо `CustomPrintLead` як «pending-cart», приклеюємо аплоади з base64 або робимо multipart fetch. У V2 — multipart (повторюємо buildFormData, але з `submission_type=cart`).
  - Ліди зберігаються з `exit_step="cart_pending"`, `status="cart"`.
  - У сесії `request.session["custom_print_cart"]` — список `{"lead_id": 123, "label": ..., "total": ..., "qty": ..., "thumbnail": ...}`.
  - Telegram: шлемо окремий шаблон «Клієнт хоче оплатити онлайн: #LEAD-123». Менеджер може створити реальний товар у адмінці або надіслати інвойс.
- `view_cart()` розширюється: читає стандартний dict `cart` + додає custom items з `session["custom_print_cart"]`. Custom items не мають `product_id`, мають `is_custom=True`.
- `cart.html` додає conditional блок для кастом-позицій (окрема секція з кнопкою «Редагувати на конфігураторі»).
- Checkout — не інтегрую у V2 (маркуємо повідомленням «менеджер надішле вам рахунок протягом 15 хв»). Це Phase 2.
- `remove_from_cart` приймає параметр `custom=true` і видаляє з session list.

## 13. Per-zone файли на бекенді

Існуюча модель вже підтримує:
- `CustomPrintLeadForm` зчитує `placement_specs_json` і при `save()` проставляє `CustomPrintLeadAttachment.placement_zone` для кожного файлу у порядку, у якому вони йдуть у `files[]`.
- JS у V2:
  ```js
  const formData = new FormData();
  const placementSpecs = [];
  Object.entries(state.zones).forEach(([zone, data]) => {
    if (!data.selected) return;
    data.files.forEach((file, i) => {
      formData.append("files", file, file.name);
      placementSpecs.push({
        zone,
        label: zoneLabels[zone],
        variant: "standard",
        is_free: placementSpecs.length === 0,
        format: "standard",
        size: "standard",
        file_index: placementSpecs.length,
        attachment_role: "design",
      });
    });
  });
  formData.append("placement_specs_json", JSON.stringify(placementSpecs));
  ```
- Telegram-нотифікація вже групує attachments by zone (`custom_print_notifications.py`). Нічого не міняю.

## 14. Карта файлів до зміни

| Файл | Дія |
|------|-----|
| `storefront/custom_print_config.py` | оновити `ARTWORK_SERVICES` з цінами, спростити add_ons до `lacing`, додати `GIFT_SERVICE` / `B2B_TIER_STEP` / `SIZE_GRID`, лишити старі константи для back-compat |
| `storefront/forms.py` | додати очікування поля `gift_text`, `gift_enabled`, `size_breakdown` (JSON), `submission_type` (`lead` / `cart`) |
| `storefront/views/static_pages.py` | новий `custom_print_add_to_cart`; `custom_print_lead` маркує `exit_step="submitted"` |
| `storefront/urls.py` | додати `path('custom-print/add-to-cart/', views.custom_print_add_to_cart, name='custom_print_add_to_cart')` |
| `storefront/views/cart.py` | `view_cart()` мердж кастом-позицій з сесії; `remove_from_cart` — custom branch |
| `storefront/views/utils.py` | `calculate_cart_total` — враховує кастом |
| `twocomms_django_theme/templates/pages/custom_print.html` | повний ребілд: waterfall, stage receipt, inline prices, per-zone dropzones, dual action |
| `twocomms_django_theme/static/js/custom-print-configurator.js` | повний ребілд: CONFIG_STATE, waterfall render, pricing з data-атрибутів, per-zone uploads, B2B live calc, dual submit |
| `twocomms_django_theme/static/css/custom-print-configurator.css` | додати `.cp-step` waterfall states, `.cp-stage-receipt`, `.cp-size-grid`, `.cp-size-matrix`, `.cp-addon-card`, `.cp-dropzone`, `.cp-final-actions`; прибрати `.cp-capsule`, `.cp-mobile-bar`, `.cp-build-strip` |
| `twocomms_django_theme/templates/pages/cart.html` | conditional відрендер `custom_items` |
| `storefront/custom_print_notifications.py` | опційно — новий branch для «cart_pending» повідомлень |

## 15. Поступовість зарту

1. Backend config + forms (без ламання існуючих драфтів).
2. Нова розмітка template + CSS.
3. Повний рерайт JS (CONFIG_STATE) з початковим null-станом.
4. Новий endpoint + session cart.
5. Cart template.
6. Локальна перевірка `python manage.py check`.
7. Git commit.
8. Deploy через SSH.

---

## 16. Acceptance Criteria (ручний чеклист)

- [ ] На завантаженні нічого не обрано. Жодна картка не підсвічена.
- [ ] Нижній «Попередня вартість» зник. Замість нього — інтегрований блок у sceni.
- [ ] Кроки розкриваються одразу під попереднім (waterfall), старі — згортаються у рядок з edit-посиланням.
- [ ] Hoodie показує лише «Люверси зі шнурками (+300 грн)» з SVG.
- [ ] Артворк-кнопки показують ціну inline.
- [ ] Per-zone dropzones рендеряться відповідно до обраних зон.
- [ ] qty=1 → чіп-ряд розмірів; qty>1 → матриця з перевіркою суми.
- [ ] Gift service активує textarea + додає +100 грн у чек + повідомляє про промокод -10%.
- [ ] B2C не бачить поля «Бренд».
- [ ] B2B має живий калькулятор (-10 грн кожні 5 шт).
- [ ] На фіналі дві кнопки: «Додати в кошик» (сесія) та «Надіслати менеджеру» (Telegram).
- [ ] Telegram повідомлення приходять з файлами, підписаними зонами.
- [ ] Django `check` без помилок.
