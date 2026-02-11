/**
 * Floating Dock
 * - Desktop global dock with macOS-like magnification
 * - Constructor local dock with file actions + badge state
 * - Unified visibility contract (desktop only, hide near footer and overlays)
 */
(function () {
  'use strict';
  var DTF = (window.DTF = window.DTF || {});

  var DESKTOP_QUERY = '(min-width: 961px)';
  var FINE_POINTER_QUERY = '(hover: hover) and (pointer: fine)';
  var MAGNIFY_DISTANCE = 170;
  var MAGNIFY_SCALE = 1.82;
  var MAGNIFY_LIFT = 14;
  var HIDDEN_PAGES = {
    order: true,
    constructor: true,
    'constructor-app': true,
  };

  function prefersReduced() {
    return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  function isDesktop() {
    return !!(window.matchMedia && window.matchMedia(DESKTOP_QUERY).matches);
  }

  function hasFinePointer() {
    return !!(window.matchMedia && window.matchMedia(FINE_POINTER_QUERY).matches);
  }

  function initDockTooltip(item) {
    if (!item || item.querySelector('.dock-tooltip')) return;
    var title = item.getAttribute('data-dock-title') || item.getAttribute('aria-label') || '';
    if (!title) return;
    var tooltip = document.createElement('span');
    tooltip.className = 'dock-tooltip';
    tooltip.textContent = title;
    tooltip.setAttribute('aria-hidden', 'true');
    item.appendChild(tooltip);
  }

  function clearMagnify(items) {
    items.forEach(function (item) {
      item.style.setProperty('--dock-item-scale', '1');
      item.style.setProperty('--dock-item-lift', '0px');
    });
  }

  function applyMagnify(items, x) {
    items.forEach(function (item) {
      var rect = item.getBoundingClientRect();
      var cx = rect.left + rect.width / 2;
      var distance = Math.abs(x - cx);
      var ratio = distance >= MAGNIFY_DISTANCE ? 0 : 1 - (distance / MAGNIFY_DISTANCE);
      var eased = ratio * ratio;
      var scale = 1 + eased * (MAGNIFY_SCALE - 1);
      var lift = eased * MAGNIFY_LIFT;
      item.style.setProperty('--dock-item-scale', scale.toFixed(3));
      item.style.setProperty('--dock-item-lift', (-lift).toFixed(2) + 'px');
    });
  }

  function initGlobalDock(dock, items, listeners, observers) {
    var footerSelector = dock.getAttribute('data-hide-near-footer') || '[data-footer-anchor]';
    var footer = document.querySelector(footerSelector);
    var nearFooter = false;

    function on(el, evt, fn, opts) {
      el.addEventListener(evt, fn, opts || false);
      listeners.push([el, evt, fn, opts || false]);
    }

    function sync() {
      var body = document.body;
      var page = body && body.dataset ? body.dataset.page : '';
      var modalOpen = !!(
        body && (
          body.classList.contains('is-modal-open') ||
          body.classList.contains('is-drawer-open') ||
          body.classList.contains('is-profile-open')
        )
      );
      var shouldHide = !isDesktop() || modalOpen || nearFooter || !!HIDDEN_PAGES[page];
      dock.classList.toggle('dock-hidden', shouldHide);
      dock.classList.toggle('dock-scrolled', (window.scrollY || 0) > 120);
      if (!shouldHide) dock.classList.add('dock-ready');
    }

    if (footer && 'IntersectionObserver' in window) {
      var footerObserver = new IntersectionObserver(
        function (entries) {
          entries.forEach(function (entry) {
            nearFooter = !!entry.isIntersecting;
            sync();
          });
        },
        { threshold: 0, rootMargin: '0px 0px 130px 0px' }
      );
      footerObserver.observe(footer);
      observers.push(footerObserver);
    }

    if (!prefersReduced() && hasFinePointer()) {
      on(dock, 'mousemove', function (event) {
        applyMagnify(items, event.clientX);
      });
      on(dock, 'mouseleave', function () {
        clearMagnify(items);
      });
    } else {
      clearMagnify(items);
    }

    on(window, 'scroll', sync, { passive: true });
    on(window, 'resize', sync, { passive: true });
    on(document, 'visibilitychange', sync);
    sync();
  }

  function setBadgeState(badge, status, count, previewUrl) {
    if (!badge) return;
    var normalized = status || 'pending';
    badge.className = 'dock-badge badge-' + normalized + (previewUrl ? ' badge-has-preview' : '');
    badge.textContent = count > 1 ? String(count) : '';
    badge.hidden = count <= 0;
    if (previewUrl) {
      badge.style.setProperty('--badge-preview', 'url("' + previewUrl + '")');
    } else {
      badge.style.removeProperty('--badge-preview');
    }
  }

  function collectPreflightStatus(scope) {
    if (!scope) return 'pending';
    var steps = scope.querySelectorAll('.constructor-preflight-card .msl-step');
    if (!steps.length) return 'pending';
    var hasFail = false;
    var hasWarn = false;
    var hasOk = false;
    steps.forEach(function (step) {
      var className = step.className || '';
      if (className.indexOf('msl-status-fail') >= 0) hasFail = true;
      if (className.indexOf('msl-status-warn') >= 0) hasWarn = true;
      if (className.indexOf('msl-status-ok') >= 0 || className.indexOf('msl-status-pass') >= 0) hasOk = true;
    });
    if (hasFail) return 'fail';
    if (hasWarn) return 'warn';
    if (hasOk) return 'ok';
    return 'pending';
  }

  function clearFileInput(input) {
    if (!input) return;
    try {
      input.value = '';
      if (typeof DataTransfer !== 'undefined') {
        input.files = new DataTransfer().files;
      }
    } catch (err) {
      input.value = '';
    }
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function initConstructorDock(dock, listeners, observers) {
    var scope = dock.closest('[data-ui="dtf:constructor:layout"]') || document;
    var builderForm = scope.querySelector('[data-constructor-builder-form]') || document.getElementById('constructor-builder-form');
    var submitForm = scope.querySelector('[data-constructor-submit]') || document.getElementById('constructor-submit-form');
    var fileInput = builderForm && (
      builderForm.querySelector('input[type="file"][name$="design_file"]') ||
      builderForm.querySelector('input[type="file"][name="design_file"]')
    );
    var badge = dock.querySelector('.dock-badge');
    var actionButtons = dock.querySelectorAll('[data-action]');
    var previewUrl = '';

    function on(el, evt, fn, opts) {
      el.addEventListener(evt, fn, opts || false);
      listeners.push([el, evt, fn, opts || false]);
    }

    function revokePreviewUrl() {
      if (!previewUrl) return;
      try {
        URL.revokeObjectURL(previewUrl);
      } catch (err) {
        // no-op
      }
      previewUrl = '';
    }

    function refreshBadgeFromState() {
      if (!badge || !fileInput) return;
      var count = fileInput.files ? fileInput.files.length : 0;
      if (!count) {
        revokePreviewUrl();
        setBadgeState(badge, 'pending', 0, '');
        return;
      }
      var status = collectPreflightStatus(scope);
      if (status === 'pending') status = 'pending';
      setBadgeState(badge, status, count, previewUrl);
    }

    function refreshBadgeFromInput() {
      if (!badge || !fileInput) return;
      revokePreviewUrl();
      var count = fileInput.files ? fileInput.files.length : 0;
      if (count === 0) {
        setBadgeState(badge, 'pending', 0, '');
        return;
      }
      var file = fileInput.files[0];
      if (file && file.type && file.type.indexOf('image/') === 0) {
        try {
          previewUrl = URL.createObjectURL(file);
        } catch (err) {
          previewUrl = '';
        }
      }
      setBadgeState(badge, 'pending', count, previewUrl);
    }

    actionButtons.forEach(function (button) {
      initDockTooltip(button);
      on(button, 'click', function (event) {
        event.preventDefault();
        var action = button.getAttribute('data-action');
        if (action === 'upload' && fileInput) {
          fileInput.click();
          return;
        }
        if (action === 'clear') {
          clearFileInput(fileInput);
          return;
        }
        if (action === 'check' && builderForm) {
          if (builderForm.requestSubmit) builderForm.requestSubmit();
          else builderForm.submit();
          return;
        }
        if (action === 'submit' && submitForm) {
          if (submitForm.requestSubmit) submitForm.requestSubmit();
          else submitForm.submit();
        }
      });
    });

    if (fileInput) {
      on(fileInput, 'change', function () {
        refreshBadgeFromInput();
      });
      refreshBadgeFromInput();
    }

    var preflightPanel = scope.querySelector('.constructor-preflight-card');
    if (preflightPanel && typeof MutationObserver !== 'undefined') {
      var mutationObserver = new MutationObserver(function () {
        refreshBadgeFromState();
      });
      mutationObserver.observe(preflightPanel, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['class'],
      });
      observers.push(mutationObserver);
    }

    dock.classList.add('dock-ready');
    return function cleanupConstructorDock() {
      revokePreviewUrl();
    };
  }

  function initFloatingDock(dock, ctx) {
    if (!dock) return null;

    var listeners = [];
    var observers = [];
    var cleanupFns = [];
    var items = Array.prototype.slice.call(dock.querySelectorAll('.dock-item, a, button'));
    var isConstructor = dock.getAttribute('data-dock-type') === 'constructor';

    items.forEach(initDockTooltip);
    clearMagnify(items);

    if (isConstructor) {
      var cleanup = initConstructorDock(dock, listeners, observers);
      if (typeof cleanup === 'function') cleanupFns.push(cleanup);
    } else {
      initGlobalDock(dock, items, listeners, observers);
    }

    return function cleanup() {
      listeners.forEach(function (entry) {
        entry[0].removeEventListener(entry[1], entry[2], entry[3]);
      });
      listeners.length = 0;
      observers.forEach(function (observer) {
        if (!observer) return;
        if (typeof observer.disconnect === 'function') observer.disconnect();
      });
      observers.length = 0;
      cleanupFns.forEach(function (fn) {
        try {
          fn();
        } catch (err) {
          // no-op
        }
      });
      cleanupFns.length = 0;
      clearMagnify(items);
    };
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('floating-dock', '[data-floating-dock]', initFloatingDock);
  }
})();
