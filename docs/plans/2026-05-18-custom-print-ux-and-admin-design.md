# Custom Print: UX поліпшення + інформативність уведомлень адміна

Дата: 2026-05-18
Автор: Kiro

## Контекст

Кастомний принт-конфігуратор має дві проблемні зони:

1. **UX вибору режимів та зон** — недостатньо очевидно що:
   - можна вибрати **кілька** зон друку одночасно;
   - для режимів `ready` (готовий файл) і `adjust` (потрібно допрацювати) файл **обовʼязковий на кожну вибрану зону**;
2. **Інформативність уведомлень адміна (Telegram + админ-панель)** — колір та тип тканини виводяться як «сирі слаги» (`black`, `premium`) замість читабельних ярликів («Чорний», «Преміум»).

Додатково:
- Мобільний UX — немає sticky-bar з ціною/CTA внизу (CSS є, але не задіяний в HTML/JS);
- Переходи між кроками — частково готові, але можна посилити.

## Архітектура поточної системи (ключові точки)

```
┌──────────────────── FRONTEND ────────────────────┐
│  templates/pages/custom_print.html               │
│  static/js/custom-print-configurator.js          │
│   ↳ STATE.print.zones[]   (масив вибраних зон)   │
│   ↳ filesByPlacement Map  (per-zone файли)       │
│   ↳ getArtworkValidationIssues()  (frontend val) │
│   ↳ buildActionPolicy()   (leadReady/cartReady)  │
└──────────────────────┬───────────────────────────┘
                       │ POST FormData (placements,
                       │   placement_specs_json, files…)
                       ▼
┌──────────────────── BACKEND ─────────────────────┐
│  storefront/forms.py  — CustomPrintLeadForm      │
│   ↳ require_artwork_files (зараз: False для     │
│       submission_type == "lead")                 │
│   ↳ clean(): валідація що files >= specs        │
│  storefront/custom_print_config.py               │
│   ↳ PRODUCT_MATRIX (виріб → fits → fabrics →    │
│       colors з label/hex)                        │
│   ↳ FABRIC_LABELS, FIT_LABELS                    │
│  storefront/custom_print_notifications.py        │
│   ↳ _format_product_block — формує рядок        │
│       "Виріб: Худі / Класичний / Преміум /      │
│        black"  ← СИРИЙ СЛАГ ЦВЕТА                │
│  storefront/views/admin.py +                     │
│  templates/pages/admin_panel.html — там же.     │
└──────────────────────────────────────────────────┘
```

## Завдання 1. Обовʼязковий аплоад на кожну зону для ready/adjust

### Поточна поведінка

`forms.py`:
```python
require_artwork_files = self.require_artwork_files
if require_artwork_files is None:
    require_artwork_files = submission_type != "lead"   # ← root cause
```

Тобто при `submission_type == "lead"` (натиснули «Надіслати менеджеру») — файли **не** обовʼязкові навіть для `service_kind == "ready"`. Це і є причина того що клієнт може відправити без файлу.

### Зміни

#### 1.1 Backend (`forms.py`)

- Якщо `service_kind in {"ready", "adjust"}` — `require_artwork_files = True` **завжди**, незалежно від `submission_type`.
- Зберегти послаблення тільки для `service_kind == "design"` (там файли неактуальні, є тільки brief).

```python
# Логіка (псевдокод):
if service_kind in {READY, ADJUST}:
    require_artwork_files = True
elif require_artwork_files is None:
    require_artwork_files = submission_type != "lead"
```

#### 1.2 Frontend — блокувати «Надіслати менеджеру» якщо файлів немає

`buildActionPolicy()` вже використовує `getArtworkValidationIssues()` для `cartReady`. Перенесемо цю валідацію також на `leadReady` для режимів `ready`/`adjust`.

