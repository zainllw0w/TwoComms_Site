/* TwoComms Finance — рахунки та інтеграції: додавання, QR-підключення, імпорт. */
(function () {
  'use strict';

  function csrf() { var m = document.cookie.match(/csrftoken=([^;]+)/); return m ? m[1] : ''; }
  function api(url, method, body) {
    return fetch(url, {
      method: method || 'GET',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf(), 'X-Requested-With': 'XMLHttpRequest' },
      body: body ? JSON.stringify(body) : undefined,
    }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); });
  }
  function show(el) { if (el) { el.hidden = false; document.body.classList.add('fin-modal-open'); } }
  function hide(el) { if (el) { el.hidden = true; document.body.classList.remove('fin-modal-open'); } }

  var ACCOUNTS = [];
  try { ACCOUNTS = JSON.parse(document.getElementById('fin-accounts-data').textContent); } catch (e) {}

  document.querySelectorAll('[data-fin-close]').forEach(function (b) {
    b.addEventListener('click', function () { hide(b.closest('.fin-modal-overlay')); });
  });
  document.querySelectorAll('.fin-modal-overlay').forEach(function (ov) {
    ov.addEventListener('click', function (e) { if (e.target === ov) hide(ov); });
  });

  // --- Додавання рахунку ---
  var addModal = document.getElementById('fin-addacc-modal');
  var methodCards = document.getElementById('fin-method-cards');
  var manualPane = document.getElementById('fin-manual-pane');
  var integPane = document.getElementById('fin-integration-pane');
  var addBtn = document.getElementById('fin-add-account-btn');

  function resetAddModal() {
    if (methodCards) methodCards.hidden = false;
    if (manualPane) manualPane.hidden = true;
    if (integPane) integPane.hidden = true;
  }
  if (addBtn) addBtn.addEventListener('click', function () { resetAddModal(); show(addModal); });
  document.querySelectorAll('[data-method]').forEach(function (card) {
    card.addEventListener('click', function () {
      methodCards.hidden = true;
      if (card.dataset.method === 'manual') manualPane.hidden = false;
      else integPane.hidden = false;
    });
  });
  document.querySelectorAll('[data-back-method]').forEach(function (b) {
    b.addEventListener('click', resetAddModal);
  });

  var manualForm = document.getElementById('fin-manual-pane');
  if (manualForm) manualForm.addEventListener('submit', function (e) {
    e.preventDefault();
    var alert = document.getElementById('fin-acc-alert');
    var name = document.getElementById('fin-acc-name').value.trim();
    if (!name) { alert.textContent = 'Вкажіть назву'; alert.hidden = false; return; }
    api('/api/accounts/create/', 'POST', {
      name: name,
      currency: document.getElementById('fin-acc-currency').value,
      type: document.getElementById('fin-acc-type').value,
      initial_balance: document.getElementById('fin-acc-initial').value || 0,
    }).then(function (res) {
      if (res.data.ok) window.location.reload();
      else { alert.textContent = res.data.error || 'Помилка'; alert.hidden = false; }
    });
  });

  // --- Фільтр провайдерів ---
  var integSearch = document.getElementById('fin-integ-search');
  var integCountry = document.getElementById('fin-integ-country');
  function filterProviders() {
    var q = (integSearch.value || '').toLowerCase();
    var c = integCountry.value;
    document.querySelectorAll('.fin-integ-item').forEach(function (it) {
      var okText = it.textContent.toLowerCase().indexOf(q) !== -1;
      var okCountry = c === 'all' || it.dataset.country === c;
      it.style.display = (okText && okCountry) ? '' : 'none';
    });
  }
  if (integSearch) integSearch.addEventListener('input', filterProviders);
  if (integCountry) integCountry.addEventListener('change', filterProviders);

  // --- QR-підключення ---
  var qrModal = document.getElementById('fin-qr-modal');
  var qrCanvas = document.getElementById('fin-qr-canvas');
  var qrStatus = document.getElementById('fin-qr-status');
  var qrSpinner = document.getElementById('fin-qr-spinner');
  var qrLink = document.getElementById('fin-qr-link');
  var qrFinish = document.getElementById('fin-qr-finish');
  var currentConn = null;
  var pollTimer = null;

  function drawQR(payload) {
    if (window.QRCode && qrCanvas) {
      window.QRCode.toCanvas(qrCanvas, payload, { width: 180, margin: 1 }, function () {});
    }
  }
  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(function () {
      if (!currentConn) return;
      api('/api/integrations/' + currentConn + '/status/').then(function (res) {
        var st = res.data.status;
        if (st === 'connecting') { qrSpinner.hidden = false; qrStatus.textContent = 'Підключення…'; }
        if (st === 'success') {
          clearInterval(pollTimer);
          qrSpinner.hidden = true;
          document.getElementById('fin-qr-box').hidden = true;
          qrStatus.hidden = true;
          fillQrAccounts();
          qrLink.hidden = false;
          qrFinish.hidden = false;
        }
      });
    }, 2000);
  }
  function fillQrAccounts() {
    var sel = document.getElementById('fin-qr-account');
    sel.innerHTML = '<option value="">Створити новий рахунок</option>';
    ACCOUNTS.forEach(function (a) {
      var o = document.createElement('option'); o.value = a.id; o.textContent = a.name; sel.appendChild(o);
    });
  }
  document.querySelectorAll('.fin-integ-item').forEach(function (it) {
    it.addEventListener('click', function () {
      api('/api/integrations/start/', 'POST', { provider: it.dataset.provider }).then(function (res) {
        if (!res.data.ok) return;
        currentConn = res.data.connection_id;
        hide(addModal);
        qrStatus.hidden = false; qrStatus.textContent = 'Для підключення відскануйте код';
        document.getElementById('fin-qr-box').hidden = false;
        qrLink.hidden = true; qrFinish.hidden = true; qrSpinner.hidden = true;
        drawQR(res.data.qr_payload);
        show(qrModal);
        startPolling();
      });
    });
  });
  var qrRefresh = document.getElementById('fin-qr-refresh');
  if (qrRefresh) qrRefresh.addEventListener('click', function () {
    if (!currentConn) return;
    api('/api/integrations/' + currentConn + '/refresh-qr/', 'POST').then(function (res) {
      if (res.data.ok) { drawQR(res.data.qr_payload); startPolling(); }
    });
  });
  var qrCancel = document.getElementById('fin-qr-cancel');
  if (qrCancel) qrCancel.addEventListener('click', function () {
    if (pollTimer) clearInterval(pollTimer);
    if (currentConn) api('/api/integrations/' + currentConn + '/cancel/', 'POST');
    hide(qrModal);
  });
  if (qrFinish) qrFinish.addEventListener('click', function () {
    var sel = document.getElementById('fin-qr-account');
    api('/api/integrations/' + currentConn + '/link/', 'POST', {
      account: sel.value || '',
      new_account_name: document.getElementById('fin-qr-newname').value || '',
      sync_from: document.getElementById('fin-qr-syncfrom').value || '',
    }).then(function (res) { if (res.data.ok) window.location.reload(); });
  });

  // --- Імпорт ---
  var importModal = document.getElementById('fin-import-modal');
  var importBtn = document.getElementById('fin-import-btn');
  function fillImportAccounts() {
    var sel = document.getElementById('fin-import-account');
    sel.innerHTML = '';
    ACCOUNTS.forEach(function (a) {
      var o = document.createElement('option'); o.value = a.id; o.textContent = a.name + ' (' + a.currency + ')'; sel.appendChild(o);
    });
  }
  if (importBtn) importBtn.addEventListener('click', function () { fillImportAccounts(); show(importModal); });
  var previewBtn = document.getElementById('fin-import-preview-btn');
  if (previewBtn) previewBtn.addEventListener('click', function () {
    var fileInput = document.getElementById('fin-import-file');
    var alert = document.getElementById('fin-import-alert');
    if (!fileInput.files.length) { alert.textContent = 'Оберіть файл'; alert.hidden = false; return; }
    alert.hidden = true;
    var fd = new FormData();
    fd.append('file', fileInput.files[0]);
    fetch('/api/import/preview/', { method: 'POST', headers: { 'X-CSRFToken': csrf() }, body: fd })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.ok) { alert.textContent = d.error || 'Помилка'; alert.hidden = false; return; }
        document.getElementById('fin-import-count').textContent = d.count;
        var list = document.getElementById('fin-import-preview-list');
        list.innerHTML = '';
        d.preview.forEach(function (row) {
          var div = document.createElement('div');
          div.className = 'fin-import-row' + (row.valid ? '' : ' is-invalid');
          div.innerHTML = '<span>' + row.date + '</span><span class="fin-import-row__amt fin-amount--' +
            (row.type === 'income' ? 'pos' : 'neg') + '">' + row.amount + '</span><span>' + (row.comment || '') + '</span>';
          list.appendChild(div);
        });
        document.getElementById('fin-import-preview').hidden = false;
        document.getElementById('fin-import-confirm-btn').disabled = false;
      });
  });
  var confirmBtn = document.getElementById('fin-import-confirm-btn');
  if (confirmBtn) confirmBtn.addEventListener('click', function () {
    api('/api/import/confirm/', 'POST', {
      account: document.getElementById('fin-import-account').value,
      apply_rules: document.getElementById('fin-import-rules').checked,
    }).then(function (res) {
      if (res.data.ok) {
        alert('Імпортовано: ' + res.data.created + ', пропущено дублів: ' + res.data.skipped + ', помилок: ' + res.data.errors);
        window.location.reload();
      } else { var a = document.getElementById('fin-import-alert'); a.textContent = res.data.error; a.hidden = false; }
    });
  });

  // --- Редагування / архів / видалення ---
  var editModal = document.getElementById('fin-editacc-modal');
  function accById(id) { return ACCOUNTS.find(function (a) { return String(a.id) === String(id); }); }
  document.querySelectorAll('[data-acc-edit]').forEach(function (b) {
    b.addEventListener('click', function () {
      var a = accById(b.dataset.accEdit);
      document.getElementById('fin-editacc-id').value = b.dataset.accEdit;
      document.getElementById('fin-editacc-name').value = a ? a.name : '';
      document.getElementById('fin-editacc-initial').value = a ? a.initial_balance : '';
      document.getElementById('fin-editacc-target').value = '';
      show(editModal);
    });
  });
  var editForm = document.getElementById('fin-editacc-form');
  if (editForm) editForm.addEventListener('submit', function (e) {
    e.preventDefault();
    var id = document.getElementById('fin-editacc-id').value;
    api('/api/accounts/' + id + '/update/', 'POST', {
      name: document.getElementById('fin-editacc-name').value,
      initial_balance: document.getElementById('fin-editacc-initial').value,
    }).then(function (res) { if (res.data.ok) window.location.reload(); });
  });
  var correctBtn = document.getElementById('fin-editacc-correct');
  if (correctBtn) correctBtn.addEventListener('click', function () {
    var id = document.getElementById('fin-editacc-id').value;
    var target = document.getElementById('fin-editacc-target').value;
    if (target === '') return;
    api('/api/accounts/' + id + '/correct/', 'POST', { target: target }).then(function (res) {
      if (res.data.ok) window.location.reload();
    });
  });
  document.querySelectorAll('[data-acc-archive]').forEach(function (b) {
    b.addEventListener('click', function () {
      var archived = b.dataset.archived === '1';
      api('/api/accounts/' + b.dataset.accArchive + '/archive/', 'POST', { archived: !archived })
        .then(function (res) { if (res.data.ok) window.location.reload(); });
    });
  });
  document.querySelectorAll('[data-acc-delete]').forEach(function (b) {
    b.addEventListener('click', function () {
      if (!confirm('Видалити рахунок?')) return;
      api('/api/accounts/' + b.dataset.accDelete + '/delete/', 'POST').then(function (res) {
        if (res.data.ok) window.location.reload(); else alert(res.data.error || 'Помилка');
      });
    });
  });

  // --- Drag-and-drop сортування ---
  var list = document.getElementById('fin-accounts-list');
  var dragEl = null;
  if (list) {
    list.querySelectorAll('.fin-acc-card').forEach(function (card) {
      card.addEventListener('dragstart', function () { dragEl = card; card.classList.add('is-dragging'); });
      card.addEventListener('dragend', function () {
        card.classList.remove('is-dragging'); dragEl = null;
        var order = Array.prototype.slice.call(list.querySelectorAll('.fin-acc-card'))
          .map(function (c) { return c.dataset.accountId; });
        api('/api/accounts/reorder/', 'POST', { order: order });
      });
    });
    list.addEventListener('dragover', function (e) {
      e.preventDefault();
      if (!dragEl) return;
      var after = null;
      list.querySelectorAll('.fin-acc-card:not(.is-dragging)').forEach(function (c) {
        var box = c.getBoundingClientRect();
        if (e.clientY > box.top + box.height / 2) after = c;
      });
      if (after && after.nextSibling) list.insertBefore(dragEl, after.nextSibling);
      else if (after) list.appendChild(dragEl);
      else list.insertBefore(dragEl, list.firstChild);
    });
  }
})();
