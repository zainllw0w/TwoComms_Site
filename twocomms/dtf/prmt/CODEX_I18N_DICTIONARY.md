# CODEX_I18N_DICTIONARY.md

Цель: дать Codex **единый словарь UI‑строк** для трёх языков (UA/RU/EN), чтобы:
- не было смешения языков,
- ключевые термины были стабильными по всему сайту,
- preflight/risks/CTA звучали «по‑человечески».

> Правило: если в проекте есть i18n ресурсы (JSON/YAML/TS), Codex должен:
> 1) найти соответствующие ключи/ресурсы,
> 2) заменить значения на текст из этого файла,
> 3) если ключей нет — создать их (или использовать ближайшую существующую структуру).

---

## 1) Глобальный словарь терминов (обязательно везде одинаково)

| Концепт | UA | RU | EN |
|---|---|---|---|
| FileCheckName | Перевірка файлу перед друком | Проверка файла перед печатью | File check before print |
| PreflightTermShort | Перевірка файлу | Проверка файла | File check |
| HotPeelLabel | Hot peel (гарячий відрив) | Hot peel (горячий отрыв) | Hot peel |
| HotPeelTooltip | Плівка знімається одразу після преса — швидше у роботі. | Плёнка снимается сразу после пресса — быстрее в работе. | Remove immediately after pressing — faster workflow. |
| Layout60Term | Макет 60 см (ганг‑лист) | Макет 60 см (ганг‑лист) | 60 cm layout (gang sheet) |
| Layout60Tooltip | Файл шириною 60 см із розкладеними дизайнами. | Файл шириной 60 см с размещёнными дизайнами. | A 60 cm wide file with multiple designs placed. |
| CutoffHook | Підтвердили до 12:00 — відправка сьогодні | Подтвердили до 12:00 — отправка сегодня | Approved by 12:00 — ship today |
| Support247 | Працюємо 24/7 | Работаем 24/7 | 24/7 support |
| Reply10Min | Відповідаємо до 10 хв | Отвечаем до 10 минут | Reply within ~10 minutes |

---

## 2) CTA (кнопки/ссылки)

| Key | UA | RU | EN |
|---|---|---|---|
| CTA_CalcPrice | Розрахувати вартість | Рассчитать стоимость | Calculate price |
| CTA_SendForCheck | Надіслати на перевірку й розрахунок | Отправить на проверку и расчет | Send for check & quote |
| CTA_UploadLayout | Завантажити макет 60 см | Загрузить макет 60 см | Upload 60 cm layout |
| CTA_GetSample | Отримати безкоштовний зразок A4 | Получить бесплатный образец A4 | Get a free A4 sample |
| CTA_NeedHelpArtwork | Потрібна допомога з макетом | Нужна помощь с макетом | Need help with artwork |
| CTA_ViewPricing | Подивитися прайс | Посмотреть прайс | View pricing |
| CTA_ViewTemplates | Завантажити шаблони | Скачать шаблоны | Download templates |
| CTA_ViewRequirements | Вимоги до макетів | Требования к макетам | Artwork requirements |
| CTA_OpenFAQ | Всі питання та відповіді | Все вопросы и ответы | See all FAQs |
| CTA_OpenGallery | Відкрити галерею | Открыть галерею | Open gallery |
| CTA_ContactTelegram | Написати в Telegram | Написать в Telegram | Message on Telegram |
| CTA_CallPhone | Зателефонувати | Позвонить | Call |

---

## 3) Шапка/футер/контакты

| Key | UA | RU | EN |
|---|---|---|---|
| Label_Phone | Телефон | Телефон | Phone |
| Label_Telegram | Telegram | Telegram | Telegram |
| Label_WorkHours | Графік роботи | График работы | Working hours |
| Value_WorkHours | 24/7 | 24/7 | 24/7 |
| Label_SLA | Час відповіді | Время ответа | Response time |
| Value_SLA | До 10 хвилин | До 10 минут | ~10 minutes |
| Label_Address | Адреса | Адрес | Address |
| Value_Address | (додайте місто/адресу, якщо публічно) | (добавьте город/адрес, если публично) | (add city/address if public) |

---

## 4) Preflight / Risks UI (статусы, подсказки, ошибки)

### 4.1 Статусы проверки

| Key | UA | RU | EN |
|---|---|---|---|
| Check_OK | Все добре | Всё ок | All good |
| Check_INFO | Є рекомендація | Есть рекомендация | Recommendation |
| Check_WARN | Потрібна увага | Нужно внимание | Needs attention |
| Check_FAIL | Потрібна правка | Нужна правка | Fix required |

### 4.2 Заголовки и пояснения блока

| Key | UA | RU | EN |
|---|---|---|---|
| Check_BlockTitle | Перевірка файлу перед друком | Проверка файла перед печатью | File check before print |
| Check_BlockSubtitle | Перевіряємо критичні речі, щоб уникнути браку. Якщо є ризик — покажемо й попросимо підтвердити. | Проверяем критичные вещи, чтобы избежать брака. Если есть риск — покажем и попросим подтвердить. | We check critical issues to prevent misprints. If there’s a risk, we’ll show it and ask for approval. |

