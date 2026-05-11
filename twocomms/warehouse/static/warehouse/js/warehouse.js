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
