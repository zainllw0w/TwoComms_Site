/* TwoComms Finance — shell interactions (Block 1 scaffold).
   Бургер-меню, мобільний сайдбар і заглушки швидких дій.
   Модалки доходу/витрати/переказу під'єднуються у Блоці 3. */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var body = document.body;
        var burger = document.getElementById('fin-burger');
        var backdrop = document.getElementById('fin-sidebar-backdrop');
        var EDGE_SWIPE_WIDTH = 28;
        var MIN_SWIPE_DISTANCE = 72;
        var SWIPE_AXIS_RATIO = 1.35;
        var SWIPE_CANCEL_Y = 44;
        var swipe = null;

        function isMobileDrawerViewport() {
            return window.matchMedia ? window.matchMedia('(max-width: 900px)').matches : window.innerWidth <= 900;
        }

        function setSidebarOpen(open) {
            if (open && !isMobileDrawerViewport()) return;
            if (open && window.FinanceSettings && typeof window.FinanceSettings.close === 'function') {
                window.FinanceSettings.close();
            }
            body.classList.toggle('fin-sidebar-open', open);
            body.classList.toggle('fin-menu-open', open);
            body.classList.toggle('fin-any-drawer-open', open || body.classList.contains('fin-settings-open'));
            if (burger) burger.setAttribute('aria-expanded', open ? 'true' : 'false');
        }

        function openSettingsDrawer() {
            setSidebarOpen(false);
            if (window.FinanceSettings && typeof window.FinanceSettings.open === 'function') {
                window.FinanceSettings.open();
            }
        }

        function resetSwipe() {
            swipe = null;
        }

        function onTouchStart(e) {
            if (!isMobileDrawerViewport() || !e.touches || e.touches.length !== 1) return;
            var touch = e.touches[0];
            var viewportWidth = window.visualViewport ? window.visualViewport.width : window.innerWidth;
            var side = null;

            if (touch.clientX <= EDGE_SWIPE_WIDTH) {
                side = 'left';
            } else if (touch.clientX >= viewportWidth - EDGE_SWIPE_WIDTH) {
                side = 'right';
            }
            if (!side) return;

            swipe = {
                side: side,
                startX: touch.clientX,
                startY: touch.clientY,
                cancelled: false,
                horizontal: false
            };
        }

        function onTouchMove(e) {
            if (!swipe || !e.touches || e.touches.length !== 1) return;
            var touch = e.touches[0];
            var deltaX = touch.clientX - swipe.startX;
            var deltaY = touch.clientY - swipe.startY;
            var absX = Math.abs(deltaX);
            var absY = Math.abs(deltaY);

            if (absY > SWIPE_CANCEL_Y && Math.abs(deltaX) <= Math.abs(deltaY)) {
                swipe.cancelled = true;
                resetSwipe();
                return;
            }
            if ((swipe.side === 'left' && deltaX < -8) || (swipe.side === 'right' && deltaX > 8)) {
                swipe.cancelled = true;
                resetSwipe();
                return;
            }
            if (absX > 16 && absX > absY * SWIPE_AXIS_RATIO) {
                swipe.horizontal = true;
                if (e.cancelable) e.preventDefault();
            }
        }

        function onTouchEnd(e) {
            if (!swipe || swipe.cancelled) {
                resetSwipe();
                return;
            }
            var touch = e.changedTouches && e.changedTouches[0];
            if (!touch) {
                resetSwipe();
                return;
            }
            var side = swipe.side;
            var deltaX = touch.clientX - swipe.startX;
            var deltaY = touch.clientY - swipe.startY;
            var isHorizontal = Math.abs(deltaX) >= MIN_SWIPE_DISTANCE &&
                Math.abs(deltaX) > Math.abs(deltaY) * SWIPE_AXIS_RATIO;

            resetSwipe();
            if (!isHorizontal) return;

            if (side === 'left' && deltaX > 0) {
                setSidebarOpen(true);
            } else if (side === 'right' && deltaX < 0) {
                openSettingsDrawer();
            }
        }

        window.FinanceSidebar = {
            open: function () { setSidebarOpen(true); },
            close: function () { setSidebarOpen(false); },
            isOpen: function () { return body.classList.contains('fin-sidebar-open'); }
        };

        // Бургер відкриває фінансові показники на мобільних.
        if (burger) {
            burger.addEventListener('click', function () {
                setSidebarOpen(!body.classList.contains('fin-sidebar-open'));
            });
        }
        if (backdrop) {
            backdrop.addEventListener('click', function () {
                setSidebarOpen(false);
            });
        }

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                setSidebarOpen(false);
            }
        });

        document.addEventListener('touchstart', onTouchStart, { passive: true });
        document.addEventListener('touchmove', onTouchMove, { passive: false });
        document.addEventListener('touchend', onTouchEnd, { passive: true });
        document.addEventListener('touchcancel', resetSwipe, { passive: true });

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
