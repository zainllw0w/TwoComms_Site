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
            fd.append('debt_amount', document.getElementById('cons-ship-debt').value || 0);
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

    // ---------- Редагувати магазин (відкрити модалку з заповненням) ----------
    const editBtn = document.getElementById('cons-edit-btn');
    if (editBtn) {
        editBtn.addEventListener('click', () => {
            const addBtn = document.getElementById('cons-add-btn');
            // Перевикористовуємо модалку магазину (заповнення — з даних на сторінці).
            openModal(document.getElementById('cons-reseller-modal'));
            document.getElementById('cons-reseller-id').value = resellerId;
            document.getElementById('cons-reseller-modal-title').textContent = 'Редагувати магазин';
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
