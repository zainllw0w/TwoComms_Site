/* TwoComms Finance — розділ «Планові»: погашення, редагування плану, історія контрагента. */
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

  function opt(value, label, selected) {
    var o = document.createElement('option');
    o.value = value; o.textContent = label;
    if (selected) o.selected = true;
    return o;
  }
  function fillSelect(sel, items, placeholder, selectedId) {
    if (!sel) return;
    sel.innerHTML = '';
    if (placeholder) sel.appendChild(opt('', placeholder));
    (items || []).forEach(function (it) { sel.appendChild(opt(it.id, it.name, String(it.id) === String(selectedId))); });
  }
  function categoryItems(type) {
    return type === 'income' ? (DROPDOWNS.income_categories || []) : (DROPDOWNS.expense_categories || []);
  }
  function todayISO() { return new Date().toISOString().slice(0, 10); }

  // ---------------------------------------------------------------- Settle
  var settleModal = document.getElementById('fin-settle-modal');
  var settleEls = {
    txnId: document.getElementById('fin-settle-txn-id'),
    account: document.getElementById('fin-settle-account'),
    accountLabel: document.getElementById('fin-settle-account-label'),
    counterparty: document.getElementById('fin-settle-counterparty'),
    linkCp: document.getElementById('fin-settle-link-cp'),
    date: document.getElementById('fin-settle-date'),
    summary: document.getElementById('fin-settle-summary'),
    title: document.getElementById('fin-settle-title'),
    alert: document.getElementById('fin-settle-alert'),
    submit: document.getElementById('fin-settle-submit'),
  };

  function openModal(el) { if (el) { el.hidden = false; document.body.classList.add('fin-modal-open'); } }
  function closeModal(el) { if (el) { el.hidden = true; document.body.classList.remove('fin-modal-open'); } }

  function openSettle(card) {
    var txnId = card.getAttribute('data-next-txn');
    if (!txnId) return;
    var type = card.getAttribute('data-type');
    var title = card.getAttribute('data-title') || '';
    var amount = card.getAttribute('data-per-amount') || '';
    settleEls.txnId.value = txnId;
    settleEls.alert.hidden = true;
    settleEls.title.textContent = type === 'income' ? 'Підтвердити надходження' : 'Сплатити платіж';
    settleEls.accountLabel.textContent = type === 'income' ? 'Рахунок зарахування *' : 'Рахунок списання *';
    settleEls.summary.textContent = title + (amount ? ' · ' + amount : '');
    fillSelect(settleEls.account, DROPDOWNS.accounts || [], 'Оберіть рахунок');
    fillSelect(settleEls.counterparty, DROPDOWNS.counterparties || [], 'Без контрагента',
               card.getAttribute('data-counterparty-id'));
    settleEls.linkCp.checked = false;
    settleEls.date.value = todayISO();
    openModal(settleModal);
  }

  if (settleModal) {
    settleModal.querySelectorAll('[data-settle-close]').forEach(function (b) {
      b.addEventListener('click', function () { closeModal(settleModal); });
    });
    document.getElementById('fin-settle-form').addEventListener('submit', function (e) {
      e.preventDefault();
      var body = {
        account_id: settleEls.account.value || '',
        counterparty_id: settleEls.counterparty.value || '',
        date: settleEls.date.value || '',
        link_account_cp: settleEls.linkCp.checked ? '1' : '',
      };
      settleEls.submit.disabled = true;
      api('/api/transactions/' + settleEls.txnId.value + '/settle/', 'POST', body).then(function (res) {
        settleEls.submit.disabled = false;
        if (res.ok && res.data.ok) { window.location.reload(); }
        else { settleEls.alert.textContent = (res.data && res.data.error) || 'Помилка'; settleEls.alert.hidden = false; }
      }).catch(function () { settleEls.submit.disabled = false; settleEls.alert.textContent = 'Помилка мережі'; settleEls.alert.hidden = false; });
    });
  }

  // ---------------------------------------------------------------- Edit plan
  var planModal = document.getElementById('fin-plan-modal');
  var planEls = {
    ruleId: document.getElementById('fin-plan-rule-id'),
    title: document.getElementById('fin-plan-title'),
    amount: document.getElementById('fin-plan-amount'),
    frequency: document.getElementById('fin-plan-frequency'),
    category: document.getElementById('fin-plan-category'),
    counterparty: document.getElementById('fin-plan-counterparty'),
    endMode: document.getElementById('fin-plan-end-mode'),
    untilWrap: document.getElementById('fin-plan-until-wrap'),
    endDate: document.getElementById('fin-plan-end-date'),
    countWrap: document.getElementById('fin-plan-count-wrap'),
    count: document.getElementById('fin-plan-count'),
    alert: document.getElementById('fin-plan-alert'),
  };

  function syncPlanEnd() {
    if (!planEls.endMode) return;
    planEls.untilWrap.hidden = planEls.endMode.value !== 'until';
    planEls.countWrap.hidden = planEls.endMode.value !== 'count';
  }

  function openPlan(card) {
    var ruleId = card.getAttribute('data-rule-id');
    if (!ruleId) return;
    planEls.ruleId.value = ruleId;
    planEls.alert.hidden = true;
    planEls.title.value = card.getAttribute('data-title') || '';
    planEls.amount.value = card.getAttribute('data-per-amount') || '';
    fillSelect(planEls.category, categoryItems(card.getAttribute('data-type')), 'Без категорії');
    fillSelect(planEls.counterparty, DROPDOWNS.counterparties || [], 'Без контрагента',
               card.getAttribute('data-counterparty-id'));
    planEls.endMode.value = 'never';
    syncPlanEnd();
    openModal(planModal);
  }

  if (planModal) {
    planModal.querySelectorAll('[data-plan-close]').forEach(function (b) {
      b.addEventListener('click', function () { closeModal(planModal); });
    });
    if (planEls.endMode) planEls.endMode.addEventListener('change', syncPlanEnd);
    document.getElementById('fin-plan-form').addEventListener('submit', function (e) {
      e.preventDefault();
      var body = {
        title: planEls.title.value || '',
        amount: planEls.amount.value || '',
        frequency: planEls.frequency.value || '',
        category_id: planEls.category.value || '',
        counterparty_id: planEls.counterparty.value || '',
        end_mode: planEls.endMode.value || 'never',
        end_date: planEls.endDate.value || '',
        count: planEls.count.value || '',
      };
      api('/api/recurrence/' + planEls.ruleId.value + '/update/', 'POST', body).then(function (res) {
        if (res.ok && res.data.ok) { window.location.reload(); }
        else { planEls.alert.textContent = (res.data && res.data.error) || 'Помилка'; planEls.alert.hidden = false; }
      });
    });
  }

  // ---------------------------------------------------------------- Counterparty history
  var cpModal = document.getElementById('fin-cp-modal');
  function openCpHistory(cpId, name) {
    if (!cpId) return;
    document.getElementById('fin-cp-title').textContent = 'Історія: ' + (name || '');
    document.getElementById('fin-cp-totals').innerHTML = '<span class="fin-muted-cell">Завантаження…</span>';
    document.getElementById('fin-cp-accounts').innerHTML = '';
    document.getElementById('fin-cp-tx-body').innerHTML = '';
    openModal(cpModal);
    api('/api/counterparties/' + cpId + '/history/').then(function (res) {
      if (!res.ok || !res.data.ok) { document.getElementById('fin-cp-totals').textContent = 'Не вдалося завантажити'; return; }
      var d = res.data;
      var t = d.totals;
      document.getElementById('fin-cp-totals').innerHTML =
        '<div class="fin-cp-total"><span>Отримано</span><b class="is-pos">' + t.received + '</b></div>' +
        '<div class="fin-cp-total"><span>Сплачено</span><b class="is-neg">' + t.paid + '</b></div>' +
        '<div class="fin-cp-total"><span>Чисто</span><b>' + t.net + '</b></div>' +
        '<div class="fin-cp-total"><span>Заплановано ↑</span><b>' + t.planned_in + '</b></div>' +
        '<div class="fin-cp-total"><span>Заплановано ↓</span><b>' + t.planned_out + '</b></div>';
      document.getElementById('fin-cp-accounts').innerHTML = (d.accounts || []).map(function (a) {
        return '<span class="fin-cp-acc' + (a.linked ? ' is-linked' : '') + '">💳 ' + a.name + ' · ' + a.balance + (a.linked ? ' 🔗' : '') + '</span>';
      }).join('');
      document.getElementById('fin-cp-tx-body').innerHTML = (d.transactions || []).map(function (x) {
        return '<tr><td>' + (x.date || '') + '</td><td class="fin-amount--' + x.amount_class + '">' + x.amount_display +
          '</td><td>' + (x.account_name || '—') + '</td><td>' + x.status_display +
          (x.is_recurring ? ' ⟳' : '') + '</td><td>' + (x.comment || '') + '</td></tr>';
      }).join('') || '<tr><td colspan="5" class="fin-muted-cell">Операцій ще немає</td></tr>';
    });
  }
  if (cpModal) {
    cpModal.querySelectorAll('[data-cp-close]').forEach(function (b) {
      b.addEventListener('click', function () { closeModal(cpModal); });
    });
  }

  // ---------------------------------------------------------------- Delegation
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-act]');
    if (btn) {
      var card = btn.closest('.fin-oblig');
      var act = btn.getAttribute('data-act');
      if (act === 'settle') openSettle(card);
      else if (act === 'edit-plan') openPlan(card);
      else if (act === 'stop-rule') {
        if (confirm('Зупинити повторення та прибрати майбутні планові платежі?')) {
          api('/api/recurrence/' + btn.getAttribute('data-rule-id') + '/stop/', 'POST', { delete_future: '1' })
            .then(function (res) { if (res.ok && res.data.ok) window.location.reload(); });
        }
      }
      return;
    }
    var cpChip = e.target.closest('[data-cp-history]');
    if (cpChip) {
      var card2 = cpChip.closest('.fin-oblig');
      openCpHistory(card2.getAttribute('data-counterparty-id'), cpChip.textContent.replace('👤', '').trim());
    }
  });

  // Закриття модалок по кліку на бекдроп / Esc.
  [settleModal, planModal, cpModal].forEach(function (m) {
    if (!m) return;
    m.addEventListener('click', function (e) { if (e.target === m) closeModal(m); });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { closeModal(settleModal); closeModal(planModal); closeModal(cpModal); }
  });
})();
