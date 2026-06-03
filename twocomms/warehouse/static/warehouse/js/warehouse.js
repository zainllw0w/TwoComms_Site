/* Global utilities for the warehouse app. */
(function () {
    'use strict';

    function getCsrfToken() {
        if (window.__warehouse__ && window.__warehouse__.csrfToken) {
            return window.__warehouse__.csrfToken;
        }
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? match[1] : '';
    }

    function postForm(url, formData) {
        return fetch(url, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken(),
            },
            credentials: 'same-origin',
        }).then(function (response) {
            return response.json().catch(function () { return { ok: false, error: 'bad json' }; });
        });
    }

    window.WAREHOUSE = {
        getCsrfToken: getCsrfToken,
        postForm: postForm,
        flash: function (text, type) {
            const container = (function () {
                let c = document.querySelector('.wh-messages');
                if (c) return c;
                c = document.createElement('div');
                c.className = 'wh-messages';
                document.body.appendChild(c);
                return c;
            })();
            const node = document.createElement('div');
            node.className = 'wh-message wh-message--' + (type || 'success');
            node.textContent = text;
            container.appendChild(node);
            setTimeout(function () {
                node.style.opacity = '0';
                node.style.transition = 'opacity 0.3s';
                setTimeout(function () { node.remove(); }, 350);
            }, 3500);
        },
    };
})();

/* Header left drawer (burger menu) */
(function () {
    'use strict';

    function init() {
        var btn = document.getElementById('wh-burger-btn');
        var drawer = document.getElementById('wh-drawer');
        var backdrop = document.getElementById('wh-drawer-backdrop');
        if (!btn || !drawer || !backdrop) { return; }
        var closeBtn = document.getElementById('wh-drawer-close');

        function open() {
            drawer.classList.add('open');
            backdrop.classList.add('open');
            document.body.classList.add('wh-drawer-open');
            btn.setAttribute('aria-expanded', 'true');
            drawer.setAttribute('aria-hidden', 'false');
        }

        function close() {
            drawer.classList.remove('open');
            backdrop.classList.remove('open');
            document.body.classList.remove('wh-drawer-open');
            btn.setAttribute('aria-expanded', 'false');
            drawer.setAttribute('aria-hidden', 'true');
        }

        function toggle() {
            if (drawer.classList.contains('open')) { close(); } else { open(); }
        }

        btn.addEventListener('click', toggle);
        backdrop.addEventListener('click', close);
        if (closeBtn) { closeBtn.addEventListener('click', close); }
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') { close(); }
        });

        // Swipe-left to close
        var startX = null;
        drawer.addEventListener('touchstart', function (e) {
            startX = e.touches[0].clientX;
        }, { passive: true });
        drawer.addEventListener('touchmove', function (e) {
            if (startX === null) { return; }
            if (e.touches[0].clientX - startX < -50) { close(); startX = null; }
        }, { passive: true });
        drawer.addEventListener('touchend', function () { startX = null; });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
