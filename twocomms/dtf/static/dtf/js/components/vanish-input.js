/**
 * Vanish Input — invalid input shake + vanish + clear
 * Cycling placeholders that stop on focus/typing
 * Registered via DTF.registerEffect
 */
(function () {
  'use strict';
  var DTF = (window.DTF = window.DTF || {});

  var DEFAULT_CYCLE_DURATION = 3000;

  function initVanishInput(root) {
    var scope = root || document;
    var fields = [];
    if (scope.matches && scope.matches('[data-vanish-input]')) fields.push(scope);
    if (scope.querySelectorAll) fields.push.apply(fields, scope.querySelectorAll('[data-vanish-input]'));

    fields.forEach(function (field) {
      if (field.dataset.vanishInit === '1') return;
      field.dataset.vanishInit = '1';

      var listeners = [];
      var cycleTimer = null;
      var placeholders = [];
      var placeholderIndex = 0;
      var isFocused = false;
      var isTyping = false;

      function on(el, evt, fn, opts) {
        el.addEventListener(evt, fn, opts || false);
        listeners.push([el, evt, fn, opts || false]);
      }

      /* --- Placeholders cycling --- */
      var placeholderAttr = field.dataset.placeholders;
      if (placeholderAttr) {
        try {
          placeholders = JSON.parse(placeholderAttr);
        } catch (e) {
          placeholders = placeholderAttr.split(',').map(function (s) { return s.trim(); });
        }
      }

      var cycleDuration = parseInt(field.dataset.cycleDuration || DEFAULT_CYCLE_DURATION, 10) || DEFAULT_CYCLE_DURATION;

      function updatePlaceholder() {
        if (!placeholders.length) return;
        /* Animate out current placeholder */
        field.classList.add('vanish-placeholder-out');
        setTimeout(function () {
          placeholderIndex = (placeholderIndex + 1) % placeholders.length;
          field.setAttribute('placeholder', placeholders[placeholderIndex]);
          field.classList.remove('vanish-placeholder-out');
          field.classList.add('vanish-placeholder-in');
          setTimeout(function () {
            field.classList.remove('vanish-placeholder-in');
          }, 200);
        }, 200);
      }

      function startCycling() {
        if (isFocused || isTyping || !placeholders.length) return;
        stopCycling();
        cycleTimer = setInterval(updatePlaceholder, cycleDuration);
      }

      function stopCycling() {
        if (cycleTimer) {
          clearInterval(cycleTimer);
          cycleTimer = null;
        }
      }

      if (placeholders.length > 1) {
        field.setAttribute('placeholder', placeholders[0]);
        startCycling();
      }

      /* Stop cycling on focus */
      on(field, 'focus', function () {
        isFocused = true;
        stopCycling();
      });

      on(field, 'blur', function () {
        isFocused = false;
        isTyping = false;
        if (!field.value) {
          startCycling();
        }
      });

      /* Stop cycling on typing */
      on(field, 'input', function () {
        isTyping = field.value.length > 0;
        if (isTyping) {
          stopCycling();
        }
      });

      /* --- Invalid: shake + vanish + clear --- */
      function vanishClear() {
        /* 1. Shake animation */
        field.classList.add('vanish-shake');

        setTimeout(function () {
          /* 2. Vanish: dissolve the text */
          field.classList.remove('vanish-shake');
          field.classList.add('vanish-dissolve');

          setTimeout(function () {
            /* 3. Clear the field */
            field.value = '';
            field.classList.remove('vanish-dissolve');

            /* Restart cycling if placeholders exist */
            isTyping = false;
            if (placeholders.length > 1 && !isFocused) {
              startCycling();
            }
          }, 350);
        }, 400);
      }

      on(field, 'invalid', function (evt) {
        evt.preventDefault();
        vanishClear();
      });

      /* Also trigger on explicit data-vanish-trigger event */
      on(field, 'vanish', function () {
        vanishClear();
      });

      /* Cleanup */
      field._vanishCleanup = function () {
        stopCycling();
        for (var i = 0; i < listeners.length; i++) {
          var l = listeners[i];
          l[0].removeEventListener(l[1], l[2], l[3]);
        }
        listeners.length = 0;
      };
    });
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('vanish-input', initVanishInput);
  }
})();
