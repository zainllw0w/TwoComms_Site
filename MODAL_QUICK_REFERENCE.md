# 🚀 Быстрая Справка: Рабочее Модальное Окно для Накладных

## 📍 Где Находится

**Страница**: `/wholesale/order-form/` (Список накладных опта)
**Файлы**: 
- `wholesale_order_form.html` (строки 4085-4506)
- `wholesale.html` (строки 6667-7083)

**Кнопка**: "Відправити" → Открывает модальное окно

---

## ⚡ Как Работает (Кратко)

```
КЛИК на "Відправити"
  ↓
handleMainAction(invoiceId)
  ↓
sendToWork(invoiceId)
  ├─ Отправка на сервер (с CSRF)
  ├─ Обновление UI кнопки
  ├─ Сохранение в localStorage
  └─ openSendModal(invoiceId)
      ├─ Создание popup элемента
      ├─ Создание backdrop элемента
      ├─ Добавление обработчиков (click, Escape)
      ├─ Добавление в DOM
      └─ Запуск анимации
```

---

## 🔑 Ключевые Элементы

### 1. Popup (Модальное окно)
```css
position: fixed;
top: 50%;
left: 50%;
transform: translate(-50%, -50%);
z-index: 10000;
opacity: 0 → 1 (анимация);
```

### 2. Backdrop (Затемнение)
```css
position: fixed;
top: 0;
left: 0;
width: 100vw;
height: 100vh;
background: rgba(0,0,0,.6);
z-index: 9999;
```

### 3. Функции
- `handleMainAction(id)` - точка входа
- `sendToWork(id)` - отправка на сервер
- `openSendModal(id)` - открытие модала
- `closeSendPopup()` - закрытие модала
- `getCookie(name)` - получение CSRF токена

---

## ✅ Чек-лист Отладки

Если модальное окно не работает:

1. ☐ Проверьте console.log в `openSendModal()`
2. ☐ Проверьте, создается ли popup в DOM (F12 → Elements)
3. ☐ Проверьте z-index (должен быть 10000)
4. ☐ Проверьте CSRF токен (`getCookie('csrftoken')`)
5. ☐ Проверьте ошибки в Console (F12)
6. ☐ Проверьте, что функция в глобальной области
7. ☐ Проверьте, что backdrop добавляется в DOM
8. ☐ Проверьте inline стили элементов

---

## 🎯 Частые Ошибки

| Ошибка | Причина | Решение |
|--------|---------|---------|
| Не появляется | Функция не вызывается | Добавьте `console.log()` |
| За контентом | Низкий z-index | z-index: 10000 |
| Не центрируется | Неправильный CSS | `position: fixed` + `transform` |
| Не закрывается | Нет обработчиков | Добавьте click и keydown handlers |
| 403 ошибка | Нет CSRF | Добавьте `getCookie('csrftoken')` |

---

## 💾 Готовый Код

Полный рабочий код в файле: `WORKING_MODAL_WINDOW_ANALYSIS.md` (раздел "Быстрое Решение")

**Минимальная версия:**
```javascript
function openSendModal(id) {
    // Popup
    const popup = document.createElement('div');
    popup.id = 'sendPopup';
    popup.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);z-index:10000;background:rgba(20,22,27,.95);padding:30px;border-radius:14px;opacity:0;transition:all .3s ease;';
    popup.innerHTML = `<h3>Накладна відправлена</h3><button onclick="closeSendPopup()">Закрити</button>`;
    
    // Backdrop
    const backdrop = document.createElement('div');
    backdrop.id = 'sendPopupBackdrop';
    backdrop.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,.6);z-index:9999;cursor:pointer;';
    backdrop.addEventListener('click', closeSendPopup);
    
    // Escape handler
    const escapeHandler = e => e.key === 'Escape' && closeSendPopup();
    document.addEventListener('keydown', escapeHandler);
    popup.escapeHandler = escapeHandler;
    
    // Добавление в DOM
    document.body.appendChild(backdrop);
    document.body.appendChild(popup);
    
    // Анимация
    setTimeout(() => { popup.style.opacity = '1'; popup.style.transform = 'translate(-50%, -50%) scale(1)'; }, 10);
}

function closeSendPopup() {
    const popup = document.getElementById('sendPopup');
    const backdrop = document.getElementById('sendPopupBackdrop');
    
    if (popup) {
        popup.style.opacity = '0';
        setTimeout(() => {
            if (popup.escapeHandler) document.removeEventListener('keydown', popup.escapeHandler);
            popup.remove();
        }, 300);
    }
    
    if (backdrop) backdrop.remove();
}
```

---

## 📚 Полная Документация

Смотрите `WORKING_MODAL_WINDOW_ANALYSIS.md` для:
- Детального анализа каждой функции
- Полного чек-листа отладки (10 шагов)
- Объяснения всех стилей
- Диаграммы потока выполнения
- Таблицы ошибок и решений

---

**Версия**: 1.0 | **Дата**: Октябрь 2025

