/* TwoComms Finance — графіки звітів (Chart.js 4). */
(function () {
  'use strict';

  var POS = '#34d399', NEG = '#fb7185', LINE = '#ffb270';
  var PIE = ['#ff7e29', '#6f95ff', '#34d399', '#fb7185', '#f3a43d', '#a78bfa', '#22d3ee', '#facc15', '#fb923c', '#94a3b8'];
  var GRID = 'rgba(255,255,255,0.06)', TICK = '#9aa4b8';

  // Визначаємо чи це мобільний пристрій
  var isMobile = window.innerWidth <= 900;
  var isSmallMobile = window.innerWidth <= 640;

  function data() {
    try { return JSON.parse(document.getElementById('fin-chart-data').textContent); }
    catch (e) { return {}; }
  }

  function fmt(n) {
    var v = Math.round(Number(n) || 0);
    return v.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  function setDefaults() {
    if (!window.Chart) return;
    Chart.defaults.color = TICK;
    Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
    Chart.defaults.font.size = isMobile ? 11 : 12;
    Chart.defaults.plugins.legend.display = !isSmallMobile; // Ховаємо легенду на малих екранах
  }

  function seriesChart(d, posLabel, negLabel, netLabel) {
    var el = document.getElementById('fin-chart-series');
    if (!el || !window.Chart || !d.series) return;
    var labels = d.series.map(function (s) { return s.label; });
    var inData = d.series.map(function (s) { return s.in; });
    var outData = d.series.map(function (s) { return s.out; });
    var netData = d.series.map(function (s) { return (s.in || 0) - (s.out || 0); });

    new Chart(el, {
      data: {
        labels: labels,
        datasets: [
          { type: 'bar', label: posLabel, data: inData, backgroundColor: POS, borderRadius: isMobile ? 4 : 6, maxBarThickness: isMobile ? 24 : 34, order: 2 },
          { type: 'bar', label: negLabel, data: outData, backgroundColor: NEG, borderRadius: isMobile ? 4 : 6, maxBarThickness: isMobile ? 24 : 34, order: 2 },
          { type: 'line', label: netLabel, data: netData, borderColor: LINE, backgroundColor: LINE,
            borderWidth: isMobile ? 1.5 : 2, tension: 0.35, pointRadius: isMobile ? 2 : 3, pointBackgroundColor: LINE, order: 1, fill: false },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            display: !isSmallMobile,
            labels: {
              usePointStyle: true,
              boxWidth: isMobile ? 6 : 8,
              padding: isMobile ? 10 : 16,
              font: { size: isMobile ? 10 : 12 }
            }
          },
          tooltip: {
            enabled: true,
            callbacks: {
              label: function (c) { return c.dataset.label + ': ' + fmt(c.parsed.y) + ' ₴'; }
            },
            titleFont: { size: isMobile ? 11 : 12 },
            bodyFont: { size: isMobile ? 10 : 11 },
            padding: isMobile ? 8 : 10
          },
        },
        scales: {
          x: {
            ticks: {
              color: TICK,
              font: { size: isMobile ? 10 : 11 },
              maxRotation: isMobile ? 45 : 0,
              minRotation: isMobile ? 45 : 0
            },
            grid: { display: false }
          },
          y: {
            ticks: {
              color: TICK,
              font: { size: isMobile ? 10 : 11 },
              callback: function (v) { return fmt(v); }
            },
            grid: { color: GRID }
          },
        },
      },
    });
  }

  function donut(id, rows) {
    var el = document.getElementById(id);
    if (!el || !window.Chart || !rows || !rows.length) return;
    new Chart(el, {
      type: 'doughnut',
      data: {
        labels: rows.map(function (r) { return r.name; }),
        datasets: [{
          data: rows.map(function (r) { return r.total; }),
          backgroundColor: PIE,
          borderColor: 'rgba(11,14,20,0.6)',
          borderWidth: isMobile ? 1 : 2
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: isMobile ? '65%' : '62%',
        plugins: {
          legend: { display: false },
          tooltip: {
            enabled: true,
            callbacks: {
              label: function (c) { return c.label + ': ' + fmt(c.parsed) + ' ₴'; }
            },
            titleFont: { size: isMobile ? 11 : 12 },
            bodyFont: { size: isMobile ? 10 : 11 },
            padding: isMobile ? 8 : 10
          },
        },
      },
    });
  }

  window.FinanceCharts = {
    renderCashflow: function () {
      setDefaults();
      var d = data();
      seriesChart(d, 'Поступлення', 'Списання', 'Чистий потік');
      donut('fin-chart-income', d.income_by_category);
      donut('fin-chart-expense', d.expense_by_category);
    },
    renderPnl: function () {
      setDefaults();
      var d = data();
      seriesChart(d, 'Доходи', 'Витрати', 'Прибуток');
      donut('fin-chart-income', d.income_by_category);
      donut('fin-chart-expense', d.expense_by_category);
    },
  };
})();
