/* TwoComms Finance — shell interactions (Block 1 scaffold).
   Бургер-меню, мобільний сайдбар і заглушки швидких дій.
   Модалки доходу/витрати/переказу під'єднуються у Блоці 3. */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var body = document.body;
        var burger = document.getElementById('fin-burger');
        var sidebar = document.getElementById('fin-sidebar');
        var backdrop = document.getElementById('fin-sidebar-backdrop');
        var settingsPanel = document.getElementById('fin-settings-panel');
        var settingsContent = settingsPanel ? settingsPanel.querySelector('.fin-settings-panel__content') : null;
        var SAFE_EDGE_GUARD = 20;
        var EDGE_OPEN_ZONE = 132;
        var EDGE_DRAG_THRESHOLD = 8;
        var CENTER_DRAG_THRESHOLD = 22;
        var CLOSE_DRAG_THRESHOLD = 8;
        var EDGE_AXIS_RATIO = 1.05;
        var CENTER_AXIS_RATIO = 1.15;
        var CLOSE_AXIS_RATIO = 1.05;
        var VERTICAL_CANCEL_DISTANCE = 64;
        var DRAWER_OPEN_RATIO = 0.28;
        var DRAWER_CLOSE_RATIO = 0.72;
        var DRAWER_OPEN_FLING = 0.35;
        var DRAWER_CLOSE_FLING = 0.35;
        var DRAWER_MIN_RELEASE = 44;
        var DRAWER_MIN_CLOSE = 52;
        var DRAWER_SETTLE_MS = 320;
        var drawerDrag = null;

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

        function closeSidebarDrawer() {
            setSidebarOpen(false);
        }

        function closeSettingsDrawer() {
            if (window.FinanceSettings && typeof window.FinanceSettings.close === 'function') {
                window.FinanceSettings.close();
            }
        }

        function viewportWidth() {
            return window.visualViewport ? window.visualViewport.width : window.innerWidth;
        }

        function isControlGestureTarget(target) {
            return !!(target && target.closest(
                'a, button, input, select, textarea, label, [role="button"], [contenteditable="true"]'
            ));
        }

        function isInteractiveGestureTarget(target) {
            return isControlGestureTarget(target) || !!(target && target.closest(
                '.fin-sidebar, .fin-settings-panel, .fin-modal-overlay, .fin-table-wrap, .fin-tabs'
            ));
        }

        function clamp(value, min, max) {
            return Math.min(Math.max(value, min), max);
        }

        function drawerWidth(side) {
            var width = 0;
            if (side === 'left' && sidebar) {
                width = sidebar.getBoundingClientRect().width;
            } else if (side === 'right' && settingsContent) {
                width = settingsContent.getBoundingClientRect().width;
            }
            return width || Math.min(420, viewportWidth() * 0.92);
        }

        function setDrawerProgress(side, progress, width) {
            var safeWidth = width || drawerWidth(side);
            var nextProgress = clamp(progress, 0, safeWidth);
            var ratio = safeWidth ? clamp(nextProgress / safeWidth, 0, 1) : 0;
            if (side === 'left') {
                body.style.setProperty('--fin-left-drawer-progress', nextProgress + 'px');
                body.style.setProperty('--fin-left-drawer-ratio', ratio.toFixed(3));
            } else {
                body.style.setProperty('--fin-right-drawer-progress', nextProgress + 'px');
                body.style.setProperty('--fin-right-drawer-ratio', ratio.toFixed(3));
            }
            return nextProgress;
        }

        function clearDrawerProgress(side) {
            if (!side || side === 'left') {
                body.style.removeProperty('--fin-left-drawer-progress');
                body.style.removeProperty('--fin-left-drawer-ratio');
                body.classList.remove('fin-sidebar-peeking');
            }
            if (!side || side === 'right') {
                body.style.removeProperty('--fin-right-drawer-progress');
                body.style.removeProperty('--fin-right-drawer-ratio');
                body.classList.remove('fin-settings-peeking');
            }
        }

        function hideSettingsPreview() {
            if (!settingsPanel || body.classList.contains('fin-settings-open')) return;
            window.setTimeout(function () {
                if (
                    settingsPanel &&
                    !body.classList.contains('fin-settings-open') &&
                    !body.classList.contains('fin-settings-peeking')
                ) {
                    settingsPanel.hidden = true;
                }
            }, DRAWER_SETTLE_MS);
        }

        function currentDrawerSide() {
            if (body.classList.contains('fin-sidebar-open')) return 'left';
            if (body.classList.contains('fin-settings-open')) return 'right';
            return null;
        }

        function prepareDrawerPreview(side, mode) {
            if (side === 'right' && settingsPanel) {
                settingsPanel.hidden = false;
                if (mode === 'open') settingsPanel.classList.remove('is-open');
            }
            if (side === 'left' && window.FinanceSettings && typeof window.FinanceSettings.close === 'function') {
                window.FinanceSettings.close();
            }
            body.classList.add('fin-drawer-dragging');
            body.classList.toggle('fin-sidebar-peeking', side === 'left');
            body.classList.toggle('fin-settings-peeking', side === 'right');
            return drawerWidth(side);
        }

        function releasePointerCapture() {
            if (
                drawerDrag &&
                drawerDrag.captureTarget &&
                typeof drawerDrag.captureTarget.releasePointerCapture === 'function'
            ) {
                try {
                    drawerDrag.captureTarget.releasePointerCapture(drawerDrag.pointerId);
                } catch (err) {}
            }
        }

        function resetDrawerDrag() {
            var side = drawerDrag ? drawerDrag.side : null;
            releasePointerCapture();
            drawerDrag = null;
            body.classList.remove('fin-drawer-dragging');
            clearDrawerProgress(side);
            if (side === 'right') hideSettingsPreview();
        }

        function settleDrawerRelease(side, progress, width, afterSettle) {
            setDrawerProgress(side, progress, width);
            body.classList.remove('fin-drawer-dragging');
            if (typeof afterSettle === 'function') afterSettle();
            clearDrawerProgress(side);
            if (side === 'right') hideSettingsPreview();
        }

        function startDrawerDrag(side, e, mode) {
            if (!drawerDrag || drawerDrag.active) return;
            drawerDrag.active = true;
            drawerDrag.side = side;
            drawerDrag.mode = mode || drawerDrag.mode || 'open';
            drawerDrag.width = prepareDrawerPreview(side, drawerDrag.mode);
            drawerDrag.lastX = e.clientX;
            drawerDrag.lastTime = window.performance ? performance.now() : Date.now();
            if (drawerDrag.mode === 'close') {
                setDrawerProgress(side, drawerDrag.width, drawerDrag.width);
            }

            if (e.target && typeof e.target.setPointerCapture === 'function') {
                try {
                    e.target.setPointerCapture(e.pointerId);
                    drawerDrag.captureTarget = e.target;
                } catch (err) {}
            }
        }

        function startClosingDrawerDrag(side, e) {
            startDrawerDrag(side, e, 'close');
        }

        function dragProgressFromEvent(e) {
            if (!drawerDrag || !drawerDrag.side) return 0;
            var deltaX = e.clientX - drawerDrag.startX;
            if (drawerDrag.mode === 'close') {
                var closeDistance = drawerDrag.side === 'left' ? -deltaX : deltaX;
                return drawerDrag.width - clamp(closeDistance, 0, drawerDrag.width);
            }
            if (drawerDrag.side === 'left') return clamp(deltaX, 0, drawerDrag.width);
            return clamp(-deltaX, 0, drawerDrag.width);
        }

        function candidateSideFromEdge(x, width) {
            if (x <= SAFE_EDGE_GUARD || x >= width - SAFE_EDGE_GUARD) return null;
            if (x <= EDGE_OPEN_ZONE) return 'left';
            if (x >= width - EDGE_OPEN_ZONE) return 'right';
            return null;
        }

        function onPointerDown(e) {
            var openSide = currentDrawerSide();
            if (
                !window.PointerEvent ||
                !isMobileDrawerViewport() ||
                (e.pointerType === 'mouse' && e.button !== 0) ||
                e.isPrimary === false
            ) {
                return;
            }

            if (openSide) {
                if (isControlGestureTarget(e.target)) return;
                drawerDrag = {
                    mode: 'close',
                    pointerId: e.pointerId,
                    startX: e.clientX,
                    startY: e.clientY,
                    side: openSide,
                    active: false,
                    width: drawerWidth(openSide),
                    lastX: e.clientX,
                    lastTime: window.performance ? performance.now() : Date.now(),
                    velocityX: 0,
                    captureTarget: null
                };
                return;
            }

            if (
                body.classList.contains('fin-any-drawer-open') ||
                isInteractiveGestureTarget(e.target)
            ) {
                return;
            }

            var width = viewportWidth();
            var startSide = candidateSideFromEdge(e.clientX, width);
            var fromSystemEdge = e.clientX <= SAFE_EDGE_GUARD || e.clientX >= width - SAFE_EDGE_GUARD;
            if (fromSystemEdge) return;

            drawerDrag = {
                mode: 'open',
                pointerId: e.pointerId,
                startX: e.clientX,
                startY: e.clientY,
                side: startSide,
                active: false,
                width: 0,
                lastX: e.clientX,
                lastTime: window.performance ? performance.now() : Date.now(),
                velocityX: 0,
                captureTarget: null
            };
        }

        function onPointerMove(e) {
            if (!drawerDrag || e.pointerId !== drawerDrag.pointerId) return;

            var deltaX = e.clientX - drawerDrag.startX;
            var deltaY = e.clientY - drawerDrag.startY;
            var absX = Math.abs(deltaX);
            var absY = Math.abs(deltaY);
            var now = window.performance ? performance.now() : Date.now();
            var elapsed = Math.max(now - drawerDrag.lastTime, 1);
            drawerDrag.velocityX = (e.clientX - drawerDrag.lastX) / elapsed;
            drawerDrag.lastX = e.clientX;
            drawerDrag.lastTime = now;

            if (!drawerDrag.active) {
                if (absY >= VERTICAL_CANCEL_DISTANCE && absY > absX * 1.2) {
                    resetDrawerDrag();
                    return;
                }

                if (drawerDrag.mode === 'close') {
                    if ((drawerDrag.side === 'left' && deltaX > 8) || (drawerDrag.side === 'right' && deltaX < -8)) {
                        resetDrawerDrag();
                        return;
                    }
                    if (absX >= CLOSE_DRAG_THRESHOLD && absX > absY * CLOSE_AXIS_RATIO) {
                        startClosingDrawerDrag(drawerDrag.side, e);
                    }
                } else if (drawerDrag.side) {
                    if ((drawerDrag.side === 'left' && deltaX < -8) || (drawerDrag.side === 'right' && deltaX > 8)) {
                        resetDrawerDrag();
                        return;
                    }
                    if (absX >= EDGE_DRAG_THRESHOLD && absX > absY * EDGE_AXIS_RATIO) {
                        startDrawerDrag(drawerDrag.side, e);
                    }
                } else if (absX >= CENTER_DRAG_THRESHOLD && absX > absY * CENTER_AXIS_RATIO) {
                    startDrawerDrag(deltaX > 0 ? 'left' : 'right', e);
                }
            }

            if (!drawerDrag || !drawerDrag.active) return;
            if (e.cancelable) e.preventDefault();
            setDrawerProgress(drawerDrag.side, dragProgressFromEvent(e), drawerDrag.width);
        }

        function onPointerEnd(e) {
            if (!drawerDrag || e.pointerId !== drawerDrag.pointerId) return;
            var side = drawerDrag.side;
            var mode = drawerDrag.mode || 'open';
            var progress = drawerDrag.active ? dragProgressFromEvent(e) : 0;
            var width = drawerDrag.width || drawerWidth(side);
            var velocity = drawerDrag.velocityX || 0;
            var flungOpen = side === 'left' ? velocity >= DRAWER_OPEN_FLING : velocity <= -DRAWER_OPEN_FLING;
            var flungClosed = side === 'left' ? velocity <= -DRAWER_CLOSE_FLING : velocity >= DRAWER_CLOSE_FLING;
            var hiddenDistance = width - progress;
            var shouldOpen = mode === 'open' && drawerDrag.active && (
                progress >= width * DRAWER_OPEN_RATIO ||
                (progress >= DRAWER_MIN_RELEASE && flungOpen)
            );
            var shouldClose = mode === 'close' && drawerDrag.active && (
                progress <= width * DRAWER_CLOSE_RATIO ||
                hiddenDistance >= DRAWER_MIN_CLOSE ||
                flungClosed
            );

            releasePointerCapture();
            drawerDrag = null;

            if (shouldOpen && side === 'left') {
                settleDrawerRelease(side, width, width, function () {
                    setSidebarOpen(true);
                });
            } else if (shouldOpen && side === 'right') {
                settleDrawerRelease(side, width, width, openSettingsDrawer);
            } else if (shouldClose && side === 'left') {
                settleDrawerRelease(side, 0, width, closeSidebarDrawer);
            } else if (shouldClose && side === 'right') {
                settleDrawerRelease(side, 0, width, closeSettingsDrawer);
            } else if (mode === 'close') {
                settleDrawerRelease(side, width, width);
            } else if (side === 'right') {
                settleDrawerRelease(side, 0, width);
            } else {
                settleDrawerRelease(side, 0, width);
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

        document.addEventListener('pointerdown', onPointerDown, { passive: true });
        document.addEventListener('pointermove', onPointerMove, { passive: false });
        document.addEventListener('pointerup', onPointerEnd, { passive: true });
        document.addEventListener('pointercancel', resetDrawerDrag, { passive: true });

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