```js
// submissionPolicy.buildFinalActionPolicy:
const artworkRequiredForLead = serviceKind === "ready" || serviceKind === "adjust";
const leadReady = baseIssues.length === 0
  && (!artworkRequiredForLead || artworkIssues.length === 0);
const leadHint = baseIssues[0]
  || (artworkRequiredForLead && artworkIssues[0])
  || "Бот відправить заявку в Telegram";
```

#### 1.3 UX підсилення dropzone

- Додати в `renderDropzones()` лічильник: «Файли для зон: 1 з 3».
- Якщо зона активна, але файлу немає — підсвітити dropzone червоним рамкою + іконка «❗», текст «Потрібен файл».
- Коли файл доданий — зелена рамка, чекмарк, ім'я файлу.

CSS-зміни в `custom-print-configurator.css`:
```css
.cp-dropzone[data-status="missing"] { border-color: #ff7a59; box-shadow: 0 0 0 1px rgba(255,122,89,0.18) inset; }
.cp-dropzone[data-status="ok"]     { border-color: #38d39f; }
.cp-dropzone-status                 { font-size: 0.78rem; ... }
```

## Завдання 2. Очевидний multi-зональний вибір

### Поточна поведінка

```html
<div class="cp-mini-chip-row cp-mini-chip-row--zones" data-zone-list></div>
```
JS додає `<button class="cp-mini-chip cp-mini-chip--zone">` — це маленькі текстові чіпси без візуальної підказки на multi-select.

### Зміни

#### 2.1 Замінити чіпси на «zone cards» з:
- іконкою (front/back/sleeve, з `static/img/configurator/ui/zone-*.svg` або inline SVG);
- назвою зони;
- коротким описом ("Класичне розміщення");
- чекбоксом-індикатором у верхньому-правому куті;
- активний state (підсвічений border + glow).

```html
<button class="cp-zone-card is-active" data-choice-value="front">
  <span class="cp-zone-card-check" aria-hidden="true">✓</span>
  <span class="cp-zone-card-icon">[svg]</span>
  <strong>Спереду</strong>
  <small>Головний принт у класичному форматі</small>
</button>
```

#### 2.2 Підказка над списком

```html
<div class="cp-zone-hint">
  <span class="cp-zone-hint-icon">✦</span>
  <span>Можна обрати <strong>кілька зон</strong> — друк на додаткових зонах розраховується окремо.</span>
</div>
```

#### 2.3 Адаптивність
- Десктоп: 3 колонки (`grid-template-columns: repeat(3, 1fr)`)
- Планшет: 2 колонки
- Мобільний: 1 колонка з горизонтальним скролом або 2 колонки в стек

## Завдання 3. Мобільний UX: sticky bottom bar з ціною

### Поточна поведінка

CSS вже містить `.cp-mobile-bar { display: grid }` і `.cp-capsule { position: fixed... }`, але в HTML цих елементів немає, тобто на мобільному немає sticky-CTA. Тільки sticky прогрес-strip.

### Зміни

#### 3.1 Додати в `custom_print.html` sticky bottom bar (видимий тільки на мобільному):

```html
<div class="cp-mobile-bottom-bar" data-mobile-bottom-bar hidden>
  <div class="cp-mobile-bottom-bar-info">
    <small>Ціна</small>
    <strong data-mobile-bottom-bar-total>—</strong>
  </div>
  <button type="button" class="cp-mobile-bottom-bar-action" data-mobile-bottom-bar-next>
    <span data-mobile-bottom-bar-action-label>Далі</span>
    <svg>...</svg>
  </button>
</div>
```

#### 3.2 JS логіка
- Bar показується після того як обрано виріб (STAGE_VISIBLE_AFTER).
- Текст кнопки залежить від поточного шага: «Далі до виробу», «Далі до зон», … «Надіслати менеджеру» на останньому.
- Total оновлюється з `renderReceipt()`.
- При кліку — той самий handler що `data-step-next` для поточного шага, або submit на останньому.

