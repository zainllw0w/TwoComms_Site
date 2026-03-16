# 🟡 FIX #3: CSS Анімації Іконок — Timing + JS Тригери

> **Severity:** MAJOR | **Файли:** `icons.css`, `dtf.js`
> **Дефекти:** A-1 (неправильний timing), A-3 (відсутній JS-тригер)

---

## СУТЬ ПРОБЛЕМИ

### Дефект A-1: Неправильний Timing

| Анімація | Специфікація | Реалізація | Статус |
|----------|-------------|------------|--------|
| `soft-glow` (bulb) | Blink 200-260ms, раз на 7-9 сек | `2.4s infinite` | ❌ |
| `soft-glow` (telegram) | One-shot glow ≤400ms, без повторів | `2.8s infinite` | ❌ |
| `upload-bounce` | Bounce при тригері (upload action) | `2.6s infinite` | ❌ |
| `truck-slide` | Тригер при статусі "Відправка" | `2.9s infinite` | ❌ |

### Дефект A-3: Відсутній JS-тригер

Клас `dtf-icon-animate` додається **статично в HTML**, CSS анімації запускаються відразу при рендері. Користувач може не побачити анімацію, бо вона вже відіграла до прокрутки.

---

## ЩО ЗРОБИТИ

### Крок 1: Змінити `icons.css`

Замінити весь блок анімацій (рядки 44-75) на:

```css
/* 3. soft-glow (bulb) — НЕ через CSS animation, а через JS class toggle */
.dtf-icon-bulb.dtf-icon-blink {
  animation: bulb-blink 230ms ease-out;
}
@keyframes bulb-blink {
  0%   { filter: drop-shadow(0 0 0 transparent); opacity: 1; }
  50%  { filter: drop-shadow(0 0 8px var(--dtf-accent, #f97316)); opacity: 0.85; }
  100% { filter: drop-shadow(0 0 0 transparent); opacity: 1; }
}

/* 3b. soft-glow (telegram) — one-shot, 1 iteration */
.dtf-icon-telegram.dtf-icon-animate {
  animation: soft-glow 380ms ease-in-out 1;  /* ← ONE-SHOT, не infinite */
}
@keyframes soft-glow {
  0%   { filter: drop-shadow(0 0 0 transparent); }
  50%  { filter: drop-shadow(0 0 6px var(--dtf-accent, #3b82f6)); }
  100% { filter: drop-shadow(0 0 0 transparent); }
}

/* 4. upload-bounce — ТІЛЬКИ при тригері */
.dtf-icon-upload.dtf-icon-animate {
  animation: upload-bounce 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) 1;  /* ← ONE-SHOT */
}
@keyframes upload-bounce {
  0%, 100% { transform: translateY(0); }
  40%  { transform: translateY(-6px); }
  70%  { transform: translateY(-2px); }
}

/* 5. truck-slide — ТІЛЬКИ при тригері */
.dtf-icon-truck.dtf-icon-animate {
  animation: truck-slide 0.6s ease-out 1;  /* ← ONE-SHOT */
}
@keyframes truck-slide {
  0%   { transform: translateX(0); opacity: 1; }
  50%  { transform: translateX(6px); opacity: 0.8; }
  100% { transform: translateX(0); opacity: 1; }
}
```

### Крок 2: Видалити `dtf-icon-animate` зі статичного HTML

У **всіх шаблонах** де іконки мають клас `dtf-icon-animate` — **ВИДАЛИТИ** цей клас:

**Файли для пошуку:**
```
grep -rn "dtf-icon-animate" twocomms/dtf/templates/
```

**Замінити:**
```html
<!-- БУЛО: -->
<span class="dtf-icon dtf-icon-check dtf-icon-animate" aria-hidden="true">

<!-- СТАЛО: -->
<span class="dtf-icon dtf-icon-check" aria-hidden="true">
```

### Крок 3: Додати JS для IntersectionObserver тригерів

У `dtf.js`, додати нову функцію `initIconAnimations()`:

```javascript
function initIconAnimations() {
  // 1. One-shot reveal для ВСІХ іконок при вході у viewport
  const icons = collectTargets(document, '.dtf-icon[class*="dtf-icon-"]');
  if (!icons.length) return;
  
  if (!('IntersectionObserver' in window) || prefersReduced) {
    // Fallback: показати все без анімації
    icons.forEach(icon => icon.classList.add('dtf-icon-animate'));
    return;
  }
  
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('dtf-icon-animate');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.5 });
  
  icons.forEach(icon => observer.observe(icon));
  
  // 2. Спеціальна обробка для bulb (рідкий blink)
  initBulbBlink();
}

function initBulbBlink() {
  const bulbs = document.querySelectorAll('.dtf-icon-bulb');
  if (!bulbs.length || prefersReduced) return;
  
  const isMobile = window.matchMedia('(hover: none)').matches;
  
  bulbs.forEach(bulb => {
    if (isMobile) {
      // Mobile: один blink при вході у viewport
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            bulb.classList.add('dtf-icon-blink');
            bulb.addEventListener('animationend', () => {
              bulb.classList.remove('dtf-icon-blink');
            }, { once: true });
            observer.unobserve(bulb);
          }
        });
      }, { threshold: 0.5 });
      observer.observe(bulb);
    } else {
      // Desktop: blink раз на 7-9 сек
      const blink = () => {
        if (document.hidden) return;
        bulb.classList.add('dtf-icon-blink');
        bulb.addEventListener('animationend', () => {
          bulb.classList.remove('dtf-icon-blink');
        }, { once: true });
      };
      
      // Перший blink через 3 сек після завантаження
      setTimeout(blink, 3000);
      // Далі — раз на 7-9 сек (рандомний інтервал)
      setInterval(() => {
        blink();
      }, 7000 + Math.random() * 2000);
    }
  });
}
```

### Крок 4: Підключити у `initAll()`

У функції `initAll()` (рядок ~2631 у `dtf.js`), додати виклик:
```javascript
initIconAnimations();
```

---

## ПЕРЕВІРКА

1. При завантаженні сторінки іконки НЕ анімуються одразу
2. При скролі до іконки — вона плавно "з'являється" (check-draw, тощо)
3. Лампочка блимає рідко (раз на 7-9 сек), не постійно
4. Telegram іконка блимає ОДНОРАЗОВО
5. Upload/truck анімуються ТІЛЬКИ при відповідних діях
6. `prefers-reduced-motion: reduce` — жодної анімації
