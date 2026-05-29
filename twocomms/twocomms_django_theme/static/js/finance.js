/* TwoComms Finance — shell interactions (Block 1 scaffold).
   Бургер-меню, мобільний сайдбар і заглушки швидких дій.
   Модалки доходу/витрати/переказу під'єднуються у Блоці 3. */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var body = document.body;
        var burger = document.getElementById('fin-burger');
        var backdrop = document.getElementById('fin-sidebar-backdrop');

        // Бургер відкриває вкладки + сайдбар на мобільних.
        if (burger) {
            burger.addEventListener('click', function () {
                var open = body.classList.toggle('fin-sidebar-open');
                body.classList.toggle('fin-menu-open', open);
                burger.setAttribute('aria-expanded', open ? 'true' : 'false');
            });
        }
        if (backdrop) {
            backdrop.addEventListener('click', function () {
                body.classList.remove('fin-sidebar-open', 'fin-menu-open');
                if (burger) burger.setAttribute('aria-expanded', 'false');
            });
        }

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                body.classList.remove('fin-sidebar-open', 'fin-menu-open');
                if (burger) burger.setAttribute('aria-expanded', 'false');
            }
        });

        // Швидкі дії: справжні модалки додаються у Блоці 3.
        // Поки лишаємо хук, щоб кнопки не виглядали «мертвими».
        document.querySelectorAll('[data-fin-modal]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var kind = btn.getAttribute('data-fin-modal');
                if (window.FinanceModals && typeof window.FinanceModals.open === 'function') {
                    window.FinanceModals.open(kind);
                } else {
                    // Каркас: повідомлення-заглушка до підключення модалок.
                    console.info('[finance] modal requested:', kind);
                }
            });
        });
    });
})();
