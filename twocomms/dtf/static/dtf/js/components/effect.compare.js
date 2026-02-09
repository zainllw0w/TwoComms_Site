/**
 * Compare effect — before/after image slider
 * Modes: drag | hover | autoplay
 * ARIA slider semantics + keyboard support
 * Registered via DTF.registerEffect
 */
(function () {
  'use strict';
  var DTF = (window.DTF = window.DTF || {});

  function initCompare(node, ctx) {
    if (!node) return null;
    var range = node.querySelector('.compare-range');
    var media = node.querySelector('.compare-media');
    if (!range || !media) return null;

    var mode = (node.dataset.compareMode || 'drag').toLowerCase();
    var autoplayEnabled = node.dataset.autoplay === 'true' || mode === 'autoplay';
    var autoplayDuration = parseInt(node.dataset.autoplayDuration || '5000', 10) || 5000;
    var initialValue = parseInt(range.value || '50', 10) || 50;

    var dragging = false;
    var pointerId = null;
    var autoplayRaf = null;
    var autoplayRunning = false;
    var autoplayStart = 0;
    var autoplayDirection = 1;
    var autoplayValue = initialValue;
    var hoverActive = false;
    var listeners = [];
    var reducedMotion = ctx && ctx.reducedMotion;

    function clamp(v, min, max) { return Math.min(max, Math.max(min, v)); }

    function apply(value) {
      var pct = clamp(Math.round(Number(value) || 0), 0, 100);
      range.value = String(pct);
      range.setAttribute('aria-valuenow', String(pct));
      media.style.setProperty('--compare', pct + '%');
    }

    function on(el, evt, fn, opts) {
      el.addEventListener(evt, fn, opts || false);
      listeners.push([el, evt, fn, opts || false]);
    }

    function valueByX(clientX) {
      var rect = media.getBoundingClientRect();
      if (!rect.width) return Number(range.value || 50);
      return clamp((clientX - rect.left) / rect.width, 0, 1) * 100;
    }

    /* --- ARIA setup --- */
    range.setAttribute('role', 'slider');
    range.setAttribute('aria-valuemin', '0');
    range.setAttribute('aria-valuemax', '100');
    range.setAttribute('aria-valuenow', String(initialValue));
    if (!range.getAttribute('aria-label')) {
      range.setAttribute('aria-label', 'Compare slider');
    }

    /* --- Keyboard --- */
    on(range, 'keydown', function (e) {
      stopAutoplay();
      var step = e.shiftKey ? 10 : 2;
      var cur = parseInt(range.value || '50', 10);
      if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
        e.preventDefault();
        apply(cur - step);
      } else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
        e.preventDefault();
        apply(cur + step);
      } else if (e.key === 'Home') {
        e.preventDefault();
        apply(0);
      } else if (e.key === 'End') {
        e.preventDefault();
        apply(100);
      }
    });

    /* --- Range input --- */
    on(range, 'input', function () {
      stopAutoplay();
      apply(range.value);
    });

    /* --- Drag mode --- */
    function stopDrag() {
      dragging = false;
      pointerId = null;
      media.classList.remove('is-dragging');
    }

    if (mode === 'drag' || mode === 'autoplay') {
      if ('PointerEvent' in window) {
        on(media, 'pointerdown', function (e) {
          stopAutoplay();
          dragging = true;
          pointerId = e.pointerId;
          media.classList.add('is-dragging');
          if (media.setPointerCapture) media.setPointerCapture(e.pointerId);
          apply(valueByX(e.clientX));
        });
        on(media, 'pointermove', function (e) {
          if (!dragging) return;
          if (pointerId !== null && e.pointerId !== pointerId) return;
          apply(valueByX(e.clientX));
        });
        on(media, 'pointerup', stopDrag);
        on(media, 'pointercancel', stopDrag);
        on(media, 'lostpointercapture', stopDrag);
      }
    }

    /* --- Hover mode --- */
    if (mode === 'hover') {
      on(media, 'mouseenter', function () { hoverActive = true; stopAutoplay(); });
      on(media, 'mouseleave', function () {
        hoverActive = false;
        apply(initialValue);
      });
      on(media, 'mousemove', function (e) {
        if (!hoverActive) return;
        apply(valueByX(e.clientX));
      });
      /* Touch fallback for hover mode */
      on(media, 'touchstart', function (e) {
        stopAutoplay();
        hoverActive = true;
        if (e.touches && e.touches[0]) apply(valueByX(e.touches[0].clientX));
      }, { passive: true });
      on(media, 'touchmove', function (e) {
        if (!hoverActive) return;
        if (e.touches && e.touches[0]) apply(valueByX(e.touches[0].clientX));
      }, { passive: true });
      on(media, 'touchend', function () {
        hoverActive = false;
        apply(initialValue);
      });
    }

    /* --- Autoplay --- */
    function autoplayTick(timestamp) {
      if (!autoplayRunning) return;
      if (!autoplayStart) autoplayStart = timestamp;
      var elapsed = timestamp - autoplayStart;
      var progress = (elapsed % autoplayDuration) / autoplayDuration;
      /* Ping-pong between 20 and 80 */
      var t = Math.sin(progress * Math.PI * 2) * 0.5 + 0.5;
      autoplayValue = 20 + t * 60;
      apply(autoplayValue);
      autoplayRaf = requestAnimationFrame(autoplayTick);
    }

    function startAutoplay() {
      if (reducedMotion) return;
      if (autoplayRunning) return;
      autoplayRunning = true;
      autoplayStart = 0;
      autoplayRaf = requestAnimationFrame(autoplayTick);
      node.classList.add('compare-autoplay');
    }

    function stopAutoplay() {
      if (!autoplayRunning) return;
      autoplayRunning = false;
      if (autoplayRaf) {
        cancelAnimationFrame(autoplayRaf);
        autoplayRaf = null;
      }
      node.classList.remove('compare-autoplay');
    }

    if (autoplayEnabled && !reducedMotion) {
      startAutoplay();
      /* Stop on any user interaction */
      on(media, 'pointerdown', stopAutoplay);
      on(media, 'mouseenter', stopAutoplay);
      on(range, 'focus', stopAutoplay);
      on(range, 'input', stopAutoplay);
    }

    /* --- Pause on hover for autoplay --- */
    if (autoplayEnabled) {
      on(node, 'mouseenter', function () { if (autoplayRunning) stopAutoplay(); });
    }

    /* Apply initial */
    apply(initialValue);
    node.classList.add('compare-ready');

    /* --- Mobile fallback: add compare mode class --- */
    node.classList.add('compare-mode-' + mode);

    return function cleanup() {
      stopAutoplay();
      stopDrag();
      for (var i = 0; i < listeners.length; i++) {
        var l = listeners[i];
        l[0].removeEventListener(l[1], l[2], l[3]);
      }
      listeners.length = 0;
    };
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('compare', '[data-compare], [data-effect~="compare"]', initCompare);
  }
})();
