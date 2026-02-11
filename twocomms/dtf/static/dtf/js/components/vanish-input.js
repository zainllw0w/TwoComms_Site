/**
 * Vanish Input
 * - Invalid value: shake + dissolve + clear
 * - Cycling placeholders with focus/typing pause
 */
(function () {
  'use strict';

  var DTF = (window.DTF = window.DTF || {});
  var DEFAULT_CYCLE_DURATION = 3000;

  function parsePlaceholders(raw, fallback) {
    var values = [];
    if (raw) {
      try {
        values = JSON.parse(raw);
      } catch (err) {
        values = String(raw).split(',').map(function (item) { return item.trim(); });
      }
    }
    if (!Array.isArray(values)) values = [];
    values = values
      .map(function (item) { return String(item || '').trim(); })
      .filter(Boolean);
    if (!values.length && fallback) values.push(String(fallback));
    return values;
  }

  function collectFields(scope) {
    var root = scope || document;
    var fields = [];
    if (root.matches && root.matches('[data-vanish-input]')) fields.push(root);
    if (root.querySelectorAll) fields.push.apply(fields, root.querySelectorAll('[data-vanish-input]'));
    return fields;
  }

  function ensureWrapper(field) {
    var wrapper = field.parentElement && field.parentElement.classList.contains('vanish-field-wrap')
      ? field.parentElement
      : null;
    if (!wrapper) {
      wrapper = document.createElement('span');
      wrapper.className = 'vanish-field-wrap';
      field.parentNode.insertBefore(wrapper, field);
      wrapper.appendChild(field);
    }

    var overlay = wrapper.querySelector('.vanish-placeholder');
    if (!overlay) {
      overlay = document.createElement('span');
      overlay.className = 'vanish-placeholder';
      overlay.setAttribute('aria-hidden', 'true');
      wrapper.appendChild(overlay);
    }

    return { wrapper: wrapper, overlay: overlay };
  }

  function initVanishField(field) {
    if (!field || field.dataset.vanishInit === '1') return;
    field.dataset.vanishInit = '1';

    var listeners = [];
    var timers = [];
    var cycleTimer = null;
    var isFocused = false;
    var isAnimating = false;
    var originalPlaceholder = field.getAttribute('placeholder') || '';
    var placeholders = parsePlaceholders(field.dataset.placeholders, originalPlaceholder);
    var placeholderIndex = 0;
    var cycleDuration = parseInt(field.dataset.cycleDuration || DEFAULT_CYCLE_DURATION, 10) || DEFAULT_CYCLE_DURATION;
    var nodes = ensureWrapper(field);
    var wrapper = nodes.wrapper;
    var overlay = nodes.overlay;

    if (placeholders.length) {
      field.setAttribute('placeholder', '');
      overlay.textContent = placeholders[0];
      overlay.hidden = !!field.value;
    }

    function on(el, eventName, handler, options) {
      el.addEventListener(eventName, handler, options || false);
      listeners.push([el, eventName, handler, options || false]);
    }

    function addTimer(timerId) {
      timers.push(timerId);
    }

    function clearTimers() {
      while (timers.length) {
        clearTimeout(timers.pop());
      }
    }

    function hasValue() {
      return String(field.value || '').length > 0;
    }

    function updateStateClasses() {
      wrapper.classList.toggle('is-focused', isFocused);
      wrapper.classList.toggle('has-value', hasValue());
      wrapper.classList.toggle('is-animating', isAnimating);
      if (overlay) overlay.hidden = hasValue();
    }

    function stopCycling() {
      if (!cycleTimer) return;
      clearInterval(cycleTimer);
      cycleTimer = null;
    }

    function canCycle() {
      return placeholders.length > 1
        && !isFocused
        && !hasValue()
        && !isAnimating
        && document.visibilityState !== 'hidden';
    }

    function swapPlaceholder(nextIndex) {
      if (!overlay || !placeholders.length) return;
      overlay.classList.remove('vanish-placeholder-out', 'vanish-placeholder-in');
      overlay.classList.add('vanish-placeholder-out');
      addTimer(window.setTimeout(function () {
        placeholderIndex = nextIndex;
        overlay.textContent = placeholders[placeholderIndex];
        overlay.classList.remove('vanish-placeholder-out');
        overlay.classList.add('vanish-placeholder-in');
        addTimer(window.setTimeout(function () {
          overlay.classList.remove('vanish-placeholder-in');
        }, 180));
      }, 170));
    }

    function startCycling() {
      if (!canCycle()) return;
      stopCycling();
      cycleTimer = window.setInterval(function () {
        if (!canCycle()) {
          stopCycling();
          return;
        }
        var next = (placeholderIndex + 1) % placeholders.length;
        swapPlaceholder(next);
      }, cycleDuration);
    }

    function syncPlaceholder() {
      updateStateClasses();
      if (placeholders.length && !hasValue() && !overlay.textContent) {
        overlay.textContent = placeholders[placeholderIndex];
      }
      if (canCycle()) startCycling();
      else stopCycling();
    }

    function playShakeOnly() {
      field.classList.remove('vanish-shake');
      void field.offsetWidth;
      field.classList.add('vanish-shake');
      addTimer(window.setTimeout(function () {
        field.classList.remove('vanish-shake');
      }, 320));
    }

    function playVanishAndClear() {
      if (isAnimating) return;
      if (!hasValue()) {
        playShakeOnly();
        return;
      }

      isAnimating = true;
      updateStateClasses();
      field.classList.remove('vanish-dissolve');
      field.classList.add('vanish-shake');

      addTimer(window.setTimeout(function () {
        field.classList.remove('vanish-shake');
        field.classList.add('vanish-dissolve');
        addTimer(window.setTimeout(function () {
          field.value = '';
          field.classList.remove('vanish-dissolve');
          isAnimating = false;
          syncPlaceholder();
        }, 320));
      }, 320));
    }

    on(field, 'focus', function () {
      isFocused = true;
      syncPlaceholder();
    });

    on(field, 'blur', function () {
      isFocused = false;
      syncPlaceholder();
    });

    on(field, 'input', function () {
      syncPlaceholder();
    });

    on(field, 'change', function () {
      syncPlaceholder();
    });

    on(field, 'invalid', function () {
      playVanishAndClear();
    });

    on(field, 'vanish', function () {
      playVanishAndClear();
    });

    on(document, 'visibilitychange', function () {
      if (document.visibilityState === 'hidden') stopCycling();
      else syncPlaceholder();
    });

    syncPlaceholder();

    field._vanishCleanup = function () {
      stopCycling();
      clearTimers();
      for (var i = 0; i < listeners.length; i += 1) {
        var item = listeners[i];
        item[0].removeEventListener(item[1], item[2], item[3]);
      }
      listeners.length = 0;
    };
  }

  function initVanishInput(root) {
    collectFields(root).forEach(initVanishField);
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('vanish-input', '[data-vanish-input], [data-effect~="vanish-input"]', initVanishInput);
  }
})();
