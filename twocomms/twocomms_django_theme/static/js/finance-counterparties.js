/* TwoComms Finance — розділ «Контрагенти»: створення/редагування/видалення. */
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

  var modal = document.getElementById('fin-cp-form-modal');
  var form = document.getElementById('fin-cp-form');
  if (!modal || !form) return;

  var els = {
    id: document.getElementById('fin-cp-id'),
    title: document.getElementById('fin-cp-form-title'),
    submit: document.getElementById('fin-cp-submit'),
    alert: document.getElementById('fin-cp-alert'),
    name: document.getElementById('fin-cp-name'),
    type: document.getElementById('fin-cp-type'),
    group: document.getElementById('fin-cp-group'),
    edrpou: document.getElementById('fin-cp-edrpou'),
    iban: document.getElementById('fin-cp-iban'),
    country: document.getElementById('fin-cp-country'),
    address: document.getElementById('fin-cp-address'),
    phone: document.getElementById('fin-cp-phone'),
    email: document.getElementById('fin-cp-email'),
    telegram: document.getElementById('fin-cp-telegram'),
    responsible: document.getElementById('fin-cp-responsible'),
    note: document.getElementById('fin-cp-note'),
  };

  function showAlert(msg) { els.alert.textContent = msg || ''; els.alert.hidden = !msg; }

  function setReqOpen(open) {
    var btn = document.getElementById('fin-cp-toggle-req');
    var wrap = document.getElementById('fin-cp-req-wrap');
    if (wrap) wrap.hidden = !open;
    if (btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  function openModal(cp) {
    form.reset();
    showAlert('');
    setReqOpen(false);
    if (cp) {
      els.id.value = cp.id;
      els.title.textContent = 'Редагувати контрагента';
      els.submit.textContent = 'Зберегти';
      els.name.value = cp.name || '';
      els.type.value = cp.type || 'client';
      els.group.value = cp.group || '';
      els.edrpou.value = cp.edrpou || '';
      els.iban.value = cp.iban || '';
      els.country.value = cp.country || '';
      els.address.value = cp.address || '';
      var c = cp.contacts || {};
      els.phone.value = c.phone || '';
      els.email.value = c.email || '';
      els.telegram.value = c.telegram || '';
      els.responsible.value = c.responsible || '';
      els.note.value = c.note || '';
      if (cp.iban || cp.address || c.phone || c.email) setReqOpen(true);
    } else {
      els.id.value = '';
      els.title.textContent = 'Новий контрагент';
      els.submit.textContent = 'Створити';
    }
    modal.hidden = false;
    document.body.classList.add('fin-modal-open');
    setTimeout(function () { els.name.focus(); }, 50);
  }

  function closeModal() {
    modal.hidden = true;
    document.body.classList.remove('fin-modal-open');
  }

  function collect() {
    return {
      name: els.name.value.trim(),
      type: els.type.value,
      group: els.group.value.trim(),
      edrpou: els.edrpou.value.trim(),
      iban: els.iban.value.trim(),
      country: els.country.value.trim(),
      address: els.address.value.trim(),
      contacts: {
        phone: els.phone.value.trim(),
        email: els.email.value.trim(),
        telegram: els.telegram.value.trim(),
        responsible: els.responsible.value.trim(),
        note: els.note.value.trim(),
      },
    };
  }

  // --- Події відкриття ---
  function bindOpen(id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener('click', function () { openModal(null); });
  }
  bindOpen('cp-add-btn');
  bindOpen('cp-add-empty-btn');

  document.querySelectorAll('[data-cp-edit]').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      var id = btn.getAttribute('data-cp-edit');
      api('/api/counterparties/' + id + '/get/').then(function (res) {
        if (res.data.ok) openModal(res.data.counterparty);
      });
    });
  });

  document.querySelectorAll('[data-cp-delete]').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      var id = btn.getAttribute('data-cp-delete');
      doDelete(id, false);
    });
  });

  function doDelete(id, force) {
    if (!force && !confirm('Видалити контрагента?')) return;
    api('/api/counterparties/' + id + '/delete/', 'POST', { force: force ? 1 : 0 }).then(function (res) {
      if (res.data.ok) {
        window.location.href = '/counterparties/';
      } else if (res.data.needs_force) {
        if (confirm(res.data.error)) doDelete(id, true);
      } else {
        alert(res.data.error || 'Помилка видалення');
      }
    });
  }

  // --- Закриття ---
  modal.querySelectorAll('[data-cpf-close]').forEach(function (b) { b.addEventListener('click', closeModal); });
  modal.addEventListener('click', function (e) { if (e.target === modal) closeModal(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !modal.hidden) closeModal(); });

  var reqToggle = document.getElementById('fin-cp-toggle-req');
  if (reqToggle) reqToggle.addEventListener('click', function () {
    var wrap = document.getElementById('fin-cp-req-wrap');
    setReqOpen(wrap && wrap.hidden);
  });

  // --- Збереження ---
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var payload = collect();
    if (!payload.name) { showAlert('Вкажіть назву контрагента'); return; }
    var id = els.id.value;
    var url = id ? '/api/counterparties/' + id + '/update/' : '/api/counterparties/create/';
    showAlert('');
    api(url, 'POST', payload).then(function (res) {
      if (res.ok && res.data.ok) {
        window.location.reload();
      } else {
        showAlert(res.data.error || 'Не вдалося зберегти');
      }
    }).catch(function () { showAlert('Помилка мережі'); });
  });
})();
