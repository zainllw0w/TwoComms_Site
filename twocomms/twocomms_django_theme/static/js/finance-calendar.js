/* TwoComms Finance — календар: вибір дня, деталізація, створення платежу з дня. */
(function () {
  'use strict';

  var panel = document.getElementById('fin-day-panel');
  if (!panel) return;
  var selectedDate = null;

  function api(url) {
    return fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json(); });
  }

  function fmtDate(iso) {
    var p = iso.split('-');
    return p[2] + '.' + p[1] + '.' + p[0];
  }

  function openDay(date) {
    selectedDate = date;
    var qs = window.location.search ? window.location.search.replace('?', '&') : '';
    api('/api/calendar/day/' + date + '/?_=' + Date.now() + qs).then(function (d) {
      if (!d.ok) return;
      document.getElementById('fin-day-title').textContent = 'День ' + fmtDate(date);
      document.getElementById('fin-day-start').textContent = d.start_balance;
      document.getElementById('fin-day-income').textContent = d.income;
      document.getElementById('fin-day-expense').textContent = d.expense;
      document.getElementById('fin-day-end').textContent = d.end_balance;
      var body = document.getElementById('fin-day-txns');
      var empty = document.getElementById('fin-day-empty');
      body.innerHTML = '';
      if (!d.transactions.length) { empty.hidden = false; }
      else {
        empty.hidden = true;
        d.transactions.forEach(function (t) {
          var tr = document.createElement('tr');
          tr.innerHTML = '<td>' + t.time + (t.is_planned ? ' <span class="fin-badge fin-badge--planned">план</span>' : '') + '</td>' +
            '<td class="fin-amount--' + t.amount_class + '">' + t.amount_display + '</td>' +
            '<td>' + t.account_name + '</td>' +
            '<td>' + (t.category || '—') + '</td>' +
            '<td>' + (t.counterparty || '—') + '</td>' +
            '<td>' + (t.comment || '') + '</td>';
          body.appendChild(tr);
        });
      }
      panel.hidden = false;
      panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
  }

  document.querySelectorAll('.fin-cal-cell[data-date]').forEach(function (cell) {
    cell.addEventListener('click', function () {
      document.querySelectorAll('.fin-cal-cell.is-selected').forEach(function (c) { c.classList.remove('is-selected'); });
      cell.classList.add('is-selected');
      openDay(cell.dataset.date);
    });
  });

  var closeBtn = document.getElementById('fin-day-close');
  if (closeBtn) closeBtn.addEventListener('click', function () { panel.hidden = true; });

  // Створення платежу з дня — відкриваємо модалку та підставляємо дату.
  document.querySelectorAll('[data-day-add]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (window.FinanceModals && selectedDate) {
        window.FinanceModals.open(btn.dataset.dayAdd);
        var dateInput = document.getElementById('fin-txn-date');
        if (dateInput) dateInput.value = selectedDate + 'T12:00';
      }
    });
  });
})();
