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
      if (it.dataset.provider === 'monobank') { hide(addModal); openMono(); return; }
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

  // --- Редагування рахунку: назва, баланс, іконка-картка, колір ---
  var editModal = document.getElementById('fin-editacc-modal');
  function accById(id) { return ACCOUNTS.find(function (a) { return String(a.id) === String(id); }); }

  var BANK_PRESETS = {};
  try { BANK_PRESETS = JSON.parse(document.getElementById('fin-bank-presets').textContent); } catch (e) {}

  // Поточний стан іконки в модалці.
  var iconState = { type: '', value: '', data: '', file: null, previewSrc: '' };

  var previewIcon = document.getElementById('fin-editacc-preview-icon');
  var previewName = document.getElementById('fin-editacc-preview-name');
  var nameInput = document.getElementById('fin-editacc-name');
  var colorPick = document.getElementById('fin-editacc-color');
  var colorHex = document.getElementById('fin-editacc-color-hex');
  var iconFileInput = document.getElementById('fin-editacc-icon-file');
  var iconRemoveBtn = document.getElementById('fin-editacc-icon-remove');

  function curColor() {
    var v = colorHex ? colorHex.value.trim() : '';
    return /^#[0-9a-fA-F]{6}$/.test(v) ? v : '';
  }
  function renderPreviewIcon() {
    if (!previewIcon) return;
    previewIcon.className = 'fin-acc-icon';
    previewIcon.removeAttribute('style');
    previewIcon.innerHTML = '';
    var t = iconState.type;
    if (t === 'emoji' && iconState.value) {
      previewIcon.classList.add('fin-acc-icon--emoji');
      previewIcon.textContent = iconState.value;
      previewIcon.hidden = false;
    } else if (t === 'bank' && BANK_PRESETS[iconState.value]) {
      var b = BANK_PRESETS[iconState.value];
      previewIcon.classList.add('fin-acc-icon--bank');
      previewIcon.style.background = b.bg; previewIcon.style.color = b.fg;
      previewIcon.textContent = b.label;
      previewIcon.hidden = false;
    } else if (t === 'image' && (iconState.previewSrc || iconState.data)) {
      previewIcon.classList.add('fin-acc-icon--image');
      var img = document.createElement('img');
      img.src = iconState.previewSrc || iconState.data; img.alt = '';
      previewIcon.appendChild(img);
      previewIcon.hidden = false;
    } else {
      previewIcon.hidden = true;
    }
  }
  function renderPreviewName() {
    if (!previewName) return;
    previewName.textContent = (nameInput && nameInput.value.trim()) || 'Назва рахунку';
    previewName.style.color = curColor() || '';
  }
  function setActiveTab(type) {
    document.querySelectorAll('[data-icon-tab]').forEach(function (t) {
      t.classList.toggle('is-active', t.dataset.iconTab === type);
    });
    document.querySelectorAll('[data-icon-pane]').forEach(function (p) {
      p.hidden = type === '' || p.dataset.iconPane !== type;
    });
  }
  function markActiveOption() {
    document.querySelectorAll('[data-icon-pick]').forEach(function (o) {
      o.classList.toggle('is-active',
        o.dataset.iconPick === iconState.type && o.dataset.value === iconState.value);
    });
  }
  function setIconType(type) {
    iconState.type = type;
    if (type !== 'image') { iconState.file = null; iconState.previewSrc = ''; }
    if (type === '') iconState.value = '';
    if (iconRemoveBtn) iconRemoveBtn.hidden = !(type === 'image' && (iconState.data || iconState.previewSrc));
    setActiveTab(type);
    markActiveOption();
    renderPreviewIcon();
  }

  document.querySelectorAll('[data-icon-tab]').forEach(function (t) {
    t.addEventListener('click', function () { setIconType(t.dataset.iconTab); });
  });
  document.querySelectorAll('[data-icon-pick]').forEach(function (o) {
    o.addEventListener('click', function () {
      iconState.type = o.dataset.iconPick;
      iconState.value = o.dataset.value;
      markActiveOption();
      renderPreviewIcon();
    });
  });
  if (iconFileInput) iconFileInput.addEventListener('change', function () {
    var f = iconFileInput.files && iconFileInput.files[0];
    if (!f) return;
    iconState.type = 'image'; iconState.value = ''; iconState.file = f;
    var reader = new FileReader();
    reader.onload = function () {
      iconState.previewSrc = reader.result;
      if (iconRemoveBtn) iconRemoveBtn.hidden = false;
      renderPreviewIcon();
    };
    reader.readAsDataURL(f);
  });
  if (iconRemoveBtn) iconRemoveBtn.addEventListener('click', function () {
    iconState.data = ''; iconState.file = null; iconState.previewSrc = '';
    if (iconFileInput) iconFileInput.value = '';
    setIconType('');
  });

  function markActiveColorSwatch() {
    var c = curColor();
    document.querySelectorAll('.fin-color-swatch').forEach(function (s) {
      s.classList.toggle('is-active', (s.dataset.color || '') === c);
    });
  }

  document.querySelectorAll('[data-acc-edit]').forEach(function (b) {
    b.addEventListener('click', function () {
      var a = accById(b.dataset.accEdit);
      document.getElementById('fin-editacc-id').value = b.dataset.accEdit;
      if (nameInput) nameInput.value = a ? a.name : '';
      document.getElementById('fin-editacc-initial').value = a ? a.initial_balance : '';
      document.getElementById('fin-editacc-target').value = '';
      var hex = (a && a.color) ? a.color : '';
      if (colorHex) colorHex.value = hex;
      if (colorPick) colorPick.value = /^#[0-9a-fA-F]{6}$/.test(hex) ? hex : '#e8edf7';
      iconState = {
        type: (a && a.icon_type) || '', value: (a && a.icon_value) || '',
        data: (a && a.icon_data) || '', file: null, previewSrc: '',
      };
      if (iconFileInput) iconFileInput.value = '';
      setActiveTab(iconState.type);
      markActiveOption();
      if (iconRemoveBtn) iconRemoveBtn.hidden = !(iconState.type === 'image' && iconState.data);
      markActiveColorSwatch();
      renderPreviewIcon();
      renderPreviewName();
      show(editModal);
    });
  });

  // Синхронізація color-picker ↔ hex ↔ свотчі ↔ передогляд
  if (colorPick && colorHex) {
    colorPick.addEventListener('input', function () {
      colorHex.value = colorPick.value; markActiveColorSwatch(); renderPreviewName();
    });
    colorHex.addEventListener('input', function () {
      if (/^#[0-9a-fA-F]{6}$/.test(colorHex.value)) colorPick.value = colorHex.value;
      markActiveColorSwatch(); renderPreviewName();
    });
  }
  document.querySelectorAll('.fin-color-swatch').forEach(function (s) {
    s.addEventListener('click', function () {
      var c = s.dataset.color || '';
      if (colorHex) colorHex.value = c;
      if (colorPick && /^#[0-9a-fA-F]{6}$/.test(c)) colorPick.value = c;
      markActiveColorSwatch(); renderPreviewName();
    });
  });
  if (nameInput) nameInput.addEventListener('input', renderPreviewName);
  var colorClear = document.getElementById('fin-editacc-color-clear');
  if (colorClear) colorClear.addEventListener('click', function () {
    if (colorHex) colorHex.value = '';
    markActiveColorSwatch(); renderPreviewName();
  });

  var editForm = document.getElementById('fin-editacc-form');
  if (editForm) editForm.addEventListener('submit', function (e) {
    e.preventDefault();
    var id = document.getElementById('fin-editacc-id').value;
    var fd = new FormData();
    fd.append('name', nameInput ? nameInput.value : '');
    fd.append('initial_balance', document.getElementById('fin-editacc-initial').value);
    fd.append('color', curColor());
    fd.append('icon_type', iconState.type);
    fd.append('icon_value', (iconState.type === 'bank' || iconState.type === 'emoji') ? iconState.value : '');
    if (iconState.type === 'image' && iconState.file) fd.append('icon_image', iconState.file);
    var btn = editForm.querySelector('button[type=submit]');
    if (btn) { btn.disabled = true; btn.textContent = 'Зберігаємо…'; }
    fetch('/api/accounts/' + id + '/update/', {
      method: 'POST',
      headers: { 'X-CSRFToken': csrf(), 'X-Requested-With': 'XMLHttpRequest' },
      body: fd,
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d.ok) { window.location.reload(); return; }
      if (btn) { btn.disabled = false; btn.textContent = 'Зберегти'; }
      alert(d.error || 'Помилка збереження');
    }).catch(function () {
      if (btn) { btn.disabled = false; btn.textContent = 'Зберегти'; }
      alert('Помилка мережі');
    });
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

  // --- Monobank: підключення за токеном ---
  var monoModal = document.getElementById('fin-mono-modal');
  var monoConn = null;
  function monoStep(id) {
    ['choose', 'token', 'accounts', 'progress'].forEach(function (s) {
      var el = document.getElementById('fin-mono-step-' + s);
      if (el) el.hidden = (s !== id);
    });
  }
  function openMono() { monoStep('choose'); show(monoModal); }
  document.querySelectorAll('[data-mono-mode]').forEach(function (b) {
    b.addEventListener('click', function () {
      if (b.dataset.monoMode === 'token') monoStep('token');
      else {
        // QR-режим використовує загальний потік інтеграцій monobank.
        hide(monoModal);
        api('/api/integrations/start/', 'POST', { provider: 'monobank' }).then(function (res) {
          if (!res.data.ok) return;
          currentConn = res.data.connection_id;
          qrStatus.hidden = false; qrStatus.textContent = 'Для підключення відскануйте код';
          document.getElementById('fin-qr-box').hidden = false;
          qrLink.hidden = true; qrFinish.hidden = true; qrSpinner.hidden = true;
          drawQR(res.data.qr_payload); show(qrModal); startPolling();
        });
      }
    });
  });
  document.querySelectorAll('[data-mono-back]').forEach(function (b) {
    b.addEventListener('click', function () { monoStep('choose'); });
  });

  var monoTokenForm = document.getElementById('fin-mono-step-token');
  if (monoTokenForm) monoTokenForm.addEventListener('submit', function (e) {
    e.preventDefault();
    var alert = document.getElementById('fin-mono-alert');
    var btn = document.getElementById('fin-mono-connect-btn');
    var token = document.getElementById('fin-mono-token').value.trim();
    if (!token) { alert.textContent = 'Введіть токен'; alert.hidden = false; return; }
    alert.hidden = true; btn.disabled = true; btn.textContent = 'Перевіряємо…';
    api('/api/integrations/mono/connect/', 'POST', { token: token }).then(function (res) {
      btn.disabled = false; btn.textContent = 'Підключити';
      if (!res.data.ok) { alert.textContent = res.data.error || 'Помилка'; alert.hidden = false; return; }
      document.getElementById('fin-mono-token').value = '';
      monoConn = res.data.connection.id;
      loadMonoAccounts();
    });
  });

  function loadMonoAccounts() {
    monoStep('accounts');
    var list = document.getElementById('fin-mono-acc-list');
    list.innerHTML = '<div class="fin-qr-spinner">Отримуємо рахунки…</div>';
    api('/api/integrations/mono/' + monoConn + '/accounts/').then(function (res) {
      if (!res.data.ok) { list.innerHTML = '<div class="fin-form-alert">' + (res.data.error || 'Помилка') + '</div>'; return; }
      list.innerHTML = '';
      res.data.accounts.forEach(function (a) {
        var row = document.createElement('label');
        row.className = 'fin-mono-acc';
        var biz = a.is_business ? '<span class="fin-badge fin-badge--biz">ФОП / бізнес</span>' : '<span class="fin-badge">особисте</span>';
        var linked = a.linked ? ' <span class="fin-badge">вже підключено</span>' : '';
        row.innerHTML = '<input type="checkbox" value="' + a.external_id + '"' + (a.linked ? ' disabled' : ' checked') + '>' +
          '<span class="fin-mono-acc__main"><b>' + a.label + '</b>' + biz + linked +
          '<small>' + a.balance + ' ' + a.currency + (a.iban ? ' · ' + a.iban : '') + '</small></span>';
        list.appendChild(row);
      });
      var client = document.getElementById('fin-mono-client');
      client.textContent = '';
    });
  }

  var monoLinkBtn = document.getElementById('fin-mono-link-btn');
  if (monoLinkBtn) monoLinkBtn.addEventListener('click', function () {
    var ids = Array.prototype.slice.call(
      document.querySelectorAll('#fin-mono-acc-list input[type=checkbox]:checked:not(:disabled)'))
      .map(function (c) { return c.value; });
    if (!ids.length) {
      var al = document.getElementById('fin-mono-acc-alert');
      al.textContent = 'Оберіть хоча б один рахунок'; al.hidden = false; return;
    }
    monoStep('progress');
    api('/api/integrations/mono/' + monoConn + '/link/', 'POST', {
      external_ids: ids,
      sync_from: document.getElementById('fin-mono-syncfrom').value || '',
    }).then(function (res) {
      if (res.data.ok) window.location.reload();
      else { monoStep('accounts'); var al = document.getElementById('fin-mono-acc-alert'); al.textContent = res.data.error || 'Помилка'; al.hidden = false; }
    });
  });

  // --- Monobank: налаштування підключень ---
  var monoSettingsModal = document.getElementById('fin-mono-settings-modal');
  var monoSettingsBtn = document.getElementById('fin-mono-settings-btn');

  function renderMonoSettings(conns) {
    var body = document.getElementById('fin-mono-settings-body');
    if (!conns.length) { body.innerHTML = '<div class="fin-empty-state"><p>Немає активних підключень monobank.</p></div>'; return; }
    body.innerHTML = '';
    conns.forEach(function (c) {
      var wrap = document.createElement('div');
      wrap.className = 'fin-mono-conn';
      var head = '<div class="fin-mono-conn__head"><b>' + (c.client_name || 'monobank') + '</b>' +
        '<span class="fin-badge">' + (c.token_mask || '') + '</span></div>' +
        '<div class="fin-mono-conn__meta">Остання синхронізація: ' + (c.last_sync_at || '—') +
        (c.error ? ' · <span class="fin-amount--neg">' + c.error + '</span>' : '') + '</div>';
      var accs = c.accounts.map(function (a) {
        return '<div class="fin-mono-acc-row" data-acc="' + a.id + '">' +
          '<span class="fin-mono-acc-row__name">' + a.name + ' <small>' + a.balance + ' ' + a.currency + '</small></span>' +
          '<label class="fin-chk" title="Бізнес-рахунок"><input type="checkbox" data-acc-biz="' + a.id + '"' + (a.is_business ? ' checked' : '') + '> бізнес</label>' +
          '<label class="fin-chk" title="Автосинхронізація"><input type="checkbox" data-acc-sync="' + a.id + '"' + (a.auto_sync ? ' checked' : '') + '> синк</label>' +
          '</div>';
      }).join('');
      var foot = '<div class="fin-modal-foot">' +
        '<button type="button" class="fin-btn fin-btn--ghost fin-btn--sm" data-mono-disconnect="' + c.id + '">Відключити</button>' +
        '<button type="button" class="fin-btn fin-btn--ghost fin-btn--sm" data-mono-add="' + c.id + '">+ Ще рахунок</button>' +
        '<button type="button" class="fin-btn fin-btn--primary fin-btn--sm" data-mono-sync="' + c.id + '">Синхронізувати</button>' +
        '</div>';
      wrap.innerHTML = head + '<div class="fin-mono-acc-rows">' + accs + '</div>' + foot;
      body.appendChild(wrap);
    });
    bindMonoSettingsEvents();
  }

  function bindMonoSettingsEvents() {
    document.querySelectorAll('[data-acc-biz]').forEach(function (cb) {
      cb.addEventListener('change', function () {
        api('/api/integrations/mono/account/' + cb.dataset.accBiz + '/settings/', 'POST', { is_business: cb.checked });
      });
    });
    document.querySelectorAll('[data-acc-sync]').forEach(function (cb) {
      cb.addEventListener('change', function () {
        api('/api/integrations/mono/account/' + cb.dataset.accSync + '/settings/', 'POST', { auto_sync: cb.checked });
      });
    });
    document.querySelectorAll('[data-mono-sync]').forEach(function (b) {
      b.addEventListener('click', function () {
        b.disabled = true; b.textContent = 'Синхронізуємо…';
        api('/api/integrations/mono/' + b.dataset.monoSync + '/sync/', 'POST', {}).then(function (res) {
          if (res.data.ok) window.location.reload();
          else { b.disabled = false; b.textContent = 'Синхронізувати'; alert(res.data.error || 'Помилка'); }
        });
      });
    });
    document.querySelectorAll('[data-mono-disconnect]').forEach(function (b) {
      b.addEventListener('click', function () {
        if (!confirm('Відключити monobank? Операції залишаться, синхронізація зупиниться.')) return;
        api('/api/integrations/mono/' + b.dataset.monoDisconnect + '/disconnect/', 'POST').then(function (res) {
          if (res.data.ok) window.location.reload();
        });
      });
    });
    document.querySelectorAll('[data-mono-add]').forEach(function (b) {
      b.addEventListener('click', function () { monoConn = b.dataset.monoAdd; hide(monoSettingsModal); loadMonoAccounts(); show(monoModal); });
    });
  }

  function loadMonoSettings() {
    show(monoSettingsModal);
    var body = document.getElementById('fin-mono-settings-body');
    body.innerHTML = '<div class="fin-qr-spinner">Завантаження…</div>';
    api('/api/integrations/mono/connections/').then(function (res) {
      if (res.data.ok) renderMonoSettings(res.data.connections);
    });
  }
  if (monoSettingsBtn) monoSettingsBtn.addEventListener('click', loadMonoSettings);

  // Показуємо кнопку «monobank», якщо є хоч одне підключення.
  api('/api/integrations/mono/connections/').then(function (res) {
    if (res.data.ok && res.data.connections.length && monoSettingsBtn) monoSettingsBtn.hidden = false;
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
