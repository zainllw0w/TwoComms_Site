# 🟢 FIX #9: FAQ Format — Уніфікація

> **Severity:** MINOR | **Файли:** `faq.html`, порівняння з `index.html`
> **Дефект:** UI-3 — FAQ page використовує інший формат ніж homepage FAQ

---

## СУТЬ ПРОБЛЕМИ

### Homepage FAQ (`index.html`, рядки 778-800):
```html
<div class="faq-item">
  <button type="button" class="faq-q">Формат файлу?</button>
  <div class="faq-a">PNG з прозорістю або PDF — якщо не впевнені, надішліть і підкажемо.</div>
</div>
```

### FAQ page (`faq.html`):
⚠️ Може використовувати ІНШІ CSS-класи або структуру. Перевірити:
```bash
grep -n "faq-" twocomms/dtf/templates/dtf/faq.html | head -30
```

---

## ЩО ЗРОБИТИ

### Крок 1: Дослідити faq.html

Відкрити `twocomms/dtf/templates/dtf/faq.html` і перевірити:
1. Які CSS класи використовуються для FAQ items
2. Чи є `<button>` для accordion toggle
3. Чи використовується JavaScript для expand/collapse

### Крок 2: Привести до єдиного формату

**Канонічний формат** (з homepage):
```html
<div class="faq-item">
  <button type="button" class="faq-q">ПИТАННЯ</button>
  <div class="faq-a">ВІДПОВІДЬ</div>
</div>
```

- `faq-item` — контейнер
- `faq-q` — кнопка-тригер (accordion toggle)
- `faq-a` — відповідь (прихована за замовчуванням, розкривається при кліку)
- JavaScript у `dtf.js` → `initFaq()` обробляє toggle

### Крок 3: Перевірити JavaScript

У `dtf.js` знайти `initFaq()` і перевірити що вона таргетить правильні селектори:
```javascript
// Очікувана поведінка:
document.querySelectorAll('.faq-item .faq-q').forEach(btn => {
  btn.addEventListener('click', () => {
    btn.parentElement.classList.toggle('is-open');
  });
});
```

### Крок 4: Перевірити CSS

У `animations.css` перевірити:
```css
.faq-a {
  max-height: 0;
  overflow: hidden;
  transition: max-height 300ms ease, padding 300ms ease;
}
.faq-item.is-open .faq-a {
  max-height: 400px;  /* або auto через JS */
}
```

---

## ПЕРЕВІРКА

1. Відкрити `/faq/` сторінку
2. Всі FAQ items мають accordion поведінку (клік → розкриття)
3. Зовнішній вигляд ідентичний homepage FAQ
4. `aria-expanded` правильно оновлюється
5. Анімація expand/collapse плавна
6. Перевірити на 3 мовах
