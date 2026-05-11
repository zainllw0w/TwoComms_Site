/* Category detail: bottom-sheet for quick stock adjust + new row creation. */
(function () {
    'use strict';

    const W = window.WAREHOUSE;
    if (!W || !window.__warehouse__) return;

    const sheet = document.getElementById('wh-sheet');
    const backdrop = document.getElementById('wh-sheet-backdrop');
    const sheetTitle = document.getElementById('wh-sheet-title');
    const qtyMinus = document.getElementById('qty-minus');
    const qtyPlus = document.getElementById('qty-plus');
    const qtyValue = document.getElementById('qty-value');
    const qtySet = document.getElementById('qty-set');
    const costSet = document.getElementById('cost-set');
    const commentSet = document.getElementById('comment-set');
    const saveBtn = document.getElementById('wh-sheet-save');
    const cancelBtn = document.getElementById('wh-sheet-cancel');

    const addSheet = document.getElementById('wh-add-sheet');
    const addCancel = document.getElementById('wh-add-cancel');
    const addSave = document.getElementById('wh-add-save');
    const addSubcategoryId = document.getElementById('add-subcategory-id');
    const addSize = document.getElementById('add-size');
    const addColor = document.getElementById('add-color');
    const addQty = document.getElementById('add-qty');
    const addCost = document.getElementById('add-cost');
    const addTitle = document.getElementById('wh-add-title');

    let currentCell = null;
    let pendingDelta = 0;

    function openSheet(cell) {
        currentCell = cell;
        pendingDelta = 0;
        const subName = cell.dataset.subcategoryName || '';
        const size = cell.dataset.size || '';
        const colorName = cell.dataset.colorName || '';
        const qty = parseInt(cell.dataset.quantity, 10) || 0;
        sheetTitle.textContent = subName + ' · ' + colorName + ' · ' + size;
        qtyValue.textContent = qty;
        qtySet.value = '';
        costSet.value = '';
        commentSet.value = '';
        sheet.classList.add('open');
        backdrop.classList.add('open');
    }

    function closeSheet() {
        sheet.classList.remove('open');
        backdrop.classList.remove('open');
        currentCell = null;
    }

    function openAddSheet(btn) {
        addSubcategoryId.value = btn.dataset.subcategoryId;
        addTitle.textContent = 'Нова позиція: ' + (btn.dataset.subcategoryName || '');
        addSize.value = '';
        addColor.value = '';
        addQty.value = '1';
        addCost.value = '0';

        // Filter color options by allowed colors of this subcategory.
        // data-allowed-colors is a comma-separated list of color ids; empty = no restriction.
        const raw = btn.dataset.allowedColors || '';
        const allowed = raw ? raw.split(',').map(function (s) { return s.trim(); }).filter(Boolean) : null;
        const allowSet = allowed && allowed.length ? new Set(allowed) : null;
        Array.from(addColor.options).forEach(function (opt) {
            if (opt.value === '') { opt.hidden = false; return; }
            opt.hidden = !!(allowSet && !allowSet.has(opt.value));
        });

        addSheet.classList.add('open');
        backdrop.classList.add('open');
    }

    function closeAddSheet() {
        addSheet.classList.remove('open');
        backdrop.classList.remove('open');
    }

    function updateCellQty(cell, newQty) {
        cell.dataset.quantity = String(newQty);
        cell.innerHTML = '';
        const span = document.createElement('span');
        if (newQty <= 0) span.className = 'qty-zero';
        else if (newQty < 3) span.className = 'qty-low';
        else span.className = 'qty-positive';
        span.textContent = newQty;
        cell.appendChild(span);
    }

    document.querySelectorAll('.qty-cell').forEach(function (cell) {
        cell.addEventListener('click', function () { openSheet(cell); });
    });

    document.querySelectorAll('.wh-add-row-btn').forEach(function (btn) {
        btn.addEventListener('click', function () { openAddSheet(btn); });
    });

    cancelBtn.addEventListener('click', closeSheet);
    addCancel.addEventListener('click', closeAddSheet);
    backdrop.addEventListener('click', function () { closeSheet(); closeAddSheet(); });

    qtyMinus.addEventListener('click', function () {
        const cur = parseInt(qtyValue.textContent, 10) || 0;
        const newQty = Math.max(cur - 1, 0);
        qtyValue.textContent = newQty;
        pendingDelta = newQty - (parseInt(currentCell.dataset.quantity, 10) || 0);
    });
    qtyPlus.addEventListener('click', function () {
        const cur = parseInt(qtyValue.textContent, 10) || 0;
        qtyValue.textContent = cur + 1;
        pendingDelta = (cur + 1) - (parseInt(currentCell.dataset.quantity, 10) || 0);
    });

    saveBtn.addEventListener('click', function () {
        if (!currentCell) return;
        const fd = new FormData();
        fd.append('subcategory_id', currentCell.dataset.subcategoryId);
        fd.append('size', currentCell.dataset.size);
        fd.append('color_id', currentCell.dataset.colorId || '');
        fd.append('comment', commentSet.value || '');
        if (costSet.value) fd.append('cost_price', costSet.value);

        if (qtySet.value !== '') {
            fd.append('mode', 'set');
            fd.append('quantity', qtySet.value);
        } else if (pendingDelta !== 0) {
            fd.append('mode', 'delta');
            fd.append('delta', String(pendingDelta));
            fd.append('reason', pendingDelta > 0 ? 'manual_add' : 'manual_remove');
        } else {
            closeSheet();
            return;
        }

        saveBtn.disabled = true;
        W.postForm(window.__warehouse__.urls.stockAdjust, fd).then(function (data) {
            saveBtn.disabled = false;
            if (data.ok) {
                updateCellQty(currentCell, data.quantity);
                W.flash('Збережено', 'success');
                closeSheet();
            } else {
                W.flash(data.error || 'Помилка', 'error');
            }
        });
    });

    addSave.addEventListener('click', function () {
        const fd = new FormData();
        fd.append('subcategory_id', addSubcategoryId.value);
        fd.append('size', (addSize.value || '').trim());
        fd.append('color_id', addColor.value || '');
        fd.append('mode', 'delta');
        fd.append('delta', addQty.value || '0');
        fd.append('reason', 'manual_add');
        if (addCost.value) fd.append('cost_price', addCost.value);

        if (!fd.get('size') || parseInt(fd.get('delta'), 10) <= 0) {
            W.flash('Заповніть розмір та кількість', 'error');
            return;
        }

        addSave.disabled = true;
        W.postForm(window.__warehouse__.urls.stockAdjust, fd).then(function (data) {
            addSave.disabled = false;
            if (data.ok) {
                W.flash('Додано: ' + data.quantity + ' шт', 'success');
                closeAddSheet();
                setTimeout(function () { location.reload(); }, 600);
            } else {
                W.flash(data.error || 'Помилка', 'error');
            }
        });
    });
})();
