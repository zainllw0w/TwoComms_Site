/**
 * Service Worker cleanup: unregister legacy workers and clear caches.
 * Запускается один раз в сутки (локальный throttle через localStorage).
 * Вынесено из inline <script> в base.html (Phase 2.2) — ~1.4 KB экономии
 * на каждом HTML-ответе, плюс кэшируется статикой навсегда.
 */
(function () {
  'use strict';
  var CLEANUP_KEY = 'twcSwCleanupV1';
  var DAY_MS = 24 * 60 * 60 * 1000;
  var now = Date.now();

  try {
    var lastRun = parseInt(localStorage.getItem(CLEANUP_KEY) || '0', 10);
    if (Number.isFinite(lastRun) && now - lastRun < DAY_MS) {
      return;
    }
    localStorage.setItem(CLEANUP_KEY, String(now));
  } catch (err) {
    // Если localStorage недоступен, пытаемся выполнить очистку однократно
  }

  if (!('serviceWorker' in navigator)) {
    return;
  }

  window.addEventListener('load', function () {
    navigator.serviceWorker.getRegistrations()
      .then(function (registrations) {
        return Promise.all(registrations.map(function (registration) {
          return registration.unregister();
        }));
      })
      .catch(function () { /* no-op */ });

    if ('caches' in window) {
      caches.keys()
        .then(function (cacheNames) {
          return Promise.all(cacheNames.map(function (cacheName) {
            return caches.delete(cacheName);
          }));
        })
        .catch(function () { /* no-op */ });
    }
  });
})();
