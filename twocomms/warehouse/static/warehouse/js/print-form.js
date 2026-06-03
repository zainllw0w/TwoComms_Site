/* Print add/edit form:
   - segmented controls (placement, garment fit, variant color mode)
   - per-variant color picker → syncs hidden comma-joined ids
   - variant add/remove
   - product picker (search / select all / only-selected)
*/
(function () {
    'use strict';

    function init() {
        const form = document.getElementById('print-form');
        if (!form) return;

        // ---------- Generic single-choice segmented controls ----------
        // Wires data-seg="placement" / "garment_fit" segments to their hidden input.
        function wireSingleSeg(seg, hiddenId, onChange) {
            const hidden = document.getElementById(hiddenId);
            seg.addEventListener('click', function (e) {
                const btn = e.target.closest('.wh-seg__btn');
                if (!btn) return;
                seg.querySelectorAll('.wh-seg__btn').forEach(function (b) {
                    b.classList.toggle('is-active', b === btn);
                });
                if (hidden) hidden.value = btn.dataset.val;
                if (onChange) onChange(btn.dataset.val);
            });
        }

        const placementSeg = form.querySelector('[data-seg="placement"]');
        if (placementSeg) wireSingleSeg(placementSeg, 'placement-input');

        const garmentSeg = form.querySelector('[data-seg="garment_fit"]');
        const garmentColorsField = document.getElementById('garment-colors-field');
        function toggleGarmentColors(val) {
            if (garmentColorsField) garmentColorsField.hidden = (val !== 'specific');
        }
        if (garmentSeg) {
            wireSingleSeg(garmentSeg, 'garment-fit-input', toggleGarmentColors);
            const cur = document.getElementById('garment-fit-input');
            toggleGarmentColors(cur ? cur.value : 'any');
        }

        // ---------- Variant rows ----------
        const container = document.getElementById('variant-rows');
        const tpl = document.getElementById('variant-template');
        const addBtn = document.getElementById('add-variant');

        function modeLabel(mode) {
            return ({ single: 'Один колір', combo: 'Поєднання', mix: 'Мікс', standard: 'Стандарт' })[mode] || mode;
        }

        function syncRow(row) {
            const modeInput = row.querySelector('.variant-mode-input');
            const colorsInput = row.querySelector('.variant-colors-input');
            const picker = row.querySelector('.variant-colors-picker');
            const label = row.querySelector('[data-variant-label]');
            const mode = modeInput.value || 'single';
            const checks = picker ? picker.querySelectorAll('input[type="checkbox"]') : [];

            // Picker visibility per mode
            if (picker) picker.hidden = (mode === 'mix' || mode === 'standard');

            // For "single" — enforce a single selected checkbox
            const selected = [];
            checks.forEach(function (c) { if (c.checked) selected.push(c.value); });

            colorsInput.value = selected.join(',');

            // Build human label
            if (label) {
                if (mode === 'mix') label.textContent = 'Мікс';
                else if (mode === 'standard') label.textContent = 'Стандарт';
                else {
                    const names = [];
                    checks.forEach(function (c) {
                        if (c.checked) {
                            const lbl = c.closest('.wh-color-pill').querySelector('.wh-color-pill__label');
                            names.push(lbl ? lbl.textContent.trim() : c.value);
                        }
                    });
                    label.textContent = names.length ? names.join(' + ') : (mode === 'combo' ? 'Поєднання' : 'Один колір');
                }
            }
        }

        function wireRow(row) {
            const modeInput = row.querySelector('.variant-mode-input');
            const seg = row.querySelector('[data-seg="mode"]');
            const picker = row.querySelector('.variant-colors-picker');

            if (seg) {
                seg.addEventListener('click', function (e) {
                    const btn = e.target.closest('.wh-seg__btn');
                    if (!btn) return;
                    seg.querySelectorAll('.wh-seg__btn').forEach(function (b) {
                        b.classList.toggle('is-active', b === btn);
                    });
                    modeInput.value = btn.dataset.val;
                    syncRow(row);
                });
            }

            if (picker) {
                picker.addEventListener('change', function (e) {
                    if (!e.target.matches('input[type="checkbox"]')) return;
                    const mode = modeInput.value || 'single';
                    if (mode === 'single' && e.target.checked) {
                        // single → keep only this one
                        picker.querySelectorAll('input[type="checkbox"]').forEach(function (c) {
                            if (c !== e.target) c.checked = false;
                        });
                    }
                    syncRow(row);
                });
            }

            syncRow(row);
        }

        // Wire existing rows
        if (container) {
            container.querySelectorAll('.variant-row').forEach(wireRow);

            container.addEventListener('click', function (e) {
                if (e.target.closest('.variant-remove')) {
                    e.target.closest('.variant-row').remove();
                    reindexDefaults();
                }
            });
        }

        function reindexDefaults() {
            container.querySelectorAll('.variant-row').forEach(function (row, idx) {
                row.dataset.index = idx;
                const radio = row.querySelector('input[type="radio"][name="variant_default"]');
                if (radio) radio.value = idx;
            });
        }

        if (addBtn && tpl) {
            addBtn.addEventListener('click', function () {
                const clone = tpl.content.cloneNode(true);
                const row = clone.querySelector('.variant-row');
                container.appendChild(clone);
                wireRow(row);
                reindexDefaults();
            });
        }

        // Make sure inputs are synced right before submit (belt-and-suspenders)
        form.addEventListener('submit', function () {
            if (container) container.querySelectorAll('.variant-row').forEach(syncRow);
        });

        // ---------- Product picker ----------
        const picker = document.getElementById('product-picker');
        if (!picker) return;
        const search = document.getElementById('pp-search');
        const counter = document.getElementById('pp-counter');
        const allBtn = document.getElementById('pp-all');
        const clearBtn = document.getElementById('pp-clear');
        const onlySelectedBtn = document.getElementById('pp-only-selected');
        const emptyHint = document.getElementById('pp-empty');
        let onlySelected = false;

        function checkboxes() { return picker.querySelectorAll('.wh-pp-card input[type="checkbox"]'); }
        function cards() { return picker.querySelectorAll('.wh-pp-card'); }
        function refreshCounter() {
            const total = cards().length;
            let checked = 0;
            checkboxes().forEach(function (i) { if (i.checked) checked += 1; });
            counter.textContent = checked + ' / ' + total;
            counter.classList.toggle('is-selected', checked > 0);
        }
        function applyFilter() {
            const q = (search.value || '').trim().toLowerCase();
            let visibleAny = false;
            picker.querySelectorAll('.wh-pp-group').forEach(function (group) {
                let groupVisible = 0;
                group.querySelectorAll('.wh-pp-card').forEach(function (card) {
                    const name = card.getAttribute('data-name') || '';
                    const isChecked = card.querySelector('input').checked;
                    const matchesQuery = !q || name.includes(q);
                    const matchesFilter = !onlySelected || isChecked;
                    const visible = matchesQuery && matchesFilter;
                    card.style.display = visible ? '' : 'none';
                    if (visible) { groupVisible += 1; visibleAny = true; }
                });
                const countEl = group.querySelector('[data-group-count]');
                if (countEl) countEl.textContent = groupVisible;
                group.style.display = groupVisible > 0 ? '' : 'none';
            });
            emptyHint.hidden = visibleAny;
        }

        if (search) search.addEventListener('input', applyFilter);
        if (allBtn) allBtn.addEventListener('click', function () {
            cards().forEach(function (card) { if (card.style.display !== 'none') card.querySelector('input').checked = true; });
            refreshCounter();
        });
        if (clearBtn) clearBtn.addEventListener('click', function () {
            cards().forEach(function (card) { if (card.style.display !== 'none') card.querySelector('input').checked = false; });
            refreshCounter();
        });
        if (onlySelectedBtn) onlySelectedBtn.addEventListener('click', function () {
            onlySelected = !onlySelected;
            onlySelectedBtn.classList.toggle('is-active', onlySelected);
            onlySelectedBtn.textContent = onlySelected ? 'Показати всі' : 'Показати обрані';
            applyFilter();
        });
        picker.addEventListener('change', function (e) {
            if (e.target && e.target.matches('.wh-pp-card input[type="checkbox"]')) refreshCounter();
        });

        refreshCounter();
        applyFilter();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
