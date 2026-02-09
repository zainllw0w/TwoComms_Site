/**
 * Multi-step Loader — real preflight step display
 * Integrates with backend preflight step_items
 * No fake delays: sync-first, honest UX
 * Shows PASS/WARN/FAIL per step, stops chain on FAIL
 * Registered via DTF.registerEffect
 */
(function () {
  'use strict';
  var DTF = (window.DTF = window.DTF || {});

  var STATUS_ICONS = {
    ok: '\u2713',     /* ✓ */
    pass: '\u2713',
    warn: '\u26A0',   /* ⚠ */
    fail: '\u2717',   /* ✗ */
    loading: '\u21BB', /* ↻ */
    pending: '\u2022', /* • */
  };

  var STEP_LABELS = {
    format_signature: { uk: 'Формат / сигнатура', ru: 'Формат / сигнатура', en: 'Format / signature' },
    dpi: { uk: 'DPI', ru: 'DPI', en: 'DPI' },
    physical_size_60cm: { uk: 'Розміри / 60 см', ru: 'Размеры / 60 см', en: 'Physical size / 60 cm' },
    transparency_bounds: { uk: 'Прозорість / межі', ru: 'Прозрачность / границы', en: 'Transparency / bounds' },
    tiny_lines: { uk: 'Тонкі лінії', ru: 'Тонкие линии', en: 'Tiny lines risk' },
    summary: { uk: 'Підсумок', ru: 'Итог', en: 'Summary' },
  };

  function getLang() {
    return ((document.documentElement.lang || 'uk').toLowerCase() || 'uk').slice(0, 2);
  }

  function stepLabel(key) {
    var lang = getLang();
    var labels = STEP_LABELS[key];
    if (labels) return labels[lang] || labels['uk'] || key;
    return key;
  }

  /**
   * Render preflight steps into a container
   * @param {HTMLElement} container - the loader container
   * @param {Array} stepItems - array from preflight engine step_items
   * @param {Object} options - { animated: true, onComplete: fn }
   */
  function renderSteps(container, stepItems, options) {
    if (!container || !stepItems) return;
    var opts = options || {};
    var animated = opts.animated !== false;
    var onComplete = opts.onComplete || null;

    container.innerHTML = '';
    container.classList.add('msl-active');
    var failReached = false;
    var currentDelay = 0;
    var STEP_DELAY = animated ? 180 : 0;

    stepItems.forEach(function (step, idx) {
      var el = document.createElement('div');
      el.className = 'msl-step';
      el.setAttribute('data-step-key', step.key || '');
      el.setAttribute('data-step-status', failReached ? 'skipped' : (step.status || 'pending'));

      var icon = document.createElement('span');
      icon.className = 'msl-step-icon';
      var statusKey = failReached ? 'pending' : (step.status || 'pending');
      icon.textContent = STATUS_ICONS[statusKey] || STATUS_ICONS.pending;
      icon.setAttribute('aria-hidden', 'true');

      var label = document.createElement('span');
      label.className = 'msl-step-label';
      label.textContent = stepLabel(step.key) || step.label || '';

      var msg = document.createElement('span');
      msg.className = 'msl-step-message';
      msg.textContent = failReached ? '' : (step.message || '');

      var value = document.createElement('span');
      value.className = 'msl-step-value';
      value.textContent = (step.value || '');

      el.appendChild(icon);
      el.appendChild(label);
      el.appendChild(msg);
      if (step.value) el.appendChild(value);

      /* Status class */
      if (!failReached) {
        el.classList.add('msl-status-' + (step.status || 'pending'));
      } else {
        el.classList.add('msl-status-skipped');
      }

      /* Recommendations for summary step */
      if (step.key === 'summary' && step.recommendations && step.recommendations.length) {
        var recList = document.createElement('ul');
        recList.className = 'msl-recommendations';
        step.recommendations.forEach(function (rec) {
          var li = document.createElement('li');
          li.textContent = rec;
          recList.appendChild(li);
        });
        el.appendChild(recList);
      }

      if (animated) {
        el.style.opacity = '0';
        el.style.transform = 'translateY(6px)';
        setTimeout(function () {
          el.style.transition = 'opacity 220ms ease, transform 220ms ease';
          el.style.opacity = '1';
          el.style.transform = 'translateY(0)';
        }, currentDelay);
        currentDelay += STEP_DELAY;
      }

      container.appendChild(el);

      /* Stop chain on FAIL */
      if (step.status === 'fail' && !failReached) {
        failReached = true;
      }
    });

    if (onComplete) {
      setTimeout(onComplete, currentDelay + 100);
    }
  }

  /**
   * Simple upload-step chip toggler (fallback for basic upload flow)
   */
  function setUploadStep(host, value) {
    var steps = host.querySelectorAll('[data-upload-step]');
    steps.forEach(function (stepNode) {
      var step = parseInt(stepNode.getAttribute('data-upload-step') || '0', 10);
      stepNode.classList.toggle('is-active', step === value);
      stepNode.classList.toggle('is-done', step < value);
    });
  }

  /**
   * Legacy init: basic upload flow with file change detection
   */
  function initMultiStepLoader(root) {
    var scope = root || document;
    var hosts = [];
    if (scope.matches && scope.matches('[data-upload-flow]')) hosts.push(scope);
    if (scope.querySelectorAll) hosts.push.apply(hosts, scope.querySelectorAll('[data-upload-flow]'));

    hosts.forEach(function (host) {
      if (host.dataset.mslInit === '1') return;
      host.dataset.mslInit = '1';

      var input = host.querySelector('input[type="file"]');
      var loaderContainer = host.querySelector('.msl-container');

      setUploadStep(host, 1);

      if (input) {
        input.addEventListener('change', function () {
          if (!input.files || !input.files.length) {
            setUploadStep(host, 1);
            return;
          }
          setUploadStep(host, 2);

          /* Try to get preflight data if available from form submission */
          var preflightDataEl = host.querySelector('[data-preflight-steps]');
          if (preflightDataEl) {
            try {
              var stepItems = JSON.parse(preflightDataEl.textContent || '[]');
              if (stepItems.length && loaderContainer) {
                renderSteps(loaderContainer, stepItems, {
                  animated: true,
                  onComplete: function () {
                    var hasFail = stepItems.some(function (s) { return s.status === 'fail'; });
                    setUploadStep(host, hasFail ? 2 : 4);
                  },
                });
                return;
              }
            } catch (e) { /* ignore parse errors */ }
          }

          /* Fallback: advance steps with minimal delay */
          setUploadStep(host, 3);
          setTimeout(function () { setUploadStep(host, 4); }, 300);
        });
      }
    });
  }

  /* Export renderSteps for use by other modules */
  DTF.MultiStepLoader = {
    renderSteps: renderSteps,
    setUploadStep: setUploadStep,
    stepLabel: stepLabel,
    STATUS_ICONS: STATUS_ICONS,
  };

  if (DTF.registerEffect) {
    DTF.registerEffect('multi-step-loader', initMultiStepLoader);
  }
})();