### 4.3 Типовые тултипы

| Key | UA | RU | EN |
|---|---|---|---|
| Tip_DPI | Рекомендовано ~300 DPI у фінальному розмірі. Нижче може бути «мило/пікселі». | Рекомендуем ~300 DPI в финальном размере. Ниже может быть «мыло/пиксели». | ~300 DPI at final size is recommended. Lower may look blurry/pixelated. |
| Tip_Transparency | Прозорий фон потрібен, щоб не надрукувати «квадрат» навколо дизайну. | Прозрачный фон нужен, чтобы не напечатать «квадрат» вокруг дизайна. | Transparent background prevents unwanted “box” around artwork. |
| Tip_ThinLines | Дуже тонкі лінії й дрібний текст можуть втратитися при переносі. Краще трохи потовстити. | Слишком тонкие линии и мелкий текст могут потеряться при переносе. Лучше немного утолстить. | Very thin lines & tiny text may not hold during transfer. Slightly thicken if possible. |
| Tip_SafeArea | Тримайте важливі елементи всередині safe‑area шаблону, щоб край не «зрізало». | Держите важные элементы в safe‑area шаблона, чтобы край не «срезало». | Keep key elements inside the safe area to avoid edge issues. |

### 4.4 Сообщения результатов

| Key | UA | RU | EN |
|---|---|---|---|
| Msg_OK | Файл виглядає добре. Можемо запускати у друк після вашого підтвердження замовлення. | Файл выглядит хорошо. Можем запускать в печать после подтверждения заказа. | File looks good. Ready to print once you confirm the order. |
| Msg_INFO | Можна друкувати, але є рекомендація для кращого результату: {tip}. | Печатать можно, но есть рекомендация для лучшего результата: {tip}. | Printable, but we recommend: {tip}. |
| Msg_WARN | Є ризик: {issue}. Рекомендуємо правку. Якщо друкувати «як є», можливий результат: {outcome}. | Есть риск: {issue}. Рекомендуем правку. Если печатать «как есть», возможен результат: {outcome}. | Risk detected: {issue}. We recommend fixing it. If printed as-is: {outcome}. |
| Msg_FAIL | У такому вигляді файл не можна друкувати: {reason}. Завантажте виправлену версію або напишіть нам — підкажемо. | В таком виде файл нельзя печатать: {reason}. Загрузите исправленную версию или напишите нам — подскажем. | Can’t print this file as-is: {reason}. Upload a fixed version or message us. |

### 4.5 Кнопки внутри WARN/FAIL

| Key | UA | RU | EN |
|---|---|---|---|
| Action_AskHelp | Попросити підказку | Запросить подсказку | Ask for help |
| Action_UploadFixed | Завантажити виправлений файл | Загрузить исправленный файл | Upload fixed file |
| Action_PrintAsIs | Друкувати як є | Печатать как есть | Print as-is |

### 4.6 Чекбокс «печать как есть»

| Key | UA | RU | EN |
|---|---|---|---|
| AsIs_Checkbox | Я підтверджую друк «як є» і розумію можливі наслідки: втрата дрібних деталей / нечіткий текст / артефакти по краю. | Я подтверждаю печать «как есть» и понимаю возможные последствия: потеря мелких деталей / нечеткий текст / артефакты по краю. | I approve printing as-is and understand possible outcomes: loss of fine details / blurry text / edge artifacts. |
| AsIs_HelpHint | Якщо хочете — підкажемо, як виправити за 5–10 хв. | Если хотите — подскажем, как исправить за 5–10 минут. | We can suggest a quick fix (5–10 min). |

---

## 5) SEO/контент‑ярлыки (если нужны в админке)

| Key | UA | RU | EN |
|---|---|---|---|
| Admin_Title | Заголовок | Заголовок | Title |
| Admin_Slug | Slug | Slug | Slug |
| Admin_ShortDesc | Короткий опис | Короткий опис | Short description |
| Admin_PublishDate | Дата публікації | Дата публикации | Publish date |
| Admin_Status | Статус | Статус | Status |
| Admin_Published | Опубліковано | Опубликовано | Published |
| Admin_Draft | Чернетка | Черновик | Draft |
| Admin_SEOTitle | SEO Title | SEO Title | SEO Title |
| Admin_SEOKeywords | SEO keywords | SEO keywords | SEO keywords |
| Admin_SEODescription | SEO Description | SEO Description | SEO Description |

---

## 6) Примечания по внедрению

1) Если проект использует `?lang=ru` / `?lang=en`, нужно убедиться, что **все строки** берутся из правильного словаря для выбранного языка.
2) Если проект использует server-side templates — заменить строки в шаблонах и не оставить «хардкод».
3) Если есть HTMX/динамические вставки — обеспечить повторную инициализацию подсказок/tooltip после подгрузки.