#### 3.3 CSS
```css
@media (max-width: 720px) {
  .cp-mobile-bottom-bar { 
    position: fixed; bottom: 0; left: 0; right: 0;
    z-index: 50;
    background: linear-gradient(180deg, rgba(15,12,10,0.92), rgba(8,6,5,0.98));
    backdrop-filter: blur(18px);
    padding: env(safe-area-inset-bottom, 0.6rem) 1rem 0.7rem;
    display: grid; grid-template-columns: 1fr auto;
    gap: 0.8rem; align-items: center;
    border-top: 1px solid rgba(255,255,255,0.08);
  }
  .cp-page { padding-bottom: 7rem; } /* місце під bar */
}
@media (min-width: 721px) {
  .cp-mobile-bottom-bar { display: none; }
}
```

## Завдання 4. Інформативність для адміна

### Поточна поведінка

`custom_print_notifications.py` `_format_product_block`:
```python
parts.append(escape(lead.color_choice))   # ← "black", "graphite", "thermo_pink"
```

`admin_panel.html`:
```html
<strong>{{ custom_print_selected_lead.fabric|default:"—" }}</strong>     <!-- "premium" -->
<strong>{{ custom_print_selected_lead.color_choice|default:"—" }}</strong> <!-- "black" -->
```

### Зміни

#### 4.1 Створити сервісну функцію `resolve_lead_display_labels(lead)` 

Місце: `storefront/custom_print_config.py` (приєднується до уже існуючих лейблів).

```python
def resolve_color_label(product_type: str, color_value: str, fabric_value: str = "") -> dict:
    """Повертає {label, hex} для color_choice з PRODUCT_MATRIX.
    
    Якщо це термо-варіант (футболка oversize + thermo) — шукає в
    fabrics[fit][thermo].colors. Інакше — у головному products.colors.
    """
    if not color_value:
        return {"label": "", "hex": ""}
    matrix = PRODUCT_MATRIX.get(product_type) or {}
    
    # 1) перевіряємо термо-кольори (тільки для футболки)
    if product_type == "tshirt" and fabric_value == "thermo":
        for fit_key, fabric_list in (matrix.get("fabrics") or {}).items():
            for fabric_def in fabric_list:
                if fabric_def.get("value") == "thermo":
                    for c in (fabric_def.get("colors") or []):
                        if c["value"] == color_value:
                            return {"label": str(c.get("label") or color_value), "hex": c.get("hex") or ""}
    
    # 2) звичайні кольори
    for c in matrix.get("colors") or []:
        if c["value"] == color_value:
            return {"label": str(c.get("label") or color_value), "hex": c.get("hex") or ""}
    
    return {"label": color_value, "hex": ""}


def resolve_fabric_label(product_type: str, fit_value: str, fabric_value: str) -> str:
    """Повертає 'Преміум' для 'premium' з PRODUCT_MATRIX[type].fabrics[fit][...].label."""
    if not fabric_value:
        return ""
    matrix = PRODUCT_MATRIX.get(product_type) or {}
    fabrics = (matrix.get("fabrics") or {}).get(fit_value or "") or []
    for fabric_def in fabrics:
        if fabric_def.get("value") == fabric_value:
            return str(fabric_def.get("label") or FABRIC_LABELS.get(fabric_value, fabric_value))
    return FABRIC_LABELS.get(fabric_value, fabric_value)


def resolve_fit_label(product_type: str, fit_value: str) -> str:
    """Повертає 'Класичний' для 'regular' з PRODUCT_MATRIX[type].fits[i].label."""
    if not fit_value:
        return ""
    matrix = PRODUCT_MATRIX.get(product_type) or {}
    for f in matrix.get("fits") or []:
        if f.get("value") == fit_value:
            return str(f.get("label") or FIT_LABELS.get(fit_value, fit_value))
    return FIT_LABELS.get(fit_value, fit_value)
```

#### 4.2 Використання у `_format_product_block`:

