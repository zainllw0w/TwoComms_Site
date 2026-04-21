(function () {
  'use strict';

  if (!('serviceWorker' in navigator)) {
    return;
  }

  function isCurrentWorkerScript(scriptUrl) {
    if (!scriptUrl) {
      return false;
    }
    try {
      var url = new URL(scriptUrl, window.location.origin);
      return url.pathname === '/sw.js' || /\/sw(\.[^/]+)?\.js$/.test(url.pathname);
    } catch (_) {
      return false;
    }
  }

  window.addEventListener('load', function () {
    navigator.serviceWorker.getRegistrations()
      .then(function (registrations) {
        return Promise.all(registrations.map(function (registration) {
          var scriptUrl =
            (registration.active && registration.active.scriptURL) ||
            (registration.waiting && registration.waiting.scriptURL) ||
            (registration.installing && registration.installing.scriptURL) ||
            '';

          if (isCurrentWorkerScript(scriptUrl)) {
            return undefined;
          }
          return registration.unregister();
        }));
      })
      .catch(function () { /* no-op */ });
  });
})();
