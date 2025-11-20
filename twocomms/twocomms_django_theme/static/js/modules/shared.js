// Shared utilities across frontend modules

export const DOMCache = {
  elements: {},
  computedStyles: new Map(),

  get(id) {
    if (!this.elements[id]) {
      this.elements[id] = document.getElementById(id);
    }
    return this.elements[id];
  },

  query(selector) {
    if (!this.elements[selector]) {
      this.elements[selector] = document.querySelector(selector);
    }
    return this.elements[selector];
  },

  queryAll(selector) {
    if (!this.elements[selector]) {
      this.elements[selector] = document.querySelectorAll(selector);
    }
    return this.elements[selector];
  },

  getComputedStyle(element, forceRefresh = false) {
    const key = element;
    if (!forceRefresh && this.computedStyles.has(key)) {
      return this.computedStyles.get(key);
    }

    const styles = window.getComputedStyle(element);
    this.computedStyles.set(key, styles);
    return styles;
  },

  clear() {
    this.elements = {};
    this.computedStyles.clear();
  },

  invalidate(selector) {
    if (selector) {
      delete this.elements[selector];
    } else {
      this.elements = {};
    }
    this.computedStyles.clear();
  }
};

export const prefersReducedMotion = (() => {
  try {
    return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  } catch (_) {
    return false;
  }
})();

export const PERF_LITE = (() => {
  try {
    return document.documentElement.classList.contains('perf-lite');
  } catch (_) {
    return false;
  }
})();

export function debounce(fn, wait) {
  let t;
  return function debounced(...args) {
    const ctx = this;
    clearTimeout(t);
    t = setTimeout(() => {
      requestAnimationFrame(() => fn.apply(ctx, args));
    }, wait);
  };
}

export function scheduleIdle(fn, timeout = 400) {
  try {
    if ('requestIdleCallback' in window) {
      return window.requestIdleCallback(fn, { timeout });
    }
  } catch (_) { }
  return setTimeout(fn, Math.min(timeout, 400));
}

let uiEventSeq = 0;
export const nextEvt = () => (++uiEventSeq);
export const nowTs = () => Date.now();

export function getCookie(name) {
  const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
  return match ? decodeURIComponent(match.pop()) : '';
}

export const noop = () => { };

export function escapeHtml(unsafe) {
  if (typeof unsafe !== 'string') return '';
  return unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
