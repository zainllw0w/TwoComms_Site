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

        // ---- Фільтр журналу за рахунками (зелена полоска) ----
        // Клік по рахунку у лівій панелі вмикає/вимикає його у фільтрі та веде
        // у журнал платежів із параметром ?accounts=. Нічого не обрано → усі.
        var accBtns = Array.prototype.slice.call(document.querySelectorAll('.fin-account[data-account-id]'));
        var resetBtn = document.getElementById('fin-accounts-reset');
        var hint = document.getElementById('fin-accounts-hint');

        function currentAccountSet() {
            // Джерело правди — URL журналу (?accounts=); інакше localStorage.
            var fromUrl = new URLSearchParams(window.location.search).get('accounts');
            if (fromUrl !== null) {
                return new Set(fromUrl.split(',').filter(Boolean));
            }
            try {
                return new Set(JSON.parse(localStorage.getItem('fin_selected_accounts') || '[]').map(String));
            } catch (e) { return new Set(); }
        }

        function persist(set) {
            try { localStorage.setItem('fin_selected_accounts', JSON.stringify(Array.from(set))); } catch (e) {}
        }

        function paintSelection(set) {
            accBtns.forEach(function (b) {
                b.classList.toggle('is-selected', set.has(String(b.dataset.accountId)));
            });
            var has = set.size > 0;
            if (resetBtn) resetBtn.hidden = !has;
            if (hint) hint.hidden = !has;
        }

        if (accBtns.length) {
            var sel = currentAccountSet();
            // Синхронізуємо localStorage з URL, якщо ми у журналі з фільтром.
            if (new URLSearchParams(window.location.search).has('accounts')) persist(sel);
            paintSelection(sel);

            accBtns.forEach(function (b) {
                b.addEventListener('click', function () {
                    var id = String(b.dataset.accountId);
                    var s = currentAccountSet();
                    if (s.has(id)) s.delete(id); else s.add(id);
                    persist(s);
                    paintSelection(s);
                    var qs = s.size ? ('?accounts=' + Array.from(s).join(',')) : '';
                    window.location.href = '/' + qs;
                });
            });

            if (resetBtn) resetBtn.addEventListener('click', function () {
                persist(new Set());
                window.location.href = '/';
            });
        }
    });
})();
