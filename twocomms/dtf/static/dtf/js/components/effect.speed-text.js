/**
 * Speed / Tremble text
 * - Per-character vibration with stagger
 * - Modes: hover | reveal | once
 */
(function () {
  'use strict';

  var DTF = (window.DTF = window.DTF || {});

  function splitIntoChars(node, sourceText) {
    var text = String(sourceText || '').trim();
    node.innerHTML = '';
    var fragment = document.createDocumentFragment();
    var characters = Array.from(text);
    for (var i = 0; i < characters.length; i += 1) {
      var char = characters[i];
      var span = document.createElement('span');
      span.className = 'speed-char';
      if (char === ' ') {
        span.classList.add('speed-char-space');
        span.innerHTML = '&nbsp;';
      } else {
        span.textContent = char;
        span.setAttribute('data-char', char);
        span.style.setProperty('--char-delay', (Math.random() * 120 + i * 12).toFixed(0) + 'ms');
        span.style.setProperty('--char-shift', (0.55 + Math.random() * 0.9).toFixed(3));
        span.style.setProperty('--char-rot', (0.3 + Math.random() * 0.8).toFixed(3));
      }
      fragment.appendChild(span);
    }
    node.appendChild(fragment);
  }

  function initSpeedText(node, ctx) {
    if (!node) return null;
    if (node.dataset.speedInit === '1') return null;
    node.dataset.speedInit = '1';

    var reducedMotion = !!(ctx && ctx.reducedMotion);
    var mode = String(node.dataset.speedMode || 'hover').toLowerCase();
    var repeatReveal = String(node.dataset.speedRepeat || 'false').toLowerCase() === 'true';
    var intensity = parseFloat(node.dataset.speedIntensity || '1') || 1;
    var duration = parseInt(node.dataset.speedDuration || '680', 10) || 680;
    var listeners = [];
    var timer = null;
    var observer = null;
    var animating = false;
    var hasPlayed = false;
    var sourceText = node.dataset.speedSource || node.textContent || '';

    node.dataset.speedSource = sourceText;
    node.style.setProperty('--speed-intensity', intensity.toFixed(2));
    node.style.setProperty('--speed-duration', duration + 'ms');
    node.classList.add('speed-text-ready');
    node.setAttribute('aria-label', String(sourceText).trim());
    splitIntoChars(node, sourceText);

    if (reducedMotion) {
      node.classList.add('speed-text-static');
      return null;
    }

    function on(el, eventName, handler, options) {
      el.addEventListener(eventName, handler, options || false);
      listeners.push([el, eventName, handler, options || false]);
    }

    function clearTimer() {
      if (!timer) return;
      clearTimeout(timer);
      timer = null;
    }

    function triggerAnimation() {
      if (animating) return;
      if (mode === 'once' && hasPlayed) return;
      if (mode === 'reveal' && hasPlayed && !repeatReveal) return;

      clearTimer();
      animating = true;
      node.classList.remove('speed-text-active');
      void node.offsetWidth;
      node.classList.add('speed-text-active');

      timer = window.setTimeout(function () {
        node.classList.remove('speed-text-active');
        animating = false;
        hasPlayed = true;
      }, duration + 260);
    }

    if (mode === 'hover') {
      on(node, 'mouseenter', triggerAnimation);
      on(node, 'focusin', triggerAnimation);
      on(node, 'touchstart', triggerAnimation, { passive: true });
    } else if (mode === 'reveal' || mode === 'once') {
      if ('IntersectionObserver' in window) {
        observer = new IntersectionObserver(function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting) {
              triggerAnimation();
            } else if (mode === 'reveal' && repeatReveal) {
              hasPlayed = false;
            }
          });
        }, { threshold: 0.55 });
        observer.observe(node);
      } else {
        triggerAnimation();
      }
    } else {
      on(node, 'mouseenter', triggerAnimation);
    }

    return function cleanup() {
      clearTimer();
      if (observer && typeof observer.disconnect === 'function') observer.disconnect();
      for (var i = 0; i < listeners.length; i += 1) {
        var item = listeners[i];
        item[0].removeEventListener(item[1], item[2], item[3]);
      }
      listeners.length = 0;
    };
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('speed-text', '[data-effect~="speed-text"]', initSpeedText);
  }
})();
