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
    mode: document.getElementById('fin-settle-mode'),
    paymentId: document.getElementById('fin-settle-payment-id'),
    amount: document.getElementById('fin-settle-amount'),
    amountLabel: document.getElementById('fin-settle-amount-label'),
    amountHint: document.getElementById('fin-settle-amount-hint'),
    account: document.getElementById('fin-settle-account'),
    accountLabel: document.getElementById('fin-settle-account-label'),
    date: document.getElementById('fin-settle-date'),
    summary: document.getElementById('fin-settle-summary'),
    cp: document.getElementById('fin-settle-cp'),
    title: document.getElementById('fin-settle-title'),
    alert: document.getElementById('fin-settle-alert'),
    submit: document.getElementById('fin-settle-submit'),
    modes: document.getElementById('fin-settle-modes'),
    modePick: document.getElementById('fin-settle-mode-pick'),
    paneNew: document.getElementById('fin-settle-pane-new'),
    panePick: document.getElementById('fin-settle-pane-pick'),
    candidates: document.getElementById('fin-settle-candidates'),
    candidatesEmpty: document.getElementById('fin-settle-candidates-empty'),
    period: document.getElementById('fin-settle-period'),
    remainder: document.getElementById('fin-settle-remainder'),
    fullHint: document.getElementById('fin-settle-full-hint'),
    remember: document.getElementById('fin-settle-remember'),
    rememberWrap: document.getElementById('fin-settle-remember-wrap'),
  };
  var settleCtx = null;   // контекст із сервера

  function openModal(el) { if (el) { el.hidden = false; document.body.classList.add('fin-modal-open'); } }
  function closeModal(el) { if (el) { el.hidden = true; document.body.classList.remove('fin-modal-open'); } }

  function fmtMoney(v) { return v; }

  function setMode(mode) {
    settleEls.mode.value = mode;
    var isPick = mode === 'pick_txn';
    settleEls.panePick.hidden = !isPick;
    settleEls.paneNew.hidden = isPick;
    if (settleEls.modes) {
      settleEls.modes.querySelectorAll('.fin-seg__btn').forEach(function (b) {
        b.classList.toggle('is-active', b.getAttribute('data-mode') === mode);
      });
    }
    if (!isPick) { settleEls.paymentId.value = ''; clearCandidateSelection(); }
    syncPeriod();
  }

  function clearCandidateSelection() {
    if (!settleEls.candidates) return;
    settleEls.candidates.querySelectorAll('.fin-cand.is-selected').forEach(function (c) {
      c.classList.remove('is-selected');
    });
  }

  function selectedAmount() {
    if (settleEls.mode.value === 'pick_txn') {
      var sel = settleEls.candidates.querySelector('.fin-cand.is-selected');
      return sel ? parseFloat(sel.getAttribute('data-amount')) : NaN;
    }
    return parseFloat(settleEls.amount.value);
  }

  function syncPeriod() {
    if (!settleCtx) return;
    var per = parseFloat(settleCtx.per_amount) || 0;
    var paid = selectedAmount();
    // Показуємо вибір «повністю/частково», якщо платимо менше за оцінку.
    var showPeriod = settleCtx.is_recurring || (!isNaN(paid) && paid < per);
    settleEls.period.hidden = !showPeriod;
    if (!isNaN(paid) && per > paid) {
      settleEls.remainder.textContent = (per - paid).toFixed(2);
    } else {
      settleEls.remainder.textContent = '0';
    }
    if (settleEls.fullHint) {
      settleEls.fullHint.textContent = settleCtx.is_recurring ? ' (наступний місяць)' : '';
    }
  }

  function renderCandidates(list) {
    settleEls.candidates.innerHTML = '';
    if (!list || !list.length) {
      settleEls.candidatesEmpty.hidden = false;
      return;
    }
    settleEls.candidatesEmpty.hidden = true;
    list.forEach(function (c) {
      var el = document.createElement('button');
      el.type = 'button';
      el.className = 'fin-cand';
      el.setAttribute('data-payment-id', c.id);
      el.setAttribute('data-amount', c.amount);
      var meta = [c.date, c.account_name].filter(Boolean).join(' · ');
      var tail = c.card_transfer_label ? ('<span class="fin-cand__card">' + c.card_transfer_label + '</span>') : '';
      el.innerHTML = '<span class="fin-cand__amt">' + c.amount_display + '</span>' +
        '<span class="fin-cand__meta">' + meta + '</span>' + tail;
      el.addEventListener('click', function () {
        clearCandidateSelection();
        el.classList.add('is-selected');
        settleEls.paymentId.value = c.id;
        syncPeriod();
      });
      settleEls.candidates.appendChild(el);
    });
  }

  function openSettle(card) {
    var txnId = card.getAttribute('data-next-txn');
    if (!txnId) return;
    settleEls.txnId.value = txnId;
    settleEls.alert.hidden = true;
    settleEls.paymentId.value = '';
    settleCtx = null;
    settleEls.summary.textContent = 'Завантаження…';
    settleEls.candidates.innerHTML = '';
    openModal(settleModal);

    api('/api/obligations/' + txnId + '/settle-context/').then(function (res) {
      if (!res.ok || !res.data.ok) { settleEls.summary.textContent = 'Не вдалося завантажити'; return; }
      settleCtx = res.data;
      var isIncome = settleCtx.ttype === 'income';
      settleEls.title.textContent = isIncome ? 'Підтвердити надходження' : 'Сплатити платіж';
      settleEls.accountLabel.textContent = isIncome ? 'Рахунок зарахування *' : 'Рахунок списання *';
      settleEls.summary.textContent = (settleCtx.title || '') + ' · ' +
        (settleCtx.estimated ? '≈ ' : '') + settleCtx.per_amount_display;
      if (settleCtx.counterparty) {
        settleEls.cp.hidden = false;
        settleEls.cp.textContent = '👤 ' + settleCtx.counterparty.name;
      } else { settleEls.cp.hidden = true; }

      // Сума.
      settleEls.amount.value = settleCtx.per_amount || '';
      settleEls.amountLabel.textContent = settleCtx.estimated ? 'Фактична сума *' : 'Сума';
      settleEls.amountHint.hidden = !settleCtx.estimated;

      // Рахунки (привʼязані до контрагента — першими).
      settleEls.account.innerHTML = '';
      (settleCtx.accounts || []).forEach(function (a) {
        var o = document.createElement('option');
        o.value = a.id; o.textContent = a.name + (a.linked ? ' 🔗' : '');
        settleEls.account.appendChild(o);
      });
      settleEls.date.value = todayISO();

      // Кандидати + режим за замовчуванням.
      renderCandidates(settleCtx.candidates);
      var hasCands = (settleCtx.candidates || []).length > 0;
      settleEls.modePick.disabled = !hasCands;
      setMode(hasCands ? 'pick_txn' : 'new_payment');

      // Запамʼятати картку — якщо є контрагент.
      settleEls.rememberWrap.hidden = !settleCtx.counterparty;
      settleEls.remember.checked = false;
    });
  }

  if (settleModal) {
    settleModal.querySelectorAll('[data-settle-close]').forEach(function (b) {
      b.addEventListener('click', function () { closeModal(settleModal); });
    });
    if (settleEls.modes) {
      settleEls.modes.addEventListener('click', function (e) {
        var b = e.target.closest('.fin-seg__btn');
        if (b && !b.disabled) setMode(b.getAttribute('data-mode'));
      });
    }
    if (settleEls.amount) settleEls.amount.addEventListener('input', syncPeriod);
    document.getElementById('fin-settle-form').addEventListener('submit', function (e) {
      e.preventDefault();
      var mode = settleEls.mode.value;
      var fullRadio = settleModal.querySelector('input[name="fin-settle-full"]:checked');
      var body = {
        mode: mode,
        full_period: (settleEls.period.hidden || !fullRadio) ? '1' : fullRadio.value,
        remember_card: settleEls.remember.checked ? '1' : '',
      };
      if (mode === 'pick_txn') {
        if (!settleEls.paymentId.value) {
          settleEls.alert.textContent = 'Оберіть платіж зі списку'; settleEls.alert.hidden = false; return;
        }
        body.payment_txn_id = settleEls.paymentId.value;
      } else {
        body.amount = settleEls.amount.value || '';
        body.account_id = settleEls.account.value || '';
        body.date = settleEls.date.value || '';
        if (!body.account_id) {
          settleEls.alert.textContent = 'Оберіть рахунок'; settleEls.alert.hidden = false; return;
        }
      }
      settleEls.submit.disabled = true;
      api('/api/obligations/' + settleEls.txnId.value + '/settle/', 'POST', body).then(function (res) {
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
    amountType: document.getElementById('fin-plan-amount-type'),
    frequency: document.getElementById('fin-plan-frequency'),
    interval: document.getElementById('fin-plan-interval'),
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
    // Прелоад поточного графіка правила, щоб редагування показувало реальний
    // стан, а зміна періодичності справді застосовувалась.
    if (planEls.amountType) planEls.amountType.value = card.getAttribute('data-estimated') === '1' ? '1' : '0';
    if (planEls.frequency) planEls.frequency.value = card.getAttribute('data-frequency') || 'monthly';
    if (planEls.interval) planEls.interval.value = card.getAttribute('data-interval') || '1';
    fillSelect(planEls.category, categoryItems(card.getAttribute('data-type')), 'Без категорії');
    fillSelect(planEls.counterparty, DROPDOWNS.counterparties || [], 'Без контрагента',
               card.getAttribute('data-counterparty-id'));
    planEls.endMode.value = card.getAttribute('data-end-mode') || 'never';
    planEls.endDate.value = card.getAttribute('data-end-date') || '';
    planEls.count.value = card.getAttribute('data-count') || '';
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
        amount_is_estimated: (planEls.amountType && planEls.amountType.value === '1') ? '1' : '0',
        frequency: planEls.frequency.value || '',
        interval: (planEls.interval && planEls.interval.value) || '1',
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
