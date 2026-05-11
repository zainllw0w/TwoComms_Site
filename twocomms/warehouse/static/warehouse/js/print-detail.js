/* Print variant quick adjust (+/-). */
(function () {
    'use strict';
    const W = window.WAREHOUSE;
    if (!W || !window.__warehouse__) return;

    function adjust(variantId, delta) {
        const fd = new FormData();
        fd.append('variant_id', variantId);
        fd.append('mode', 'delta');
        fd.append('delta', String(delta));
        return W.postForm(window.__warehouse__.urls.printAdjust, fd);
    }

    function setQty(variantId, qty) {
        const el = document.querySelector('[data-variant-qty="' + variantId + '"]');
        if (el) el.textContent = qty;
    }

    document.querySelectorAll('.print-variant-minus').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const id = btn.dataset.variantId;
            adjust(id, -1).then(function (data) {
                if (data.ok) {
                    setQty(id, data.quantity);
                    W.flash('−1', 'success');
                } else {
                    W.flash(data.error || 'Помилка', 'error');
                }
            });
        });
    });
    document.querySelectorAll('.print-variant-plus').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const id = btn.dataset.variantId;
            adjust(id, 1).then(function (data) {
                if (data.ok) {
                    setQty(id, data.quantity);
                    W.flash('+1', 'success');
                } else {
                    W.flash(data.error || 'Помилка', 'error');
                }
            });
        });
    });
})();
