/* TwoComms Finance — графіки звітів (Chart.js). */
(function () {
  'use strict';

  var ACCENT = '#ff7e29', POS = '#34d399', NEG = '#fb7185', INFO = '#6f95ff';
  var PIE = ['#ff7e29', '#6f95ff', '#34d399', '#fb7185', '#f3a43d', '#a78bfa', '#22d3ee', '#facc15', '#fb923c', '#94a3b8'];
  var GRID = 'rgba(255,255,255,0.06)', TICK = '#9aa4b8';

  function data() {
    try { return JSON.parse(document.getElementById('fin-chart-data').textContent); }
    catch (e) { return {}; }
  }
  function baseOpts() {
    return { responsive: true, maintainAspectRatio: true,
      plugins: { legend: { labels: { color: TICK } } },
      scales: { x: { ticks: { color: TICK }, grid: { color: GRID } },
                y: { ticks: { color: TICK }, grid: { color: GRID } } } };
  }
  function pieOpts() {
    return { responsive: true, maintainAspectRatio: true,
      plugins: { legend: { position: 'right', labels: { color: TICK, boxWidth: 12 } } } };
  }

  function seriesChart(d, posLabel, negLabel) {
    var el = document.getElementById('fin-chart-series');
    if (!el || !window.Chart) return;
    var labels = d.series.map(function (s) { return s.label; });
    new Chart(el, {
      type: 'bar',
      data: { labels: labels, datasets: [
        { label: posLabel, data: d.series.map(function (s) { return s.in; }), backgroundColor: POS },
        { label: negLabel, data: d.series.map(function (s) { return s.out; }), backgroundColor: NEG },
      ] },
      options: baseOpts(),
    });
  }

  function pieChart(id, rows) {
    var el = document.getElementById(id);
    if (!el || !window.Chart || !rows || !rows.length) return;
    new Chart(el, {
      type: 'doughnut',
      data: { labels: rows.map(function (r) { return r.name; }),
              datasets: [{ data: rows.map(function (r) { return r.total; }), backgroundColor: PIE }] },
      options: pieOpts(),
    });
  }

  window.FinanceCharts = {
    renderCashflow: function () {
      var d = data();
      seriesChart(d, 'Поступлення', 'Списання');
      pieChart('fin-chart-income', d.income_by_category);
      pieChart('fin-chart-expense', d.expense_by_category);
    },
    renderPnl: function () {
      var d = data();
      seriesChart(d, 'Доходи', 'Витрати');
      pieChart('fin-chart-income', d.income_by_category);
      pieChart('fin-chart-expense', d.expense_by_category);
    },
  };
})();
