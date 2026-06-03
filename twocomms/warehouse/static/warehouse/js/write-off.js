/* Write-off page:
   - qty steppers (+/-) clamped to [min, max]
   - print toggle (checkbox) enables/disables its controls
   - variant <select> keeps the checkbox value AND the qty input name in sync
     (so the submitted print_qty_<variant_id> matches the chosen variant).
*/
(function () {
    'use strict';

    function clamp(val, min, max) {
        if (isNaN(val)) return min;
        if (max != null && val > max) return max;
        if (min != null && val < min) return min;
        return val;
    }

    function init() {
        // --- Steppers ---
        document.querySelectorAll('[data-stepper]').forEach(function (stepper) {
            var input = stepper.querySelector('input[type="number"]');
            if (!input) return;
            stepper.querySelectorAll('[data-step]').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var step = parseInt(btn.dataset.step, 10) || 0;
                    var min = input.min !== '' ? parseInt(input.min, 10) : null;
                    var max = input.max !== '' ? parseInt(input.max, 10) : null;
                    var cur = parseInt(input.value, 10) || 0;
                    input.value = clamp(cur + step, min, max);
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                });
            });
        });

        // --- Print rows ---
        document.querySelectorAll('[data-print]').forEach(function (row) {
            var toggle = row.querySelector('[data-print-toggle]');
            var variantSel = row.querySelector('[data-print-variant]');
            var qtyInput = row.querySelector('[data-print-qty]');
            var itemId = variantSel ? variantSel.dataset.item : null;

            function syncEnabled() {
                var on = toggle && toggle.checked;
                row.classList.toggle('is-on', !!on);
                if (variantSel) variantSel.disabled = !on;
                if (qtyInput) qtyInput.disabled = !on;
            }

            // When variant changes: update checkbox value + qty input name to match.
            function syncVariant() {
                if (!variantSel) return;
                var vid = variantSel.value;
                if (toggle) toggle.value = vid;
                if (qtyInput && itemId != null) {
                    qtyInput.name = 'item_' + itemId + '_print_qty_' + vid;
                }
            }

            if (toggle) toggle.addEventListener('change', syncEnabled);
            if (variantSel) variantSel.addEventListener('change', syncVariant);

            syncVariant();
            syncEnabled();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
