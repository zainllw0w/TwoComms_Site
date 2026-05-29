/* TwoComms Finance — журнал платежів: модалки операцій, фільтри, масові дії.
   Працює поверх finance.js (бургер/сайдбар). */
(function () {
  'use strict';

  function csrf() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }

  function api(url, method, body) {
    return fetch(url, {
      method: method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf(),
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: body ? JSON.stringify(body) : undefined,
    }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); });
  }

  var DROPDOWNS = {};
  try { DROPDOWNS = JSON.parse(document.getElementById('fin-dropdowns').textContent); } catch (e) {}

  var modal = document.getElementById('fin-txn-modal');
  var form = document.getElementById('fin-txn-form');
  if (!modal || !form) return;

  var TYPE_LABELS = { income: 'Додати дохід', expense: 'Додати витрату', transfer: 'Додати переказ' };
  var ACCOUNT_LABELS = { income: 'На рахунок', expense: 'З рахунку', transfer: '' };
  var DATE_LABELS = { income: 'Фактична дата', expense: 'Дата списання', transfer: 'Дата переказу коштів' };

  var els = {
    type: document.getElementById('fin-txn-type'),
    status: document.getElementById('fin-txn-status'),
    id: document.getElementById('fin-txn-id'),
    account: document.getElementById('fin-txn-account'),
    from: document.getElementById('fin-txn-from'),
    to: document.getElementById('fin-txn-to'),
    amount: document.getElementById('fin-txn-amount'),
    currency: document.getElementById('fin-txn-currency'),
    toAmount: document.getElementById('fin-txn-to-amount'),
    toAmountWrap: document.getElementById('fin-to-amount-wrap'),
    category: document.getElementById('fin-txn-category'),
    counterparty: document.getElementById('fin-txn-counterparty'),
    date: document.getElementById('fin-txn-date'),
    agreement: document.getElementById('fin-txn-agreement'),
    project: document.getElementById('fin-txn-project'),
    comment: document.getElementById('fin-txn-comment'),
    submit: document.getElementById('fin-txn-submit'),
    similar: document.getElementById('fin-txn-similar'),
    alert: document.getElementById('fin-txn-alert'),
    accountLabel: document.getElementById('fin-account-label'),
    dateLabel: document.getElementById('fin-date-label'),
    editActions: document.getElementById('fin-edit-actions'),
    markActual: document.getElementById('fin-act-mark-actual'),
    tags: document.getElementById('fin-txn-tags'),
  };

  function opt(value, label, selected) {
    var o = document.createElement('option');
    o.value = value; o.textContent = label;
    if (selected) o.selected = true;
    return o;
  }

  function fillSelect(sel, items, opts) {
    opts = opts || {};
    sel.innerHTML = '';
    if (opts.placeholder) sel.appendChild(opt('', opts.placeholder));
    items.forEach(function (it) { sel.appendChild(opt(it.id, it.name)); });
  }

  function populateAccounts() {
    fillSelect(els.account, DROPDOWNS.accounts || []);
    fillSelect(els.from, DROPDOWNS.accounts || []);
    fillSelect(els.to, DROPDOWNS.accounts || []);
    fillSelect(els.project, DROPDOWNS.projects || [], { placeholder: 'Без проекта' });
    fillSelect(els.counterparty, DROPDOWNS.counterparties || [], { placeholder: 'Вказати' });
    syncCurrency();
    renderTags([]);
  }

  function categoryItems(type) {
    return type === 'income' ? (DROPDOWNS.income_categories || []) : (DROPDOWNS.expense_categories || []);
  }

  function syncCategory(type) {
    fillSelect(els.category, categoryItems(type), { placeholder: 'Вказати' });
  }

  function accountById(id) {
    return (DROPDOWNS.accounts || []).find(function (a) { return String(a.id) === String(id); });
  }

  function syncCurrency() {
    var type = els.type.value;
    var accId = type === 'transfer' ? els.from.value : els.account.value;
    var acc = accountById(accId);
    if (acc) els.currency.value = acc.currency;
    if (type === 'transfer') {
      var toAcc = accountById(els.to.value);
      var diff = acc && toAcc && acc.currency !== toAcc.currency;
      els.toAmountWrap.hidden = !diff;
    }
  }

  // --- Теги (мультивибір) ---
  function renderTags(selectedIds) {
    if (!els.tags) return;
    var sel = new Set((selectedIds || []).map(String));
    els.tags.innerHTML = '';
    (DROPDOWNS.tags || []).forEach(function (t) {
      var chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'fin-tag-toggle' + (sel.has(String(t.id)) ? ' is-on' : '');
      chip.dataset.id = t.id;
      chip.textContent = t.name;
      chip.addEventListener('click', function () { chip.classList.toggle('is-on'); });
      els.tags.appendChild(chip);
    });
  }
  function selectedTagIds() {
    if (!els.tags) return [];
    return Array.prototype.slice.call(els.tags.querySelectorAll('.fin-tag-toggle.is-on'))
      .map(function (c) { return c.dataset.id; });
  }

  function applyTypeVisibility(type) {
    modal.querySelectorAll('[data-show]').forEach(function (el) {
      var types = el.getAttribute('data-show').split(',');
      var show = types.indexOf(type) !== -1;
      el.hidden = !show;
      el.querySelectorAll('[data-field]').forEach(function (f) { f.disabled = !show; });
    });
    els.accountLabel.textContent = ACCOUNT_LABELS[type] || '';
    els.dateLabel.textContent = DATE_LABELS[type] || 'Дата';
    els.submit.textContent = els.id.value ? 'Зберегти зміни' : (TYPE_LABELS[type] || 'Додати');
    modal.querySelectorAll('.fin-txn-tab').forEach(function (tab) {
      tab.classList.toggle('active', tab.dataset.type === type);
    });
  }

  function setType(type) {
    els.type.value = type;
    syncCategory(type);
    applyTypeVisibility(type);
    syncCurrency();
  }

  function nowLocal() {
    var d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 16);
  }

  function showAlert(msg) {
    els.alert.textContent = msg; els.alert.hidden = !msg;
  }

  function openModal(type, txn) {
    form.reset();
    els.id.value = '';
    els.status.value = 'actual';
    showAlert('');
    populateAccounts();
    els.editActions.hidden = true;
    els.similar.hidden = false;
    els.date.value = nowLocal();

    if (txn) {
      // Режим редагування.
      els.id.value = txn.id;
      els.status.value = txn.status;
      setType(txn.type);
      els.amount.value = txn.amount;
      if (txn.type === 'transfer') {
        if (txn.account_id) els.from.value = txn.account_id;
        if (txn.to_account_id) els.to.value = txn.to_account_id;
        if (txn.to_amount) els.toAmount.value = txn.to_amount;
      } else {
        if (txn.account_id) els.account.value = txn.account_id;
        if (txn.category_id) els.category.value = txn.category_id;
        if (txn.counterparty_id) els.counterparty.value = txn.counterparty_id;
      }
      if (txn.date_actual) els.date.value = txn.date_actual;
      if (txn.date_agreement) els.agreement.value = txn.date_agreement;
      if (txn.project_id) els.project.value = txn.project_id;
      els.comment.value = txn.comment || '';
      renderTags((txn.tags || []).map(function (t) { return t.id; }));
      els.editActions.hidden = false;
      els.similar.hidden = true;
      els.markActual.hidden = txn.status !== 'planned';
      syncCurrency();
    } else {
      setType(type || 'income');
    }
    modal.hidden = false;
    document.body.classList.add('fin-modal-open');
  }

  function closeModal() {
    modal.hidden = true;
    document.body.classList.remove('fin-modal-open');
  }

  // Expose to shell quick-action buttons (finance.js calls FinanceModals.open).
  window.FinanceModals = { open: function (kind) { openModal(kind); } };

  // --- Збір payload ---
  function collectPayload() {
    var type = els.type.value;
    var p = {
      type: type,
      status: els.status.value,
      amount: els.amount.value,
      date_actual: els.date.value,
      comment: els.comment.value,
      project: els.project.value,
      tags: selectedTagIds().join(','),
    };
    if (els.agreement.value) p.date_agreement = els.agreement.value;
    if (type === 'transfer') {
      p.from_account = els.from.value;
      p.to_account = els.to.value;
      if (!els.toAmountWrap.hidden && els.toAmount.value) p.to_amount = els.toAmount.value;
    } else {
      p.account = els.account.value;
      p.currency = els.currency.value;
      p.category = els.category.value;
      p.counterparty = els.counterparty.value;
    }
    return p;
  }

  function save(keepOpen) {
    var id = els.id.value;
    var url = id ? '/api/transactions/' + id + '/update/' : '/api/transactions/create/';
    showAlert('');
    return api(url, 'POST', collectPayload()).then(function (res) {
      if (res.ok && res.data.ok) {
        if (keepOpen) {
          var type = els.type.value;
          form.reset(); els.id.value = ''; populateAccounts();
          els.date.value = nowLocal(); setType(type);
        } else {
          window.location.reload();
        }
      } else {
        showAlert(res.data.error || 'Не вдалося зберегти операцію');
      }
    }).catch(function () { showAlert('Помилка мережі'); });
  }

  // --- Події ---
  modal.querySelectorAll('.fin-txn-tab').forEach(function (tab) {
    tab.addEventListener('click', function () { if (!els.id.value) setType(tab.dataset.type); });
  });
  modal.querySelectorAll('[data-fin-close]').forEach(function (b) { b.addEventListener('click', closeModal); });
  modal.addEventListener('click', function (e) { if (e.target === modal) closeModal(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !modal.hidden) closeModal(); });

  els.account.addEventListener('change', syncCurrency);
  els.from.addEventListener('change', syncCurrency);
  els.to.addEventListener('change', syncCurrency);

  ['agreement', 'recurring', 'extra'].forEach(function (key) {
    var btn = document.getElementById('fin-toggle-' + key);
    var wrap = document.getElementById('fin-' + key + '-wrap');
    if (btn && wrap) btn.addEventListener('click', function () { wrap.hidden = !wrap.hidden; });
  });

  form.addEventListener('submit', function (e) { e.preventDefault(); save(false); });
  els.similar.addEventListener('click', function () { save(true); });

  // Швидке створення сутностей із дропдаунів.
  modal.querySelectorAll('[data-create]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var kind = btn.dataset.create;
      var name = prompt('Назва нового запису:');
      if (!name) return;
      var body = { kind: kind, name: name };
      if (kind === 'category') body.type = els.type.value;
      api('/api/entity/create/', 'POST', body).then(function (res) {
        if (res.ok && res.data.ok) {
          var listKey = { project: 'projects', counterparty: 'counterparties',
                          category: els.type.value === 'income' ? 'income_categories' : 'expense_categories' }[kind];
          (DROPDOWNS[listKey] = DROPDOWNS[listKey] || []).push({ id: res.data.id, name: res.data.name });
          if (kind === 'project') { fillSelect(els.project, DROPDOWNS.projects, { placeholder: 'Без проекта' }); els.project.value = res.data.id; }
          else if (kind === 'counterparty') { fillSelect(els.counterparty, DROPDOWNS.counterparties, { placeholder: 'Вказати' }); els.counterparty.value = res.data.id; }
          else { syncCategory(els.type.value); els.category.value = res.data.id; }
        }
      });
    });
  });

  // --- Дії редагування ---
  function withId(fn) { var id = els.id.value; if (id) fn(id); }
  var delBtn = document.getElementById('fin-act-delete');
  if (delBtn) delBtn.addEventListener('click', function () {
    if (!confirm('Видалити операцію?')) return;
    withId(function (id) { api('/api/transactions/' + id + '/delete/', 'POST').then(function () { window.location.reload(); }); });
  });
  var dupBtn = document.getElementById('fin-act-duplicate');
  if (dupBtn) dupBtn.addEventListener('click', function () {
    withId(function (id) { api('/api/transactions/' + id + '/duplicate/', 'POST').then(function () { window.location.reload(); }); });
  });
  var convBtn = document.getElementById('fin-act-convert');
  if (convBtn) convBtn.addEventListener('click', function () {
    withId(function (id) {
      var toId = prompt('ID рахунку отримувача:');
      if (!toId) return;
      api('/api/transactions/' + id + '/convert-transfer/', 'POST', { to_account: toId }).then(function (res) {
        if (res.data.ok) window.location.reload(); else showAlert(res.data.error || 'Помилка');
      });
    });
  });
  if (els.markActual) els.markActual.addEventListener('click', function () {
    withId(function (id) { api('/api/transactions/' + id + '/mark-actual/', 'POST').then(function () { window.location.reload(); }); });
  });

  // --- Клік по рядку → редагування ---
  document.querySelectorAll('.fin-row').forEach(function (row) {
    row.addEventListener('click', function (e) {
      if (e.target.closest('.fin-col-check')) return;
      var id = row.dataset.txnId;
      api('/api/transactions/' + id + '/').then(function (res) {
        if (res.data.ok) openModal(res.data.transaction.type, res.data.transaction);
      });
    });
  });

  // --- Період: показ діапазону ---
  var periodSel = document.getElementById('fin-period');
  var rangeWrap = document.getElementById('fin-custom-range');
  if (periodSel && rangeWrap) {
    periodSel.addEventListener('change', function () { rangeWrap.hidden = periodSel.value !== 'custom'; });
  }

  // --- Розгортання планових ---
  var plannedToggle = document.getElementById('fin-planned-toggle');
  var plannedTable = document.getElementById('fin-planned-table');
  if (plannedToggle && plannedTable) {
    plannedToggle.addEventListener('click', function () {
      var open = plannedTable.hidden;
      plannedTable.hidden = !open;
      plannedToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  // --- Масовий вибір ---
  var checkAll = document.getElementById('fin-check-all');
  var bulkbar = document.getElementById('fin-bulkbar');
  var bulkCount = document.getElementById('fin-bulk-count');
  function rowChecks() { return Array.prototype.slice.call(document.querySelectorAll('.fin-row-check')); }
  function selectedIds() { return rowChecks().filter(function (c) { return c.checked; }).map(function (c) { return c.value; }); }
  function refreshBulk() {
    var ids = selectedIds();
    if (bulkbar) bulkbar.hidden = ids.length === 0;
    if (bulkCount) bulkCount.textContent = ids.length;
  }
  if (checkAll) checkAll.addEventListener('change', function () {
    rowChecks().forEach(function (c) { c.checked = checkAll.checked; });
    refreshBulk();
  });
  rowChecks().forEach(function (c) { c.addEventListener('change', refreshBulk); });

  // Bulk-дії
  var bulkModal = document.getElementById('fin-bulk-modal');
  var bulkValue = document.getElementById('fin-bulk-value');
  var bulkLabel = document.getElementById('fin-bulk-label');
  var pendingBulk = null;
  function runBulk(action, value) {
    api('/api/transactions/bulk/', 'POST', { action: action, ids: selectedIds().join(','), value: value })
      .then(function (res) { if (res.data.ok) window.location.reload(); else alert(res.data.error || 'Помилка'); });
  }
  if (bulkbar) bulkbar.querySelectorAll('[data-bulk]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var action = btn.dataset.bulk;
      if (action === 'delete') { if (confirm('Видалити обрані операції?')) runBulk('delete'); return; }
      if (action === 'mark_actual') { runBulk('mark_actual'); return; }
      // Дії з вибором значення.
      pendingBulk = action;
      var map = { set_category: ['expense_categories', 'Категорія'], set_project: ['projects', 'Проект'],
                  set_counterparty: ['counterparties', 'Контрагент'], add_tag: ['tags', 'Тег'] };
      var conf = map[action];
      fillSelect(bulkValue, DROPDOWNS[conf[0]] || []);
      bulkLabel.textContent = conf[1];
      if (bulkModal) { bulkModal.hidden = false; document.body.classList.add('fin-modal-open'); }
    });
  });
  if (bulkModal) {
    bulkModal.querySelectorAll('[data-fin-close]').forEach(function (b) {
      b.addEventListener('click', function () { bulkModal.hidden = true; document.body.classList.remove('fin-modal-open'); });
    });
    var applyBtn = document.getElementById('fin-bulk-apply');
    if (applyBtn) applyBtn.addEventListener('click', function () {
      if (pendingBulk) runBulk(pendingBulk, bulkValue.value);
    });
  }

  // --- Розширений фільтр ---
  var filterBtn = document.getElementById('fin-advanced-filter-btn');
  var filterModal = document.getElementById('fin-filter-modal');
  function buildChecklist(container, items) {
    container.innerHTML = '';
    (items || []).forEach(function (it) {
      var lbl = document.createElement('label');
      lbl.innerHTML = '<input type="checkbox" value="' + it.id + '"> ' + it.name;
      container.appendChild(lbl);
    });
  }
  if (filterBtn && filterModal) {
    filterBtn.addEventListener('click', function () {
      filterModal.querySelectorAll('[data-multi]').forEach(function (c) {
        buildChecklist(c, DROPDOWNS[c.dataset.multi]);
      });
      filterModal.hidden = false; document.body.classList.add('fin-modal-open');
    });
    filterModal.querySelectorAll('[data-fin-close]').forEach(function (b) {
      b.addEventListener('click', function () { filterModal.hidden = true; document.body.classList.remove('fin-modal-open'); });
    });
    var filterForm = document.getElementById('fin-filter-form');
    if (filterForm) filterForm.addEventListener('submit', function () {
      filterModal.querySelectorAll('[data-multi]').forEach(function (c) {
        var ids = Array.prototype.slice.call(c.querySelectorAll('input:checked')).map(function (i) { return i.value; });
        document.getElementById('flt-' + c.dataset.multi).value = ids.join(',');
      });
      filterModal.querySelectorAll('[data-chips]').forEach(function (c) {
        var vals = Array.prototype.slice.call(c.querySelectorAll('input:checked')).map(function (i) { return i.value; });
        document.getElementById('flt-' + c.dataset.chips).value = vals.join(',');
      });
    });
    var resetBtn = document.getElementById('fin-filter-reset');
    if (resetBtn) resetBtn.addEventListener('click', function () {
      filterModal.querySelectorAll('input:checked').forEach(function (i) { i.checked = false; });
    });
  }
})();
