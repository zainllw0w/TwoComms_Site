(function () {
  const DTF = (window.DTF = window.DTF || {});

  function qs(root, sel) {
    if (!root || !sel) return null;
    return root.querySelector(sel);
  }

  function qsa(root, sel) {
    if (!root || !sel) return [];
    return Array.from(root.querySelectorAll(sel));
  }

  function on(el, evt, fn, opts) {
    if (!el || !evt || typeof fn !== 'function') return function noop() {};
    el.addEventListener(evt, fn, opts);
    return function unsubscribe() {
      try {
        el.removeEventListener(evt, fn, opts);
      } catch (err) {
        // No-op.
      }
    };
  }

  function rafThrottle(fn) {
    if (typeof fn !== 'function') return function noop() {};
    let rafId = null;
    let nextArgs = null;
    return function throttled() {
      nextArgs = arguments;
      if (rafId !== null) return;
      rafId = window.requestAnimationFrame(() => {
        rafId = null;
        fn.apply(null, nextArgs);
      });
    };
  }

  function clamp(v, a, b) {
    return Math.min(b, Math.max(a, v));
  }

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  function inViewportObserver(callback, options) {
    if (!('IntersectionObserver' in window) || typeof callback !== 'function') return null;
    return new IntersectionObserver(callback, options || { threshold: 0.1 });
  }

  function prefersReducedMotion() {
    if (document.documentElement && document.documentElement.dataset.labReducedMotion === '1') {
      return true;
    }
    return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  function isCoarsePointer() {
    if (document.documentElement && document.documentElement.dataset.labCoarsePointer === '1') {
      return true;
    }
    return !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches);
  }

  function oncePerEl(el, key) {
    if (!el || !key) return false;
    const safeKey = String(key).replace(/[^a-z0-9-]/gi, '-').toLowerCase();
    const attrName = `data-init-${safeKey}`;
    if (el.getAttribute(attrName) === '1') return false;
    el.setAttribute(attrName, '1');
    return true;
  }

  DTF.utils = {
    qs,
    qsa,
    on,
    rafThrottle,
    clamp,
    lerp,
    inViewportObserver,
    prefersReducedMotion,
    isCoarsePointer,
    oncePerEl,
  };
})();
