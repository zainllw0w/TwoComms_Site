---
inclusion: fileMatch
fileMatchPattern: '**/{management.css,management/templates/**/*.html}'
---

# Management-оболонка: інваріант скролу (профілактика «не доскролити низ»)

## Корінь історичного бага

Раніше оболонка рахувала висоту робочої області через
`calc(100vh - var(--shell-header-offset))` з magic-number висоти хедера
(76px), тоді як реальний хедер = 113px. При `body{overflow:hidden}` низ
контенту (~37px) обрізався і був недосяжний. Кожна нова сторінка/блок,
що додавали висоти, «повертали» цей баг. JS-патч offset працював лише для
whitelist-сторінок (`data-mgmt-shell="1"`), тому на інших баг лишався.

## Канонічна модель (commit f793d8c6) — НЕ ламати

```
.management-body { height:100vh; display:grid; grid-template-rows:auto 1fr;
                   overflow:hidden; }            /* хедер(auto) + робоча(1fr) */
.workspace       { display:flex; min-height:0; overflow:hidden; }  /* = рядок 1fr */
.main-content    { flex:1; min-height:0; overflow:hidden; }
.content-area    { height:100%; overflow-y:auto; box-sizing:border-box; }  /* ЄДИНИЙ скрол */
@media (max-width:1080px){ .management-body{display:block;height:auto;overflow:auto} }
```

Висоту робочої області задає grid-рядок `1fr`, а не арифметика. Працює при
будь-якій висоті хедера, без whitelist, без JS. **`.content-area` — єдиний
скрол-контейнер на desktop.**

## Правила для нових management-сторінок

1. **НЕ** використовуй `height:100vh` / `min-height:100vh` /
   `height:calc(100vh - Npx)` на контенті всередині `.content-area`. Контент
   має зростати природно — скролить його `.content-area`.
2. **НЕ** додавай прямих дітей `<body>` крім `.global-header` і `.workspace`
   (інакше grid-рядки зсунуться). Модалки/тости — `position:fixed`.
3. Вкладені скрол-зони всередині сторінки допустимі, але задавай їм
   `min-height:0` у flex/grid-контейнерах, інакше вони «розпирають» батька.
4. `position:sticky` всередині `.content-area` — ок (липне в межах скролу).
   `position:fixed` низ-оверлеї не повинні перекривати останній блок.
5. Не повертай per-page band-aid `calc(100vh - <header>px)` — це і є корінь бага.

## Перевірка перед комітом

Регресійний інваріант: `management/tests_shell_scroll_invariant.py`
(перевіряє grid-оболонку + `.content-area` як єдиний скрол + мобільний
fallback + відсутність magic-number calc). Має лишатися зеленим:

```
SECRET_KEY=test_local_secret python twocomms/manage.py test \
  management.tests_shell_scroll_invariant --settings=test_settings
```
