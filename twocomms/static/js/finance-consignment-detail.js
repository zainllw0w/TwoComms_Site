/**
 * Деталь магазину під реалізацію: модалки поставки/виплати/продажу + графіки.
 * Залежить від finance-consignment.js (window.consignment) та Chart.js.
 */
(function () {
    'use strict';
    const C = window.consignment || {};
    const postJSON = C.postJSON;
    const postForm = C.postForm;
    const openModal = C.openModal;
    const closeModal = C.closeModal;
    const dropdowns = C.dropdowns || {};

    // reseller_id з URL: /consignment/<id>/
    const m = location.pathname.match(/consignment\/(\d+)/);
    const resellerId = m ? m[1] : null;
    if (!resellerId) return;

    function fillAccountSelect(sel) {
        if (!sel) return;
        sel.innerHTML = '';
        (dropdowns.accounts || []).forEach(a => {
            const opt = document.createElement('option');
            opt.value = a.id;
            opt.textContent = a.name + ' (' + a.currency + ')';
            sel.appendChild(opt);
        });
    }

    // ---------- Поставка ----------
    const shipBtn = document.getElementById('cons-shipment-btn');
    const shipModal = document.getElementById('cons-shipment-modal');
    const itemsRows = document.getElementById('cons-items-rows');
    const itemTpl = document.getElementById('cons-item-row-tpl');

    function addItemRow() {
        if (!itemTpl || !itemsRows) return;
        const node = itemTpl.content.cloneNode(true);
        node.querySelector('.ci-del').addEventListener('click', function (e) {
            e.target.closest('.fin-cons-item-row').remove();
        });
        itemsRows.appendChild(node);
    }

    if (shipBtn) {
        shipBtn.addEventListener('click', () => {
            const d = document.getElementById('cons-ship-date');
            if (d && !d.value) d.value = new Date().toISOString().slice(0, 10);
            if (itemsRows && !itemsRows.children.length) addItemRow();
            openModal(shipModal);
        });
    }
    const addItemBtn = document.getElementById('cons-add-item-row');
    if (addItemBtn) addItemBtn.addEventListener('click', addItemRow);

    // Заповнення рядка позиції даними з менеджменту
    function addItemRowFilled(it) {
        if (!itemTpl || !itemsRows) return;
        const node = itemTpl.content.cloneNode(true);
        node.querySelector('.ci-title').value = it.title || '';
        node.querySelector('.ci-print').value = it.print_name || '';
        node.querySelector('.ci-size').value = it.size || '';
        node.querySelector('.ci-qty').value = it.qty || 0;
        node.querySelector('.ci-cost').value = it.unit_cost || 0;
        node.querySelector('.ci-price').value = it.unit_price || 0;
        node.querySelector('.ci-consignment').checked = !!it.is_consignment;
        node.querySelector('.ci-del').addEventListener('click', function (e) {
            e.target.closest('.fin-cons-item-row').remove();
        });
        itemsRows.appendChild(node);
    }

    // Вибір джерела (вручну / замовлення / тестова партія)
    const sourceSel = document.getElementById('cons-ship-source');
    const mgmtWrap = document.getElementById('cons-ship-mgmt-wrap');
    const mgmtSelect = document.getElementById('cons-ship-mgmt-select');
    const mgmtLabel = document.getElementById('cons-ship-mgmt-label');

    function loadMgmtList(kind) {
        const url = kind === 'order'
            ? '/api/consignment/management/orders/'
            : '/api/consignment/management/tests/';
        mgmtSelect.innerHTML = '<option value="">— завантаження… —</option>';
        fetch(url).then(r => r.json()).then(res => {
            mgmtSelect.innerHTML = '<option value="">— оберіть —</option>';
            const list = res.orders || res.batches || [];
            if (!list.length) {
                mgmtSelect.innerHTML = '<option value="">немає даних</option>';
                return;
            }
            list.forEach(o => {
                const opt = document.createElement('option');
                opt.value = o.id;
                opt.textContent = kind === 'order'
                    ? (o.number + ' · ' + o.company + ' · ' + o.amount + ' ₴')
                    : (o.name + ' · ' + (o.product || '') + ' · ' + o.qty + ' шт');
                mgmtSelect.appendChild(opt);
            });
        }).catch(() => { mgmtSelect.innerHTML = '<option value="">помилка</option>'; });
    }

    if (sourceSel) {
        sourceSel.addEventListener('change', function () {
            const kind = sourceSel.value;
            if (kind === 'manual') {
                mgmtWrap.hidden = true;
            } else {
                mgmtWrap.hidden = false;
                mgmtLabel.textContent = kind === 'order' ? 'Оберіть замовлення' : 'Оберіть тестову партію';
                loadMgmtList(kind);
            }
        });
    }

    const mgmtLoadBtn = document.getElementById('cons-ship-mgmt-load');
    if (mgmtLoadBtn) {
        mgmtLoadBtn.addEventListener('click', function () {
            const kind = sourceSel.value;
            const id = mgmtSelect.value;
            if (!id) { alert('Оберіть джерело'); return; }
            const url = kind === 'order'
                ? '/api/consignment/management/orders/' + id + '/items/'
                : '/api/consignment/management/tests/' + id + '/items/';
            fetch(url).then(r => r.json()).then(res => {
                const items = res.items || [];
                if (!items.length) { alert('Позицій не знайдено'); return; }
                // Очищаємо порожні рядки і додаємо підтягнуті
                itemsRows.innerHTML = '';
                items.forEach(addItemRowFilled);
                recalcMonths();
                // Підставляємо ТТН/номер якщо порожні
                if (kind === 'order') {
                    const numEl = document.getElementById('cons-ship-number');
                    const opt = mgmtSelect.options[mgmtSelect.selectedIndex];
                    if (numEl && !numEl.value && opt) numEl.value = (opt.textContent.split(' · ')[0] || '');
                }
            }).catch(() => alert('Помилка завантаження'));
        });
    }

    // Авто-розрахунок кількості місяців за щомісячною виплатою.
    function recalcMonths() {
        const debtField = parseFloat(document.getElementById('cons-ship-debt').value) || 0;
        let itemsDebt = 0;
        document.querySelectorAll('.fin-cons-item-row').forEach(row => {
            const isCons = row.querySelector('.ci-consignment').checked;
            if (isCons) return; // консигнація не борг
            const qty = parseInt(row.querySelector('.ci-qty').value, 10) || 0;
            const cost = parseFloat(row.querySelector('.ci-cost').value) || 0;
            itemsDebt += qty * cost;
        });
        const total = debtField + itemsDebt;
        const monthly = parseFloat(document.getElementById('cons-ship-monthly').value) || 0;
        const hint = document.getElementById('cons-ship-months-hint');
        if (monthly > 0 && total > 0) {
            const months = Math.ceil(total / monthly);
            hint.textContent = months + ' міс. (борг ' + total.toLocaleString('uk') + ' ₴)';
        } else {
            hint.textContent = total > 0 ? ('борг ' + total.toLocaleString('uk') + ' ₴') : '—';
        }
    }
    const monthlyEl = document.getElementById('cons-ship-monthly');
    const debtEl = document.getElementById('cons-ship-debt');
    if (monthlyEl) monthlyEl.addEventListener('input', recalcMonths);
    if (debtEl) debtEl.addEventListener('input', recalcMonths);
    if (itemsRows) itemsRows.addEventListener('input', recalcMonths);

    const shipForm = document.getElementById('cons-shipment-form');
    if (shipForm) {
        shipForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const items = [];
            document.querySelectorAll('.fin-cons-item-row').forEach(row => {
                const title = row.querySelector('.ci-title').value.trim();
                const qty = parseInt(row.querySelector('.ci-qty').value, 10) || 0;
                if (!title || qty <= 0) return;
                items.push({
                    source_kind: 'manual',
                    title: title,
                    print_name: row.querySelector('.ci-print').value,
                    size: row.querySelector('.ci-size').value,
                    qty: qty,
                    unit_cost: row.querySelector('.ci-cost').value || 0,
                    unit_price: row.querySelector('.ci-price').value || 0,
                    is_consignment: row.querySelector('.ci-consignment').checked,
                });
            });
            const fd = new FormData();
            fd.append('date', document.getElementById('cons-ship-date').value);
            fd.append('number', document.getElementById('cons-ship-number').value);
            fd.append('ttn', document.getElementById('cons-ship-ttn').value);
            fd.append('debt_amount', document.getElementById('cons-ship-debt').value || 0);
            fd.append('payment_monthly', document.getElementById('cons-ship-monthly').value || '');
            fd.append('comment', document.getElementById('cons-ship-comment').value);
            fd.append('items', JSON.stringify(items));
            const files = document.getElementById('cons-ship-files').files;
            for (let i = 0; i < files.length; i++) fd.append('files', files[i]);

            postForm('/api/consignment/resellers/' + resellerId + '/shipments/create/', fd)
                .then(res => res.ok ? location.reload() : alert(res.error || 'Помилка'));
        });
    }

    // Видалення поставки
    document.querySelectorAll('[data-cons-ship-del]').forEach(btn => {
        btn.addEventListener('click', function () {
            if (!confirm('Видалити поставку? Борг буде анульовано.')) return;
            const sid = btn.getAttribute('data-cons-ship-del');
            postJSON('/api/consignment/shipments/' + sid + '/delete/', {})
                .then(res => res.ok ? location.reload() : alert(res.error || 'Помилка'));
        });
    });

    // ---------- Виплата ----------
    const payBtn = document.getElementById('cons-payment-btn');
    const payModal = document.getElementById('cons-payment-modal');

    function syncPayMode() {
        const mode = (document.querySelector('input[name="mode"]:checked') || {}).value || 'manual_cash';
        document.getElementById('cons-pay-cash').hidden = (mode !== 'manual_cash');
        document.getElementById('cons-pay-txn').hidden = (mode !== 'pick_txn');
    }
    document.querySelectorAll('input[name="mode"]').forEach(r => r.addEventListener('change', syncPayMode));

    function loadPayableTxns() {
        const sel = document.getElementById('cons-pay-txn-select');
        if (!sel) return;
        fetch('/api/consignment/resellers/' + resellerId + '/payable-txns/')
            .then(r => r.json())
            .then(res => {
                sel.innerHTML = '<option value="">— оберіть —</option>';
                (res.candidates || []).forEach(c => {
                    const opt = document.createElement('option');
                    opt.value = c.id;
                    opt.textContent = (c.date || '') + ' · ' + (c.amount_display || '') + ' · ' + (c.account_name || '');
                    opt.setAttribute('data-amount', c.amount || '');
                    opt.setAttribute('data-has-cp', c.account_has_counterparty ? '1' : '0');
                    sel.appendChild(opt);
                });
            });
    }

    const txnSelect = document.getElementById('cons-pay-txn-select');
    if (txnSelect) {
        txnSelect.addEventListener('change', function () {
            const opt = txnSelect.options[txnSelect.selectedIndex];
            if (!opt) return;
            const amt = opt.getAttribute('data-amount');
            if (amt) document.getElementById('cons-pay-amount').value = amt;
            // Показати чекбокс привʼязки, якщо рахунок ще не привʼязаний.
            const hasCp = opt.getAttribute('data-has-cp') === '1';
            document.getElementById('cons-link-cp-wrap').hidden = hasCp;
        });
    }

    if (payBtn) {
        payBtn.addEventListener('click', () => {
            fillAccountSelect(document.getElementById('cons-pay-account'));
            const d = document.getElementById('cons-pay-date');
            if (d && !d.value) d.value = new Date().toISOString().slice(0, 10);
            loadPayableTxns();
            syncPayMode();
            openModal(payModal);
        });
    }

    const payForm = document.getElementById('cons-payment-form');
    if (payForm) {
        payForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const mode = document.querySelector('input[name="mode"]:checked').value;
            const payload = {
                mode: mode,
                amount: document.getElementById('cons-pay-amount').value,
                date: document.getElementById('cons-pay-date').value,
                comment: document.getElementById('cons-pay-comment').value,
            };
            if (mode === 'manual_cash') {
                payload.account_id = document.getElementById('cons-pay-account').value;
            } else {
                payload.txn_id = document.getElementById('cons-pay-txn-select').value;
                payload.link_account_cp = document.getElementById('cons-link-cp').checked;
            }
            postJSON('/api/consignment/resellers/' + resellerId + '/payment/', payload)
                .then(res => res.ok ? location.reload() : alert(res.error || 'Помилка'));
        });
    }

    // ---------- Продаж ----------
    const saleModal = document.getElementById('cons-sale-modal');
    document.querySelectorAll('[data-cons-sale]').forEach(btn => {
        btn.addEventListener('click', function () {
            document.getElementById('cons-sale-item-id').value = btn.getAttribute('data-cons-sale');
            document.getElementById('cons-sale-title').textContent =
                btn.getAttribute('data-title') + ' (залишок: ' + btn.getAttribute('data-remaining') + ')';
            document.getElementById('cons-sale-price').value = btn.getAttribute('data-price') || '';
            document.getElementById('cons-sale-qty').max = btn.getAttribute('data-remaining');
            const d = document.getElementById('cons-sale-date');
            if (d && !d.value) d.value = new Date().toISOString().slice(0, 10);
            openModal(saleModal);
        });
    });

    const saleForm = document.getElementById('cons-sale-form');
    if (saleForm) {
        saleForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const itemId = document.getElementById('cons-sale-item-id').value;
            const payload = {
                qty: document.getElementById('cons-sale-qty').value,
                unit_price: document.getElementById('cons-sale-price').value,
                date: document.getElementById('cons-sale-date').value,
                creates_debt: document.getElementById('cons-sale-debt').checked,
            };
            postJSON('/api/consignment/items/' + itemId + '/sale/', payload)
                .then(res => res.ok ? location.reload() : alert(res.error || 'Помилка'));
        });
    }

    // ---------- Редагувати магазин (відкрити модалку із заповненням) ----------
    const editBtn = document.getElementById('cons-edit-btn');
    if (editBtn) {
        editBtn.addEventListener('click', () => {
            fetch('/api/consignment/resellers/' + resellerId + '/get/')
                .then(r => r.json())
                .then(res => {
                    if (!res.ok) return;
                    const d = res.reseller;
                    // Заповнюємо селект контрагентів (з dropdowns)
                    const cpSel = document.getElementById('cons-reseller-cp');
                    if (cpSel) {
                        cpSel.innerHTML = '<option value="">— не вказано —</option>';
                        (dropdowns.counterparties || []).forEach(cp => {
                            const o = document.createElement('option');
                            o.value = cp.id; o.textContent = cp.name;
                            if (cp.id === d.counterparty_id) o.selected = true;
                            cpSel.appendChild(o);
                        });
                    }
                    document.getElementById('cons-reseller-id').value = d.id;
                    document.getElementById('cons-reseller-name').value = d.name;
                    document.getElementById('cons-reseller-status').value = d.status;
                    document.getElementById('cons-terms-kind').value = d.terms_kind;
                    document.getElementById('cons-notes').value = d.notes || '';
                    document.getElementById('cons-phone').value = (d.contacts || {}).phone || '';
                    document.getElementById('cons-responsible').value = (d.contacts || {}).responsible || '';
                    const t = d.terms || {};
                    if (document.getElementById('cons-due-days')) document.getElementById('cons-due-days').value = t.due_days || 14;
                    if (document.getElementById('cons-period')) document.getElementById('cons-period').value = t.period || 'month';
                    if (document.getElementById('cons-every')) document.getElementById('cons-every').value = t.every || 1;
                    if (document.getElementById('cons-amount')) document.getElementById('cons-amount').value = t.amount || '';
                    if (document.getElementById('cons-periods')) document.getElementById('cons-periods').value = t.periods || '';
                    if (document.getElementById('cons-anchor')) document.getElementById('cons-anchor').value = t.anchor_day || 5;
                    document.getElementById('cons-reseller-modal-title').textContent = 'Редагувати магазин';
                    // Синхронізуємо видимість груп умов
                    if (window.consignmentSyncTerms) window.consignmentSyncTerms();
                    openModal(document.getElementById('cons-reseller-modal'));
                });
        });
    }

    // ---------- Графіки ----------
    let chartData = {};
    try {
        chartData = JSON.parse(document.getElementById('cons-chart-data').textContent);
    } catch (e) { /* ignore */ }

    const chartOpts = {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#9aa4b8' } } },
        scales: {
            x: { ticks: { color: '#9aa4b8' }, grid: { color: 'rgba(255,255,255,0.05)' } },
            y: { ticks: { color: '#9aa4b8' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        },
    };

    if (window.Chart) {
        const pc = document.getElementById('consPaymentsChart');
        if (pc && (chartData.payments_by_month || []).length) {
            new Chart(pc.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: chartData.payments_by_month.map(x => x.month),
                    datasets: [{ label: 'Виплати', data: chartData.payments_by_month.map(x => x.amount),
                                 backgroundColor: '#34d399' }],
                },
                options: chartOpts,
            });
        }
        const sc = document.getElementById('consScheduleChart');
        if (sc && (chartData.schedule || []).length) {
            new Chart(sc.getContext('2d'), {
                type: 'line',
                data: {
                    labels: chartData.schedule.map(x => x.date),
                    datasets: [{ label: 'Очікувані виплати',
                                 data: chartData.schedule.map(x => parseFloat(x.amount) || 0),
                                 borderColor: '#6f95ff', backgroundColor: 'rgba(111,149,255,0.1)', fill: true }],
                },
                options: chartOpts,
            });
        }
    }
})();
