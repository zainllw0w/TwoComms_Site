/**
 * Compare effect
 * Modes: drag | hover | autoplay
 * Features: keyboard + ARIA, autoplay ping-pong, sparkles line, hover reset
 */
(function () {
  'use strict';
  var DTF = (window.DTF = window.DTF || {});

  function ensureSparkles(handle) {
    if (!handle || handle.querySelector('.compare-sparkles')) return;
    var wrap = document.createElement('span');
    wrap.className = 'compare-sparkles';
    for (var i = 0; i < 8; i += 1) {
      var spark = document.createElement('span');
      spark.className = 'compare-spark';
      spark.style.setProperty('--spark-i', String(i));
      spark.style.setProperty('--spark-y', String((i % 4) * 20 + 8) + '%');
      wrap.appendChild(spark);
    }
    handle.appendChild(wrap);
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function easeInOutQuad(value) {
    var t = clamp(Number(value) || 0, 0, 1);
    return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
  }

  function initCompare(node, ctx) {
    if (!node) return null;
    var range = node.querySelector('.compare-range');
    var media = node.querySelector('.compare-media');
    var handle = node.querySelector('.compare-handle');
    if (!range || !media) return null;

    var mode = (node.dataset.compareMode || 'drag').toLowerCase();
    var autoplayEnabled = node.dataset.autoplay === 'true' || mode === 'autoplay';
    var autoplayDuration = parseInt(node.dataset.autoplayDuration || '5000', 10) || 5000;
    var initialValue = parseInt(range.value || '50', 10) || 50;
    var reducedMotion = !!(ctx && ctx.reducedMotion);

    var dragging = false;
    var hoverActive = false;
    var pointerId = null;
    var listeners = [];
    var raf = null;
    var autoplayRunning = false;
    var autoplayStart = 0;
    var userStoppedAutoplay = false;

    function on(el, evt, fn, opts) {
      el.addEventListener(evt, fn, opts || false);
      listeners.push([el, evt, fn, opts || false]);
    }

    function apply(value) {
      var pct = clamp(Math.round(Number(value) || 0), 0, 100);
      range.value = String(pct);
      range.setAttribute('aria-valuenow', String(pct));
      media.style.setProperty('--compare', pct + '%');
    }

    function valueByX(clientX) {
      var rect = media.getBoundingClientRect();
      if (!rect.width) return Number(range.value || initialValue);
      return clamp((clientX - rect.left) / rect.width, 0, 1) * 100;
    }

    function stopDrag() {
      dragging = false;
      pointerId = null;
      media.classList.remove('is-dragging');
    }

    function stopAutoplay() {
      if (!autoplayRunning) return;
      autoplayRunning = false;
      if (raf) {
        cancelAnimationFrame(raf);
        raf = null;
      }
      node.classList.remove('compare-autoplay');
    }

    function stopAutoplayPermanently() {
      userStoppedAutoplay = true;
      stopAutoplay();
    }

    function canResumeAutoplay() {
      if (!autoplayEnabled || reducedMotion) return false;
      if (userStoppedAutoplay) return false;
      if (dragging || hoverActive) return false;
      if (document.hidden) return false;
      return true;
    }

    function autoplayTick(timestamp) {
      if (!autoplayRunning) return;
      if (!autoplayStart) autoplayStart = timestamp;
      var elapsed = timestamp - autoplayStart;
      var cycle = autoplayDuration * 2;
      var position = elapsed % cycle;
      var inForward = position <= autoplayDuration;
      var progress = inForward
        ? position / autoplayDuration
        : (position - autoplayDuration) / autoplayDuration;
      var eased = easeInOutQuad(progress);
      var percentage = inForward ? eased * 100 : (1 - eased) * 100;
      apply(percentage);
      raf = requestAnimationFrame(autoplayTick);
    }

    function startAutoplay() {
      if (!canResumeAutoplay() || autoplayRunning) return;
      autoplayRunning = true;
      autoplayStart = 0;
      node.classList.add('compare-autoplay');
      raf = requestAnimationFrame(autoplayTick);
    }

    ensureSparkles(handle);
    node.classList.add('compare-ready', 'compare-mode-' + mode);
    media.style.setProperty('--compare', initialValue + '%');
    media.style.cursor = (mode === 'drag' || mode === 'autoplay') ? 'grab' : 'col-resize';

    range.setAttribute('role', 'slider');
    range.setAttribute('aria-valuemin', '0');
    range.setAttribute('aria-valuemax', '100');
    range.setAttribute('aria-valuenow', String(initialValue));
    if (!range.getAttribute('aria-label')) {
      range.setAttribute('aria-label', 'Compare slider');
    }

    on(range, 'focus', function () {
      node.classList.add('compare-range-focus');
      stopAutoplay();
    });
    on(range, 'blur', function () {
      node.classList.remove('compare-range-focus');
      startAutoplay();
    });

    on(range, 'keydown', function (event) {
      var step = event.shiftKey ? 10 : 2;
      var current = parseInt(range.value || '50', 10);
      if (autoplayEnabled) stopAutoplayPermanently();
      if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') {
        event.preventDefault();
        apply(current - step);
      } else if (event.key === 'ArrowRight' || event.key === 'ArrowUp') {
        event.preventDefault();
        apply(current + step);
      } else if (event.key === 'Home') {
        event.preventDefault();
        apply(0);
      } else if (event.key === 'End') {
        event.preventDefault();
        apply(100);
      }
    });

    on(range, 'input', function () {
      if (autoplayEnabled) stopAutoplayPermanently();
      apply(range.value);
    });

    if ('PointerEvent' in window && (mode === 'drag' || mode === 'autoplay')) {
      on(media, 'pointerdown', function (event) {
        if (autoplayEnabled) stopAutoplayPermanently();
        dragging = true;
        pointerId = event.pointerId;
        media.classList.add('is-dragging');
        media.style.cursor = 'grabbing';
        if (media.setPointerCapture) media.setPointerCapture(event.pointerId);
        apply(valueByX(event.clientX));
      });
      on(media, 'pointermove', function (event) {
        if (!dragging) return;
        if (pointerId !== null && event.pointerId !== pointerId) return;
        apply(valueByX(event.clientX));
      });
      on(media, 'pointerup', function () {
        stopDrag();
        media.style.cursor = 'grab';
      });
      on(media, 'pointercancel', function () {
        stopDrag();
        media.style.cursor = 'grab';
      });
      on(media, 'lostpointercapture', function () {
        stopDrag();
        media.style.cursor = 'grab';
      });
    }

    if (mode === 'hover') {
      on(media, 'mouseenter', function () {
        hoverActive = true;
        stopAutoplay();
      });
      on(media, 'mousemove', function (event) {
        if (!hoverActive) return;
        apply(valueByX(event.clientX));
      });
      on(media, 'mouseleave', function () {
        hoverActive = false;
        apply(initialValue);
        startAutoplay();
      });
      on(media, 'touchstart', function () {
        if (autoplayEnabled) stopAutoplayPermanently();
      }, { passive: true });
    } else {
      on(media, 'mouseenter', function () {
        stopAutoplay();
      });
      on(media, 'mouseleave', function () {
        startAutoplay();
      });
    }

    on(document, 'visibilitychange', function () {
      if (document.hidden) stopAutoplay();
      else startAutoplay();
    });

    apply(initialValue);
    startAutoplay();

    return function cleanup() {
      stopAutoplay();
      stopDrag();
      for (var i = 0; i < listeners.length; i += 1) {
        var entry = listeners[i];
        entry[0].removeEventListener(entry[1], entry[2], entry[3]);
      }
      listeners.length = 0;
      node.classList.remove('compare-ready', 'compare-range-focus', 'compare-autoplay');
    };
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('compare', '[data-compare], [data-effect~="compare"]', initCompare);
  }
})();
