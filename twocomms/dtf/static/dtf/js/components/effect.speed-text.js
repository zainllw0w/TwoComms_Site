/**
 * Speed/Tremble Text — vibrate animation for speed messaging
 * "день в день", "швидко" — one-shot or on-hover trigger
 * Respects prefers-reduced-motion
 * Registered via DTF.registerEffect
 */
(function () {
  'use strict';
  var DTF = (window.DTF = window.DTF || {});

  function initSpeedText(node, ctx) {
    if (!node) return null;
    if (ctx && ctx.reducedMotion) {
      node.classList.add('speed-text-static');
      return null;
    }

    var mode = (node.dataset.speedMode || 'hover').toLowerCase(); /* hover | reveal | once */
    var intensity = parseFloat(node.dataset.speedIntensity || '1') || 1;
    var duration = parseInt(node.dataset.speedDuration || '600', 10) || 600;
    var listeners = [];
    var animating = false;
    var hasPlayed = false;

    function on(el, evt, fn, opts) {
      el.addEventListener(evt, fn, opts || false);
      listeners.push([el, evt, fn, opts || false]);
    }

    function startTremble() {
      if (animating) return;
      animating = true;
      node.classList.add('speed-text-active');
      node.style.setProperty('--speed-intensity', intensity);
      node.style.setProperty('--speed-duration', duration + 'ms');

      setTimeout(function () {
        node.classList.remove('speed-text-active');
        animating = false;
        hasPlayed = true;
      }, duration);
    }

    if (mode === 'hover') {
      on(node, 'mouseenter', startTremble);
      /* Touch support */
      on(node, 'touchstart', function () { startTremble(); }, { passive: true });
    } else if (mode === 'reveal' || mode === 'once') {
      /* One-shot on first viewport entry */
      if ('IntersectionObserver' in window) {
        var observer = new IntersectionObserver(function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting && !hasPlayed) {
              startTremble();
              observer.disconnect();
            }
          });
        }, { threshold: 0.5 });
        observer.observe(node);
      } else {
        /* Fallback: immediate */
        startTremble();
      }
    }

    node.classList.add('speed-text-ready');

    return function cleanup() {
      for (var i = 0; i < listeners.length; i++) {
        var l = listeners[i];
        l[0].removeEventListener(l[1], l[2], l[3]);
      }
      listeners.length = 0;
    };
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('speed-text', '[data-effect~="speed-text"]', initSpeedText);
  }
})();
