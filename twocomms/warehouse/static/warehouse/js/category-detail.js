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
    const costSet = document.getElementById('cost-set');         // delta-mode (purchase price)
    const costSetAbs = document.getElementById('cost-set-abs');  // set-mode (override)
    const commentSet = document.getElementById('comment-set');
    const saveBtn = document.getElementById('wh-sheet-save');
    const cancelBtn = document.getElementById('wh-sheet-cancel');

    // Summary widgets
    const adjustCurrentQty = document.getElementById('adjust-current-qty');
    const adjustCurrentCost = document.getElementById('adjust-current-cost');
    const adjustLastCostRow = document.getElementById('adjust-lastcost-row');
    const adjustLastCost = document.getElementById('adjust-last-cost');
    const adjustSpreadBadge = document.getElementById('adjust-spread-badge');
    const adjustPreviewRow = document.getElementById('adjust-preview-row');
    const adjustPreviewQty = document.getElementById('adjust-preview-qty');
    const adjustPreviewCost = document.getElementById('adjust-preview-cost');
    const adjustDeltaBadge = document.getElementById('adjust-delta-badge');
    const costFieldDelta = document.getElementById('cost-field-delta');

    // Tabs
    const tabs = sheet.querySelectorAll('.wh-adjust-tab');
    const panes = sheet.querySelectorAll('.wh-adjust-pane');
    let currentTab = 'delta';

    function setTab(name) {
        currentTab = name;
        tabs.forEach(function (t) {
            t.classList.toggle('is-active', t.dataset.tab === name);
        });
        panes.forEach(function (p) {
            p.hidden = p.dataset.pane !== name;
        });
        updatePreview();
    }
    tabs.forEach(function (t) {
        t.addEventListener('click', function () { setTab(t.dataset.tab); });
    });

    function fmtMoney(d) {
        if (isNaN(d) || d === null) return '0';
        return (Math.round(parseFloat(d) * 100) / 100).toFixed(2).replace(/\.?0+$/, '');
    }

    function updatePreview() {
        if (!currentCell) return;
        const oldQty = parseInt(currentCell.dataset.quantity, 10) || 0;
        const oldCost = parseFloat(currentCell.dataset.cost) || 0;

        let newQty, newCost, delta;
        if (currentTab === 'delta') {
            const enteredCost = parseFloat(costSet.value);
            newQty = oldQty + pendingDelta;
            delta = pendingDelta;
            // WAC only applies on positive delta with cost specified
            if (pendingDelta > 0 && !isNaN(enteredCost) && enteredCost >= 0) {
                if (oldQty === 0) {
                    newCost = enteredCost;
                } else {
                    newCost = (oldQty * oldCost + pendingDelta * enteredCost) / newQty;
                }
            } else {
                newCost = oldCost;
            }
            // Hide cost field when removing (delta < 0)
            if (costFieldDelta) {
                costFieldDelta.style.opacity = pendingDelta < 0 ? '0.4' : '';
                costFieldDelta.style.pointerEvents = pendingDelta < 0 ? 'none' : '';
            }
        } else {
            // set-mode
            const absQty = parseInt(qtySet.value, 10);
            if (isNaN(absQty)) { adjustPreviewRow.hidden = true; return; }
            const enteredCost = parseFloat(costSetAbs.value);
            newQty = Math.max(absQty, 0);
            delta = newQty - oldQty;
            newCost = !isNaN(enteredCost) && enteredCost >= 0 ? enteredCost : oldCost;
        }

        const changed = (newQty !== oldQty) || (Math.abs(newCost - oldCost) > 0.005);
        adjustPreviewRow.hidden = !changed;
        if (changed) {
            adjustPreviewQty.textContent = newQty;
            adjustPreviewCost.textContent = fmtMoney(newCost);
            if (delta !== 0) {
                adjustDeltaBadge.textContent = (delta > 0 ? '+' : '') + delta;
                adjustDeltaBadge.classList.remove('is-positive', 'is-negative');
                adjustDeltaBadge.classList.add(delta > 0 ? 'is-positive' : 'is-negative');
                adjustDeltaBadge.hidden = false;
            } else {
                adjustDeltaBadge.hidden = true;
            }
        }
    }

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
    let currentCellCostAtOpen = '0';

    function openSheet(cell) {
        currentCell = cell;
        pendingDelta = 0;
        currentCellCostAtOpen = cell.dataset.cost || '0';
        const subName = cell.dataset.subcategoryName || '';
        const size = cell.dataset.size || '';
        const colorName = cell.dataset.colorName || '';
        const qty = parseInt(cell.dataset.quantity, 10) || 0;
        const cost = parseFloat(cell.dataset.cost) || 0;
        sheetTitle.textContent = subName + ' · ' + colorName + ' · ' + size;

        // Summary
        adjustCurrentQty.textContent = qty;
        adjustCurrentCost.textContent = fmtMoney(cost);
        adjustPreviewRow.hidden = true;

        // Last-batch cost vs weighted average (price-shift indicator)
        const lastCost = parseFloat(cell.dataset.lastCost) || 0;
        if (adjustLastCostRow && adjustLastCost && adjustSpreadBadge) {
            if (lastCost > 0 && Math.abs(lastCost - cost) > 0.5) {
                adjustLastCost.textContent = fmtMoney(lastCost);
                const diff = lastCost - cost;
                adjustSpreadBadge.textContent = (diff > 0 ? '+' : '') + fmtMoney(diff) + ' ₴';
                adjustSpreadBadge.classList.remove('is-positive', 'is-negative');
                adjustSpreadBadge.classList.add(diff > 0 ? 'is-negative' : 'is-positive');
                adjustLastCostRow.hidden = false;
            } else {
                adjustLastCostRow.hidden = true;
            }
        }

        // Delta pane defaults
        qtyValue.textContent = '0';
        if (costSet) costSet.value = '';
        // Set pane defaults
        if (qtySet) qtySet.value = '';
        if (costSetAbs) costSetAbs.value = '';
        if (commentSet) commentSet.value = '';

        // Always start on Delta tab
        setTab('delta');

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

    function qtyClass(n) {
        if (n <= 0) return 'qty-zero';
        if (n < 3) return 'qty-low';
        return 'qty-positive';
    }

    function updateCellQty(cell, newQty, newCost) {
        cell.dataset.quantity = String(newQty);
        if (newCost !== undefined && newCost !== null) {
            cell.dataset.cost = String(newCost);
        }
        const cls = qtyClass(newQty);
        // Mobile card cell — preserve .wh-mc__size and only swap qty span
        const qtySpan = cell.querySelector('.wh-mc__qty');
        if (qtySpan) {
            cell.classList.remove('qty-zero', 'qty-low', 'qty-positive');
            cell.classList.add(cls);
            qtySpan.textContent = newQty;
            return;
        }
        // Table cell — rewrite inner span
        cell.innerHTML = '';
        const span = document.createElement('span');
        span.className = cls;
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

    // Delta is signed (− or +). qtyValue shows the magnitude OR signed delta.
    // We use a signed approach: display "0" initially, +1/-1 per click.
    qtyMinus.addEventListener('click', function () {
        const cur = parseInt(qtyValue.textContent, 10) || 0;
        const oldQty = parseInt(currentCell.dataset.quantity, 10) || 0;
        // Don't allow delta that goes below 0 total
        if (oldQty + (cur - 1) < 0) return;
        pendingDelta = cur - 1;
        qtyValue.textContent = (pendingDelta > 0 ? '+' : '') + pendingDelta;
        updatePreview();
    });
    qtyPlus.addEventListener('click', function () {
        const cur = parseInt(qtyValue.textContent, 10) || 0;
        pendingDelta = cur + 1;
        qtyValue.textContent = (pendingDelta > 0 ? '+' : '') + pendingDelta;
        updatePreview();
    });

    // Live preview reacts to typing
    if (costSet) costSet.addEventListener('input', updatePreview);
    if (costSetAbs) costSetAbs.addEventListener('input', updatePreview);
    if (qtySet) qtySet.addEventListener('input', updatePreview);

    saveBtn.addEventListener('click', function () {
        if (!currentCell) return;
        const fd = new FormData();
        fd.append('subcategory_id', currentCell.dataset.subcategoryId);
        fd.append('size', currentCell.dataset.size);
        fd.append('color_id', currentCell.dataset.colorId || '');
        fd.append('comment', commentSet.value || '');

        const oldQty = parseInt(currentCell.dataset.quantity, 10) || 0;

        if (currentTab === 'set') {
            const hasQty = qtySet.value !== '';
            const hasCost = costSetAbs.value !== '';
            if (!hasQty && !hasCost) { closeSheet(); return; }
            fd.append('mode', 'set');
            // Якщо кількість не задано — лишаємо поточну (правимо тільки ціну).
            fd.append('quantity', hasQty ? qtySet.value : String(oldQty));
            if (hasCost) fd.append('cost_price', costSetAbs.value);
        } else {
            // Delta tab. Можливі сценарії:
            //  • змінили кількість (pendingDelta != 0) — звичайне коригування;
            //  • кількість 0, але ввели ціну — це корекція ціни без руху,
            //    шлемо як mode=set із поточною кількістю (баг-фікс: раніше
            //    таке мовчки ігнорувалось).
            const enteredCost = costSet.value;
            if (pendingDelta === 0) {
                if (enteredCost === '') { closeSheet(); return; }
                fd.append('mode', 'set');
                fd.append('quantity', String(oldQty));
                fd.append('cost_price', enteredCost);
            } else {
                fd.append('mode', 'delta');
                fd.append('delta', String(pendingDelta));
                fd.append('reason', pendingDelta > 0 ? 'manual_add' : 'manual_remove');
                // Ціну закупки враховуємо лише при прибутті (середньозважена).
                if (pendingDelta > 0 && enteredCost) {
                    fd.append('cost_price', enteredCost);
                }
            }
        }

        saveBtn.disabled = true;
        W.postForm(window.__warehouse__.urls.stockAdjust, fd).then(function (data) {
            saveBtn.disabled = false;
            if (data.ok) {
                updateCellQty(currentCell, data.quantity, data.cost_price);
                W.flash('Збережено', 'success');
                closeSheet();
                // Ціна могла змінитись — перерендеримо мітки спреду через reload,
                // але тільки якщо змінилась собівартість (щоб не смикати зайвий раз).
                if (data.cost_price !== undefined &&
                    String(data.cost_price) !== String(currentCellCostAtOpen)) {
                    setTimeout(function () { location.reload(); }, 500);
                }
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
