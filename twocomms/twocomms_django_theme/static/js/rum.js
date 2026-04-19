/**
 * RUM (Real User Monitoring) — Core Web Vitals beacon.
 *
 * Цель: собрать LCP / CLS / INP / FCP / TTFB / FID на реальных устройствах
 * пользователей и отправить одним navigator.sendBeacon() при скрытии вкладки
 * (visibilitychange=hidden) или на pagehide — без влияния на LCP/TBT.
 *
 * Принципы:
 *   - 0 зависимостей, ~3 KB минифицируется до ~1.5 KB.
 *   - Никакого polling, никаких setInterval. Только PerformanceObserver.
 *   - Отправка ОДИН раз за навигацию и только через beacon (не блокирует).
 *   - Если PerformanceObserver / sendBeacon отсутствуют — тихо no-op.
 *   - Не ломает ничего и не перехватывает существующие аналитические потоки.
 *
 * Endpoint: POST /api/rum/ (JSON body). Сервер пишет в logger 'storefront.rum'.
 */
(function () {
  'use strict';

  if (typeof window === 'undefined' || typeof document === 'undefined') return;
  // Не шлём beacon с preview/preload/prefetch (prerender2 обходит)
  if (document.prerendering) {
    document.addEventListener('prerenderingchange', init, { once: true });
    return;
  }
  init();

  function init() {
    var W = window;
    var PO = W.PerformanceObserver;
    var nav = W.navigator || {};
    var beaconFn = nav.sendBeacon ? nav.sendBeacon.bind(nav) : null;

    // Если нет ни PO, ни способов отправки — выходим тихо
    if (!PO && !W.performance) return;

    var metrics = {};
    var sent = false;
    // Сохраняем максимальный LCP (LCP может приходить несколько раз)
    var lcpValue = 0;
    // Сумма CLS (кроме сессионных окон — минимальная реализация)
    var clsValue = 0;
    var clsEntries = [];
    var sessionValue = 0;
    var sessionEntries = [];
    // Макс. длительность INP
    var inpValue = 0;

    // --- LCP ---
    try {
      new PO(function (list) {
        var entries = list.getEntries();
        for (var i = 0; i < entries.length; i++) {
          var e = entries[i];
          if (e && e.startTime > lcpValue) {
            lcpValue = Math.round(e.startTime);
          }
        }
        metrics.LCP = lcpValue;
      }).observe({ type: 'largest-contentful-paint', buffered: true });
    } catch (_) { }

    // --- CLS (session-window алгоритм, v4) ---
    try {
      new PO(function (list) {
        list.getEntries().forEach(function (entry) {
          if (entry.hadRecentInput) return;
          var firstEntry = sessionEntries[0];
          var lastEntry = sessionEntries[sessionEntries.length - 1];
          if (
            sessionValue &&
            lastEntry &&
            firstEntry &&
            entry.startTime - lastEntry.startTime < 1000 &&
            entry.startTime - firstEntry.startTime < 5000
          ) {
            sessionValue += entry.value;
            sessionEntries.push(entry);
          } else {
            sessionValue = entry.value;
            sessionEntries = [entry];
          }
          if (sessionValue > clsValue) {
            clsValue = sessionValue;
            clsEntries = sessionEntries;
          }
        });
        metrics.CLS = Math.round(clsValue * 10000) / 10000;
      }).observe({ type: 'layout-shift', buffered: true });
    } catch (_) { }

    // --- INP (event) / FID fallback ---
    try {
      new PO(function (list) {
        list.getEntries().forEach(function (entry) {
          // INP = longest interaction duration
          if (entry.duration && entry.duration > inpValue) {
            inpValue = Math.round(entry.duration);
          }
          // FID = first input delay (до первого кадра)
          if (entry.entryType === 'first-input' && metrics.FID == null) {
            metrics.FID = Math.round(entry.processingStart - entry.startTime);
          }
        });
        metrics.INP = inpValue;
      }).observe({ type: 'event', buffered: true, durationThreshold: 16 });
    } catch (_) { }
    // First-input отдельным observer (если браузер не поддерживает 'event')
    try {
      new PO(function (list) {
        list.getEntries().forEach(function (entry) {
          if (metrics.FID == null) {
            metrics.FID = Math.round(entry.processingStart - entry.startTime);
          }
        });
      }).observe({ type: 'first-input', buffered: true });
    } catch (_) { }

    // --- FCP / TTFB (через Navigation & Paint API) ---
    try {
      new PO(function (list) {
        list.getEntries().forEach(function (entry) {
          if (entry.name === 'first-contentful-paint') {
            metrics.FCP = Math.round(entry.startTime);
          }
        });
      }).observe({ type: 'paint', buffered: true });
    } catch (_) { }

    try {
      var navEntries = W.performance && W.performance.getEntriesByType
        ? W.performance.getEntriesByType('navigation')
        : [];
      if (navEntries && navEntries[0]) {
        var ne = navEntries[0];
        metrics.TTFB = Math.round(ne.responseStart);
      }
    } catch (_) { }

    // --- Отправка ---
    function send() {
      if (sent) return;
      sent = true;

      var connection = nav.connection || nav.mozConnection || nav.webkitConnection;
      var payload = {
        url: location.href.slice(0, 200),
        nav_type: (function () {
          try {
            var navEntries = W.performance.getEntriesByType('navigation');
            return (navEntries && navEntries[0] && navEntries[0].type) || 'navigate';
          } catch (_) { return 'navigate'; }
        })(),
        device_class: (function () {
          try { return document.documentElement.dataset.deviceClass || ''; }
          catch (_) { return ''; }
        })(),
        conn: (connection && connection.effectiveType) || 'unknown',
        metrics: metrics,
        ua_mobile: !!(nav.userAgentData && nav.userAgentData.mobile)
      };

      var body = '';
      try { body = JSON.stringify(payload); } catch (_) { return; }

      // Предпочитаем sendBeacon (не блокирует unload)
      if (beaconFn) {
        try {
          var blob = new Blob([body], { type: 'application/json' });
          if (beaconFn('/api/rum/', blob)) return;
        } catch (_) { }
      }
      // Fallback: keepalive fetch
      try {
        W.fetch('/api/rum/', {
          method: 'POST',
          body: body,
          keepalive: true,
          credentials: 'omit',
          headers: { 'Content-Type': 'application/json' }
        }).catch(function () { });
      } catch (_) { }
    }

    // visibilitychange → hidden — основной триггер (Web Vitals best practice)
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'hidden') send();
    }, { capture: true });
    // pagehide — страховка для Safari (не всегда стреляет visibilitychange)
    W.addEventListener('pagehide', send, { capture: true });
  }
})();
