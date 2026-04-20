/**
 * CSS loading enhancement: flips preloaded stylesheets from rel=preload
 * to rel=stylesheet after load, removes body.loading class post-DOMReady.
 * Вынесено из inline <script> в base.html (Phase 2.2).
 * Dead code (60-line loadCSS IIFE helper) удалён 2026-04-20 — нигде не вызывался.
 */
(function () {
  // Применяем улучшения для всех preload CSS
  var preloadLinks = document.querySelectorAll('link[rel="preload"][as="style"]');
  preloadLinks.forEach(function (link) {
    link.addEventListener('load', function () {
      this.rel = 'stylesheet';
    });
  });

  // Убираем класс loading после загрузки CSS
  document.addEventListener('DOMContentLoaded', function () {
    setTimeout(function () {
      document.body.classList.remove('loading');
    }, 100);
  });
})();
