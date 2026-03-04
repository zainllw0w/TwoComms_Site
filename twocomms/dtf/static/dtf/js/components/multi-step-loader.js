/**
 * Multi-step Loader
 * - Uses real backend file check when data-filecheck-url is provided
 * - No synthetic completion timers
 * - Shared between order and constructor flows
 */
(function () {
  'use strict';
  var DTF = (window.DTF = window.DTF || {});

  var STATUS_ICONS = {
    ok: '\u2713',
    pass: '\u2713',
    warn: '\u26A0',
    fail: '\u2717',
    loading: '\u21BB',
    pending: '\u2022',
  };

  var STEP_LABELS = {
    format_signature: { uk: 'Формат файлу', ru: 'Формат файла', en: 'File format' },
    dpi: { uk: 'DPI', ru: 'DPI', en: 'DPI' },
    physical_size_60cm: { uk: 'Розмір / 60 см', ru: 'Размер / 60 см', en: 'Size / 60 cm' },
    transparency_bounds: { uk: 'Прозорість / поля', ru: 'Прозрачность / поля', en: 'Transparency / safe area' },
    tiny_lines: { uk: 'Тонкі лінії / дрібний текст', ru: 'Тонкие линии / мелкий текст', en: 'Thin lines / tiny text' },
    summary: { uk: 'Результат перевірки', ru: 'Результат проверки', en: 'Check result' },
  };

  var STATUS_LABELS = {
    ok: { uk: 'Все добре', ru: 'Все хорошо', en: 'All good' },
    info: { uk: 'Є рекомендація', ru: 'Есть рекомендация', en: 'Recommendation' },
    warn: { uk: 'Потрібна увага', ru: 'Нужно внимание', en: 'Needs attention' },
    fail: { uk: 'Потрібна правка', ru: 'Нужна правка', en: 'Needs fix' },
    loading: { uk: 'Проводимо перевірку...', ru: 'Проводим проверку...', en: 'Running file check...' },
    pending: { uk: 'Очікує перевірки', ru: 'Ожидает проверки', en: 'Waiting for check' },
  };

  var UI_TEXT = {
    filecheck_running: {
      uk: 'Перевірка файлу виконується...',
      ru: 'Проверка файла выполняется...',
      en: 'File check is running...',
    },
    filecheck_failed: {
      uk: 'Перевірка файлу не виконана. Спробуйте ще раз.',
      ru: 'Проверка файла не выполнена. Попробуйте ещё раз.',
      en: 'File check failed. Please try again.',
    },
  };

  function getLang() {
    return ((document.documentElement.lang || 'uk').toLowerCase() || 'uk').slice(0, 2);
  }

  function stepLabel(key) {
    var lang = getLang();
    var labels = STEP_LABELS[key];
    if (!labels) return key || '';
    return labels[lang] || labels.uk || key;
  }

  function uiText(key) {
    var lang = getLang();
    var values = UI_TEXT[key] || {};
    return values[lang] || values.uk || values.en || key;
  }

  function statusLabel(status) {
    var lang = getLang();
    var labels = STATUS_LABELS[status] || STATUS_LABELS.pending;
    return labels[lang] || labels.uk || labels.en || status;
  }

  function getCsrfToken(host) {
    var input = host.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input && input.value) return input.value;
    var cookie = document.cookie.split('; ').find(function (row) {
      return row.indexOf('csrftoken=') === 0;
    });
    return cookie ? decodeURIComponent(cookie.split('=')[1]) : '';
  }

  function renderSteps(container, stepItems, options) {
    if (!container || !Array.isArray(stepItems)) return;
    var opts = options || {};
    var animated = !!opts.animated;
    container.innerHTML = '';
    container.classList.add('msl-active');

    stepItems.forEach(function (step, index) {
      var status = (step && step.status) ? String(step.status).toLowerCase() : 'pending';
      var row = document.createElement('div');
      row.className = 'msl-step msl-status-' + status;
      if (step && step.key) row.setAttribute('data-step-key', step.key);

      var icon = document.createElement('span');
      icon.className = 'msl-step-icon';
      icon.setAttribute('aria-hidden', 'true');
      icon.textContent = STATUS_ICONS[status] || STATUS_ICONS.pending;

      var label = document.createElement('span');
      label.className = 'msl-step-label';
      label.textContent = stepLabel(step.key || '') || step.label || '';

      var message = document.createElement('span');
      message.className = 'msl-step-message';
      message.textContent = '';

      var statusText = document.createElement('span');
      statusText.className = 'msl-step-message';
      statusText.textContent = statusLabel(status);

      row.appendChild(icon);
      row.appendChild(label);
      row.appendChild(statusText);
      row.appendChild(message);

      if (step.value) {
        var value = document.createElement('span');
        value.className = 'msl-step-value';
        value.textContent = step.value;
        row.appendChild(value);
      }

      if (animated) {
        row.style.opacity = '0';
        row.style.transform = 'translateY(8px)';
        window.setTimeout(function () {
          row.style.transition = 'opacity 220ms ease, transform 220ms ease';
          row.style.opacity = '1';
          row.style.transform = 'translateY(0)';
        }, index * 110);
      }

      container.appendChild(row);
    });
  }

  function setUploadStep(host, value) {
    if (!host) return;
    host.querySelectorAll('[data-upload-step]').forEach(function (chip) {
      var step = parseInt(chip.getAttribute('data-upload-step') || '0', 10);
      chip.classList.toggle('is-active', step === value);
      chip.classList.toggle('is-done', step < value);
    });
  }

  function deriveStepProgress(container) {
    if (!container) return 1;
    if (container.querySelector('.msl-status-fail')) return 2;
    if (container.querySelector('.msl-status-ok, .msl-status-pass, .msl-status-warn')) return 4;
    return 2;
  }

  function renderLoadingState(container) {
    if (!container) return;
    renderSteps(container, [
      {
        key: 'format_signature',
        status: 'loading',
        message: uiText('filecheck_running'),
      },
      {
        key: 'dpi',
        status: 'pending',
        message: '',
      },
      {
        key: 'physical_size_60cm',
        status: 'pending',
        message: '',
      },
      {
        key: 'transparency_bounds',
        status: 'pending',
        message: '',
      },
      {
        key: 'tiny_lines',
        status: 'pending',
        message: '',
      },
      {
        key: 'summary',
        status: 'pending',
        message: '',
      },
    ], { animated: false });
  }

  function initMultiStepLoader(host, ctx) {
    if (!host) return null;
    var reducedMotion = !!(ctx && ctx.reducedMotion);
    var input = host.querySelector('input[type="file"]');
    var loaderContainer = host.querySelector('.msl-container[data-filecheck-loader], .msl-container');
    var filecheckUrl = host.getAttribute('data-filecheck-url') || '';
    var listeners = [];
    var aborter = null;

    function on(el, evt, fn, opts) {
      el.addEventListener(evt, fn, opts || false);
      listeners.push([el, evt, fn, opts || false]);
    }

    function syncFromDom() {
      if (!input || !(input.files && input.files.length)) {
        setUploadStep(host, 1);
        return;
      }
      setUploadStep(host, deriveStepProgress(loaderContainer));
    }

    function requestFilecheck(file) {
      if (!filecheckUrl || !file || !loaderContainer) return;
      if (aborter) aborter.abort();
      aborter = (typeof AbortController !== 'undefined') ? new AbortController() : null;
      renderLoadingState(loaderContainer);
      var body = new FormData();
      body.append('file', file);
      body.append('csrfmiddlewaretoken', getCsrfToken(host));

      fetch(filecheckUrl, {
        method: 'POST',
        body: body,
        credentials: 'same-origin',
        headers: {
          'X-Requested-With': 'fetch',
          'X-CSRFToken': getCsrfToken(host),
        },
        signal: aborter ? aborter.signal : undefined,
      })
        .then(function (response) {
          if (!response.ok) {
            throw new Error('File check request failed');
          }
          return response.json();
        })
        .then(function (payload) {
          if (!payload || !payload.ok || !payload.report) {
            throw new Error('Invalid file check payload');
          }
          var stepItems = payload.report.step_items || [];
          if (!stepItems.length) {
            throw new Error('No file check steps returned');
          }
          renderSteps(loaderContainer, stepItems, { animated: !reducedMotion });
          setUploadStep(host, deriveStepProgress(loaderContainer));
        })
        .catch(function (error) {
          if (error && error.name === 'AbortError') return;
          renderSteps(loaderContainer, [
            {
              key: 'summary',
              status: 'fail',
              message: uiText('filecheck_failed'),
            },
          ], { animated: false });
          setUploadStep(host, 2);
        });
    }

    syncFromDom();

    if (input) {
      on(input, 'change', function () {
        if (!input.files || !input.files.length) {
          if (aborter) aborter.abort();
          setUploadStep(host, 1);
          return;
        }
        setUploadStep(host, 2);
        requestFilecheck(input.files[0]);
      });
    }

    on(host, 'dtf:filecheck-ready', function (event) {
      var detail = event && event.detail ? event.detail : {};
      var steps = detail.stepItems || [];
      if (!steps.length || !loaderContainer) return;
      renderSteps(loaderContainer, steps, { animated: !reducedMotion });
      setUploadStep(host, deriveStepProgress(loaderContainer));
    });

    return function cleanup() {
      if (aborter) aborter.abort();
      listeners.forEach(function (entry) {
        entry[0].removeEventListener(entry[1], entry[2], entry[3]);
      });
      listeners.length = 0;
    };
  }

  DTF.MultiStepLoader = {
    renderSteps: renderSteps,
    setUploadStep: setUploadStep,
    stepLabel: stepLabel,
    STATUS_ICONS: STATUS_ICONS,
  };

  if (DTF.registerEffect) {
    DTF.registerEffect('multi-step-loader', '[data-upload-flow], [data-effect~="multi-step-loader"]', initMultiStepLoader);
  }
})();