```python
def _format_product_block(lead) -> list[str]:
    parts = [escape(lead.get_product_type_display())]
    
    fit_label = resolve_fit_label(lead.product_type, lead.fit)
    if fit_label:
        parts.append(escape(fit_label))
    
    fabric_label = resolve_fabric_label(lead.product_type, lead.fit, lead.fabric)
    if fabric_label:
        parts.append(escape(fabric_label))
    
    color_info = resolve_color_label(lead.product_type, lead.color_choice, lead.fabric)
    if color_info["label"]:
        color_text = color_info["label"]
        if color_info["hex"]:
            color_text += f" ({color_info['hex']})"
        parts.append(escape(color_text))
    
    rows = [f"• <b>Виріб:</b> {' / '.join(parts)}"]
    ...
```

#### 4.3 Окремий highlighted-рядок для тканини у Telegram

Якщо вибрано преміум — додаємо окремий рядок з акцентом:

```python
if fabric_value == "premium":
    rows.append("• <b>Тип тканини:</b> 💎 <b>Преміум</b> (320 г/м², акуратна обробка)")
elif fabric_value == "thermo":
    rows.append("• <b>Тип тканини:</b> 🌡 <b>Термо</b> (реагує на тепло)")
elif fabric_value == "standard" or fabric_value == "":
    rows.append("• <b>Тип тканини:</b> 📦 Стандарт")
```

#### 4.4 Те саме для `_snapshot_product_label` (використовується в media-group caption)

Замінити `details.append(color)` на `details.append(resolve_color_label(...).label)`.

#### 4.5 Адмін-панель (`admin_panel.html`)

Шукаємо рядки 2767-2769:

```html
<div class="custom-print-kv"><small>Fit</small><strong>{{ custom_print_selected_lead.fit|default:"—" }}</strong></div>
<div class="custom-print-kv"><small>Тканина</small><strong>{{ custom_print_selected_lead.fabric|default:"—" }}</strong></div>
<div class="custom-print-kv"><small>Колір</small><strong>{{ custom_print_selected_lead.color_choice|default:"—" }}</strong></div>
```

Передаємо в context (з `_build_custom_print_orders_context`) обчислені рядки:

```python
# у views/admin.py:
from storefront.custom_print_config import resolve_color_label, resolve_fabric_label, resolve_fit_label

if selected_lead:
    selected_lead.fit_display      = resolve_fit_label(selected_lead.product_type, selected_lead.fit)
    selected_lead.fabric_display   = resolve_fabric_label(selected_lead.product_type, selected_lead.fit, selected_lead.fabric)
    selected_lead.color_display    = resolve_color_label(selected_lead.product_type, selected_lead.color_choice, selected_lead.fabric)
```

У шаблоні:

```html
<div class="custom-print-kv">
  <small>Fit</small>
  <strong>{{ custom_print_selected_lead.fit_display|default:custom_print_selected_lead.fit|default:"—" }}</strong>
</div>
<div class="custom-print-kv">
  <small>Тканина</small>
  <strong>
    {% if custom_print_selected_lead.fabric == "premium" %}<span class="custom-print-fabric-pill custom-print-fabric-pill--premium">💎 {{ custom_print_selected_lead.fabric_display }}</span>
    {% elif custom_print_selected_lead.fabric == "thermo" %}<span class="custom-print-fabric-pill custom-print-fabric-pill--thermo">🌡 {{ custom_print_selected_lead.fabric_display }}</span>
    {% elif custom_print_selected_lead.fabric_display %}<span class="custom-print-fabric-pill">📦 {{ custom_print_selected_lead.fabric_display }}</span>
    {% else %}—{% endif %}
  </strong>
</div>
<div class="custom-print-kv">
  <small>Колір</small>
  <strong>
    {% if custom_print_selected_lead.color_display.label %}
      {% if custom_print_selected_lead.color_display.hex %}
        <span class="custom-print-color-swatch" style="background: {{ custom_print_selected_lead.color_display.hex }};"></span>
      {% endif %}
      {{ custom_print_selected_lead.color_display.label }}
    {% else %}—{% endif %}
  </strong>
</div>
```

