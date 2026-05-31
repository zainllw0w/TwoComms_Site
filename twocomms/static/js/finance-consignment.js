/**
 * Магазини під реалізацію (consignment) — фронтенд логіка.
 * Модалки створення/редагування магазину, поставки, виплати, продажу.
 */
(function () {
    'use strict';

    function getCookie(name) {
        const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
        return m ? m.pop() : '';
    }
    const CSRF = getCookie('csrftoken');

    function postJSON(url, data) {
        return fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
            body: JSON.stringify(data || {}),
        }).then(r => r.json());
    }

    function postForm(url, formData) {
        return fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': CSRF },
            body: formData,
        }).then(r => r.json());
    }

    let dropdowns = {};
    try {
        const el = document.getElementById('fin-dropdowns');
        if (el) dropdowns = JSON.parse(el.textContent);
    } catch (e) { /* ignore */ }

    // ---------- Модалка магазину ----------
    const modal = document.getElementById('cons-reseller-modal');

    function openModal(el) { if (el) el.hidden = false; }
    function closeModal(el) { if (el) el.hidden = true; }

    document.querySelectorAll('[data-cons-close]').forEach(btn => {
        btn.addEventListener('click', () => {
            const m = btn.closest('.fin-modal-overlay');
            closeModal(m);
        });
    });

    // Заповнити селект контрагентів
    function fillCounterparties(selectEl, selectedId) {
        if (!selectEl) return;
        const cps = dropdowns.counterparties || [];
        selectEl.innerHTML = '<option value="">— не вказано —</option>';
        cps.forEach(cp => {
            const opt = document.createElement('option');
            opt.value = cp.id;
            opt.textContent = cp.name;
            if (selectedId && cp.id === selectedId) opt.selected = true;
            selectEl.appendChild(opt);
        });
    }

    // Перемикання груп параметрів умов оплати
    function syncTermsGroups() {
        const kind = (document.getElementById('cons-terms-kind') || {}).value || 'installment';
        document.querySelectorAll('.fin-terms-group').forEach(g => {
            const kinds = (g.getAttribute('data-terms') || '').split(' ');
            g.hidden = !kinds.includes(kind);
        });
        document.querySelectorAll('[data-terms-only]').forEach(el => {
            el.style.display = (el.getAttribute('data-terms-only') === kind) ? '' : 'none';
        });
    }

    const termsKindEl = document.getElementById('cons-terms-kind');
    if (termsKindEl) termsKindEl.addEventListener('change', syncTermsGroups);
    window.consignmentSyncTerms = syncTermsGroups;

    function openResellerModal() {
        if (!modal) return;
        // Скидаємо у режим створення
        document.getElementById('cons-reseller-id').value = '';
        document.getElementById('cons-reseller-form').reset();
        const titleEl = document.getElementById('cons-reseller-modal-title');
        if (titleEl) titleEl.textContent = 'Новий магазин';
        fillCounterparties(document.getElementById('cons-reseller-cp'));
        syncTermsGroups();
        openModal(modal);
    }

    const addBtn = document.getElementById('cons-add-btn');
    if (addBtn) addBtn.addEventListener('click', openResellerModal);
    const addEmptyBtn = document.getElementById('cons-add-empty-btn');
    if (addEmptyBtn) addEmptyBtn.addEventListener('click', openResellerModal);

    // Збір terms з форми
    function collectTerms() {
        const kind = document.getElementById('cons-terms-kind').value;
        if (kind === 'onetime') {
            return { due_days: parseInt(document.getElementById('cons-due-days').value, 10) || 14 };
        }
        const terms = {
            period: document.getElementById('cons-period').value,
            every: parseInt(document.getElementById('cons-every').value, 10) || 1,
            anchor_day: parseInt(document.getElementById('cons-anchor').value, 10) || 5,
        };
        if (kind === 'installment') {
            const amount = document.getElementById('cons-amount').value;
            const periods = document.getElementById('cons-periods').value;
            terms.amount = amount || null;
            terms.periods = periods ? parseInt(periods, 10) : null;
        }
        return terms;
    }

    const form = document.getElementById('cons-reseller-form');
    if (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            const id = document.getElementById('cons-reseller-id').value;
            const payload = {
                name: document.getElementById('cons-reseller-name').value.trim(),
                counterparty_id: document.getElementById('cons-reseller-cp').value || null,
                status: document.getElementById('cons-reseller-status').value,
                terms_kind: document.getElementById('cons-terms-kind').value,
                terms: collectTerms(),
                contacts: {
                    phone: document.getElementById('cons-phone').value,
                    responsible: document.getElementById('cons-responsible').value,
                },
                notes: document.getElementById('cons-notes').value,
            };
            const url = id
                ? '/api/consignment/resellers/' + id + '/update/'
                : '/api/consignment/resellers/create/';
            postJSON(url, payload).then(res => {
                if (res.ok) {
                    location.reload();
                } else {
                    alert(res.error || 'Помилка збереження');
                }
            });
        });
    }

    // Експортуємо хелпери для detail-сторінки
    window.consignment = { postJSON, postForm, dropdowns, openModal, closeModal };
})();