CSS-доповнення в `admin_panel.html` (inline або в окремому файлі):
```css
.custom-print-fabric-pill { padding: 0.18rem 0.5rem; border-radius: 999px; font-size: 0.82rem; background: rgba(255,255,255,0.08); }
.custom-print-fabric-pill--premium { background: rgba(215,164,80,0.18); color: #f4d6a0; }
.custom-print-fabric-pill--thermo { background: rgba(231,139,167,0.18); color: #f5c4d4; }
.custom-print-color-swatch { display: inline-block; width: 1rem; height: 1rem; border-radius: 50%; border: 1px solid rgba(255,255,255,0.2); margin-right: 0.4rem; vertical-align: middle; }
```

## Тестування

1. **Backend контракт** (новий тест у `tests/test_custom_print_config_contract.py`):
   ```python
   def test_resolve_color_label_returns_label_and_hex():
       result = resolve_color_label("hoodie", "black", "")
       assert result == {"label": "Чорний", "hex": "#151515"}
   
   def test_resolve_color_label_for_thermo_tshirt():
       result = resolve_color_label("tshirt", "thermo_green", "thermo")
       assert result["label"] == "Зелений (Термо)"
   
   def test_resolve_fabric_label_premium_hoodie():
       assert resolve_fabric_label("hoodie", "regular", "premium") == "Преміум"
   ```

2. **Forms validation** (новий тест у `tests/test_custom_print_form_logic.py`):
   ```python
   def test_lead_submission_requires_files_for_ready_service():
       form = CustomPrintLeadForm(data={
           "service_kind": "ready",
           "product_type": "hoodie",
           "placements": ["front", "back"],
           "config_draft_json": json.dumps({"submission_type": "lead", ...}),
           # БЕЗ files
       })
       form.is_valid()
       assert "files" in form.errors
   ```

3. **Notification message** (`tests/test_custom_print_notifications_unit.py`):
   ```python
   def test_message_includes_resolved_color_label():
       lead = make_lead(product_type="hoodie", color_choice="graphite", fabric="premium", fit="regular")
       message = _build_message(lead)
       assert "Графіт" in message
       assert "Преміум" in message
       assert "graphite" not in message  # сирий слаг не повинен витекти
   ```

## План впровадження

1. ✅ Створити цей design.md
2. Backend: додати `resolve_color_label`, `resolve_fabric_label`, `resolve_fit_label` в `custom_print_config.py`
3. Backend: оновити `forms.py`, щоб ready/adjust завжди потребували файли
4. Backend: оновити `custom_print_notifications.py` — використати нові резолвери
5. Backend: оновити `views/admin.py` — додати display-fields у контексті
6. Frontend HTML: оновити `custom_print.html` — нова структура zone cards, мобільний bar
7. Frontend JS: оновити `custom-print-configurator.js` — нова рендер-функція zone cards, мобільний bar, валідація для submitLead
8. Frontend CSS: нові стилі в `custom-print-configurator.css` (та `styles.css`/`styles.purged.css` якщо ассети підключаються там)
9. Адмін-панель шаблон: оновити `admin_panel.html` — color swatch, fabric pill
10. Тести: додати нові тести для резолверів та валідації
11. `python manage.py test storefront.tests.test_custom_print_*`
12. `git commit && git push && deploy`

## Безпека / зворотна сумісність

- Існуючі lead-и в БД мають `color_choice="black"` (сирий слаг) — резолвер обробляє це через fallback `return color_value`.
- Існуючі lead-и без `submission_type` у `config_draft_json` — поведінка не зміниться (вони вже пройшли валідацію).
- Нова поведінка валідації НЕ застосовується до старих чернеток (вони не повертаються через handleSubmitLead).
